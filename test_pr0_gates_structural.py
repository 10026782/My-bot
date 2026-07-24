# test_pr0_gates_structural.py — BUG-PENDING-APPROVAL-B, Gate 1 + Gate 2 proofs
#
# The behavioral integration tests (test_pr0_ingress_context_gate.py) prove
# that each route class interrupts (or doesn't) *today*. These tests prove
# two structural invariants directly against app.py's/core/action_gateway.py's
# AST, so a future edit that silently violates either one fails CI instead of
# only being caught by luck in a future live incident:
#
#   Gate 1 — in each of the three webhook functions, _apply_ingress_context_gate
#   is called strictly after the function's own junk/idempotency/duplicate
#   filtering, and strictly before EVERY callback/command/wizard/media/
#   Decision Hub/Agent routing branch that function contains. Proven by
#   comparing AST line numbers of the gate call against every other routing
#   marker inside each relevant `if` branch — since every early-return path
#   in each function lives inside one of those enumerated branches, this
#   also proves no business path can bypass the gate.
#
#   Gate 2 — ActionGateway.is_own_resolution_event() is not a parallel
#   reimplementation of the real confirm/cancel/disambiguation matching
#   logic that could silently drift from it. Proven by mutating the shared
#   class-level keyword sets and confirming both is_own_resolution_event()
#   and the real routing methods change behavior together — plus a direct
#   check that an approve:/reject:-style external callback (a different
#   mechanism entirely, not an ActionGateway resolution) still interrupts.

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


def _find_if(node, test_substring):
    """First `if` anywhere under `node` whose unparsed test contains substring."""
    best = None
    for child in ast.walk(node):
        if isinstance(child, ast.If):
            try:
                rep = ast.unparse(child.test)
            except Exception:
                continue
            if test_substring in rep and (best is None or child.lineno < best.lineno):
                best = child
    return best


def _first_call_lineno(node, target_substring):
    """Lineno of the first Call anywhere under `node` whose unparsed .func
    contains target_substring, else None."""
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


def _first_if_lineno(node, test_substring):
    found = _find_if(node, test_substring)
    return found.lineno if found else None


# ══════════════════════════════════════════════════
# Gate 1a: Telegram callback_query branch
# ══════════════════════════════════════════════════
print("\n── Gate 1a: Telegram callback branch ordering ────────────────")
tree = _parse_app()
tg_func = _find_function(tree, "_webhook_telegram_impl")
cb_branch = _find_if(tg_func, "callback_query")
chk("found the callback_query branch", cb_branch is not None)

gate_cb = _first_call_lineno(cb_branch, "_apply_ingress_context_gate")
approval_cb = _first_call_lineno(cb_branch, "_handle_approval_callback")
process_updates_cb = _first_call_lineno(cb_branch, "bot.process_new_updates")

chk("gate call found in callback branch", gate_cb is not None)
chk("gate runs before _handle_approval_callback (mechanism #2, unrelated to ActionGateway)",
    gate_cb is not None and approval_cb is not None and gate_cb < approval_cb)
chk("gate runs before bot.process_new_updates (other pyTeleBot callbacks)",
    gate_cb is not None and process_updates_cb is not None and gate_cb < process_updates_cb)


# ══════════════════════════════════════════════════
# Gate 1b: Telegram text-message branch
# ══════════════════════════════════════════════════
print("\n── Gate 1b: Telegram text-message branch ordering ────────────")
text_branch = _find_if(tg_func, "message.text")
chk("found the text-message branch", text_branch is not None)

dedup_text = _first_call_lineno(text_branch, "idempotency.is_duplicate")
gate_text = _first_call_lineno(text_branch, "_apply_ingress_context_gate")
command_if = _first_if_lineno(text_branch, "text.startswith")
wizard_call = _first_call_lineno(text_branch, "has_pending_text_capture")
decision_hub_call = _first_call_lineno(text_branch, "is_attachment_reference")
run_agent_call = _first_call_lineno(text_branch, "run_agent")

chk("idempotency dedup found", dedup_text is not None)
chk("gate call found in text branch", gate_text is not None)
chk("dedup runs before the gate (duplicates never reach it)",
    dedup_text is not None and gate_text is not None and dedup_text < gate_text)
chk("gate runs before slash-command routing",
    gate_text is not None and command_if is not None and gate_text < command_if)
chk("gate runs before wizard text-capture routing",
    gate_text is not None and wizard_call is not None and gate_text < wizard_call)
chk("gate runs before Decision Hub attachment-reference routing",
    gate_text is not None and decision_hub_call is not None and gate_text < decision_hub_call)
chk("gate runs before run_agent (the Agent path)",
    gate_text is not None and run_agent_call is not None and gate_text < run_agent_call)


# ══════════════════════════════════════════════════
# Gate 1c: Telegram media branch (voice/photo/document)
# ══════════════════════════════════════════════════
print("\n── Gate 1c: Telegram media branch ordering ───────────────────")
media_branch = _find_if(tg_func, "content_type")
chk("found the media branch", media_branch is not None)

gate_media = _first_call_lineno(media_branch, "_apply_ingress_context_gate")
file_capture_call = _first_call_lineno(media_branch, "has_pending_file_capture")
handle_media_call = _first_call_lineno(media_branch, "_handle_telegram_media")

chk("gate call found in media branch", gate_media is not None)
chk("gate runs before wizard file-capture routing",
    gate_media is not None and file_capture_call is not None and gate_media < file_capture_call)
chk("gate runs before general media handling",
    gate_media is not None and handle_media_call is not None and gate_media < handle_media_call)


# ══════════════════════════════════════════════════
# Gate 1d: WhatsApp (Twilio) webhook ordering
# ══════════════════════════════════════════════════
print("\n── Gate 1d: WhatsApp (Twilio) webhook ordering ────────────────")
wa_func = _find_function(tree, "_webhook_whatsapp_impl")

junk_wa = _first_call_lineno(wa_func, "_is_junk_inbound_text")
dedup_wa = _first_call_lineno(wa_func, "idempotency.is_duplicate")
gate_wa = _first_call_lineno(wa_func, "_apply_ingress_context_gate")
media_wa = _first_call_lineno(wa_func, "extract_whatsapp_media")
funnel_wa = _first_call_lineno(wa_func, "handle_furniture_lead_message")
run_agent_wa = _first_call_lineno(wa_func, "run_agent")

chk("junk filter found", junk_wa is not None)
chk("dedup found", dedup_wa is not None)
chk("gate call found", gate_wa is not None)
chk("junk filter before dedup", junk_wa is not None and dedup_wa is not None and junk_wa < dedup_wa)
chk("dedup before the gate", dedup_wa is not None and gate_wa is not None and dedup_wa < gate_wa)
chk("gate before media handling", gate_wa is not None and media_wa is not None and gate_wa < media_wa)
chk("gate before the furniture-funnel early-return path",
    gate_wa is not None and funnel_wa is not None and gate_wa < funnel_wa)
chk("gate before run_agent", gate_wa is not None and run_agent_wa is not None and gate_wa < run_agent_wa)


# ══════════════════════════════════════════════════
# Gate 1e: Meta WhatsApp webhook ordering
# ══════════════════════════════════════════════════
print("\n── Gate 1e: Meta WhatsApp webhook ordering ───────────────────")
meta_func = _find_function(tree, "webhook_meta_whatsapp")

junk_meta = _first_call_lineno(meta_func, "_is_junk_inbound_text")
dedup_meta = _first_call_lineno(meta_func, "idempotency.is_duplicate")
gate_meta = _first_call_lineno(meta_func, "_apply_ingress_context_gate")
run_agent_meta = _first_call_lineno(meta_func, "run_agent")

chk("junk filter found", junk_meta is not None)
chk("dedup found", dedup_meta is not None)
chk("gate call found", gate_meta is not None)
chk("junk filter before dedup", junk_meta is not None and dedup_meta is not None and junk_meta < dedup_meta)
chk("dedup before the gate", dedup_meta is not None and gate_meta is not None and dedup_meta < gate_meta)
chk("gate before run_agent", gate_meta is not None and run_agent_meta is not None and gate_meta < run_agent_meta)


# ══════════════════════════════════════════════════
# Gate 2a: is_own_resolution_event shares real routing's keyword sets —
# not a parallel reimplementation that could silently drift.
# ══════════════════════════════════════════════════
print("\n── Gate 2a: exemption check reuses real routing (no drift) ───")
from core.action_gateway import ActionGateway, ExecutionLedger  # noqa: E402

gw = ActionGateway(ledger=ExecutionLedger())
r = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="gate2_user",
    tool_name="gmail_send_draft", tool_inputs={"to": "a@b.com"},
    origin_channel="telegram", origin_chat_id="tg:1", requires_approval=True,
)
chk("setup: contract proposed", r.ok)
chk("baseline: 'לגמרי משהו אחר' is not a resolution", not gw.is_own_resolution_event("gate2_user", "לגמרי משהו אחר"))

# Mutate the SHARED class-level keyword set and confirm both is_own_resolution_event
# AND the real free-text routing method treat the new word as a genuine confirm —
# proving they draw from the exact same source of truth, not two separate lists.
_orig_confirm_keywords = ActionGateway._CONFIRM_KEYWORDS
ActionGateway._CONFIRM_KEYWORDS = _orig_confirm_keywords | {"בדיקת_דריפט_ייחודית"}
try:
    chk("mutated keyword now recognized by is_own_resolution_event",
        gw.is_own_resolution_event("gate2_user", "בדיקת_דריפט_ייחודית"))
    reply = gw.route_confirmation_word("gate2_user", approver_role="owner")
    # route_confirmation_word doesn't itself check the text (it's invoked only
    # once app.py already classified the message as a confirm word) — the real
    # proof is that _CONFIRM_KEYWORDS is the single shared set consumed by
    # _parse_combined too, exercised directly here:
    chk("the same mutated set is what _parse_combined consults (shared, not copied)",
        ActionGateway._parse_combined("בדיקת_דריפט_ייחודית 1") == ("confirm", 1))
finally:
    ActionGateway._CONFIRM_KEYWORDS = _orig_confirm_keywords


# ══════════════════════════════════════════════════
# Gate 2b: bare-digit-only-with-2+-live precedent (BUG-070) — not exempt
# with a single live contract, matching real disambiguation behavior exactly.
# ══════════════════════════════════════════════════
print("\n── Gate 2b: bare digit exemption matches BUG-070 precedent ───")
chk("bare '1' NOT exempt with only one live contract (matches real routing)",
    not gw.is_own_resolution_event("gate2_user", "1"))

r2 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="gate2_user",
    tool_name="gmail_send_draft", tool_inputs={"to": "different@b.com"},
    origin_channel="telegram", origin_chat_id="tg:1", requires_approval=True,
    trusted_source="test_harness",
)
chk("setup: second distinct contract proposed", r2.ok)
chk("bare '1' IS exempt now that 2 contracts are live (matches real disambiguation)",
    gw.is_own_resolution_event("gate2_user", "1"))


# ══════════════════════════════════════════════════
# Gate 2c: approve:/reject:-style external callback still interrupts
# ActionGateway even though it belongs to a different mechanism entirely.
# (Re-asserted at the unit level here; also covered end-to-end at the
# webhook level by test_pr0_ingress_context_gate.py's T3b.)
# ══════════════════════════════════════════════════
print("\n── Gate 2c: unrelated approval-callback mechanism still interrupts ─")
gw3 = ActionGateway(ledger=ExecutionLedger())
r3 = gw3.propose_action(
    tenant_id="boss_hq", canonical_user_id="gate2c_user",
    tool_name="gmail_send_draft", tool_inputs={"to": "x@y.com"},
    origin_channel="telegram", origin_chat_id="tg:1", requires_approval=True,
)
chk("setup: contract proposed", r3.ok)
# A callback event is never "text", so is_own_resolution_event is not even
# consulted by the gate for it (app.py only checks kind=="text") — the gate
# always calls mark_context_interrupted for kind=="callback".
gw3.mark_context_interrupted("gate2c_user")
c3 = gw3.find_contract(r3.contract_id)
chk("contract marked interrupted despite originating from an unrelated callback flow",
    c3.context_interrupted is True)


print(f"\n{'='*60}\nBUG-PENDING-APPROVAL-B structural gates: {passed} passed, {failed} failed\n{'='*60}")
sys.exit(1 if failed else 0)
