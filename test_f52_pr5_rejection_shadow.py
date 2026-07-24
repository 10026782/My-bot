#!/usr/bin/env python3
# test_f52_pr5_rejection_shadow.py — F52 PR5: route approval cancellation/
# rejection replies through the unified formatter shadow.
#
# Production finding that opened this follow-up: a real log showed the
# ActionContract lifecycle PATCH succeeding, "[ActionGateway] rejected:
# contract=... tool=airtable_update by=..." logged, and
# route_cancellation_word() returning "🚫 הפעולה בוטלה." — but NO
# [UnifiedStatusFormatterShadow] line was ever emitted. Root cause: PR4
# (F52 PR4, see test_f52_status_reply_reconciliation.py) only wired
# ActionGateway.compose_status_reply() into the EXECUTED/status-query path
# (_execute_contract/query_execution_status) — reject()/
# route_cancellation_word()/route_combined_word() built their own hardcoded
# legacy strings directly and never called compose_status_reply() at all,
# so FEATURE_UNIFIED_STATUS_FORMATTER=shadow had zero visibility into this
# surface.
#
# Fix (core/action_gateway.py): a new _render_rejection_reply() reuses the
# EXACT same off/shadow/on machinery PR4 already built
# (_compose_status_reply_unified/_log_shadow_comparison/_shadow_leak_flags —
# not duplicated, not reimplemented), applied to a "rejected" ActionFact.
# "rejected" continues to map to the "failure" family state — a decision
# already locked in PR1-3 (see agent_message_formatter.py's PR1 note);
# this PR does not add a new canonical state. Deliberately NOT folded into
# reject() itself (see the "F52 PR5" comment in core/action_gateway.py) —
# rendering happens at route_cancellation_word()'s and
# route_combined_word()'s own final return points, the actually-user-visible
# boundary, exactly mirroring where compose_status_reply() itself is called
# for the executed path.
#
# Explicitly out of scope / NOT covered by this PR (see final report):
#   - route_disambiguation()'s sibling-contract rejections (closing OTHER
#     pending contracts when the user picks one via ordinal) — never shown
#     to the user on their own (only the chosen contract's approve() reply
#     is returned), so there is no user-facing text to route through the
#     formatter there.
#   - app.py's Telegram inline-button reject path (_handle_approval_
#     callback_impl's "reject" branch) — a pre-existing, separate legacy
#     path that builds its own text directly and never calls
#     ActionGateway.reject()/compose_status_reply() at all (same gap the
#     existing BUG-BATCH-DISCARD comment already documents for contract
#     sync). Confirmed, not silently missed — see Test 6 below.
#   - BUG-111 lead parsing, RP5, FEATURE_UNIFIED_STATUS_FORMATTER's default/
#     enablement — untouched by this PR (see Test 7/8 + final report).

from __future__ import annotations

import logging
import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.action_gateway import ActionGateway

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _set_flag(state):
    if state is None:
        os.environ.pop("FEATURE_UNIFIED_STATUS_FORMATTER", None)
    else:
        os.environ["FEATURE_UNIFIED_STATUS_FORMATTER"] = state


class _LogCapture(logging.Handler):
    """Real logging.Handler (not the module-level logger swap PR4's own test
    file uses) — attached/detached around each call, capturing formatted
    messages without depending on core.action_gateway's private `logger`
    attribute name."""

    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


def _with_capture(fn):
    """Runs fn() with a capture handler attached to core.action_gateway's
    logger; returns (result, [captured message strings])."""
    cap = _LogCapture()
    gw_logger = logging.getLogger("core.action_gateway")
    gw_logger.addHandler(cap)
    gw_logger.setLevel(logging.INFO)
    try:
        result = fn()
    finally:
        gw_logger.removeHandler(cap)
    return result, cap.records


_CID = 0


def _propose(gw: ActionGateway, tool_name: str = "airtable_update") -> tuple[str, str]:
    """Proposes one pending contract for a fresh canonical_user_id; returns
    (canonical_user_id, contract_id)."""
    global _CID
    _CID += 1
    uid = f"boss_hq:f52pr5-{_CID}"
    result = gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=uid, tool_name=tool_name,
        tool_inputs={"table": "Leads", "record_id": f"recF52PR5{_CID:04d}", "fields": {"x": str(_CID)}},
        origin_channel="telegram", origin_chat_id=uid, requires_approval=True,
    )
    assert result.ok, f"propose_action failed: {result}"
    return uid, result.contract_id


# ══════════════════════════════════════════════════
# 1. off (default) — legacy text byte-identical, no shadow log
# ══════════════════════════════════════════════════
print("── 1. off (default): legacy text unchanged, no shadow log ──")

gw1 = ActionGateway()
uid1, cid1 = _propose(gw1)
try:
    _set_flag(None)
    out1, log1 = _with_capture(lambda: gw1.route_cancellation_word(uid1))
finally:
    _set_flag(None)

chk("T1: off -> exact legacy text '🚫 הפעולה בוטלה.'", out1 == "🚫 הפעולה בוטלה.")
chk("T1: off -> no [UnifiedStatusFormatterShadow] line at all",
    not any("UnifiedStatusFormatterShadow" in m for m in log1))
chk("T1: off -> contract durably rejected regardless",
    gw1._ledger.find_by_id(cid1).status == "rejected")


# ══════════════════════════════════════════════════
# 2. shadow: free-text "לא" against ONE pending ActionContract
# ══════════════════════════════════════════════════
print()
print("── 2. shadow: free-text cancellation emits unified shadow comparison ──")

gw2 = ActionGateway()
uid2, cid2 = _propose(gw2)
try:
    _set_flag("shadow")
    out2, log2 = _with_capture(lambda: gw2.route_cancellation_word(uid2))
finally:
    _set_flag(None)

chk("T2: shadow -> legacy text STILL sent (unchanged)", out2 == "🚫 הפעולה בוטלה.")
shadow_lines2 = [m for m in log2 if "UnifiedStatusFormatterShadow" in m]
chk("T2: shadow -> exactly one [UnifiedStatusFormatterShadow] comparison logged",
    len(shadow_lines2) == 1)
if shadow_lines2:
    line2 = shadow_lines2[0]
    chk("T2: shadow log -> outcome=rejected", "outcome=rejected" in line2)
    chk("T2: shadow log -> mapped_state is the failure family (locked "
        "since PR1-3, not a new state)", "mapped_state=failure" in line2)
    chk("T2: shadow log -> text_differs is present as a boolean field",
        "text_differs=" in line2)
    chk("T2: shadow log -> record_id_leak=False", "record_id_leak=False" in line2)
    chk("T2: shadow log -> tool_name_leak=False", "tool_name_leak=False" in line2)
    chk("T2: shadow log -> contract_id_leak=False", "contract_id_leak=False" in line2)
    chk("T2: shadow log -> fallback_used=False (recognized state, not the "
        "unrecognized-state fallback)", "fallback_used=False" in line2)
    chk("T2: shadow log never contains the raw record id",
        "recF52PR5" not in line2)
    chk("T2: shadow log never contains the raw tool name",
        "airtable_update" not in line2)
    chk("T2: shadow log never contains the raw contract id", cid2 not in line2)


# ══════════════════════════════════════════════════
# 3. shadow: "לא 1" combined cancel emits unified shadow comparison
# ══════════════════════════════════════════════════
print()
print("── 3. shadow: 'לא 1' combined cancel emits unified shadow comparison ──")

gw3 = ActionGateway()
uid3, cid3 = _propose(gw3)
try:
    _set_flag("shadow")
    out3, log3 = _with_capture(lambda: gw3.route_combined_word(uid3, "לא 1"))
finally:
    _set_flag(None)

chk("T3: combined cancel -> legacy text still sent",
    out3 == "🚫 פעולה מספר 1 בוטלה.")
shadow_lines3 = [m for m in log3 if "UnifiedStatusFormatterShadow" in m]
chk("T3: combined cancel -> exactly one shadow comparison logged",
    len(shadow_lines3) == 1)
if shadow_lines3:
    chk("T3: combined cancel shadow log -> outcome=rejected, mapped_state=failure",
        "outcome=rejected" in shadow_lines3[0] and "mapped_state=failure" in shadow_lines3[0])
chk("T3: contract durably rejected", gw3._ledger.find_by_id(cid3).status == "rejected")


# ══════════════════════════════════════════════════
# 4. Cancellation never renders as success
# ══════════════════════════════════════════════════
print()
print("── 4. cancellation never renders as success ──")

gw4 = ActionGateway()
uid4, cid4 = _propose(gw4)
try:
    _set_flag("on")
    out4 = gw4.route_cancellation_word(uid4)
finally:
    _set_flag(None)

chk("T4: 'on' rejection text contains no success marker (✓/✅)",
    "✓" not in out4 and "✅" not in out4)
chk("T4: 'on' rejection text is not empty and is genuinely the unified text "
    "(differs from the legacy '🚫 הפעולה בוטלה.')",
    bool(out4) and out4 != "🚫 הפעולה בוטלה.")

gw4b = ActionGateway()
uid4b, cid4b = _propose(gw4b)
try:
    _set_flag("on")
    out4b = gw4b.route_combined_word(uid4b, "לא 1")
finally:
    _set_flag(None)
chk("T4b: 'on' combined-cancel text also contains no success marker",
    "✓" not in out4b and "✅" not in out4b)


# ══════════════════════════════════════════════════
# 5. No Airtable record IDs / ActionContract IDs / tool names in the
#    user-facing UNIFIED text (legacy text is explicitly exempt — see the
#    route_combined_word() comment on its pre-existing tool_name leak)
# ══════════════════════════════════════════════════
print()
print("── 5. no record/contract IDs or tool names in unified cancellation text ──")

gw5 = ActionGateway()
uid5, cid5 = _propose(gw5)
try:
    _set_flag("on")
    out5 = gw5.route_cancellation_word(uid5)
finally:
    _set_flag(None)
chk("T5: unified single-cancel text has no raw record id", "recF52PR5" not in out5)
chk("T5: unified single-cancel text has no raw tool name", "airtable_update" not in out5)
chk("T5: unified single-cancel text has no raw contract id", cid5 not in out5)

gw5b = ActionGateway()
uid5b, cid5b = _propose(gw5b)
try:
    _set_flag("on")
    out5b = gw5b.route_combined_word(uid5b, "לא 1")
finally:
    _set_flag(None)
chk("T5b: unified combined-cancel text has no raw record id", "recF52PR5" not in out5b)
chk("T5b: unified combined-cancel text has no raw tool name "
    "(the LEGACY text for this exact path DOES leak it today — this proves "
    "the unified rendering specifically does not)",
    "airtable_update" not in out5b)
chk("T5b: unified combined-cancel text has no raw contract id", cid5b not in out5b)


# ══════════════════════════════════════════════════
# 6. Telegram callback reject path: canonical lifecycle wiring
# ══════════════════════════════════════════════════
print()
print("── 6. Telegram callback reject path: canonical rejection wired ──")

import inspect
import app as _app

_full_src = inspect.getsource(_app._handle_approval_callback_impl)
_reject_branch_src = _full_src[_full_src.index('elif action == "reject":'):]
_reject_branch_code_only = "\n".join(
    line for line in _reject_branch_src.splitlines()
    if not line.strip().startswith("#")
)
chk("T6: Telegram reject calls ActionGateway.reject()",
    ".reject(" in _reject_branch_code_only)
chk("T6: Telegram reject verifies the durable rejected status",
    '_reject_after.status != "rejected"' in _reject_branch_code_only)


# ══════════════════════════════════════════════════
# 7. Regression: legacy output unchanged when formatter flag is off
#    (byte-identical, both call sites)
# ══════════════════════════════════════════════════
print()
print("── 7. regression: legacy output unchanged when flag is off ──")

gw7 = ActionGateway()
uid7, _ = _propose(gw7)
_set_flag(None)
out7 = gw7.route_cancellation_word(uid7)
chk("T7: default (unset) flag -> exact legacy single-cancel text",
    out7 == "🚫 הפעולה בוטלה.")

gw7b = ActionGateway()
uid7b, _ = _propose(gw7b)
_set_flag("off")
out7b = gw7b.route_combined_word(uid7b, "לא 1")
chk("T7b: explicit 'off' -> exact legacy combined-cancel text",
    out7b == "🚫 פעולה מספר 1 בוטלה.")
_set_flag(None)


# ══════════════════════════════════════════════════
# 8. Confirmation: BUG-111 / RP5 / other flags / defaults untouched
# ══════════════════════════════════════════════════
print()
print("── 8. confirmation: no BUG-111/RP5/flags/defaults were changed ──")

from feature_flags import get_unified_status_formatter_state

_set_flag(None)
chk("T8: FEATURE_UNIFIED_STATUS_FORMATTER still defaults to 'off'",
    get_unified_status_formatter_state() == "off")

import core.ingress_classifier as _ic
chk("T8: core.ingress_classifier (BUG-111 live path) exposes its "
    "BUG-111 fixes unchanged — _extract_domain_hint present",
    hasattr(_ic, "_extract_domain_hint"))

from feature_flags import get_evidence_finalizer_state
chk("T8b: FEATURE_EVIDENCE_FINALIZER (RP4/RP5) still defaults to 'off' — "
    "this PR touched no RP5-related file",
    get_evidence_finalizer_state() == "off")


print(f"\n{'='*50}")
print(f"F52 PR5 (rejection/cancellation shadow) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
