from unittest.mock import patch

from ad_attribution import _load_leads_with_timeframe
from tools.airtable_read_adapter import render_query


def test_ad_attribution_uses_provider_neutral_after_query():
    captured = {}

    def fake_get(table, query):
        captured.update(table=table, query=query)
        return []

    with patch("tools.airtable_tools.airtable_get", side_effect=fake_get):
        assert _load_leads_with_timeframe(7) == []

    assert captured["table"] == "Leads"
    assert render_query(captured["query"]) == "IS_AFTER({created_at}, '" + captured["query"].arguments[1] + "')"
