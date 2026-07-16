# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.
> זהו מסמך תדרוך (briefing), לא תיעוד מלא. לפרטים מלאים: `ROADMAP.md` (מקור אמת יחיד
> למתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו. `BOSS_CURRENT_STATE.md` מיושן (עודכן לאחרונה
> 26/06/2026) — נשמר כארכיון, לא מקור אמת נוכחי.

**עודכן:** 2026-07-16 · **main:** `2be2472` (PR #352, PA-01 Phantom Approval Prompt structural enforcement — ראו §1/§3) · **סטטוס:** ראו §1

**⚠️ פער תיעוד (מורחב מהעדכון הקודם):** `ROADMAP.md` (עד עדכון זה, עצר ב-13/07 `b962773`) ו-`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md`/`BUG_AUDIT_LOG.md` (עוצרים ב-PR #326, אותה נקודה) **לא** שיקפו ~26 PRs שמוזגו מאז (#327-#352). עדכון זה **סוגר את הפער רק עבור PA-01/TurnCoordinator** (`claude/f52-audit-turn-ownership-u1gizk`, PR #352 — ראו §1/§3 ו-`ROADMAP.md`'s סעיף PA-01 החדש) — זה כולל גם את Phase 0 TurnCoordinator ownership-signal work (`core/turn_envelope.py`, כבר היה בענף לפני PA-01 עצמו) שממוזג יחד באותו PR. **שאר ה-PRs בטווח (#327-#341 מהפער הקודם, ועוד #342-#351 חדשים — single-speaker-fallback-fix, changelog-catchup, approval-callback-hardening, approval-invite-hallucination-gate, gifted-clarke) נשארים UNVERIFIED** מול הבריפינג הזה — לא נבדקו בסבב הזה, לא CRITICAL, פשוט לא-מאומתים. `CHANGE_CONTROL_LOG.md`/`BUG_AUDIT_LOG.md` הם append-only ידני (אין CI hook אוטומטי — נבדק ב-`.github/workflows/`) ועדיין לא קיבלו רשומה ל-PA-01 או לאף אחד מה-PRs האלה; יש לרענן את שלושתם + `CHANGELOG.md` + לבמפ `עודכן:` ב-ROADMAP (נעשה בעדכון זה, ראו למטה) לפני שסומכים עליהם לסטטוס עכשווי.

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio) על `main`, Identity→Router→Context→Agent, Airtable כ-CRM. אין שינוי במסלול הזה מהעדכון הקודם.
- **PA-01 (Phantom Approval Prompt) — קוד הושלם, ממוזג ל-`main`, לא מופעל בפרודקשן.** מונע מהסוכן להציג תשובת "הפעולה ממתינה לאישור" כשלא נוצרה בפועל ראיה תקפה (contract) לכלי הצפוי בסבב הזה — state-only enforcement, לעולם לא מסתמך על טקסט תשובת הסוכן. עבר **חמישה סבבי Codex re-audit** רצופים, כל אחד סגר פער אמיתי (לא קוסמטי): `created_this_turn` ≠ `contract_id` קיים; שם-כלי קנוני מ-`resolve_canonical_tool()` לא raw `tu.name`; fingerprint אינו הוכחת בעלות (הוסר cleanup הרסני מבוסס-fingerprint); TOCTOU race ב-atomic reject (RAM lock + `reject_if_pending()`); Airtable/durable repository ללא CAS אמיתי → fail-closed (`APPROVAL_QUEUE_ORPHANED` חדש, לא `APPROVAL_QUEUE_ERROR` כוזב). סבב מבני נוסף חילץ helpers ל-`core/approval_queue_recovery.py` (מכני, אפס שינוי התנהגות). **נשלט ע"י `FEATURE_PA01_ENFORCEMENT_STATE`, ברירת מחדל/לא-מוגדר/ערך לא-תקין = `off`. אין הפעלת פרודקשן במסגרת PR זה.** ראו §3 לפירוט מלא, `docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md` למקור.
- **Phase 4B — Atomic Claims:** ללא שינוי מהעדכון הקודם (13/07) — קוד מוכן, `FEATURE_ATOMIC_CLAIMS`/`FEATURE_ACTION_CONTRACT_PERSISTENCE` שניהם עדיין OFF, הפעלת פרודקשן טרם התבצעה. **הערה:** PA-01's fix לסבב Codex האחרון (`core/action_contract_repository.py`) נוגע ל-`ActionContractRepository.transition()` עצמה (ordering fix + `supports_atomic_conditional_transition` capability flag) — זה **לא** מפעיל את Phase 4B, אבל זה קוד משותף; ראו §3 להיקף המדויק.
- **F52 Unified Approval Runtime** (`docs/architecture/f52-unified-approval-runtime/`) — עדיין תכנון/מחקר בלבד, אפס קוד production, ללא שינוי מהעדכון הקודם. **שונה מ-PA-01**: PA-01 חי תחת `docs/architecture/turn-coordinator/` — תוכנית TurnCoordinator נפרדת שצורכת את audit maps של F52 כקלט אך אינה מחליפה אותה (ראו `docs/architecture/turn-coordinator/README.md`).
- PR #341 (Single-Speaker fix) ו-2 items 🔴 דחוף (C81-FU, C82-FU) מהעדכון הקודם — **לא נבדקו בסבב הזה**, נשארים כפי שהיו: PR #341 ממוזג-לא-מאומת, C81-FU/C82-FU עדיין ללא ראיה שטופלו.
- נזק ידוע ב-Airtable (רשומת ליד `recRvK6hFTNgyj8ag`) — לא נבדק בסבב הזה, נשאר לא-מאומת.
- אין harness pytest לרוב הקבצים — בדיקות הן סקריפטים עצמאיים; CI מריץ את כולן על כל PR/push ל-main. **הערה מ-PA-01:** התגלה בסבב זה שכמה קבצי בדיקה (`test_phase_4b_1b_durable_lifecycle.py` ואחרים) כתובים בסגנון `pytest` (fixtures, בלי `if __name__ == "__main__"`) ורצים בפועל **רק** תחת `python3 -m pytest`, לא תחת ה-CI sweep הרגיל (`python3 <file>.py`) — ראו §3 והערה דומה שכבר קיימת ב-ROADMAP סעיף Fxx/BUG-049 לתבנית זהה (test רץ "ירוק" ב-CI בלי לבצע assertion בפועל). לא אומת אם `ci.yml` בפועל מריץ את קובצי ה-pytest האלה נכון — נדרש בדיקה נפרדת.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram + WhatsApp(Twilio) inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed אטומי, SPEC A1); Approval flow (Airtable `Approvals` כרגע עדיין הנתיב האמיתי — ה-projection החדש דורם); Daily Digest; Finance Pulse; TMA; Cost Watchdog; C94 Ingress Envelope (ON כברירת מחדל); צינור חילוץ-ליד מ-WhatsApp.

**מיושם חלקית / ממתין להפעלה (קוד מוכן, flag כבוי):**
- **PA-01 — Phantom Approval Prompt structural enforcement (חדש בעדכון זה):** `FEATURE_PA01_ENFORCEMENT_STATE` — three-state (`off`/`shadow`/`enforce`), ברירת מחדל `off`, בלתי-תלוי ב-`FEATURE_ACTION_GATEWAY`. Shadow mode (לוגים/warnings בלבד, אינו נוגע ב-`final_reply`) לא הופעל בפרודקשן — אין תצפית production evidence עדיין. ראו §3.
- **Phase 4B — Atomic Claims (PostgreSQL):** durable proposal persistence (4B-1A), durable execution-ledger lifecycle (4B-1B), Approvals הופך ל-projection לא-אותנטי + `tma_write` דורש claim חי לפני כתיבה (4B-2). כל השכבה נעולה מאחורי `FEATURE_ACTION_CONTRACT_PERSISTENCE`+`FEATURE_ATOMIC_CLAIMS` (שניהם OFF) — "dormant" במפורש בקוד. כלי rollout (`tools/phase_4b_*`) קיימים ומתועדים אך לא הופעלו על פרודקשן. ללא שינוי מהעדכון הקודם, פרט לתיקון ordering/capability-flag ב-`ActionContractRepository.transition()` שהגיע דרך PA-01 (ראו §3) — לא משנה את סטטוס ה-flags.
- **F52 Unified Approval Runtime** — תוכנית מיזוג ל-4 מנגנוני אישור קיימים למנוע אחד. תכנון בלבד (README="Planning Gate", CUTOVER_PLAN=draft ריק). אין קוד production. ללא שינוי.
- C90 (xlsx/csv), Lead Scoring/Memory/Followup (N02-N04), Decision Hub (Stages 0-6) — ללא שינוי מהעדכון הקודם: code done, flags off.
- `IngressEnvelope.normalized_text` נבנה ונזרק (BUG-102); `EvidenceTrace` נבנה ולא נשמר ל-DB (BUG-103); Core Reasoning Layer ללא קוראים חיים (BUG-104) — **ללא עדכון סטטוס, ולא נגעו בסבב PA-01 (הוחרג במפורש מכל 6 סבבי ה-audit — ראו §3).**

**חסום:**
- Decision Hub activation — ממתין ל-production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- C93 (OCR) — חסום על צבירת `AgentObservation`.
- BUG-099b.1, PR #341 — ממוזגים, לא deployed/verified בפרודקשן (לא נבדק מחדש בסבב זה).
- **PA-01 production activation** — קוד מוכן ומאומת (110/110 בדיקות ייעודיות + full regression), אך `FEATURE_PA01_ENFORCEMENT_STATE` נשאר לא-מוגדר בפרודקשן. אין staged rollout plan כתוב לזה (בדומה לפער שכבר קיים ל-Phase 4B).

---

## 3. Completed Since Last Update (15/07 → 16/07)

1. **PA-01 — Phantom Approval Prompt structural enforcement, PR #352 (`2be2472`, squash של 22 commits מהענף `claude/f52-audit-turn-ownership-u1gizk`).** תוכנית רב-סבבית (planning gate מאושר → מימוש → 5 סבבי Codex re-audit עוקבים → סבב ניקוי מבני), כל אחד בעקבות ממצא אמיתי שנמצא ע"י audit חיצוני, לא self-review:
   - **מימוש בסיס:** `core/router/risk_router.py` (`_CONTRACT_REQUIRED_INTENT_TO_TOOL`, `intent_requires_contract_for_success`, `expected_tool_for_intent`, `contract_capable_this_turn`), `feature_flags.py` (`FEATURE_PA01_ENFORCEMENT_STATE`), `app.py` (5-row decision matrix ב-`run_agent()` — row 2 contract-created-this-turn, row 3 structured terminal outcome, row 4 Phantom fallback, row 5 capability fallback).
   - **סבב 1 (`b7eb2bb`):** `created_this_turn` הוסף כשדה נפרד — `contract_id` לא-`None` **אינו** הוכחה שנוצר בסבב הזה (`propose_action()` מחזיר contract_id גם ל-contract קיים/דחוי).
   - **סבב 2 (`c95799f`):** `action_tool` בסנטינל חייב להיות שם הכלי הקנוני (`resolve_canonical_tool()`), לא `tu.name` הגולמי — אחרת contract אמיתי יכול להיראות "לא רלוונטי" ל-intent שגרם ל-Phantom fallback כוזב.
   - **סבב 3 (`8e05d67`→`818c8a6`):** **החלטה ארכיטקטונית מרכזית** — fingerprint עסקי מוכיח זהות-פעולה, **לא** בעלות-קריאה. `cleanup` הרסני (revoke) לפי fingerprint match הוסר לגמרי; הוחלף בכלל: mutation מותר **רק** על `contract_id` שהתקבל ישירות מ-`propose_action()` של הקריאה הנוכחית. תוצאה חדשה `APPROVAL_QUEUE_ORPHANED` (לצד `APPROVAL_QUEUE_ERROR` הקיים) — `contract_id=None` ב-ORPHANED פירושו "לא ניתן לייחוס", לא "אומת שאין contract".
   - **סבב 4 (`ce990a0`):** TOCTOU race אמיתי — `reject()` בדק `status=="pending"` ואז כתב בנפרד; concurrent approval יכל להידרס. תוקן: `ExecutionLedger.update_status(require_status=...)` אטומי תחת lock יחיד (RAM), `ActionGateway.reject_if_pending()` חדש (תוספתי, `reject()` המקורי לא שונה).
   - **סבב 5 (`0dba4c4`):** ה-lock האטומי מ-סבב 4 היה אטומי **רק** ב-RAM. Airtable-backed `ActionContractRepository.transition()` הוא read→check→PATCH — אין CAS אמיתי. תוקן: `supports_atomic_conditional_transition = False` capability flag על ה-repository; ה-ledger מסרב לבצע transition מותנה-הרסני נגד repository שלא מצהיר `True` (fail-closed, אין PATCH כלל); **וגם** תוקן סדר-בדיקות שגוי ב-`transition()` עצמה — ה-idempotent shortcut רץ *לפני* בדיקת `expected_status`/`expected_version`, מה שאיפשר "הצלחה" כוזבת (`expected=pending`, `actual=rejected`, `new=rejected` → shortcut מחזיר success).
   - **סבב מבני (`88c6a25`):** חילוץ מכני בלבד — 4 helpers (`_revoke_and_verify_contract`, `_cancel_and_verify_pending`, `_orphan_cleanup_failure_response`, `_SAFE_CANCELLED_CONTRACT_STATUSES`) הועברו מ-`app.py` ל-`core/approval_queue_recovery.py` חדש. אפס שינוי behavior/return-shape, אומת ע"י structural audit ייעודי.
   - **קבצים עיקריים:** `app.py` (+608/- נטו), `core/action_gateway.py`, `core/action_contract_repository.py`, `core/approval_queue_recovery.py` (חדש), `core/router/risk_router.py`, `feature_flags.py`, `test_pa01_phantom_approval_enforcement.py` (חדש, 110 assertions), `docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md` (חדש, ~1750 שורות — מסמך המקור לכל החלטה/סטייה).
   - **בדיקות:** 110/110 ב-`test_pa01_phantom_approval_enforcement.py`, 117/117 ב-full script sweep, `smoke_tests.py` PASS, `compileall` נקי, `git diff --check` נקי — נבדק מחדש בכל אחד מ-6 הסבבים.
   - **לא נגעו (הוחרג במפורש בכל סבב):** BUG-104, migration/Postgres wiring, CAS מלא ל-Airtable, refactor כללי של `ActionGateway`/`EventBus`, שינוי predicate/matrix/wording של PA-01 עצמו מעבר למה שתואר.
2. **Phase 0 TurnCoordinator ownership-signal work** — היה כבר בענף `claude/f52-audit-turn-ownership-u1gizk` **לפני** תחילת סבבי PA-01 (לא חלק מהעבודה שתוארה כאן ישירות, אך מוזג יחד באותו PR #352): `core/turn_envelope.py`'s `OwnershipSignal`, מחווט ל-`run_agent()`, Telegram callbacks (`_handle_approval_callback_impl`), TMA (`_queue_tma_write_approval`), ו-2 פונקציות scheduler proposal (`followup_engine.py`, `core/lead_recovery.py`). ראו `docs/architecture/turn-coordinator/README.md` ו-`docs/architecture/f52-unified-approval-runtime/audits/phase-4c/TURN_OWNERSHIP_EXTENSION.md`. **לא אומת production evidence** — קוד+בדיקות בלבד.
3. **אין רישום** ל-#1-#2 לעיל ב-`BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md`/`CHANGELOG.md` — פער תיעוד פעיל, ראו §0.
4. **לא נבדק בסבב זה:** PRs #342-#351 (single-speaker-fallback-fix, changelog-catchup-327-345, approval-callback-hardening ×2, approval-invite-hallucination-gate, gifted-clarke) — כולם ממוזגים ל-`main` בטווח התאריכים הזה לפי `git log`, תוכנם לא נבדק/אומת בעדכון זה. ראו §0.

---

## 4. Next Priorities

1. **🔴 רענון תיעוד מלא** — לעדכן `CHANGELOG.md`, `CHANGE_CONTROL_LOG.md`, `BUG_AUDIT_LOG.md` עם PA-01 (#352) וגם PRs #327-#351 שעדיין לא תועדו שם בכלל. `ROADMAP.md` עודכן בסבב הזה (ראו commit) עם סעיף PA-01 ייעודי — יש לוודא ששלושת הלוגים האחרים לא נשארים מיושנים עוד סבב.
2. **החלטה: הפעלת PA-01 shadow mode בפרודקשן** — `FEATURE_PA01_ENFORCEMENT_STATE=shadow` (לוגים/warnings בלבד, ללא שינוי `final_reply`) תיתן production evidence אמיתי לפני מעבר ל-`enforce`. אין staged rollout plan כתוב — נדרש להחליט/לכתוב לפני הפעלה.
3. **🔴 Production-verify PR #341** — ללא שינוי מהעדכון הקודם: לוודא ב-Render שה-hash החדש פרוס, לשחזר את תקרית ה-Single-Speaker המקורית ולוודא ששני התיקונים מונעים אותה חי. **לא נבדק בסבב הזה.**
4. **החלטה על Phase 4B staged rollout** — ללא שינוי מהעדכון הקודם: %-staged (5%→25%→100%) עדיין לא קיים בכתב.
5. **🔴 C81-FU / C82-FU** — ללא שינוי מהעדכון הקודם, עדיין ללא ראיה שטופלו.
6. **תיקון ידני** לרשומת `recRvK6hFTNgyj8ag` ("יעל רייס") ב-Airtable — לא נבדק בסבב הזה.
7. **לבדוק wiring של קבצי בדיקה בסגנון pytest** (`test_phase_4b_1b_durable_lifecycle.py` ואחרים שנמצאו במהלך PA-01) מול `ci.yml` בפועל — ייתכן שרצים "ירוק" ב-CI בלי לבצע assertion, תבנית זהה ל-BUG-049 הישן. לא אומת בסבב הזה, רק זוהה.
