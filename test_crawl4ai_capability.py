"""Crawl4AI capability POC: registry registration, adapter security boundary
(allowlist/scheme/redirect), artifact storage, and the generic boundary's
new sync-completion path. No network access — real crawl4ai calls are
avoided by monkeypatching Crawl4AIAdapter._crawl (an internal async method)
rather than the package itself; the "missing dependency" test relies on
crawl4ai genuinely not being installed in CI, exercising the real
ImportError path with no mocking at all."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from core.crawl4ai_adapter import Crawl4AIAdapter, _is_ip_or_local
from core.external_capability_contract import get_contract, resolve_adapter
from core.external_execution_boundary import ExternalExecutionBoundary
from core.local_artifact_store import LocalArtifactStore


ALLOWED = ("example.com",)


def _adapter(tmp_path, *, allowed_hosts=ALLOWED):
    return Crawl4AIAdapter(
        allowed_hosts=allowed_hosts,
        store=LocalArtifactStore(root=tmp_path, subdir="crawl4ai", suffix=".md"),
    )


async def _fake_crawl(final_hostname="example.com", markdown="# hi", title="Hi"):
    return final_hostname, markdown, title


# ── Registry registration (item 1, 2) ──────────────────────────────────

def test_crawl4ai_registered_atomically_as_second_capability():
    adapter = resolve_adapter("crawl4ai")
    assert isinstance(adapter, Crawl4AIAdapter)
    assert adapter.name == "crawl4ai"


def test_crawl4ai_contract_metadata():
    contract = get_contract("crawl4ai")
    assert contract is not None
    assert contract.capability_id == "crawl4ai"
    assert contract.adapter_name == "crawl4ai"
    assert contract.execution_mode == "sync"
    assert contract.version == "0.9.2"


# ── Missing dependency (item 4) — real ImportError, no mocking ─────────

def test_missing_dependency_is_deterministic_failure_not_a_crash(tmp_path):
    adapter = _adapter(tmp_path)
    result = adapter.submit({"contract_id": "c1", "payload": {"url": "https://example.com/page"}})
    assert result.status == "failed"
    assert result.failure_code == "crawl4ai_not_installed"


# ── URL / scheme / allowlist validation (items 5, 6, 7, 8, 9) ──────────

def test_url_not_in_allowlist_is_rejected_before_crawler_invocation(tmp_path):
    adapter = _adapter(tmp_path)
    adapter._crawl = lambda url: (_ for _ in ()).throw(AssertionError("crawler must not be invoked"))
    result = adapter.submit({"contract_id": "c1", "payload": {"url": "https://not-allowed.example.org/"}})
    assert result.status == "failed"
    assert result.failure_code == "crawl4ai_host_not_allowlisted"


@pytest.mark.parametrize("url", ["not a url", "https://", "https:///path"])
def test_malformed_url_is_rejected(tmp_path, url):
    adapter = _adapter(tmp_path)
    result = adapter.submit({"contract_id": "c1", "payload": {"url": url}})
    assert result.status == "failed"


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "javascript:alert(1)",
    "data:text/html,hi",
    "ftp://example.com/",
    "http://example.com/",
])
def test_forbidden_scheme_is_rejected(tmp_path, url):
    adapter = _adapter(tmp_path)
    result = adapter.submit({"contract_id": "c1", "payload": {"url": url}})
    assert result.status == "failed"
    assert result.failure_code == "crawl4ai_scheme_forbidden"


def test_credentials_in_url_are_rejected(tmp_path):
    adapter = _adapter(tmp_path)
    result = adapter.submit({"contract_id": "c1", "payload": {"url": "https://user:pass@example.com/"}})
    assert result.status == "failed"
    assert result.failure_code == "crawl4ai_credentials_in_url"


def test_exact_host_allowlist_permits_configured_host(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    monkeypatch.setattr(adapter, "_crawl", lambda url: _fake_crawl())
    result = adapter.submit({"contract_id": "c1", "payload": {"url": "https://example.com/page"}})
    assert result.status == "completed"


@pytest.mark.parametrize("lookalike", [
    "evil-example.com",
    "example.com.evil.com",
    "notexample.com",
    "sub.example.com",
])
def test_lookalike_hostname_is_rejected(tmp_path, lookalike):
    adapter = _adapter(tmp_path)
    adapter._crawl = lambda url: (_ for _ in ()).throw(AssertionError("crawler must not be invoked"))
    result = adapter.submit({"contract_id": "c1", "payload": {"url": f"https://{lookalike}/"}})
    assert result.status == "failed"
    assert result.failure_code == "crawl4ai_host_not_allowlisted"


@pytest.mark.parametrize("hostname", ["127.0.0.1", "0.0.0.0", "169.254.169.254", "localhost", "::1"])
def test_ip_literal_and_loopback_hosts_can_never_be_allowlisted(hostname):
    assert _is_ip_or_local(hostname) is True


def test_ip_literal_in_allowed_hosts_argument_is_dropped_defensively(tmp_path):
    adapter = Crawl4AIAdapter(allowed_hosts=("example.com", "127.0.0.1"), store=LocalArtifactStore(root=tmp_path, subdir="c", suffix=".md"))
    assert adapter.allowed_hosts == frozenset({"example.com"})


# ── Redirect safety ──────────────────────────────────────────────────

def test_redirect_to_non_allowlisted_host_is_rejected(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    monkeypatch.setattr(adapter, "_crawl", lambda url: _fake_crawl(final_hostname="attacker.example.org"))
    result = adapter.submit({"contract_id": "c1", "payload": {"url": "https://example.com/"}})
    assert result.status == "failed"
    assert result.failure_code == "crawl4ai_redirect_not_allowlisted"


# ── Successful crawl / artifact / evidence (items 10, 12, 13, 14, 15) ──

def test_successful_crawl_produces_markdown_artifact_with_checksum(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    monkeypatch.setattr(adapter, "_crawl", lambda url: _fake_crawl(markdown="# Hello\nworld", title="Hello"))
    result = adapter.submit({"contract_id": "job-1", "payload": {"url": "https://example.com/"}})
    assert result.status == "completed"
    artifact = tmp_path / "crawl4ai" / "job-1.md"
    assert artifact.is_file()
    text = artifact.read_text(encoding="utf-8")
    assert "# Hello" in text and "world" in text
    assert result.evidence["result_checksum"]
    assert result.evidence["result_checksum"] == hashlib.sha256(artifact.read_bytes()).hexdigest()


def test_evidence_is_bounded_to_declared_keys(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    monkeypatch.setattr(adapter, "_crawl", lambda url: _fake_crawl())
    result = adapter.submit({"contract_id": "job-2", "payload": {"url": "https://example.com/"}})
    expected = {
        "adapter_name", "provider_status", "result_ref", "result_checksum",
        "final_hostname", "markdown_chars", "crawl4ai_version",
    }
    assert set(result.evidence) == expected


def test_caller_cannot_inject_arbitrary_evidence_keys(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    monkeypatch.setattr(adapter, "_crawl", lambda url: _fake_crawl())
    result = adapter.submit({
        "contract_id": "job-3",
        "payload": {"url": "https://example.com/", "evidence": {"injected": "x"}, "storage_provider": "s3"},
    })
    assert "injected" not in result.evidence
    assert "storage_provider" not in result.evidence


def test_caller_cannot_choose_output_path(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    monkeypatch.setattr(adapter, "_crawl", lambda url: _fake_crawl())
    result = adapter.submit({
        "contract_id": "job-4",
        "payload": {"url": "https://example.com/", "result_ref": "/etc/passwd", "path": "/etc/passwd"},
    })
    assert result.status == "completed"
    assert result.result_ref == str((tmp_path / "crawl4ai" / "job-4.md").resolve())


def test_artifact_path_cannot_escape_configured_root(tmp_path):
    store = LocalArtifactStore(root=tmp_path, subdir="crawl4ai", suffix=".md")
    src = tmp_path / "src.md"
    src.write_text("x", encoding="utf-8")
    stored = store.put(path=src, identity="../../etc/passwd", metadata={})
    resolved = Path(stored.result_ref).resolve()
    assert str(resolved).startswith(str((tmp_path / "crawl4ai").resolve()))


# ── Failure semantics (items 16, 17) ────────────────────────────────────

def test_crawl4ai_reported_failure_is_failed_not_completed(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)

    async def _raise(url):
        from core.crawl4ai_adapter import _CrawlFailed
        raise _CrawlFailed("crawl4ai_crawl_failed:timeout")

    monkeypatch.setattr(adapter, "_crawl", _raise)
    result = adapter.submit({"contract_id": "c1", "payload": {"url": "https://example.com/"}})
    assert result.status == "failed"


def test_unexpected_adapter_exception_is_outcome_unknown_never_success(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)

    async def _boom(url):
        raise RuntimeError("browser launch exploded")

    monkeypatch.setattr(adapter, "_crawl", _boom)
    result = adapter.submit({"contract_id": "c1", "payload": {"url": "https://example.com/"}})
    assert result.status == "outcome_unknown"


def test_storage_missing_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("CRAWL4AI_ARTIFACT_ROOT", raising=False)
    adapter = Crawl4AIAdapter(allowed_hosts=ALLOWED)
    monkeypatch.setattr(adapter, "_crawl", lambda url: _fake_crawl())
    result = adapter.submit({"contract_id": "c1", "payload": {"url": "https://example.com/"}})
    assert result.status == "failed"
    assert result.failure_code == "crawl4ai_storage_unconfigured"


# ── Generic boundary sync-completion path (items 18, 19, 20) ───────────

class FakeRepo:
    def __init__(self):
        self.jobs = {}
        self.submitted_scans = 0

    def get(self, contract_id):
        job = self.jobs.get(contract_id)
        return replace(job) if job else None

    def create(self, job):
        self.jobs[job.contract_id] = replace(job)

    def update(self, job):
        self.jobs[job.contract_id] = replace(job)

    def list_for_adapter(self, adapter_name):
        return [j for j in self.jobs.values() if j.adapter_name == adapter_name]

    def due_submitted(self, interval_seconds=300):
        self.submitted_scans += 1
        return [j for j in self.jobs.values() if j.status == "submitted"]


def test_sync_completed_result_persists_full_terminal_state(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    monkeypatch.setattr(adapter, "_crawl", lambda url: _fake_crawl(markdown="# X"))
    repo = FakeRepo()
    boundary = ExternalExecutionBoundary(repository=repo, adapter=adapter)

    outcome = boundary.submit(contract_id="job-5", idempotency_key="k1", payload={"url": "https://example.com/"})
    assert outcome.result == "completed"
    job = repo.jobs["job-5"]
    assert job.status == "completed"
    assert job.completed_at is not None
    assert job.result_ref
    assert job.evidence["provider_status"] == "completed"


def test_completed_sync_job_is_never_due_for_polling(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    monkeypatch.setattr(adapter, "_crawl", lambda url: _fake_crawl())
    repo = FakeRepo()
    boundary = ExternalExecutionBoundary(repository=repo, adapter=adapter)
    boundary.submit(contract_id="job-6", idempotency_key="k1", payload={"url": "https://example.com/"})
    assert repo.due_submitted() == []


def test_duplicate_submit_with_same_contract_id_does_not_crawl_twice(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    calls = []

    async def _counted(url):
        calls.append(url)
        return await _fake_crawl()

    monkeypatch.setattr(adapter, "_crawl", _counted)
    repo = FakeRepo()
    boundary = ExternalExecutionBoundary(repository=repo, adapter=adapter)
    first = boundary.submit(contract_id="job-7", idempotency_key="k1", payload={"url": "https://example.com/"})
    second = boundary.submit(contract_id="job-7", idempotency_key="k1", payload={"url": "https://example.com/"})
    assert first.result == "completed" and second.result == "completed"
    assert len(calls) == 1


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
