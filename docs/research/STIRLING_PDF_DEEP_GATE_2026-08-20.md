# Stirling-PDF — Deep Gate (2026-08-20)

**Scope: research only.** No code, install, deployment, PR (beyond this doc), or table changes. This closes the two open questions the prior audit (`docs/research/SIX_TOOL_AUTOMATION_AUDIT_GATE_2026-08.md`, §17, "Procurement / Architecture-Fit Audit — Stirling-PDF") flagged as blocking a straight "USE NOW" verdict, plus a short set of additional items. It does **not** decide to build, does not update `business_tool_registry.py`/`OPEN_SOURCE_TOOL_INDEX.md`/`EXTERNAL_CAPABILITY_INDEX.md`, and does not start a POC.

**Method:** the prior audit could not resolve the two open questions from official documentation alone and flagged that direct code inspection would be required. This gate does that — a shallow, read-only clone of the pinned upstream tag, grepped and read, then discarded. No Stirling-PDF instance was ever installed, run, or exposed to a network.

---

## Question 1 — File lifecycle: where, how long, when deleted

**Closed. MIT-licensed, active, code-verified.**

`app/common/src/main/java/stirling/software/common/service/TempFileCleanupService.java` (MIT — not in any of the license-carve-out directories) is a real, wired-in `@Service`, not dead code:

- **Where:** `TMPDIR=/tmp/stirling-pdf` (set as a container env var in `docker/embedded/Dockerfile`), further namespaced per-purpose (`stirling-pdf-*`, LibreOffice's own subdirectory, PDFBox's `.pdfbox.cache` in the user home). No persistent volume by default — this is ephemeral container-local storage, not a durable store, unless an operator explicitly bind-mounts something over it (the official compose examples don't).
- **How long:** default `maxAgeHours = 24`, checked by a `@Scheduled` job that runs every `cleanupIntervalMinutes = 30` (both configurable via `ApplicationProperties.TempFileManagement`). Files matching known Stirling-PDF/PDFBox/LibreOffice temp-file name patterns older than the max age are deleted; empty/zero-byte files get a much shorter 5-minute timeout (treated as corrupted).
- **On restart:** `startupCleanup = true` by default, and in **container mode** (detected via a `machineType` bean — Docker/Kubernetes) the startup pass uses `maxAgeMillis = 0`, i.e. it deletes *all* matching temp files immediately on boot, not just old ones. This directly closes the "does a container restart leave stale files" question: no, by default it doesn't.
- **What's covered:** both files the registry explicitly tracks (`TempFileRegistry`/`TempFileManager`, files created via the app's own temp-file helper) and unregistered stray temp files matching known name patterns, scanned recursively (capped at depth 5) under the configured temp directories.

**Verdict on this question: resolved favorably.** Default behavior is short-lived (≤24h, actively swept every 30 minutes, plus an aggressive container-restart sweep), ephemeral (no persistent volume unless an operator adds one), and the mechanism is real and MIT-licensed — BOSS would inherit it for free, not need to build it.

**What this does not answer:** encryption-at-rest for the ≤24h window a file does exist in `/tmp` (not found — treat as absent; standard container filesystem, no evidence of any at-rest encryption layer). If that matters for a specific document type, it's a deployment-level control (encrypted container filesystem/volume), not something Stirling-PDF provides.

---

## Question 2 — Isolated, safe deployment

**Closed, with a concrete recommended shape.**

| Item | Finding |
|---|---|
| **Internal-service-only image** | `docker/backend/Dockerfile` + `docker/compose/docker-compose-unified-backend.yml` (`MODE=BACKEND`) build a **backend-API-only** image — no bundled web UI at all, smaller attack surface than the standard embedded image the prior audit assumed. This is the shape that matches BOSS's actual need (server-to-server API calls only, no human ever browses to it). |
| **Network exposure** | Nothing in any official compose file publishes beyond `8080:8080` on the compose network; there is no requirement to expose it publicly. Same recommendation as the prior audit: bind it to an internal network only, never route public/Telegram/WhatsApp traffic to it directly. |
| **Authentication** | Off by default (`SECURITY_ENABLELOGIN`/`DOCKER_ENABLE_SECURITY: "false"` in every official compose example) — confirmed still the default at v2.14.3. For a single-caller (BOSS-only) deployment this is an acceptable default *only* combined with network isolation — BOSS should still set `security.customGlobalAPIKey` (a single shared API key, MIT-licensed mechanism, not a proprietary-tier feature) and send it as `X-API-KEY` on every call, per the prior audit's own integration sketch. **New finding this round:** avoid the `/api/v1/pipeline/*` endpoint family specifically — see CVE-2026-57485 below; BOSS's planned direct-endpoint-per-tool integration (`pdf_merge`, `pdf_compress`, etc., not the pipeline feature) never touches this at all. |
| **Docker/image pinning** | The official Dockerfiles pin their own build-stage base images by full digest (`FROM gradle:9.6.0-jdk25@sha256:...`, `FROM eclipse-temurin:25-jre-noble@sha256:...`). For BOSS's own deployment, the equivalent discipline is pinning the published Stirling-PDF tag exactly (e.g. `stirlingtools/stirling-pdf:2.14.3`, never `:latest`) — matches the same "pin exactly, verify before bumping" convention already applied to `crawl4ai==0.9.2` in this repo's other POC. |
| **Resource limits** | `docker/compose/docker-compose-unified-backend.yml` ships an **official example**: `deploy.resources.limits.memory: 4G`, `reservations.memory: 2G` — directly matches the prior audit's own "4GB recommended for production" inference, now with an official source. No CPU limit example given; add one (e.g. `cpus: "2"`) independently if needed. |
| **Non-root runtime** | Container starts as root (needed to fix volume-mount permissions via `PUID`/`PGID`, default `1000`/`1000`) then drops privileges via `setpriv` to a dedicated `stirlingpdfuser`/`stirlingpdfgroup` before running the app (`scripts/init-without-ocr.sh`) — standard, reasonable pattern, not running the JVM as root in steady state. |
| **Health check** | Built in: `HEALTHCHECK` hits `/api/v1/info/status` every 30s (embedded image) — reusable for BOSS's own container orchestration/monitoring without extra work. |
| **Cleanup** | Covered by Question 1 above — the temp-file cleanup service runs regardless of deployment shape. |

**Concrete recommended isolated-deployment shape (still no code, matches the prior audit's sketch, refined with this round's findings):** `docker/compose/docker-compose-unified-backend.yml`-style, `MODE=BACKEND`, single pinned tag (not `:latest`), internal Docker network only (no public port publish), `security.customGlobalAPIKey` set + `X-API-KEY` sent by BOSS's dispatcher on every call, `4G` memory limit / `2G` reservation, default temp-file cleanup left as-is (already favorable), integration calling individual REST endpoints only (`/api/v1/general/*`, `/api/v1/security/*`, `/api/v1/convert/*` etc.) — never `/api/v1/pipeline/*`, never `/api/v1/user/*`/`/api/v1/admin/*`/`/api/v1/info/requests/all` (irrelevant anyway with login disabled and BOSS as sole caller, but worth naming as a hard "never call" list).

---

## Additional items

**Current version:** `v2.14.3`, released 2026-08-06 (14 days before this gate), repo actively pushed to as of 2026-08-19 — not stale, not archived. VERIFIED via `gh api repos/Stirling-Tools/Stirling-PDF/releases/latest` and `.../repos/Stirling-Tools/Stirling-PDF`.

**License:** unchanged since the prior audit — confirmed by reading the actual `LICENSE` file at the `v2.14.3` tag. Dual/open-core: MIT everywhere except `app/proprietary/`, `app/saas/`, `engine/` (AI agent), and a handful of `frontend/*` subtrees, each with its own proprietary "Stirling PDF User License." **Code-verified this round:** `app/core/` and `app/common/` — which is where the temp-file cleanup, SSRF protection, and every PDF-operation controller BOSS would actually call live — are unambiguously MIT (not listed in the carve-out). The rate-limiting filters (`UserBasedRateLimitingFilter`, `IPRateLimitingFilter`), by contrast, live under `app/proprietary/` — confirming that a self-built MIT-only image has **no built-in rate limiting**; that remains BOSS's own responsibility if concurrency/throughput control is ever needed (same open item as already named for the Crawl4AI POC's own `.policy` gap).

**Security advisories:** 12 published GitHub Security Advisories as of 2026-08-20 (`gh api repos/Stirling-Tools/Stirling-PDF/security-advisories`) — 5 high, 2 medium, 2 low, plus the 3 SSRF advisories the prior audit already found (now confirmed still exactly 12, not more than the prior audit implied by omission — the prior audit's list of 7 was incomplete; the full list adds CVE-2026-57485, CVE-2026-34071, CVE-2026-33438, CVE-2026-33437, and a corrected read of CVE-2026-33436). **All 12 are patched at or before v2.9.0** — v2.14.3 is current on every one. Most recent and most relevant: **CVE-2026-57485** (HIGH, CVSS 8.5, published 2026-07-30) — an authenticated `ROLE_USER` can steal the internal service account's API key via the `/api/v1/pipeline/handleData` endpoint and use it to bypass rate limits / access admin-only monitoring endpoints. Patched in 2.9.0. **Not exploitable under BOSS's planned deployment** (login disabled, BOSS is the only caller, no second `ROLE_USER` account ever exists to mount the attack) — named here because it reinforces the "never call `/api/v1/pipeline/*`" rule above regardless. **New finding this round, materially improving the security picture beyond the prior audit's CVE-history-only view:** the SSRF CVEs (CVE-2025-4656{8,150,151,161}) are not just "patched" — the fix is a real, still-present, wired-in `SsrfProtectionService` (MIT, `app/common/`) called from `CustomHtmlSanitizer`/`SvgSanitizer`/`OfficeDocumentSanitizer`, enabled by default at `MEDIUM` level (blocks private networks, localhost, link-local, and cloud-metadata endpoints out of the box; `MAX` level available to block all external URLs entirely). This is defense-in-depth beyond "stay patched," not just a historical fix.

**API surface to use:** plain REST, one endpoint per operation (`/api/v1/general/merge-pdfs`, `/api/v1/security/add-password`, `/api/v1/convert/pdf/img`, etc.), Swagger UI at `/swagger-ui/index.html` on the running instance for the exact current schema. Confirms the prior audit's plan — call individual operation endpoints directly, never the pipeline/AI-agent layers.

**File size limit:** `SYSTEM_MAXFILESIZE` env var, in MB, valid range 1–999 (code-enforced range check, invalid values are logged and ignored — falls back to Spring's own `spring.servlet.multipart.max-file-size`, default `2000MB` if that env var is never set either). Official example compose files use `50` (ultra-lite), `100` (standard/unified), `200` (fat) — pick per BOSS's actual expected document sizes; there is no reason to leave it at the 2000MB fallback for a bot ingesting WhatsApp/Telegram-sourced documents.

**Timeout:** `spring.mvc.async.request-timeout`, default 1,200,000ms (20 minutes), overridable via `SYSTEM_CONNECTIONTIMEOUTMILLISECONDS`. Generous default for OCR/LibreOffice-heavy operations on large files; BOSS's own dispatcher-level tool-call timeout would still need to be set shorter than whatever's configured here (or this would need lowering) to avoid a hung HTTP call blocking BOSS's own request cycle.

**Concurrency:** no built-in queue or worker pool for the free/MIT tier (confirms prior audit — synchronous request/response, one JVM handling requests via its own thread pool). No rate limiting in the MIT core (see License above — that's proprietary-tier). If BOSS ever needs to bound concurrent PDF operations, that's a BOSS-side gate (same shape as `MPTExecutionPolicy`/a future `.policy` object), not something Stirling-PDF provides itself.

**Infra cost:** still not calculable to an exact dollar figure without BOSS's actual PDF-operation volume (same missing input the prior audit named) — this gate doesn't change that. What's now concrete: the **official 4GB/2GB memory-limit example** above gives a firm sizing floor to price against (e.g. a Render container sized for 4GB RAM), rather than the prior audit's inferred range.

---

## Updated status

Both concrete open questions from the prior "AUDIT DEEPER" verdict are now closed with direct, code-level evidence (not marketing docs, not inference):

1. **File retention** — ephemeral, ≤24h default, actively swept every 30 minutes, aggressively cleared on every container restart. Favorable.
2. **Isolated/safe deployment** — a backend-only image variant exists (smaller surface than assumed), official resource-limit example exists, image pinning/non-root/healthcheck are all already handled by the upstream Dockerfile, and the one auth-relevant CVE this round (`CVE-2026-57485`) is both patched in the current pin and structurally inapplicable to BOSS's single-caller deployment shape regardless.

**This gate does not change the verdict from AUDIT DEEPER to USE NOW** — that's an owner decision, and per this task's explicit scope, no implementation, POC, or catalog update happens here. What this gate does is remove the two specific "unresolved, must confirm before touching real customer PDFs" blockers the prior audit named — the remaining open items (BOSS's actual expected PDF volume for cost sizing, and the eventual dispatcher-tool-registration work itself) are ordinary next-step engineering questions, not open research risk.

---

*No code was edited, installed, or executed in any repository for this gate. The shallow clone used to inspect `app/common/`'s temp-file/SSRF source and the official Docker/compose files was read-only and deleted after use; no Stirling-PDF instance was ever run.*
