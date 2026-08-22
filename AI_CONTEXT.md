# AI CONTEXT

**Updated:** 22/08/2026  
**Sources:** ROADMAP.md (canonical, last updated 21/08), CHANGELOG.md (through 20/08), `git log origin/main` through latest merge  
**Read this before anything else.** Compressed briefing, not exhaustive documentation.  
**"Merged" ≠ "deployed" ≠ "production-verified."** Owner holds field details.

## 1. Executive Summary

- **CORE v1 COMPLETE & READY TO FREEZE** — formal freeze remains owner decision; no blocking gaps documented. Canonical source: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`.
- **Main branch stable:** `origin/main` carries CORE audit, Governance/Horizon refresh, N18 Phase 2 shared primitives (Slices 1-5 complete), and F23 M1+M2 production-verified code.
- **N18 Phase 2 COMPLETE (Slices 1-5):** Shared Write Primitives extracted (`core/structured_command.py`, `core/draft_flow.py`), confirm/cancel dispatch unified, clarification/validation loop wired, and terminal-turn-result contract (narrow form) implemented. Ready for Phase 3 writer consolidation.
- **F23 Marketing Bridge M1+M2 VERIFIED IN PROD** (12-13/08/2026) — all orchestration paths live; non-blocking finding recorded (BUG-164: creative-ideas factual grounding, prompt defense added). TMA screen remains unbuilt.
- **H6 Command Center ACTIVE/MERGED** — owner API/UI deployed; needs fresh route verification on current SHA.
- **H4 Media/Gateway STAGING-GATED** — MoneyPrinterTurbo, Media Probe, Artifact Contract v1, and gateway canary harness merged; no production without explicit gate evidence.

## 2. Current System State

**Operational / Owner-Observed Live:**
- Identity → Router → Context → Agent pipeline; deterministic task routing for create/update/complete.
- Airtable gateway: single write path with normalization, read-only filtering, linked-record coercion, audit logging.
- Approval flow: Telegram confirmation words, TMA buttons, TC8 turn-state, fail-closed exception path.
- WhatsApp inbound: Twilio signature validation; Meta receiver wired (receive → identity → agent).
- Emergency Stop: five durable Airtable-backed flags.
- F23 M1/M2: `/marketing_new` wizard and `/marketing_status` verified on live Airtable records.
- Daily digest, Finance Pulse, payment reminder, Game/TMA persistence, task writes, approval integration live.

**Merged / Code Complete, Not Fully Production-Verified:**
| Item | Status | Notes |
|------|--------|-------|
| **N18 Phase 2, Slices 1-5** | CODE COMPLETE | `structured_command.py`, `draft_flow.py` extracted; confirm/cancel unified; multi-field validation loop wired; narrow terminal-turn-result contract added. No deployed canary yet. |
| **BUG-164 creative-grounding** | PROMPT DEFENSE ADDED | `_DEMAND_FIDELITY_RULE` in free-text brief tasks; deterministic fix already merged separately. Local tests pass; no fresh live AI call verified. |
| **H6 Command Center** | ACTIVE/MERGED | API/UI deployed; route verification against current SHA needed. Known issue: `system_health` can degrade to `UNKNOWN`. |
| **Lead Capture / Scoring / Memory / Followup** | CODE PRESENT | All code operationally wired; product flags default off. Activation requires owner env-var decision + canary. |
| **WhatsApp Outbound** | HONEST STUB | Meta Cloud API approval pending; Twilio outbound works; Meta receiver works. |
| **TMA Stubs** | PARTIAL | Personal Mode, Assets, Activity Feed, Recruitment return `coming_soon`. Approval receipts returned but Activity Feed display not built. |
| **Memory Durability** | PARTIAL | PostgreSQL backing + episodic capture merged; production cutover pending policy decision. |
| **H4 Media/Gateway** | STAGING-GATED | MoneyPrinterTurbo E2E staging-verified; Media Probe/Artifact Contract v1/gateway readiness merged; no production without hash/path/publishing-off gates. |

**Shadow/Gated / Zero Operational Impact:**
- TC7-B1, RP4/RP5 evidence shadow (`FEATURE_EVIDENCE_FINALIZER` off by default).
- Episodic memory capture/retrieval (`BOSS_MEMORY_*` flags off/shadow-only).
- Context Librarian CI gates are governance signals only.

**Blocked / Deferred (Owner Decision):**
- Layer 2 TurnCoordinator formal class: de-facto replaced by `router.py`; formalization deferred post-CORE-freeze.
- Memory durability blocks full lead-memory and learning activation.
- FINANCIAL_COMMITMENT_GATE shadow mode; blocked on 7-14 days zero-false-positive validation.
- `lead_qualifier` state machine: dead code; decide wire or remove post-N04.

## 3. Completed Since 21/08/2026

- **N18 Phase 2, Slices 2-5 finalized:** Shared primitives extracted, multi-field validation end-to-end test added, confirm/cancel unified, terminal-turn-result (narrow) implemented.
- **BUG-164 defense hardened:** Prompt-level rule added to free-text tasks; deterministic route already merged.
- **F23 audit finalized:** Production orchestration verified; non-blocking creative-grounding finding recorded.

## 4. Next Priorities

1. **H0 Production Truth:** Deploy current SHA, run canaries for BUG-164, Command Center route, N18 Draft→Write→Evidence, and lead product-flag activation readiness.
2. **N18 Phase 3:** Canonical Writers consolidation — extract lead-specific draft/approval/write handling into reusable strategies.
3. **H6 Command Center:** Verify `/api/owner/command-center` route, resolve/register `system_health` UNKNOWN source, maintain read-only posture.
4. **H4 Production Gate:** Keep Media/Gateway behind explicit gates before any production activation.
5. **Lead Product Flags:** Owner decision on `LEAD_CAPTURE`, `LEAD_SCORING`, `LEAD_MEMORY`, `FOLLOWUP_AUTOMATION`.
6. **F23 M2 TMA Screen:** Build demand intake/review/creative ideas/production handoff UI.
7. **Memory Durability:** Wire PostgreSQL backing and episodic production policy.
8. **TMA Receipt Display:** Build Activity Feed for approval receipts.

## Reference

- **CORE audit:** `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`
- **Program map:** `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5.1
- **Horizon audit:** `docs/governance/HORIZON_STATUS_AND_NEXT_STEPS_AUDIT_20260821.md`
- **N18 detail:** ROADMAP.md "N18 — Canonical Write Infrastructure"
- **F23 audit:** `BOSS_MEDIA_MARKETING_AUDIT.md` + CHANGELOG.md entries
- **Feature flags:** `feature_flags.py` docstring
