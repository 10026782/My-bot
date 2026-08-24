"""Focused PR-A1 guard tests."""

from tools.audit_provider_boundary import (
    ImportFingerprint,
    classify,
    scan_text,
)


def test_known_legacy_import_is_detected_with_stable_fingerprint():
    findings = scan_text(
        "core/lead_buffer.py",
        "from tools.airtable_tools import airtable_get\n",
    )
    groups = classify(findings)
    assert groups["legacy"] == [
        ImportFingerprint("core/lead_buffer.py", "tools.airtable_tools", "airtable_get", "from")
    ]
    assert not groups["new"]


def test_legacy_crm_import_is_baselined_without_being_approved():
    findings = scan_text(
        "core/lead_recovery.py",
        "from crm import crm_list_deals\n",
    )
    groups = classify(findings)
    assert len(groups["legacy"]) == 1
    assert not groups["new"]


def test_approved_boundary_module_is_not_a_false_positive():
    assert not scan_text(
        "core/runtime_schema_provider.py",
        "from tools.airtable_tools import airtable_get_records\n",
    )


def test_new_import_is_blocking_delta():
    finding = ImportFingerprint(
        "core/new_feature.py", "tools.airtable_tools", "airtable_get", "from"
    )
    groups = classify([finding])
    assert groups["new"] == [finding]
    assert groups["legacy"] == []


def test_import_statement_and_nested_imports_are_ast_detected():
    findings = scan_text(
        "core/new_feature.py",
        """
import tools.google_tools
def load():
    from tools.calendar_tools import calendar_get_events
""",
    )
    assert [item.as_text() for item in findings] == [
        "core/new_feature.py|from|tools.calendar_tools|calendar_get_events",
        "core/new_feature.py|import|tools.google_tools|*",
    ]


if __name__ == "__main__":
    test_known_legacy_import_is_detected_with_stable_fingerprint()
    test_legacy_crm_import_is_baselined_without_being_approved()
    test_approved_boundary_module_is_not_a_false_positive()
    test_new_import_is_blocking_delta()
    test_import_statement_and_nested_imports_are_ast_detected()
    print("test_audit_provider_boundary: 5/5 passed")
