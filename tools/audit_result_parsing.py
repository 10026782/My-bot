#!/usr/bin/env python3
# tools/audit_result_parsing.py — F52 Safe Refactor #7
#
# Static, read-only audit: finds the false-success text-parsing anti-pattern
# — `"✅" in result` / `re.search(r"rec\w+", ...)` used as proof that a tool
# call succeeded, instead of a structured result contract
# ({ok, tool, external_id, evidence, user_message} per C53-A). Display
# strings become an implicit, brittle API this way (docs/f52/F52_BYPASS_MAP.md).
#
# Warning-only inventory — does NOT fix anything, does NOT fail CI.
#
# NOTE ON BASELINE PROVENANCE: this baseline was derived by actually running
# this scan against the repo on 2026-07-03. It does not match the file list
# given in the original task SPEC (telegram_adapter.py, app.py, google_tools.py,
# email_inbound.py, knowledge_engine.py, survey_worker.py) — none of those
# files contain this pattern today (tools/telegram_adapter.py in particular
# already uses a structured ActionResult/delivery_success bool, the opposite
# of the anti-pattern). The real offenders match docs/f52/F52_BYPASS_MAP.md:163
# plus a few more found in this repo scan (voice_adapter.py, interaction_engine.py,
# tenant_provisioner.py, ad_attribution.py).
#
# שימוש: python3 tools/audit_result_parsing.py

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

_EXCLUDE_DIRS = {".git", "node_modules", "tma-frontend", "__pycache__", ".venv", "venv"}
_EXCLUDE_FILE_PREFIXES = ("test_",)
# This script (and its sibling audit) contain example "✅"/rec\w+ strings in
# their own self-tests/docstrings/baseline literals — exclude from scan targets.
_EXCLUDE_FILES = {"tools/audit_gateway_bypass.py", "tools/audit_result_parsing.py"}

_EMOJI_RE = re.compile(r"""['"]✅['"]\s+in\s""")

# Literal substrings (not compiled as regex) for the rec\w+ display-string
# parsing anti-pattern — built as plain strings to avoid backslash-escaping
# confusion between the Python source and the regex engine.
_REC_MARKERS = (
    're.search(r"rec\\w+"',
    "re.search(r'rec\\w+'",
)

# Known offenders as of 2026-07-03 (file relative to repo root, line, kind).
# kind: "emoji" = "✅" in result, "rec" = re.search(r"rec\w+", ...)
BASELINE: frozenset[tuple[str, int, str]] = frozenset({
    ("lead_memory.py", 29, "emoji"),
    ("lead_memory.py", 40, "rec"),
    ("lead_memory.py", 183, "rec"),
    ("lead_capture.py", 215, "rec"),
    ("furniture_lead_funnel.py", 180, "rec"),
    ("voice_adapter.py", 249, "emoji"),
    ("interaction_engine.py", 300, "emoji"),
    ("interaction_engine.py", 302, "rec"),
    ("interaction_engine.py", 386, "emoji"),
    ("tenant_provisioner.py", 176, "emoji"),
    ("ad_attribution.py", 172, "rec"),
    ("ad_attribution.py", 176, "emoji"),
    ("ad_attribution.py", 192, "rec"),
    ("ad_attribution.py", 201, "emoji"),
    ("core/lead_buffer.py", 147, "rec"),
    ("inbound_handler.py", 52, "rec"),
    ("inbound_handler.py", 66, "rec"),
    ("inbound_handler.py", 129, "rec"),
    ("lead_conversion.py", 90, "rec"),
    # Self-test assertions on our own formatter output (not external
    # tool-result parsing) — noise, but left in the baseline rather than
    # special-cased so the script stays a simple grep, not a scope-aware parser.
    # STATIC-AUDIT-20260830 (follow-up 3/3): this is a plain line-number
    # baseline, not a stable-identity one (contrast tools/audit_dispatcher_
    # bypass.py's _stable_identity()) — any edit above a baselined line in
    # the same file shifts it and produces a spurious NEW + a spurious
    # "no longer present" pair. media_handler.py grew from ~600 to ~1500+
    # lines since the 2026-07-03 baseline was taken (F16 media layer +
    # later additions), pushing this same self-test assert from line 521 to
    # 852 without ever touching its content — re-verified 2026-08-30 by
    # confirming line 521 no longer matches the pattern at all and line 852
    # is the identical `assert "✅" in ok_text` against _format_media_
    # result()'s own output. Updated in place rather than adding a second
    # entry, since it's the same assert, not a new occurrence.
    ("media_handler.py", 852, "emoji"),
    ("startup_validator.py", 353, "emoji"),
})


def _iter_py_files():
    for path in _REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(_REPO_ROOT)
        if any(part in _EXCLUDE_DIRS for part in rel.parts):
            continue
        if rel.name.startswith(_EXCLUDE_FILE_PREFIXES):
            continue
        yield rel


def scan() -> list[tuple[str, int, str]]:
    """Returns list of (relative_path_str, line_no, kind) for false-success
    text-parsing occurrences."""
    findings: list[tuple[str, int, str]] = []
    for rel in _iter_py_files():
        rel_str = rel.as_posix()
        if rel_str in _EXCLUDE_FILES:
            continue
        try:
            text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for idx, line in enumerate(text.splitlines()):
            if _EMOJI_RE.search(line):
                findings.append((rel_str, idx + 1, "emoji"))
            elif any(marker in line for marker in _REC_MARKERS):
                findings.append((rel_str, idx + 1, "rec"))
    return findings


def main() -> int:
    found = scan()
    found_keys = {(f, l, k) for f, l, k in found}

    print("🔍 F52 Safe Refactor #7 — False-Success Text Parsing Audit")
    print("━" * 60)

    for file, line, kind in sorted(found):
        is_new = (file, line, kind) not in BASELINE
        marker = "⚠️  NEW" if is_new else "•  known"
        label = '"✅" in result' if kind == "emoji" else 're.search(r"rec\\w+", ...)'
        print(f"{marker}  {file}:{line}  {label}")

    missing = sorted(BASELINE - found_keys)
    for file, line, kind in missing:
        print(f"✅  no longer present (fixed?)  {file}:{line}  kind={kind}")

    new_count = len(found_keys - BASELINE)
    print("━" * 60)
    print(f"סיכום: {len(found)} false-success parsing occurrences found, "
          f"{new_count} new (not in baseline), {len(missing)} resolved since baseline.")

    if new_count:
        print("⚠️  Warning-only: new occurrence(s) found outside the baseline. "
              "Not blocking CI, but verify whether this is expected scope growth.")

    return 0  # warning-only, per F52 Safe Refactor #7 — never blocks CI


def _self_test() -> None:
    assert _EMOJI_RE.search('    return "✅" in (result or "")')
    assert _EMOJI_RE.search("    ok = '✅' in result")
    assert not _EMOJI_RE.search('    print(f"✅ {desc}"); passed += 1')

    assert any(m in 'm = re.search(r"rec\\w+", raw or "")' for m in _REC_MARKERS)
    assert any(m in "m = re.search(r'rec\\w+', raw)" for m in _REC_MARKERS)
    assert not any(m in 're.search(r"•\\s*\\[?(rec\\w+)\\]?", text)' for m in _REC_MARKERS)

    print("✅ audit_result_parsing self-test: 6/6 assertions passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
        sys.exit(0)
    sys.exit(main())
