# AI CONTEXT

**Updated:** 01/09/2026
**Truth Reset:** `origin/main` = `894320409a67df992afedeb70aae8e76fdfd00d1`
**Sources:** `ROADMAP.md`, `docs/governance/HORIZON.md`, `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md`, `BOSS_CURRENT_STATE.md`, and `docs/architecture/CURRENT_SYSTEM_EXECUTION_MAP.md`
**Read this before anything else.** Compressed briefing for all AI agents — not exhaustive documentation.  
**"Merged" ≠ "deployed" ≠ "production-verified."** Owner holds field truth.

---

## 1. Executive Summary

- **CORE v1 COMPLETE & READY TO FREEZE** — no blocking gaps; freeze remains owner decision per `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`.
- **N18 Phase 3 now in progress** — canonical lead writer cutovers (PRs #823/828/831) landed 23/08, routing WhatsApp/email/furniture/voice inbound through unified write path vs. agent. Non-interactive lead path now live-gated.
- **F23 Marketing Bridge verified in prod** (12-13/08) — `/marketing_new` wizard, `/marketing_status` live; non-blocking creative-grounding finding (BUG-164) has prompt defense added.
- **Free Worker Pilot v1.1 hardened** (PR #827/833) — boundary execution safety, forbidden-file change detection live.
- **Schema v1 Track B complete** (22/08) — business outcome fallback scaffold removed; tier field data cleanup confirmed; one legacy status option cleared from Leads.

## 2. Current System State

**Operational (Owner-Observed Live Today):**
- Identity → Router → Context → Agent deterministic pipeline.
- Airtable gateway: single write path, read-only filtering, linked-record coercion, audit logging.
- Approval flow: Telegram/TMA buttons, TC8 turn-state, fail-closed on exception.
- Inbound: WhatsApp via Twilio (signature-validated) + Meta receiver; deterministic lead routing via `core/whatsapp_lead_cutover.py` (feature-gated, new).
- Emergency Stop: five durable Airtable-backed flags.
- `core/action_gateway.py` is active for ingress context/prefetch, proposal deduplication, and several unconditional callers. `FEATURE_ACTION_GATEWAY` specifically controls enforcement strength for the general-agent path; it is not a global dormant/shadow switch.
- Voice has a canonical writer wrapper, but its default flag leaves the legacy direct-write path reachable; the legacy path lacks canonical Owner/dedup/scope behavior. Activation and canary proof precede retirement.
- `commercial_crm.py` is now statically wired through `crm_create_deal`, `crm_create_payment_term`, and `crm_create_payment` (PR1153), but has no production canary and no first-class TMA Deal/Payment surface.
- PR1153 also fixed the reasoning Contacts adapter and retimed `audience_report` to 08:05; the former broken-import and 08:00 collision findings are historical/code-done, while the Sunday 08:30 collision remains open.
- Meta outbound has no real send implementation. `META_OUTBOUND_ENABLED` alone never enables delivery; this is structurally adapter-gated.
- The current frontend is TMA/mobile-oriented. Contact, Deal/Payment, Knowledge, task-lifecycle, and Media browse/detail surfaces are not currently available; desktop admin is a separate product decision.
- Daily digest, Finance Pulse, payment reminders, Game/TMA persistence, task writes all live.

**Code Complete / Merged Since 22/08:**

| Item | Status | Evidence |
|------|--------|----------|
| **N18 Phase 3: Canonical Lead Writers** | CODE COMPLETE | PRs #823/828/831 merged; `core/source_owner_mapping.py`, `core/whatsapp_lead_cutover.py` wired; non-interactive path routing via unified writer factory. Feature-flagged (off by default for WhatsApp/email). |
| **Free Worker Pilot v1.1** | CODE COMPLETE | PR #827/833 merged; boundary hardening (forbidden-file hash detection, gitignore-aware state checks). Execution safety validated. |
| **Schema v1 Track B Cleanup** | CODE COMPLETE | Fallback scaffold removed (PR #825/821); `_is_invalid_option_error`, `option_fallback` logic deleted from gateway; tier/outcome field options cleansed at Airtable UI; one legacy "ליד חדש" status migrated. Zero test regression (37/37 airtable_gateway). |
| **Context Librarian Auto-Maintenance** | CODE COMPLETE | PR #821 merged; bounded auto-registry refresh + policy-pre-approved registration updates. |

**Partially Implemented / Code Present, Not Fully Deployed:**
- **N18 Phase 2 (Slices 1-5):** Shared Write Primitives (`structured_command.py`, `draft_flow.py`) extracted; confirm/cancel unified; multi-field validation end-to-end tested. No fresh canary since merge.
- **BUG-164 Creative-Grounding:** Prompt defense (`_DEMAND_FIDELITY_RULE`) added to free-text brief tasks; deterministic route already fixed separately. Needs fresh live AI call verification.
- **Lead Capture/Scoring/Memory/Followup:** All code operationally wired; product flags default off. Activation requires owner env decision + canary.
- **H6 Command Center:** API/UI live; route verification against current SHA needed. Known: `system_health` can degrade to `UNKNOWN`.
- **H4 Media/Gateway:** MoneyPrinterTurbo E2E staging-verified; Artifact Contract v1, gateway readiness merged — no production without explicit hash/path/publishing-off gates.

**Shadow / Zero Impact:**
- TC7-B1, RP4/RP5 evidence shadow (`FEATURE_EVIDENCE_FINALIZER` off).
- Episodic memory (`BOSS_MEMORY_*` off/shadow-only).

**Blocked (Owner Decision):**
- Layer 2 TurnCoordinator formal class (de-facto replaced by `router.py`).
- Memory durability blocks full lead-memory + learning activation.
- FINANCIAL_COMMITMENT_GATE shadow mode (7-14 days zero-false-positive validation).

---

## 3. Completed Since 22/08/2026

- **N18 Phase 3 foundational code:** Source owner mappings, WhatsApp canonical cutover, non-interactive writer consolidation (email/furniture/voice). All feature-gated, off by default pending activation decision.
- **Free Worker hardening:** v1.1 boundary execution safety, forbidden-file state tracking merged.
- **Schema cleanup:** Outcome fallback removal, legacy status migration, tier field observations confirmed.
- **Context Librarian:** Auto-maintenance registration refresh live.

---

## 4. Next Priorities

1. **N18 Phase 3 Activation Canary:** Owner decision on `WHATSAPP_CANONICAL_LEAD_WRITE`, `VOICE_CANONICAL_LEAD_WRITE`. Fresh inbound test against live Airtable. (`EMAIL_CANONICAL_LEAD_WRITE`/`FURNITURE_CANONICAL_LEAD_WRITE` removed 27/08/2026 — never consumed by any live code; Email/Furniture Lead creation already runs unconditionally through `create_lead()`.)
2. **H0 Production Truth:** Deploy the latest approved/current main SHA, record the actual deployed SHA, and run canaries for N18 Phase 3 activation, BUG-164 creative-grounding, Command Center route verification, lead product-flag readiness against that deployed SHA.
3. **N18 Phase 4:** Terminal-turn-result formal contract implementation (broader scope, shared across all write flows).
4. **H6 Command Center:** Verify `/api/owner/command-center` route on current SHA, resolve `system_health` `UNKNOWN` source, maintain read-only posture.
5. **Lead Product Flags:** Owner decision on full `LEAD_CAPTURE`, `LEAD_SCORING`, `LEAD_MEMORY`, `FOLLOWUP_AUTOMATION` activation.
6. **F23 M2 TMA Screen:** Build demand intake/creative ideas/handoff UI.
7. **Memory Durability:** PostgreSQL + episodic policy wire-up for production.

---

## Reference

- **CORE audit:** `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`
- **N18 detail:** ROADMAP.md "N18 — Canonical Write Infrastructure"
- **Phase 3 work:** PRs #823, #828, #831 (phase3-lead-writer-cutovers, phase3-whatsapp-lead-cutover, phase3-email-furniture-voice)
- **Feature flags:** `feature_flags.py` docstring
