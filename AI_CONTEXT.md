# AI CONTEXT

**עודכן:** 16/08/2026 · **origin/main:** `1c3d7fd` (6 PRs מוזגו אחרי
`e9d1ca8` — #647 BUG-051-FU, #648 מסמך-תדרוך יומי קודם, #649 BUG-164
demand-fidelity, #650 Ventures UI, #651 Librarian owner decision, #653
Librarian PR-time gate; ראו סעיף 3).

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקור האמת ראו `ROADMAP.md` (קודם כול), `CHANGELOG.md`. **שני המסמכים
> האלה עדיין מפגרים אחרי `main`** — `ROADMAP.md`'s `עודכן:` העליון הוא
> 15/08/2026 (מתעד את #649 בלבד, לא #647/#650/#651/#653), ו-`CHANGELOG.md`
> עוצר הרבה קודם (סעיף "Unreleased" לא נבדק שורה-שורה בסבב הזה — לא
> להסתמך עליו כמקור סטטוס נוכחי). `BOSS_CURRENT_STATE.md` **stale
> מ-26/06/2026** — ארכיון, לא לצטט כמצב נוכחי. **main גובר על מסמכי
> תכנון בכל סתירה. "מוזג" ≠ "פרוס" ≠ "מאומת בפרודקשן."**

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio): Identity → Router →
  Context → Agent, Airtable כ-CRM. ללא שינוי.
- **CORE v1 — COMPLETE / READY TO FREEZE** (freeze עצמו = החלטת owner,
  לא מוכרז) — קנוני: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`.
  ללא שינוי הסבב הזה.
- **Context Librarian CI — עבר מ-אדום ל-ירוק, מאומת ישירות מול GitHub
  Actions API** (לא רק claim ב-PR): 7 ריצות push-to-main רצופות נכשלו
  (`#644`→`#649`, כולל `e9d1ca8`), ואז PR #651 (owner decision על 9
  המקורות הלא-רשומים) החזיר `conclusion=success`; PR #653 (מנגנון
  gate חדש ב-PR-time) עדיין ירוק ב-`1c3d7fd` (ה-tip הנוכחי). זה סוגר את
  סעיף 4-פריט-3 מהעדכון הקודם.
- **PR #653 מוסיף שכבת מניעה חדשה:** בדיקת "מקור לא-רשום" עוברת
  מ-post-merge (main בלבד) ל-PR-time — PR עתידי שמכניס קובץ authority
  חדש ייחסם *לפני* מיזוג, לא רק אחריו. תשתית ממשל בלבד, אין שינוי
  runtime עסקי.
- **BUG-051-FU (PR #647) — תוקן, לא מתועד ב-ROADMAP/BUG_AUDIT_LOG,
  ולא מאומת בפרודקשן.** סוגר repro אמיתי: `"צור איש קשר..."` (intent
  `create_contact`, conf=0.90) נבלע בשקט ל-Lead capture במקום Contact.
  גם שיפור matching בקטלוג הכלים החיצוני (נורמליזציית "ה-" הידיעה
  בעברית + ביטוי חסר ל-Squoosh). טסטים ייעודיים ירוקים מוצהר ב-PR
  (כולל תיקון ל-CodeRabbit findings שני-שלב) — **לא הורץ מחדש בסבב
  תיעוד זה, לא נבדק חי מול production**.
- **BUG-164 — עדכון נוסף מעבר לדיווח הקודם:** מעבר לחיווט הדטרמיניסטי
  שכבר מוזג ומאומת ב-grep, PR #649 הוסיף `_DEMAND_FIDELITY_RULE`
  (הגנת-עומק ברמת prompt) ל-3 סוגי המשימה שעדיין free-text ב-
  `compose_brief()` (`creative_review`/`ad_package`/`publishing_plan`).
  **לא VERIFIED** מול קריאת AI חיה — הצהרה מפורשת ב-ROADMAP עצמו.
- **SCOREBOS Tool Catalog DB Phase 2 — חיווט אומת ב-code read ישיר
  (PR #651's own commit body):** `business_tool_registry.py`'s
  `list_tools()`/`maybe_recommend()` (call site חי מ-`app.py`) כן
  קוראים מה-snapshot שנוצר ע"י ה-DB layer, לא רק מה-dict המוטבע. **לא
  אומת** אם ה-migration עצמו רץ בפרודקשן.
- F23 M1/M2, D1 domain canonicalization, Tool Runtime Snapshot Phase 1 —
  ✅ ללא שינוי מהדוח הקודם.

## 2. Current System State

**תפעולי** (מאומת ב-grep/git log/GitHub API ישירות מול `1c3d7fd`):

- ActionGateway/ActionContract lifecycle, CORE v1, F23 M1/M2, D1
  canonicalization, Tool Runtime Snapshot Phase 1 — ✅ ללא שינוי.
- **Context Librarian post-merge + PR-time gate** — ✅ שניהם ירוקים
  ב-`main` נכון לרגע זה (מאומת GitHub Actions API, לא רק PR text).
- **business_tool_registry.py / SCOREBOS catalog** — ✅ MERGED + WIRED
  (Phase 1 כבר היה; Phase 2 ה-snapshot layer אומת חי בקריאת קוד ב-PR
  #651, ראו סעיף 1).
- **BUG-164** — קוד סגור לנתיב הדטרמיניסטי + הגנת-עומק prompt-level
  לשלושת הנתיבים הנותרים. **production/staging verification עדיין
  פתוח** כפריט עבודה (ללא שינוי מסבב קודם).

**מיושם חלקית / לא production-active:**

- BUG-157/160/163 — ✅ STAGING VERIFIED; production verification לא
  בוצע (במכוון), ללא שינוי.
- **BUG-051-FU** — קוד מוזג, טסטים ירוקים מוצהר, **לא אומת חי**
  (חדש בסבב הזה — ראה סעיף 1).
- **BUG-164** — 3 נתיבי free-text (`creative_review`/`ad_package`/
  `publishing_plan`) מוגנים ברמת prompt בלבד, לא דטרמיניסטית.
- **SCOREBOS Tool Catalog DB Phase 2** — הקוד/ה-wiring אומתו כנ"ל;
  הרצת ה-migration בפרודקשן עצמה **לא אומתה**.
- TC7-B1, RP4/RP5 shadow, F52 — עדיין shadow/כבוי/אפס קוראים, ללא שינוי.

**חסום (החלטה ארכיטקטונית/owner):**

- מחלקת `TurnCoordinator` פורמלית (Layer 2) — אפס מימוש, ללא שינוי.
- BUG-161/BUG-162 — ממתינים להחלטת מדיניות owner, ללא שינוי.
- BUG-148/150/152 — נרשמו, לא תוקנו, ללא שינוי.

## 3. Completed Since Last Update (מאז 15/08/2026 `e9d1ca8`
→ 16/08/2026 `1c3d7fd`, 6 PRs)

- **BUG-051-FU מוזג** (PR #647) — Router-confirmed `create_contact`
  (וכו') כבר לא נבלע ל-Lead capture ע"י `lead_candidate_handler.py`;
  נורמליזציית "ה-" הידיעה + ביטוי Squoosh חסר ב-`business_tool_
  registry.py`. **לא תועד עדיין ב-ROADMAP/BUG_AUDIT_LOG**, לא אומת
  בפרודקשן.
- **AI_CONTEXT.md יומי קודם מוזג** (PR #648) — ריצת הסבב הזה עצמו,
  אתמול.
- **BUG-164 demand-fidelity rule מוזג** (PR #649) — הגנת-עומק
  ל-3 נתיבי `compose_brief()` הנותרים; ROADMAP.md עודכן באותה PR.
- **Ventures UI polish מוזג** (PR #650) — `tma-frontend` בלבד
  (hierarchy/mobile lifecycle), אין נגיעה ב-backend.
- **Context Librarian owner decision מוזג** (PR #651) — סיווג 9
  המקורות הלא-רשומים (3 קבצי BUG-164 authority + 6 קבצי SCOREBOS DB)
  אושר ע"י owner תחת nodes קיימים (`layer.marketing`,
  `decision.external_business_tool_recommendation_catalog`), ללא node
  חדש. **הפך את CI ל-ירוק אחרי 7 ריצות אדומות רצופות** — מאומת ישירות
  מול GitHub Actions.
- **Context Librarian PR-time gate מוזג** (PR #653 + תיקוני CodeRabbit)
  — מקור לא-רשום נחסם עכשיו כבר ב-PR, לא רק אחרי מיזוג ל-main. תשתית
  ממשל בלבד.

## 4. Next Priorities

1. **אמת BUG-164 חי:** הרץ webhook regression אמיתי מול production
   (`/marketing_new`) לנתיב הדטרמיניסטי, ובדוק ידנית שהגנת-ה-prompt
   ב-3 הנתיבים הנותרים (`creative_review`/`ad_package`/
   `publishing_plan`) אכן מונעת עיוות עובדות — עדיין UNVERIFIED.
2. **תעד את BUG-051-FU ב-`ROADMAP.md`/`BUG_AUDIT_LOG.md`** ותזמן
   אימות production — קוד מוזג אך תיעוד וverification עדיין חסרים.
3. **אמת שה-migration של Tool Catalog DB Phase 2 רץ בפרודקשן** — ה-code
   wiring כבר אומת (סעיף 1), הפריט הפתוח היחיד הוא ה-DB layer עצמו.
4. **עדכן את `ROADMAP.md`/`CHANGELOG.md` עצמם** מול `1c3d7fd` — ROADMAP
   מפגר אחרי #647/#650/#651/#653, CHANGELOG מפגר משמעותית יותר.
5. **סגור BUG-161/BUG-162** (החלטת owner) ותזמן production verification
   ל-BUG-157/160/163 — ללא שינוי מסבבים קודמים.
