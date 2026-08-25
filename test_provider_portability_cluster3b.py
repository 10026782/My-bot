"""Focused guard for residual formula/query cleanup."""

from pathlib import Path


BUSINESS_FILES = (
    "daily_digest.py",
    "cmd_update.py",
    "core/memory_retrieval.py",
    "core/turn_coordinator_runtime.py",
    "lead_conversion.py",
    "weekly_summary.py",
    "cmd_decision.py",
)
FORMULA_TOKENS = (
    "SEARCH(", "FIND(", "ARRAYJOIN(", "RECORD_ID(",
    "IS_BEFORE(", "IS_AFTER(", "IS_SAME(", "DATEADD(",
    "CREATED_TIME(", "TODAY(",
)
QUERY_BUILDERS = (
    "equals", "contains", "array_contains", "record_id_equals",
    "before", "after", "all_of", "any_of", "negate",
)


def test_business_modules_contain_no_provider_formula_tokens():
    for filename in BUSINESS_FILES:
        source = Path(filename).read_text(encoding="utf-8")
        assert not any(token in source for token in FORMULA_TOKENS), filename


def test_business_modules_do_not_import_query_builders_from_adapter():
    for filename in BUSINESS_FILES:
        source = Path(filename).read_text(encoding="utf-8")
        assert not any(
            f"from tools.airtable_read_adapter import {builder}" in source
            for builder in QUERY_BUILDERS
        ), filename
