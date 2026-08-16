# External Execution Jobs — Airtable provisioning

The canonical table name is `External Execution Jobs`. It must be provisioned
before `EXTERNAL_EXECUTION_ENABLED=true`. The repository does not provision
Airtable tables automatically; this document is the manual provisioning
contract and verification checklist.

| Field | Airtable type | Required | Values/default |
|---|---|---:|---|
| `contract_id` | single line text; primary | yes | unique ActionContract ID |
| `adapter_name` | single line text | yes | boundary-owned adapter name |
| `provider_job_id` | single line text | no | empty until accepted submit |
| `status` | single select | yes | `created` default; `submitted`, `completed`, `failed`, `outcome_unknown` |
| `submitted_at` | number | no | Unix seconds |
| `last_checked_at` | number | no | Unix seconds |
| `completed_at` | number | no | Unix seconds |
| `attempt_count` | number | yes | `0` default |
| `result_ref` | single line text | no | bounded result reference/checksum |
| `evidence` | multiline text | no | bounded JSON evidence |
| `failure_code` | single line text | no | bounded short code |

`contract_id` is the only record key. Approval, tenant, identity, frozen
payload, and idempotency remain owned by ActionContracts. Provider secrets,
raw payloads, and unbounded logs are not fields in this table.

Verification: confirm the exact table/field names and select choices with the
existing `schema_audit.py` / RuntimeSchemaProvider before enabling the flag.
