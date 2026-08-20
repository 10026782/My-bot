"""Crawl4AI capability adapter — POC / NOT PRODUCTION READY.

Single explicitly-allowlisted HTTPS URL -> bounded Markdown artifact, via the
Crawl4AI Python SDK in-process (no Docker API server, no LLM extraction, no
hooks/user JS/computed fields/proxy — see
docs/research/CRAWL4AI_CAPABILITY_POC.md for the full scope and the
redirect-safety limitation this adapter cannot fully close without adding a
network surface this POC deliberately doesn't add).

This is a sync capability (CapabilityContract.execution_mode == "sync"):
submit() performs the crawl and returns a terminal SubmitResult directly —
poll() is never legitimately reached and exists only to satisfy the
ExternalAdapter contract.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from core.artifact_store import ArtifactStoreError
from core.external_execution_boundary import PollResult, SubmitResult
from core.local_artifact_store import LocalArtifactStore

UPSTREAM_REPOSITORY = "https://github.com/unclecode/crawl4ai"
UPSTREAM_VERSION = "0.9.2"
_MAX_MARKDOWN_BYTES = 500_000
_LOOPBACK_NAMES = frozenset({"localhost", "0.0.0.0", "metadata.google.internal"})


class _CrawlFailed(Exception):
    """Crawl4AI ran and deterministically reported failure (result.success is False)."""


def _is_ip_or_local(hostname: str) -> bool:
    if hostname in _LOOPBACK_NAMES:
        return True
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False


def _allowed_hosts_from_env() -> frozenset[str]:
    raw = os.environ.get("CRAWL4AI_ALLOWED_HOSTS", "")
    hosts = {h.strip().lower() for h in raw.split(",") if h.strip()}
    # Defense in depth: even a misconfigured allowlist can never grant an IP
    # literal or a loopback/local name — only real public hostnames.
    return frozenset(h for h in hosts if not _is_ip_or_local(h))


def _configured_store():
    root = os.environ.get("CRAWL4AI_ARTIFACT_ROOT")
    if not root:
        return None
    return LocalArtifactStore(root=root, subdir="crawl4ai", suffix=".md")


def _sanitize_source_url(url: str) -> str:
    """Scheme + hostname[:port] + path only — query/fragment (and any
    credentials, already rejected upstream) are never persisted."""
    parsed = urlparse(url)
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))


def _render_artifact(*, url: str, final_hostname: str, title: str, markdown: str) -> str:
    # Every header value is JSON-quoted -- a deterministic, unambiguous
    # encoding that escapes embedded newlines/quotes, so untrusted page
    # content (title) can never inject a new header line or a fake closing
    # "---" delimiter, regardless of what the crawled page contains.
    fields = {
        "source_url": _sanitize_source_url(url),
        "final_hostname": final_hostname,
        "title": title,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "crawl4ai_version": UPSTREAM_VERSION,
    }
    header_lines = "\n".join(f"{key}: {json.dumps(value)}" for key, value in fields.items())
    return f"---\n{header_lines}\n---\n\n{markdown}"


class Crawl4AIAdapter:
    name = "crawl4ai"

    # Capability-specific evidence fields — see core/external_execution_boundary.py
    # _UNIVERSAL_EVIDENCE_KEYS for the shared core (adapter_name, provider_status,
    # completed_at, result_ref, result_checksum, ...).
    evidence_extra_keys = frozenset({"final_hostname", "markdown_chars", "crawl4ai_version"})

    def __init__(self, *, allowed_hosts=None, store=None, page_timeout_ms: int = 30_000):
        self.allowed_hosts = (
            frozenset(h.lower() for h in allowed_hosts if not _is_ip_or_local(h.lower()))
            if allowed_hosts is not None
            else _allowed_hosts_from_env()
        )
        self.store = store if store is not None else _configured_store()
        self.page_timeout_ms = page_timeout_ms

    def submit(self, request: dict) -> SubmitResult:
        payload = request.get("payload") if isinstance(request, dict) else None
        try:
            url = self._validate_url(payload)
        except ValueError as exc:
            return SubmitResult("failed", failure_code=f"crawl4ai_{exc}"[:120])
        if self.store is None:
            return SubmitResult("failed", failure_code="crawl4ai_storage_unconfigured")

        try:
            final_hostname, markdown, title = asyncio.run(self._crawl(url))
        except ImportError:
            return SubmitResult("failed", failure_code="crawl4ai_not_installed")
        except _CrawlFailed as exc:
            return SubmitResult("failed", failure_code=str(exc)[:120])
        except Exception:
            # Anything past this point (browser launch failure, network
            # exception, asyncio error) is uncertain, not a known failure —
            # never presented as success.
            return SubmitResult("outcome_unknown", failure_code="crawl4ai_submit_exception")

        if final_hostname not in self.allowed_hosts:
            # Crawl4AI already followed the redirect before this check runs —
            # see the redirect-safety limitation in the architecture doc. The
            # result is rejected, never persisted, never reported as success.
            return SubmitResult("failed", failure_code="crawl4ai_redirect_not_allowlisted")

        bounded_markdown = markdown.encode("utf-8")[:_MAX_MARKDOWN_BYTES].decode("utf-8", "ignore")
        artifact_text = _render_artifact(url=url, final_hostname=final_hostname, title=title, markdown=bounded_markdown)
        contract_id = str(request.get("contract_id") or "")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
                tmp.write(artifact_text)
                tmp_path = Path(tmp.name)
            stored = self.store.put(
                path=tmp_path, identity=contract_id,
                metadata={"final_hostname": final_hostname}, mime_type="text/markdown",
            )
        except ArtifactStoreError as exc:
            status = "outcome_unknown" if exc.uncertain else "failed"
            return SubmitResult(status, failure_code=exc.code[:120])
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        return SubmitResult(
            "completed",
            result_ref=stored.result_ref,
            evidence={
                "adapter_name": self.name,
                "provider_status": "completed",
                "result_ref": stored.result_ref,
                "result_checksum": stored.sha256,
                "final_hostname": final_hostname,
                "markdown_chars": str(len(bounded_markdown)),
                "crawl4ai_version": UPSTREAM_VERSION,
            },
        )

    def poll(self, job) -> PollResult:
        # execution_mode is "sync" — submit() already returned a terminal
        # result and the boundary never schedules this job for polling.
        return PollResult("outcome_unknown", failure_code="crawl4ai_unexpected_poll")

    def _validate_url(self, payload) -> str:
        if not isinstance(payload, dict):
            raise ValueError("payload")
        url = payload.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError("url_missing")
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise ValueError("scheme_forbidden")
        if parsed.username or parsed.password:
            raise ValueError("credentials_in_url")
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ValueError("url_malformed")
        if _is_ip_or_local(hostname):
            raise ValueError("host_forbidden_pattern")
        if hostname not in self.allowed_hosts:
            raise ValueError("host_not_allowlisted")
        return url

    async def _crawl(self, url: str) -> tuple[str, str, str]:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        browser = BrowserConfig(headless=True, java_script_enabled=True)
        config = CrawlerRunConfig(
            word_count_threshold=10,
            page_timeout=self.page_timeout_ms,
            screenshot=False,
            pdf=False,
            check_robots_txt=True,
            verbose=False,
        )
        async with AsyncWebCrawler(config=browser) as crawler:
            result = await crawler.arun(url=url, config=config)
        if not result.success:
            raise _CrawlFailed(f"crawl4ai_crawl_failed:{(result.error_message or '')[:80]}")
        final_url = result.redirected_url or result.url or url
        final_hostname = (urlparse(final_url).hostname or "").lower()
        title = ""
        if isinstance(result.metadata, dict):
            title = str(result.metadata.get("title") or "")[:200]
        return final_hostname, str(result.markdown or ""), title
