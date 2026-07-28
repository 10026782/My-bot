from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .librarian import (
    ContextLibrarianError,
    assess_profile_suggestions,
    build_bundle,
    load_catalog,
    suggest_profiles,
    verify_consumption,
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
    build.add_argument(
        "--production-claim",
        action="store_true",
        help="Require qualifying production evidence in the workflow gate",
    )
    build.add_argument(
        "--verified-production-evidence",
        help="Explicitly attest a selected evidence path after direct review",
    )
    build.add_argument(
        "--assert-main",
        action="store_true",
        help=(
            "Backward-compatible alias for --assert-on-main-history"
        ),
    )
    build.add_argument(
        "--assert-on-main-history",
        action="store_true",
        help="Fail closed unless generated_commit is an ancestor of origin/main",
    )
    build.add_argument(
        "--assert-at-origin-main-tip",
        action="store_true",
        help="Fail closed unless generated_commit equals origin/main",
    )

    suggest = sub.add_parser(
        "suggest-profile",
        help="Rank profiles deterministically; does not select one for build",
    )
    suggest.add_argument("--query", required=True)
    suggest.add_argument("--limit", type=int, default=3)
    suggest.add_argument(
        "--all",
        action="store_true",
        help="Show every profile while preserving the Phase 0 default limit",
    )

    sub.add_parser("validate", help="Validate schemas, catalogs, edges, and paths")

    verify = sub.add_parser(
        "verify-consumption",
        help=(
            "Fail-closed check that every mandatory-tier source for a profile+query "
            "was reviewed or explicitly (independently-approved) waived"
        ),
    )
    verify.add_argument("--task-type", required=True)
    verify.add_argument("--query", default="")
    verify.add_argument("--ledger", required=True, type=Path)
    verify.add_argument(
        "--production-claim",
        action="store_true",
        help="Include production evidence in the mandatory tier (mirrors build's --production-claim)",
    )
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

        if args.command == "verify-consumption":
            ledger_path = args.ledger
            if not ledger_path.is_absolute():
                ledger_path = _repo_root() / ledger_path
            try:
                ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ContextLibrarianError(
                    f"cannot load ledger {ledger_path}: {exc}"
                ) from exc
            result = verify_consumption(
                catalog,
                task_type=args.task_type,
                query=args.query,
                ledger=ledger_data,
                production_claim=args.production_claim,
            )
            print(result.status)
            for reason in result.blocked_reasons:
                print(f"- {reason}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            return result.exit_code

        if args.command == "suggest-profile":
            ranked = suggest_profiles(catalog, args.query)
            visible = ranked if args.all else ranked[: max(1, args.limit)]
            for item in visible:
                terms = ", ".join(item["matched_terms"]) or "none"
                print(f"{item['profile_id']}\tscore={item['score']}\tmatched={terms}")
            assessment = assess_profile_suggestions(ranked)
            candidates = ", ".join(assessment["candidates"]) or "none"
            print(
                f"Selection status: {assessment['status']}; "
                f"top_score={assessment['top_score']}; candidates={candidates}; "
                "automatic_selection=false"
            )
            print("Suggestion only: pass an explicit --task-type to build.")
            return 0

        bundle = build_bundle(
            catalog,
            task_type=args.task_type,
            query=args.query,
            max_tokens=args.max_tokens,
            max_documents=args.max_documents,
            production_claim=args.production_claim,
            verified_production_evidence=args.verified_production_evidence,
            assert_main=args.assert_main,
            assert_on_main_history=args.assert_on_main_history,
            assert_at_origin_main_tip=args.assert_at_origin_main_tip,
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
