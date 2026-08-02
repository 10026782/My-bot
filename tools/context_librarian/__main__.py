from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .librarian import (
    ContextLibrarianError,
    assess_profile_suggestions,
    build_bundle,
    estimate_bundle,
    load_catalog,
    discover_new_sources,
    refresh_after_merge,
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
    build.add_argument(
        "--direct-source-reverified", action="store_true",
        help="Allow planning after stale-node direct source re-verification",
    )
    build.add_argument(
        "--verification-ledger", action="append", default=[],
        help="Record a directly re-verified source in the bundle ledger",
    )

    estimate = sub.add_parser(
        "estimate",
        help=(
            "Non-raising dry run: report whether a bundle would fit its token "
            "budget without building/writing anything. Use before editing "
            "docs/context_librarian/*.json to see the exact honest number for "
            "every affected profile in one call, instead of an edit/test loop."
        ),
    )
    estimate_target = estimate.add_mutually_exclusive_group(required=True)
    estimate_target.add_argument("--task-type", help="Single profile to estimate")
    estimate_target.add_argument(
        "--all-profiles",
        action="store_true",
        help="Estimate every profile in the catalog, not just one",
    )
    estimate.add_argument("--query", default="")
    estimate.add_argument("--max-tokens", type=int)
    estimate.add_argument("--max-documents", type=int)
    estimate.add_argument(
        "--production-claim",
        action="store_true",
        help="Require qualifying production evidence in the workflow gate",
    )
    estimate.add_argument(
        "--verified-production-evidence",
        help="Explicitly attest a selected evidence path after direct review",
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

    refresh = sub.add_parser(
        "refresh-after-merge",
        help="Reconcile mechanical provenance against canonical main",
    )
    refresh.add_argument("--main-ref", default="origin/main")
    refresh.add_argument("--check", action="store_true", help="Report only; never write")
    refresh.add_argument("--write", action="store_true", help="Apply mechanical updates")

    discover = sub.add_parser("discover-sources", help="Classify new unregistered sources")
    discover.add_argument("--main-ref", default="origin/main")

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

        if args.command == "refresh-after-merge":
            if args.check and args.write:
                raise ContextLibrarianError("choose only one of --check or --write")
            proposal = refresh_after_merge(
                catalog, main_ref=args.main_ref, write=args.write
            )
            print(json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True))
            if proposal["status"] == "OK":
                print("OK: refresh is a no-op; catalog unchanged")
                return 0
            if proposal["status"] == "WARNING":
                print("WARNING: refresh has non-blocking warning-only sources")
                return 0
            if args.check:
                print(
                    "CHANGES_REQUIRED: catalog provenance is stale or has "
                    "unregistered sources; review before merge",
                    file=sys.stderr,
                )
                return 1
            return 0

        if args.command == "discover-sources":
            print(json.dumps(
                discover_new_sources(catalog, main_ref=args.main_ref),
                ensure_ascii=False, indent=2, sort_keys=True,
            ))
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

        if args.command == "estimate":
            task_types = sorted(catalog.profiles) if args.all_profiles else [args.task_type]
            results = [
                estimate_bundle(
                    catalog,
                    task_type=task_type,
                    query=args.query,
                    max_tokens=args.max_tokens,
                    max_documents=args.max_documents,
                    production_claim=args.production_claim,
                    verified_production_evidence=args.verified_production_evidence,
                )
                for task_type in task_types
            ]
            all_fit = True
            for result in results:
                status = "FITS" if result.fits else "OVER_BUDGET"
                if not result.fits:
                    all_fit = False
                print(
                    f"{result.task_type}\t{status}\t"
                    f"{result.actual_tokens}/{result.token_budget} tokens"
                )
            return 0 if all_fit else 2

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
            direct_source_reverified=args.direct_source_reverified,
            verification_ledger=args.verification_ledger,
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
