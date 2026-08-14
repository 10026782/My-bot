# AI CONTEXT

**עודכן:** 14/08/2026 · **origin/main:** `cb03b24` (PR #633 — docs/F14 gap
qualification; latest of a 64-commit run since PR #613/`98f3626`, 13/08/2026).

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקור האמת ראו `ROADMAP.md` (קודם כול), `CHANGELOG.md`, ו-
> `docs/audit/CORE_COMPLETION_AUDIT_20260810.md` (קנוני ל-CORE, מבוסס main
> `134148e`; ללא drift פונקציונלי מאז ל-CORE עצמו). `BOSS_CURRENT_STATE.md`
> **stale מ-26/06/2026** — ארכיון היסטורי, לא לצטט כמצב נוכחי. **main גובר
> על מסמכי תכנון בכל סתירה. "מוזג" ≠ "פרוס" ≠ "מאומת בפרודקשן."**

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio): Identity → Router →
  Context → Agent, Airtable כ-CRM. ללא שינוי.
- **CORE v1 — COMPLETE / READY TO FREEZE** (freeze עצמו = החלטת owner, לא
  מוכרז) — ללא שינוי, קנוני: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`.
- **F23 Marketing Bridge M1** (`/marketing_new`) — ✅ VERIFIED IN PROD, ללא
  שינוי. **F23 M2** (`/marketing_status`) — **עודכן**: עבר מ-"מוזג, לא
  מאומת" (מצב הדוח הקודם) ל-**✅ VERIFIED IN PROD** — הבעלים הריץ live
  regression אמיתי מול production ב-13/08, החלקים הדטרמיניסטיים (list/Next
  Action/handoff) נכונים ומאומתים.
- **חדש: BUG-164 נפתח** — תוכן "הרעיון שנבחר" שה-AI מייצר (Prompt 1 של M1,
  לא M2) מכיל עיוות עובדתי כמותי; 🟡 פתוח, לא-חוסם, אינו regression של M2
  ואין עדיין תיקון מוצע/מאושר.
- BUG-157/160/163 נשארים ✅ STAGING VERIFIED (13/08, TRACK 3); אימות
  production עדיין לא בוצע במכוון. BUG-161/162 — נשארים פתוחים, ממתינים
  להחלטת owner. TurnCoordinator Layer 2 — עדיין לא ממומש. ללא שינוי מהותי
  מהדוח הקודם בפרטים אלה.
- **⚠️ פער תיעוד חדש שנפתח בסבב הזה:** בין `98f3626` (13/08) ל-`cb03b24`
  (14/08) מוזגו **64 קומיטים נוספים** ל-`main` — אך **אף אחד מהם לא קיבל
  שורת `עודכן:` ב-`ROADMAP.md` או רשומה תואמת ב-`CHANGELOG.md`** (שתי
  ה-Sources of Truth עדיין עוצרות ב-13/08). זהו אותו דפוס "פער-תיעוד" שכבר
  תועד וסודר בעבר (למשל רשומות 07/08, 09/08, 10/08, 11/08 ב-`ROADMAP.md`) —
  **טרם בוצע כאן**. פירוט הקטגוריות בסעיף 3; כל טענת סטטוס עליהן היא
  **UNVERIFIED**, לא CRITICAL, עד לבדיקה ישירה מול `main`.

## 2. Current System State

**תפעולי** (מאומת ב-ROADMAP.md/grep/git log על `main`):

- ActionGateway/ActionContract lifecycle — מקור אמת יחיד, חי, ✅.
- CORE v1 (ActionGateway, TC6/TC8/TC9, F14/F15, PA-01, Track D, RP4/RP5
  shadow) — ✅ ללא שינוי מהסבבים הקודמים.
- **F23 M1** (`/marketing_new`) — ✅ חי בפרודקשן,
  `FEATURE_MARKETING_BRIDGE=true` דלוק בפרודקשן כרגע.
- **F23 M2** (`/marketing_status`/`מצב_שיווק`) — ✅ **כעת גם חי ומאומת**
  בפרודקשן (עודכן 13/08, אחרי snapshot הדוח הקודם).

**מיושם חלקית / לא production-active:**

- BUG-157/160/163 — מוזגים+פרוסים ל-`main` מזמן, ✅ STAGING VERIFIED
  (13/08) מול race/regression אמיתי; verification בפרודקשן עדיין לא בוצע
  (במכוון, לא באג).
- **BUG-164** (חדש) — תוכן רעיון AI לא-מבוסס-עובדות ב-Prompt 1; לוגי, פתוח,
  לא-חוסם, אין fix עדיין.
- TC7-B1 (`core/claim_authorization.py`) — עדיין אפס קוראים חיים, ללא שינוי.
- RP4/RP5 shadow, F52 Unified Status Formatter — עדיין shadow/כבוי כברירת
  מחדל, ללא שינוי.
- F23 Marketing Rules (Business Memory writer) — עדיין אפס caller, נדחה
  במפורש ל-"Later". F23 `business_rules` — רק recruitment עם תוכן אמיתי.
- **64 קומיטים לא-מתועדים (13→14/08)** — לפי כותרות commit בלבד (לא
  מאומת-קוד בסבב הזה): הרחבת "Context Librarian" (bounded reconciliation
  engine, crash-recovery idempotency, סגירת registration gaps — PR
  #628/#634/#638/#639-docs), תיעוד F14 כ-evidence gap + Gap Qualification
  Gate (PR #633, docs-only לפי הכותרות), חקר/UX ל-"Ventures"/SCOREBOS
  ב-TMA (workspace shell, collection lifecycle, business-tool playbooks —
  PR #614/#621/#622/#625/#629/#631/#632/#637), תיקון קיבוע fixture ל-CI
  (PR #638). **סטטוס תפעולי לא נקבע כאן — UNVERIFIED.**

**חסום (החלטה ארכיטקטונית/owner, לא implementation blocker):**

- מחלקת `TurnCoordinator` פורמלית (Layer 2) — אפס מימוש, ממתינה להחלטת owner.
- BUG-161/BUG-162 — ממתינים להחלטת מדיניות owner (reconfirmation
  ב-Agent path / turn-ownership).
- BUG-148/150/152 — נרשמו, לא תוקנו, ללא שינוי.

## 3. Completed Since Last Update (מאז 13/08/2026 `98f3626` → 14/08/2026
`cb03b24`, 64 commits)

- **F23 M2 — production verification הושלם** (`ROADMAP.md`, 13/08): הבעלים
  הריץ live regression אמיתי ב-`/telegram` מול Demand ייעודי — list, כרטיס
  Next Action, ובחירת רעיון הפעילו נכון את מסלול הכתיבה הקיים מ-M1.
  **החלקים הדטרמיניסטיים ✅ VERIFIED**; תוכן הרעיון עצמו לא, ראה BUG-164.
- **BUG-164 נרשם** — עיוות עובדתי כמותי בתוכן רעיון AI (Prompt 1, M1),
  מופרד במפורש מסטטוס VERIFIED של M2.
- **קטגוריות נוספות מוזגו אך לא סוכמו כאן במלואן** (ראו סעיף 2 לפירוט
  PR-numbers) — Context Librarian reconciliation/hardening, F14
  gap-classification docs, Ventures/SCOREBOS TMA UX exploration, CI fixture
  fix. אלה **טעונות סבב "סגירת פער-תיעוד" ייעודי** (כמו ב-07/08–11/08)
  לפני שניתן לצטט סטטוס תפעולי שלהן.

## 4. Next Priorities

1. **סגור את פער-התיעוד של 64 הקומיטים** (13→14/08) — סבב ייעודי שמאמת
   כל קבוצת PR מול `git log`/grep/Render ומוסיף שורת `עודכן:` תואמת
   ל-`ROADMAP.md` + רשומה ל-`CHANGELOG.md`, לפי הדפוס שכבר קיים בקובץ.
2. **טפל ב-BUG-164** (Creative Ideas grounding) — אין עדיין fix מוצע;
   נדרשת החלטה אם/איך להוסיף grounding/fact-check לפני שילוב תוכן AI
   בהפקה.
3. **קבל החלטת owner מפורשת** ל-BUG-161 (מדיניות reconfirmation במסלול
   Agent) ו-BUG-162 (הפרת turn-ownership) — שניהם חוסמים סגירה סופית של
   אצווית BUG-160/161/162/163.
4. **תזמן/בצע אימות production** ל-BUG-157/160/163 (Staging-only כרגע) —
   דורש החלטה מפורשת על race test בפרודקשן, כרגע מחוץ להיקף כברירת מחדל.
5. **F23: תוכן `business_rules` אמיתי** לארבעת סוגי הדרישה הנותרים
   (furniture_import/fiber_equipment/real_estate_listing/service) מה-owner
   — אין לנחש/להמציא.
