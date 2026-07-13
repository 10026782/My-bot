#!/usr/bin/env python3
# tools/check_airtable_schema_runtime.py — PR3C: on-demand Airtable runtime
# schema diagnostic.
#
# NOT a scheduled job, NOT wired into scheduler.py, NOT a daily/periodic
# refresh. Run manually:
#   python3 tools/check_airtable_schema_runtime.py --dry-run
#   python3 tools/check_airtable_schema_runtime.py --dry-run --json
#
# Trigger this on-demand after: owner-made Airtable schema changes,
# schema-related code changes, before enabling any *_ENFORCE state, after
# a significant deploy, or when schema drift / 422s are suspected.
#
# Never logs/prints secret values -- only env-var presence (yes/no).
#
# Exact-value diagnostic: table/field/select-option names are reported
# verbatim (quoted + repr()), never normalized/trimmed/cleaned/re-cased --
# the whole point is to surface drift that normalization would hide.
#
# Future provider note: Airtable is provider #1 of a future Provider
# Contract Governance pattern (adapter + contract + diagnostic per
# provider, not raw tool calls). This file is that diagnostic for
# Airtable specifically -- it does not generalize to other providers,
# and this PR does not build that generalization.

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_SELECT_TYPES = {"singleSelect", "multipleSelects"}
_PUNCT_SUSPECT_RE = re.compile(r"[.,;:!?][^\s.,;:!?]")
_SIMILARITY_THRESHOLD = 0.85


def _value_warnings(value: str, siblings: list[str]) -> list[str]:
    """Exact-string diagnostic warnings for one select-option value.
    `siblings` is the full choice list for the same field (value included)."""
    warnings: list[str] = []

    if value != value.lstrip():
        warnings.append("leading_space")
    if value != value.rstrip():
        warnings.append("trailing_space")
    if "  " in value:
        warnings.append("repeated_space")
    if _PUNCT_SUSPECT_RE.search(value):
        warnings.append("punctuation_suspect")
    if any(not ch.isprintable() for ch in value):
        warnings.append("hidden_control_chars")

    loose = re.sub(r"\s+", " ", value.strip().lower())
    casing_variant_found = False
    for other in siblings:
        if other == value:
            continue
        if re.sub(r"\s+", " ", other.strip().lower()) == loose:
            warnings.append("casing_variant")
            casing_variant_found = True
            break

    if not casing_variant_found:
        for other in siblings:
            if other == value:
                continue
            if difflib.SequenceMatcher(None, value, other).ratio() >= _SIMILARITY_THRESHOLD:
                warnings.append("visually_similar_duplicate")
                break

    return warnings


def _examine_table_contract(contract: dict) -> dict:
    fields_info = contract.get("fields", {})
    select_fields = []
    for fname, finfo in sorted(fields_info.items()):
        if finfo.get("type") not in _SELECT_TYPES:
            continue
        choices = list(finfo.get("choices") or [])
        choice_reports = [
            {
                "value": val,
                "quoted": json.dumps(val, ensure_ascii=False),
                "repr": repr(val),
                "length": len(val),
                "warnings": _value_warnings(val, choices),
            }
            for val in choices
        ]
        select_fields.append({
            "field": fname,
            "field_id": finfo.get("field_id"),
            "type": finfo.get("type"),
            "choice_count": len(choices),
            "choices": choice_reports,
        })

    table_warnings = []
    if contract.get("mode") != "full":
        table_warnings.append("mode_not_full")
    if contract.get("source") == "seed":
        table_warnings.append("source_is_seed")

    return {
        "table_id": contract.get("table_id"),
        "mode": contract.get("mode"),
        "source": contract.get("source"),
        "field_count": len(fields_info),
        "select_field_count": len(select_fields),
        "select_fields": select_fields,
        "warnings": table_warnings,
    }


def _table_has_any_warning(report: dict) -> bool:
    """True if the table itself (mode/source) or any select-option value
    within it has a warning — the single source of truth for both the
    overall PASS/WARN rollup and the per-table printed marker."""
    if report["warnings"]:
        return True
    return any(
        c["warnings"]
        for sf in report["select_fields"]
        for c in sf["choices"]
    )


def run_diagnostic() -> dict:
    """
    Runs the full on-demand diagnostic. Never raises -- every failure mode
    is captured in the returned dict's "overall" (PASS/WARN/FAIL) and
    per-section fields, so both the human-readable printer and --json can
    consume the same structure.
    """
    result: dict = {
        "env_present": False,
        "meta_api_reachable": False,
        "tables_fetched": 0,
        "live_table_names": [],
        "missing_in_airtable": [],
        "unknown_to_code": [],
        "snapshot_table_exists": False,
        "table_reports": {},
        "overall": "FAIL",
    }

    key = os.environ.get("AIRTABLE_API_KEY", "")
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    result["env_present"] = bool(key and base)
    if not result["env_present"]:
        return result

    from tools.schema_snapshot import fetch_live_schema, _snapshot_table_exists

    raw_meta = fetch_live_schema()
    if raw_meta is None:
        return result
    result["meta_api_reachable"] = True

    live_tables = raw_meta.get("tables", [])
    result["tables_fetched"] = len(live_tables)
    live_names = sorted(t.get("name", "") for t in live_tables if t.get("name"))
    result["live_table_names"] = live_names
    result["snapshot_table_exists"] = _snapshot_table_exists(raw_meta)

    import airtable_schema

    code_tables = sorted({
        v for k, v in vars(airtable_schema.Tables).items()
        if not k.startswith("_") and isinstance(v, str)
    })

    live_set = set(live_names)
    code_set = set(code_tables)
    result["missing_in_airtable"] = sorted(code_set - live_set)
    result["unknown_to_code"] = sorted(live_set - code_set)

    from core.runtime_schema_provider import get_provider

    provider = get_provider()
    for table in sorted(code_set & live_set):
        contract = provider.get_table_contract(table)
        result["table_reports"][table] = _examine_table_contract(contract)

    warn = bool(result["missing_in_airtable"] or result["unknown_to_code"]
                or not result["snapshot_table_exists"])
    warn = warn or any(_table_has_any_warning(r) for r in result["table_reports"].values())

    result["overall"] = "WARN" if warn else "PASS"
    return result


def _print_human(result: dict) -> None:
    print("Airtable Runtime Schema Diagnostic")
    print("=" * 60)
    print(f"Airtable env present: {'yes' if result['env_present'] else 'no'}")
    if not result["env_present"]:
        print("FAIL: AIRTABLE_API_KEY / AIRTABLE_BASE_ID missing — cannot proceed.")
        return

    print(f"Meta API reachable: {'yes' if result['meta_api_reachable'] else 'no'}")
    if not result["meta_api_reachable"]:
        print("FAIL: Meta API unreachable — cannot proceed.")
        return

    print(f"Tables fetched: {result['tables_fetched']}")
    print("Live table names:")
    for name in result["live_table_names"]:
        print(f"  - {json.dumps(name, ensure_ascii=False)}")

    print(f"\nSnapshot table ({'Tables.SCHEMA_SNAPSHOTS'!s}) exists live: "
          f"{'yes' if result['snapshot_table_exists'] else 'no'}")

    if result["missing_in_airtable"]:
        print("\nWARN: known to code, missing in live Airtable:")
        for t in result["missing_in_airtable"]:
            print(f"  - {json.dumps(t, ensure_ascii=False)}")
    if result["unknown_to_code"]:
        print("\nWARN: live Airtable tables not known to code:")
        for t in result["unknown_to_code"]:
            print(f"  - {json.dumps(t, ensure_ascii=False)}")

    print("\nPer-table RuntimeSchemaProvider contracts:")
    for table, report in result["table_reports"].items():
        marker = "WARN" if _table_has_any_warning(report) else "PASS"
        print(f"  [{marker}] {json.dumps(table, ensure_ascii=False)} "
              f"mode={report['mode']} source={report['source']} "
              f"fields={report['field_count']} select_fields={report['select_field_count']}")
        for w in report["warnings"]:
            print(f"           warning: {w}")
        for sf in report["select_fields"]:
            field_has_warning = any(c["warnings"] for c in sf["choices"])
            if not field_has_warning:
                continue
            print(f"           select field {json.dumps(sf['field'], ensure_ascii=False)} "
                  f"({sf['choice_count']} choices):")
            for c in sf["choices"]:
                if not c["warnings"]:
                    continue
                print(f"             {c['quoted']}  repr={c['repr']}  len={c['length']}  "
                      f"warnings={c['warnings']}")

    print("\n" + "=" * 60)
    print(f"OVERALL: {result['overall']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="On-demand Airtable runtime schema diagnostic")
    parser.add_argument("--dry-run", action="store_true", help="Run the diagnostic (read-only, no writes)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    args = parser.parse_args()

    if not args.dry_run:
        parser.print_help()
        return 1

    result = run_diagnostic()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)

    return 0 if result["overall"] in ("PASS", "WARN") else 1


if __name__ == "__main__":
    sys.exit(main())
