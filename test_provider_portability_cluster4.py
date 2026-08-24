from pathlib import Path


BUSINESS_FILES = (
    Path("daily_digest.py"),
    Path("cmd_update.py"),
    Path("core/lead_candidate_handler.py"),
)


def test_business_scope_has_no_provider_field_type_names():
    source = "\n".join(path.read_text() for path in BUSINESS_FILES)
    assert "singleSelect" not in source
    assert "multipleSelects" not in source


if __name__ == "__main__":
    test_business_scope_has_no_provider_field_type_names()
    print("Provider Portability Cluster #4: PASS")
