# BOSS Unified Screen Contract

**Status:** `DESIGN / UX ARCHITECTURE GATE — WIP`
**Scope:** תיעוד, design architecture ו־UX בלבד.
**Branch:** `docs/tma-screen-audit`
**Related:** PR #600, `reports/tma-audit/TMA_UX_AUDIT_HE.md`

> מטרת המסמך היא להגדיר מערכת מסכים אחידה לפני איחוד, מחיקה או בנייה מחדש של מסכי production. זה אינו target navigation סופי ואינו מאשר implementation.

## 1. Screen principles

### ONE BOSS SCREEN SYSTEM

Ventures, Finance, Marketing, Leads, Actions ו־Owner Control יכולים להשתמש במבני מידע שונים, אך חייבים לחלוק שפה אחת של:

- hierarchy ו־Page Header;
- primary/secondary actions;
- cards, lists, boards, timelines ו־work queues;
- search, filters, tabs ו־saved views כשנדרש;
- status, loading, empty, error ו־receipt states;
- RTL, mobile spacing, typography, radius, elevation ו־icon rules.

המערכת מאחדת את ה־language וההתנהגות לפני שהיא מצמצמת את מספר המסכים. כל החלטה על merge/retire נשארת פתוחה עד Screen Qualification, prototype ו־overlap validation.

### עקרונות מחייבים

1. כל מסך מתחיל בשאלה עסקית אחת וב־next action ברור.
2. כרטיס/section אחד מייצג החלטה או פעולה אחת, לא אוסף KPI ופקדים ללא היררכיה.
3. פעולה משמעותית עוברת דרך `Initiate → Preview/Validation → Execute/Approve → Result → Receipt/Error`.
4. Detail הוא הקשר של רשומה, לא destination ראשי לכל סוג מידע.
5. צבע ו־emoji אינם יכולים להיות האות היחיד לסטטוס או פעולה.
6. אין לחשוף internal IDs, tool names או payloads למשתמש.
7. כל מסך חדש חייב לתעד את ה־components וה־patterns שהוא משתמש בהם.

## 2. Canonical screen anatomy

### AppShell

מכיל top-level container, `dir="rtl"`, Telegram safe-area, responsive/mobile-first behavior, scroll ownership, background/surface hierarchy ו־global action entry point. ה־Shell אינו מחליט כמה destinations קיימים.

### Page Header

כולל title, optional subtitle/context, back behavior, primary action אחת ו־secondary actions מוגבלות. כותרת אינה מקום ל־10 קיצורי דרך אייקוניים.

### Summary Area

אזור קצר של KPI, alerts, blockers, status או next-action summary. כל metric חייב להוביל ל־drill-down או להחלטה; metrics ללא שימוש מוכח נשארים candidate.

### Main Work Area

המערכת תומכת ב־patterns הבאים, לפי סוג העבודה:

| Pattern | מתאים ל־ | דרישת contract |
|---|---|---|
| List / Collection | Leads, assets, records | search/filter, row hierarchy, empty/error |
| Board / Lifecycle | Ventures, Marketing stages | stage semantics, transitions, counts, detail |
| Timeline | entity context, memory, interactions | source, timestamp, related entity, next action |
| Dashboard | Command Center, Finance | limited KPIs, alerts, drill-down |
| Work Queue | Actions/My Work, contextual approvals | priority, owner, status, continue/complete |

### Detail Surface

Detail נפתח כ־full page, drawer, sheet או inline expansion לפי עומק, mobile constraints ו־back-stack. המבנה הקנוני:

1. status ו־identity;
2. key facts;
3. next action;
4. timeline/history;
5. related entities;
6. action controls ו־More.

אין לשכפל את אותה רשומה ב־Lead Detail, Activity, Dashboard ו־Action screen בלי להגדיר מהו source ומהו context.

## 3. Component inventory

| Component | תפקיד | Variants מינימליים | מצב נוכחי ב־frontend | החלטת Gate |
|---|---|---|---|---|
| `AppShell` | shell, RTL, safe-area | loading/content/error | אין רכיב משותף; App.tsx משכפל wrapper | לשמור כ־future canonical component |
| `PageHeader` | title/back/actions | title-only, detail, workspace | כל view מגדיר header inline | לאחד pattern לפני מסכים חדשים |
| `Section` | grouping והיררכיה | title, action, collapsible | קיים inline ב־Owner Control ובמסכים נוספים | לשמר semantics ולהוציא ל־shared |
| `Card` | surface להחלטה אחת | clickable, static, danger | `ProjectCard`, `LeadCard` ו־cards inline | למפות variants, לא ליצור עוד card style |
| `KPICard` | metric עם meaning | compact, dashboard | `GlobalKpis` כולל `KpiPill` מקומי | לשמר concept, להגדיר token/label contract |
| `StatusBadge` | status non-color-only | lifecycle, risk, system | מימושים מקומיים ב־Lead/Ventures/Approvals | לאחד vocabulary ו־accessibility |
| `Alert` | exception/blocker | info, warning, danger | divs עם צבעים שונים | לשמר semantic states, להוציא shared |
| `ListItem` | row hierarchy | entity, action, compact | inline ב־Activity/Approvals/Assets | להגדיר row contract |
| `BoardCard` | lifecycle item | venture, demand, project | אין board primitive מוכח | candidate לשלב prototype |
| `TimelineItem` | event/context | memory, interaction, receipt | `ActivityRow` קרוב אך לא canonical | להפריד event source מ־global feed |
| `SearchBar` | retrieval | global, workspace | אין pattern shared ברור | להגדיר לפני הרחבת collections |
| `FilterBar` | narrowing | chips, select, saved view | Ventures משתמש ב־stage chips inline | לשמר chips אך להגדיר common behavior |
| `Tabs` | sibling views | primary, secondary, scrollable | inline tab/chip patterns | לא להשתמש ליצירת navigation סמויה |
| `EmptyState` | no data / no result | first-use, filtered, unavailable | copy inline במסכים | להגדיר action ו־reason variants |
| `LoadingState` | pending | initial, refresh, action | spinners inline בכל view | לאחד spinner/skeleton/copy |
| `ErrorState` | failure/retry | network, permission, stale | banners inline | להגדיר retry ו־safe explanation |
| `Toast` | transient feedback | success, error, info | `Ventures` local toast | לשמר רק למשוב קצר; לא כ־receipt |
| `ActionBar` | primary/secondary actions | sticky, inline, contextual | bottom bars inline ב־Ventures/System | להגדיר focus/order/safe-area |
| `QuickCreate` | global creation | lead, task, demand, record | אין primitive shared | candidate; surface עדיין פתוח |
| `DetailDrawer/Sheet` | contextual detail | sheet, drawer, inline | `ActivityFeed` ו־Ventures local variants | לאחד behavior, לא בהכרח markup |
| `ConfirmationPreview` | intent/impact | low-risk, destructive, approval | Approvals/System use custom blocks | canonical before action execution |
| `ExecutionState` | in-flight/pending | queued, running, blocked | local status handling | shared action lifecycle state |
| `Receipt` | result/evidence | success, partial, failed | אין primitive ברור בכל המסכים | חובה לכל write/approval path |

### Duplicate patterns שנצפו

- header מלא (`bg-white px-4 pt-5 pb-4 mb-3 shadow-sm`) חוזר במסכים רבים;
- loading spinner כחול חוזר inline כמעט בכל view;
- error banner אדום חוזר עם מבנים שונים;
- `bg-white rounded-xl shadow-sm p-4` משמש card, alert, section ו־detail ללא semantic distinction;
- status badges משתמשים ב־מפות צבע מקומיות;
- bottom action bars, sheets ו־toast קיימים בתוך `Ventures`, `ActivityFeed` ו־`SystemHealth` בלי contract משותף;
- App.tsx מחזיק boolean open state נפרד לכל view, ולכן navigation/back behavior אינו primitive אחיד.

### רכיבים שכדאי לשמר

`ProjectCard`, `LeadCard`, `GlobalKpis/KpiPill`, `ActivityRow`, stage/risk mapping helpers, detail sheet pattern ו־action lifecycle concepts. יש לשמר את התוכן העסקי ולחלץ את השפה המשותפת, לא לבצע rewrite גורף.

### מה ידרוש consolidation בעתיד

`AppShell`, `PageHeader`, state components, status vocabulary, card surface, detail surface, action bar, confirmation/receipt ו־navigation state. זהו backlog design/implementation עתידי בלבד.

## 4. Navigation primitives

ה־Contract מגדיר primitives בלבד, לא מספר destinations:

- Primary navigation;
- More menu;
- global `+` / Action Center;
- contextual navigation מתוך workspace/detail;
- back stack;
- tabs ו־saved views;
- detail navigation;
- deep links;
- Command Center links לחריגים/החלטות.

Mobile usability דורשת מעט slots ו־targets גדולים, אך אין לקבע עכשיו “5 tabs” או מספר סופי אחר. הבחירה תבוא לאחר qualification, prototype ו־usage validation.

## 5. Action UX contract

### Canonical flow

`Initiate → Preview/Validation → Execute/Approve if required → Result → Receipt/Error`

### Action classes

| Class | UX rule |
|---|---|
| Quick action | פעולה קצרה עם default בטוח ומשוב inline |
| Contextual action | נפתחת מתוך entity/workspace ושומרת על הקשר |
| Destructive/high-risk | impact ברור, confirmation מפורש, אין destructive default |
| Background action | pending/running state ויכולת continue/inspect |
| Approval action | preview, requester/context/risk, approve/reject, receipt |
| Already pending | לא ליצור duplicate; להציג state קיים ו־next step |
| Emergency Stop | פעולה מערכתית בולטת בתוך Actions/System Actions, לא Design System נפרד ולא primary screen אוטומטי |

אין להציג “saved/success” בלי receipt או state אמין. Toast לבדו אינו תחליף ל־result.

## 6. Design tokens

### Token families

- typography scale, Hebrew line-height ו־font weights;
- spacing scale ו־mobile content padding;
- radius, border ו־surface hierarchy;
- elevation/shadows לפי level, לא לפי component מקרי;
- icon sizing ו־touch target minimum;
- semantic colors: neutral/info/success/warning/danger/pending;
- focus/pressed/disabled/loading states;
- light/dark strategy רק אם נדרש על ידי Telegram/product context.

UIDrop או SaaS references יכולים לשמש extraction/reference בלבד. הערכים הסופיים חייבים להפוך ל־BOSS-owned tokens, לא להעתיק Design System של מוצר חיצוני.

## 7. Detail behavior

- collection → detail שומר על מקור, filters ו־back context;
- drawer/sheet מתאים ל־quick review; full page מתאים לעריכה עמוקה או lifecycle ארוך;
- detail מציג תמיד status, key facts ו־next action לפני מידע משני;
- timeline/related content הוא contextual ולא feed גלובלי כברירת מחדל;
- actions נדירות/מסוכנות עוברות ל־More, אלא אם הן ה־next action;
- close/back/escape/tap-outside behavior חייבים להיות עקביים ונגישים;
- focus, scroll lock ו־safe-area נדרשים ל־sheet/drawer.

## 8. States and feedback

כל screen contract חייב להגדיר:

1. initial loading;
2. refresh/stale;
3. empty first-use;
4. empty filtered/no result;
5. permission/unauthorized;
6. network/server error עם retry;
7. action pending/running;
8. action success עם receipt;
9. partial/unknown result;
10. destructive/error recovery.

Copy צריך לענות על: מה קרה, מה ידוע, מה אפשר לעשות עכשיו. אין להציג stack trace, internal IDs או tool names.

## 9. RTL, mobile and accessibility rules

- `dir="rtl"`, יישור טקסט וכיוון back בהתאם לעברית;
- Telegram safe-area ו־dynamic viewport;
- touch targets גדולים ועקביים, ללא header צפוף;
- visible label לצד icon-only controls, כולל accessible name;
- focus/keyboard order ו־screen reader semantics לכל interactive element;
- contrast נבדק מול token colors; status אינו color-only;
- text יכול להתרחב בלי לשבור card/row או להסתיר primary action;
- horizontal scroll רק עבור tabs/chips עם affordance ברור;
- sticky action bar אינו מכסה content או keyboard;
- loading/error/empty states ניתנים להבנה גם ללא צבע, emoji או motion.

## 10. Examples across workspaces

### OC / Command Center

שאלה: **מה דורש את תשומת לב הבעלים עכשיו?**
Anatomy: Page Header → exceptions/decisions → selected KPIs → approvals/next actions → drill-down.
לא להציג בו את כל המערכת; Digest עשוי להיטמע כאן אך exact widgets פתוחים.

### Ventures

שאלה: **איפה עומדת ההזדמנות ומה החלטת ההמשך?**
Pattern: board/list לפי lifecycle → Venture detail → risks, assumptions, documents, participants, next decision ו־readiness gate.
זהו upstream business-development workspace, לא Leads tab.

### Marketing / Media

שאלה: **איפה עומדים Demand → Creative → Asset → Publication → Result?**
Pattern: lifecycle board/list עם asset layer, creative selection, publication status/results ו־next action. `Media Files` נשאר בדרך כלל contextual asset layer.

### Actions / My Work

שאלה: **מה אפשר/צריך לבצע עכשיו?**
Pattern: work queue + quick-create + continue unfinished actions + contextual approval/emergency controls.
האם זה primary screen, global `+`, Action Center או hybrid — פתוח.

### Leads / CRM

שאלה: **מי דורש טיפול ומה ה־next action?**
Pattern: collection/pipeline → detail → next action → timeline/related.
Contacts ו־Deals placement פתוחים.

### Finance

שאלה: **מה מצב הכסף והחריגים?**
Pattern: KPI summary → ledger/data view → filters/tabs → record detail/action.
Finance נשאר מועמד CORE עצמאי כי השאלה והמידע שונים מ־CRM/Operations.

## 11. Open architecture questions

- האם Actions הוא screen, global Action Center, My Work או hybrid?
- האם Operations הוא primary workspace ומה boundary מול Ventures, Projects ו־My Work?
- כמה primary navigation destinations יהיו, ומה יישב ב־More/context/`+`?
- האם Finance תמיד primary או נגיש לפי role/context?
- האם Contacts/Deals הם tabs, views או entities נפרדים?
- מהו המקור וה־future surface של Business Memory/Activity?
- איפה יושבים Game ו־Check-in ביחס ל־BossBar, Today ו־Actions?
- אילו legacy screens merge/demote/retire רק לאחר replacement mapping?
- אילו token values ו־status vocabulary יאושרו רשמית?

## 12. Migration rules for future screens

כל מסך עתידי חייב לעבור את השער הבא לפני implementation:

1. להגדיר business question, user ו־next action.
2. לסווג Screen Type: workspace, collection, detail, action surface, dashboard, contextual layer או system/admin.
3. לבחור Main Work Area pattern מתוך הרשימה הקנונית.
4. להשתמש ב־AppShell, PageHeader, states, status, detail ו־action contract המשותפים.
5. לתעד data/entities, primary actions, related surfaces ו־open questions.
6. לבדוק duplication מול המסכים הקיימים ומול Screen Qualification Matrix.
7. להכין wireframe/spec בלבד ולבדוק את הזרימה לפני production implementation.
8. אין למחוק/למזג מסך בלי replacement destination, capability mapping, navigation replacement ובדיקת אובדן מידע.
9. אין לקבע navigation count מתוך screen count.
10. כל שינוי production יגיע בשינוי נפרד, עם review, בדיקות ו־verification מתאימים.

## Audit קצר של ה־frontend הקיים

### Files inspected

- `tma-frontend/src/App.tsx`
- `tma-frontend/src/index.css`
- `tma-frontend/src/api.ts`
- `tma-frontend/src/types.ts`
- `tma-frontend/src/components/ActivityFeed.tsx`
- `Approvals.tsx`, `BossCheckin.tsx`, `BossDigest.tsx`, `FinancePulse.tsx`, `GameScreen.tsx`
- `GlobalKpis.tsx`, `LeadCard.tsx`, `LeadDetail.tsx`, `LeadPipeline.tsx`
- `OwnerControlCenter.tsx`, `PersonalMode.tsx`, `ProjectCard.tsx`, `SystemHealth.tsx`, `Ventures.tsx`
- `reports/tma-audit/TMA_UX_AUDIT_HE.md`

### Current reusable building blocks

`GlobalKpis/KpiPill`, `ProjectCard`, `LeadCard`, Activity row/detail sheet, stage/risk color helpers, loading spinners, error banners, empty copy, toast, bottom action bars ו־form/detail structures קיימים כבסיסים שימושיים.

### Duplicated or inconsistent patterns

- Page headers ו־back controls מוגדרים inline כמעט בכל component;
- cards, surfaces ו־shadows משתמשים באותם utility strings עם semantics שונים;
- loading/error/empty states משוכפלים עם copy ו־spacing שונים;
- status colors ו־badge vocabulary מקומיים ל־Lead/Venture/Approval/System;
- sheets, sticky action bars ו־toasts ממומשים מקומית;
- App.tsx מנהל boolean state נפרד לכל view במקום navigation primitives משותפים;
- Hub מציג קיצורי דרך אייקוניים רבים במקום contract של primary/secondary/contextual navigation.

### Proposed keep / consolidate

**Keep as domain content:** project/lead/venture/finance data shapes, business-specific cards, stage/risk semantics לאחר vocabulary review, Activity detail information ו־action lifecycle concepts.
**Consolidate later:** AppShell, PageHeader, Section/Card variants, KPI, StatusBadge, states, ActionBar, DetailSheet, ConfirmationPreview, ExecutionState, Receipt ו־navigation state.
**Do not implement in this Gate:** component extraction, CSS rewrite, routing rewrite, API changes, schema changes, business logic או deletion of screens.

## Gate result

- המסמך מגדיר Contract משותף לפני כל consolidation.
- examples מכסים OC, Ventures, Marketing/Media, Actions, Leads ו־Finance.
- Navigation count, Actions surface, Operations boundary ו־legacy deletion נשארו פתוחים.
- כל שינוי במסמך הזה הוא design/documentation evidence בלבד.
- לא בוצע production behavior/UI rewrite.
