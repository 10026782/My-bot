# BOSS Unified Master Plan

**Status:** שכבת-על יחידה — מאחד את `BOSS_ROADMAP_CONTINUATION.md` ו-`BOSS_UNIFIED_MASTER_PLAN_v2.md`.
**לא מחליף את `ROADMAP.md`** — אינו נוגע, משנה, או ממספר מחדש שום C/N/F קיים שם. רק מפנה אליהם.
**עודכן:** 28/08/2026 | **Owner:** אליהו

**Canonical CORE completion status (10/08/2026):** `CORE v1 — COMPLETE /
READY TO FREEZE`. See
`docs/audit/CORE_COMPLETION_AUDIT_20260810.md` for the current evidence and
limitations. The four-layer program remains **PARTIAL / NON-BLOCKING** because
formal Layer 2 TurnCoordinator implementation is absent. Dated registry
snapshots below are historical evidence and must not override the canonical
audit. Freeze remains an owner/governance decision.

**Governance refresh (21/08/2026, `origin/main` `6a0ba6a`):** main moved
materially since the previous registry reconciliation. Horizon status changes
recorded here are documentation-only: H6 Command Center is now
`ACTIVE / MERGED / needs runtime verification`; H1/N18 Canonical Write
Infrastructure is active with Lead as the first consumer; H4 Media/Gateway has
staging-gated MPT plus Media Probe/Gateway canary artifacts, still not production
activated. Runtime/deployment claims still require explicit deployed-SHA and
live canary evidence.

**Status reconciliation (28/08/2026):** Owner decision recorded for `U1`:
do not build a new general Understanding Contract or PendingAction Store.
Reuse the existing Core Reasoning, ActionContracts/DraftFlow, ActionGateway,
Turn Coordinator, MessageContract, and channel-adapter layers. This supersedes
the older U1 registry wording that said the architecture decision was pending.
`UX-01` is therefore `IN_PROGRESS` through the F52 / Single-Speaker Approval
UX implementation path; R0.1, R1.1, R2.0, R2.1, R3.1, R3.2 and R4 are recorded
as merged/static. R5's read-only gate found no second uniform consumer, so R6.1
aligns only `/decision new`; its current evidence is CODE_DONE / STATIC_VERIFIED.
Runtime is not implied. The registry rows below are reconciled to this decision
and current main evidence.

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

## 3.5 רישום עבודה חי (Active Work Registry) — המקור המסוכם הקנוני

> סעיף זה הוא ה־canonical Active Work Registry עבור owner development ו־Command Center. HORIZON הוא סיכום owner-facing קצר של אותן שורות; Command Center הוא projection read-only שלהן. הסעיף אינו מחליף את הראיות המקוריות ואינו יוצר Registry מתחרה. Reconciliation מתבצע בשגרה נפרדת; OC-C קורא את הסעיף לאחר validation בלבד.

**Schema וכללי validation:** `Initiative Key` הוא מזהה יציב, ייחודי ומכונה־קריא שאינו תלוי בשם התצוגה. `Work State` ו־`Evidence State` הם vocabularies סגורים. `Current Stage` הוא הסבר קצר לבעלים ואינו מקור parsing ל־Work State. `Needs Verification`, `Blocked` ו־`Owner Decision Required` הם booleans מפורשים. ב־DEV-REG-1 `Last Reconciled` הוא timestamp של migration בלבד, וכל `Evidence Source` של המיגרציה מסומן ב־`migration-*`; הוא אינו טוען שבוצע evidence reconciliation. DEV-REG-2 יחליף את `Last Reconciled` רק לאחר reconciliation אמיתי. שורה malformed, key כפול, Horizon שאינו H0–H7, ערך state לא חוקי, boolean לא תקין או mismatch בין state ל־flag נכשלים ב־`tools/dev_registry_validator.py`.

| Initiative Key | Initiative / Document | Scope | Horizon | Work State | Current Stage | Evidence State | Next Decided Step | Needs Verification | Blocked | Owner Decision Required | Last Reconciled | Evidence Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TURN_COORDINATOR_PROGRAM | Turn Coordinator | intent ownership, routing, authorization, reply ownership | H0 | ACTIVE | TC1–TC6 merged. TC7-B claim-authorization wiring + RP5 evidence enforcement merged (PR #1036, `44fd3605`, 26/08/2026): canonical `app.py` response path now captures TC7-B's `authorize_claim()`/`ClaimAuthorizationShadowComparison.authorized` verdict, and RP5 blocks an unauthorized execution-success claim by substituting the existing A32 fallback when `FEATURE_EVIDENCE_FINALIZER=enforce`. RP5 is OFF by default in production (flag not activated) — STATIC VERIFIED / MERGED / RUNTIME NOT ESTABLISHED for both. **Superseded 27/08/2026 (PR #1041, `09935a8`):** the two `core/action_gateway.py` ActionGateway-owned call sites (`approve_with_lifecycle_result()`'s and `_execute_contract()`'s `_finish()` closures) now both replicate the same RP5 enforcement predicate and capture `observe_claim_authorization_shadow()`'s verdict — grep-confirmed present at `core/action_gateway.py:2081` and `:3234` on current `origin/main`. Mixed-category claim coverage also closed in the same PR (`test_rp5_evidence_enforcement.py` A6a/A6b/A6c). See §3.5.1 rows A/C for detail. | MERGED | owner decision on RP5 activation (`FEATURE_EVIDENCE_FINALIZER=enforce`) — the ActionGateway sink design item is closed | true | false | true | 2026-08-27T00:00:00Z | git:main:09935a8;PR#1041;test_tc7_b_rp5_gateway_sink_enforcement.py |
| UNIFIED_APPROVAL_ACTIONGATEWAY | Unified Approval / ActionGateway | canonical action lifecycle, approval and execution boundaries | H0 | ACTIVE | lifecycle and approval paths merged; staged rollout remains separate | MERGED | rollout and runtime verification of approved paths | true | false | false | 2026-08-26T00:00:00Z | git:main:c10f557;docs/architecture/action-gateway/ |
| COST_AGENT_LAST | Cost / Agent-Last architecture | cost attribution, usage measurement and deterministic execution | H0 | ACTIVE | cost/watchdog lineage merged; usage telemetry remains shadow | MERGED | validate live usage/cost and decide enforcement progression | true | false | true | 2026-08-26T00:00:00Z | git:main:c10f557;docs/governance/MAINTENANCE_AUDIT_LEDGER.md |
| ARCHITECTURE_AUTHORITY_BOUNDARIES | Architecture authority / execution boundaries | capability, operation identity and execution authority | H0 | ACTIVE | static authority boundaries reconciled; runtime evidence is separate | MERGED | deployed-SHA and runtime-authority verification | true | false | false | 2026-08-26T00:00:00Z | git:main:c10f557;docs/governance/MAINTENANCE_AUDIT_LEDGER.md |
| NO_NEW_ARCHITECTURAL_DEBT | No-new-architectural-debt enforcement | blocking guards for new architectural debt | H0 | CLOSED | A1–A5 blocking posture established and CI-wired | WIRED | normal monitoring only | false | false | false | 2026-08-26T00:00:00Z | git:main:c10f557;docs/governance/NO_NEW_ARCHITECTURAL_DEBT_POSTURE.md |
| SCHEMA_DATA_CONTRACTS | Schema / Data Contracts | static schema and data-contract consistency | H0 | ACTIVE | #2/#3 statically reconciled; live schema/contract verification remains | MERGED | live schema / contract verification | true | false | false | 2026-08-26T00:00:00Z | git:main:c10f557;docs/governance/MAINTENANCE_AUDIT_LEDGER.md |
| MAINTENANCE_PROGRAM | Maintenance structural cleanup program | numbered audit closure and deferred/runtime governance | H0 | CLOSED | 0 open numbered audits and 0 current owned static gaps | MERGED | monitor only deferred/runtime triggers | true | false | false | 2026-08-26T00:00:00Z | git:main:c10f557;docs/governance/MAINTENANCE_AUDIT_LEDGER.md |
| TEST_CI_HYGIENE | Test / CI / verification hygiene | fidelity, coverage and blocking verification guards | H0 | CLOSED | #8/#9 closure and CI enforcement recorded | WIRED | normal monitoring only | false | false | false | 2026-08-26T00:00:00Z | git:main:c10f557;docs/governance/HORIZON.md |
| SECURITY_PERMISSIONS | Security / permissions | formula safety, error-boundary safety and security guards | H0 | CLOSED | static security gaps closed and guard wired into CI | WIRED | production verification only | true | false | false | 2026-08-26T00:00:00Z | git:main:c10f557;docs/governance/HORIZON.md |
| LEAD_CRM_CANONICAL_FLOW | Lead / CRM canonical flow | canonical Lead-to-CRM write and evidence path | H1 | ACTIVE | shared write infrastructure merged; full canary not yet verified | MERGED | live Draft → Approval → Write → Evidence canary | true | false | false | 2026-08-26T00:00:00Z | git:main:c10f557;docs/governance/BOSS_UNIFIED_MASTER_PLAN.md:§3.5 |
| ROADMAP_CORE | `ROADMAP.md` | C/N/F ליבה + באגים | H0 | ACTIVE | ראה Current Execution Status בקובץ עצמו | PLANNED | ראה טבלת Next Actions שם | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:ROADMAP_CORE:migration-explicit-status |
| BOSS_CONTEXT_LIBRARIAN_PHASE_0 | BOSS Context Librarian (mandatory session-bootstrap index) | Documentation / developer tooling only | H0 | ACTIVE | מוזג ל-main (עשרות PRs, כולל תחזוקה אוטומטית שוטפת); `AGENTS.md` מגדיר אותו כ-bootstrap חובה-ידני לכל development agent, ו-`.github/workflows/context-librarian-reconcile.yml` מריץ reconciliation אוטומטי אחרי כל push ל-main (פותח PR לתחזוקה גבולית, נכשל בבירור על OWNER_DECISION_REQUIRED). עד `6a0ba6a`, auto-maintenance ממשיך להוסיף provenance/policy registrations מאושרים מראש סביב Media Probe/N18/Gateway. עדיין index/governance layer בלבד — production code לא מייבא אותו, אינו מקור אמת מקביל (גבול שנשמר, ר' `docs/context_librarian/README.md`). | MERGED | אין שלב-הבא בודד ומתוזמן — תחזוקה שוטפת (auto-maintenance PRs). מ-ROADMAP.md N17 (סעיף 6, נשאר פתוח): multi-session coordination טרם תוכנן; dogfooding עצמי טרם הושלם (רק תכנון VCM מוזג). | true | false | false | 2026-08-21T00:00:00Z | git:main:6a0ba6a |
| F52_UNIFIED_USER_MESSAGES | F52 Unified Approval Runtime — Unified User Messages | Message UX / Approval Runtime | H0 | ACTIVE | R3.2 and R4 are merged/static; R5 gate rejected a new abstraction; F52 remains an active implementation program for UX-01 | MERGED | R6.1 Decision New UX alignment, then re-run uniformity gate; runtime/deployment verification remains separate | true | false | false | 2026-08-28T00:00:00Z | git:main:c8f1ab7;docs/architecture/f52-unified-approval-runtime/README.md;docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md |
| APPROVAL_POLICY_SINGLE_SOURCE | Approval Policy Single Source (F52→C83) | Core/Security | H0 | ACTIVE | ✅ C83 סגור ומאומת — `event_bus.ACTIONS_REQUIRING_APPROVAL` הוא alias טהור ל-`tool_registry.TOOLS_REQUIRING_APPROVAL`, לא רשימה עצמאית (ר' ROADMAP.md §C83). **BUG-077** — root cause וגם תסמין (Tier 3) ✅ **מוזגו ל-main** (PR #254, commit `07caf9d`, מאומת `git merge-base --is-ancestor` על `origin/main`) — `propose_action()` כעת מאמת `requires_approval` מול `tool_registry.needs_approval()`, פרט ל-`self_confirm` carve-out. אימות production: לא נבדק במפורש (ר' `BUG_AUDIT_LOG.md` BUG-077). | MERGED | לאמת בפרוד — ראה `BUG_AUDIT_LOG.md` BUG-077. | true | false | false | 2026-08-18T10:08:28Z | git:main:07caf9d |
| MARKETING_EXECUTION_MAP | `BOSS_Marketing_Execution_Map.md` | Revenue Execution (H1-H2, H5) | H1 | ACTIVE | גל 1 נשאר דורש אימות חי, אבל main התקדם משמעותית: N18 פתח Canonical Write Infrastructure, Lead הוא consumer ראשון, ו־Lead creation/Draft Card/shared draft primitives merged. אין להסיק שה־Revenue loop כולו verified; זהו בסיס כתיבה משותף שצריך canary. | MERGED | להריץ live/staging canary ל־Draft→Approval→Write→Evidence על ה־deployed SHA הנוכחי, ואז להכריע consumer הבא. | true | false | false | 2026-08-21T00:00:00Z | git:main:6a0ba6a |
| DECISION_HUB | Decision Hub | Trust/Decision loop | H3 | ACTIVE | Stage 0-1 merged, flag off, לא verified. **BUG-DH-03/04** (formula injection) 🟡 תוקן בקוד, **✅ ממוזג ל-main** (PR #251, `d51e6be`; תוקן 07/07/2026, רשומה קודמת טענה "טרם ממוזג" בטעות) — `tools/airtable_gateway._safe_formula_param()`, `cmd_decision.py`/`decision_pipeline.py`, `test_bugdh03_04_formula_injection.py` 15/15, ר' BUG_AUDIT_LOG.md BUG-036/BUG-037. **לא מאומת בפרוד.** | MERGED | לא להפעיל `FEATURE_DECISION_HUB` עד production evidence (המיזוג עצמו כבר בוצע) | true | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:DECISION_HUB:migration-explicit-status |
| MEDIA_LAYER_F16 | Media Layer (F16) | Media/Context loop | H4 | ACTIVE | קוד ממוזג, flag off. מאז הסטטוס הקודם: MoneyPrinterTurbo נשאר staging-only; Media Probe POC, Artifact Contract v1, StoredArtifact MIME support, Gateway readiness docs ו־fail-closed gateway canary harness מוזגו עד `6a0ba6a`. אין production activation. | MERGED | לפני כל activation: artifact/hash/path validation, publishing-off invariant, deployed-SHA evidence, ו־rollback/gate checklist. | true | false | false | 2026-08-21T00:00:00Z | git:main:6a0ba6a |
| TASKS_DEADLINES_ROADMAP_TASKS | Tasks/Deadlines/Roadmap_Tasks איחוד | Data model | H0 | ACTIVE | בעבודה בפועל (לא סגור) | UNKNOWN | לעדכן כאן כשנסגר | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:TASKS_DEADLINES_ROADMAP_TASKS:migration-no-explicit-evidence |
| COMMAND_CENTER_KNOWLEDGE_HUB | Command Center / Knowledge Hub | Product UI loop | H6 | ACTIVE | **Command Center כבר התחיל וממוזג:** unified owner read API/UI, owner attention, owner development status, registry validator/reconciliation/projection קיימים על main. **`system_health` UNKNOWN-source hygiene issue — superseded 27/08/2026 (read-only Truth Reset, no code change):** התיאור הקודם (שורה זו, מתוארך ל-`6a0ba6a`/21/08) היה כבר לא נכון בזמן שנכתב — התיקון האמיתי מוזג שלושה ימים קודם לכן, `3e10dbc` (18/08/2026): `tma_api._system_health_payload(identity)` (helper לא-מעוטר) הופרד מ-route ה-`@require_tma_auth`-המעוטר, `core/owner_attention.py`'s `health()` reader קורא לו ישירות, ומאומת ב-`test_owner_attention.py`. `docs/ux/OC_CANONICAL_DATA_SOURCE_AND_ATTENTION_PLAN.md`'s רישום המקורי (16/08) נשאר תקין כרשומת audit היסטורית ("not fixed here" — כפי שנכתב אז) — לא מסמן סטטוס נוכחי, לא נערך. Knowledge Hub remains separate/future. | MERGED | לאמת `/api/owner/command-center` מול deployed SHA, ואז לעדכן UX docs/Command Center status from planning to runtime-gated. | true | false | false | 2026-08-27T00:00:00Z | git:main:3e10dbc;test_owner_attention.py |
| F12_F13_MODEL_PROVIDER_TENANT_CONFIG | F12 vs F13 (Model Provider / TenantConfig overlap) | Architecture | H0 | CLOSED | ✅ סגור — הכרעת בעלים מפורשת (07/07/2026): F13 סופגת את F12, F12 נגנז כתכנון עצמאי. F13 עצמה נשארת DEAD CODE — DO NOT WIRE (ההכרעה קובעת רק איזה תכנון ממשיך, לא מתירה activation). ר' ROADMAP.md §F12/§F13. | UNKNOWN | לוודא שהעדכון ב-ROADMAP.md בוצע בפועל (בוצע 07/07/2026) | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:F12_F13_MODEL_PROVIDER_TENANT_CONFIG:migration-no-explicit-evidence |
| B2_CONTACTS_BRAIN | B2 Contacts Brain | Product | H7 | PLANNED | **PARTIAL** — `tools/contact_resolver.py` קיים בפועל (ranking + disambiguation), אך `CONTACT_RESOLVER` כבוי כברירת מחדל, אין alias/nickname table, אין preferred-channel logic. מקור סמכותי: `docs/audit/C95A_ARCHIVE_CARRY_FORWARD_GAP_REPORT.md` (לא `MASTER_PLAN_v2.md`, שהוא הקשר-כוונה היסטורי בלבד, 25/05/2026, לא קובץ בריפו). | UNKNOWN | להוסיף alias table + preferred-channel לפני שקוראים לזה "done"; להחליט אם להדליק את הדגל | false | false | true | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:B2_CONTACTS_BRAIN:migration-no-explicit-evidence |
| B3_DRAFT_MODE | B3 Draft Mode | Product | H7 | PLANNED | **MISSING כקונספט כללי** — אין מימוש קיים כלל (לא "תלוי ב-B2 בלבד" כפי שנוסח בטעות קודם). `MASTER_PLAN_v2.md`'s `draft_mode.py` (העלה הבעלים, לא קובץ בריפו) הוא הגדרת-כוונה מקורית (25/05/2026), לא SPEC מוכן למימוש. | PLANNED | תלוי בהחלטת בעלים אם הצורך העסקי עדיין קיים; לעצב (לא ad hoc) אם כן | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:B3_DRAFT_MODE:migration-explicit-status |
| B1_QUEUE_WORKERS | B1 Queue/Workers | Infra | H0 | PLANNED | **MISSING לחלוטין** — אפס Redis/RQ/Celery/SQS ב-`requirements.txt`/בקוד. `worker.py` סינכרוני (Render-cron HTTP endpoint), `scheduler.py` thread יחיד חוסם (`schedule` library) — סיכון stall מתועד (`daily_collector.py:15-18`). `MASTER_PLAN_v2.md` הוא הסבר-מקור לרעיון (Redis+RQ), לא תוכנית קיימת. מקור סמכותי: C95A §G. | PLANNED | NEEDS_C95 (C95F) — להכריע אם queue אמיתי נדרש בקנה-מידה הנוכחי, או לתעד ש-`schedule` חד-thread היא בחירה מכוונת | false | false | true | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:B1_QUEUE_WORKERS:migration-explicit-status |
| AIRTABLE_SCHEMA_REFRESH | Airtable Schema Refresh (Snapshot / RuntimeSchemaProvider / Value Validation — SPEC v2 + PR3B rev.2) | Data/Reliability | H0 | ACTIVE | ✅ שלושת ה-PRs (PR3B/PR2/PR3A) ממוזגים ל-`main`. למצב runtime עדכני ר' תת-הסעיף "Runtime Capability Status — verified 09/08/2026" למטה באותו מסמך — הוא **מחליף (supersedes)** את הניסוח הקודם כאן: RuntimeSchemaProvider במצב SHADOW (הנתיב אומת, אך הלוגים הנוכחיים לא חושפים provider result/source), Gateway Select-Value Validation אומת בפרוד פעמיים (shadow+enforce), `FEATURE_AIRTABLE_SCHEMA_SNAPSHOT` כבוי כברירת מחדל וטרם אומת בפרוד. | MERGED | להמשיך shadow על טבלאות/שדות נוספים לפני enforce רחב יותר; PR3A טעון manual pre-activation checklist; PR_RESPONSE_CONTRACT (BUG-017 remaining callers) ו-PR3C/PR4 עדיין לא התחילו. **🔒 אין להדליק `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE=enforce` עבור `Leads` עד שמאמתים `get_provider().get_table_contract("Leads")["mode"]=="full"` בנפרד — ר' שורת "SPEC A1" למטה.** | true | false | false | 2026-08-18T10:08:28Z | git:main:183ecdd;git:main:358b3bc;git:main:529e344 |
| SPEC_A1_ATOMIC_FAIL_CLOSED | SPEC A1 (Atomic Fail-Closed — כתיבה חלקית ל-Airtable) | Core/Security | H0 | ACTIVE | ✅ **סגור, ממוזג ומאומת בפרוד** — קוד: PR #296, אימות production חי: PR #297 דרך `verify_a1.py` (סקריפט חד-פעמי, נמחק אחרי השימוש). ה-fail-closed guard (`dropped = set(fields)-set(clean)`) קיים ב-`tools/airtable_gateway.py`; ריצה חיה ב-Render אישרה חסימת HTTP מלאה לפני יציאה עבור payload מעורב (שדה תקין+שדה בעייתי) בשלושה מתוך ארבעה מקרים (unknown field / malformed linked-record / read-only field). **ממצא צדדי לא-פתור:** ערך select לא-חוקי ל-`Leads.status` אינו נבדק כלל (לא ספציפי ל-SPEC A1 עצמה — תלוי ב-PR2/PR3B, ר' `BUG_AUDIT_LOG.md`). | MERGED | A2 (structured error propagation) — registered, טרם התחיל. | true | false | false | 2026-08-18T10:08:28Z | git:main:0ed89e2;git:main:4b9ae60 |
| SPEC_A2_STRUCTURED_ERROR_PROPAGATION | A2 — Structured error propagation (airtable_tools.py / decision_ports.py / providers/airtable_shim.py / core/reasoning_ports.py) | Core/Security | H0 | PLANNED | Registered, טרם התחיל. מטרה: להעביר את ה-`errors` שמחזירה `validate_airtable_fields()` בפועל לקורא/למשתמש (לא רק ל-log) — SPEC A1 רק מונע כתיבה חלקית שקטה, לא פותר את "*למה* נכשל". | UNKNOWN | לתכנן scope מדויק לפני התחלה — ר' `BUG_AUDIT_LOG.md` SPEC A1 §סטטוס. | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:SPEC_A2_STRUCTURED_ERROR_PROPAGATION:migration-no-explicit-evidence |
| SPEC_B_ROUTER_PREVIEW_INTEGRITY | SPEC ב' — Router-level (Preview Integrity audit, סעיף ב) | Core/Security | H0 | PLANNED | Registered, טרם נסקר/הוגדר בריפו הזה. הוזכר כממצא-אחות ל-SPEC A1 מתוך אותו audit ("Preview Integrity", סעיפים א/ב) — תוכן מדויק **לא אומת/לא נמצא כמסמך בריפו** נכון ל-10/07/2026; אין להניח scope לפני שמאתרים/מגדירים את המסמך המקורי. | UNKNOWN | לאתר/לשחזר את תוכן "סעיף ב'" לפני שמתחילים לתכנן. | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:SPEC_B_ROUTER_PREVIEW_INTEGRITY:migration-no-explicit-evidence |
| SPEC_PREVIEW_CONTENT_FIX | SPEC Preview Content Fix (Sites #3+#4) | Core/Security | H0 | ACTIVE | ✅ קוד+טסטים מוכנים (`app.py`: `_describe_tool_call`/`_format_field_value`/`_SENSITIVE_FIELD_KEYS`, `approval_response`/`CONFIRMATION_SUFFIX`; `test_preview_content_fix.py` 23/23) — ממתין ל-merge+production verification. ר' `BUG_AUDIT_LOG.md` "SPEC Preview Content Fix (Sites #3+#4)" לפירוט מלא. | CODE_DONE | להריץ Contract Chain אימות production אחרי מיזוג (בדומה ל-SPEC A1/`verify_a1.py`) — לוודא ש-preview באמת מציג ערכים ממוסכים נכון בפרוד, לא רק ביחידה. | true | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:SPEC_PREVIEW_CONTENT_FIX:migration-explicit-status |
| HEBREW_FIELD_NAME_SENSITIVITY | Hebrew Field-Name Sensitivity Audit (מ-`_SENSITIVE_FIELD_KEYS`) | Core/Security | H0 | PLANNED | **טרם התחיל.** מקור: תוך כדי SPEC Preview Content Fix (10/07/2026) התגלה ש-`_SENSITIVE_FIELD_KEYS` המקורי (4 מפתחות אנגליים) פספס לגמרי `ContactFields.PHONE="טלפון"`/`EMAIL="אימייל"` — טופל נקודתית, אבל סריקה מהירה (`grep "^class.*Fields"` + חילוץ קבועים עם תווים עבריים ב-`airtable_schema.py`) העלתה **6/38 מחלקות Field עם שמות שדה בעברית, 45 קבועים בסך הכל** (`DealFields`, `TaskFields`, `DeadlineFields`, `LearningFields`, `ApprovalsFields` — לא רק `ContactFields`), **מתוכם לא סווג אף אחד** כ-PII/מזהה-פנימי מול תוכן עסקי לגיטימי (חשוד במיוחד: `ApprovalsFields.CONTEXT_ID`="מזהה הקשר"/`CONTEXT_DATA`="נתוני הקשר" — עלולים להכיל payload/מזהה פנימי). | PLANNED | audit שיטתי מלא — לסווג כל אחד מ-45 השדות, לעדכן `_SENSITIVE_FIELD_KEYS` בהתאם — לפני שעוד שדה חסר מתגלה בפרודקשן כמו שקרה עם `ContactFields.PHONE`. | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:HEBREW_FIELD_NAME_SENSITIVITY:migration-explicit-status |
| BUG_098_HOTFIX | ✅ BUG-098 hotfix — `_FOLLOWUP_WORDS` substring match | Core/Security | H0 | CLOSED | **סגור, ממוזג ל-main** (PR #301, commit `165bcee`, מאומת `git merge-base --is-ancestor` על `origin/main`). אימות פרוד חי (10/07/2026: הודעות "קומה חמישית"/"קומה שנייה" לא הפעילו יותר את חטיפת ה-batch הישן) מתועד ב-`BUG_AUDIT_LOG.md` BUG-098 — לא שוחזר עצמאית בסשן הזה. 16/16 טסטים. `last_lead_candidate_batch` TTL (הרחבה נלווית) לא מומשה — לא דחוף, התסמין שנצפה נפתר לגמרי בלעדיה. | MERGED | לשקול הוספת TTL בנפרד (עקרוני, לא דחוף) או להשאיר ל-Follow-up 3. | true | false | false | 2026-08-18T10:08:28Z | git:main:165bcee |
| BUG_099_LEAD_EXTRACTION | 🔴 BUG-099 — Lead extraction integrity (`core/ingress_classifier.py`) | Core/Security | H0 | ACTIVE | **שורש מאומת, קוד לא שונה עדיין.** התגלה תוך כדי אימות BUG-098: שם ליד מוחלף בתיאור-נכס ("חדרים קומה ראשונה") כשתיאור ארוך יושב בין השם לטלפון (חלון חילוץ ±80 תווים מעוגן לטלפון, לא לשם) — **אושר עם רשומה אמיתית שנכתבה לפרוד** (`recRvK6hFTNgyj8ag`, Leads). גם תלות ב-multi-line (`_BLOCK_SEP` מבודד טלפון משם → `candidates=0`). **תיקון לדיווח מוקדם יותר**: לא הפסיק הוא הגורם (אומת ב-4 וריאציות) — הסדר (תיאור-לפני/אחרי-טלפון) הוא הגורם. `DeterministicDenial` (`core/router/deterministic_denial.py`) אומת כשכבת-ניסוח מעל `enforce_leads_write_gate` הקיים, לא gate נפרד — חשד "BUG-100" בוטל. ר' `BUG_AUDIT_LOG.md` BUG-099 לפירוט מלא כולל טבלת reproduction. **קובץ נכון לתיקון: `core/ingress_classifier.py`, לא `lead_candidate_handler.py`'s קוד מת.** | UNKNOWN | מפוצל ל-3 תת-items למטה — לא לממש כגוש אחד. | true | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:BUG_099_LEAD_EXTRACTION:migration-no-explicit-evidence |
| BUG_099A_NAME_STOP | ✅ BUG-099a — הרחבת `_NAME_STOP` (אוצר-מילים תיאור-נכס) | Core/Security | H0 | CLOSED | ✅ מוזג ל-main (commit `eb0d731`) — נוספו 24 מילות תיאור-נכס ל-`_NAME_STOP` (קומה/חדרים/floor-ordinals/מרפסת/מטבח/חניה/מעלית/וכו'), מאומת קיים על `origin/main`. אין רשומת "VERIFIED IN PROD" עצמאית ל-099a בפני עצמה, אך אותו קוד-בסיס נבדק חי כחלק מאימות הפרודקשן של BUG-099b (12/07/2026, ר' `BUG_AUDIT_LOG.md`) — לא שוחזר עצמאית בסשן הזה. 9/9 טסטים ייעודיים + רגרסיה מלאה ירוקים בזמן המיזוג. | MERGED | אין שלב פתוח — הורחב ואומת בפועל דרך BUG-099b/BUG-099b.1. | false | false | false | 2026-08-18T10:08:28Z | git:main:eb0d731 |
| BUG_099B_NAME_SEARCH | BUG-099b — הרחבת חיפוש שם מעבר לחלון ±80 סביב הטלפון | Core/Security | H0 | CLOSED | ✅ מוזג ומאומת בפרוד (12/07/2026, ר' `BUG_AUDIT_LOG.md` "BUG-099b — VERIFIED IN PROD"; לא שוחזר עצמאית בסשן הזה). משחזר את השם האמיתי (למשל "יעל רייס") מעבר לחלון ±80 סביב הטלפון, ולא רק דוחה תיאור-נכס כמו 099a. BUG-099b.1 (אותו סבב) תיקן גם מקרה-קצה של קלט-ללא-שם שהפיק candidate שגוי — גם הוא VERIFIED IN PROD. | MERGED | אין שלב פתוח — סגור. | false | false | false | 2026-08-18T10:08:28Z | git:main:32c45c8;git:main:4292845;git:main:c8bd37e |
| BUG_099C_FALLBACK_FORM | BUG-099c — Fallback form כש-LCH נכשל אך Router בטוח ב-create_lead | Core/Security | H0 | CLOSED | ✅ מוזג ומאומת בפרוד (ר' `BUG_AUDIT_LOG.md` "BUG-099c — VERIFIED IN PROD"; לא שוחזר עצמאית בסשן הזה). מומש כ-clarification ("מה שם הליד?"), לא כ-fallback-form קלאסי — כש-LCH לא מוצא שם אבל Router בטוח ב-create_lead, המערכת שואלת במקום לחסום. `enforce_leads_write_gate` לא נחלש — מנותב סביבו למסלול המאושר. תלוי מראש ב-BUG-106 (session lookup דטרמיניסטי), שבוצע קודם באותו PR ואומת גם הוא. | MERGED | אין שלב פתוח — סגור. | false | false | false | 2026-08-18T10:08:28Z | git:main:7f54a16 |
| BUG_099_FOLLOWUP_DOMAIN | Follow-up (BUG-099) — domain inconsistency בין בדיקות דומות | Core/Security | H0 | PLANNED | Registered, טרם נחקר. שלוש בדיקות דומות הפיקו `domain` שונה (finance/general/crm) — ייתכן session state ישן, ייתכן regex-detection תלוי-טקסט. עדיפות נמוכה יחסית ל-BUG-099 עצמו. | PLANNED | לתעד תצפיות נוספות; לא לחקור לפני שסוגרים BUG-099. | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:BUG_099_FOLLOWUP_DOMAIN:migration-explicit-status |
| BUG_099_FOLLOWUP_TRIGGER | Follow-up 1 — הרחבת trigger לזיהוי ליד (טלפון/"ליד"/"צור") | Core/Security | H0 | PLANNED | Registered, טרם התחיל. **לא חלק מ-BUG-098 hotfix** — משנה את תנאי candidate detection עצמו (Tier system), לא רק follow-up matching. דורש Contract Chain נפרדת: (1) grep מול `classify_ingress`/Tier gating הקיים — לוודא שזו לא Dual Mechanism מול לוגיקת ה-Tier הקיימת שכבר מחליטה מתי phone-only מספיק; (2) בדיקת false-positive הפוך — טלפון שמוזכר בהקשר לא-קשור-לליד (ספק/חשבונית/תזכורת) עלול להיתפס כ-lead candidate בטעות. | PLANNED | Contract Chain מול Tier system לפני כל מימוש. | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:BUG_099_FOLLOWUP_TRIGGER:migration-explicit-status |
| BUG_099_FOLLOWUP_ESCALATION | Follow-up 2 — escalation-to-Agent path לשערי pre-Agent (`_handle_batch_followup` וכדומה) | Core/Security | H0 | PLANNED | Registered, טרם התחיל. **תגלית ארכיטקטונית**: `_handle_batch_followup()` (וכל gate דומה שרץ לפני ה-Agent, כמו LCH כולו) בנוי כ-"match → return" בלבד — אין path של "לא בטוח → העבר ל-Agent". זה לא עקבי עם העיקרון המתועד ב-`intent_router.py:4` ("Rule-based קודם, LLM רק כשאין ודאות") — היום, גם כש-rule-based לא בטוח, אין דרך מובנית להעביר את ההחלטה ל-Claude; ה-gate פשוט מחזיר תשובה (נכונה או שגויה) בלי אפשרות אחרת. | PLANNED | לעצב מנגנון escalation גנרי לשערי pre-Agent — לא ספציפי ל-LCH בלבד. | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:BUG_099_FOLLOWUP_ESCALATION:migration-explicit-status |
| BUG_099_FOLLOWUP_SESSION | Follow-up 3 — Session selection non-determinism + correlation ID | Core/Security | H0 | PLANNED | Registered, טרם התחיל. מ-BUG-098: `_load_from_db`/`_find_best_session_in_db` (`session_store.py`) בלי `sort` מפורש, טבלת Sessions בלי שדה Status (אין סינון done/resolved), `_find_best_session_in_db` לא נעול תחת `_create_lock`. בנוסף: אין correlation ID עקבי (`update_id`/`message_id` לא נרשמים ברמת INFO) דרך inbound→session→tool→outbound. לא הגורם הישיר ל-BUG-098 אבל risk אמיתי נפרד. | PLANNED | audit + עיצוב sort דטרמיניסטי, ואולי שדה Status ב-Sessions; לתכנן correlation ID scheme. | false | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:BUG_099_FOLLOWUP_SESSION:migration-explicit-status |
| BUG_PENDING_APPROVAL_B | ✅ BUG-PENDING-APPROVAL-B — Pending Approval Context Safety | Core/Security | H0 | CLOSED | **✅ סגור במלואו, VERIFIED IN PROD (12/07/2026)** — שרשרת 4 PRs (#311-#314), כל אחד מוזג רק אחרי שבדיקה חיה חשפה את הפער הבא: state fields+reconfirmation logic (#311) → global ingress context gate על כל webhook, לא רק `run_agent()` (#312) → Telegram idempotency key = event identity, לא טקסט (#313) → FSM חסום-סיבוב-אחד ל-reconfirmation חוזרת + קבלת-ביצוע עם תיאור עסקי (#314). לוג פרודקשן מילולי מלא (12/07) מוכיח את כל השרשרת יחד. ר' `ROADMAP.md`/`BUG_AUDIT_LOG.md` BUG-108/BUG-PENDING-APPROVAL-B. | UNKNOWN | סגור — אין המשך נדרש. | true | false | false | 2026-08-16T00:00:00Z | BOSS_UNIFIED_MASTER_PLAN.md:§3.5:BUG_PENDING_APPROVAL_B:migration-no-explicit-evidence |
| U1_UNDERSTANDING_LAYER | U1 — Understanding Layer Architecture Decision | Core/Architecture | H0 | CLOSED | Resolved at architecture/static level: do not build a new general Understanding Contract authority, competing Interaction Envelope authority, or PendingAction Store; reuse Core Reasoning, ActionContracts/DraftFlow, ActionGateway, Turn Coordinator, MessageContract, and channel adapters | MERGED | No standalone U1 implementation; continue under the approved UX-01/F52 path | false | false | false | 2026-08-28T00:00:00Z | git:main:c8f1ab7;docs/audit/PROGRAM_DEPENDENCY_STATUS_DRIFT_AUDIT_20260828.md |
| UX_01_UNIFIED_BOSS_EXPERIENCE | UX-01 — Unified BOSS Experience | Product/UI (H6 Product UI) | H6 | ACTIVE | Implementation in progress through F52 / Single-Speaker Approval UX; UX-01 remains the canonical identity and is not replaced by F52 | MERGED | R6.1 Decision New UX alignment, then re-run uniformity gate; program completion remains pending | true | false | false | 2026-08-28T00:00:00Z | git:main:c8f1ab7;ROADMAP.md;docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md |
| HERMES_INTERNAL_ARCHITECTURE_LEARNINGS | Hermes Learnings — Internal Architecture Reference Patterns | Core architecture / reference-pattern adoption | H0 | ACTIVE | Umbrella reference-pattern track, not a product/runtime/vertical. Re-audited against `main` `f31858a` (20/08/2026): **Adopted/merged** — ToolAvailability (`tool_registry.py::ToolAvailability`/`get_availability()`, `FEATURE_TOOL_AVAILABILITY_FILTER`, catalogued in `docs/context_librarian/layers/tools.json::layer.tools`); BOSS Doctor (`boss_doctor.py`/`run_doctor()`/`format_report()`, read-only, no repair/mutation — wired to an owner-only `/boss_doctor` Telegram command in `app.py` (`cmd_boss_doctor`), grep-confirmed live on `main`, superseding this doc's own earlier "no command wired yet" note); Memory Architecture spawned its own first-class initiative, see `BOSS_MEMORY_RETRIEVAL` below. **Already covered, not adopted from Hermes** — Approval/Authority: the canonical identity→ActionContract→approval→ActionGateway→evidence chain remains BOSS-owned. **Still deferred** — Channel Adapter (`PARTIAL/DESIGN GAP`: `core/ingress_envelope.py`, Telegram/WhatsApp ingress adapters, `core/output_gateway.py` exist, but no canonical `ChannelEvent → DeliveryRequest/DeliveryResult` contract — grep-confirmed no such contract exists yet); Provider Port (`CONFORMANCE TESTS FIRST`: `providers/interfaces.py` shim exists, active callers remain provider-shaped); Scheduler Safety (`HARDEN WHEN EVIDENCED`); Skills/Playbooks (`READ-ONLY PLAYBOOKS MAY HELP`, no executable-skill authority); Sandbox (`OUT OF CURRENT SCOPE`, grep-confirmed no general shell/code-execution tool surface); Hermes runtime/MCP (`DO NOT ADOPT`/`ARCHITECTURE GAP — PREREQUISITES FIRST`, grep-confirmed zero MCP client/server code on `main`). | MERGED | Continue selective adoption only when a concrete BOSS architecture gap justifies it. Current active child initiative is Memory/Retrieval (`BOSS_MEMORY_RETRIEVAL`); Channel Adapter, Provider Port, Scheduler Safety and Playbooks remain separately gated/deferred. No automatic sequence forcing every pattern to be built. | true | false | false | 2026-08-20T00:00:00Z | git:main:b323b3e;git:main:e8a7dbf;docs/research/HERMES_DEFERRED_PATTERNS_REVISIT_2026-08.md |
| BOSS_MEMORY_RETRIEVAL | BOSS Memory & Retrieval Architecture | Core Memory / Retrieval / Episodic History | H0 | ACTIVE | Real active implementation initiative (not merely a Hermes child note). Re-audited against `main` `f31858a` (20/08/2026), superseding this doc's design draft's own "Status (post-2026-08-18)" note: **Phase 1 — Episodic Capture** (`EpisodicEntry` contract, `EpisodicMemoryRepository`, `core/migrations/003_episodic_entries.sql`) merged (PR #715), and the live `run_agent()` write path (`app.py::_capture_turn_outcome_episodic`, flag `FEATURE_EPISODIC_CAPTURE`, default off) is **now also merged — PR #765, commit `e8a7dbf`, 19/08/2026** — grep-confirmed present on `main`; **not runtime-verified** (flag not confirmed on in any environment). **Phase 2 — Retrieval contract** (`core/memory_retrieval.py`/`core/memory_retrieval_contract.py`) merged, shadow-only — not called from `context.py`/`memory_store.py`/any live turn path. **Phase 2B — scheduled shadow-comparison logging** (`core/memory_retrieval_shadow.py`, `FEATURE_MEMORY_SHADOW_LOGGING`, default off) merged, writes only structured comparison counts, no memory text. **Not done**: additional action/tool-result capture, session/entity canonical IDs, Business Memory provenance/conflict/supersession handling, accumulated shadow evidence, prompt/context cutover, retrieval-policy tuning. Business Memory stays Airtable-owned throughout; Postgres is the Episodic storage substrate. | MERGED | Merge/deploy/runtime-verify Episodic Capture Phase 1, accumulate real episodic data, then evaluate shadow evidence before expanding capture or designing cutover. Do not jump directly to cutover. | true | false | false | 2026-08-20T00:00:00Z | git:main:e8a7dbf;docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md;docs/context_librarian/layers/memory.json |

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
| **A. Turn Coordinator TC1–TC7** | `docs/architecture/turn-coordinator/README.md` (canonical current-status); `turn-coordinator-full/GAP_ANALYSIS.md` (gap↔workstream ownership) | Intent ownership, entity resolution, canonical proposal construction, reply ownership, per-action evidence | TC1–TC5: MERGED (TC1 admission gate wired only for CREATE_TASK — UPDATE_TASK/COMPLETE_TASK branch is dead code today). TC6: MERGED (PR #566 `684d299`, PR #569 `d0a8620`). TC7-A: MERGED (PR #573 `c16245c`). **TC7-B1/B1.1: MERGED (PR #583 `7676ca6`, PR #587 `0eafeeb`) — new `core/claim_authorization.py` (`authorize_claim()`), but grep-verified 10/08/2026: zero callers anywhere outside the module's own `__main__` block and its test file; does NOT connect TC7-A's `EvidenceResult` and RP4's `TurnEvidenceSummary` despite the name — BUILT_UNWIRED, target chain in §3.5.2 still not closed.** Separately, PR #579 (`2603b44`, supersedes #576) wired TC7-A's `project_evidence_result()` into RP4 comparison logging under `FEATURE_EVIDENCE_FINALIZER` shadow/enforce — this is RP4 shadow logging, not TC7-B claim authorization. **Superseded 26/08/2026 — TC7-B3 wiring: MERGED (PR #1036, `44fd3605`)** — the three canonical `observe_claim_authorization_shadow()` call sites in `app.py`'s general Agent-loop/branch-A/branch-B response paths now assign the return value and capture `ClaimAuthorizationShadowComparison.authorized` (`= not divergent`, additive property) into `_out_meta["claim_authorization"]` instead of discarding it — the TC7-A/RP4→claim-authorization chain named above as "still not closed" is now closed as an *observable* decision. **Superseded 27/08/2026 (PR #1041, `09935a8`):** the two `core/action_gateway.py`-owned call sites (separate from these three) now also capture the decision — both `approve_with_lifecycle_result()`'s and `_execute_contract()`'s `_finish()` closures call `observe_claim_authorization_shadow()` and enforce RP5, grep-confirmed at `core/action_gateway.py:2081`/`:3234` on current `origin/main` — DEFERRED status closed, does not reopen this row further | `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` — code default `false`; last verified production value **`true`** (09/08/2026, Render dashboard env-var read + live app-log/Telegram transcript, deploy `7dbdddd`); current: not reverified in this pass | TC6: **RUNTIME_VERIFIED** for 3/6 scenarios (09/08/2026 — create→pending, status query, second-create-block; callback-button/RP5-classification/replay still open). TC7-A: unit-tested only, SHADOW-only observability (not wired to `final_reply`). TC7-B1/B1.1/B3: STATIC VERIFIED (unit + AST structural regression, `test_tc7_b3_claim_authorization_wiring.py` 10/10) — MERGED, no production/deployed-SHA runtime verification exists yet, RUNTIME NOT ESTABLISHED | ActionGateway (B); F14/TC5 (F) for entity resolution | See §3.5.3 Next Gates |
| **B. ActionGateway / Approval Runtime** | `docs/architecture/action-gateway/`; `core/action_gateway.py` | Canonical business-action lifecycle + approval + atomic execution ownership | MERGED — `ActionContract`, propose/approve/reject/cancel, BUG-157 CAS fingerprint-claim fix | `FEATURE_ACTION_GATEWAY`/`FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` — code default `false`; last verified production value **`true`** (30/07/2026, `PRODUCTION_30JUL2026_RENDER_VERIFICATION.md`, direct Render env read); current: not reverified in this pass. `FEATURE_ACTION_CONTRACT_PERSISTENCE`/`FEATURE_ATOMIC_CLAIMS` — code default `false`; **no production verification found in either direction** — do not report as off, report as unverified | RUNTIME_VERIFIED for core create/approve/cancel/replay-guard flows (30/07, 07/08) | A32 (D) for evidence validators; TC6 (A) for reply ownership | Staged `FEATURE_ACTION_CONTRACT_PERSISTENCE`/`FEATURE_ATOMIC_CLAIMS` rollout — runbook exists (`docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md`), not executed. Parallel, not a TC7-B blocker |
| **C. RP4/RP5 Evidence Finalizer** | `core/turn_evidence.py`; `RP5_PREFLIGHT_BLOCKER.md` | Per-turn evidence aggregation (RP4) + claim/evidence enforcement (RP5) | RP4: MERGED, actively maintained. **RP5: MERGED 26/08/2026 (PR #1036, `44fd3605`) — supersedes "no PR has ever merged."** `app.py`'s general Agent-loop response path now has a real enforcement block: when `FEATURE_EVIDENCE_FINALIZER=="enforce"` AND the agent's own text asserts execution success AND TC7-B's `.authorized` is `false`, `final_reply` is replaced with `core.anti_hallucination`'s existing `_NO_TOOL_EVIDENCE_FALLBACK` (no new fallback text invented, A32 itself untouched). Coverage: the one general Agent-loop `final_reply` site only. **Superseded 27/08/2026 (PR #1041, `09935a8`):** the two ActionGateway-owned sites (row A) now also enforce, and `mixed`-category claim coverage was added (`test_rp5_evidence_enforcement.py` A6a/A6b/A6c) — neither gap remains | `FEATURE_EVIDENCE_FINALIZER` (three-state off/shadow/enforce) — code default `off`; last verified production value **`shadow`** (28/07/2026, direct Render env read, `SINGLE_SPEAKER_APPROVAL_UX_PRODUCTION_VERIFICATION_PLAN.md`) — **that reading is now 4+ weeks old and must be re-verified, not cited as current**; current: not reverified in this pass. RP5's block only activates on `enforce`; production has never been confirmed at `enforce`, so RP5 is OFF BY DEFAULT / RUNTIME NOT ESTABLISHED in production today regardless of the stale `shadow` reading | RP4: SHADOW (comparison logging vs. live traffic; BUG-139 open unresolved mismatch). RP5: STATIC VERIFIED (17/17 in `test_rp5_evidence_enforcement.py` — pure-predicate, real `app.run_agent()` end-to-end with TC7-B decision spied, and structural proof it sits after A32/is flag-gated/only touches "success" claims) — MERGED, RUNTIME NOT ESTABLISHED, no production/deployed-SHA canary exists for the `enforce` block itself | A32 (D) upstream evidence source; consumes TC7 (A)'s `.authorized` verdict directly — no longer "non-competing by test," now a real consumer | Owner decision: activate `FEATURE_EVIDENCE_FINALIZER=enforce` in production (with re-verification of current flag value first) — the ActionGateway sink design item is closed, see §3.5.3 |
| **D. A32 Anti-Hallucination** | `core/anti_hallucination.py` | Post-hoc claim-detection + response sanitization | MERGED, unconditional | No flag — **ENFORCED**, always live | RUNTIME_VERIFIED (`test_a32_enforcement.py`) | None (foundational) — TC7/RP4/RP5 depend on it, not the reverse | None open — stable |
| **E. F52 Unified Status / MessageContract** | `docs/architecture/f52-unified-approval-runtime/README.md`; `audits/phase-4c/CURRENT_STATE_MAP.md` | Single canonical rendering contract across approval/status surfaces | MERGED — D-001…D-019 decisions, PR1/PR4/PR5/PR6 shadow adapters, D-018 leak fix | `FEATURE_UNIFIED_STATUS_FORMATTER` (three-state off/shadow/on) — code default `off`; last verified production evidence: shadow logging observed live (`[UnifiedStatusFormatterShadow]` entries, 09/08/2026 sampling per `ROADMAP.md` N17 item 4) — **never confirmed `on` anywhere**; current: not reverified in this pass. D-018's tool_name-leak fix is unconditional/live regardless of this flag | SHADOW (log comparison in production); D-018 piece RUNTIME_VERIFIED | TC6 (A) feeds reply-owner; TC7 (A) feeds optional `evidence_status` metadata (non-authoritative, D-013) | F52 rollout prerequisites — parallel track, not a TC7-B blocker |
| **F. F14 Entity Resolution / TC5** | `ROADMAP.md` §F14; `core/router/entity_resolvers.py` | Bounded, identity-scoped entity resolution + Contact find-or-create gate | F14-A1 (PR #568) + F14-B1 (PR #570): MERGED. TC5 framework: MERGED. **F14-B2 (PR #577 `cc67f9f`, 09/08/2026): MERGED** — `find_or_create_contact()` gains `create_writer`; two more live callers route through it (`tools/dispatcher.py`'s `airtable_add`→Contacts path, `tools/approval_actions.py`'s `tma_write` Contacts POST), grep-confirmed. **Superseded 27/08/2026 (F14-B3/B4/B5, commits `82681c8`/`10dee68`/`1e4a9d1`/`ed24a8a`, PR #1042 for the CI-guard slice):** `82681c8` extracted a shared `crm.create_contact_from_fields()` (dedup only — same 3 create callers, no new coverage). `10dee68` is the real expansion: a new `crm.update_contact()` canonical boundary now sits in front of Contact **updates** at `tools/dispatcher.py`'s `airtable_update`→Contacts path and `tools/approval_actions.py`'s `tma_write` PATCH path — both previously called `airtable_patch`/`airtable_update` directly with **zero** dedup/gate logic. `1e4a9d1`/`ed24a8a` hardened `tools/audit_dispatcher_bypass.py`'s CI guard to enforce the new boundary. | Not flag-gated — always-on for all migrated callers | **BUILT_UNWIRED text is now partially stale** — Contact *update* paths, previously fully unguarded, are now gated too, so "other agent-tool paths into Contacts remain unguarded" is narrower than when this row was last written. The interception mechanism itself is **still** the same pattern as before — hardcoded per-table branching inside `tools/dispatcher.py`/`tools/approval_actions.py`, not a generic `ActionGateway`/dispatcher-wide gate — so "not centralized" remains accurate. Whether any Contact write path is still fully unguarded was not re-audited in this pass. | — | Centralized dispatcher/ActionGateway-wide gate (F14-B2's original scope) remains open — parallel track, not a TC7-B blocker |
| **G. Agent Cost / Deterministic Execution** | `cost_monitor.py`, `core/cost_watchdog.py`, `core/usage_telemetry.py` | Measure Claude/Agent token spend; maximize zero-Agent-call routing | MERGED — 3-tier measurement lineage (no duplicate system) | `cost_monitor.py`/`core/cost_watchdog.py` live (write `AI_Usage_Daily`, no flag). `core/usage_telemetry.py`/`usage_events` genuinely SHADOW, confirmed unread by any production code path; PR3 cutover explicitly **owner-blocked** pending real-billing comparison | RUNTIME_VERIFIED (live trigger); usage_telemetry SHADOW | Measures traffic from all other programs; not blocking | POST-TC COST VALIDATION after sufficient post-TC6/TC7 traffic — parallel track, not a TC7-B blocker |
| **H. Durable State (TC8)** | `turn-coordinator-full/GAP_ANALYSIS.md` (BLOCKER rows); `TC8_DURABLE_TURN_STATE.md` | Single durable turn-ownership/concurrency record, replacing 4 coexisting pending/approval stores | **MERGED (PR #585 `a945ee7`, 10/08/2026)** — new `core/turn_state_repository.py` (`TurnStateRepository`) | Not flag-gated — grep-confirmed live/unconditional, called from `app.py`'s `_tc8_claim_contract()`/`_tc8_finish_contract()` at all 4 approve/reject/cancel callback+text sites; fails closed on repository unavailability | **MERGED, live/unflagged.** "Staging verified" (`TC8_DURABLE_TURN_STATE.md`, commit `c7b4d9b`) is asserted prose against staging commit `2750f8ca9b`, no checked-in artifact — not independently confirmed | TC6, TC7-B (A) | Independent artifact-based verification of the staging closure claim; TC10 regression harness (still code-absent) |
| **I. MessageContract full-surface (TC9)** | `turn-coordinator-full/GAP_ANALYSIS.md` (FOLLOW_UP row) | One public composer across Telegram/WhatsApp/TMA | **MERGED (PR #588 `cec3f83`, 10/08/2026)** — `ActionFact`/`GatewayReply` gain MessageContract fields, `_message_contract_for_fact()` builds it unconditionally in `compose_status_reply()`. **Follow-up closed 27/08/2026 (read-only Truth Reset, no code change, no PR):** `_message_contract_for_fact()` now delegates through `core.action_fact_message_adapter.from_action_fact()` (a module not documented in this row before) → `build_message_contract()` → `_state_from_lifecycle()` — confirmed **single** state-computation authority, no competing logic in ActionGateway. `core/evidence_message_adapter.py`/`core/lifecycle_message_adapter.py` remain dormant (zero live callers) but are confirmed to be unused *front doors* to that same `build_message_contract()`, built for `core/turn_coordinator_runtime.py` (a different, already-live producer that does not yet build any MessageContract) — not a second authority, not a TC9 bypass. The `verified_read_only → MessageState.SUCCESS` mapping is confirmed present and **deliberate**, documented in `core/claim_authorization.py`'s own module docstring and pinned by `test_action_fact_message_adapter.py`/`test_message_contract.py` — explicitly not a defect to remediate | `FEATURE_UNIFIED_STATUS_FORMATTER` — code default `off`; construction is live/unconditional but the text-output switch stays gated by this flag (shadow/on). `GatewayReply.contract` has no downstream reader yet (not re-verified in the 27/08 follow-up) | BUILT, live construction, output-gated OFF by default; not runtime-verified as changing user-visible text anywhere. Construction itself: **STAGING RUNTIME VERIFIED (2026-08-10)** per row J's `scripts/verify_tc9_staging.py` evidence (pending/executed/failed/turn_id all confirmed against real staging) — **PRODUCTION NOT ESTABLISHED**; `outcome_unknown` state was never exercised against real staging, isolated-unit coverage only | F52 (E) schema (stable, D-012); TC6/TC7 (A) | Wire `GatewayReply.contract` to an actual consumer; F52 rollout decision. No TC9-owned code change identified as needed |
| **J. Observability closure (TC10)** | `turn-coordinator-full/TC10_OPERATIONAL_VERIFICATION_HARNESS.md` | Verification harness + rollout/rollback gates | **COMPLETE AND VERIFIED (10/08/2026)** — `scripts/run_isolated_regression.py`/`scripts/regression_matrix.py`/`scripts/staging_identity.py` (new), `scripts/verify_tc9_staging.py` (new), `scripts/verify_tc8_staging.py` fixed (no longer runs the full regression matrix against real staging — root cause of the BUG-122 contamination the TC8 handoff described). Not a runtime layer — no ActionGateway/TC7/TC8/TC9/F14/router/approval-policy code touched | N/A — tooling only, no flags | Isolated regression: **RUNTIME_VERIFIED via real CI** — PR #590 commit `2b6ecb3`, `backend-ci` run 31362450916, `FINAL: PASS`, 39/39 callback hardening, 8/8 PR-0C, 11/11 BUG-158, 21/21 full matrix, stable across 2 repeated runs (harness doc §6.2). Staging runtime: **RUNTIME_VERIFIED against real staging (2026-08-10)** — `scripts/verify_tc8_staging.py` (`FINAL: TC8: DONE`, deploy SHA matched) and `scripts/verify_tc9_staging.py` (`FINAL: TC9 STAGING CANARY: DONE` — pending/turn_id/real successful execution/failed/clean cleanup all confirmed) both ran from the actual Render staging shell against real DATABASE_URL/AIRTABLE credentials (harness doc §6.3). Two self-caught bugs found and fixed along the way: an over-broad Telegram credential override (PR #590) and an Airtable-base-id name check that could never pass for any real base (PR #592) — both root-caused from real failures, not assumed | TC8 (H, MERGED), TC9 (I, MERGED) | None — closure gate satisfied |
| **K. PA-01 Structural Enforcement** | `docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md` | Block phantom approval-pending claims lacking structural evidence | MERGED (PR #352, `2be2472`) | `FEATURE_PA01_ENFORCEMENT_STATE` (three-state) — code default `off`; **no production verification found in either direction** — do not report as off, report as unverified | BUILT_UNWIRED — not activated in production | Risk router contract-required-intent table | Does not itself close the TC1 CREATE_TASK-only admission gate — that remains open (see A) |

### 3.5.2 Target Canonical Harness Authority Chain

> **⚠️ Updated 27/08/2026 — the connector links below are now BUILT, but
> still not production-activated.** As of 09/08/2026 this chain was target
> architecture only. **Superseding that as of PR #1036 (`44fd3605`,
> 26/08/2026):** TC7-B now consumes TC7-A's `EvidenceResult`-derived
> `evidence_status` and RP4's `TurnEvidenceSummary`-derived
> `legacy_response_claim` together (via
> `core.claim_authorization_shadow.compare_claim_authorization_shadow()`),
> producing a real `.authorized` verdict that `app.py` captures on every
> general-Agent-loop/branch-A/branch-B turn; RP5 now consumes that verdict
> to block an unauthorized execution-success claim, replacing it with A32's
> existing no-tool-evidence fallback. Both are **STATIC VERIFIED / MERGED /
> RUNTIME NOT ESTABLISHED** — RP5's block only fires when
> `FEATURE_EVIDENCE_FINALIZER=="enforce"`, and production has never been
> confirmed at `enforce` (see row C), so **the chain is wired but currently
> inert in production**. **Superseded 27/08/2026 (PR #1041, `09935a8`):** the
> two `core/action_gateway.py`-owned call sites are now also inside this
> connected chain (both enforce the same predicate) — no call site remains
> outside it.
> Treat every arrow below as "connected in code," not yet "observed active
> in production."

```
Ingress/Identity → Intent Ownership/Routing (TC1) → Entity Resolution (TC5/F14)
  → Canonical Proposal (TC2/TC4) → ActionContract/Approval Runtime (ActionGateway)
  → Atomic Execution → Execution Evidence (TC7-A, MERGED, standalone)
  → Turn Evidence Aggregation (RP4, MERGED, standalone)
  → Claim Authorization (TC7-B, MERGED — PR #1036, wired into app.py's 3 canonical call sites)
  → Evidence Enforcement (RP5, MERGED — PR #1036, gated FEATURE_EVIDENCE_FINALIZER=enforce, OFF by default)
  → Reply Ownership (TC6, ✅ live)
  → Rendering/MessageContract (F52/TC9, construction live/unconditional, staging-verified 2026-08-10)
  → Observability/Cost (Cost program/TC10)
```

Live/verified today, independent of this target chain: TC6 reply ownership
(RUNTIME_VERIFIED), A32's claim-detection/sanitization gate (ENFORCED,
unconditional — today's actual, only, claim-admission mechanism *in
production*; RP5 is a second, code-complete but not-yet-activated
mechanism sitting after it, not a replacement for it).

### 3.5.3 Next Gates (Core Harness) — ordered

1. ~~TC6 documentation closure~~ — ✅ **done** (PR #574, `612a119`, 09/08/2026).
2. ~~TC7-A review corrections and merge gate~~ — ✅ **done** (PR #573, `c16245c`, 09/08/2026).
3. ~~TC7-B claim-authorization wiring~~ — ✅ **done** (PR #1036, `44fd3605`, 26/08/2026): `authorize_claim()`'s verdict is now captured at all 3 canonical `app.py` call sites via `_out_meta["claim_authorization"]`. STATIC VERIFIED / MERGED / RUNTIME NOT ESTABLISHED — no production activation performed or claimed. **The two `core/action_gateway.py`-owned sites are also closed — ✅ done (PR #1041, `09935a8`, 27/08/2026)**, no longer unwired.
4. ~~RP5 enforcement~~ — ✅ **implementation done** (PR #1036, `44fd3605`, 26/08/2026): `app.py`'s general Agent-loop path now blocks an unauthorized execution-success claim when `FEATURE_EVIDENCE_FINALIZER=="enforce"`. STATIC VERIFIED / MERGED / RUNTIME NOT ESTABLISHED / **OFF BY DEFAULT** — the flag has never been confirmed at `enforce` in production, and this pass did not activate it. **(c) the two ActionGateway sink sites and (d) `mixed`-claim coverage are also now done (PR #1041, `09935a8`, 27/08/2026)**, `core/action_gateway.py:2081`/`:3234` and `test_rp5_evidence_enforcement.py` A6a/A6b/A6c. Remaining: (a) re-verify `FEATURE_EVIDENCE_FINALIZER`'s actual current production value (last read `shadow`, 28/07/2026, now stale), (b) owner decision on activating `enforce` — neither reopens the current RP5 slice.
5. ~~TC8 durable turn state~~ — ✅ **merged** (PR #585, `a945ee7`, 10/08/2026), live/unflagged; staging-verified claim not independently confirmed (see row H).
6. ~~TC9 MessageContract full-surface integration~~ — ✅ **merged** (PR #588, `cec3f83`, 10/08/2026), construction live, output still gated off by `FEATURE_UNIFIED_STATUS_FORMATTER`. **Follow-up closed 27/08/2026** — read-only Truth Reset confirmed no duplicate state-authority and no code gap remains on TC9's owned path (see row I); no PR opened, no code changed.
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

### 3.5.5 Hermes ↔ Memory relationship (added 20/08/2026)

`HERMES_INTERNAL_ARCHITECTURE_LEARNINGS` is the source of selected
architectural learnings, not the owner of BOSS Memory. `BOSS_MEMORY_RETRIEVAL`
is a first-class BOSS initiative in its own right — it must not remain merely
a subtask of Hermes.

```text
HERMES_INTERNAL_ARCHITECTURE_LEARNINGS
        ↓ selective reference patterns
        ├── ToolAvailability          adopted
        ├── BOSS Doctor               adopted
        ├── Memory Architecture       spawned active BOSS initiative (BOSS_MEMORY_RETRIEVAL)
        ├── Channel Adapter           deferred/gap
        ├── Provider Port             deferred
        ├── Scheduler Safety          gated hardening
        ├── Read-only Playbooks       optional/deferred
        └── Sandbox / Hermes runtime  not adopted
```

This does not create a competing registry or a new roadmap — both initiatives
are rows in the same §3.5 Active Work Registry above, and
`docs/research/HERMES_DEFERRED_PATTERNS_REVISIT_2026-08.md` /
`docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md` remain the
design/evidence references this section summarizes.

### 3.5.6 TC7-B + RP5 wiring, TC9 follow-up closure (27/08/2026)

**Truth Reset SHA:** `origin/main` `bdcd078e3e8499567a6980da442570848723d1c5`.

**TC7-B (rows A) + RP5 (row C):** PR #1036 (`44fd3605`, merged 26/08/2026)
wired `authorize_claim()`'s verdict into `app.py`'s 3 canonical response-path
call sites (`_out_meta["claim_authorization"]`) and added RP5's evidence
enforcement block (blocks an unauthorized execution-success claim under
`FEATURE_EVIDENCE_FINALIZER=="enforce"`, replacing it with A32's existing
`_NO_TOOL_EVIDENCE_FALLBACK`). Both:

```
TC7-B — STATIC VERIFIED / MERGED / RUNTIME NOT ESTABLISHED
RP5   — STATIC VERIFIED / MERGED / RUNTIME NOT ESTABLISHED / OFF BY DEFAULT
```

Explicitly not closed by this PR, tracked separately, does not reopen either
row: the two `core/action_gateway.py`-owned call sites that compute
authorization but do not propagate it into a parallel sink
(`DEFERRED — DESIGN DECISION REQUIRED`); RP5 coverage of `mixed`-category
claims (`DEFERRED`); RP5 production activation (owner decision, not
attempted). Test evidence: `test_tc7_b3_claim_authorization_wiring.py`
(10/10), `test_rp5_evidence_enforcement.py` (17/17), plus a 16-suite
regression run (`test_tc7_b1_claim_authorization.py`,
`test_tc7_b2_claim_authorization_shadow.py`, `test_a32_enforcement.py`,
`test_pa01_phantom_approval_enforcement.py`, `smoke_tests.py`,
`test_integration.py`, and others) — all green, no regression.

**TC9 (row I):** a same-day (27/08/2026) read-only follow-up re-verified
`_message_contract_for_fact()` against current `origin/main` and found the
concern it was asked to check — a duplicate MessageContract state authority
between ActionGateway and the `evidence_projection.py`/
`evidence_message_adapter.py`/`lifecycle_projection.py`/
`lifecycle_message_adapter.py` cluster — **does not exist**:
`_message_contract_for_fact()` delegates through `core.action_fact_message_adapter.from_action_fact()`
(added since the 10/08/2026 pass that wrote row I, not previously documented
here) to the same single `build_message_contract()`/`_state_from_lifecycle()`
authority the other adapters would also use if wired. `evidence_message_adapter.py`/
`lifecycle_message_adapter.py` remain dormant, confirmed built for
`core/turn_coordinator_runtime.py` (a different, already-live producer that
does not yet build a MessageContract), not a competing authority. The
`verified_read_only → MessageState.SUCCESS` mapping is confirmed present and
**deliberate** — documented in `core/claim_authorization.py`'s own module
docstring, pinned by 2 existing tests — not a remediation item.

```
TC9 CORE       — STAGING RUNTIME VERIFIED (2026-08-10) / PRODUCTION NOT
                 ESTABLISHED — outcome_unknown state: isolated-unit only
                 (unchanged from row J; not re-walked in this pass)
TC9 FOLLOW-UP  — ALREADY RESOLVED (no gap found, no code changed, no PR)
```

No PR opened for the TC9 portion — nothing to merge. This note only updates
this registry; it does not re-litigate or re-run the underlying TC7-B/RP5/TC9
work.

### 3.5.7 ActionGateway RP5 sink closure + cross-program status reconciliation (27/08/2026)

**Truth Reset SHA:** `origin/main` `5135a69e2c3a57247b025b5c0aeeb2d14fe68264`.

**Supersedes §3.5.6's "explicitly not closed by this PR" list** — the two
items it named as `DEFERRED` were closed the same day by a follow-up PR that
§3.5.6 predates:

- **ActionGateway sink propagation (row A):** PR #1041 (`14068d6`, merge
  `09935a8`, 27/08/2026) added the same RP5 enforcement predicate used at
  `app.py`'s canonical path to both `core/action_gateway.py`-owned sinks —
  `approve_with_lifecycle_result()`'s and `_execute_contract()`'s `_finish()`
  closures — grep-confirmed present at `core/action_gateway.py:2081` and
  `:3234` on current `origin/main`.
- **`mixed`-category claim coverage (row C):** closed in the same PR —
  `test_rp5_evidence_enforcement.py` gained checks A6a/A6b/A6c proving
  `mixed`/`mixed_with_unknown` evidence with a "success" legacy claim is
  blocked, and `mixed` evidence with a non-"success" claim (e.g. `"mixed"`)
  is never blocked.

```
ActionGateway sink propagation — STATIC VERIFIED / MERGED / RUNTIME NOT ESTABLISHED
mixed-claim coverage           — STATIC VERIFIED / MERGED
```

New test file `test_tc7_b_rp5_gateway_sink_enforcement.py` (13/13) plus a
regression sweep (`test_rp5_evidence_enforcement.py` 20/20,
`test_tc7_b3_claim_authorization_wiring.py` 10/10,
`test_tc7_rp5_gateway_execution_shadow.py` 85/85, `test_a32_enforcement.py`,
`test_pa01_phantom_approval_enforcement.py`, `test_action_gateway.py`,
`smoke_tests.py`) — all green, no regression, all re-run in an isolated
worktree off `origin/main` before merge.

**Only remaining Turn Coordinator/RP5 item:** owner decision to activate
`FEATURE_EVIDENCE_FINALIZER=enforce` in production (with re-verification of
its current value — last read `shadow`, 28/07/2026, now stale). RP5 stays
OFF BY DEFAULT; no runtime/production activation performed or claimed by
this note.

**Same-pass reconciliation (read-only, no code change) found and corrected**
five separate locations in §3.5/§3.5.1/§3.5.2/§3.5.3 above still describing
the two ActionGateway sinks and mixed-claim coverage as open a full day
after PR #1041 closed them — all five updated in this same pass. Also
corrected in the same pass: `HORIZON.md`'s Turn Coordinator row (same stale
claim), and §3.5.1 row F (F14-B3/B4/B5 — Contact *update* paths, previously
fully unguarded, are now gated too via a new `crm.update_contact()`
boundary; the interception mechanism itself is still not a generic
ActionGateway-wide gate, so row F's "not centralized" framing stays
accurate even as its specific caller-count/coverage claim was updated).

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
