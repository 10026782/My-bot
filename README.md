# The Boss Bot

Hebrew-language Telegram, WhatsApp, and Telegram Mini App assistant for business operations, CRM workflows, lead handling, approvals, and the BOSS game/check-in screens.

## Runtime

- Backend: Python Flask in `app.py`
- Telegram webhook: `POST /telegram`
- WhatsApp webhook: `POST /whatsapp` (Twilio)
- Telegram Mini App API: `tma_api.py`
- Mini App frontend: `tma-frontend/` (React + Vite)
- CRM/data store: Airtable

## Required Backend Environment

See `.env.example` for the full list. Core production variables include:

- `TELEGRAM_TOKEN`
- `ANTHROPIC_API_KEY`
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `RENDER_APP_URL`
- `TMA_ALLOWED_ORIGINS`

## Local Development

```bash
ANTHROPIC_API_KEY=<key> TELEGRAM_TOKEN=<bot_id:secret> python3 app.py
```

Flask listens on `0.0.0.0:10000` by default unless `PORT` is set.

## Documentation Map

| מסמך | נושא |
|------|------|
| `AGENTS.md`, `CLAUDE.md` | Agent / runtime notes (incl. shared-checkout / concurrent-session rules in `AGENTS.md`) |
| `BOSS_CURRENT_STATE.md` | Current system state |
| `ROADMAP.md` | Feature roadmap (single source of truth) |
| `FILE_OWNERSHIP.md` | Which file owns which responsibility |
| `MODULE_RULES.md` | Architecture rules (10 iron laws) |
| `docs/operations/DEPLOYMENT.md` | Deploy to Render + Vercel |
| `docs/operations/RUNBOOK.md` | Incident response |
| `docs/governance/SECURITY_CHECKLIST.md` | Security checklist |
| `docs/governance/ARCHITECTURE_DRIFT_MAP.md` | Known drift |
| `docs/schemas/MIGRATION_AIRTABLE_ENGLISH_SCHEMA.md` | Airtable schema migration |

## Verification

This repository has lightweight smoke scripts but no full automated test suite. For narrow Python changes, run:

```bash
python3 -m py_compile app.py
```

For Mini App frontend changes, run from `tma-frontend/`:

```bash
npm run build
```
