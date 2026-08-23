# C02–C04 Remediation 1 — Finding #3

## Historical finding (preserved)

`core/lead_service.py::create_lead()` caught an ActionGateway proposal
exception and continued to the direct `airtable_create()` / `airtable_patch()`
business mutation. This was classified in the C02–C04 audit as
`SWALLOWED_FAILURE` / `MISSING_EVIDENCE`.

## Remediation note

On the remediation branch based on `origin/main` at `0646ae3`, the exact path
was re-confirmed. The exception path now returns `ok=False` with
`action="gateway_failed"`, `reason="gateway_proposal_failed"`, and evidence
`mutation_executed=False`. The direct Airtable writer is not reached after a
Gateway proposal failure. Existing Gateway-success and Gateway-blocked paths
remain unchanged.

Status: implemented locally; not production verified; not deployed; not merged.
