# BOSS Bot — ROADMAP

עודכן: 28/08/2026

## תחזוקת המסמך

- `ROADMAP.md` מכיל מצב נוכחי וניווט בלבד; פירוט היסטורי שייך למסמכי history/archive.
- לכל פריט יש מקור קנוני מפורט אחד. Snapshot היסטורי ישן אינו גובר על ראיה חדשה.
- טענות runtime/deployment דורשות evidence מפורש; מיזוג או בדיקה מקומית אינם הוכחת production.
- פריט שגדל מעבר לתמצית מפוצל למסמך קנוני ייעודי, ולא מורחב כאן ללא גבול.

## 1. Current System Status

המערכת נמצאת במצב **ACTIVE / MERGED / טעונת אימות**: תשתיות הליבה,
ה־Turn Coordinator, ה־ActionGateway, מסלולי הכתיבה הקנוניים ו־Command Center
מוזגו, אך מרבית היכולות עדיין דורשות אימות deployed-SHA/runtime. אין להסיק
הפעלת feature flag, deployment או production behavior ממסמך תכנון או מטסט מקומי.

CORE v1 מסומן **COMPLETE / READY TO FREEZE**, אך הכרעת ה־freeze נשארה החלטת
owner משום שה־formal Layer 2 TurnCoordinator עדיין אינו שלם. פירוט והסתייגויות:
[`CORE_COMPLETION_AUDIT_20260810.md`](docs/audit/CORE_COMPLETION_AUDIT_20260810.md).

## 2. Active Programs

### Turn Coordinator / RP5

Status: ACTIVE — MERGED; static verification קיימת.
Current phase: TC7-B ו־RP5 כוללים גם את שני sinks של ActionGateway ואת כיסוי `mixed`.
Evidence: PR #1041, `09935a8`, לפי HORIZON.
Runtime: NOT ESTABLISHED; RP5 כבוי כברירת מחדל.
Next: החלטת owner על `FEATURE_EVIDENCE_FINALIZER=enforce` ואימות deployed-SHA.
Blocked by: runtime evidence והחלטת הפעלה.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`](docs/architecture/turn-coordinator/TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md).

### Unified Approval / ActionGateway

Status: ACTIVE — MERGED; rollout/runtime verification pending.
Current phase: canonical lifecycle, approval ו־execution paths.
Evidence: current program map and approval audits.
Runtime: NOT ESTABLISHED כאן.
Next: verify approved paths on the deployed SHA.
Blocked by: explicit production evidence.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`f52-unified-approval-runtime/README.md`](docs/architecture/f52-unified-approval-runtime/README.md).

### N18 — Canonical Write Infrastructure

Status: ACTIVE — Lead הוא consumer ראשון של shared write infrastructure.
Current phase: Phase 3 slice 1 (Telegram Lead preview) is recorded as closed; later phases remain sequenced.
Evidence: [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) §3.5 and N18 records.
Runtime: end-to-end Draft→Approval→Write→Evidence not established כאן.
Next: continue only after the applicable approval/evidence gates.
Blocked by: staged sequencing and live canary evidence.
Canonical source: [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md), [`f52-unified-approval-runtime/README.md`](docs/architecture/f52-unified-approval-runtime/README.md).

### Lead / CRM Canonical Flow

Status: ACTIVE — MERGED; live verification pending.
Current phase: shared write path and canonical Lead flow are available.
Evidence: HORIZON major program map; schema status is tracked separately.
Runtime: NOT ESTABLISHED.
Next: run the approved end-to-end canary.
Blocked by: deployed/runtime evidence and any live schema checks.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`MAINTENANCE_STATUS_MATRIX.md`](MAINTENANCE_STATUS_MATRIX.md).

### Media / H4

Status: ACTIVE — MERGED; staging-gated.
Current phase: Media Probe, artifact contract and gateway canary assets exist.
Evidence: HORIZON major program map.
Runtime: production activation NOT ESTABLISHED.
Next: run the deployed-SHA canary only after the documented gates pass.
Blocked by: artifact/hash/path/publishing-off gates and production evidence.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`GATEWAY_CUTOVER_READINESS_20260820.md`](docs/architecture/f52-unified-approval-runtime/rollout/GATEWAY_CUTOVER_READINESS_20260820.md).

### Command Center / H6

Status: ACTIVE — MERGED; endpoint verification pending.
Current phase: read-only API/UI and registry projection exist.
Evidence: HORIZON records the `system_health` source correction as historical merged evidence.
Runtime: deployed-SHA endpoint behavior NOT ESTABLISHED כאן.
Next: verify the endpoint in the relevant environment.
Blocked by: direct deployed/runtime evidence.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md).

### Memory & Retrieval

Status: ACTIVE — MERGED; shadow/retrieval expansion remains gated.
Current phase: episodic capture and retrieval contracts are merged; retrieval remains shadow-only.
Evidence: [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) runtime capability registry.
Runtime: flag activation and live behavior NOT ESTABLISHED.
Next: accumulate shadow evidence before any cutover or expansion.
Blocked by: live evidence, policy decisions and canonical provenance work.
Canonical source: [`BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md`](docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md), [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md).

### Decision Hub / Distribution

Status: ACTIVE — MERGED; activation/canary evidence pending.
Current phase: Decision Hub safety work and canonical distribution mapping exist.
Evidence: [`HORIZON.md`](docs/governance/HORIZON.md).
Runtime: NOT ESTABLISHED.
Next: verify before enabling or expanding activation.
Blocked by: owner decisions and production verification.
Canonical source: [`HORIZON.md`](docs/governance/HORIZON.md), [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md).

## 3. Open Architecture / Owner Decisions

### U1 — Understanding Layer Architecture

Status: OWNER_DECISION / UNKNOWN for the broader architecture.
Decision required: הרחבת המנגנונים הקיימים או בניית Understanding Contract כללי חדש.
Why it matters: ההחלטה קובעת את מבנה ה־clarification/status/error messages ואת סדר העבודה.
Blocks: UX-01.
Canonical source: [`BOSS_UNIFIED_MASTER_PLAN.md`](docs/governance/BOSS_UNIFIED_MASTER_PLAN.md) §3.5, [`BUG_AUDIT_LOG.md`](BUG_AUDIT_LOG.md) BUG-104.

### RP5 Production Activation

Status: OWNER_DECISION; implementation is not an activation decision.
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
