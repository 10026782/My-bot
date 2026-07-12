# test_whatsapp_resolve_identity_scoping.py
#
# app.py's WhatsApp webhook functions (_webhook_whatsapp_impl,
# webhook_meta_whatsapp) each had a local `from identity import
# resolve_identity` further down the function body (inside their media-
# handling try-block). In Python, any local assignment to a name — including
# a nested `from X import Y` — makes that name local to the ENTIRE enclosing
# function, shadowing the module-level import (app.py already has
# `from identity import resolve_identity, Role` at module level) throughout
# the whole function, even before the local import line executes. Any
# reference to `resolve_identity` earlier in the function body than that
# local import raises UnboundLocalError instead of resolving to the
# module-level name.
#
# This was a latent bug even before any new code referenced resolve_identity
# earlier in these functions — removing the now-redundant local imports
# (the name is already available via the module-level import) fixes it
# unconditionally, independent of any other feature built on top.
#
# Structural (AST-based) regression: neither function may contain a local
# `from identity import resolve_identity` (or any other local rebinding of
# the name) anywhere in its body ever again.

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

APP_PATH = os.path.join(os.path.dirname(__file__), "app.py")

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _parse_app():
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return ast.parse(f.read(), filename=APP_PATH)


def _find_function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found in app.py")


def _has_local_resolve_identity_import(func_node) -> bool:
    for node in ast.walk(func_node):
        if isinstance(node, ast.ImportFrom) and node.module == "identity":
            for alias in node.names:
                if alias.name == "resolve_identity":
                    return True
    return False


tree = _parse_app()

print("\n── WhatsApp (Twilio) webhook: no local resolve_identity import ──")
wa_func = _find_function(tree, "_webhook_whatsapp_impl")
chk("_webhook_whatsapp_impl has no local `from identity import resolve_identity`",
    not _has_local_resolve_identity_import(wa_func))

print("\n── Meta WhatsApp webhook: no local resolve_identity import ──────")
meta_func = _find_function(tree, "webhook_meta_whatsapp")
chk("webhook_meta_whatsapp has no local `from identity import resolve_identity`",
    not _has_local_resolve_identity_import(meta_func))

print("\n── module-level resolve_identity import still present ───────────")
has_module_level = any(
    isinstance(node, ast.ImportFrom) and node.module == "identity"
    and any(alias.name == "resolve_identity" for alias in node.names)
    for node in tree.body
)
chk("app.py still imports resolve_identity at module level (line 50)", has_module_level)

print("\n── functional: both functions can reference resolve_identity ────")
# Import app to exercise the real module-level binding — proves the name is
# genuinely resolvable, not just "no local import found" via AST alone.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-scoping-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:SCOPING_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patScopingTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appScopingTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
import app  # noqa: E402

chk("app.resolve_identity is bound at module level and callable",
    callable(getattr(app, "resolve_identity", None)))


print(f"\n{'='*60}\nWhatsApp resolve_identity scoping: {passed} passed, {failed} failed\n{'='*60}")
sys.exit(1 if failed else 0)
