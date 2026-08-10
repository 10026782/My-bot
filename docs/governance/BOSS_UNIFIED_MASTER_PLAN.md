# BOSS Unified Master Plan

**Status:** שכבת-על יחידה — מאחד את `BOSS_ROADMAP_CONTINUATION.md` ו-`BOSS_UNIFIED_MASTER_PLAN_v2.md`.
**לא מחליף את `ROADMAP.md`** — אינו נוגע, משנה, או ממספר מחדש שום C/N/F קיים שם. רק מפנה אליהם.
**עודכן:** 09/08/2026 | **Owner:** אליהו

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
| BOSS Context Librarian — Phase 0 | Documentation / developer tooling only | H0 | מימוש Phase 0 בענף ייעודי: metadata files-first, typed edges, task profiles ו־CLI דטרמיניסטי; ללא חיבור ל־runtime וללא מקור אמת חדש | להשלים tests, review ו־PR קטן; לא להפעיל או לחווט ל־production |
| F52 Unified Approval Runtime — Unified User Messages | Message UX / Approval Runtime | H0 | PR 0 documentation/audit ready for merge — התכנון והאודיט הושלמו ותועדו; היישום טרם התחיל | PR 1 Message Contract Foundation בלבד, ללא חיבור ל־production |
| Approval Policy Single Source (F52→C83) | Core/Security | H0 | ✅ C83 סגור ומאומת — `event_bus.ACTIONS_REQUIRING_APPROVAL` הוא alias טהור ל-`tool_registry.TOOLS_REQUIRING_APPROVAL`, לא רשימה עצמאית (ר' ROADMAP.md §C83). **BUG-077** (אומת מחדש באותה בדיקה, לא נפתח כפול): 🟡 **תוקן במלואו בקוד 07/07/2026 (root cause + תסמין), טרם ממוזג** — התסמין החי (Tier 3, PR #250, ✅ ממוזג) **וגם** ה-root cause הארכיטקטוני (`propose_action()` כעת מאמת `requires_approval` מול `tool_registry.needs_approval()`, פרט ל-`self_confirm` carve-out; נדרש גם לתקן את `core/lead_candidate_handler.py::_write_one_lead()` שהיה עם payload שגוי שמנע ממנו לקבל self_confirm) סגורים. ר' `BUG_AUDIT_LOG.md` BUG-077 לפירוט מלא, כולל קונפליקט שהתגלה עם יישום נאיבי-מדי ותוקן לפני push. | לאמת בפרוד אחרי מיזוג — ראה `BUG_AUDIT_LOG.md` BUG-077. |
| `BOSS_Marketing_Execution_Map.md` | Revenue Execution | H1-H2, H5 | גל 1 (הפעלת הלולאה הקיימת) — טרם אומת בפרוד | להדליק `LEAD_CAPTURE=true` ולאמת (זהה ל-H1.1) |
| Decision Hub | Trust/Decision loop | H3 | Stage 0-1 merged, flag off, לא verified. **BUG-DH-03/04** (formula injection) 🟡 תוקן בקוד, **✅ ממוזג ל-main** (PR #251, `d51e6be`; תוקן 07/07/2026, רשומה קודמת טענה "טרם ממוזג" בטעות) — `tools/airtable_gateway._safe_formula_param()`, `cmd_decision.py`/`decision_pipeline.py`, `test_bugdh03_04_formula_injection.py` 15/15, ר' BUG_AUDIT_LOG.md BUG-036/BUG-037. **לא מאומת בפרוד.** | לא להפעיל `FEATURE_DECISION_HUB` עד production evidence (המיזוג עצמו כבר בוצע) |
| Media Layer (F16) | Media/Context loop | H4 | קוד ממוזג, flag off | ליצור טבלת Media Files ידנית |
| Tasks/Deadlines/Roadmap_Tasks איחוד | Data model | — | בעבודה בפועל (לא סגור) | לעדכן כאן כשנסגר |
| Command Center / Knowledge Hub | Product UI loop | H6 | טרם התחיל | תלוי ב-H1-H2 יציבים |
| F12 vs F13 (Model Provider / TenantConfig overlap) | Architecture | — | ✅ סגור — הכרעת בעלים מפורשת (07/07/2026): F13 סופגת את F12, F12 נגנז כתכנון עצמאי. F13 עצמה נשארת DEAD CODE — DO NOT WIRE (ההכרעה קובעת רק איזה תכנון ממשיך, לא מתירה activation). ר' ROADMAP.md §F12/§F13. | לוודא שהעדכון ב-ROADMAP.md בוצע בפועל (בוצע 07/07/2026) |
| B2 Contacts Brain | Product | Backlog | **PARTIAL** — `tools/contact_resolver.py` קיים בפועל (ranking + disambiguation), אך `CONTACT_RESOLVER` כבוי כברירת מחדל, אין alias/nickname table, אין preferred-channel logic. מקור סמכותי: `docs/audit/C95A_ARCHIVE_CARRY_FORWARD_GAP_REPORT.md` (לא `MASTER_PLAN_v2.md`, שהוא הקשר-כוונה היסטורי בלבד, 25/05/2026, לא קובץ בריפו). | להוסיף alias table + preferred-channel לפני שקוראים לזה "done"; להחליט אם להדליק את הדגל |
| B3 Draft Mode | Product | Backlog | **MISSING כקונספט כללי** — אין מימוש קיים כלל (לא "תלוי ב-B2 בלבד" כפי שנוסח בטעות קודם). `MASTER_PLAN_v2.md`'s `draft_mode.py` (העלה הבעלים, לא קובץ בריפו) הוא הגדרת-כוונה מקורית (25/05/2026), לא SPEC מוכן למימוש. | תלוי בהחלטת בעלים אם הצורך העסקי עדיין קיים; לעצב (לא ad hoc) אם כן |
| B1 Queue/Workers | Infra | Parking Lot | **MISSING לחלוטין** — אפס Redis/RQ/Celery/SQS ב-`requirements.txt`/בקוד. `worker.py` סינכרוני (Render-cron HTTP endpoint), `scheduler.py` thread יחיד חוסם (`schedule` library) — סיכון stall מתועד (`daily_collector.py:15-18`). `MASTER_PLAN_v2.md` הוא הסבר-מקור לרעיון (Redis+RQ), לא תוכנית קיימת. מקור סמכותי: C95A §G. | NEEDS_C95 (C95F) — להכריע אם queue אמיתי נדרש בקנה-מידה הנוכחי, או לתעד ש-`schedule` חד-thread היא בחירה מכוונת |
| Airtable Schema Refresh (Snapshot / RuntimeSchemaProvider / Value Validation — SPEC v2 + PR3B rev.2) | Data/Reliability | H0 | ✅ **כל שלושת ה-PRs ממוזגים ל-`main`.** **PR3B — RuntimeSchemaProvider** (`core/runtime_schema_provider.py`): ✅ ממוזג (PR #267, `183ecdd`, 08/07/2026) **וגם מאומת בפרוד** — shadow רץ, Meta API 200 OK, כתיבה על טבלת Business Memory לא נחסמה (contract mode="full" מאושר live). **PR2 — Gateway Select-Value Validation**: ✅ ממוזג (PR #269, `358b3bc`, 08/07/2026) **וגם מאומת בפרוד פעמיים**, בבדיקה מבוקרת עם ערך Domain שגוי בכוונה: (1) `shadow` — הערך הלא-תקין דווח בלוג (`[SelectValueValidation:SHADOW]`) בלי לחסום כלום, הכתיבה נכשלה באותה צורה כמו לפני ה-PR (422 כללי, כצפוי — shadow לא אמור למנוע זאת); (2) `enforce` — אותו ערך לא-תקין הביא ל-drop של שדה ה-Domain בלבד וה-write הצליח (`recJvDp9vuga4nffa` נוצר, שאר השדות נשמרו) — 08/07/2026, הוחזר ל-`shadow` מיד אחרי האימות. **PR3A — Schema Snapshot Archive**: ✅ ממוזג (PR #270, `529e344`, 08/07/2026 — נבנה מחדש מ-`main` נקי אחרי שה-PR המקורי #268 נתקל בקונפליקטים ונסגר) — `FEATURE_AIRTABLE_SCHEMA_SNAPSHOT` **עדיין כבוי כברירת מחדל, טרם מאומת בפרוד**, דורש manual pre-activation checklist (טבלת "System Schema Snapshots" קיימת ב-Airtable + שדות תואמים) לפני הפעלה — ר' `tools/schema_snapshot.py`. | להחזיר את ה-Domain option ב-Airtable לערך התקין (התיקון הפך מכוון לצורך הבדיקה); להמשיך shadow על טבלאות/שדות נוספים לפני enforce רחב יותר; PR3A טעון manual pre-activation checklist לפני שמדליקים; PR_RESPONSE_CONTRACT (BUG-017 remaining callers: `ad_attribution.py`/`voice_adapter.py`/`interaction_engine.py`/`tenant_provisioner.py`/`lead_memory.py`) ו-PR3C/PR4 עדיין לא התחילו. **🔒 חסום במפורש: אל תדליקו `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE=enforce` עבור `Leads` עד שמאמתים `get_provider().get_table_contract("Leads")["mode"]=="full"` בנפרד — ר' שורה "SPEC A1" למטה, הממצא ב-`Leads.status` מ-10/07/2026.** |
| SPEC A1 (Atomic Fail-Closed — כתיבה חלקית ל-Airtable) | Core/Security | H0 | ✅ **סגור, ממוזג ומאומת בפרוד** — קוד: PR #296 (`38fd5f7`/`0ed89e2`), אימות production חי: PR #297 (`c9e83a2`/`4b9ae60`) דרך `verify_a1.py` (סקריפט חד-פעמי, נמחק אחרי השימוש). `dropped = set(fields)-set(clean)` מאושר קיים על `origin/main` (`tools/airtable_gateway.py:320,383`); ריצה חיה ב-Render אישרה חסימת HTTP מלאה לפני יציאה עבור payload מעורב (שדה תקין+שדה בעייתי) בשלושה מתוך ארבעה מקרים (unknown field / malformed linked-record / read-only field). **ממצא צדדי לא-פתור:** ערך select לא-חוקי ל-`Leads.status` אינו נבדק כלל ומגיע לניסיון HTTP אמיתי (לא ספציפי ל-SPEC A1 עצמה — תלוי ב-PR2/PR3B, ר' פירוט מלא ב-`BUG_AUDIT_LOG.md` SPEC A1, עדכון 10/07/2026). | A2 (structured error propagation) — registered, טרם התחיל. |
| A2 — Structured error propagation (airtable_tools.py / decision_ports.py / providers/airtable_shim.py / core/reasoning_ports.py) | Core/Security | H0 | Registered, טרם התחיל. מטרה: להעביר את ה-`errors` שמחזירה `validate_airtable_fields()` בפועל לקורא/למשתמש (לא רק ל-log) — SPEC A1 רק מונע כתיבה חלקית שקטה, לא פותר את "*למה* נכשל". | לתכנן scope מדויק לפני התחלה — ר' `BUG_AUDIT_LOG.md` SPEC A1 §סטטוס. |
| SPEC ב' — Router-level (Preview Integrity audit, סעיף ב) | — | — | Registered, טרם נסקר/הוגדר בריפו הזה. הוזכר כממצא-אחות ל-SPEC A1 מתוך אותו audit ("Preview Integrity", סעיפים א/ב) — תוכן מדויק **לא אומת/לא נמצא כמסמך בריפו** נכון ל-10/07/2026; אין להניח scope לפני שמאתרים/מגדירים את המסמך המקורי. | לאתר/לשחזר את תוכן "סעיף ב'" לפני שמתחילים לתכנן. |
| SPEC Preview Content Fix (Sites #3+#4) | Core/Security | H0 | ✅ קוד+טסטים מוכנים (`app.py`: `_describe_tool_call`/`_format_field_value`/`_SENSITIVE_FIELD_KEYS`, `approval_response`/`CONFIRMATION_SUFFIX`; `test_preview_content_fix.py` 23/23) — ממתין ל-merge+production verification. ר' `BUG_AUDIT_LOG.md` "SPEC Preview Content Fix (Sites #3+#4)" לפירוט מלא. | להריץ Contract Chain אימות production אחרי מיזוג (בדומה ל-SPEC A1/`verify_a1.py`) — לוודא ש-preview באמת מציג ערכים ממוסכים נכון בפרוד, לא רק ביחידה. |
| Hebrew Field-Name Sensitivity Audit (מ-`_SENSITIVE_FIELD_KEYS`) | Core/Security | H0 | **טרם התחיל.** מקור: תוך כדי SPEC Preview Content Fix (10/07/2026) התגלה ש-`_SENSITIVE_FIELD_KEYS` המקורי (4 מפתחות אנגליים) פספס לגמרי `ContactFields.PHONE="טלפון"`/`EMAIL="אימייל"` — טופל נקודתית, אבל סריקה מהירה (`grep "^class.*Fields"` + חילוץ קבועים עם תווים עבריים ב-`airtable_schema.py`) העלתה **6/38 מחלקות Field עם שמות שדה בעברית, 45 קבועים בסך הכל** (`DealFields`, `TaskFields`, `DeadlineFields`, `LearningFields`, `ApprovalsFields` — לא רק `ContactFields`), **מתוכם לא סווג אף אחד** כ-PII/מזהה-פנימי מול תוכן עסקי לגיטימי (חשוד במיוחד: `ApprovalsFields.CONTEXT_ID`="מזהה הקשר"/`CONTEXT_DATA`="נתוני הקשר" — עלולים להכיל payload/מזהה פנימי). | audit שיטתי מלא — לסווג כל אחד מ-45 השדות, לעדכן `_SENSITIVE_FIELD_KEYS` בהתאם — לפני שעוד שדה חסר מתגלה בפרודקשן כמו שקרה עם `ContactFields.PHONE`. |
| ✅ BUG-098 hotfix — `_FOLLOWUP_WORDS` substring match | Core/Security | H0 | **סגור, ממוזג ומאומת בפרוד.** PR #301, commit `165bcee` (`git log origin/main` מאשר). אומת חי: הודעות "קומה חמישית"/"קומה שנייה" (10/07/2026 18:10-18:16) לא הפעילו יותר את חטיפת ה-batch הישן. 16/16 טסטים. ר' `BUG_AUDIT_LOG.md` BUG-098. **הערה:** `last_lead_candidate_batch` TTL (הרחבה שהייתה מתוכננת יחד עם ה-hotfix) **לא מומשה בפועל** — ה-word-boundary fix לבדו הספיק לפתור את התסמין שנצפה; TTL עדיין נכון להוסיף מסיבות עקרוניות (state שלא נגמר לעולם) אך לא דחוף יותר. | לשקול אם להוסיף TTL בנפרד או להשאיר ל-Follow-up 3. |
| 🔴 BUG-099 — Lead extraction integrity (`core/ingress_classifier.py`) | Core/Security | H0 | **שורש מאומת, קוד לא שונה עדיין.** התגלה תוך כדי אימות BUG-098: שם ליד מוחלף בתיאור-נכס ("חדרים קומה ראשונה") כשתיאור ארוך יושב בין השם לטלפון (חלון חילוץ ±80 תווים מעוגן לטלפון, לא לשם) — **אושר עם רשומה אמיתית שנכתבה לפרוד** (`recRvK6hFTNgyj8ag`, Leads). גם תלות ב-multi-line (`_BLOCK_SEP` מבודד טלפון משם → `candidates=0`). **תיקון לדיווח מוקדם יותר**: לא הפסיק הוא הגורם (אומת ב-4 וריאציות) — הסדר (תיאור-לפני/אחרי-טלפון) הוא הגורם. `DeterministicDenial` (`core/router/deterministic_denial.py`) אומת כשכבת-ניסוח מעל `enforce_leads_write_gate` הקיים, לא gate נפרד — חשד "BUG-100" בוטל. ר' `BUG_AUDIT_LOG.md` BUG-099 לפירוט מלא כולל טבלת reproduction. **קובץ נכון לתיקון: `core/ingress_classifier.py`, לא `lead_candidate_handler.py`'s קוד מת.** | מפוצל ל-3 תת-items למטה — לא לממש כגוש אחד. |
| ✅ BUG-099a — הרחבת `_NAME_STOP` (אוצר-מילים תיאור-נכס) | Core/Security | H0 | **קוד+טסטים מוכנים, ממתין ל-merge+production verification.** `core/ingress_classifier.py:205-217` — נוספו 24 מילות תיאור-נכס ל-`_NAME_STOP` (קומה/חדרים/floor-ordinals/מרפסת/מטבח/חניה/מעלית/וכו'). Contract Chain קצר בוצע (5 שורות — `_NAME_STOP` לא משותף עם `lead_candidate_handler.py`'s עותק מת, מאומת ב-grep). `test_bug099a_name_stop_extension.py` (חדש, 9/9): T1 (reproduction מדויק של `recRvK6hFTNgyj8ag`, דרך `summary` field שנשלף מ-Airtable) → כעת `candidates=[]`/Tier 5 במקום garbage; T2 (description-before-phone) זהה; 2 control cases (description-after-phone, ליד תקין רגיל) ללא שינוי; isolation check מאשר `_NAME_STOP` לא משותף. Sanity: הוסר זמנית התיקון → 5/9 טסטים נכשלו (מוכיח שהטסטים תופסים רגרסיה אמיתית). **Regression מלא לפי דרישת המשתמש**: `test_bug096_ingress_classifier_batch_bleed.py` (29/29), `test_bug098_followup_word_boundary.py` (16/16), `core/router/test_router.py` (44/44), `smoke_tests.py`, `python3 -m py_compile` — כולם ירוקים. | PR + push, ואז production verification (בדומה ל-BUG-098/A1). |
| BUG-099b — הרחבת חיפוש שם מעבר לחלון ±80 סביב הטלפון | Core/Security | H0 | Registered, טרם התחיל. **נפרד בכוונה מ-099a** — 099a רק *דוחה* שם שגוי (מוביל ל-`candidates=0`/Tier 5); זה נדרש כדי *למצוא בפועל* את השם הנכון ("יעל רייס") גם כשהוא רחוק מהטלפון. שינוי ארכיטקטוני גדול יותר וסיכוני-רגרסיה — חולק תשתית (`_extract_lead_candidates`/`_BLOCK_SEP`/windowing) עם לוגיקת ה-batch-extraction שתוקנה בזהירות רבה ב-BUG-096/097 (ר' `BUG_AUDIT_LOG.md`). | Contract Chain נפרדת מול BUG-096/097 לפני מימוש — לוודא שזה לא שובר את תיקוני ה-batch-bleed הקיימים. |
| BUG-099c — Fallback form כש-LCH נכשל אך Router בטוח ב-create_lead | Core/Security | H0 | Registered, טרם התחיל. כש-099a "מציל" מ-garbage-name אבל לא מוצא שם תקין (candidates=0) — היום הזרימה נופלת ל-`DeterministicDenial`/"❌ חסום". צריך fallback form (שם/טלפון/דומיין/עניין/הערות) או שאלת-הבהרה ממוקדת, **לא** reuse של `core/lead_buffer.py` (מאומת: מחובר לזרימת `capture_inbound_lead` החיצונית בלבד, לא ל-LCH). לא מחליש את `enforce_leads_write_gate` — מנתב סביבו למסלול המאושר. | לעצב אחרי 099a+099b — תלוי בהבנה מלאה של מתי LCH "נכשל" באמת. |
| Follow-up (BUG-099) — domain inconsistency בין בדיקות דומות | Core/Security | Backlog | Registered, טרם נחקר. שלוש בדיקות דומות הפיקו `domain` שונה (finance/general/crm) — ייתכן session state ישן, ייתכן regex-detection תלוי-טקסט. עדיפות נמוכה יחסית ל-BUG-099 עצמו. | לתעד תצפיות נוספות; לא לחקור לפני שסוגרים BUG-099. |
| Follow-up 1 — הרחבת trigger לזיהוי ליד (טלפון/"ליד"/"צור") | Core/Security | H0 | Registered, טרם התחיל. **לא חלק מ-BUG-098 hotfix** — משנה את תנאי candidate detection עצמו (Tier system), לא רק follow-up matching. דורש Contract Chain נפרדת: (1) grep מול `classify_ingress`/Tier gating הקיים — לוודא שזו לא Dual Mechanism מול לוגיקת ה-Tier הקיימת שכבר מחליטה מתי phone-only מספיק; (2) בדיקת false-positive הפוך — טלפון שמוזכר בהקשר לא-קשור-לליד (ספק/חשבונית/תזכורת) עלול להיתפס כ-lead candidate בטעות. | Contract Chain מול Tier system לפני כל מימוש. |
| Follow-up 2 — escalation-to-Agent path לשערי pre-Agent (`_handle_batch_followup` וכדומה) | Core/Security | H0 | Registered, טרם התחיל. **תגלית ארכיטקטונית**: `_handle_batch_followup()` (וכל gate דומה שרץ לפני ה-Agent, כמו LCH כולו) בנוי כ-"match → return" בלבד — אין path של "לא בטוח → העבר ל-Agent". זה לא עקבי עם העיקרון המתועד ב-`intent_router.py:4` ("Rule-based קודם, LLM רק כשאין ודאות") — היום, גם כש-rule-based לא בטוח, אין דרך מובנית להעביר את ההחלטה ל-Claude; ה-gate פשוט מחזיר תשובה (נכונה או שגויה) בלי אפשרות אחרת. | לעצב מנגנון escalation גנרי לשערי pre-Agent — לא ספציפי ל-LCH בלבד. |
| Follow-up 3 — Session selection non-determinism + correlation ID | Core/Security | H0 | Registered, טרם התחיל. מ-BUG-098: `_load_from_db`/`_find_best_session_in_db` (`session_store.py`) בלי `sort` מפורש, טבלת Sessions בלי שדה Status (אין סינון done/resolved), `_find_best_session_in_db` לא נעול תחת `_create_lock`. בנוסף: אין correlation ID עקבי (`update_id`/`message_id` לא נרשמים ברמת INFO) דרך inbound→session→tool→outbound. לא הגורם הישיר ל-BUG-098 אבל risk אמיתי נפרד. | audit + עיצוב sort דטרמיניסטי, ואולי שדה Status ב-Sessions; לתכנן correlation ID scheme. |
| ✅ BUG-PENDING-APPROVAL-B — Pending Approval Context Safety | Core/Security | H0 | **✅ סגור במלואו, VERIFIED IN PROD (12/07/2026)** — שרשרת 4 PRs (#311-#314), כל אחד מוזג רק אחרי שבדיקה חיה חשפה את הפער הבא: state fields+reconfirmation logic (#311) → global ingress context gate על כל webhook, לא רק `run_agent()` (#312) → Telegram idempotency key = event identity, לא טקסט (#313) → FSM חסום-סיבוב-אחד ל-reconfirmation חוזרת + קבלת-ביצוע עם תיאור עסקי (#314). לוג פרודקשן מילולי מלא (12/07) מוכיח את כל השרשרת יחד. ר' `ROADMAP.md`/`BUG_AUDIT_LOG.md` BUG-108/BUG-PENDING-APPROVAL-B. | סגור — אין המשך נדרש. |
| U1 — Understanding Layer Architecture Decision | Core/Architecture | — | **🟡 רישום בלבד, ממתין להחלטה** (נרשם 12/07/2026 ב-ROADMAP.md F-section). BUG-102/103/104 מיפו מנגנוני-הבנה קיימים בקוד (`core/reasoning_entity.py`+`leads_adapter.py`/`decision_adapter.py`) — `leads_adapter.py` קרוב מבנית להצעת "שכבת הבנה כללית" (Interaction Envelope + Understanding Contract + PendingAction Store) אך 0 קוראים חיצוניים. נדרשת החלטת בעלים: להרחיב/לחבר את הקיים, או לבנות מנגנון נפרד. **חוסם UX-01 (למטה).** | להכריע לפני שממשיכים לדון בשכבת-הבנה חדשה — ר' `BUG_AUDIT_LOG.md` BUG-104. |
| UX-01 — Unified BOSS Experience | Product/UI | H6 (Product UI) | **📋 PLANNED, לא התחיל** (נרשם 12/07/2026 ב-ROADMAP.md F-section, spec מלא שם). שכבת ניסוח/הצגה אחידה לכל הודעות BOSS (Telegram/WhatsApp/Mini App/Daily Digest) — `UXMessage`/`MessageType`/`BusinessDescription`/`ChannelRenderer`, בלי מזהים טכניים (`record_id`/`contract_id`/`tool_name`) בהודעות משתמש. **סדר תלות מחייב: ייצוב Pending Approval (✅ הושלם) → סגירת U1 (🟡 פתוח) → ואז UX-01.** אין לגעת בניסוחי-הודעות בקוד עד ש-U1 סגור — כדי לא לקבל טלאים שונים בין ערוצים תוך-כדי תיקוני-באגים נפרדים. | לא להתחיל לפני שU1 מוכרע. |

**חובה:** כל פעם שמתחילים לעבוד בפועל על שורה מהטבלה, לעדכן את עמודת "שלב נוכחי" **באותו commit/שיחה** — לא בדיעבד. אם שורה "בעבודה" בפועל אבל לא מעודכנת כאן במשך יותר משבוע — זה סימן שנוצר שוב מסלול נשכח.

### 3.5 Runtime Capability Status — verified 09/08/2026

המסמך המפורט והראיות נמצאים ב־[`docs/audit/RUNTIME_CAPABILITY_AUDIT_20260809.md`](../audit/RUNTIME_CAPABILITY_AUDIT_20260809.md). זהו snapshot סטטוס תפעולי קצר; הדוח המפורט הוא מקור הראיות.

**ACTIVE:** Core routing, TurnEnvelope, ActionGateway, approval boundary, deterministic approval cost-cut, gateway/single-speaker ownership on verified paths, IngressEnvelope, Emergency Stop durable persistence, and deterministic `CREATE_TASK`. Staging additionally verifies successful ActionGateway execution. Production verifies proposal and approval-boundary activity, but no successful Production execution occurred in the available export. Single-speaker ownership is verified only on observed paths, not as a global invariant.

**SHADOW:** RuntimeSchemaProvider — `RUNTIME PATH VERIFIED — COMPONENT LOGGING NOT OBSERVABLE`; EvidenceFinalizer — `SHADOW VERIFIED`.

**OFF:** Production `COST_WATCHDOG_LIVE`, `INTERACTION_INTELLIGENCE`, Emergency Window, Knowledge Engine, Creative Generator, and other capabilities already established as effectively/configured OFF. Production watchdog OFF / Staging watchdog ON is an **EXPECTED ENVIRONMENT DIFFERENCE**, not drift.

**CODE-ONLY / RUNTIME UNVERIFIED:** Profile, Project Timeline, Tenant Provisioner, Knowledge Router, Tenant Config/providers, OTP, and Financial Gate. They are not labeled disconnected without positive evidence.

**UNKNOWN / PARTIAL:** Production successful approval execution inside the current export, learning-cycle execution, full usage-telemetry consumption, deterministic PA-01 behavior for `UPDATE_TASK`, and `COMPLETE_TASK` runtime behavior.

**VERIFIED ARCHITECTURAL DRIFT:** `INTERACTION_INTELLIGENCE` scheduler gating reads the environment variable directly instead of the centralized feature-flag accessor — **ARCHITECTURAL DRIFT VERIFIED — NO CURRENT RUNTIME CONFLICT**. No correction is made here.

**OBSERVABILITY DEBT:** RuntimeSchemaProvider lacks source/result logging sufficient to distinguish `live`/`cached`/`snapshot`/`seed`; IngressEnvelope lacks direct envelope ID/source-reference logging. These are observability gaps, not runtime failures.

**OPEN RUNTIME FOLLOW-UPS:** `UPDATE_TASK` PA-01 comparison, `COMPLETE_TASK` verification, Staging `sheets_append → Tasks` canonicalization failure, learning/usage-telemetry verification, and runtime verification of remaining code-present secondary systems. Do not treat these registry entries as implementation authorization.

**Supersession note:** the older Airtable Schema Refresh row above used
`contract mode="full" מאושר live` as a current runtime claim. The 09/08/2026
verified audit supersedes that wording: the current evidence establishes the
RuntimeSchemaProvider path in `SHADOW`, but current logs do not expose the
provider result/source. The detailed evidence and this §3.5 snapshot are the
current status source.

---

### 3.5.1 BOSS Core Harness — Program Map (עודכן: 10/08/2026 — rows A/F/H/I/J and §3.5.3 Next Gates updated for PR #577/#579/#583/#585/#587/#588; §3.5.2's target chain diagram and §3.5's Runtime Capability Status snapshot remain dated 09/08/2026, not re-walked in this pass)

**זהו הסעיף הקנוני היחיד** למצב תכניות-הליבה חוצות-התוכנית (Turn Coordinator,
ActionGateway, RP4/RP5, A32, F52, F14, Agent Cost). כל תכנית שומרת את מפרט
היישום המפורט שלה במקומה (`docs/architecture/...`) — הסעיף הזה **לא**
מחליף אותם, רק ממפה איך הם מרכיבים Harness אחד. `ROADMAP.md` **אינו**
מחזיק טבלת current-state מקבילה — הוא מפנה לכאן (ראה §3.5.1 שם).

**אוצר-מילים מבוקר לעמודת "מצב":** `PLANNING` · `BUILT_UNWIRED` · `MERGED` ·
`SHADOW` · `ENFORCED` · `RUNTIME_VERIFIED` · `BLOCKED` · `SUPERSEDED`.

**כלל flag-disclosure מחייב לעמודת "Runtime state":** כל flag מדווח בשלושה
חלקים נפרדים — **code default** (מה `feature_flags.py` מחזיר ללא env var) ·
**last verified production value** (מה נקרא בפועל מ-Render/לוגים, עם תאריך
ומקור) · **current production value** — מדווח **רק** אם אומת *עכשיו*,
בסבב הזה. איפה שלא אומת עכשיו, נכתב במפורש "not reverified in this pass" —
**אף פעם לא מוסק OFF רק כי code default=false.**

| Program | Canonical authority/docs | Objective | Current implementation state | Runtime state | Verification state | Depends On | Next gate |
|---|---|---|---|---|---|---|---|
| **A. Turn Coordinator TC1–TC7** | `docs/architecture/turn-coordinator/README.md` (canonical current-status); `turn-coordinator-full/GAP_ANALYSIS.md` (gap↔workstream ownership) | Intent ownership, entity resolution, canonical proposal construction, reply ownership, per-action evidence | TC1–TC5: MERGED (TC1 admission gate wired only for CREATE_TASK — UPDATE_TASK/COMPLETE_TASK branch is dead code today). TC6: MERGED (PR #566 `684d299`, PR #569 `d0a8620`). TC7-A: MERGED (PR #573 `c16245c`). **TC7-B1/B1.1: MERGED (PR #583 `7676ca6`, PR #587 `0eafeeb`) — new `core/claim_authorization.py` (`authorize_claim()`), but grep-verified 10/08/2026: zero callers anywhere outside the module's own `__main__` block and its test file; does NOT connect TC7-A's `EvidenceResult` and RP4's `TurnEvidenceSummary` despite the name — BUILT_UNWIRED, target chain in §3.5.2 still not closed.** Separately, PR #579 (`2603b44`, supersedes #576) wired TC7-A's `project_evidence_result()` into RP4 comparison logging under `FEATURE_EVIDENCE_FINALIZER` shadow/enforce — this is RP4 shadow logging, not TC7-B claim authorization | `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` — code default `false`; last verified production value **`true`** (09/08/2026, Render dashboard env-var read + live app-log/Telegram transcript, deploy `7dbdddd`); current: not reverified in this pass | TC6: **RUNTIME_VERIFIED** for 3/6 scenarios (09/08/2026 — create→pending, status query, second-create-block; callback-button/RP5-classification/replay still open). TC7-A: unit-tested only, SHADOW-only observability (not wired to `final_reply`). TC7-B1/B1.1: unit-tested only, no runtime path exists to verify | ActionGateway (B); F14/TC5 (F) for entity resolution | See §3.5.3 Next Gates |
| **B. ActionGateway / Approval Runtime** | `docs/architecture/action-gateway/`; `core/action_gateway.py` | Canonical business-action lifecycle + approval + atomic execution ownership | MERGED — `ActionContract`, propose/approve/reject/cancel, BUG-157 CAS fingerprint-claim fix | `FEATURE_ACTION_GATEWAY`/`FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` — code default `false`; last verified production value **`true`** (30/07/2026, `PRODUCTION_30JUL2026_RENDER_VERIFICATION.md`, direct Render env read); current: not reverified in this pass. `FEATURE_ACTION_CONTRACT_PERSISTENCE`/`FEATURE_ATOMIC_CLAIMS` — code default `false`; **no production verification found in either direction** — do not report as off, report as unverified | RUNTIME_VERIFIED for core create/approve/cancel/replay-guard flows (30/07, 07/08) | A32 (D) for evidence validators; TC6 (A) for reply ownership | Staged `FEATURE_ACTION_CONTRACT_PERSISTENCE`/`FEATURE_ATOMIC_CLAIMS` rollout — runbook exists (`docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md`), not executed. Parallel, not a TC7-B blocker |
| **C. RP4/RP5 Evidence Finalizer** | `core/turn_evidence.py`; `RP5_PREFLIGHT_BLOCKER.md` | Per-turn evidence aggregation (RP4) + claim/evidence enforcement (RP5) | RP4: MERGED, actively maintained. **RP5: no PR has ever merged** — zero implementation | `FEATURE_EVIDENCE_FINALIZER` (three-state off/shadow/enforce) — code default `off`; last verified production value **`shadow`** (28/07/2026, direct Render env read, `SINGLE_SPEAKER_APPROVAL_UX_PRODUCTION_VERIFICATION_PLAN.md`) — **that reading is 12+ days old and must be re-verified, not cited as current**; current: not reverified in this pass. `enforce` today behaves identically to `shadow` (no RP5 code exists to differentiate) | RP4: SHADOW (comparison logging vs. live traffic; BUG-139 open unresolved mismatch). RP5: BLOCKED — no implementation to verify | A32 (D) upstream evidence source; sits alongside TC7 (A) — structurally non-competing by test, no owner-decision doc found reconciling them | RP5 runtime re-verification + enforcement planning — see §3.5.3 |
| **D. A32 Anti-Hallucination** | `core/anti_hallucination.py` | Post-hoc claim-detection + response sanitization | MERGED, unconditional | No flag — **ENFORCED**, always live | RUNTIME_VERIFIED (`test_a32_enforcement.py`) | None (foundational) — TC7/RP4/RP5 depend on it, not the reverse | None open — stable |
| **E. F52 Unified Status / MessageContract** | `docs/architecture/f52-unified-approval-runtime/README.md`; `audits/phase-4c/CURRENT_STATE_MAP.md` | Single canonical rendering contract across approval/status surfaces | MERGED — D-001…D-019 decisions, PR1/PR4/PR5/PR6 shadow adapters, D-018 leak fix | `FEATURE_UNIFIED_STATUS_FORMATTER` (three-state off/shadow/on) — code default `off`; last verified production evidence: shadow logging observed live (`[UnifiedStatusFormatterShadow]` entries, 09/08/2026 sampling per `ROADMAP.md` N17 item 4) — **never confirmed `on` anywhere**; current: not reverified in this pass. D-018's tool_name-leak fix is unconditional/live regardless of this flag | SHADOW (log comparison in production); D-018 piece RUNTIME_VERIFIED | TC6 (A) feeds reply-owner; TC7 (A) feeds optional `evidence_status` metadata (non-authoritative, D-013) | F52 rollout prerequisites — parallel track, not a TC7-B blocker |
| **F. F14 Entity Resolution / TC5** | `ROADMAP.md` §F14; `core/router/entity_resolvers.py` | Bounded, identity-scoped entity resolution + Contact find-or-create gate | F14-A1 (PR #568) + F14-B1 (PR #570): MERGED. TC5 framework: MERGED. **F14-B2 (PR #577 `cc67f9f`, 09/08/2026): MERGED** — `find_or_create_contact()` gains `create_writer`; two more live callers route through it (`tools/dispatcher.py`'s `airtable_add`→Contacts path, `tools/approval_actions.py`'s `tma_write` Contacts POST), grep-confirmed | Not flag-gated — always-on for the now-4 migrated callers only | **BUILT_UNWIRED** — gate covers 4 specific callers (`crm_add_contact`, `convert_lead_to_contact`, dispatcher `airtable_add`→Contacts, `tma_write` Contacts POST) via hardcoded interception, still not a centralized `ActionGateway`/dispatcher-wide gate; other agent-tool paths into Contacts remain unguarded. Unit-tested only | — | Centralized dispatcher/ActionGateway-wide gate (F14-B2's original scope) — parallel track, not a TC7-B blocker |
| **G. Agent Cost / Deterministic Execution** | `cost_monitor.py`, `core/cost_watchdog.py`, `core/usage_telemetry.py` | Measure Claude/Agent token spend; maximize zero-Agent-call routing | MERGED — 3-tier measurement lineage (no duplicate system) | `cost_monitor.py`/`core/cost_watchdog.py` live (write `AI_Usage_Daily`, no flag). `core/usage_telemetry.py`/`usage_events` genuinely SHADOW, confirmed unread by any production code path; PR3 cutover explicitly **owner-blocked** pending real-billing comparison | RUNTIME_VERIFIED (live trigger); usage_telemetry SHADOW | Measures traffic from all other programs; not blocking | POST-TC COST VALIDATION after sufficient post-TC6/TC7 traffic — parallel track, not a TC7-B blocker |
| **H. Durable State (TC8)** | `turn-coordinator-full/GAP_ANALYSIS.md` (BLOCKER rows); `TC8_DURABLE_TURN_STATE.md` | Single durable turn-ownership/concurrency record, replacing 4 coexisting pending/approval stores | **MERGED (PR #585 `a945ee7`, 10/08/2026)** — new `core/turn_state_repository.py` (`TurnStateRepository`) | Not flag-gated — grep-confirmed live/unconditional, called from `app.py`'s `_tc8_claim_contract()`/`_tc8_finish_contract()` at all 4 approve/reject/cancel callback+text sites; fails closed on repository unavailability | **MERGED, live/unflagged.** "Staging verified" (`TC8_DURABLE_TURN_STATE.md`, commit `c7b4d9b`) is asserted prose against staging commit `2750f8ca9b`, no checked-in artifact — not independently confirmed | TC6, TC7-B (A) | Independent artifact-based verification of the staging closure claim; TC10 regression harness (still code-absent) |
| **I. MessageContract full-surface (TC9)** | `turn-coordinator-full/GAP_ANALYSIS.md` (FOLLOW_UP row) | One public composer across Telegram/WhatsApp/TMA | **MERGED (PR #588 `cec3f83`, 10/08/2026)** — `ActionFact`/`GatewayReply` gain MessageContract fields, `_message_contract_for_fact()` builds it unconditionally in `compose_status_reply()` | `FEATURE_UNIFIED_STATUS_FORMATTER` — code default `off`; construction is live/unconditional but the text-output switch stays gated by this flag (shadow/on). `GatewayReply.contract` has no downstream reader yet | BUILT, live construction, output-gated OFF by default; not runtime-verified as changing user-visible text anywhere | F52 (E) schema (stable, D-012); TC6/TC7 (A) | Wire `GatewayReply.contract` to an actual consumer; F52 rollout decision |
| **J. Observability closure (TC10)** | `turn-coordinator-full/TC10_OPERATIONAL_VERIFICATION_HARNESS.md` | Verification harness + rollout/rollback gates | **COMPLETE AND VERIFIED (10/08/2026)** — `scripts/run_isolated_regression.py`/`scripts/regression_matrix.py`/`scripts/staging_identity.py` (new), `scripts/verify_tc9_staging.py` (new), `scripts/verify_tc8_staging.py` fixed (no longer runs the full regression matrix against real staging — root cause of the BUG-122 contamination the TC8 handoff described). Not a runtime layer — no ActionGateway/TC7/TC8/TC9/F14/router/approval-policy code touched | N/A — tooling only, no flags | Isolated regression: **RUNTIME_VERIFIED via real CI** — PR #590 commit `2b6ecb3`, `backend-ci` run 31362450916, `FINAL: PASS`, 39/39 callback hardening, 8/8 PR-0C, 11/11 BUG-158, 21/21 full matrix, stable across 2 repeated runs (harness doc §6.2). Staging runtime: **RUNTIME_VERIFIED against real staging (2026-08-10)** — `scripts/verify_tc8_staging.py` (`FINAL: TC8: DONE`, deploy SHA matched) and `scripts/verify_tc9_staging.py` (`FINAL: TC9 STAGING CANARY: DONE` — pending/turn_id/real successful execution/failed/clean cleanup all confirmed) both ran from the actual Render staging shell against real DATABASE_URL/AIRTABLE credentials (harness doc §6.3). Two self-caught bugs found and fixed along the way: an over-broad Telegram credential override (PR #590) and an Airtable-base-id name check that could never pass for any real base (PR #592) — both root-caused from real failures, not assumed | TC8 (H, MERGED), TC9 (I, MERGED) | None — closure gate satisfied |
| **K. PA-01 Structural Enforcement** | `docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md` | Block phantom approval-pending claims lacking structural evidence | MERGED (PR #352, `2be2472`) | `FEATURE_PA01_ENFORCEMENT_STATE` (three-state) — code default `off`; **no production verification found in either direction** — do not report as off, report as unverified | BUILT_UNWIRED — not activated in production | Risk router contract-required-intent table | Does not itself close the TC1 CREATE_TASK-only admission gate — that remains open (see A) |

### 3.5.2 Target Canonical Harness Authority Chain

> **⚠️ This is TARGET architecture, not a live end-to-end runtime flow
> today.** The chain below is the intended shape once TC7-B, TC8, TC9, TC10
> land. As of 09/08/2026, it is **not one connected pipeline** — several
> links exist as independently-verified pieces that have not been wired
> together. In particular: **TC7-A (`EvidenceResult`, per-action) and RP4
> (`TurnEvidenceSummary`, per-turn) are two separate, MERGED-but-unconnected
> mechanisms today** — nothing in the code imports across them, and no
> "claim authorization" step consumes either to gate a reply. **TC7-B is
> specifically the connection/claim-authorization stage that does not exist
> yet** — it is what would join per-action evidence (TC7-A) and per-turn
> aggregation (RP4) into an actual admission decision (RP5). Treat every
> arrow below as "designed to connect here," not "already connected here."

```
Ingress/Identity → Intent Ownership/Routing (TC1) → Entity Resolution (TC5/F14)
  → Canonical Proposal (TC2/TC4) → ActionContract/Approval Runtime (ActionGateway)
  → Atomic Execution → Execution Evidence (TC7-A, MERGED, standalone)
  → Turn Evidence Aggregation (RP4, MERGED, standalone)
  → [ TC7-B — claim authorization / the connector, NOT BUILT ]
  → Claim Authorization (RP5, NOT BUILT) → Reply Ownership (TC6, ✅ live)
  → Rendering/MessageContract (F52/TC9) → Observability/Cost (Cost program/TC10)
```

Live/verified today, independent of this target chain: TC6 reply ownership
(RUNTIME_VERIFIED), A32's claim-detection/sanitization gate (ENFORCED,
unconditional — today's actual, only, claim-admission mechanism, not RP5).

### 3.5.3 Next Gates (Core Harness) — ordered

1. ~~TC6 documentation closure~~ — ✅ **done** (PR #574, `612a119`, 09/08/2026).
2. ~~TC7-A review corrections and merge gate~~ — ✅ **done** (PR #573, `c16245c`, 09/08/2026).
3. **TC7-B claim-authorization — PARTIALLY done, still not the actual gate.** `core/claim_authorization.py` merged (PR #583/#587, 10/08/2026) but grep-verified zero callers — it does not connect TC7-A/RP4 into a live decision. Remains the next real core gate: **wire `authorize_claim()` to an actual TC7-A/RP4 consumer and to a reply-suppression decision.**
4. RP5 runtime/shadow re-verification (current `FEATURE_EVIDENCE_FINALIZER` production value is 12+ days stale as of 09/08; still not reverified as of 10/08) + enforcement planning.
5. ~~TC8 durable turn state~~ — ✅ **merged** (PR #585, `a945ee7`, 10/08/2026), live/unflagged; staging-verified claim not independently confirmed (see row H).
6. ~~TC9 MessageContract full-surface integration~~ — ✅ **merged** (PR #588, `cec3f83`, 10/08/2026), construction live, output still gated off by `FEATURE_UNIFIED_STATUS_FORMATTER`.
7. ~~TC10 observability closure~~ — implementation complete 10/08/2026 (see row J): isolated regression harness built, TC8 handoff's BUG-122 staging-contamination bug fixed at its root cause, TC9 MessageContract staging canary written. Real-staging execution of that canary + `verify_tc8_staging.py`'s PG checks is still outstanding — no session has run them against real staging secrets yet.

**Parallel tracks — explicitly NOT blockers to TC7-B:**
- Closing the TC1/TC4 `Handler.TOOL` admission gap for UPDATE_TASK/COMPLETE_TASK (currently dead code).
- F14-B2 — partially done (PR #577, two more callers), centralized gate still open.
- F52 `FEATURE_UNIFIED_STATUS_FORMATTER` rollout prerequisites.
- POST-TC COST VALIDATION (once sufficient post-TC6/TC7 traffic accumulates).
- `FEATURE_ACTION_CONTRACT_PERSISTENCE`/`FEATURE_ATOMIC_CLAIMS` staged cutover.
- Track A (relative-date canonicalization, PR #581/#582 — closed) and Track D (RuntimeSchemaProvider/IngressEnvelope observability, PR #580 — code/test-verified, not production-verified) — both independent, unrelated to TC7-B.

### 3.5.4 AI_CONTEXT.md regeneration note

`AI_CONTEXT.md` was regenerated 10/08/2026 against `main` `cec3f83` (this same
commit range, PR #572–#588), superseding the stale draft based on `7dbdddd`
that PR #572 had opened. §3.5.1/§3.5.3 above were updated in the same pass for
rows A/F/H/I/J (TC7-B1/B1.1, F14-B2, TC8, TC9, TC10); §3.5.2's target-chain
diagram and §3.5's Runtime Capability Status snapshot (still dated 09/08/2026)
were **not** re-walked in this pass and should not be read as current beyond
what §3.5.1's per-row updates state explicitly.

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

C-CORE-01 lead_memory Persistence · C-CORE-02 Airtable Write Queue (תלוי V3 מאומת) · C-CORE-04 N10 Rollback אוטומטי · **C-CORE-05 BUG-077 root-cause fix — ✅ הושלם בקוד 07/07/2026 (סגור, לא backlog עוד)** — `propose_action()` ב-`core/action_gateway.py` מאמת כעת `requires_approval` מול `tool_registry.needs_approval(tool_name)` (fail-closed), חוץ מ-`approval_policy == self_confirm` (carve-out בטוח של BUG-076). תוקן גם `core/lead_candidate_handler.py::_write_one_lead()` — עטף `tool_inputs` תחת `"fields"` (היה חסר, גרם לכל קריאותיו לקבל בטעות `approval_policy="approval"` תמיד, לא `self_confirm`). ר' `BUG_AUDIT_LOG.md` BUG-077 לפירוט המלא כולל הקונפליקט שהתגלה עם יישום נאיבי-מדי. 🟡 קוד מוכן, טרם ממוזג/מאומת בפרוד.

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
