from __future__ import annotations

from pathlib import Path

from .result import ConversionResult, failure

SUPPORTED_TYPES = {"markdown", "md", "html", "txt", "docx", "csv", "xlsx"}
NORMALIZED_TYPES = {"md": "markdown"}
UNSUPPORTED_TYPES = {"pdf", "ocr"}


def convert_document(input_file, input_type, output_type) -> dict:
    """Convert a document with deterministic converters only.

    The public API intentionally returns a plain dict so callers can serialize
    the result directly without depending on dataclass internals.
    """

    result = _convert_document(input_file, input_type, output_type)
    return result.as_dict()


def _convert_document(input_file, input_type, output_type) -> ConversionResult:
    source = Path(input_file)
    in_type = _normalize_type(input_type)
    out_type = _normalize_type(output_type)

    if in_type in UNSUPPORTED_TYPES or out_type in UNSUPPORTED_TYPES:
        return failure("PDF/OCR conversion is not supported")
    if in_type not in SUPPORTED_TYPES or out_type not in SUPPORTED_TYPES:
        return failure(f"unsupported conversion type: {input_type} -> {output_type}")
    if in_type == out_type:
        return failure("input_type and output_type must be different")
    if not source.exists() or not source.is_file():
        return failure(f"input file not found: {source}")
    if source.stat().st_size == 0:
        return failure("input file is empty")

    output = _output_path(source, out_type)
    pair = (in_type, out_type)

    try:
        if pair in {("markdown", "html"), ("html", "markdown")}:
            from .converters.markdown_html import convert
        elif pair in {("markdown", "txt"), ("txt", "markdown")}:
            from .converters.markdown_txt import convert
        elif pair in {("html", "txt"), ("txt", "html")}:
            from .converters.html_txt import convert
        elif out_type == "docx" and in_type in {"markdown", "html", "txt"}:
            from .converters.to_docx import convert
        elif in_type == "docx" and out_type in {"markdown", "txt"}:
            from .converters.from_docx import convert
        elif pair in {("csv", "xlsx"), ("xlsx", "csv")}:
            from .converters.csv_xlsx import convert
        else:
            return failure(f"unsupported conversion pair: {in_type} -> {out_type}")

        result = convert(source, output, in_type, out_type)
    except ImportError as exc:
        _delete_partial_output(output)
        return failure(f"missing deterministic converter dependency: {exc.name}")
    except Exception as exc:
        _delete_partial_output(output)
        return failure(str(exc))

    if result.output_file is None:
        _delete_partial_output(output)
        return result

    output_file = Path(result.output_file)
    if not output_file.exists() or output_file.stat().st_size == 0:
        _delete_partial_output(output_file)
        return failure("converter did not create a non-empty output file")
    return result


def _normalize_type(value: str) -> str:
    normalized = str(value or "").strip().lower().lstrip(".")
    return NORMALIZED_TYPES.get(normalized, normalized)


def _output_path(source: Path, output_type: str) -> Path:
    suffix = ".md" if output_type == "markdown" else f".{output_type}"
    if source.suffix.lower() == suffix:
        candidate = source.with_name(f"{source.stem}.converted{suffix}")
    else:
        candidate = source.with_suffix(suffix)
    if not candidate.exists():
        return candidate
    index = 1
    while True:
        numbered = source.with_name(f"{source.stem}.converted-{index}{suffix}")
        if not numbered.exists():
            return numbered
        index += 1


def _delete_partial_output(output: Path) -> None:
    try:
        if output.exists():
            output.unlink()
    except OSError:
        pass
