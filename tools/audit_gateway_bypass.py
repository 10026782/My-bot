#!/usr/bin/env python3
# tools/audit_gateway_bypass.py — F52 Safe Refactor #6
#
# Static, read-only audit: finds direct httpx.get/post/patch/put/delete calls
# targeting the Airtable API from outside tools/airtable_gateway.py (the
# single sanctioned write path per that file's own docstring: "אין לקרוא
# ל-httpx.patch/post על Airtable מחוץ לקובץ זה").
#
# The legacy inventory mode does NOT move any call site and does NOT fail CI.
# The --boundary mode below is the blocking gateway-boundary guard.
# warning-only inventory. It compares live grep results against a known
# BASELINE (verified by hand against the current repo state); anything new
# is flagged as a WARNING so scope drift gets noticed instead of silently
# growing.
#
# NOTE ON BASELINE PROVENANCE: this baseline was derived by actually running
# this scan against the repo on 2026-07-03, not copied from
# docs/f52/F52_CURRENT_TOOL_MAP.md's illustrative file list (which named
# only crm.py / tma_api.py / cmd_decision.py:806 / decision_matching.py:61 —
# that list does not match the live repo: cmd_decision.py:806 has no httpx
# call at all, and several more real bypass sites exist beyond those four).
#
# שימוש: python3 tools/audit_gateway_bypass.py

from __future__ import annotations

import re
import ast
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GATEWAY_FILE = "tools/airtable_gateway.py"

_EXCLUDE_DIRS = {".git", "node_modules", "tma-frontend", "__pycache__", ".venv", "venv"}
_EXCLUDE_FILE_PREFIXES = ("test_",)
# This script (and its sibling audit) contain example httpx.* calls in their
# own self-tests/docstrings — exclude them from being scanned as targets.
_EXCLUDE_FILES = {"tools/audit_gateway_bypass.py", "tools/audit_result_parsing.py"}

_CALL_RE = re.compile(r"\b(?:_?httpx|requests)\.(get|post|patch|put|delete)\s*\(")

# Substrings that, if present within a small window around the call, mark
# it as targeting the Airtable API (as opposed to Google/Telegram/Supabase
# APIs also reached via httpx elsewhere in the repo).
_AIRTABLE_MARKERS = ("airtable", "_at_url", "_at_headers", "_base_url")

# How far forward to look for the call's own (possibly multi-line) first
# argument when nothing follows the opening paren on the call line itself.
_FORWARD_LOOKAHEAD = 3
# How far back to trace a bare-identifier first argument (e.g. `httpx.get(url, ...)`)
# to its `url = f"https://api.airtable.com/..."` assignment.
_BACKWARD_LOOKAHEAD = 20

_BARE_IDENTIFIER_RE = re.compile(r"^([A-Za-z_]\w*)\s*[,)]")
_ASSIGNMENT_RE_TEMPLATE = r"^\s*{name}\s*="

_WRITE_METHODS = {"post", "patch", "put", "delete"}

# Baseline re-verified on 2026-08-24 (Track D-Structure Audit #7): all 24
# entries known as of 2026-07-03 were individually checked against current
# origin/main. 23 were resolved by migrating to tools/airtable_gateway.py or
# tools/airtable_read_adapter.py; the remaining one (the search logic
# formerly in core/lead_candidate_handler.py) moved to
# core/lead_service.py::find_existing_lead, which itself also routes through
# tools/airtable_read_adapter.py. No baseline entry remained a live bypass,
# so the baseline resets to empty — current truth is zero known bypasses.
# Full history of the historical 2026-07-03 entries is preserved in git log,
# not duplicated here as executable code.
# New entries not in this set → WARNING (scope drift). Entries in this set
# that disappear → reported as "no longer present" (likely fixed upstream).
BASELINE: frozenset[tuple[str, int, str]] = frozenset()


class ScanBoundaryError(RuntimeError):
    """Raised when the tracked-file boundary can't be determined — fail closed
    rather than falling back to an unsafe filesystem walk (see #7 gateway-bypass
    scan-boundary remediation: rglob() previously picked up untracked sibling
    worktrees under .worktrees/)."""


def _iter_py_files():
    """Enumerates *.py files tracked by this repository's git index. Untracked
    files, nested/sibling checkouts (e.g. .worktrees/*), and generated scratch
    files are never scanned, regardless of where they sit under _REPO_ROOT."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.py"],
            cwd=_REPO_ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ScanBoundaryError(
            f"audit_gateway_bypass: 'git ls-files' failed, refusing to scan "
            f"the filesystem as a fallback: {exc}"
        ) from exc

    for rel_str in result.stdout.decode("utf-8").split("\0"):
        if not rel_str:
            continue
        rel = Path(rel_str)
        if any(part in _EXCLUDE_DIRS for part in rel.parts):
            continue
        if rel.name.startswith(_EXCLUDE_FILE_PREFIXES):
            continue
        yield rel


def _gateway_private_imports(tree: ast.AST) -> list[str]:
    aliases: set[str] = set()
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "tools.airtable_gateway":
            for alias in node.names:
                if alias.name.startswith("_"):
                    violations.append(f"line {node.lineno}: private gateway import {alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tools.airtable_gateway":
                    aliases.add(alias.asname or "tools.airtable_gateway")

    def attribute_path(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = attribute_path(node.value)
            return f"{parent}.{node.attr}" if parent else None
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            parent = attribute_path(node.value)
            if parent in aliases:
                violations.append(f"line {node.lineno}: private gateway usage {parent}.{node.attr}")
    return violations


def _source_boundary_violations(rel_str: str, text: str) -> list[str]:
    """Find transport/provider knowledge outside the canonical gateway."""
    violations: list[str] = []
    forbidden = ("api.airtable.com", "content.airtable.com", "/v0/", "/v0/meta/")
    for token in forbidden:
        if token in text:
            violations.append(f"{rel_str}: forbidden Airtable endpoint token {token}")
    try:
        tree = ast.parse(text.lstrip("\ufeff"), filename=rel_str)
    except SyntaxError as exc:
        return [f"{rel_str}: syntax error: {exc}"]
    violations.extend(f"{rel_str}: {item}" for item in _gateway_private_imports(tree))
    # Authorization construction is only forbidden here when the file also
    # carries Airtable transport markers; unrelated provider auth is allowed.
    if re.search(r"[\"']Authorization[\"']\s*:", text) and re.search(
        r"api\.airtable\.com|content\.airtable\.com|/v0/|_at_(?:url|headers|base|key)",
        text,
        re.IGNORECASE,
    ):
        violations.append(f"{rel_str}: Airtable Authorization/header construction")
    return violations


def boundary_scan() -> list[str]:
    violations: list[str] = []
    for rel in _iter_py_files():
        rel_str = rel.as_posix()
        if rel_str in {_GATEWAY_FILE, *_EXCLUDE_FILES}:
            continue
        try:
            text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        violations.extend(_source_boundary_violations(rel_str, text))
    for file, line, method in scan():
        violations.append(f"{file}:{line}: direct Airtable HTTP httpx.{method}()")
    return sorted(set(violations))


def _is_airtable_target(lines: list[str], idx: int) -> bool:
    """Decides whether the httpx call at lines[idx] targets the Airtable API.

    Looks only at the call's own (first) argument — same line if present,
    else the next non-blank line(s) for a multi-line call — rather than a
    blind line-distance window, so an unrelated Airtable reference in a
    neighboring code block (e.g. an import used for something else a few
    lines above) can't cause a false match.
    """
    line = lines[idx]
    m = _CALL_RE.search(line)
    after = line[m.end():].strip()

    if after:
        first_arg_line = after
    else:
        lookahead = "\n".join(lines[idx + 1: idx + 1 + _FORWARD_LOOKAHEAD])
        first_arg_line = lookahead.strip()

    if any(marker in first_arg_line.lower() for marker in _AIRTABLE_MARKERS):
        return True

    # Bare-identifier first argument (e.g. `httpx.get(url, headers=...)`) —
    # trace it back to its assignment and check that line instead.
    ident_source = after if after else lines[idx + 1].strip() if idx + 1 < len(lines) else ""
    ident_match = _BARE_IDENTIFIER_RE.match(ident_source)
    if not ident_match:
        return False

    name = ident_match.group(1)
    assign_re = re.compile(_ASSIGNMENT_RE_TEMPLATE.format(name=re.escape(name)))
    start = max(0, idx - _BACKWARD_LOOKAHEAD)
    for back_line in reversed(lines[start:idx]):
        if assign_re.match(back_line):
            return any(marker in back_line.lower() for marker in _AIRTABLE_MARKERS)
    return False


def scan() -> list[tuple[str, int, str]]:
    """Returns list of (relative_path_str, line_no, method) for Airtable-targeted
    httpx calls found outside the gateway file."""
    findings: list[tuple[str, int, str]] = []
    for rel in _iter_py_files():
        rel_str = rel.as_posix()
        if rel_str == _GATEWAY_FILE or rel_str in _EXCLUDE_FILES:
            continue
        try:
            text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            m = _CALL_RE.search(line)
            if not m:
                continue
            if not _is_airtable_target(lines, idx):
                continue
            findings.append((rel_str, idx + 1, m.group(1)))
    return findings


def classify(method: str) -> str:
    return "WRITE" if method in _WRITE_METHODS else "read"


def main() -> int:
    if "--boundary" in sys.argv:
        violations = boundary_scan()
        if violations:
            print("❌ Airtable boundary violations:")
            for violation in violations:
                print(f"- {violation}")
            return 1
        print("✅ Airtable boundary guard: PASS")
        return 0
    try:
        found = scan()
    except ScanBoundaryError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
    found_keys = {(f, l, m) for f, l, m in found}

    print("🔍 F52 Safe Refactor #6 — Airtable Gateway Bypass Audit")
    print("━" * 60)

    for file, line, method in sorted(found):
        tag = classify(method)
        is_new = (file, line, method) not in BASELINE
        marker = "⚠️  NEW" if is_new else "•  known"
        print(f"{marker}  {file}:{line}  httpx.{method}()  [{tag}]")

    missing = sorted(BASELINE - found_keys)
    for file, line, method in missing:
        print(f"✅  no longer present (fixed?)  {file}:{line}  httpx.{method}()")

    new_count = len(found_keys - BASELINE)
    print("━" * 60)
    print(f"סיכום: {len(found)} Airtable bypass call-sites found, "
          f"{new_count} new (not in baseline), {len(missing)} resolved since baseline.")

    if new_count:
        print("⚠️  Warning-only: new bypass call-site(s) found outside the baseline. "
              "Not blocking CI, but verify whether this is expected scope growth.")

    return 0  # warning-only, per F52 Safe Refactor #6 — never blocks CI


def _self_test() -> None:
    # Same-line marker.
    lines = [
        "def f():",
        "    r = httpx.get(_base_url(table), headers=_headers())",
        "    return r",
    ]
    assert _is_airtable_target(lines, 1) is True

    # Unrelated API — must NOT match even with an Airtable-ish import nearby.
    lines2 = [
        "    from tools.airtable_gateway import check_alias_consistency as _gw_check",
        "    _gw_mismatches = _gw_check()",
        "    if _gw_mismatches:",
        "        pass",
        "    if True:",
        '        httpx.post(f"https://api.telegram.org/bot{tok}/sendMessage", json={})',
    ]
    assert _is_airtable_target(lines2, 5) is False

    # Multi-line call, URL literal on the next line.
    lines3 = [
        "        r = httpx.get(",
        '            f"https://api.airtable.com/v0/{_base()}/{encoded}",',
        "            headers=_headers(),",
        "        )",
    ]
    assert _is_airtable_target(lines3, 0) is True

    # Bare-identifier first argument, traced back to its assignment.
    lines4 = [
        'url     = f"https://api.airtable.com/v0/{base}/Leads"',
        "headers = {}",
        "for x in y:",
        "    r = httpx.get(url, headers=headers,",
        "                  params={}, timeout=8)",
    ]
    assert _is_airtable_target(lines4, 3) is True

    # Bare-identifier first argument that resolves to something unrelated.
    lines5 = [
        'url = f"https://api.telegram.org/bot{tok}/getMe"',
        "r = httpx.get(url, timeout=5)",
    ]
    assert _is_airtable_target(lines5, 1) is False

    assert classify("post") == "WRITE"
    assert classify("get") == "read"

    assert _source_boundary_violations(
        "bad.py", 'import httpx\nhttpx.get("https://api.airtable.com/v0/Leads")'
    )
    assert _source_boundary_violations(
        "bad.py", "from tools.airtable_gateway import _safe_formula_param"
    )
    assert _source_boundary_violations(
        "bad.py", "import tools.airtable_gateway as gateway\ngateway._safe_formula_param('x')"
    )
    assert _source_boundary_violations(
        "bad.py", 'import requests\nrequests.post("https://api.airtable.com/v0/Leads")'
    )
    assert _source_boundary_violations(
        "bad.py", 'def _at_headers(): return {"Authorization": "Bearer x"}'
    )
    assert not _source_boundary_violations(
        "good.py", "def _safe_formula_param(value): return value"
    )
    assert not _source_boundary_violations(
        "good.py", "from tools.airtable_gateway import escape_formula_value"
    )

    print("✅ audit_gateway_bypass self-test: 12/12 assertions passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
        sys.exit(0)
    sys.exit(main())
