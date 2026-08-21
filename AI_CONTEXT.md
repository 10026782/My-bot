# AI CONTEXT

**Updated:** 21/08/2026
**Sources:** ROADMAP.md (canonical), CHANGELOG.md, `git log origin/main` through `6a0ba6a`

> Read this before anything else. Compressed briefing, not exhaustive documentation.
> **"Merged" ≠ "deployed" ≠ "production-verified."** Owner holds field details.

## 1. Executive Summary

- **CORE v1 COMPLETE & READY TO FREEZE** (formal freeze = owner decision). No blocking gaps; Layer 2 TurnCoordinator formal class unbuilt, de-facto substituted by `router.py`. Canonical source: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`.
- **Main advanced materially after the prior briefing:** local `origin/main` is now `6a0ba6a` (21/08/2026), not the 20/08 snapshot. Treat older "planned/not started" wording in planning docs as historical unless reconciled below.
- **H6 Command Center is ACTIVE / MERGED, not planned:** unified owner Command Center API/UI, owner attention, and owner development projections are present on main; runtime/deployed SHA still needs fresh verification.
- **H1/N18 Canonical Write Infrastructure is ACTIVE:** canonical Lead creation, Lead Draft Card, shared structured-command primitive, shared draft-flow primitive, and confirm/cancel dispatch unification are merged. Lead remains the first consumer; the goal is a shared write framework, not a separate lead system.
- **H4 Media/Gateway progressed:** MoneyPrinterTurbo remains staging-gated; Media Probe POC, Artifact Contract v1, StoredArtifact MIME support, gateway readiness docs, and fail-closed gateway canary harness are merged. Production activation is still gated.

## 2. Current System State

**✅ Operational / Owner-Observed Live:**
- Approval flow: 4 paths (Telegram, TMA, TC8 turn-state, fail-closed).
- Airtable gateway: Single centralized write path, normalization + audit logging.
- Lead pipeline: WhatsApp → Leads record (LEAD_CAPTURE flag-gated, off by default).
- Task routing: Deterministic `create_task`/`update_task`/`complete_task` → TC2; ambiguous → Agent.
- Emergency Stop: Five durable flags (Airtable-backed, survive restarts).
- F23 M1/M2: Marketing intake, 3-idea generation, next-action orchestration, `/marketing_status` command.
- Daily digest: Real data, score/tier field-names corrected.
- Game/TMA: Checkin persistence, task writes, approval integration.
- My Work owner task visibility: owner verified production screen recovered from 0 tasks to 19 immediate + 77 upcoming after Owner linked-record fixes.

**🟡 Merged, Not Production-Verified (code-correct, awaiting live canary):**
1. **BUG-164 creative-grounding defense (PR #645):** Prompt-level guardrails added to 3 free-text brief tasks. Deterministic routing already fixed BUG-164 root cause in earlier PR; this adds defense-in-depth. Local tests pass; no live AI call verified.
2. **Tool Catalog DB Phase 2 (PR #644):** Deferred relation support, capability-based filtering, Tool Discovery UI preparation. No production impact until UI ships.
3. **BUG-051-FU (PR #647):** Router correctly routes `create_contact` intent; Catalog matching improved.
4. **Command Center H6:** API/UI/read projections merged; needs deployed-SHA and live route verification. Known data-hygiene issue remains recorded in `docs/ux/OC_CANONICAL_DATA_SOURCE_AND_ATTENTION_PLAN.md`: `system_health` attention source degrades to `UNKNOWN`.
5. **N18 Lead/shared write primitives:** broad code/test progress, but no unified production canary for the full Draft→Approval→Write→Evidence chain on the current deployed SHA.
6. **Media/Gateway stack:** MoneyPrinterTurbo staging E2E and Media Probe/Gateway canary harness are merged; production remains off/not authorized without explicit gate evidence.

**🔵 Shadow/Gated (no operational impact):**
- TC7-B1, RP4/RP5 evidence shadow (`FEATURE_EVIDENCE_FINALIZER` off).
- Context Librarian CI gates (governance, not functional).
- BOSS Memory/Retrieval: episodic capture and retrieval/shadow components merged, flags default off/shadow-only; no runtime cutover.

**⏸ Blocked (Owner decision pending):**
- Layer 2 TurnCoordinator formal class (de-facto replaced by `router.py`).
- BUG-161/162 (deferred).
- BUG-003 (multiple active Worlds — owner DEFERRED).
- Context Librarian reconciliation may open bounded auto-maintenance PRs; owner-decision failures are governance signals, not product regressions.

## 3. Completed Since 20/08/2026

- **N18 Phase 2:** shared `core/structured_command.py` and `core/draft_flow.py`; Lead consumes `LEAD_DRAFT_SPEC`; confirm/cancel draft dispatch now has one decision point; missing continuous clarification-loop regression was added.
- **Canonical Lead Creation / My Work:** Phase 1 Lead creation service and Owner linked-record fixes merged; owner observed My Work production recovery.
- **Artifact/Gateway/Media:** StoredArtifact MIME support, Artifact Contract v1, gateway readiness documentation, Media Probe POC, and fail-closed staging gateway canary harness merged through PR #804.
- **Context Librarian:** bounded auto-maintenance continues to register approved provenance/policy updates; this is now regular governance maintenance, not a one-off project.

## 4. Next Priorities

1. **H0 Production Truth:** capture current deployed SHA and run one live/staging canary set for BUG-164, BUG-051-FU, Tool Catalog DB Phase 2, Command Center route, and N18 Draft→Write path.
2. **H6 Command Center Hygiene:** verify `/api/owner/command-center` against deployment, fix or formally register the `system_health` UNKNOWN source, and stop treating H6 as "planned" in governance docs.
3. **H1/N18 Completion Gate:** finish terminal-turn-result contract and define when shared write primitives can be reused by the next domain.
4. **H4 Production Gate:** keep MoneyPrinterTurbo/Media Probe/Gateway behind explicit artifact/hash/path/publishing-off gates before any production activation.
5. **D Governance Split:** keep Governance work confined to `AI_CONTEXT.md`, `ROADMAP.md`, `CHANGE_CONTROL_LOG.md`, and `docs/governance/*`; other agents own runtime/UI/media files.
