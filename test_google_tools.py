"""
Regression tests for drive_read_file()'s document_converter fallback path
(else branch: non-google-apps files downloaded via alt=media).
Scope: tools/google_tools.py only.
Run: python3 test_google_tools.py
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import docx as _python_docx


def _mock_token(monkeypatch_target="tools.google_tools.get_google_token"):
    """Returns a patcher that makes get_google_token return a fake token."""
    return patch(monkeypatch_target, return_value="fake-token")


def _search_and_media_mock(file_id, name, mime_type, content_bytes):
    """Builds the (search_resp, media_resp) pair drive_read_file expects for
    a single-match, non-google-apps file."""
    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {"files": [{
        "id": file_id, "name": name, "mimeType": mime_type,
        "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
    }]}

    media_resp = MagicMock()
    media_resp.status_code = 200
    media_resp.content = content_bytes

    def _fake_get(url, **kwargs):
        if "/files/" in url and kwargs.get("params", {}).get("alt") == "media":
            return media_resp
        return search_resp

    return _fake_get


def _real_docx_bytes(paragraph_text: str) -> bytes:
    """Real, valid .docx bytes via python-docx — an actual conversion runs,
    not a mocked-away one."""
    doc = _python_docx.Document()
    doc.add_paragraph(paragraph_text)
    fd, path = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    try:
        doc.save(path)
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)


def test_read_docx_returns_converted_markdown():
    from tools.google_tools import drive_read_file

    docx_bytes = _real_docx_bytes("Hello from a real docx paragraph.")
    fake_get = _search_and_media_mock(
        "docx-id-1", "Brief.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx_bytes,
    )

    with _mock_token(), patch("httpx.get", side_effect=fake_get):
        result = drive_read_file("Brief.docx")

    assert "Hello from a real docx paragraph." in result, (
        f"Expected converted markdown content in result, got: {result!r}"
    )
    assert "Brief.docx" in result
    print("✅ test_read_docx_returns_converted_markdown")


def test_read_pdf_returns_unsupported_message():
    from tools.google_tools import drive_read_file

    fake_get = _search_and_media_mock(
        "pdf-id-1", "Contract.pdf", "application/pdf", b"%PDF-1.4 fake bytes",
    )

    with _mock_token(), patch("httpx.get", side_effect=fake_get):
        result = drive_read_file("Contract.pdf")

    assert "פורמט לא נתמך" in result, f"Expected unsupported-format message, got: {result!r}"
    assert "drive.google.com" in result, "Expected webViewLink fallback in the message"
    print("✅ test_read_pdf_returns_unsupported_message")


def test_read_google_native_doc_unchanged():
    """The google-apps export branch is untouched by the else-branch fix —
    must still return the raw exported text as before."""
    from tools.google_tools import drive_read_file

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {"files": [{
        "id": "gdoc-id-1", "name": "Meeting Notes", "mimeType": "application/vnd.google-apps.document",
    }]}
    export_resp = MagicMock()
    export_resp.status_code = 200
    export_resp.text = "Plain exported text from Google Docs."

    def _fake_get(url, **kwargs):
        if "/export" in url:
            return export_resp
        return search_resp

    with _mock_token(), patch("httpx.get", side_effect=_fake_get):
        result = drive_read_file("Meeting Notes")

    assert "Plain exported text from Google Docs." in result
    assert result == "📄 תוכן 'Meeting Notes':\nPlain exported text from Google Docs."
    print("✅ test_read_google_native_doc_unchanged")


def test_low_confidence_falls_back_to_raw():
    """csv -> markdown is not a supported document_converter pair (only
    csv<->xlsx is) — confidence must come back "low" and the code must fall
    back to the raw downloaded bytes instead of crashing or losing content."""
    from tools.google_tools import drive_read_file

    csv_bytes = b"name,phone\nMoshe,0501234567\n"
    fake_get = _search_and_media_mock("csv-id-1", "contacts.csv", "text/csv", csv_bytes)

    with _mock_token(), patch("httpx.get", side_effect=fake_get):
        result = drive_read_file("contacts.csv")

    assert "Moshe,0501234567" in result, f"Expected raw CSV fallback content, got: {result!r}"
    print("✅ test_low_confidence_falls_back_to_raw")


def test_output_file_cleaned_up_after_read():
    """The engine does not delete output_file on success (confirmed via
    document_converter/engine.py) — drive_read_file must clean it up itself."""
    from tools.google_tools import drive_read_file

    fd, real_output_path = tempfile.mkstemp(suffix=".md")
    os.close(fd)
    with open(real_output_path, "w", encoding="utf-8") as f:
        f.write("# converted content\n")

    fake_convert_result = {
        "status": "success", "confidence": "high",
        "warnings": [], "output_file": real_output_path,
    }
    docx_bytes = _real_docx_bytes("irrelevant — convert_document is mocked")
    fake_get = _search_and_media_mock(
        "docx-id-2", "Report.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx_bytes,
    )

    assert os.path.exists(real_output_path), "test setup: output file should exist before the call"

    with _mock_token(), patch("httpx.get", side_effect=fake_get), \
         patch("document_converter.engine.convert_document", return_value=fake_convert_result):
        result = drive_read_file("Report.docx")

    assert "converted content" in result
    assert not os.path.exists(real_output_path), (
        "output_file must be deleted by drive_read_file after reading it — "
        "engine.py does not clean it up on success"
    )
    print("✅ test_output_file_cleaned_up_after_read")


if __name__ == "__main__":
    passed = failed = 0
    tests = [
        test_read_docx_returns_converted_markdown,
        test_read_pdf_returns_unsupported_message,
        test_read_google_native_doc_unchanged,
        test_low_confidence_falls_back_to_raw,
        test_output_file_cleaned_up_after_read,
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
    import sys
    sys.exit(0 if failed == 0 else 1)
