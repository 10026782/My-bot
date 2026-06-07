# BOSS CURRENT STATE

Audit date: 2026-06-07
Mode: Audit only. No production code changed. No commits created.

This document describes only what is implemented in the current codebase and what was confirmed by today's audit reports. Future plans, roadmap-only screens, TODO promises, and comments are ignored unless matching runtime code exists.

## Classification Key

- WORKING: implemented and reachable, with no current blocking issue found.
- PARTIAL: implemented and reachable, but limited, fragile, mock-dependent, schema-dependent, or missing some runtime path.
- STUB: route/module exists but returns TODO/mock/demo/waiting output instead of real behavior.
- BROKEN: implemented but currently fails, cannot import, or is blocked by a known runtime error.
- NOT IMPLEMENTED: no current runtime implementation found.

## Source Set Used

- Current codebase: `app.py`, `tma_api.py`, `tools/`, `core/`, `guards/`, workers, Airtable/CRM modules, frontend files.
- Current audit reports: `CORE_KNOWLEDGE_AUDIT_REPORT.md`, `TOOLS_DATAFLOW_AUDIT.md`, `TOOLS_DATA_SECURITY_AUDIT_REPORT.md`, `MEMORY_LEARNING_AUDIT_REPORT.md`, `WORKERS_GUARDS_AUDIT_REPORT.md`, `AUXILIARY_INTEGRATIONS_AUDIT_REPORT.md`.
- Current docs/audits: `SECURITY_CHECKLIST.md`, `ISSUES_6-10_DIAGNOSTIC.md`, `PATCH_REPORT.md`, `boss_bot_summary.md`.
- Roadmap/task files under `agents-*` were used only to verify names/status, not to count future plans as implemented.

## Current Runtime Entry Points

| Entry point | Status | Source | What exists today | Data source | Live in production | Limitations / audit link |
|---|---:|---|---|---|---|---|
| Telegram webhook | PARTIAL | `app.py:547-612` | Receives Telegram updates and calls `run_agent()` | Telegram update, Anthropic, memory, tools | Yes if webhook/token configured | Google tool import conflict can break tool chain; approvals can dead-end |
| WhatsApp webhook | PARTIAL | `app.py:614-648` | Receives Twilio WhatsApp POST and calls `run_agent()` | Twilio form data, optional UTM, Anthropic | Yes if Twilio points to `/whatsapp` | No Twilio signature validation found; UTM write can run before lead exists |
| Voice IVR | PARTIAL | `app.py:685-702`, `voice_adapter.py` | Twilio voice endpoints and IVR state machine | Twilio form data, RAM sessions, optional Airtable | Yes if `VOICE_IVR` enabled and Twilio configured | No signature validation; lead write likely schema mismatch |
| Worker trigger | PARTIAL | `app.py:653-673` | POST endpoint can run `run_agent()` for supplied chat/event | Request JSON, `WORKER_SECRET` | Yes if secret configured | Can act as arbitrary chat_id if secret leaks |
| TMA blueprint | PARTIAL | `app.py:64-65`, `tma_api.py` | Registers `/api/*` endpoints | Telegram initData/dev header, Airtable | Yes because blueprint is registered | Many endpoints are stubs; DEV_MODE risks |
| Health | PARTIAL | `app.py:532-545`, `health_monitor.py` | Returns health summary | env presence, scheduler object, memory | Yes | Presence check only; can be green while tools broken |

## Module State Matrix

| Area | Classification | What exists today | Source file / endpoint / table | Data source used | Works? | Live? | Known limitations / related audit finding |
|---|---:|---|---|---|---|---|---|
| Screens | PARTIAL | One implemented frontend screen: Projects Hub with KPI pills and project cards | `tma-frontend/src/App.tsx`, `api.ts`, `components/*` | `GET /api/projects` | Works if backend auth/Airtable works | Yes if deployed frontend points to backend | No router/navigation; no lead/card/finance/assets UI |
| API endpoints | PARTIAL | Flask app routes plus TMA routes | `app.py`, `tma_api.py` | Telegram/Twilio/Airtable/Anthropic | Mixed | Yes | Several `/api/*` routes are TODO stubs |
| Airtable integrations | PARTIAL | `tools/airtable_tools.py`, `crm.py`, `daily_digest.py`, `tma_api.py`, schema constants | Airtable tables: `Leads`, `משימות (Tasks)`, `עסקאות (Deals)`, `תשלומים (Payments)`, `אנשי קשר (Contacts)`, `ProjectsHub`, `Business Memory` | Airtable API | Mixed | Yes if env configured | Schema sources diverge; English/Hebrew field mismatches; some errors become empty data |
| Telegram features | PARTIAL | Bot status/schema commands, message agent loop, approval callbacks | `app.py:69-244`, `app.py:340-511` | Telegram + Anthropic + tools | Chat loop works partially | Yes | Tool chain broken by Google conflict; approval fake/dead-end risks |
| Approval system | BROKEN | `_queue_approval`, callback handling, `event_bus` queue | `app.py:146-244`, `event_bus.py` | RAM queue/event bus | Inconsistent | Yes | Can show approval text without real queued action; worker approvals not executable by main callback |
| Memory system | PARTIAL | Main RAM conversation memory and disconnected memory modules | `memory_store.py`, `lead_memory.py`, `session_store.py`, `profile.py` | RAM, optional Airtable | Short-term chat memory works | Yes | RAM-only; business/knowledge memory mostly disconnected |
| Learning system | STUB | Readiness checks, mock/partial learning engines | `core/learning_engine.py`, `learning_engine.py`, `data_engines.py` | Mock events or Airtable readiness | Not real production learning | Scheduler can call | Uses mock fallback; real event store missing |
| Workers / scheduler | PARTIAL | Scheduler runs digest, collectors, followups, payments, recovery, email, audience, attribution, interaction | `scheduler.py`, worker modules | Airtable/RAM/mock/event_bus | Mixed | Yes if scheduler starts | Mock fallbacks; approval actions not executable; payment reminder self-test fails |
| Guards / safety | PARTIAL | Rate limiter, idempotency, circuit breaker, output validation, shabbat guard | `guards/`, `shabbat_guard.py`, `feature_flags.py` | RAM/runtime flags | Basic behavior works | Yes | Process-local only; emergency not centrally enforced |
| Assets module | STUB | Backend TODO endpoints only | `/api/assets`, `/api/assets/<id>`, `airtable_schema.py:AssetsFields` | None | Returns TODO | Route live | No real assets data/UI |
| Projects module | PARTIAL | Projects Hub API and frontend cards | `/api/projects`, `/api/projects/<slug>/dashboard`, `ProjectsHub` | Airtable | Partially works | Yes | Project dashboard not fully scoped; frontend only uses projects list |
| Finance module | STUB | `/api/finance/pulse` returns TODO; finance domain exists in router/identity | `tma_api.py:815-820`, router files | None for endpoint | Stub | Route live | No real Finance Pulse screen/API |
| Activity module | STUB | `/api/activity` returns TODO | `tma_api.py:847-852` | None | Stub | Route live | No real feed |
| Personal Mode | STUB | Auth can include `personal`; assets endpoints TODO | `tma_api.py:444-455`, `tma_api.py:857-882` | Identity allowed domains | Auth mode only | Partially route live | No usable personal screens/assets |
| Recruitment module | PARTIAL | Domain prompt/lead qualification config for recruitment | `domain_prompts.py:51-85`, `airtable_schema.py` project type names | Prompt config only | Not usable through current lead qualifier due broken domain call | No dedicated live module | No recruitment UI/tools found |
| Investor tools | NOT IMPLEMENTED | No current investor-specific runtime module found | Mentions only in docs/roadmap-like text | None | No | No | No implemented investor tool/screen |
| Google integrations | BROKEN | Gmail/Drive/Calendar code exists | `tools/google_tools.py`, `tools/gmail_tools.py`, `tools/calendar_tools.py`, `tools/drive_tools.py` | Google OAuth/env | Broken import | Intended live via tools | `tools/google_tools.py` has unresolved merge conflict |
| Email tools | BROKEN / PARTIAL | Gmail draft/read/send tools plus email inbound scheduler | `tools/gmail_tools.py`, `email_inbound.py` | Google OAuth, Gmail API, event_bus | Tool import broken; inbound falls to mock | Intended live | `email_inbound.py` imports wrong `google_tools` path and uses mock |
| Calendar tools | BROKEN | Calendar get/create tools exist | `tools/calendar_tools.py`, `tools/google_tools.py` | Google OAuth, Calendar API | Broken by merge conflict | Intended live | conflict around `calendar_create_event`; approval not consistently gated |
| WhatsApp tools | PARTIAL | WhatsApp webhook agent path; lead qualifier code exists but broken | `app.py:614-648`, `lead_qualifier.py` | Twilio, agent, Airtable tools | Agent path partial; qualifier broken | Yes | no Twilio signature validation; qualifier `get_domain` TypeError |
| Security features | PARTIAL | Identity roles, registry enforcement, Airtable tenant security, TMA auth, DEV_MODE, CORS, rate/idempotency | `identity.py`, `tool_registry.py`, `tools/airtable_security.py`, `tma_api.py`, `guards/` | env, initData, RAM | Mixed | Yes | DEV_MODE bypass risk; tenant scope assumptions; CORS broad for Vercel |
| Emergency Stop | PARTIAL | `/api/health/emergency` sets runtime flags | `tma_api.py:897-922`, `feature_flags.py` | in-process dict | Sets flag | Route live | Not persisted and not centrally enforced |
| TMA / Mini App | PARTIAL | Frontend Projects Hub and backend endpoints | `tma-frontend/src/*`, `tma_api.py` | Airtable, Telegram initData/dev header | Projects only partially | Yes if deployed | Most planned screens are not implemented |

## Screens

| Screen | Classification | What exists today | Source | Data source | Works? | Live? | Known limitations |
|---|---:|---|---|---|---|---|---|
| Projects Hub | PARTIAL | Single React screen with global KPIs, exceptions, project cards | `tma-frontend/src/App.tsx`, `GlobalKpis.tsx`, `ProjectCard.tsx` | `GET /api/projects` | Yes if backend returns valid data | Yes | No navigation/click-through; only one screen |
| Project Dashboard | PARTIAL | Backend endpoint exists; no frontend screen found | `tma_api.py:519-569` | `ProjectsHub`, `Leads`, Deals, Tasks | API partial | Endpoint live | Deals/tasks not scoped to project, only broad filters |
| Lead Pipeline | PARTIAL | Backend list endpoint exists; no frontend screen found | `tma_api.py:590-616` | `Leads` | API partial | Endpoint live | Formula/field mismatch risk |
| Lead Card | PARTIAL | Backend detail endpoint exists; no frontend screen found | `tma_api.py:619-666` | `Leads`, `Business Memory` | API partial | Endpoint live | Fetches record before partner domain authorization |
| Finance Pulse | STUB | Endpoint returns TODO | `tma_api.py:815-820` | None | No | Endpoint live | Not implemented |
| Approvals screen | STUB | Endpoints return TODO | `tma_api.py:823-844` | None | No | Endpoints live | Not connected to real approval queue |
| Activity Feed | STUB | Endpoint returns TODO | `tma_api.py:847-852` | None | No | Endpoint live | Not implemented |
| Assets Overview/Card | STUB | Endpoints return TODO | `tma_api.py:861-882` | None | No | Endpoints live | No assets module behavior |
| System Health screen | STUB | `/api/health` returns TODO; root `/health` works separately | `tma_api.py:889-894`, `app.py:532-545` | None for TMA; health monitor for app | TMA no; app partial | Both routes live | TMA health is TODO |
| Personal Mode screens | STUB | Auth can report `personal`, assets TODO | `tma_api.py:444-455`, `tma_api.py:857-882` | Identity | No usable screen | Partial | No frontend mode switch |
| Recruitment screen | NOT IMPLEMENTED | No frontend or API screen found | N/A | N/A | No | No | Only domain prompt config exists |
| Investor screen/tools | NOT IMPLEMENTED | No runtime implementation found | N/A | N/A | No | No | Mentions are roadmap/docs only |

## API Endpoints

### Flask App

| Endpoint | Classification | Source | What exists today | Auth | Data source | Limitations |
|---|---:|---|---|---|---|---|
| `GET /` | WORKING | `app.py:676-678` | Plain live string | none | none | Basic status only |
| `GET /health` | PARTIAL | `app.py:532-545` | JSON health | none | env/scheduler/memory | Does not verify real Airtable/Google functionality |
| `POST /<TELEGRAM_TOKEN>` | PARTIAL | `app.py:547-612` | Telegram webhook | token in path | Telegram/Anthropic/tools | Tool import conflict and approvals issues |
| `POST /whatsapp` | PARTIAL | `app.py:614-648` | WhatsApp webhook | none found | Twilio form, agent | No signature validation |
| `POST /worker/trigger` | PARTIAL | `app.py:653-673` | Worker event trigger | bearer `WORKER_SECRET` | Agent | arbitrary `chat_id` if secret leaks |
| `POST /voice/incoming` | PARTIAL | `app.py:685-693` | Voice start | none found | Twilio form | no signature validation |
| `POST /voice/step` | PARTIAL | `app.py:696-702` | Voice gather step | none found | Twilio form | no signature validation |

### TMA API

| Endpoint | Classification | Source | What exists today | Auth | Data source | Limitations |
|---|---:|---|---|---|---|---|
| `OPTIONS /api/tma/auth`, `/api/projects`, `/api/leads`, `/api/ai/ask`, `/api/followup` | WORKING | `tma_api.py:56-61` | CORS preflight | none | none | Not all `/api/*` covered |
| `POST /api/tma/auth` | PARTIAL | `tma_api.py:426-455` | Validates Mini App initData and returns role/modes | Telegram initData | identity resolver | No session token; DEV behavior differs elsewhere |
| `GET /api/projects` | PARTIAL | `tma_api.py:462-484` | Global KPIs + project cards | TMA auth owner | Airtable | Schema/read errors can collapse to empty |
| `POST /api/projects` | PARTIAL | `tma_api.py:487-516` | Creates `ProjectsHub` record | owner | Airtable | Slug uniqueness not enforced |
| `GET /api/projects/<slug>/dashboard` | PARTIAL | `tma_api.py:519-569` | Project summary | TMA auth | Airtable | Deals/tasks not scoped to project/domain strongly enough |
| `GET /api/leads` | PARTIAL | `tma_api.py:590-616` | Lead list | owner/manager/partner | Airtable `Leads` | formula field mismatch risk |
| `GET /api/leads/<id>` | PARTIAL | `tma_api.py:619-666` | Lead detail + timeline | owner/manager/partner | Airtable `Leads`, `Business Memory` | partner authorization after fetch |
| `PATCH /api/leads/<id>/status` | PARTIAL | `tma_api.py:669-686` | Updates lead status | owner/manager | Airtable `Leads` | errors not very detailed |
| `POST /api/followup` | PARTIAL | `tma_api.py:693-723` | Creates task from lead card | owner/manager | Airtable `Leads`, `משימות (Tasks)` | no approval queue; schema dependent |
| `POST /api/ai/ask` | PARTIAL / BROKEN RISK | `tma_api.py:730-804` | Single-turn contextual AI answer | owner/manager | Anthropic, memory, context | can fail due Google conflict in context import path; does not write memory back |
| `GET /api/finance/pulse` | STUB | `tma_api.py:815-820` | TODO response | owner | none | not implemented |
| `GET /api/approvals` | STUB | `tma_api.py:823-828` | TODO response | owner | none | not real approvals |
| `POST /api/approvals/bulk` | STUB | `tma_api.py:831-836` | TODO response | owner | none | bulk approval not implemented |
| `POST /api/approvals/<id>` | STUB | `tma_api.py:839-844` | TODO response | owner | none | single approval not implemented |
| `GET /api/activity` | STUB | `tma_api.py:847-852` | TODO response | owner/manager | none | not implemented |
| `GET /api/assets` | STUB | `tma_api.py:861-866` | TODO response | owner/personal | none | not implemented |
| `GET /api/assets/<id>` | STUB | `tma_api.py:869-874` | TODO response | owner/personal | none | not implemented |
| `PATCH /api/assets/<id>` | STUB | `tma_api.py:877-882` | TODO response | owner/personal | none | not implemented |
| `GET /api/health` | STUB | `tma_api.py:889-894` | TODO response | owner | none | not implemented |
| `POST /api/health/emergency` | PARTIAL | `tma_api.py:897-922` | Sets runtime emergency flag | owner | in-process flag dict | not persisted / not centrally enforced |
| `GET /api/dev/schema` | PARTIAL | `tma_api.py:930+` | Dev schema inspection | DEV_MODE + owner | Airtable | should not be production-facing |

## Airtable Integrations

| Module | Classification | What exists today | Tables | Works? | Known limitations |
|---|---:|---|---|---|---|
| Schema constants | PARTIAL | `Tables`, field classes, aliases | `airtable_schema.py` | yes as static code | sources diverge with `schema_intelligence.py` and runtime strings |
| Tool Airtable CRUD | PARTIAL | `airtable_get/add/update/get_schema/search_lead` | `tools/airtable_tools.py` | partial | formula fields not prevalidated; aliasing incomplete |
| Tenant security | PARTIAL | `enforce_tenant_scope`, audit log | `tools/airtable_security.py` | partial | assumes `tenant_id` / `{user_id}` exist |
| CRM | PARTIAL | Contacts/deals/payments helpers | `crm.py` | partial | audit found field constant/schema mismatches |
| Daily digest | PARTIAL | builds daily task/deal/payment/change sections | `daily_digest.py` | partial | Airtable failures can become empty/benign sections |
| TMA Airtable helpers | PARTIAL | `_at_list`, `_at_get_record`, `_at_patch`, `_at_post` | `tma_api.py` | partial | read errors swallowed as empty lists |
| Auxiliary imports | BROKEN/PARTIAL | voice/attribution/audience/data/tenant use root `airtable_tools` imports | root modules | often mock/dry-run | wrong import path versus `tools/airtable_tools.py` |

## Telegram Features

| Feature | Classification | Source | What exists today | Works? | Limitations |
|---|---:|---|---|---|---|
| Chat agent loop | PARTIAL | `app.py:340-511` | Claude loop with tools and memory | partial | broken Google import path can affect tools |
| `/status` command | PARTIAL | `app.py:69-75` | returns health status | likely | shallow health |
| `/schema` command | PARTIAL | `app.py:78-104` | returns Airtable schema info | partial | depends on schema module/import |
| Typing indicator | WORKING | `app.py:288-305` | background typing while processing | yes | Telegram only |
| Approval callback | BROKEN | `app.py:191-244` | handles approve/reject callbacks | inconsistent | queue/event bus mismatch, stale actions |

## Approval System

Current state: BROKEN.

What exists:

- `app.py:146-189` queues approval payloads with `tool_name` and `tool_inputs`.
- `app.py:191-244` handles callback approve/reject.
- `event_bus.py` has separate approval/action queue concepts.
- `tool_registry.py` marks some tools as `requires_approval`.

Known current reality:

- Audit reports found approval response text can appear without a real queued approval.
- Worker approvals use custom actions such as `send_followup`, `send_bounce`, `send_recovery`, and email `send_email_reply`, but no main executable confirmation handler was found.
- `calendar_create_event`, `airtable_add`, and `airtable_update` are not consistently approval-gated across registry/event bus/validator.

## Memory System

| System | Classification | What exists today | Source | Used by model? | Limitations |
|---|---:|---|---|---|---|
| Main conversation memory | PARTIAL | RAM memory read/write in `run_agent()` | `memory_store.py`, `app.py` | yes | not persistent, 12h inactivity cleanup |
| Tool-result memory | PARTIAL | truncated result written into RAM memory | `app.py` | yes, as text | can lose detail/context |
| Lead memory | PARTIAL | module exists and scheduler flushes | `lead_memory.py`, `scheduler.py` | mostly no | not populated by main agent path |
| Session store | PARTIAL/BROKEN | lead qualifier sessions | `session_store.py`, `lead_qualifier.py` | no in main agent | qualifier public flow currently crashes |
| Business memory | PARTIAL | interaction/timeline storage attempts | `interaction_engine.py`, `tma_api.py` | mostly no | table naming inconsistent |
| Knowledge engine | DEAD | importable module | `knowledge_engine.py` | no | not connected to main context |
| Profile memory | PARTIAL | single global Airtable profile row | `profile.py` | not clearly in main agent | no tenant/user scope; errors return defaults |

## Learning System

Current state: STUB / PARTIAL.

What exists:

- `core/learning_engine.py` and `learning_engine.py` have learning-like logic.
- `data_engines.py` has readiness checks and KPI/learning/attribution stubs.
- `scheduler.py` can schedule learning cycle jobs.

Current reality:

- Audit reports classify learning as MOCK/PARTIAL.
- Real event store population is missing or inconsistent.
- Several paths fall back to mock data.
- It is not reliably injected into the main agent prompt.

## Workers / Scheduler

| Worker/job | Classification | Source | What exists today | Works? | Limitations |
|---|---:|---|---|---|---|
| Scheduler thread | PARTIAL | `scheduler.py`, `app.py:89-93` | starts background schedule loop | partial | duplicate thread risk |
| Daily digest | PARTIAL | `daily_digest.py`, `scheduler.py` | daily summary | partial | errors can appear as empty/no data |
| Daily collector | PARTIAL | `daily_collector.py` | collects memory summary | partial | reports all clear on errors |
| Followup scan | PARTIAL | `followup_engine.py` | scans candidates and queues approvals | partial | lead memory not populated; approval dead-end |
| Payment reminders | BROKEN/PARTIAL | `payment_reminder.py` | reminder worker | self-test fails | `IndexError` in self-test |
| Lead recovery | PARTIAL | `core/lead_recovery.py` | recovery draft/approval | partial | approval action mismatch |
| Abandoned lead scan | PARTIAL | `abandoned_lead_worker.py` | scans abandoned leads | partial | falls back to mock/no records |
| Email inbound | BROKEN/PARTIAL | `email_inbound.py`, `scheduler.py` | inbox poll/draft approval | mock | wrong Google helper import |
| Audience report | PARTIAL/STUB-LIKE | `audience_intelligence.py` | weekly segmentation report | mock if Airtable fails | can send fake data |
| Attribution report | PARTIAL/STUB-LIKE | `ad_attribution.py` | campaign attribution report | mock if Airtable fails | UTM injection timing issue |
| Survey worker | PARTIAL/DEAD | `workers/survey_worker.py` | importable worker | no caller found | ignores HTTP status |
| Root `worker.py` | BROKEN/OLD | `worker.py` | old proactive worker | not wired to current trigger | old English schema |

## Guards / Safety

| Guard | Classification | Source | What exists today | Works? | Limitations |
|---|---:|---|---|---|---|
| Rate limiter | PARTIAL | `guards/rate_limiter.py` | per-key in-process limiter | yes | process-local |
| Idempotency | PARTIAL | `guards/idempotency.py` | duplicate request suppression | yes | process-local, truncated hash |
| Circuit breaker | PARTIAL | `guards/circuit_breaker.py` | basic breaker | yes | not applied to broken Google path |
| Tool output validation | PARTIAL | `guards/__init__.py`, `rate_limiter.py` | stringify/truncate | yes | no semantic validation |
| Shabbat guard | PARTIAL | `shabbat_guard.py` | time guard | yes | approximate time/DST |
| Feature flags | PARTIAL | `feature_flags.py` | env/runtime flags | yes | in-process only |
| Anti-hallucination | PARTIAL | `core/anti_hallucination.py` | checks narrow failure strings | partial | misses many fake success cases |

## Google / Email / Calendar / Drive

Current state: BROKEN.

What exists:

- `tools/google_tools.py` implements OAuth, Gmail draft/read/send, Drive search/read, Calendar get/create.
- `tools/gmail_tools.py`, `tools/calendar_tools.py`, `tools/drive_tools.py` re-export from `tools/google_tools.py`.
- Tool schemas and dispatcher expose: `gmail_draft`, `gmail_send_draft`, `gmail_read`, `calendar_get_events`, `calendar_create_event`, `search_drive`, `read_drive_file`.

Current blocker:

- `tools/google_tools.py:21` contains `<<<<<<< HEAD`.
- `tools/google_tools.py:344-355` has another conflict around `calendar_create_event`.
- Therefore imports depending on `tools.google_tools` are broken.

OAuth reality:

- New helper version logging code exists: `GOOGLE_OAUTH_HELPER_VERSION = "2026-06-03-v3"`.
- It cannot reliably run until the merge conflict is resolved.

## Security Features

| Feature | Classification | Source | What exists today | Works? | Limitations |
|---|---:|---|---|---|---|
| Identity resolver | PARTIAL | `identity.py` | roles/domains/tenant/memory_key | yes | unknown users can become fallback roles depending env |
| Role permissions | PARTIAL | `identity.py`, `tool_registry.py` | permissions and tool registry | partial | registry/validator/schema not in sync |
| Airtable tenant scoping | PARTIAL | `tools/airtable_security.py`, dispatcher | tenant filters/audit | partial | assumes fields exist |
| TMA auth | PARTIAL | `tma_api.py:207-289` | Telegram initData or dev header | yes | DEV_MODE bypass risk |
| CORS | PARTIAL | `tma_api.py:42-61` | allows frontend origins | yes | broad `.vercel.app` risk from audit |
| Audit logging | PARTIAL | `tma_api.py:189-205`, Airtable security | best-effort writes | partial | failures silent |
| Emergency stop | PARTIAL | `tma_api.py:897-922`, `feature_flags.py` | runtime flag set | partial | not persisted/enforced centrally |

## WORKING TODAY

These are the things that appear usable today, assuming required env vars and external services are configured:

1. Flask app starts far enough to register routes if imports are not blocked by local conflict path.
2. `GET /` returns a live string.
3. `GET /health` returns a JSON health summary.
4. Telegram webhook route exists and routes messages into `run_agent()`.
5. WhatsApp webhook route exists and routes messages into `run_agent()`.
6. TMA blueprint is registered in `app.py`.
7. TMA `GET /api/projects` exists and can return global KPIs/project cards from Airtable.
8. TMA frontend renders Projects Hub from `/api/projects`.
9. TMA auth endpoint validates Telegram Mini App initData.
10. Basic identity roles/domains/memory keys exist.
11. Basic in-process conversation memory is used by the main agent.
12. Airtable schema constants exist for core Hebrew production tables.
13. Airtable CRUD tools exist.
14. Rate limiting/idempotency guards exist.
15. Scheduler has runnable job definitions.
16. Daily digest code exists and can format sections.
17. CRM contacts/deals/payments helpers exist.
18. Voice IVR state machine self-tests pass.
19. Attribution/audience modules can produce reports, but currently this includes mock fallback.
20. Emergency endpoint can set a runtime flag.

## PARTIALLY WORKING

1. Main Telegram/WhatsApp agent loop: reachable, but tool path and approvals are fragile.
2. TMA Projects Hub: backend/frontend exist, but schema/auth/data errors can break it.
3. TMA lead APIs: implemented, but no frontend screen and known field/filter risks.
4. TMA followup task creation: implemented, but no approval workflow.
5. TMA Ask AI: implemented single-turn, but can fail due context/Google conflict and does not write memory.
6. Airtable reads/writes: implemented, but schema mismatches and swallowed errors exist.
7. CRM module: implemented, but some field constants do not match production.
8. Daily digest: implemented, but can hide Airtable failures.
9. Workers: scheduled and broad, but several use mock fallback or old schemas.
10. Guards: exist, but are process-local and incomplete.
11. Voice IVR: state machine exists, but auth/schema/name capture are problematic.
12. Personal Mode auth: mode can be returned, but screens/assets are stubs.
13. Recruitment domain: prompt config exists, but no usable module/screen and qualifier flow is broken.
14. Security/tenant isolation: implemented in layers, but inconsistent and field-dependent.
15. Emergency stop: endpoint exists, but not durable or centrally enforced.

## STUBS

1. `/api/finance/pulse`.
2. `/api/approvals`.
3. `/api/approvals/bulk`.
4. `/api/approvals/<approval_id>`.
5. `/api/activity`.
6. `/api/assets`.
7. `/api/assets/<asset_id>`.
8. `/api/assets/<asset_id>` PATCH.
9. TMA `/api/health`.
10. `data_engines.py` learning/revenue attribution full engines.
11. `creative_generator.py` when `CREATIVE_GENERATOR` is disabled returns demo text.
12. Audience/attribution reports behave like stubs when Airtable is unavailable because they use mock data.

## BROKEN

1. Google tools import chain: `tools/google_tools.py` has unresolved merge conflicts.
2. Calendar tools: blocked by Google conflict and ambiguous `calendar_create_event` signature.
3. Gmail tools: blocked by Google conflict.
4. Drive tools: blocked by Google conflict.
5. Email inbound real Gmail polling: imports wrong `google_tools` path and falls into mock mode.
6. Lead qualifier public flow: `get_domain(channel, sender)` TypeError because `config.get_domain()` accepts one arg.
7. Approval execution for several worker/custom actions: queued action cannot be executed by main approval callback.
8. Payment reminder self-test: fails with `IndexError`.
9. Root `worker.py`: old schema and not wired to current worker trigger.
10. Full project compile: audit reports show it fails because of `tools/google_tools.py` conflict.

## NOT IMPLEMENTED

1. Investor tools.
2. Investor screen/API.
3. Real Assets module data operations.
4. Real Finance Pulse screen/data API.
5. Real Activity Feed.
6. Real TMA approval queue actions.
7. TMA bulk approval execution.
8. Personal Mode usable frontend.
9. Recruitment frontend/API workflow.
10. Persistent emergency stop.
11. Persistent multi-instance guards.
12. Durable conversation memory.
13. Real connected knowledge engine in main agent flow.
14. Real production learning loop that updates prompts.
15. Real email inbound without mock fallback.
16. Real voice signature authentication.
17. Frontend routes beyond Projects Hub.
18. Partner share-ready dashboards beyond current partial project cards.

## OPEN AUDIT RISKS

1. Google merge conflict blocks tool imports.
2. Approval flow can claim or imply execution without actual execution.
3. Worker approval actions are not wired to real executable handlers.
4. Airtable schema mismatches can break reads/writes or produce wrong data.
5. TMA DEV_MODE can bypass real Telegram auth if enabled in production.
6. TMA CORS is broader than a single frontend origin.
7. Airtable read failures are often returned as empty lists.
8. Daily digest can hide failures as empty sections.
9. Mock fallback in workers/reports can create false confidence.
10. Emergency stop is process-local and not centrally enforced.
11. Voice and WhatsApp endpoints lack Twilio signature validation.
12. Worker trigger can impersonate arbitrary chat_id if secret leaks.
13. Memory is RAM-only and not durable.
14. Business/knowledge memory exists but is mostly disconnected.
15. Tenant scoping assumes fields that may not exist in every table.
16. TMA partner authorization sometimes happens after record fetch.
17. Project dashboards do not strongly scope deals/tasks to project.
18. `lead_qualifier` runtime flow is broken.
19. Root auxiliary modules import wrong Airtable/Google helper paths.
20. Health checks do not prove core tools work.

## TOP 20 THINGS THE OWNER CAN ACTUALLY USE TODAY

1. Open the TMA Projects Hub frontend and view project cards if API/auth/Airtable are configured.
2. Call `GET /api/projects` as owner to get global KPIs and project cards.
3. Create a project record through `POST /api/projects` if `ProjectsHub` exists.
4. View a project dashboard through `GET /api/projects/<slug>/dashboard` if the project exists.
5. List leads through `GET /api/leads` if the `Leads` formulas match real fields.
6. View a lead through `GET /api/leads/<lead_id>`.
7. Update lead status through `PATCH /api/leads/<lead_id>/status`.
8. Create a followup task from TMA through `POST /api/followup`.
9. Ask single-turn AI through `POST /api/ai/ask` if context imports and Anthropic env work.
10. Use Telegram chat for general agent responses.
11. Use WhatsApp webhook for agent responses.
12. Use `/status` in Telegram for health summary.
13. Use `/schema` in Telegram for schema display if imports work.
14. Receive daily digest if scheduler/env/Airtable work.
15. Use CRM helper code for contacts/deals/payments through tools if invoked successfully.
16. Use Airtable tool CRUD for supported tables if schema and tenant fields match.
17. Use the basic in-process memory during one running process.
18. Trigger worker events through `/worker/trigger` with `WORKER_SECRET`.
19. Enable voice IVR state machine if `VOICE_IVR` and Twilio are configured, with security caveats.
20. Use emergency endpoint to set a runtime flag, with the caveat that enforcement is incomplete.

## TOP 20 FIXES NEEDED BEFORE SHARING WITH PARTNERS

1. Resolve `tools/google_tools.py` merge conflict.
2. Add a smoke test proving Google tools import.
3. Fix `lead_qualifier.py` / `config.get_domain()` signature mismatch.
4. Remove production mock fallbacks or gate them behind explicit dev mode.
5. Standardize all Airtable imports to the production helper path.
6. Standardize Google helper imports for email inbound.
7. Make approval queue and callback use one executable payload contract.
8. Wire worker approval actions to real handlers or real tool dispatch.
9. Mark high-risk writes consistently in registry/event bus/validator.
10. Validate Twilio signatures for WhatsApp and Voice.
11. Persist and centrally enforce emergency stop.
12. Replace stale English Airtable field/table references.
13. Validate formula fields before sending Airtable formulas.
14. Make Airtable read/write errors visible in TMA and digest.
15. Fix TMA partner authorization order and scoping.
16. Scope project dashboard deals/tasks by project/domain.
17. Replace process-local guards with persistent/shared stores where needed.
18. Add durable memory or clearly label memory as session-only.
19. Implement or hide TMA stub screens before partner demo.
20. Add production smoke tests for Telegram/TMA/Airtable/Google/approvals.
