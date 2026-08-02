# Agent Prompt — Workstream 1: Routing, Builders and Resolvers

## Base and Librarian gate

Branch from the canonical current `origin/main` SHA. Do not branch from
another agent. Run `suggest-profile --all` with the full task, select
`turn_coordinator_routing`, build/read the bundle, directly review mandatory
sources, and return a consumption report before implementation.

## Read exactly

`core/router/router.py` (`route_request`, `deterministic_create_task_title`),
`core/router/route_decision.py`, `core/router/intent_router.py`,
`core/router/risk_router.py`, `core/lead_candidate_handler.py`,
`core/adapters/leads_adapter.py`, `core/adapters/decision_adapter.py`,
`core/leads_reasoning_projection.py`, `core/turn_envelope.py`, the current
Turn Coordinator docs, `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`,
`BUG_AUDIT_LOG.md`, and the router/lead/reasoning tests cited by the bundle.

## Scope

Implement only ownership selection, Agent admission, canonical task/lead
builders, and bounded task/lead/contact/deal resolvers for:
`create_task`, `update_task`, `complete_task`, `search_task`, `create_lead`,
`update_lead`, `search_lead`, known entity update, and deterministic non-
lifecycle read/status intents.

Preserve `RouteDecision`, ActionContract authority, evidence semantics, and
current reply behavior. Add no direct execution path.

## Forbidden

Do not edit `app.py`, ActionGateway/repository/atomic executor, EventBus, TMA,
MessageContract/formatters/adapters, feature flags, catalog, or implementation
sequence. Do not modify approval/evidence/reply authority. Do not remove tests,
guards, validation, fail-closed paths, or telemetry.

## Interfaces and tests

Use the frozen `IntentOwnershipDecision`, `CanonicalActionProposal`, and
`ResolverResult` contracts. Run existing router, create-task, lead, reasoning,
and TurnEnvelope tests plus new builder/resolver 0/1/many, identity-scope,
bounded-read, and Agent-admission tests.

## Acceptance and delivery

Every owned intent has one target owner; complete structured inputs never reach
Agent; ambiguous inputs clarify or admit Agent; unsupported inputs do not
invent a path; proposals use named canonical fields; no approval/lifecycle
state changes. Commit in small TC1–TC4 commits, push the branch, and open a
Draft PR targeting `main`. Do not merge.

## Final report

Return base SHA, profile/bundle hash, receipts, changed files/functions,
intents covered, resolver bounds, tests, forbidden-scope confirmation,
rollback/flag statement, commit SHAs, PR URL, and verifier result.
