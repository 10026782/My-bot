# Crawl4AI Capability POC

Status: **POC / NOT PRODUCTION READY.** Second capability registered under
`core/external_capability_contract.py`, proving the contract with a real
external tool end-to-end. Not wired to Telegram, WhatsApp, any customer-facing
endpoint, the dispatcher's default boundary, or any scheduled job.

```
BOSS
  ↓
External Capability Contract   (core/external_capability_contract.py)
  ↓
ExternalExecutionBoundary      (core/external_execution_boundary.py)
  ↓
Crawl4AIAdapter                (core/crawl4ai_adapter.py)
  ↓
Crawl4AI Python SDK
  ↓
bounded Markdown artifact (core/local_artifact_store.py)
```

## Version

`crawl4ai==0.9.2`, pinned exactly (not `>=`/`latest`).

- **Official source:** PyPI (`pip index versions crawl4ai`, 2026-08-19 — 0.9.2 is the latest published release) and the upstream GitHub release tag `v0.9.2` (`gh api repos/unclecode/crawl4ai/releases/tags/v0.9.2`, published 2026-07-15).
- **Security notes:** `gh api repos/unclecode/crawl4ai/security-advisories` lists 11 advisories as of 2026-08-19 (3 critical, 6 high, 2 unrated), every one of them patched at or before `0.9.0` — i.e. all fixed well before this pin. Every advisory's vulnerable surface is the Docker API server, computed-field extraction (`JsonCssExtractionStrategy`), request-supplied hooks, `browser_config.extra_args` (Chromium launch-argument injection), or file-download handling — none of it reachable by this adapter, which never starts the Docker API server, never sets hooks/computed fields/`extra_args`, and never enables downloads. This matches `docs/research/SIX_TOOL_AUTOMATION_AUDIT_GATE_2026-08.md`'s Crawl4AI verdict (POC, pin `>=0.9.2`, treat "no Docker server, no computed fields, no LLM extraction, exact-hostname allowlist" as a hard security requirement).

## Installation mode: Python SDK, not the Docker API server

**Use:** `crawl4ai` as an in-process Python library (`AsyncWebCrawler`, `BrowserConfig`, `CrawlerRunConfig`), same pattern as the existing `scripts/research_crawler_poc/crawl.py`.

**Do not use:** the Crawl4AI Docker API server, MCP server, playground, or dashboard. Every Critical/High advisory in the section above is scoped to that server surface — running it would add a network service and reopen exactly the attack surface this POC is designed to avoid. It also avoids adding a second long-running service for a single-URL, request/response capability.

## Dependency isolation

`crawl4ai==0.9.2` is **not** added to `requirements.txt` — it pulls in Playwright/Chromium, which every other BOSS deployment target would otherwise download for no reason. It lives only in a bounded, optional requirements file:

```
scripts/crawl4ai_capability_poc/requirements.txt
```

installed into a disposable virtualenv, exactly like the existing `scripts/research_crawler_poc/requirements.txt` convention. No `[all]` extra, no torch/transformers/local-LLM/embedding/GPU package — the adapter's own `_crawl()` only ever imports `AsyncWebCrawler`/`BrowserConfig`/`CrawlerRunConfig`.

`core/crawl4ai_adapter.py` itself has no import-time dependency on the `crawl4ai` package — the `from crawl4ai import ...` line lives inside `_crawl()`, imported lazily on first real submit. `resolve_adapter("crawl4ai")` and the module import succeed even when the package isn't installed; only an actual crawl attempt fails, deterministically (`SubmitResult("failed", failure_code="crawl4ai_not_installed")`), never a crash.

## Capability contract

Registered in `core/external_capability_contract.py`:

| Field | Value |
|---|---|
| `capability_id` | `crawl4ai` |
| `adapter_name` | `crawl4ai` |
| `version` | `0.9.2` |
| `execution_mode` | `sync` — see "Sync completion" below |
| `risk_class` | `medium` |
| `timeout_seconds` | `30` |
| `cleanup_capability` | `False` — no local job directory to clean up (unlike MPT) |

## Sync completion (generic boundary extension)

Crawl4AI's SDK call is a single in-process request/response — the result is known before `submit()` returns, so forcing it through MPT's async submit-then-poll shape would mean either a fake background job or performing the crawl inside `submit()` while lying that it's still pending. Neither is acceptable, so `core/external_execution_boundary.py` gained a small, generic extension: `SubmitResult.status` now also accepts `"completed"` (plus a `result_ref` field, mirroring `PollResult.result_ref`). When an adapter's `submit()` returns `status="completed"`, the boundary durably persists the job as `status="completed"`/`completed_at`/`result_ref`/bounded evidence in the same `submit()` call — no background thread, no in-memory queue, no fake provider job. `poll_due()` only ever scans jobs with `status == "submitted"` (`ExternalExecutionRepository.due_submitted()` filters on that Airtable field), so a sync-completed job is structurally never polled. This is a capability-agnostic addition to the boundary, not Crawl4AI-specific — any future sync capability can use the same path. `Crawl4AIAdapter.poll()` exists only to satisfy the `ExternalAdapter` Protocol and is never legitimately reached.

## Allowlist policy

- **Scheme:** `https` only. `http`, `file:`, `data:`, `javascript:`, `ftp:`, and everything else is rejected before any network access.
- **Host:** exact-match only, against `CRAWL4AI_ALLOWED_HOSTS` (comma-separated hostnames), normalized to lowercase. No substring/suffix matching — `example.com` never matches `evil-example.com`, `example.com.evil.com`, or `sub.example.com` unless that exact string is also listed.
- **Defense in depth:** any allowlist entry (or incoming URL hostname) that is a raw IP literal (`ipaddress.ip_address()` succeeds — v4 or v6) or a known loopback/metadata name (`localhost`, `0.0.0.0`, `metadata.google.internal`) is rejected even if an operator mistakenly puts it in `CRAWL4AI_ALLOWED_HOSTS`.
- **Credentials in URL** (`https://user:pass@host/...`) are rejected outright.

## Storage behavior

Reuses the existing `core/artifact_store.py` `ArtifactStore` protocol (`put()`/`cleanup()`, same shape `core/google_drive_artifact_store.py` already implements for MPT) via a new, generic `core/local_artifact_store.py` — filesystem-backed, no OAuth/Google Drive scope needed for this POC. Configured via `CRAWL4AI_ARTIFACT_ROOT`; if unset, `submit()` fails closed (`crawl4ai_storage_unconfigured`) before any crawl is attempted.

- Path shape: `<CRAWL4AI_ARTIFACT_ROOT>/crawl4ai/<sanitized-contract-id>.md`.
- The filename is derived solely from `contract_id` (sanitized to `[A-Za-z0-9._-]`, everything else collapsed to `-`) — never from a caller-supplied path/filename.
- Write is atomic: content is written to a temp file, then `os.replace()`d into place.
- A resolved-path containment check (`_within()`, same pattern as `moneyprinterturbo_adapter.py`) rejects any target that would resolve outside the configured root, as defense in depth beyond the filename sanitization.
- The Markdown artifact carries a small YAML-ish header (`source_url`, `final_hostname`, `title`, `crawled_at`, `crawl4ai_version`) followed by the page's Markdown body, truncated to 500,000 bytes.

## Evidence (bounded)

`Crawl4AIAdapter.evidence_extra_keys = {"final_hostname", "markdown_chars", "crawl4ai_version"}`, combined with the boundary's universal core, yields exactly: `adapter_name`, `provider_status`, `result_ref`, `result_checksum`, `final_hostname`, `markdown_chars`, `crawl4ai_version` (plus `completed_at`, set directly on the job by the boundary). The caller-supplied payload has no mechanism to inject additional evidence keys or choose the output path — both are entirely adapter/boundary-derived.

## Security limitations (read before any further use)

- **Redirect safety is detect-and-reject, not prevent.** Crawl4AI's browser already follows a redirect before this adapter can see the destination. `submit()` checks the *final* hostname after the crawl completes and rejects the result (`crawl4ai_redirect_not_allowlisted`) if it isn't in the allowlist — the result is never stored or reported as success — but the outbound navigation to the disallowed host already happened. Closing this fully would require either disabling redirect-following (breaks normal sites) or a request-level network hook, which this POC deliberately does not add (see "Do not build yet" in the original spec). Treat this as owner/dev-only, not safe for an untrusted or attacker-influenced allowlist.
- **No DNS-level SSRF protection.** The allowlist matches on the URL's literal hostname string; it does not resolve DNS and check the resolved IP against private/internal ranges. An allowlisted public hostname whose DNS is later repointed to an internal address is not defended against by this adapter. Mitigated only by the allowlist being operator-controlled and small, not a general answer.
- **`check_robots_txt=True`** is honored (Crawl4AI's own robots.txt check), but this is netiquette, not a security control.
- Not multi-tenant safe, not rate-limited, not concurrency-limited (no `.policy` capacity gate — single ad-hoc calls only), no resource/memory ceiling beyond Crawl4AI's own per-page timeout.

## Exact POC scope

One capability: `crawl one explicitly allowlisted HTTPS URL → bounded Markdown artifact`. No site-wide/recursive/adaptive/deep crawl, no autonomous discovery, no batch or scheduled crawling, no authenticated sessions, no LLM extraction, no user-supplied JS/hooks/computed fields, no screenshots/PDF output, no arbitrary browser args or proxy configuration. No Telegram command, no WhatsApp flow, no customer-facing endpoint, no wiring into the shared `get_default_boundary()` singleton the dispatcher/scheduler use for MPT.

## Manual smoke procedure

Requires real network access and the isolated dependency — never run in CI.

```bash
python3 -m venv /tmp/crawl4ai-poc-venv
/tmp/crawl4ai-poc-venv/bin/pip install -r scripts/crawl4ai_capability_poc/requirements.txt

CRAWL4AI_ALLOWED_HOSTS="example.com" \
CRAWL4AI_ARTIFACT_ROOT=/tmp/crawl4ai-poc-artifacts \
/tmp/crawl4ai-poc-venv/bin/python3 scripts/crawl4ai_capability_poc/smoke.py --url https://example.com/
```

This constructs its own `ExternalExecutionBoundary` with an in-memory repository and a real `Crawl4AIAdapter` — it does **not** touch `get_default_boundary()`, Airtable, or any live BOSS state. It prints the resulting `DispatcherOutcome` and the stored artifact path.

## Known limitations

- Redirect and DNS-level SSRF gaps described above.
- Single fixed page-load timeout (30s in the contract; adjustable per-adapter-instance, not per-call).
- No capacity/concurrency policy — unlike MPT, this adapter has no `.policy` attribute, so the generic boundary applies no gating.
- The in-memory smoke harness's repository is not durable — a real integration would need a caller that goes through Airtable-backed `ExternalExecutionRepository`, which this POC does not add.

## What is required before production

- A resolved-IP SSRF check, not just hostname string matching.
- A real answer to the redirect-navigation-happens-before-rejection gap (either accept the residual risk explicitly for a curated allowlist, or add a pre-navigation network hook).
- Concurrency/rate limits (a `.policy` object, same shape as `MPTExecutionPolicy`).
- A decision on real dispatcher wiring: which tool/role/approval requirement would gate `dispatch_tool("crawl4ai_fetch", ...)`, and whether it needs `requires_approval` in `tool_registry.py`.
- Durable artifact retention/cleanup policy (this POC never deletes what it writes).
- Multi-tenant scoping if ever exposed beyond owner/dev use.
