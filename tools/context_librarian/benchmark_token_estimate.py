"""benchmark_token_estimate.py — N17 item 1 (token estimation hardening).

Dev-only, manual script. NOT part of automated CI (it makes a real network
call to the Anthropic API and requires ANTHROPIC_API_KEY) and is NOT imported
by `librarian.py` or any production code.

Purpose: measure how far the librarian's `chars / 4` proxy
(`_approximate_char_estimate()`) diverges from a real Anthropic token count,
across bundles that mix Hebrew, English, and code — the exact content shape
real bundles contain. Until this has actually been run and its output
recorded in TOKEN_ESTIMATION_BENCHMARK.md, the chars/4 divisor must not be
changed: this repository's own governance rule (GOVERNANCE_RULES.md, Rule 15)
is "no claim without verification," and an unverified divisor change would be
exactly that.

Usage (requires a real ANTHROPIC_API_KEY; this script fails closed without
one rather than silently skipping the comparison):

    ANTHROPIC_API_KEY=<key> python3 tools/context_librarian/benchmark_token_estimate.py

Optional: `--model <model-id>` to benchmark against a different model's
tokenizer (Anthropic's `count_tokens` endpoint is model-specific). Use
`--output docs/context_librarian/token_calibration.json` to persist the
versioned calibration rows without running this script in per-PR CI.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.context_librarian.librarian import (  # noqa: E402
    Catalog,
    _approximate_char_estimate,
    build_bundle,
    load_catalog,
)
from tools.context_librarian.budget_preflight import (  # noqa: E402
    CANONICAL_PROFILE_QUERY_ENTRIES,
)

DEFAULT_MODEL = "claude-sonnet-5"

# One representative query per profile, chosen to pull in Hebrew node names/
# notes, English prose, and cited code paths — the actual mixed content a
# real bundle renders, not a synthetic corpus.
_PROFILE_QUERIES: dict[str, str] = {
    profile: query for profile, _query_id, query in CANONICAL_PROFILE_QUERY_ENTRIES
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _real_token_count(client, model: str, text: str) -> int:
    result = client.messages.count_tokens(
        model=model,
        messages=[{"role": "user", "content": text}],
    )
    return result.input_tokens


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--safety-margin", type=float, default=0.10)
    args = parser.parse_args(argv)
    if args.safety_margin < 0:
        parser.error("--safety-margin must be non-negative")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "benchmark_token_estimate: ANTHROPIC_API_KEY is not set. "
            "This benchmark requires a real API call and fails closed rather "
            "than fabricating or skipping the comparison.",
            file=sys.stderr,
        )
        return 2

    try:
        import anthropic
    except ImportError:
        print(
            "benchmark_token_estimate: the 'anthropic' package is required "
            "(already in requirements.txt) but is not importable here.",
            file=sys.stderr,
        )
        return 2

    client = anthropic.Anthropic()
    catalog: Catalog = load_catalog(_repo_root())
    commit_sha = subprocess.run(
        ["git", "-C", str(_repo_root()), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    rows: list[tuple[str, int, int, int]] = []
    for profile_id, query in _PROFILE_QUERIES.items():
        if profile_id not in catalog.profiles:
            continue
        bundle = build_bundle(catalog, task_type=profile_id, query=query)
        char_count = len(bundle)
        estimate = _approximate_char_estimate(bundle)
        real_tokens = _real_token_count(client, args.model, bundle)
        rows.append((profile_id, char_count, estimate, real_tokens))

    if not rows:
        print("benchmark_token_estimate: no profiles produced a bundle.", file=sys.stderr)
        return 1

    print(f"{'profile':<28}{'chars':>8}{'chars/4 estimate':>18}{'real tokens':>13}{'ratio':>8}")
    ratios: list[float] = []
    worst_understatement_divisor: float | None = None
    for profile_id, char_count, estimate, real_tokens in rows:
        ratio = real_tokens / estimate if estimate else float("nan")
        ratios.append(ratio)
        print(f"{profile_id:<28}{char_count:>8}{estimate:>18}{real_tokens:>13}{ratio:>8.2f}")
        if real_tokens > 0:
            # The largest divisor that would still make chars/divisor >=
            # real_tokens for this sample — the conservative bound.
            candidate = char_count / real_tokens
            if worst_understatement_divisor is None or candidate < worst_understatement_divisor:
                worst_understatement_divisor = candidate

    print()
    print(f"min ratio (real/estimate): {min(ratios):.2f}")
    print(f"max ratio (real/estimate): {max(ratios):.2f}")
    print(f"avg ratio (real/estimate): {sum(ratios) / len(ratios):.2f}")
    if worst_understatement_divisor is not None:
        print(
            "conservative divisor (never understates real tokens across "
            f"these samples): {worst_understatement_divisor:.1f} "
            f"(current divisor: {4})"
        )
    print()
    print(
        "Record this output in "
        "docs/context_librarian/TOKEN_ESTIMATION_BENCHMARK.md before making "
        "any divisor change."
    )
    if args.output:
        payload = {
            "schema_version": "1.0",
            "estimator": "anthropic_count_tokens",
            "freshness_days": 90,
            "results": [
                {
                    "model": args.model,
                    "commit_sha": commit_sha,
                    "timestamp": timestamp,
                    "profile": profile_id,
                    "character_count": char_count,
                    "estimated_tokens": estimate,
                    "real_counted_tokens": real_tokens,
                    "observed_ratio": real_tokens / estimate if estimate else 0,
                    "safety_margin": args.safety_margin,
                }
                for profile_id, char_count, estimate, real_tokens in rows
            ],
        }
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"calibration written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
