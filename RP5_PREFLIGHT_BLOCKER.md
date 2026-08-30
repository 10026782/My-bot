# RP5 Preflight — Blocker & Decisions (17/07/2026)

**Status:** planning/audit only. No code, no schema, no migration, no frontend, no feature flag change in this document or its branch.
**Program:** BOSS Agent Reliability and Permission Hardening — `PR-RP5` (Evidence Finalizer enforcement).
**Source of truth:** `BOSS_AGENT_RELIABILITY_AND_PERMISSION_HARDENING_SPEC.md` §4 R4/R5, delivery-plan row `PR-RP5`; `docs/architecture/f52-unified-approval-runtime/spec/UNIFIED_MESSAGE_UX_STANDARD.md` ("Relationship to RP5 Evidence Contract").

## Owner decision — 30/08/2026

**Decision: CONTINUE SHADOW / KEEP ENFORCE OFF.**

RP5 is accepted as `MERGED_STATIC`, but production activation of
`FEATURE_EVIDENCE_FINALIZER=enforce` is explicitly deferred. Shadow evidence
collection may continue; this decision authorizes no flag change, redeploy, or
runtime behavior change.

Reconsider `enforce` only after review of real production shadow evidence,
including all nine classifications, every `mismatch=true` event, deployed-SHA
identity, canary scope, and rollback to `shadow`/`off`, followed by separate
owner approval.

```text
RP5 STATUS: MERGED_STATIC
SHADOW: CONTINUE
ENFORCE: OFF
ACTIVATION: DEFERRED
```

---

## 1. Finding: RP5 enforcement activation is deferred

At the original preflight snapshot, RP5 (`FEATURE_EVIDENCE_FINALIZER=enforce`
actually changing `final_reply`) could not start: RP4
(`core/turn_evidence.py`, PR #362, `3a3edbe`) was code-complete and fully
unit-tested, but no production shadow evidence had yet been reviewed. This
historical finding does not override the current owner decision above. The
flag remains non-enforcing until the evidence and activation gates pass.

This blocks the spec's own rollout gates: gate 3 (shadow observation) is technically satisfiable but never exercised; gate 4 (canary, "with before/after evidence") has no evidence to point to.

## 2. Shadow activation — scope decision

**Decision: global shadow, no code change.** Set `FEATURE_EVIDENCE_FINALIZER=shadow` on Render for all traffic, not gated to owner/canary identity.

Rationale: shadow mode is provably zero-risk to end users — `observe_shadow_finalizer()`'s only effect is a log line (`[EvidenceFinalizerShadow] ...`); `final_reply` is guaranteed unchanged by RP4's own invariant (enforced by the test suite: `test_shadow_observer_never_alters_final_user_text`). Restricting collection to owner-only traffic would require new identity-gating code (a small PR of its own) and would narrow sample diversity — several classification states (`mixed`, `mixed_with_unknown`, `unverified_effect`, `approval_pending`) are unlikely to occur from manual owner-only testing and are better sampled from real broader usage.

**Action required (outside this session — no Render access here):** an operator with Render dashboard access sets `FEATURE_EVIDENCE_FINALIZER=shadow` in the `my-bot` service's Environment tab and confirms redeploy, per the same manual process already used for other three-state flags in this repo.

## 3. Sample collection plan

`TurnEvidenceSummary.classification()` (`core/turn_evidence.py`) has exactly 9 possible return values. Target: at least one real (non-synthetic) `[EvidenceFinalizerShadow]` log line per state, ideally 3–5, before RP5 can credibly claim "production samples show no regressions."

| State | What produces it | What to verify in the log line |
|---|---|---|
| `no_evidence` | Pure conversation turn, zero tool calls, zero approvals | `response_claim` is `empty` or `neutral` — any other claim is a false-evidence bug |
| `verified_read_only` | Only read tools called (e.g. `airtable_get`, `calendar_get_events`), all verified ok | `response_claim=neutral` — a `success` claim here is a false-positive completion |
| `verified_write_success` | At least one verified mutation (`airtable_add`, `calendar_create_event`), nothing else mixed in | `response_claim=success` — mismatch means a real success failed to be communicated |
| `failure` | A dispatched write/action failed verification, nothing else in the turn | `response_claim=failure` — mismatch means a failure got reported as success (the exact regression class R4 exists to catch) |
| `outcome_unknown` | `DispatcherOutcome` neither completed nor failed (ambiguous provider outcome) | `response_claim=unknown` — never `success` |
| `approval_pending` | A `requires_approval` tool got queued this turn | `response_claim=pending` — never `success`/`executed` (this is the exact bug class already logged in `ROADMAP.md:283-287`, a counter advancing without customer receipt) |
| `unverified_effect` | A warning/ambiguous verifier status, not a clean ok/failed | Rarest — worth a deliberate search; F52's UX doc treats this as its own manual-review state, so real examples matter most here |
| `mixed` | Multiple tool calls in one turn with different outcomes (e.g. one verified write + one failure) | `response_claim=mixed` — collapsing to `success` is the multi-tool-call regression class |
| `mixed_with_unknown` | Same as `mixed`, at least one component is `outcome_unknown` | Same check, `unknown` component present |

`mixed`/`mixed_with_unknown`/`unverified_effect` may need to be deliberately exercised (a turn that both succeeds and fails a tool call) rather than passively waited on, since organic usage may not produce them quickly.

## 4. Architectural decisions

### 4a. RP5 vs. F52 sequencing

**Decision: RP5 waits for F52 PR 1 (Message Contract Foundation).**

`UNIFIED_MESSAGE_UX_STANDARD.md` explicitly designates RP5 as feeding evidence-derived classification into F52's not-yet-built `format_agent_message()` public API, and F52's own doc warns against introducing "a competing formatter." Building RP5's renderer against a target that doesn't exist yet risks throwaway work. This is currently moot in practice — RP5 is blocked on shadow evidence (§1) regardless of this decision, so no immediate action follows from it; it only fixes the *order* of the next two programs once both are unblocked.

### 4b. PA-01 vs. RP5 precedence

**Decision: keep the current code order — PA-01 first.**

`app.py` already runs the PA-01-enforce block (~3151–3159) before the RP4/RP5 evidence-finalizer block (~3161–3179). Rule: if PA-01 already replaced `final_reply` this turn, RP5's future enforce-path only logs/classifies evidence and does not overwrite it — no new precedence logic needed. **Action for the eventual RP5 implementation PR:** add an explicit test asserting this non-overwrite behavior (not present in `test_turn_evidence_shadow.py` today, since RP4 never mutates `final_reply` at all).

## 5. What unblocks RP5

1. Operator sets `FEATURE_EVIDENCE_FINALIZER=shadow` in Render (§2).
2. Real production turns accumulate `[EvidenceFinalizerShadow]` log lines covering the 9 states in §3, with `mismatch=true` lines reviewed as potential real bugs (a mismatch means the model's response claim disagreed with verified evidence — worth investigating each one, not just counting them).
3. Once sample coverage is judged sufficient (owner call, not a fixed number), RP5 implementation can start as its own isolated branch/PR — not combined with RP3/RP6/RP9 or any Phase 4B activation (explicit spec rule) — scoped to §4's two decisions already made.

## 6. Non-goals of this document

No code, no schema/migration/frontend/flag change. This document does not itself activate `FEATURE_EVIDENCE_FINALIZER` — that is a Render-side operator action per §2.
