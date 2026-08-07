# BUG-161/162/163 — Turn-Coordinator-Adjacent Fallback Authority Planning Gate

**תאריך:** 07/08/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
(§7) — כל מסמך Planning Gate הנוגע ב-reasoning/routing/tools/actions/approvals/execution
חייב לפתוח בהפניה מפורשת לשער הזה ולא להתקדם בלי Cross-Layer Impact Matrix מלא
(§2 שם). Baseline: `main` `e54f9f0` (07/08/2026).
**היקף:** שלושת הבאגים נפתחו יחד באותו סבב אימות (Turn Coordinator E2E,
07/08/2026, ראו `BUG_AUDIT_LOG.md`), וה-owner ביקש במפורש לפתוח את המטריצה
עבור שלושתם יחד ולא לדחות אף אחד מהם בנפרד — גם אם רמת-המימוש שלהם שונה
(ראו §0 למטה).

---

## 0. סטטוס מימוש בפועל של כל אחד משלושת הבאגים (לפני המטריצה)

| באג | מדיניות הוכרעה? | קוד שונה בסבב הזה? | סטטוס אחרי הסבב |
|---|---|---|---|
| **BUG-163** | לא נדרשה — תיקון parser צר | ✅ כן — `core/router/intent_router.py` | 🟢 מומש, בדוק |
| **BUG-161** | ✅ כן (owner, 07/08/2026 — אופציה א') | ✅ חלקית — `core_knowledge.py` (system-prompt honesty rule) | 🟡 מומש חלקית — ראה §0.2 למגבלה |
| **BUG-162** | ❌ לא — מנגנון ה-enforcement עצמו עדיין לא הוכרע | ❌ לא | 🔴 עדיין PLANNING BLOCKED על החלטת owner נפרדת |

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
1. **grep evidence:** `git diff -- core/router/intent_router.py core_knowledge.py | grep -c "BUG-104\|leads_reasoning_projection\|FEATURE_CORE_REASONING_LEADS_STATE"` → **0**.
2. **unchanged-tests evidence:** `test_bug104_*.py` (5 חבילות) לא נוגעות
   בשום קובץ ששונה בסבב הזה — לא הורצו כי אין תלות; `smoke_tests.py`
   (הכולל import-sanity לכל המודולים) ירוק לפני ואחרי.
3. **no-new-coupling evidence:** אין `import` חדש ל-`core.leads_reasoning_
   projection`/`core.adapters.leads_adapter` באף אחד משני הקבצים ששונו.

### שכבה 2 — TurnCoordinator (de-facto: `router.py::route_request()` + `intent_router.py` + Agent free-text, per `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §1 שכבה 2)
**touched: directly** (BUG-163 — `intent_router.py`, נצרך ישירות ע"י
`router.py:193`'s `detect_intent(text)`) **וגם directly** (BUG-161 —
`core_knowledge.py`, קובע את הטקסט שה-Agent מייצר בזמן ש-Handler.AGENT
הוא בעל ה-turn).
- **input impact:** BUG-163 — אותו `text` input ל-`detect_intent()`, אין
  שינוי סוג/מקור/סמנטיקה של signal — רק הרחבת כיסוי-regex. BUG-161 —
  אין input חדש; system prompt static, לא תלוי ב-per-turn state.
- **output impact:** BUG-163 — `route.intent` עכשיו `complete_task` (היה
  `unknown`) לשתי הניסוחים החדשות בלבד; `route.handler` **לא** משתנה
  (נשאר `Handler.AGENT` — PA-01's גap לא נסגר כאן, ראה §0.1). BUG-161 —
  אין output-signal חדש; רק תוכן הטקסט שה-Agent עשוי לחבר.
- **authority impact:** **אין לאף אחד מהשניים.** BUG-163 לא נותן
  `Handler.TOOL` לאף intent חדש. BUG-161 לא משנה מי מחליט `reply_owner`
  (זה עדיין shadow-only, ללא אכיפה — ראה §0.2).
- **shared identifiers:** `Intent.COMPLETE_TASK`/`Intent.UPDATE_TASK` —
  נצרכים, לא מוגדרים-מחדש. אין identifier חדש נוסף בשכבה הזו.
- **invariants:** "ספציפי לפני כללי" (סדר ה-`_RULES` list) נשמר — הכללים
  החדשים נוספו ליד הכלל הקיים של `COMPLETE_TASK`, עדיין לפני `DELETE_TASK`/
  `LIST_TASKS`; מאומת ב-regression (`LIST_TASKS` על "אילו משימות כבר
  בוצעו" עדיין נכון, לא נחטף ע"י התבנית החדשה).
- **failure semantics:** ללא שינוי-חומרה. סיווג-שגוי היפותטי של intent
  עדיין נופל ל-`Handler.AGENT` (בדיוק כמו `unknown` היה נופל) — אין נתיב
  `Handler.TOOL` חדש שסיווג שגוי יכול "לפתוח" בטעות (PA-01 עדיין לא
  קיים). ה-blast radius חסום כרגע בבנייה, לא בזכות התיקון הזה.
- **observability:** `route.to_log()`'s `intent=complete_task` (היה
  `unknown`) לשתי הניסוחים החדשות — נראה בלוג הקיים, אין שדה חדש.
- **cross-layer tests:** `test_bug163_complete_task_intent_coverage.py`
  (12/12, כולל בדיקת אי-התנגשות מפורשת עם `LIST_TASKS`) +
  `core/router/test_router.py` (44/44, ללא regression) +
  `test_bug161_agent_no_reconfirmation_promise.py` (7/7 — מוודא את
  מיקום/ניסוח כלל-הכנות + את תקינות ה-Gateway backstop שהכלל נשען עליו).

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
**touched: not touched.**
1. **grep evidence:** `git diff -- core/router/intent_router.py core_knowledge.py | grep -c "ToolMeta\|tool_registry\|dispatch_tool\|action_validator\|tools/schemas\|tools\.dispatcher"` → **0**.
2. **unchanged-tests evidence:** לא נוגע ב-`tool_registry.py`/`tools/
   dispatcher.py`/`action_validator.py` — אין נתיב שיכול לשבור טסטים של
   השכבה הזו; `smoke_tests.py`'s "Tool registry / dispatcher sanity"
   ירוק לפני ואחרי.
3. **no-new-coupling evidence:** אין `import` חדש ממודול בשכבה 3.

### שכבה 4 — Durable Atomic Approval
**touched: indirectly** (BUG-161 בלבד; BUG-163 לא נוגע כלל).
- **grep evidence (זיהוי):** `git diff -- core/router/intent_router.py core_knowledge.py | grep -c "ActionContract\|ActionGateway\|action_gateway\.py\|propose_action"` → **0** — כלומר **אין** קריאה/הפניה **ישירה בקוד** לזהויות של שכבה 4. הנגיעה היא **התנהגותית**, לא-מזוהה ב-grep, ולכן חייבת להיות מתועדת במפורש כאן (לא רק "0 → not touched"):
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

**applies: yes**, ל-BUG-161 בלבד. BUG-163 (סיווג intent גרידא, לפני כל
tool_use/evidence) — **לא applies**, `grep` על diff-163 מול
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
python3 test_bug163_complete_task_intent_coverage.py   → 12/12 passed
python3 test_bug161_agent_no_reconfirmation_promise.py → 7/7 passed
python3 core/router/test_router.py                     → 44/44 passed
python3 smoke_tests.py                                  → PASS (all checks)
python3 -m py_compile core_knowledge.py core/router/intent_router.py → OK
```

`test_turn_coordinator_task_runtime_integration.py::test_app_create_
consumer_receives_gateway_mapping` נכשל גם **לפני** הסבב הזה (אומת עם
`git stash` — כשל זהה על `main`/הענף הנוכחי ללא השינויים) — כשל
לא-קשור, קיים-מראש, לא נגרם ולא הוחמר ע"י BUG-161/163.

---

## 5. מסקנה ומצב-סגירה

- **BUG-163:** 🟢 מומש, בדוק, ללא regression מאומת. ניתן לסגור בעצמאות —
  אינו תלוי ב-BUG-161/162.
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
