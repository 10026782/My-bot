# Changelog

All notable repository-level changes should be recorded here.

## Unreleased

- Added `docs/operations/DEPLOYMENT.md` — deploy guide for Render + Vercel.
- Added `docs/operations/RUNBOOK.md` — incident response for 6 common failure scenarios.
- Updated `README.md` — added WhatsApp channel, Twilio env vars, operations docs to documentation map.
- Added Screen Filter Gateway (`SCREEN_CONFIGS` + `_build_formula()`) to `tma_api.py` — `GET /api/leads` now supports `?view=active|monitoring|all`; `_get_project_cards()` / `get_project_dashboard()` wired to the same lead-filtering config (PR #75).

## 2026-06-12

- Added root `README.md` with runtime, environment, and documentation map.
- Added root `CHANGELOG.md`.
- Moved Airtable schema migration notes from `docs/governance/` to `docs/schemas/`.
