# SaaS Replacement Index — 2026-08

> This is a research/procurement catalog, not a BOSS source of truth for implementation or runtime status.

Known cost: Render Postgres staging $7/month; production $7/month; total $14/month (owner supplied). No other current costs are inferred.

| Paid SaaS / category | Current use? | Current cost if known | Open-source/self-hosted alternatives | Hosted alternative | Migration complexity | Feature gaps | Maintenance cost | License risk | Data/privacy impact | Recommendation | Revisit trigger |
|---|---|---:|---|---|---|---|---|---|---|---|---|
| Workflow automation | no current n8n evidence | unknown | n8n | n8n Cloud/other | high if core | none proven | high | Sustainable Use/Enterprise | high | Do not replace core | approved internal ETL case |
| Database/backend | Render Postgres used | $14/month total | PostgreSQL | Supabase | high | Auth/RLS/Realtime/Storage not currently required | medium | Apache-2.0 platform; hosted terms | high | KEEP RENDER | measured limits or required capability |
| File/storage | Google Drive/Airtable paths | unknown | MinIO/other candidates | existing providers | high | none proven | medium/high | per project | high | Keep current | cost/retention/scale evidence |
| Monitoring | repository logs/cost monitor | unknown | self-hosted observability candidates | hosted monitoring | medium | no dashboard requirement proven | medium | per project | medium/high | No change | incident/retention requirement |
| Analytics | usage_events shadow + reports | unknown | Postgres/reporting | hosted analytics | medium | no durable product analytics contract | medium | per project | high | Extend current DB first | validated analytics need |
| Knowledge/wiki | Markdown/governance docs | unknown | self-hosted wiki candidates | hosted wiki | high | none proven | medium | per project | high | Keep repo docs | owner-approved source-of-truth need |
| Transcription | OpenAI STT path | unknown | local model later | hosted STT | medium | quality/latency unknown | medium | model/provider terms | high | Keep provider | measured cost/privacy trigger |
| Document tools | `document_converter` exists | unknown | self-hosted converters | hosted conversion | medium | none proven | medium | per project | medium/high | Keep current | format/volume gap |
| Communication integrations | Telegram/WhatsApp/Google providers | unknown | adapters | hosted provider APIs | high | none proven | medium | provider terms | high | Keep current | reliability/cost evidence |

## Replacement rule

Do not migrate because an alternative is open-source, popular, or appears cheaper. Compare total cost, feature need, backups, HA, latency, egress, storage, pooling, observability, restore/recovery, auth/RLS, tenant model, maintenance, migration effort, and lock-in. No current entry justifies a migration.

Security rule: before any spike inspect license, maintainership, security policy, recent releases, dependency health/CVEs, secrets, network/process privileges, tenant isolation, auth, data retention, telemetry, outbound calls, and supply-chain risk.
