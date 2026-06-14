# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

"The Boss Bot" — a Hebrew-language Telegram/WhatsApp business assistant chatbot powered by Anthropic Claude (`app.py` is the Flask entrypoint, formerly `bot.py` per older docs — the live entrypoint is `app.py`). It serves multiple roles (owner, partner, manager, employee, lead, guest) across multiple business domains (real_estate, import, media, saas, finance, general), backed by Airtable as the CRM/data store, with optional Google Workspace, Twilio/WhatsApp, and a Telegram Mini App (TMA) frontend (`tma-frontend/`, React + Vite + TS).

Most comments, log messages, and docstrings in this codebase are in **Hebrew** — match that convention when editing existing files.

## Running locally

```bash
# Minimal — just the bot
ANTHROPIC_API_KEY=<key> TELEGRAM_TOKEN=<token> python3 app.py

# Full local dev with ngrok tunnel + webhook setup (requires .env from .env.example)
./run_local.sh
```

- Flask listens on `0.0.0.0:10000` by default (override with `PORT`).
- `TELEGRAM_TOKEN` must be in `<bot_id>:<secret>` format or `telebot.TeleBot()` raises `ValueError` at import time, preventing the server from starting.
- `startup_validator.validate_startup()` runs at import time in `app.py` and will hard-fail on missing critical env vars (see `.env.example` for the required set: `TELEGRAM_TOKEN`, `ANTHROPIC_API_KEY`, `ELIYAHU_CHAT_ID`, `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`).
- `/status` and `/schema` Telegram commands are owner/admin-only diagnostics; `format_startup_message()` from `startup_validator` reports env var state.
- Always use `python3`, not `python` (may not be on PATH).

## Tests

There is no pytest/unittest harness wired up — tests are plain scripts with their own runners:

```bash
python3 smoke_tests.py        # static AST-based checks: imports resolve, required tools registered, no old table names, etc.
python3 test_integration.py   # Identity → Router → Decision flow, mocked, no Flask/Anthropic/DB
python3 -m py_compile app.py  # quick syntax check (no linter config exists in the repo)
```

`core/router/test_router.py` similarly exercises the router in isolation — run it directly with `python3 core/router/test_router.py`.

When verifying behavioral changes to the webhook flow, start the server and POST simulated Telegram/WhatsApp webhook payloads with `curl` — there's no automated end-to-end suite.

## Architecture: Identity → Router → Context → Agent

Every inbound message in `app.py` flows through this fixed pipeline (see the comment block at the top of `app.py`):

```
resolve_identity → route_request → build_context → run_agent
```

1. **Identity** (`identity.py`): `resolve_identity(channel, external_id)` returns an `Identity` with a `role` (owner > partner > manager > employee > lead > guest > readonly, ranked via `Role.rank`), `tenant_id`, and `domain_id`. **"There is no action without identity."** Hard rule: `identity is None` must hard-fail, never silently fall back.
2. **Router** (`core/router/`): `route_request()` composes several sub-routers — `channel_router`, `domain_router`, `intent_router`, `risk_router` — into a single `RouteDecision` (`core/router/route_decision.py`) carrying `Intent`, `RouterDomain`, `Risk`, and a `Handler` (e.g. `AGENT`, `APPROVAL`, blocked/clarify flows). `app.py._safe_route()` wraps `route_request` with a fallback `RouteDecision`.
3. **Context** (`context.py`): `build_context()` assembles the system prompt / conversation context for the model, pulling in `domain_prompts.py` (per-domain prompt variants) and short-term memory from `memory_store.py`.
4. **Agent** (`run_agent` in `app.py`): drives the Claude tool-use loop (`MAX_TOOL_TURNS = 3`, `AGENT_TIMEOUT = 25`s), calling tools via the dispatcher and verifying outputs with `core.anti_hallucination` (`verify_execution`, `sanitize_agent_response`).

## Tool execution: Registry decides, Dispatcher executes

This is the security-critical core — **"Iron rule: no Tool without a permission check."**

- `tool_registry.py`: declarative metadata per tool (`ToolMeta`): `roles_allowed`, `tenant_scoped`, `requires_approval`, `high_risk`, `read_only`. `enforce(tool, identity)` from this module is the gate — it raises `ToolDenied` if the role isn't permitted.
- `tools/dispatcher.py`: the **single entry point** for all tool execution — `dispatch_tool(name, inputs, identity)`. It performs dedup checks (`_DEDUP_FIELDS`), table-name aliasing (`_ALIAS_MAP`), and routes to the concrete tool implementations in `tools/` (drive, calendar, gmail, sheets, airtable, contact_resolver).
- `tools/airtable_security.py`: `enforce_tenant_scope()` must be called before any raw Airtable read/write to prevent cross-tenant data leaks; `audit_log_airtable()` logs all access.
- `_MEMORABLE_TOOLS` in `app.py` lists tools whose results get persisted to memory across agent turns (e.g. `airtable_add`, `calendar_create_event`).
- **Never** import tool functions (e.g. from `crm` or `airtable_tools`) directly outside of the dispatcher/digest/scheduler/collector modules — this bypasses identity and tenant enforcement (see the grep check in `docs/governance/SECURITY_CHECKLIST.md`).

### Approval flow

High-risk/irreversible actions (`requires_approval=True` in the registry, e.g. `gmail_send_draft`, `crm_mark_payment_paid`) don't execute immediately. They route through `Handler.APPROVAL`:
- `app.py._queue_approval()` stores a pending action keyed by `chat_id` in `_pending_approvals` / `event_bus.pending` (`PendingActionsStore`/`EventBus` in `event_bus.py`).
- The user confirms/cancels with natural-language words from `_CONFIRM_WORDS` / `_CANCEL_WORDS` (Hebrew + English + emoji), handled in `_handle_approval_callback`, which **re-runs `enforce()` for the original requester** immediately before dispatching — never trust a stored decision blindly.

## Adding a new tool — checklist

(from `docs/governance/SECURITY_CHECKLIST.md`, required before merging)
1. Implement it in the relevant `tools/*.py` module.
2. Add its JSON schema to `tools/schemas.py`.
3. Register it in `tool_registry.py` with correct `roles_allowed` (and `requires_approval`/`high_risk`/`tenant_scoped` as needed).
4. Wire it into `tools/dispatcher.py`'s dispatch switch.
5. Run the grep checks in `docs/governance/SECURITY_CHECKLIST.md` (e.g. confirm every `case "..."` in the dispatcher has a matching registry entry).

## Other key modules

- `event_bus.py`: pending-action store + audit/event log used by the approval flow and lead-recovery features.
- `feature_flags.py`: runtime + env-based flags; `EMERGENCY_STOP_*` flags persist across restarts via `/tmp/emergency_flags.json`.
- `core/anti_hallucination.py`: post-hoc verification that the agent's claimed actions actually happened (`verify_execution`) and response sanitization (`sanitize_agent_response`).
- `core/lead_recovery.py`, `lead_qualifier.py`, `lead_memory.py`, `core/lead_events.py`: the lead lifecycle — qualification state machine, long-term memory, audit log, and recovery/follow-up logic.
- `crm.py`, `airtable_schema.py`, `airtable_tools.py`: the Airtable-backed CRM repository and table/field name constants — prefer the Hebrew table aliases defined here over hardcoded English names (see `_ALIAS_MAP` / `OLD_TABLE_NAMES` checks in `smoke_tests.py`).
- `scheduler.py`: background jobs (daily digest, overdue payments, cleanup, security reminders) registered via the `schedule` library and run on a background thread started from `app.py` (`start_scheduler`).
- `tma_api.py`: Flask blueprint registered onto the main app, serving the Telegram Mini App's REST API (projects, leads, approvals, game/quests, finance pulse). Auth is via `require_tma_auth` decorator validating Telegram `initData`.
- `config.py`: WhatsApp number → business domain mapping (`CHANNEL_DOMAINS`) — add new channel mappings only here.
- `guards/`: `idempotency`, `rate_limiter`, `circuit_breaker` — cross-cutting reliability wrappers re-exported from `guards/__init__.py`.

## Frontend (`tma-frontend/`)

React + TypeScript + Vite + Tailwind Telegram Mini App.

```bash
cd tma-frontend
npm run dev       # vite dev server
npm run build     # tsc && vite build
npm run preview
```

## Planning & docs conventions

- `ROADMAP.md` is **the single source of truth** for planned work — "every batch starts by reading the ROADMAP, not from memory." Other planning docs (`BOSS_MASTER_PLAN_*.md`, `BOSS_CURRENT_STATE.md`, `boss_bot_summary.md`) are archives/snapshots, not authoritative.
- `docs/governance/SECURITY_CHECKLIST.md` defines when a security review is required (new file touching `dispatcher`/`crm`/`identity`/`auth`, new tool, new role, new endpoint) and the manual checklist to run before merging to main — consult it whenever touching identity, tenancy, registry, or endpoint auth.
