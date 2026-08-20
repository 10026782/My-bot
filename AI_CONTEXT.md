# AI CONTEXT

**Updated:** 20/08/2026  
**Sources:** ROADMAP.md (canonical), CHANGELOG.md, git log origin/main

> Read this before anything else. Compressed briefing, not exhaustive documentation.
> **"Merged" ≠ "deployed" ≠ "production-verified."** Owner holds field details.

## 1. Executive Summary

- **CORE v1 COMPLETE & READY TO FREEZE** (formal freeze = owner decision). No blocking gaps; Layer 2 TurnCoordinator formal class unbuilt, de-facto substituted by `router.py`. Canonical source: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`.
- **F23 Marketing Bridge:** M1 + M2 VERIFIED IN PROD (12–13/08). BUG-164 prompt-hardening deployed (PR #645, 20/08).
- **Tool Catalog DB Phase 2 (PR #644):** Deferred-relation wiring + capability filtering live (20/08).
- **39 PRs merged (#517–#646)** since production-verified base (`5ec37b8`, PR #516, 09/08). Core changes unblocked; no new production-verification canary.

## 2. Current System State

**✅ Operational (Live in Production):**
- Approval flow: 4 paths (Telegram, TMA, TC8 turn-state, fail-closed).
- Airtable gateway: Single centralized write path, normalization + audit logging.
- Lead pipeline: WhatsApp → Leads record (LEAD_CAPTURE flag-gated, off by default).
- Task routing: Deterministic `create_task`/`update_task`/`complete_task` → TC2; ambiguous → Agent.
- Emergency Stop: Five durable flags (Airtable-backed, survive restarts).
- F23 M1/M2: Marketing intake, 3-idea generation, next-action orchestration, `/marketing_status` command.
- Daily digest: Real data, score/tier field-names corrected.
- Game/TMA: Checkin persistence, task writes, approval integration.

**🟡 Merged, Not Production-Verified (code-correct, awaiting live canary):**
1. **BUG-164 creative-grounding defense (PR #645):** Prompt-level guardrails added to 3 free-text brief tasks. Deterministic routing already fixed BUG-164 root cause in earlier PR; this adds defense-in-depth. Local tests pass; no live AI call verified.
2. **Tool Catalog DB Phase 2 (PR #644):** Deferred relation support, capability-based filtering, Tool Discovery UI preparation. No production impact until UI ships.
3. **BUG-051-FU (PR #647):** Router correctly routes `create_contact` intent; Catalog matching improved.
4. **39 merged PRs (#517–#646):** No single unified production-verification run since 09/08. Core infrastructure changes present; behavioral changes unverified against live traffic.

**🔵 Shadow/Gated (no operational impact):**
- TC7-B1, RP4/RP5 evidence shadow (`FEATURE_EVIDENCE_FINALIZER` off).
- Context Librarian CI gates (governance, not functional).

**⏸ Blocked (Owner decision pending):**
- Layer 2 TurnCoordinator formal class (de-facto replaced by `router.py`).
- BUG-161/162 (deferred).
- BUG-003 (multiple active Worlds — owner DEFERRED).

## 3. Completed Since 19/08/2026

- **BUG-164 PR2 (Marketing creative grounding):** Prompt-level hardening deployed (20/08). Root-cause fix already live; this adds defense. Local verified.
- **Tool Catalog DB Phase 2:** Deferred-relation support, capability-filtering infrastructure. Ready for Discovery UI.
- **Doc reconciliation (PR #646):** Canonical status records updated to 904ce13 (09/08 + earlier PRs 517–641 integrated).

## 4. Next Priorities

1. **Production verification gap:** 39 PRs merged; highest risk: BUG-051-FU (router contact logic), Lead Capture chain (LEAD_CAPTURE/SCORING/MEMORY flags), Tool Catalog Phase 2 integration. Priority: select one subsystem, run live staging canary, verify before next feature merge.
2. **F23 completion:** BUG-164 fix verified; TMA screen (M2 second half) unbuilt.
3. **Layer 2 decision:** Formalize de-facto `router.py` substitution before Phase 3.
4. **TMA Receipt Persistence:** Activity Feed display not implemented.
5. **Documentation parity:** ROADMAP.md now ~9 days ahead; CHANGELOG synchronized (20/08).
