#!/usr/bin/env python3
"""Enforce the PR-A1 provider boundary without requiring legacy cleanup.

The scanner is intentionally narrow: it audits concrete provider/tool imports
from governed ``core/`` feature code.  Existing debt is represented by stable
file/module/symbol fingerprints, not line numbers.  Explicit adapter and
boundary modules are allowlisted; known cross-track findings remain visible
but do not block this guard.  Any other fingerprint is a new violation.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOVERNED_ROOT = "core/"
EXCLUDED_FILENAMES = {"__init__.py"}

# These are implementation modules, not ports/adapters.  Keep this list
# explicit so adding a new concrete provider family requires reviewing this
# guard rather than silently widening the boundary.
CONCRETE_MODULE_PREFIXES = (
    "tools.airtable_tools",
    "tools.calendar_tools",
    "tools.contact_resolver",
    "tools.drive_tools",
    "tools.gmail_tools",
    "tools.google_tools",
    "tools.sheets_tools",
    "crm",
)

# Provider-facing boundary modules are allowed to know their implementation.
# Each entry needs a code-review rationale; feature modules must not be added
# here merely to make the current scan green.
APPROVED_BOUNDARY_FILES = frozenset({
    "core/google_drive_artifact_store.py",  # Google Drive artifact adapter
    "core/runtime_schema_provider.py",      # schema/provider boundary
    "core/reasoning_ports.py",              # ReasoningPorts adapter layer — its own
                                             # docstring states engines import only
                                             # from this file, never providers directly
})


@dataclass(frozen=True, order=True)
class ImportFingerprint:
    path: str
    module: str
    symbol: str
    import_kind: str

    def as_text(self) -> str:
        return f"{self.path}|{self.import_kind}|{self.module}|{self.symbol}"


# Existing findings are deliberately not erased.  The two newer entries are
# accepted only as cross-track handoffs documented by the architecture audit;
# they remain visible in every report and are not treated as approved design.
LEGACY_BASELINE = frozenset({
    ImportFingerprint("core/lead_buffer.py", "tools.airtable_tools", "airtable_get", "from"),
    ImportFingerprint("core/lead_recovery.py", "crm", "crm_list_deals", "from"),
})

CROSS_TRACK_BASELINE = frozenset({
    ImportFingerprint("core/memory_retrieval.py", "tools.airtable_tools", "airtable_get_records", "from"),
    ImportFingerprint("core/turn_coordinator_runtime.py", "tools.airtable_tools", "airtable_get_records", "from"),
})


def _is_concrete_module(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in CONCRETE_MODULE_PREFIXES
    )


def _iter_tracked_core_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", f"{GOVERNED_ROOT}*.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("unable to enumerate tracked core files; refusing to scan filesystem") from exc
    return [p for p in result.stdout.decode("utf-8").split("\0") if p]


def scan_text(path: str, text: str) -> list[ImportFingerprint]:
    """Return concrete provider imports in one governed source file."""
    if not path.startswith(GOVERNED_ROOT) or Path(path).name in EXCLUDED_FILENAMES:
        return []
    if path in APPROVED_BOUNDARY_FILES:
        return []
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        raise RuntimeError(f"{path}: syntax error: {exc}") from exc

    findings: list[ImportFingerprint] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_concrete_module(module):
                for alias in node.names:
                    findings.append(ImportFingerprint(path, module, alias.name, "from"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_concrete_module(alias.name):
                    findings.append(ImportFingerprint(path, alias.name, "*", "import"))
    return sorted(set(findings))


def scan() -> list[ImportFingerprint]:
    findings: list[ImportFingerprint] = []
    for path in _iter_tracked_core_files():
        findings.extend(scan_text(path, (REPO_ROOT / path).read_text(encoding="utf-8")))
    return sorted(set(findings))


def classify(findings: list[ImportFingerprint]) -> dict[str, list[ImportFingerprint]]:
    known = LEGACY_BASELINE | CROSS_TRACK_BASELINE
    return {
        "legacy": sorted(set(findings) & LEGACY_BASELINE),
        "cross_track": sorted(set(findings) & CROSS_TRACK_BASELINE),
        "new": sorted(set(findings) - known),
        "missing_legacy": sorted(LEGACY_BASELINE - set(findings)),
        "missing_cross_track": sorted(CROSS_TRACK_BASELINE - set(findings)),
    }


def report(findings: list[ImportFingerprint]) -> str:
    groups = classify(findings)
    lines = ["PR-A1 — Core Provider Boundary Freeze", ""]
    for label, key in (("LEGACY", "legacy"), ("CROSS-TRACK", "cross_track"), ("NEW", "new")):
        lines.append(f"{label} ({len(groups[key])})")
        lines.extend(f"  {item.as_text()}" for item in groups[key])
    lines.append(f"SUMMARY legacy={len(groups['legacy'])} cross_track={len(groups['cross_track'])} new={len(groups['new'])}")
    return "\n".join(lines)


def main() -> int:
    try:
        findings = scan()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(report(findings))
    groups = classify(findings)
    if groups["new"]:
        print("FAIL: new concrete provider imports require remediation or explicit authority review.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
