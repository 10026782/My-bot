# test_telegram_dedup_ordering.py
#
# app.py's Telegram webhook used to check idempotency.is_duplicate() AFTER
# the slash-command dispatch (text.startswith("/")) and the /update wizard
# text-capture dispatch (has_pending_text_capture()). Since both of those
# branches `return` immediately once they dispatch, a duplicate delivery of
# a slash command or a wizard reply was never caught by the dedup check at
# all — it was dispatched (and could execute) a second time instead of
# being discarded as "already handled".
#
# Fix: idempotency.is_duplicate() now runs first, before either of those
# checks. This is independent of any other feature — a standalone ordering
# fix to existing code.

import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-dedup-order-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DEDUP_ORDER_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patDedupOrderTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDedupOrderTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-dedup-secret")

import app  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# Structural: dedup call precedes slash-command/wizard-capture checks
# ══════════════════════════════════════════════════
print("\n── structural: dedup check line precedes command/wizard checks ─")
import ast

with open(os.path.join(os.path.dirname(__file__), "app.py"), encoding="utf-8") as f:
    tree = ast.parse(f.read())


def _find_function(name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def _find_if(node, test_substring):
    best = None
    for child in ast.walk(node):
        if isinstance(child, ast.If):
            try:
                rep = ast.unparse(child.test)
            except Exception:
                continue
            if test_substring in rep and (best is None or child.lineno < best.lineno):
                best = child
    return best.lineno if best else None


def _first_call_lineno(node, target_substring):
    best = None
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            try:
                rep = ast.unparse(child.func)
            except Exception:
                continue
            if target_substring in rep and (best is None or child.lineno < best):
                best = child.lineno
    return best


tg_func = _find_function("_webhook_telegram_impl")
text_branch = None
for node in ast.walk(tg_func):
    if isinstance(node, ast.If):
        try:
            rep = ast.unparse(node.test)
        except Exception:
            continue
        if "message.text" in rep:
            text_branch = node
            break
assert text_branch is not None, "text-message branch not found"

dedup_line = _first_call_lineno(text_branch, "idempotency.is_duplicate")
command_if_line = _find_if(text_branch, "text.startswith")
wizard_call_line = _first_call_lineno(text_branch, "has_pending_text_capture")

chk("dedup call found", dedup_line is not None)
chk("slash-command check found", command_if_line is not None)
chk("wizard text-capture check found", wizard_call_line is not None)
chk("dedup runs before slash-command dispatch",
    dedup_line is not None and command_if_line is not None and dedup_line < command_if_line)
chk("dedup runs before wizard text-capture dispatch",
    dedup_line is not None and wizard_call_line is not None and dedup_line < wizard_call_line)


# ══════════════════════════════════════════════════
# Behavioral: a duplicate slash command is discarded, not dispatched twice
# ══════════════════════════════════════════════════
print("\n── behavioral: duplicate slash command is discarded ─────────")

_bot_calls = []


def _stub_process_new_updates(updates):
    _bot_calls.append(("process_new_updates", updates))


def _stub_send_message(*_a, **_kw):
    _bot_calls.append(("send_message", _a, _kw))
    return types.SimpleNamespace(message_id=1)


orig_bot = app.bot
orig_idempotency = app.idempotency
app.bot = types.SimpleNamespace(
    process_new_updates=_stub_process_new_updates,
    send_message=_stub_send_message,
    delete_message=lambda *a, **k: None,
)
app.idempotency = types.SimpleNamespace(is_duplicate=lambda *a, **k: True)  # force "duplicate"

client = app.app.test_client()
update = {
    "update_id": 9001,
    "message": {
        "message_id": 9001, "date": 1710000000,
        "chat": {"id": 777000111, "type": "private"},
        "from": {"id": 777000111, "is_bot": False, "first_name": "Test"},
        "text": "/status",
    },
}
try:
    resp = client.post("/telegram", data=json.dumps(update), headers={
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": "test-dedup-secret",
    })
    chk("webhook responded 200", resp.status_code == 200)
    chk("duplicate slash command NOT dispatched via bot.process_new_updates",
        not any(c[0] == "process_new_updates" for c in _bot_calls))
    chk("'already handled' notice sent instead",
        any(c[0] == "send_message" for c in _bot_calls))
finally:
    app.bot = orig_bot
    app.idempotency = orig_idempotency


print(f"\n{'='*60}\nTelegram dedup ordering: {passed} passed, {failed} failed\n{'='*60}")
sys.exit(1 if failed else 0)
