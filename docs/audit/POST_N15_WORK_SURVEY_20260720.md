# Post-N15 Work Survey — 20/07/2026

**מטרה:** אחרי שסבב N15/BUG-110/Day-3-flags/BUG-120/BUG-121 הסתיים ומוזג, נדרשה תכנית עבודה למספר ימים נוספים — כל דבר שאפשר לחזק/להשלים/לשפר **מחוץ** ל-RP5, F52, ולכל דבר חסום אחר. זהו הדוח המלא, לא-מקוצר, כדי שאף פרט לא ילך לאיבוד לפני שמתחילים לעבוד על התכנית עצמה.

**איך זה נאסף:** 4 סוכני חקירה מקבילים (Explore, read-only), כל אחד סרק תחום נפרד — ROADMAP.md, BUG_AUDIT_LOG.md, feature_flags.py, וחוב טכני/governance drift כללי. לכל הסוכנים ניתנה הנחיה מפורשת להוציא **RP5** (`core/rp5_fault_injection.py`, staging-only), **F52** (`FEATURE_UNIFIED_STATUS_FORMATTER`/EvidenceFinalizer), **FEATURE_ACTION_GATEWAY**/PR-0C, **FEATURE_PA01_ENFORCEMENT_STATE** (enforce), **FEATURE_DECISION_HUB**, **FEATURE_AUTO_CAPTURE**, ו-**MULTITENANT** מהתוצאות.

---

## 0. תיקוני Drift שאותרו תוך כדי הסקירה עצמה

ה-ROADMAP טוען שלושה דברים שהתבררו כלא-נכונים — נמצא תוך כדי הצלבה מול עבודה מאומתת מהשבוע הזה:

1. **C84** — ROADMAP עדיין כתוב "טרם ממוזג ל-main". שגוי: אומת בשבוע הזה (`git merge-base --is-ancestor c5c5a97 origin/main`) שזה **כן** ממוזג, PR #408.
2. **C86** — ROADMAP כתוב "planned, not started". שגוי: `test_c86_scheduler_emergency_matrix.py::test_emergency_stop_matrix_blocks_every_registered_scheduler_job` **כבר קיים ועובר**, מתועד בעדכון C82-FU (19/07/2026) ב-ROADMAP עצמו — שני מקומות בו-זמנית בקובץ סותרים זה את זה.
3. **"Known Issues" table — `/status` decorator "removed in PR #55, does nothing"** — שגוי: עבדנו על `/status` ישירות השבוע (BUG-120/BUG-121) וה-decorator קיים ורשום (`@bot.message_handler(commands=["status"])`, `app.py:401`). תואם ל-BUG-005 ("`/status` decorator restored") שכבר סגור ב-BUG_AUDIT_LOG.

**מסקנה:** ה-ROADMAP סוטה מהמציאות במקומות ממשיים, לא רק ב"עדכון אחרון". שווה sweep תיקון תיעוד לפני שממשיכים.

---

## 1. ROADMAP.md — פריטים פתוחים (לא-RP5/F52, לא חסומים)

- **C84** — TMA Approvals TTL/freshness check ב-`tma_api.py::_claim_and_execute_approval()`. **בפועל: ✅ כבר merged** (ראו סעיף 0) — התיקון הנדרש הוא רק בתיעוד.
- **C85** — CI structural test שמוודא שלכל `request_approval(action=...)` יש subscriber/handler רשום. תכנון, לא התחיל. מאמץ: קטן.
- **C86** — מטריצת test ל-EMERGENCY_STOP_AUTOMATION על כל jobs ה-scheduler. **בפועל: ✅ כבר קיים ועובר** (ראו סעיף 0) — התיקון הנדרש הוא רק בתיעוד.
- **C87** — החלטת ארכיטקטורה: לאחד את מצב ה-Approvals למקור אמת יחיד (טבלת `Approvals` הקיימת מול מנגנון חדש), לפני שמקדמים `SPEC_LL13`. היה חסום על C81-FU/C82-FU/C83 — **כולם סגורים כעת, בפועל לא-חסום יותר**, אבל הטקסט לא עודכן. דורש **החלטת owner**. מאמץ: בינוני (החלטה+עיצוב, לא רק קוד).
- **C88** — Secondary Guard: להפוך ל-fail-closed כברירת מחדל (כרגע fail-open ב-staging); override מפורש רק לטסטים. תכנון. מאמץ: קטן.
- **C91** — Capture Policy Stage 3.2: לחבר תמלול Whisper לקול לתוך `classify_ingress(source_type="voice")` עם baseline ביטחון מופחת. לא התחיל, לא-חסום. מאמץ: בינוני.
- **C92** — Capture Policy Stage 3.3: לחבר את `email_inbound.py` ל-`classify_ingress()` המשותף במקום לוגיקה נפרדת. לא התחיל, לא-חסום (דורש רק החלטות flag). מאמץ: בינוני.
- **N10** — rollback אוטומטי ל-commit יציב אחרון אם health check אחרי deploy נכשל (כרגע gate ידני בלבד). תכנון, לא התחיל. מאמץ: גדול.
- **N15** — `RouteDecision.notify_owner` נקבע ל-Restricted flow אבל אף אחד לא צורך אותו מלבד logger.warning. **כבר טופל בסבב הזה** — עוצב פתרון (Restricted Activity Digest, יומי/שבועי לבעלים) והוחלט מפורשות לדחות מימוש. אין פעולה נדרשת עד החלטה חדשה.
- **U1** — החלטת ארכיטקטורה: לבנות "Understanding Layer" גנרי חדש (Interaction Envelope/Understanding Contract) מול הרחבת `core/reasoning_entity.py`/`leads_adapter.py` הקיימים. חוסם UX-01. דורש **החלטת owner**. מאמץ: בינוני (החלטה, לא קוד).
- **F06** — Email inbound lead capture דורש גם `EMAIL_INBOUND` וגם `LEAD_CAPTURE` יחד (שניהם כבויים כרגע); דורש **החלטת owner** על השלכות `LEAD_CAPTURE`. מאמץ: קטן ברגע שהוחלט.
- **F09** — להחליט אם לחבר את מכונת-המצבים הקיימת `lead_qualifier.py` ל-`run_agent`, או להישאר עם ניקוד Claude-native (המסלול הפעיל, N02/N03). אין חסם טכני. דורש **החלטת owner**. מאמץ: קטן ברגע שהוחלט.
- **F14** — פונקציית gate חדשה `find_or_create_contact(phone, name, **fields)` ב-`crm.py` למניעת אנשי-קשר כפולים בין import/`crm_add_contact`/המרת ליד→איש-קשר עתידית. תכנון, לא התחיל. מאמץ: קטן-בינוני.
- **F15** — להעביר את הקריאות הישירות `_post`/`_patch` של `crm.py` ל-`airtable_gateway.upsert()` (סוגר הפרת "כל הכתיבות דרך ה-gateway"). חוב טכני מתוכנן. מאמץ: בינוני.
- **BUG-072** — לוגים (גם מלפני C94) חושפים sender ID/טלפון גולמיים לא-מסוננים; נמצא אגב בדיקת עשן ל-C94, לא קשור ל-C94 עצמו. פתוח, לא תוקן. מאמץ: בינוני. (מופיע גם בסקירת BUG_AUDIT_LOG — ראו שם.)
- **Safe Document Converter** — ל-`convert_document()` אין אף קורא חי (`app.py`/dispatcher) — קוד קיים אבל לא מחובר בכלל. בנפרד: תיקון ה-CI `__main__`-guard ל-`test_document_converter.py` יושב על branch `fix/ci-silent-pass-document-converter`, לא ממוזג. מאמץ: קטן (מיזוג תיקון הטסט) / בינוני (החלטת חיווט+אינטגרציה).
- **טבלת "Known Issues"/חוב טכני קטן** (כל אחד קטן, "בפעם הבאה שנוגעים בזה"):
  - `_ALIAS_MAP` משוכפל ב-`dispatcher.py` וב-`airtable_tools.py` (סיכון drift).
  - `lead_memory.py:155` כותב שדה `updated_at` שלא קיים ב-Airtable schema (נשמט בשקט).
  - טבלת Worlds — אין DB constraint שמונע שתי רשומות "Active" בו-זמנית.
  - `LeadFields.TIER` מוזכר בקוד אבל אין שדה כזה ב-Airtable בפועל — דורש **החלטת owner** (ליצור שדה או להסיר קוד).
  - טבלת Assets — שמות שדות סטו ממסמך המיגרציה (`Mortgage Balance` מול `Mortgage`, חסרים `Purchase Cost`/`Documents`).
  - `Table 16` ריקה ב-Airtable, placeholder — צריך מחיקה ידנית.
  - `/status` handler decorator — **מתברר שכבר תוקן** (ראו סעיף 0), הטבלה עצמה מיושנת.
- **פערים ידועים נוספים:**
  - `schema_cache.json` מיושן ל-Coins_Log/Roadmap_Tasks/Leads — refresh טריוויאלי.
  - `core_knowledge.py` smoke-test false positive על ביטוי `_NEVER_FAKE_CONTROL` — לתעד כ-false positive ידוע, טריוויאלי.

---

## 2. BUG_AUDIT_LOG.md — באגים פתוחים (לא-RP5/F52, לא BUG-120/121)

נסרק הקובץ המלא (2850 שורות). מקובץ לפי קטגוריית פעולה נדרשת:

### תוקנו/merged, צריך רק אימות פרודקשן
BUG-002/003/004 (game/today endpoint filter, אין constraint על World פעיל, Daily_Checkin write-through — BUG-003 גם דורש constraint אמיתי ב-Airtable, לא רק קוד), BUG-005/006 (`/status` decorator + Hub debug block הוסר), BUG-011 (אובדן שקט של תשובת טלגרם ב-exceptions של `run_agent()`), BUG-013 (טיפול בקובץ גדול — מורד לפני בדיקת גודל), BUG-014 (gate נגד טענת-הצלחה כוזבת בחיפוש Drive), BUG-016 (תזכורת security-review תקועה על 999 ימים — גם דורש שימוש ראשון אמיתי ב-tracker), BUG-017 (session_store — חוסר-התאמה dict/string ב-sync), BUG-018 (Mojibake ב-app.py — 132 שורות עברית פגומות ללקוח, דורש בדיקה חיה), BUG-020 (קבועי טבלה/שדה מיושנים — התנהגות, לא רק קוד, עדיין לא אומתה), BUG-072 (טלפון/sender ID גולמי דולף ללוגים — **גם מופיע בסקירת ROADMAP למעלה**), BUG-015 (דורש הרצה חיה מול Airtable אמיתי, לא רק merge), BUG-051, BUG-056, BUG-057, BUG-061-065, BUG-074-077, BUG-085 (flag כבוי), BUG-086, BUG-087 (מדיניות notify-owner של N15 גם עדיין לא הוחלטה), BUG-112 round 2 (ניקוי ניסוח callback ישן/חסר — התיקון המרכזי כבר סגור).

### דורש merge (לא רק אימות)
- **BUG-007** — CORS 500 על OPTIONS preflight, חוסר-התאמת שם-פרמטר. תוקן, לא ממוזג. קטן.
- **BUG-049** — קובץ test רץ בשקט 0 assertions ב-CI. תוקן, PR אף פעם לא נפתח. קטן.
- **BUG-073** — תוויות "חוסם" ב-ROADMAP.md היו drift תיעודי. תיקון ממתין למיזוג. קטן.
- **BUG-058** — פותר Tier-2 batch "לשמור הכל?" — נבנה בפועל, ממתין ל-push/PR + אימות פרודקשן. בינוני.
- **BUG-071** — קבצים מצורפים ב-WhatsApp עקפו את כל טיפול המדיה. תוקן, דורש merge+אימות. **נשמע חשוב — עדיפות גבוהה.**
- **BUG-BATCH-DISCARD** — בקשות multi-task איבדו בשקט כל משימה אחרי הראשונה. תוקן/נבדק, לא ממוזג/deployed. **נשמע חשוב — עדיפות גבוהה.**
- **BUG-110** — חלק ה-read-side (attribution/audience) **כבר טופל בסבב הזה**; חלק ה-write-side כבר merged מזמן.

### דורש החלטת owner
- **BUG-036/037** — Decision Hub formula injection — קוד מוכן, לא merged; חוסם הפעלת `FEATURE_DECISION_HUB` (מחוץ לסקופ ממילא).
- **BUG-059** — ענף רדום עם משטח prompt-injection לא-מסונן; חייב להיפתר לפני שהענף אי-פעם ימוזג.
- **BUG-068/069** — Daily Digest בלי הגבלת אורך/פירוט; שורש אומת, אין תיקון/החלטה.
- **BUG-070 gap(3)** — "ענה במספר" של `daily_collector` אין לו שום backend; עדיין פתוח.
- **BUG-083** — טבלאות Decision Hub חסרות מ-audit ה-schema drift; עדיפות נמוכה, לא מתוזמן.
- **BUG-102** — `normalized_text` של IngressEnvelope נבנה ונזרק במסלול טקסט; דורש החלטת חיווט-או-תיעוד.
- **BUG-103** — EvidenceTrace נבנה ומלוגג, לעולם לא persist; דורש החלטת אחסון.
- **BUG-104** — Core Reasoning Activation Program (ReasoningEntity/adapters לא מחוברים); כבר בתהליך דרך ה-shadow flag שהפעלנו.
- **BUG-109** — אישור-override הופך בשקט ל-no-op תחת `FEATURE_ATOMIC_CLAIMS` (מפתח-claim לא-מורכב); נשאר פתוח בהמתנה לבדיקת side-effect (הflag כבוי ממילא).
- **`schema_cache.json`** — קובץ seed מיושן בשורש; דורש החלטת מחיקה/רענון/השארה.
- **`Next Action` field constants drift** — לא בשימוש כרגע; דורש טיקט רק אם אי-פעם יחובר.

### מתועד בלבד, אין תיקון מתוכנן
BUG-035 (מחרוזות emoji עבריות hard-coded במקום קבועי schema), BUG-050/054 (כלל "פתח PR כברירת מחדל" הופר פעמיים; אין אכיפה בנויה), BUG-052 (ל-`run_agent()` אין טסטים end-to-end מבודדים), **BUG-105** (מספרי טלפון בין-לאומיים עם מקף פנימי נשמטים בשקט כמועמדים — **נשמע כמו באג מוצר אמיתי, קטן**), **Preview-gap** (תצוגות preview יחיד/batch/disambiguation לא-עקביות, דולפות contract IDs פנימיים — **security-adjacent**, דורש PR ייעודי).

### אומת חלקית, דורש טסט המשך ספציפי
BUG-023/024/025 (שחיתות Primary-Field "ליד חדש" — נבדק בעשן רק דרך הכתבה של הבעלים, דורש מספר טלפון חיצוני חדש אמיתי), **BUG-080** (datetime מלא נכתב לשדות Date-only — רק 1 מתוך 7 אתרי כתיבה אומת חי, 6 נותרו), BUG-081 (תיקון Domain/Tags ל-Business Memory — שלבים 1-5 אומתו חי, שלב 6 [dynamic schema lookup] merged אך לא אומת בנפרד), BUG-094/095/097 (דליפת שם/טלפון בהכתבת batch לידים — תוקן/נבדק, דורש טסט batch חי עם טלפון פגום באמצע), BUG-099a (חילוץ שם-ליד תופס תיאורי נכס כשמות — קוד+טסטים מוכנים, דורש PR+אימות פרודקשן).

### מיגרציה גדולה בתהליך (מחוץ לסקופ הפעיל — קשור ל-FEATURE_ACTION_GATEWAY)
PR-0C (event_bus → ActionGateway) — שלבים 1-3 merged (flag כבוי, לא אומת חי); שלב 4A/4B0 merged כ-scaffolding אינרטי (singleton לא מחובר); שלב 4B0.1 (atomic-claim primitive אמיתי) לא התחיל, חוסם שלב 4B (ניתוב TMA לפי contract ID). **מוזכר כאן לשלמות בלבד — לא נכלל בתכנית הפעילה כי הוא חלק מ-`FEATURE_ACTION_GATEWAY`, מחוץ לסקופ.**

---

## 3. feature_flags.py — מועמדים בטוחים להפעלה/קידום

- **`FEATURE_LAST_TOOL_RESULT_SHADOW`** (כבוי→`true`) — רושם RAM-only פסיבי, TTL-bounded, side-effect-only. שלוש נקודות הקריאה (`tools/dispatcher.py:457`, `tma_api.py:265`, `core/output_gateway.py:250`) כולן עטופות ב-try/except. חבילת test ייעודית קיימת (הוספנו השבוע). **בטוח.**
- **`FEATURE_WEEKLY_SUMMARY`** (כבוי→`true`) — דוח שבועי Read-only בטלגרם, מקובץ לפי domain. מחובר ל-`scheduler.py:334`, רץ כל יום ראשון 08:30 מאחורי `_automation_guard`. באג הקיבוץ שלו **כבר תוקן השבוע**. גרוע ביותר: הודעה מוטעית/מיותרת בטלגרם. **בטוח.**
- **`FEATURE_STRUCTURED_FILE_CAPTURE`** (כבוי→`true`) — מנתב xlsx/csv שהועלו דרך `classify_ingress()` הקיים ל-preview Tier-4-בלבד. מוגבל נוסף ל-`identity.is_internal`. אין נתיב כתיבה חדש. **בטוח.**
- **`FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE`** (כבוי→`shadow`) — משווה סכמה חיה מול הבדיקה הקיימת, ב-shadow רק מלוגג `discrepancy`, לא חוסם. מכוסה ב-`test_runtime_schema_provider.py`. **בטוח.**
- **`FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE`** (כבוי→`shadow`) — מוולד ערכי singleSelect/multipleSelects מול choices חיים; ב-shadow רק `logger.warning`, לא מסיר שדות. פועל רק כש-provider מדווח `mode="full"` — אין false positives מבניים. עצמאי מהדגל הקודם. **בטוח.**
- **`FEATURE_RAW_CAPTURE`** (כבוי→`true`) — שומר טקסט גולמי נכנס ל-Decision Inbox, עטוף try/except, לא חוסם סיווג. **עדיפות נמוכה יותר** — כן כותב שורות Airtable אמיתיות, לוודא שהטבלה/שדות קיימים לפני הפעלה.
- **`FINANCIAL_COMMITMENT_GATE`** (כרגע `false`=shadow→`true`) — מזהה שפת-התחייבות-פיננסית ומסלים לבעלים (**אף פעם לא חוסם/מוריד הודעה** — עיקרון "ESCALATE not BLOCK"). **סיכון מעט גבוה יותר** מהשאר — מתחיל לשלוח התראות אמיתיות לבעלים, לא רק לוגים.

**מפורשות הוצאו מהרשימה (לא מועמדים, off-limits):** `FEATURE_ACTION_GATEWAY`, `FEATURE_PA01_ENFORCEMENT_STATE` (הפעלת enforce), `FEATURE_UNIFIED_STATUS_FORMATTER` (F52), `FEATURE_EVIDENCE_FINALIZER`, `FEATURE_AUTO_CAPTURE`, `FEATURE_DECISION_HUB`, `FEATURE_DECISION_AUTO_INGESTION`, כל דבר RP5, `MULTITENANT`, `FEATURE_ATOMIC_CLAIMS`, `FEATURE_ACTION_CONTRACT_PERSISTENCE`, `EMERGENCY_WINDOW`.

---

## 4. חוב טכני וGovernance Drift

### TODO/FIXME אמיתיים (לא placeholders)
- `data_engines.py:56,74,137` — שלושה imports מוערים-החוצה (`learning_engine.run_learning_cycle`, `get_domain_insights`, `revenue_attribution.get_report`) שמשאירים פונקציות stub; לוגיקה אמיתית לא מחוברת. בינוני.
- `data_engines.py:117` — "TODO: לוגיקת attribution אמיתית" — עדיין stub. בינוני.
- `lead_conversion.py:13` — "TODO (future): migrate to gateway when crm.py is refactored" — חוב מוכר, ממתין לרפקטור `crm.py` שלא מתוזמן. קטן (ברגע שמופעל).
- `scheduler.py:448` — הערה לשקול מחדש `INTERACTION_INTERVAL_MIN` (10→30 דק') ברגע ש-`INTERACTION_INTELLIGENCE` חי בפרוד, לחתוך קריאות Calendar API ב-50%. קטן.

### מסמכי Governance — פריטים פתוחים
- **`SECURITY_CHECKLIST.md`** מסומן כארכיון החל מ-14/06/2026 ("no longer active planning source of truth") — שווה לוודא ש-CLAUDE.md/תהליך ה-onboarding לא עדיין מפנים אליו כאילו הוא חי. קטן לאימות/relink.
- **`ARCHITECTURE_DRIFT_MAP.md`** — 6 מתוך 8 שורות עדיין `TODO`: Emergency Stop persistence, Messaging facade, Approvals canonicalization, Task taxonomy freeze, Audit event schema unification, Airtable read gateway. שורה אחת `DEFERRED` (Google risk metadata, קפוא בכוונה). שורה אחת `DONE` (Identity normalization smoke test, 14/06/2026).
  - **הכי קריטי — שורה 1, Emergency Stop flags נשמרים ב-`/tmp` בלבד** — מתאפס בשקט ב-restart/deploy של Render, כלומר `EMERGENCY_STOP_ALL` שהבעלים הפעיל עלול לפוג בשקט. מסומן **P0**, עדיין פתוח. בינוני-גדול (דורש אחסון persistent ב-Airtable + guard clauses ב-4 workers).
  - שורה 3 (איחוד Approvals, `event_bus._pending` בזיכרון מול Airtable כמקורות-אמת כפולים) ו-שורה 2 (messaging facade, 8+ אתרי שליחה ישירה) גם P0/TODO. בינוני כל אחת.

### פער תיעוד — CHANGELOG PA-01
- אומת שעדיין פתוח — כותרת ה-Unreleased ב-CHANGELOG.md אומרת במפורש ש-PRs #348–353 לא פורטו בנפרד ("known, separate documentation gap, not addressed"). עדכון ה-ROADMAP מ-16/07/2026 מאשר: 6 PRs (#348-353, סאגת PA-01) + `CHANGE_CONTROL_LOG.md` חסר בנפרד ערכים #327–353 אחרי C111. מאמץ backfill: בינוני — 6 ערכי CHANGELOG + כ-27 ערכי CHANGE_CONTROL_LOG; `PA01_PLANNING_GATE.md` (כ-1750 שורות) כבר קיים כחומר מקור, אז זו תמלול/סיכום, לא חקירה.

### מודולים "parked" — מועמדים לחיווט
- **`creative_generator.py`** — עצמאי, תלוי רק במודולים חיים (`feature_flags.py`, `llm_fallback.py`), flag-gated (`CREATIVE_GENERATOR`), אין תלות תשתית חיצונית. **המועמד הכי טוב לחיווט קרוב** — רק צריך caller/command מחובר. קטן-בינוני.
- **`profile.py`** — עטיפת Airtable REST פשוטה (טבלת `Profile` עצמאית), אין שאלות עיצוב פתוחות, אבל צריך שהטבלה תיווצר קודם. בינוני (חיווט+הקמת Airtable).
- **`tenant_provisioner.py`** (F08 multi-tenant) ו-**`knowledge_engine.py`**/`router.py` השורש (Supabase-backed) — צריכים להישאר parked: הראשון החלטת עסק/מודל מלאה (SaaS white-label), השני תלוי פשוטו-כמשמעו בתשתית (Supabase) שלא קיימת בסטאק. גם `core/tenant_config.py`+`providers/` נשארים parked כראוי (חופפים שאלת עיצוב לא-מוחלטת עם ה-`providers/` המתוכנן של F12). גדול אם ייפתחו (דורש החלטות מוצר קודם).

### פער כיסוי טסטים
- אין פער אמיתי ברמת קובץ: `identity.py`, `tool_registry.py`, `tools/dispatcher.py`, ו-`context.py` כל אחד חסר קובץ `test_identity.py`/`test_tool_registry.py`/`test_dispatcher.py`/`test_context.py` יחיד בשם קנוני, אבל כולם מכוסים דרך קבצי test רבים ספציפיים-לבאג/פיצ'ר (למשל `test_action_gateway.py`, `test_pa01_phantom_approval_enforcement.py`, `test_tool_registry_invariants.py`). ל-`core/router/` יש `test_router.py` משלו בתוך התיקייה. זה **פער נראות/מוסכמת-שם, לא חור כיסוי אמיתי** — שווה לציין כ-process nit (אין מקום אחד להריץ "את בדיקות ה-identity"). קטן אם רוצים לטפל (aggregator דק או מוסכמת שינוי-שם).

---

## 5. מחוץ לסקופ במפורש (לא ייכללו בתכנית הפעילה)

RP5 (כולל `core/rp5_fault_injection.py`, staging-only), F52/`FEATURE_UNIFIED_STATUS_FORMATTER`/`FEATURE_EVIDENCE_FINALIZER`, `FEATURE_ACTION_GATEWAY`/PR-0C (event_bus migration), `FEATURE_DECISION_HUB` + כל מה שחוסם אותו (BUG-036/037), `FEATURE_AUTO_CAPTURE`, `FEATURE_PA01_ENFORCEMENT_STATE` (enforce), `MULTITENANT`, `FEATURE_ATOMIC_CLAIMS`, `FEATURE_ACTION_CONTRACT_PERSISTENCE`, `EMERGENCY_WINDOW`.

---

## 6. תכנית העבודה המוצעת — 5 ימים

**יום 1 — ניקוי תיעוד + Flags בטוחים.** תיקון 3 ה-drift-ים בסעיף 0. הפעלת `FEATURE_WEEKLY_SUMMARY→true`, `FEATURE_LAST_TOOL_RESULT_SHADOW→true`, `FEATURE_STRUCTURED_FILE_CAPTURE→true`, `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE→shadow`, `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE→shadow`.

**יום 2 — Flags עם בדיקה מקדימה + מיזוג קוד קיים.** `FEATURE_RAW_CAPTURE`/`FINANCIAL_COMMITMENT_GATE` אחרי בדיקת תנאים. מיזוג BUG-071 (WhatsApp attachments), BUG-BATCH-DISCARD, BUG-058, BUG-007, BUG-049.

**יום 3 — אבטחה/פרטיות + תיקונים קטנים חדשים.** BUG-072 (דליפת טלפון/sender ID ללוגים), Preview-gap (דליפת contract ID), BUG-105 (טלפון בין-לאומי), F14 (dedup gate), C88 (fail-closed).

**יום 4 — Emergency Stop persistence (P0).** אחסון persistent ל-`EMERGENCY_STOP_*` (Airtable, לא `/tmp`) + guard clauses ב-4 workers.

**יום 5 — ניקוי backlog + אימות פרודקשן שיטתי.** מעבר על רשימת ה-"merged, need production verification only" הארוכה בסעיף 2, `schema_cache.json` refresh.

**דורש החלטת owner לפני ביצוע (לא בתכנית האוטונומית):** C87, U1, F06, F09, `LeadFields.TIER`, BUG-104 (בתהליך דרך shadow flag ממילא).
