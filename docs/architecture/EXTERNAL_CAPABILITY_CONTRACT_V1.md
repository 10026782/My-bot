# External Capability Contract v1

Status: implemented, v1. Scope: contract + generic-boundary decoupling only —
no new external tool is connected by this document or its accompanying PR.

## 1. Purpose

`core/external_execution_boundary.py` (`ExternalExecutionBoundary`) is the
durable boundary BOSS uses to hand off long-running or out-of-process work to
an external tool and later poll for its result. Before this contract, the
boundary's own code carried MoneyPrinterTurbo-specific knowledge (a literal
`"moneyprinterturbo"` string gating capacity checks, an evidence allowlist
shaped around MPT's video/script fields, a hardcoded import of
`MPTExecutionPolicy`). That made the boundary look generic but actually
required editing shared code for every new capability.

This contract makes the boundary capability-neutral: it defines the small,
stable pieces of metadata (`CapabilityContract`) and the explicit resolution
mechanism (`core/external_capability_contract.py`) a future adapter needs to
plug into the existing boundary, without the boundary ever branching on a
specific adapter's name again.

```
BOSS
  ↓
Identity / Permission / Approval
  ↓
Capability Contract          (this document — metadata + registry)
  ↓
External Execution Boundary  (generic — core/external_execution_boundary.py)
  ↓
Adapter                      (capability-owned — e.g. MoneyPrinterTurboAdapter)
  ↓
External Tool
```

BOSS remains the sole source of authority. An external tool is never a
router, a permission authority, an approval authority, a business-state
authority, or a source of truth — it only executes bounded work the boundary
already durably recorded before submission.

## 2. Ownership boundaries

| Concern | Owner |
|---|---|
| Identity, permissions, approval | Upstream of the boundary — unchanged, unaffected by this contract |
| Durable job state, create-before-submit, idempotency, polling lease | `ExternalExecutionBoundary` / `ExternalExecutionRepository` / `ExternalPollLeaseRepository` — generic, capability-agnostic |
| Capacity/throughput policy | The adapter, via an optional `.policy` attribute the adapter constructs itself (e.g. `MPTExecutionPolicy`) |
| Evidence shape beyond a small universal core | The adapter, via an optional `.evidence_extra_keys` frozenset |
| Capability metadata (version, execution mode, risk class, semantics) | `CapabilityContract` in `core/external_capability_contract.py` |
| capability_id → adapter resolution | The explicit `_ADAPTER_FACTORIES` registry in `core/external_capability_contract.py` |
| Actual external-tool integration | The adapter module (e.g. `core/moneyprinterturbo_adapter.py`) |

The boundary never imports a specific adapter's policy or evidence-shape
module. It only calls `getattr(self.adapter, "policy", None)` and
`getattr(self.adapter, "evidence_extra_keys", frozenset())` — structural,
not name-based.

## 3. Lifecycle (unchanged by this contract)

`submit()`: read existing job → if terminal (`submitted`/`completed`), return
the existing acceptance; if failed/outcome_unknown, refuse to resubmit → if
the adapter declares a capacity policy, check it and durably park the job
without calling the adapter if capacity is unavailable → durable
create-before-submit → call `adapter.submit()` → durably record
`submitted`/`failed`/`outcome_unknown`.

`poll_due()`: acquire a per-job poll lease → re-read the job → call
`adapter.poll()` → durably record the terminal or in-progress result → run
`adapter.cleanup()` only after a `completed` result is durably persisted →
release the lease.

`completed_job()`: the only way any caller may treat external work as done —
existence of a durable `completed` row is the sole authority; a raw
provider/process success signal alone is never accepted.

None of this changed in v1. Every existing MoneyPrinterTurbo test in
`test_external_execution_boundary.py`, `test_mpt_runtime_policy.py`, and
`test_moneyprinterturbo_adapter.py` passes unmodified.

## 4. Adapter contract

An adapter must provide:

```python
class ExternalAdapter(Protocol):
    name: str
    def submit(self, request: dict) -> SubmitResult: ...
    def poll(self, job: ExternalExecutionJob) -> PollResult: ...
```

An adapter may optionally provide:

- `.policy` — an object with `capacity_reason(jobs: list[ExternalExecutionJob]) -> str` (empty string = capacity available). If absent, the boundary applies no capacity gating for that adapter.
- `.evidence_extra_keys` — a `frozenset[str]` of additional evidence field names the adapter is allowed to write, beyond the universal core (`provider_job_id`, `provider_status`, `submitted_at`, `completed_at`, `result_checksum`, `result_ref`, `adapter_name`, `checked_at`, `storage_result`, `capacity`). If absent, only the universal core is kept.
- `.cleanup(job)` — called only after a `completed` poll result is durably persisted.

## 5. Capability metadata (`CapabilityContract`)

```python
@dataclass(frozen=True)
class CapabilityContract:
    capability_id: str
    adapter_name: str
    version: str
    execution_mode: str        # "sync" | "async"
    risk_class: str            # "low" | "medium" | "high"
    input_schema_ref: str = ""
    output_schema_ref: str = ""
    timeout_seconds: int | None = None
    retry_semantics: str = ""
    idempotency_semantics: str = ""
    evidence_schema_ref: str = ""
    cleanup_capability: bool = False
    healthcheck_capability: bool = False
```

This is metadata only in v1 — it documents an adapter's shape for humans and
future tooling; the boundary does not currently branch on any of these
fields. `execution_mode` is recorded for future sync-capability support (see
§8) but the boundary itself only implements the async submit/poll path
today.

## 6. Adapter resolution

```python
def resolve_adapter(capability_id: str) -> ExternalAdapter | None:
    factory = _ADAPTER_FACTORIES.get(capability_id)
    return factory() if factory else None
```

`_ADAPTER_FACTORIES` is a plain, explicit, code-reviewed `dict[str,
Callable[[], ExternalAdapter]]` in `core/external_capability_contract.py`.
Adding a capability means adding one entry, in a reviewed PR — nothing is
auto-discovered, no `capability_id` is ever taken from user input and used to
import a module, and no plugin loading exists. An unknown `capability_id`
resolves to `None` — fail closed; callers must treat that identically to
"not configured," never as a default.

`ExternalExecutionBoundary`'s own default-adapter selection
(`_default_adapter()` in `core/external_execution_boundary.py`) still gates
on `MPT_RUNTIME_ROOT` being set, then resolves through this registry — the
env-var-driven selection trigger is unchanged from before this contract;
only the *lookup mechanism* is now the explicit registry instead of a direct
hardcoded import.

## 7. Failure semantics

- Adapter exception during `submit()` or `poll()` → `outcome_unknown`, never
  a crash, never an automatic resubmit.
- `failed` and `outcome_unknown` are both terminal from the caller's
  perspective — the boundary refuses to resubmit a contract_id that already
  reached either state.
- A capacity-policy block durably parks the job (creating it if it didn't
  exist yet) and returns `outcome_unknown` with the policy's reason as
  `error_code` — it never silently drops the request.

## 8. Evidence semantics

Evidence is bounded and allowlisted before being durably persisted:
`_bounded_evidence()` keeps only universal fields plus whatever the adapter's
`evidence_extra_keys` declares, and truncates every value to 200 characters.
This is unchanged in shape from before v1 — only the *source* of the
allowlist changed, from one flat MPT-shaped set hardcoded in the boundary to
a small universal core (boundary-owned) plus an adapter-declared extension
(capability-owned).

## 9. Sync vs. async

v1 implements async only: `submit()` returns immediately with an
accepted/failed/outcome_unknown result, and a separate `poll_due()` scan
later discovers the terminal outcome. `CapabilityContract.execution_mode`
already has a `"sync"` value reserved for a future capability that returns
its result inline from `submit()` (e.g. a bounded synchronous Crawl4AI
fetch) — no sync code path exists yet, and none is required for this
contract to hold together to record intent.

## 10. Security invariants

- No arbitrary command execution, dynamic plugin loading, user-controlled
  adapter names, or arbitrary URLs are introduced by this contract.
- No credentials in payload or evidence; no secrets in logs.
- No adapter writes directly to Airtable or mutates business state — all
  durable state goes through `ExternalExecutionRepository`.
- No bypass of `ActionGateway`/dispatcher governance — capability resolution
  happens only inside the boundary the dispatcher already calls through
  `get_default_boundary()`.

## 11. Non-binding illustrative examples (not implemented)

These show the contract is not blocked by a future adapter's shape — none of
this code exists yet.

**Crawl4AI** — `request → bounded network operation → structured/Markdown
result`. Likely `execution_mode="sync"` or a fast async poll; `risk_class`
probably `"low"`/`"medium"`; no `cleanup_capability` needed if it produces no
local artifact.

**Stirling-PDF** — `file/artifact → external processing → output artifact →
cleanup`. Async, `cleanup_capability=True`, evidence extras similar in shape
to MPT's artifact-validation fields but PDF-specific (page count, output
mime type) declared via its own `evidence_extra_keys`.

**n8n Internal** — `BOSS/internal trigger → workflow execution → async
result/webhook/poll`. Async; if a webhook callback is added later it would
need its own durable correlation to a `contract_id`, out of scope for v1.

## 12. Explicitly out of scope for v1

- No Crawl4AI, Stirling-PDF, or n8n implementation or installation.
- No new Docker infrastructure, Redis, or queue engine.
- No sync execution path implementation (metadata field only).
- No webhook-driven completion path.
- No plugin auto-discovery or dynamic adapter loading.
- No change to `ActionGateway` semantics, approval flow, permissions, or
  MoneyPrinterTurbo's runtime behavior.
- No new monitoring/telemetry system — `ExternalExecutionJob`'s existing
  fields (`attempt_count`, `submitted_at`, `completed_at`, `failure_code`,
  `evidence`) plus `CapabilityContract.capability_id` (currently 1:1 with
  `adapter_name` on the job) already carry what a future observability pass
  would need; no new write path was added for this.
