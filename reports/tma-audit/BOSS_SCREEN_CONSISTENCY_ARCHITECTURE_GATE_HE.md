# BOSS Screens — Screen Consistency Architecture Gate

**תאריך:** 12/08/2026  
**סטטוס:** `OWNER APPROVED CONSTITUTION / SCREEN ARCHITECTURE OPEN`  
**היקף:** ארכיטקטורת אחידות למסכים, מיפוי משפחות, חוזים משותפים, שונות מותרת ו־governance.  
**מחוץ להיקף:** בחירת אתרי Reference, Reference research, שימוש ב־JCodesMore, mockups, frontend, refactor ושינוי Design System.

החוזים שאושרו מתועדים ב־[SCOREBOS UX Constitution — Owner Decision Record](./SCOREBOS_UX_CONSTITUTION_OWNER_DECISION_RECORD_HE.md). מסמך זה ממשיך לתעד את מיפוי משפחות המסכים, qualification והחלטות הארכיטקטורה שעדיין פתוחות.

## 1. Current Screen Families

המיפוי מבוסס על ה־screen inventory הקיים ב־`tma-frontend/src/App.tsx` ועל הקומפוננטות הקיימות. הוא מתאר את המצב ואת משפחות ה־UX לבדיקה; הוא אינו מפת ניווט סופית.

| משפחת UX | מסכים/קומפוננטות נצפים | השאלה המרכזית | ביטחון | הערת qualification |
|---|---|---|---|---|
| Command / Attention | Projects Hub, Owner Control Center, BossDigest | מה דורש תשומת לב עכשיו? | גבוה | חפיפה בין summary, חריגים, approvals ו־next actions דורשת פירוק תפקידים. |
| Work / Operations | Projects, tasks ופעולות הקשורות לביצוע | מה צריך ליצור, לבצע או להמשיך? | בינוני | גבולות מול Actions/My Work, Ventures ו־Personal עדיין פתוחים. |
| Leads / CRM | Lead Pipeline, Lead Detail | איזה lead ומה הצעד הבא? | גבוה | CORE DOMAIN; Pipeline ו־Detail צריכים להרגיש כ־master-detail אחד. |
| Ventures / Business Development | Ventures overview, Venture detail, create/edit flow | האם opportunity/idea בשלה להתקדמות? | גבוה | מחזור upstream; אין להניח שהוא וריאציה של CRM. |
| Marketing / Media | מועמד עסקי עתידי: demand, creative, assets, publication, results | מה מייצרים, מפרסמים ומה התוצאה? | גבוה | מועמד CORE SCREEN חזק; אינו מסך מלא במצב הנוכחי. |
| Finance | Finance Pulse | האם הכסף בשליטה ומה דורש review? | גבוה | CORE SCREEN candidate; KPI + ledger דורשים היררכיה ייעודית בתוך אותו contract. |
| Action / Approval | Approvals, פעולות עסקיות, receipts | מה עומד לשינוי והאם בטוח לבצע? | גבוה | capability ליבה; surface סופי יכול להיות contextual או בתוך My Work. |
| Activity / Memory | Activity Feed, timelines, related history | מה קרה ומה ההקשר? | בינוני-נמוך | יש לאמת אם המקור הוא interaction log, business memory, receipts או שילוב. |
| Personal / Assets | Personal Mode, Assets detail | מה שייך לי אישית ומה אני מחזיק? | בינוני | כפילות אפשרית מול My Work ו־Operations; לא למחוק לפני qualification. |
| System / Safety | System Health, Emergency Stop | האם המערכת תקינה ומהו מצב הבטיחות? | בינוני-גבוה | system/action surface; לא business workspace יומי כברירת מחדל. |
| Engagement / Daily ritual | Check-in, Game | מה אני מעדכן או משלים היום? | בינוני | שונות פונקציונלית מותרת; destination ראשי עדיין לא מוצדק. |

### Qualification rule

כל מסך עתידי יעבור qualification לפי: משתמש/בעלות, שאלה עסקית, ישויות, פעולות, תדירות, זמן־להשלמה, עומק workflow, כפילות, mobile discoverability, סיכון פעולה והאם הוא workspace או contextual surface. רק לאחר מכן אפשר להציע איחוד, קידום, הורדה או מחיקה.

## 2. What Must Be Globally Uniform

אלה הם `Global Product Contracts`. מסך אינו רשאי להמציא להם גרסה מקומית ללא שינוי מאושר ב־BOSS Screen Constitution.

### Application shell

- RTL, safe-area, page frame, רוחב תוכן, scroll והתנהגות חזרה.
- Sidebar/top navigation במבנה עקבי; מספר ה־workspaces הראשיים נשאר החלטה פתוחה.
- מקום עקבי ל־context, secondary panel, breadcrumbs אם יאושרו ו־global quick action.
- Mobile navigation, bottom actions, drawers ו־context switching באותה לוגיקה.

### Layout, visual hierarchy and density

- grid, spacing, padding, margins, content widths, breakpoints ו־density levels.
- היררכיית `page title → section title → body → metadata → KPI`.
- רקע, cards, elevated surfaces, borders, elevation, selected/active ו־disabled states.
- שימוש עקבי בטוקנים הקיימים; מסמך זה אינו משנה אותם.

### Actions and states

- primary, secondary, contextual, destructive, overflow ו־icon actions עם naming ומיקום עקביים.
- lifecycle משותף: `intent/inspect → preview → confirmation when required → execute → receipt/result → error/retry`.
- status semantics אחידים עבור pending, warning, blocked, approved, completed, failed, saved ו־stale.
- צבע אינו אות יחיד; badge צריך label וטקסט/אייקון נגישים.

### Entity and collection patterns

- Lead, Contact, Deal, Task, Project, Venture ו־Action צריכים Entity Header/logic משותפים ככל שהישות תומכת בכך.
- Search/filter/sort, lists, cards, tables, boards, saved views ו־pagination צריכים primitives ומילים עקביים.
- Timeline/activity ו־related context משתמשים באותו interaction model בכל מקום שבו המשמעות זהה.
- Empty, loading, error, permission, retry ו־success states מקבלים conventions משותפים.

### AI and action safety

- AI summary, suggestion, detected issue, recommended next action, generated content, context indication ו־AI status מופיעים באותה שפה.
- AI אינו עוקף preview, confirmation או approval כשנדרש; המשתמש מבין מה הוצע, מה יקרה ומה כבר קרה.
- אין חשיפה של internal IDs, contract IDs, tool names או payloads למשתמש.

## 3. What May Vary

שונות מוצדקת כאשר היא נובעת מהשאלה העסקית ומה־workflow, לא מ־Reference חיצוני.

- **Command Center:** attention/decision oriented; summary, exceptions ו־next actions.
- **Ventures:** lifecycle/board עם discovery, due diligence, assumptions, risks ו־readiness gates.
- **Marketing / Media:** workflow של demand → creative → asset → publication → results.
- **Finance:** KPI + ledger/review, עם density ו־filters המתאימים לנתונים כספיים.
- **Leads / CRM:** collection/pipeline → entity detail → next action → timeline/related.
- **Operations / My Work:** queue או continuation surface אם יוכח שזה צורך נפרד מה־domain screens.
- **Approvals:** action-centric עם emphasis על שינוי, סיבה, סיכון, השפעה ו־receipt.
- **Activity / Business Memory:** feed/timeline/knowledge navigation רק אם source ו־use case מובחנים.
- **Check-in / Game:** ritual או engagement; יכולים להיות drawer, contextual layer או flow ייעודי.

בכל המקרים האלה typography, button language, status semantics, spacing, navigation logic, AI language ו־shared primitives נשארים משותפים.

## 4. Forbidden / Controlled / Screen-Specific Variation Matrix

| תחום | Forbidden variation | Controlled variation | Screen-specific variation | תנאי לאישור |
|---|---|---|---|---|
| Shell/navigation | מסך ממציא shell או back behavior | drawer, secondary nav, contextual entry | board/detail navigation | שומר על orientation ומונע destination כפול. |
| Typography/tokens | font scale, צבע semantic או spacing מקומי | density לפי dataset | chart/ledger density | חוזר לטוקנים ולנגישות המערכת. |
| Actions | ניסוח/מיקום אחר לאותה פעולה | primary action נוסף לפי workflow | stage transition, publish או venture gate | primary אחד ברור; destructive ו־approval מובחנים. |
| Status | אותו צבע עם משמעות אחרת | סטטוסים נוספים בתחום | venture readiness או publication state | mapping מפורש ל־status vocabulary. |
| Collections | implementation כפולה לאותו pattern | table/list/board לפי task | Kanban pipeline או ledger | אותה search/filter/sort ושפה. |
| Detail/context | detail עצמאי לכל שדה | page מול drawer לפי עומק | risk panel או due-diligence workspace | entity header, next action ו־related נשמרים. |
| AI | “AI mode” אחר לכל מסך | מיקום summary/suggestion לפי context | generated creative או finance explanation | מקור, confidence/action boundary וה confirmation ברורים. |
| Mobile | overflow, target או focus לא עקביים | sticky actions, collapsible sections | multi-pane inbox/board adaptation | task נשאר אפשרי ב־viewport קטן. |
| Safety/approval | bypass, hidden execution או internal IDs | prominence לפי risk | emergency stop surface | נשען על חוזי המערכת ולא lifecycle חלופי. |

## 5. Recommended Shared Primitives

המלצה ראשונית בלבד; יש לאמת כל primitive מול הקיים לפני יצירת גרסה חדשה.

1. `AppShell` / mobile navigation
2. `PageHeader` עם title, context ו־primary action
3. `EntityHeader` ו־`RelatedContext`
4. `SectionHeader`
5. `KpiSummary` / decision-oriented metric card
6. `RecordCard`, `RecordList` ו־`DataTable`
7. `Board` / stage column pattern
8. `SearchFilterBar` ו־saved view controls
9. `StatusBadge` / `ProgressState`
10. `Timeline` / `ActivityItem`
11. `ActionCard` ו־`ApprovalCard`
12. `PreviewConfirmation` / action safety panel
13. `ReceiptResult` / success, failure, retry
14. `ContextPanel` / `Drawer` / `Modal`
15. `EmptyState`, `LoadingState`, `ErrorState`, `PermissionState`
16. `AiSummary`, `AiSuggestion`, `AiGeneratedContent` עם confirmation boundary
17. `QuickAction` / global create and continue entry
18. `Toast`/inline feedback עם saved/unsaved distinction

כל primitive חדש חייב לתעד: use case, reused alternatives שנבדקו, states, responsive behavior, accessibility contract ו־deviation rationale.

## 6. 80/20 Verdict

**Verdict: `ADJUST RATIO`**

80/20 הוא heuristics טוב לכיוון, אך אינו כלל הנדסי חד מספיק ל־BOSS. היחס המתאים יותר לתכנון הוא:

> **Core contracts are 100% uniform; composition is approximately 70–80% shared; 20–30% may vary by workflow.**

כלומר, ה־Shell, tokens, semantics, states, action safety, AI language ו־responsive behavior חייבים להיות אחידים. השונות מותרת בעיקר בהרכב: board ל־Ventures, ledger ל־Finance, pipeline ל־Leads, attention summary ל־Command Center ו־workflow ל־Marketing. אין לספור pixels; בודקים אם המשתמש מזהה את אותו BOSS ואת אותה לוגיקת פעולה.

## 7. Draft BOSS Screen Constitution

### Global Invariants

- כל מסך משתמש ב־BOSS shell, RTL, hierarchy, tokens ו־state vocabulary.
- כל פעולה מציגה intent, מצב, תוצאה ושגיאה באופן ברור.
- entity context ו־next action נגישים בלי לחפש מחדש מידע שכבר ידוע למערכת.
- AI הוא שכבה עקבית של עזרה/הצעה, לא מערכת UX נפרדת.

### Shared Components

ה־primitives בסעיף 5 הם catalog מועמד. אין להוסיף component רק כדי למסך על חוסר החלטה ארכיטקטונית.

### Interaction Contracts

- inspect לפני execute; preview לפני שינוי משמעותי; confirmation ו־approval לפי risk.
- לאחר פעולה מוצגים receipt/result, updated state ו־next step.
- back, close, cancel, retry ו־unsaved changes מתנהגים באופן עקבי.

### Responsive Contracts

- mobile הוא workflow מלא, לא גרסת desktop מצומצמת.
- touch targets, sticky primary action, focus, keyboard/dynamic viewport ו־safe-area מוגדרים לכל pattern.
- tables, boards, drawers ו־dense information מקבלים adaptation מתועד, לא overflow מקרי.

### AI UX Contracts

- כל הצעה מסומנת כהצעה, עם הקשר מספיק וגבול פעולה ברור.
- generated content ניתן לבדיקה/עריכה לפני פרסום או כתיבה.
- אין חשיפה של IDs, tool names או פרטי payload פנימיים.

### Action / Approval Contracts

כל פעולה עסקית נשענת על lifecycle קיים: inspect, approve/reject/cancel/edit/execute, completed/failed. המסך מציג את החוזה; הוא לא יוצר lifecycle ויזואלי חלופי.

### Allowed Variation

Variation מותרת רק אם היא נרשמה כ־controlled או screen-specific, קשורה ל־workflow, נשענת על primitives קיימים, ומסבירה למה אחידות מלאה פוגעת במשימה.

### New Pattern Rule

`Reuse existing pattern first.` רק צורך UX אמיתי שלא נפתר על ידי primitive קיים מאפשר הצעת pattern חדש. ההצעה מחייבת owner/design review ותיעוד של alternative שנדחה.

## 8. Screen Consistency Gate

לפני Reference, mockup או implementation של מסך חדש:

1. האם המסך עבר Screen Qualification?
2. מה השאלה העסקית וה־workflow הייחודי שלו?
3. האם נעשה reuse ל־BOSS primitives?
4. האם ה־Shell וה־navigation logic נשמרו?
5. האם status semantics, actions ו־state patterns נשמרו?
6. האם AI interaction תואם ל־contract?
7. האם mobile/tablet/desktop behavior מתועד?
8. אילו deviations קיימים ומה ההצדקה לכל אחד?
9. האם נוצר pattern חדש; אם כן, למה הקיים לא מספיק?
10. האם יש כפילות עם workspace, detail או contextual surface קיימים?
11. האם יש השפעה על approval/action safety או חשיפת מידע פנימי?
12. מי ה־owner שמאשר את ההחלטות הפתוחות?

## 9. Open Decisions Requiring Owner Approval

| החלטה | אפשרויות לבדיקה | confidence | מה חסר לפני הכרעה |
|---|---|---|---|
| יחס אחידות | ACCEPT 80/20 או adjusted contract/composition model | גבוה | אישור שההבחנה בין contracts להרכב מקובלת. |
| Primary workspaces | לא נקבע בשלב זה; qualification לפני navigation map | נמוך-בינוני | תדירות, jobs-to-be-done, mobile usage וחפיפות. |
| Command Center scope | attention summary בלבד מול summary + digest/health | בינוני | רשימת decisions/widgets ו־owner job. |
| Actions / My Work surface | screen, global `+`, queue או hybrid | בינוני | תדירות create/continue/approve וזמני השלמה. |
| Operations boundaries | workspace נפרד או חיבור ל־Projects/My Work/Ventures | בינוני | entity ownership ו־workflow transitions. |
| Ventures lifecycle | stages, readiness gates והמרות ל־Project/Marketing/CRM | בינוני-גבוה | business owner ו־transition rules. |
| Marketing / Media scope | demand→creative→asset→publication→results | בינוני-גבוה | publication ownership, asset approval ו־result metrics. |
| Activity / Memory meaning | interaction log, business memory, receipts או שילוב | נמוך-בינוני | source-of-truth ו־global use case. |
| Contacts / Deals | tabs, views או entities/workspaces נפרדים | בינוני | שימוש בפועל ויחסי entity. |
| Approvals placement | contextual, Actions/My Work, Command Center או System | גבוה | תדירות, risk ו־receipt discoverability; לא עצם היכולת. |
| System Health / Emergency Stop | More/System surface עם prominence לפי risk | בינוני-גבוה | owner vs admin audience ו־safety requirements. |
| Check-in / Game | contextual layer, drawer או destination | בינוני | ערך תפעולי, frequency ו־retention evidence. |

## Stop condition

מסמך זה עוצר לפני References. לאחר אישור ה־Constitution בלבד ניתן לעבור ל־Reference selection, research, visual exploration ו־screen design. אין לראות באף שורת `candidate`, `demote`, `merge candidate` או `open` החלטת מחיקה, איחוד או target architecture סופי.
