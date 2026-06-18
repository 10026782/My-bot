# Changelog

All notable repository-level changes should be recorded here.

## Unreleased

- Added `inbound_handler.py` (F06) — unified inbound lead gate sitting in front of `lead_capture.py`: dedups by `external_id` (exact, e.g. `gmail:<msg_id>`), updates existing leads by `sender_id`, otherwise creates a new email lead. Added `LeadFields.EXTERNAL_ID`/`SENDER_ID` to `airtable_schema.py`. Rewired `email_inbound.run_email_poll()` to route through the new gate instead of building/approving drafts directly; added `_alias_to_domain()` (To-address → business domain) and `InboundEmail.to` (the Gmail `To` header wasn't previously fetched — without it, domain routing would have always fallen through to `general`). `scheduler.py` already had `_job_email_inbound` wired to `run_email_poll()` — no scheduler change needed. Added `test_inbound_handler.py`. **Manual step required before enabling `EMAIL_INBOUND`:** add `external_id` and `sender_id` (Single line text) to the Airtable `Leads` table, then refresh `schema_cache.json` (`schema_audit.py`) — confirmed via a local test run that `airtable_gateway` currently drops both fields as "unknown field ... not in schema_cache".
- Added `docs/operations/DEPLOYMENT.md` — deploy guide for Render + Vercel.
- Added `docs/operations/RUNBOOK.md` — incident response for 6 common failure scenarios.
- Updated `README.md` — added WhatsApp channel, Twilio env vars, operations docs to documentation map.
- Added Screen Filter Gateway (`SCREEN_CONFIGS` + `_build_formula()`) to `tma_api.py` — `GET /api/leads` now supports `?view=active|monitoring|all`; `_get_project_cards()` / `get_project_dashboard()` wired to the same lead-filtering config (PR #75).

## 2026-06-12

- Added root `README.md` with runtime, environment, and documentation map.
- Added root `CHANGELOG.md`.
- Moved Airtable schema migration notes from `docs/governance/` to `docs/schemas/`.
