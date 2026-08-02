# Production Render Verification — 30–31/07/2026

This is a read-only verification record for the approval/runtime briefing. It
must not be read as proof that production is running the current `origin/main`
tip unless the deployed commit below matches that tip.

## Environment and deployment

- Production service: `srv-d80ehsf7f7vs73cq5rn0`
- Public service: `https://my-bot-jqz2.onrender.com`
- Render owner: `tea-d804tr8sfn5c7398geag`
- Current `origin/main` at verification time: `1c51570196c4660980546bdcf8dc337353489be8`
- Latest live Render deploy: `5ec37b8227d4c62da5bd3235933ff1e95c2a40fb`
- Live deploy status: `live`, finished `2026-07-30T23:43:34.968267Z`
- Therefore production was live on `5ec37b8`, not on the current `origin/main` tip.

## Feature-flag verification

Read-only `GET /v1/services/srv-d80ehsf7f7vs73cq5rn0/env-vars`, filtered before
output to the three non-secret keys, returned:

```text
FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS=true
FEATURE_SINGLE_SPEAKER_APPROVAL_UX=true
FEATURE_ACTION_GATEWAY=true
```

No other environment variables or secret values were printed or persisted.

## Runtime log verification

The repository's read-only `scripts/render_log_export.py` fetched 111 matching
`ActionContract` application-log entries for the production service in the
window `2026-07-29T11:11:28Z` through `2026-07-31T11:11:28Z`. The export is
stored under the gitignored `render_logs/production_verification/` directory.
The entries show live ActionContract reads, creates, approvals, and lifecycle
updates on 29–30/07.

## Scope and remaining caveats

- This verifies the three flag values in the live production environment and
  confirms ActionContract runtime activity.
- It does not prove that production equals the current `origin/main` tip.
- It does not independently prove the exact `sheets_append` positional
  canonicalization branch; that branch remains test-only.
- BUG-152 remains an observed, unroot-caused production-adjacent finding and is
  not marked fixed by this evidence.
