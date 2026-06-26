from __future__ import annotations

from pathlib import Path

from ..result import failure, success
from .pandoc import try_pandoc


def convert(source: Path, output: Path, input_type: str, output_type: str):
    if try_pandoc(source, output, input_type, output_type):
        return success(str(output), ["converted with pandoc"])

    text = source.read_text(encoding="utf-8")
    if output_type == "html":
        import markdown

        html = markdown.markdown(text, extensions=["tables"])
        output.write_text(f"<!doctype html>\n<html><body>\n{html}\n</body></html>\n", encoding="utf-8")
        return success(str(output), ["pandoc unavailable; used python markdown"])

    if input_type == "html":
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(text, "html.parser")
        if soup.find(["script", "style", "svg", "canvas", "iframe"]):
            return failure("complex html is not supported for markdown conversion")
        output.write_text(_html_to_markdown(soup), encoding="utf-8")
        return success(str(output), ["pandoc unavailable; converted html text to markdown-compatible text"])

    return failure(f"unsupported markdown/html conversion: {input_type} -> {output_type}")


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


def _html_to_markdown(soup) -> str:
    body = soup.body or soup
    lines: list[str] = []
    for element in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"], recursive=True):
        if element.find_parent(["table"]) and element.name != "table":
            continue
        if element.name.startswith("h"):
            level = int(element.name[1])
            lines.append(f"{'#' * level} {element.get_text(' ', strip=True)}")
            lines.append("")
        elif element.name == "li":
            lines.append(f"- {element.get_text(' ', strip=True)}")
        elif element.name == "table":
            rows = [
                [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
                for row in element.find_all("tr")
            ]
            lines.extend(_markdown_table(rows))
            lines.append("")
        else:
            text = element.get_text(" ", strip=True)
            if text:
                lines.append(text)
                lines.append("")
    return _collapse_blank_lines("\n".join(lines))


def _markdown_table(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    result = ["| " + " | ".join(normalized[0]) + " |"]
    result.append("| " + " | ".join(["---"] * width) + " |")
    for row in normalized[1:]:
        result.append("| " + " | ".join(row) + " |")
    return result
