# Agent Prompt — Workstream 3: MessageContract, Surfaces and Verification Harness

## Base and Librarian gate

Branch from the canonical current `origin/main` SHA. Run full profile
suggestion, select `turn_coordinator_routing`, and add `approval_ux` plus
`rp5_evidence_mismatch` coverage. Build/read the bundle, directly review all
material formatter/surface/evidence sources, and return receipts.

## Read exactly

`core/message_contract.py`, `core/agent_message_formatter.py`,
`core/action_fact_message_adapter.py`,
`core/approval_lifecycle_message_adapter.py`, `core/action_gateway.py` result
types, `app.py` send/render seams, `tma_api.py` response seams, Telegram and
WhatsApp adapters, F52 UX/evidence documents, and message/redaction/status
tests cited by the bundle.

## Scope

Own MessageContract projection, display payload rendering, Telegram/WhatsApp/
TMA/API parity, pending/rejected/completed/failed/outcome-unknown wording,
internal identifier/tool-name redaction, staging harness, readiness reports,
canary gates, and rollback reports.

## Forbidden

Do not edit routing, builders/resolvers, ActionContract lifecycle, atomic
claims, EventBus, feature flags, catalog, or `app.py` directly. Submit an
isolated integration patch to the integrator. Do not let surfaces reinterpret
lifecycle/evidence state or claim deployment/production completion.

## Interfaces and tests

Consume frozen `ActionLifecycleResult` and `EvidenceResult`; produce only the
public `MessageContract`. Run MessageContract, formatter, adapter, redaction,
F52 reconciliation, and surface tests. Add cross-surface golden cases,
state/evidence precedence cases, adapter compatibility tests, and readiness /
rollback harness tests.

## Acceptance and delivery

Exactly one public presentation contract exists; no internal IDs/tool names
leak; pending is not completed; outcome_unknown is not success; all supported
surfaces render the same semantic state. Commit TC9–TC10-sized changes, push a
separate branch, and open a Draft PR to `main`. Do not merge or change flags.

## Final report

Return base SHA, profiles/bundle hash, receipts, contract fields and adapters,
surface matrix, redaction results, harness/readiness output, tests, changed
files/functions, integration patch, rollback/flag statement, commit SHAs, PR
URL, and verifier result.
