# Stirling-PDF Capability POC

Status: **POC / NOT PRODUCTION READY.** Third capability registered under
`core/external_capability_contract.py`, alongside `moneyprinterturbo` and
`crawl4ai`, proving the contract with a real document-processing service.
Not wired to Telegram, WhatsApp, any customer-facing endpoint, the
dispatcher, the shared `get_default_boundary()` singleton, or any Universal
Media/File Gateway (none exists yet, and this POC does not build one).

```
BOSS
  ↓
External Capability Contract   (core/external_capability_contract.py)
  ↓
ExternalExecutionBoundary      (core/external_execution_boundary.py)
  ↓
StirlingPDFAdapter             (core/stirling_pdf_adapter.py)
  ↓
isolated Stirling-PDF 2.14.3 backend service (loopback-only, local/dev)
  ↓
governed output PDF artifact (core/local_artifact_store.py)
```

## Exact version and operation

`stirlingtools/stirling-pdf:2.14.3` (Docker), pinned exactly — re-verified
current (still the latest release, no advisory published since it shipped,
see `docs/research/STIRLING_PDF_DEEP_GATE_2026-08-20.md` §"Additional items"
and the re-check performed at the start of this POC). One operation only:
`merge_pdfs` — two or more input PDF artifacts in, one merged PDF artifact
out. No compress/OCR/split/convert/redact/password/pipeline/arbitrary
operation selection.

## Verified API schema (read from `v2.14.3` source, not guessed)

- **Endpoint:** `POST /api/v1/general/merge-pdfs` (`@GeneralApi` class-level
  `@RequestMapping("/api/v1/general")` + `@AutoJobPostMapping(value =
  "/merge-pdfs")` on `MergeController.mergePdfs()`).
- **Content-Type:** `multipart/form-data` (the endpoint's default; no
  `?async=true` is ever sent, so the call is synchronous by construction —
  matches `execution_mode="sync"`).
- **Fields sent, all explicit, none left to server defaults:** `fileInput`
  (repeated file parts, one per input PDF, in submission order) — the exact
  field name from `MultiplePDFFiles.fileInput`; `sortType=orderProvided` (a
  no-op comparator — preserves the order BOSS submitted the files in, not
  Stirling's own file-name/date heuristics); `removeCertSign=false`;
  `generateToc=false`.
- **Response on success:** HTTP 200, `Content-Type: application/pdf`, raw
  merged PDF bytes in the body (`WebResponseUtils.pdfFileToWebResponse`).
- **Health endpoint:** `GET /api/v1/info/status` — confirmed unauthenticated
  even when login is enabled (`RequestUriUtils` explicitly treats it as
  public), MIT-licensed (`app/core`), no `X-API-KEY` needed.

## Authentication — and a licensing nuance discovered while building this

BOSS is the sole caller, authenticated via a single `X-API-KEY` header
checked against `SECURITY_CUSTOMGLOBALAPIKEY`
(`ApplicationProperties.Security.customGlobalAPIKey`).

**New finding, not surfaced by the prior Deep Gate:** reading the actual
`v2.14.3` source for this POC found that the *enforcement* of this
mechanism — `UserAuthenticationFilter`, `UserService`, and the whole login
system it depends on — lives entirely in `app/proprietary/`, under the
**Stirling PDF User License** (the same restrictive license as
`engine/LICENSE`), not the MIT core. That license's own text: *"You or your
organization may not use the Software in production, at scale, or for
business-critical processes"* without a paid User License, but *"you may use
the Software without a paid subscription for the sole purposes of internal
trial, evaluation, or minimal use"* provided it's not used "in client-facing
or commercial contexts." This POC is used strictly for **local
evaluation/POC purposes only** — no production deployment, no client-facing
use. **No production license clearance is claimed here**: this document
reports what the license text says, it does not make a legal determination
beyond what the source itself proves. Production use of this same mechanism
**remains blocked** pending an explicit license review/decision — either a
paid Stirling PDF User License, or a different auth approach that doesn't
depend on `app/proprietary` at all (e.g. network-isolation-only with a
reverse-proxy-injected header, since Stirling's own auth module is off the
table without a license). This correction is also now reflected in
`docs/research/STIRLING_PDF_DEEP_GATE_2026-08-20.md` ("Authentication" —
corrected as of this PR to remove its prior "MIT-licensed mechanism"
characterization of `customGlobalAPIKey`).

`SECURITY_ENABLELOGIN=true` is required for the API-key filter to activate
at all (verified: `SecurityConfiguration`'s `loginEnabledValue` gates the
whole filter chain) — set together with `SECURITY_CUSTOMGLOBALAPIKEY` in
`scripts/stirling_pdf_capability_poc/docker-compose.yml`.

Hard requirements enforced in `core/stirling_pdf_adapter.py`: missing
`STIRLING_PDF_API_KEY` → fails closed before any network call
(`stirling_pdf_api_key_unconfigured`); the key is read only from trusted
config (env var / constructor arg), never from the caller's payload; it is
never written into evidence, logs, or the durable `ExternalExecutionJob`
(which has no raw-payload field to begin with — see
`core/external_execution_repository.py`); no hardcoded default.

## Deployment mode

Docker, loopback-only (`127.0.0.1:<port>:8080`, never `0.0.0.0`), local/dev
POC only — no Render deployment, no public host. `scripts/stirling_pdf_capability_poc/docker-compose.yml`
uses the standard published image (not a from-source backend-only build —
simpler and more reliable for a POC; BOSS only ever calls API endpoints, the
bundled UI is never touched or exposed beyond loopback). `/tmp/stirling-pdf`
is `tmpfs` (in-memory, wiped with the container) on top of Stirling's own
upstream temp-file cleanup (24h default max age, swept every 30 minutes, see
the Deep Gate doc) — no persistent volume for Stirling's internal processing
state. Memory limit 2G/1G reservation — a POC-sized deviation from the
upstream-recommended 4G/2G production sizing, appropriate for tiny test PDFs
on a local machine, not a production sizing recommendation.

## File-size limits

- **BOSS-side (enforced in the adapter, before any network call):** 20MB per
  input file, 60MB total across all inputs, 80MB max accepted output size.
- **Stirling-side:** `SYSTEM_MAXFILESIZE=25` (MB) — set above BOSS's 20MB
  per-file cap, so BOSS's own limit is always the tighter, first-enforced
  one; Stirling's limit exists only as a second, looser backstop.
- 2–10 input files per call (`_MIN_FILES`/`_MAX_FILES`).

## Timeout

HTTP request timeout: 45 seconds (`STIRLING_PDF_HTTP_TIMEOUT_SECONDS`,
clamped to a 120-second ceiling regardless of configuration — never the
upstream's own 20-minute default). `CapabilityContract.timeout_seconds=60`
— set above the HTTP timeout, non-contradictory (60 > 45), reflecting the
adapter's whole budget (preflight + network + output validation + artifact
write), not just the network call.

## Artifact-first input contract

The adapter never accepts arbitrary caller-supplied filesystem paths. Each
input is a small, POC-narrow structure (no canonical `ArtifactRef` type
exists in the repo yet, and this POC doesn't invent a repo-wide one — see
"Explicitly out of scope" below):

```json
{"result_ref": "<path>", "mime_type": "application/pdf", "size": <int>, "sha256": "<hex>"}
```

## Preflight validation (every input, before any network call)

1. Resolve `result_ref`.
2. **Symlink check on the raw, unresolved path** — checked before
   resolving, because `.resolve()` follows symlinks and would otherwise let
   a symlink through by checking its *target's* symlink-ness instead of its
   own (a real bug caught and fixed by this POC's own test suite — see
   `test_symlink_input_rejected`).
3. Require the resolved path to be under the configured
   `STIRLING_PDF_INPUT_ROOT` (resolved-path containment check).
4. Require a regular file, non-empty.
5. Enforce the 20MB per-file cap.
6. Require `mime_type == "application/pdf"` (caller-supplied metadata check).
7. Verify the `%PDF-` magic header (lightweight preflight — no PDF-parsing
   dependency added just for this).
8. Recompute the actual on-disk size and SHA-256; compare against the
   caller-supplied `size`/`sha256` — any mismatch fails closed.
9. Enforce the 60MB total-across-inputs cap.

## Output validation (before persisting completion)

Not "HTTP 200 alone." In order: response `Content-Type` (if present) must
start with `application/pdf`; body non-empty; bounded to 80MB; `%PDF-` magic
header present. Only then: write to a transient local temp file →
`LocalArtifactStore.put()` (the same, unmodified, reused artifact store from
the Crawl4AI POC — no new storage abstraction) → `StoredArtifact` → delete
the transient temp file in `finally`, success or failure.

## Evidence (bounded)

`StirlingPDFAdapter.evidence_extra_keys = {"operation", "input_count",
"input_total_bytes", "output_bytes", "stirling_pdf_version", "elapsed_ms"}`,
combined with the boundary's universal core, yields exactly: `adapter_name`,
`provider_status`, `result_ref`, `result_checksum`, plus those six. No PDF
bytes, no full input paths beyond what's already implied by evidence keys,
no secrets — ever.

## File lifecycle — four distinct ownership classes

**A. Input artifacts** — owned by BOSS/the calling harness. The adapter
never deletes them (`test_input_source_artifacts_are_not_deleted_by_adapter`).

**B. Stirling-PDF's own internal temp files** — container-local, ephemeral,
governed entirely by Stirling's own upstream `TempFileCleanupService`
(24h default max age, swept every 30 minutes, aggressive on container
restart — see the Deep Gate doc). This POC does not claim to immediately
delete these itself; that would misrepresent a lifecycle this POC doesn't
own or control.

**C. The adapter's transient local response file** — created only to move
the HTTP response body into `ArtifactStore.put()`; always deleted in
`finally`, on both success and storage failure (proven by
`test_transient_response_temp_file_cleaned_after_success`/
`..._after_storage_failure`).

**D. The final output artifact** — retained as the POC's durable result
while the completed `ExternalExecutionJob` references it; not automatically
deleted. `cleanup_capability=False` in the contract — not because nothing is
ever cleaned up, but because this adapter's `poll()` (and therefore any
`adapter.cleanup(job)` call, which the boundary only ever makes after a
polled `completed` result) is structurally unreachable for a sync adapter;
marking `cleanup_capability=True` here would misrepresent semantics the
adapter doesn't actually implement.

## Concurrency decision — intentionally deferred, not implemented

The existing adapter-declared `.policy` mechanism
(`ExternalExecutionBoundary`'s `getattr(adapter, "policy", None)` +
`policy.capacity_reason(jobs)`) was built for MPT's long-lived async jobs,
where a job realistically sits in `submitted` state for minutes — a durable
job-row count is a meaningful proxy for real concurrent load in that window.
For a fast synchronous single-flight guarantee (this POC's actual need), it
is not safe: `capacity_reason()` reads a snapshot of existing job rows with
no locking or atomicity relative to a concurrent `submit()` call, and a sync
job resolves to `completed` within seconds — two genuinely simultaneous
calls could both read the job list before either has durably created its
own row, and both would proceed to call Stirling-PDF in parallel. That would
be a **false concurrency guarantee**, worse than documenting the gap
honestly. Per instruction, this PR does not refactor the generic boundary to
add a real primitive for this (no Redis, no distributed lock, no queue
engine) — that would be exactly the kind of speculative framework this POC
is scoped to avoid.

**What's actually in place for this POC:** the manual smoke harness is
single-flight by construction (one sequential script, no concurrent calls).
**What a real production concurrency guarantee would need:** either an
actual mutex primitive scoped per-adapter inside the boundary itself (e.g. a
`threading.Lock`/`asyncio.Lock` held for the duration of `submit()` when the
adapter declares a "single-flight" contract field — a real, small, generic
addition, not Stirling-specific), or a durable, atomic claim (e.g. a
conditional Airtable/DB write with a uniqueness constraint) — neither exists
today and neither is implemented here.

## Manual smoke procedure

Requires Docker and real local network access — never run in CI.

```bash
export STIRLING_PDF_POC_API_KEY=$(openssl rand -hex 24)
docker compose -f scripts/stirling_pdf_capability_poc/docker-compose.yml up -d
# wait for the container to report healthy

export STIRLING_PDF_BASE_URL=http://127.0.0.1:8091
export STIRLING_PDF_API_KEY=$STIRLING_PDF_POC_API_KEY
export STIRLING_PDF_INPUT_ROOT=/tmp/stirling-pdf-poc-inputs
export STIRLING_PDF_ARTIFACT_ROOT=/tmp/stirling-pdf-poc-artifacts
python3 scripts/stirling_pdf_capability_poc/smoke.py

docker compose -f scripts/stirling_pdf_capability_poc/docker-compose.yml down
```

This constructs its own `ExternalExecutionBoundary` with an in-memory
repository and a real `StirlingPDFAdapter` — it does **not** touch
`get_default_boundary()`, Airtable, or any live BOSS state.

## Real smoke evidence

Executed against a real local container (image digest
`sha256:3b3670fce70b396ec56ba380a3cc7858e0abf83fe13f31c88f7737847763a396`).
See the PR description for the bounded evidence (Stirling version,
operation, input/output byte counts, completed status, checksum presence,
elapsed time, container teardown confirmation) — no document contents
copied, no customer data used.

**A real bug was found and fixed while running this smoke, not worked
around with another mock:** the first `docker-compose.yml` draft mounted
`/tmp/stirling-pdf` as `tmpfs` for an extra in-memory-only guarantee beyond
the container's already-ephemeral writable layer. Every merge call then
failed with HTTP 500: `NoClassDefFoundError: Could not initialize class
stirling.software.jpdfium.panama.JpdfiumLib`, root-caused via `docker logs`
to `UnsatisfiedLinkError: ... libpdfium.so: failed to map segment from
shared object` — Stirling 2.14.3 extracts jpdfium's native library into a
subdirectory of that exact path and `mmap`s it with `PROT_EXEC`, which this
Docker daemon's `tmpfs` mounts don't grant. Confirmed by reproducing with
plain `docker run` (same failure with `tmpfs`, real 200 + a genuine 2-page
merged PDF without it). Fixed by removing the `tmpfs:` directive — the
container's default writable layer is already ephemeral and volume-free, so
nothing was lost by removing it, and the fix is documented inline in the
compose file so it isn't silently reintroduced.

**Also directly confirms the licensing finding above, from the running
application's own logs, not just static source reading:** with
`SECURITY_ENABLELOGIN=true` set, container startup logs `License check
result: type=NORMAL, requiresPaid=true, hasPaid=false` (via
`UserLicenseSettingsService`) — the application itself reports, at runtime,
that this configuration requires a paid license beyond a small grandfathered
allowance.

## Security limitations

- Everything named in `docs/research/STIRLING_PDF_DEEP_GATE_2026-08-20.md`
  still applies (no DNS-level SSRF check on Stirling's own side, detect-vs-
  prevent nature of some mitigations, etc.) — this POC doesn't relitigate
  those.
- **New this POC:** the auth mechanism this POC relies on is itself
  proprietary-licensed (see "Authentication" above) — a licensing blocker,
  not a technical one, but a real one before production.
- No rate limiting on either side (Stirling's MIT core has none; this POC
  adds none — see "Concurrency decision").
- Loopback-only exposure is a POC convenience, not a substitute for a real
  network-isolation design in a shared/production environment.

## Production blockers

- The authentication-licensing decision above (paid User License vs. a
  non-Stirling auth layer).
- A real concurrency primitive (see "Concurrency decision").
- Real hosting placement, durable service observability, resource sizing
  based on actual volume.
- Dispatcher/tool registration (`pdf_merge` as a governed dispatcher tool,
  `roles_allowed`/`requires_approval` in `tool_registry.py`).
- Permissions/approval UX for a document-processing action.
- Production artifact retention policy for the merged-PDF output (this POC
  never deletes what it writes).
- Encrypted-at-rest requirements, if the documents BOSS would process
  warrant it.
- Service upgrade/security-patch policy, production health monitoring,
  rollback/deployment procedures.

POC success means only that the capability architecture works end-to-end
with a real second document-processing service — not that any of the above
is solved.

## Explicitly out of scope for this POC

Compress/OCR/split/convert/redact/password/image/Office-conversion
operations; the `/api/v1/pipeline/*` feature (hard-denied by design — never
called, never reachable through any payload field); a generic `ArtifactRef`
platform (this POC uses one small, Stirling-specific input structure, not a
repo-wide framework); a Universal Media/File Gateway, GoFile/MagiCode
adapters, ffprobe/MediaInfo, a general ingest router (none of this exists
yet; this POC only avoids coupling itself to a specific transport provider,
so a future gateway could produce the same artifact references this POC
already consumes — that's the extent of the architectural commitment made
here); Telegram/WhatsApp/customer-facing wiring; any change to
`business_tool_registry.py`/`OPEN_SOURCE_TOOL_INDEX.md`/
`EXTERNAL_CAPABILITY_INDEX.md`; production deployment.
