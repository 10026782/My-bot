# BUG-CRM-BYPASS follow-up — deterministic Turn Coordinator route for Deal creation

**תאריך:** 01/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.
**Cross-Layer Planning Gate assessment:** FULL — שינוי זה מוסיף `Intent`
חדש (`route_decision.py`), מרחיב את מדיניות ה-PA-01 contract-required
(`risk_router.py`), ומוסיף נתיב ביצוע דטרמיניסטי חדש ב-`app.py`'s turn
flow (routing/runtime-wiring חוצה-שכבות: Router → app.py → ActionGateway
→ Dispatcher) — לא שינוי מוכל בשכבה אחת.

## הרקע — למה זה נבדק

לאחר PR #1165/#1166 (סגירת עקיפת `airtable_add` הגנרית ל-Deals/Payment
Terms/Payments, ואז תיקון resolution ל-Owner), הקנריות בפרודקשן נכשלו
**שוב** (PR #1169 — aliases של שמות שדה בשפה טבעית). כל אחד מהתיקונים
תיקן פער אמיתי, אבל אף אחד לא טיפל בשורש: **ל-Deal creation לא היה
`Intent` ייעודי בכלל** — הבקשה תמיד הגיעה ל-`Handler.AGENT`, כלומר ה-LLM
היה זה שבוחר בין `crm_create_deal` לבין `airtable_add` הגנרי. זה בדיוק
ההפך מההחלטה הארכיטקטונית הקיימת (Turn Coordinator / Single Speaker):
המערכת מנתבת פעולות mutation באופן דטרמיניסטי, לא הסוכן. `Intent.CREATE_TASK`
כבר פתר את זה (`core/router/router.py`'s `parse_deterministic_create_task`
→ `Handler.TOOL`/`Handler.CLARIFY`, `app.py`'s `_queue_deterministic_create_task()`
עם `agent_calls=0` מתועד) — ל-Deal לא היה מקביל.

PR נוסף (`codex/commercial-crm-canonical-path`, #1171) ניסה לתקן את זה
ע"י שיפור תיאורי הכלים (`airtable_add`/`crm_create_deal`) כדי שה-LLM "יבחר
נכון" — **זה עדיין הסוכן מחליט**, רק עם ניסוח טוב יותר. נסגר ללא מיזוג
לפי החלטת הבעלים: זה לא תואם את הארכיטקטורה המוחלטת.

## התיקון

הורחב דפוס ה-Turn Coordinator הקיים של `CREATE_TASK` ל-`Intent.CREATE_DEAL`
חדש — **ללא** המצאת מנגנון חדש:

1. **`core/router/route_decision.py`** — `Intent.CREATE_DEAL` חדש (Tier 5).
2. **`core/router/intent_router.py`** — כלל regex חדש (`(פתח|תפתח|צור|תיצור|הוסף|תוסיף).*(עסקה|עסק חדש|deal)`
   → `Intent.CREATE_DEAL`, confidence 0.95), אחרי `CLOSE_DEAL`/`UPDATE_DEAL_STAGE`
   (אין חפיפת מילות-מפתח, הסדר לא קריטי).
3. **`core/router/risk_router.py`** — `Intent.CREATE_DEAL` נוסף ל-`_NORMAL_INTENTS`
   (אותה קבוצה כמו `CREATE_TASK`) וגם ל-`_CONTRACT_REQUIRED_INTENT_TO_TOOL`
   (`Intent.CREATE_DEAL → "crm_create_deal"`) — כך ש-PA-01's
   `intent_requires_contract_for_success()`/`contract_capable_this_turn()`
   מכירים את הכלי הקנוני הנכון ל-Deal (בניגוד ל-Task, שאין לו כלי ייעודי
   ומשתמש ב-`airtable_add`, ל-Deal יש `crm_create_deal` אמיתי מ-PR1153).
4. **`core/router/router.py`** — `_STRUCTURED_CREATE_DEAL_RE` (anchored
   fullmatch, מבנה קשיח: `<פועל> עסקה בשם X בתחום Y` או הסדר ההפוך, עם
   סיומת אופציונלית `בבעלותי`), `DeterministicDealParse` (name/domain,
   `certain` דורש את שניהם), `parse_deterministic_create_deal()`, וחיווט
   `Handler.TOOL`/`Handler.CLARIFY` בדיוק כמו `CREATE_TASK`'s (שורות
   ~327-336 ו-~415-421).
   - **ממצא/תיקון תוך-כדי-בנייה**: בקשה מפורשת עם בעלים אחר ("בבעלות אורי")
     אינה תואמת את הסיומת `בבעלותי` המדויקת, ובלי guard מפורש נבלעה בשקט
     לתוך שדה `domain` (קבוצת ה-`.+?` הבלתי-חמדנית פשוט ממשיכה עד סוף
     המשפט). נוסף guard מפורש: `"בעלות" in name or "בעלות" in domain` →
     `uncertain=True` — נכשל ל-CLARIFY במקום לכתוב שדה מזוהם. מכוסה ע"י
     regression ייעודי (ראה Verification).
5. **`app.py`** — `_queue_deterministic_create_deal()` (מראה מדויק את
   `_queue_deterministic_create_task()`, אך פשוט יותר: אין שלב resolution
   של ישות קיימת — זו רק CREATE — ואין צורך ב-table/fields translation כי
   `crm_create_deal` הוא כבר כלי קנוני ייעודי). `enforce("crm_create_deal",
   identity)` נבדק **לפני** כל הצעה ל-ActionGateway. `owner_id` מכוונת
   מושמט מה-payload בכוונה — `tools/dispatcher.py`'s `case "crm_create_deal":`
   הקיים (מ-PR #1166) כבר פותר owner חסר מהזהות המאומתת. חווט לתוך
   `app.py`'s turn flow מיד אחרי `create_task`/`update_task`/`complete_task`'s
   בלוקים הדטרמיניסטיים הקיימים, לפני LeadCandidateHandler ו-Agent.

## Cross-Layer Impact Matrix

- **Router (`core/router/*.py`)**: touched directly — `Intent` חדש,
  regex, risk policy, deterministic parser/gate.
- **`app.py`**: touched directly — פונקציית queue חדשה + חיווט ב-turn flow.
- **`tools/dispatcher.py`/`commercial_crm.py`/`tool_registry.py`**: NOT
  touched — `crm_create_deal`'s תיקוף/הרשאה/ביצוע נשארים בדיוק כפי שהיו;
  הנתיב הדטרמיניסטי רק **מציע** contract לאותו כלי קנוני קיים, לא ממציא
  כלי חדש או עוקף `enforce()`.
- **ActionGateway/execution-proof**: NOT touched — `fingerprint_payload`
  הוא בדיוק אותה צורה שנשלחת בפועל ל-dispatcher (`{"name":..., "domain":...}`,
  תואם `inputs["name"]`/`inputs["domain"]` בבלוק ה-`crm_create_deal` הקיים
  ב-dispatcher) — אין סיכון ל-BUG-TASK-01-class mismatch (מפתחות
  טבלה/שדה שלא תואמים את ה-payload האמיתי שנשלח לביצוע).
- **PA-01 contract-required policy**: `Intent.CREATE_DEAL` מצטרף למדיניות
  הקיימת — כשל בבניית contract עבור `crm_create_deal` ייכשל את
  `intent_requires_contract_for_success()`'s בדיקה, בדיוק כמו לכל intent
  אחר במדיניות זו.

## CI enforcement — `tools/audit_turn_coordinator_bypass.py`

בעקבות סבב הכשלים החוזרים (#1165→#1166→#1169→#1171), נוסף שער CI חוסם
(`tools/audit_turn_coordinator_bypass.py`, מריץ ב-`backend-ci` מיד אחרי
`audit_dispatcher_bypass.py`) שמונע **חזרה** על אותה מחלקת באג, לא רק
סוגר את המופע הנוכחי שלה. שלושה checks עצמאיים:

1. **ROUTE_REGRESSION** — כל `Intent` שכבר קיבל שער דטרמיניסטי
   (`CREATE_TASK`/`UPDATE_TASK`/`COMPLETE_TASK`/`CREATE_DEAL`) חייב לשמור
   גם על שער `Handler.TOOL` (למקרה "certain") וגם על נפילה ל-`Handler.CLARIFY`
   (למקרה "uncertain") — רץ על העץ הנוכחי תמיד, לא רק על diff, כדי שהסרה
   שקטה של שער קיים תיכשל גם ב-PR לא-קשור שנוגע ב-`router.py`.
2. **NEW_TOOL_UNROUTED** — כלי `ToolMeta` חדש שנוסף ל-`tool_registry.py`
   עם `requires_approval=True`+`high_risk=True` ושם התואם למוסכמת
   "יוצר רשומה עסקית חדשה" (`crm_create_*`/`create_*`) חייב רישום מפורש
   ב-`_TC_ROUTE_REGISTRY` של הסקריפט — `ROUTED` (עם Intent קיים שבאמת
   מקושר) או `EXEMPT` מנומק. בלי רישום → חסימה. זה בדיוק המקרה שקרה
   בפועל: `crm_create_deal` היה כלי קנוני קיים בלי אף מנגנון שמונע מהסוכן
   לעקוף אותו.
3. **SCHEMA_NUDGE_LANGUAGE** — תיאור כלי חדש ב-`tools/schemas.py` שמכיל
   ניסוח "אל תשתמש"/"חובה להשתמש"/וכו' נחסם אלא אם אותו diff נוגע גם
   ב-`core/router/router.py` — תופס במדויק את הדפוס של PR #1171 (לנסות
   לפתור בחירת-כלי ע"י ניסוח טוב יותר ל-LLM במקום ניתוב דטרמיניסטי).

בדיקות: `test_audit_turn_coordinator_bypass.py` (16 בדיקות, כולל אימות
שהרישום/השערים בפועל בקוד תואמים, לא רק שהלוגיקה של הסקריפט נכונה על
קלט מזויף). מומש כ-static/read-only בלבד — אותו invariant כמו כל שאר
`tools/audit_*.py`.

## Verification

- `python3 -m py_compile app.py core/router/*.py test_bug_crm_bypass_create_deal_deterministic_route.py` — עבר
- `python3 test_bug_crm_bypass_create_deal_deterministic_route.py` — כל הבדיקות עברו, כולל:
  - פענוח certain/uncertain/no-match (כולל regression מפורש לבאג ה-"בעלות אורי" שנמצא ותוקן תוך-כדי)
  - `route_request()`: בקשה מובנית → `Handler.TOOL`; בעלים מפורש אחר → `Handler.CLARIFY`; ניסוח חופשי → `Handler.AGENT`; תפקיד `lead` → `Handler.AGENT` גם עם ניסוח מובנה
  - `enforce()` חוסם לפני כל הצעה ל-ActionGateway עבור זהות לא-מורשית
  - **end-to-end אמיתי**: `app.run_agent()` עם `app.client.messages.create` שמשליך `AssertionError` אם נקרא — מוכיח `agent_calls=0` בפועל, לא רק בלוג. contract יחיד, `tool_name="crm_create_deal"`, בלי `owner_id` מזויף.
- `python3 core/router/test_router.py` — 54/54 (4 מקרי CREATE_DEAL חדשים)
- רגרסיה מלאה: `smoke_tests.py`, `test_integration.py`, `test_create_task_deterministic_route.py`,
  `test_bug_task_01_execution_proof_fingerprint_parity.py`, `test_action_gateway.py` (46/46),
  `test_stage_b_full_suite.py` (128/128), `test_commercial_crm.py` (97/97),
  `test_commercial_crm_dispatcher_wiring.py` (40/40), `test_bug_commercial_crm_dispatcher_bypass_closure.py`,
  `test_commercial_crm_owner_ssot.py`, `test_f14_contact_gate.py` (8/8), `test_f14_b2_contact_integration.py` (21/21),
  `test_bug_contact_03_invalid_status_feedback.py` (15/15), `test_a32_enforcement.py` (6/6),
  `test_identity_smoke.py` (4/4), `test_airtable_gateway.py` (37/37), `test_approval_concurrency.py` (22/22),
  `test_c53a.py` (50/50), `test_inbound_handler.py` (8/8), `test_avi_pilot_scope.py` — כולם ירוקים.
- `python3 tools/audit_dispatcher_bypass.py` — `new=0`
- `python3 tools/audit_turn_coordinator_bypass.py` — `PASS`
- `python3 -m pytest test_audit_turn_coordinator_bypass.py -q` — 16/16
- `git diff --check` — נקי
- `python3 -c "import app; import tma_api; import tools.dispatcher"` (עם משתני CI) — עבר

## PRs שנסגרו/הוחזקו כתוצאה מהחלטה זו

- **PR #1171** (`route Commercial CRM through canonical tools`) — **נסגר ללא
  מיזוג**. תיקן את בעיית בחירת הכלי ע"י שיפור תיאורי כלים בלבד — עדיין
  הסוכן בוחר, לא המערכת. הוחלף ע"י המסמך הזה.
- **PR #1169** (`map generic CRM field aliases before owner resolution`) —
  **מוחזק (לא ממוזג, לא נסגר)**. שכבת היירוט הגנרית ב-`tools/dispatcher.py`
  נשארת הגנת-עומק לגיטימית (התאמה דטרמיניסטית בקוד, לא תלות בבחירת
  הסוכן) — אבל אינה עוד הנתיב הראשי ל-Deal creation. יש להעריך מחדש
  לאחר שהנתיב הדטרמיניסטי הזה ב-production, כולל הפער שנמצא בו (מיפוי
  aliases גלובלי במקום per-table — "בעלות" ל-Payment/PaymentTerm לא
  יעבוד נכון, ראה השיחה המקורית).

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.** דורש קנרית owner-approved אמיתית (בקשת "צור עסקה
בשם X בתחום Y" מ-Telegram) אחרי merge+deploy, בהתאם לכלל הברזל
ב-CLAUDE.md.
