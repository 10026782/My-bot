# BOSS Bot — ROADMAP

עודכן: 28/08/2026

## תחזוקת המסמך

- `ROADMAP.md` מכיל מצב נוכחי וניווט בלבד; פירוט היסטורי שייך למסמכי history/archive.
- לכל פריט יש מקור קנוני מפורט אחד. Snapshot היסטורי ישן אינו גובר על ראיה חדשה.
- טענות runtime/deployment דורשות evidence מפורש; מיזוג או בדיקה מקומית אינם הוכחת production.
- פריט שגדל מעבר לתמצית מפוצל למסמך קנוני ייעודי, ולא מורחב כאן ללא גבול.
- Program ID הוא זהות יציבה; `ROADMAP` מתאר current state; Horizon והמסמך הקנוני
  מתארים phases פנימיים; archive שומר narrative היסטורי.
- טבלת ה־registry משתמשת רק ב־`PLANNED`, `IN_PROGRESS`, `MERGED_STATIC`,
  `DEPLOYED`, `RUNTIME_VERIFIED`. כל שורה פעילה מפנה למקור מפורט אחד.

## 1. Current System Status

המערכת נמצאת במצב **IN_PROGRESS**: תשתיות הליבה,
ה־Turn Coordinator, ה־ActionGateway, מסלולי הכתיבה הקנוניים ו־Command Center
מוזגו, אך מרבית היכולות עדיין דורשות אימות deployed-SHA/runtime. אין להסיק
הפעלת feature flag, deployment או production behavior ממסמך תכנון או מטסט מקומי.

CORE v1 מסומן **COMPLETE / READY TO FREEZE**, אך הכרעת ה־freeze נשארה החלטת
owner משום שה־formal Layer 2 TurnCoordinator עדיין אינו שלם. פירוט והסתייגויות:
[`CORE_COMPLETION_AUDIT_20260810.md`](docs/audit/CORE_COMPLETION_AUDIT_20260810.md).

## 2. Active Programs

| ID | Canonical Name | Status | Evidence | Next | Canonical Source |
|---|---|---|---|---|---|
| TURN_COORDINATOR_PROGRAM | Turn Coordinator | IN_PROGRESS | MERGED_STATIC — TC7-B/RP5 coverage recorded in HORIZON | Decide RP5 activation and verify deployed-SHA | [`HORIZON.md`](docs/governance/HORIZON.md) |
| UNIFIED_APPROVAL_ACTIONGATEWAY | Unified Approval / ActionGateway | IN_PROGRESS | MERGED_STATIC — lifecycle and approval paths | Verify approved paths in runtime | [`HORIZON.md`](docs/governance/HORIZON.md) |
| N18 | Canonical Write Infrastructure | IN_PROGRESS | MERGED_STATIC — Lead consumer and current slice recorded | Continue gated write-flow sequence | [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) |
| LEAD_CRM_CANONICAL_FLOW | Lead / CRM canonical flow | IN_PROGRESS | MERGED_STATIC — canary not verified | Run Draft → Approval → Write → Evidence canary | [`HORIZON.md`](docs/governance/HORIZON.md) |
| MEDIA_LAYER_F16 | Media Layer (F16) | IN_PROGRESS | MERGED_STATIC — staging-gated assets | Run gated deployed-SHA canary | [`HORIZON.md`](docs/governance/HORIZON.md) |
| COMMAND_CENTER_KNOWLEDGE_HUB | Command Center / Knowledge Hub | IN_PROGRESS | MERGED_STATIC — endpoint verification pending | Verify endpoint | [`HORIZON.md`](docs/governance/HORIZON.md) |
| BOSS_MEMORY_RETRIEVAL | BOSS Memory & Retrieval Architecture | IN_PROGRESS | MERGED_STATIC — retrieval remains shadow-only | Accumulate shadow evidence before cutover | [`BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md`](docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md) |
| DECISION_HUB | Decision Hub | IN_PROGRESS | MERGED_STATIC — activation evidence pending | Verify before activation | [`HORIZON.md`](docs/governance/HORIZON.md) |
| F52_UNIFIED_USER_MESSAGES | F52 Unified Approval Runtime — Unified User Messages | IN_PROGRESS | MERGED_STATIC — refreshed Single-Speaker plan established | Continue the current implementation program under its plan | [`SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md`](docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md) |

### Turn Coordinator / RP5

Status: IN_PROGRESS.
Current phase: TC7-B ו־RP5 כוללים גם את שני sinks של ActionGateway ואת כיסוי `mixed`.
Evidence: PR #1041, `09935a8`, לפי HORIZON.
Runtime: NOT ESTABLISHED; RP5 כבוי כברירת מחדל.
Next: החלטת owner על `FEATURE_EVIDENCE_FINALIZER=enforce` ואימות deployed-SHA.
Blocked by: runtime evidence והחלטת הפעלה.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`](docs/architecture/turn-coordinator/TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md).

### Unified Approval / ActionGateway

Status: IN_PROGRESS.
Current phase: canonical lifecycle, approval ו־execution paths.
Evidence: current program map and approval audits.
Runtime: NOT ESTABLISHED כאן.
Next: verify approved paths on the deployed SHA.
Blocked by: explicit production evidence.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`f52-unified-approval-runtime/README.md`](docs/architecture/f52-unified-approval-runtime/README.md).

### N18 — Canonical Write Infrastructure

Status: IN_PROGRESS — Lead הוא consumer ראשון של shared write infrastructure.
Current phase: Phase 3 slice 1 (Telegram Lead preview) is recorded as closed; later phases remain sequenced.
Evidence: [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) §3.5 and N18 records.
Runtime: end-to-end Draft→Approval→Write→Evidence not established כאן.
Next: continue only after the applicable approval/evidence gates.
Blocked by: staged sequencing and live canary evidence.
Canonical source: [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md), [`f52-unified-approval-runtime/README.md`](docs/architecture/f52-unified-approval-runtime/README.md).

### Lead / CRM Canonical Flow

Status: IN_PROGRESS — live verification pending.
Current phase: shared write path and canonical Lead flow are available.
Evidence: HORIZON major program map; schema status is tracked separately.
Runtime: NOT ESTABLISHED.
Next: run the approved end-to-end canary.
Blocked by: deployed/runtime evidence and any live schema checks.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`MAINTENANCE_STATUS_MATRIX.md`](MAINTENANCE_STATUS_MATRIX.md).

### Media / H4

Status: IN_PROGRESS — staging-gated.
Current phase: Media Probe, artifact contract and gateway canary assets exist.
Evidence: HORIZON major program map.
Runtime: production activation NOT ESTABLISHED.
Next: run the deployed-SHA canary only after the documented gates pass.
Blocked by: artifact/hash/path/publishing-off gates and production evidence.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`GATEWAY_CUTOVER_READINESS_20260820.md`](docs/architecture/f52-unified-approval-runtime/rollout/GATEWAY_CUTOVER_READINESS_20260820.md).

### Command Center / H6

Status: IN_PROGRESS — endpoint verification pending.
Current phase: read-only API/UI and registry projection exist.
Evidence: HORIZON records the `system_health` source correction as historical merged evidence.
Runtime: deployed-SHA endpoint behavior NOT ESTABLISHED כאן.
Next: verify the endpoint in the relevant environment.
Blocked by: direct deployed/runtime evidence.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md).

### Memory & Retrieval

Status: IN_PROGRESS — shadow/retrieval expansion remains gated.
Current phase: episodic capture and retrieval contracts are merged; retrieval remains shadow-only.
Evidence: [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) runtime capability registry.
Runtime: flag activation and live behavior NOT ESTABLISHED.
Next: accumulate shadow evidence before any cutover or expansion.
Blocked by: live evidence, policy decisions and canonical provenance work.
Canonical source: [`BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md`](docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md), [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md).

### Decision Hub / Distribution

Status: IN_PROGRESS — activation/canary evidence pending.
Current phase: Decision Hub safety work and canonical distribution mapping exist.
Evidence: [`HORIZON.md`](docs/governance/HORIZON.md).
Runtime: NOT ESTABLISHED.
Next: verify before enabling or expanding activation.
Blocked by: owner decisions and production verification.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md).

## 3. Open Architecture / Owner Decisions

### U1 — Understanding Layer Architecture

Status: PLANNED for the broader architecture; owner decision required.
Decision required: הרחבת המנגנונים הקיימים או בניית Understanding Contract כללי חדש.
Why it matters: ההחלטה קובעת את מבנה ה־clarification/status/error messages ואת סדר העבודה.
Blocks: UX-01.
Canonical source: [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) §3.5, [`BUG_AUDIT_LOG.md`](BUG_AUDIT_LOG.md) BUG-104.

### RP5 Production Activation

Status: PLANNED; implementation is not an activation decision.
Decision required: האם ומתי להפעיל `FEATURE_EVIDENCE_FINALIZER=enforce` בסביבת production.
Why it matters: enforcement changes the handling of unauthorized success claims.
Blocks: production rollout claim for RP5.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`RP5_PREFLIGHT_BLOCKER.md`](RP5_PREFLIGHT_BLOCKER.md).

## 4. Deferred / Blocked

### UX-01 — Unified BOSS Experience

Reason: intentionally waits for U1; the canonical plan says not to redesign message wording before the understanding-layer decision.
Owner: owner decision / product architecture.
Revisit condition: U1 is resolved and Pending Approval remains stable.
Canonical source: [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) §3.5, [`SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md`](docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md).

### Single-Speaker Approval UX

Status: IN_PROGRESS.
Reason: the refreshed plan is established, while later phases and runtime rollout remain sequenced work.
Owner: F52 / Turn Coordinator owner.
Revisit condition: complete the next permitted phase with its own evidence; no runtime claim is implied by the plan.
Canonical source: [`SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md`](docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md).

### Queue / Worker Architecture

Reason: requirement and scheduler ownership are not established.
Owner: product/architecture owner.
Revisit condition: explicit requirement and scheduler decision.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md).

### Generic Draft Capability

Reason: no generic capability is claimed without a confirmed business requirement.
Owner: product owner.
Revisit condition: requirement confirmation and scope decision.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md).

## 5. Canonical References

- [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) — שכבת התכנון וה־registry המאוחדים.
- [`HORIZON.md`](docs/governance/HORIZON.md) — מפת סטטוס ניהולית מתמשכת.
- [`MAINTENANCE_STATUS_MATRIX.md`](MAINTENANCE_STATUS_MATRIX.md) — סטטוס audit/maintenance וא evidence.
- [`BOSS_CURRENT_STATE.md`](BOSS_CURRENT_STATE.md) — תמונת מצב תפעולית משלימה.
- [`SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md`](docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_UNIFIED_TELEGRAM_WHATSAPP_PLAN.md) — מקור Single-Speaker UX.
- [`BUG_AUDIT_LOG.md`](BUG_AUDIT_LOG.md) — יומן ראיות והיסטוריית audit; אינו מחליף את תקציר המצב כאן.
- [`archive/ROADMAP_HISTORICAL_ARCHIVE_20260828.md`](archive/ROADMAP_HISTORICAL_ARCHIVE_20260828.md) — snapshot מלא של ROADMAP לפני הניקוי; HISTORICAL בלבד.

המספור והפרטים ההיסטוריים של C/N/F נשמרו ב־snapshot הארכיוני ובמסמכים הקנוניים
הייעודיים. אין להשתמש בפסקאות מתוארכות מהארכיון כדי להסיק מצב נוכחי ללא אימות
מול המקור הקנוני העדכני.
