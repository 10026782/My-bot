from __future__ import annotations

from pathlib import Path

from tools import audit_writer_authority_registration as audit


def test_existing_implementation_is_not_a_delta():
    assert audit.scan_source("core/local_artifact_store.py", "class LocalArtifactStore:\n    pass\n")


def test_new_writer_shape_is_detected_on_added_definition():
    finding = audit.Finding("feature.py", "FeatureWriter", 4, "class")
    assert finding.key == ("feature.py", "FeatureWriter")
    assert audit.scan_source("feature.py", "x = 1\n\n\nclass FeatureWriter:\n    pass\n") == [finding]


def test_synthetic_unregistered_delta_is_blocking(tmp_path, monkeypatch):
    source = tmp_path / "feature_writer.py"
    source.write_text("class FeatureWriter:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "REGISTRY", tmp_path / "empty_registry.md")
    monkeypatch.setattr(audit, "_added_line_ranges", lambda: {"feature_writer.py": {1, 2}})
    new, registered, _ = audit.audit()
    assert not registered
    assert [(item.path, item.symbol) for item in new] == [
        ("feature_writer.py", "<module>"),
        ("feature_writer.py", "FeatureWriter"),
    ]


def test_harmless_refactor_of_existing_writer_is_not_a_new_delta(tmp_path, monkeypatch):
    source = tmp_path / "legacy_store.py"
    source.write_text(
        '"""Existing implementation after harmless line movement."""\n\n'
        "class LegacyStore:\n    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "REGISTRY", tmp_path / "empty_registry.md")
    monkeypatch.setattr(audit, "_added_line_ranges", lambda: {"legacy_store.py": {1, 2, 3, 4}})
    monkeypatch.setattr(
        audit,
        "_baseline_findings",
        lambda path: {("legacy_store.py", "<module>"), ("legacy_store.py", "LegacyStore")},
    )
    new, registered, _ = audit.audit()
    assert not new
    assert not registered


def test_exact_registration_requires_owner_and_decision(tmp_path, monkeypatch):
    registry = tmp_path / "registry.md"
    registry.write_text(
        "| `feature.py` | `FeatureWriter` | core owner | `ADR-42` |\n"
        "| `feature.py` | `MissingOwner` |  | `ADR-42` |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "REGISTRY", registry)
    registrations = audit.load_registrations()
    assert registrations == {("feature.py", "FeatureWriter"): ("core owner", "ADR-42")}


def test_no_runtime_or_registry_write_side_effects():
    assert Path(audit.REGISTRY).name == "WRITER_AUTHORITY_REGISTRY.md"
