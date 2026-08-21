# Media Probe Capability POC

Status: **POC / NOT PRODUCTION READY.** Fifth capability registered under
`core/external_capability_contract.py`. Not wired to Telegram, WhatsApp, any
customer-facing endpoint, the dispatcher's default boundary, or any
scheduled job.

```
BOSS
  ↓
governed local artifact (result_ref / mime_type / size / sha256)
  ↓
External Capability Contract   (core/external_capability_contract.py)
  ↓
ExternalExecutionBoundary      (core/external_execution_boundary.py)
  ↓
MediaProbeAdapter              (core/media_probe_adapter.py)
  ↓
ffprobe (system binary)
  ↓
normalized bounded metadata → new JSON result artifact (core/local_artifact_store.py)
```

## Scope: read-only source, but a real result artifact

"Read-only" means the **source** artifact is never modified, converted, or
uploaded. It does not mean nothing is stored: the normalized probe result is
written as a small JSON artifact through the same `LocalArtifactStore`
boundary every other capability in this file uses. `SubmitResult.result_ref`
points at that **result** artifact, never back at the source file.

There is no `MediaGateway`/`FileGateway`, no conversion, no transcoding, no
GoFile/MagiCode, no Telegram/WhatsApp wiring, and no remote/provider input —
this POC supports local artifact references only.

## Input contract: artifact-first, not a bare path

`submit()` does not accept `payload["path"]`. It accepts the same fields
`core/artifact_store.py`'s `StoredArtifact` already carries — no new
`ArtifactRef` type:

```json
{"result_ref": "...", "mime_type": "...", "size": 123, "sha256": "..."}
```

Every input goes through, in order: require a configured approved root
(`MEDIA_PROBE_INPUT_ROOT`) → reject a `result_ref` that looks remote/
provider-specific (contains `://`, or looks like a JSON blob — the shape
Google Drive's `result_ref` uses) → reject a symlink (checked before
resolving) → resolve → require containment under the approved root → require
a regular, non-empty file → enforce a bounded max input size (500 MB) →
recompute the file's real size and compare against the supplied `size` →
compute SHA-256 by streaming the file in chunks (never loaded fully into
memory) and compare against the supplied `sha256` → validate the supplied
`mime_type` against an explicit POC allowlist (a handful of common video/
audio containers). Any mismatch fails deterministically before ffprobe ever
runs — the caller controls none of: the ffprobe executable, its flags, the
subprocess environment, or any path outside the approved root.

## Output: normalized JSON result artifact + bounded evidence

The full normalized result — `mime_type`, `size`, `duration`, `container`,
`video_codec`, `width`, `height`, `audio_stream_count`, `audio_codecs`,
`subtitle_stream_count`, `bitrate` — is written to a new JSON artifact
(`mime_type="application/json"`) via `LocalArtifactStore`, then the temp
file is deleted. A field ffprobe doesn't report for a given input (e.g.
`video_codec` for an audio-only file) is `null` — never fabricated,
defaulted to `0`, or guessed from a plausible-looking value.

`SubmitResult.evidence` stays small and operational — `adapter_name`,
`provider_status`, `result_ref` (the result artifact, not the source),
`result_checksum`, `operation`, `input_mime_type`, `input_size`,
`detected_format`, `stream_count`, `elapsed_ms`, `ffprobe_version`. It never
carries the full normalized JSON, raw ffprobe output, arbitrary ffprobe
tags, the source's local path, or raw stderr.

## Failure semantics

This capability performs no durable *external* mutation whose outcome could
become unknowable — ffprobe is a local, read-only subprocess call. Every
validation failure and every ffprobe failure (not installed, timeout,
non-zero exit, malformed JSON, oversized stdout, too many streams) is
therefore `failed`, not `outcome_unknown`. The one exception is the local
JSON-artifact write itself — a genuine local durable effect — which defers
to `LocalArtifactStore`'s own `ArtifactStoreError.uncertain` flag, the same
pattern every other adapter here already uses.

## Resource bounds

Bounded input size (500 MB), bounded ffprobe stdout (2 MB), a deterministic
max stream count (64) rejected outright rather than silently truncated,
streaming (not whole-file) SHA-256, and a subprocess timeout (15s) — always
`shell=False`, always a fixed argv, never caller-controlled flags or
environment.

## Why ffprobe, not MediaInfo

Both give overlapping metadata; shipping both in the first POC would be two
unproven surfaces instead of one. `ffprobe` was picked because it's already
the assumed sibling of `ffmpeg` elsewhere in this codebase's future roadmap
(transcoding) and has a stable, well-documented `-print_format json` output.
MediaInfo is deferred — only added later if a real file surfaces metadata
ffprobe can't extract.

## Dependency

`ffprobe` is a system binary (part of the `ffmpeg` package), not a Python
package — no new `requirements.txt` entry, no vendored binary in this repo.
If it's not on `PATH`, `submit()` returns `failed` /
`media_probe_ffprobe_not_installed` rather than crashing (this is the real,
unmocked path exercised in CI, which has no ffprobe installed).

## Real ffprobe smoke

Verified manually (not as a committed script — CI has no ffprobe, and this
capability's own catalog registration is already at this node's context
budget ceiling; see `docs/context_librarian/layers/approvals.json`'s
`layer.approvals` notes): a tiny local fixture synthesized with `ffmpeg` (no
download, no customer data) was probed end to end through
`ExternalExecutionBoundary` with a real `ffprobe` binary, independently
re-verifying the stored result's checksum and MIME type, confirming the
source file's SHA-256/size were unchanged afterward, and confirming a
duplicate `contract_id` submit does not re-invoke ffprobe. See the PR
description for the recorded run output.

## Explicitly out of scope for this POC

MediaGateway, FileGateway, GoFile, MagiCode, storage-provider routing,
remote/provider artifact materialization, transcoding, FFmpeg conversion,
Telegram ingestion, production deployment, generic concurrency
infrastructure, a new `ArtifactRef` type.
