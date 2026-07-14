# F52 — Decision Log

This log records planning decisions for the F52 program. It is not runtime implementation authority until the planning gate is explicitly approved.

## D-001 — Establish F52 as the canonical program name

- Date: 14/07/2026
- Status: Closed
- Decision: Rename the program to **F52 — Unified Approval Runtime Migration and Implementation Program**. Phase 4C remains a historical research identifier only.
- Rationale: The verified scope spans channels, tools, claims, identity, projections, media and background work; it is not a point bug fix.
- Affected documents: `README.md`, all Phase 4C research documents, this log.

## D-002 — All 11 `requires_approval` tools remain in the claim cohort

- Date: 14/07/2026
- Status: Closed
- Decision: Every currently marked `requires_approval` tool requires verified live PostgreSQL execution ownership before provider execution, including `gmail_draft`, `send_followup` and `send_recovery`.
- Rationale: Reclassification is a separate business-policy decision; exceptions would recreate an execution-boundary bypass during migration.
- Affected documents: `research/OPEN_QUESTIONS.md`, `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/MIGRATION_PLAN.md`.

## D-003 — Future policy reclassification is outside F52 migration

- Date: 14/07/2026
- Status: Closed
- Decision: Changing approval requirements for drafts, notifications or low-risk actions is excluded from the F52 migration.
- Rationale: F52 migrates existing policy safely; it does not silently broaden business-policy scope.
- Affected documents: `research/OPEN_QUESTIONS.md`, `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`.

## D-004 — Signed references are opaque, signed, versioned and expiring

- Date: 14/07/2026
- Status: Closed
- Decision: Channel references are transport tokens with action/recipient binding, TTL, version and key-rotation readiness.
- Rationale: UI data must resolve one existing contract and must not reconstruct executable payload.
- Affected documents: `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/MIGRATION_PLAN.md`.

## D-005 — Presentation state uses a separate projection store

- Date: 14/07/2026
- Status: Closed
- Decision: Presentation state is stored outside ActionContract and linked by `contract_id`.
- Rationale: A contract is canonical authority; adapter/provider/message state is replaceable display state.
- Affected documents: `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/MIGRATION_PLAN.md`.

## D-006 — Legacy EventBus compatibility is lookup-only

- Date: 14/07/2026
- Status: Closed
- Decision: A legacy EventBus ID can resolve only an existing unambiguous canonical contract; it can never create, infer, repair or persist one.
- Rationale: Legacy payload is not trustworthy execution authority.
- Affected documents: `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/CUTOVER_PLAN.md`.

## D-007 — AP-36 is a separate narrow hotfix

- Date: 14/07/2026
- Status: Closed — follow-up required
- Decision: AP-36 will move the Meta media enablement/readiness guard before media processing as a separate hotfix.
- Rationale: The hotfix must prevent Drive/Airtable writes while the relevant Meta media path is disabled, without changing approval policy or adding the final typed media handler. It requires a regression test; full media migration remains in the later F52 media workstream.
- Affected documents: `audits/phase-4c/CURRENT_STATE_MAP.md`, `research/MIGRATION_OPTIONS.md`, this log.

## D-008 — Implementation components deploy dark before cutover

- Date: 14/07/2026
- Status: Closed
- Decision: F52 components are deployed dark and pass readiness checks before activation/cutover.
- Rationale: Authority changes require observable staged verification and a rollback boundary.
- Affected documents: `rollout/MIGRATION_PLAN.md`, `rollout/CUTOVER_PLAN.md`, `rollout/ROLLBACK_PLAN.md`.

## D-009 — Rollback never restores direct execution

- Date: 14/07/2026
- Status: Closed
- Decision: Rollback may disable presentation or new proposals, but never restores a direct-execution fallback.
- Rationale: A rollback must not reintroduce the P0 bypass the migration removes.
- Affected documents: `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/ROLLBACK_PLAN.md`.
