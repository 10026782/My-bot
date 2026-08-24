#!/usr/bin/env python3
"""Block new writer/store/authority implementations without registration.

This is a delta guard. Existing implementations are the reviewed baseline;
new implementation-shaped symbols or modules must carry an exact registration
in ``docs/governance/WRITER_AUTHORITY_REGISTRY.md``.  The guard is static and
has no runtime or persistence side effects.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/governance/WRITER_AUTHORITY_REGISTRY.md"
_EXCLUDED_PARTS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
_EXCLUDED_PREFIXES = ("test_",)
_IMPLEMENTATION_WORDS = re.compile(r"(?:writer|store|repository|authority)", re.I)
_FUNCTION_WORDS = re.compile(r"^(?:write|save|persist|store|register_.*authority)", re.I)
_REGISTRATION_RE = re.compile(
    r"^\| `(?P<path>[^`]+)` \| `(?P<symbol>[^`]+)` \| (?P<owner>[^|]+?) \| `(?P<decision>[^`]+)` \|$"
)


@dataclass(frozen=True)
class Finding:
    path: str
    symbol: str
    line: int
    kind: str

    @property
    def key(self) -> tuple[str, str]:
        return self.path, self.symbol


def _tracked_python_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    paths = []
    for raw in result.stdout.decode().split("\0"):
        if not raw:
            continue
        path = Path(raw)
        if any(part in _EXCLUDED_PARTS for part in path.parts):
            continue
        if path.name.startswith(_EXCLUDED_PREFIXES):
            continue
        paths.append(raw)
    return sorted(paths)


def _module_is_implementation(path: str) -> bool:
    return _IMPLEMENTATION_WORDS.search(Path(path).stem) is not None


def scan_source(path: str, source: str) -> list[Finding]:
    findings: list[Finding] = []
    if _module_is_implementation(path):
        findings.append(Finding(path, "<module>", 1, "module"))
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            if isinstance(node, ast.ClassDef) and _IMPLEMENTATION_WORDS.search(node.name):
                findings.append(Finding(path, node.name, node.lineno, "class"))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _FUNCTION_WORDS.search(node.name):
                findings.append(Finding(path, node.name, node.lineno, "function"))
    return findings


def _added_line_ranges() -> dict[str, set[int]]:
    result = subprocess.run(
        ["git", "diff", "--unified=0", "origin/main...HEAD", "--", "*.py"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    ranges: dict[str, set[int]] = {}
    current: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            ranges.setdefault(current, set())
            continue
        if current is None or not line.startswith("@@"):
            continue
        match = re.search(r"\+(\d+)(?:,(\d+))?", line)
        if not match:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        ranges[current].update(range(start, start + count))
    return ranges


def load_registrations() -> dict[tuple[str, str], tuple[str, str]]:
    registrations: dict[tuple[str, str], tuple[str, str]] = {}
    if not REGISTRY.exists():
        return registrations
    for raw in REGISTRY.read_text(encoding="utf-8").splitlines():
        match = _REGISTRATION_RE.match(raw.strip())
        if not match:
            continue
        owner = match.group("owner").strip()
        decision = match.group("decision").strip()
        if owner and decision:
            registrations[(match.group("path"), match.group("symbol"))] = (owner, decision)
    return registrations


def audit() -> tuple[list[Finding], list[Finding], dict[tuple[str, str], tuple[str, str]]]:
    added = _added_line_ranges()
    registrations = load_registrations()
    candidates: list[Finding] = []
    for path, lines in added.items():
        if path == "tools/audit_writer_authority_registration.py":
            continue
        source_path = ROOT / path
        if not source_path.exists():
            continue
        for finding in scan_source(path, source_path.read_text(encoding="utf-8")):
            if finding.line in lines or (finding.kind == "module" and 1 in lines):
                candidates.append(finding)
    registered = [finding for finding in candidates if finding.key in registrations]
    new = [finding for finding in candidates if finding.key not in registrations]
    return sorted(new, key=lambda f: (f.path, f.line, f.symbol)), sorted(registered, key=lambda f: (f.path, f.line, f.symbol)), registrations


def main() -> int:
    new, registered, registrations = audit()
    print(f"Writer/authority delta: candidates={len(new) + len(registered)} registered={len(registered)} new={len(new)}")
    for finding in registered:
        owner, decision = registrations[finding.key]
        print(f"REGISTERED {finding.kind} {finding.path}:{finding.line} {finding.symbol} owner={owner} decision={decision}")
    for finding in new:
        print(f"NEW_REGISTRATION_REQUIRED {finding.kind} {finding.path}:{finding.line} {finding.symbol}")
    if new:
        print("FAIL: new writer/store/authority implementations require exact owner + architecture decision registration.", file=sys.stderr)
        return 1
    print("PASS: no unregistered writer/store/authority delta")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
