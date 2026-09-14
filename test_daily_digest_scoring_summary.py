"""Focused tests for the daily lead-temperature summary."""

from unittest.mock import patch

import daily_digest
from airtable_schema import LeadFields


def _lead(score):
    return {"fields": {LeadFields.SCORE: score}}


# ══════════════════════════════════════════════════════════════════
# PIPELINE-1 Blocker #3 — _tier_label() now delegates to score_display.py's
# canonical get_temperature() instead of a locally re-derived 25/50/70 scale.
# ══════════════════════════════════════════════════════════════════

def test_tier_label_delegates_to_canonical_score_display():
    import score_display
    for score in (0, 20, 21, 40, 41, 60, 61, 80, 81, 100):
        expected_emoji, expected_label, _ = score_display.get_temperature(score)
        assert daily_digest._tier_label(score) == f"{expected_emoji} {expected_label}"


def test_hot_leads_uses_canonical_hot_tier_cutoff():
    errors = []
    with patch.object(daily_digest, "_fetch", return_value=[]) as fetch:
        daily_digest._hot_leads(errors)

    formula = fetch.call_args.args[1]
    assert "60" in str(formula), "expected the Score>=60 canonical HOT cutoff in the fetch formula"
    assert errors == []


def test_temperature_counts_use_canonical_score_bands():
    # PIPELINE-1 Blocker #3: bands are now 20/60 (score_display.py's canonical
    # 20/40/60/80 scale), not the old locally re-derived 25/50 split.
    records = [_lead(100), _lead(70), _lead(60), _lead(59), _lead(20), _lead(19), _lead(0)]

    assert daily_digest._lead_temperature_counts(records) == (3, 2, 2)


def test_temperature_counts_treat_invalid_scores_as_cold():
    records = [_lead(None), _lead(""), _lead("invalid"), {"fields": {}}]

    assert daily_digest._lead_temperature_counts(records) == (0, 0, 4)


def test_summary_requests_all_leads_and_formats_counts():
    errors = []
    with patch.object(daily_digest, "_fetch", return_value=[_lead(80), _lead(55), _lead(30), _lead(10)]) as fetch:
        result = daily_digest._leads_scoring_summary(errors)

    fetch.assert_called_once_with("Leads", "", max_rec=0)
    # PIPELINE-1 Blocker #3: 80>=60 HOT, 55/30 in [20,60) WARM, 10<20 COLD.
    assert result == '📊 *לידים:* 🔥 1 HOT | 🌤️ 2 WARM | ❄️ 1 COLD | סה"כ 4'
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
def test_fetch_with_limit_ignores_offset_and_returns_first_page(monkeypatch):
    class Response:
        status_code = 200
        text = ""

        def json(self):
            return {"records": [{"id": "one"}], "offset": "next-page"}

    seen_params = []

    def fake_get(*_args, **kwargs):
        seen_params.append(dict(kwargs["params"]))
        return Response()

    monkeypatch.setenv("AIRTABLE_BASE_ID", "base")
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    with patch("httpx.get", side_effect=fake_get):
        records = daily_digest._fetch("Leads", max_rec=1)

    assert records == [{"id": "one"}]
    assert seen_params == [{"maxRecords": 1}]
