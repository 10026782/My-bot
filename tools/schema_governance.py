#!/usr/bin/env python3
# schema_governance.py — N07
#
# מריץ השוואה: live Airtable schema vs airtable_schema.py
# מוצא drift:
#   - שדה קיים ב-code, לא קיים ב-Airtable (whitespace-tolerant)     → ERROR
#   - שדה קיים ב-Airtable, לא ב-code                                 → WARNING
#   - trailing/leading spaces בשמות שדות ב-Airtable                  → WARNING
#   - trailing/leading spaces ב-singleSelect/multipleSelects options → WARNING
#   - סוג שדה שהשתנה מהריצה הקודמת (text → singleSelect וכו')        → ERROR
#   - *Fields class קיים ב-airtable_schema.py בלי רישום ב-TABLE_CLASS_MAP
#     (schema_audit.py) → ERROR. זה הפער שאיפשר ל-MediaFileFields (F16)
#     להיכנס לקוד עם שדה שלא תואם ל-live בלי שה-CI יתפוס את זה: ה-loop
#     הראשי רץ רק על טבלאות שכבר רשומות ב-TABLE_CLASS_MAP, אז טבלה חדשה
#     שלא נרשמה דולגת בשתיקה — לא ERROR, לא WARNING, שום דבר.
#
# שימוש: python3 tools/schema_governance.py
# פלט: דוח עברית ל-console + schema_drift_report.json (לא ב-git, ב-.gitignore)
#
# לא נוגע בשום דבר — READ ONLY לחלוטין. אפס כתיבה ל-Airtable.
# (השוואת "סוג שדה שהשתנה" משתמשת בדוח השמור מהריצה הקודמת כ-baseline,
#  כי airtable_schema.py מכיל רק שמות שדות, לא סוגים.)

from __future__ import annotations

import inspect
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import airtable_schema  # noqa: E402
from schema_audit import TABLE_CLASS_MAP, _class_values  # noqa: E402

_REPORT_PATH = Path(__file__).resolve().parent.parent / "schema_drift_report.json"

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

_ICONS = {SEVERITY_ERROR: "❌", SEVERITY_WARNING: "⚠️ "}

_SELECT_TYPES = {"singleSelect", "multipleSelects"}


def fetch_live_schema(base_id: str, api_key: str) -> dict:
    """שולף schema חי מ-Airtable Metadata API. קריאה בלבד, אין כתיבה."""
    import httpx

    r = httpx.get(
        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def _load_previous_report() -> dict | None:
    if not _REPORT_PATH.exists():
        return None
    try:
        return json.loads(_REPORT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _previous_field_types(previous: dict | None, table_name: str) -> dict[str, str]:
    if not previous:
        return {}
    return previous.get("field_types", {}).get(table_name, {})


def compare_table(
    table_name: str,
    code_fields: set[str],
    live_fields: list[dict],
    previous_types: dict[str, str],
) -> tuple[list[dict], dict[str, str]]:
    """
    משווה שדות קוד מול שדות live עבור טבלה אחת.
    מחזיר (findings, current_field_types) — current_field_types נשמר כ-baseline לריצה הבאה.
    """
    findings: list[dict] = []
    current_types: dict[str, str] = {}

    live_by_exact = {f["name"]: f for f in live_fields}
    live_by_stripped: dict[str, dict] = {}
    for f in live_fields:
        live_by_stripped.setdefault(f["name"].strip(), f)

    matched_live_names: set[str] = set()

    for code_name in sorted(code_fields):
        if code_name in live_by_exact:
            matched_live_names.add(code_name)
            continue
        stripped_match = live_by_stripped.get(code_name.strip())
        if stripped_match is not None:
            matched_live_names.add(stripped_match["name"])
            findings.append(
                {
                    "table": table_name,
                    "field": stripped_match["name"],
                    "severity": SEVERITY_WARNING,
                    "message": f'trailing/leading space בשם השדה ב-Airtable (קוד: "{code_name}")',
                }
            )
            continue
        findings.append(
            {
                "table": table_name,
                "field": code_name,
                "severity": SEVERITY_ERROR,
                "message": "קיים בקוד, לא קיים ב-Airtable",
            }
        )

    for f in live_fields:
        name = f["name"]
        field_type = f.get("type", "")
        current_types[name] = field_type

        if name not in matched_live_names and name.strip() not in code_fields:
            findings.append(
                {
                    "table": table_name,
                    "field": name,
                    "severity": SEVERITY_WARNING,
                    "message": "קיים ב-Airtable, לא קיים בקוד",
                }
            )

        prev_type = previous_types.get(name)
        if prev_type and field_type and prev_type != field_type:
            findings.append(
                {
                    "table": table_name,
                    "field": name,
                    "severity": SEVERITY_ERROR,
                    "message": f'סוג שדה השתנה: "{prev_type}" → "{field_type}"',
                }
            )

        if field_type in _SELECT_TYPES:
            for choice in f.get("options", {}).get("choices", []):
                choice_name = choice.get("name", "")
                if choice_name != choice_name.strip():
                    findings.append(
                        {
                            "table": table_name,
                            "field": name,
                            "severity": SEVERITY_WARNING,
                            "message": f'trailing/leading space ב-select option: "{choice_name}"',
                        }
                    )

    return findings, current_types


def run_governance(live_schema: dict, previous_report: dict | None = None) -> dict:
    """
    מריץ את ההשוואה על כל הטבלאות ב-TABLE_CLASS_MAP.
    מחזיר את ה-report dict המלא (לפני כתיבה לדיסק).
    """
    live_tables_by_name = {t["name"]: t for t in live_schema.get("tables", [])}

    all_findings: list[dict] = []
    field_types: dict[str, dict[str, str]] = {}
    table_summaries: list[dict] = []

    for table_name, fields_class in TABLE_CLASS_MAP.items():
        code_fields = _class_values(fields_class)
        live_table = live_tables_by_name.get(table_name)

        if live_table is None:
            all_findings.append(
                {
                    "table": table_name,
                    "field": None,
                    "severity": SEVERITY_ERROR,
                    "message": "הטבלה לא קיימת ב-Airtable (live)",
                }
            )
            table_summaries.append({"table": table_name, "ok": 0, "total": len(code_fields)})
            continue

        live_fields = live_table.get("fields", [])
        previous_types = _previous_field_types(previous_report, table_name)

        findings, current_types = compare_table(table_name, code_fields, live_fields, previous_types)
        all_findings.extend(findings)
        field_types[table_name] = current_types

        error_or_warning_fields = {f["field"] for f in findings if f["field"] in code_fields}
        ok_count = len(code_fields) - len(error_or_warning_fields)
        table_summaries.append({"table": table_name, "ok": ok_count, "total": len(code_fields)})

    error_count = sum(1 for f in all_findings if f["severity"] == SEVERITY_ERROR)
    warning_count = sum(1 for f in all_findings if f["severity"] == SEVERITY_WARNING)

    return {
        "generated_at": date.today().isoformat(),
        "tables_checked": list(TABLE_CLASS_MAP.keys()),
        "table_summaries": table_summaries,
        "findings": all_findings,
        "field_types": field_types,
        "summary": {
            "total": len(all_findings),
            "errors": error_count,
            "warnings": warning_count,
        },
    }


def find_unregistered_field_classes() -> list[dict]:
    """
    מוצא *Fields classes שמוגדרים ב-airtable_schema.py אך לא רשומים ב-TABLE_CLASS_MAP
    (schema_audit.py). אלה לא נבדקים כלל מול live Airtable — לא בלולאה הראשית של
    run_governance, כיוון שהיא מבוססת רק על TABLE_CLASS_MAP.items(). זה הפער שאיפשר
    ל-MediaFileFields (F16) לעבור בשתיקה: הטבלה נוצרה ב-Airtable עם שדה "Domain" אבל
    הקוד כתב "domain" — ה-CI לא תפס את זה כי הטבלה לא היתה רשומה ב-TABLE_CLASS_MAP.
    """
    registered = set(TABLE_CLASS_MAP.values())
    findings: list[dict] = []
    for name, cls in inspect.getmembers(airtable_schema, inspect.isclass):
        if cls.__module__ != airtable_schema.__name__:
            continue
        if not name.endswith("Fields"):
            continue
        if cls in registered:
            continue
        findings.append(
            {
                "table": name,
                "field": None,
                "severity": SEVERITY_ERROR,
                "message": "מוגדר ב-airtable_schema.py אך לא רשום ב-TABLE_CLASS_MAP (schema_audit.py) — לא נבדק מול live Airtable",
            }
        )
    return findings


def print_report(report: dict) -> None:
    today_str = date.fromisoformat(report["generated_at"]).strftime("%d/%m/%Y")
    print("🔍 BOSS Schema Governance Report — " + today_str)
    print("━" * 43)

    findings_by_table: dict[str, list[dict]] = {}
    for f in report["findings"]:
        findings_by_table.setdefault(f["table"], []).append(f)

    known_tables = {summary["table"] for summary in report["table_summaries"]}

    for summary in report["table_summaries"]:
        table_name = summary["table"]
        print(f"✅ {table_name} — {summary['ok']}/{summary['total']} שדות תקינים")
        for f in findings_by_table.get(table_name, []):
            icon = _ICONS[f["severity"]]
            field_part = f'."{f["field"]}"' if f["field"] else ""
            print(f'{icon} {table_name}{field_part} — {f["message"]}')

    for table_name, findings in findings_by_table.items():
        if table_name in known_tables:
            continue
        for f in findings:
            icon = _ICONS[f["severity"]]
            print(f'{icon} {table_name} — {f["message"]}')

    print("━" * 43)
    s = report["summary"]
    print(f"סיכום: {s['total']} drift items נמצאו")
    print(f"       {s['errors']} קריטי | {s['warnings']} warning")


def main() -> int:
    api_key = os.environ.get("AIRTABLE_API_KEY", "")
    base_id = os.environ.get("AIRTABLE_BASE_ID", "")
    if not api_key or not base_id:
        print("❌ AIRTABLE_API_KEY / AIRTABLE_BASE_ID חסרים ב-env", file=sys.stderr)
        return 1

    previous_report = _load_previous_report()
    live_schema = fetch_live_schema(base_id, api_key)
    report = run_governance(live_schema, previous_report)

    report["findings"].extend(find_unregistered_field_classes())
    report["summary"] = {
        "total": len(report["findings"]),
        "errors": sum(1 for f in report["findings"] if f["severity"] == SEVERITY_ERROR),
        "warnings": sum(1 for f in report["findings"] if f["severity"] == SEVERITY_WARNING),
    }

    print_report(report)
    _REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 1 if report["summary"]["errors"] > 0 else 0


def _self_test() -> None:
    """בודק את לוגיקת ההשוואה על mock schema — אין קריאות רשת."""

    class _MockFields:
        A = "Name"
        B = "Business Outcome"
        C = "Tier"

    mock_table_class_map = {"MockTable": _MockFields}

    live_schema = {
        "tables": [
            {
                "name": "MockTable",
                "fields": [
                    {"id": "f1", "name": "Name", "type": "singleLineText"},
                    {"id": "f2", "name": "Business Outcome ", "type": "singleSelect",
                     "options": {"choices": [{"id": "c1", "name": "Won "}, {"id": "c2", "name": "Lost"}]}},
                    {"id": "f3", "name": "Extra Live Field", "type": "singleLineText"},
                ],
            }
        ]
    }

    global TABLE_CLASS_MAP
    original_map = TABLE_CLASS_MAP
    TABLE_CLASS_MAP = mock_table_class_map
    try:
        report = run_governance(live_schema, previous_report=None)
    finally:
        TABLE_CLASS_MAP = original_map

    messages = [f["message"] for f in report["findings"]]
    severities = {f["field"]: f["severity"] for f in report["findings"]}

    assert any("trailing/leading space בשם השדה" in m for m in messages), "expected field-name trailing-space WARNING"
    assert severities.get("Tier") == SEVERITY_ERROR, "expected 'Tier' missing-from-live ERROR"
    assert any("קיים ב-Airtable, לא קיים בקוד" in m for m in messages), "expected live-only field WARNING"
    assert any("select option" in m for m in messages), "expected select-option trailing-space WARNING"
    assert report["summary"]["errors"] == 1
    assert report["summary"]["warnings"] == 3

    previous_report = {"field_types": {"MockTable": {"Name": "singleLineText"}}}
    live_schema_type_changed = {
        "tables": [
            {
                "name": "MockTable",
                "fields": [{"id": "f1", "name": "Name", "type": "singleSelect", "options": {"choices": []}}],
            }
        ]
    }
    TABLE_CLASS_MAP = mock_table_class_map
    try:
        report2 = run_governance(live_schema_type_changed, previous_report=previous_report)
    finally:
        TABLE_CLASS_MAP = original_map

    type_change_findings = [f for f in report2["findings"] if "סוג שדה השתנה" in f["message"]]
    assert len(type_change_findings) == 1, "expected exactly one type-changed ERROR"
    assert type_change_findings[0]["severity"] == SEVERITY_ERROR

    print("✅ schema_governance self-test: 6/6 assertions passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
        sys.exit(0)
    sys.exit(main())
