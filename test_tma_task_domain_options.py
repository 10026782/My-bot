from tma_api import _normalize_task_domain


def test_normalize_task_domain_returns_exact_tasks_options():
    cases = {
        "Real Estate": "Real Estate",
        "real_estate": "Real Estate",
        "Income Properties": "Income Properties",
        "income_properties": "Income Properties",
        "Recruitment": "Recruitment",
        "recruiting": "Recruitment",
        "Import": "Import",
        "imports": "Import",
        "Saas": "Saas",
        "SaaS": "Saas",
        "saas": "Saas",
        "  SaaS   ": "Saas",
    }

    for raw, expected in cases.items():
        assert _normalize_task_domain(raw) == expected


def test_normalize_task_domain_preserves_unknown_values():
    assert _normalize_task_domain("Other Domain") == "Other Domain"
    assert _normalize_task_domain("") == ""
