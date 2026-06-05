# BOSS Bug Audit Report

Date: 2026-06-05  
Mode: read-only audit report. No production code changes in this patch.

## Summary

- Guards reviewed first, then the repository was reviewed file by file.
- This report lists concrete likely bugs only; style/refactor suggestions are omitted.
- Severity: Critical / High / Medium / Low.

---

## Guards

### `guards/__init__.py`

- No direct bug found. It re-exports guard singletons and helpers as expected.

### `guards/idempotency.py`

- Medium: In-memory idempotency state is per Python process. In a multi-worker deployment, duplicate Telegram/WhatsApp retries can be processed by different workers and bypass the guard.
- Low: The duplicate key uses only the first 16 hex chars of SHA-256. Collision risk is low, but non-zero under high volume.

### `guards/rate_limiter.py`

- Medium: Rate limiting is in-memory and per process, so multi-worker deployments multiply the real request limit.
- Medium: `_windows` is a `defaultdict(deque)` keyed by caller-controlled identifiers. Many unique keys can grow memory until process restart because cleanup only happens for the current key.

### `guards/circuit_breaker.py`

- Medium: HALF_OPEN behavior resets `_failures` to `0` before the trial call. If that trial fails, the breaker records only one failure and effectively closes until five more failures, instead of reopening immediately.

---

## File-by-file audit

### `abandoned_lead_worker.py`

- Medium: `_parse_sessions()` depends on parsing the human-readable `airtable_get()` output. If Airtable output formatting changes, abandoned-session detection silently returns no leads.
- Low: The module contains self-test monkeypatching for a top-level `airtable_tools` module; this is test-only, but it differs from production import paths.

### `action_validator.py`

- High: `resolve_contact` exists in tool schemas and dispatcher, but is missing from `_REQUIRED`; unknown-tool validation can block it.
- Medium: Required-field validation treats empty `{}` / `[]` as present, so empty Airtable fields or empty Sheets rows can pass validation.

### `ad_attribution.py`

- High: Several paths expect structured Airtable records, while `airtable_get()` returns a formatted string; attribution reports can fall back to mock data or fail to parse production data.
- High: Lead attribution fields such as `utm_source`, `utm_medium`, and conversion status values may not match current schema validation.
- Medium: Airtable formulas interpolate `memory_key` without escaping quotes.

### `airtable_schema.py`

- Low: Back-compat CRM enums still include English deal/payment values that do not match Hebrew production select values. They can encourage incorrect writes in older code paths.

### `app.py`

- High: WhatsApp webhook has no Twilio signature validation.
- Medium: Voice webhooks also have no Twilio signature validation.
- High: Router-level `Handler.APPROVAL` returns a static approval response and does not enter the real queued approval flow.
- Medium: `/schema` command has no identity/role guard.
- Medium: `route.notify_owner` is logged but not acted on.

### `audience_intelligence.py`

- High: `load_all_leads()` treats `airtable_get()` as a structured list; production path can fall back to mock data.
- Medium: Score field lookup uses English variants; Airtable production field is `score ציון`.
- Medium: New leads are classified before hot leads, so a hot new lead can be labeled `new`.

### `config.py`

- Medium: `get_domain()` accepts one argument, while at least one caller historically passed channel and sender. Any remaining two-argument call will raise `TypeError`.
- Medium: `DEFAULT_DOMAIN = "general"` does not have a matching domain prompt config and falls back to real estate behavior.

### `context.py`

- Low: `build_context()` mutates `identity.domain_id` in place. It is safe for per-request identities, but fragile if identities become cached.
- Low: Israel timezone handling uses a month-based DST heuristic and can be off near DST transitions.

### `core/__init__.py`

- No direct bug found. Empty package initializer.

### `core/anti_hallucination.py`

- Medium: Success language with no tool calls is not flagged; only "all tools failed" is treated as hallucination evidence.

### `core/lead_recovery.py`

- Critical: Recovery scans deal-list output while parser expects lead/tier/last-active shape. The recovery engine likely skips or misclassifies real leads.
- Medium: If `feature_flags` import fails, recovery continues instead of failing closed.

### `core/learning_engine.py`

- High: Missing `core/lead_events.py` causes learning to use mock events. If enabled, owner insights can be generated from fake data.
- Low: Average days-to-close depends on mock-shaped `days_ago` fields that real events may not provide.

### `core/router/__init__.py`

- No direct bug found. Package export file only.

### `core/router/channel_router.py`

- Medium: Channel-specific tool override is computed by router but not used downstream, so channel-specific routing is ineffective.

### `core/router/domain_router.py`

- No new concrete bug found in this pass.

### `core/router/intent_router.py`

- No new concrete bug found in this pass.

### `core/router/risk_router.py`

- High: High-risk intents for senior users return `Handler.APPROVAL`, which currently dead-ends before the tool-level approval queue.

### `core/router/route_decision.py`

- Low: Comments and actual confidence thresholds diverge, which can mislead future maintenance.

### `core/router/router.py`

- Medium: `tool_override` is appended to logs only and is not enforced or passed to dispatch.
- Low: Low-confidence approval can turn into CLARIFY while `needs_approval` remains true, leaving mixed semantics.

### `core/router/test_router.py`

- No direct runtime bug found. Test helper only.

### `core_knowledge.py`

- Medium: Dynamic context caches `data.json` and does not reload unless `invalidate()` is called, so prompts can contain stale business data.

### `creative_generator.py`

- Low: Assumes `response.content[0].text` exists. Empty Anthropic content raises `IndexError`, caught as a generic failure.
- Low: Command entrypoint appears unwired from the main app.

### `crm.py`

- Medium: Contact search formula still uses English `{Name}` and `{Company}` instead of Hebrew production fields `שם` and `חברה`; searches can return no results.
- Medium: Deal status code paths still use English legacy `DealStatus` values for Hebrew `שלב` field.

### `daily_collector.py`

- Medium: Collector doc says "today", but memory source can include the full TTL window rather than day-bounded conversations.
- Medium: JSON parse failure is treated as all-clear, potentially hiding extraction errors.

### `daily_digest.py`

- High: "Tasks completed yesterday" section queries all completed tasks without a yesterday date filter.
- Medium: Upcoming payments exclude payments due today because the formula uses `IS_AFTER({תאריך}, today)`.

### `data_engines.py`

- Medium: KPI formulas still use English fields/statuses (`Status`, `Active`, `Overdue`) against Hebrew production tables.

### `diagnose_airtable.py`

- Low: Diagnostic script exits on missing Airtable env vars and cannot run partial offline diagnostics.

### `domain_prompts.py`

- High: `import` domain is missing and falls back to real estate prompts, causing wrong qualification questions for import leads.

### `email_inbound.py`

- High: Missing Google auth/import can return mock emails; if enabled, fake messages can be routed.
- High: Polls unread mail but does not mark messages read/archive after routing, so the same email can be processed repeatedly.

### `event_bus.py`

- Medium: Pending approvals are in-memory only and are lost across process restarts or different workers.
- Low: 8-character action IDs have limited entropy for concurrent pending actions.

### `feature_flags.py`

- High: Flag names use raw keys like `LEAD_QUALIFIER`, while provisioning/comments often emit `FEATURE_LEAD_QUALIFIER`; features can remain disabled.

### `followup_engine.py`

- High: Scans only in-memory `lead_memory`; if no runtime writer populated it, follow-up scans return zero candidates.
- Medium: Approval requests can run with empty owner chat IDs and still inflate counters.

### `health_monitor.py`

- High: `get_health_status()` signature does not match the two-argument call in `app.py`; `/health` can raise `TypeError`.

### `identity.py`

- Medium: `can_access_domain()` returns true for most non-partner roles, so domain isolation is not enforced there.
- Low: Unknown Telegram users get `READONLY`, while unknown WhatsApp users become `LEAD`; behavior is asymmetric.

### `interaction_engine.py`

- High: Calendar adapter imports `calendar_tools` as a top-level module and expects a list, while the tool returns a string; real calendar data likely falls back to mock behavior.
- Medium: Business memory table naming appears inconsistent with TMA naming in other modules.
- Medium: Search formula embeds user query without escaping quotes.

### `knowledge_engine.py`

- Low: Deal-intelligence block is appended without subtracting from token budget.
- Low: Supabase/API errors are swallowed as empty data.

### `lead_memory.py`

- High: No clear runtime writer feeds `lead_memory.update()`, so memory-dependent features can remain empty.
- Medium: `get()` returns a live `LeadState` object; callers can mutate without lock protection.
- Medium: Domain/channel changes do not mark state dirty and may not flush.

### `lead_qualifier.py`

- Medium: Qualification flow appears weakly wired into main handlers; it may be unreachable for normal message paths.
- Medium: Final answer collection depends on `session_store.get()` returning a live dict reference.

### `memory.py`

- Low: Appears unused; production uses `memory_store.py`. Future callers may assume this is active memory when it is not.

### `memory_store.py`

- Low: `is_fresh()` uses `defaultdict`, creating empty user entries for unknown IDs.

### `payment_reminder.py`

- High: "exactly 3 days away" logic uses a 3-day range and can alert multiple days.
- High: Parsed reminder due date is assigned as today+3 instead of reading the actual due date from the CRM line.
- Medium: Overdue alerts only fire on exact day counts 1, 3, and 7.

### `profile.py`

- Medium: Shallow merge of profile data can drop nested default preference keys.
- Medium: Birthday reminder logic skips birthdays already passed in the current year instead of rolling to next year.

### `project_timeline.py`

- Medium: Dates are computed at import time and become stale in a long-lived process.
- Medium: Record creation has no dedup and can duplicate timeline rows.

### `router.py`

- Low: Legacy router is mostly unused. Hebrew topic detection is simplistic and can misroute mixed input.

### `scheduler.py`

- Low: Bad day/time env values can prevent scheduler startup; app catches it, but background jobs silently do not run.

### `schema_intelligence.py`

- High: Unknown tables pass validation instead of failing closed.
- Low: Lead status options are uppercase while prompts/tools may send lowercase.

### `score_display.py`

- Medium: `int(qualification.get("score", 0))` can raise on malformed score strings.

### `session_store.py`

- High: `_load_from_db()` does not restore `answers`, so restarted sessions can lose qualification state.
- Medium: Sender is embedded in Airtable formula without escaping.

### `shabbat_guard.py`

- Medium: Uses fixed UTC+2 and approximate Shabbat hours; can allow/block messages at wrong times.

### `smoke_tests.py`

- Low: It sets dummy critical env vars before importing `app`, which is useful for smoke tests but does not validate real deployment secrets.

### `startup_validator.py`

- Medium: `TELEGRAM_TOKEN` is only checked as non-empty; malformed tokens can still crash `TeleBot()`.
- Low: `format_startup_message()` repeatedly validates the same rules.

### `tenant_provisioner.py`

- High: Env snippet emits `FEATURE_*` flags that `feature_flags.is_enabled()` does not read.
- Medium: Provision can return `ok=True` even if saving tenant to Airtable fails.

### `test_integration.py`

- Low: `MockIdentity` lacks properties used by newer identity-aware code paths.
- Low: Some restricted-flow tests are duplicated.

### `tma_api.py`

- Medium: Project dashboard filters leads by domain but deals/tasks are fetched more globally, risking cross-domain data.
- Low: Formula values for slug/domain are not escaped.

### `tool_registry.py`

- High: Several CRM tools exist in `tools/schemas.py` but are missing from registry and dispatcher.
- Medium: `resolve_contact` is registered but not exposed through role tool lists in normal agent context.

### `tools/__init__.py`

- No direct bug found. It exposes dispatcher and schemas.

### `tools/airtable_security.py`

- Medium: `identity=None` is not guarded before `identity.is_internal`.
- Medium: `tenant_id` is interpolated into Airtable formula without escaping quotes.

### `tools/airtable_tools.py`

- Low: `airtable_get()` has no pagination and returns a formatted string, which encourages parser bugs in callers expecting records.

### `tools/calendar_tools.py`

- No direct bug found. Re-export only.

### `tools/contact_resolver.py`

- High: Production parser expects `crm_find_contact()`-style output but uses `crm_list_contacts()` output, so record IDs/email/phone can be empty.
- High: `crm_list_contacts()` does not include email, so resolver cannot reliably supply addresses for Gmail flows.

### `tools/dispatcher.py`

- Medium: External Airtable read filter uses `{user_id}` rather than the tenant/schema fields used elsewhere.
- Medium: Non-Leads `airtable_add` injects `tenant_id`, but schema sanitization can strip it.

### `tools/drive_tools.py`

- No direct bug found here; behavior comes from `tools/google_tools.py` re-export.

### `tools/gmail_tools.py`

- No direct bug found here; behavior comes from `tools/google_tools.py` re-export.

### `tools/google_tools.py`

- Medium: OAuth refresh response status/errors are not surfaced; callers get generic missing-auth behavior.
- Medium: Gmail/Drive functions often do not check HTTP status before parsing/returning content.
- Medium: Sheets search query embeds spreadsheet name without escaping quotes.

### `tools/schemas.py`

- High: CRM tools are advertised to the model but many are not implemented in registry/dispatcher.
- Low: `sheets_append` schema uses `sheet_name` while lower-level implementation names it `spreadsheet_name`; dispatcher maps it today.

### `tools/sheets_tools.py`

- No direct bug found here; behavior comes from `tools/google_tools.py` re-export.

### `voice_adapter.py`

- High: NAME step uses DTMF digits, not speech, so spoken names are not captured.
- High: NAME-state handling can store the same digits as both name and interest.
- Medium: Voice leads bypass the lead qualifier scoring pipeline.

### `worker.py`

- Medium: `/worker/trigger` in `app.py` does not call `run_proactive_check()`, so this worker is not actually triggered by that route.
- Medium: `days_left` uses datetime arithmetic against midnight UTC; tasks due tomorrow can be classified as today depending on current time.
- Medium: Telegram Markdown is not escaped for task names/statuses.
- Medium: `schedule_background_worker()` can start duplicate infinite daemon threads if called more than once.

### `workers/__init__.py`

- No direct bug found. Empty package initializer.

### `workers/survey_worker.py`

- Medium: `_bot()` constructs `TeleBot` with an empty token if `TELEGRAM_TOKEN` is missing; survey send fails at runtime and is swallowed into logs.
- Medium: Supabase insert response is not checked, so failed survey persistence can be silent.
- Low: `contact_name` is inserted into Markdown without escaping.

---

## Validation performed

- `python3 -m py_compile worker.py workers/survey_worker.py workers/__init__.py` passed.
- `import worker; import workers.survey_worker` passed.
- `git status --short --branch` was checked before writing this report.
