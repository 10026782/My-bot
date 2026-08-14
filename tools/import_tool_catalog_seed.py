"""One-time/idempotent importer for the SCOREBOS catalog seed."""
from __future__ import annotations

import argparse

from tools.tool_catalog_db import import_seed_to_db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-revision", default="python-seed")
    args = parser.parse_args()
    print(import_seed_to_db(source_revision=args.source_revision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
