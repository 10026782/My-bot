"""Provider-neutral query intent regression checks for Cluster #3."""

from core.query_contract import after, all_of, any_of, array_contains, before, contains, equals, negate, record_id_equals
from tools.airtable_read_adapter import render_query


def test_query_intents_translate_without_changing_semantics():
    assert render_query(contains("Name", "O'Brien")) == "SEARCH('O\\'Brien', {Name})"
    assert render_query(contains("Name", "O'Brien", case_sensitive=True)) == "FIND('O\\'Brien', {Name})"
    assert render_query(contains("Name", "O'Brien", case_insensitive=True)) == (
        "FIND(LOWER('O\\'Brien'), LOWER({Name}))"
    )
    assert render_query(array_contains("keywords", "real_estate")) == (
        "FIND('real_estate', ARRAYJOIN({keywords}))"
    )
    assert render_query(record_id_equals("rec123")) == "RECORD_ID()='rec123'"


def test_query_composition_preserves_and_or_and_empty_behavior():
    open_clause = equals("Status", "open")
    done_clause = equals("Status", "done")
    assert render_query(all_of(open_clause, done_clause)) == "AND({Status}='open', {Status}='done')"
    assert render_query(any_of(open_clause, done_clause)) == "OR({Status}='open', {Status}='done')"
    assert render_query(negate(done_clause)) == "NOT({Status}='done')"
    assert render_query(all_of()) == ""
    assert render_query(any_of()) == ""


def test_date_and_case_insensitive_intents_are_provider_neutral():
    assert render_query(before("Due", "2026-08-25")) == "IS_BEFORE({Due}, '2026-08-25')"
    assert render_query(after("Due", "2026-08-01")) == "IS_AFTER({Due}, '2026-08-01')"
    assert render_query(equals("Name", "Dana", case_insensitive=True)) == "LOWER({Name})=LOWER('Dana')"


def test_lead_service_keeps_existing_search_contract():
    from core.lead_service import _search_formulas

    assert [render_query(query) for query in _search_formulas("Dana Levi", "0501234567")] == [
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
