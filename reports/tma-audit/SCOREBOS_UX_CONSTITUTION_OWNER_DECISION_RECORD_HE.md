# SCOREBOS UX Constitution — Owner Decision Record

**תאריך:** 12/08/2026  
**סטטוס:** `OWNER APPROVED — BASELINE FOR UX / REFERENCES / SCREEN DESIGN`

## Scope

מסמך זה מקבע את חוקי ה־UX והאחידות של SCOREBOS לפני מעבר ל־Reference Research ולתכנון מסכים. הוא אינו מכריע Screen Inventory, איחוד מסכים, Primary Workspaces, מבנה Deals/Leads/Ventures, מיקום Game/Approvals/System Health או יעדי ניווט סופיים. אלה נשארים בתהליך Screen Architecture נפרד.

## DEC-UX-01 — Uniformity Model

אין להשתמש ב־80/20 כמדידה ויזואלית קשיחה. חוזי הליבה של המוצר הם 100% אחידים: Shell, navigation contracts, typography, layout, semantic states, action architecture, permissions, feedback, AI behavior, responsive contracts ו־shared primitives. בהרכב המסך יש לשאוף ל־70–80% reuse משותף ו־20–30% composition ייחודי ל־workflow, כאשר השונות נובעת מצורך תפקודי אמיתי ולא מ־Reference חיצוני.

## DEC-UX-02–05 — Shell, Layout, Typography and Semantics

- **Fixed Shell + Flexible Zones:** Primary Navigation, Page/Context Header, Main Content, optional Secondary Context, Global Quick Action/Command entry ו־Back/Close behavior משותפים לכל המערכת. Desktop ו־Mobile הם אותו Shell רעיוני עם adaptation responsive.
- **One Layout System + Approved Density Modes:** grid, spacing tokens, gutters, widths, alignment, breakpoints ו־responsive rules משותפים. המצבים המאושרים הם `Comfortable`, `Standard`, `Dense` בלבד.
- Typography נקבעת לפי roles סמנטיים: Page Title, Section Title, Entity Title, Card Title, Body, Label, Metadata, KPI, Status ו־Action Text. אין local font scale.
- צבע, surface ו־elevation הם semantic system אחיד. הצבעים והפלטה המיתוגית בפועל עדיין פתוחים להחלטת Brand נפרדת.

## DEC-UX-06–08 — Canonical Actions, Capabilities and Schema

כל entry point משתמש באותו מסלול:

`User Intent → Canonical Capability → Validation → Preview / Approval when required → Execution → Verified Result → Canonical Business State`

UI variation אינה יוצרת runtime variation. ברירת המחדל היא שלושה entry modes: Entity Actions, Global Create/Quick Action ו־Guided Next Step. כל capability משמעותי צריך Action Surface, Result/State Surface ו־Business Data Surface.

ה־UI אינו ממציא business semantics. Statuses ו־transitions מגיעים מ־Canonical Schema / Data Model ומחוקים מאושרים. יש להפריד בין Business Status, System/Execution State ו־Presentation. אין לחשוף ActionContracts, internal stores, tool payloads, internal IDs או backend tables שאינם business concepts.

## DEC-UX-09–11 — Shared Data, Search and Continuity

Datasets וישויות משתמשים ב־shared presentation primitives כגון DataTable, List, Board, Entity Header ו־Timeline. loading, sorting, filtering, pagination, selection, refresh, error handling ו־responsive adaptation הם behavior משותף.

Search / Filter / Sort משתמשים ב־query contract אחד; כל מסך מגדיר רק את השדות והרלוונטיות לפי schema. אין fake filters או query semantics מקומיים.

הניווט הוא depth-based עם connected lifecycle: quick inspection ב־context panel/drawer, עריכה קצרה ב־drawer/modal ועבודה עמוקה ב־full entity surface. יש לשמר filters, sort, entity, tab, scroll, originating context ו־return destination. אין להסתמך על chrome של Telegram/WebView לניווט ראשי או ליציאה.

## DEC-UX-12–13 — Verified Feedback and Responsive Contract

ה־UI מציג רק states ותוצאות מאומתים. Working indicator אינו ממציא reasoning או שלב פנימי. Success מוצג רק לאחר verified result, וכולל מה השתנה והיכן למצוא אותו. שגיאות מוצגות בקטגוריה אנושית עם next step, בלי BUG numbers, stack traces, tool errors, contract IDs או payloads.

Desktop, Tablet ו־Mobile חולקים capabilities, permissions, statuses, actions, lifecycle, query model, data sources ו־business rules. מותר לשנות composition: Table→List/Cards, Side Panel→Drawer, columns, sticky action ו־filter sheet, אך אסור להסיר capability חוקית בשקט.

## DEC-UX-14–15 — Contextual AI and Action Safety

ה־AI הוא `Contextual Side Assistant`: מסביר, מסכם, מנתח, מציג context ומציע אפשרויות, אך אינו מפעיל שינוי עסקי מיוזמתו. פעולה persistent מתחילה רק בבקשה מפורשת ונכנסת לאותו Canonical Action Architecture. יש להבחין בין Canonical Data, AI Interpretation/Suggestion ו־Verified Execution Result. Context selection ו־Model/Mode selection הם controls נפרדים.

כל המוצר משתמש ב־Action & Approval UX Contract אחד. לפני פעולה רגישה מוצגים הפעולה, הישות, השינוי, התוצאה הצפויה ומה חסר אם היא חסומה. קיימים שני מסלולים עקרוניים: Direct Action ו־Confirmation/Approval Required. Authorization נבדקת לפי Role + Tenant + Domain + Record/Team Scope + Capability, ובנפרד: `Can View?`, `Can Initiate?`, `Can Approve?`, `Can Execute?`. Hidden UI אינו security control.

## DEC-UX-16–17 — Controlled Variation and System-Level Admission

שונות מותרת רק דרך modes/variants/compositions מאושרים: density, Table/List/Board, context depth, Inline/Drawer/Full Detail ו־Single Column/Split/Grid/Full-width. מסך אינו ממציא spacing, navigation, status, action, responsive logic, component semantics או interaction family.

צורך ב־pattern או capability חדש עובר `System-Level UX Gate`: בדיקת reuse, הגדרת צורך ברמת SCOREBOS, review ואישור, shared implementation, documentation/testing וזמינות לכל המסכים הרלוונטיים. Screen חדש, Domain חדש או Table חדש אינם בהכרח pattern חדש.

## Consolidated Principles

1. One Product — SCOREBOS מרגיש ומתנהג כמוצר אחד.
2. One Architecture — אין runtime/action architecture חדש למסך.
3. Schema First — ה־UI מציג business truth.
4. Capabilities Must Be Visible — יכולת קיימת מקבלת דרך שימוש ברורה.
5. Business Data Must Be Accessible — מידע שימושי נגיש דרך SCOREBOS.
6. Closed Business Loop — Action → Execution → Verified Result → Updated State → Discoverable Record.
7. Continuous Lifecycle — ישויות קשורות מחוברות לאורך ה־workflow.
8. Verified UX — success/failure/state מבוססים על אמת קנונית.
9. One AI Assistant — אין מערכת פעולה נפרדת ל־AI.
10. Authorization Is Architecture — visibility אינה הרשאה.
11. Controlled Flexibility — modes ו־variants מאושרים בלבד.
12. System-Level Evolution — pattern חסר מתווסף למערכת, לא למסך יחיד.

## Explicitly Deferred

Logo, final brand palette, primary/accent colors, controls לבחירת AI context/model, Screen consolidation, final navigation destinations ושינויים ב־Screen Inventory אינם מוכרעים במסמך זה.

## Gate for the Next Phase

כל Reference Research, JCodesMore inspection, UX synthesis, Screen Spec, UI design ו־frontend implementation חייבים לציית למסמך זה. Reference חיצוני הוא חומר לימוד שממופה ל־tokens, modes, primitives ו־contracts המאושרים — הוא אינו מגדיר את SCOREBOS.

**Next Phase:** הגדרת `Reference Extraction Contract` לפני תכנון Screen כלשהו.
