"""Focused checks for the read-only schema presentation boundary."""

from pathlib import Path

import schema_intelligence as si


def test_schema_presentation_is_read_only() -> None:
    table = si.handle_schema_command("tasks")
    tables = si.handle_schema_command("")

    assert "משימות (Tasks)" in table
    assert "Roadmap_Tasks" in tables
    assert si.READ_ONLY_NOTICE in table
    assert si.READ_ONLY_NOTICE in tables


def test_duplicate_write_validation_is_gone() -> None:
    assert not hasattr(si, "validate_before_write")
    assert not hasattr(si, "validate_fields")
    assert not hasattr(si, "_find_similar")


def test_write_path_still_uses_schema_validator() -> None:
    gateway = Path("tools/airtable_gateway.py").read_text(encoding="utf-8")
    assert "import schema_validator as _sv" in gateway
    assert "_sv.validate_fields(table, clean)" in gateway


if __name__ == "__main__":
    tests = [
        test_schema_presentation_is_read_only,
        test_duplicate_write_validation_is_gone,
        test_write_path_still_uses_schema_validator,
    ]
    for test in tests:
        test()
        print(f"✅ {test.__name__}")
    print(f"{len(tests)} passed, 0 failed")
