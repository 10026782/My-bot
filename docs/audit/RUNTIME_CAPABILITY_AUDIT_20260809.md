# Runtime Capability Audit — Final Verified Report

**Audit date:** 2026-08-09
**Mode:** Evidence only — no runtime, configuration, deployment, or application-code changes
**Evidence hierarchy:** `runtime evidence > Render config > current code > documentation`

## Environments and evidence window

- Owner: `tea-d804tr8sfn5c7398geag`
- Production: `srv-d80ehsf7f7vs73cq5rn0`
- Staging: `srv-d99uq63eo5us73967cj0`
- Requested export window: `2026-07-26T10:33:50Z` → `2026-08-09T10:37:31Z`
- Runtime records available: `2026-08-02` → `2026-08-09`
- Production: 4,993 entries
- Staging: 7,815 entries
- Targeted Meta-API export: Production 7 entries; Staging 3 entries

Missing logs are not evidence that a subsystem is OFF or disconnected.

## Final Runtime Capability Matrix

| Subsystem / flag | Production | Staging | Capability | Verification status |
|---|---|---|---|---|
| Core routing | VERIFIED | VERIFIED | ACTIVE | VERIFIED IN BOTH |
| TurnEnvelope | VERIFIED | VERIFIED | ACTIVE | VERIFIED IN BOTH |
| ActionGateway proposal | VERIFIED | VERIFIED | ACTIVE | VERIFIED IN BOTH |
| Approval boundary | PARTIAL | VERIFIED | ACTIVE | Production queue/rejection; Staging successful lifecycle |
| Execution / completion | NOT OBSERVED | VERIFIED | ACTIVE | Staging claim → dispatch → success; no successful Production execution in export |
| Single-speaker / reply ownership | Observed path | Observed path | ACTIVE | VERIFIED IN BOTH — observed paths only |
| Deterministic approval cost-cut | VERIFIED | VERIFIED | ACTIVE | `agent_calls=0` observed in both |
| RuntimeSchemaProvider | PATH VERIFIED | PATH VERIFIED | SHADOW | RUNTIME PATH VERIFIED — COMPONENT LOGGING NOT OBSERVABLE |
| IngressEnvelope | PATH VERIFIED | PATH VERIFIED | ACTIVE | RUNTIME PATH VERIFIED — COMPONENT LOGGING NOT OBSERVABLE |
| Emergency Stop durable persistence | VERIFIED | Bootstrap verified | ACTIVE | VERIFIED IN PROD — CURRENT |
| `COST_WATCHDOG_LIVE` | VERIFIED OFF | VERIFIED ACTIVE | OFF / ACTIVE | EXPECTED ENVIRONMENT DIFFERENCE |
| `INTERACTION_INTELLIGENCE` | VERIFIED OFF | VERIFIED OFF | OFF | OFF VERIFIED IN BOTH |
| EvidenceFinalizer | VERIFIED | VERIFIED | SHADOW | SHADOW VERIFIED IN BOTH |
| Learning scheduler | Bootstrap only | Bootstrap only | UNKNOWN | Schedule observed; execution not proven |
| Usage telemetry | Not proven | Partial | UNKNOWN | Watchdog-side `AI_Usage_Daily` persistence only |
| `CREATE_TASK` deterministic path | VERIFIED | VERIFIED | ACTIVE | Staging additionally proves execution |
| `UPDATE_TASK` | Not observed | Agent-owned | UNKNOWN | PA-01 deterministic behavior not proven |
| `COMPLETE_TASK` | Not observed | Not observed | UNKNOWN | Needs runtime evidence |
| Profile subsystem | Not observed | Not observed | CODE-ONLY | Runtime unverified |
| Project timeline | Not observed | Not observed | CODE-ONLY | Runtime unverified |
| Tenant provisioning | Not observed | Not observed | CODE-ONLY | Runtime unverified |
| Creative Generator | Not observed | Not observed | OFF / unobserved | Effective configuration is OFF |
| Knowledge Engine | Not observed | Not observed | OFF / unobserved | Effective configuration is OFF |
| Knowledge router | Not observed | Not observed | CODE-ONLY | Runtime unverified |
| Tenant config/providers | Not observed | Not observed | CODE-ONLY | Runtime unverified |
| Emergency Window | Not observed | Not observed | OFF | Effective default is OFF |
| OTP | Not observed | Not observed | CODE-ONLY | Runtime unverified |
| Financial Gate | Not observed | Not observed | CODE-ONLY | Runtime unverified |

## Detailed evidence

### Core routing, TurnEnvelope, and ActionGateway

Production Telegram evidence at `2026-08-09T00:25:23.865437868Z`–
`00:25:26.186748365Z` shows identity resolution, TurnEnvelope, classifier,
router, ActionGateway proposal, approval queue, deterministic handling, and a
completed Telegram request ([Production log](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:12>), [TurnEnvelope](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:21>), [proposal](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:31>), [deterministic path](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:43>)).

Staging shows the same path at `2026-08-09T00:30:10.502047878Z`–
`00:30:12.034378862Z` ([classifier](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:161>), [route](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:162>), [proposal](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:170>)).

Staging successful lifecycle evidence:

- approval: `2026-08-05T20:53:46.239826321Z` ([log](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-05.jsonl:608>));
- execution: `2026-08-05T20:53:47.667367669Z` ([log](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-05.jsonl:627>));
- deterministic metrics: `agent_calls=0`, `deterministic=True` ([log](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-05.jsonl:629>)).

Production proves proposal and approval-boundary activity, but no successful
Production execution occurred in the available export. Single-speaker
ownership is verified only on observed paths: Production reports
`reply_owner=gateway`, `agent_calls=0` ([log](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:43>)); Staging reports `reply_owner=gateway` and `agent_claimed_approval=false` ([log](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-02.jsonl:127>)).

### RuntimeSchemaProvider

Final classification: **SHADOW — RUNTIME PATH VERIFIED — COMPONENT LOGGING NOT OBSERVABLE**.

Configuration is `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE=shadow` in
both environments. Current code establishes:

`Airtable write → _provider_unknown_fields() → RuntimeSchemaProvider.get_table_contract()`

([gateway path](</home/elichazan/My-bot/tools/airtable_gateway.py:140>), [provider call](</home/elichazan/My-bot/tools/airtable_gateway.py:199>)).

Targeted Meta API evidence correlates with schema-sensitive writes:

- Production: `2026-08-09T00:25:24.852857655Z`, Meta API `200 OK`, immediately before ActionContract creation ([gap log](</home/elichazan/My-bot/render_logs/gap/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:1>), [write](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:30>)).
- Production: `2026-08-09T00:25:25.787321060Z`, immediately before session update ([gap log](</home/elichazan/My-bot/render_logs/gap/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:2>)).
- Staging: `2026-08-09T00:30:10.917008571Z`, immediately before ActionContract creation ([gap log](</home/elichazan/My-bot/render_logs/gap/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:1>), [write](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:169>)).
- Staging: `2026-08-09T00:30:11.675028715Z`, immediately before session update ([gap log](</home/elichazan/My-bot/render_logs/gap/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:2>), [write](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:179>)).

The provider emits no success/source log for `live` or `cached` returns
([implementation](</home/elichazan/My-bot/core/runtime_schema_provider.py:66>)).
The evidence proves the runtime path, but not whether the selected source was
`live`, `cached`, `snapshot`, or `seed`, and does not show an explicit shadow
comparison. This is an observability gap, not evidence of provider failure or
OFF state.

### IngressEnvelope

Final classification: **ACTIVE — RUNTIME PATH VERIFIED — COMPONENT LOGGING NOT OBSERVABLE**.

The Telegram webhook passes `raw_event_id=str(update.update_id)` into
`run_agent()` ([app.py](</home/elichazan/My-bot/app.py:5808>)). With the effective
flag enabled, `run_agent()` builds and validates the envelope before routing
([app.py](</home/elichazan/My-bot/app.py:4137>)), and passes its ID into the router
([app.py](</home/elichazan/My-bot/app.py:4153>)).

Production shows identity → classifier → route → completed Telegram request
at `2026-08-09T00:25:23.865437868Z`–`00:25:26.186748365Z` ([identity](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:12>), [classifier/router](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:21>), [request](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-09.jsonl:45>)). Staging shows the same at `2026-08-09T00:30:10.502047878Z`–`00:30:12.034378862Z` ([classifier](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:161>), [route](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:162>), [request](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-09.jsonl:184>)).

Current logs do not emit the literal `IngressEnvelope`, envelope ID, or
source reference. This is an observability limitation, not evidence that the
subsystem is inactive.

### EvidenceFinalizer

Final classification: **SHADOW VERIFIED**. Staging emitted
`[EvidenceFinalizerShadow] state=shadow` with a mixed/status-claim mismatch at
`2026-08-02T09:27:16.481952334Z` ([log](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-02.jsonl:128>)). Production also emitted shadow observations in the fresh export. No evidence establishes enforcement behavior.

### Emergency Stop

Final Production status: **VERIFIED IN PROD — CURRENT**. Same-day evidence
established durable bootstrap, active persistence, restart retention,
successful TMA clear, resumed normal responses, and re-hydration after restart.
The fresh export additionally shows five-flag durable hydration at
`2026-08-08T22:51:38.991272932Z` ([log](</home/elichazan/My-bot/render_logs/fresh/production/srv-d80ehsf7f7vs73cq5rn0/2026-08-08.jsonl:794>)); Staging also shows durable bootstrap ([log](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-02.jsonl:43>)). Individual current flag values are not inferred here.

### Environment difference and drift

`COST_WATCHDOG_LIVE` is intentionally OFF in Production and ON in Staging.
Staging writes daily usage at `2026-08-06T05:15:02.309942379Z` and upserts
`AI_Usage_Daily` ([daily](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-06.jsonl:96>), [upsert](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-06.jsonl:101>)). This is an **EXPECTED ENVIRONMENT DIFFERENCE**, not drift.

`INTERACTION_INTELLIGENCE` is OFF in both environments; runtime logs report
`interaction intelligence disabled by env` ([Staging](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-08.jsonl:460>)). Separately, `scheduler.py` reads the environment variable directly rather than the centralized feature-flag accessor ([scheduler.py](</home/elichazan/My-bot/scheduler.py:436>)). Status: **ARCHITECTURAL DRIFT VERIFIED — NO CURRENT RUNTIME CONFLICT**. No correction was made.

### PA-01 and downstream finding

- `CREATE_TASK`: deterministic ActionGateway path ACTIVE in both; Staging additionally proves execution.
- `UPDATE_TASK`: observed in Staging through `handler=agent`; deterministic PA-01 behavior remains unproven.
- `COMPLETE_TASK`: no fresh runtime evidence; do not classify OFF.
- Staging-only canonicalization finding: `sheets_append → Airtable Tasks → no explicit positional converter` at `2026-08-02T09:27:12.290481437Z` ([log](</home/elichazan/My-bot/render_logs/fresh/staging/srv-d99uq63eo5us73967cj0/2026-08-02.jsonl:105>)). This is a downstream gap and does not downgrade ActionGateway or establish a Production issue.

### Runtime-unverified systems, learning, and telemetry

Profile, Project Timeline, Tenant Provisioning, Knowledge Router, Tenant
Config/providers, OTP, and Financial Gate remain **CODE-ONLY / RUNTIME
UNVERIFIED**, not disconnected. Creative Generator, Knowledge Engine, and
Emergency Window are effectively OFF from current configuration/defaults;
absence of logs alone is not the basis for that classification.

Bootstrap reports `learning=sunday 06:00`, but no learning-cycle execution was
observed. Staging watchdog-side `AI_Usage_Daily` persistence is proven, but
the complete core usage-telemetry consumption path is not.

## Remaining follow-ups

1. Provider-scoped observability for `live`, `cached`, `snapshot`, and `seed`.
2. Envelope-scoped observability for envelope ID and source reference.
3. Staging `UPDATE_TASK` comparison with PA-01 policy.
4. `COMPLETE_TASK` runtime verification.
5. Staging Airtable canonicalization follow-up.
6. Learning-cycle and full usage-telemetry verification.
7. Runtime verification of remaining code-present secondary systems.

No further narrow Render export can close the two observability gaps under the
current logging implementation. These are observability improvements, not
evidence of subsystem failure.
