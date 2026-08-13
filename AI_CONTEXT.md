# AI CONTEXT

**עודכן:** 13/08/2026 · **origin/main:** `98f3626` (PR #620 — Track 2 TC8/BUG-158
regression-harness fixture fix v2; latest of a ~10-PR run since PR #605).

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
- **F23 Marketing Bridge M1** (`/marketing_new`) — ✅ VERIFIED IN PROD,
  ללא שינוי. **F23 M2** (`/marketing_status`, כרטיס Next Action) **מוזג
  ל-`main` היום** (PR #613) אך **טרם פרוס/מאומת בפרודקשן** — 🟡 CODE DONE,
  NOT VERIFIED.
- אחד משני הפערים הלא-חוסמים ב-CORE **נסגר בסבב הזה**: רישום Context
  Librarian ל-מקורות TC2-TC10/marketing (PR #611) — טיפל בשער ה-freshness
  שהיה אדום ב-CI. הפער השני (מחלקת `TurnCoordinator` פורמלית, Layer 2)
  **נשאר לא ממומש** — רק תועד/הובהר (PR #612), אין שינוי קוד.
- **חדש: אימות Staging אמיתי (לא production) ל-3 באגים שהיו "קוד תוקן, לא
  מאומת"** — BUG-157 (concurrency race ב-`propose_action()`), BUG-160
  (עקיפת parser דטרמיניסטי ע"י מרכאה לא מאוזנת), BUG-163 (כיסוי intent
  חסר ל-complete_task/update_task) — כולם עברו ל-✅ **STAGING VERIFIED**
  (13/08/2026, TRACK 3), מול `ActionGateway` אמיתי ב-`my-bot-approval-
  staging`. **אימות production עדיין לא בוצע** במכוון (race test
  ב-production דורש החלטה נפרדת, מחוץ להיקף הסבב הזה).
- BUG-161 (reconfirmation לא עקבי במסלול Agent) ו-BUG-162 (הפרת
  turn-ownership) — נשארים פתוחים, ממתינים להחלטת מדיניות מפורשת של
  ה-owner. ללא שינוי.
- שני ה-merge-ים האחרונים (PR #619/#620) הם **fixture fixes בטסטים בלבד**
  בתוך ה-harness המבודד של TC10 (BUG-158 recovery + TC8 callback
  R11/R13/R16) — לא נגעו בקוד runtime/מוצר.

## 2. Current System State

**תפעולי** (מאומת ב-grep/log/Render API על `main`):

- ActionGateway/ActionContract lifecycle — מקור אמת יחיד, חי, ✅.
- CORE v1 (ActionGateway, TC6/TC8/TC9, F14/F15, PA-01, Track D, RP4/RP5
  shadow) — ✅ ללא שינוי מהסבבים הקודמים.
- **F23 M1** (`/marketing_new`) — ✅ חי בפרודקשן,
  `FEATURE_MARKETING_BRIDGE=true` דלוק בפרודקשן כרגע.
- **F23 M2** (`/marketing_status`/`מצב_שיווק`) — קוד מוזג ל-`main`
  (`d2cfb8b`/PR #613), **לא פרוס ל-Render, לא מאומת חי**.

**מיושם חלקית / לא production-active:**

- BUG-157/160/163 — מוזגים+פרוסים ל-`main` מזמן, כעת גם ✅ STAGING
  VERIFIED (13/08) מול race/regression אמיתי; **verification בפרודקשן
  עדיין לא בוצע** (במכוון, לא באג).
- TC7-B1 (`core/claim_authorization.py`) — עדיין אפס קוראים חיים, ללא
  שינוי.
- RP4/RP5 shadow, F52 Unified Status Formatter — עדיין shadow/כבוי
  כברירת מחדל, ללא שינוי.
- F23 Marketing Rules (Business Memory writer) — עדיין אפס caller,
  נדחה במפורש ל-"Later".
- F23 `business_rules` — רק ל-recruitment תוכן אמיתי; 4 סוגי דרישה
  נותרים עם ערך ניטרלי מפורש. PR #606 חיזק את ה-anti-invention contract
  ב-Production Handoff סביב זה, אך לא הוסיף תוכן עסקי חסר.

**חסום (החלטה ארכיטקטונית/owner, לא implementation blocker):**

- מחלקת `TurnCoordinator` פורמלית (Layer 2) — אפס מימוש, ממתינה להחלטת
  owner; PR #612 רק הבהיר תיעוד, לא קוד.
- BUG-161/BUG-162 — ממתינים להחלטת מדיניות owner (reconfirmation
  ב-Agent path / turn-ownership).
- BUG-148/150/152 — נרשמו, לא תוקנו, ללא שינוי.

## 3. Completed Since Last Update (מאז 12/08/2026 `4c94d68` → 13/08/2026
`98f3626`, 34 commits / כ-10 PRs)

- **F23 M2 מוזג** (PR #613): `/marketing_status`+`מצב_שיווק` — רשימת
  Demands מורשית + כרטיס Next Action ע"י `marketing_orchestrator.py`
  חדש (pure/pull-only), משתמש מחדש במסלול הכתיבה הקיים מ-M1 (לא נוסף
  מסלול חדש). Fail-closed על 0 או 2+ Creatives ממתינים. **טרם פרוס/מאומת.**
- **F23 Production Handoff grounding** (PR #606): anti-invention
  contract, ניסוח ניטרלי ל-demand types בלי `business_rules` אמיתי,
  known/unknown production inputs מפורשים.
- **ממשל**: רישום Context Librarian ל-מקורות TC2-TC10 + marketing
  (PR #610/#611) — סוגר אחד משני הפערים הלא-חוסמים מה-audit הקנוני.
- **תיעוד**: הבהרת הפער בין מנגנוני TC2-TC10 הפועלים בפועל לבין מחלקת
  `TurnCoordinator` הפורמלית שעדיין לא נבנתה (PR #612) — ללא שינוי runtime.
- **תיעוד**: אושר ונוסף מסמך "SCOREBOS UX constitution" (PR #609).
- **TRACK 3 — אימות Staging אמיתי**: BUG-157 (race של 5 קריאות
  `propose_action()` מקבילות + race של 3 קריאות `approve` מקבילות,
  invariants A–E כולם PASS), BUG-160 (תיקון עקיפת quote), BUG-163 (תיקון
  כיסוי intent) — כולם עברו מ-"קוד תוקן, לא מאומת" ל-✅ STAGING VERIFIED
  מול `ActionGateway`/Airtable אמיתיים ב-`my-bot-approval-staging` (לא
  mock, לא production).
- **טסטים בלבד**: תוקנו fixture stubs בהרנס הרגרסיה המבודד של TC10
  (BUG-158 recovery + TC8 callback R11/R13/R16, PR #619/#620) — קוד
  מוצר/runtime לא נגע.

## 4. Next Priorities

1. **פרוס ואמת בפרודקשן את F23 M2** (`/marketing_status`) — מוזג אך לא
   חי/מאומת עדיין.
2. **קבל החלטת owner מפורשת** ל-BUG-161 (מדיניות reconfirmation במסלול
   Agent) ו-BUG-162 (הפרת turn-ownership) — שניהם חוסמים סגירה סופית של
   אצווית BUG-160/161/162/163.
3. **תזמן/בצע אימות production** ל-BUG-157/160/163 (Staging-only כרגע) —
   דורש החלטה מפורשת על race test בפרודקשן, כרגע מחוץ להיקף כברירת מחדל.
4. **מחלקת TurnCoordinator פורמלית (Layer 2)** — עדיין החלטת ארכיטקטורה
   של owner, לא חסם implementation.
5. **F23: תוכן `business_rules` אמיתי** לארבעת סוגי הדרישה הנותרים
   (furniture_import/fiber_equipment/real_estate_listing/service) מה-owner
   — אין לנחש/להמציא.
