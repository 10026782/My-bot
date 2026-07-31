# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקורות הקנוניים ראו `ROADMAP.md`, `CHANGELOG.md`, `BUG_AUDIT_LOG.md`,
> `CHANGE_CONTROL_LOG.md` ומסמכי הארכיטקטורה. `CANONICAL_STATE.md` **לא קיים**.
> `BOSS_CURRENT_STATE.md` עודכן לאחרונה ב־26/06/2026 והוא ארכיון היסטורי בלבד.
> **main גובר על מסמכי תכנון בכל סתירה. "תוקן" ≠ "מאומת בפרודקשן".**

**עודכן:** 31/07/2026 · **origin/main:** `1c515701` (PR #509)

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), עם Identity→Router→Context→Agent ו־Airtable כ־CRM.
- **Production Render verification (30–31/07/2026):** שלושת הדגלים
  `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`,
  `FEATURE_ACTION_GATEWAY` הוחזרו כ־`true` ב־env-vars של השירות החי.
- **פער deploy חשוב:** ה־deploy החי הוא `5ec37b8`, בעוד `origin/main` הנוכחי הוא `1c515701`.
  לכן ראיית production אינה הוכחה שה־tip הנוכחי כבר פרוס. פירוט: `docs/architecture/action-gateway/PRODUCTION_30JUL2026_RENDER_VERIFICATION.md`.
- Render החזיר 111 רשומות `ActionContract` בחלון 29–31/07, כולל reads, creates, approvals ו־lifecycle updates.
- **BUG-152** — בקשת אישור נעצרה פעם אחת ורק בשליחה חוזרת הצליחה; נרשם, לא root-caused ולא מסומן כמתוקן.
- Emergency Stop הושלם ונרשם כמאומת בפרודקשן; Cost Telemetry נשאר shadow-only.

## 2. Current System State

**מאומת לפי scope:**

- ActionContracts הוא מקור האמת למחזור חיי approval; קיימים במקביל מסלולי legacy ו־TMA שיש להבחין ביניהם.
- שלושת דגלי approval פעילים ב־Render production בזמן הבדיקה; ערכי הקוד וברירת המחדל נשארים `off`.
- `describe_pending_queue()` קורא מ־ActionContracts; אין להסיק ממנו על תורי legacy אחרים.
- F52 Unified Status Formatter ו־RP5 Evidence Finalizer נשארים shadow/comparison-only; `enforce`/`on` אינם נחשבים פעילים.
- **Production אינו מסונכרן עם `origin/main`:** live deploy `5ec37b8`; current main `1c515701`.

**מיושם חלקית / לא production-active:**

- Message Contract Envelope ו־adapters של F52 הם חוזים/מסלולים טהורים; PR #509 מוזג ל־main, אך אין להסיק ממנו חיווט מלא של כל מסלולי runtime.
- Context Librarian Consumption Enforcement Phase 1 קיים בכלי הפנימי; CI blocking gate של Phase 3 לא מיושם.
- Cost Telemetry (`usage_events`) shadow-only; אינו מפעיל את ה־trigger החי.
- TurnCoordinator / Cross-Layer Authority Contract V1 נשאר תכנון בלבד ו־`READY FOR OWNER DECISION`.

**פתוח:**

- BUG-130, BUG-134, BUG-136, BUG-137, BUG-140 ו־BUG-150 — רשומים וממתינים להחלטת owner/שער cross-layer.
- BUG-152 — לא root-caused.
- `sheets_append` positional canonicalization ו־mutation-budget exception לא אומתו בנתיב production המדויק; נשארו test-only.
- WhatsApp outbound אמיתי נשאר honest stub, ממתין ל־Meta Cloud API.

## 3. Completed / verified scope

- PR2 ו־Hotfix E/C מוזגו ל־main ונכללים ב־production evidence רק לפי ההסתייגויות במסמכי C181–C184.
- היכולת העסקית הכללית של יצירת Task עם תאריך יעד נצפתה end-to-end; זו אינה הוכחה ל־`sheets_append` canonicalization.
- PR #506 ו־PR #509 של MessageContract מוזגו; PR #509 נוכח ב־`origin/main`, אך אין לטעון שכל adapter מחווט לכל מסלול חי.
- Consumption Enforcement ו־dry-run estimate הם dev tooling, ללא שינוי התנהגות הבוט העסקי.

## 4. Next priorities

1. לשמור את פער ה־deploy מול `origin/main` גלוי עד שה־live deploy מתעדכן.
2. לחקור את BUG-152 עם Render logs ותרחיש מבודד.
3. לקבל החלטות owner ל־BUG-130/134 ול־TurnCoordinator Phase 2.
4. לאמת בנפרד את `sheets_append` positional canonicalization ואת mutation-budget exception.
5. לשמור את מסמכי הסטטוס מסונכרנים עם commit, deploy hash, תאריך, scope והסתייגויות.

## 5. Claim disposition from the rejected briefing

- Claims retained: approval authority, current open bugs, shadow-vs-active boundaries, and dated production observations.
- Claims corrected: `origin/main` pointer, live deploy identity, and the distinction between flag verification and deployed-main verification.
- Claims narrowed: end-to-end Task creation is verified, but the exact `sheets_append` canonicalization path is not.
- Claims not promoted: BUG-152 root cause, full F52 adapter wiring, and any statement that production equals current main.
- The deleted detail remains available in `CHANGE_CONTROL_LOG.md`, `BUG_AUDIT_LOG.md`, and the architecture evidence documents; it was condensed, not silently treated as resolved.
