# DEV-REG — תכנון מקור סטטוס פיתוח קנוני ל־Command Center

**סטטוס:** planning/audit בלבד — אינו משנה production runtime, UI, API, schema או persistence.

**מטרה:** להפוך את סעיף 3.5 — `Active Work Registry` — למקור המסוכם הקנוני שממנו OC-C קורא סטטוס פיתוח. הראיות המקוריות נשארות סמכותיות בתחומן, אך reconciliation מתבצע בשגרה נפרדת ומעדכן את ה־Registry. OC-C אינו פותר drift בזמן קריאה.

## 1. Audit של סעיף 3.5 היום

### מה כבר קיים

`docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` כבר מכיל סעיף 3.5 יחיד, עם כלל מפורש שיוזמה חדשה חייבת להירשם לפני התחלה. קיימת בו טבלה פעילה הכוללת:

| שדה קיים | מצב נוכחי |
|---|---|
| יוזמה / מסמך | קיים; משמש זהות אנושית, אך אינו תמיד מזהה יציב ומפורש |
| היקף | קיים; טקסט חופשי |
| Horizon מקביל | קיים; מחובר ל־H0–H7 בחלק מהרשומות |
| שלב נוכחי בפועל | קיים; טקסט חופשי ולעיתים מערבב work state, evidence ופרטים היסטוריים |
| הצעד הבא שהוחלט | קיים; טקסט חופשי |

קיימת גם טבלת Horizons נפרדת (§5), שמגדירה את משמעות H0–H7 וממפה פריטי RV/BM/FUT. היא שימושית כקטלוג ותלות, אך אינה registry של מצב שורה-לשורה.

### מה חסר כדי להיות מקור מספיק ל־owner development status

1. אין vocabulary סגור ל־work state או ל־evidence state.
2. אין הפרדה בין “מה מצב העבודה” לבין “מה הראיה האחרונה מוכיחה”.
3. אין שדה מפורש ל־Needs Verification, חסימה או החלטת Owner; כיום הם מוטמעים בתוך prose.
4. אין `Last Reconciled`, ולכן לא ניתן לדעת אם שורה עדכנית או drifted.
5. אין provenance מובנה שמאפשר audit של הטענה בלי להפוך את ה־Registry לתחליף לראיות.
6. אין כלל schema מחייב לרשומה malformed או חסרת evidence; fail-closed אינו מובטח ברמת המסמך.
7. חלק מהרשומות מכילות פרטי PR/BUG/production בתוך `Current Stage`, אך ללא קשר מובנה וחד-משמעי.

המסקנה: אין ליצור Registry חדש. יש להקשיח את הטבלה הקיימת ואת כללי העדכון שלה, ואז להפוך אותה ל־read model קנוני עבור OC-C.

## 2. Schema מוצע — מינימום שימושי

שומרים את חמש העמודות הקיימות ומוסיפים רק את השדות שנדרשים ל־Command Center:

| שדה קנוני | קיים היום | חובה | משמעות |
|---|---:|---:|---|
| `Initiative / Document` | כן | כן | שם ותיאור קצר של היוזמה; בשלב DEV-REG-1 יש לקבוע גם key יציב כשאפשר, בלי ליצור טבלה חדשה |
| `Scope` | כן | כן | גבולות היוזמה והמערכות שנכללות בה |
| `Horizon` | כן | כן | אחד מ־H0–H7; חייב להתאים לטבלת Horizons |
| `Current Stage` | כן | כן | תיאור owner-facing קצר של השלב; לא מחליף את ה־vocabulary ואת `Evidence State` |
| `Evidence State` | לא | כן | הראיה המאוחדת שה־reconciliation אישר עבור היוזמה |
| `Next Decided Step` | כן, בשם אחר | כן | הצעד הבא שאושר; נשמר כעמודה הקיימת עם שם קנוני אחיד |
| `Needs Verification` | לא | כן | boolean מפורש; true כאשר נדרשת בדיקת merge/deploy/runtime או אימות אחר |
| `Blocked` | לא | כן | boolean מפורש; true רק כאשר יש חסימה מתועדת |
| `Owner Decision Required` | לא | כן | boolean מפורש; true כאשר נדרשת הכרעת Owner |
| `Last Reconciled` | לא | כן | timestamp של הריצה האחרונה שהשלימה בהצלחה את reconciliation לשורה |
| `Evidence Source` | לא | כן | provenance קצר ומוגבל: נתיב/מזהה ראיה, סוג evidence ותאריך/commit לפי הצורך; לא להעתיק את כל הראיה |

אין להוסיף בשלב זה שדות כמו assignee, percent complete, risk score, priority, PR URL או runtime endpoint. אין להם שימוש נדרש ב־OC-C הנוכחי והם עלולים להפוך את הטבלה ל־tracker מתחרה.

### Vocabulary סגור

`Work State` הוא vocabulary פנימי של השדה `Current Stage`/projection:

```text
PLANNED | ACTIVE | BLOCKED | OWNER_DECISION | CLOSED | UNKNOWN
```

`Evidence State` הוא שדה נפרד:

```text
PLANNED | CODE_DONE | MERGED | WIRED | DEPLOYED | RUNTIME_VERIFIED | UNKNOWN
```

ה־Registry חייב לשמר את invariant הבא:

```text
CODE_DONE != MERGED
MERGED != DEPLOYED
DEPLOYED != RUNTIME_VERIFIED
```

`Needs Verification`, `Blocked` ו־`Owner Decision Required` הם flags תפעוליים, לא ערכי Evidence State. אין להסיק אותם ממילה כללית כמו “implemented” או “verified”. ערך חסר, לא חוקי או לא נתמך נכשל ל־`UNKNOWN`/flag מתאים.

## 3. מי רשאי לעדכן כל שדה

| שדה | בעלים/מעדכן מורשה | כלל |
|---|---|---|
| זהות, Scope, Horizon | Owner/governance; שינוי ידני מתועד | אין ליצור שורת shadow; key קיים נשמר |
| Current Stage / Work State | reconciliation routine לאחר evidence מקושר, או Owner בהחלטה מפורשת | לא לעדכן לפי חיפוש prose כללי |
| Evidence State | reconciliation routine בלבד, לפי evidence authority המתאימה | אין “promote” אוטומטי בלי ראיה מספקת |
| Next Decided Step | Owner/governance או routine שמיישמת החלטה מפורשת | לא להחליף בהחלטה משוערת מה־PR |
| Needs Verification | reconciliation routine לפי evidence חסרה/מפורשת | merge אינו runtime verification |
| Blocked | Owner/governance או routine לפי blocker מפורש ומקושר | ניסוח עמום אינו blocker |
| Owner Decision Required | Owner/governance או routine לפי gate מפורש | אין להסיק רק מ־unknown |
| Last Reconciled | routine בלבד | מתעד זמן ריצה שהצליחה; אינו זמן שינוי ידני |
| Evidence Source | routine; Owner יכול לתקן provenance שגוי | provenance חייב להישאר traceable ומצומצם |

## 4. Evidence שמותר לו לשנות Evidence State

הראיה המקורית אינה מוחלפת. היא רק נקראת על ידי routine נפרדת, ולאחר מכן נרשם ב־3.5 הסיכום שאושר:

| Evidence State | ראיה מספקת |
|---|---|
| `PLANNED` | החלטת תכנון/רישום backlog מפורש ללא טענת מימוש |
| `CODE_DONE` | evidence מפורש של code complete/done, או שינוי קוד שנבדק כמיושם; אינו מוכיח merge |
| `MERGED` | merge/commit evidence מפורש ב־main או PR שמוזג |
| `WIRED` | evidence מפורש שהחיבור לקונטרקט/consumer הושלם; לא להסיק מ־code בלבד |
| `DEPLOYED` | evidence מפורש של deployment עבור אותה יוזמה/גרסה |
| `RUNTIME_VERIFIED` | production/runtime evidence מפורש, scoped לאותה יוזמה וגרסה/פריסה |
| `UNKNOWN` | payload חסר, malformed, ambiguous, לא מקושר או שאינו מוכיח את הערך המבוקש |

Commit subject לבדו יכול לתמוך לכל היותר ב־`CODE_DONE`/`MERGED`. גם אם הוא מכיל “deployed” או “runtime verified”, זה provenance תיעודי בלבד עד שקיימת ראיית deployment/runtime נפרדת ומקושרת.

BUG_AUDIT_LOG מוכיח מצב באג או audit רק לפי שדה/רשומה מפורשים; CHANGE_CONTROL_LOG מוכיח שינוי רק לפי הרשומה המקושרת. PR/CI מוכיחים רק את התוצאה שהבדיקה מגדירה. אין להפוך success של transport, test או API ל־runtime verification.

## 5. כללי reconciliation דטרמיניסטיים

ה־routine אינה מערכת גדולה ואינה חלק מקריאת OC. היא job/command מתוכנן, בעל קלטים מוגדרים ופלט עדכון ל־3.5 בלבד.

1. טען את שורת ה־Registry לפי identity/key יציב. אם שורת ה־Registry עצמה malformed — אין לכתוב חלקית; דווח כ־`UNKNOWN` ואל תעדכן `Last Reconciled` כאילו הצליח.
2. בדוק evidence sources רק דרך references מפורשים בשורה/קטלוג. אין חיפוש arbitrary repository prose לפי מילים.
3. לכל source שמצא — בדוק schema, scope, initiative identity וגרסה. אי-יכולת לקשר deterministic evidence מסומנת כ־unknown/unresolved, לא כ־zero או healthy.
4. סדר ההכרעה הוא לפי סוג claim, לא לפי כמות טקסט: runtime evidence עבור אותה יוזמה יכול לקבוע `RUNTIME_VERIFIED`; deployment evidence יכול לקבוע `DEPLOYED`; merge evidence יכול לקבוע `MERGED`; code evidence יכול לקבוע `CODE_DONE`; אחרת נשמר הערך הקודם אם הוא תקין, או `UNKNOWN` אם אין ערך אמין.
5. עדכן `Needs Verification`, `Blocked`, `Owner Decision Required` רק מערכים מפורשים או מחישוב fail-closed שמוגדר במסמך. אין להמיר `UNKNOWN` ל־OK/CLOSED.
6. כתוב provenance קצר ב־`Evidence Source` ועדכן `Last Reconciled` רק אחרי שכל השורה עברה validation.
7. אם יש conflict בין שתי ראיות מקושרות שאינן ניתנות להכרעה בטוחה — השורה נשארת `UNKNOWN`/flagged, נשמרים שני המקורות, ונדרשת החלטת Owner או reconciliation הבא.
8. reconciliation הוא idempotent: אותה קבוצת inputs מפיקה אותה שורה, מלבד timestamp.

## 6. Drift detection

Drift הוא פער בין הסיכום ב־3.5 לבין ראיה מקורית, לא הזמנה ל־OC-C ליישב בזמן אמת.

- מזהים drift כאשר מקור מקושר השתנה אחרי `Last Reconciled`, או כאשר source hash/commit אינו תואם ל־`Evidence Source`.
- מזהים missing provenance כאשר `Evidence State` אינו `PLANNED` אך `Evidence Source` חסר.
- מזהים invalid state כאשר ערך אינו ב־vocabulary הסגור, flag אינו boolean או Horizon אינו H0–H7.
- מזהים stale verification כאשר `Needs Verification=true` בלי evidence runtime/deployment חדש שמקושר לאותה יוזמה.
- מזהים orphan evidence כאשר PR/BUG/change/runtime record מפנה ליוזמה שאינה רשומה; אין ליצור שורת Registry אוטומטית.
- כל drift נכנס לדוח reconciliation/owner attention ומוביל להרצת routine; הוא אינו משנה את projection בזמן קריאה.
- CI/catalog validation צריך לבדוק schema, vocabulary, duplicate identity, missing provenance ו־malformed rows.

## 7. מה OC-C יקרא לאחר השינוי

ה־Command Center יקבל read model פשוט:

```text
read section 3.5
→ validate rows and vocabulary
→ filter owner-relevant rows
→ build typed owner projection
```

OC-C לא יקרא בזמן projection את ROADMAP, BUG_AUDIT_LOG, CHANGE_CONTROL_LOG, AI_CONTEXT, git history או runtime evidence כדי להכריע סטטוס. מקורות אלה שייכים ל־reconciliation routine ולדוח provenance/drift.

Validation ב־OC-C עדיין fail-closed: מסמך חסר, row malformed או ערך לא חוקי מחזירים projection `UNKNOWN`/partial לפי contract, ללא inferencing. `Evidence Source` מוצג כתקציר בטוח לבעלים, ללא internal IDs, commit hashes או payloads.

## 8. מה נשאר ומה יוסר/יועבר מ־PR #663

PR #663 הנוכחי מכיל ב־`core/owner_development.py` גם typed projection וגם reconciliation בזמן קריאה. תכנון migration:

### נשמר

- `DevelopmentItem`, `OwnerDevelopmentStatus`, `SourceVersion` והחוזים הטיפוסיים.
- validation של work/evidence/projection states ו־fail-closed behavior.
- owner-facing redaction/filtering ו־horizon grouping.
- projection buckets: current focus, next actions, needs verification, blocked, owner decisions, recently closed — בכפוף לכך שהשדות נקראים מה־Registry בלבד.
- provenance/version metadata במבנה projection, בלי להפוך אותו למקור סמכות נוסף.

### מצטמצם או מועבר ל־DEV-REG-2

- `_read_sources()` והקריאה הישירה של חמשת המסמכים בזמן `generate_owner_development_status` — יוצאים מה־consumer.
- `_main_commit_subjects()`, git-log crawling ו־main precedence — עוברים ל־reconciliation routine, עם invariant ש־main אינו מוכיח deployment/runtime.
- `_canonical_candidate_lines()`, `_source_evidence()`, `_reconcile()` וכל parsing של ROADMAP/BUG/CHANGE — אינם שייכים למסך; יועברו בעתיד למודול routine נפרד או יישארו planning-only עד DEV-REG-2.
- `_brief_items()`/`_recently_closed()` על AI_CONTEXT — לא ישמשו מקור סטטוס בזמן projection. תוכן שטרם נכנס ל־Registry לא יופיע כמצב קנוני.
- precedence engine, ambiguous-link detection ו־conflict resolution — יוגדרו וייבדקו ב־routine, לא ב־OC-C.

אין למחוק קוד שימושי לפני שיש יעד DEV-REG-2 ברור; אבל אין להשאיר אותו reachable דרך consumer API כאילו הוא נדרש להצגת status.

## 9. Migration plan ל־PR #663

1. להוסיף את מסמך התכנון הזה כ־PR תיעודי נפרד.
2. DEV-REG-1 יקשיח את סעיף 3.5 בפועל: vocabulary, flags, provenance, timestamp, validation וכללי ownership. אין ליצור Registry נוסף.
3. DEV-REG-2 יוסיף routine דטרמיניסטית, עם input/output contract, source adapters מוגבלים ו־tests ל־UNKNOWN, drift, conflict ו־promotion מדויק של evidence. הרוטינה תעדכן 3.5 בשגרה בלבד.
4. DEV-REG-3 יצמצם את `core/owner_development.py` ל־consumer של Registry rows validated. יוסר coupling ל־git/doc parsing מקריאת OC-C, והטסטים יעברו ל־fixtures של 3.5.
5. לאחר שה־Registry וה־consumer יציבים, OC-D יחשוף unified API read-only. OC-D אינו חלק מה־PR התכנוני הזה.

הגשר הבטוח הוא migration דו-שלבי: קודם Registry schema ו־fixture canonical, לאחר מכן routine, ורק אחר כך החלפת consumer. אין להפעיל reconciliation בזמן ש־OC-C קורא או לכתוב runtime state.

## 10. Sequence מומלץ

```text
DEV-REG-1 Registry hardening
        ↓
DEV-REG-2 deterministic reconciliation routine
        ↓
DEV-REG-3 OC-C simplification / Registry-only consumer
        ↓
OC-D unified read-only API
```

כל שלב חייב להישאר bounded ולשמור את invariant הסטטוסים. OC-D לא מתחיל לפני ש־3.5 הוא schema-valid, provenance-complete מספיק לצרכים שהוגדרו, ו־OC-C אינו מבצע source reconciliation בזמן קריאה.

## 11. החלטות והנחות שנדרשות לפני implementation

- לאשר האם `Current Stage` יכיל גם את Work State המובנה או שיוגדר parsing/serialization קנוני בתוך אותה עמודה; בכל מקרה אין להוסיף טבלת status שנייה.
- לקבוע פורמט מינימלי ל־`Evidence Source` (לדוגמה: `source_type:path#record@version`) בלי לחשוף מזהים פנימיים ל־owner projection.
- לקבוע מי מפעיל את DEV-REG-2 ובאיזו cadence, בלי להוסיף worker/runtime path במסגרת התכנון הזה.
- לאשר אילו רשומות קיימות דורשות backfill, ובמקרה של ספק להכניס `UNKNOWN` ולא לנחש.
