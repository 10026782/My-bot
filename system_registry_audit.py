"""CORE_03_GOVERNANCE Phase 1: read-only System Registry audit."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "system_registry.yaml"
REPORTS_DIR = ROOT / "reports"
JSON_REPORT = REPORTS_DIR / "system_registry_report.json"
MD_REPORT = REPORTS_DIR / "system_registry_report.md"

VALID_STATUSES = {"OK", "EMPTY", "MISSING", "BROKEN"}


def _parse_list_block(lines: list[str], start_key: str) -> list[dict[str, Any]]:
    """Small YAML subset parser for this registry shape."""
    items: list[dict[str, Any]] = []
    in_block = False
    current: dict[str, Any] | None = None
    current_list_key: str | None = None

    for raw in lines:
        line = raw.rstrip()
        if line == f"{start_key}:":
            in_block = True
            continue
        if in_block and line and not line.startswith(" ") and not line.startswith("-"):
            break
        if not in_block:
            continue

        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- id:"):
            if current:
                items.append(current)
            current = {"id": stripped.split(":", 1)[1].strip()}
            current_list_key = None
            continue
        if current is None:
            continue
        if stripped.startswith("- ") and current_list_key:
            current.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "[]":
                current[key] = []
                current_list_key = key
            elif value:
                current[key] = value
                current_list_key = None
            else:
                current[key] = []
                current_list_key = key

    if current:
        items.append(current)
    return items


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"services": [], "airtable_tables": [], "load_status": "MISSING"}

    text = REGISTRY_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    return {
        "services": _parse_list_block(lines, "services"),
        "airtable_tables": _parse_list_block(lines, "airtable_tables"),
        "load_status": "OK" if text.strip() else "EMPTY",
    }


def _status_from_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "EMPTY"
    if any(item.get("status") == "BROKEN" for item in items):
        return "BROKEN"
    if any(item.get("status") == "MISSING" for item in items):
        return "MISSING"
    return "OK"


def _fetch_airtable_schema() -> tuple[str, dict[str, set[str]], str]:
    key = os.environ.get("AIRTABLE_API_KEY", "").strip()
    base = os.environ.get("AIRTABLE_BASE_ID", "").strip()
    if not key or not base:
        return "MISSING", {}, "AIRTABLE_API_KEY or AIRTABLE_BASE_ID missing"

    try:
        response = httpx.get(
            f"https://api.airtable.com/v0/meta/bases/{base}/tables",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
    except Exception as exc:
        return "BROKEN", {}, f"Airtable metadata request failed: {type(exc).__name__}"

    if response.status_code != 200:
        return "BROKEN", {}, f"Airtable metadata returned HTTP {response.status_code}"

    tables = response.json().get("tables", [])
    if not tables:
        return "EMPTY", {}, "Airtable metadata returned zero tables"

    by_name: dict[str, set[str]] = {}
    for table in tables:
        by_name[table.get("name", "")] = {field.get("name", "") for field in table.get("fields", [])}
    return "OK", by_name, f"Airtable metadata reachable; tables={len(by_name)}"


def audit_registry() -> dict[str, Any]:
    registry = load_registry()
    services = registry["services"]
    expected_tables = registry["airtable_tables"]
    airtable_status, airtable_schema, airtable_detail = _fetch_airtable_schema()

    env_checks = []
    for service in services:
        env_names = service.get("env", [])
        missing = [name for name in env_names if not os.environ.get(name, "").strip()]
        env_checks.append({
            "id": service.get("id", ""),
            "name": service.get("name", ""),
            "status": "MISSING" if missing else "OK",
            "missing_env": missing,
        })

    table_checks = []
    for table in expected_tables:
        name = table.get("name", "")
        expected_fields = table.get("critical_fields", [])
        if airtable_status != "OK":
            status = airtable_status
            missing_fields = expected_fields
            detail = airtable_detail
        elif name not in airtable_schema:
            status = "MISSING"
            missing_fields = expected_fields
            detail = "table missing in Airtable metadata"
        else:
            existing_fields = airtable_schema[name]
            missing_fields = [field for field in expected_fields if field not in existing_fields]
            status = "MISSING" if missing_fields else "OK"
            detail = "critical fields present" if not missing_fields else "critical fields missing"

        table_checks.append({
            "id": table.get("id", ""),
            "name": name,
            "status": status,
            "missing_fields": missing_fields,
            "detail": detail,
        })

    sections = {
        "registry": registry["load_status"],
        "environment": _status_from_items(env_checks),
        "airtable": airtable_status,
        "tables": _status_from_items(table_checks),
    }
    overall = "OK"
    if "BROKEN" in sections.values():
        overall = "BROKEN"
    elif "MISSING" in sections.values():
        overall = "MISSING"
    elif "EMPTY" in sections.values():
        overall = "EMPTY"

    return {
        "status": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_path": str(REGISTRY_PATH),
        "sections": sections,
        "airtable_detail": airtable_detail,
        "env_checks": env_checks,
        "table_checks": table_checks,
    }


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# System Registry Audit",
        "",
        f"Status: {report['status']}",
        f"Generated: {report['generated_at']}",
        "",
        "## Sections",
    ]
    for name, status in report["sections"].items():
        lines.append(f"- {name}: {status}")

    lines.extend(["", "## Airtable", f"- {report['airtable_detail']}", "", "## Environment"])
    for item in report["env_checks"]:
        missing = ", ".join(item["missing_env"]) if item["missing_env"] else "none"
        lines.append(f"- {item['status']} {item['id']} ({item['name']}): missing={missing}")

    lines.extend(["", "## Tables"])
    for item in report["table_checks"]:
        missing = ", ".join(item["missing_fields"]) if item["missing_fields"] else "none"
        lines.append(f"- {item['status']} {item['name']}: {item['detail']}; missing_fields={missing}")

    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    MD_REPORT.write_text(format_markdown(report), encoding="utf-8")


def main() -> None:
    report = audit_registry()
    write_reports(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
