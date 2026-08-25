from pathlib import Path

from core.query_contract import Query, equals, negate
from tools.airtable_read_adapter import render_query


def test_data_engine_queries_are_provider_neutral_and_render_unchanged():
    assert render_query(equals("tier", "HOT")) == "{tier}='HOT'"
    assert render_query(equals("tier", "WARM")) == "{tier}='WARM'"
    assert render_query(equals("Status", "Active")) == "{Status}='Active'"
    assert render_query(equals("Status", "Overdue")) == "{Status}='Overdue'"
    assert render_query(negate(equals("campaign_source", ""))) == "NOT({campaign_source}='')"


def test_data_engines_pass_query_intents_to_legacy_facade(monkeypatch):
    import data_engines
    import tools.airtable_tools as legacy

    calls = []
    monkeypatch.setattr(
        legacy,
        "airtable_get",
        lambda table, query: calls.append((table, query)) or "••",
    )
    data_engines._basic_kpi()
    assert len(calls) == 4
    assert all(isinstance(query, Query) for _, query in calls)
    assert [render_query(query) for _, query in calls] == [
        "{tier}='HOT'",
        "{tier}='WARM'",
        "{Status}='Active'",
        "{Status}='Overdue'",
    ]


def test_residual_business_files_have_no_provider_query_shapes():
    for filename in ("core/lead_event_writer.py", "data_engines.py", "core/emergency_window.py"):
        source = Path(filename).read_text(encoding="utf-8")
        assert 'record["id"]' not in source
        assert 'record["fields"]' not in source
        assert 'max_records=' not in source
        assert "SEARCH(" not in source
        assert "FIND(" not in source
        assert "ARRAYJOIN(" not in source
        assert "IS_BEFORE(" not in source
        assert "IS_AFTER(" not in source


def test_lead_event_writer_uses_relation_payload_and_record_id_helpers():
    source = Path("core/lead_event_writer.py").read_text(encoding="utf-8")
    assert "relation_payload(lead_id)" in source
    assert "record_id(rec)" in source
