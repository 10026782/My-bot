from __future__ import annotations

import re
from pathlib import Path

from ..result import failure, success
from .pandoc import try_pandoc


def convert(source: Path, output: Path, input_type: str, output_type: str):
    if try_pandoc(source, output, input_type, output_type):
        return success(str(output), ["converted with pandoc"])

    text = source.read_text(encoding="utf-8")
    if output_type == "txt":
        output.write_text(_markdown_to_text(text), encoding="utf-8")
        return success(str(output), ["pandoc unavailable; used deterministic markdown text extraction"])

    if output_type == "markdown":
        output.write_text(text if text.endswith("\n") else f"{text}\n", encoding="utf-8")
        return success(str(output), ["plain text copied as markdown"])

    return failure(f"unsupported markdown/txt conversion: {input_type} -> {output_type}")


def _markdown_to_text(text: str) -> str:
    text = re.sub(r"```.*?```", lambda m: m.group(0).strip("`"), text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "- ", text, flags=re.M)
    text = re.sub(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", "", text, flags=re.M)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip() + "\n"
