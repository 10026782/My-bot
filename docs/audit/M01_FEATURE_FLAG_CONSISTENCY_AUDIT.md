# M01 — Feature Flag Consistency Audit

**Scope:** `feature_flags.py`, `app.py`, `scheduler.py`, `core/`, `tools/`,
`scripts/`, `.env.example`, and relevant documentation. `.worktrees/` and
frontend-only references were excluded.

**Audit mode:** read-only static inspection. No runtime code was changed.

## Evidence levels

- **STATIC FINDING** — established from source or documentation inspection.
- **LIVE STRUCTURE CONFIRMED** — confirmed from read-only Render/Airtable
  structure or configuration.
- **RUNTIME BEHAVIOR VERIFIED** — requires direct execution evidence; none is
  claimed by this audit.

The latest Render deploy was not treated as runtime evidence. Configuration
values alone do not prove process behavior.

## Canonical registry and defaults

`feature_flags.py` is the declared registry (`feature_flags.py:17-201`).
`is_enabled()` reads `_RUNTIME`, then the environment, then `_DEFAULTS`, and
defaults unknown boolean flags to `false` (`feature_flags.py:218-296`).

Explicit boolean defaults are:

- `IMPORT_DOMAIN`: `true`
- `FEATURE_INGRESS_ENVELOPE`: `true`
- `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`: `false`
- `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`: `false`
- `EXTERNAL_EXECUTION_ENABLED`: `false`

Three-state flags use dedicated accessors and fail closed to `off` on invalid
values (`feature_flags.py:305-395`). Emergency-stop flags are delegated to the
durable manager and are fail-safe when the manager is not configured.

## Inventory

| Canonical flag | Aliases / alternate names | Read path and consumers | Gate / unset behavior | Classification |
|---|---|---|---|---|
| `EMERGENCY_STOP_ALL` | none | EmergencyStopManager; `feature_flags.py:267` | tool/action; manager-backed fail-safe | NONE / HIGH |
| `EMERGENCY_STOP_WHATSAPP` | none | EmergencyStopManager | outbound WhatsApp; fail-safe | NONE / HIGH |
| `EMERGENCY_STOP_EMAIL` | none | EmergencyStopManager | outbound email; fail-safe | NONE / HIGH |
| `EMERGENCY_STOP_AUTOMATION` | none | `scheduler.py:800-817` | scheduler execution; fail-safe | NONE / HIGH |
| `EMERGENCY_STOP_AI` | none | AI/cost-watchdog paths | AI/tool execution; fail-safe | NONE / HIGH |
| `LEAD_CAPTURE` | none | `is_enabled()` in lead creation paths | tool/action; default off | NONE / MEDIUM |
| `LEAD_SCORING` | none | `is_enabled()` in lead creation/scoring | tool/action; default off | NONE / MEDIUM |
| `LEAD_MEMORY` | none | lead-memory update path | tool/action; default off | NONE / LOW |
| `FOLLOWUP_AUTOMATION` | none | `scheduler.py:118` | scheduler execution; default off | NONE / MEDIUM |
| `LEAD_QUALIFIER` | none | `lead_qualifier.py:27` | tool/action; default off | NONE / LOW |
| `LEAD_RECOVERY` | none | `core/lead_recovery.py:303-305`, scheduler | scheduler/tool; default off | NONE / MEDIUM |
| `ABANDONED_LEADS` | none | `scheduler.py:357`; adapter gate in `feature_flags.py:244-250` | scheduler execution; default off and blocked without `send_bounce` | NONE / MEDIUM |
| `KNOWLEDGE_ENGINE` | none | `knowledge_engine.py:26,54,63` | tool/action; default off | NONE / LOW |
| `SUPABASE` | none | `knowledge_engine.py:26,54,63` | tool/action; default off | NONE / LOW |
| `COST_WATCHDOG_LIVE` | `COST_WATCHDOG_ENABLED` override | `core/cost_watchdog.py:74-79`; `cost_monitor.py:55,101,217` uses `is_enabled()` | watchdog/tool; fallback default true | READ_PATH_DRIFT / MEDIUM |
| `COST_WATCHDOG_ENABLED` | alternate override name | direct `os.environ` in `core/cost_watchdog.py:75` | overrides `COST_WATCHDOG_LIVE` when non-empty | NAME_DRIFT / MEDIUM |
| `IMPORT_DOMAIN` | none | `_DEFAULTS` and `is_enabled()` | tool/action; default on | NONE / LOW |
| `MULTITENANT` | none | `tenant_provisioner.py:118` | tool/action; default off | NONE / LOW |
| `FEATURE_TOOL_AVAILABILITY_FILTER` | none | `feature_flags.py:305-308`; `context.py:82-100`, `boss_doctor.py:126` | tool exposure; `off` | NONE / MEDIUM |
| `FEATURE_EVIDENCE_FINALIZER` | none | accessor; `app.py:5113,5178,5475`, `core/action_gateway.py:3106` | evidence/action; `off` | NONE / HIGH |
| `FEATURE_UNIFIED_STATUS_FORMATTER` | none | accessor; multiple `core/action_gateway.py` consumers | action output; `off` | NONE / MEDIUM |
| `VOICE_IVR` | documentation sometimes says `FEATURE_VOICE_IVR` | `app.py:6644-6650` | `/voice/incoming` execution; default off | REGISTRATION_DRIFT / HIGH |
| `EMAIL_INBOUND` | `FEATURE_EMAIL_INBOUND` in old comments/docs | `email_inbound.py:338`, `scheduler.py:357` | scheduler/tool; default off and adapter-gated | NAME_DRIFT / MEDIUM |
| `CREATIVE_GENERATOR` | none | `creative_generator.py:41` | tool/action; default off | NONE / LOW |
| `AD_ATTRIBUTION` | none | `scheduler.py:386` | scheduler execution; default off | NONE / LOW |
| `CONTACT_RESOLVER` | none | `contact_resolver.py:220` | tool/action; default off | NONE / LOW |
| `LLM_FALLBACK` | `OPENAI_FALLBACK_ENABLED` is historical only | `app.py:5543-5552,5560-5568` | tool/model fallback; default off | DOC_DRIFT / LOW |
| `FEATURE_BUSINESS_UPDATE` | none | `cmd_update.py:50` | tool/action; default off | NONE / LOW |
| `FEATURE_WEEKLY_SUMMARY` | none | `weekly_summary.py:45-48` | scheduler execution; default off | REGISTRATION_DRIFT / MEDIUM |
| `FEATURE_VOICE_NOTES` | none | `app.py:5831-5837` | route execution; default off | NONE / LOW |
| `FEATURE_MEDIA_UPLOAD` | none | `app.py:5875-5879` | route execution; default off | NONE / LOW |
| `META_OUTBOUND_ENABLED` | none | `is_enabled()`; `.env.example:64` | tool/action; default off | NONE / MEDIUM |
| `FEATURE_MARKETING_BRIDGE` | none | route/command registration in `cmd_marketing.py:173` | route registration and action; default off | NONE / MEDIUM |
| `FEATURE_MEMORY_SHADOW_LOGGING` | none | `scheduler.py:756` | scheduler execution; default off | NONE / LOW |
| `FEATURE_EPISODIC_CAPTURE` | none | `app.py:5510-5511` | tool/action; default off | NONE / LOW |
| `EMERGENCY_WINDOW` | none | emergency-window path | tool/action; default off | NONE / HIGH |
| `FEATURE_ACTION_GATEWAY` | none | `app.py`, `core/action_gateway.py`, `tma_api.py` | action/approval; default off | DEFAULT_DRIFT / HIGH |
| `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` | none | `_DEFAULTS`; approval routing | action/approval; default off | NONE / HIGH |
| `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` | none | `feature_flags.py:293-294`; approval paths | action; default off and requires single-speaker flag | NONE / HIGH |
| `FEATURE_ACTION_CONTRACT_PERSISTENCE` | none | ActionContract persistence paths | action; default off | DEFAULT_DRIFT / HIGH |
| `FEATURE_ATOMIC_CLAIMS` | none | atomic execution paths | action; default off | DEFAULT_DRIFT / HIGH |
| `EXTERNAL_EXECUTION_ENABLED` | none | external execution boundary | action; default off | NONE / HIGH |
| `FEATURE_PA01_ENFORCEMENT_STATE` | none | accessor; `app.py:5401` | action; `off` on invalid value | DEFAULT_DRIFT / HIGH |
| `FEATURE_AUTO_CAPTURE` | none | `core/lead_candidate_handler.py:1262-1264` | tool/write; default off | NONE / MEDIUM |
| `FEATURE_RAW_CAPTURE` | none | `core/ingress_classifier.py:746-776` | Airtable write gate; default off | NONE / MEDIUM |
| `FEATURE_STRUCTURED_FILE_CAPTURE` | none | `app.py:5803-5807` | route/tool execution; default off | NONE / LOW |
| `FEATURE_LAST_TOOL_RESULT_SHADOW` | none | `tools/dispatcher.py:545-549`, `core/output_gateway.py:250` | observation only; default off | NONE / LOW |
| `FEATURE_DECISION_HUB` | none | app and decision command paths | route/action; default off | NONE / MEDIUM |
| `FEATURE_DECISION_AUTO_INGESTION` | none | `decision_auto_ingestion.py:67,230-234` | action; default off; requires both Decision flags | NONE / MEDIUM |
| `FINANCIAL_COMMITMENT_GATE` | none | dynamic `is_enabled()` in `core/financial_gate.py:74-82` | output escalation; false means shadow | NONE / HIGH |
| `GAME_SCHEDULER` | none | `scheduler.py:485,588,666` | scheduler execution; default off | NONE / LOW |
| `PAYMENT_REMINDERS` | none | `scheduler.py:149`, `payment_reminder.py:295-296` | scheduler/tool; default off | NONE / MEDIUM |
| `FEATURE_AIRTABLE_SCHEMA_SNAPSHOT` | none | `scheduler.py:64` | scheduler registration/execution; default off | NONE / MEDIUM |
| `FEATURE_AIRTABLE_SCHEMA_SNAPSHOT_CLEANUP` | none | `tools/schema_snapshot.py:272` | tool execution; default off | NONE / LOW |
| `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE` | none | accessor; `tools/airtable_gateway.py:172` | tool; `off` | NONE / HIGH |
| `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE` | none | accessor; `tools/airtable_gateway.py:204` | tool; `off` | NONE / HIGH |
| `FEATURE_INGRESS_ENVELOPE` | none | `_DEFAULTS`; `app.py:4479` | route execution; default on | NONE / HIGH |
| `FEATURE_CORE_REASONING_LEADS_STATE` | none | accessor; `tma_api.py:1580` | API projection; `off` | NONE / MEDIUM |
| `AUDIENCE_INTELLIGENCE` | `FEATURE_AUDIENCE_INTELLIGENCE` in old comments/docs | `audience_intelligence.py:422`, `scheduler.py:428` | scheduler/tool; default off | NAME_DRIFT / LOW |
| `INTERACTION_INTELLIGENCE` | `FEATURE_INTERACTION_INTELLIGENCE` in old comments/docs | `interaction_engine.py:489` via `FF`; `scheduler.py:448` via direct `ENV` | scheduler/tool; default off | NAME_DRIFT + READ_PATH_DRIFT / MEDIUM |
| `KPI_ENGINE` | none | `data_engines.py:107,128,178,228` | tool/action; default off | NONE / LOW |
| `LEARNING_ENGINE` | `FEATURE_LEARNING_ENGINE` in old comments/docs | `core/learning_engine.py:287`, `scheduler.py:210` | scheduler/tool; default off | NAME_DRIFT / LOW |
| `REVENUE_ATTRIBUTION` | none | `data_engines.py:107,128,178,228` | tool/action; default off | NONE / LOW |
| `ERROR_REPORTING` | not in registry | direct `ENV`; `feature_flags.py:661`, `core/error_reporter.py:21,55` | error reporting; default true | READ_PATH_DRIFT / LOW |
| `FEATURE_UNIFIED_APPROVAL_MESSAGES` | none | no runtime consumer found | planning-only; not active | DEAD_FLAG / LOW / DEFER |

## Top findings

1. Render configuration contained `FEATURE_PA01_ENFORCEMENT_STATE=shadow.` with
   a trailing period. The accessor accepts only `off`, `shadow`, or `enforce`,
   so the invalid value fails closed to `off`. **LIVE STRUCTURE CONFIRMED;
   runtime behavior not verified.**
2. Render configuration contained `FEATURE_ACTION_CONTRACT_PERSISTENCE=true` and
   `FEATURE_ATOMIC_CLAIMS=true`, while `FEATURE_ACTION_GATEWAY` was absent. The
   repository default for the parent flag is off. **LIVE STRUCTURE CONFIRMED;
   runtime behavior not verified.**
3. `VOICE_IVR` is checked for `/voice/incoming` (`app.py:6644-6650`) but not for
   `/voice/step` (`app.py:6653-6662`).
4. `INTERACTION_INTELLIGENCE` has both direct environment access and an
   `is_enabled()` consumer, plus an old `FEATURE_` documentation name.
5. `FEATURE_WEEKLY_SUMMARY` is registered by the scheduler at
   `scheduler.py:871` even when its execution path is disabled.

## Safe cleanup candidates

- Normalize old `FEATURE_EMAIL_INBOUND`, `FEATURE_INTERACTION_INTELLIGENCE`,
  `FEATURE_AUDIENCE_INTELLIGENCE`, and `FEATURE_LEARNING_ENGINE` references to
  their canonical names.
- Document `COST_WATCHDOG_ENABLED` precedence over `COST_WATCHDOG_LIVE`.
- Keep `OPENAI_FALLBACK_ENABLED` only as historical migration evidence; the
  runtime flag is `LLM_FALLBACK`.
- Mark `FEATURE_UNIFIED_APPROVAL_MESSAGES` as planning-only until implemented
  and wired.

## No-deploy boundary

Do not change Render flag values, emergency-stop state, `/voice/step` gating,
or scheduler registration based only on this static audit. Those changes need
separate implementation, deployment, and direct verification.
