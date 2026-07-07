# BOSS Unified Master Plan

**Status:** שכבת-על יחידה — מאחד את `BOSS_ROADMAP_CONTINUATION.md` ו-`BOSS_UNIFIED_MASTER_PLAN_v2.md`.
**לא מחליף את `ROADMAP.md`** — אינו נוגע, משנה, או ממספר מחדש שום C/N/F קיים שם. רק מפנה אליהם.
**עודכן:** 06/07/2026 | **Owner:** אליהו

---

## 0. למה המסמך הזה קיים, ומה קרה למסמכים הקודמים

היו שני מסמכי-על מקבילים שתיארו את אותה תכנית בשתי שפות-רצף שונות:

| מסמך קודם | שפת רצף | סטטוס עכשיו |
|---|---|---|
| `BOSS_ROADMAP_CONTINUATION.md` | Stage 0-V, Stage 1-6 + IDs (V0-V5, C-CORE-, BM-, RV-, F-01..08) | **מוזג לכאן. הקובץ המקורי → archive** |
| `BOSS_UNIFIED_MASTER_PLAN_v2.md` | Horizon 0-7 | **מוזג לכאן. הקובץ המקורי → archive** |
| `BOSS_MASTER_PLAN_One_Road.md` | — | כבר תויג ARCHIVE לפני כן (עקרון "One Road" שלו משולב בסעיף 1 למטה) |
| `BOSS_Marketing_Execution_Map.md` | גלים 1-5 | **נשאר מסמך עצמאי חי** — הוא Execution layer ספציפי ל-Revenue, לא שכבת-על. ממופה כאן ל-Horizon המתאים בלבד (§3) |

**כלל ברזל חדש:** מרגע זה יש **שפת רצף אחת** — Horizon (0-7), כי זו הייתה השפה במסמך המאוחר יותר. Stage-מספור של Continuation מובא כאן ממופה ל-Horizons, לא כשפה מקבילה.

**מספור ROADMAP.md (C/N/F) לא משתנה.** כל פריט למטה שכבר קיים שם מסומן `[ROADMAP: <ID>]`. פריטים חדשים שאין להם עדיין ID ב-ROADMAP מקבלים namespace ייעודי שלא מתנגש: `BM-`, `RV-`, `FUT-`. **לעולם לא `F-` בלבד** — זה מה שיצר את ההתנגשות עם F09-F16.

---

## 1. העיקרון המכונן — One Road, Many Exits

כביש אחד (Core: Input → Memory → Understanding → 5 Gates → Decision/Action), עם 3 סוגי יציאה: דומיינים (שדה בערך), כלים (Port adapter), ייעודים (TenantConfig). הסכנה היחידה: לבנות ישות decision נפרדת לכל דומיין. השמירה: ישות אחת, MODULE_RULE 11.

---

## 2. כללי ברזל (מאוחד מ-Unified Plan §3 + Governance Additions Rules 13-18)

| # | כלל | מקור |
|---|---|---|
| 1 | Money-First Gate — משימה חדשה חייבת להכניס כסף/למדוד/לפתוח הפצה | Unified §3.1 |
| 2 | No Claim Without Verification — ✅ רק אחרי production evidence | Unified §3.2, Rule 15 |
| 3 | Feature Flag Default Off | Unified §3.3 |
| 4 | One Write Path — כל כתיבה ל-Airtable דרך gateway/approval/audit | Unified §3.4 |
| 5 | Broadcast Safety — אין broadcast לפני COG+Approval+Emergency Stop+audit | Unified §3.5 |
| 6 | Core Domain-Agnostic | Unified §3.6, MODULE_RULE 11 |
| 7 | Main Is Reality — אודיט מבוסס main+production, לא branches | Rule 13 |
| 8 | Audit Cannot Modify — אודיט לא יוצר branch/PR/fix | Rule 14 |
| 9 | Root Cause Before Fix — לא patch-first | Rule 16 |
| 10 | Single Source of Status — אין מסמכי סטטוס מתחרים | Rule 17 |
| 11 | Fix The Process — תקלה חוזרת מחייבת guard, לא רק תיקון | Rule 18 |
| 12 | לא יוצרים עוד "Master Plan" מתחרה ב-ROADMAP | Unified §8.8 |

---

## 3. מקור אמת ותיעוד (מעודכן)

**מסמכי אמת פעילים:** `ROADMAP.md` (ראשון) · `BOSS_CURRENT_STATE.md` (שני) · `CHANGE_CONTROL_LOG.md` · `BUG_AUDIT_LOG.md` · `AI_CONTEXT.md` · **`docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` (מסמך זה — שכבת-על בלבד, לא מחליף ROADMAP)** · `BOSS_Marketing_Execution_Map.md` (Execution layer ל-Revenue, ממופה להורייזונים 1/2/5 למטה).

**הכל השאר — archive evidence בלבד**, כולל שני המסמכים שמוזגו לכאן (§0).

**מסמך מקור (Origin, לא Active/Archive):** `MASTER_PLAN_v2.md` (25/05/2026) — genesis document שהעלה הבעלים לשיחה; **אינו קובץ בריפו**. משמש הקשר-כוונה היסטורי בלבד לטבלאות Airtable המקוריות, Contacts Brain, Draft Mode, Schema Discovery, Queue — לא מקור סטטוס נוכחי. חלקים גדולים הוחלפו בארכיטקטורה אחרת בפועל (Supabase→Airtable-only, Redis→לא נבנה, `orchestrator.py`/`router.py` בשורש→`core/router/*`). למצב הנוכחי הסמכותי של B1/B2/B3 (Queue/Contacts Brain/Draft Mode) ראה `docs/audit/C95A_ARCHIVE_CARRY_FORWARD_GAP_REPORT.md` ו-§3.5 למטה.

---

## 3.5 רישום עבודה חי (Active Work Registry) — הסיבה שהמסמך הזה קיים

> **מה שקרה בפועל:** התחילו כאן ~10 תכניות שונות (Continuation, One Road, Unified Plan v2, Marketing Map, Gap Analysis, Fix Roadmap 14-Day, Stabilization Sprint, ...) בלי מקום אחד שמראה מה מהן פעיל *עכשיו*, באיזה שלב, ומה הצעד הבא שהוחלט. התוצאה: עובדים על שלב א׳ של תכנית אחת, קובעים שלב ב׳ בנפרד במסמך אחר, ואף אחד לא זוכר לחבר ביניהם.

**כלל חדש (מצטרף לסעיף 2):** לפני שמתחילים "גל"/"שלב"/"Sprint" חדש בכל מסמך — חובה לעדכן את הטבלה הזו קודם. אם היוזמה לא רשומה כאן, היא לא אושרה להתחיל.

| יוזמה / מסמך | היקף | Horizon מקביל | שלב נוכחי בפועל | הצעד הבא שהוחלט |
|---|---|---|---|---|
| `ROADMAP.md` | C/N/F ליבה + באגים | H0 | ראה Current Execution Status בקובץ עצמו | ראה טבלת Next Actions שם |
| Approval Policy Single Source (F52→C83) | Core/Security | H0 | ✅ C83 סגור ומאומת — `event_bus.ACTIONS_REQUIRING_APPROVAL` הוא alias טהור ל-`tool_registry.TOOLS_REQUIRING_APPROVAL`, לא רשימה עצמאית (ר' ROADMAP.md §C83). **BUG-077** (אומת מחדש באותה בדיקה, לא נפתח כפול): 🟡 **חלקית תוקן, ✅ ממוזג** — התסמין החי (Tier 3, `_handle_mixed_batch` כתב לידים ללא שום בדיקת `FEATURE_AUTO_CAPTURE`/ליד-קיים) נסגר ב-`core/lead_candidate_handler.py` (שער `_should_auto_write()` משותף ל-3 ה-Tiers) + `test_bug077_tier3_auto_capture_gate.py` (5/5), **✅ ממוזג ל-main (PR #250, `cdc41b5`) — לא מאומת בפרוד** (תוקן 07/07/2026, רשומה קודמת טענה "טרם ממוזג" בטעות). ה-root cause הארכיטקטוני (`propose_action()` ב-`action_gateway.py` עדיין לא מאמת `requires_approval` מול `tool_registry`) **נשאר פתוח במכוון** — SPEC המקורי הגביל את ההיקף לקובץ אחד. | 1) לאמת בפרוד. 2) להחליט אם/מתי לתקן גם את ה-root cause ב-`action_gateway.py:propose_action()` (לפני שורה 468) — ראה `BUG_AUDIT_LOG.md` BUG-077 לפרטים המלאים. |
| `BOSS_Marketing_Execution_Map.md` | Revenue Execution | H1-H2, H5 | גל 1 (הפעלת הלולאה הקיימת) — טרם אומת בפרוד | להדליק `LEAD_CAPTURE=true` ולאמת (זהה ל-H1.1) |
| Decision Hub | Trust/Decision loop | H3 | Stage 0-1 merged, flag off, לא verified. **BUG-DH-03/04** (formula injection) 🟡 תוקן בקוד, **✅ ממוזג ל-main** (PR #251, `d51e6be`; תוקן 07/07/2026, רשומה קודמת טענה "טרם ממוזג" בטעות) — `tools/airtable_gateway._safe_formula_param()`, `cmd_decision.py`/`decision_pipeline.py`, `test_bugdh03_04_formula_injection.py` 15/15, ר' BUG_AUDIT_LOG.md BUG-036/BUG-037. **לא מאומת בפרוד.** | לא להפעיל `FEATURE_DECISION_HUB` עד production evidence (המיזוג עצמו כבר בוצע) |
| Media Layer (F16) | Media/Context loop | H4 | קוד ממוזג, flag off | ליצור טבלת Media Files ידנית |
| Tasks/Deadlines/Roadmap_Tasks איחוד | Data model | — | בעבודה בפועל (לא סגור) | לעדכן כאן כשנסגר |
| Command Center / Knowledge Hub | Product UI loop | H6 | טרם התחיל | תלוי ב-H1-H2 יציבים |
| F12 vs F13 (Model Provider / TenantConfig overlap) | Architecture | — | ✅ סגור — הכרעת בעלים מפורשת (07/07/2026): F13 סופגת את F12, F12 נגנז כתכנון עצמאי. F13 עצמה נשארת DEAD CODE — DO NOT WIRE (ההכרעה קובעת רק איזה תכנון ממשיך, לא מתירה activation). ר' ROADMAP.md §F12/§F13. | לוודא שהעדכון ב-ROADMAP.md בוצע בפועל (בוצע 07/07/2026) |
| B2 Contacts Brain | Product | Backlog | **PARTIAL** — `tools/contact_resolver.py` קיים בפועל (ranking + disambiguation), אך `CONTACT_RESOLVER` כבוי כברירת מחדל, אין alias/nickname table, אין preferred-channel logic. מקור סמכותי: `docs/audit/C95A_ARCHIVE_CARRY_FORWARD_GAP_REPORT.md` (לא `MASTER_PLAN_v2.md`, שהוא הקשר-כוונה היסטורי בלבד, 25/05/2026, לא קובץ בריפו). | להוסיף alias table + preferred-channel לפני שקוראים לזה "done"; להחליט אם להדליק את הדגל |
| B3 Draft Mode | Product | Backlog | **MISSING כקונספט כללי** — אין מימוש קיים כלל (לא "תלוי ב-B2 בלבד" כפי שנוסח בטעות קודם). `MASTER_PLAN_v2.md`'s `draft_mode.py` (העלה הבעלים, לא קובץ בריפו) הוא הגדרת-כוונה מקורית (25/05/2026), לא SPEC מוכן למימוש. | תלוי בהחלטת בעלים אם הצורך העסקי עדיין קיים; לעצב (לא ad hoc) אם כן |
| B1 Queue/Workers | Infra | Parking Lot | **MISSING לחלוטין** — אפס Redis/RQ/Celery/SQS ב-`requirements.txt`/בקוד. `worker.py` סינכרוני (Render-cron HTTP endpoint), `scheduler.py` thread יחיד חוסם (`schedule` library) — סיכון stall מתועד (`daily_collector.py:15-18`). `MASTER_PLAN_v2.md` הוא הסבר-מקור לרעיון (Redis+RQ), לא תוכנית קיימת. מקור סמכותי: C95A §G. | NEEDS_C95 (C95F) — להכריע אם queue אמיתי נדרש בקנה-מידה הנוכחי, או לתעד ש-`schedule` חד-thread היא בחירה מכוונת |

**חובה:** כל פעם שמתחילים לעבוד בפועל על שורה מהטבלה, לעדכן את עמודת "שלב נוכחי" **באותו commit/שיחה** — לא בדיעבד. אם שורה "בעבודה" בפועל אבל לא מעודכנת כאן במשך יותר משבוע — זה סימן שנוצר שוב מסלול נשכח.

---

## 4. חוקי המרה בין ישויות דאטה (הובהרו בשיחה, לא היו כתובים באף מקום)

> נמצא בבדיקת `governance_mapping_report.md`: הדוח סימן את אלה כ"כפילות" — הן **לא**. זו הבהרה קבועה שמונעת ניסיון איחוד שגוי בעתיד.

- **Lead → Contact:** כשההזדמנות נהיית רצינית ועוברת בפועל לטיפול (לא רק מגע ראשוני).
- **Contact → Deal:** כשכסף עובר בפועל או שנחתם הסכם.
- **Payments (טבלת-אם) vs Loans / Debt Management:** לא כפילות — Loans ו-Debt Management משויכות לעסקת-על ספציפית (מבנה נפרד, base אחר). Payments היא המערכת המרכזית.
- **Interaction Log → Business Memory → Learnings:** שרשרת סדרתית, לא כפילות — Interaction Log = מידע גולמי (שיחה בודדת), Business Memory = הצטברות הקשר (מעל שיחה אחת), Learnings = למידה עסקית מופקת מהמערכת.
- **Tasks / Deadlines / Roadmap_Tasks:** כפילות אמיתית — איחוד כבר החל (בעבודה, לא סגור).
- **Worlds / Quests / Coins_Log / Daily_Tasks / Weekly_Goals / Boss_Battles:** **מחוץ לתחום** — כלי תמריץ אישי לתהליך הבנייה, לא חלק ממוצר BOSS. לא נדרש מיפוי Governance Language.

---

## 5. התכנית המאוחדת לפי Horizons

### Horizon 0 — Truth Reset & Production Verification
- H0.1 מסמך זה (הושלם ביצירה)
- H0.2 לנקות סטטוסים שגויים (✅→🟡 בלי evidence)
- H0.3 לאמת Deployment/flags
- H0.4 לסגור קונפליקטים פתוחים:
  - `[ROADMAP: BUG-DH-03/04]` Formula injection — 🟡 **תוקן בקוד 07/07/2026** (`_safe_formula_param()`), **טרם ממוזג/מאומת בפרוד** — ר' BUG_AUDIT_LOG.md BUG-036/BUG-037
  - **C59/C60 ID collision** — טעון תיעוד mapping, לא בוצע עדיין
  - C60 Tool Context Awareness — merge או freeze, טרם הוכרע
  - `[ROADMAP: F12/F13]` — **סגור בשלושה מסמכים בעקביות** (Continuation, Unified Plan, ROADMAP) — נותר רק לרשום את ההחלטה בפועל ב-ROADMAP.md ולסגור
  - F16 Media Files table לפני activation

### Horizon 1 — Revenue Loop MVP
`[Marketing Map: גל 1]` H1.1 Lead Capture live · H1.2 Source Attribution · H1.3 Lead Scoring+Tier · H1.4 Owner Alert · H1.5 Daily Digest בסיסי

### Horizon 2 — Revenue Attribution & Partner Loop
`[Marketing Map: גל 2-3]` H2.1 Revenue Attribution · H2.2 Partner Attribution · H2.3 Manual Distribution First

### Horizon 3 — Decision Hub Owner-Only
H3.1 מצב קיים (Stage 0/0.5/0.6 merged flag-off; Stage 1 Trust Layer merged not-verified; Stages 2-4 לא התחילו)
H3.2 לפני הדלקה: Airtable fields, multi-select, Source Reliability UI, owner-only test, **+ מיזוג/אימות בפרוד של תיקון BUG-DH-03/04 (קוד קיים בענף, ר' BUG_AUDIT_LOG.md BUG-036/BUG-037 — עדיין לא מספיק להדלקה)**
H3.3 החלטת C60

### Horizon 4 — Media Layer Enablement
`[ROADMAP: F16]` לפי מצב קיים + סדר הפעלה (טבלת Media Files ידנית קודם)

### Horizon 5 — Distribution Gateway
`[Marketing Map: גל 4-5]` H5.1 COG/Messaging Gateway `[ROADMAP: C52]` · H5.2 Meta WhatsApp `[ROADMAP: N05-C]` · H5.3 Content

### Horizon 6 — Product UI / OS Refactor
BM-07 Ventures Convert+Notifications · RV-01 Command Center MVP · RV-02 Knowledge Hub

### Horizon 7 — Future Business Management
RV-03 Lead Recovery · FUT-01 Learning Engine · FUT-02 Revenue Attribution מתקדם · FUT-03 KPI Engine · FUT-04 WhatsApp Production (Meta) · FUT-05 Email Channel `[ROADMAP: C92]` · FUT-06 Voice/IVR `[ROADMAP: C91]` · FUT-07 SaaS Multi-Tenant `[ROADMAP: F12/F13]` · FUT-08 Lead Qualifier Wire-up `[ROADMAP: F09]`

> **הבהרת namespace:** FUT-01..08 = פריטי ה-"F-01..F-08" הישנים מ-Continuation, שוחלפו במפורש כדי לא להתנגש עם F09-F16 הקיימים ב-ROADMAP.md.

---

## 6. Business Modules (ללא Horizon ספציפי — נכנסים לפי תלות)

BM-01 5 Gates: Delta · BM-02 Readiness Engine · BM-03 Attention Engine · BM-04 Lead Source Attribution E2E · BM-05 Partner Attribution · BM-06 Followup Full Activation · BM-08 F14 Contact Gate `[ROADMAP: F14]` · BM-09 F15 crm.py Write Migration · BM-10 F52 Tool Refactor

## 7. Core Strengthening (רץ במקביל ל-Horizon 0)

C-CORE-01 lead_memory Persistence · C-CORE-02 Airtable Write Queue (תלוי V3 מאומת) · C-CORE-04 N10 Rollback אוטומטי · **C-CORE-05 BUG-077 root-cause fix (נשאר, אחרי התיקון החלקי)** — התסמין החי (Tier 3) כבר נסגר ב-`core/lead_candidate_handler.py` (06/07/2026, קוד+טסט) **✅ ממוזג ל-main** (PR #250, `cdc41b5`) — תוקן 07/07/2026 (רשומה קודמת כאן טענה "טרם ממוזג" בטעות, אחרי שהמיזוג כבר קרה). מה שנשאר: `propose_action()` עדיין לא מאמת `requires_approval` מול `tool_registry.get_tool_meta(tool_name).requires_approval` (fail-closed, לפני שורה 468 ב-`core/action_gateway.py`) — כל קורא עתידי אחר שיצהיר `requires_approval=False` בטעות עדיין לא ייתפס. ר' `BUG_AUDIT_LOG.md` BUG-077.

---

## 8. מה לא עושים עכשיו (מאוחד, ללא כפילות)

1. לא פותחים Business Module לפני Horizon 0 Complete.
2. לא בונים Multi-Tenant/SaaS לפני שהמערכת יציבה בשוכר יחיד.
3. לא בונים Learning Engine לפני חודשי דאטה אמיתי.
4. לא מחברים F12/F13 לפני שההחלטה הקיימת נרשמת בפועל ב-ROADMAP.
5. לא מפעילים WhatsApp outbound לפני Gateway+Meta+audit.
6. לא מסמנים ✅ בלי production evidence.
7. לא בונים UI refactor רחב לפני Horizon 0/1.
8. לא יוצרים עוד "Master Plan" מתחרה — זה המסמך היחיד מסוג זה מעכשיו.

---

## 9. פערים שנותרו פתוחים (טעונים בדיקת קוד/CLAUDE.md — לא נבדקו כאן)

| # | פער | דורש |
|---|---|---|
| 1 | ~~BUG-DH-03/04 עדיין קיים?~~ נבדק 07/07/2026 — היה קיים, תוקן בקוד (`_safe_formula_param()`), טרם ממוזג/מאומת בפרוד | מיזוג + production evidence לפני סגירה מלאה |
| 2 | C59/C60 mapping מתועד? | קריאת קוד/היסטוריית ROADMAP |
| 3 | CLAUDE.md מבטא Rule 14/16 בפועל? | העלאת הקובץ |

---

## 10. משפט סיכום

אמת → כסף → מדידה → החלטות → הפצה → UI → אוטונומיה. כביש אחד, ROADMAP.md כמספור היחיד לפריטים קיימים, המסמך הזה כשכבת-הרצף היחידה מעליו.
