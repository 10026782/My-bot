#!/usr/bin/env python3
"""Automated smoke tests for BOSS.

Run:
    python smoke_tests.py
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent

CRITICAL_IMPORT_ENV = {
    "ANTHROPIC_API_KEY": "sk-ant-smoke-test",
    "TELEGRAM_TOKEN": "123456789:SMOKE_TEST",
    "AIRTABLE_API_KEY": "patSmokeTest",
    "AIRTABLE_BASE_ID": "appSmokeTest",
    "RENDER_APP_URL": "https://example.com",
    "SETUP_WEBHOOK": "0",
}

REQUIRED_IMPORTS = [
    "app",
    "tools.dispatcher",
    "airtable_schema",
    "crm",
    "daily_digest",
]

REQUIRED_TOOLS = {
    "airtable_add",
    "airtable_get",
    "calendar_get_events",
}

# Legacy literal table names to guard against hardcoding instead of using
# Tables.* constants — historically these were common mistakes for the
# Hebrew-named live tables (Tables.TASKS="משימות (Tasks)", Tables.DEALS=
# "עסקאות (Deals)"). NOTE (30/08/2026, Track 8 schema/data-contract audit):
# "Payments" is no longer purely a legacy literal — Tables.PAYMENTS is now
# itself the canonical English name for the separate, live Canonical
# Deal/Payment Architecture "Payments" table (see airtable_schema.py's
# PaymentFields/commercial_crm.py), distinct from the older Hebrew
# "תשלומים (Payments)" table. This AST check only flags a hardcoded string
# literal "Payments" passed directly to an Airtable call (not the Tables.
# PAYMENTS constant), so it does not block correct current usage — kept here
# only as a reminder that "Payments" is ambiguous between two real tables and
# any new literal-string use of it should be double-checked against which one
# is intended.
OLD_TABLE_NAMES = {"Tasks", "Deals", "Payments"}
AIRTABLE_CALLS = {
    "airtable_get",
    "airtable_add",
    "airtable_update",
    "_get",
    "_post",
    "_patch",
    "_at_list",
    "_at_post",
    "_at_patch",
}
FAKE_APPROVAL_TEXT = "אשר עם: ✅ כן / ❌ לא"


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


def _prepare_env() -> None:
    for key, value in CRITICAL_IMPORT_ENV.items():
        os.environ[key] = value


def _module_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.py")
        if path.name != Path(__file__).name
        and not path.name.startswith("test_")
        and ".git" not in path.parts
    )


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _line(path: Path, node: ast.AST) -> str:
    return f"{path.relative_to(ROOT)}:{getattr(node, 'lineno', '?')}"


def _iter_strings(node: ast.AST) -> list[ast.Constant]:
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def run_check(name: str, fn: Callable[[], str | None]) -> Result:
    try:
        detail = fn() or ""
        return Result(name=name, ok=True, detail=detail)
    except AssertionError as exc:
        return Result(name=name, ok=False, detail=str(exc))
    except Exception as exc:
        return Result(name=name, ok=False, detail=f"{type(exc).__name__}: {exc}")


def check_imports() -> str:
    _prepare_env()
    imported = []
    for module_name in REQUIRED_IMPORTS:
        importlib.import_module(module_name)
        imported.append(module_name)
    return ", ".join(imported)


def check_airtable_schema() -> str:
    from airtable_schema import Tables

    for attr in ("LEADS", "TASKS", "DEALS", "PAYMENTS", "CONTACTS"):
        assert hasattr(Tables, attr), f"Tables.{attr} is missing"

    expected = {
        "TASKS": "משימות (Tasks)",
        "DEALS": "עסקאות (Deals)",
        "PAYMENTS": "Payments",
        "CONTACTS": "אנשי קשר (Contacts)",
    }
    for attr, value in expected.items():
        actual = getattr(Tables, attr)
        assert actual == value, f"Tables.{attr} = {actual!r}, expected {value!r}"

    return "Tables constants match production Hebrew table names"


def check_field_mapping() -> str:
    from airtable_schema import DealFields, PaymentFields, TaskFields

    assert TaskFields.NAME == "כותרת המשימה", "TaskFields.NAME mismatch"
    assert DealFields.STATUS == "שלב", "DealFields.STATUS mismatch"
    assert PaymentFields.STATUS == "status", "PaymentFields.STATUS mismatch"
    assert PaymentFields.DATE == "date", "PaymentFields.DATE mismatch"
    return "critical Airtable fields match production"


def check_tools() -> str:
    from tool_registry import get as get_tool
    from tools.dispatcher import dispatch_tool
    from tools.schemas import TOOL_SCHEMAS

    assert callable(dispatch_tool), "dispatch_tool is not callable"

    dispatcher_source = inspect.getsource(dispatch_tool)
    schema_names = {schema.get("name") for schema in TOOL_SCHEMAS}

    missing = []
    for name in sorted(REQUIRED_TOOLS):
        if get_tool(name) is None:
            missing.append(f"{name} missing from tool_registry")
        if name not in schema_names:
            missing.append(f"{name} missing from TOOL_SCHEMAS")
        if f'case "{name}"' not in dispatcher_source:
            missing.append(f"{name} missing from dispatch_tool")

    assert not missing, "; ".join(missing)
    return ", ".join(sorted(REQUIRED_TOOLS))


def check_daily_digest() -> str:
    daily_digest = importlib.import_module("daily_digest")

    digest_fn = None
    for name in ("build_digest", "generate_daily_digest", "build_daily_digest", "generate_digest"):
        candidate = getattr(daily_digest, name, None)
        if callable(candidate):
            digest_fn = candidate
            break

    assert digest_fn is not None, "no build/generate daily digest function found"

    original_fetch = getattr(daily_digest, "_fetch", None)
    if original_fetch is not None:
        daily_digest._fetch = lambda *args, **kwargs: []  # type: ignore[attr-defined]

    try:
        result = digest_fn()
    finally:
        if original_fetch is not None:
            daily_digest._fetch = original_fetch  # type: ignore[attr-defined]

    assert isinstance(result, str), f"{digest_fn.__name__} returned {type(result).__name__}"
    assert result.strip(), f"{digest_fn.__name__} returned an empty string"
    return f"{digest_fn.__name__} returned {len(result)} characters"


class SafetyVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[str] = []
        self.function_stack: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in AIRTABLE_CALLS and node.args:
            table = _constant_string(node.args[0])
            if table in OLD_TABLE_NAMES:
                self.violations.append(
                    f"{_line(self.path, node)} hardcoded old table name {table!r} in {name}(); use Tables constants"
                )

        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and len(node.args) >= 2
        ):
            env_key = _constant_string(node.args[0])
            default = _constant_string(node.args[1])
            if env_key and "TABLE" in env_key and default in OLD_TABLE_NAMES:
                self.violations.append(
                    f"{_line(self.path, node)} hardcoded old table default {default!r}; use Tables constants"
                )

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and FAKE_APPROVAL_TEXT in node.value:
            # core_knowledge.py contains a static safety manifest that shows
            # forbidden example phrasing. That text is not user-facing execution
            # output and should not weaken the real approval-queue check.
            if (
                self.path.name == "core_knowledge.py"
                and "BOSS NEVER FAKES CONTROL" in node.value
            ):
                return
            if not self._inside_real_approval_queue():
                self.violations.append(
                    f"{_line(self.path, node)} fake approval text without real approval queue"
                )

    def _inside_real_approval_queue(self) -> bool:
        if not self.function_stack:
            return False
        current = self.function_stack[-1]
        strings = " ".join(s.value for s in _iter_strings(current))
        calls = {_call_name(call.func) for call in ast.walk(current) if isinstance(call, ast.Call)}
        return "request_approval" in calls or "InlineKeyboardButton" in calls or "בקשת אישור" in strings


def check_safety() -> str:
    violations: list[str] = []
    for path in _module_files():
        tree = _parse(path)
        visitor = SafetyVisitor(path)
        visitor.visit(tree)
        violations.extend(visitor.violations)

    assert not violations, "\n".join(violations)
    return "no unsafe legacy table-name calls or fake approval text found"


# Decision Hub / Core Reasoning Layer entrypoints whose live-wiring state is
# declared explicitly here. `expected_wired=True` means some non-test module
# other than the defining file must import it (a regression guard). The
# `expected_wired=False` entries are the known governance-drift cases (merged
# but unreachable, per the 2026-06-29 governance repair) — flipping one to
# True here is only correct once a real caller exists, which this check
# enforces both ways.
DECISION_HUB_ENTRYPOINTS = [
    ("decision_attention", "decision_attention.py", True,
     "F19 — wired via cmd_decision.py _format_decision_card()"),
    ("decision_orchestrator", "decision_orchestrator.py", True,
     "F21 — wired via cmd_decision.py _format_decision_card()"),
    ("decision_matching", "decision_matching.py", True,
     "wired via cmd_decision.py _suggest_decision_link()"),
    ("decision_auto_ingestion", "decision_auto_ingestion.py", False,
     "F20 — merged but unreachable; no caller in app.py/inbound_handler.py/"
     "email_inbound.py/voice_adapter.py. See ROADMAP.md F20 governance note."),
    ("core.reasoning_engines", "core/reasoning_engines.py", False,
     "Core Reasoning Layer — run() has no caller outside its own tests."),
    ("core.adapters.decision_adapter", "core/adapters/decision_adapter.py", True,
     "F22 — wired via cmd_decision.py _format_decision_card() as a fallback "
     "reasoning block, used only when FEATURE_DECISION_HUB is disabled "
     "(29/06/2026)."),
    ("core.adapters.leads_adapter", "core/adapters/leads_adapter.py", False,
     "Core Reasoning Layer — append_reasoning_block() has no caller outside its own tests."),
]


# Files that are actual live pipeline entrypoints per CLAUDE.md's documented
# inbound flow + scheduled jobs. A module is "wired" only if one of these
# imports it directly — being imported only by another unreachable module
# (transitively dead code) does not count, since that's the exact drift this
# check exists to catch.
LIVE_ENTRYPOINT_FILES = {
    "app.py", "cmd_decision.py", "inbound_handler.py", "email_inbound.py",
    "voice_adapter.py", "scheduler.py", "worker.py", "daily_digest.py",
    "daily_collector.py", "tools/dispatcher.py",
}


def _module_referenced(module_name: str, defining_path: Path) -> bool:
    """True if some live entrypoint file directly imports `module_name`."""
    short_name = module_name.rsplit(".", 1)[-1]
    for path in _module_files():
        if path == defining_path:
            continue
        if str(path.relative_to(ROOT)) not in LIVE_ENTRYPOINT_FILES:
            continue
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == module_name or alias.name == short_name for alias in node.names):
                    return True
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod == module_name or mod == short_name or mod.endswith("." + short_name):
                    return True
    return False


def check_decision_hub_call_sites() -> str:
    """Catch 'feature file exists but has zero call sites' drift.

    Compares the declared wiring state of each Decision Hub / Core Reasoning
    entrypoint against the real import graph, so a feature can't be silently
    wired in (or silently un-wired) without this check forcing a matching
    documentation/manifest update.
    """
    mismatches: list[str] = []
    for module_name, defining_rel, expected_wired, note in DECISION_HUB_ENTRYPOINTS:
        actual_wired = _module_referenced(module_name, ROOT / defining_rel)
        if actual_wired != expected_wired:
            mismatches.append(
                f"{module_name}: expected wired={expected_wired}, actual={actual_wired} ({note})"
            )

    assert not mismatches, "\n".join(mismatches)
    return f"{len(DECISION_HUB_ENTRYPOINTS)} Decision Hub entrypoints match their declared wiring state"


def check_marketing_capture_ownership() -> str:
    """F23: a pending /marketing_new MarketingCaptureState must claim the
    user's next text before run_agent() ever sees it (mirrors cmd_update's
    has_pending_text_capture() ownership check) — otherwise every wizard
    reply silently leaks to the general Agent. Static source-order check
    (no live webhook harness exists) so this can't regress unnoticed if
    _webhook_telegram_impl is reordered or the check is deleted.
    """
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    impl_start = source.index("def _webhook_telegram_impl():")
    next_def = source.index("\ndef ", impl_start + 1)
    impl_body = source[impl_start:next_def]

    ownership_pos = impl_body.find("has_pending_capture(")
    # "reply = run_agent(" (the actual call), not just any "run_agent(" —
    # several comments above it mention "run_agent()" in prose and would
    # otherwise match first.
    run_agent_pos = impl_body.find("reply = run_agent(")

    assert ownership_pos != -1, "cmd_marketing.has_pending_capture(...) call missing from _webhook_telegram_impl"
    assert run_agent_pos != -1, "the 'reply = run_agent(...)' call missing from _webhook_telegram_impl"
    assert ownership_pos < run_agent_pos, (
        "has_pending_capture(...) must be checked before run_agent(...) in "
        "_webhook_telegram_impl, or pending Marketing wizard replies leak to the Agent"
    )
    return "has_pending_capture() ownership check precedes run_agent() in _webhook_telegram_impl"


def main() -> int:
    checks = [
        ("Import test", check_imports),
        ("Airtable schema sanity", check_airtable_schema),
        ("Critical field mapping", check_field_mapping),
        ("Tool registry / dispatcher sanity", check_tools),
        ("Daily digest sanity", check_daily_digest),
        ("Safety checks", check_safety),
        ("Decision Hub call-site governance", check_decision_hub_call_sites),
        ("Marketing capture ownership governance", check_marketing_capture_ownership),
    ]

    print("BOSS automated smoke tests")
    print("=" * 28)

    results = [run_check(name, fn) for name, fn in checks]
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {result.name}")
        if result.detail:
            for line in result.detail.splitlines():
                print(f"  {line}")

    failed = [result for result in results if not result.ok]
    print("=" * 28)
    if failed:
        print(f"FAIL: {len(failed)} smoke check(s) failed")
        return 1

    print("PASS: all smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
