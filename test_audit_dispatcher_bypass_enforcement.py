"""PR-A3 no-new-dispatcher-bypass enforcement tests."""

import tools.audit_dispatcher_bypass as audit


def test_legacy_finding_is_non_blocking():
    finding = next(iter(audit.BASELINE))
    assert audit.classify([finding])["new"] == []
    assert len(audit.classify([finding])["legacy"]) == 1


def test_sanctioned_finding_is_not_new():
    finding = next(iter(audit._SANCTIONED_CALL_SITES))
    groups = audit.classify([finding])
    assert groups["sanctioned"] == [finding]
    assert groups["new"] == []


def test_f14_contact_update_is_sanctioned_but_another_import_is_new():
    update = ("tools/approval_actions.py", 395, "crm")
    unrelated = ("tools/approval_actions.py", 396, "crm")
    groups = audit.classify([update, unrelated])
    assert groups["sanctioned"] == [update]
    assert groups["new"] == [unrelated]


def test_cross_track_finding_is_visible_but_non_blocking():
    finding = next(iter(audit.CROSS_TRACK))
    groups = audit.classify([finding])
    assert groups["cross_track"] == [finding]
    assert groups["new"] == []


def test_stable_identity_handles_shifted_cross_track_import():
    finding = ("core/runtime_schema_provider.py", 204, "tools.airtable_tools")
    groups = audit.classify([finding])
    assert groups["cross_track"] == [finding]
    assert groups["new"] == []


def test_accepted_staging_finding_is_visible_but_non_blocking():
    finding = next(iter(audit.ACCEPTED))
    groups = audit.classify([finding])
    assert groups["accepted"] == [finding]
    assert groups["new"] == []


def test_standalone_commercial_crm_helper_import_is_explicitly_accepted():
    finding = ("commercial_crm.py", 37, "tools.airtable_tools")
    groups = audit.classify([finding])
    assert groups["accepted"] == [finding]
    assert groups["new"] == []


def test_synthetic_new_bypass_is_blocking():
    finding = ("new_feature.py", 1, "tools.airtable_tools")
    assert audit.classify([finding])["new"] == [finding]


def test_synthetic_tracked_bypass_makes_main_fail(tmp_path, monkeypatch):
    (tmp_path / "new_feature.py").write_text(
        "from tools.airtable_tools import airtable_get\n"
    )
    monkeypatch.setattr(audit, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        audit, "_iter_py_files", lambda: [tmp_path / "new_feature.py"]
    )
    assert audit.main() == 1


def test_stable_identity_handles_shifted_legacy_import():
    finding = ("lead_capture.py", 132, "tools.airtable_tools")
    groups = audit.classify([finding])
    assert groups["legacy"] == [finding]
    assert groups["new"] == []


def test_stable_identity_handles_shifted_interaction_imports():
    findings = [
        ("interaction_engine.py", 339, "tools.airtable_tools"),
        ("interaction_engine.py", 626, "tools.calendar_tools"),
    ]
    groups = audit.classify(findings)
    assert groups["legacy"] == findings
    assert groups["new"] == []


def test_direct_contact_create_and_update_are_blocking(tmp_path, monkeypatch):
    source = tmp_path / "new_contact_writer.py"
    source.write_text(
        "from tools.airtable_gateway import airtable_create, airtable_patch\n"
        "def create(): airtable_create(\"Contacts\", {})\n"
        "def update(): airtable_patch(\"Contacts\", \"rec1\", {})\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "_iter_py_files", lambda: [source.relative_to(tmp_path)])
    assert {item[2] for item in audit.scan_contact_bypasses()} == {"airtable_create", "airtable_patch"}


def test_generic_provider_contact_write_is_blocking_but_non_contact_is_allowed(tmp_path, monkeypatch):
    source = tmp_path / "provider_writer.py"
    source.write_text(
        "storage.update(\"Contacts\", \"rec1\", {})\n"
        "storage.update(\"Tasks\", \"rec2\", {})\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "_iter_py_files", lambda: [source.relative_to(tmp_path)])
    assert audit.scan_contact_bypasses() == [("provider_writer.py", 1, "update")]


def test_contact_boundaries_and_non_contact_writes_are_allowed(tmp_path, monkeypatch):
    source = tmp_path / "crm.py"
    source.write_text(
        "from airtable_schema import Tables\n"
        "from tools.airtable_gateway import airtable_create, airtable_patch\n"
        "def create_contact_from_fields(): airtable_create(Tables.CONTACTS, {})\n"
        "def update_contact(): airtable_patch(\"Contacts\", \"rec1\", {})\n"
        "def other(): airtable_create(\"Tasks\", {})\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "_iter_py_files", lambda: [source.relative_to(tmp_path)])
    assert audit.scan_contact_bypasses() == []


def test_stable_identity_handles_shifted_cmd_update_import():
    finding = ("cmd_update.py", 726, "tools.airtable_tools")
    groups = audit.classify([finding])
    assert groups["legacy"] == [finding]
    assert groups["new"] == []


def test_stable_identity_does_not_hide_a_second_same_import(tmp_path, monkeypatch):
    source = tmp_path / "feature.py"
    source.write_text(
        "from tools.airtable_tools import airtable_get\n"
        "from tools.airtable_tools import airtable_get\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        audit, "BASELINE", frozenset({("feature.py", 1, "tools.airtable_tools")})
    )
    original = ("feature.py", 1, "tools.airtable_tools")
    added_duplicate = ("feature.py", 2, "tools.airtable_tools")
    groups = audit.classify([original, added_duplicate])
    assert groups["legacy"] == [original]
    assert groups["new"] == [added_duplicate]
