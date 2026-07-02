from __future__ import annotations

import csv

import pytest

from document_converter import convert_document


def test_markdown_simple_to_html_and_txt(tmp_path):
    source = tmp_path / "simple.md"
    source.write_text("# Title\n\nHello **world**.\n", encoding="utf-8")

    html = convert_document(source, "markdown", "html")
    assert html["status"] == "success"
    assert html["confidence"] == "high"
    assert "<h1>Title</h1>" in (tmp_path / "simple.html").read_text(encoding="utf-8")

    txt = convert_document(source, "markdown", "txt")
    assert txt["status"] == "success"
    assert "Title" in (tmp_path / "simple.txt").read_text(encoding="utf-8")


def test_markdown_table_to_html_and_txt(tmp_path):
    source = tmp_path / "table.md"
    source.write_text("| Name | Count |\n| --- | --- |\n| A | 1 |\n", encoding="utf-8")

    html = convert_document(source, "md", "html")
    assert html["status"] == "success"
    assert "<table>" in (tmp_path / "table.html").read_text(encoding="utf-8")

    txt = convert_document(source, "markdown", "txt")
    assert txt["status"] == "success"
    assert "Name" in (tmp_path / "table.txt").read_text(encoding="utf-8")


def test_html_conversions(tmp_path):
    source = tmp_path / "page.html"
    source.write_text("<html><body><h1>Hello</h1><p>World</p></body></html>", encoding="utf-8")

    txt = convert_document(source, "html", "txt")
    assert txt["status"] == "success"
    assert "Hello" in (tmp_path / "page.txt").read_text(encoding="utf-8")

    md = convert_document(source, "html", "markdown")
    assert md["status"] == "success"
    assert "# Hello" in (tmp_path / "page.md").read_text(encoding="utf-8")


def test_docx_round_trips_to_markdown_and_txt(tmp_path):
    pytest.importorskip("docx")
    source = tmp_path / "plain.txt"
    source.write_text("Hello\n\nWorld\n", encoding="utf-8")

    docx_result = convert_document(source, "txt", "docx")
    assert docx_result["status"] == "success"
    docx_file = tmp_path / "plain.docx"
    assert docx_file.exists()

    md = convert_document(docx_file, "docx", "markdown")
    assert md["status"] == "success"
    assert "Hello" in (tmp_path / "plain.md").read_text(encoding="utf-8")

    txt = convert_document(docx_file, "docx", "txt")
    assert txt["status"] == "success"
    assert "World" in (tmp_path / "plain.converted-1.txt").read_text(encoding="utf-8")


def test_csv_xlsx_round_trip(tmp_path):
    pytest.importorskip("openpyxl")
    source = tmp_path / "data.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "count"])
        writer.writerow(["alpha", "1"])

    xlsx = convert_document(source, "csv", "xlsx")
    assert xlsx["status"] == "success"
    xlsx_file = tmp_path / "data.xlsx"
    assert xlsx_file.exists()

    csv_result = convert_document(xlsx_file, "xlsx", "csv")
    assert csv_result["status"] == "success"
    rows = list(csv.reader((tmp_path / "data.converted-1.csv").open("r", encoding="utf-8", newline="")))
    assert rows[0] == ["name", "count"]
    assert rows[1] == ["alpha", "1"]


def test_fail_closed_for_pdf_and_complex_html(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    result = convert_document(pdf, "pdf", "docx")
    assert result["status"].startswith("error:")
    assert result["confidence"] == "low"
    assert result["output_file"] is None

    html = tmp_path / "complex.html"
    html.write_text("<html><body><svg></svg></body></html>", encoding="utf-8")
    result = convert_document(html, "html", "docx")
    assert result["status"].startswith("error:")
    assert result["output_file"] is None


if __name__ == "__main__":
    # BUG-CI-SILENT-PASS-DOCUMENT-CONVERTER: ci.yml runs test_*.py via
    # `python "$f"`, not pytest, so bare pytest-style test functions never
    # executed here — CI reported a false green. tmp_path is a pytest
    # fixture with no plain-Python equivalent, so each test is invoked
    # explicitly (no auto-collect) against a real temp dir per test.
    import shutil
    import tempfile
    from pathlib import Path

    _tests = [
        test_markdown_simple_to_html_and_txt,
        test_markdown_table_to_html_and_txt,
        test_html_conversions,
        test_docx_round_trips_to_markdown_and_txt,
        test_csv_xlsx_round_trip,
        test_fail_closed_for_pdf_and_complex_html,
    ]

    passed = 0
    skipped = 0
    for fn in _tests:
        tmp_dir = tempfile.mkdtemp(prefix="document_converter_selftest_")
        try:
            fn(Path(tmp_dir))
        except pytest.skip.Exception as exc:
            print(f"skipped {fn.__name__}: {exc}")
            skipped += 1
            continue
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"passed {fn.__name__}")
        passed += 1

    print(f"document_converter self-test OK — {passed} passed, {skipped} skipped")
