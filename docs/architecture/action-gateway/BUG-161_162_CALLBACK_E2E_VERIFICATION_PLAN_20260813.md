# BUG-161/162 — Callback-Path E2E Production Verification Plan (13/08/2026)

**מטרת המסמך:** תשריט מדויק, בר-ביצוע, לסגירת הפער שכבר מתועד ב-`TC6_APP_
INTEGRATOR_PATCH_SPEC.md`'s Status ו-`GAP_ANALYSIS.md`: TC6 אומת בפרודקשן
ל-3 תרחישים טקסטואליים בלבד (יצירה→pending, status query, חסימת יצירה
שנייה). **callback-button flow (approve/reject), TTL expiry, ו-replay/
duplicate callback מעולם לא אומתו באותה שיטה.** זה בדיוק אותה שיטה ש-
`PRODUCTION_30JUL2026_RENDER_VERIFICATION.md` ו-`TC6_APP_INTEGRATOR_PATCH_
SPEC.md`'s Status note השתמשו בה — Render dashboard/API + application logs
+ Telegram transcript אמיתי.

**לא ממומש בסבב הזה** — זה תשריט-ביצוע, לא ראיה. הסעיפים המסומנים
✅-preflight בוצעו בפועל (read-only, GET-only מול Render API); הסעיפים
המסומנים 👤 דורשים אינטראקציה אמיתית בטלגרם מול הבוט החי — לא ניתנים
לביצוע ע"י Claude (אין גישה לחשבון טלגרם אמיתי/session אנושי).

---

## 0. Preflight — בוצע בפועל, 13/08/2026 (read-only, GET בלבד)

| בדיקה | Production (`srv-d80ehsf7f7vs73cq5rn0`) | Staging (`srv-d99uq63eo5us73967cj0`) |
|---|---|---|
| Latest deploy status | `live` | `live` |
| Deployed commit | `f14190d` (PR #613) | `f14190d` (PR #613) |
| `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` | `true` | `true` |
| `FEATURE_ACTION_GATEWAY` | `true` | `true` |
| `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` | `true` | `true` |

**מסקנה:** שני הסביבות פרוסות על אותו commit בדיוק, עם שני הדגלים
הרלוונטיים דלוקים — הקוד שנותח ב-authority audit (Branch A/B המאוחד,
TC8 claim, כל ה-fail-closed branches בנתיב ה-callback) **הוא בדיוק הקוד
החי כרגע**, לא ניתוח מול קוד ישן. `origin/main` המקומי כרגע (`252c8ff`)
כולל 2 commits נוספים שטרם נפרסו (לא נוגעים ב-`app.py`) — אין drift
רלוונטי ל-BUG-161/162.

**פקודת חזרה (idempotent, GET בלבד):**
```bash
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/srv-d80ehsf7f7vs73cq5rn0/deploys?limit=1"
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/srv-d80ehsf7f7vs73cq5rn0/env-vars?limit=100"
```
(אותו דבר עם `srv-d99uq63eo5us73967cj0` ל-staging.)

---

## 1. סדר מומלץ — Staging קודם

לפי התקדים הקיים ברפו (`RP5_LOG_OBSERVATION_23JUL2026.md`,
`CORE_COMPLETION_AUDIT_20260810.md`): כל תרחיש מבוצע קודם מול
**staging** (`my-bot-approval-staging`), ורק אחרי שהראיה נקייה — חוזרים
עליו מול **production**. staging הוא בוט טלגרם אמיתי, נפרד, לא משפיע על
משתמשים אמיתיים.

---

## 2. שישה התרחישים — צעדים + ראיה נדרשת לכל אחד

לכל תרחיש: (1) פעולה 👤 בטלגרם מול הבוט, (2) exact log marker לחיפוש
אחרי, (3) מה לתעד.

### 2.1 Approve — happy path (baseline, לא כוסה קודם לנתיב callback)
👤 שלח בקשה שיוצרת ActionContract (למשל "תוסיף משימה: להתקשר ללקוח
מחר"), לחץ ✅ על הכפתור.
**Marker לחיפוש:** contract_id (מהלוג של יצירת ה-contract) + חפש `[TC8]`
ליד אותו contract_id — **העדר** אזהרת `[TC8] callback approval ownership
unavailable` פירושו claim הצליח; ואז ודא ב-Airtable/log ש-`status`
הגיע ל-`completed`/`executed`.
**לתעד:** contract_id, timestamp, screenshot/טקסט התשובה היחידה שהתקבלה
בטלגרם (צריך להיות **אחת בלבד**, לא כפולה).

### 2.2 Reject
👤 בקשה נוספת, לחץ ❌.
**Marker:** `[ActionGateway] reject callback durable transition failed`
**צריך שלא יופיע** (זה error path); ודא `status == "rejected"` ב-log/
Airtable.
**לתעד:** contract_id, תוכן ההודעה הסופית (צריך לנקוב שהפעולה בוטלה,
לא "אשר בבירור" — זה בדיוק BUG-161's regression surface).

### 2.3 Duplicate/replay callback — TC-12's testability gap
👤 לחץ ✅ **פעמיים ברצף מהיר** (double-tap) על אותו כפתור לפני שהראשון
מספיק לחזור — אם טלגרם מבטל את הכפתור אחרי שימוש (כפי ש-TC-12 כבר
תיעד), נסה גם: שלח את אותה בקשה **פעמיים** (כפילות-fingerprint) ובדוק
שהכפתור השני נחסם ב-`existing_pending_blocks_agent`, וגם נסה ללחוץ על
כפתור שכבר טופל (התרחיש הבא, 2.4, מכסה replay-אחרי-resolve בפועל).
**Marker:** `[ActionGateway] SB-02: blocked duplicate callback` **או**
`[TC8] callback approval ownership unavailable` (אם התנגשות claim
תפסה קודם).
**לתעד:** האם בדיוק תשובה סופית **אחת** נשלחה, לא שתיים; מספר קריאות
בפועל ל-dispatch (מה-log — צריך להיות פעם אחת בלבד).

### 2.4 Stale/already-resolved callback (לחיצה חוזרת אחרי resolve)
👤 אחרי 2.1/2.2 (contract כבר terminal), לחץ שוב על אותו כפתור אם
עדיין קיים ב-Telegram (או שלח מחדש callback_data זהה אם יש לך גישה ל-
Bot API ישירות — ראו §3 להצעת automation ל-replay מדויק).
**Marker:** `[ActionGateway] blocked post-completion callback fallthrough`
או `_notify_stale_or_resolved_callback`'s log path.
**לתעד:** אפס dispatches נוספים, תשובה דטרמיניסטית אחת ("כבר בוצעה"/
"כבר בוטלה").

### 2.5 TTL expiry
👤 שלח בקשה, **המתן >10 דקות** (`_PENDING_APPROVAL_TTL=600`), לחץ ✅.
**Marker:** `[Approval] TTL-expired callback:` (יש שני variants בקוד —
ActionContract ו-legacy — חפש את שניהם).
**לתעד:** ההודעה "⏰ פג תוקף — הפעולה לא בוצעה", contract לא בוצע.

### 2.6 Clarification / multi-contract conflict (BUG-122)
👤 עם ≥1 בקשה pending כבר קיימת, שלח בקשה חדשה דומה (fingerprint שונה
אך intent זהה, כדי להגיע ל-BUG-122 gate, לא ל-dedup).
**Marker:** `[BUG-122] pending_gate_decision=ask_queue_resolution`
**לתעד:** ההודעה מבקשת *מאשר*/*בטל* מפורש, לא מבטיחה פעולה.

---

## 3. Automation חלקי (TC-12's המלצה המתועדת) — מומש 13/08/2026

`BUG_AUDIT_LOG.md` שורה 4824 כבר המליצה במפורש: integration test שקורא
ל-`_handle_approval_callback_impl` **ישירות** (לא דרך Telegram UI) כדי
לעקוף את מגבלת "הכפתור מתבטל אחרי שימוש". **מומש**:
`scripts/verify_bug161_162_callback_staging.py` — קורא ל-handler האמיתי
in-process, מול ה-`ActionGateway`/`TurnStateRepository`/Airtable *האמיתיים*
של staging (לא test doubles), עם `app.bot`/`app.resolve_identity` מדומים
בלבד (אותה טכניקה בדיוק ש-`test_bug_stale_callback_ux.py` כבר משתמש בה).
מכסה 2.1 (approve), 2.2 (reject), 2.3 (duplicate — גם רצף מיידי וגם race
של threads אמיתי דרך `TC8`'s claim), 2.4 (stale/resolved), ו-2.5 (TTL,
באותה טכניקת backdating כמו `test_bug112_telegram_approval_ttl.py`). **לא
מכסה 2.6** (clarification/BUG-122) — זה תרחיש ברמת `run_agent()`/טקסט, לא
callback, ונשאר ב-§2.6 כתרחיש-ידני.

**הרצה** (על Render staging shell, לא מקומית — התלות ב-`DATABASE_URL`/
Airtable/Render env האמיתיים של staging, כמו `scripts/verify_bug157_160_
163_staging.py`'s docstring):
```bash
python3 scripts/verify_bug161_162_callback_staging.py
```
**מגבלה מאומתת (13/08/2026, מקומית, credentials מזויפים):** רץ עד הסוף
ללא crash על כל 6 החלקים, לא נכנס ל-CI (יוצר רשומות אמיתיות ב-Airtable —
לא מתאים ל-CI). לא הורץ עדיין מול staging אמיתי — זה עדיין העבודה
שנותרה, לא ראיית-production.

---

## 4. איסוף ראיה אחרי כל תרחיש

```bash
python3 scripts/render_log_export.py export \
  --owner-id tea-d804tr8sfn5c7398geag \
  --service-id <srv-id-of-tested-env> \
  --marker "<exact marker from §2>" \
  --catch-up-days 1 \
  --export-dir render_logs/bug161_162_verification
```
תוצאה נשמרת ב-`render_logs/` (gitignored — לא מחויב).

## 5. תבנית תיעוד סופית (למלא לכל תרחיש, לפי כלל הברזל של CLAUDE.md)

```
תרחיש: <2.1-2.6>
סביבה: staging | production
contract_id: <...>
deploy commit: <...>
timestamp: <...>
log evidence: <קובץ/שורה מ-render_logs/>
Telegram transcript: <טקסט/screenshot>
תוצאה: PASS | FAIL — <תיאור>
```

**STATUS: 🟡 PLAN + AUTOMATION READY, NOT YET RUN AGAINST STAGING — 0/6 תרחישים בוצעו בפועל.**
**EVIDENCE: preflight §0 (Render API, read-only, 13/08/2026); automation for
2.1-2.5 written and smoke-tested locally with fake credentials (no crash,
structurally sound) — `scripts/verify_bug161_162_callback_staging.py`,
commit `89087b4`. Not yet executed against real staging — running it there
is the actual remaining evidence gap, not code.**
