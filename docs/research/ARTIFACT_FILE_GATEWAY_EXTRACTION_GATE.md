# Artifact / File Gateway Extraction Gate

Status: **AUDIT / DESIGN ONLY.** No production code changed. This document is
the entire output of the gate — no `FileGateway`, no `MediaGateway`, no
provider routing, no materialization boundary was implemented.

Base SHA at gate close: `6a0ba6a` (`origin/main`, includes #804
`chore/gateway-canary-harness-20260821`). Note: the gate-opening message cited
`bb1b416` as "current verified main" — `main` had already advanced one merge
(#804) by the time this audit ran; the gate was re-opened against the
then-current tip per "work on latest `origin/main` only," not against the
stale SHA quoted in the prompt.

Capabilities inspected: MoneyPrinterTurbo (`core/moneyprinterturbo_adapter.py`),
Crawl4AI (`core/crawl4ai_adapter.py`), Stirling-PDF
(`core/stirling_pdf_adapter.py`), Media Probe
(`core/media_probe_adapter.py`) — all registered in
`core/external_capability_contract.py` and run through
`core/external_execution_boundary.py`. Storage: `core/artifact_store.py`
(protocol), `core/local_artifact_store.py`, `core/google_drive_artifact_store.py`.

## 1. Capability matrix

| | MPT | Crawl4AI | Stirling-PDF | Media Probe |
|---|---|---|---|---|
| **A. Input** | Raw local path list (`approved_media_refs`), no artifact contract — just containment + `is_file()` under `MPT_APPROVED_MEDIA_ROOT`, no size/checksum verification | Bare HTTPS URL, allowlist-checked, no artifact at all | List of governed artifacts, each `{result_ref, mime_type, size, sha256}` | Single governed artifact `{result_ref, mime_type, size, sha256}` |
| **B. Output** | `StoredArtifact` via `GoogleDriveArtifactStore` (JSON `result_ref`) **or**, if no artifact store configured, a raw local path string used directly as `result_ref` — bimodal | `StoredArtifact` via `LocalArtifactStore`, local path `result_ref`, `.md` | `StoredArtifact` via `LocalArtifactStore`, local path `result_ref`, `.pdf` | `StoredArtifact` via `LocalArtifactStore`, local path `result_ref`, `.json` |
| **C. Common metadata actually used** | `size`, `sha256`, `mime_type` on the Drive path only | `size`(via `stored.size`, not returned in evidence), `sha256`, `mime_type` | `size`, `sha256`, `mime_type` — as an **input contract**, not just output | `size`, `sha256`, `mime_type` — as an **input contract**, not just output |
| **D. Capability-specific metadata** | `script_sha256`, `runtime_profile`, ffprobe validation fields, `storage_provider` (ad hoc evidence string, not a `StoredArtifact` field) | `final_hostname`, `markdown_chars`, `crawl4ai_version` | `operation`, `input_count`, `stirling_pdf_version` | `detected_format`, `stream_count`, `ffprobe_version` |
| **E. Materialization** | Input already local (media root); output is produced locally by the subprocess, then optionally uploaded to Drive by the adapter itself | Output generated in-process, no materialization needed | Input must already be a real local file under an approved root — **adapter does not download/fetch it from a `result_ref`, it only resolves and verifies one that's already local** | Same as Stirling: resolves/verifies an already-local file, never fetches |
| **F. Ownership/lifecycle** | Adapter owns job dir (deletes it in `cleanup()`); artifact store's durable copy is never deleted by anything | Adapter owns temp file (deleted in `finally`); durable artifact never deleted | Same temp-file pattern; durable artifact never deleted | Same temp-file pattern; durable artifact never deleted |
| **G. Security boundary** | Approved media root, containment only (`_within`), **no checksum/size verification of inputs** | HTTPS-only, IP/loopback-literal rejection, explicit host allowlist (no local-path concept) | Approved root, symlink-reject-before-resolve, containment, regular-file, non-empty, size bound, size-match, checksum-match, MIME allowlist, **plus PDF magic-byte sniff** | Approved root, symlink-reject-before-resolve, containment, regular-file, non-empty, size bound, size-match, checksum-match, MIME allowlist, **plus explicit remote/provider-ref pre-rejection** |

No convergence is assumed from column-D name similarity — `final_hostname`
(Crawl4AI) and `storage_provider` (MPT) describe unrelated things (crawl
destination vs. upload backend) and stay adapter-owned evidence, not shared
fields.

## 2. `StoredArtifact` field audit (current main truth)

```python
@dataclass(frozen=True)
class StoredArtifact:
    result_ref: str
    file_id: str
    size: int
    sha256: str
    mime_type: str | None = None
```

| Field | Populated by | Consumed by | Universally meaningful? |
|---|---|---|---|
| `result_ref` | All 3 stores | `ExternalExecutionBoundary` (opaque, truncated to 500 chars, never parsed), evidence dicts | **No** — see §3, shape differs by store |
| `file_id` | All 3 stores | Nothing reads it outside the store that produced it | Yes as "the store's own identifier for its own record," not cross-store |
| `size` | All 3 stores | Stirling/Media Probe re-verify a *caller-supplied* `size` against it on the **input** side; MPT/Crawl4AI only echo it in evidence | Yes, same meaning everywhere (bytes) |
| `sha256` | All 3 stores | Stirling/Media Probe re-verify a *caller-supplied* `sha256` on the **input** side | Yes, same meaning everywhere |
| `mime_type` | All 3 stores (Drive store hardcodes `"video/mp4"`, others pass it through) | Stirling/Media Probe validate it against a capability-specific allowlist on input | Yes, same meaning, but the *allowed set* is capability-specific by design |

**Revisiting the "no generic `source`/`type`/`provider`" decision:** current
code still proves this was correct, not stale. `GoogleDriveArtifactStore`
already encodes `"provider": "google_drive"` — but *inside* the opaque
`result_ref` JSON blob, not as a `StoredArtifact` field. `MoneyPrinterTurboAdapter`
independently encodes `"storage_provider": "google_drive"` — but as a bounded
*evidence* string key, a completely different mechanism. Two capabilities
that both want to say "this came from Drive" have already, independently,
picked two different, non-interoperable ways to say it. That is evidence
*against* a shared `provider` field having one obvious meaning, not evidence
for adding one. No reversal recommended.

## 3. `result_ref` semantics — the actual pressure point

`result_ref` is not one shape. Confirmed from current code:

- **Local stores** (`LocalArtifactStore`, both `LocalArtifactStore`
  instances Crawl4AI/Stirling/Media Probe use): `result_ref = str(path)` — a
  raw absolute filesystem path string.
- **`GoogleDriveArtifactStore`**: `result_ref = json.dumps({"provider":
  "google_drive", "drive_file_id", "folder_id", "sha256", "size",
  "mime_type"})` — a JSON envelope, not a path.
- **MPT is bimodal on its own**: if `MPT_ARTIFACT_STORAGE=google_drive`, its
  `PollResult.result_ref` is the Drive JSON blob; if unset, `poll()` falls
  back to returning `str(final)` — a raw local path — directly, with no
  store involved at all (lines `core/moneyprinterturbo_adapter.py:169-177`).

Answers to §5's questions:

1. **Is `result_ref` intentionally opaque?** Yes at the boundary
   (`ExternalExecutionBoundary` never parses it, only truncates/stores it) —
   but not opaque to *consumers*, because there are now consumers
   (Stirling-PDF, Media Probe) that must open it.
2. **Are consumers parsing provider-specific shapes themselves?** No —
   and this is deliberate. Both Stirling-PDF and Media Probe **refuse**
   anything that isn't a plain local path (Stirling implicitly, via
   containment failing on a URL/JSON string; Media Probe explicitly, via a
   `"://" in raw_ref or raw_ref.startswith("{")` pre-check). Neither adapter
   attempts to interpret a Drive-shaped `result_ref`.
3. **Are there multiple places that must know local vs. remote?** Not yet —
   exactly two places (Stirling, Media Probe), and both resolve it the same
   way: "must already be a real local path under my configured root, or I
   fail closed."
4. **Is there already a canonical way to resolve/materialize it?** No. No
   code anywhere converts a Drive-shaped `result_ref` into a local file.
5. **Does Media Probe expose the first real pressure point because it's
   local-only?** Yes, and it is the sharper of the two data points — Media
   Probe's docstring and validator were written *knowing* about the Drive
   JSON shape and explicitly designed to reject it rather than guess. That's
   the strongest evidence in the repo that "local-only, fail closed on
   anything else" is the current, deliberate, and — per the evidence in §9 —
   still-sufficient answer.

## 4. Real duplication (§6)

| Duplication | Real consumers | Classification |
|---|---|---|
| `_within(path, root)` — commonpath containment check | Verbatim in `local_artifact_store.py`, `moneyprinterturbo_adapter.py`, `stirling_pdf_adapter.py`; re-implemented differently (but equivalently) in `media_probe_adapter.py` via `Path.relative_to()` + `try/except` | **A — genuinely generic now.** 4 independent copies/reimplementations of the same 5-line check. |
| Governed-artifact-reference → verified local `Path` validation sequence (symlink-reject-before-resolve → resolve → containment → regular-file → non-empty → size-bound → size-match(supplied vs. actual) → checksum-match(supplied vs. actual) → MIME-allowlist) | `StirlingPDFAdapter._validate_inputs` (looped, N files) and `MediaProbeAdapter._validate_input` (single file) — same 4-field input contract (`result_ref`/`mime_type`/`size`/`sha256`), same check order, same fail-closed semantics | **A — genuinely generic now**, ≥2 real consumers, proven identical intent and near-identical implementation. This is the finding the gate exists to surface. |
| Content-sniffing the resolved bytes (`%PDF-` magic bytes) | Stirling-PDF only | **B — similar but capability-specific.** Media Probe has no equivalent (ffprobe itself is the content check). Must NOT be pulled into a shared validator. |
| `tempfile.NamedTemporaryFile` → write → `store.put()` → `unlink()` in `finally` | Crawl4AI, Stirling-PDF, Media Probe — 3 consumers, ~6 lines each, byte-identical shape | **C — not worth extracting yet.** Real duplication, but each site's `metadata=` dict and `mime_type=` differ enough, and the block is small/low-risk/rarely-touched enough, that a shared helper would trade "3 obvious inline blocks" for "1 indirection + 3 call sites," a wash at this size. Revisit if a 4th consumer appears. |
| Streaming vs. whole-buffer SHA-256 | Media Probe streams in 1 MB chunks; `LocalArtifactStore.put()`, `GoogleDriveArtifactStore.put()`, and `StirlingPDFAdapter._validate_inputs` all read the whole file into memory before hashing | Not duplication — an **inconsistency** (Media Probe alone chose the more memory-safe pattern). Flagged, not fixed — a behavior change is out of scope for an audit-only gate; bounds today (20-500 MB depending on capability) make it non-urgent. |

## 5. Producer → consumer analysis (§9)

| Pair | Status | Why |
|---|---|---|
| Crawl4AI output (local, `.md`) → Stirling-PDF | Conceptually invalid | Stirling requires `mime_type == "application/pdf"` and `%PDF-` signature; markdown fails both. |
| Crawl4AI output → Media Probe | Conceptually invalid | Not in Media Probe's MIME allowlist. |
| Stirling-PDF output (local, `.pdf`) → Media Probe | Conceptually invalid | Not in Media Probe's MIME allowlist (by design — audio/video only). |
| **LocalArtifactStore output (any) → another local-artifact capability sharing a root** | **Works now, with only configuration, zero new code** | This is the positive existence proof: two POCs already speak the exact same "local path + verified size/sha256/mime" contract. Nothing about the *shape* blocks chaining today — only domain/MIME fit does. |
| MPT output, **local fallback** (`MPT_ARTIFACT_STORAGE` unset) → Media Probe | **Works now, with only configuration** | Result is a raw local `.mp4` path; `video/mp4` is already in Media Probe's allowlist; only requirement is both roots pointing at compatible locations. |
| MPT output, **Google Drive mode** (`MPT_ARTIFACT_STORAGE=google_drive`) → Media Probe | **Blocked — result_ref cannot be materialized** | This is the one concrete, reproducible case of §3's pressure point: Media Probe's `_validate_input` deterministically raises `remote_unsupported` on the Drive JSON blob. This is a *proven-would-block*, not an *actively-needed-today* flow — nothing in the current codebase attempts this chain yet. |
| GoogleDriveArtifactStore output → Stirling-PDF | Blocked, same reason, purely hypothetical (no caller attempts it) | Same `remote_unsupported`-shaped rejection would occur (Stirling's containment check would fail on the JSON string, just without Media Probe's more specific error). |

One real, reproducible blocked seam exists (MPT-via-Drive → Media Probe).
Zero *actual* callers are blocked by it today — it is a proven capability
gap, not a proven incident. That is the evidentiary line between Verdict B
and Verdict C below.

## 6. Ownership / lifecycle (§10) — current truth, no invented policy

- **Source artifacts**: never deleted by any adapter. Stirling and Media
  Probe only read; MPT copies media into its own job dir, leaving the
  original untouched.
- **Temp files**: always adapter-owned, always deleted in a `finally` before
  `submit()` returns. Consistent across all three sync capabilities.
- **Durable result artifacts** (the `LocalArtifactStore`/`GoogleDriveArtifactStore`
  output of `.put()`): **nothing deletes these, ever, for any capability.**
  `ArtifactStore.cleanup(identity)` exists as a protocol method, but grep
  confirms its only caller is `MoneyPrinterTurboAdapter.cleanup()` — which
  calls `shutil.rmtree()` on the adapter's own **job working directory**, not
  `self.artifact_store.cleanup(...)`. The durable Drive/local artifact
  produced by `.put()` is retained indefinitely, for every capability, today.
  This is current fact, not a gap this gate is asked to close.

## 7. Security contract comparison (§11)

Stirling-PDF's `_validate_inputs` and Media Probe's `_validate_input` are
materially equivalent: same fields, same fail-closed order, same "reject
before resolve" symlink handling, same size/checksum/MIME gate. The only
differences are (a) single-file vs. list, (b) Stirling's PDF magic-byte sniff
(capability-specific, stays out), (c) Media Probe's explicit pre-check for
remote/JSON-shaped refs vs. Stirling's implicit rejection via containment
failure — a cosmetic difference in failure-code specificity, not in outcome
(both fail closed either way). This is a real, provable "materially
equivalent" case per §11's own test — a shared validator is justified.

## 8. Verdict

### B — Extract one small shared primitive: `ArtifactInputValidator`

Not a Gateway (§8/§12-D fails: only one capability-to-capability chain is
even hypothetically blocked, and nothing calls it — no proof of "multiple
providers, multiple consumers, routing/orchestration requirements").

Not a materialization boundary (§12-C fails: zero *actual* consumers are
blocked by a remote `result_ref` today; §5's one blocked pair is proven-
possible, not proven-needed. Materialization of a Drive-shaped `result_ref`
into a local file remains explicitly out of scope until a real caller needs
it — Problem B from §8 stays deferred, not solved and not started).

What *is* proven: two real, independent capabilities (Stirling-PDF, Media
Probe) already implement — correctly, and almost identically — the same
narrow responsibility: *take a governed artifact reference the caller
supplied, and produce a verified local file handle or a specific rejection
reason, refusing anything not already local.* That responsibility is real,
small, and duplicated today. Extract exactly that, nothing more.

## 9. Minimal spec — `ArtifactInputValidator`

**Responsibility.** Given a governed artifact reference and an approved
root, return a verified local `Path` or raise a specific, stable reason.
Nothing else — no fetching, no uploading, no format-specific content
validation, no provider awareness.

**Inputs.**
- `result_ref: str`, `mime_type: str`, `size: int`, `sha256: str` (the
  existing 4-field contract both current consumers already use — no new
  type).
- `approved_root: Path` (adapter-configured, as today).
- `allowed_mime_types: frozenset[str]` (adapter-owned allowlist — Stirling's
  and Media Probe's are different sets and stay different).

**Output.** A resolved, verified `Path` on success. On failure, one of a
fixed small set of reason atoms (not adapter-prefixed strings) — e.g.
`missing_field`, `remote_or_provider_ref`, `symlink`, `outside_root`,
`not_found`, `empty`, `too_large`, `size_mismatch`, `checksum_mismatch`,
`mime_unsupported` — that each adapter maps to its own existing
`{adapter}_{reason}` failure-code string, so **today's exact user-visible
failure codes do not change** (`stirling_pdf_input_symlink`,
`media_probe_symlink_rejected`, etc. are adapter-owned formatting, not the
validator's concern).

**Ownership.** Caller-owned. The validator never deletes, moves, or copies
anything — it only inspects and hashes the file the caller already pointed
it at. No lifecycle change from today.

**Cleanup.** None — this primitive never creates a file, so it has nothing
to clean up.

**Errors.** All failures are deterministic/local (file-not-found,
size/hash/MIME mismatch) — never `outcome_unknown`. Matches both current
adapters' existing behavior exactly; no new failure semantics introduced.

**Security invariants (must all be preserved, not just replicated):**
reject a symlink *before* resolving it; require containment under the
approved root after resolving; require a regular, non-empty file; enforce a
caller-supplied max-size bound; recompute size/sha256 from the real file and
compare against the caller's claim, never trust the claim alone; enforce a
capability-owned MIME allowlist last.

**Explicit non-responsibilities.** Does not fetch/download/materialize a
remote or provider-specific `result_ref` (still rejected, exactly as both
adapters do today — `remote_or_provider_ref`). Does not sniff content beyond
what the adapter already does (PDF magic bytes stay in Stirling-PDF; ffprobe
stays in Media Probe). Does not decide which MIME types are allowed
(adapter-owned). Does not touch `StoredArtifact`, `ArtifactStore`, or
`ExternalExecutionBoundary` contracts. Does not add a `source`/`type`/
`provider` field anywhere (§2's finding stands).

**First two consumers (already exist, this is a refactor of them, not new
call sites):** `StirlingPDFAdapter._validate_inputs` (called once per item in
its input list) and `MediaProbeAdapter._validate_input` (called once).

**Exact duplication this replaces.** The symlink/resolve/containment/
regular-file/non-empty/size-bound/size-match/checksum-match sequence
currently living independently in `core/stirling_pdf_adapter.py:173-227` and
`core/media_probe_adapter.py:173-234`, plus the `_within()` copies in
`core/local_artifact_store.py:63-67`, `core/moneyprinterturbo_adapter.py:300-304`,
and `core/stirling_pdf_adapter.py:70-74` (all four collapse onto whatever
single containment check the extracted validator uses internally).

## 10. What this gate deliberately does not decide

- Whether/when to actually perform the extraction (a future implementation
  PR, not this gate).
- Any remote/provider-ref materialization boundary (deferred — no proven
  need).
- Any provider routing, storage selection, or gateway of any kind (deferred
  — no proven need, and explicitly out of scope per the gate's own rules).
- MPT's un-upgraded local-media input path (`approved_media_refs`, no
  checksum/size verification) — flagged in §1 row A/G as an inconsistency
  with the artifact-reference contract Stirling/Media Probe use, but fixing
  it is a separate, capability-owned decision, not this gate's scope.
