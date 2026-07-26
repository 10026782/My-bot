# test_bug_telegram_idempotency_key.py
#
# Live production verification of BUG-PENDING-APPROVAL-B's global ingress
# gate confirmed the gate itself works (an interrupted "כן" correctly
# re-displayed the pending lead instead of executing). But it exposed a
# NEW blocker: the legitimate second "כן" (the actual reconfirmation) was
# rejected by guards.idempotency as a duplicate of the first "כן" — a dead
# end, since there is no way to "retry" a reconfirmation once its exact
# text has already been marked seen.
#
# Root cause: app.py's Telegram webhook called
# `idempotency.is_duplicate("telegram", sender_user_id, text)` — keying
# the dedup hash on the raw MESSAGE TEXT. Two distinct Telegram messages
# (different update_id/message_id) can legitimately carry identical text
# — most obviously two consecutive "כן" replies — and got treated as the
# same event. guards/idempotency.py's IdempotencyStore itself is fine
# (channel:sender:content → hash); the bug was entirely in what app.py
# passed as `content` for Telegram. WhatsApp's two call sites already pass
# a true unique id (Twilio MessageSid / Meta message id), never text —
# only Telegram's call site had this defect.
#
# Fix: the Telegram call site now passes f"{update.update_id}:
# {update.message.message_id}" as the dedup content — the provider's own
# event identity, chat-scoped via sender_user_id (the existing second
# argument to is_duplicate) — never the message text. Dedup still runs
# before the context gate (ordering unchanged, per explicit instruction
# not to weaken it).

import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-idem-key-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:IDEM_KEY_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patIdemKeyTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appIdemKeyTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-idem-secret")

import app  # noqa: E402
from guards.idempotency import IdempotencyStore  # noqa: E402
from core.action_gateway import ActionGateway, ExecutionLedger  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


TEST_SENDER = 999000222
HEADERS = {
    "Content-Type": "application/json",
    "X-Telegram-Bot-Api-Secret-Token": "test-idem-secret",
}

_bot_calls = []


def _stub_process_new_updates(updates):
    _bot_calls.append(("process_new_updates", updates))


def _stub_send_message(*_a, **_kw):
    _bot_calls.append(("send_message", _a, _kw))
    return types.SimpleNamespace(message_id=1)


def _stub_run_agent(*_a, **_kw):
    _bot_calls.append(("run_agent", _a, _kw))
    return "stub reply"


def _tg_update(update_id: int, message_id: int, text: str, sender_id: int = TEST_SENDER) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id, "date": 1710000000,
            "chat": {"id": sender_id, "type": "private"},
            "from": {"id": sender_id, "is_bot": False, "first_name": "Test"},
            "text": text,
        },
    }


client = app.app.test_client()


def _post(update):
    return client.post("/telegram", data=json.dumps(update), headers=HEADERS)


# ══════════════════════════════════════════════════
# Test 1: same update_id (and message_id) sent twice → second blocked
# ══════════════════════════════════════════════════
print("\n── Test 1: identical update_id twice → second blocked ───────")
orig_bot = app.bot
orig_idempotency = app.idempotency
orig_run_agent = app.run_agent
orig_resolve_identity = app.resolve_identity
app.bot = types.SimpleNamespace(
    process_new_updates=_stub_process_new_updates,
    send_message=_stub_send_message,
    delete_message=lambda *a, **k: None,
)
app.idempotency = IdempotencyStore()  # fresh, isolated from other tests
app.run_agent = _stub_run_agent
app.resolve_identity = lambda *a, **k: types.SimpleNamespace(memory_key="boss_hq:idem_test", role="owner")
try:
    upd = _tg_update(7001, 7001, "/status")
    r1 = _post(upd)
    r2 = _post(upd)  # identical update sent again (Telegram retry semantics)
    chk("first delivery responded 200", r1.status_code == 200)
    chk("second (identical) delivery responded 200", r2.status_code == 200)
    chk("first delivery dispatched the command", any(c[0] == "process_new_updates" for c in _bot_calls))
    chk("second delivery was blocked as duplicate (only one dispatch total)",
        sum(1 for c in _bot_calls if c[0] == "process_new_updates") == 1)
    chk("second delivery got the 'already handled' notice",
        any(c[0] == "send_message" and "כבר טופלה" in str(c[1]) for c in _bot_calls))
finally:
    app.bot, app.idempotency, app.run_agent, app.resolve_identity = (
        orig_bot, orig_idempotency, orig_run_agent, orig_resolve_identity)
    _bot_calls.clear()


# ══════════════════════════════════════════════════
# Test 2: different message IDs with identical "כן" text → both processed
# ══════════════════════════════════════════════════
print("\n── Test 2: identical text, different event ids → both processed ─")
app.bot = types.SimpleNamespace(
    process_new_updates=_stub_process_new_updates,
    send_message=_stub_send_message,
    delete_message=lambda *a, **k: None,
)
app.idempotency = IdempotencyStore()
app.run_agent = _stub_run_agent
app.resolve_identity = lambda *a, **k: types.SimpleNamespace(memory_key="boss_hq:idem_test2", role="owner")
try:
    r1 = _post(_tg_update(7101, 7101, "כן"))
    r2 = _post(_tg_update(7102, 7102, "כן"))  # same text, different update_id/message_id
    chk("first 'כן' responded 200", r1.status_code == 200)
    chk("second 'כן' (different event id) responded 200", r2.status_code == 200)
    run_agent_calls = [c for c in _bot_calls if c[0] == "run_agent"]
    chk("BOTH 'כן' messages reached run_agent (neither blocked as a false duplicate)",
        len(run_agent_calls) == 2)
    chk("no 'already handled' duplicate notice was sent",
        not any(c[0] == "send_message" and "כבר טופלה" in str(c[1]) for c in _bot_calls))
finally:
    app.bot, app.idempotency, app.run_agent, app.resolve_identity = (
        orig_bot, orig_idempotency, orig_run_agent, orig_resolve_identity)
    _bot_calls.clear()


# ══════════════════════════════════════════════════
# Test 3: full reconfirmation sequence with repeated "כן" text (different
# event ids) ends in exactly one execution — composes the real
# IdempotencyStore (proving neither "כן" is falsely blocked) with the real
# ActionGateway state machine (proving the second "כן" alone executes).
# ══════════════════════════════════════════════════
print("\n── Test 3: repeated כן across the reconfirmation flow → one exec ─")
store = IdempotencyStore()
executions = []


def _mock_executor(tool_name, tool_inputs, contract_id):
    executions.append(tool_name)
    return {"ok": True, "external_id": "recTEST", "tool": tool_name}


gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_mock_executor)
user = "boss_hq:idem_test3"
r = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=user,
    tool_name="gmail_send_draft", tool_inputs={"to": "a@b.com"},
    origin_channel="telegram", origin_chat_id="tg:1", requires_approval=True,
)
chk("setup: contract proposed", r.ok)
gw.mark_context_interrupted(user)  # simulates an intervening message via the gate

# First "כן" — event id from update 8001/8001
dup1 = store.is_duplicate("telegram", str(TEST_SENDER), "8001:8001")
chk("first כן not blocked by idempotency", not dup1)
reply1 = gw.route_confirmation_word(user, approver_role="owner")
chk("first כן does not execute — re-shows business description", len(executions) == 0)
chk("first כן reply asks for reconfirmation", "לאשר אותה" in reply1)

# Second "כן" — SAME text, DIFFERENT event id (8002/8002)
dup2 = store.is_duplicate("telegram", str(TEST_SENDER), "8002:8002")
chk("second כן (different event id) not falsely blocked despite identical text", not dup2)
reply2 = gw.route_confirmation_word(user, approver_role="owner")
chk("second כן executes exactly once", len(executions) == 1)
chk("second כן reply reports canonical success", "הפעולה הושלמה" in reply2)

# Replaying the exact same second update again (retry) — this one SHOULD be blocked
dup2_retry = store.is_duplicate("telegram", str(TEST_SENDER), "8002:8002")
chk("a true retry of the same event id IS blocked", dup2_retry)


print(f"\n{'='*60}\nTelegram idempotency key fix: {passed} passed, {failed} failed\n{'='*60}")
sys.exit(1 if failed else 0)
