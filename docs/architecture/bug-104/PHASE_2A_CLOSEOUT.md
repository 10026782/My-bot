# BUG-104 — Core Reasoning Activation Program — Phase 2A Closeout

**Official name:** Core Reasoning Activation Program
**Tracking ID:** BUG-104
**Document type:** Closeout note (documentation only — no runtime code, no schema change, no data migration, no frontend change, no feature flag change).
**As of:** `main` @ `e3ce5a4` (17/07/2026)

---

## 1. Completed Items

- **Phase 2A.0 — Leads Schema Canonicalization SPEC** (PR #370) — `docs/architecture/bug-104/PHASE_2A0_LEADS_SCHEMA_CANONICALIZATION_SPEC.md`. Audit + SPEC only, no code. Established `status`/`Business Outcome`/`Score`/`domain` as the canonical Leads reasoning inputs; `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` documented as empty/unreliable in practice and excluded from reasoning.
- **Phase 2A.1 — Current State Policy SPEC** (PR #371) — `docs/architecture/bug-104/PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md`. Audit + SPEC only, no code. Documented — as verified fact, not assumption — that `Business Outcome` did not reach `ReasoningEntity` at all before this phase, and that only 2 of 10 live `Leads.status` values were intentionally mapped.
- **BUG-105 (documented in this repo as BUG-110 — see numbering note in `AI_CONTEXT.md`) — non-canonical `status="converted"` writers** (PR #372) — `lead_conversion.py` and `ad_attribution.py::mark_converted()` no longer write the non-canonical `status="converted"`; they now write `status=LeadStatus.DONE` + `Business Outcome=LeadOutcome.CONVERTED`.
- **Phase 2A.1 implementation** (PR #373, `48b90c4`, merge `fa29514`) — implements the SPEC from PR #371:
  - `core/leads_reasoning_projection.py` — `Business Outcome` added to `_LIVE_TO_ADAPTER_FIELDS` so it reaches the adapter.
  - `core/adapters/leads_adapter.py::_normalise_status()` — terminal Business Outcome (`converted`→DECIDED_YES; `lost`/`not_relevant`→DECIDED_NO; `duplicate`/`archived`→CANCELLED) now overrides status; when Business Outcome is not terminal (intermediate/unknown/missing), an extended status map covers all 10 live `Leads.status` values (previously only `new`/`lost` were intentionally mapped, everything else — including `done`, the canonical "converted" status value — fell through to `OPEN`).
  - No new public phase/state enum values; no change to the projection's public envelope; `FEATURE_CORE_REASONING_LEADS_STATE` untouched.
- **Phase 2A.2 — Lead-specific `next_step`/evidence wording implementation** (PR #377, merged `2026-07-17T13:02:37Z`) — **moved here from §5A below; that listing was stale.** `core/leads_reasoning_projection.py::_apply_lead_wording()`, applied at the end of `build_reasoning_projection()`, post-processes the shared (Decision-shaped) engine's `missing_evidence`/`next_step` text into Lead-appropriate Hebrew wording. Pure text relabeling — `state`/`confidence.score`/`entity.status`/Phase 2A.1's Business Outcome precedence are untouched. Also fixes the Example-A/D terminal-phase corner case (a terminal, 0-event lead now correctly gets `missing_evidence=[]` instead of stale "no events" wording). `test_bug104_phase2a2_lead_wording.py` (37/37) plus all 5 related regression suites green, unchanged. No feature-flag/schema/frontend change; `FEATURE_CORE_REASONING_LEADS_STATE` still off/shadow. **Status: code-complete and merged, test/static-verified — not yet claimed as production-traffic verified** (no live shadow/enforce evidence collected for this wording path).

---

## 2. Runtime Evidence from Operator-Provided Render Logs

**These logs were provided by the operator during the session. The documentation branch did not independently access Render and does not claim an independent deployment verification. The independently reproducible verification artifact in the repo remains the merged test suite.**

### 2.1 `converted` / `הומר` → `DECIDED`

```
2026-07-17 15:38:39 [INFO] tma_api: [BUG-104][shadow] lead=recLQNCnuyfoMMcV4 reasoning={... 'state': 'DECIDED', ... 'next_step': {'action': 'העבר לביצוע', ...}, ... 'events': {'available': True, 'count': 1}, 'engine': {'degraded': False, 'errors': []}}
```

**Conclusion:** `converted` / `הומר` resolved to `DECIDED`, with no engine degradation/errors.

### 2.2 `meeting_scheduled` / `פגישה נקבעה` → non-terminal

```
2026-07-17 15:34:14 [INFO] tma_api: [BUG-104][shadow] lead=recLQNCnuyfoMMcV4 reasoning={... 'state': 'COLLECTING', ... 'events': {'available': True, 'count': 0}, 'engine': {'degraded': False, 'errors': []}}
```

**Conclusion:** `meeting_scheduled` / `פגישה נקבעה` did not resolve to `DECIDED` or `CLOSED`.

### 2.3 Lead Events visible to reasoning

```
2026-07-17 15:15:32 [INFO] tma_api: [BUG-104][shadow] lead=recclB826QV0QQXFd reasoning={... 'state': 'REVIEW', ... 'events': {'available': True, 'count': 5}, 'engine': {'degraded': False, 'errors': []}}
```

**Conclusion:** Lead Events were visible to the reasoning projection.

### Verification Limits

- Logs are operator-provided.
- No independent Render access by this branch/agent.
- No feature flag change claimed.
- No deployment assertion beyond the provided logs.
- Reproducible repo verification remains:
  - `test_bug104_phase2a1_current_state_policy.py` — 52/52 passing
  - plus the pre-existing regression suites listed in PR #373 (`test_bug104_leads_reasoning_projection.py` — 102/102, `test_bug104_phase1_1_contract_hardening.py` — 57/57, `test_bug104_tma_lead_event_bridge.py` — 46/46, `test_core_reasoning.py` — 59/59)

---

## 3. Confirmations

- ❌ No Airtable schema change
- ❌ No data migration
- ❌ No frontend change
- ❌ No feature flag change — `FEATURE_CORE_REASONING_LEADS_STATE` remains `off`/`shadow` per environment, unchanged by any Phase 2A work

---

## 4. Remaining Known Limitations

- **Readiness is still unknown for Leads.** `LeadsAdapter` supplies no readiness signal (Phase 1 boundary, unchanged by 2A.1); the projection reports an explicit `unknown` readiness state, never a positive value and never a copy of `state`.
- **`missing_evidence` still uses generic Decision evidence** (e.g. `"מסמך תומך"`) — the `REQUIRED_EVIDENCE`/`missing_evidence` mechanism was built for Decisions (contracts, appraisals, CVs, etc.), not Leads; `DOMAIN.GENERAL` falls back to a generic "supporting document" label that isn't Lead-accurate. Documented as a known boundary condition in the Phase 2A.1 SPEC, not fixed here.
- **`Next Action` / `Next Followup` remain excluded** from the current-state policy until a real writer and real data exist — both fields are effectively dead in live data today (`Next Action`: 0/92 populated with no code writer at all; `Next Followup`: 1/92, no computed-value writer), per the Phase 2A.0 audit.
- **`status=done` without a matching `Business Outcome` is covered by tests, not manually tested through the UI**, because the UI/TMA exposes `הומר` (which sets `Business Outcome`) rather than writing `status=done` directly. The `done`→`DECIDED_YES` fallback mapping is therefore verified at the code/test level (`test_bug104_phase2a1_current_state_policy.py` §E) but has no corresponding manual UI walkthrough.

---

## 5. Recommended Next Options

- **A. ~~Phase 2A.2~~ — done, see §1.** (Was: Lead-specific `next_step`/evidence wording — completed and merged via PR #377; moved to Completed Items above. This listing is kept, struck through, so the option's original rationale isn't lost, not because it's still pending.)
- **B. Leads schema cleanup/deprecation plan.** Act on the Phase 2A.0 SPEC's candidates for deletion/deprecation (`tier`, `Domain category`, `Domain risk assessment`, `Domain summary`) and the still-open documentation-conflict on `tier` (three contradictory descriptions in the codebase, per SPEC §7C) — requires an explicit owner decision before any schema mutation.
- **C. Observability: compact reasoning log with status/outcome/state/events.** A single-line structured log (status, Business Outcome, resulting state, event count, engine.degraded) per `GET /api/leads/<id>` call, to make future shadow-mode verification independently reproducible from Render logs without relying on ad hoc operator-provided excerpts like §2 above.
