# TMA UX Audit — Follow-up / Correction Pass

**תאריך:** 11/08/2026
**סטטוס:** `WIP DESIGN EVIDENCE / SCREEN ARCHITECTURE EXPLORATION`
**היקף:** current-state UX/UI, screen qualification, עקביות, נגישות בסיסית וארכיטקטורת מסכים עתידית.
**מקורות:** `tma-frontend/src`, `tma_api.py`, `BOSS_Refactor_Plan.md`, והרצת UI מקומית עם 12 צילומי המסך שבתיקייה זו.

> המסמך אינו מפרסם ארכיטקטורת יעד סופית. הוא מפריד בין עובדות שנצפו, החלטות עיצוב בטוחות, מועמדים חזקים, שאלות פתוחות ומועמדי איחוד עתידיים. אין למחוק מסכים או לשנות production כחלק מהאודיט הזה.

## 1. סיכום מנהלים

המערכת הקיימת מציגה אוסף של מסכים ועולמות עסקיים אמיתיים, אבל הם אינם נראים או מתנהגים עדיין כמו מערכת אחת. הבעיה המרכזית אינה רק מספר המסכים; היא היעדר חוזה משותף ל־BOSS: היררכיית כותרת, ניווט, פעולות, סטטוסים, מצבי טעינה/שגיאה, detail, אישור ו־receipt.

העיקרון המנחה לסבב הבא הוא:

> **ONE BOSS SCREEN SYSTEM** — מאחדים את שפת המסכים וההתנהגות לפני שמאחדים או מצמצמים את המסכים עצמם.

מסקנות בעלות ביטחון גבוה כרגע:

- `Owner Control / Command Center`, `Ventures`, `Marketing / Media`, `Finance` ו־`Leads / CRM` הם מועמדי CORE חזקים.
- `Actions / My Work` הוא דרישת שימוש חזקה, אך פני השטח הסופיים שלו עדיין פתוחים.
- `Operations` הוא מועמד CORE סביר, אך הגבולות מול Ventures, Projects ו־My Work עדיין דורשים בדיקה.
- `Approvals`, `Activity / Business Memory`, `Digest`, `Emergency Stop`, פרטי ישויות ו־System Health אינם מצדיקים כרגע הנחה של יעד ניווט ראשי עצמאי.
- אין לקבע 5/6/7 tabs או מפת ניווט סופית לפני Screen Qualification ו־validation של החפיפות.

## 2. Current-state audit

### מה נצפה בממשק הקיים

- ה־Projects Hub מציג KPI, חריגים וכרטיסי פרויקט, ובכותרת יש ריבוי קיצורי דרך אייקוניים.
- `App.tsx` מנהל views נפרדים עבור Hub, Leads, Activity, Approvals, Finance, Personal, System Health, Game, Check-in, Digest, Owner Control ו־Ventures.
- Lead Pipeline ו־Lead Detail הם כבר בפועל זרימת master-detail, אך מוצגים כחוויות נפרדות ועמוסות.
- Owner Control ו־BossDigest מציגים חפיפה סביב תשומת לב, חריגים, approvals ו־next actions.
- Ventures כבר קיים כקומפוננטה וכמקור נתונים נפרד; הוא אינו רק וריאציה של CRM.
- Finance עונה על שאלות עסקיות שונות מ־CRM/Operations.
- Activity מוצג כ־feed כללי, אך מקור הנתונים והמשמעות העסקית שלו אינם מסבירים מספיק אם מדובר בזיכרון, אינטראקציות, receipts או שילוב.
- Check-in ו־Game משתמשים באותה שכבת חוויה רוחבית רעיונית, אך Check-in הוא מסך פעולה ו־Game הוא שכבת engagement.
- Marketing / Media קיים כרעיון עסקי, טבלאות/מושגים ו־Media upload עתידי, אך אינו מיוצג כיום כ־workspace מלא.

### ראיות וסייגים

- צילומי המסך נלכדו באודיט זה עם API דמה סינתטי, לאחר שה־API החי החזיר `401` בסביבת הבדיקה.
- לכן הממצאים על היררכיה, צפיפות, naming וזרימות נצפות; הם אינם הוכחה לשימוש בפועל, לנתוני Airtable חיים, להרשאות, ל־latency או ל־production.
- לא בוצעה בדיקת keyboard, קורא מסך, contrast מדוד, safe-area או touch targets במכשיר Telegram אמיתי.

## 3. בעיות UX שאומתו

1. **עומס ניווט בכותרת:** כפתורי אייקון רבים באותה שורה מקטינים discoverability ויוצרים עדיפות לא ברורה במסך מובייל. (01-hub)
2. **חפיפת שאלות:** Hub, Owner Control ו־Digest מתחרים על “מה דורש ממני תשומת לב עכשיו?”. (01, 06, 09)
3. **פעולה ראשית לא עקבית:** במסכי detail וב־Approvals יש מספר פעולות משמעותיות ללא pattern אחיד של primary action, preview, אישור ו־receipt. (02, 12)
4. **קונטקסט חסר ב־Activity:** feed כללי ללא סינון/קישור ישיר לישות או לפרויקט מקשה להפוך אירוע להחלטה. (05)
5. **Lead Detail עמוס:** Ask AI, score, task, outcome ו־follow-up מתחרים על היררכיה אחת. (12)
6. **ערבוב בין עבודה עסקית לעבודה אישית:** Personal/Assets מנותק מהקשר של פרויקט ותפעול, אך גם אינו עונה על אותו צורך כמו My Work. (04)
7. **מצבי שמירה לא מספיק ברורים:** Check-in דורש הבחנה גלויה בין “נשמר”, “שומר” ו־“לא נשמר”. (07)
8. **תלות בצבע/Emoji:** סטטוסים ואייקונים אינם צריכים להיות האות היחיד למשמעות; נדרשים label, טקסט או icon נגיש. (01–12)
9. **RTL ושפה:** ערבוב עברית/אנגלית וניסוחים טכניים מגדילים עומס קריאה; נדרש contract לשפה, יישור וחיצי חזרה.

## 4. Unified Screen System — ההמלצה הראשונה

לפני איחוד או מחיקה, להגדיר ספריית BOSS משותפת ו־screen contract. הדומיינים יכולים להיות שונים במבנה, אך לא להיראות כמו אפליקציות נפרדות.

### חוזה המסך המשותף

| שכבה | כלל אחיד מוצע |
|---|---|
| App shell | RTL, safe-area, רוחב תוכן, scroll, חזרה ו־global quick-create באותו pattern |
| Global navigation | מספר מצומצם של workspaces ראשיים; More/contextual access נשארים אפשריים ולא נקבעים כאן |
| Page header | title, subtitle של “מה אפשר לעשות כאן”, back/context ו־primary action אחת |
| Actions | primary/secondary/rare actions עם naming, מיקום ו־disabled states אחידים |
| KPI / summary strip | מעט מדדים שמובילים להחלטה, עם drill-down ברור ולא dashboard עמוס |
| Content patterns | Cards, lists, boards, timelines, search, filters, tabs ו־saved views לפי הצורך העסקי |
| Status | Badge עם label וטקסט; צבע אינו האות היחיד |
| State patterns | loading, empty, error, stale, saved, retry ו־permission states עם copy עברי עקבי |
| Detail | drawer או page לפי עומק, עם header, summary, next action, timeline/related ו־More |
| Action lifecycle | intent/preview → confirmation אם נדרש → execution → receipt/result/error |
| Mobile | spacing, target size, sticky action bar, keyboard/focus ו־dynamic viewport מוגדרים מראש |
| Visual tokens | typography, spacing, radius, shadows/elevation, colors, icons ו־density נשלטים מטוקנים משותפים |
| BOSS layer | BossBar רוחבי אופציונלי; Check-in/Game אינם חייבים להיות destinations ראשיים |
| Quick create | pattern גלובלי ליצירת Lead, Task, Marketing Demand, brief או record רלוונטי |

הכלל: Ventures יכול להיות board/lifecycle, Finance יכול להיות KPI + ledger, Marketing יכול להיות workflow, Leads יכול להיות list/pipeline/detail ו־Actions יכול להיות work queue. כולם צריכים לחלוק את אותה שפת BOSS.

## 5. מפת confidence נוכחית

| תחום | ביטחון נוכחי | עמדה באודיט הזה |
|---|---|---|
| Owner Control / Command Center | חזק | CORE SCREEN candidate; קורא: מה דורש את תשומת הלב של הבעלים עכשיו? |
| Ventures | חזק | CORE SCREEN candidate; להרחיב כ־upstream business-development workspace |
| Marketing / Media | חזק | CORE SCREEN candidate; להוסיף כיוון מוצרי משמעותי |
| Finance | חזק | CORE SCREEN candidate עצמאי |
| Leads / CRM | חזק | CORE DOMAIN — REDESIGN REQUIRED |
| Actions / My Work | דרישה חזקה | surface פתוח: screen, `+`, queue, hybrid או שילוב |
| Operations | סביר | core workspace אפשרי; גבולות פתוחים |
| Approvals | capability קיים, surface לא | demote from primary assumption; state בתוך lifecycle |
| Activity / Business Memory | capability קיים, surface לא | contextualize/demote; verify source and use |
| Digest | חפיפה נצפית | candidate לשילוב ב־Command Center, לא יעד סופי |
| Emergency Stop | capability בטיחותי | system/action surface עם prominence; לא primary screen |
| Lead Detail / Project Detail | detail patterns | contextual layer, לא destinations נפרדים כברירת מחדל |
| Media Files | asset layer | embed בתוך Marketing; raw collection אינה primary assumption |
| System Health | system/admin | More/System/Command Center context; לא primary assumption |
| Game / Check-in | BOSS layer | drill-down או drawer עד שיוכח אחרת |

## 6. Screen Qualification Matrix

הטבלה היא qualification של המצב והכיוונים, לא החלטת ניווט סופית.

| מסך קיים | שאלה עסקית | נתונים/ישויות | פעולות עיקריות | ערך שימוש | כפילות | סוג | בעיות UX | סיווג | ביטחון | שאלות פתוחות |
|---|---|---|---|---|---|---|---|---|---|---|
| Projects Hub | מה מצב הפרויקטים עכשיו? | ProjectsHub, KPI, חריגים, Leads | פתיחת פרויקט/ליד, drill-down | גבוה | OCC/Digest/Operations | Dashboard / Workspace | header צפוף, שאלות רבות | `REDESIGN` | בינוני | מה נשאר כ־summary ומה עובר ל־Operations? |
| Owner Control | מה דורש מהבעלים החלטה? | health, approvals, ventures summary, alerts | פתיחת החלטה, Ventures, approvals | גבוה | Hub/Digest/System | Dashboard / Command Center | יותר מדי תפקידים במסך אחד | `EXPAND` | גבוה | אילו widgets באמת תומכים בהחלטה? |
| BossDigest | מה השתנה ומה לעשות היום? | health, approvals, daily digest | review, follow-up, approval | בינוני-גבוה | Command Center | Dashboard / Contextual Layer | duplicate destination | `EMBED / CONTEXTUALIZE` | בינוני | האם summary יומי נפרד עדיין משרת צורך? |
| Ventures | האם ההזדמנות בשלה? | Ventures, participants, docs, assumptions, risks | create, evaluate, due diligence, next decision, convert | גבוה | Strategic summary ב־OCC; לא CRM | Workspace / Board / Detail | lifecycle עדיין לא מלא בממשק | `EXPAND` | גבוה | מהו readiness gate ומהי המרה מאושרת? |
| Lead Pipeline | איזה Lead דורש פעולה? | Leads, stage, score, next action | search, filter, stage update, open detail | גבוה | Lead Detail ו־Activity | Entity Collection / Workspace | מעבר קשיח לעומק | `REDESIGN` | גבוה | Contacts/Deals tabs או entities נפרדים? |
| Lead Detail | מה ידוע ומה הצעד הבא? | Lead, timeline, outcomes, tasks | update, next action, task, follow-up | גבוה | Pipeline/Activity | Record Detail | action overload | `EMBED / CONTEXTUALIZE` | גבוה | אילו פעולות primary ואילו More? |
| Personal Mode | מה יש לי אישית לבצע/להחזיק? | Units, assets, personal fields | view/update assets | בינוני | Operations/My Work | Workspace / Collection | מנותק מהקשר עסקי, schema drift risk | `MERGE CANDIDATE` | בינוני | האם “My Work” הוא task view או domain? |
| Finance Pulse | האם הכסף בשליטה? | payments, expenses, income, balances | review, filter, open record | גבוה | מעטה; שונה מ־CRM | Workspace / Dashboard | צריך היררכיית KPI + ledger עקבית | `KEEP` | גבוה | אילו פעולות הן review ואילו write? |
| Activity Feed | מה קרה בקשרים ובעסק? | מקור לאומת במלואו; Activity/Interaction/Memory אפשריים | filter, open context | בינוני | Lead/Project timelines, Digest | Contextual Layer / Collection | feed פסיבי וחסר הקשר | `OPEN / NEEDS MORE OBSERVATION` | נמוך-בינוני | מה המקור המדויק ומהו ה־global use case? |
| Approvals | מה ממתין להחלטה? | approval projection, lifecycle state, risk/context | preview, approve, reject, receipt | גבוה אך תדירות נמוכה | Command Center/Actions | Action Surface / System | מבודד; receipt והשלכה עסקית לא מספיקים | `DEMOTE FROM PRIMARY NAV` | גבוה | queue אחת או surfaces contextual? |
| System Health | האם המערכת תקינה? | health, permissions, service states | inspect, retry, admin action | נקודתי | Owner Control | System/Admin | לא business workspace יומי | `DEMOTE FROM PRIMARY NAV` | בינוני-גבוה | מה owner צריך לראות מול admin בלבד? |
| Boss Check-in | מה אני מסמן/מעדכן היום? | daily tasks, status, streak | update, save, continue | בינוני-גבוה | Digest/BossBar/Game | Action Surface / Contextual Layer | עריכה עמוקה מדי ל־quick action; save state | `EMBED / CONTEXTUALIZE` | בינוני | drawer, My Work או Today? |
| Game Screen | איך ה־BOSS engagement מתקדם? | worlds, quests, coins, progress | view progress, quest, drill-down | משלים | BossBar/Check-in | Contextual Layer | יעד ניווט נוסף, לא business question | `DEMOTE FROM PRIMARY NAV` | בינוני | מה הערך התפעולי ומה ניתן להסתיר? |
| Marketing / Media (מועמד חדש) | מה מייצרים, מפרסמים ומה התוצאה? | Marketing Demand, Creatives, Publications, Media Files, Traffic Sources | demand, creative brief, attach/select/approve asset, prepare publication, view results | גבוה | חלקית Leads/Operations; lifecycle שונה | Workspace / Workflow | אינו קיים כמסך מלא כיום | `EXPAND` | גבוה | בעלות על publication/result והאם approval נדרש בכל asset? |

## 7. Marketing / Media — תיקון והרחבה

זהו מועמד CORE חזק שחסר באודיט הקודם. הוא אינו “עוד Leads” ואינו רק אוסף קבצים. מחזור החיים העסקי המוצע לבדיקה הוא:

`Demand → Creative Options → Selected Creative → Media Assets → Publication → Results / Next Action`

ה־Marketing workspace צריך לאפשר לענות על שש שאלות:

1. מה אנחנו מנסים לשווק?
2. איזה כיוון יצירתי נבחר ולמה?
3. אילו assets קיימים ומה עדיין חסר?
4. היכן פורסם ובאיזה סטטוס?
5. מה קרה אחרי הפרסום — תוצאה, מקור תנועה, CPL/המרה אם קיים?
6. מהו ה־next action?

פעולות מועמדות: create Marketing Demand; request/generate creative ideas; create media prompt/brief; attach/upload asset; select creative; approve asset כשנדרש; prepare publication; view publication status/results.

`Media Files` הוא בדרך כלל asset layer בתוך Marketing ולא מסך top-level עצמאי. עדיין צריך להציג אותו במפורש דרך asset picker, סטטוס production, preview, metadata ו־publication links. אין לממש את הזרימה בשלב הזה.

## 8. Ventures — תיקון

אין למזג Ventures אוטומטית ל־Leads/Pipeline. העסק עשוי להתחיל ב־opportunity או idea לפני שקיים Lead.

המרחב צריך לחקור lifecycle של:

`Opportunity / Idea → Discovery → Information Gathering → Business Feasibility → Financial Examination → Commercial Negotiation → Legal/Business Closure → Readiness → Project / Marketing Activation → First Leads → CRM / Operations`

המסך צריך לתת מקום ל־discovery, business case, documents, participants, financial assumptions, risks, next decision, due diligence, negotiation status, legal/commercial status ו־readiness gates. המרה ל־Project, Marketing Demand או execution היא transition שצריך להיות מפורש ומאומת, לא shortcut שמוחק את ההבחנה בין Venture ל־CRM.

## 9. Command Center ו־Actions / My Work

### Command Center — Read / Understand / Decide

השאלה: **מה דורש את תשומת הלב של הבעלים עכשיו?**

מועמדים לתוכן: exceptions חשובים, critical next actions, overdue items, business alerts, selected KPIs, pending decisions, cross-business summary והמלצות BOSS. Digest עשוי להשתלב כאן, אך exact widgets עדיין פתוחים. Command Center אינו צריך לשכפל את כל העבודה בכל workspace.

### Actions / My Work — Create / Execute / Continue

זו דרישה פונקציונלית חזקה: create lead/task/record, create Marketing Demand, request media prompt/brief, search lead/task/contact, continue unfinished actions, rare approvals ו־Emergency Stop בולט ובטוח.

המשטח הסופי פתוח בין:

- primary Actions screen;
- global `+` opening an Action Center;
- My Work queue plus global quick-create;
- hybrid.

אין לקבע את הבחירה לפני בדיקת תדירות, זמני השלמה, mobile discoverability ו־transition בין Create ל־Continue. Emergency Stop יכול לחיות בתוך Actions/System Actions, ללא מסך ראשי עצמאי.

## 10. Leads / CRM — פישוט ללא מחיקה

Leads נשאר CORE DOMAIN, אך דורש redesign. המודל הפשוט לבדיקה:

`Lead collection / list / pipeline → Lead detail → Next Action → Timeline / related information`

לא ליצור destinations ראשיים נפרדים לכל מידע ששייך ל־Lead detail. Pipeline ו־Detail צריכים להרגיש כמו master-detail אחד. Contacts ו־Deals נשארים שאלה פתוחה: tabs, views או entities נפרדים. לא להסיק זאת רק ממספר המסכים.

## 11. Approvals / Activity — demotion analysis

### Approvals

Approval הוא בעיקר **state בתוך lifecycle של action**, לא בהכרח עולם ניווט. היכולת נשארת: preview, risk/context, approve/reject, execution status ו־receipt. המיקומים העתידיים האפשריים הם Actions/My Work, contextual approval, Command Center notification או System/Admin detail. תדירות נמוכה לבדה אינה סיבה למחוק את היכולת.

### Activity / Business Memory

השם Activity מטעה עד שלא יאומת מהו המקור בפועל. יש לבדוק האם הוא מציג Business Memory, Interaction Log, receipts או נתונים מעורבים; אילו פריטים צריכים להופיע ב־entity timelines; ומה שייך ל־Knowledge/Memory בעתיד. הכיוון החזק כרגע הוא `Activity as context/timeline/memory layer`, לא primary destination אוטומטי. הסיווג נשאר open עד verification של מקור הנתונים והשימוש.

## 12. Operations — נשאר תחת evaluation

Operations הוא מועמד workspace סביר עבור Projects, execution state, operational tasks ו־assets. יש להבחין בינו לבין:

- Ventures — מה בודקים ומבשילים לפני execution;
- Actions/My Work — מה אני אישית צריך לבצע עכשיו;
- Leads — מה קורה ב־CRM;
- Projects Hub — summary מול execution detail;
- Personal/Assets — הקשר של נכס מול עבודה תפעולית.

הכלל לבדיקה: `Operations = what is being executed in the business`; `My Work = what I personally need to do`. אין למזג אותם לפני mapping של capabilities ו־transitions.

## 13. שאלות ארכיטקטורה פתוחות

- אילו workspaces יגיעו ל־primary navigation, ומה יעבור ל־More, context או `+`?
- האם Actions הוא screen, Action Center, My Work או hybrid?
- האם Command Center ו־Digest חולקים summary יחיד או שני מצבי קריאה?
- מהי סמכות המקור של Activity, ומהו הגבול בין Memory, Interaction ו־timeline?
- מהו boundary מוסכם בין Ventures, Projects, Marketing activation ו־Operations?
- האם Contacts ו־Deals הם tabs, views או entities נפרדים בתוך CRM?
- אילו approvals מצריכים אישור בכל שלב, ואילו רק state/receipt?
- מתי Media Files מוצגים asset layer ומתי יש צורך ב־asset management עמוק יותר?
- אילו widgets ב־Command Center באמת מובילים להחלטה ולא רק מוסיפים מידע?
- אילו מסכים דורשים page מלא, drawer או side panel במובייל?
- אילו token values ו־content rules יוגדרו ב־BOSS Design System?

## 14. סדר עבודה מומלץ — ללא destructive IA changes

### Phase 1 — Unified Screen / Design System

להגדיר את חוזה BOSS המשותף: shell, navigation primitives, header, actions, KPI, cards, lists, boards, timelines, search, filters, tabs, badges, states, detail, action lifecycle, mobile tokens ו־quick-create. לא למחוק או למזג מסכים.

### Phase 2 — Screen Qualification

להריץ את המטריצה על כל מסך קיים, לאמת source/entities/actions, לתעד תדירות ושימוש, ולסמן confidence/open questions.

### Phase 3 — Prototype strong core screens

לבנות prototypes בלבד ל־Command Center, Ventures, Marketing/Media, Finance ו־Leads/CRM באמצעות אותה מערכת מסכים. Actions/My Work ו־Operations נבחנים כזרימות, בלי לנעול surface.

### Phase 4 — Validate overlaps

לבדוק transitions אמיתיים וחפיפות: Venture→Project/Marketing, Lead→Next Action, Command Center→Action, Activity→entity timeline, Operations↔My Work ו־Media→Publication/Results.

### Phase 5 — Consolidation

רק לאחר שהחלופה מוגדרת, הפונקציונליות ממופה, הניווט החלופי קיים ואין אובדן capability — לסמן מסכים כ־merge, demote או retire. כל שינוי production דורש עבודה נפרדת ואישור.

## 15. Design reference tooling

`UIDrop` / design-system extraction יכול לשמש כלי תומך בשלב ה־Design System: inspect SaaS references, לחלץ tokens/patterns ולהשוות density, hierarchy ו־interaction conventions. אין להשתמש בו להעתקה עיוורת. התוצר צריך להיות BOSS-owned design system עם החלטות מקומיות, לא אוסף סגנונות מועתקים.

## 16. Change report

### נוספו או עודכנו

- סטטוס מפורש: `WIP DESIGN EVIDENCE / SCREEN ARCHITECTURE EXPLORATION`.
- Current-state audit ו־Verified UX Problems.
- Unified Screen System / Screen Contract לפני consolidation.
- Current decision-confidence map.
- Screen Qualification Matrix לכל מסך קיים ולמועמד Marketing/Media.
- Marketing / Media כמועמד CORE משמעותי, עם lifecycle ופעולות מועמדות.
- Ventures כמועמד CORE upstream, ללא מיזוג אוטומטי ל־Leads.
- Actions / My Work כהכרח פונקציונלי עם surface פתוח.
- Leads כ־CORE DOMAIN עם redesign, לא מחיקה.
- Approvals ו־Activity כיכולות שימור עם demotion/contextualization שנשארים לבדיקה.
- Operations תחת evaluation והפרדה בין business execution ל־personal work.
- שאלות ארכיטקטורה פתוחות וסדר חמשת השלבים.
- UIDrop ככלי עזר אפשרי בלבד.

### תוקן או הורד בדרגת ודאות

- מפת “5 אזורי ניווט” הוחלפה ב־navigation questions פתוחות.
- “Ventures בתוך Pipeline” הוחלף ב־Ventures עצמאי/מורחב כמועמד CORE.
- “Marketing/Media כחלק משני” הוחלף במועמד CORE.
- “Approvals כמסך” הוחלף ב־approval state בתוך action lifecycle.
- “Activity כ־primary destination” הוחלף ב־context/timeline/memory candidate.
- המלצות merge/retire הוגדרו כמועמדים בלבד, בכפוף ל־qualification ו־validation.

### גבולות השינוי

- לא שונו screenshots; לא נדרשו צילומים נוספים כדי לתמוך בממצאי התיקון.
- לא שונה production code, runtime behavior, API, routing, Airtable schema או business logic.
- אין במסמך טענה לארכיטקטורת מסכים סופית.
- PR #600 לא מוזג; התוצר נשאר Draft/WIP.

## קבצי ראיות

כל צילומי המסך נשמרו תחת `reports/tma-audit/` ונלכדו באודיט זה. הם משמשים ראיות ל־current-state בלבד, לא למסך יעד סופי.
