# Safe Document Converter

Updated: 26/06/2026

## Purpose

`document_converter.convert_document(input_file, input_type, output_type)` is a deterministic, fail-closed conversion API for simple documents. It does not use AI, OCR, PDF reconstruction, or layout guessing.

## API

```python
from document_converter import convert_document

result = convert_document("example.md", "markdown", "docx")
```

Return shape:

```python
{
    "status": "success",
    "confidence": "high",
    "warnings": ["pandoc unavailable; used python-docx"],
    "output_file": "example.docx",
}
```

Failures return no document:

```python
{
    "status": "error: PDF/OCR conversion is not supported",
    "confidence": "low",
    "warnings": [],
    "output_file": None,
}
```

## Supported MVP Conversions

| Input | Output |
|---|---|
| Markdown | HTML, TXT, DOCX |
| HTML | Markdown, TXT, DOCX |
| TXT | Markdown, HTML, DOCX |
| DOCX | Markdown, TXT |
| CSV | XLSX |
| XLSX | CSV |

`md` is accepted as an alias for `markdown`.

## Conversion Engine

The converter tries Pandoc first for document pairs where Pandoc can provide deterministic conversion. If `pandoc` is unavailable, it uses deterministic Python libraries:

- `markdown` for Markdown to HTML
- `beautifulsoup4` for simple HTML parsing
- `python-docx` for DOCX read/write
- `openpyxl` for XLSX read/write
- Python `csv` for CSV read/write

No model is called during conversion.

## Known Limitations

- PDF input or output is not supported.
- OCR is not supported.
- Scanned documents are not supported.
- Complex document layout reconstruction is not supported.
- HTML containing `script`, `style`, `svg`, `canvas`, or `iframe` fails closed.
- DOCX files with embedded images fail closed.
- XLSX conversion supports exactly one non-empty sheet.
- XLSX files with merged cells, charts, or images fail closed.
- CSV conversion supports rectangular rows only; ragged CSV rows fail closed.
- The API chooses an adjacent output path. If that path already exists, it writes a deterministic `converted-N` filename instead of overwriting existing files.

## Examples

```python
convert_document("notes.md", "markdown", "html")
convert_document("notes.md", "markdown", "txt")
convert_document("page.html", "html", "docx")
convert_document("brief.docx", "docx", "markdown")
convert_document("contacts.csv", "csv", "xlsx")
convert_document("contacts.xlsx", "xlsx", "csv")
```

## Governance

- Every converter lives in its own module under `document_converter/converters/`.
- Every supported converter family has regression coverage in `test_document_converter.py`.
- Unsupported or uncertain conversions return `confidence="low"` and `output_file=None`.
- The converter never calls AI and never infers missing structure.
