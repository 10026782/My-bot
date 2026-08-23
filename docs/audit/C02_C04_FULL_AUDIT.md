# C02–C04 Full Audit

Status: historical audit record; read-only findings. This document preserves
the complete audit inventory so findings are not lost between remediation PRs.

Evidence boundary: static repository review only. Production runtime was not
verified because local Airtable/Render credentials and runtime evidence were
unavailable.

## Findings

### 1. Idempotency / Scheduler — HIGH

Scheduler deduplication is process-local. Multiple Render instances may run
the same jobs concurrently and create duplicate reminders, events, or writes.

Evidence: `gunicorn.conf.py:15`, `scheduler.py:822`.

Classification: `PROCESS_LOCAL_ONLY`, `RACE_WINDOW`.

### 2. Feature Flag / Permission — HIGH

`/voice/incoming` checks `VOICE_IVR`, but `/voice/step` does not check the same
flag. When the feature is disabled, a caller who passes Twilio authentication
can still continue the IVR flow.

Evidence: `app.py:6638`, `app.py:6653` at audit time.

Classification: `READ_PATH_DRIFT`, `PERMISSION_GAP`.

### 3. Error Handling — HIGH

The Meta WhatsApp media failure path previously swallowed download/save
failures while the endpoint returned `200 received`.

Evidence at audit time: `app.py:6571`, `app.py:6585`.

Remediation status: superseded/verified by PR #859. Current behavior records a
non-completed `media_processing` result with explicit error evidence while
preserving the provider ACK policy. This audit finding remains historical and
is not rewritten.

Classification: `FALSE_SUCCESS`, `SWALLOWED_FAILURE` — historical.

### 4. State Transitions — MEDIUM/HIGH

The Action contract permits `pending → completed` and `pending → failed`,
which can bypass `approved` and `executing`. This may be an intentional
recovery path, but requires an explicit decision and documentation.

Evidence: `core/action_contract_repository.py:64`.

Classification: `STATE_TRANSITION_SKIP`.

### 5. Feature Flag Drift — MEDIUM

- Documentation uses `FEATURE_EMAIL_INBOUND`; code uses `EMAIL_INBOUND`.
- `INTERACTION_INTELLIGENCE` is read directly from the environment in the
  scheduler but through `feature_flags` in the engine.
- `FEATURE_WEEKLY_SUMMARY` is checked inside the job, so the scheduler still
  registers and invokes the weekly job while the flag is disabled.

Evidence: `feature_flags.py:68`, `scheduler.py:332`, `scheduler.py:444`.

Classification: `NAME_DRIFT`, `READ_PATH_DRIFT`, `REGISTRATION_DRIFT`.

### 6. Logging / Sensitive Data — MEDIUM

Operational logs included potentially sensitive content:

- agent reply prefix, up to 100 characters;
- transcript prefix, up to 60 characters in an approval label;
- chat/user identifiers in multiple paths.

Evidence at audit time: `app.py:6595`, `media_handler.py:300`.

Remediation status: PR #857 removed the confirmed transcript/tool input/result
logging paths. The remaining Meta reply-content log was isolated as a small
follow-up and is addressed by PR #873 with metadata-only logging and a
sentinel regression test. No production verification claim is made here.

Classification: `SENSITIVE_LOG`, `NO_CONTEXT` — historical/current gap tracked
by PR #873.

### 7. Import Boundaries — MEDIUM

Logical dependency cycles were found, largely hidden by local imports:

```text
app → scheduler → followup_engine → app
app → media_handler → app
app → cmd_update → media_handler → cmd_update
```

Evidence: `followup_engine.py:199`, `media_handler.py:308`.

Classification: `CIRCULAR_IMPORT`, `LAYER_BOUNDARY_DRIFT`.

### 8. Approval Coverage — MEDIUM

Two parallel paths exist: Action Gateway and a legacy path when
`FEATURE_ACTION_GATEWAY=false`. Approval enforcement therefore does not have
one owner for every mutation; the legacy writers need an explicit inventory.

Evidence: `app.py:3235`, `app.py:1564`.

Classification: `APPROVAL_PATH_DRIFT`.

## Categories with no confirmed finding

- **Routes / Entry Points:** principal routes are connected to Flask or
  Gunicorn startup. `/worker/trigger` connects `worker.py`. Three ghost-button
  matches were false positives caused by template-path decoding in
  `Ventures.tsx`.
- **Ownership / Permissions:** TMA owner/role checks were consistent in the
  reviewed write endpoints; no definite bypass was found statically.
- **Orphan state values:** no definite orphan status was found. The transition
  skip in Finding #4 remains a separate risk.

## Remediation ledger

| Finding | Current record |
|---|---|
| #1 | Static finding; scheduler multi-process race remains open/deferred |
| #2 | Current concrete gap; `VOICE_IVR` parity requires a separate focused PR |
| #3 | PR #859; already verified/superseded at audit truth-reset |
| #4 | Requires explicit state-transition decision |
| #5 | Feature-flag drift audit/remediation history retained separately |
| #6 | PR #857 plus PR #873; production verification still pending |
| #7 | Import-boundary risk; no change in this logging PR |
| #8 | Legacy approval-writer inventory still required |

This document is documentation only. It does not change runtime behavior,
schema, permissions, scheduler behavior, or provider acknowledgement policy.
