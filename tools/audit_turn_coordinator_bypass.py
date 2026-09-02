#!/usr/bin/env python3
"""Block regressions to the Turn Coordinator / Single Speaker architecture.

BUG-CRM-BYPASS (01/09/2026, see docs/architecture/action-gateway/
BUG-CRM-BYPASS_DETERMINISTIC_CREATE_DEAL_ROUTE_20260901.md): Deal creation
had a dedicated canonical tool (crm_create_deal) but no deterministic
Intent — every request reached Handler.AGENT, meaning the LLM chose
between crm_create_deal and generic airtable_add. Three separate PRs
(#1165/#1166/#1169) each patched a different gap in the generic-write
interception layer that exists to catch whatever the agent picked, without
ever keeping the agent out of the decision. A fourth PR (#1171) tried to
fix tool selection by improving tool-description prose so the LLM "chooses
correctly" — closed without merging, because that is still the agent
deciding, not the system.

The actual decision: mutation intents backed by a dedicated canonical
write tool must be routed to it DETERMINISTICALLY by
core/router/router.py (Turn Coordinator) before the Agent tool_use loop is
ever entered — mirroring Intent.CREATE_TASK's own long-standing route.
This script is the CI guard against reintroducing any of the ways that
was broken:

  1. ROUTE_REGRESSION — every intent already given a deterministic
     Handler.TOOL gate (the protected set below) must keep it, with a
     matching Handler.CLARIFY fallback for its uncertain case. Checked
     against the CURRENT tree unconditionally (not diff-only) — a working
     route silently disappearing must fail even on an unrelated PR that
     happens to touch router.py.
  2. NEW_TOOL_UNROUTED — a git-diff delta guard (same technique as
     tools/audit_writer_authority_registration.py). A newly added
     ToolMeta entry in tool_registry.py that is requires_approval +
     high_risk and whose name matches the "creates a new business record"
     naming convention (crm_create_*, create_*) must be registered below
     in _TC_ROUTE_REGISTRY as either ROUTED (cross-checked against guard
     1's live gates) or an explicit, reasoned EXEMPT. Anything else blocks
     — a brand-new canonical create-tool must never ship reachable only
     through the Agent's free tool choice.
  3. SCHEMA_NUDGE_LANGUAGE — a git-diff delta guard on tools/schemas.py:
     newly added tool-description text containing routing-by-prose
     phrasing ("לא להשתמש", "must use the dedicated", ...) is blocked
     unless the same diff also touches core/router/router.py — this is
     exactly PR #1171's pattern (fix tool selection by asking the LLM
     nicely instead of routing deterministically).
  4. FINGERPRINT_PAYLOAD_DIVERGENCE — BUG-CRM-BYPASS-FINGERPRINT-PARITY
     (02/09/2026): a deterministic route passed a custom fingerprint_payload
     to _queue_approval_detailed() that structurally diverged from the real
     dispatched tool_inputs — core/action_gateway.py's propose_action()
     computes the STORED business_action_fingerprint from fingerprint_payload
     when one is given, so the stored fingerprint could never match
     tools/dispatcher.py's execution-time recomputation from the real
     payload. Every approved contract failed with "approval-sensitive
     execution proof does not match the action payload" — the exact
     BUG-TASK-01 failure class, recreated by a method whose own docstring
     cited BUG-TASK-01's lesson. Checked against the CURRENT tree
     unconditionally: any call passing a non-None fingerprint_payload must
     be an exact, pre-registered (file, function) exception in
     _FINGERPRINT_DIVERGENCE_REGISTRY with a documented, tested reason the
     divergence is safe (the Task due_time precedent is the only current
     example) — an unregistered one blocks. Removing the custom
     fingerprint_payload entirely (never diverge from the real dispatched
     payload) is always the preferred fix over registering a new exception.
  5. PROTECTED_BUSINESS_TABLE_RAW_UPDATE — BUG-CRM-BYPASS-UPDATE follow-up,
     owner rule (02/09/2026): tools/airtable_tools.py's generic
     "airtable_update" may only write system/infrastructure data (Sessions,
     schema snapshots, tenant config, ...) directly. Business records
     (Leads, Contacts, Deals, Payment Terms, Payments) must either be
     blocked outright or pass through a canonical-writer redirect / a
     field-allowlist + canonicalization gate before ever reaching a raw
     write — never straight through. Checked against the CURRENT tree
     unconditionally: tools/dispatcher.py's `case "airtable_update":` block
     must still contain a recognizable protection signature for every
     entry in _PROTECTED_BUSINESS_TABLE_UPDATE_REGISTRY before that block's
     final, unconditional generic-write fallback line — if a signature
     silently disappears (e.g. someone "simplifies" the case statement and
     drops a branch), this fails even on an unrelated change. A brand-new
     protected business table needs an explicit new registry entry naming
     its protection mechanism — the same "register or fail" discipline as
     guards 2 and 4 above.

Static and read-only. No runtime or persistence side effects.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER_PY = ROOT / "core/router/router.py"
ROUTE_DECISION_PY = ROOT / "core/router/route_decision.py"
TOOL_REGISTRY_PY = ROOT / "tool_registry.py"
SCHEMAS_PY = ROOT / "tools/schemas.py"
DISPATCHER_PY = ROOT / "tools/dispatcher.py"

# Every Intent that MUST keep a live Handler.TOOL (certain) + Handler.CLARIFY
# (uncertain) deterministic gate in core/router/router.py. Adding an intent
# here without the gate existing will make this script fail immediately —
# add the route first, then register it here (or in the same change).
_TC_PROTECTED_INTENTS: tuple[str, ...] = (
    "CREATE_TASK", "UPDATE_TASK", "COMPLETE_TASK", "CREATE_DEAL",
)

# tool_name -> ("ROUTED", "Intent.X") | ("EXEMPT", "reason")
# New entries require explicit owner sign-off — this registry is the
# enforcement point for the 01/09/2026 Turn Coordinator architecture
# decision, not a formality to route around.
_TC_ROUTE_REGISTRY: dict[str, tuple[str, str]] = {
    "crm_create_deal": ("ROUTED", "CREATE_DEAL"),
    "crm_create_payment_term": (
        "EXEMPT",
        "not yet migrated to a deterministic route (scope decision "
        "01/09/2026: Deal first) — tools/dispatcher.py's generic-write "
        "interception (BUG-CRM-BYPASS) remains defense-in-depth; see "
        "ROADMAP.md's Commercial CRM Owner SSOT remediation section.",
    ),
    "crm_create_payment": (
        "EXEMPT",
        "same as crm_create_payment_term — not yet migrated.",
    ),
}

# (file, function_name) -> documented reason a custom fingerprint_payload is
# safe there. New entries require explicit owner sign-off — this is the
# enforcement point for BUG-CRM-BYPASS-FINGERPRINT-PARITY. The bar is the
# same as the Task precedent: the reason must name exactly which key(s)
# differ from the real dispatched payload and why that's provably safe
# (not just "it works today").
_FINGERPRINT_DIVERGENCE_REGISTRY: dict[tuple[str, str], str] = {
    ("app.py", "_queue_deterministic_create_task"): (
        "due_time is deliberately excluded (BUG-156) — Tasks' due-date "
        "field is Airtable type 'date', not 'dateTime', so no write ever "
        "persists a time value; business_identity() agrees with the real "
        "dispatched payload on every other key (table alias, field name)."
    ),
}

# Table-name/mechanism-name literal -> documented protection mechanism.
# Each key must appear, verbatim, somewhere inside tools/dispatcher.py's
# `case "airtable_update":` block (checked by check_protected_business_
# table_raw_update() below) -- if a key silently disappears from that
# source, the corresponding protection was removed, whether or not the
# table name itself was touched. New protected business tables require an
# explicit new entry naming their protection mechanism; a table this
# session's owner rule (02/09/2026) explicitly excludes -- system/
# infrastructure data (Sessions, schema snapshots, tenant config, feature
# flags, ...) -- must NEVER be added here, since airtable_update writing
# those directly is the intended, allowed behavior.
_PROTECTED_BUSINESS_TABLE_UPDATE_REGISTRY: dict[str, str] = {
    "enforce_leads_write_gate": (
        "Leads: blocked outright via enforce_leads_write_gate() -- no "
        "canonical update writer exists or is needed; Lead edits happen "
        "through the TMA UI, never the chat Agent."
    ),
    '"אנשי קשר (Contacts)"': (
        "redirected to the canonical writer crm.update_contact()."
    ),
    "_CRM_TABLE_ROUTING": (
        "Deals/Payment Terms/Payments (BUG-CRM-BYPASS-UPDATE, 02/09/2026): "
        "field-allowlist + domain canonicalization gate reusing the same "
        "closed field maps the create path already validates against -- "
        "no general canonical update writer exists yet (Intent."
        "UPDATE_DEAL_STAGE legitimately depends on this same generic "
        "airtable_update today), so this is the enforceable floor until "
        "one does."
    ),
}

_TOOL_GATE_RE = re.compile(
    r"if\s*\((?P<cond>(?:[^()]|\([^()]*\))*)\)\s*:\s*\n\s*"
    r"risk,\s*handler,\s*needs_approval\s*=\s*Risk\.NEEDS_APPROVAL,\s*Handler\.TOOL,\s*True"
)
_CLARIFY_RE = re.compile(
    r"elif\s+(?P<cond>[^:]+):\s*\n\s*handler\s*=\s*Handler\.CLARIFY"
)
_INTENT_REF_RE = re.compile(r"Intent\.([A-Z_]+)")
_CREATE_TOOL_NAME_RE = re.compile(r"^crm_create_|^create_")

_NUDGE_PHRASES: tuple[str, ...] = (
    "לא להשתמש", "חובה להשתמש", "אל תשתמש", "השתמש רק ב",
    "instead use", "must use the dedicated", "do not use this tool for",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_deterministic_tool_gates(router_source: str) -> dict[str, str]:
    """Intent name -> the if-condition text gating it to Handler.TOOL."""
    gates: dict[str, str] = {}
    for match in _TOOL_GATE_RE.finditer(router_source):
        cond = match.group("cond")
        for name in _INTENT_REF_RE.findall(cond):
            gates.setdefault(name, cond)
    return gates


def find_clarify_gates(router_source: str) -> dict[str, str]:
    """Intent name -> the elif-condition text gating it to Handler.CLARIFY."""
    gates: dict[str, str] = {}
    for match in _CLARIFY_RE.finditer(router_source):
        cond = match.group("cond")
        for name in _INTENT_REF_RE.findall(cond):
            gates.setdefault(name, cond)
    return gates


def check_route_regressions() -> list[str]:
    router_source = _read(ROUTER_PY)
    intent_source = _read(ROUTE_DECISION_PY)
    tool_gates = find_deterministic_tool_gates(router_source)
    clarify_gates = find_clarify_gates(router_source)
    failures: list[str] = []
    for name in _TC_PROTECTED_INTENTS:
        if not re.search(rf"\b{name}\s*=", intent_source):
            failures.append(f"Intent.{name} no longer defined in core/router/route_decision.py")
            continue
        if name not in tool_gates:
            failures.append(
                f"Intent.{name} no longer has a live Handler.TOOL deterministic "
                f"gate in core/router/router.py — the Agent can freely choose a "
                f"tool for this intent again."
            )
            continue
        if "certain" not in tool_gates[name]:
            failures.append(
                f"Intent.{name}'s Handler.TOOL gate no longer checks a "
                f"deterministic parse's .certain flag."
            )
        if name not in clarify_gates:
            failures.append(
                f"Intent.{name} has a Handler.TOOL gate but no matching "
                f"Handler.CLARIFY fallback for its uncertain case — an "
                f"uncertain-but-structured request would fall through to "
                f"Handler.AGENT again."
            )
    return failures


def _added_line_ranges(pathspec: str) -> dict[str, set[int]]:
    result = subprocess.run(
        ["git", "diff", "--unified=0", "origin/main...HEAD", "--", pathspec],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE,
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


@dataclass(frozen=True)
class ToolMetaEntry:
    name: str
    requires_approval: bool
    high_risk: bool
    line: int


def _kw_value(call: ast.Call, key: str):
    for kw in call.keywords:
        if kw.arg == key and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return None


def scan_tool_registry(source: str) -> list[ToolMetaEntry]:
    entries: list[ToolMetaEntry] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return entries
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ToolMeta":
            name = _kw_value(node, "name")
            if not isinstance(name, str):
                continue
            entries.append(ToolMetaEntry(
                name=name,
                requires_approval=bool(_kw_value(node, "requires_approval")),
                high_risk=bool(_kw_value(node, "high_risk")),
                line=node.lineno,
            ))
    return entries


def _baseline_tool_names() -> set[str]:
    try:
        result = subprocess.run(
            ["git", "show", "origin/main:tool_registry.py"],
            cwd=ROOT, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {entry.name for entry in scan_tool_registry(result.stdout)}


def check_new_unrouted_tools() -> list[str]:
    added = _added_line_ranges("tool_registry.py")
    added_lines = added.get("tool_registry.py")
    if not added_lines:
        return []
    baseline_names = _baseline_tool_names()
    router_source = _read(ROUTER_PY)
    routed_intents = set(find_deterministic_tool_gates(router_source))

    failures: list[str] = []
    for entry in scan_tool_registry(_read(TOOL_REGISTRY_PY)):
        if entry.name in baseline_names or entry.line not in added_lines:
            continue
        if not (entry.requires_approval and entry.high_risk):
            continue
        if not _CREATE_TOOL_NAME_RE.search(entry.name):
            continue
        registration = _TC_ROUTE_REGISTRY.get(entry.name)
        if registration is None:
            failures.append(
                f"tool_registry.py:{entry.line} new high-risk create-tool "
                f"'{entry.name}' has no Turn Coordinator route registration "
                f"in tools/audit_turn_coordinator_bypass.py's "
                f"_TC_ROUTE_REGISTRY — add a deterministic Intent/"
                f"Handler.TOOL route (preferred) or an explicit, reasoned "
                f"EXEMPT entry."
            )
            continue
        kind, detail = registration
        if kind == "ROUTED" and detail not in routed_intents:
            failures.append(
                f"tool_registry.py:{entry.line} '{entry.name}' is registered "
                f"as ROUTED to Intent.{detail}, but core/router/router.py has "
                f"no live Handler.TOOL gate for that intent — registration is "
                f"stale or the route was removed."
            )
    return failures


def check_schema_nudge_language() -> list[str]:
    added = _added_line_ranges("tools/schemas.py")
    lines = added.get("tools/schemas.py")
    if not lines:
        return []
    router_touched = bool(_added_line_ranges("core/router/router.py").get("core/router/router.py"))
    if router_touched:
        # Real routing work landed in the same change — prose alongside it
        # (e.g. documenting the new deterministic route in a description)
        # is not the PR #1171 pattern.
        return []
    schema_lines = _read(SCHEMAS_PY).splitlines()
    failures: list[str] = []
    for lineno in sorted(lines):
        if lineno > len(schema_lines):
            continue
        text = schema_lines[lineno - 1]
        for phrase in _NUDGE_PHRASES:
            if phrase in text:
                failures.append(
                    f"tools/schemas.py:{lineno} adds tool-selection guidance "
                    f"('{phrase}') with no matching core/router/router.py "
                    f"change in this diff — this is the PR #1171 pattern "
                    f"(asking the LLM to choose the right tool via prose "
                    f"instead of routing deterministically). Add a real "
                    f"Intent/Handler.TOOL route instead."
                )
    return failures


def find_fingerprint_payload_divergences(source: str) -> list[tuple[str, int]]:
    """Return (enclosing_function_name, line) for every call in `source`
    that passes a non-None fingerprint_payload keyword argument."""
    results: list[tuple[str, int]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.func_stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.func_stack.append(node.name)
            self.generic_visit(node)
            self.func_stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

        def visit_Call(self, node: ast.Call) -> None:
            for kw in node.keywords:
                if kw.arg != "fingerprint_payload":
                    continue
                is_none = isinstance(kw.value, ast.Constant) and kw.value.value is None
                # A same-name passthrough (fingerprint_payload=fingerprint_payload,
                # inside a thin wrapper like _queue_approval_detailed/_impl)
                # introduces no NEW divergence at this call site — whatever
                # value it forwards was already decided by its own caller.
                # Attributing it here would only flag the generic plumbing,
                # never the actual place a custom payload gets constructed.
                is_passthrough = isinstance(kw.value, ast.Name) and kw.value.id == kw.arg
                if not is_none and not is_passthrough:
                    # Attribute to the OUTERMOST enclosing function, not the
                    # innermost — a custom fingerprint_payload built in an
                    # outer scope and used by a nested closure (e.g. Task's
                    # _queue_task() inside _queue_deterministic_create_task())
                    # is owned by the outer function for registry purposes.
                    func_name = self.func_stack[0] if self.func_stack else "<module>"
                    results.append((func_name, node.lineno))
            self.generic_visit(node)

    _Visitor().visit(tree)
    return results


def _tracked_python_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE,
    )
    excluded_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules"}
    paths = []
    for raw in result.stdout.decode().split("\0"):
        if not raw:
            continue
        path = Path(raw)
        if any(part in excluded_dirs for part in path.parts):
            continue
        if path.name.startswith("test_"):
            continue
        paths.append(raw)
    return sorted(paths)


def check_fingerprint_payload_divergence() -> list[str]:
    failures: list[str] = []
    for relpath in _tracked_python_files():
        full = ROOT / relpath
        if not full.exists():
            continue
        for func_name, lineno in find_fingerprint_payload_divergences(_read(full)):
            key = (relpath, func_name)
            if key not in _FINGERPRINT_DIVERGENCE_REGISTRY:
                failures.append(
                    f"{relpath}:{lineno} function '{func_name}' passes a "
                    f"non-None fingerprint_payload — this is the exact "
                    f"BUG-CRM-BYPASS-FINGERPRINT-PARITY/BUG-TASK-01 failure "
                    f"class (a hand-maintained second payload representation "
                    f"that can silently drift from what's actually "
                    f"dispatched, breaking every approved contract's "
                    f"execution proof). Register ({relpath!r}, {func_name!r}) "
                    f"in _FINGERPRINT_DIVERGENCE_REGISTRY with a documented, "
                    f"tested reason the divergence is safe, or — preferred — "
                    f"remove the custom fingerprint_payload entirely so the "
                    f"fingerprint is always computed from the real dispatched "
                    f"payload."
                )
    return failures


_AIRTABLE_UPDATE_CASE_RE = re.compile(
    r'case\s+"airtable_update":\s*\n(?P<body>.*?)(?=\n {12}case\s+"|\Z)',
    re.DOTALL,
)


def find_airtable_update_case_body(dispatcher_source: str) -> str | None:
    """Returns tools/dispatcher.py's `case "airtable_update":` block source
    (from just after the case line to the next same-indent `case` or EOF),
    or None if the case itself can no longer be found at all."""
    match = _AIRTABLE_UPDATE_CASE_RE.search(dispatcher_source)
    return match.group("body") if match else None


def check_protected_business_table_raw_update() -> list[str]:
    """BUG-CRM-BYPASS-UPDATE follow-up, owner rule (02/09/2026): airtable_update
    may only write system/infrastructure data directly -- every business
    table's protection mechanism (block or canonical-writer/allowlist
    redirect) must still be present in tools/dispatcher.py's `case
    "airtable_update":` block. This is a textual-presence check (the same
    rigor level as this script's other guards), not a full control-flow
    proof -- it catches a registered protection's signature silently
    disappearing from the block, not every conceivable new bypass."""
    if not DISPATCHER_PY.exists():
        return [f"{DISPATCHER_PY.relative_to(ROOT)} no longer exists — cannot verify airtable_update protections."]
    source = _read(DISPATCHER_PY)
    body = find_airtable_update_case_body(source)
    if body is None:
        return [
            'tools/dispatcher.py no longer has a `case "airtable_update":` '
            "block at all — every registered business-table protection "
            "(_PROTECTED_BUSINESS_TABLE_UPDATE_REGISTRY) is unverifiable."
        ]
    failures: list[str] = []
    for signature, reason in _PROTECTED_BUSINESS_TABLE_UPDATE_REGISTRY.items():
        if signature not in body:
            failures.append(
                f'tools/dispatcher.py\'s `case "airtable_update":` block no '
                f"longer contains the protection signature {signature!r} — "
                f"its registered protection ({reason}) appears to have been "
                f"removed. Business records must never reach a raw, "
                f"unvalidated airtable_update; restore the protection or, if "
                f"it was deliberately replaced, update "
                f"_PROTECTED_BUSINESS_TABLE_UPDATE_REGISTRY to match the new "
                f"mechanism's signature."
            )
    return failures


def main() -> int:
    failures: list[str] = []
    failures += check_route_regressions()
    failures += check_new_unrouted_tools()
    failures += check_schema_nudge_language()
    failures += check_fingerprint_payload_divergence()
    failures += check_protected_business_table_raw_update()
    if failures:
        print(
            "FAIL: Turn Coordinator / Single Speaker architecture bypass risk detected:",
            file=sys.stderr,
        )
        for item in failures:
            print(f" - {item}", file=sys.stderr)
        return 1
    print("PASS: no Turn Coordinator bypass regressions or unrouted new create-tools detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
