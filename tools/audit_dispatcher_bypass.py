#!/usr/bin/env python3
# tools/audit_dispatcher_bypass.py
#
# Static, read-only audit: finds direct imports of tool-implementation
# modules (tools.airtable_tools, tools.gmail_tools, tools.calendar_tools,
# tools.drive_tools, tools.sheets_tools, tools.google_tools,
# tools.contact_resolver) or the CRM repository (`crm`) from outside the
# sanctioned dispatch/scheduling path. Per CLAUDE.md: "Never import tool
# functions (e.g. from crm or airtable_tools) directly outside of the
# dispatcher/digest/scheduler/collector modules — this bypasses identity
# and tenant enforcement." Same intent as the manual grep in
# docs/governance/SECURITY_CHECKLIST.md ("סריקה מהירה" section), automated
# here as a warning-only CI inventory alongside audit_gateway_bypass.py /
# audit_result_parsing.py (F52 Safe Refactor #6/#7).
#
# This does NOT move any import and does NOT fail CI — it is a warning-only
# inventory. It compares live results against a known BASELINE; anything new
# is flagged so scope drift gets noticed instead of silently growing.
#
# NOTE ON BASELINE PROVENANCE: this baseline was derived by actually running
# this scan against the repo on 2026-07-03.
#
# שימוש: python3 tools/audit_dispatcher_bypass.py

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

_EXCLUDE_DIRS = {".git", "node_modules", "tma-frontend", "__pycache__", ".venv", "venv"}
# Leftover local worktree checkouts (e.g. .c81-ci-path-20260702, .codex-*) —
# not part of the live repo tree, would otherwise duplicate every finding
# once per stale worktree copy left on disk.
_EXCLUDE_DIR_PREFIXES = (".",)
_EXCLUDE_FILE_PREFIXES = ("test_",)
_EXCLUDE_FILES = {
    "tools/audit_gateway_bypass.py",
    "tools/audit_result_parsing.py",
    "tools/audit_dispatcher_bypass.py",
}

# Modules allowed to import tool implementations directly, per CLAUDE.md's
# "dispatcher/digest/scheduler/collector" exception — matched the same way
# as the manual grep in docs/governance/SECURITY_CHECKLIST.md
# (`grep -v "dispatcher\|daily_digest\|daily_collector\|scheduler"`).
_ALLOWED_NAME_SUBSTRINGS = ("dispatcher", "daily_digest", "daily_collector", "scheduler")

_TOOL_MODULES = (
    "airtable_tools", "gmail_tools", "calendar_tools",
    "drive_tools", "sheets_tools", "google_tools", "contact_resolver",
)
_TOOLS_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+tools\.(" + "|".join(_TOOL_MODULES) + r")\s+import\b"
    r"|import\s+tools\.(" + "|".join(_TOOL_MODULES) + r")\b)"
)
_CRM_IMPORT_RE = re.compile(r"^\s*(?:from\s+crm\s+import\b|import\s+crm\b)")

# Known offenders as of 2026-07-03 (file relative to repo root, line, module).
BASELINE: frozenset[tuple[str, int, str]] = frozenset({
    ("abandoned_lead_worker.py", 101, "tools.airtable_tools"),
    ("abandoned_lead_worker.py", 246, "tools.airtable_tools"),
    ("ad_attribution.py", 168, "tools.airtable_tools"),
    ("ad_attribution.py", 188, "tools.airtable_tools"),
    ("ad_attribution.py", 355, "tools.airtable_tools"),
    ("audience_intelligence.py", 136, "tools.airtable_tools"),
    ("cmd_decision.py", 263, "tools.contact_resolver"),
    ("cmd_update.py", 251, "tools.airtable_tools"),
    ("core/lead_buffer.py", 132, "tools.airtable_tools"),
    ("data_engines.py", 82, "tools.airtable_tools"),
    ("data_engines.py", 144, "tools.airtable_tools"),
    ("data_engines.py", 203, "tools.airtable_tools"),
    ("decision_ports.py", 88, "tools.contact_resolver"),
    ("drive_adapter.py", 19, "tools.google_tools"),
    ("email_inbound.py", 82, "tools.google_tools"),
    ("furniture_lead_funnel.py", 152, "tools.airtable_tools"),
    ("inbound_handler.py", 34, "tools.airtable_tools"),
    ("inbound_handler.py", 91, "tools.airtable_tools"),
    ("inbound_handler.py", 115, "tools.airtable_tools"),
    ("interaction_engine.py", 102, "tools.calendar_tools"),
    ("interaction_engine.py", 287, "tools.airtable_tools"),
    ("interaction_engine.py", 327, "tools.airtable_tools"),
    ("interaction_engine.py", 342, "tools.airtable_tools"),
    ("interaction_engine.py", 370, "tools.airtable_tools"),
    ("interaction_engine.py", 550, "tools.calendar_tools"),
    ("lead_capture.py", 130, "tools.airtable_tools"),
    ("lead_capture.py", 210, "tools.airtable_tools"),
    ("lead_memory.py", 167, "tools.airtable_tools"),
    ("providers/airtable_shim.py", 18, "tools.airtable_tools"),
    ("session_store.py", 308, "tools.airtable_tools"),
    ("session_store.py", 396, "tools.airtable_tools"),
    ("session_store.py", 442, "tools.airtable_tools"),
    ("session_store.py", 494, "tools.airtable_tools"),
    ("tenant_provisioner.py", 160, "tools.airtable_tools"),
    ("tenant_provisioner.py", 225, "tools.airtable_tools"),
    ("tenant_provisioner.py", 252, "tools.airtable_tools"),
    ("tenant_provisioner.py", 280, "tools.airtable_tools"),
    ("voice_adapter.py", 233, "tools.airtable_tools"),
    ("core/lead_recovery.py", 76, "crm"),
    ("lead_conversion.py", 21, "crm"),
    ("payment_reminder.py", 98, "crm"),
    ("payment_reminder.py", 167, "crm"),
    ("tools/contact_resolver.py", 133, "crm"),
})


def _iter_py_files():
    for path in _REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(_REPO_ROOT)
        if any(part in _EXCLUDE_DIRS for part in rel.parts):
            continue
        if any(part.startswith(_EXCLUDE_DIR_PREFIXES) for part in rel.parts[:-1]):
            continue
        if rel.name.startswith(_EXCLUDE_FILE_PREFIXES):
            continue
        yield rel


def _is_allowed(rel_str: str) -> bool:
    return any(sub in rel_str for sub in _ALLOWED_NAME_SUBSTRINGS)


def scan() -> list[tuple[str, int, str]]:
    """Returns list of (relative_path_str, line_no, module) for direct
    tool-implementation / crm imports found outside allowed modules."""
    findings: list[tuple[str, int, str]] = []
    for rel in _iter_py_files():
        rel_str = rel.as_posix()
        if rel_str in _EXCLUDE_FILES or _is_allowed(rel_str):
            continue
        try:
            text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for idx, line in enumerate(text.splitlines()):
            m = _TOOLS_IMPORT_RE.match(line)
            if m:
                module = "tools." + (m.group(1) or m.group(2))
                findings.append((rel_str, idx + 1, module))
                continue
            if _CRM_IMPORT_RE.match(line):
                findings.append((rel_str, idx + 1, "crm"))
    return findings


def main() -> int:
    found = scan()
    found_keys = {(f, l, m) for f, l, m in found}

    print("GOV — Dispatcher Bypass Audit (direct tool-implementation imports)")
    print("-" * 60)

    for file, line, module in sorted(found):
        is_new = (file, line, module) not in BASELINE
        marker = "WARN_NEW" if is_new else "known   "
        print(f"{marker}  {file}:{line}  import {module}")

    missing = sorted(BASELINE - found_keys)
    for file, line, module in missing:
        print(f"RESOLVED  no longer present (fixed?)  {file}:{line}  import {module}")

    new_count = len(found_keys - BASELINE)
    print("-" * 60)
    print(f"Summary: {len(found)} direct import(s) found outside dispatcher/digest/scheduler/collector, "
          f"{new_count} new (not in baseline), {len(missing)} resolved since baseline.")

    if new_count:
        print("Warning-only: new import bypass site(s) found outside the baseline. "
              "Not blocking CI, but verify whether this is expected scope growth "
              "(see CLAUDE.md 'Tool execution' section / docs/governance/SECURITY_CHECKLIST.md).")

    return 0  # warning-only — never blocks CI


def _self_test() -> None:
    assert _TOOLS_IMPORT_RE.match("from tools.airtable_tools import airtable_get")
    assert _TOOLS_IMPORT_RE.match("        from tools.gmail_tools import gmail_send_draft  # type: ignore")
    assert _TOOLS_IMPORT_RE.match("import tools.calendar_tools")
    assert not _TOOLS_IMPORT_RE.match("    # from tools.airtable_tools import airtable_get")
    assert not _TOOLS_IMPORT_RE.match("from .airtable_tools import airtable_get")
    assert not _TOOLS_IMPORT_RE.match("from tools.airtable_gateway import post_to_airtable")

    assert _CRM_IMPORT_RE.match("from crm import crm_add_contact")
    assert _CRM_IMPORT_RE.match("    import crm")
    assert not _CRM_IMPORT_RE.match("    # from crm import crm_add_contact")
    assert not _CRM_IMPORT_RE.match("from crm_extra import something")

    assert _is_allowed("tools/dispatcher.py")
    assert _is_allowed("scheduler.py")
    assert not _is_allowed("abandoned_lead_worker.py")

    print("audit_dispatcher_bypass self-test: 12/12 assertions passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
        sys.exit(0)
    sys.exit(main())
