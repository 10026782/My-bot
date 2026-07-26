# BOSS Unified Master Plan

**Status:** שכבת-על יחידה — מאחד את `BOSS_ROADMAP_CONTINUATION.md` ו-`BOSS_UNIFIED_MASTER_PLAN_v2.md`.
**לא מחליף את `ROADMAP.md`** — אינו נוגע, משנה, או ממספר מחדש שום C/N/F קיים שם. רק מפנה אליהם.
**עודכן:** 27/07/2026 | **Owner:** אליהו

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
