# PL-1 — proposed source classification for owner review

Local pre-merge reconciliation on 2026-10-13 returned OWNER_DECISION_REQUIRED
(NO_POLICY_MATCH). This document is a **proposal**, not an approval or catalog
registration. AGENTS.md: "New sources are proposals, never silent registrations."
No catalog/policy changes were made. Runtime integration remains out of scope.

| New source | Gate classification | Proposed role | Proposed authority |
|---|---|---|---|
| portfolio_lab/models.py | REVIEW_REQUIRED | local typed mathematical inputs and tax-adapter data contracts | no BOSS authority |
| portfolio_lab/engine.py | REVIEW_REQUIRED | deterministic in-memory research calculations only | no writes, routing, approval or execution authority |
| portfolio_lab/__init__.py | REVIEW_REQUIRED | standalone local API exports | no BOSS authority |
| portfolio_lab/__main__.py | REVIEW_REQUIRED | stdin/stdout local CLI only | no bot tool or endpoint |
| docs/portfolio_lab/base.json | REVIEW_REQUIRED | unverified owner scenario inputs | no production/market/tax authority |
| docs/portfolio_lab/comparison.json | REVIEW_REQUIRED | hypothetical comparison fixture | no production/market/tax authority |
| docs/portfolio_lab/crises.json | REVIEW_REQUIRED | hypothetical annual-sequence fixture | no production/market/tax authority |
| docs/portfolio_lab/EVIDENCE.json | STOP | local test/calculator results snapshot | historical local verification only, never production evidence or BOSS evidence-finalizer authority |

Boundary evidence: standalone import with Python -S passes without core, Flask,
Airtable, requests, NumPy or Anthropic. New code has no external I/O except CLI
stdin/stdout. Existing bot/core/TMA/CRM/requirements/workflow files are unchanged.
Purchase units and tax-port examples are research data, not a security master,
broker ledger, legal rule registry or automatic trade executor.

Owner decision requested during PR review: accept/revise the exact roles above.
Only after that decision should a bounded catalog registration follow. Do not
broaden an unrelated node/policy or authorize arbitrary future files by wildcard.
No merge requested; PR is a review-only draft.

## Bounded resolution — 2026-10-13

Owner follow-up: "Portfolio Lab PL-1 — Governance Resolution & CI Verification"
accepts this proposal as the classification basis and authorizes exact limited
registration under current origin/main policy. Direct review of
`docs/context_librarian/RECONCILIATION.md` §E/§F confirms owner-reviewed paths
may be registered directly in the catalog in this same PR. No additional
file-specific approval requirement was found for this supporting-only entry.

Registered node: `decision.portfolio_lab_local_research` in
`docs/context_librarian/decisions/canonical_boundaries.json`, with candidate
status, REGISTER_SUPPORTING, is_authority=false, runtime_consumed=false,
production_evidence=[], feature_flags=[], exact paths only. Four code paths
are code_paths; three simulation fixtures and the historical local snapshot
are canonical_docs with explicit non-authoritative roles. No policy, glob,
future-source authorization, edge or existing node was changed.

Policy baseline: origin/main `5e20e6069e558e6e4a8bb8712c7b49a30177da08`.
Reviewed implementation: `b34186e4f6eac8b1c367eb9d8a38a957580cc94a`.
The required last_verified_commit field records only the main policy baseline;
it does NOT claim PL-1 code exists or is verified on main. Branch source review
is separately recorded in last_semantic_review_commit and the node's notes.

Cross-Layer Impact: NONE. Owner: standalone Portfolio Lab/local catalog metadata.
No existing authority boundary, shared contract, lifecycle, routing, persistence,
new cross-layer caller, dormant activation, fallback or bypass changes. Contract
chain: owner-reviewed classification -> catalog node exact references -> existing
load_catalog/classify_new_sources/reconcile_pr -> read-only report -> CLEAN.
All mathematical runtime code and input fixtures remain unchanged in this pass.

Verification ledger / context expansion:
- Re-read current-main AGENTS.md, RECONCILIATION.md §E/F, node schema,
  AGENT_CONSUMPTION_CONTRACT and revised planning gate; selected
  cross_layer_architecture explicitly after displaying all suggestion scores.
- Inspected catalogue validation/reference extraction in librarian.py and
  registration-only precedent decision.businessdraft_core_envelope. Required
  because new sources had no existing appropriate catalog owner; recurring
  new-source classification case, not a new execution authority.
- Inspected all Portfolio Lab code, tests and fixtures. Search of app/core/tools/
  TMA/CRM finds no Portfolio Lab caller; production-path diff against main empty.
- pre_session_gate exit 0. No new branch, shared-checkout mutation or main merge.
- 323 local unit/CLI/catalog/reconciliation/status tests passed: includes 55
  Portfolio Lab tests (four extra verification tests, no engine changes).
- Catalog valid: 51 nodes, 27 edges, 8 profiles. Budget preflight: no overflow;
  cross_layer_architecture estimate 14782/15400, headroom 618; existing stale
  calibration/tight-budget warnings are not changed by this exact unconnected node.
- reconcile-pr: CLEAN, empty decision queue. dev_registry_validator: 46 rows pass.
- Additional calculation checks cover nominal/effective equivalence, independent
  720-month sum of management fees, drifting buy-and-hold weights vs rebalancing,
  8.64% arithmetic vs 8% geometric crisis means, unverified source labels/null tax.

Hosted CI must still be verified at the newly pushed head. No merge/deployment or
production validation is represented by this local ledger. Original proposal and
local EVIDENCE.json snapshot above remain historical, not overwritten proof.
