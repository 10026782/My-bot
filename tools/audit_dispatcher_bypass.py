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
# This does NOT move any import. It compares live results against explicit
# classifications; only genuinely NEW findings fail CI. Legacy debt remains
# visible, while cross-track and accepted findings are kept out of BASELINE.
#
# NOTE ON BASELINE PROVENANCE: this baseline was derived by actually running
# this scan against the repo on 2026-07-03.
#
# שימוש: python3 tools/audit_dispatcher_bypass.py

from __future__ import annotations

import re
import ast
import subprocess
import sys
from dataclasses import dataclass
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

_CONTACT_TABLE_NAMES = frozenset(("Contacts", "אנשי קשר (Contacts)"))
_CONTACT_WRITE_NAMES = frozenset((
    "airtable_add", "airtable_update", "airtable_create", "airtable_patch",
))
_GENERIC_WRITE_NAMES = frozenset(("create", "update"))
_CONTACT_BOUNDARY_FUNCTIONS = frozenset((
    "create_contact_from_fields", "update_contact",
))

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
    # Shifted again by the BUG-SESSION-DUP-RAM additions (04/09/2026, PR
    # #1203 review follow-up: set_request_channel()/_ram_key()/
    # _strip_ram_key() and their docstrings/comment block) — same 4
    # existing import statements as before (_sync_to_db(),
    # _find_best_session_in_db(), _load_from_db(), _delete_from_db()), not a
    # new bypass authority.
    ("session_store.py", 676, "tools.airtable_tools"),
    ("session_store.py", 834, "tools.airtable_tools"),
    ("session_store.py", 875, "tools.airtable_tools"),
    ("session_store.py", 937, "tools.airtable_tools"),
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

# These are intentionally not merged into BASELINE. They are active
# cross-track handoffs and must remain visible as their own class.
CROSS_TRACK: frozenset[tuple[str, int, str]] = frozenset({
    ("core/google_drive_artifact_store.py", 32, "tools.google_tools"),
    ("core/memory_retrieval.py", 107, "tools.airtable_tools"),
    ("core/runtime_schema_provider.py", 204, "tools.airtable_tools"),
    ("core/turn_coordinator_runtime.py", 73, "tools.airtable_tools"),
    # core/reasoning_ports.py is the ReasoningPorts adapter layer (own
    # docstring: engines import only from this file, never providers
    # directly) — same architectural role as the two entries above.
    # Callers are gated behind FEATURE_DECISION_HUB/FEATURE_CORE_REASONING_LEADS_STATE
    # (both off by default), same reachability profile as the other
    # CROSS_TRACK adapter entries here.
    ("core/reasoning_ports.py", 158, "tools.contact_resolver"),
})

# Verification-only staging utility; it is legitimate but not a runtime
# dispatcher exception and must remain separately visible.
ACCEPTED: frozenset[tuple[str, int, str]] = frozenset({
    ("scripts/verify_f15_staging.py", 143, "crm"),
    # Explicit owner review for the standalone commercial Deal/Payment
    # implementation (PR #1104): this imports only the legacy result-shape
    # helper; all provider writes go through tools.airtable_gateway. The
    # module has no current callers and is not registered in the dispatcher,
    # so this is not a reachable dispatcher bypass. Keep the exact call site
    # visible as ACCEPTED rather than hiding it in the legacy baseline.
    ("commercial_crm.py", 37, "tools.airtable_tools"),
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
#   - tools/approval_actions.py:398 -- tools/dispatcher.py:26 does
#     `from . import approval_actions`; its dispatch switch at
#     tools/dispatcher.py:497 calls approval_actions.tma_write(), whose
#     "patch" branch contains the B2-02 Contact UPDATE `import crm`.
#     (Shifted from line 395 by BUG-CONTACT-03's 3-line insertion earlier
#     in the "post" branch, 01/09/2026 -- exactly the (file, line, module)
#     baseline fragility this script's own C05-C07 audit refresh already
#     documented; the call site itself is unchanged, only its line moved.)
#   - tools/schema_snapshot.py:286 -- scheduler.py:66 imports and calls
#     run_snapshot_archive() (scheduled at scheduler.py:857), which calls
#     apply_retention_policy() at tools/schema_snapshot.py:265, containing
#     this `import tools.airtable_tools`.
# Unlike BASELINE (known offenders not yet fixed), these are not bypass
# debt -- they are permanently excluded from findings, never surfaced as
# WARN_NEW, and never need baselining.
_SANCTIONED_CALL_SITES: frozenset[tuple[str, int, str]] = frozenset({
    ("tools/approval_actions.py", 365, "crm"),
    ("tools/approval_actions.py", 398, "crm"),
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


def _contact_table_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value in _CONTACT_TABLE_NAMES
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Tables"
        and node.attr == "CONTACTS"
    )


def _contact_table_argument(node: ast.Call) -> ast.AST | None:
    if node.args:
        return node.args[0]
    for keyword in node.keywords:
        if keyword.arg == "table":
            return keyword.value
    return None


class _ContactWriteVisitor(ast.NodeVisitor):
    def __init__(self, rel_str: str):
        self.rel_str = rel_str
        self.function_stack: list[str] = []
        self.findings: list[tuple[str, int, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        table_arg = _contact_table_argument(node)
        if table_arg is not None and _contact_table_literal(table_arg):
            target = node.func
            name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else ""
            direct_generic = name in _CONTACT_WRITE_NAMES
            receiver_parts: list[str] = []
            receiver = target.value if isinstance(target, ast.Attribute) else None
            while isinstance(receiver, ast.Attribute):
                receiver_parts.append(receiver.attr.lower())
                receiver = receiver.value
            if isinstance(receiver, ast.Name):
                receiver_parts.append(receiver.id.lower())
            provider_generic = (
                name in _GENERIC_WRITE_NAMES
                and any(any(token in part for token in ("storage", "provider", "airtable")) for part in receiver_parts)
            )
            if (direct_generic or provider_generic) and not (
                self.rel_str == "crm.py"
                and self.function_stack[-1:] and self.function_stack[-1] in _CONTACT_BOUNDARY_FUNCTIONS
            ):
                self.findings.append((self.rel_str, node.lineno, name))
        self.generic_visit(node)


def scan_contact_bypasses() -> list[tuple[str, int, str]]:
    """Find literal Contact writes outside the two canonical CRM boundaries."""
    findings: list[tuple[str, int, str]] = []
    for rel in _iter_py_files():
        rel_str = rel.as_posix()
        if rel_str in _EXCLUDE_FILES or rel.name.startswith(_EXCLUDE_FILE_PREFIXES):
            continue
        try:
            tree = ast.parse(((_REPO_ROOT / rel).read_text(encoding="utf-8")), filename=rel_str)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        visitor = _ContactWriteVisitor(rel_str)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    return findings


def _module_from_line(line: str) -> str | None:
    match = _TOOLS_IMPORT_RE.match(line)
    if match:
        return "tools." + (match.group(1) or match.group(2))
    if _CRM_IMPORT_RE.match(line):
        return "crm"
    return None


def _imported_symbol(line: str) -> str:
    """Return the first imported symbol, which is stable across line shifts."""
    match = re.match(r"^\s*from\s+\S+\s+import\s+(.+?)(?:\s+#.*)?$", line)
    return match.group(1).strip().split(",", 1)[0].strip() if match else "*"


def _stable_identity(finding: tuple[str, int, str]) -> tuple[str, str, str, int]:
    """Return path/module/symbol/ordinal identity, independent of line number.

    The ordinal matters when a file contains two imports of the same module and
    symbol: moving the old import must be tolerated, while adding a second one
    must remain a new finding.
    """
    rel_str, line, module = finding
    try:
        source_lines = (_REPO_ROOT / rel_str).read_text(encoding="utf-8").splitlines()
        source_line = source_lines[line - 1]
    except (IndexError, OSError, UnicodeDecodeError):
        return (rel_str, module, "*", 0)
    symbol = _imported_symbol(source_line)
    ordinal = sum(
        1 for candidate in source_lines[:line]
        if _module_from_line(candidate) == module and _imported_symbol(candidate) == symbol
    )
    return (rel_str, module, symbol, ordinal)


def _stable_identities(entries) -> frozenset[tuple[str, str, str, int]]:
    """Resolve classified imports by structure when their line has moved.

    A baseline line can now point at a neighbouring import after harmless file
    growth. Search the nearest same-module import in that file, then retain its
    imported symbol and ordinal as the stable identity.
    """
    identities: set[tuple[str, str, str, int]] = set()
    for rel_str, line, module in entries:
        try:
            source_lines = (_REPO_ROOT / rel_str).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        candidates = [
            index for index, candidate in enumerate(source_lines)
            if _module_from_line(candidate) == module
        ]
        if not candidates:
            continue
        index = min(candidates, key=lambda candidate: abs(candidate + 1 - line))
        identities.add(_stable_identity((rel_str, index + 1, module)))
    return frozenset(identities)


def _baseline_stable_identities() -> frozenset[tuple[str, str, str, int]]:
    return _stable_identities(BASELINE)


def _matches_stable_legacy_identity(finding: tuple[str, int, str]) -> bool:
    """Match a legacy import by structure, independent of line drift."""
    return _stable_identity(finding) in _baseline_stable_identities()


def _matches_stable_classified_identity(
    finding: tuple[str, int, str], entries,
) -> bool:
    return _stable_identity(finding) in _stable_identities(entries)


def _classify_finding(finding: tuple[str, int, str]) -> str:
    if finding in _SANCTIONED_CALL_SITES:
        return "sanctioned"
    if finding in CROSS_TRACK or _matches_stable_classified_identity(finding, CROSS_TRACK):
        return "cross_track"
    if finding in ACCEPTED or _matches_stable_classified_identity(finding, ACCEPTED):
        return "accepted"
    if finding in BASELINE or _matches_stable_legacy_identity(finding):
        return "legacy"
    return "new"


def classify(findings: list[tuple[str, int, str]]) -> dict[str, list[tuple[str, int, str]]]:
    groups = {key: [] for key in ("legacy", "sanctioned", "cross_track", "accepted", "new")}
    for finding in sorted(set(findings)):
        groups[_classify_finding(finding)].append(finding)
    return groups


def main() -> int:
    try:
        found = scan()
    except ScanBoundaryError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
    groups = classify(found)
    contact_bypasses = scan_contact_bypasses()

    print("GOV — Dispatcher Bypass Audit (direct tool-implementation imports)")
    print("-" * 60)

    labels = {
        "legacy": "LEGACY",
        "sanctioned": "SANCTIONED",
        "cross_track": "CROSS_TRACK",
        "accepted": "ACCEPTED",
        "new": "NEW_VIOLATION",
    }
    for key in ("legacy", "sanctioned", "cross_track", "accepted", "new"):
        for file, line, module in groups[key]:
            print(f"{labels[key]:13} {file}:{line}  import {module}")
    for file, line, operation in contact_bypasses:
        print(f"NEW_VIOLATION  {file}:{line}  direct Contact {operation} bypass")

    found_keys = {(f, l, m) for f, l, m in found}
    stable_legacy_paths = {
        (file, module)
        for file, line, module in found
        if _matches_stable_legacy_identity((file, line, module))
    }
    missing = sorted(
        baseline for baseline in BASELINE - found_keys
        if (baseline[0], baseline[2]) not in stable_legacy_paths
    )
    for file, line, module in missing:
        print(f"RESOLVED  no longer present (fixed?)  {file}:{line}  import {module}")

    print("-" * 60)
    sanctioned_count = len(_SANCTIONED_CALL_SITES)
    print(f"SANCTIONED      {sanctioned_count} exact call-site exception(s)")
    new_count = len(groups["new"]) + len(contact_bypasses)
    print(f"Summary: legacy={len(groups['legacy'])} sanctioned={sanctioned_count} "
          f"cross_track={len(groups['cross_track'])} accepted={len(groups['accepted'])} "
          f"new={new_count} resolved={len(missing)}")
    if groups["new"] or contact_bypasses:
        print("FAIL: new dispatcher/tool bypass findings require remediation or explicit authority review.", file=sys.stderr)
        return 1
    return 0


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
