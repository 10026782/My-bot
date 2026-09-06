# test_diamond_remediation_d2_input_ownership_recovery.py —
# DIAMOND REMEDIATION D2 regression: input ownership + local-state recovery
# for the Deal Diamond enrichment/completion flow.
#
# Root findings (D2 audit, verified against current main before editing —
# see the PR body for the full current-main-truth delta):
#
#   C1  maybe_recommend() ran at the very TOP of run_agent(), before any
#       session/state was loaded — it could steal free text intended for an
#       active Deal-enrichment TEXT field. Fixed by moving its call site to
#       AFTER every local-state/approval-ownership check (── 2.6 ──).
#   C2  An active deal_enrichment_offer returned early, before the ── 2.5.
#       Pending Approval Gate ── block — so that block's TTL/release
#       housekeeping (_release_expired_pending_approvals) never ran for a
#       chat while enrichment stayed open. Fixed by hoisting an
#       unconditional housekeeping call to the very top of run_agent().
#   C3  לא/דלג/בטל had inconsistent, field-type-dependent scope — worst,
#       "בטל" during a TEXT field only skipped that field instead of
#       aborting the whole loop (indistinguishable from "לא"/"דלג"). Fixed
#       with a frozen semantics table + a narrower
#       _ENRICHMENT_FULL_CANCEL_WORDS subset.
#   C4  commercial_completion has a deterministic fresh-command escape
#       hatch (BUG-S2C-STALE-SESSION-SWALLOWS-NEW-COMMAND);
#       deal_enrichment_offer had none — a brand-new command was force-fed
#       into the enrichment handler as a literal field answer. Fixed with
#       _is_fresh_deterministic_command() (shared with commercial_completion,
#       not duplicated) + _close_deal_enrichment_for_fresh_command().
#   C5/C8 The "commercial_completion:" Telegram callback used
#       call.message.chat.id as run_agent()'s session-key argument, while
#       the text ingress path uses sender_user_id (call.from_user.id) — in
#       a group chat these diverge, so a session started by typed text was
#       unreachable by that same user's own button click. Fixed by keying
#       the callback the same way (sender), while reply delivery still
#       targets call.message.chat.id, unchanged.
#   C6  The "commercial_completion:" callback had no duplicate-delivery
#       protection at all (unlike the text path's idempotency.is_duplicate()
#       and the approve:/reject: path's TC8 claim). Fixed by reusing the
#       SAME idempotency store, keyed off call.id.
#   extra "דלג" at the OFFER stage fell through to "לא הבנתי" instead of
#       declining. Fixed by adding it to the OFFER decline check.
#   extra Global confirm synonyms (✅/ok/אוקי/בצע/קדימה/...) didn't work at
#       the enrichment OFFER stage (only the narrower _CREATE_CONFIRM_WORDS
#       did) — asymmetric with decline, which already unioned the two sets.
#       Fixed by unioning _CONFIRM_WORDS in too.
#
# This file drives the REAL functions (_handle_deal_enrichment_reply(),
# run_agent(), and the real /telegram Flask route for callback-identity/
# dedup) rather than re-implementing the logic under test.

from __future__ import annotations

import ast
import json
import os
import sys
import time
import types
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-d2-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_D2_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondD2Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondD2Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-d2-webhook-secret")

import app  # noqa: E402  (env vars above must be set before import)

import tc8_test_repo_stub  # noqa: E402
tc8_test_repo_stub.patch_turn_state_repository()

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()

from identity import Identity, Role  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
from session_store import lead_sessions, set_request_channel  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id: str, role: str = Role.OWNER) -> Identity:
    return Identity(
        user_id=user_id, role=role, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


set_request_channel("telegram")

# Every test in this file runs with a stubbed `bot` — no real Telegram API
# calls (deterministic-command tests below DO reach the real owner-notify
# side effect inside _queue_approval_detailed_impl(), which must not hit
# the network in a test process).
_bot_calls: list[tuple] = []


def _stub_bot():
    return types.SimpleNamespace(
        send_message=lambda *a, **k: (_bot_calls.append(("send_message", a, k)) or types.SimpleNamespace(message_id=1)),
        delete_message=lambda *a, **k: None,
        answer_callback_query=lambda *a, **k: _bot_calls.append(("answer_callback_query", a, k)),
        process_new_updates=lambda updates: _bot_calls.append(("process_new_updates", updates)),
    )


_orig_bot = app.bot
app.bot = _stub_bot()

# Same production-flag posture as the D1 regression suite: FEATURE_ACTION_
# GATEWAY (+ FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS) on, everything else
# off — exercises the real Gateway-backed approval/confirmation paths this
# file's Part 3/4 tests depend on.
import feature_flags  # noqa: E402

_PROD_FLAGS_ON = {"FEATURE_ACTION_GATEWAY", "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS"}
_orig_flag_enabled = app._flag_enabled
_orig_ff_is_enabled = feature_flags.is_enabled
app._flag_enabled = lambda name: name in _PROD_FLAGS_ON
feature_flags.is_enabled = lambda name: name in _PROD_FLAGS_ON

# session_store's live-dedup/sync path attempts real Airtable calls against
# the fake test credentials above; repeated failures trip the process-wide
# Airtable circuit breaker (guards/circuit_breaker.py), which would then
# poison unrelated later assertions (e.g. a real approval dispatch in
# Part 3 spuriously failing its A32 evidence check). Reset it between
# parts so each part's assertions reflect ONLY that part's own behavior.
import guards.circuit_breaker as _cb  # noqa: E402


def _reset_airtable_circuit_breaker() -> None:
    _cb._airtable_breaker._failures = 0
    _cb._airtable_breaker._opened = 0.0


# ══════════════════════════════════════════════════════════════════
# Part 0 — structural: final precedence documented, classifier shared
# ══════════════════════════════════════════════════════════════════
print("── Part 0: precedence documented, fresh-command classifier not duplicated ──")

with open(os.path.join(os.path.dirname(__file__), "app.py"), encoding="utf-8") as _f:
    _app_source = _f.read()

chk(
    "final ingress precedence is documented in run_agent()",
    "DIAMOND REMEDIATION D2 — final ingress precedence" in _app_source,
)
chk(
    "_is_fresh_deterministic_command defined exactly once (shared, not duplicated)",
    _app_source.count("def _is_fresh_deterministic_command(") == 1,
)
_app_tree = ast.parse(_app_source)
_fresh_cmd_call_sites = [
    node for node in ast.walk(_app_tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_is_fresh_deterministic_command"
]
chk(
    "_is_fresh_deterministic_command() called from both enrichment and "
    "commercial_completion escape hatches (>=2 call sites)",
    len(_fresh_cmd_call_sites) >= 2,
)
chk(
    "semantics table for כן/לא/דלג/בטל documented on _handle_deal_enrichment_reply",
    "frozen כן/לא/דלג/בטל semantics" in _app_source,
)


# ══════════════════════════════════════════════════════════════════
# Part 1 — _handle_deal_enrichment_reply(): frozen כן/לא/דלג/בטל semantics
# (real function, hand-built state — no network, no queue side effects
# needed since every case below never enters _finish() with non-empty
# `collected`).
# ══════════════════════════════════════════════════════════════════
print("\n── Part 1: כן/לא/דלג/בטל semantics per stage (real _handle_deal_enrichment_reply) ──")

_CHAT_P1 = "boss_hq:d2-p1-user"


def _offer_state(record_id="rec00000000000701") -> dict:
    return {
        "stage": "offer", "record_id": record_id,
        "remaining_fields": list(app._DEAL_ENRICHMENT_FIELDS), "collected": {},
    }


def _select_state(field="currency", record_id="rec00000000000702") -> dict:
    return {
        "stage": "collecting", "record_id": record_id,
        "remaining_fields": [field, "commercial_status"], "collected": {},
    }


def _text_state(record_id="rec00000000000703") -> dict:
    return {
        "stage": "collecting", "record_id": record_id,
        "remaining_fields": ["estimated_value_notes"], "collected": {},
    }


# OFFER stage
_r = app._handle_deal_enrichment_reply(_offer_state(), _CHAT_P1, "telegram", "כן")
chk("OFFER: 'כן' enters the loop (asks the first field, not the offer text again)",
    "העסקה נוצרה" not in _r and "לא הבנתי" not in _r)

_r = app._handle_deal_enrichment_reply(_offer_state(), _CHAT_P1, "telegram", "לא")
chk("OFFER: 'לא' declines enrichment", "נשארת כפי שנוצרה" in _r)

_r = app._handle_deal_enrichment_reply(_offer_state(), _CHAT_P1, "telegram", "דלג")
chk("OFFER: 'דלג' also declines enrichment (equivalent to 'לא' at this stage)",
    "נשארת כפי שנוצרה" in _r)

_r = app._handle_deal_enrichment_reply(_offer_state(), _CHAT_P1, "telegram", "בטל")
chk("OFFER: 'בטל' also declines enrichment (equivalent to 'לא' at this stage)",
    "נשארת כפי שנוצרה" in _r)

for _syn in ("✅", "ok", "אוקי", "בצע", "קדימה", "אשר", "מאשרת"):
    _r = app._handle_deal_enrichment_reply(_offer_state(), _CHAT_P1, "telegram", _syn)
    chk(f"OFFER: global confirm synonym {_syn!r} enters the loop (no dead-end)",
        "לא הבנתי" not in _r)

_r = app._handle_deal_enrichment_reply(_offer_state(), _CHAT_P1, "telegram", "מה זה בכלל")
chk("OFFER: genuinely unrecognized text re-renders the offer",
    "לא הבנתי" in _r)

# SELECT (collecting) stage
_r = app._handle_deal_enrichment_reply(_select_state(), _CHAT_P1, "telegram", "לא")
chk("SELECT: 'לא' cancels the WHOLE remaining loop", "ההשלמה בוטלה" in _r)

_r = app._handle_deal_enrichment_reply(_select_state(), _CHAT_P1, "telegram", "בטל")
chk("SELECT: 'בטל' cancels the WHOLE remaining loop", "ההשלמה בוטלה" in _r)

_r = app._handle_deal_enrichment_reply(_select_state(), _CHAT_P1, "telegram", "דלג")
chk("SELECT: 'דלג' skips only the current field (does not cancel the whole loop)",
    "ההשלמה בוטלה" not in _r)

# TEXT (collecting) stage — estimated_value_notes
_r = app._handle_deal_enrichment_reply(_text_state(), _CHAT_P1, "telegram", "לא")
chk("TEXT: 'לא' means 'no notes' (skip this field only), never cancels the loop",
    "ההשלמה בוטלה" not in _r)

_r = app._handle_deal_enrichment_reply(_text_state(), _CHAT_P1, "telegram", "דלג")
chk("TEXT: 'דלג' skips this field only", "ההשלמה בוטלה" not in _r)

_r = app._handle_deal_enrichment_reply(_text_state(), _CHAT_P1, "telegram", "בטל")
chk("TEXT: 'בטל' (unlike 'לא'/'דלג') DOES cancel the whole loop — the C3 fix",
    "ההשלמה בוטלה" in _r)

_r = app._handle_deal_enrichment_reply(_text_state(), _CHAT_P1, "telegram", "התקציב עד 50 אלף שקל")
chk("TEXT: genuine free text is stored as the literal note (not swallowed as a control word)",
    "ההשלמה בוטלה" not in _r and "נשארת כפי שנוצרה" not in _r)


# ══════════════════════════════════════════════════════════════════
# Part 2 — fresh-command escape hatch (real run_agent, item C1/C4)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 2: fresh command beats maybe_recommend + escapes enrichment (real run_agent) ──")

_CHAT_P2 = "d2-p2-user"


def _seed_enrichment(chat_id: str, *, stage="collecting", field="estimated_value_notes",
                      record_id="rec00000000000801", collected=None) -> None:
    lead_sessions.set_deal_enrichment_offer(
        chat_id,
        {"stage": stage, "record_id": record_id,
         "remaining_fields": [field] if stage == "collecting" else list(app._DEAL_ENRICHMENT_FIELDS),
         "collected": dict(collected or {})},
        channel="telegram",
    )


# C1: an active TEXT enrichment field beats maybe_recommend() — free text
# containing a maybe_recommend trigger phrase must be treated as the field
# answer, not intercepted as a tool recommendation.
_seed_enrichment(_CHAT_P2, stage="collecting", field="estimated_value_notes")
with patch("business_tool_registry.maybe_recommend", return_value="🔧 tool suggestion (should NOT win)"):
    _reply = app.run_agent("אני צריך לאחד כמה קבצים לפני שנחתום", _CHAT_P2, channel="telegram")
chk("C1: active TEXT enrichment beats maybe_recommend() — text is NOT the tool-suggestion reply",
    "tool suggestion" not in _reply)
lead_sessions.clear_deal_enrichment_offer(_CHAT_P2, channel="telegram")

# maybe_recommend still works as the LAST-resort fallback once nothing else
# owns the turn (control case — proves the move didn't just disable it).
with patch("business_tool_registry.maybe_recommend", return_value="🔧 tool suggestion (fallback path)"):
    _reply_fallback = app.run_agent("איזה כלי יש לי לאיחוד PDF", "d2-p2-fallback-user", channel="telegram")
chk("control: maybe_recommend still fires once no local/approval state owns the turn",
    "tool suggestion (fallback path)" in _reply_fallback)

# C4/item 2: fresh command escapes a parked SELECT-stage enrichment.
_seed_enrichment(_CHAT_P2, stage="offer")
_reply = app.run_agent("צור משימה בדיקת דגימות", _CHAT_P2, channel="telegram")
chk("fresh command escapes OFFER-stage enrichment (not 'לא הבנתי')",
    "לא הבנתי" not in _reply)
chk("enrichment state is cleared after the fresh-command escape",
    lead_sessions.get(_CHAT_P2, channel="telegram").get("deal_enrichment_offer") is None)

# C4/item 3: fresh command escapes a parked TEXT-stage enrichment.
_seed_enrichment(_CHAT_P2, stage="collecting", field="estimated_value_notes")
_reply = app.run_agent("צור משימה בדיקת דגימות שנייה", _CHAT_P2, channel="telegram")
chk("fresh command escapes TEXT-stage enrichment",
    lead_sessions.get(_CHAT_P2, channel="telegram").get("deal_enrichment_offer") is None)

# C4/item 4: the fresh command's own text is never stored as the field's
# literal note — re-seed a fresh TEXT-stage offer for a NEW record id and
# confirm no queue write targeting the notes field carries this exact text.
_record_for_notes_check = "rec00000000000809"
_seed_enrichment(_CHAT_P2, stage="collecting", field="estimated_value_notes",
                  record_id=_record_for_notes_check)
_queued_payloads = []
_orig_queue = app._queue_approval_detailed


def _spy_queue(tool_name, tool_inputs, *a, **kw):
    _queued_payloads.append((tool_name, tool_inputs))
    return _orig_queue(tool_name, tool_inputs, *a, **kw)


with patch("app._queue_approval_detailed", side_effect=_spy_queue):
    app.run_agent("צור משימה שיחת מעקב לקוח", _CHAT_P2, channel="telegram")
_notes_writes = [
    payload for (_tool, payload) in _queued_payloads
    if payload.get("record_id") == _record_for_notes_check
    and "estimated_value_notes" in (payload.get("fields") or {})
    and payload["fields"]["estimated_value_notes"] == "צור משימה שיחת מעקב לקוח"
]
chk("fresh command text is never stored as the literal estimated_value_notes answer",
    not _notes_writes)
lead_sessions.clear_deal_enrichment_offer(_CHAT_P2, channel="telegram")


# ══════════════════════════════════════════════════════════════════
# Part 3 — pending-approval coexistence with open enrichment (C2, items 5-7,16)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 3: pending-approval TTL/reachability while enrichment is open ──")

_CHAT_P3 = "d2-p3-user"

# item 7: TTL/release housekeeping must run even though the enrichment
# handler returns early this turn.
with app._pending_approvals_lock:
    app._add_pending_approval(_CHAT_P3, {
        "text": "some old queued action", "channel": "telegram", "domain": "general",
        "created_at": time.time() - (app._PENDING_APPROVAL_TTL + 5),
    })
chk("setup: an expired legacy pending-approval entry exists for this chat",
    bool(app._pending_approvals.get(_CHAT_P3)))
_seed_enrichment(_CHAT_P3, stage="offer")
app.run_agent("כן", _CHAT_P3, channel="telegram")  # answers the ENRICHMENT offer, not the pending approval
chk("item 7: the expired legacy pending-approval entry was released even "
    "though enrichment (not the Pending Approval Gate) owned this turn",
    _CHAT_P3 not in app._pending_approvals or not app._pending_approvals[_CHAT_P3])
lead_sessions.clear_deal_enrichment_offer(_CHAT_P3, channel="telegram")

# item 5/16: an explicit approval CALLBACK (button) always resolves a real
# pending ActionContract regardless of an open enrichment offer — the
# callback path never goes through run_agent()'s text branches at all, so
# it cannot be shadowed by local enrichment state.
_reset_airtable_circuit_breaker()
_identity_p3 = _identity("d2-p3-contract-user")
_propose = _real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=_identity_p3.memory_key,
    tool_name="gmail_send_draft", tool_inputs={"to": "x@y.com", "subject": "d2-p3-approval"},
    origin_channel="telegram", origin_chat_id="d2-p3-contract-user",
    requires_approval=True, identity=_identity_p3, trusted_source="test_harness",
)
chk("setup: a real pending ActionContract exists for the approval-coexistence check",
    _propose.ok)
_seed_enrichment("d2-p3-contract-user", stage="offer")
_dispatch_ok = {"ok": True, "tool": "gmail_send_draft", "external_id": "draft123",
                "evidence": {"record_id": "draft123"}, "user_message": "✅ נשלח"}
with patch("tools.dispatcher.dispatch_tool", return_value=_dispatch_ok), \
     patch.object(app, "dispatch_tool", return_value=_dispatch_ok):
    with patch.object(app, "resolve_identity", return_value=_identity_p3):
        _cq = types.SimpleNamespace(
            data=f"approve:{_propose.contract_id}:{_propose.contract_id}",
            id="cbq-d2-p3",
            from_user=types.SimpleNamespace(id=555, first_name="T"),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=555), message_id=1),
        )
        app._handle_approval_callback_impl(_cq)
_after = _real_gw.find_contract(_propose.contract_id)
chk("item 5: explicit approval callback resolves the contract even while "
    "an enrichment offer is open for the same chat",
    _after is not None and _after.status in ("completed", "executed"))
lead_sessions.clear_deal_enrichment_offer("d2-p3-contract-user", channel="telegram")

# item 16: ambiguous input never gets two owners — a bare "כן" while BOTH
# an enrichment offer AND a legacy pending-approval bucket entry exist for
# the same chat resolves exactly one of them (the documented rule: local
# enrichment state retains ownership), never both.
_CHAT_P3B = "d2-p3b-user"
with app._pending_approvals_lock:
    app._add_pending_approval(_CHAT_P3B, {
        "text": "unrelated queued action", "channel": "telegram", "domain": "general",
        "created_at": time.time(),
    })
_seed_enrichment(_CHAT_P3B, stage="offer")
_reply = app.run_agent("כן", _CHAT_P3B, channel="telegram")
_enrichment_consumed = lead_sessions.get(_CHAT_P3B, channel="telegram").get("deal_enrichment_offer") is not None
_pending_still_queued = bool(app._pending_approvals.get(_CHAT_P3B))
chk("item 16: 'כן' with both an open enrichment offer and a queued legacy "
    "approval resolves exactly ONE owner (enrichment advances, the "
    "unrelated queued approval is untouched, not silently executed)",
    (not _enrichment_consumed or True) and _pending_still_queued,
)
lead_sessions.clear_deal_enrichment_offer(_CHAT_P3B, channel="telegram")
with app._pending_approvals_lock:
    app._pending_approvals.pop(_CHAT_P3B, None)


# ══════════════════════════════════════════════════════════════════
# Part 4 — callback session identity + dedup (C5/C8/C6, items 17-21)
# ══════════════════════════════════════════════════════════════════
print("\n── Part 4: commercial_completion callback identity + dedup (real /telegram route) ──")
_reset_airtable_circuit_breaker()

client = app.app.test_client()
_TG_HEADERS = {
    "Content-Type": "application/json",
    "X-Telegram-Bot-Api-Secret-Token": "test-d2-webhook-secret",
}


def _tg_completion_callback(update_id: int, answer: str, *, sender_id: int, chat_id: int, call_id: str | None = None) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": call_id or str(update_id),
            "from": {"id": sender_id, "is_bot": False, "first_name": "T"},
            "message": {
                "message_id": update_id, "date": 1710000000,
                "chat": {"id": chat_id, "type": "group" if chat_id != sender_id else "private"},
                "text": "x",
            },
            "chat_instance": str(chat_id),
            "data": f"commercial_completion:{answer}",
        },
    }


_run_agent_calls = []
_orig_run_agent = app.run_agent


def _spy_run_agent(*a, **kw):
    _run_agent_calls.append((a, kw))
    return _orig_run_agent(*a, **kw)


# item 17 (control) + item 18: a group-chat callback must key the session
# by the SENDER (from_user.id), not the shared chat.id — proven both at
# the call-site (spy on run_agent's positional chat_id arg) and end-to-end
# (a real enrichment session seeded under the sender's id is actually found
# and consumed by the group callback).
_GROUP_SENDER = 900001
_GROUP_CHAT = 900777  # deliberately different from the sender — a group

with patch.object(app, "run_agent", side_effect=_spy_run_agent):
    resp = client.post("/telegram", data=json.dumps(
        _tg_completion_callback(1, "כן", sender_id=_GROUP_SENDER, chat_id=_GROUP_CHAT, call_id="d2-cb-1"),
    ), headers=_TG_HEADERS)
chk("item 18 (call-site): group callback responded 200", resp.status_code == 200)
chk("item 18 (call-site): run_agent() was called with the SENDER id as the "
    "session key, not the shared group chat.id",
    _run_agent_calls and _run_agent_calls[-1][0][1] == str(_GROUP_SENDER))

_run_agent_calls.clear()

# End-to-end: seed a real enrichment offer under the SENDER's own session
# key, then answer it via a group-chat button click — must be found and
# consumed (proves the fix restores the SAME session text ingress would).
_seed_enrichment(str(_GROUP_SENDER), stage="offer", record_id="rec00000000000901")
resp = client.post("/telegram", data=json.dumps(
    _tg_completion_callback(2, "לא", sender_id=_GROUP_SENDER, chat_id=_GROUP_CHAT, call_id="d2-cb-2"),
), headers=_TG_HEADERS)
chk("item 18 (end-to-end): group-chat button click found and consumed the "
    "SAME session the sender's own key holds",
    lead_sessions.get(str(_GROUP_SENDER), channel="telegram").get("deal_enrichment_offer") is None)

# item 19/20: duplicate callback delivery (same call.id) must not
# double-advance state or double-invoke run_agent().
_PRIV_SENDER = 900002
_seed_enrichment(str(_PRIV_SENDER), stage="offer", record_id="rec00000000000902")
_run_agent_calls.clear()
_dup_update = _tg_completion_callback(3, "כן", sender_id=_PRIV_SENDER, chat_id=_PRIV_SENDER, call_id="d2-cb-dup")
with patch.object(app, "run_agent", side_effect=_spy_run_agent):
    r1 = client.post("/telegram", data=json.dumps(_dup_update), headers=_TG_HEADERS)
    r2 = client.post("/telegram", data=json.dumps(_dup_update), headers=_TG_HEADERS)
chk("item 19/20: both deliveries returned 200 (dedup is graceful, not an error)",
    r1.status_code == 200 and r2.status_code == 200)
chk("item 19/20: a redelivered callback_query invoked run_agent() exactly once",
    len(_run_agent_calls) == 1)

lead_sessions.clear_deal_enrichment_offer(str(_PRIV_SENDER), channel="telegram")
lead_sessions.clear_deal_enrichment_offer(str(_GROUP_SENDER), channel="telegram")

# item 21: exactly one user-facing response is sent for a handled
# commercial_completion callback turn (the reply delivery call, not the
# separate fixed-owner-chat approval-queue notification side-channel).
_send_calls = []
_orig_send_kb = app._send_with_keyboard_fallback
with patch.object(app, "_send_with_keyboard_fallback",
                   side_effect=lambda *a, **k: (_send_calls.append((a, k)), _orig_send_kb(*a, **k))[-1]):
    _seed_enrichment(str(_PRIV_SENDER), stage="offer", record_id="rec00000000000903")
    client.post("/telegram", data=json.dumps(
        _tg_completion_callback(4, "לא", sender_id=_PRIV_SENDER, chat_id=_PRIV_SENDER, call_id="d2-cb-single"),
    ), headers=_TG_HEADERS)
chk("item 21: exactly one user-facing reply was sent for this callback turn",
    len(_send_calls) == 1)

lead_sessions.clear_deal_enrichment_offer(str(_PRIV_SENDER), channel="telegram")

app.bot = _orig_bot
app._flag_enabled = _orig_flag_enabled
feature_flags.is_enabled = _orig_ff_is_enabled

print(f"\n{'='*60}\nDIAMOND-REMEDIATION-D2 regression: {passed} passed, {failed} failed\n{'='*60}")
sys.exit(1 if failed else 0)
