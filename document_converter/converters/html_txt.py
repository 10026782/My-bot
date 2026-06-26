from __future__ import annotations

from html import escape
from pathlib import Path

from ..result import failure, success
from .pandoc import try_pandoc


def convert(source: Path, output: Path, input_type: str, output_type: str):
    if try_pandoc(source, output, input_type, output_type):
        return success(str(output), ["converted with pandoc"])

    text = source.read_text(encoding="utf-8")
    if output_type == "txt":
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(text, "html.parser")
        if soup.find(["script", "style", "svg", "canvas", "iframe"]):
            return failure("complex html is not supported for text conversion")
        output.write_text(_collapse_blank_lines(soup.get_text("\n")), encoding="utf-8")
        return success(str(output), ["pandoc unavailable; used beautifulsoup4"])

    if output_type == "html":
        body = "<br>\n".join(escape(line) for line in text.splitlines())
        output.write_text(f"<!doctype html>\n<html><body>\n{body}\n</body></html>\n", encoding="utf-8")
        return success(str(output), ["plain text wrapped as deterministic html"])

    return failure(f"unsupported html/txt conversion: {input_type} -> {output_type}")


def _collapse_blank_lines(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    collapsed: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        collapsed.append(line)
        previous_blank = blank
    return "\n".join(collapsed).strip() + "\n"
