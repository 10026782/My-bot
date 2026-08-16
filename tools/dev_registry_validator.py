#!/usr/bin/env python3
"""CLI compatibility wrapper for the neutral §3.5 Registry contract."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dev_registry_contract import *  # noqa: F401,F403 - compatibility exports


def main() -> int:
    try:
        rows = validate_registry_file()
    except RegistryValidationError as exc:
        print(f"DEV-REG VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"DEV-REG VALIDATION PASSED: {len(rows)} Registry rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
