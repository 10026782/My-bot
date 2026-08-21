# Horizon Status and Next Steps Audit

**Date:** 21/08/2026
**Baseline:** `origin/main` `6a0ba6a`
**Scope:** Governance handoff snapshot for splitting the next work across four non-overlapping agent tracks.

This document records the working audit that preceded the Governance refresh. It is a continuation map, not an implementation authorization and not a replacement for `ROADMAP.md` or `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md`.

## 1. Current Horizon Status

| Horizon | Current status | Priority | Notes |
|---|---|---|---|
| H0 - Truth Reset / Production Verification | ACTIVE | Highest | Needs current deployed SHA and live/staging verification for the latest merged work. |
| H1 - Revenue Loop / Canonical Write | ACTIVE | High | N18 made Lead the first consumer of shared write primitives. Needs end-to-end canary. |
| H2 - Revenue Attribution / Partner Loop | BLOCKED / DEPENDENT | Later | Depends on H1 being stable and verified. |
| H3 - Decision Hub Owner-Only | OWNER DECISION / GATED | Medium | Stage 0-1 merged/flag-off; do not activate without owner decision and production evidence. |
| H4 - Media Layer / MPT / Gateway | ACTIVE / STAGING-GATED | High | MPT staging-only; Media Probe, Artifact Contract, Gateway readiness/canary merged. Production remains gated. |
| H5 - Distribution Gateway | PLANNED / PREP | Later | Should wait for H1/H4 readiness and approval/broadcast safeguards. |
| H6 - Product UI / Command Center | ACTIVE / MERGED | High | Command Center API/UI/projections merged; needs deployed route verification and data-hygiene fix/registration. |
| H7 - Future Business Management | PLANNED | Later | Not a current execution priority. |

## 2. Priority Order

1. H0 Production Truth: verify deployed SHA, flags, and current live/staging behavior.
2. H6 Command Center: verify `/api/owner/command-center`, close or register the `system_health` UNKNOWN source, and keep it read-only.
3. H1/N18: finish the terminal-turn-result contract and verify Draft to Approval to Write to Evidence end-to-end.
4. H4 Media/Gateway: keep MPT, Media Probe, and Gateway behind artifact/hash/path/publishing-off gates.
5. H3 Decision Hub: owner decision before activation.
6. H2/H5/H7: defer until upstream loops are stable and verified.

## 3. Active Blockers

| Blocker | Impact | Owning track |
|---|---|---|
| No current deployed SHA evidence for latest main | Cannot claim production verification for current merged state | Track A |
| BUG-164 / BUG-051-FU / Tool Catalog / N18 lack one unified live canary on current deploy | Merged does not equal verified | Track A |
| Command Center `system_health` source can degrade to UNKNOWN | H6 may look partially unavailable even when system health route works | Track B |
| MPT/Media/Gateway are staging-gated only | No production activation without artifact and publishing gates | Track C |
| Governance docs had stale "planned/not started" wording | Agents may start duplicate work or choose wrong priority | Track D |
| Decision Hub and formal Layer 2 TurnCoordinator still need owner decisions before activation/freeze decisions | H3 and CORE freeze remain governance-gated | Track D |

## 4. Four-Agent Split

The split below is designed so four agents can work in parallel without touching the same files.

### Track A - Production Verification

**Owns only:** `scripts/verify_*`, `docs/audit/*`, `BUG_AUDIT_LOG.md`

1. Capture current deployed SHA and flag state for production/staging.
2. Run focused canaries for BUG-164, BUG-051-FU, Tool Catalog DB Phase 2, Command Center route, and N18 Draft to Write.
3. Record evidence in audit files and bug log without editing runtime code.

### Track B - Command Center / Owner Projection

**Owns only:** `core/owner_attention.py`, `core/owner_development.py`, `core/command_center.py`, `tma_api.py`, `tma-frontend/*`, `tools/dev_registry_*`, related Command Center tests.

4. Fix or formally isolate the `system_health` UNKNOWN source in the owner attention collector.
5. Smoke-test Command Center API/UI states against realistic projection data and keep the surface read-only.

### Track C - Media / MPT / Gateway

**Owns only:** `core/moneyprinterturbo_adapter.py`, `core/external_execution_boundary.py`, `core/external_execution_repository.py`, `core/external_poll_lease.py`, `core/media_probe_adapter.py`, artifact/gateway media tests.

6. Enforce approved-script, script-hash, media-ref, result-artifact, MIME, size, and hash invariants.
7. Build the production-readiness gate: publishing off, local/path isolation, rollback checklist, and explicit activation evidence.

### Track D - Governance / Context

**Owns only:** `AI_CONTEXT.md`, `ROADMAP.md`, `CHANGE_CONTROL_LOG.md`, `docs/governance/*`, `docs/context_librarian/*`

8. Keep Horizon status aligned with `origin/main` and stop stale "planned" language from overriding merged evidence.
9. Resolve Context Librarian owner-decision/freshness signals as governance work, not product regressions.
10. Record owner decisions for H3, Layer 2 TurnCoordinator/freeze, and when H2/H5 may start.

## 5. Hand-Off Rule

Each track must stay inside its file ownership boundary. If a required fix crosses into another track's files, the agent should stop and hand off the finding instead of editing across the boundary.
