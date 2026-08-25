from unittest.mock import patch

from tools.airtable_read_adapter import list_records


def test_limit_wins_over_legacy_max_records():
    with patch("tools.airtable_read_adapter.at_list_by_formula", return_value=[]) as fetch:
        list_records("Leads", limit=5, max_records=20)
    assert fetch.call_args.args[2] == 5


def test_limit_preserves_multi_page_runtime_behavior():
    with patch("tools.airtable_read_adapter.at_list_by_formula", return_value=[]) as fetch:
        list_records("Tasks", limit=6, paginate=True)
    assert fetch.call_args.args[2] == 6
    assert fetch.call_args.kwargs["paginate"] is True


def test_legacy_max_records_remains_compatible():
    with patch("tools.airtable_read_adapter.at_list_by_formula", return_value=[]) as fetch:
        list_records("Leads", max_records=7)
    assert fetch.call_args.args[2] == 7
