# MoneyPrinterTurbo × BOSS — Audit and Integration Design

**Date:** 16/08/2026  
**Scope:** audit and design only  
**BOSS evidence:** `origin/main` at `e9d1ca82f5f0101ade3785216e8efc2df8fae3dc`  
**MoneyPrinterTurbo evidence:** `harry0703/MoneyPrinterTurbo`, `main`

## Executive verdict

**GO WITH CONDITIONS**

MoneyPrinterTurbo fits BOSS as an automated media-production worker, not as a
marketing or content authority. BOSS can own the script and media policy, but
the integration must use explicit inputs, disable internal content generation,
block publishing, and isolate the worker.

## A. Actual MoneyPrinterTurbo flow

```text
VideoParams
  → script
  → video terms
  → TTS or custom audio
  → subtitles
  → local materials or stock download
  → clip composition
  → subtitles/BGM/aspect-ratio render
  → MP4 task output
  → optional cross-post
```

Relevant upstream functions:

- `app/services/task.py:generate_script`
- `app/services/task.py:generate_terms`
- `app/services/task.py:generate_audio`
- `app/services/task.py:generate_subtitle`
- `app/services/task.py:get_video_materials`
- `app/services/task.py:generate_final_videos`
- `app/services/video.py:generate_video`

Sources: [task pipeline](https://github.com/harry0703/MoneyPrinterTurbo/blob/main/app/services/task.py), [renderer](https://github.com/harry0703/MoneyPrinterTurbo/blob/main/app/services/video.py).

## B. Input control

| Input | Pre-supplied? | Finding |
|---|---:|---|
| Topic | Yes | Used for script generation when no script exists |
| Complete script | Yes | Skips script LLM generation |
| Video terms | Yes | Skips term LLM generation |
| Script/system prompts | Yes | Only affect script generation |
| Local media | Yes | `video_source=local` and `video_materials` |
| Stock media | Yes | Pexels, Pixabay, Coverr |
| Voice/custom audio | Yes | `voice_name` or `custom_audio_file` |
| Subtitles | Yes | Enable/disable and style controls |
| Aspect ratio | Yes | `9:16`, `16:9`, `1:1` |
| Batch count | Yes | `video_count` |
| CLI/API | Yes | `cli.py` and FastAPI service |

The CLI explicitly requires either `--video-subject` or `--video-script`, and
supports `--video-source local --video-materials ...`.

Source: [CLI](https://github.com/harry0703/MoneyPrinterTurbo/blob/main/cli.py), [schema](https://github.com/harry0703/MoneyPrinterTurbo/blob/main/app/models/schema.py).

## C. Script ownership

**YES, with a representation caveat.**

`generate_script()` calls the LLM only when `video_script` is empty. With an
approved script supplied, that exact string becomes the TTS input.

The rendered subtitle representation is not byte-identical by contract:

- Edge subtitles split text into punctuation-based segments.
- Whisper can transcribe the generated audio again.
- Line wrapping and timestamps are technical transformations.

Therefore the safe invariant is:

```text
approved_script == TTS input
```

not:

```text
approved_script == subtitle file byte-for-byte
```

Source: [`task.generate_script`](https://github.com/harry0703/MoneyPrinterTurbo/blob/main/app/services/task.py).

## D. Media ownership

**PARTIAL, close to YES.**

Local-only media is a real supported path. In that mode the worker preprocesses
the supplied files and does not search stock providers.

Stock mode searches Pexels, Pixabay, or Coverr, uses a 24-hour search cache,
filters by aspect ratio, downloads files, and may shuffle clips. BOSS must
choose the policy explicitly and reject any fallback from local to stock.

Source: [material pipeline](https://github.com/harry0703/MoneyPrinterTurbo/blob/main/app/services/material.py).

## E. Platform behavior

The actual video platform behavior is mostly aspect-ratio behavior:

- `9:16` → `1080x1920`
- `16:9` → `1920x1080`
- `1:1` → `1080x1080`

There is also a separate LLM path for title, caption, and hashtags, plus an
optional Upload-Post cross-post path.

There is no complete platform profile for safe zones, CTA rules, duration
limits, bitrate policy, or platform-specific subtitle placement. BOSS should
own a small `PlatformProductionProfile` concept in its adapter/configuration,
not delegate that policy to MoneyPrinterTurbo.

Source: [video aspect model](https://github.com/harry0703/MoneyPrinterTurbo/blob/main/app/models/schema.py), [social metadata](https://github.com/harry0703/MoneyPrinterTurbo/blob/main/app/services/llm.py).

## F. Internal LLM calls

| Call | Trigger | Phase 1 action |
|---|---|---|
| Script generation | No `video_script` | Disable by requiring script |
| Search-term generation | No `video_terms` in stock mode | Supply terms or use local-only |
| TwelveLabs reranking | Stock mode without script-order | Disable |
| Social metadata | Separate metadata request | Do not call |
| TTS | Voice generation, not content LLM | Allowed if selected |
| Whisper | ASR model, not content LLM | Optional |

With an approved script, explicit terms/local media, and no social-metadata
request, Phase 1 can run with **zero content-generation LLM calls inside the
worker**.

## G. Current BOSS fit

`origin/main` already contains:

- `Marketing Demand`
- `Marketing Creatives`
- `Production Handoff`
- `ProtectedDemandFacts`
- `Media Files`
- `Marketing Publications`
- `marketing_gateway`
- `media_gateway.save_asset()`

The existing `Production Handoff` is provider-neutral prose. It includes
selected creative, demand facts, business rules, and explicit “not supplied”
production inputs, but it does not provide a typed, canonical `Approved Script`.

Evidence: `marketing_brief_composer.py:148-199`,
`cmd_marketing.py:735-781`, `marketing_fact_authority.py`, and
`airtable_schema.py:603-688` on `origin/main`.

Do not parse the handoff prose heuristically as a script. Add or designate one
canonical approved-script field only after confirming no existing field can
serve that purpose.

## H. Minimal contract

```python
ProductionRequest(
    request_id,
    approved_script,
    script_sha256,
    video_source,          # local | stock
    approved_media_refs,
    video_terms,
    aspect_ratio,
    voice_name,
    custom_audio_ref,
    subtitle_policy,
    bgm_policy,
    clip_duration,
    output_format,
)
```

```python
ProductionResult(
    request_id,
    status,
    asset_ref,
    duration_seconds,
    mime_type,
    size_bytes,
    script_sha256,
    media_refs_used,
    warnings,
    failure_stage,
)
```

The hash makes script identity testable without asking the worker to become a
content reviewer.

## I. Security and isolation

The worker should receive only a bounded request, a temporary job directory,
approved media, and narrowly scoped TTS/stock credentials when required.

It must not receive BOSS database, Airtable, Drive, Telegram, WhatsApp,
approval, or publishing credentials. Because the CLI accepts absolute paths,
the adapter/container must restrict paths to the mounted job directory.

Set Upload-Post auto-upload off and do not configure publishing credentials.
MoneyPrinterTurbo can otherwise schedule cross-posting after generation.

Source: [cross-post behavior](https://github.com/harry0703/MoneyPrinterTurbo/blob/main/app/services/task.py).

## J. Minimal implementation footprint

1. One BOSS media adapter.
2. One isolated worker process/container.
3. Existing MoneyPrinterTurbo CLI or API.
4. Required `approved_script`.
5. Explicit local/stock policy.
6. Publishing disabled.
7. Result validation: hash, MIME, size, path, and warnings.
8. Reuse `media_gateway.save_asset()` for persistence.

No new capability framework, scheduler, content planner, duplicate engine, or
publisher is needed for Phase 1.

## K. POC

### POC A — approved script + stock allowed

```text
BOSS fixture: approved script + approved terms + platform profile
→ MoneyPrinterTurbo
→ MP4
```

Verify that script and term generation are not called, publishing is absent,
and the structured result contains media evidence.

### POC B — same script + local-only

```text
Same approved script + approved local media only
→ MoneyPrinterTurbo
→ MP4
```

Verify no stock network call, no fallback, exact script hash, and that every
used media ref is approved.

## L. Final ownership split

```text
BOSS owns:
- demand, audience, angle, facts, constraints, CTA
- creative selection and approved script
- media policy and approved media refs
- platform profile, uniqueness, history, approval
- asset identity, evidence, and publication decision

MoneyPrinterTurbo owns:
- TTS/audio rendering
- subtitle timing and segmentation
- local media preprocessing
- explicitly allowed stock download
- clip composition, transitions, aspect-ratio rendering, MP4 generation

Must never be delegated to MoneyPrinterTurbo:
- strategy, topic selection, content generation, fact creation
- CTA invention, creative selection, duplicate prevention
- approval, scheduling, publishing, or BOSS credentials
```

## Audit status

This document records audit/design findings only. It does not implement the
adapter, install MoneyPrinterTurbo, change schemas, or enable production use.

## Verified POC runtime floor

For the approved local-only 1080×1920 POC fixture, Render Standard (2 GiB)
completed `final-1.mp4`; Render Starter (512 MiB) was terminated during
combine. Treat Standard 2 GiB as the minimum proven MPT runtime for this
fixture. This is staging POC evidence, not production enablement; keep
`EXTERNAL_EXECUTION_ENABLED=false` until a separately approved rollout.

## Phase 1 — staging E2E verified (16/08/2026)

The controlled staging-only External Execution path completed with one approved
ActionContract: `f5c73380-40b5-4fda-a626-6049d69bf0b6`.

- MoneyPrinterTurbo provider job: `e0a37806-000c-4ec5-a7c9-8783525d0423`.
- Durable transition: `created → submitted → completed`; submit count: `1`.
- PostgreSQL poll-lease contention: PASS.
- Hardened artifact validation: `final-1.mp4`, 178,500 bytes, 1080×1920.
- The exact approved-script SHA was preserved:
  `d83fb7748851f41ef311ecf62d1e3730a8e0b616e44354ae991173238606a1f1`.
- Staging restart PASS on deploy
  `5c15eddcb17582a598dc35bb102950faf710a288`; the same completed job persisted
  and post-restart resubmission count was `0`.
- Final staging service setting: `EXTERNAL_EXECUTION_ENABLED=false`.

This verifies Phase 1 in staging only. Production was untouched; production
rollout remains a separate explicit decision.
