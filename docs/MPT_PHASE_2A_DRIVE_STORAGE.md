# MPT Phase 2A — Durable Drive Artifact Storage

This track keeps Airtable as the `ExternalExecutionJob` metadata/control plane
and uses one least-privilege Google Drive folder as the durable artifact store.
The Render/MPT filesystem remains temporary working storage.

## Runtime configuration

Enable only in the target staging runtime with:

```text
MPT_ARTIFACT_STORAGE=google_drive
GOOGLE_DRIVE_ARTIFACT_FOLDER_ID=<dedicated-folder-id>
GOOGLE_CLIENT_ID=<secret/config>
GOOGLE_CLIENT_SECRET=<secret>
GOOGLE_REFRESH_TOKEN=<secret>
```

The dedicated Google user owns the My Drive folder. The code reuses the
existing BOSS Google OAuth helper and variables
(`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`). The
helper refreshes the token; this store does not duplicate token refresh logic
or log credentials.

`EXTERNAL_EXECUTION_ENABLED=false` remains the production default. Without
`MPT_ARTIFACT_STORAGE=google_drive`, the existing local-only Phase 1 adapter
path is unchanged.

## Completion contract

The adapter validates the local MP4, then uploads it using a deterministic
machine-safe identity derived from `contract_id` and `provider_job_id`.
Upload readback verifies file ID, name, MIME type, size, parent folder, and
identity. The stored `result_ref` is compact JSON containing the provider,
Drive file ID, folder ID, local SHA256, size, and MIME type.

`ExternalExecutionJob` is marked `completed` only after the boundary persists
that `result_ref`. If persistence fails, local work is retained for recovery;
after successful persistence the temporary adapter job directory is removed.
Repeated recovery looks up the deterministic identity before creating a new
Drive file, so an uncertain upload does not blindly duplicate artifacts.

## Staging gate

The staging POC requires a dedicated test folder, service-account secret, and
Render Standard 2 GiB runtime. It must verify one controlled MPT execution,
Drive readback, Airtable `result_ref` persistence, restart idempotency, and test
artifact cleanup. Production remains untouched until a separate decision.
