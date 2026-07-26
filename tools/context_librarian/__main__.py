from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .librarian import (
    ContextLibrarianError,
    build_bundle,
    load_catalog,
    suggest_profiles,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.context_librarian",
        description="Build deterministic, files-first BOSS context bundles.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build a Markdown context bundle")
    build.add_argument("--task-type", required=True)
    build.add_argument("--query", default="")
    build.add_argument("--max-tokens", type=int)
    build.add_argument("--max-documents", type=int)
    build.add_argument("--output", type=Path)

    suggest = sub.add_parser(
        "suggest-profile",
        help="Rank profiles deterministically; does not select one for build",
    )
    suggest.add_argument("--query", required=True)
    suggest.add_argument("--limit", type=int, default=3)

    sub.add_parser("validate", help="Validate schemas, catalogs, edges, and paths")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        catalog = load_catalog(_repo_root())
        if args.command == "validate":
            print(
                f"Context Librarian catalog valid: {len(catalog.nodes)} nodes, "
                f"{len(catalog.edges)} edges, {len(catalog.profiles)} profiles"
            )
            return 0

        if args.command == "suggest-profile":
            ranked = suggest_profiles(catalog, args.query)
            for item in ranked[: max(1, args.limit)]:
                terms = ", ".join(item["matched_terms"]) or "none"
                print(f"{item['profile_id']}\tscore={item['score']}\tmatched={terms}")
            print("Suggestion only: pass an explicit --task-type to build.")
            return 0

        bundle = build_bundle(
            catalog,
            task_type=args.task_type,
            query=args.query,
            max_tokens=args.max_tokens,
            max_documents=args.max_documents,
        )
        if args.output:
            output = args.output
            if not output.is_absolute():
                output = _repo_root() / output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(bundle, encoding="utf-8", newline="\n")
            print(output)
        else:
            print(bundle, end="")
        return 0
    except ContextLibrarianError as exc:
        print(f"context-librarian: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
