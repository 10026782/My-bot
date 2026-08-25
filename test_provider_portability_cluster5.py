from tools import airtable_read_adapter


def test_provider_neutral_limit_translates_to_existing_record_cap(monkeypatch):
    captured = {}

    def fake_list(table, formula, max_records, **kwargs):
        captured.update(table=table, formula=formula, max_records=max_records, kwargs=kwargs)
        return []

    monkeypatch.setattr(airtable_read_adapter, "at_list_by_formula", fake_list)
    assert airtable_read_adapter.list_records("Leads", limit=37) == []
    assert captured["max_records"] == 37


def test_legacy_max_records_argument_remains_compatible(monkeypatch):
    captured = {}

    def fake_list(table, formula, max_records, **kwargs):
        captured["max_records"] = max_records
        return []

    monkeypatch.setattr(airtable_read_adapter, "at_list_by_formula", fake_list)
    assert airtable_read_adapter.list_records("Leads", max_records=12) == []
    assert captured["max_records"] == 12


if __name__ == "__main__":
    print("Provider Portability Cluster #5: focused tests require pytest")
