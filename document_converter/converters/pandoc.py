from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


PANDOC_TYPES = {
    "markdown": "markdown",
    "html": "html",
    "txt": "plain",
    "docx": "docx",
}


def try_pandoc(source: Path, output: Path, input_type: str, output_type: str) -> bool:
    if input_type not in PANDOC_TYPES or output_type not in PANDOC_TYPES:
        return False

    pandoc = shutil.which("pandoc")
    if not pandoc:
        return False

    command = [
        pandoc,
        str(source),
        "--from",
        PANDOC_TYPES[input_type],
        "--to",
        PANDOC_TYPES[output_type],
        "--output",
        str(output),
    ]
    subprocess.run(command, check=True, timeout=30, capture_output=True, text=True)
    return True
