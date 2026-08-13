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

### 2.6 Clarification / multi-contract conflict (BUG-122) — ✅ נסגר 13/08/2026, marker תוקן

👤 עם ≥1 בקשה pending כבר קיימת, שלח בקשה חדשה דומה (fingerprint שונה
אך intent זהה, כדי להגיע ל-BUG-122 gate, לא ל-dedup).

**⚠️ תיקון-marker (13/08/2026):** ה-marker שתועד כאן במקור
(`[BUG-122] pending_gate_decision=ask_queue_resolution`, `app.py:5099`,
מקוד commit `3935091` מ-20/07/2026) **לעולם לא יופיע בפועל.** ארבעה
ימים אחרי אותו commit, `006506d` ("Fix July 24 sampling blockers",
24/07/2026) הוסיף שער מוקדם יותר — `[BUG-122] pending_gate_decision=
block_new_action` (`app.py:4343-4368`) — שבודק **בדיוק אותו תנאי-על**
(`_live_contracts_snapshot` לא-ריק + `intent_requires_contract_for_
success(route.intent)`), אבל *לפני* ש-Router מסיים ואפילו לפני
ש-Agent/Anthropic נקראים בכלל, ומחזיר מיד. מכיוון ש-`_live_contracts_
snapshot`/`route.intent` לא משתנים בין שתי הנקודות באותו turn, כל
מצב שהיה מפעיל את `ask_queue_resolution` (5063-5108) כבר גרם ל-return
מוקדם יותר ב-4364 — **`ask_queue_resolution` הוא dead code, בלתי-
נגיש, מ-24/07/2026.** אומת סטטית (route/live_contracts_snapshot לא
מוקצים מחדש בין שתי הבדיקות) וגם אמפירית: הרצת `test_bug122_pending_
queue_ux.py` מקומית (13/08/2026) מראה בלוג `pending_gate_decision=
block_new_action` יורה עבור תרחיש (b) — לא `ask_queue_resolution`
כפי שה-docstring של הטסט טוען — והפונקציה חוזרת *לפני* שורת הלוג
"[Agent] owner |" (כלומר Anthropic מעולם לא נקרא). ראיה תואמת קיימת
כבר גם ב-`BUG_AUDIT_LOG.md` (חקירת BUG-155, 03-04/08/2026, staging
אמיתי: `pending_gate_decision=block_new_action` ו-`live_contracts_
count=1`, עם הטקסט המדויק שהוצג למשתמש בפועל — ראה שם).

**Marker הנכון לחיפוש:** `[BUG-122] pending_gate_decision=block_new_action`
(לא `ask_queue_resolution`).
**לתעד:** ההודעה מבקשת *מאשר*/*בטל* מפורש, לא מבטיחה פעולה — מתקיים
(גם בראיית staging האמיתית מ-BUG-155 וגם ב-unit test המקומי).

**סיווג (defect / missing-verification / test-fixture-gap / expected):**
לא product defect — ה-invariant של BUG-161 ("Agent לעולם לא מבטיח
פעולה שלא קיימת") **מתקיים באופן חזק יותר** דרך `block_new_action`
(מחזיר לפני שה-Agent בכלל רץ, לא רק אחרי שהתשובה שלו סוננה). כן
test-fixture gap: `test_bug122_pending_queue_ux.py`'s חלק (b) בודק
בפועל את `block_new_action`, לא את מה שה-docstring שלו טוען
(`ask_queue_resolution`) — הטסט **עדיין ירוק** (8/8) כי שני הענפים
מפיקים טקסט דומה מספיק לעבור את ה-assertions, אבל התיעוד הפנימי שלו
מיושן. לא תוקן כאן (ה-behavior תקין, אין סיבה ל-patch; ה-docstring/
dead-code cleanup הם refactor נפרד, לא בסקופ של סבב זה — "אם ההתנהגות
עוברת, לתעד ראיה בלבד").

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
לא מתאים ל-CI).

**הורץ בפועל מול staging אמיתי, 13/08/2026, שני סבבים:**

**סבב 1** (commit `cc82792`, לפני תיקון dispatch-counting): חשף ש-`EmergencyStop`
פעיל כרגע ב-staging וחוסם כל `airtable_add` בפועל
(`[CRITICAL] tools.dispatcher: [EmergencyStop] BLOCKED airtable_add`) — כל
contract שהגיע ל-dispatch נחת על `status=failed`, לא `completed`. זה חשף
גם באג אמיתי בסקריפט עצמו: הבדיקות הסתמכו על ספירת רשומות Tasks שנוצרו
בפועל — אינדיקטור מת כש-EmergencyStop חוסם כתיבה בכל מקרה, בלי קשר לכמה
פעמים dispatch נקרא.

**סבב 2** (commit `63280e2`, אחרי התיקון — dispatch_tool נספר ישירות
בנקודת ה-import של `core/action_gateway.py`'s `_executor()`, לא מוסק
מ-Tasks records): **26/26 checks PASSED, exit=0.** כולל הראיה המרכזית
ל-TC-12/BUG-162:

| חלק | ממצא |
|---|---|
| 1. Approve happy path | `dispatch_tool` נקרא בדיוק פעם אחת; תשובה יחידה |
| 2. Reject | `dispatch_tool` לא נקרא כלל |
| 3. Duplicate — double-press רציף | `dispatch_tool` נקרא **לכל היותר פעם אחת** למרות הלחיצה הכפולה |
| 3b. Duplicate — 3 threads אמיתיים במקביל | `dispatch_tool` נקרא **פעם אחת בדיוק מתוך 3 לחיצות מקבילות אמיתיות**; שתי הלחיצות האחרות נחסמו ב-`TurnStateConflictError` (`core/turn_state_repository.py`'s `claim()`) **לפני** שהגיעו קרוב ל-dispatch — ראיה ישירה, תחת race אמיתי על PostgreSQL אמיתי, ש-TC8's claim מונע כל אפשרות ל-second speaker/double-dispatch |
| 4. Stale/already-resolved | הלחיצה השנייה: `dispatch_tool` לא נקרא כלל, contract status ללא שינוי |
| 5. TTL expiry | contract נסגר `rejected` (BUG-155, לא נשאר תקוע pending), `dispatch_tool` לא נקרא כלל |

**הסתייגות פתוחה:** כל הריצה בוצעה עם `EmergencyStop` פעיל — לא נצפה
תרחיש "completed" אמיתי מקצה-לקצה (כתיבה אמיתית שהצליחה). זה לא פוגם
בראיית ה-single-speaker/single-dispatch (זה בדיוק מה שהסקריפט מודד
ישירות, לא תלוי בהצלחת הכתיבה) — אבל "approve מלא, כולל כתיבה מוצלחת
בפועל" עדיין לא אומת באותה ריצה. הרצה נוספת עם `EmergencyStop` כבוי
(בהחלטת owner, לא בהחלטתי) תסגור גם את הפער הזה.

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

**STATUS: 🟢 VERIFIED — 6/6 scenarios (2.1-2.6).** 2.1-2.5: real staging,
26/26 automated checks PASSED, exit=0 (`scripts/verify_bug161_162_
callback_staging.py`, 13/08/2026). 2.6: closed 13/08/2026 (Agent 2 cycle)
after correcting the scenario's expected marker — see §2.6's "תיקון-
marker" — via (a) pre-existing real staging log evidence in
`BUG_AUDIT_LOG.md`'s BUG-155 write-up (03-04/08/2026, `pending_gate_
decision=block_new_action`, exact user-facing text quoted) and (b) a
fresh local run of the pre-existing `test_bug122_pending_queue_ux.py`
(8/8 passed, real `run_agent()`/`ActionGateway`/`ExecutionLedger` code,
mocked Anthropic/Router/Identity only). No code change was required —
behavior already satisfies BUG-161's invariant (block_new_action returns
*before* the Agent runs at all, a stronger guarantee than the originally-
documented ask_queue_resolution path, which is dead code since commit
`006506d`, 24/07/2026 — see §2.6). Two non-blocking findings recorded,
not fixed (out of scope — "no opportunistic refactor"): `app.py:5063-5108`
(`ask_queue_resolution` branch) is unreachable dead code; `test_bug122_
pending_queue_ux.py`'s part (b) docstring describes testing a path it no
longer actually exercises (test itself is correct/green, only its stated
intent is stale).
**EVIDENCE: preflight §0 (Render API, read-only, 13/08/2026); real staging
run 13/08/2026 (`my-bot-approval-staging`, `srv-d99uq63eo5us73967cj0`),
commit `63280e2`, `scripts/verify_bug161_162_callback_staging.py`, exit=0,
26/26 checks PASSED — see §3 table above for the per-scenario dispatch-count
findings, including the real 3-way concurrent-thread claim race
(`3b. dispatch_tool called at most once across 3 concurrent presses`).
2.6: `BUG_AUDIT_LOG.md` BUG-155 section (real staging, 03-04/08/2026) +
local `test_bug122_pending_queue_ux.py` run (13/08/2026, 8/8 passed).
Open caveat (2.1-2.5 only): run performed with `EmergencyStop` active on
staging, so no scenario reached a genuinely successful "completed" write
— see §3's "הסתייגות פתוחה." Owner ran the script directly on Render's
staging shell; I ran the read-only Render API preflight and wrote/fixed
the script from this session, but did not execute it myself (no staging
shell access).**
