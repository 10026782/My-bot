"""FCC statement reader — the ONE I/O boundary that turns an uploaded bank / card statement (PDF or Excel bytes) into the pure parsers' input.
No Airtable, no network, no model; the PDF / Excel libraries are imported lazily (a server without them answers with a clear error, never crashes).

* Bank PDF   -> text fragments (Hebrew stored in VISUAL order, reversed back per run) (``bank_import.parse_statement_fragments``): pure Python, no ``pdftotext`` binary needed.
* Card PDF   -> the same fragments, ``card_import.parse_card_statement``.
* Card Excel -> the rows of the first sheet, ``card_import.parse_card_table`` (header-driven; the preferred input).
* A bank Excel export is not supported yet (no sample): it is refused with that message, never guessed.

Limits: a size cap and a content check (the file's real type, not its name), so a renamed file is refused rather than fed to a parser.
"""

from __future__ import annotations

import io
import re

from core.financial_control import bank_import as bi
from core.financial_control import card_import as ci

MAX_BYTES = 6 * 1024 * 1024
_HEBREW_RUN = re.compile(r'[֐-׿][֐-׿"\' ./\-]*[֐-׿]|[֐-׿]')


class StatementError(Exception):
    """A statement that cannot be read; the message is safe to show to the owner."""


def kind_of(data: bytes) -> str:
    """"pdf" | "xlsx" by the file's own magic bytes."""
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:4] == b"PK\x03\x04":
        return "xlsx"
    raise StatementError("הקובץ אינו PDF או Excel (xlsx)")


def _check(data: bytes) -> str:
    if not data:
        raise StatementError("הקובץ ריק")
    if len(data) > MAX_BYTES:
        raise StatementError("הקובץ גדול מדי (עד 6MB)")
    return kind_of(data)


def logical(text: str) -> str:
    """A card PDF stores Hebrew in visual order: reverse every Hebrew run (digits / Latin stay as they are)."""
    return _HEBREW_RUN.sub(lambda m: m.group()[::-1], text)


def pdf_fragments(data: bytes, visual_hebrew: bool) -> list[ci.Fragment]:
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LAParams, LTTextContainer, LTTextLine
    except ImportError as exc:                                                 # pragma: no cover — depends on the deployment
        raise StatementError("קריאת PDF אינה זמינה בשרת הזה (חסרה pdfminer.six)") from exc
    out: list[ci.Fragment] = []
    try:
        for number, page in enumerate(extract_pages(io.BytesIO(data), laparams=LAParams(line_margin=0.1, char_margin=1.0)), 1):
            for el in page:
                if not isinstance(el, LTTextContainer):
                    continue
                for line in el:
                    text = line.get_text().strip() if isinstance(line, LTTextLine) else ""
                    if text:
                        out.append(ci.Fragment(number, round(line.x0, 1), round(page.height - line.y0, 1), logical(text) if visual_hebrew else text, round(line.x1, 1)))
    except StatementError:
        raise
    except Exception as exc:
        raise StatementError("לא הצלחתי לקרוא את ה-PDF") from exc
    if not out:
        raise StatementError("ה-PDF אינו מכיל טקסט (סרוק?)")
    return out


def xlsx_rows(data: bytes) -> list[tuple]:
    try:
        import openpyxl
    except ImportError as exc:                                                 # pragma: no cover
        raise StatementError("קריאת Excel אינה זמינה בשרת הזה (חסרה openpyxl)") from exc
    try:
        ws = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True).worksheets[0]
        return [tuple(r) for r in ws.iter_rows(values_only=True)]
    except Exception as exc:
        raise StatementError("לא הצלחתי לקרוא את קובץ ה-Excel") from exc


def read_bank(data: bytes, account_ref: str) -> bi.ParseResult:
    if _check(data) == "xlsx":
        raise StatementError("ייצוא Excel של הבנק עדיין לא נתמך — יש לשלוח את דוח ה-PDF")
    return bi.parse_statement_fragments(pdf_fragments(data, visual_hebrew=True), account_ref)


def read_card(data: bytes, card_ref: str) -> ci.CardParse:
    if _check(data) == "xlsx":
        return ci.parse_card_table(xlsx_rows(data), card_ref)
    return ci.parse_card_statement(pdf_fragments(data, visual_hebrew=True), card_ref)
