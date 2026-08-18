# Metabase / `usage_events` Deep Audit — 2026-08

> Follow-up to the Money Printer/Worker External Tool Audit
> (`docs/research/MONEY_PRINTER_WORKER_EXTERNAL_TOOL_AUDIT_2026-08.md`), which
> flagged Metabase as `DEEP AUDIT` against the already-populated, unread
> `usage_events` table. This is an audit only — no install, no deploy, no
> credentials, no DB mutation, no schema change.

Base SHA: `d2f9481ace7a7f422d75f4bd306069c720f283a2` (`origin/main`).
Worktree: `../My-bot-worktrees/metabase-deep-audit`, branch `audit/metabase-usage-events`.

## A. What `usage_events` actually contains

Schema source: `core/migrations/002_usage_events.sql`. Writer: `core/usage_telemetry.py::record_usage()` (and its `record_llm_usage`/`record_stt_usage` wrappers).

Columns: `id`, `ts`, `provider` (`anthropic`|`openai`), `service` (`text`|`stt`), `model` (exact provider model string), `source` (calling code site), `caller` (free-form text), `unit` (`tokens`|`seconds`), `quantity_in`, `quantity_out`, `cost_usd`, `cost_is_estimate`, `request_id`, `meta` (JSONB), `created_at`.

**No tenant_id, user_id, chat_id, tool/action name, outcome, or lead/revenue linkage columns exist.** These would have to come from `caller`/`meta`, which are unstructured and inconsistently populated (see below) — not real columns Metabase (or anything else) can filter/aggregate on natively.

### Writers (6 call sites, grepped directly)

| Call site | `source` | `caller` value | Real tenant/user info? |
|---|---|---|---|
| `app.py` (`run_agent`, the main chat loop) | `"run_agent"` | `ctx.memory_key` = `f"{tenant_id}:{user_id}"` (`identity.py:130`) | **Yes** — the only site that does |
| `llm_fallback.py::call_openai_text` | passed-through `source` param | same as `source` (code-site name, not caller identity) | No |
| `llm_fallback.py::call_anthropic_text` | passed-through `source` param | same as `source` | No |
| `voice_stt_adapter.py` | `"voice_stt_adapter"` | hardcoded `"voice_stt_adapter._transcribe_openai"` | No |
| `interaction_engine.py` | `"interaction_engine"` | hardcoded `"interaction_engine.analyze_interaction"` | No |
| `providers/anthropic_shim.py` | `"providers.anthropic_shim.AnthropicLLMProvider.generate"` | hardcoded `"anthropic_shim"` | No — also currently dead code, zero live callers (per `CLAUDE.md`'s F13 note) |

`run_agent` is the primary chat path and almost certainly the dominant share of call volume, but it is not all of it — `daily_collector.py`, `creative_generator.py`, `lead_qualifier.py`, `tma_api.py` route through `llm_fallback.py` per `CLAUDE.md`, and none of those preserve who the end user/tenant was. A per-tenant cost dashboard would be accurate for `source = run_agent` rows only, silently blank for the rest.

`meta` JSONB is populated only by the OpenAI-fallback path (`{"fallback_from": "anthropic"}`) — otherwise NULL everywhere.

`cost_usd` is trustworthy: `core/model_pricing.py` has a real per-model `$/1M tokens` table (`claude-sonnet-4-6`, `claude-haiku-4-5-20251001`, etc.) independent of `cost_monitor.py`'s separate (and known-buggy-key) pricing table, with `cost_is_estimate` correctly flagging the fail-safe path for an unrecognized model. **No exception/error/failure rows exist** — `record_usage()` is only called after a successful provider response, so this table is a record of successful, billed calls only, never a source for error-rate dashboards.

**Nothing else writes to Postgres for observability.** Grepped `worker.py` and `scheduler.py` directly — neither imports `usage_telemetry` nor touches any DB table. There is zero job/run/failure telemetry for the background worker or scheduler today; that gap is orthogonal to `usage_events` and is already tracked separately (Sentry/GlitchTip/Axiom/healthchecks.io rows, same index, from the prior audit).

## B. AVAILABLE NOW / NEEDS NEW EVENTS / NOT AVAILABLE

```text
AVAILABLE NOW (from usage_events as it is today)
- LLM/STT cost and call-volume by day (get_daily_usage / get_usage_window already implement this)
- Breakdown by provider, service, model
- Breakdown by source (which code path is spending money)
- Estimated vs. confirmed cost split (cost_is_estimate)
- Cost/volume trend over any date range
- Per-tenant/user cost breakdown — but ONLY for source="run_agent" rows
  (requires splitting the caller string "tenant_id:user_id" in SQL; the
  other 5 sources have no real identity in caller)

NEEDS NEW EVENTS (schema/instrumentation change required — out of scope for this audit)
- Tool/action-level cost or usage (which dispatcher tool a call was for)
- Success/failure or error-rate dashboards (only successful calls are recorded at all)
- Worker/scheduler job telemetry (started/completed/failed/latency/last-run) — nothing writes this anywhere
- Lead/campaign/channel outcome linkage (no lead_id, no revenue field)
- Consistent tenant/user attribution across all 6 write sites (5 of them don't carry it)

NOT AVAILABLE (would need a different data source entirely, not just more usage_events columns)
- Revenue attribution, "cost per outcome", campaign ROI — Money Printer's outcome/revenue
  stages don't exist as data anywhere in this repo yet, this table included
- Leads generated/enriched/converted counts — that's Airtable CRM data, not usage_events
```

## C. Architecture

Confirmed safe shape, matching the prior audit's constraint:

```text
Render Postgres (existing, $14/mo total for staging+prod)
      ↓ read-only role, SELECT-only on usage_events
Metabase (self-hosted, own small app-db)
      ↓
owner-only dashboard, internal
```

Never:

```text
Metabase → write access → any BOSS table
```

`core/database.py::get_pool()` reads `DATABASE_URL` (Render's standard connection string) or discrete `DATABASE_*` env vars. No code path currently creates or references any restricted-privilege Postgres role — a read-only role for Metabase does not exist today and would have to be created (`CREATE ROLE ... GRANT SELECT ON usage_events`), which is standard Postgres/Render Postgres functionality but is itself a DB-config change, out of scope for this audit to perform.

## D. Security

| Control | Finding |
|---|---|
| Read-only DB role | Does not exist yet — would need to be created and scoped to `SELECT` on `usage_events` only (not the whole schema; `usage_events` sits in the same Postgres instance as claims/turn-state tables per `core/database.py`'s docstring) |
| Schema/table restriction | Must be enforced at the Postgres `GRANT` level, not just Metabase's own permission UI — Metabase permissions are a second layer, not a substitute for DB-level restriction |
| Network exposure | If Metabase is hosted as another Render service in the same account/region, it can use Render's **internal** Postgres connection string (private network, not public internet) — this is the safer option and avoids exposing Postgres externally at all |
| TLS | Render Postgres connection strings are TLS by default; no action needed |
| Credential storage | Metabase needs its own encrypted credential store for the DB connection (standard Metabase feature) — one more secret to manage/rotate |
| User authentication | Metabase has its own login/user system, separate from BOSS's Telegram-identity-based auth — a new auth surface, not reusing `identity.py` |
| Admin access | Must be owner-only initially, consistent with the rest of the repo's admin surfaces (`/status`, `/schema`) |
| Public links / embedding | Metabase supports public dashboard links and embedding by default in some configs — **must be explicitly disabled**; this is exactly the kind of accidental-exposure footgun the "no public dashboards" default guards against |
| Tenant exposure / PII | `usage_events` itself has no PII (no message content, no phone/email) — lowest-risk table in the schema to expose read-only. `caller` for `run_agent` rows does contain `tenant_id:user_id`, which is an internal identifier, not PII by itself |
| Query permissions | Self-hosted Metabase ships a SQL/native-query editor and (per current Metabase pricing research below) an AI SQL-generation feature — both should be owner-only if enabled at all, since ad-hoc SQL against a read-only role is safe *only as far as the role's grants go* |

Conclusion: a read-only connection is safe **if and only if** the Postgres role is genuinely `SELECT`-only on `usage_events` specifically (not the whole DB) and public links/embedding are turned off. Neither is automatic — both require explicit setup.

## E. Hosting options

Checked current Metabase pricing directly (metabase.com/pricing, fetched today):

| Option | Setup | Cost | Notes |
|---|---|---|---|
| Metabase OSS, self-hosted (Docker) | Docker image + its own app-db (recommend Postgres, not embedded H2, for anything beyond a throwaway eval) + hosting | **$0 license** (AGPL-3.0) + hosting cost | Free forever, unlimited questions/dashboards/users — this is the only self-hosted path |
| Metabase Cloud | Managed, no ops | **No free tier** — Starter $90/mo (5 users, yearly) / $100/mo monthly, Pro $517.50/mo, Enterprise custom ($20k+/yr) | Confirmed via live pricing page; ruled out purely on cost — BOSS has 1-2 internal users, not 5+ |
| Render (self-hosted Docker web service) | Add a new Render web service running the Metabase Docker image | Render's cheapest paid web-service tier is the same order of magnitude as the existing $7/mo Postgres instances (exact current tier pricing should be re-verified at adoption time — Render's pricing page did not load statically) | Consistent with the repo's existing hosting; can use Render's internal network to reach Postgres without public exposure |
| Alternative cheap hosting (Fly.io, Railway, a VPS) | New provider relationship, new billing, new ops surface | Similar or marginally cheaper | Not worth it purely to save a few dollars/month when Render is already the operational home for everything else |

**Self-hosted is not free once hosting + maintenance are counted** — it avoids only the license cost. Real ongoing cost: one more Docker service to deploy/monitor/upgrade, one more (small) database to back up, one more login system to manage, security-patch cadence for a Java application with a SQL/AI query surface.

## F. Compare alternatives

| Option | Setup | Cost | Business UX | Maintenance | Read-only safety | Fit |
|---|---|---|---|---|---|---|
| Metabase (self-hosted) | New Docker service + app-db + read-only role | ~$7-10/mo hosting, $0 license | Good — proper charts/filters/scheduled reports, but built for exploring many tables, not the ~5 fields BOSS has today | New service to patch/upgrade/back up | Safe if role scoped correctly (see §D) | Overkill for one table |
| Grafana (self-hosted or Cloud) | Similar new-service burden; Grafana Cloud already rejected in the prior audit at BOSS's scale | Cloud has hard caps that don't fit even trivially; self-hosted has the same new-service cost as Metabase | Built for metrics/timeseries, not built for "business explains this table to itself" | Same class of burden as Metabase | Same class of safety story | Wrong tool shape — Grafana wants a metrics backend (Prometheus-style), not ad-hoc SQL over a Postgres table |
| **Custom minimal dashboard, reusing existing code** | A single owner-only Flask route (or an addition to `tma_api.py`'s existing owner-gated surface) rendering `core/usage_telemetry.py::get_daily_usage()` / `get_usage_window()`, which **already exist and are already correct** — just currently called by nothing | $0 — no new service, no new hosting line, no new DB role (reuses the existing app's own Postgres connection) | Minimal — a table of numbers, no charts, no self-serve filtering — but answers exactly the question currently unanswered ("what did we spend today, on what") | None beyond the existing app's own deploy cycle | Read path only, reuses the app's existing DB connection and existing owner-only auth pattern (`/status`, `/schema`) — no new attack surface at all | **Best fit for the actual, narrow, current need** |
| SQL queries / manual reporting | `psql` against the existing DB whenever someone wants a number | $0 | Worst UX, requires DB access + SQL knowledge each time | None | Whoever has DB access already has full read (and write) access — no scoping at all | Fine as a stopgap, not a real answer |

The custom-dashboard option isn't a made-up alternative — `get_daily_usage()`, `get_trailing_hour_usage()`, and `get_usage_window()` in `core/usage_telemetry.py` already implement exactly the "spend by day/model/source" aggregation Metabase would be asked to do, and grepping the whole repo confirms **zero callers use any of them today**. The unread-table gap the prior audit found is really an unread-*function* gap — the aggregation layer already exists, nothing surfaces it.

## G. Money Printer fit

| Money Printer stage | Supported by `usage_events` today? |
|---|---|
| Leads generated / enriched | No — that's Airtable CRM data, not in this table at all |
| Actions executed / follow-ups | No — no tool/action column |
| Outcomes / revenue attribution | No — no lead_id, no revenue field, no outcome field anywhere in the schema |
| Cost per outcome | No — cost side exists (per-call `cost_usd`), outcome side doesn't; can't join without a lead_id this table doesn't have |
| Campaign/channel results | No — no campaign/channel field |
| Cost of running Money Printer itself (if built) | **Yes, already** — any future Money Printer LLM call routed through `record_llm_usage()`/`record_usage()` would show up here for free |

Money Printer's revenue/outcome side needs new instrumentation (elsewhere — likely Airtable/`lead_events`-adjacent, not this table) before Metabase or anything else could dashboard it. `usage_events` only ever answers "what did the AI cost", never "what did it produce."

## H. Worker fit

`worker.py`/`scheduler.py` write **no events anywhere** — not to `usage_events`, not to any other table. There is nothing for Metabase to dashboard for worker jobs today; this is a documented gap, not something this audit can partially satisfy. (It's the same gap the prior audit's healthchecks.io/Sentry/Axiom candidates target — those are the right fix for worker observability, not Metabase.)

## I. Cost verdict

Does Metabase save enough build/ops effort to justify another service? **No, not for the current, narrow need** — because the thing it would save (writing an aggregation query) is *already written* (`get_usage_window()`), and the thing it would cost (a new Docker service, its own app-db, backups, upgrades, a second login system, a SQL/AI query surface that needs to stay owner-only) is real and ongoing.

- Current incremental cost of doing nothing: the `usage_events` table keeps filling up, unread, exactly as now.
- Implementation effort for the custom-route alternative: small — wire an existing, already-tested aggregation function into an existing owner-only surface.
- Implementation effort for Metabase: new service provisioning, read-only role creation, public-link/embedding lockdown, its own app-db, first-run setup.
- Maintenance burden: custom route rides the existing app's deploy cycle at zero marginal cost; Metabase is a new thing to patch and keep patched (AGPL-3.0 Java app with a SQL surface).
- Avoided build effort: minimal, since the aggregation code already exists — Metabase's main remaining value-add over the custom route is charts/filters/scheduled email reports, not the underlying query.

**Verdict: `FUTURE`** for Metabase itself, with a **`SMALL SPIKE`** recommended on the custom-route alternative instead (see §L).

Revisit Metabase specifically when any of these becomes true: BOSS needs ad-hoc SQL exploration across *multiple* tables (not just `usage_events`), more than 1-2 non-engineer stakeholders want self-serve filtering/charts, or scheduled email reports become a real requirement — none of which is true today.

## J. Required decision (answers)

1. **Is Metabase a fit for `usage_events` today?** Technically yes (safe, low-cost architecture exists), but not the cheapest fix for the actual current need.
2. **What can really be measured today?** Cost/volume by day, provider, service, model, source; estimated-vs-confirmed cost; per-tenant cost only for the `run_agent` source.
3. **Which Money Printer metrics are still missing from the data?** All of them — leads, actions, outcomes, revenue, campaign attribution. None exist in `usage_events` or anywhere else yet.
4. **What would future event instrumentation need to add?** A `tool`/`action` field, consistent tenant/user attribution across all 6 write sites (not just `run_agent`), and — separately, in a different table — lead/outcome/revenue events with a joinable key.
5. **Is a read-only connection safe enough?** Yes, but only with an explicitly `SELECT`-only Postgres role scoped to `usage_events` and public links/embedding disabled — neither is automatic.
6. **Expected cost?** Self-hosted: ~$7-10/mo hosting (order of magnitude, re-verify Render's current tier pricing at adoption) + $0 license; Cloud: no free tier, $90+/mo — ruled out.
7. **Is it better than a custom dashboard?** No, not for the current need — the aggregation function already exists and has zero callers; a small owner-only route is cheaper on every axis (cost, new attack surface, maintenance) than standing up Metabase for one table.
8. **Is it better than Grafana for business analytics?** Both carry similar new-service burden; Grafana is metrics/timeseries-shaped and a worse fit for "explain this Postgres table" than either Metabase or a custom route, and Grafana Cloud was already rejected at BOSS's scale in the prior audit.

## K. Verification boundary

No Metabase install, Docker run, Render service creation, DB user/role creation, schema change, env var change, dashboard, or production connection was performed. All findings above come from reading `core/migrations/002_usage_events.sql`, `core/usage_telemetry.py`, `core/database.py`, `core/model_pricing.py`, `worker.py`, `scheduler.py`, `health_monitor.py`, grepping every writer/reader of `usage_events`-related functions across the repo, and one live pricing-page fetch each for Metabase and (attempted, inconclusive) Render.

## L. Top recommendation

**Single next step:** a small owner-only diagnostic route (Flask, following the existing `/status`/`/schema` pattern) that calls `core/usage_telemetry.py::get_daily_usage()` and renders it as a plain table — closes the "nothing reads `usage_events`" gap at zero marginal cost, zero new service, zero new DB role, and zero new auth surface, by using code that already exists and is already correct. Revisit Metabase only if/when the dashboarding need broadens past this one table.
