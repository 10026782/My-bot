# AI CONTEXT

**עודכן:** 14/08/2026 · **origin/main:** `904ce13b` (PR #641 — regeneration
עצמה + 7 קומיטים/PRs נוספים שמוזגו אחריה/סביבה: #623/#624/#634/#636/#640/#642;
ראו סעיף 3).

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקור האמת ראו `ROADMAP.md` (קודם כול), `CHANGELOG.md`, ו-
> `docs/audit/CORE_COMPLETION_AUDIT_20260810.md` (קנוני ל-CORE, מבוסס main
> `134148e` + addendum מ-14/08/2026). `BOSS_CURRENT_STATE.md`
> **stale מ-26/06/2026** — ארכיון היסטורי, לא לצטט כמצב נוכחי. **main גובר
> על מסמכי תכנון בכל סתירה. "מוזג" ≠ "פרוס" ≠ "מאומת בפרודקשן."**

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio): Identity → Router →
  Context → Agent, Airtable כ-CRM. ללא שינוי.
- **CORE v1 — COMPLETE / READY TO FREEZE** (freeze עצמו = החלטת owner, לא
  מוכרז) — קנוני: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`, **כולל
  addendum 14/08/2026** (מעדכן CI-red ו-ws2/ws3 מול main נוכחי, ראה שם).
- **F23 Marketing Bridge M1/M2** — ✅ VERIFIED IN PROD, ללא שינוי.
- **BUG-164 — עדכון:** PR1 ("Authority/Foundation" — PR #623) מוזג
  (14/08), אך מאומת ב-grep שאין קורא לו מחוץ לטסטים — **foundation קיים,
  לא מחווט, הבאג עצמו עדיין פתוח**. אין עדיין live cutover.
- BUG-157/160/163 נשארים ✅ STAGING VERIFIED; production verification
  עדיין לא בוצע במכוון. BUG-161/162 — פתוחים, ממתינים להחלטת owner.
  TurnCoordinator Layer 2 הפורמלי — עדיין אפס מימוש (מאומת ב-grep מחדש
  מול `904ce13b`).
- **⚠️ Context Librarian CI — אדום כרגע ב-`904ce13b` עצמו** (לא רק
  היסטורי): גם ה-workflow "CI" וגם workflow חדש נפרד "Context Librarian
  Reconciliation" (נוסף 14/08 ע"י PR #634, לא קיים כשהאודיט המקורי
  נכתב) מחזירים `failure`. שלב הרקונסיליאציה נכשל וגרם ל-skip של
  TC10/pytest-librarian steps (לא PASS, לא FAIL — פשוט לא רצו).
- **פער תיעוד:** בין `98f3626` (13/08) ל-`904ce13b` (14/08) מוזגו כ-71
  קומיטים. סבב זה סגר verification ישיר לחלק מהם (ראה סעיף 3); השאר
  נשארים UNVERIFIED במפורש — לא לצטט סטטוס תפעולי שלהם.

## 2. Current System State

**תפעולי** (מאומת ב-grep/git log/`gh run`/`gh pr` ישירות מול `904ce13b`):

- ActionGateway/ActionContract lifecycle — מקור אמת יחיד, חי, ✅.
- CORE v1 (ActionGateway, TC6/TC8/TC9, F14/F15, PA-01, Track D, RP4/RP5
  shadow) — ✅ ללא שינוי.
- **F23 M1/M2** — ✅ חי ומאומת בפרודקשן, ללא שינוי.
- **business_tool_registry.py / SCOREBOS catalog** — ✅ MERGED, ✅ WIRED
  (`app.py::run_agent()`, קריאה ישירה לפני tool loop). DEPLOYED/RUNTIME
  VERIFIED — **לא evidenced** (כבר מתועד נכון ב-
  `docs/tool-research/BUSINESS_TOOLS_RUNTIME_VERIFICATION.md`, ללא שינוי
  נדרש).
- **תוסף חדש: Tool Runtime Snapshot Phase 1** (PR #640, 14/08) — מוסיף
  `tools/tool_runtime_snapshot.py`: מייצר snapshot קריאה-בלבד, מאומת
  strict, מ-business-tool seed קיים; `business_tool_registry.py` צורך
  אותו כעת (65 שורות שונו). מפורש **מחוץ ל-scope**: Airtable, crawler,
  Mini-App, ActionGateway/approvals/execution. 14 טסטים ממוקדים
  (`test_tool_runtime_snapshot.py`), `py_compile` ירוק. לא נוגע בנתיב
  קריטי — קריאה-בלבד, לא הרחבה של recommendation feature קיים.
- **תיעוד ארכיטקטוני בלבד: Dynamic SCOREBOS Tool Capability Registry**
  (PR #639) — `docs/tool-research/SCOREBOS_DYNAMIC_TOOL_CAPABILITY_REGISTRY.md`
  בלבד. **מפורש: לא מומש, אין שינוי קוד/runtime.** הצעת ארכיטקטורה
  לעתיד, לא מצב נוכחי.
- **D1 — קנוניזציה של domain רה-קרוטמנט** (PR #598, מוזג 11/08) —
  Business Memory adapter פולט `recruitment` (lowercase) חי; קריאות
  legacy `Recruitment` נתמכות לתאימות. מחווט דרך routing, identity,
  weekly summary, Lead Event. אומת ב-PR body מול Airtable חי (read-only)
  + 4 חבילות טסטים (10/24/50/50 pass).

**מיושם חלקית / לא production-active:**

- BUG-157/160/163 — ✅ STAGING VERIFIED; production verification לא
  בוצע (במכוון).
- **BUG-164** — ראה תיקון בסעיף 1. Foundation (PR #623) מוזג, לא מחווט.
- TC7-B1 — עדיין אפס קוראים חיים, ללא שינוי.
- RP4/RP5 shadow, F52 — עדיין shadow/כבוי כברירת מחדל, ללא שינוי.
- **ws2/ws3 (`core/evidence_projection.py`/`core/lifecycle_projection.py`)
  — עדכון:** האודיט הקנוני (10/08) טען "אפס הפניות מ-`core/action_gateway.py`".
  זה כבר לא מדויק כפשוטו — יש כעת קריאות אמיתיות דרך `approval_status()`/
  `execution_status()`/`reply_ownership_for_contract()`, כל אחת מתועדת
  במפורש כ-**read-only WS2/TC6 projection**, לא כחלק ממסלול הרכבת
  טקסט-התשובה. `TC9`'s `_message_contract_for_fact()` עדיין נראה כבעל
  הסמכות היחיד לטקסט (לא אומת end-to-end בסבב הזה). ראו addendum
  ב-`CORE_COMPLETION_AUDIT_20260810.md`. **סיכון הארכיטקטורה המקורי
  (STOP gate) מצומצם, לא סגור — כל חיווט נוסף עובר דרך
  `docs/governance/GAP_QUALIFICATION.md`.**
- **Context Librarian — אדום ב-`904ce13b`, סיבה מדויקת ידועה:** הרצה
  ישירה של `python3 -m tools.context_librarian reconcile --check` מול
  `904ce13b` מחזירה `"outcome": "OWNER_DECISION_REQUIRED"` עם 5 מקורות
  לא-רשומים ב-catalog — כולם מ-PR #623/#640, **לא קשורים ל-PR
  #611/#628/#634/#638** (אלה האחרונים לא הסיבה): `marketing_fact_authority.py`
  → **STOP** ("unregistered source may change authority"),
  `marketing_creative_renderer.py`/`marketing_creative_templates.py`/
  `tools/tool_runtime_snapshot.py`/`data/tool_registry/runtime_snapshot.json`
  → REVIEW_REQUIRED ("new runtime source"/"new source with unknown role").
  זה מחזק עצמאית את הממצא למעלה (BUG-164 PR1 לא מחווט) — הכלי הרשמי
  מזהה בדיוק את אותם קבצים כ-"עלול לשנות authority". **תיקון: לרשום את
  5 המקורות האלה ב-catalog (owner decision על התפקיד שלהם), לא לגעת
  בקוד.**
- **קומיטים שנשארים UNVERIFIED בפירוט (לא נבדקו לעומק בסבב הזה):**
  Ventures/VUX UX (PR #625/#629/#632/#636/#642 — foundations/workspace/
  collection-lifecycle/soft-3D/venture-detail), business tool playbooks
  UX פרטים נוספים (PR #631/#637 מעבר למה שכבר מאומת למעלה), Context
  Librarian catalog-registration/reconciliation-engine internals (PR
  #611/#628/#634/#638 מעבר לתוצאת ה-CI האדומה עצמה). **אין לצטט סטטוס
  תפעולי מפורט של אלה עד בדיקה ישירה.**

**חסום (החלטה ארכיטקטונית/owner, לא implementation blocker):**

- מחלקת `TurnCoordinator` פורמלית (Layer 2) — אפס מימוש (אומת מחדש
  ב-grep מול `904ce13b`), ממתינה להחלטת owner.
- BUG-161/BUG-162 — ממתינים להחלטת מדיניות owner.
- BUG-148/150/152 — נרשמו, לא תוקנו, ללא שינוי.

## 3. Completed Since Last Update (מאז 13/08/2026 `98f3626` → 14/08/2026
`904ce13b`, ~71 commits — verification חלקי, לא מלא)

- **F23 M2 — production verification הושלם** (13/08, ללא שינוי מהדוח
  הקודם).
- **BUG-164 נרשם (13/08) ואז PR1/Authority-Foundation מוזג (14/08,
  PR #623)** — foundation בלבד, לא מחווט. ראו סעיף 1-2.
- **D1 domain canonicalization מוזג ומאומת** (PR #598, 11/08 — נבדק
  לעומק בסבב הזה, לא רק כותרת).
- **Tool Runtime Snapshot Phase 1 מוזג** (PR #640, 14/08 — נבדק לעומק,
  קריאה-בלבד, מחוץ למסלול קריטי).
- **Dynamic Tool Capability Registry — הצעת ארכיטקטורה מתועדת, לא
  מומשה** (PR #639, נבדק לעומק — docs בלבד).
- **ws2/ws3 wiring claim תוקן** — ראו סעיף 2, ה-addendum ב-audit
  הקנוני.
- **TC10 baseline מעודכן** — הרצה אמיתית אחרונה: PASS ב-`7d742f7`
  (13/08, CI run מאומת), לא רק ה-21/21 ההיסטורי ב-`134148e`.
- **Context Librarian CI — אדום ב-`904ce13b`, סיבה מדויקת מזוהה** (ראה
  סעיף 2): 5 מקורות לא-רשומים מ-PR #623/#640, **לא** מ-#611/#628/#634/#638.
  תיקון (רישום ב-catalog) לא בוצע בסבב תיעוד זה — מחוץ ל-scope.
- **קטגוריות שנותרו לא-מסוכמות** (Ventures/VUX UX, Context Librarian
  internals מעבר ל-CI, business-tool-playbooks UX פרטים) — ראו רשימה
  מלאה בסעיף 2. טעונות סבב ייעודי נוסף.

## 4. Next Priorities

1. **רשום את 5 המקורות החדשים ב-Context Librarian catalog** —
   `marketing_fact_authority.py` (STOP: "unregistered source may change
   authority"), `marketing_creative_renderer.py`,
   `marketing_creative_templates.py`, `tools/tool_runtime_snapshot.py`,
   `data/tool_registry/runtime_snapshot.json` (REVIEW_REQUIRED). דורש
   owner decision על התפקיד הארכיטקטוני של כל אחד, לא שינוי קוד. זו
   כרגע החסימה היחידה שמונעת CI ירוק ב-`main`.
2. **סגור verification לקומיטים שנותרו UNVERIFIED** (רשימה בסעיף 2) —
   בעיקר Ventures/VUX UX ו-Context Librarian internals.
3. **טפל ב-BUG-164** — foundation (PR1) קיים; נדרשת החלטת owner/PR
   נוסף לחיווט בפועל ל-`_create_demand_and_generate_ideas()`.
4. **קבל החלטת owner מפורשת** ל-BUG-161/BUG-162.
5. **תזמן/בצע אימות production** ל-BUG-157/160/163.
6. **F23: תוכן `business_rules` אמיתי** לארבעת סוגי הדרישה הנותרים —
   אין לנחש/להמציא.
