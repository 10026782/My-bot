from __future__ import annotations

from tools import audit_public_renderer_contract as audit


def test_public_renderer_definition_is_detected():
    found = audit._renderer_definitions(
        "feature.py", "def render_feature(value):\n    return str(value)\n", {1}
    )
    assert found == [audit.Finding("feature.py", "public_renderer", "render_feature", 1)]


def test_contract_import_is_detected_outside_canonical_path():
    found = audit._contract_entries(
        "feature.py", "from core.message_contract import MessageContract\n", {1}
    )
    assert found == [audit.Finding("feature.py", "contract_import", "message_contract", 1)]


def test_canonical_paths_are_not_self_blocked():
    assert not audit._renderer_definitions(
        "core/agent_message_formatter.py", "def render_new_surface():\n    pass\n", {1}
    )
    assert not audit._contract_entries(
        "core/message_contract.py", "from core.message_contract import MessageContract\n", {1}
    )


def test_exact_registration_requires_owner_and_decision(tmp_path, monkeypatch):
    registry = tmp_path / "registry.md"
    registry.write_text(
        "| `feature.py` | `public_renderer` | `render_feature` | owner | `D-123` |\n"
        "| `feature.py` | `contract_import` | `message_contract` |  | `D-123` |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "REGISTRY", registry)
    assert audit.load_registrations() == {
        ("feature.py", "public_renderer", "render_feature"): ("owner", "D-123")
    }


def test_synthetic_new_surface_is_blocking(tmp_path, monkeypatch):
    source = tmp_path / "feature.py"
    source.write_text("def render_feature(value):\n    return value\n", encoding="utf-8")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "REGISTRY", tmp_path / "empty.md")
    monkeypatch.setattr(audit, "_added_lines", lambda: {"feature.py": {1, 2}})
    new, registered, _ = audit.audit()
    assert not registered
    assert [(item.kind, item.symbol) for item in new] == [("public_renderer", "render_feature")]


def test_guard_does_not_scan_its_own_source(tmp_path, monkeypatch):
    source = tmp_path / "tools"
    source.mkdir()
    self_file = source / "audit_public_renderer_contract.py"
    self_file.write_text(
        "# MessageContract and format_agent_message appear in guard implementation\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "REGISTRY", tmp_path / "empty.md")
    monkeypatch.setattr(
        audit, "_added_lines", lambda: {"tools/audit_public_renderer_contract.py": {1}}
    )
    new, registered, _ = audit.audit()
    assert not new
    assert not registered
