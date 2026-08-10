# Context Librarian planning gate

For cross-layer architectural impact classification, use the mandatory assessment and conditional matrix in `docs/governance/CROSS_LAYER_GOVERNANCE_REVISED_PLANNING_GATE.md`. Stale metadata alone does not force a full matrix; authority, contract, lifecycle, evidence, persistence, runtime-wiring, fallback, and multi-layer impact do.


The librarian may stop a dangerous change, but it must not stop planning because
of ordinary GitHub activity.

Planning, research, scoping, and decomposition continue when the only signal is
stale nodes, commits, PRs, tests, changelog entries, audit/planning/alignment
documents, or activity on the current branch. These are `WARNING` signals.

After direct source re-verification, the agent records the sources and commit in
the verification ledger and continues. Refresh is a separate mechanical path;
it is not a prerequisite for planning.

`STOP` means one of:

- authority is missing;
- canonical sources conflict or canonical state cannot be determined;
- a runtime/write/approval/ownership/queue/evidence change relies on stale
  authority;
- an unregistered source changes authority.

`REVIEW_REQUIRED` means a new authority/runtime source or a source that may
change authority. It needs review, but ordinary planning may proceed unless a
STOP condition also exists.

The librarian does not change BOSS runtime, approval logic, ownership, queue, or
evidence authority. It reports and routes those decisions to their existing
owners.
