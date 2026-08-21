# BOSS Free Worker Pilot v1

This is a development-only, standalone contract layer. It is not imported by
`app.py`, `tools/dispatcher.py`, or `core/action_gateway.py`.

## Identity boundaries

`role` (Builder, Auditor, Tester, Researcher, Reviewer) is independent from
`harness` (Claude Code, OpenCode, Qwen Code, Kimi Code), which is independent
from opaque `model` and `provider` strings. A `WorkerProfile` carries that
configuration; orchestration does not hardcode model capabilities.

## Lifecycle

`WorkerRequest` explicitly bounds allowed paths and verification commands.
`WorkerRouter` selects a profile and adapter. Adapters detect installed
executables with `shutil.which` and normalize outcomes to `WorkerResult`.
Unknown or missing harnesses, disabled/unqualified workers, and default pilot
execution are blocked. A future execution slice must create an isolated git
worktree and retain the existing approval/governance gates.

`qualification` defaults to `unqualified`; this pilot has no promotion path.
The CLI only lists profiles, reports executable availability, and dry-runs
routing. It never launches a subprocess.
