#!/usr/bin/env python3
"""Enforce PR-A2: no new direct model/provider SDK calls.

The guard scans application runtime Python paths for direct Anthropic/OpenAI
SDK imports, client construction, and completion/transcription endpoints.
Existing app.py calls are grandfathered; llm_fallback.py is the approved
model adapter. New fingerprints fail CI while the legacy baseline remains
visible in every report.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_FILES = frozenset({
    "app.py",
    "context.py",
    "event_bus.py",
    "tma_api.py",
    "tool_registry.py",
})
RUNTIME_PREFIXES = ("core/", "tools/")
EXCLUDED_PATH_PARTS = ("tools/context_librarian/",)

APPROVED_ADAPTER_FILES = frozenset({"llm_fallback.py"})
MODEL_MODULES = frozenset({"anthropic", "openai"})
MODEL_CONSTRUCTORS = frozenset({"anthropic.Anthropic", "openai.OpenAI"})
MODEL_ENDPOINT_SUFFIXES = frozenset({
    "messages.create",
    "chat.completions.create",
    "audio.transcriptions.create",
})


@dataclass(frozen=True, order=True)
class CallFingerprint:
    path: str
    kind: str
    target: str

    def as_text(self) -> str:
        return f"{self.path}|{self.kind}|{self.target}"


LEGACY_BASELINE = frozenset({
    CallFingerprint("app.py", "import", "anthropic"),
    CallFingerprint("app.py", "call", "anthropic.Anthropic"),
    CallFingerprint("app.py", "call", "messages.create"),
})


def _is_runtime_path(path: str) -> bool:
    if path in RUNTIME_FILES:
        return True
    return (
        path.startswith(RUNTIME_PREFIXES)
        and not any(part in path for part in EXCLUDED_PATH_PARTS)
    )


def _dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.alias):
        parts.append(node.name)
    return ".".join(reversed(parts))


def _iter_runtime_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("unable to enumerate tracked Python files") from exc
    return sorted(
        path for path in result.stdout.decode("utf-8").split("\0")
        if path and _is_runtime_path(path)
    )


def scan_text(path: str, text: str) -> list[CallFingerprint]:
    if not _is_runtime_path(path) or path in APPROVED_ADAPTER_FILES:
        return []
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        raise RuntimeError(f"{path}: syntax error: {exc}") from exc

    findings: set[CallFingerprint] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in MODEL_MODULES:
                    findings.add(CallFingerprint(path, "import", alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module in MODEL_MODULES:
                findings.add(CallFingerprint(path, "import", node.module))
        elif isinstance(node, ast.Call):
            target = _dotted_name(node.func)
            if target in MODEL_CONSTRUCTORS:
                findings.add(CallFingerprint(path, "call", target))
            elif any(target.endswith(suffix) for suffix in MODEL_ENDPOINT_SUFFIXES):
                findings.add(CallFingerprint(path, "call", next(
                    suffix for suffix in MODEL_ENDPOINT_SUFFIXES if target.endswith(suffix)
                )))
    return sorted(findings)


def scan() -> list[CallFingerprint]:
    findings: list[CallFingerprint] = []
    for path in _iter_runtime_files():
        findings.extend(scan_text(path, (REPO_ROOT / path).read_text(encoding="utf-8")))
    return sorted(set(findings))


def classify(findings: list[CallFingerprint]) -> dict[str, list[CallFingerprint]]:
    known = LEGACY_BASELINE
    return {
        "legacy": sorted(set(findings) & known),
        "new": sorted(set(findings) - known),
        "missing_legacy": sorted(known - set(findings)),
    }


def report(findings: list[CallFingerprint]) -> str:
    groups = classify(findings)
    lines = ["PR-A2 — Direct Model / Agent Call Freeze", ""]
    for label, key in (("LEGACY", "legacy"), ("NEW", "new")):
        lines.append(f"{label} ({len(groups[key])})")
        lines.extend(f"  {item.as_text()}" for item in groups[key])
    lines.append(f"SUMMARY legacy={len(groups['legacy'])} new={len(groups['new'])}")
    return "\n".join(lines)


def main() -> int:
    try:
        findings = scan()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(report(findings))
    if classify(findings)["new"]:
        print("FAIL: new direct model/agent SDK calls require the canonical adapter or authority review.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
