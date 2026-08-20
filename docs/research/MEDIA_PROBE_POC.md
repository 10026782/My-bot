# Media Probe Capability POC

Status: **POC / NOT PRODUCTION READY.** Fifth capability registered under
`core/external_capability_contract.py`. Not wired to Telegram, WhatsApp, any
customer-facing endpoint, the dispatcher's default boundary, or any
scheduled job.

```
BOSS
  ↓
External Capability Contract   (core/external_capability_contract.py)
  ↓
ExternalExecutionBoundary      (core/external_execution_boundary.py)
  ↓
MediaProbeAdapter              (core/media_probe_adapter.py)
  ↓
ffprobe (system binary)
  ↓
bounded structured metadata (evidence dict — no artifact written)
```

## Scope: strictly read-only

Local file path in → `ffprobe -show_format -show_streams` → bounded metadata
out. No conversion, no upload, no artifact store write, no mutation of any
kind. This is deliberately narrower than the Crawl4AI/Stirling-PDF/MPT
adapters, which all produce a new stored artifact — Media Probe produces
nothing but a metadata evidence dict describing a file that already exists.

## Output fields

`mime_type`, `size`, `duration`, `container` (ffprobe `format_name`),
`video_codec`, `width`, `height`, `audio_stream_count`, `audio_codecs`,
`subtitle_stream_count`, `bitrate`. A field ffprobe doesn't report for a
given file (e.g. `video_codec` for an audio-only file) is empty in the
evidence dict — never fabricated or defaulted to a plausible-looking value.

## Why ffprobe, not MediaInfo

Both give overlapping metadata; shipping both in the first POC would be two
unproven surfaces instead of one. `ffprobe` was picked because it's already
the assumed sibling of `ffmpeg` elsewhere in this codebase's future roadmap
(transcoding) and has a stable, well-documented `-print_format json` output.
MediaInfo is deferred — only added later if a real file surfaces metadata
ffprobe can't extract.

## Dependency

`ffprobe` is a system binary (part of the `ffmpeg` package), not a Python
package — no new `requirements.txt` entry. `MediaProbeAdapter` never bundles
or vendors ffprobe; if it's not on `PATH`, `submit()` returns
`failed` / `media_probe_ffprobe_not_installed` rather than crashing.

## Explicitly out of scope for this POC

MediaGateway, GoFile, MagiCode, storage-provider routing, transcoding,
FFmpeg conversion, Telegram ingestion.
