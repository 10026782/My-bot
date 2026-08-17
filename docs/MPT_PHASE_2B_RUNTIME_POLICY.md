# MPT Phase 2B Runtime Policy

The current proven profile is Render Standard 2 GiB (`plan-srv-008`) for the
1080×1920 fixture. The adapter does not downgrade resolution. When a runtime
profile is explicitly supplied, only `standard-2gb`, `render-standard-2gb`, or
`plan-srv-008` are accepted.

Defaults are conservative and staging-safe:

| Variable | Default | Meaning |
|---|---:|---|
| `MPT_RUNTIME_PROFILE` | unset | Optional runtime identity; unknown is not guessed |
| `MPT_MAX_CONCURRENT_EXECUTIONS` | `1` | One active MPT execution per service/runtime |
| `MPT_MAX_EXECUTIONS_PER_DAY` | `1` | Bounded daily execution ceiling |
| `MPT_MAX_RUNTIME_MINUTES` | `30` | Optional execution limit |

Capacity is checked before a new MPT submit. If full, a durable `created` job
is left without provider submission; a later explicit retry may reuse it.
Existing `ExternalExecutionJob` states and Drive persistence ordering are
unchanged.

Runtime evidence is bounded to profile, start/finish timestamps, elapsed
seconds, artifact bytes/validation, and termination/failure classification.
Exit 137/SIGKILL is `RESOURCE_LIMIT`; timeout is `TIMEOUT`. No generic retry is
performed. Only an explicitly approved caller may retry `TRANSIENT_TTS` or
`TRANSIENT_NETWORK`, at most once; `OUTCOME_UNKNOWN`, resource, input, auth and
artifact failures are never automatically resubmitted.
