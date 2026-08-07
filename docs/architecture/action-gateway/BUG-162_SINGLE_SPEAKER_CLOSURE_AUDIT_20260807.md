# BUG-162 — Closure Audit: Why the Gap Existed Despite an Existing DoD, and Exit-Path Coverage Proof

**תאריך:** 07/08/2026
**מטרת המסמך:** לא תכנון-ארכיטקטורה חדש. תשובה ל-2 שאלות שנשאלו במפורש: (1) איך
קרתה תקלה כזו למרות ש-DoD קיים מגדיר במפורש שלא ישאר מנגנון ריק, ו-(2) closure
audit — כל exit paths, producer→consumer contract coverage, reachability,
duplicate authority, dead/bypassed mechanisms — מול הקוד הנוכחי, כדי להוכיח
שהמימוש עומד בתכנית המקורית (או לתעד בדיוק איפה לא).
**היקף:** ממוקד ב-single-speaker/reply-ownership contract (BUG-161/162's
domain). לא סוקר את כל 70+ הממצאים של F52 Phase 4C — רק את אלה הרלוונטיים
ישירות לשאלה הזו.

---

## 1. איפה ה-DoD בפועל, ולמה הוא לא נאכף כאן

`docs/architecture/turn-coordinator/TURN_COORDINATOR_PROPOSAL_V2.md`'s **Gate
C — Reply Ownership / MessageKind / Commitment Grounding** (שורה 781) הוא ה-DoD
המחייב עבור "Phase 3: Reply Ownership" של תוכנית ה-TurnCoordinator המלאה.
כולל, בין השאר:

> - [ ] Reply Ownership (Phase 3) מתועד עם reference ל-incident הממשי (approval
>   prompt/fallback סותר, הודעת הצלחה כפולה) — לא רק כהגנה תיאורטית
> - [ ] regression: תרחיש ה-incident המתועד (approval prompt במקביל ל-fallback)
>   לא חוזר לאחר Phase 3

זה **בדיוק** ה-DoD item שהיה אמור לחייב טסט-regression שמכסה את כל
ה-manifestations האפשריות של "Agent מדבר ב-turn שה-Gateway אמור לבעול" — לא רק
תרחיש אחד לדוגמה.

**הבעיה:** `docs/architecture/turn-coordinator/README.md`'s Status section קובע
במפורש: **"Phase 1 (structural enforcement) not started"** — Gate C, כמו כל
Phase 3, **מעולם לא נפתח רשמית**. אבל PR #471 ("PR1 single-speaker boundary",
`app.py:4437-4494` היום) **כן שלח קוד אמיתי לפרודקשן** שממש חלק ניכר ממה ש-Gate
C מתאר — `reply_owner="gateway"` כתנאי ל-early-return, בדיוק מנגנון ה-Reply
Ownership ש-Phase 3 היה אמור לפרמל.

`docs/context_librarian/layers/turn_coordinator.json`'s notes מתעדים את זה
בכנות: "PR #471... **a conditional, code-level ownership assignment for
approval-queuing turns specifically — it does not create a general reply_owner
claim mechanism**." כלומר — התיעוד **ידע** שזו מימוש חלקי/לא-רשמי, לא Phase 3
המלא. אבל אף אחד לא חיבר את הנקודה ההפוכה: **מימוש חלקי-של-Phase-3 עדיין חייב
להיבדק לפי אותה רמת-קפדנות שה-DoD של Phase 3 דורש**, גם אם הוא לא "רשמית"
Phase 3. שום Gate לא אכף את זה — כי ה-Gate עצמו מוגדר להפעיל **אחרי** ש-Phase 3
"מתחיל", וה-Phase הזה מעולם לא הוכרז כמתחיל, למרות שקוד ששייך לו כבר רץ
בפרודקשן.

**זו התשובה המדויקת ל"למרות שה-DoD מגדיר... זה קרה":** ה-DoD קיים, מפורט,
ומחייב — אבל הוא ממתין ל"Phase 3 שרשמית מתחיל", בזמן שקוד-מקדים כבר מומש בפועל
מחוץ לתהליך שהיה אמור להריץ אותו מול ה-DoD. הפער הוא **תהליכי**: אין מנגנון
שמזהה "קוד X ממש חלק ממטרה Y שיש לה DoD — X חייב לעבור מול ה-DoD גם אם הוא לא
נקרא רשמית 'Y'."

**ראיה נוספת שזה נחזה מראש, לא רק בדיעבד:** `docs/architecture/
f52-unified-approval-runtime/audits/phase-4c/TURN_OWNERSHIP_EXTENSION.md`
(נכתב סביב 15/07/2026, **שלושה שבועות לפני** ש-BUG-162 דווח), Finding 3:

> "AP-02's reply is Gateway-authored, not agent-authored, and today's fix is a
> suppression patch, not a `reply_owner` field. The single-speaker regression
> suite (`test_single_speaker_fallback_and_duplication.py`) should be named
> explicitly in Gate C's DoD as the pre-existing behavior Phase 3 generalizes."

המסמך הזה **כבר אמר** שהמנגנון-אז-הקיים (pattern-matching suppression ב-
`sanitize_agent_response()`) הוא "stopgap", וש-Phase 3 (ה-`reply_owner` field
המבני) הוא ה"generalization" הנדרש. מה שלא נחזה: כש-Phase 3's מנגנון-בפועל
(PR #471) **כן** נשלח, הוא עצמו לא עבר מול אותו DoD — ואפילו נשאר **לא-שלם**
מבנית (ראו §2).

---

## 2. Closure Audit — Exit Paths, Producer→Consumer Contract, Reachability

### 2.1 ה-Contract: מי צרכן, מי מפיק

**הצרכן (consumer):** `app.py`'s tool-use loop, `_gateway_owned` lookup
(אחרי התיקון — שורה ~4484-4488):
```python
_gateway_owned = next((
    entry for entry in reversed(tool_results_log)
    if entry.get("tool") == "__approval_queued__"
    and entry.get("reply_owner") == "gateway"
), None)
```
דורש: entry עם `tool=="__approval_queued__"` **וגם** `reply_owner=="gateway"`.

**המפיק (producer) היחיד:** `_queue_approval_detailed()`/`_queue_approval_
detailed_impl()` (שורה 1417). **מאומת ב-grep** (`grep -n '"__approval_queued__"'
app.py`) — רק מקום אחד ב-repo כולו דוחף entry עם `tool: "__approval_queued__"`
ל-`tool_results_log` (שורה ~4360-4380, `_approval_outcome` = תוצאת
`_queue_approval_detailed()`). אין producer מקביל/כפול לצרכן הזה — reachability
נקייה, לא בעיית "מי עוד יכול לייצר את זה".

### 2.2 מיפוי מלא של כל exit path של הפרודיוסר (11 branches)

| # | תנאי | contract_id | reply_owner **לפני** התיקון | reply_owner **אחרי** | נכון? |
|---|---|---|---|---|---|
| 1 | duplicate fingerprint (executed_action_cache) | `None` | לא מוגדר | לא מוגדר | ✅ נכון — אין contract אמיתי |
| 2 | cross-channel dedup (bus, legacy pre-Gateway) | `None` | לא מוגדר | לא מוגדר | ✅ נכון — אין contract אמיתי |
| 3 | `persistence_lookup_failed` (enforce) | `None` | לא מוגדר | לא מוגדר | ✅ נכון — "לא אומת קיים/לא-קיים" |
| 4 | `existing_pending_blocks_agent` (BUG-122 pre-scan, enforce) | real | `"gateway"` | `"gateway"` | ✅ תמיד היה נכון |
| 5 | **generic ok=False** (rejected/pending/completed/approved/executing/outcome_unknown — enforce) | real | ❌ **לא מוגדר** | ✅ `"gateway"` | 🔴 **זה היה הבאג — עכשיו תוקן** |
| 6 | `persistence_lookup_failed` (shadow) | `None` | לא מוגדר | לא מוגדר | ✅ נכון |
| 7 | `existing_pending_blocks_agent` (shadow) | real | `"gateway"` | `"gateway"` | ✅ תמיד היה נכון |
| 8 | `persistence_failed` (shadow) | `None` | לא מוגדר | לא מוגדר | ✅ נכון — "unknown, not confirmed absent" |
| 9 | `bus.request_approval()` raises, revoke הצליח | `None` (revoked) | לא מוגדר | לא מוגדר | ✅ נכון — contract בוטל, אין מה לבעול |
| 10 | `bus.request_approval()` raises, revoke נכשל → `_orphan_cleanup_failure_response()` | real אך **לא-מאומת** | לא מוגדר | לא מוגדר | ✅ נכון **בכוונה** — מצב "unknown", לא canonical |
| 11 | הצלחה מלאה (contract נוצר) | real | `_lifecycle_result.reply_owner` (="gateway") | ללא שינוי | ✅ תמיד היה נכון, ונבדק (`test_pr1_single_speaker_approval_ux.py`) |

**מסקנת ה-audit:** מתוך 11 exit paths, **10 היו נכונים-בעיצוב** (או שיש
contract אמיתי ו-reply_owner מוגדר, או שאין contract אמיתי/מצב לא-מאומת
ובכוונה לא מוגדר). **רק #5 היה שגוי** — יש contract אמיתי, סטטוס ידוע וסופי
(rejected/pending/completed/approved/executing/outcome_unknown — כולם canonical,
לא "unknown"), אך `reply_owner` לא הוגדר. זה **לא** תבנית שחוזרת על עצמה בכל
הפונקציה — תיקון #5 סוגר את כל הפער בפונקציה הזו, לא רק מופע אחד ממנו.

### 2.3 למה טסטים קיימים לא תפסו את זה — coverage gap מדויק

| טסט קיים | מה הוא בודק | האם היה תופס את הבאג? |
|---|---|---|
| `test_pr1_single_speaker_approval_ux.py` | `build_approval_lifecycle_result()` — הפונקציה הטהורה, מחשבת `reply_owner="gateway"` **תמיד**, כולל ל-`rejected`/`repeated_rejected` (שורה 81) | ❌ לא — בודק שכבה מתחת ל-producer; `build_approval_lifecycle_result()` עצמה **הייתה** תמיד נכונה |
| `test_single_speaker_fallback_and_duplication.py` | `sanitize_agent_response()` — מנגנון-אכיפה **נפרד ומקביל** (pattern-matching על `_AGENT_ACTION_STATUS_PATTERN` וכו', לא בודק `reply_owner` כלל) | ❌ לא — בודק מנגנון אחר לגמרי (ראו §2.4) |
| `test_bug153_create_task_reconfirmation_after_rejection.py` (סעיפים 1-3) | `ActionGateway.propose_action()` **ישירות** — `GatewayResult.reason`/`.contract_id`, לא עובר דרך `_queue_approval_detailed_impl()` בכלל | ❌ לא — מדלג בדיוק על שכבת ה-glue שהייתה שבורה |
| `test_bug153_...py` (סעיף 4, "end-to-end") | `app._queue_deterministic_create_task()` עם `trusted_source="deterministic_create_task"` — **תמיד פותח contract חדש**, לעולם לא מגיע ל-branch #5 (זה בדיוק ה-carve-out) | ❌ לא — end-to-end אמיתי, אבל למסלול השונה (create חדש, לא block) |

**המסקנה המדויקת:** היה כיסוי מלא בשתי הקצוות — הפונקציה הטהורה
(`build_approval_lifecycle_result`) והאינטגרציה המלאה למסלול ה-**create**
(BUG-153 §4) — אבל **אף טסט לא בדק את שכבת ה-glue** (`_queue_approval_
detailed_impl()`) במסלול ה-**block** (Agent מגיע ל-fingerprint שכבר נדחה/
תפוס/הושלם). זה בדיוק "unit tests passed, integration boundary untested" —
לא כשל ב-DoD התיאורטי, אלא **בפועל אף טסט לא כיסה את הצומת הספציפי הזה**.

### 2.4 Duplicate Authority — ממצא פתוח, לא תוקן (לפי בקשה מפורשת שלא לתכנן מנגנון חדש)

נמצאו **שני מנגנונים נפרדים, מחושבים באופן עצמאי**, ששניהם עונים על השאלה
"האם ה-turn הזה שייך ל-Gateway":

1. **מנגנון האכיפה** (`_gateway_owned` lookup, `app.py:4484-4488`) — דורש
   `tool=="__approval_queued__"` **וגם** `reply_owner=="gateway"` (שדה נפרד,
   שהיה חסר ב-branch #5).
2. **אות ה-shadow observation** (`_approval_queued_this_turn`, `app.py:4629`,
   נצרך ע"י `build_ownership_signal()` ב-`app.py:4670`) — דורש **רק**
   `tool=="__approval_queued__"` (לא בודק `reply_owner` בכלל).

**זו הסיבה המדויקת שה-shadow log תפס את ההפרה נכון ("[TurnOwnershipShadow]
violation=agent_spoke_in_gateway_owned_approval_turn") בזמן שמנגנון-האכיפה לא
פעל** — שני המנגנונים מסתמכים על תנאים שונים לחלוטין, לא על אותו מקור-אמת יחיד.
זה בדיוק "duplicate authority" — לא אסור פורמלית (אין policy כפול-מנוגד כאן,
שני המנגנונים מסכימים על **הכיוון**), אבל הם **יכולים להתפצל בשקט** אם אחד
מהם משתנה ולא השני — בדיוק מה שקרה.

**לא תוקן בסבב הזה — במפורש, לפי הנחיה.** מתועד כממצא פתוח: אם/כש-Gate C
(Phase 3) יתחיל רשמית, `_approval_queued_this_turn`'s reply_owner computation
(`"gateway" if _approval_queued_this_turn else "agent"`, `app.py:4670`) צריך
להיגזר מ**אותו** `reply_owner` field ש-`_gateway_owned` כבר צורך, לא מ-boolean
נפרד — לא כדי "לתכנן מנגנון חדש", אלא כדי לאחד שני מקורות-קיימים לאחד.

---

## 3. הטסט המבני שסוגר את המחלקה הזו (לא מנגנון runtime חדש)

`test_bug162_gateway_reply_owner_on_generic_block.py` (32/32) — לא רק תרחיש
BUG-153 בודד, אלא **enumeration ממצה** על כל 6 ערכי `existing.status` שמגיעים
ל-branch #5 (pending/completed/rejected/approved/executing/outcome_unknown),
כל אחד נבדק בנפרד עבור `reply_owner=="gateway"` + `lifecycle_result` מאוכלס +
תוכן-הודעה לא-ממציא. זה סוגר בדיוק את הפער ש-§2.3 מתעד — הפעם הבאה ש-branch
בפונקציה הזו (או branch חדש דומה שיתווסף) ישכח `reply_owner`, הטסט הזה נכשל
מיידית, לא רק כש-owner יבחין בזה ידנית בפרודקשן.

**זה טסט, לא ארכיטקטורה חדשה** — עונה במפורש על הדרישה "BUG-162 הוא דוגמת כשל
שחייב להיות נתפס על ידי gate קיים או test structural חדש": ה-gate הקיים
(`test_pr1_single_speaker_approval_ux.py`) לא יכול היה לתפוס את זה מבנית (הוא
בודק שכבה אחרת) — לכן test structural **חדש**, ממוקד בדיוק בשכבת ה-glue
שהייתה חסרת-כיסוי, הוא הכלי הנכון.

---

## 4. סיכום — האם המימוש עומד בתכנית המקורית?

| שאלה | תשובה |
|---|---|
| האם `build_approval_lifecycle_result()` (הבסיס ל-Gate C) תקין? | ✅ כן, תמיד היה — נבדק ומאומת |
| האם ה-producer (`_queue_approval_detailed_impl()`) עקבי מול הבסיס הזה? | 🔴 היה לא-עקבי ב-1 מתוך 11 exit paths — **עכשיו תוקן ומאומת ב-11/11** |
| האם קיים duplicate authority לא-פתור? | 🟡 כן — שני מנגנונים עצמאיים (§2.4), **מתועד כפתוח, לא תוקן** לפי הנחיה |
| האם Gate C (Phase 3) עצמו "הושלם"? | ❌ לא — עדיין `PLANNING ONLY` רשמית, למרות שחלק ממנו (PR #471) כבר בפרודקשן |
| האם יש עכשיו טסט מבני שהיה תופס את BUG-162 מראש? | ✅ כן — `test_bug162_gateway_reply_owner_on_generic_block.py`, 32/32, ממצה על כל הסטטוסים הרלוונטיים |

**המלצה אחת בלבד (לא מימוש, החלטת owner):** Gate C's DoD checklist
(`TURN_COORDINATOR_PROPOSAL_V2.md` §Gate C) צריך לצטט במפורש את PR #471
כ"informal Phase 3 precursor already in production" — כדי שהפעם הבאה שמישהו
בודק "האם Phase 3 הושלם", התשובה לא תהיה "לא התחיל רשמית" תוך התעלמות מקוד
שכבר רץ ומשרת בפועל את אותה מטרה.
