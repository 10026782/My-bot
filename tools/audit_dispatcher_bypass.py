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
import subprocess
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

# Baseline rebased on 2026-08-24 (Track D-Structure Audit #7): all 43 entries
# known as of 2026-07-03 were individually re-verified against current
# origin/main. 41 were still-live direct-import bypass sites (20 unchanged,
# 21 at shifted line numbers from unrelated code growth elsewhere in their
# files); 2 were genuinely resolved (furniture_lead_funnel.py:152 — import
# removed entirely; inbound_handler.py:91 — consolidated into the existing
# shared _airtable_get() helper, already covered by inbound_handler.py:34)
# and are dropped here. 8 additional direct-import sites found during this
# re-verification are NOT in this baseline — they are genuinely new since
# 2026-07-03 and are left to surface as WARN_NEW for separate triage, not
# silently accepted. Full history of the 2026-07-03 entries and this
# re-verification is preserved in git log, not duplicated here as comments.
BASELINE: frozenset[tuple[str, int, str]] = frozenset({
    ("abandoned_lead_worker.py", 101, "tools.airtable_tools"),
    ("abandoned_lead_worker.py", 246, "tools.airtable_tools"),
    ("ad_attribution.py", 169, "tools.airtable_tools"),
    ("ad_attribution.py", 196, "tools.airtable_tools"),
    ("ad_attribution.py", 378, "tools.airtable_tools"),
    ("audience_intelligence.py", 136, "tools.airtable_tools"),
    ("cmd_decision.py", 267, "tools.contact_resolver"),
    ("cmd_update.py", 548, "tools.airtable_tools"),
    ("core/lead_buffer.py", 132, "tools.airtable_tools"),
    ("data_engines.py", 82, "tools.airtable_tools"),
    ("data_engines.py", 144, "tools.airtable_tools"),
    ("data_engines.py", 203, "tools.airtable_tools"),
    ("decision_ports.py", 91, "tools.contact_resolver"),
    ("drive_adapter.py", 19, "tools.google_tools"),
    ("email_inbound.py", 82, "tools.google_tools"),
    ("inbound_handler.py", 34, "tools.airtable_tools"),
    ("inbound_handler.py", 102, "tools.airtable_tools"),
    ("interaction_engine.py", 102, "tools.calendar_tools"),
    ("interaction_engine.py", 304, "tools.airtable_tools"),
    ("interaction_engine.py", 342, "tools.airtable_tools"),
    ("interaction_engine.py", 357, "tools.airtable_tools"),
    ("interaction_engine.py", 385, "tools.airtable_tools"),
    ("interaction_engine.py", 565, "tools.calendar_tools"),
    ("lead_capture.py", 131, "tools.airtable_tools"),
    ("lead_capture.py", 211, "tools.airtable_tools"),
    ("lead_memory.py", 167, "tools.airtable_tools"),
    ("providers/airtable_shim.py", 17, "tools.airtable_tools"),
    ("session_store.py", 502, "tools.airtable_tools"),
    ("session_store.py", 614, "tools.airtable_tools"),
    ("session_store.py", 645, "tools.airtable_tools"),
    ("session_store.py", 705, "tools.airtable_tools"),
    ("tenant_provisioner.py", 160, "tools.airtable_tools"),
    ("tenant_provisioner.py", 225, "tools.airtable_tools"),
    ("tenant_provisioner.py", 252, "tools.airtable_tools"),
    ("tenant_provisioner.py", 283, "tools.airtable_tools"),
    ("voice_adapter.py", 242, "tools.airtable_tools"),
    ("core/lead_recovery.py", 76, "crm"),
    ("lead_conversion.py", 20, "crm"),
    ("payment_reminder.py", 98, "crm"),
    ("payment_reminder.py", 167, "crm"),
    ("tools/contact_resolver.py", 133, "crm"),
})

# Exact call sites verified sanctioned despite failing _is_allowed()'s
# filename-substring heuristic -- each is imported and invoked by a module
# that IS on the allowlist, just not itself named dispatcher*/scheduler*/etc.
# Verified by direct caller-graph read (Track D-Structure Audit #7), not a
# guess:
#   - tools/approval_actions.py:365 -- tools/dispatcher.py:26 does
#     `from . import approval_actions`; its dispatch switch at
#     tools/dispatcher.py:497 calls approval_actions.tma_write(), whose
#     "post" branch contains this `import crm`.
#   - tools/schema_snapshot.py:286 -- scheduler.py:66 imports and calls
#     run_snapshot_archive() (scheduled at scheduler.py:857), which calls
#     apply_retention_policy() at tools/schema_snapshot.py:265, containing
#     this `import tools.airtable_tools`.
# Unlike BASELINE (known offenders not yet fixed), these are not bypass
# debt -- they are permanently excluded from findings, never surfaced as
# WARN_NEW, and never need baselining.
_SANCTIONED_CALL_SITES: frozenset[tuple[str, int, str]] = frozenset({
    ("tools/approval_actions.py", 365, "crm"),
    ("tools/schema_snapshot.py", 286, "tools.airtable_tools"),
})


class ScanBoundaryError(RuntimeError):
    """Raised when the tracked-file boundary can't be determined — fail closed
    rather than falling back to an unsafe filesystem walk (see #7 dispatcher-bypass
    scan-boundary remediation: rglob() previously picked up untracked files and
    non-dot-prefixed nested checkouts)."""


def _iter_py_files():
    """Enumerates *.py files tracked by this repository's git index. Untracked
    files and nested/sibling checkouts are never scanned, regardless of where
    they sit under _REPO_ROOT."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.py"],
            cwd=_REPO_ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ScanBoundaryError(
            f"audit_dispatcher_bypass: 'git ls-files' failed, refusing to scan "
            f"the filesystem as a fallback: {exc}"
        ) from exc

    for rel_str in result.stdout.decode("utf-8").split("\0"):
        if not rel_str:
            continue
        rel = Path(rel_str)
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
    return [f for f in findings if f not in _SANCTIONED_CALL_SITES]


def main() -> int:
    try:
        found = scan()
    except ScanBoundaryError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
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
