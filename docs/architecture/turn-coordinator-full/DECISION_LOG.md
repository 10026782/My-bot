# Decision Log

## Implementation status update — 2026-08-02

13. WS1 foundation contracts were merged through PR #536. PR #545's narrow
    runtime integration, head `1d117ab`, was merged as `46db9af`; follow-up
    PR #546 is also merged. Local focused/standalone verification passed. The
    approved sequence remains WS1 → WS2 → WS3, with staging still required
    before rollout claims.

1. The selected primary profile is `turn_coordinator_routing`; selection was
   unique, not name-based.
2. The coordinator is an owner selector, not a new execution, approval,
   evidence, or reply authority.
3. ActionContracts remain lifecycle authority. EventBus, app pending state,
   session state, and TMA approvals are projections/legacy paths to be
   reconciled, not new authorities.
4. Agent admission is deny-by-default for known deterministic lifecycle and
   mutation paths; ambiguity is a reason to clarify or admit Agent, never a
   reason to guess.
5. Resolvers are bounded, identity-scoped, durable-first, and return explicit
   0/1/many outcomes.
6. The first implementation PR is TC1, because ownership must be observable
   before behavior moves.
7. The Librarian pilot is `LIBRARIAN_PILOT_PASS` and the planning result is
   `PLANNING_READY`: all 75 mandatory sources have direct receipts and the
   verifier returns `CONCLUSION_PROCEED`. The bundle still warns that the
   planning checkout is not on main; no production claim is made.
8. Catalog gaps are not edited in this PR.
9. Review found a planning defect in `IMPLEMENTATION_SEQUENCE.md`: it listed
   PRs without explicit dependencies. The table now declares and topologically
   orders the DAG (`TC1 → TC2 → TC3 → TC5 → TC4 → TC6 → TC7/TC8 → TC9 → TC10`).
10. The implementation is partitioned into exactly three workstreams. TC1–TC4
    are internal milestones of Workstream 1, TC5–TC8 of Workstream 2, and
    TC9–TC10 of Workstream 3; merge order remains WS1 → WS2 → WS3.
11. `app.py` has one integration owner. The agents may submit isolated patches,
    but no two workstreams may edit it concurrently.
12. The planned contracts absent from current runtime are
    `PRE_PARALLEL_BLOCKER`s. Agents may draft and test them independently, but
    authority-changing parallel implementation cannot start until the freeze.

## Implementation status update — 2026-08-07

14. Production staging E2E surfaced a live "reply ownership is conditional"
    incident (BUG-160/161/162/163, `BUG_AUDIT_LOG.md`) — the Agent spoke in a
    Gateway-owned turn because one exit branch of the legacy
    `_queue_approval_detailed_impl()` (`app.py`) never set `reply_owner`.
    Closure audit (`docs/architecture/action-gateway/BUG-162_SINGLE_SPEAKER_
    CLOSURE_AUDIT_20260807.md`) confirmed this is exactly the gap TC6 exists
    to close (`GAP_ANALYSIS.md`'s "reply ownership is conditional" row,
    `NEXT_IMPLEMENTATION`), and that TC6 has genuinely not been implemented —
    `ActionGateway.approval_status()`/`execution_status()` exist but their
    return value is discarded at both call sites; the legacy path this
    incident lived in remains the sole live authority for reply text.
    Decision: apply a narrow, well-tested **interim tactical patch** to the
    legacy branch rather than block on TC6's full sequence position — a
    live, user-facing defect does not wait for its formal turn when the fix
    is small, additive, and does not touch authority (only adds the
    `reply_owner`/`lifecycle_result` fields the sibling branch already set).
    This patch is explicitly **not** TC6 and does not reduce TC6's remaining
    scope. It was applied as a direct `app.py` edit, outside the WS2
    agent-prompt/Librarian-bundle/integrator-review workflow this plan
    defines (`app.py` is "Integrator only" per the file ownership map) —
    recorded here so TC6's eventual implementer finds it deliberately, not
    as unexplained drift, and is expected to review/absorb or explicitly
    supersede it during TC6's own implementation.
15. `docs/architecture/turn-coordinator/` (the older, still-actively-updated
    Turn Coordinator directory referenced directly by `CLAUDE.md` and by
    `docs/context_librarian/layers/turn_coordinator.json`'s `canonical_docs`)
    and this directory (`turn-coordinator-full/`, the WS1/WS2/WS3 execution
    plan) are **two separate documents describing the same program**, last
    updated on different dates, and until this entry neither one referenced
    the other. This is exactly the "parallel sources of truth" pattern
    `docs/architecture/f52-unified-approval-runtime/audits/original/
    F52_CONTRACT_COVERAGE_MAP.md`-class documents warn against generally.
    Resolved (see both READMEs): `docs/architecture/turn-coordinator/
    README.md` is the canonical index for **current merge/implementation
    status** (it is actively kept current and is the one wired into the
    Librarian's `canonical_docs`); this directory remains authoritative for
    the **WS1/WS2/WS3 task breakdown, DoD items (TC1–TC10), and gap
    ownership** — not for current merge-status facts, which drift here
    between updates. Neither directory supersedes the other's own domain.
