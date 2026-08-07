# BUG-160/161/162/163 — Turn-Coordinator-Adjacent Fallback Authority Planning Gate

**תאריך:** 07/08/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
(§7) — כל מסמך Planning Gate הנוגע ב-reasoning/routing/tools/actions/approvals/execution
חייב לפתוח בהפניה מפורשת לשער הזה ולא להתקדם בלי Cross-Layer Impact Matrix מלא
(§2 שם). Baseline: `main` `e54f9f0` (07/08/2026).
**היקף:** ארבעת הבאגים נפתחו יחד באותו סבב אימות (Turn Coordinator E2E,
07/08/2026, ראו `BUG_AUDIT_LOG.md`) — BUG-160 היה קיים ורשום עוד לפני
הסבב הזה (staging validation, 03-07/08/2026) אך נשכח מהמטריצה בכתיבה
הראשונה; ה-owner ביקש במפורש לתקן זאת ("שכחתי את באג 160 בתוך הלייר")
ולפתוח את המטריצה עבור **ארבעתם** יחד, לא לדחות אף אחד בנפרד — גם אם
רמת-המימוש שלהם שונה (ראו §0 למטה). כל ארבעת הבאגים שייכים לאותה שרשרת
תצפית אחת: BUG-160 הוא ה-trigger הקונקרטי (מרכאה לא-מאוזנת מפילה
create_task למסלול Agent) שממנו נחשפו BUG-161/162 (מה ה-Agent עושה
כשהוא מגיע לשם) — BUG-163 נתגלה בנפרד, באותו סבב, בתרחישי update/complete
task.

---

## 0. סטטוס מימוש בפועל של כל אחד מארבעת הבאגים (לפני המטריצה)

| באג | מדיניות הוכרעה? | קוד שונה בסבב הזה? | סטטוס אחרי הסבב |
|---|---|---|---|
| **BUG-160** | לא נדרשה — תיקון parser צר | ✅ כן — `core/router/router.py` | 🟢 מומש, בדוק |
| **BUG-163** | לא נדרשה — תיקון parser צר | ✅ כן — `core/router/intent_router.py` | 🟢 מומש, בדוק |
| **BUG-161** | ✅ כן (owner, 07/08/2026 — אופציה א') | ✅ חלקית — `core_knowledge.py` (system-prompt honesty rule) | 🟡 מומש חלקית — ראה §0.2 למגבלה |
| **BUG-162** | ❌ לא — מנגנון ה-enforcement עצמו עדיין לא הוכרע | ❌ לא | 🔴 עדיין PLANNING BLOCKED על החלטת owner נפרדת |

### 0.0 BUG-160 — מה בדיוק מומש

`core/router/router.py::_normalize_create_task_input()` — לפני התיקון,
זוג-מרכאות/סוגריים הוסר **רק** אם גם הפתיחה וגם הסגירה קיימות
(`value.startswith(opening) and value.endswith(closing)`). מרכאה פותחת
בודדת ללא סוגרת תואמת (למשל `"צור משימה ... 14:54` — התחלה עם `"`, בלי
`"` נוסף בהמשך כלל) נשארה לעולם לא-מוסרת, ושברה את
`_STRUCTURED_CREATE_TASK_RE.fullmatch()` (דורש שהמחרוזת תתחיל ישירות
בפועל-הטריגר) — נפילה שקטה למסלול Agent, בדיוק כמו BUG-159 אך מסיבה
שונה (פיסוק, לא צורת-פועל).

**התיקון:** נוסף מקרה שלישי, צר, ללולאת ה-strip הקיימת והחסומה
(`for _ in range(4)`): אם הערך מתחיל בתו-פתיחה מתוך `_CREATE_TASK_QUOTE_
PAIRS` **וה-תו-הסגירה התואם לא מופיע בשום מקום בהמשך המחרוזת** — מוסר
**רק** תו-הפתיחה הבודד (לא מניחים סגירה-שקיימת-איפשהו ומורידים גם
אותה). אם תו-הסגירה **כן** מופיע במקום כלשהו (רק לא בדיוק בסוף) — הצורה
נשארת מכוונת-לא-ברורה ולא-מטופלת, בדיוק כמו לפני התיקון (אין stripping
חדש למקרה עמום). מאומת ב-`test_bug160_unbalanced_quote_create_task.py`
(15/15) — כולל בדיקה מפורשת שהמקרה העמום (`"say hi" צור משימה...`)
נשאר לא-תואם, ושכל ה-stripping הקיים (זוגות מאוזנים, `>`, `Eli:`/`אלי:`)
לא השתנה.

**חשוב להיות מדויקים (אותה הערה כמו BUG-163):** זה מתקן פרסור/נירמול
בלבד — לא נוגע ב-`Handler`/authority. הבקשה שהייתה נופלת בעבר ל-Agent
בגלל המרכאה השבורה עכשיו מגיעה ל-`Handler.TOOL` **הקיים כבר** ל-
`CREATE_TASK` (`router.py:234-239`, לא שונה כאן) — משלים תיקון-parser,
לא פותח נתיב-authority חדש.

### 0.1 BUG-163 — מה בדיוק מומש

`core/router/intent_router.py`'s `COMPLETE_TASK` rule הורחב בשני צעדים
צרים:
1. נוסף הפועל `השלם` לקבוצת-הפעלים הקיימת (verb-then-target, אין שינוי
   מבני).
2. נוספה תבנית שנייה, נפרדת, ל-`COMPLETE_TASK`: `(סמן|mark).{0,40}(משימ|
   טאסק|task).{0,20}(כבוצע|בוצעה|done|complete)` — ממוקדת ל-"סמן"/"mark"
   בלבד (לא כל אזכור משותף של "משימה"+"בוצע" במשפט), כדי לא להתנגש עם
   `LIST_TASKS` ("אילו משימות כבר בוצעו"). מאומת ב-`test_bug163_
   complete_task_intent_coverage.py` (12/12), כולל בדיקת אי-התנגשות עם
   `LIST_TASKS` במפורש.

**חשוב להיות מדויקים:** זה מתקן את **סיווג ה-intent** בלבד. זה **לא**
נותן `Handler.TOOL` דטרמיניסטי ל-`COMPLETE_TASK`/`UPDATE_TASK` — הפער הזה
הוא PA-01 (`docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md`,
עדיין PLANNING ONLY, לא נוגע בסבב הזה כלל). כלומר: בקשות שהיו נופלות
ל-`intent=unknown handler=agent` עכשיו נופלות ל-`intent=complete_task
handler=agent` — עדיין `Handler.AGENT`, לא `Handler.TOOL`. השיפור הוא
שה-Agent (ושכל telemetry/logging במורד-הזרם) רואה עכשיו intent נכון,
לא `unknown` — לא שינוי-authority.

### 0.2 BUG-161 — מה מומש, ומה עדיין תלוי ב-BUG-162

**מה מומש:** כלל-כנות חדש ב-`core_knowledge.py`'s `STATIC_MANIFEST`
(אותו בלוק "חוקי כנות — אסור לעבור עליהם" שכבר מכיל את הכלל הקיים
"אישור = כפתורי Telegram בלבד. אל תכתוב 'אשר עם ✅/❌' בטקסט"):

```text
🔴 פעולה שכבר בוטלה/נדחתה → אסור להציע "אשר בבירור"/reconfirmation
בטקסט חופשי — אין מנגנון כזה, וניסיון בפועל ייחסם. תשובה נכונה: ציין
שהפעולה בוטלה, והפנה לשליחת בקשה חדשה ומפורשת (למשל "צור משימה ...").
```

זו בדיוק אותה קטגוריית-תיקון כמו הכלל הקיים לצידו — מניעת Agent
מ**להמציא** מנגנון-אישור/reconfirmation שלא קיים בפועל בקוד.

**למה זו רמת-הסיכון הנכונה (ולא regex/code-level classifier):** ה"הבטחה
המזויפת" (`"אם אתה רוצה ליצור משימה זו בכל זאת — אנא אשר זאת בבירור."`)
היא טקסט חופשי שה-Agent חיבר **לפני** כל tool_use — אין תוצאת-כלי לבדוק
מולה. ניסיון לתפוס תבנית-משפט כזו ב-regex/classifier הוא **בדיוק** אותה
קטגוריית-בעיה ש-`BUG-127C` כבר חקר עד הסוף וקבע במפורש: "A32/regex הוא
כנראה השכבה הלא-נכונה לתיקון" עבור הבחנות סמנטיות מהסוג הזה. לכן התיקון
כאן הוא ברמת ה-system prompt (מניעה מלכתחילה), לא ברמת סינון-פלט
(שהיה חוזר על הטעות שכבר תועדה ונדחתה ב-BUG-127C).

**ה-backstop הדטרמיניסטי הקיים לא שונה, ואומת שהוא תקין:**
`core/action_gateway.py:1622-1643` — הבלוק שחוסם `propose_action()` כש-
`existing.status == "rejected" and trusted_source != "deterministic_
create_task"` — **לא נגע בו קוד בסבב הזה**. `build_approval_lifecycle_
result(existing, canonical_state="rejected", repeated=True)`'s ההודעה
("יצירת המשימה כבר בוטלה") אומתה ישירות (`test_bug161_agent_no_
reconfirmation_promise.py`) כאמיתית ולא-ממציאה, ועם `reply_owner="gateway"`.

**המגבלה שנשארת פתוחה — תלות ישירה ב-BUG-162:** `reply_owner="gateway"`
על תוצאת ה-block הזו הוא היום **shadow-בלבד** — בדיוק כמו שתועד ב-BUG-162:
שום דבר לא אוכף בפועל שהתשובה-למשתמש תהיה `safe_user_message` ולא טקסט
עצמאי שה-Agent מחבר סביב תוצאת ה-tool. כלומר: גם עם כלל-הכנות החדש
(שאמור למנוע את ה-**הבטחה המוקדמת**, לפני tool_use), **אם** ה-Agent בכל
זאת ינסה tool_use נגד fingerprint שנדחה ויחבר טקסט-משלו סביב תוצאת ה-
block — אין היום אכיפה שתמנע ממנו "לדבר" ב-turn שאמור להיות gateway-owned.
**BUG-161 נשאר 🟡, לא 🟢**, בדיוק בגלל התלות הזו — סגירה מלאה תלויה
בהחלטת-enforcement של BUG-162.

### 0.3 BUG-162 — למה אין כאן קוד, ומה עדיין דרוש

כפי שכבר תועד ב-`BUG_AUDIT_LOG.md`: כיוון-המדיניות ניתן (אותה החלטה
שהורחבה מ-BUG-161 — "לצמצם סמכויות הסוכן, לא להרחיב... לא תילקח בעלות
שלא כדין"), אבל **מנגנון ה-enforcement הקונקרטי** (מה בדיוק קורה כש-Agent
"רוצה לדבר" ב-turn `reply_owner=gateway`: silence? clarify? redirect
אוטומטי לגייטווי?) **עדיין לא הוכרע**. המטריצה למטה ממלאת את השדות
הנדרשים **לתכנון** (כדי שהשער לא יהיה `PLANNING BLOCKED` על "לא מולאה
מטריצה" כשתבוא ההחלטה), אבל **אינה** תחליף להחלטת-owner מפורשת על מנגנון
ה-enforcement — ראו §6 (אכיפה) ב-`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`:
מטריצה מלאה מסירה את חסם "אין מטריצה", לא את הדרישה להחלטה עצמה.

---

## 1. Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
**touched: not touched.**
1. **grep evidence:** `git diff -- core/router/router.py core/router/intent_router.py core_knowledge.py | grep -c "BUG-104\|leads_reasoning_projection\|FEATURE_CORE_REASONING_LEADS_STATE"` → **0**.
2. **unchanged-tests evidence:** `test_bug104_*.py` (5 חבילות) לא נוגעות
   בשום קובץ ששונה בסבב הזה — לא הורצו כי אין תלות; `smoke_tests.py`
   (הכולל import-sanity לכל המודולים) ירוק לפני ואחרי.
3. **no-new-coupling evidence:** אין `import` חדש ל-`core.leads_reasoning_
   projection`/`core.adapters.leads_adapter` באף אחד משלושת הקבצים ששונו.

### שכבה 2 — TurnCoordinator (de-facto: `router.py::route_request()` + `intent_router.py` + Agent free-text, per `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §1 שכבה 2)
**touched: directly** (BUG-160 — `router.py::_normalize_create_task_input()`,
נצרך ישירות ע"י `parse_deterministic_create_task()`→`route_request()`)
**וגם directly** (BUG-163 — `intent_router.py`, נצרך ישירות ע"י
`router.py:193`'s `detect_intent(text)`) **וגם directly** (BUG-161 —
`core_knowledge.py`, קובע את הטקסט שה-Agent מייצר בזמן ש-Handler.AGENT
הוא בעל ה-turn).
- **input impact:** BUG-160 — אותו `text` input ל-`_normalize_create_task_
  input()`, אין שינוי סוג/מקור/סמנטיקה — רק הרחבת מקרה-strip נוסף, צר.
  BUG-163 — אותו `text` input ל-`detect_intent()`, אין שינוי סוג/מקור/
  סמנטיקה של signal — רק הרחבת כיסוי-regex. BUG-161 — אין input חדש;
  system prompt static, לא תלוי ב-per-turn state.
- **output impact:** BUG-160 — `parse_deterministic_create_task().certain`
  עובר `False→True` (ו-`Handler.TOOL` **הקיים כבר** ל-`CREATE_TASK` נבחר
  בפועל, לא נוצר) רק למחרוזות עם מרכאה/סוגריים פותחים בלתי-מאוזנים
  שהתו-הסוגר שלהם לא מופיע בשום מקום אחר במחרוזת. BUG-163 — `route.intent`
  עכשיו `complete_task` (היה `unknown`) לשתי הניסוחים החדשות בלבד;
  `route.handler` **לא** משתנה (נשאר `Handler.AGENT` — PA-01's גap לא
  נסגר כאן, ראה §0.1). BUG-161 — אין output-signal חדש; רק תוכן הטקסט
  שה-Agent עשוי לחבר.
- **authority impact:** **אין לאף אחד מהשלושה.** BUG-160 לא יוצר נתיב-
  authority חדש — `Handler.TOOL` ל-`CREATE_TASK` כבר קיים ומוגדר
  (`router.py:234-239`, לא שונה), רק מספר יותר בקשות מגיעות אליו בפועל.
  BUG-163 לא נותן `Handler.TOOL` לאף intent חדש. BUG-161 לא משנה מי
  מחליט `reply_owner` (זה עדיין shadow-only, ללא אכיפה — ראה §0.2).
- **shared identifiers:** `Intent.CREATE_TASK`/`Intent.COMPLETE_TASK`/
  `Intent.UPDATE_TASK` — נצרכים, לא מוגדרים-מחדש. אין identifier חדש
  נוסף בשכבה הזו.
- **invariants:** "ספציפי לפני כללי" (סדר ה-`_RULES` list, ל-BUG-163)
  נשמר — הכללים החדשים נוספו ליד הכלל הקיים של `COMPLETE_TASK`, עדיין
  לפני `DELETE_TASK`/`LIST_TASKS`; מאומת ב-regression (`LIST_TASKS` על
  "אילו משימות כבר בוצעו" עדיין נכון, לא נחטף ע"י התבנית החדשה).
  BUG-160's invariant: stripping חד-צדדי קורה **רק** כשאין תו-סגירה
  תואם בשום מקום אחר במחרוזת — מקרה עמום (סוגר מופיע, לא בסוף) נשאר
  לא-מטופל, אין הרחבת-כיסוי-יתר; מאומת ישירות בטסט (`"say hi" צור
  משימה...` נשאר unmatched).
- **failure semantics:** ללא שינוי-חומרה בשני המקרים. BUG-160 — worst
  case: מחרוזת עם מרכאה-פותחת-בלתי-מאוזנת שהייתה נופלת ל-Agent ממשיכה
  ליפול ל-Agent אם התו-הסוגר כן מופיע איפשהו (מקרה עמום, לא מטופל
  בכוונה) — שום מחרוזת חדשה לא מתחילה "לזלוג" תוכן שלא היה חלק מהכותרת
  המקורית. BUG-163 — סיווג-שגוי היפותטי של intent עדיין נופל ל-
  `Handler.AGENT` (בדיוק כמו `unknown` היה נופל) — אין נתיב `Handler.TOOL`
  חדש שסיווג שגוי יכול "לפתוח" בטעות (PA-01 עדיין לא קיים). ה-blast
  radius חסום כרגע בבנייה, לא בזכות התיקון הזה.
- **observability:** BUG-160 — `route.to_log()`'s `handler=tool
  intent=create_task` (היה `handler=agent`) למחרוזות עם מרכאה-בלתי-
  מאוזנת שהתו-הסוגר שלהן לא מופיע בהמשך — נראה בלוג הקיים, אין שדה
  חדש. BUG-163 — `route.to_log()`'s `intent=complete_task` (היה
  `unknown`) לשתי הניסוחים החדשות — נראה בלוג הקיים, אין שדה חדש.
- **cross-layer tests:** `test_bug160_unbalanced_quote_create_task.py`
  (15/15, כולל בדיקת שהמקרה העמום נשאר unmatched ושה-stripping הקיים
  לא השתנה) + `test_bug163_complete_task_intent_coverage.py` (12/12,
  כולל בדיקת אי-התנגשות מפורשת עם `LIST_TASKS`) + `core/router/
  test_router.py` (44/44, ללא regression) + `test_bug153_create_task_
  reconfirmation_after_rejection.py` (16/16, ללא regression) +
  `test_bug159_create_task_noun_form_and_verbs.py` (52/52, ללא
  regression) + `test_hotfix_c_create_task_verb.py` (12/12, ללא
  regression) + `test_bug161_agent_no_reconfirmation_promise.py` (7/7
  — מוודא את מיקום/ניסוח כלל-הכנות + את תקינות ה-Gateway backstop
  שהכלל נשען עליו).

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
**touched: not touched.**
1. **grep evidence:** `git diff -- core/router/router.py core/router/intent_router.py core_knowledge.py | grep -c "ToolMeta\|tool_registry\|dispatch_tool\|action_validator\|tools/schemas\|tools\.dispatcher"` → **0**.
2. **unchanged-tests evidence:** לא נוגע ב-`tool_registry.py`/`tools/
   dispatcher.py`/`action_validator.py` — אין נתיב שיכול לשבור טסטים של
   השכבה הזו; `smoke_tests.py`'s "Tool registry / dispatcher sanity"
   ירוק לפני ואחרי.
3. **no-new-coupling evidence:** אין `import` חדש ממודול בשכבה 3.

### שכבה 4 — Durable Atomic Approval
**touched: indirectly** (BUG-161 בלבד; BUG-160/163 לא נוגעים כלל — BUG-160
משנה רק את סיווג ה-parser, לא נוגע ב-ActionContract/Gateway; מאומת
ב-grep מתחת).
- **grep evidence (זיהוי):** `git diff -- core/router/router.py core/router/intent_router.py core_knowledge.py | grep -c "ActionContract\|ActionGateway\|action_gateway\.py\|propose_action"` → **0** — כלומר **אין** קריאה/הפניה **ישירה בקוד** לזהויות של שכבה 4, בשום אחד משלושת הקבצים ששונו. הנגיעה (של BUG-161 בלבד) היא **התנהגותית**, לא-מזוהה ב-grep, ולכן חייבת להיות מתועדת במפורש כאן (לא רק "0 → not touched"):
- **input impact:** אין — `core_knowledge.py`'s prompt לא קורא ל-Gateway.
- **output impact:** אין ישיר — אבל כלל-הכנות **מניח (assumes)** שהתנהגות
  ה-block הקיימת ב-`core/action_gateway.py:1622-1643`
  (`existing.status=="rejected" and trusted_source!="deterministic_
  create_task"` → block עם `build_approval_lifecycle_result(...,
  canonical_state="rejected", repeated=True)`) **ממשיכה להתקיים בדיוק
  כמו שהיא היום**. זו תלות סמנטית חדשה (prompt↔Gateway-behavior), לא
  code coupling.
- **authority impact:** אין — הכלל לא נותן ל-Agent שום סמכות חדשה, הוא
  **מצמצם** מה שה-Agent מרשה לעצמו להבטיח בטקסט חופשי — עקבי עם החלטת
  ה-owner "לצמצם סמכויות, לא להרחיב".
- **shared identifiers:** אין collision — `ActionContract`/`ActionGateway`
  לא מוזכרים בשם בפרומפט (הפרומפט מדבר בעברית עסקית, "פעולה שכבר בוטלה",
  לא במונחי-מחלקה).
- **invariants חדש שנוצר (must-track):** אם `build_approval_lifecycle_
  result()`'s ניסוח ל-`canonical_state="rejected", repeated=True` ישתנה
  אי-פעם (למשל מפסיק לומר "בוטלה" בפירוש), כלל-הכנות בפרומפט **וה-backstop
  בפועל עלולים להתפצל** — התלות הזו **לא** נאכפת אוטומטית ע"י שום מנגנון
  קיים, רק ע"י `test_bug161_agent_no_reconfirmation_promise.py`'s
  assertion הישירה על `result.safe_user_message`. אם הטסט הזה יוסר/ישונה
  בלי לבדוק מול הפרומפט — הפער הזה עלול לחזור בשקט.
- **failure semantics:** ללא שינוי — ה-Gateway block עצמו (הגנת-האמת
  הדטרמיניסטית) לא שונה; אם ה-Agent "יתעלם" מהכלל בפרומפט (מודל לא
  תמיד צייתן ל-100% לכללי-פרומפט), ה-Gateway עדיין חוסם כל tool_use
  אמיתי — ה-worst-case נשאר "Agent מדבר טקסט לא-מדויק ב-turn ש-reply_owner
  שלו gateway", בדיוק תרחיש BUG-162 — לא נזק חדש, נזק **קיים** שהתיקון
  הזה לא סוגר לגמרי (ראה §0.2).
- **observability:** אין חדש — אין דרך live-log להבחין "הכלל בפרומפט
  מנע הבטחה" מ"לא הייתה סיבה להבטיח מלכתחילה" — מגבלה מוכרת, לא נפתרת
  כאן.
- **cross-layer tests:** `test_bug161_agent_no_reconfirmation_promise.py`
  — הטסט היחיד שגוזר קשר מפורש בין תוכן-הפרומפט (שכבה 2) לבין תוכן
  ההודעה בפועל שה-Gateway (שכבה 4) מחזיר לאותו תרחיש — ממש ה-"cross-layer
  test" שה-contract דורש. **אין** טסט חי-מודל (LLM behavior) שמאמת
  שה-Agent בפועל נמנע מהניסוח — לא ניתן לממש סטטית, מגבלה מוצהרת (§0.2).

---

## 2. Cross-Cutting Guard — RP5 Evidence Finalization (§1.5 ב-`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`)

**applies: yes**, ל-BUG-161 בלבד. BUG-160/163 (שניהם פרסור/סיווג גרידא,
לפני כל tool_use/evidence) — **לא applies**, `grep` על diff-160/163 מול
"action-status\|tool-result evidence\|ActionContract.status\|outcome_
unknown\|reply grounding" → 0 matches, אין נגיעה ב-claim-classification.

עבור BUG-161: הכלל שנוסף עוסק ישירות ב"ניסוח success/failure/pending
הפונה למשתמש" (§1.5's רשימת המקרים) — Agent free text שמבטיח פעולה
שלא תבוצע הוא בדיוק סוג ה-claim ש-RP5/`anti_hallucination.py` קיימים כדי
למנוע. **המנגנון הקיים שנצרך:** `core_knowledge.py`'s `STATIC_MANIFEST`
"חוקי כנות" block — **אותו מנגנון** שכבר משמש לאותה קטגוריית-מניעה (הכלל
הקיים על "אישור = כפתורי Telegram בלבד"), **לא** classifier/gate חדש
ומקביל ב-`core/anti_hallucination.py`/`core/turn_evidence.py`. זה עומד
בדרישת §1.5 במפורש ("לא מנגנון-הצדקה עצמאי חדש").

---

## 3. Proof-of-Non-Impact — סיכום

| שכבה | touched | proof |
|---|---|---|
| 1 — Core Reasoning/BUG-104 | not touched | §1, grep=0 + unchanged tests + no new coupling |
| 2 — TurnCoordinator | **directly** | §1, מטריצה מלאה |
| 3 — F52/Phase 4C | not touched | §1, grep=0 + unchanged tests + no new coupling |
| 4 — Durable Atomic Approval | **indirectly** (BUG-161 בלבד) | §1, grep=0 על identifiers **וגם** תלות-התנהגותית מתועדת במפורש (לא "0 → לא נוגע" עיוור) |

---

## 4. הרצות אימות שבוצעו (07/08/2026)

```text
python3 test_bug160_unbalanced_quote_create_task.py     → 15/15 passed
python3 test_bug163_complete_task_intent_coverage.py    → 12/12 passed
python3 test_bug161_agent_no_reconfirmation_promise.py  → 7/7 passed
python3 core/router/test_router.py                      → 44/44 passed
python3 test_bug153_create_task_reconfirmation_after_rejection.py → 16/16 passed
python3 test_bug159_create_task_noun_form_and_verbs.py  → 52/52 passed
python3 test_hotfix_c_create_task_verb.py               → 12/12 passed
python3 smoke_tests.py                                   → PASS (all checks)
python3 -m py_compile core_knowledge.py core/router/router.py core/router/intent_router.py → OK
```

`test_turn_coordinator_task_runtime_integration.py::test_app_create_
consumer_receives_gateway_mapping` נכשל גם **לפני** הסבב הזה (אומת פעמיים
עם `git stash` — פעם ראשונה אחרי BUG-161/163, פעם שנייה שוב אחרי BUG-160
— כשל זהה בשני המקרים על הענף ללא השינויים) — כשל לא-קשור, קיים-מראש,
לא נגרם ולא הוחמר ע"י אף אחד מארבעת הבאגים בסבב הזה.

---

## 5. מסקנה ומצב-סגירה

- **BUG-160:** 🟢 מומש, בדוק, ללא regression מאומת (כולל regression מלא
  על כל סוויטות ה-create_task הקיימות: BUG-153/159, Hotfix C). ניתן
  לסגור בעצמאות — אינו תלוי ב-BUG-161/162/163.
- **BUG-163:** 🟢 מומש, בדוק, ללא regression מאומת. ניתן לסגור בעצמאות —
  אינו תלוי ב-BUG-160/161/162.
- **BUG-161:** 🟡 מומש חלקית (המניעה המונעת-מראש, ברמת prompt) —
  **לא** ניתן לסגור סופית ("✅ Fixed") לפי כלל-הברזל, כי הסגירה המלאה
  תלויה במנגנון-enforcement שעדיין לא קיים (BUG-162). מצב מדויק:
  `STATUS: 🟡 CODE DONE (partial — prompt-level prevention only), NOT
  FULLY VERIFIED — depends on BUG-162 enforcement decision`.
- **BUG-162:** 🔴 נשאר `PLANNING BLOCKED` על סעיף אחד בלבד שהמטריצה הזו
  לא יכולה למלא בשבילו: החלטת-owner מפורשת על מנגנון ה-enforcement
  הקונקרטי (silence / clarify / redirect אוטומטי ל-gateway / אחר).
  ברגע שההחלטה תינתן, המטריצה הזו (שכבר ממופה) יכולה לשמש בסיס למימוש
  בלי סבב-תכנון נוסף מאפס.
