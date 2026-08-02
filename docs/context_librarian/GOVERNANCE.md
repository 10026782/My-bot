# Context Librarian governance

The librarian is a deterministic metadata index, not a source of truth. It may
stop a dangerous change, but not planning because of ordinary GitHub activity.

Refresh, gate evaluation, provenance reconciliation, source discovery, and
budget estimation are separate concerns. Mechanical metadata may be refreshed
automatically after a real merge on `main`; authority classification requires
review. The budget controls bundle selection, never catalog completeness.

The librarian must not alter BOSS runtime, approval logic, ownership, queue, or
evidence authority. See `PLANNING_GATE.md`, `POST_MERGE_REFRESH.md`, and
`RECOVERY_AFTER_FAILED_REFRESH.md` for operating procedures.
