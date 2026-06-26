# Document Conversion Governance

Updated: 26/06/2026

## Rule

Document conversion modules must be deterministic and fail closed.

## Forbidden

- AI-assisted file conversion.
- OCR.
- PDF reconstruction.
- Guessing tables, headings, layout, columns, images, or reading order.
- Returning an output file when confidence is not high.

## Allowed Engines

- Pandoc.
- `python-docx`.
- `openpyxl`.
- Python `csv`.
- `markdown`.
- `beautifulsoup4` for simple HTML parsing.

## Boundary

AI may be used for wording, summaries, translation, or content analysis after the user asks for those tasks. AI must not be used as the format conversion engine or to recover missing structure.
