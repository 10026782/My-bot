"""
Regression tests for BUG-DRIVE-READ-UNSUPPORTED-CONVERSION + BUG-SHEETS-SEARCH-STATUS.
Scope: tools/google_tools.py only.
Run: python3 test_drive_sheets_fixes.py
"""
from unittest.mock import patch, MagicMock


def _mock_token(monkeypatch_target="tools.google_tools.get_google_token"):
    """Returns a patcher that makes get_google_token return a fake token."""
    return patch(monkeypatch_target, return_value="fake-token")


def test_drive_read_file_spreadsheet_returns_sheet_message():
    """
    drive_read_file must return the Sheet-routing message immediately when
    the matched file's mimeType is application/vnd.google-apps.spreadsheet —
    no export call should be attempted (Google returns HTTP 400 for that).
    """
    from tools.google_tools import drive_read_file

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {"files": [{
        "id": "sheet-id-123",
        "name": "Budget 2026",
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }]}

    with _mock_token(), patch("httpx.get", return_value=search_resp) as mock_get:
        result = drive_read_file("Budget 2026")

    assert result == "📊 זה Google Sheet — יש להשתמש בכלי Sheets, לא בקריאת Drive.", (
        f"Expected Sheet routing message, got: {result!r}"
    )
    # export endpoint must NOT have been called (would return HTTP 400)
    for call in mock_get.call_args_list:
        url = call.args[0] if call.args else call.kwargs.get("url", "")
        assert "/export" not in str(url), "export endpoint was called for a Spreadsheet — should not be"

    print("✅ test_drive_read_file_spreadsheet_returns_sheet_message")


def test_drive_read_file_export_400_returns_error():
    """
    drive_read_file must return a controlled error when the Google export
    endpoint returns HTTP 400 (non-Sheets google-apps type, e.g. Slides).
    """
    from tools.google_tools import drive_read_file

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {"files": [{
        "id": "slides-id-456",
        "name": "Pitch Deck",
        "mimeType": "application/vnd.google-apps.presentation",
    }]}

    export_resp = MagicMock()
    export_resp.status_code = 400
    export_resp.text = "Export not supported"

    def _fake_get(url, **kwargs):
        if "/export" in url:
            return export_resp
        return search_resp

    with _mock_token(), patch("httpx.get", side_effect=_fake_get):
        result = drive_read_file("Pitch Deck")

    assert "400" in result or "שגיאה" in result or "❌" in result, (
        f"Expected a controlled error containing status / error indicator, got: {result!r}"
    )
    print("✅ test_drive_read_file_export_400_returns_error")


def test_sheets_append_search_non_200_returns_error_no_json_parse():
    """
    sheets_append must return a controlled error (not crash on .json() parse
    of an error body) when the Drive search for the spreadsheet returns non-200.
    """
    from tools.google_tools import sheets_append

    search_resp = MagicMock()
    search_resp.status_code = 403
    search_resp.text = "Forbidden: insufficient permissions"
    # Make .json() raise to confirm it is never called on a non-200 response
    search_resp.json.side_effect = Exception("json() must not be called on non-200 response")

    with _mock_token(), patch("httpx.get", return_value=search_resp):
        result = sheets_append("My Sheet", ["col1", "col2"])

    assert "403" in result and "❌" in result, (
        f"Expected error mentioning HTTP 403, got: {result!r}"
    )
    print("✅ test_sheets_append_search_non_200_returns_error_no_json_parse")


if __name__ == "__main__":
    passed = failed = 0
    tests = [
        test_drive_read_file_spreadsheet_returns_sheet_message,
        test_drive_read_file_export_400_returns_error,
        test_sheets_append_search_non_200_returns_error_no_json_parse,
    ]
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1

    print(f"\n{'='*45}")
    print(f"  {passed}/{passed+failed} passed")
    import sys; sys.exit(0 if failed == 0 else 1)
