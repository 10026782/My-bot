"""Provider-neutral query intent regression checks for Cluster #3."""

from tools.airtable_read_adapter import (
    after,
    all_of,
    any_of,
    array_contains,
    before,
    contains,
    equals,
    equals_ci,
    negate,
    record_id_equals,
)


def test_query_intents_translate_without_changing_semantics():
    assert contains("Name", "O'Brien") == "SEARCH('O\\'Brien', {Name})"
    assert contains("Name", "O'Brien", case_sensitive=True) == "FIND('O\\'Brien', {Name})"
    assert contains("Name", "O'Brien", case_insensitive=True) == (
        "FIND(LOWER('O\\'Brien'), LOWER({Name}))"
    )
    assert array_contains("keywords", "real_estate") == (
        "FIND('real_estate', ARRAYJOIN({keywords}))"
    )
    assert record_id_equals("rec123") == "RECORD_ID()='rec123'"


def test_query_composition_preserves_and_or_and_empty_behavior():
    open_clause = equals("Status", "open")
    done_clause = equals("Status", "done")
    assert all_of(open_clause, done_clause) == "AND({Status}='open', {Status}='done')"
    assert any_of(open_clause, done_clause) == "OR({Status}='open', {Status}='done')"
    assert negate(done_clause) == "NOT({Status}='done')"
    assert all_of() == ""
    assert any_of() == ""


def test_date_and_case_insensitive_intents_are_provider_neutral():
    assert before("Due", "2026-08-25") == "IS_BEFORE({Due}, '2026-08-25')"
    assert after("Due", "2026-08-01") == "IS_AFTER({Due}, '2026-08-01')"
    assert equals_ci("Name", "Dana") == "LOWER({Name})=LOWER('Dana')"


def test_lead_service_keeps_existing_search_contract():
    from core.lead_service import _search_formulas

    assert _search_formulas("Dana Levi", "0501234567") == [
        "AND(SEARCH('Dana Levi', {Name}), {phone}='0501234567')",
        "{phone}='0501234567'",
        "SEARCH('Dana Levi', {Name})",
    ]


if __name__ == "__main__":
    test_query_intents_translate_without_changing_semantics()
    test_query_composition_preserves_and_or_and_empty_behavior()
    test_date_and_case_insensitive_intents_are_provider_neutral()
    test_lead_service_keeps_existing_search_contract()
    print("Provider Portability Cluster #3: 4 passed")
