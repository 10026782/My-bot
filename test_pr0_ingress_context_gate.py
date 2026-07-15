# test_pr0_ingress_context_gate.py — BUG-PENDING-APPROVAL-B, global ingress gate
#
# Follow-up to the run_agent()-internal fix (test_pr0_pending_approval_context_
# safety.py): a live production log showed "/update" + its wizard free-text
# reply never interrupted a pending lead-write contract, because both are
# dispatched by a code path in app.py's webhook that never calls run_agent()
# at all. Root cause: the interrupt-marking hook lived *inside* run_agent(),
# so anything handled elsewhere (slash commands, callback buttons, wizard
# text/file capture, general media, Decision Hub attachment references, the
# WhatsApp webhooks) was invisible to it.
#
# Fix: a single ingress-boundary gate (app.py's _apply_ingress_context_gate),
# called once per inbound webhook event for both channels, right after
# authentication + junk/idempotency/duplicate filtering + identity
# resolution, before ANY callback/command/wizard/media/Decision Hub/Agent/
# early-return routing. These are webhook-level integration tests — they
# POST simulated payloads at the real Flask routes and inspect real
# ActionGateway contract state, with only the heavy/network-touching
# internals (bot dispatch, run_agent, signature validation) stubbed out.

import json
import os
import sys
import types
import uuid

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-pr0-gate-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PR0_GATE_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPr0GateTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPr0GateTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")

import app  # noqa: E402  (env vars above must be set before import)
from core.action_gateway import action_gateway, ActionGateway, ExecutionLedger  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


TEST_USER = "boss_hq:pr0_gate_test_user"
TG_SENDER_ID = 555000111
TG_HEADERS = {
    "Content-Type": "application/json",
    "X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret",
}


def _fake_identity(*_args, **_kwargs):
    return types.SimpleNamespace(memory_key=TEST_USER, role="owner")


def _fresh_contract():
    r = action_gateway.propose_action(
        tenant_id="boss_hq", canonical_user_id=TEST_USER,
        tool_name="gmail_send_draft", tool_inputs={"to": "x@y.com", "subject": uuid.uuid4().hex},
        origin_channel="telegram", origin_chat_id="tg:1",
        requires_approval=True,
    )
    assert r.ok, f"setup: propose_action failed: {r.reason}"
    return r.contract_id


def _is_interrupted(contract_id: str) -> bool:
    c = action_gateway.find_contract(contract_id)
    return bool(c and c.context_interrupted)


def _patch_common(monkeypatch_targets: dict) -> dict:
    """Applies attribute patches on `app`, returns the originals for restore."""
    originals = {}
    for name, value in monkeypatch_targets.items():
        originals[name] = getattr(app, name)
        setattr(app, name, value)
    return originals


def _restore(originals: dict) -> None:
    for name, value in originals.items():
        setattr(app, name, value)


_bot_calls = []


def _stub_process_new_updates(updates):
    _bot_calls.append(("process_new_updates", updates))


def _stub_send_message(*_a, **_kw):
    _bot_calls.append(("send_message", _a, _kw))
    return types.SimpleNamespace(message_id=1)


def _stub_delete_message(*_a, **_kw):
    pass


def _stub_handle_approval_callback(cq):
    _bot_calls.append(("handle_approval_callback", cq))


def _stub_handle_telegram_media(msg):
    _bot_calls.append(("handle_telegram_media", msg))


def _stub_run_agent(*_a, **_kw):
    return "stub reply"


def _stub_bot():
    return types.SimpleNamespace(
        process_new_updates=_stub_process_new_updates,
        send_message=_stub_send_message,
        delete_message=_stub_delete_message,
    )


def _base_env():
    """Standard patch set for every Telegram test: fake identity, no-op bot
    dispatch/send, stub run_agent, idempotency off by default."""
    return {
        "resolve_identity": _fake_identity,
        "run_agent": _stub_run_agent,
        "bot": _stub_bot(),
    }


client = app.app.test_client()


def _tg_text_update(update_id: int, text: str, sender_id: int = TG_SENDER_ID) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id, "date": 1710000000,
            "chat": {"id": sender_id, "type": "private"},
            "from": {"id": sender_id, "is_bot": False, "first_name": "Test"},
            "text": text,
        },
    }


def _tg_callback_update(update_id: int, data: str, sender_id: int = TG_SENDER_ID) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": str(update_id),
            "from": {"id": sender_id, "is_bot": False, "first_name": "Test"},
            "message": {
                "message_id": update_id, "date": 1710000000,
                "chat": {"id": sender_id, "type": "private"}, "text": "x",
            },
            "chat_instance": str(sender_id),
            "data": data,
        },
    }


def _tg_document_update(update_id: int, sender_id: int = TG_SENDER_ID) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id, "date": 1710000000,
            "chat": {"id": sender_id, "type": "private"},
            "from": {"id": sender_id, "is_bot": False, "first_name": "Test"},
            "document": {"file_id": "doc1", "file_unique_id": "doc1u", "file_name": "x.pdf"},
        },
    }


def _post_tg(update: dict):
    return client.post("/telegram", data=json.dumps(update), headers=TG_HEADERS)


# ══════════════════════════════════════════════════
# T1: Telegram slash command interrupts a live contract
# ══════════════════════════════════════════════════
print("\n── T1: Telegram slash command interrupts ─────────────────────")
cid = _fresh_contract()
chk("T1 setup: contract starts NOT interrupted", not _is_interrupted(cid))
originals = _patch_common({**_base_env(), "idempotency": types.SimpleNamespace(is_duplicate=lambda *a, **k: False)})
try:
    resp = _post_tg(_tg_text_update(1001, "/status"))
    chk("T1: webhook responded 200", resp.status_code == 200)
    chk("T1: slash command dispatched via bot.process_new_updates", any(c[0] == "process_new_updates" for c in _bot_calls))
    chk("T1: contract now interrupted", _is_interrupted(cid))
finally:
    _restore(originals)
    _bot_calls.clear()


# ══════════════════════════════════════════════════
# T2: Telegram wizard text-capture (mid-/update) interrupts
# ══════════════════════════════════════════════════
print("\n── T2: wizard text-capture (mid-/update) interrupts ──────────")
cid = _fresh_contract()
originals = _patch_common({**_base_env(), "idempotency": types.SimpleNamespace(is_duplicate=lambda *a, **k: False)})
import cmd_update
_orig_has_pending_text_capture = cmd_update.has_pending_text_capture
cmd_update.has_pending_text_capture = lambda uid: True
try:
    resp = _post_tg(_tg_text_update(1002, "בדיקה"))
    chk("T2: webhook responded 200", resp.status_code == 200)
    chk("T2: wizard capture dispatched via bot.process_new_updates", any(c[0] == "process_new_updates" for c in _bot_calls))
    chk("T2: contract now interrupted", _is_interrupted(cid))
finally:
    cmd_update.has_pending_text_capture = _orig_has_pending_text_capture
    _restore(originals)
    _bot_calls.clear()


# ══════════════════════════════════════════════════
# T3: unrelated Telegram callback (not approve:/reject:) interrupts
# ══════════════════════════════════════════════════
print("\n── T3: unrelated callback interrupts ─────────────────────────")
cid = _fresh_contract()
originals = _patch_common(_base_env())
try:
    resp = _post_tg(_tg_callback_update(1003, "upd_domain:media"))
    chk("T3: webhook responded 200", resp.status_code == 200)
    chk("T3: contract now interrupted", _is_interrupted(cid))
finally:
    _restore(originals)
    _bot_calls.clear()


# ══════════════════════════════════════════════════
# T3b: CORRECTED 15/07/2026 (BUG-APPROVAL-CALLBACK-CONTEXT-INTERRUPT) —
# approve:/reject: callbacks are themselves legitimate resolution events
# (exactly like a "מאשר"/"לא" text confirm exempted above), not an
# unrelated message that happened to arrive while a contract was pending.
# This used to mark unrelated ActionGateway contracts interrupted on every
# button press, including a legitimate approve/reject of that very same
# contract — production-verified regression, fixed by exempting
# kind="callback" events whose data starts with "approve:"/"reject:".
# ══════════════════════════════════════════════════
print("\n── T3b: approve:/reject: callback does NOT interrupt ActionGateway ─")
cid = _fresh_contract()
originals = _patch_common(_base_env())
originals["_handle_approval_callback"] = app._handle_approval_callback
app._handle_approval_callback = _stub_handle_approval_callback
try:
    resp = _post_tg(_tg_callback_update(1004, "approve:abc123"))
    chk("T3b: webhook responded 200", resp.status_code == 200)
    chk("T3b: routed to _handle_approval_callback (mechanism #2, unrelated)",
        any(c[0] == "handle_approval_callback" for c in _bot_calls))
    chk("T3b: ActionGateway contract NOT marked interrupted by an approve:/reject: callback",
        not _is_interrupted(cid))
finally:
    _restore(originals)
    _bot_calls.clear()


# ══════════════════════════════════════════════════
# T4: general Telegram media (document, no pending file capture) interrupts
# ══════════════════════════════════════════════════
print("\n── T4: general media (document) interrupts ───────────────────")
cid = _fresh_contract()
originals = _patch_common(_base_env())
originals["_handle_telegram_media"] = app._handle_telegram_media
app._handle_telegram_media = _stub_handle_telegram_media
import cmd_update as _cu
_orig_has_pending_file_capture = _cu.has_pending_file_capture
_cu.has_pending_file_capture = lambda uid: False
try:
    resp = _post_tg(_tg_document_update(1005))
    chk("T4: webhook responded 200", resp.status_code == 200)
    chk("T4: routed to general media handler", any(c[0] == "handle_telegram_media" for c in _bot_calls))
    chk("T4: contract now interrupted", _is_interrupted(cid))
finally:
    _cu.has_pending_file_capture = _orig_has_pending_file_capture
    _restore(originals)
    _bot_calls.clear()


# ══════════════════════════════════════════════════
# T5: Decision Hub attachment reference interrupts
# ══════════════════════════════════════════════════
print("\n── T5: Decision Hub attachment reference interrupts ──────────")
cid = _fresh_contract()
originals = _patch_common({**_base_env(), "idempotency": types.SimpleNamespace(is_duplicate=lambda *a, **k: False)})
originals["_flag_enabled"] = app._flag_enabled
app._flag_enabled = lambda name: True if name == "FEATURE_DECISION_HUB" else False
import cmd_decision
_orig_is_attachment_reference = cmd_decision.is_attachment_reference
_orig_handle_attachment_reference = cmd_decision.handle_attachment_reference
cmd_decision.is_attachment_reference = lambda text: True
cmd_decision.handle_attachment_reference = lambda bot, identity, chat_id, text: True
try:
    resp = _post_tg(_tg_text_update(1006, "זה הנספח"))
    chk("T5: webhook responded 200", resp.status_code == 200)
    chk("T5: contract now interrupted", _is_interrupted(cid))
finally:
    cmd_decision.is_attachment_reference = _orig_is_attachment_reference
    cmd_decision.handle_attachment_reference = _orig_handle_attachment_reference
    _restore(originals)


# ══════════════════════════════════════════════════
# T6: genuine "כן" is EXEMPT — does not interrupt (is_own_resolution_event)
# ══════════════════════════════════════════════════
print("\n── T6: genuine כן is exempt, does not interrupt ──────────────")
cid = _fresh_contract()
originals = _patch_common({**_base_env(), "idempotency": types.SimpleNamespace(is_duplicate=lambda *a, **k: False)})
try:
    resp = _post_tg(_tg_text_update(1007, "כן"))
    chk("T6: webhook responded 200", resp.status_code == 200)
    chk("T6: contract NOT interrupted by its own confirmation", not _is_interrupted(cid))
finally:
    _restore(originals)


# ══════════════════════════════════════════════════
# T7: duplicate Telegram message does NOT interrupt (filtered before gate)
# ══════════════════════════════════════════════════
print("\n── T7: duplicate message does not interrupt ──────────────────")
cid = _fresh_contract()
originals = _patch_common({**_base_env(), "idempotency": types.SimpleNamespace(is_duplicate=lambda *a, **k: True)})
try:
    resp = _post_tg(_tg_text_update(1008, "הודעה כלשהי לא קשורה"))
    chk("T7: webhook responded 200", resp.status_code == 200)
    chk("T7: contract NOT interrupted (duplicate filtered before the gate)", not _is_interrupted(cid))
finally:
    _restore(originals)


# ══════════════════════════════════════════════════
# T8: WhatsApp (Twilio) message interrupts
# ══════════════════════════════════════════════════
print("\n── T8: WhatsApp (Twilio) message interrupts ──────────────────")
cid = _fresh_contract()
originals = _patch_common({
    **_base_env(),
    "idempotency": types.SimpleNamespace(is_duplicate=lambda *a, **k: False),
    "_validate_twilio_signature": lambda: True,
})
try:
    resp = client.post("/whatsapp", data={
        "Body": "עדכון סטטוס לא קשור", "From": "whatsapp:+972500000000",
        "To": "whatsapp:+972500000001", "MessageSid": "SMtest8",
    })
    chk("T8: webhook responded", resp.status_code in (200, 204))
    chk("T8: contract now interrupted", _is_interrupted(cid))
finally:
    _restore(originals)


# ══════════════════════════════════════════════════
# T9: WhatsApp (Twilio) junk/empty inbound does NOT interrupt
# ══════════════════════════════════════════════════
print("\n── T9: WhatsApp junk inbound does not interrupt ──────────────")
cid = _fresh_contract()
originals = _patch_common({
    **_base_env(),
    "idempotency": types.SimpleNamespace(is_duplicate=lambda *a, **k: False),
    "_validate_twilio_signature": lambda: True,
})
try:
    resp = client.post("/whatsapp", data={
        "Body": "", "From": "whatsapp:+972500000000",
        "To": "whatsapp:+972500000001", "MessageSid": "SMtest9",
    })
    chk("T9: webhook responded", resp.status_code in (200, 204))
    chk("T9: contract NOT interrupted (junk filtered before the gate)", not _is_interrupted(cid))
finally:
    _restore(originals)


# ══════════════════════════════════════════════════
# T10: Meta WhatsApp message interrupts
# ══════════════════════════════════════════════════
print("\n── T10: Meta WhatsApp message interrupts ─────────────────────")
cid = _fresh_contract()
originals = _patch_common({
    **_base_env(),
    "idempotency": types.SimpleNamespace(is_duplicate=lambda *a, **k: False),
    "_validate_meta_signature": lambda: True,
})
meta_payload = {
    "entry": [{
        "changes": [{
            "value": {
                "metadata": {"display_phone_number": "972500000001"},
                "messages": [{
                    "id": "wamid.test10", "from": "972500000000",
                    "type": "text", "text": {"body": "עדכון לא קשור"},
                }],
            },
        }],
    }],
}
try:
    resp = client.post("/webhooks/meta/whatsapp", data=json.dumps(meta_payload),
                        content_type="application/json")
    chk("T10: webhook responded 200", resp.status_code == 200)
    chk("T10: contract now interrupted", _is_interrupted(cid))
finally:
    _restore(originals)


def _is_integrity_unknown(contract_id: str) -> bool:
    c = action_gateway.find_contract(contract_id)
    return bool(c and c.context_integrity_unknown)


# ══════════════════════════════════════════════════
# T11 (unit-level, not webhook-level): fail-closed fallback path — when the
# primary mark_context_interrupted() raises, the contract must NOT be left
# looking "context intact"; it must be marked context_integrity_unknown
# (a distinct, observable flag) via an independently-written fallback, and
# the incoming message must still be allowed to route (no crash/abort).
# ══════════════════════════════════════════════════
print("\n── T11: fail-closed fallback when the primary mark raises ────")
cid = _fresh_contract()


def _raising_mark_context_interrupted(_user):
    raise RuntimeError("simulated ledger failure")


orig_mark = action_gateway.mark_context_interrupted
action_gateway.mark_context_interrupted = _raising_mark_context_interrupted
try:
    app._apply_ingress_context_gate(
        types.SimpleNamespace(memory_key=TEST_USER, role="owner"),
        app._IngressEvent(channel="telegram", kind="callback"),
    )
    chk("T11: contract NOT left looking context-intact (context_interrupted stays as-is)",
        not _is_interrupted(cid))
    chk("T11: contract marked context_integrity_unknown via the independent fallback",
        _is_integrity_unknown(cid))
finally:
    action_gateway.mark_context_interrupted = orig_mark


# ══════════════════════════════════════════════════
# T12: context_integrity_unknown gates identically to context_interrupted —
# a bare כן on a contract marked "unknown" (never actually interrupted, just
# unrecordable) must still re-show the business description, not execute.
# ══════════════════════════════════════════════════
print("\n── T12: context_integrity_unknown blocks direct execution ────")
executions = []


def _mock_executor(tool_name, tool_inputs, contract_id):
    executions.append(tool_name)
    return {"ok": True, "external_id": "recTEST", "tool": tool_name}


_gw2 = ActionGateway(ledger=ExecutionLedger(), tool_executor=_mock_executor)
r = _gw2.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:t12_user",
    tool_name="gmail_send_draft", tool_inputs={"to": "a@b.com"},
    origin_channel="telegram", origin_chat_id="tg:1", requires_approval=True,
)
_gw2.mark_context_integrity_unknown("boss_hq:t12_user")
reply = _gw2.route_confirmation_word("boss_hq:t12_user", approver_role="owner")
chk("T12: not executed — integrity-unknown contract requires reconfirmation too",
    len(executions) == 0)
chk("T12: reply asks for reconfirmation, same as a real interruption", "לאשר אותה" in reply)
reply2 = _gw2.route_confirmation_word("boss_hq:t12_user", approver_role="owner")
chk("T12: second כן executes normally once reconfirmed", len(executions) == 1 and "בוצע" in reply2)


# ══════════════════════════════════════════════════
# T13: double failure (primary AND fallback both raise) — logs CRITICAL,
# does not crash, and the webhook still returns normally (message routes).
# ══════════════════════════════════════════════════
print("\n── T13: double failure logs CRITICAL, never crashes the request ─")
cid = _fresh_contract()


def _raising_fallback(_user):
    raise RuntimeError("simulated fallback failure too")


orig_mark2 = action_gateway.mark_context_interrupted
orig_fallback = action_gateway.mark_context_integrity_unknown
action_gateway.mark_context_interrupted = _raising_mark_context_interrupted
action_gateway.mark_context_integrity_unknown = _raising_fallback
try:
    try:
        app._apply_ingress_context_gate(
            types.SimpleNamespace(memory_key=TEST_USER, role="owner"),
            app._IngressEvent(channel="telegram", kind="callback"),
        )
        chk("T13: gate call itself does not raise even when both paths fail", True)
    except Exception:
        chk("T13: gate call itself does not raise even when both paths fail", False)
finally:
    action_gateway.mark_context_interrupted = orig_mark2
    action_gateway.mark_context_integrity_unknown = orig_fallback


print(f"\n{'='*60}\nBUG-PENDING-APPROVAL-B ingress gate: {passed} passed, {failed} failed\n{'='*60}")
sys.exit(1 if failed else 0)
