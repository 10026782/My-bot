#!/usr/bin/env python3
# tools/audit_gateway_bypass.py — F52 Safe Refactor #6
#
# Static, read-only audit: finds direct httpx.get/post/patch/put/delete calls
# targeting the Airtable API from outside tools/airtable_gateway.py (the
# single sanctioned write path per that file's own docstring: "אין לקרוא
# ל-httpx.patch/post על Airtable מחוץ לקובץ זה").
#
# This does NOT move any call site and does NOT fail CI — it is a
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
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GATEWAY_FILE = "tools/airtable_gateway.py"

_EXCLUDE_DIRS = {".git", "node_modules", "tma-frontend", "__pycache__", ".venv", "venv"}
_EXCLUDE_FILE_PREFIXES = ("test_",)
# This script (and its sibling audit) contain example httpx.* calls in their
# own self-tests/docstrings — exclude them from being scanned as targets.
_EXCLUDE_FILES = {"tools/audit_gateway_bypass.py", "tools/audit_result_parsing.py"}

_CALL_RE = re.compile(r"\b_?httpx\.(get|post|patch|put|delete)\s*\(")

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

# Known bypass sites as of 2026-07-03 (file relative to repo root, line, method).
# New entries not in this set → WARNING (scope drift). Entries in this set
# that disappear → reported as "no longer present" (likely fixed upstream).
BASELINE: frozenset[tuple[str, int, str]] = frozenset({
    ("crm.py", 59, "get"),
    ("crm.py", 70, "post"),
    ("crm.py", 80, "patch"),
    ("tools/airtable_tools.py", 166, "get"),
    ("tools/airtable_tools.py", 261, "get"),
    ("tools/airtable_tools.py", 304, "get"),
    ("tma_api.py", 199, "get"),
    ("tma_api.py", 218, "get"),
    ("tma_api.py", 2497, "get"),
    ("decision_matching.py", 63, "get"),
    ("schema_validator.py", 63, "get"),
    ("system_registry_audit.py", 103, "get"),
    ("daily_digest.py", 32, "get"),
    ("weekly_summary.py", 108, "get"),
    ("providers/airtable_shim.py", 33, "get"),
    ("tools/dispatcher.py", 84, "get"),
    ("tools/schema_governance.py", 52, "get"),
    ("cmd_decision.py", 839, "get"),
    ("cmd_decision.py", 853, "get"),
    ("decision_ports.py", 71, "get"),
    ("core/emergency_window.py", 55, "get"),
    ("core/lead_candidate_handler.py", 287, "get"),
    ("core/lead_events.py", 44, "get"),
    ("health_monitor.py", 18, "get"),
})


def _iter_py_files():
    for path in _REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(_REPO_ROOT)
        if any(part in _EXCLUDE_DIRS for part in rel.parts):
            continue
        if rel.name.startswith(_EXCLUDE_FILE_PREFIXES):
            continue
        yield rel


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
    found = scan()
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

    print("✅ audit_gateway_bypass self-test: 5/5 assertions passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
        sys.exit(0)
    sys.exit(main())
