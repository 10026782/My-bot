# test_pilot_preflight.py — smoke tests for tools/context_librarian/pilot_preflight.py
#
# Plain-script test (see CLAUDE.md: "there is no pytest/unittest harness wired
# up"), run directly with `python3 test_pilot_preflight.py`. Exercises the
# preflight gate for docs/governance/librarian/FIRST_REAL_CONSUMPTION_PILOT.md
# against real, live-recomputed profiles (approval_ux/tool_execution) — no
# mocking of tools.context_librarian.librarian, since the whole point of this
# gate is to never drift from what that module actually computes. Bundle
# fixtures are produced by the real build_bundle() rather than hand-written
# text, so the profile/checklist-binding checks are exercised against exactly
# what `python -m tools.context_librarian build` would actually emit.

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.context_librarian.librarian import (  # noqa: E402
    build_bundle,
    consumption_checklist,
    load_catalog,
)
from tools.context_librarian.pilot_preflight import run_preflight  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent
TASK_TYPE = "approval_ux"
OTHER_TASK_TYPE = "tool_execution"


def _base_ledger(required_sources: list) -> dict:
    return {
        "schema_version": "1.0",
        "task_type": TASK_TYPE,
        "profile": TASK_TYPE,
        "query": "pilot preflight smoke test",
        "production_claim": False,
        "bundle_generated_commit": "0" * 40,
        "bundle_generated_branch": "test-branch",
        "required_sources": required_sources,
        "review_receipts": [],
        "waived_sources": [],
    }


def run() -> bool:
    catalog = load_catalog(REPO_ROOT)
    profile = catalog.profiles[TASK_TYPE]
    live_required = consumption_checklist(catalog, profile, production_claim=False)

    # A real bundle, built the same way the pilot runbook builds one — the
    # fixture every "bundle is fine, something else is wrong" case starts from.
    valid_bundle_text = build_bundle(
        catalog,
        task_type=TASK_TYPE,
        query="pilot preflight smoke test",
        production_claim=False,
    )
    # A real bundle for a *different* profile — used to prove a wrong-profile
    # bundle can't satisfy the gate just because it's non-empty and well-formed.
    other_profile_bundle_text = build_bundle(
        catalog,
        task_type=OTHER_TASK_TYPE,
        query="pilot preflight smoke test",
        production_claim=False,
    )

    results: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bundle_path = tmp_path / "bundle.md"
        ledger_path = tmp_path / "ledger.json"

        def preflight(**overrides):
            kwargs = dict(
                repo_root=REPO_ROOT,
                task_type=TASK_TYPE,
                production_claim=False,
                bundle_path=bundle_path,
                ledger_path=ledger_path,
            )
            kwargs.update(overrides)
            return run_preflight(**kwargs)

        # 1. Missing bundle -> BLOCKED (exit 1), ledger not even inspected.
        code, messages = preflight()
        results.append(("missing bundle -> exit 1", code == 1))

        # 2. Hand-written/fake bundle (non-empty, no real Consumption
        #    Checklist section) -> BLOCKED (exit 1). This is the exact
        #    scenario CodeRabbit flagged on PR #501: a bundle that is merely
        #    non-empty must not be enough to satisfy the gate.
        bundle_path.write_text("# fake bundle\n", encoding="utf-8")
        code, messages = preflight()
        results.append(("hand-written bundle -> exit 1", code == 1))

        # 3. Real bundle, but built for a different profile than --task-type
        #    -> BLOCKED (exit 1), profile-binding check.
        bundle_path.write_text(other_profile_bundle_text, encoding="utf-8")
        code, messages = preflight()
        results.append(("wrong-profile bundle -> exit 1", code == 1))

        # 4. Real, matching-profile bundle written from here on.
        bundle_path.write_text(valid_bundle_text, encoding="utf-8")

        # 5. Bundle present and valid, ledger missing -> BLOCKED (exit 2).
        code, messages = preflight()
        results.append(("missing ledger -> exit 2", code == 2))

        # 6. Ledger present but required_sources doesn't match the live tier
        #    -> BLOCKED (exit 3).
        ledger_path.write_text(
            json.dumps(_base_ledger(["code:not_a_real_mandatory_item.py"])),
            encoding="utf-8",
        )
        code, messages = preflight()
        results.append(("required_sources mismatch -> exit 3", code == 3))

        # 7. Ledger's declared task_type disagrees with --task-type -> BLOCKED (exit 2).
        mismatched = _base_ledger(list(live_required))
        mismatched["task_type"] = OTHER_TASK_TYPE
        ledger_path.write_text(json.dumps(mismatched), encoding="utf-8")
        code, messages = preflight()
        results.append(("task_type mismatch -> exit 2", code == 2))

        # 8. required_sources contains a malformed (non-string) entry —
        #    CodeRabbit's flagged crash: set() over an unhashable dict/list
        #    raises TypeError instead of failing closed with a message.
        malformed = _base_ledger(list(live_required) + [{}])
        ledger_path.write_text(json.dumps(malformed), encoding="utf-8")
        try:
            code, messages = preflight()
            crashed = False
        except TypeError:
            code, messages, crashed = None, [], True
        results.append(("malformed required_sources entry does not crash", not crashed))
        results.append(("malformed required_sources entry -> exit 2", code == 2))

        # 9. Fully matching skeleton -> PROCEED (exit 0).
        ledger_path.write_text(
            json.dumps(_base_ledger(list(live_required))), encoding="utf-8"
        )
        code, messages = preflight()
        results.append(("matching skeleton -> exit 0 (PROCEED)", code == 0))
        results.append(
            ("PROCEED message present", any("PROCEED" in m for m in messages))
        )

        # 10. Invalid JSON ledger -> BLOCKED (exit 2), never crashes.
        ledger_path.write_text("{not json", encoding="utf-8")
        code, messages = preflight()
        results.append(("invalid JSON ledger -> exit 2", code == 2))

    print("\n=== pilot_preflight smoke tests ===")
    failures = [name for name, passed in results if not passed]
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if failures:
        print(f"\n❌ FAILED: {', '.join(failures)}")
    else:
        print(f"\n✅ {len(results)}/{len(results)} passed")
    return not failures


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
