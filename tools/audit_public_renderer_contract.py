#!/usr/bin/env python3
"""Freeze growth of public renderers and MessageContract entry paths.

The audit is deliberately delta-based. Existing surfaces are legacy baseline;
new public renderer symbols and new semantic-contract entry points require an
exact registration with a surface owner and architecture decision.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/governance/PUBLIC_RENDERER_CONTRACT_REGISTRY.md"
_SELF_PATH = "tools/audit_public_renderer_contract.py"
_EXCLUDED = {".git", "__pycache__", ".venv", "venv", "node_modules"}
_TEST_PREFIXES = ("test_",)
_RENDERER_NAME = re.compile(r"^(?:render|format|compose_.*reply|build_.*message)(?:_|$)", re.I)
_CONTRACT_IMPORT = re.compile(r"\b(?:from\s+core\.(?:message_contract|agent_message_formatter)|import\s+core\.(?:message_contract|agent_message_formatter))\b")
_CONTRACT_SYMBOL = re.compile(r"\b(?:MessageContract|build_message_contract|format_message_contract|format_agent_message(?:_with_meta)?)\b")

# These are the frozen canonical implementation paths. They may evolve their
# internal wiring without registering themselves as a new public surface.
_CANONICAL_PATHS = {
    "core/message_contract.py",
    "core/agent_message_formatter.py",
    "core/message_surface_harness.py",
    "core/action_gateway.py",
}


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    symbol: str
    line: int

    @property
    def key(self) -> tuple[str, str, str]:
        return self.path, self.kind, self.symbol


def _added_lines() -> dict[str, set[int]]:
    result = subprocess.run(
        ["git", "diff", "--unified=0", "origin/main...HEAD", "--", "*.py"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE,
    )
    paths: dict[str, set[int]] = {}
    current: str | None = None
    for raw in result.stdout.splitlines():
        if raw.startswith("+++ b/"):
            current = raw[6:]
            paths.setdefault(current, set())
        elif current and raw.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", raw)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or "1")
                paths[current].update(range(start, start + count))
    return paths


def _renderer_definitions(path: str, source: str, added: set[int]) -> list[Finding]:
    if path in _CANONICAL_PATHS:
        return []
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return []
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith("_") or node.lineno not in added:
                continue
            if _RENDERER_NAME.search(node.name) or (isinstance(node, ast.ClassDef) and node.name.endswith("Renderer")):
                findings.append(Finding(path, "public_renderer", node.name, node.lineno))
    return findings


def _contract_entries(path: str, source: str, added: set[int]) -> list[Finding]:
    if path in _CANONICAL_PATHS:
        return []
    findings = []
    for lineno, raw in enumerate(source.splitlines(), 1):
        if lineno not in added:
            continue
        if _CONTRACT_IMPORT.search(raw):
            findings.append(Finding(path, "contract_import", "message_contract", lineno))
        elif _CONTRACT_SYMBOL.search(raw):
            findings.append(Finding(path, "contract_entry", "message_contract", lineno))
    return findings


def load_registrations() -> dict[tuple[str, str, str], tuple[str, str]]:
    registrations: dict[tuple[str, str, str], tuple[str, str]] = {}
    if not REGISTRY.exists():
        return registrations
    row = re.compile(r"^\| `([^`]+)` \| `([^`]+)` \| `([^`]+)` \| ([^|]+?) \| `([^`]+)` \|$")
    for raw in REGISTRY.read_text(encoding="utf-8").splitlines():
        match = row.match(raw.strip())
        if match and match.group(4).strip() and match.group(5).strip():
            registrations[(match.group(1), match.group(2), match.group(3))] = (match.group(4).strip(), match.group(5).strip())
    return registrations


def audit() -> tuple[list[Finding], list[Finding], dict[tuple[str, str, str], tuple[str, str]]]:
    registrations = load_registrations()
    candidates: list[Finding] = []
    for path, added in _added_lines().items():
        if path == _SELF_PATH or path.startswith(_TEST_PREFIXES) or any(part in _EXCLUDED for part in Path(path).parts):
            continue
        source_path = ROOT / path
        if not source_path.exists():
            continue
        source = source_path.read_text(encoding="utf-8")
        candidates.extend(_renderer_definitions(path, source, added))
        candidates.extend(_contract_entries(path, source, added))
    registered = [item for item in candidates if item.key in registrations]
    new = [item for item in candidates if item.key not in registrations]
    return sorted(new, key=lambda x: (x.path, x.line, x.kind, x.symbol)), sorted(registered, key=lambda x: (x.path, x.line, x.kind, x.symbol)), registrations


def main() -> int:
    new, registered, registrations = audit()
    print(f"Public renderer/contract delta: candidates={len(new) + len(registered)} registered={len(registered)} new={len(new)}")
    for item in registered:
        owner, decision = registrations[item.key]
        print(f"REGISTERED {item.kind} {item.path}:{item.line} {item.symbol} owner={owner} decision={decision}")
    for item in new:
        print(f"NEW_PUBLIC_SURFACE {item.kind} {item.path}:{item.line} {item.symbol}")
    if new:
        print("FAIL: new public renderers/MessageContract paths require exact surface registration.", file=sys.stderr)
        return 1
    print("PASS: no unregistered public renderer/MessageContract delta")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
