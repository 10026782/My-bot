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
7. The Librarian pilot is `LIBRARIAN_PILOT_PASS` and the planning result is
   `PLANNING_READY`: all 75 mandatory sources have direct receipts and the
   verifier returns `CONCLUSION_PROCEED`. The bundle still warns that the
   planning checkout is not on main; no production claim is made.
8. Catalog gaps are not edited in this PR.
9. Review found a planning defect in `IMPLEMENTATION_SEQUENCE.md`: it listed
   PRs without explicit dependencies. The table now declares and topologically
   orders the DAG (`TC1 → TC2 → TC3 → TC5 → TC4 → TC6 → TC7/TC8 → TC9 → TC10`).
