# BUG-157 — atomic fingerprint claim in propose_action()

**תאריך:** 05/08/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— נוגע ישירות ב-Durable Atomic Approval layer (שכבה 4): `ActionGateway.propose_action()`
ו-`ExecutionLedger`.
**רקע:** נמצא ע"י ביקורת CodeRabbit על PR #550 (BUG-153/154/155/156), הועלה
ל-owner (04/08/2026, AskUserQuestion) — הוחלט להשאיר ל-PR נפרד. זהו אותו PR.

## הבעיה

`propose_action()` מבצע `find_by_fingerprint()` (בדיקת קיום) ואז, בהמשך
הפונקציה, `save()` (יצירת contract חדש) — כשני צעדים נפרדים, ללא נעילה
המקיפה את שניהם יחד. `ExecutionLedger._lock` קיים ומגן על כל אחת מהפעולות
בנפרד (`save()`, `_cache_contract()`, `find_by_id()` recovery), אך לא על
הרצף לוקאפ-ואז-שמירה כיחידה אטומית אחת.

**זה לא תיאורטי גרידא.** אומת ב-04-05/08/2026 שקיימות שתי thread נפרדות
באותו תהליך Python (לא שני processes — `gunicorn.conf.py` נועל `workers=1`,
זה עדיין נכון וללא שינוי):
- ה-thread הראשי שמטפל בבקשות webhook נכנסות (Flask, סינכרוני).
- `scheduler.py`'s `threading.Thread(target=_run_scheduler, daemon=True,
  name="scheduler")` (`scheduler.py:844`) — thread נפרד לגמרי, ריצה
  מקבילה אמיתית בתוך אותו process.

`core/lead_recovery.py:257` ו-`followup_engine.py:212` שניהם קוראים
ל-`ActionGateway.propose_gated()` (שקורא ל-`propose_action()` פנימית) —
ונקראים ממשימות scheduler, כלומר **מה-scheduler thread**. תרחיש אמיתי:
ה-scheduler thread מציע פעולת followup בדיוק כש-webhook thread מציע פעולה
אחרת עם אותו fingerprint עסקי (או, בתנאי race צר יותר, שתי בקשות scheduler
עוקבות-כמעט-בו-זמנית) — שני threads יכולים לעבור את בדיקת "אין existing
חוסם" **לפני** ששניהם השלימו `save()`, וכל אחד יוצר contract נפרד לאותו
fingerprint.

## התיקון

CAS (compare-and-set) אטומי על אינדקס ה-`_by_fingerprint` הקיים ב-RAM,
תחת `ExecutionLedger._lock` הקיים — לא מנגנון נעילה חדש, לא תלות חדשה.

### `ExecutionLedger` — שלוש תוספות

1. **`_claimed_fingerprints: set[str]`** — סט חדש, state פנימי בלבד,
   מייצג "fingerprint שנתפס ע"י proposer כלשהו, טרם נשמר contract בפועל."
2. **`claim_fingerprint_cas(fingerprint, expected_contract_id) -> bool`**
   — תחת `self._lock` יחיד:
   - אם `_by_fingerprint[fingerprint]` **שונה** מ-`expected_contract_id`
     (מישהו אחר כבר שינה את זה מאז ה-lookup של הקורא) → `False` (הפסיד את
     ה-race).
   - אם `fingerprint` כבר ב-`_claimed_fingerprints` (proposer מקביל אחר
     תפס אותו הרגע, טרם שמר) → `False`.
   - אחרת → מוסיף ל-`_claimed_fingerprints`, מחזיר `True` (זכה בזכות
     ליצור contract חדש לfingerprint הזה).
3. **`release_fingerprint_claim(fingerprint)`** — משחרר claim שלא
   הבשיל ל-`save()` מוצלח (idempotent — `discard()`, בטוח לקרוא גם אם
   כבר שוחרר). `_cache_contract()` גם משחרר אוטומטית claim על save מוצלח.

### `propose_action()` — לולאת retry חסומה

הרצף "lookup existing → status-branch checks (ללא שינוי בהתנהגות) → claim"
עטוף בלולאה חסומה (5 ניסיונות). אם ה-claim נכשל (race הפסיד), הלולאה
חוזרת ל-lookup טרי — שרואה עכשיו את מה שה-thread המנצח כבר שמר, ומחזירה
את תגובת ה-dedup הנכונה לפי המצב העדכני (אותה לוגיקה קיימת, לא שוכפלה).
אם 5 הניסיונות נכשלים (עומס מתמשך חריג, לא צפוי בפועל) — מוחזר כשל מפורש
"עומס גבוה, נסה שוב", לא תקיעה שקטה.

**ללא שינוי בהתנהגות בתנאי single-threaded/single-caller** (המקרה
הנפוץ בהחלט) — ה-claim תמיד מצליח בניסיון הראשון כש-אין race אמיתי, כי
`expected_contract_id` תמיד תואם בדיוק את מה שה-lookup הרגע ראה.

## Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
touched: not touched
input/output/authority impact: אין
shared identifiers: אין
invariants: לא רלוונטי
failure semantics: לא רלוונטי
observability: לא רלוונטי
cross-layer tests: `grep -n "leads_reasoning_projection\|BUG-104" core/action_gateway.py` — 0 תוצאות

### שכבה 2 — TurnCoordinator
touched: not touched
input impact: אין — `route_request()`/`core/turn_coordinator_runtime.py` לא נגעו
output impact: אין
authority impact: אין
shared identifiers: אין
invariants: `agent_calls=0` למסלול דטרמיניסטי — לא מושפע (התיקון כולו בתוך
  `propose_action()`, קרוי באותו אופן בדיוק מכל הקוראים הקיימים)
failure semantics: לא רלוונטי
observability: לא רלוונטי
cross-layer tests: `core/router/test_router.py` (44/44) הורץ ללא שינוי

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: indirectly
input impact: אין שינוי ל-`ToolMeta`/`tools/schemas.py`/`tools/dispatcher.py`
output impact: `GatewayResult` shape ללא שינוי — נוסף רק `failure_code`
  אפשרי חדש (`persistence_lookup_failed`, ערך קיים כבר בשימוש, לא ליטרל חדש)
  למקרה הקצה של תשישות-ניסיונות תחת עומס
authority impact: אין
shared identifiers: אין
invariants: `trusted_source` distinctions (BUG-091, BUG-153) נשארות זהות —
  ה-claim מופעל **אחרי** כל בדיקות ה-status הקיימות, לא לפניהן/לא במקומן
failure semantics: כשל-claim חוזר ל-caller כ-`GatewayResult(ok=False, ...)`
  רגיל — לא exception חדש, לא crash, fail-closed עקבי עם שאר הפונקציה
observability: `logger.info`/`logger.error` חדשים ל-race-lost/exhausted —
  נראות חדשה, אין שינוי ללוגים קיימים
cross-layer tests: `test_bug153_create_task_reconfirmation_after_rejection.py`
  (16/16, ללא שינוי-אחורה), `test_action_gateway.py` (43/43, ללא שינוי)

### שכבה 4 — Durable Atomic Approval
touched: directly
input impact: `propose_action()` מקבל אותה חתימה בדיוק — אין שינוי API
output impact: **התנהגות חדשה רק תחת race אמיתי** — שני proposers מקבילים
  עם אותו fingerprint: הראשון זוכה וממשיך כרגיל; השני מקבל תגובת dedup
  עדכנית (לא כפילות). בתנאי single-caller — **byte-identical** להתנהגות
  הקיימת (הlookup+claim תמיד מצליח בניסיון הראשון, אין שינוי בערכים
  מוחזרים)
authority impact: אין הרחבת סמכות — עדיין `propose_action()` בלבד קובע
  יצירת contract; ה-claim הוא מנגנון-הגנה פנימי, לא נקודת-החלטה חדשה
shared identifiers: `_claimed_fingerprints`/`claim_fingerprint_cas`/
  `release_fingerprint_claim` הם שמות חדשים לגמרי, לא הגדרה-מחדש של קיים
invariants: **מבטיח לראשונה** ש-fingerprint עסקי אחד לא יכול להפיק שני
  contracts חיים בו-זמנית תחת race אמיתי — invariant זה תמיד היה הכוונה
  (הערה בתחילת הקובץ: "ActionContract הוא מקור האמת לכל mutation עסקי"),
  לא נאכף במלואו לפני התיקון הזה
failure semantics: תשישות-ניסיונות (5, עומס קיצוני שלא נצפה במציאות) →
  תגובת כשל מפורשת למשתמש, לא תקיעה/exception לא-מטופל
observability: לוגים חדשים (ראה שכבה 3)
cross-layer tests: `test_business_action_fingerprint_normalization.py`
  (8/8, ללא שינוי), `test_pr0c_action_gateway_adapters.py`,
  `test_phase_4b_1a_durable_proposals.py`, `test_phase_4b_1a_lookup_correctness.py`
  (כולם ללא שינוי) — טסט חדש (`test_bug157_atomic_fingerprint_claim.py`)
  מדגים ריצה מקבילה אמיתית (threading) עם אותו fingerprint, מוודא contract
  חי יחיד ולא שניים

### Proof of non-impact — שכבות 1, 2
1. grep evidence: `grep -n "leads_reasoning_projection\|BUG-104\|route_request\|RouteDecision\|TurnCoordinator" core/action_gateway.py` (בטווח השינוי) — 0 תוצאות
2. unchanged-tests evidence: `core/router/test_router.py` (44/44), `test_bug104_*.py` (5 חבילות) — לא נוגעים בקובץ ששונה, לא הורצו מחדש מסיבה זו
3. no-new-coupling evidence: אין import חדש מ-`core/router/*`/`core/leads_reasoning_projection.py`

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)
applies: yes — נוגע ב-`ActionContract` lifecycle (יצירת contract). **איך:**
אין מנגנון grounding/evidence עצמאי נוסף — עדיין `ActionContract`/
`GatewayResult` הם מקור האמת היחיד. ה-claim הוא מנגנון concurrency-safety
פנימי בתוך שכבה 4, לא evidence/status claim כלפי המשתמש.

## עדכון (05/08/2026) — סבב ביקורת שני של CodeRabbit: המתנה ל-claim משתחרר

**רקע:** PR #552 (הגרסה המקורית של תיקון זה — retry ללא המתנה) מוזג
ל-`main` (`c5dbe86`). בסבב ביקורת שני על אותו PR, **אחרי** המיזוג,
CodeRabbit העלה ממצא Major נוסף שלא הספיק להיכלל ב-#552: ה-retry loop
היה "מפסיד → lookup טרי מייד" ללא שום המתנה. תחת `FEATURE_ACTION_
CONTRACT_PERSISTENCE=on` (כתיבה עמידה אמיתית עם latency לא-טריוויאלי
ב-`save()`), מפסיד יכול היה למצות את כל 5 ניסיונות ה-retry בזמן
שהמנצח עדיין באמצע כתיבה ל-repository, ולקבל תגובת כשל "עומס גבוה"
שגויה — במקום להמתין ולקבל את תגובת ה-dedup הנכונה מול ה-contract
שהמנצח בפועל יצר. **זהו PR נפרד חדש** (לא #552 שנסגר עם המיזוג) —
אושר במפורש ע"י ה-owner להמשך יישום.

### התיקון הנוסף

1. **`ExecutionLedger`**: `self._claim_released_condition =
   threading.Condition(self._lock)` — Condition על אותו lock קיים, לא
   מנגנון נעילה נפרד.
2. **`claim_fingerprint_cas(fingerprint, expected_contract_id, *,
   wait_timeout: float = 0.0)`** — פרמטר חדש, ברירת מחדל `0.0`
   (התנהגות זהה למקור אם לא מועבר במפורש). אם ה-claim נכשל **ספציפית**
   כי claim מתחרה כרגע בתהליך (לא כי `_by_fingerprint` כבר מצביע על
   מצב סופי שונה — שם המתנה לא עוזרת) — ממתין עד `wait_timeout` שניות
   ל-`notify_all()` מ-`release_fingerprint_claim()`/`_cache_contract()`,
   בודק מחדש, חוזר עד שה-timeout חולף.
3. **`propose_action()`**: `_CLAIM_TOTAL_WAIT_BUDGET_SECONDS = 2.0` —
   תקציב המתנה **כולל** (לא per-attempt) על פני כל 5 הניסיונות יחד;
   מחושב `deadline` פעם אחת לפני הלולאה, וכל ניסיון מעביר את הזמן
   שנותר (`wait_timeout=_remaining_wait`, יורד עם כל סיבוב). בתנאי
   ללא-race — ההמתנה אף פעם לא מופעלת בפועל (ה-claim תמיד מצליח
   בניסיון הראשון, `wait_timeout` לא נוגע).

### בדיקה חדשה — section 6 ב-`test_bug157_atomic_fingerprint_claim.py`

מדמה `save()` איטי (delay מלאכותי 0.5s, מונקי-פאץ' על ה-instance
`ledger.save`) עם 2 threads מקבילים על אותו fingerprint. מוודא:
- שני הקריאות חוזרות (אין deadlock/תקיעה).
- המפסיד מקבל את ה-contract_id **של המנצח** (dedup אמיתי), **לא**
  `failure_code="persistence_lookup_failed"`.
- הזמן הכולל של המרוץ חסום ע"י delay ה-save היחיד של המנצח (~0.5s),
  לא מוכפל ע"י ניסיונות retry חוזרים.

24/24 (היה 18/18) — 6 בדיקות חדשות, כל הקיימות ללא שינוי-אחורה.

## Verification

- `python3 -m py_compile core/action_gateway.py`
- `python3 test_bug157_atomic_fingerprint_claim.py` — 24/24 (כולל
  section 6 החדש, threading אמיתי לא רק mock)
- `python3 test_action_gateway.py` — 43/43, ללא שינוי
- `python3 test_business_action_fingerprint_normalization.py` — 8/8, ללא שינוי
- `python3 test_bug153_create_task_reconfirmation_after_rejection.py` — 16/16, ללא שינוי
- `python3 test_bug155_ttl_expiry_contract_id_lookup.py` — 5/5, ללא שינוי
- `python3 test_bug156_due_time_note_and_fingerprint_exclusion.py` — 11/11, ללא שינוי
- `python3 test_first_pending_notification_failure_suppression.py` — 14/14, ללא שינוי
- `python3 core/router/test_router.py` — 44/44, ללא שינוי
- `python3 smoke_tests.py` / `test_integration.py` — ירוק

## סטטוס

**חלק 1 (retry loop בסיסי, ללא המתנה):** מוזג ל-`main` ב-PR #552
(`c5dbe86`), 05/08/2026. **Production-verified: לא בוצע** (אין עדיין
הוכחת deploy+prod evidence לפי כלל הברזל).

**חלק 2 (המתנה ל-claim משתחרר, מסמך זה):** עיצוב אושר ע"י owner
(05/08/2026). קוד מומש ונבדק מקומית (24/24). **לא מוזג (PR נפרד חדש,
טרם נפתח בזמן כתיבת שורות אלו), לא deployed, לא verified בפרודקשן.**
