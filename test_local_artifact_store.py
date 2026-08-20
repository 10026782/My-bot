"""LocalArtifactStore.put() mime_type pass-through — the one behavior this
module doesn't already get indirect coverage for via the Stirling/Crawl4AI
capability test suites."""

from __future__ import annotations

from core.local_artifact_store import LocalArtifactStore


def test_put_returns_passed_mime_type(tmp_path):
    src = tmp_path / "in.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    store = LocalArtifactStore(root=tmp_path / "store", subdir="x", suffix=".pdf")

    stored = store.put(path=src, identity="id1", metadata={}, mime_type="application/pdf")

    assert stored.mime_type == "application/pdf"


def test_put_defaults_mime_type_to_none(tmp_path):
    src = tmp_path / "in.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    store = LocalArtifactStore(root=tmp_path / "store", subdir="x", suffix=".pdf")

    stored = store.put(path=src, identity="id2", metadata={})

    assert stored.mime_type is None
