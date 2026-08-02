# Decision Log

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
7. The Librarian pilot is `LIBRARIAN_PILOT_PARTIAL` and the planning result is
   `PLANNING_REVIEW_REQUIRED` because the consumption contract was invoked but
   not satisfied by real receipts in this run.
8. Catalog gaps are not edited in this PR.
