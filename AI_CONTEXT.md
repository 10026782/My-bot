# AI CONTEXT

**עודכן:** 15/08/2026 · **origin/main:** `e9d1ca8` (3 PRs מוזגו אחרי
`904ce13b` — #644 tool-catalog-db-phase2, #646 docs-reconciliation,
#645 BUG-164 PR2; ראו סעיף 3).

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקור האמת ראו `ROADMAP.md` (קודם כול), `CHANGELOG.md`. **שני המסמכים
> האלה פיגרו מאחורי `main` בסבב הזה** — `ROADMAP.md`'s `עודכן:` העליון
> עדיין 14/08/2026 (לא עודכן ל-#644/#645/#646), ו-`CHANGELOG.md`
> עוצר ב-PR #595-597 (10/08) — שניהם UNVERIFIED-STALE כמקור לסטטוס
> תפעולי נוכחי, ראו סעיף 4 סעיף 1. `BOSS_CURRENT_STATE.md`
> **stale מ-26/06/2026** — ארכיון היסטורי, לא לצטט כמצב נוכחי. **main
> גובר על מסמכי תכנון בכל סתירה. "מוזג" ≠ "פרוס" ≠ "מאומת בפרודקשן."**

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio): Identity → Router →
  Context → Agent, Airtable כ-CRM. ללא שינוי.
- **CORE v1 — COMPLETE / READY TO FREEZE** (freeze עצמו = החלטת owner,
  לא מוכרז) — קנוני: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md` +
  addendum 14/08/2026. ללא שינוי מהותי הסבב הזה.
- **BUG-164 — עדכון מהותי:** PR2 ("wire bounded creative authority",
  PR #645, e9d1ca8) מוזג ומאומת **חי ב-grep**: `cmd_marketing.py`'s
  `_create_demand_and_generate_ideas()` כעת מייבא ומפעיל
  `marketing_fact_authority`/`marketing_creative_renderer` (שהיו קיימים
  אך לא-מחווטים מ-PR1). הבאג הישן (Prompt 1 מעוות עובדות) **סגור בקוד**.
  **לא אומת עדיין ב-staging/production** (הצהרת ה-PR עצמו: "IMPLEMENTED.
  Not yet staging/production verified"). **`ROADMAP.md`/`BUG_AUDIT_LOG.md`
  עדיין מתעדים את המצב הישן (לפני PR2, "unwired") — תיעוד לא עודכן,
  אל תצטט אותם כסטטוס נוכחי לגבי BUG-164.**
- **תוסף חדש: SCOREBOS Tool Catalog DB Phase 2** (PR #644) — שכבת קטלוג
  חדשה DB-backed (`tools/tool_catalog_db.py` + migration + importer/
  snapshot CLIs + טסטים). **לא אומת אם מחווט למסלול חי** (dispatcher/
  agent) — UNVERIFIED, לא CRITICAL עד בדיקה ישירה.
- **תיעוד-בלבד: reconciliation pass** (PR #646) תיקן ניסוחים ב-
  `BUG_AUDIT_LOG.md`/`ROADMAP.md`/audit הקנוני/`AI_CONTEXT.md`/
  `CHANGE_CONTROL_LOG.md` מול `904ce13b`, אך **לא נגע בקוד ולא שינה את
  תוצאת ה-reconcile** (מוצהר בגוף ה-PR כ-byte-identical). המשמעות:
  **Context Librarian CI נשאר אדום** — 5 המקורות הלא-רשומים
  (`marketing_fact_authority.py` וכו', ראו סעיף 4) עדיין ממתינים
  להחלטת owner לרישום בקטלוג; PR2 (BUG-164) כנראה הוסיף שימוש חדש
  באותם מודולים ולא בדק אם זה משנה את הרשימה — **לא אומת בסבב הזה**.
- F23 M1/M2, D1 domain canonicalization, Tool Runtime Snapshot Phase 1 —
  ✅ ללא שינוי מהדוח הקודם (14/08).

## 2. Current System State

**תפעולי** (מאומת ב-grep/git log ישירות מול `e9d1ca8`):

- ActionGateway/ActionContract lifecycle, CORE v1 (TC6/TC8/TC9, F14/F15,
  PA-01, Track D, RP4/RP5 shadow) — ✅ ללא שינוי.
- **F23 M1/M2** — ✅ חי ומאומת בפרודקשן, ללא שינוי.
- **BUG-164 — קוד סגור, staging/production verification חסר.**
  `_create_demand_and_generate_ideas()` מפעיל כעת את שכבת ה-authority
  הסגורה (`ProtectedFact`/`CreativeProposal`, closed template registry);
  הפרסר הישן (`_parse_three_ideas`, regex על טקסט חופשי) נמחק לגמרי —
  אין נתיב fallback ישן. 13 טסטים ייעודיים + כל חבילות הטסט הקודמות של
  F23/Marketing ירוקות (מוצהר ב-PR, לא הורץ מחדש בסבב תיעוד זה).
  **לא בוצע webhook regression חי מול production** — נדרש לפני שינוי
  הסטטוס ל-VERIFIED.
- **business_tool_registry.py / SCOREBOS catalog (Phase 1)** — ✅ MERGED,
  ✅ WIRED (`app.py::run_agent()`), ללא שינוי.
- **Tool Runtime Snapshot Phase 1** — ✅ MERGED, קריאה-בלבד, ללא שינוי
  מהדוח הקודם.
- **D1 domain canonicalization** — ✅ מחווט, ללא שינוי.

**מיושם חלקית / לא production-active:**

- BUG-157/160/163 — ✅ STAGING VERIFIED; production verification לא
  בוצע (במכוון), ללא שינוי.
- **BUG-164** — ראה סעיף 1: קוד מחווט (PR1+PR2), production/staging
  verification עדיין פתוח כפריט עבודה.
- **SCOREBOS Tool Catalog DB Phase 2** (PR #644) — קוד/טסטים/migration
  קיימים (`core/migrations/002_tool_catalog.sql`,
  `tools/tool_catalog_db.py`, importer + DB-snapshot CLIs). **לא אומת
  בסבב הזה** אם `business_tool_registry.py`/`run_agent()` צורכים אותו
  בפועל, או אם ה-migration הורץ בפרודקשן. עד בדיקה ישירה: UNVERIFIED.
- TC7-B1, RP4/RP5 shadow, F52 — עדיין shadow/כבוי/אפס קוראים, ללא שינוי.
- ws2/ws3 projection — ללא שינוי מהדוח הקודם (read-only, לא בנתיב הטקסט).

**חסום (החלטה ארכיטקטונית/owner):**

- מחלקת `TurnCoordinator` פורמלית (Layer 2) — אפס מימוש, ללא שינוי.
- BUG-161/BUG-162 — ממתינים להחלטת מדיניות owner, ללא שינוי.
- BUG-148/150/152 — נרשמו, לא תוקנו, ללא שינוי.
- **Context Librarian CI — נשאר אדום.** 5 מקורות לא-רשומים מ-PR
  #623/#640 (`marketing_fact_authority.py` [STOP], `marketing_creative_
  renderer.py`, `marketing_creative_templates.py`,
  `tools/tool_runtime_snapshot.py`, `data/tool_registry/runtime_
  snapshot.json` [כולם REVIEW_REQUIRED]) — PR #646 תיקן תיעוד בלבד ולא
  שינה זאת. ייתכן ש-PR #644/#645 הוסיפו עוד מקורות לא-רשומים
  (`tools/tool_catalog_db.py` ודומיו) — **לא נבדק בסבב הזה**, `reconcile
  --check` לא הורץ (חוסר תלות `httpx` בסביבת התיעוד הזו).

## 3. Completed Since Last Update (מאז 14/08/2026 `904ce13b` →
15/08/2026 `e9d1ca8`, 3 PRs)

- **BUG-164 PR2 מוזג** (PR #645) — חיווט בפועל של שכבת ה-authority
  שנוספה ב-PR1 לתוך `cmd_marketing.py::_create_demand_and_generate_
  ideas()`; פרסר הטקסט-החופשי הישן נמחק. סגר את הבייפאס שאיפשר לעיוות
  עובדות להישמר. **קוד מוכן, לא אומת חי.**
- **SCOREBOS Tool Catalog DB Phase 2 מוזג** (PR #644) — שכבת DB חדשה
  לקטלוג הכלים (migration + importer/snapshot CLIs + 147 שורות טסט).
  זיקה לזרימת הריצה **לא אומתה** בסבב תיעוד זה.
- **Reconciliation pass מוזג** (PR #646) — תיקוני ניסוח/עובדה במסמכי
  audit קנוניים (`BUG_AUDIT_LOG.md`, `ROADMAP.md`, `CORE_COMPLETION_
  AUDIT_20260810.md` addendum, `CHANGE_CONTROL_LOG.md`), ללא שינוי קוד.
  **לא פתר את ה-CI האדום** (מוצהר: reconcile output byte-identical).

## 4. Next Priorities

1. **אמת BUG-164 חי:** הרץ webhook regression אמיתי מול production
   (`/marketing_new`) ובדוק שהרעיונות הנשמרים אכן עוברים דרך ה-renderer
   הסגור ולא מעוותים עובדות — רק אז לשנות סטטוס ל-VERIFIED. עדכן
   `ROADMAP.md`/`BUG_AUDIT_LOG.md` בהתאם (שניהם עדיין משקפים "unwired").
2. **בדוק אם Tool Catalog DB Phase 2 מחווט לזרימה החיה** (`business_
   tool_registry.py`/`run_agent()`) והאם ה-migration רץ בפרודקשן —
   כרגע UNVERIFIED, לא CRITICAL, עד grep/אימות ישיר.
3. **רשום את 5 המקורות ב-Context Librarian catalog** (owner decision) —
   ראו סעיף 2; זו עדיין החסימה היחידה הידועה ל-CI ירוק ב-`main`, ויש
   לבדוק אם PR #644/#645 הוסיפו מקורות נוספים לרשימה.
4. **עדכן את `ROADMAP.md`/`CHANGELOG.md` עצמם** — שניהם מפגרים אחרי
   `main` (ROADMAP לא מתעד #644/#645/#646; CHANGELOG עוצר ב-PR #597).
5. **סגור BUG-161/BUG-162** (החלטת owner) ותזמן production verification
   ל-BUG-157/160/163 — ללא שינוי מסבבים קודמים.
