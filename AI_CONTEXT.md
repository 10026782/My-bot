# AI CONTEXT

**Updated:** 21/08/2026
**Sources:** ROADMAP.md (canonical, last updated 21/08), CHANGELOG.md (through 20/08), `git log origin/main` through `ce44fba`

> Read this before anything else. Compressed briefing, not exhaustive documentation.
> **"Merged" != "deployed" != "production-verified."** Owner holds field details.

## 1. Executive Summary

- **CORE v1 COMPLETE & READY TO FREEZE** (formal freeze = owner decision, not declared). No blocking gaps; Layer 2 `TurnCoordinator` formal class unbuilt, de-facto substituted by `router.py`. Canonical source: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`.
- **Main advanced materially after the prior briefing:** local `origin/main` is now `ce44fba` (21/08/2026), including the Governance/Horizon refresh. Treat older "planned/not started" wording in planning docs as historical unless reconciled in `ROADMAP.md` / `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md`.
- **H6 Command Center is ACTIVE / MERGED, not planned:** unified owner Command Center API/UI, owner attention, and owner development projections are present on main; runtime/deployed SHA still needs fresh verification.
- **N18 Phase 2 in progress:** Canonical Write Infrastructure has Lead as the first consumer; shared write primitives were extracted to `core/structured_command.py` and `core/draft_flow.py`, multi-field draft validation is wired, and confirm/cancel dispatch is unified. Ready for terminal-turn-result contract and later writer consolidation.
- **F23 Marketing Bridge M1+M2:** verified in production 12-13/08 against real Airtable records. Separate non-blocking finding: `BUG-164` creative ideas factual grounding; prompt defense added via `_DEMAND_FIDELITY_RULE`. TMA screen remains unbuilt.
- **H4 Media/Gateway progressed but remains gated:** MoneyPrinterTurbo is staging-gated; Media Probe POC, Artifact Contract v1, StoredArtifact MIME support, gateway readiness docs, and fail-closed gateway canary harness are merged. No production activation without explicit gate evidence.

## 2. Current System State

**Operational / Owner-Observed Live:**
- Identity -> Router -> Context -> Agent core pipeline; deterministic task routing for `create_task` / `update_task` / `complete_task`, ambiguity fails closed to Agent.
- Airtable gateway: single centralized write path with normalization, read-only filtering, linked-record coercion, and audit logging.
- Approval flow: Telegram confirmation words, TMA buttons, TC8 turn-state, and fail-closed exception path; callbacks re-enforce identity.
- WhatsApp inbound: Twilio signature validation live; Meta receiver wired receive -> identity -> `run_agent`.
- Emergency Stop: five durable Airtable-backed flags.
- F23 M1/M2: `/marketing_new` wizard and `/marketing_status` command verified against real production records.
- Daily digest, Finance Pulse, payment reminder, Game/TMA checkin persistence, task writes, and approval integration are live on known paths.
- My Work owner task visibility: owner verified production screen recovered from 0 tasks to 19 immediate + 77 upcoming after Owner linked-record fixes.

**Merged / Code Complete, Not Fully Production-Verified:**
| Item | Status |
|------|--------|
| **BUG-164 creative-grounding defense** | Prompt-level guardrails added to 3 free-text brief tasks. Deterministic routing fixed the original `creative_ideas` root path earlier. Local tests pass; no fresh live AI call verified for the prompt-contract defense. |
| **BUG-051-FU** | Router correctly routes `create_contact`; Catalog matching improved. Needs live/staging canary on current deployed SHA. |
| **Tool Catalog DB Phase 2** | Deferred relation support and capability filtering merged; no production impact until UI ships. |
| **H6 Command Center** | API/UI/read projections merged. Needs deployed-SHA route verification. Known hygiene issue: `system_health` attention source can degrade to `UNKNOWN`. |
| **N18 Lead/shared write primitives** | Broad code/test progress; no unified production canary yet for full Draft -> Approval -> Write -> Evidence chain. |
| **Lead Capture / Scoring / Memory / Followup** | Code present and operationally connected, but product flags default off (`LEAD_CAPTURE`, `LEAD_SCORING`, `LEAD_MEMORY`, `FOLLOWUP_AUTOMATION`). Activation requires owner env-var decision and canary. |
| **Approval Receipts** | Returned from approval execution and persisted in code; Activity Feed display UI not yet built. |
| **WhatsApp Outbound** | Meta Cloud API approval pending; honest stub in code. Twilio outbound works; Meta receiver works. |
| **TMA Stubs** | Personal Mode, Assets, Activity Feed, Recruitment UX return `coming_soon`. |
| **Memory Durability** | Lead memory + episodic memory are not fully durable/cut over. PostgreSQL integration and runtime policy remain pending. |
| **Media/Gateway stack** | MPT staging E2E and Media Probe/Gateway canary harness are merged; production remains off/not authorized without artifact/hash/path/publishing gates. |

**Shadow/Gated / No Operational Impact:**
- TC7-B1, RP4/RP5 evidence shadow (`FEATURE_EVIDENCE_FINALIZER` off).
- BOSS Memory/Retrieval: episodic capture and retrieval/shadow components merged, flags default off/shadow-only; no runtime cutover.
- Context Librarian CI/reconciliation gates are governance signals, not product runtime behavior.

**Blocked / Deferred (Owner Decision):**
- Layer 2 TurnCoordinator formal class: de-facto replaced by `router.py`; formalization deferred until post-CORE-freeze.
- Decision Hub / H3 activation: stage 0-1 merged/flag-off; do not activate without owner decision and production evidence.
- WhatsApp Outbound via Meta: awaiting Meta Cloud API approval.
- Memory Durability: blocks full lead-memory and learning-system activation.
- FINANCIAL_COMMITMENT_GATE activation: shadow mode; blocked on 7-14 days zero-false-positive validation.
- `lead_qualifier` state machine: dead code with no live callers; decide wire or remove after N04/N18.

## 3. Completed Since 20/08/2026

- **N18 Phase 2, Slice 3:** Confirm/Cancel Dispatch Unification - `should_prefer_lead_draft()` now computed once per turn instead of 3 times. New end-to-end test through `app.run_agent()`.
- **N18 Phase 2, Slices 1-2:** Shared Write Primitives extracted: `core/structured_command.py` trigger/delimiter and `core/draft_flow.py` filling/edit/review state machine, both pure/no I/O. Multi-field draft validation loop wired with Lead test coverage; genericity proven via synthetic draft-flow tests.
- **Canonical Lead Creation / My Work:** Phase 1 Lead creation service and Owner linked-record fixes merged; owner observed My Work production recovery.
- **F23 M1 Live Regression:** production `/telegram` webhook test against real Demand record (`recfrUEj6e7uHEEf9`) proved free-text intake was captured by `cmd_marketing`, not leaked to Agent.
- **Artifact/Gateway/Media:** StoredArtifact MIME support, Artifact Contract v1, gateway readiness docs, Media Probe POC, and fail-closed staging gateway canary harness merged through PR #804.
- **Governance:** Horizon refresh landed in PR #808; `AI_CONTEXT.md`, `ROADMAP.md`, `CHANGE_CONTROL_LOG.md`, and `docs/governance/*` now record H6 active/merged, H1/N18 active, and H4 staging-gated.

## 4. Next Priorities

1. **H0 Production Truth:** capture current deployed SHA and run one live/staging canary set for BUG-164, BUG-051-FU, Tool Catalog DB Phase 2, Command Center route, and N18 Draft -> Write path.
2. **N18 Phase 2, terminal-turn-result contract:** formalize what a successful/failed lead-candidate turn returns to the caller, enabling systematic error reporting and UX branching instead of silent Agent fallback.
3. **H6 Command Center Hygiene:** verify `/api/owner/command-center` against deployment, fix or formally register the `system_health` UNKNOWN source, and keep Command Center read-only.
4. **N18 Phase 3, Canonical Writers Consolidation:** after the terminal-turn-result contract, extract Lead-specific draft/approval/final-write handling into reusable writer strategies.
5. **H4 Production Gate:** keep MoneyPrinterTurbo, Media Probe, and Gateway behind explicit artifact/hash/path/publishing-off gates before any production activation.
6. **F23 M2 TMA Screen:** build the demand intake/review/creative ideas/production handoff UI; not part of the verified Telegram slice.
7. **Production Flag Activation:** owner call only - `LEAD_CAPTURE`, `LEAD_SCORING`, `LEAD_MEMORY`, `FOLLOWUP_AUTOMATION`, `FINANCIAL_COMMITMENT_GATE`, `FEATURE_EVIDENCE_FINALIZER`, and `FEATURE_UNIFIED_STATUS_FORMATTER`.
8. **Memory Durability & Episodic Integration:** wire shadow logging, PostgreSQL backing, and eventual `core/memory_retrieval.py` production policy.
9. **TMA Receipt Persistence:** build Activity Feed display for approval receipts.
10. **Governance Split Discipline:** keep Track D confined to `AI_CONTEXT.md`, `ROADMAP.md`, `CHANGE_CONTROL_LOG.md`, `docs/governance/*`, and `docs/context_librarian/*`; runtime/UI/media changes belong to their owning tracks.

## Reference

- **Canonical CORE audit:** `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`
- **Current program map:** `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5.1
- **Horizon continuation audit:** `docs/governance/HORIZON_STATUS_AND_NEXT_STEPS_AUDIT_20260821.md`
- **N18 full detail:** ROADMAP.md "N18 - Canonical Write Infrastructure" section
- **F23 audit:** `BOSS_MEDIA_MARKETING_AUDIT.md` + CHANGELOG.md F23 entries
- **Feature flag registry:** `feature_flags.py` module docstring
