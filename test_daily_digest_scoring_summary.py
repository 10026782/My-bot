"""Focused tests for the daily lead-temperature summary."""

from unittest.mock import patch

import daily_digest
from airtable_schema import LeadFields


def _lead(score):
    return {"fields": {LeadFields.SCORE: score}}


def test_temperature_counts_use_canonical_score_bands():
    records = [_lead(100), _lead(70), _lead(50), _lead(49), _lead(25), _lead(24), _lead(0)]

    assert daily_digest._lead_temperature_counts(records) == (3, 2, 2)


def test_temperature_counts_treat_invalid_scores_as_cold():
    records = [_lead(None), _lead(""), _lead("invalid"), {"fields": {}}]

    assert daily_digest._lead_temperature_counts(records) == (0, 0, 4)


def test_summary_requests_all_leads_and_formats_counts():
    errors = []
    with patch.object(daily_digest, "_fetch", return_value=[_lead(80), _lead(55), _lead(30), _lead(10)]) as fetch:
        result = daily_digest._leads_scoring_summary(errors)

    fetch.assert_called_once_with("Leads", "", max_rec=0)
    assert result == '📊 *לידים:* 🔥 2 HOT | 🌤️ 1 WARM | ❄️ 1 COLD | סה"כ 4'
    assert errors == []


def test_summary_reports_fetch_errors():
    errors = []
    with patch.object(daily_digest, "_fetch", side_effect=RuntimeError("offline")):
        result = daily_digest._leads_scoring_summary(errors)

    assert result == "📊 *לידים:* שגיאה"
    assert errors == ["סיכום לידים: offline"]


def test_fetch_without_limit_follows_airtable_offsets(monkeypatch):
    class Response:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    responses = [
        Response({"records": [{"id": "one"}], "offset": "next-page"}),
        Response({"records": [{"id": "two"}]}),
    ]
    seen_params = []

    def fake_get(*_args, **kwargs):
        seen_params.append(dict(kwargs["params"]))
        return responses.pop(0)

    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    with patch("httpx.get", side_effect=fake_get):
        records = daily_digest._fetch("Leads", max_rec=0)

    assert records == [{"id": "one"}, {"id": "two"}]
    assert seen_params == [{}, {"offset": "next-page"}]
