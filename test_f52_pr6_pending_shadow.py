#!/usr/bin/env python3
# test_f52_pr6_pending_shadow.py — F52 PR6: approval_pending formatter shadow
# coverage + EvidenceFinalizer plumbing.
#
# Production finding that opened this follow-up (third F52 gap found in a
# row, after PR4's executed/status-query coverage and PR5's rejection/
# cancellation coverage): a real log showed
#   A32 suppressed agent action-status text after approval was already queued.
#   ownership_signal: tool_use_emitted=true approval_queued=true
#     agent_claimed_approval=false reply_owner=agent
#   EvidenceFinalizerShadow: evidence_status=approval_pending
#     approvals_pending=1 response_claim=empty mismatch=true
#   (the real, user/owner-visible "⏳ בקשת אישור..." prompt WAS sent)
#   No UnifiedStatusFormatterShadow was emitted.
#
# Root causes (three, all fixed here):
#   1. app.py's _queue_approval_detailed_impl() sends its own hardcoded
#      "⏳ בקשת אישור..." text directly via bot.send_message(), never
#      through ActionGateway.compose_status_reply()/ActionFact — the same
#      shape of gap PR5 closed for rejections. Fixed with a new
#      core.action_gateway.ActionGateway._render_pending_prompt(), reusing
#      outcome="pending" (already mapped to the "approval_pending" canonical
#      state by _action_fact_to_message() — unmodified) and the exact same
#      off/shadow/on + _log_shadow_comparison/_shadow_leak_flags machinery
#      PR4/PR5 already built.
#   2. core.turn_evidence._classify_response_claim() read an empty
#      final_text as "empty" unconditionally — but A32's Single-Speaker gate
#      deliberately returns "" for the agent's own text once a real approval
#      was queued this turn (the real message went out through the side
#      channel above, not through final_reply). Fixed: a new
#      approval_prompt_sent parameter, proven via app.py's "owner_notified"
#      key (never guessed), reclassifies that specific empty case as
#      "sent_for_approval" — compatible with evidence_status=approval_pending,
#      not a mismatch.
#   3. core.turn_envelope.build_ownership_signal() was never passed a
#      reply_owner override at its one app.py call site, so it silently kept
#      its own default ("agent") even when a real approval was queued and the
#      agent's own text was suppressed. Fixed: app.py's call site now passes
#      reply_owner="gateway" when an approval was queued this turn — the same
#      label build_turn_envelope() already uses for this situation elsewhere.
#
# Explicitly NOT touched by this PR (see final report):
#   - BUG-111 lead parsing, BUG-112 TTL enforcement.
#   - FEATURE_UNIFIED_STATUS_FORMATTER's default (still "off") or enablement.
#   - A32's actual suppression decision (sanitize_agent_response still
#     returns "" for the agent's own text in this scenario — Test 3 pins
#     this as an explicit regression, not an accidental side effect).

from __future__ import annotations

import logging
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-f52pr6-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:F52PR6_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patF52PR6Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appF52PR6Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("ELIYAHU_CHAT_ID", "888888888")  # owner_chat_id resolves
# non-empty so _queue_approval_detailed_impl() actually attempts the owner
# notification (and therefore _render_pending_prompt()) end to end.

import app  # noqa: E402
import session_store  # noqa: E402
from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision, Intent, Handler, RouterDomain  # noqa: E402
from context import AgentContext  # noqa: E402
from core.action_gateway import ActionGateway  # noqa: E402
from core.anti_hallucination import sanitize_agent_response  # noqa: E402
from core.turn_evidence import (  # noqa: E402
    TurnEvidenceSummary,
    compare_shadow_final_status,
    observe_shadow_finalizer,
)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _set_env(name, value):
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


def _with_capture(logger_name, fn):
    cap = _LogCapture()
    lg = logging.getLogger(logger_name)
    lg.addHandler(cap)
    lg.setLevel(logging.INFO)
    try:
        result = fn()
    finally:
        lg.removeHandler(cap)
    return result, cap.records


# ══════════════════════════════════════════════════
# Section 1 — ActionGateway._render_pending_prompt() unit tests
# (off/shadow/on), mirroring PR4/PR5's own established pattern exactly.
# ══════════════════════════════════════════════════
print("── 1. _render_pending_prompt(): off/shadow/on ──")

_CID = 0


def _propose(gw: ActionGateway, tool_name: str = "airtable_add") -> tuple[str, str]:
    global _CID
    _CID += 1
    uid = f"boss_hq:f52pr6-{_CID}"
    result = gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=uid, tool_name=tool_name,
        tool_inputs={"table": "Tasks", "fields": {"Task": f"pr6-{_CID}"}},
        origin_channel="telegram", origin_chat_id=uid, requires_approval=True,
    )
    assert result.ok, f"propose_action failed: {result}"
    return uid, result.contract_id


_LEGACY = "⏳ בקשת אישור\n\nהוספת רשומה: Tasks\n\nID: abc123 | פג תוקף בעוד 10 דקות"

# 1a — off (default): byte-identical legacy text, no shadow log at all.
gw1 = ActionGateway()
uid1, cid1 = _propose(gw1)
try:
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", None)
    out1, log1 = _with_capture(
        "core.action_gateway", lambda: gw1._render_pending_prompt("airtable_add", cid1, _LEGACY),
    )
finally:
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", None)

chk("T1a: off -> returns legacy_text byte-identical", out1 == _LEGACY)
chk("T1a: off -> no [UnifiedStatusFormatterShadow] line at all",
    not any("UnifiedStatusFormatterShadow" in m for m in log1))

# 1b — shadow: legacy text still returned; exactly one safe comparison logged.
gw2 = ActionGateway()
uid2, cid2 = _propose(gw2)
try:
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", "shadow")
    out2, log2 = _with_capture(
        "core.action_gateway", lambda: gw2._render_pending_prompt("airtable_add", cid2, _LEGACY),
    )
finally:
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", None)

chk("T1b: shadow -> legacy text STILL returned (unchanged)", out2 == _LEGACY)
shadow_lines2 = [m for m in log2 if "UnifiedStatusFormatterShadow" in m]
chk("T1b: shadow -> exactly one [UnifiedStatusFormatterShadow] comparison logged",
    len(shadow_lines2) == 1)
if shadow_lines2:
    line2 = shadow_lines2[0]
    chk("T1b: shadow log -> outcome=pending", "outcome=pending" in line2)
    chk("T1b: shadow log -> mapped_state=approval_pending",
        "mapped_state=approval_pending" in line2)
    chk("T1b: shadow log -> record_id_leak=False", "record_id_leak=False" in line2)
    chk("T1b: shadow log -> tool_name_leak=False", "tool_name_leak=False" in line2)
    chk("T1b: shadow log -> contract_id_leak=False", "contract_id_leak=False" in line2)
    chk("T1b: shadow log -> fallback_used=False (recognized state)",
        "fallback_used=False" in line2)
    chk("T1b: shadow log never contains the raw tool name",
        "airtable_add" not in line2)
    chk("T1b: shadow log never contains the raw contract id", cid2 not in line2)

# 1c — on: unified text returned, differs from legacy, no leaked identifiers.
gw3 = ActionGateway()
uid3, cid3 = _propose(gw3)
try:
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", "on")
    out3 = gw3._render_pending_prompt("airtable_add", cid3, _LEGACY)
finally:
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", None)

chk("T1c: on -> non-empty unified text, differs from legacy",
    bool(out3) and out3 != _LEGACY)
chk("T1c: on -> no raw contract id leaked into the unified text", cid3 not in out3)
chk("T1c: on -> no raw tool name leaked into the unified text", "airtable_add" not in out3)

# 1d — contract_id=None (e.g. shadow-mode propose_action() raised before
# returning one) must never break rendering — falls back cleanly.
try:
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", "shadow")
    out1d, log1d = _with_capture(
        "core.action_gateway",
        lambda: ActionGateway()._render_pending_prompt("airtable_add", None, _LEGACY),
    )
finally:
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", None)
chk("T1d: contract_id=None -> does not raise, still returns legacy text in shadow",
    out1d == _LEGACY)


# ══════════════════════════════════════════════════
# Section 2 — core.turn_evidence: approval_prompt_sent reclassification
# ══════════════════════════════════════════════════
print()
print("── 2. EvidenceFinalizer: empty final_text + approval_prompt_sent ──")

_pending_evidence = TurnEvidenceSummary()
_pending_evidence.record_approval_pending()
assert _pending_evidence.classification() == "approval_pending"

# 2a — the EXACT reported bug, before the approval_prompt_sent signal is
# threaded through: empty text + approval_pending evidence -> false mismatch.
comparison_before = compare_shadow_final_status("", _pending_evidence)
chk("T2a: without approval_prompt_sent, empty text still classifies as "
    "response_claim=empty (reproduces the reported false mismatch)",
    comparison_before.response_claim == "empty")
chk("T2a: ...and is flagged as a mismatch (the exact bug reported in production)",
    comparison_before.mismatch is True)

# 2b — with approval_prompt_sent=True (the fix): no longer a mismatch.
comparison_after = compare_shadow_final_status(
    "", _pending_evidence, approval_prompt_sent=True,
)
chk("T2b: with approval_prompt_sent=True, response_claim=sent_for_approval, not empty",
    comparison_after.response_claim == "sent_for_approval")
chk("T2b: ...and evidence_status is still approval_pending (unchanged)",
    comparison_after.evidence_status == "approval_pending")
chk("T2b: ...and this is no longer reported as a mismatch",
    comparison_after.mismatch is False)
chk("T2b: ...mismatch_code is 'match'", comparison_after.mismatch_code == "match")

# 2c — approval_prompt_sent must not paper over a REAL mismatch: evidence
# for a genuine FAILURE this turn must still be flagged, even if an
# approval_prompt_sent=True happens to be passed in (defense against
# over-broad suppression) — compatibility is scoped to
# evidence_status=="approval_pending" only, never a blanket "any empty text
# is fine" rule.
_failure_evidence = TurnEvidenceSummary(failed_calls=1)
comparison_failure = compare_shadow_final_status(
    "", _failure_evidence, approval_prompt_sent=True,
)
chk("T2c: approval_prompt_sent=True does not mask a genuine failure -> "
    "still a mismatch (compatibility is scoped to approval_pending only)",
    comparison_failure.mismatch is True)
chk("T2c: ...evidence_status correctly stays 'failure', not reclassified",
    comparison_failure.evidence_status == "failure")

# 2d — observe_shadow_finalizer end to end: never mutates final_text, and
# threads approval_prompt_sent through to the same classification.
returned2d, cmp2d = observe_shadow_finalizer(
    "", _pending_evidence, state="shadow", approval_prompt_sent=True,
)
chk("T2d: observe_shadow_finalizer never mutates final_text (still \"\")",
    returned2d == "")
chk("T2d: observe_shadow_finalizer threads approval_prompt_sent through -> "
    "response_claim=sent_for_approval, mismatch=False",
    cmp2d is not None and cmp2d.response_claim == "sent_for_approval" and cmp2d.mismatch is False)

# 2e — default (no kwarg passed) is backward compatible: off by default.
returned2e, cmp2e = observe_shadow_finalizer("", _pending_evidence, state="shadow")
chk("T2e: approval_prompt_sent defaults to False -> unchanged pre-fix "
    "classification for any caller that doesn't pass it",
    cmp2e is not None and cmp2e.response_claim == "empty" and cmp2e.mismatch is True)

# 2f-2i — F52 PR6 follow-up (production-validated): a turn that ALSO did a
# verified read before queuing the approval classifies as
# evidence_status="mixed" (verified_reads>0 AND approvals_pending>0), not
# "approval_pending" — the exact production log this follow-up closed:
# evidence_status=mixed response_claim=sent_for_approval mismatch=true
# counts={'verified_reads': 1, 'approvals_pending': 1, ...}.
_mixed_read_pending_evidence = TurnEvidenceSummary()
_mixed_read_pending_evidence.record_verification("ok", read_only=True)
_mixed_read_pending_evidence.record_approval_pending()
assert _mixed_read_pending_evidence.classification() == "mixed"

comparison_2f = compare_shadow_final_status(
    "", _mixed_read_pending_evidence, approval_prompt_sent=True,
)
chk("T2f: read + approval_pending (mixed) + approval_prompt_sent=True -> "
    "response_claim=sent_for_approval, no longer a mismatch (the exact "
    "production finding this follow-up closes)",
    comparison_2f.response_claim == "sent_for_approval" and comparison_2f.mismatch is False)
chk("T2f: ...evidence_status correctly stays 'mixed' (not silently "
    "reclassified to approval_pending)",
    comparison_2f.evidence_status == "mixed")

# 2g — regression: without approval_prompt_sent, the SAME mixed evidence
# still reports empty/mismatch (the widening only fires when a real prompt
# was proven sent, exactly like the plain approval_pending case).
comparison_2g = compare_shadow_final_status("", _mixed_read_pending_evidence)
chk("T2g: same mixed evidence WITHOUT approval_prompt_sent -> still "
    "response_claim=empty, still a mismatch (widening requires proof)",
    comparison_2g.response_claim == "empty" and comparison_2g.mismatch is True)

# 2h — defense: a mixed turn that ALSO has a genuine failure or unverified
# effect mixed in must NOT be swallowed by this widening — those need their
# own claim in the text, "sent_for_approval" alone would hide them.
_mixed_with_failure = TurnEvidenceSummary()
_mixed_with_failure.record_verification("ok", read_only=True)
_mixed_with_failure.record_approval_pending()
_mixed_with_failure.record_verification("failed", read_only=False)
assert _mixed_with_failure.classification() == "mixed"
comparison_2h = compare_shadow_final_status(
    "", _mixed_with_failure, approval_prompt_sent=True,
)
chk("T2h: mixed evidence that ALSO includes a genuine failure -> still a "
    "mismatch even with approval_prompt_sent=True (widening is scoped to "
    "reads+pending only, never masks a real failure)",
    comparison_2h.mismatch is True)

_mixed_with_unverified = TurnEvidenceSummary()
_mixed_with_unverified.record_verification("ok", read_only=True)
_mixed_with_unverified.record_approval_pending()
_mixed_with_unverified.record_unverified_effect()
assert _mixed_with_unverified.classification() == "mixed"
comparison_2i = compare_shadow_final_status(
    "", _mixed_with_unverified, approval_prompt_sent=True,
)
chk("T2i: mixed evidence that ALSO includes an unverified effect -> still "
    "a mismatch even with approval_prompt_sent=True (same defense as T2h)",
    comparison_2i.mismatch is True)


# ══════════════════════════════════════════════════
# Section 3 — A32 regression: Single-Speaker suppression is UNCHANGED
# ══════════════════════════════════════════════════
print()
print("── 3. A32 Single-Speaker suppression still suppresses (regression) ──")

_pending_text = "⏳ הפעולה ממתינה לאישור, אעדכן ברגע שיאושר"
_tool_results_with_approval = [{"tool": "__approval_queued__", "content": "...", "ok": True}]

out_suppressed = sanitize_agent_response(
    _pending_text, _tool_results_with_approval, _gateway_active=True,
)
chk("T3: gateway_active=True + pending-status text + real __approval_queued__ "
    "evidence -> still suppressed to \"\" (A32's own decision is untouched by this PR)",
    out_suppressed == "")

out_not_gateway = sanitize_agent_response(
    _pending_text, _tool_results_with_approval, _gateway_active=False,
)
chk("T3: regression — gateway_active=False -> Single-Speaker gate does not "
    "fire at all (unchanged trigger condition)",
    out_not_gateway == _pending_text)


# ══════════════════════════════════════════════════
# Section 4 — end-to-end via the real run_agent()
# ══════════════════════════════════════════════════
print()
print("── 4. end-to-end: create_task queues approval -> pending shadow + ownership ──")


def _text_response(text: str):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


def _tool_use_response(tool_uses: list[dict]):
    blocks = [
        SimpleNamespace(type="tool_use", id=f"tu{i}", name=tu["name"], input=tu["input"])
        for i, tu in enumerate(tool_uses)
    ]
    return SimpleNamespace(
        content=blocks,
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )


class _enter_all:
    def __init__(self, patches):
        self._patches = patches
        self._started = []

    def __enter__(self):
        for p in self._patches:
            self._started.append(p.__enter__())
        return self._started

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.__exit__(*exc)
        return False


def _run_agent(chat_id: str, user_text: str, *, anthropic_responses):
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt="test", allowed_tools=[{"name": "airtable_add"}],
        memory_key=f"f52pr6test:{chat_id}", max_tokens=500,
        model="claude-haiku-test", identity_label=Role.OWNER,
    )
    route = RouteDecision(
        intent=Intent.CREATE_TASK, handler=Handler.AGENT,
        domain=RouterDomain.GENERAL, tool_allowed=True,
    )
    mock_bot = MagicMock()
    ownership_signals = []
    out_meta: dict = {}

    patches = [
        patch.object(app, "resolve_identity", return_value=identity),
        patch.object(app, "_safe_route", return_value=route),
        patch.object(app, "build_context", return_value=fake_ctx),
        patch.object(app.client.messages, "create", side_effect=anthropic_responses),
        patch.object(session_store.lead_sessions, "get", return_value=None),
        patch.object(app, "bot", mock_bot),
        patch(
            "core.turn_envelope.log_ownership_signal",
            side_effect=lambda signal, **kw: ownership_signals.append(signal),
        ),
    ]
    with _enter_all(patches):
        reply = app.run_agent(
            user_text, chat_id, channel="telegram",
            _live_contracts_snapshot=[], _out_meta=out_meta,
        )
    return reply, out_meta, ownership_signals, mock_bot


_TURN = [
    _tool_use_response([{"name": "airtable_add",
                          "input": {"table": "Tasks", "fields": {"Task": "בדיקת F52 PR6"}}}]),
    _text_response("⏳ הפעולה ממתינה לאישור, אעדכן ברגע שיאושר"),
]

# 4a — flag off (default): legacy prompt sent unchanged, no shadow log,
# final_reply suppressed as before, reply_owner="gateway", EvidenceFinalizer
# (if shadow) sees sent_for_approval not empty.
_old_gw   = os.environ.get("FEATURE_ACTION_GATEWAY")
_old_fmt  = os.environ.get("FEATURE_UNIFIED_STATUS_FORMATTER")
_old_fin  = os.environ.get("FEATURE_EVIDENCE_FINALIZER")
try:
    _set_env("FEATURE_ACTION_GATEWAY", "true")
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", None)
    _set_env("FEATURE_EVIDENCE_FINALIZER", "shadow")
    (reply4a, meta4a, sig4a, bot4a), log4a = _with_capture(
        "core.action_gateway",
        lambda: _run_agent("pr6_e2e_off", "צור לי משימה לבדוק F52 PR6", anthropic_responses=list(_TURN)),
    )
finally:
    _set_env("FEATURE_ACTION_GATEWAY", _old_gw)
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", _old_fmt)
    _set_env("FEATURE_EVIDENCE_FINALIZER", _old_fin)

chk("T4a: A32 still suppresses the agent's own pending-status text -> final_reply == \"\"",
    reply4a == "")
chk("T4a: owner WAS notified — bot.send_message called exactly once",
    bot4a.send_message.call_count == 1)
if bot4a.send_message.call_count == 1:
    _sent_text_4a = bot4a.send_message.call_args.args[1]
    chk("T4a: sent text is the legacy '⏳ בקשת אישור' prompt (flag off -> byte-identical)",
        _sent_text_4a.startswith("⏳ בקשת אישור"))
chk("T4a: flag off -> no [UnifiedStatusFormatterShadow] line emitted",
    not any("UnifiedStatusFormatterShadow" in m for m in log4a))
chk("T4a: ownership_signal.reply_owner == 'gateway' (not 'agent') when an "
    "approval was queued and the agent's text was suppressed",
    len(sig4a) == 1 and sig4a[0].reply_owner == "gateway")
chk("T4a: ownership_signal.approval_queued is True", len(sig4a) == 1 and sig4a[0].approval_queued is True)
chk("T4a: ownership_signal.agent_claimed_approval is False — build_ownership_signal() "
    "runs AFTER A32's sanitize_agent_response() already suppressed final_reply to \"\", "
    "so the claim-shape check correctly sees no claim text at all, exactly matching "
    "the production report's own ownership_signal (agent_claimed_approval=false)",
    len(sig4a) == 1 and sig4a[0].agent_claimed_approval is False)
chk("T4a: ownership_signal.is_hijack is False (tool_use_emitted=True and "
    "approval_queued=True — this is a real, backed action, not a phantom claim)",
    len(sig4a) == 1 and sig4a[0].is_hijack is False)
_efs4a = meta4a.get("evidence_finalizer_shadow")
chk("T4a: EvidenceFinalizerShadow sees response_claim=sent_for_approval, not empty",
    _efs4a is not None and _efs4a.get("response_claim") == "sent_for_approval")
chk("T4a: EvidenceFinalizerShadow no longer reports a mismatch for this turn",
    _efs4a is not None and _efs4a.get("mismatch") is False)
chk("T4a: EvidenceFinalizerShadow evidence classification is approval_pending",
    _efs4a is not None and _efs4a.get("evidence", {}).get("classification") == "approval_pending")

# 4b — flag shadow: legacy text STILL sent to the owner (byte-identical to
# 4a), but a [UnifiedStatusFormatterShadow] comparison IS now logged.
try:
    _set_env("FEATURE_ACTION_GATEWAY", "true")
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", "shadow")
    _set_env("FEATURE_EVIDENCE_FINALIZER", None)
    (reply4b, meta4b, sig4b, bot4b), log4b = _with_capture(
        "core.action_gateway",
        lambda: _run_agent("pr6_e2e_shadow", "צור לי משימה לבדוק F52 PR6 שוב", anthropic_responses=list(_TURN)),
    )
finally:
    _set_env("FEATURE_ACTION_GATEWAY", _old_gw)
    _set_env("FEATURE_UNIFIED_STATUS_FORMATTER", _old_fmt)
    _set_env("FEATURE_EVIDENCE_FINALIZER", _old_fin)

chk("T4b: shadow mode -> owner still notified exactly once",
    bot4b.send_message.call_count == 1)
if bot4b.send_message.call_count == 1 and bot4a.send_message.call_count == 1:
    _sent_text_4b = bot4b.send_message.call_args.args[1]
    chk("T4b: shadow mode -> the ACTUAL sent text is unchanged vs. flag-off "
        "(same legacy prompt shape, never the unified text)",
        _sent_text_4b.startswith("⏳ בקשת אישור"))
_shadow_lines_4b = [m for m in log4b if "UnifiedStatusFormatterShadow" in m]
chk("T4b: shadow mode -> exactly one [UnifiedStatusFormatterShadow] line for "
    "the pending prompt this turn",
    len(_shadow_lines_4b) == 1)
if _shadow_lines_4b:
    chk("T4b: shadow log -> outcome=pending mapped_state=approval_pending",
        "outcome=pending" in _shadow_lines_4b[0] and "mapped_state=approval_pending" in _shadow_lines_4b[0])


# ══════════════════════════════════════════════════
# Section 5 — regression: no approval queued this turn -> reply_owner
# stays "agent" (the fix is scoped, not a blanket relabel).
# ══════════════════════════════════════════════════
print()
print("── 5. regression: plain conversational turn keeps reply_owner='agent' ──")

try:
    _set_env("FEATURE_ACTION_GATEWAY", "true")
    reply5, meta5, sig5, bot5 = _run_agent(
        "pr6_e2e_no_approval", "שלום, מה שלומך?",
        anthropic_responses=[_text_response("שלום! הכל טוב.")],
    )
finally:
    _set_env("FEATURE_ACTION_GATEWAY", _old_gw)

chk("T5: no approval queued this turn -> bot.send_message never called",
    bot5.send_message.call_count == 0)
chk("T5: ownership_signal.approval_queued is False",
    len(sig5) == 1 and sig5[0].approval_queued is False)
chk("T5: ownership_signal.reply_owner stays 'agent' (fix is scoped to the "
    "approval-queued case, not a blanket relabel)",
    len(sig5) == 1 and sig5[0].reply_owner == "agent")


# ══════════════════════════════════════════════════
# Section 6 — regression: BUG-111/BUG-112/RP5 surfaces and the
# FEATURE_UNIFIED_STATUS_FORMATTER default are untouched by this PR.
# ══════════════════════════════════════════════════
print()
print("── 6. regression: unaffected surfaces + defaults ──")

from feature_flags import get_unified_status_formatter_state, get_evidence_finalizer_state  # noqa: E402

_old_fmt2 = os.environ.pop("FEATURE_UNIFIED_STATUS_FORMATTER", None)
chk("T6: FEATURE_UNIFIED_STATUS_FORMATTER still defaults to 'off'",
    get_unified_status_formatter_state() == "off")
if _old_fmt2 is not None:
    os.environ["FEATURE_UNIFIED_STATUS_FORMATTER"] = _old_fmt2

_old_fin2 = os.environ.pop("FEATURE_EVIDENCE_FINALIZER", None)
chk("T6: FEATURE_EVIDENCE_FINALIZER still defaults to 'off'",
    get_evidence_finalizer_state() == "off")
if _old_fin2 is not None:
    os.environ["FEATURE_EVIDENCE_FINALIZER"] = _old_fin2

import core.ingress_classifier as _ic  # noqa: E402
chk("T6: core.ingress_classifier (BUG-111's live path) untouched — "
    "_render_pending_prompt is not defined there",
    not hasattr(_ic, "_render_pending_prompt"))


# ══════════════════════════════════════════════════
print()
print("=" * 50)
print(f"F52 PR6 (approval_pending shadow + EvidenceFinalizer plumbing) tests: "
      f"{passed} passed, {failed} failed")
if failed:
    sys.exit(1)
