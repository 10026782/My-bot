# Integration and Merge Plan

## Ownership

The integrator owns `app.py`, shared-contract approval, integration commits,
and the final staging decision. Workstream agents own only their listed files
and submit isolated integration patches. No agent cherry-picks another agent's
branch without an integrator decision.

## Freeze and merge order

1. Freeze `RouteDecision`, `IntentOwnershipDecision`,
   `CanonicalActionProposal`, `ResolverResult`, `ActionLifecycleResult`,
   `EvidenceResult`, and `MessageContract`. The four planned-but-absent types
   are `PRE_PARALLEL_BLOCKER` until fields and compatibility are approved.
2. Merge Workstream 1 first: routing, builders, resolvers, and no-Agent
   deterministic gates.
3. Re-run router, builder, resolver, and existing regression tests.
4. Merge Workstream 2: lifecycle, evidence, concurrency, and reply ownership.
5. Re-run callback, replay, concurrency, direct-dispatch, and evidence tests.
6. Merge Workstream 3: adapters, surfaces, and harness.
7. Re-run full focused suite, contract snapshots, parity/redaction tests, and
   readiness report.
8. Only after all gates pass: staging observation, canary decision, then a
   separately approved flag change. This planning PR changes no flag.

## Pre-merge contract checks

Before each merge verify: field names/defaults, producer/consumer ownership,
0/1/many and error semantics, backward compatibility, no authority transfer,
no internal identifier leakage, evidence precedence, one final responder, and
fresh Librarian receipts for the exact branch commit.

## If a workstream is delayed

Other streams may continue isolated tests and new modules against the frozen
contracts. They may not edit the delayed stream's files or replace its
authority. The integrator may merge a completed stream only if its contracts
remain adapter-compatible and the delayed stream's integration seam stays
dark.

## Shared-file conflicts

`app.py` is never edited concurrently. Each stream submits a minimal patch
proposal with context and tests; the integrator applies one ordered patch and
runs the full affected suite. Contract conflicts are resolved by authority
review, not textual merge preference. No cherry-pick is used to bypass review.

## Staging, canary, and rollback

Staging begins only after WS1–WS3 tests and readiness reports pass with flags
unchanged. Canary begins only after production-like callback/replay,
cross-surface, evidence, and concurrency cases pass. Formatter/evidence flags
remain unchanged until owner approval and the harness shows no semantic or
authority regression.

| Stage | Required evidence | Rollback |
|---|---|---|
| Contract freeze | schema snapshots, Librarian receipts | reject parallel start |
| WS1 merge | deterministic routing/resolver tests | disable new admission path; preserve legacy behavior |
| WS2 merge | lifecycle, claim, replay, evidence, race tests | fail closed; never restore direct execution |
| WS3 merge | parity, redaction, state-precedence, harness report | restore old renderer adapter only; no lifecycle change |
| Staging | dated readiness report and observability | keep flags off/shadow; retain audit data |
| Canary | provider-call count, evidence, one-speaker and surface checks | stop canary and revert integration patch; no authority downgrade |
| Activation | owner-approved flag decision plus production verification | disable the new flag/path; report implemented but not verified until rechecked |

Every stage produces a consumption report, test result, changed-file list,
rollback decision, and explicit statement that no unapproved authority moved.
