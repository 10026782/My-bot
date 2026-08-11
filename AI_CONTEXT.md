# AI CONTEXT

**עודכן:** 11/08/2026 · **origin/main:** `f69d7b3` (PR #597).

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקור האמת ראו `ROADMAP.md` (קודם כול), `CHANGELOG.md`, ו-
> `docs/audit/CORE_COMPLETION_AUDIT_20260810.md` (קנוני ל-CORE, מבוסס main
> `134148e`; ללא drift פונקציונלי מאז — שאר commits עד `f69d7b3` הם docs בלבד).
> `BOSS_CURRENT_STATE.md` **stale מ-26/06/2026** — ארכיון היסטורי, לא לצטט
> כמצב נוכחי. **main גובר על מסמכי תכנון בכל סתירה. "מוזג" ≠ "פרוס" ≠
> "מאומת בפרודקשן."**

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio): Identity → Router →
  Context → Agent, Airtable כ-CRM.
- **CORE v1 — COMPLETE / READY TO FREEZE** (freeze עצמו = החלטת owner, לא
  מוכרז). קנוני: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`, נבנה מול
  main `134148e`, כולל אימות Production+Staging חי (Render API + logs
  טריים, לא רק claim).
- **PA-01 (PR #595) סגר את ה-CORE blocker האחרון**: `UPDATE_TASK`/
  `COMPLETE_TASK` מנותבים כעת ל-`Handler.TOOL` דטרמיניסטי במקום נפילה
  אוטומטית ל-Agent. ללא flag, פרוס ל-Production 15:57 UTC 10/08/2026.
- **פער ה-deploy שדווח בסבבים קודמים נסגר**: Production מאומת חי בדיוק על
  `134148e` (Render API), לא ancestor-lag כמו קודם — כל ה-PRs עד לשם, כולל
  BUG-160–163, כעת deployed בפועל (verification-in-prod ללוגים ספציפיים של
  אותם באגים עדיין לא רוענן).
- שני פערים לא-חוסמים נותרים: (1) CI של `main` אדום על שער ה-freshness של
  Context Librarian (governance, לא regression פונקציוני); (2)
  `TurnCoordinator` הפורמלי (Layer 2 של מודל ארבע-השכבות) — אפס מימוש
  כלשהו בקוד, מוחלף היום ע"י `router.py::route_request()`.
- TC7-B2 (dual-signal shadow) — קוד חי, אך **אפס תצפיות log** בחלון הנשמר;
  root-caused כ"אין עדיין traffic post-deploy," **לא** wiring bug.
- RP5 enforcement ו-F52 unification (`FEATURE_UNIFIED_STATUS_FORMATTER`) —
  עדיין shadow/כבוי כברירת מחדל, לא הופעלו.

## 2. Current System State

**תפעולי** (מאומת ב-grep/log/Render API על `main`):

- ActionGateway/ActionContract lifecycle — מקור אמת יחיד, חי, ✅ בשני
  environments.
- Approval/reject — ✅ מאומת; cancel — לא נצפה בחלון הלוגים הנשמר (היעדר
  תעבורה, לא כשל).
- Atomic execution claims (`FEATURE_ATOMIC_CLAIMS=true` חי משני
  environments) — ✅.
- TC6 reply-ownership, TC8 durable turn-state (ללא flag, מחווט ב-4 נקודות
  approve/reject/cancel ב-`app.py`), TC9 MessageContract construction — ✅
  פרוסים; המרת-הטקסט בפועל ל-TC9 עדיין מאחורי `FEATURE_UNIFIED_STATUS_
  FORMATTER` כבוי.
- Track D observability (RuntimeSchemaProvider/IngressEnvelope) — ✅ פרוס,
  Staging-fresh; Production ללא traffic טרי עדיין לאימות עצמאי.
- F14 Contact Gate + F15 CRM one-write-path — ✅ Staging RUNTIME VERIFIED,
  אפס write-bypasses (25 read-only bypasses ידועים, לא כתיבה).
- **PA-01 — ניתוב UPDATE/COMPLETE_TASK — ✅ חי כעת** (ראו סעיף 3).

**מיושם חלקית / לא production-active:**

- TC7-B1/B1.1 (`core/claim_authorization.py`) — בנוי, **אפס קוראים חיים**
  — לא מחבר בפועל את TC7-A ל-RP4 להחלטת claim-authorization.
- TC7-B2 dual-signal shadow — פרוס, ללא תצפיות log עדיין (ראו סעיף 1).
- RP4/RP5 shadow (`FEATURE_EVIDENCE_FINALIZER=shadow`, חי משני
  environments) — shadow-comparison logging בלבד; enforcement חסום עד
  הצטברות מדגם B2/B3 מספיק + אישור owner מפורש.
- F52 Unified Status Formatter — shadow/comparison בלבד, כבוי כברירת מחדל.
- ws2/ws3 evidence/lifecycle projection modules (`core/evidence_projection.py`
  וכו') — מוזגים, **לא מחווטים** ל-`core/action_gateway.py` (grep מאשר אפס
  קריאות), לא רשומים ב-Context Librarian catalog — סיכון authority כפול
  עתידי אם יחוברו בלי Planning Gate מפורש.

**חסום:**

- `TurnCoordinator` הפורמלי (Layer 2) — אפס מימוש; חוזה קפוא ממתין לאישור
  owner. De-facto substitute היום: `router.py::route_request()` +
  `lead_candidate_handler.py`.
- BUG-130/134/136/137/140/150/152 (וכן 126/127B/127C/138/139/142/148) —
  ממתינים להחלטת owner; חלקם חסומים ע"י
  `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.
- Context Librarian catalog refresh — CI push-to-main אדום
  (`CHANGES_REQUIRED`: 4 STOP / 21 REVIEW_REQUIRED / 98 WARNING) — לא חוסם
  פונקציונלי, אך דורש הרצת `refresh-after-merge --apply`.

## 3. Completed Since Last Update (מאז 10/08/2026, `cec3f83..f69d7b3`, PR #595–#597)

- **PR #595 — PA-01 router wiring**: `parse_deterministic_task_reference()`
  חדש ב-`core/router/router.py`; `Intent.UPDATE_TASK`/`COMPLETE_TASK` עם
  reference תקין → `Handler.TOOL` (קודם תמיד `Handler.AGENT`). קוד
  ה-downstream (`app.py`'s `_queue_deterministic_task_update()`) כבר היה
  קיים (PR #564/#565/#567) אך בלתי-נגיש מהניתוב החי — נסגר עכשיו.
  Ambiguous match → `Handler.CLARIFY` fail-closed, אותה תבנית כמו
  CREATE_TASK. ללא flag. פרוס Production 15:57 UTC 10/08.
- **PR #596 — Canonical CORE Completion Audit**:
  `docs/audit/CORE_COMPLETION_AUDIT_20260810.md` (מבוסס `134148e`) מכריז
  `PASS WITH NON-BLOCKING DEFERRED ITEMS`; מחליף את הדוח הקודם-באותו-יום
  (`CORE_FINAL_INTEGRATION_GATE_20260810.md`, שכבר תוקן פעם אחת תוך-יומי
  בעצמו — מסומן היסטורי כעת). כולל מטריצת runtime-verification מלאה
  (ActionGateway, TC6–TC10, F14/F15, Track D, RP4/RP5) מול Staging טרי +
  Production deploy-SHA (Render API), ואודיט cross-layer authority (ממצא
  יחיד לא-חוסם: ws2/ws3 מוזג-ולא-מחווט).
- **PR #597 — Context Librarian test fix**: תיקון assertion חד-שורתי,
  ללא שינוי התנהגות/CI-gate.
- (PR #572–#588 מהסבב הקודם — TC7-B1/B1.1, TC8, TC9, F14-B2, Track A/D —
  עדיין בתוקף כפי שתועד, ללא שינוי בסבב הזה; ראו `CHANGELOG.md` לפירוט.)

## 4. Next Priorities

1. **סגור את שני הפערים הלא-חוסמים מה-audit הקנוני** — הרץ
   `python -m tools.context_librarian refresh-after-merge --apply` לניקוי
   ה-CI האדום; קבע/דחה במפורש מול owner את מעמד `TurnCoordinator` הפורמלי
   (Layer 2).
2. **חבר TC7-B1 (`authorize_claim()`) לצרכן אמיתי** — עדיין 0 קוראים; זו
   ה-gate המרכזית החסרה בשרשרת claim-authorization.
3. **אימות production טרי ל-Track D ול-TC8 reject/cancel** — קוד פרוס, אין
   ראיות log לאחר ה-deploy האחרון (היעדר תעבורה, לא כשל) — נדרש ייצוא
   Render עדכני.
4. **הכרע גורל ws2/ws3 evidence/lifecycle projection** — מוזג, לא מחווט,
   לא רשום ב-catalog; סמן היסטורי במפורש או חבר דרך Planning Gate לפני
   שנהיה מקור-אמת כפול בשוגג.
5. **המשך ניטור B2/B3 להתקדמות RP5 enforcement**, ותעדוף החלטת owner על
   freeze (`CORE v1 — READY TO FREEZE` הוכרז מבחינה עובדתית, אך ה-freeze
   עצמו לא הוחלט).
