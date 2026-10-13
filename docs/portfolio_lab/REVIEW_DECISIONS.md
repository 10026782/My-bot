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
