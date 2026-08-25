#!/usr/bin/env python3
"""Audit #11 (#11-3) — block new unescaped Airtable filterByFormula interpolation.

Narrowly scoped to the exact vulnerability class found by Audit #11 (#11-1):
an f-string that opens an Airtable formula string-literal comparison
(``...='`` / ``...!='``) and interpolates a value that never passed through
a sanctioned escaping helper. Not a general security linter — it does not
reason about SQL, shell, HTML, or any other injection class, and it does not
attempt full whole-program data-flow analysis: safety is resolved only
within the interpolated value's own function/module scope, which is exactly
the shape the sanctioned two-step pattern (``safe_x = escape_formula_value(x);
f"...{safe_x}..."``) documented in ``tools/airtable_gateway.py`` produces.

Existing debt this scan surfaces but does not require remediating here is
represented by stable (path, scope, expression) fingerprints, not line
numbers — see LEGACY_BASELINE.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SELF_PATH = "tools/audit_formula_escaping_boundary.py"

# scripts/ holds manual, non-production staging-verification CLIs (never
# imported by the live pipeline) — already accepted as out-of-scope by
# docs/governance/HORIZON.md's CROSS-TRACK/HANDOFFS section for the one
# formula-building example that exists there (scripts/verify_f15_staging.py).
EXCLUDED_DIR_PREFIXES = ("scripts/", ".worktrees/")
EXCLUDED_FILE_PREFIXES = ("test_",)
EXCLUDED_FILES = frozenset({SELF_PATH})

# Airtable formula comparisons always compare the close of a {Field}
# reference or a RECORD_ID()-style call against a quoted literal — i.e. the
# tail is "}" or ")", then "=" or "!=", then the opening quote. Requiring
# the "}"/")" immediately before the operator is what tells a real formula
# clause ("{field}='...'") apart from an unrelated log/message string that
# merely contains "word='...'" (e.g. "msg='...'", "key='...'").
_FORMULA_QUOTE_OPEN_RE = re.compile(r"[}\)][=!]=?\s*'$")

# Logging calls are never how a filterByFormula string reaches the Airtable
# API — an f-string passed directly as one of these calls' arguments is a
# human-readable message, even when it happens to echo the "{field}='...'"
# shape (e.g. "resolved {field}='{val}' -> {rec_id}").
_LOGGING_METHOD_NAMES = frozenset({
    "debug", "info", "warning", "warn", "error", "critical", "exception", "log",
})

# Calls recognized as escaping the value before it reaches a formula string
# literal. `_sanitize_formula_value` (tools/dispatcher.py) is a stricter,
# differently-named sibling (strips quote/brace/paren characters outright
# rather than backslash-escaping them) — still a sanctioned helper, not a
# bypass.
SANCTIONED_CALL_NAMES = frozenset({
    "escape_formula_value",
    "_safe_formula_param",
    "_sanitize_formula_value",
})


@dataclass(frozen=True, order=True)
class FormulaFingerprint:
    path: str
    scope: str
    expr: str

    def as_text(self) -> str:
        return f"{self.path}|{self.scope}|{self.expr}"


# Pre-existing sites this scan surfaces but that Audit #11 (#11-1) either
# explicitly left alone (not currently exploitable/reachable — see
# BUG_AUDIT_LOG.md "Audit #11" §NOT COUNTED AS CURRENT GAPS) or that fall
# outside #11-1's documented affected-sites list and were not part of this
# remediation's scope. Each entry needs its own review before removal, not a
# blanket sweep.
LEGACY_BASELINE = frozenset({
    # NOT CURRENTLY EXPLOITABLE — tenant_id sourced only from the curated
    # identity registry / hardcoded "boss_hq" fallback, never attacker input.
    FormulaFingerprint(
        "tools/airtable_security.py", "enforce_tenant_scope",
        "f\"{{tenant_id}}='{tenant_id}'\"",
    ),
    # NOT CURRENTLY REACHABLE — module not imported by any live pipeline
    # code (owner-parked decision, see MAINTENANCE_FILE_DRIFT_REGISTER.md's
    # #12 cluster).
    FormulaFingerprint(
        "tenant_provisioner.py", "suspend_tenant",
        "f\"{{tenant_id}}='{tenant_id}'\"",
    ),
    FormulaFingerprint(
        "tenant_provisioner.py", "get_tenant_config",
        "f\"{{tenant_id}}='{tenant_id}'\"",
    ),
    # Outside #11-1's documented affected-sites list; identity.user_id here
    # is the dispatcher's own resolved-identity value, not raw external
    # input at this call site. Not remediated by this guard's introduction.
    FormulaFingerprint(
        "tools/dispatcher.py", "dispatch_tool",
        "f\"{{user_id}}='{identity.user_id}'\"",
    ),
    # Inline-escaped via .replace(), not via the named sanctioned helpers —
    # a legacy equivalent, not an unescaped bypass.
    FormulaFingerprint(
        "tools/airtable_tools.py", "_lookup_record_id",
        "f\"{{Name}}='{safe}'\"",
    ),
    # WorldStatus.ACTIVE / similar PascalCase enum-attribute constants are
    # already exempted by _is_constant_like_attribute() below and never
    # reach this baseline — no entries needed for scheduler.py/app.py.
})


def _call_name(node: ast.expr) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_constant_like_attribute(node: ast.expr) -> bool:
    """True for a dotted attribute chain rooted at a PascalCase name, e.g.
    ``WorldStatus.ACTIVE`` or ``LeadOutcome.CONVERTED`` — Python convention
    for a class/enum reference, never attacker-controlled runtime data (as
    opposed to a lowercase instance like ``identity.user_id``)."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name) and node.id[:1].isupper()


class _Scope:
    __slots__ = ("safe_names",)

    def __init__(self) -> None:
        self.safe_names: dict[str, bool] = {}


class FormulaSafetyVisitor(ast.NodeVisitor):
    def __init__(self, path: str):
        self.path = path
        self.findings: list[FormulaFingerprint] = []
        self._scopes: list[_Scope] = [_Scope()]
        self._qualname: list[str] = []
        self._suppress_depth = 0

    # ── scope management ──────────────────────────────────────────
    def _current_qualname(self) -> str:
        return ".".join(self._qualname) if self._qualname else "<module>"

    def _is_expr_safe(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Constant):
            return True
        call_name = _call_name(node)
        if call_name in SANCTIONED_CALL_NAMES:
            return True
        if isinstance(node, ast.Attribute):
            return _is_constant_like_attribute(node)
        if isinstance(node, ast.Name):
            for scope in reversed(self._scopes):
                if node.id in scope.safe_names:
                    return scope.safe_names[node.id]
            return False
        return False

    def _visit_function(self, node) -> None:
        self._qualname.append(node.name)
        self._scopes.append(_Scope())
        self.generic_visit(node)
        self._scopes.pop()
        self._qualname.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._qualname.append(node.name)
        self.generic_visit(node)
        self._qualname.pop()

    # ── assignment tracking (single-Name targets only) ────────────
    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self._scopes[-1].safe_names[node.targets[0].id] = self._is_expr_safe(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.generic_visit(node)
        if isinstance(node.target, ast.Name) and node.value is not None:
            self._scopes[-1].safe_names[node.target.id] = self._is_expr_safe(node.value)

    # ── logging-call suppression ────────────────────────────────────
    @staticmethod
    def _is_logging_call(node: ast.Call) -> bool:
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
        return name in _LOGGING_METHOD_NAMES

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_logging_call(node):
            self._suppress_depth += 1
            self.generic_visit(node)
            self._suppress_depth -= 1
        else:
            self.generic_visit(node)

    # ── the actual detection ───────────────────────────────────────
    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        if self._suppress_depth == 0:
            for i, part in enumerate(node.values):
                if not isinstance(part, ast.FormattedValue):
                    continue
                if i == 0 or not isinstance(node.values[i - 1], ast.Constant):
                    continue
                preceding = node.values[i - 1].value
                if not isinstance(preceding, str) or not _FORMULA_QUOTE_OPEN_RE.search(preceding):
                    continue
                if self._is_expr_safe(part.value):
                    continue
                try:
                    expr_text = ast.unparse(node)
                except Exception:
                    expr_text = "<unparseable>"
                self.findings.append(FormulaFingerprint(self.path, self._current_qualname(), expr_text))
        self.generic_visit(node)


def _iter_tracked_py_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("unable to enumerate tracked .py files; refusing to scan filesystem") from exc
    paths = [p for p in result.stdout.decode("utf-8").split("\0") if p]
    return [
        p for p in paths
        if p not in EXCLUDED_FILES
        and not Path(p).name.startswith(EXCLUDED_FILE_PREFIXES)
        and not p.startswith(EXCLUDED_DIR_PREFIXES)
    ]


def scan_text(path: str, text: str) -> list[FormulaFingerprint]:
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        raise RuntimeError(f"{path}: syntax error: {exc}") from exc
    visitor = FormulaSafetyVisitor(path)
    visitor.visit(tree)
    return sorted(set(visitor.findings))


def scan() -> list[FormulaFingerprint]:
    findings: list[FormulaFingerprint] = []
    for path in _iter_tracked_py_files():
        # utf-8-sig: a handful of tracked files carry a leading UTF-8 BOM,
        # which plain utf-8 decoding leaves in the string as an invalid
        # stray U+FEFF token for ast.parse.
        findings.extend(scan_text(path, (REPO_ROOT / path).read_text(encoding="utf-8-sig")))
    return sorted(set(findings))


def classify(findings: list[FormulaFingerprint]) -> dict[str, list[FormulaFingerprint]]:
    found = set(findings)
    return {
        "legacy": sorted(found & LEGACY_BASELINE),
        "new": sorted(found - LEGACY_BASELINE),
        "missing_legacy": sorted(LEGACY_BASELINE - found),
    }


def report(findings: list[FormulaFingerprint]) -> str:
    groups = classify(findings)
    lines = ["Audit #11 (#11-3) — Airtable Formula Escaping Boundary", ""]
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
    groups = classify(findings)
    if groups["new"]:
        print(
            "FAIL: new unescaped filterByFormula interpolation — route the interpolated "
            "value through tools/airtable_gateway.py's escape_formula_value() before "
            "building the formula string (see BUG_AUDIT_LOG.md 'Audit #11' #11-1).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
