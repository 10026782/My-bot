# Post-merge refresh procedure

Refresh is a separate catalog-maintenance workflow. It reconciles mechanical
provenance after a real merge on `main`, including normal and squash merges.

```bash
python3 -m tools.context_librarian refresh-after-merge --check
python3 -m tools.context_librarian refresh-after-merge --write
```

The command resolves the canonical SHA from `origin/main` (or the configured
main ref), compares it with each node's tracked sources, and proposes/updates
`last_verified_commit` only to that canonical SHA. A temporary branch SHA is
never written as canonical. A no-op prints `OK` and does not touch files.

Metadata/provenance changes are mechanical. New-source classification and any
authority change remain review-gated; the command never auto-registers source
semantics.

CI on `push` to `main` is authoritative and runs the check. A local hook may run
the same check for convenience, but its result cannot override CI.
