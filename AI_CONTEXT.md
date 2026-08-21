# AI CONTEXT

**Updated:** 21/08/2026  
**Sources:** ROADMAP.md (canonical, last updated 21/08), BOSS_CURRENT_STATE.md (historical snapshot 26/06, now archive), CHANGELOG.md (through 20/08)

> Read this before anything else. Compressed briefing, not exhaustive documentation.
> **"Merged" ≠ "verified in production."** Owner holds field details.

## 1. Executive Summary

- **CORE v1 COMPLETE & READY TO FREEZE** (formal freeze = owner decision, not declared). No blocking gaps; Layer 2 `TurnCoordinator` formal class unbuilt, de-facto substituted by `router.py`. Canonical source: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`.
- **N18 Phase 2 in progress:** Canonical Write Infrastructure (Lead creation) — shared write primitives extracted to reusable frameworks (`core/structured_command.py`, `core/draft_flow.py`), multi-field draft validation loop wired end-to-end, confirm/cancel dispatch unified (20–21/08). Genericity proven; ready for Phase 3 consolidation + Phase 4 terminal-turn-result contract.
- **F23 Marketing Bridge M1+M2:** Verified in production 12–13/08 against real Airtable records. One separate finding: `BUG-164` (creative ideas factual grounding) — non-blocking for M2 orchestration; prompt defense added (`_DEMAND_FIDELITY_RULE`). TMA screen (second half of M2) not yet built.
- **Lead pipeline operational, flag-gated:** capture → scoring → memory → followup all code-complete, all `off` by default. No production regression; activation requires owner env-var flip.
- **Approval system live, receipts partial:** TMA write endpoints require approval-first (POST /api/projects, PATCH /api/leads, POST /api/followup); receipts returned, Activity Feed display not yet built.

## 2. Current System State

**✅ Operational (Live in Production):**
- **Identity → Router → Context → Agent:** Core pipeline; all 5 intents routed correctly (CREATE_TASK, UPDATE_TASK, COMPLETE_TASK, CREATE_LEAD, AGENT).
- **Deterministic task routing:** Structured phrasing (`create task`, `update task`, `complete task` + date/owner/priority) routes through `Handler.TOOL` deterministically, fail-closed on ambiguity.
- **Airtable gateway:** Single centralized write path; normalizes aliases, filters read-only fields, coerces linked records, audits all operations.
- **Approval flow:** 4 paths (Telegram confirmation words, TMA buttons, TC8 turn-state, fail-closed on exception); re-enforces identity on callback (never trusts stored decision).
- **WhatsApp inbound:** Twilio signature validation live; Meta Cloud API webhook receiver wired (receive → identity → run_agent).
- **Emergency Stop:** 5 durable flags (Airtable-backed, survive restarts), `is_enabled()`/`set_emergency_stop()` live.
- **Daily digest:** Running in production; score/tier field-names correct; hot leads, tasks, open deals, completed tasks all real data.
- **Finance Pulse:** `/api/finance/pulse` reads live Payments/Expenses; `?view=overdue` filters by date (deterministic, not manual status flip).
- **F23 M1+M2:** `/marketing_new` wizard (demand intake → brief → 3 creative ideas) + `/marketing_status` command (demand list + next-action card), both verified against real production records.
- **Payment reminder:** Job registered, sends reminders on schedule (self-test passing).
- **Feature flags:** Runtime + env-backed; emergency flags durable; product flags default-off. Registry in `feature_flags.py` complete.

**🟡 Partial (Code Complete, Not Verified in Production / Flag-Gated Default-Off):**
| Item | Status |
|------|--------|
| **Lead Capture (W0)** | Code: `lead_capture.py::capture_inbound_lead()` creates Leads on unknown WhatsApp. Gated: `LEAD_CAPTURE=false`. |
| **Lead Scoring (N02)** | Code: `lead_capture.py::_score_inbound_message()` + inline scoring on capture. Gated: `LEAD_CAPTURE=true` AND `LEAD_SCORING=true` (both off). Write path verified; live scoring not verified. |
| **Lead Memory (N03–N04)** | Code: `lead_memory.update()` wired after scoring. Gated: `LEAD_MEMORY=false`. Stores domain/channel/contact_name/score/tier/record_id. Not verified. |
| **Followup Automation (N04)** | Code: scheduler `_job_followup_scan()` registered, `followup_engine.py` queues approvals. Gated: `FOLLOWUP_AUTOMATION=false`. Depends on lead_memory. Not verified. |
| **Approval Receipts** | Returned from approval execution, persisted to Interaction Log in code; Activity Feed display UI not yet built. |
| **WhatsApp Outbound** | Meta Cloud API approval pending; honest stub in code. Twilio outbound works; Meta receiver works. |
| **TMA Stubs** | Personal Mode, Assets, Activity Feed, Recruitment UX: code present, return `coming_soon`. |
| **Google Integrations** | OAuth/env required; merge conflicts resolved, imports present, end-to-end wiring incomplete. |
| **Memory Durability** | Lead memory + Episodic memory: RAM-only (not durable). PostgreSQL integration pending. |
| **Learning System** | Mock events; no real production loop. Code present, not active. |

**⏸ Blocked / Deferred (Owner Decision):**
- **Layer 2 TurnCoordinator formal class:** Currently de-facto replaced by `router.py`. Formalization deferred until post-CORE-freeze.
- **WhatsApp Outbound (Meta):** Awaiting Meta Cloud API approval.
- **Memory Durability:** RAM-only; blocks lead-memory + learning systems. Requires PostgreSQL integration.
- **FINANCIAL_COMMITMENT_GATE activation:** In shadow mode (flag=false); blocked on 7–14 days zero-false-positive validation.
- **lead_qualifier state machine:** Dead code (no live callers). Decision: wire or remove after N04.

## 3. Completed Since 20/08/2026

- **N18 Phase 2, Slice 3:** Confirm/Cancel Dispatch Unification — `should_prefer_lead_draft()` now computed once per turn instead of 3 times. New end-to-end test (`test_n18_draft_dispatch_unification.py`) through `app.run_agent()`.
- **N18 Phase 2, Slices 1–2:** Shared Write Primitives extracted (`core/structured_command.py` trigger/delimiter, `core/draft_flow.py` filling/edit/review state machine, both pure/no-I/O). Multi-field draft validation loop wired with test coverage (new `test_lead_service_phase1.py` section 7h, 5 assertions, all 107 Lead tests green). Genericity proven via `test_draft_flow.py` (16/16 synthetic scenarios).
- **F23 M1 Live Regression:** Webhook test against production `/telegram` + real Demand record (`recfrUEj6e7uHEEf9`) — free-text intake ("כן"/"3 שנים") captured correctly by `cmd_marketing`, not leaked to Agent.
- **Documentation:** ROADMAP.md updated through 21/08 with N18 Phase 2 progress + owner sequencing clarification. CHANGELOG.md through 20/08.

## 4. Next Priorities

1. **N18 Phase 2, Slice 4 — Terminal Turn Result Contract** (per owner sequence, after Slices 1–3): formalize what a successful/failed lead-candidate turn returns to caller, enable systematic error reporting + UX branching (not silent Agent fallback).

2. **N18 Phase 3 — Canonical Writers Consolidation** (after Phase 2 contract finalized): extract Lead-specific `_resolve_lead_draft()` + `_handle_lead_approval()` + `_finalize_lead_write()` into reusable `LeadWriter` (same pattern as Task/Approval writers), move schema/validators/prompts into strategy objects, unlock genericity across BOSS.

3. **F23 M2 TMA Screen** (tracked separately, not built yet): build full TMA UI for demand intake, demand review, creative ideas, production handoff.

4. **Production Flag Activation** (owner call, not developer task):
   - Flip `LEAD_CAPTURE`, `LEAD_SCORING`, `LEAD_MEMORY`, `FOLLOWUP_AUTOMATION` to `true` for live lead pipeline.
   - Activate `FINANCIAL_COMMITMENT_GATE` after 7–14 days shadow validation.
   - Activate `FEATURE_EVIDENCE_FINALIZER` for RP4 execution-shadow logging.
   - Activate `FEATURE_UNIFIED_STATUS_FORMATTER` for TC6 reply-owner UX (currently off; note: active in deployed production, but code default is off).

5. **Memory Durability & Episodic Integration** (post-N18): wire unreleased shadow-logging job (`FEATURE_MEMORY_SHADOW_LOGGING`), migrate to PostgreSQL backing, activate `core/memory_retrieval.py` in production.

6. **TMA Receipt Persistence:** Build Activity Feed display for approval receipts (currently returned, not displayed).

---

## Reference

- **Canonical CORE audit:** `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`
- **Current program map:** `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5.1 (core status table)
- **N18 full detail:** ROADMAP.md "N18 — Canonical Write Infrastructure" section
- **F23 audit:** `BOSS_MEDIA_MARKETING_AUDIT.md` + CHANGELOG.md F23 entries
- **Feature flag registry:** `feature_flags.py` module docstring
