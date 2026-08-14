"""Generate the validated local runtime snapshot from the canonical DB catalog."""
from __future__ import annotations

import argparse

from tools.tool_catalog_db import write_snapshot_from_db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-revision", default="catalog-db")
    parser.add_argument("--output")
    args = parser.parse_args()
    kwargs = {"source_revision": args.source_revision}
    if args.output:
        kwargs["path"] = args.output
    write_snapshot_from_db(**kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
