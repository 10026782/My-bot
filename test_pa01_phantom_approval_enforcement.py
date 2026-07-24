#!/usr/bin/env python3
"""
test_pa01_phantom_approval_enforcement.py — PA-01 (Phantom Approval Prompt)
structural enforcement, per the approved Planning Gate:
docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md (commit 81676ad).

Mirrors test_pending_contract_read_amplification.py's direct-run_agent()-call
style (Identity/Router/Anthropic mocked, no Flask/webhook stack). Every
assertion here is a STATE check (tool_results_log contents, contract_id,
action_tool, terminal_outcome) — never a substring match on the agent's own
free text — per decision 8 ("no text detection in the gate, ever").
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-pa01-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PA01_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPA01Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPA01Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
import tool_registry  # noqa: E402
from tool_registry import ToolDenied  # noqa: E402
from tools.airtable_security import LeadsDirectWriteBlocked  # noqa: E402
from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision, Intent, Handler, RouterDomain  # noqa: E402
from core.router.risk_router import _CONTRACT_REQUIRED_INTENT_TO_TOOL  # noqa: E402
from context import AgentContext  # noqa: E402
import session_store  # noqa: E402

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
# Harness
# ══════════════════════════════════════════════════

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


def _run_agent(
    chat_id: str, user_text: str, *,
    role: str = Role.OWNER,
    intent: str = Intent.CREATE_TASK,
    handler: str = Handler.AGENT,
    domain: str = RouterDomain.GENERAL,
    tool_allowed: bool = True,
    allowed_tool_names: tuple = ("airtable_add",),  # matches the default intent (CREATE_TASK)
    anthropic_response=None,
    anthropic_responses=None,
    pa01_state: str = "off",
    capture_ownership_signal: bool = False,
    capture_memory: bool = False,
    capture_warnings: bool = False,
):
    identity = Identity(user_id=chat_id, role=role)
    fake_ctx = AgentContext(
        system_prompt="test",
        allowed_tools=[{"name": n} for n in allowed_tool_names],
        memory_key=f"pa01test:{chat_id}",
        max_tokens=500, model="claude-haiku-test", identity_label=role,
    )
    route = RouteDecision(intent=intent, handler=handler, domain=domain, tool_allowed=tool_allowed)

    create_kwargs = (
        {"side_effect": anthropic_responses} if anthropic_responses is not None
        else {"return_value": anthropic_response or _text_response("שלום")}
    )

    old_state = os.environ.get("FEATURE_PA01_ENFORCEMENT_STATE")
    os.environ["FEATURE_PA01_ENFORCEMENT_STATE"] = pa01_state

    memory_calls = []
    warning_calls = []
    ownership_signals = []

    patches = [
        patch.object(app, "resolve_identity", return_value=identity),
        patch.object(app, "_safe_route", return_value=route),
        patch.object(app, "build_context", return_value=fake_ctx),
        patch.object(app.client.messages, "create", **create_kwargs),
        patch.object(session_store.lead_sessions, "get", return_value=None),
    ]
    if capture_memory:
        patches.append(patch.object(
            app.memory, "add",
            side_effect=lambda key, role_, text: memory_calls.append((role_, text)),
        ))
    if capture_warnings:
        patches.append(patch.object(
            app.logger, "warning",
            side_effect=lambda msg, *a, **kw: warning_calls.append(msg % a if a else msg),
        ))
    if capture_ownership_signal:
        real_log = app_turn_envelope_log_ownership_signal()
        patches.append(patch(
            "core.turn_envelope.log_ownership_signal",
            side_effect=lambda signal, **kw: ownership_signals.append(signal),
        ))

    try:
        with _enter_all(patches):
            reply = app.run_agent(user_text, chat_id, channel="telegram", _live_contracts_snapshot=[])
    finally:
        if old_state is None:
            os.environ.pop("FEATURE_PA01_ENFORCEMENT_STATE", None)
        else:
            os.environ["FEATURE_PA01_ENFORCEMENT_STATE"] = old_state

    extra = {}
    if capture_memory:
        extra["memory_calls"] = memory_calls
    if capture_warnings:
        extra["warning_calls"] = warning_calls
    if capture_ownership_signal:
        extra["ownership_signals"] = ownership_signals
    return reply, extra


def app_turn_envelope_log_ownership_signal():
    from core.turn_envelope import log_ownership_signal
    return log_ownership_signal


class _enter_all:
    """Small ExitStack-style helper so the patch list above can be built
    conditionally without a fixed number of `with` clauses."""
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


PHANTOM = app._PA01_PHANTOM_APPROVAL_FALLBACK
CAPABILITY = app._PA01_CAPABILITY_UNAVAILABLE_FALLBACK


# ══════════════════════════════════════════════════
# A. Reproduction — the exact "פר 349" transcript, off/shadow/enforce
# (REPLY_OWNERSHIP_AND_APPROVAL_AUTHORITY_RESEARCH.md §2.1)
#
# Main Integration Pass note (merge commit 8fb0d0c): origin/main independently
# shipped BUG-FAKE-APPROVAL-INVITE (core/anti_hallucination.py's
# _AGENT_APPROVAL_INVITE_PATTERN) between PA-01's Planning Gate approval and
# this implementation's merge — an UNCONDITIONAL (not flag-gated), text-
# pattern-based gate inside sanitize_agent_response() that happens to also
# match this exact "פר 349" phrasing ("שלח מאשר" + "מוכנה להוספה") and
# replaces it with _NO_TOOL_EVIDENCE_FALLBACK BEFORE final_reply ever reaches
# PA-01's block. This does not change PA-01's own predicate/policy at all —
# PA-01 still computes BLOCK_PHANTOM purely from tool_results_log state,
# never from final_reply's text (decision 7/8, unchanged) — it only changes
# what final_reply already looks like by the time PA-01 evaluates it at
# state=off/shadow (where PA-01 never touches final_reply, so whichever
# upstream gate already fired is what the test observes). Confirmed via
# regex trace: only phrasing #1 below is caught by the new upstream pattern;
# phrasing #2 (identical shape, "רק תאשר" instead of "שלח מאשר") is not, and
# is used to independently pin PA-01's own off/shadow passthrough behavior
# for phrasings the new upstream gate does not cover.
# ══════════════════════════════════════════════════

from core.anti_hallucination import _NO_TOOL_EVIDENCE_FALLBACK  # noqa: E402

_PAR349_TEXT = "✅ המשימה מוכנה להוספה... שלח מאשר"

reply_off, _ = _run_agent(
    "par349_off", "צור משימה לבדוק פר 349 עד ל-8 בערב",
    anthropic_response=_text_response(_PAR349_TEXT), pa01_state="off",
)
chk("פר 349 transcript, state=off -> upstream BUG-FAKE-APPROVAL-INVITE gate (main, unconditional) "
    "already neutralizes this exact phrasing before PA-01's block runs; PA-01 itself does not "
    "touch final_reply at state=off either way",
    reply_off == _NO_TOOL_EVIDENCE_FALLBACK)

reply_shadow, extra_shadow = _run_agent(
    "par349_shadow", "צור משימה לבדוק פר 349 עד ל-8 בערב",
    anthropic_response=_text_response(_PAR349_TEXT), pa01_state="shadow",
    capture_warnings=True,
)
chk("פר 349 transcript, state=shadow -> same upstream-neutralized text as state=off "
    "(PA-01 shadow mode observes/logs but never touches final_reply)",
    reply_shadow == _NO_TOOL_EVIDENCE_FALLBACK)
chk("state=shadow -> a would_block PA-01 WARNING line still fires (PA-01's own state-based "
    "detection runs regardless of what the upstream text gate already did)",
    any("[PA-01]" in w and "would_block" in w for w in extra_shadow["warning_calls"]))

# Phrasing #2 — same phantom-approval shape, NOT matched by the new upstream
# _AGENT_APPROVAL_INVITE_PATTERN (no "שלח מאשר"/"לחץ...אשר"/"אשר כדי/בבקשה"/
# "מוכנ...להוספה" shape) — pins PA-01's own off/shadow passthrough behavior
# independent of the upstream gate's coverage.
_PAR349_VARIANT_TEXT = "המשימה מוכנה, רק תאשר ואני אוסיף אותה"

reply_off_variant, _ = _run_agent(
    "par349_off_variant", "צור משימה לבדוק פר 349 עד ל-8 בערב",
    anthropic_response=_text_response(_PAR349_VARIANT_TEXT), pa01_state="off",
)
chk("phantom-approval variant phrasing NOT caught by the upstream text gate, state=off -> "
    "PA-01 itself still does not touch final_reply (off means off)",
    reply_off_variant == _PAR349_VARIANT_TEXT)

reply_enforce, _ = _run_agent(
    "par349_enforce", "צור משימה לבדוק פר 349 עד ל-8 בערב",
    anthropic_response=_text_response(_PAR349_TEXT), pa01_state="enforce",
)
chk("פר 349 transcript, state=enforce -> final_reply equals the Phantom fallback exactly",
    reply_enforce == PHANTOM)


# ══════════════════════════════════════════════════
# B. 11-phrasing corpus (RESEARCH.md §2.8) — state-based assertion only,
# must not branch or special-case per phrasing.
# ══════════════════════════════════════════════════

_CORPUS = [
    "✅ המשימה מוכנה להוספה... שלח מאשר",
    "המשימה מוכנה, רק תאשר ואני אוסיף אותה",
    "כל 5 המשימות מוכנות — ממתינות לאישורך",
    "אני אוסיף את זה ברגע שתאשר",
    "בסדר, זה יתווסף לרשימה לאחר אישור",
    "רשמתי את זה בטיוטה, מחכה לאישור שלך",
    "המשימה מוכנה",
    "הכל מסודר, רק צריך את האישור שלך",
    "פר 349 מוכן להיכנס למערכת ברגע שתאשר",
    "✅ נרשם בטיוטה — ממתין לך",
    "בטח, אני דואג לזה — תאשר כשנוח",
]

_corpus_ok = True
for i, phrasing in enumerate(_CORPUS, start=1):
    reply, extra = _run_agent(
        f"corpus_{i}", "צור לי משימה",
        anthropic_response=_text_response(phrasing), pa01_state="enforce",
        capture_ownership_signal=True,
    )
    if reply != PHANTOM:
        _corpus_ok = False
        print(f"   ⚠ phrasing #{i} ({phrasing!r}) did not resolve to the Phantom fallback")
chk("11-phrasing corpus, state=enforce, zero tool_use, zero contract -> "
    "final_reply == Phantom fallback for all 11, uniformly (no per-phrasing branching)",
    _corpus_ok)


# ══════════════════════════════════════════════════
# C. Decision-7 regression — enforcement is state-based, not text-based:
# phrasing #7 ("המשימה מוכנה", bare) does not match is_hijack's own pattern
# at all, yet PA-01 still blocks it.
# ══════════════════════════════════════════════════

reply_c, extra_c = _run_agent(
    "decision7", "צור לי משימה",
    anthropic_response=_text_response("המשימה מוכנה"), pa01_state="enforce",
    capture_ownership_signal=True,
)
chk("is_hijack=False phrasing ('המשימה מוכנה') still triggers BLOCK_PHANTOM in enforce mode",
    reply_c == PHANTOM)
chk("...while is_hijack itself is independently False on the very same turn (proves no text dependency)",
    len(extra_c["ownership_signals"]) == 1 and extra_c["ownership_signals"][0].is_hijack is False)


# ══════════════════════════════════════════════════
# D. §3.5 policy regression — draft/conversational intents never false-positive
# ══════════════════════════════════════════════════

for _intent, _label in (
    (Intent.DRAFT_EMAIL, "DRAFT_EMAIL"),
    (Intent.DRAFT_MESSAGE, "DRAFT_MESSAGE"),
    (Intent.QUALIFY_LEAD, "QUALIFY_LEAD"),
):
    _text = "הנה טיוטה: שלום, מצטרפים לפגישה מחר?"
    reply_d, _ = _run_agent(
        f"policy_{_label}", "תכין לי טיוטה",
        intent=_intent, anthropic_response=_text_response(_text), pa01_state="enforce",
    )
    chk(f"{_label} with zero tool_use, state=enforce -> final_reply passes through unchanged "
        f"(not contract-required, matrix row 1)",
        reply_d == _text)

reply_unknown, _ = _run_agent(
    "policy_unknown", "מה השעה",
    intent=Intent.UNKNOWN, anthropic_response=_text_response("השעה 10:00"), pa01_state="enforce",
)
chk("Intent.UNKNOWN, state=enforce -> unaffected", reply_unknown == "השעה 10:00")


# ══════════════════════════════════════════════════
# E. §3.6 capability regression
# ══════════════════════════════════════════════════

# owner + CREATE_TASK + airtable_add available + zero tool_use -> Phantom (row 4)
reply_owner_cap, _ = _run_agent(
    "cap_owner", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
    allowed_tool_names=("airtable_add",),
    anthropic_response=_text_response("המשימה מוכנה להוספה, שלח מאשר"), pa01_state="enforce",
)
chk("owner + CREATE_TASK + airtable_add available + zero tool_use -> Phantom fallback",
    reply_owner_cap == PHANTOM)

# guest + CREATE_TASK + airtable_add NOT offered -> capability fallback, not Phantom
reply_guest, _ = _run_agent(
    "cap_guest", "צור לי משימה", role=Role.GUEST, intent=Intent.CREATE_TASK,
    allowed_tool_names=(),  # Role.GUEST: set() in context.py's _ROLE_TOOLS
    anthropic_response=_text_response("אני לא יכול לבצע את זה כרגע"), pa01_state="enforce",
)
chk("guest + CREATE_TASK + airtable_add not offered -> capability fallback (not Phantom)",
    reply_guest == CAPABILITY)

# employee + UPDATE_TASK + airtable_update NOT offered -> capability fallback
reply_employee, _ = _run_agent(
    "cap_employee", "עדכן את המשימה", role=Role.EMPLOYEE, intent=Intent.UPDATE_TASK,
    allowed_tool_names=("calendar_get_events", "airtable_get"),  # employee's real _ROLE_TOOLS
    anthropic_response=_text_response("אני לא יכול לעדכן משימות"), pa01_state="enforce",
)
chk("employee + UPDATE_TASK + airtable_update not offered -> capability fallback (not Phantom)",
    reply_employee == CAPABILITY)

# non-contract intent -> unaffected regardless of role/capability
reply_guest_draft, _ = _run_agent(
    "cap_guest_draft", "תכין טיוטה", role=Role.GUEST, intent=Intent.DRAFT_EMAIL,
    allowed_tool_names=(), anthropic_response=_text_response("הנה טיוטה"), pa01_state="enforce",
)
chk("guest + DRAFT_EMAIL (non-contract intent) -> unaffected regardless of capability",
    reply_guest_draft == "הנה טיוטה")


# ══════════════════════════════════════════════════
# F. ToolDenied -> PERMISSION_DENIED terminal outcome, not Phantom
# ══════════════════════════════════════════════════

_tool_denied_msg = "❌ owner אינו מורשה להפעיל 'airtable_add'"
with patch.object(app, "enforce", side_effect=ToolDenied(_tool_denied_msg)):
    reply_denied, _ = _run_agent(
        "tool_denied", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
        allowed_tool_names=("airtable_add",),
        anthropic_responses=[
            _tool_use_response([{"name": "airtable_add",
                                  "input": {"table": "Tasks", "fields": {"Task": "בדיקה"}}}]),
            _text_response("לא הצלחתי להוסיף את המשימה"),
        ],
        pa01_state="enforce",
    )
chk("ToolDenied on the expected tool -> final_reply replaced with the real ToolDenied message "
    "(row 3), not the generic Phantom fallback",
    reply_denied == _tool_denied_msg)


# ══════════════════════════════════════════════════
# G. Leads preflight block -> PREFLIGHT_BLOCKED terminal outcome, not Phantom
# ══════════════════════════════════════════════════

_preflight_msg = "❌ כתיבה ישירה לטבלת Leads חסומה מה-Agent"
with patch.object(app, "enforce_leads_write_gate", side_effect=LeadsDirectWriteBlocked(_preflight_msg)):
    reply_preflight, _ = _run_agent(
        "preflight", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
        allowed_tool_names=("airtable_add",),
        anthropic_responses=[
            _tool_use_response([{"name": "airtable_add",
                                  "input": {"table": "Leads", "fields": {"Name": "בדיקה"}}}]),
            _text_response("מנסה שוב"),
        ],
        pa01_state="enforce",
    )
chk("LeadsDirectWriteBlocked (BUG-091 preflight) on the expected tool -> final_reply replaced "
    "with the real preflight message (row 3), not the generic Phantom fallback",
    reply_preflight == _preflight_msg)


# ══════════════════════════════════════════════════
# H. Approval queue error (e.g. duplicate fingerprint) -> preserved, not Phantom
# ══════════════════════════════════════════════════

_queue_error_msg = "⚠️ פעולה זו כבר בוצעה לאחרונה (airtable_add). כפילות נחסמה."
with patch.object(app, "_queue_approval_detailed", return_value={
    "message": _queue_error_msg, "contract_id": None, "ok": False,
    "terminal_outcome": "APPROVAL_QUEUE_ERROR", "action_tool": "airtable_add",
    "created_this_turn": False,
}):
    reply_qerr, _ = _run_agent(
        "queue_error", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
        allowed_tool_names=("airtable_add",),
        anthropic_responses=[
            _tool_use_response([{"name": "airtable_add",
                                  "input": {"table": "Tasks", "fields": {"Task": "בדיקה"}}}]),
            _text_response("זה כבר בטיפול"),
        ],
        pa01_state="enforce",
    )
chk("_queue_approval_detailed() APPROVAL_QUEUE_ERROR outcome -> final_reply replaced with the "
    "gate's own accurate message (row 3), not the generic Phantom fallback",
    reply_qerr == _queue_error_msg)


# ══════════════════════════════════════════════════
# I. Contract of the correct expected tool -> row 2, Gateway reply preserved
# ══════════════════════════════════════════════════

_gw_reply_correct = "⏳ הפעולה ממתינה לאישור: הוסף ל-Tasks\nשלח *מאשר* כדי לאשר (בכל ערוץ)."
with patch.object(app, "_queue_approval_detailed", return_value={
    "message": _gw_reply_correct, "contract_id": "contract-correct-1", "ok": True,
    "terminal_outcome": None, "action_tool": "airtable_add", "created_this_turn": True,
}):
    reply_correct, _ = _run_agent(
        "contract_correct", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
        allowed_tool_names=("airtable_add",),
        anthropic_responses=[
            _tool_use_response([{"name": "airtable_add",
                                  "input": {"table": "Tasks", "fields": {"Task": "בדיקה"}}}]),
            _text_response(_gw_reply_correct),
        ],
        pa01_state="enforce",
    )
chk("CREATE_TASK + a real contract for airtable_add (the correct expected tool) -> "
    "matrix row 2, Gateway's own reply passes through untouched",
    reply_correct == _gw_reply_correct)


# ══════════════════════════════════════════════════
# J. Contract of the WRONG tool -> does not satisfy row 2, falls through to Phantom
# ══════════════════════════════════════════════════

_gw_reply_wrong = "⏳ הפעולה ממתינה לאישור: קבע פגישה\nשלח *מאשר* כדי לאשר (בכל ערוץ)."
with patch.object(app, "_queue_approval_detailed", return_value={
    "message": _gw_reply_wrong, "contract_id": "contract-wrong-tool-1", "ok": True,
    "terminal_outcome": None, "action_tool": "calendar_create_event", "created_this_turn": True,
}):
    reply_wrong, _ = _run_agent(
        "contract_wrong_tool", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
        allowed_tool_names=("airtable_add", "calendar_create_event"),
        anthropic_responses=[
            # Agent misfires: calls calendar_create_event for a CREATE_TASK request
            # (expected tool is airtable_add).
            _tool_use_response([{"name": "calendar_create_event",
                                  "input": {"summary": "בדיקה", "start": "2026-07-16T10:00"}}]),
            _text_response(_gw_reply_wrong),
        ],
        pa01_state="enforce",
    )
chk("CREATE_TASK + a real contract for calendar_create_event (the WRONG tool) -> "
    "does NOT satisfy row 2 -> falls through to Phantom fallback (row 4)",
    reply_wrong == PHANTOM)


# ══════════════════════════════════════════════════
# J2. BUG-CANONICAL-TOOL-WIRING x PA-01 (Main Integration Pass finding) —
# sentinel["action_tool"] must be the CANONICAL tool_name
# resolve_canonical_tool() actually used to create the contract, never the
# raw tool_use block's own (pre-canonicalization) name. Real
# _queue_approval_detailed()/ActionGateway.propose_action() — NOT mocked —
# so this exercises the actual canonicalization path end to end.
# ══════════════════════════════════════════════════

from core.action_gateway import action_gateway as _canon_gw  # noqa: E402

# J2.1 — model calls the expected tool directly (no rewrite needed) ->
# contract tool = airtable_add, sentinel action_tool = airtable_add,
# Gateway prompt preserved (row 2).
_gw_echo_1 = "⏳ ההוספה ממתינה לאישור שלך."
reply_j2_1, _ = _run_agent(
    "canon_direct", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
    allowed_tool_names=("airtable_add",),
    anthropic_responses=[
        _tool_use_response([{"name": "airtable_add",
                              "input": {"table": "Tasks", "fields": {"Task": "בדיקה קנונית 1"}}}]),
        _text_response(_gw_echo_1),
    ],
    pa01_state="enforce",
)
_contracts_1 = _canon_gw.find_live_contracts("boss_hq:canon_direct")
chk("J2.1: model calls airtable_add directly -> a real contract for airtable_add exists",
    len(_contracts_1) == 1 and _contracts_1[0].tool_name == "airtable_add")
chk("J2.1: row 2 holds -> final_reply untouched by PA-01",
    reply_j2_1 == _gw_echo_1)

# J2.2 — model calls sheets_append, user_text has no explicit Sheets/Drive
# request -> resolve_canonical_tool() rewrites it to airtable_add (the
# _CANONICAL_TOOL_DEFAULT). expected_tool for CREATE_TASK is airtable_add ->
# must still satisfy row 2, using the CANONICAL name, not the raw "sheets_append"
# the model actually called.
_gw_echo_2 = "⏳ ההוספה ממתינה לאישור שלך (2)."
reply_j2_2, _ = _run_agent(
    "canon_rewrite", "צור לי משימה לבדוק מה קורה עם אבי", role=Role.OWNER,
    intent=Intent.CREATE_TASK, allowed_tool_names=("airtable_add", "sheets_append"),
    anthropic_responses=[
        _tool_use_response([{"name": "sheets_append",
                              "input": {"table": "Tasks", "fields": {"Task": "בדיקה קנונית 2"}}}]),
        _text_response(_gw_echo_2),
    ],
    pa01_state="enforce",
)
_contracts_2 = _canon_gw.find_live_contracts("boss_hq:canon_rewrite")
chk("J2.2: model calls sheets_append (no explicit Sheets request) -> the REAL contract "
    "is created under the canonical airtable_add, not sheets_append",
    len(_contracts_2) == 1 and _contracts_2[0].tool_name == "airtable_add")
chk("J2.2: sentinel['action_tool'] (the canonical tool) matches expected_tool for CREATE_TASK "
    "-> contract_created_for_expected_tool=True -> row 2 holds, Gateway prompt preserved "
    "(would have been wrongly Phantom-blocked if action_tool had stayed 'sheets_append')",
    reply_j2_2 == _gw_echo_2)
chk("J2.2 invariant: sentinel['action_tool'] == the real stored ActionContract.tool_name",
    _contracts_2[0].tool_name == "airtable_add")

# J2.3 — canonical resolver returns a tool that is NOT the expected tool for
# this intent (CREATE_EVENT expects calendar_create_event; the model calls
# sheets_append with no explicit Sheets request, which resolves to
# airtable_add — a real but WRONG-for-this-intent tool). The contract must
# not be accepted as evidence for this intent; PA-01 must not reach row 2.
reply_j2_3, _ = _run_agent(
    "canon_mismatch", "קבע לי פגישה מחר", role=Role.OWNER, intent=Intent.CREATE_EVENT,
    allowed_tool_names=("calendar_create_event", "sheets_append"),
    anthropic_responses=[
        _tool_use_response([{"name": "sheets_append",
                              "input": {"table": "Tasks", "fields": {"Task": "לא רלוונטי"}}}]),
        _text_response("קבעתי לך, שלח מאשר"),
    ],
    pa01_state="enforce",
)
_contracts_3 = _canon_gw.find_live_contracts("boss_hq:canon_mismatch")
chk("J2.3: a real contract WAS created (for the canonical airtable_add), but it is not "
    "calendar_create_event (CREATE_EVENT's expected tool)",
    len(_contracts_3) == 1 and _contracts_3[0].tool_name != "calendar_create_event")
chk("J2.3: that contract is NOT accepted as evidence for CREATE_EVENT -> PA-01 does not "
    "reach row 2 -> final_reply is replaced (Phantom fallback, since owner is capable "
    "for calendar_create_event and no terminal outcome matches it either)",
    reply_j2_3 == PHANTOM)

# J2.4 — APPROVAL_QUEUE_ERROR after canonicalization: a second request with
# the same (canonicalized) tool/inputs/identity hits the cross-channel-
# duplicate branch. sentinel['action_tool'] must be the canonical tool, and
# the terminal outcome must be found only when scoped to the expected tool.
_dup_identity = Identity(user_id="canon_dup", role=Role.OWNER)
_first = app._queue_approval_detailed(
    "sheets_append", {"table": "Tasks", "fields": {"Task": "כפילות קנונית"}},
    "canon_dup", "telegram", "צור לי משימה",
)
chk("J2.4: first call's action_tool is already canonical (airtable_add), not sheets_append",
    _first["action_tool"] == "airtable_add")
_second = app._queue_approval_detailed(
    "sheets_append", {"table": "Tasks", "fields": {"Task": "כפילות קנונית"}},
    "canon_dup", "telegram", "צור לי משימה",
)
chk("J2.4: duplicate call -> APPROVAL_QUEUE_ERROR, action_tool still the canonical tool",
    _second["terminal_outcome"] == "APPROVAL_QUEUE_ERROR" and _second["action_tool"] == "airtable_add")
_dup_log = [{"tool": "__approval_queued__", "content": _second["message"], "ok": False,
             "contract_id": _second["contract_id"], "terminal_outcome": _second["terminal_outcome"],
             "action_tool": _second["action_tool"]}]
chk("J2.4: scoped lookup finds this outcome for airtable_add (the expected tool)...",
    app._pa01_structured_terminal_outcome(_dup_log, "airtable_add") is not None)
chk("...but NOT for an unrelated expected tool (e.g. calendar_create_event)",
    app._pa01_structured_terminal_outcome(_dup_log, "calendar_create_event") is None)

# J2.5 — backward compatibility: _queue_approval() (the string-returning
# wrapper) is unaffected by the action_tool addition.
_wrapper_reply = app._queue_approval(
    "airtable_add", {"table": "Tasks", "fields": {"Task": "wrapper בדיקה"}},
    "canon_wrapper", "telegram", "צור לי משימה",
)
chk("J2.5: _queue_approval() still returns a plain string",
    isinstance(_wrapper_reply, str))


# ══════════════════════════════════════════════════
# K. Unrelated-tool terminal outcome does not suppress a genuine Phantom check
# (direct unit test on the scoped lookup helper + one integration variant)
# ══════════════════════════════════════════════════

_unrelated_log = [
    {"tool": "gmail_send_draft", "content": "❌ owner אינו מורשה", "ok": False,
     "terminal_outcome": "PERMISSION_DENIED"},
]
chk("_pa01_structured_terminal_outcome: an entry for an unrelated tool is invisible "
    "to a different intent's expected_tool lookup",
    app._pa01_structured_terminal_outcome(_unrelated_log, "airtable_add") is None)

_matching_log = _unrelated_log + [
    {"tool": "airtable_add", "content": "❌ preflight blocked", "ok": False,
     "terminal_outcome": "PREFLIGHT_BLOCKED"},
]
_found = app._pa01_structured_terminal_outcome(_matching_log, "airtable_add")
chk("_pa01_structured_terminal_outcome: with multiple entries, only the one matching "
    "expected_tool is returned, and it is the correct one",
    _found == ("PREFLIGHT_BLOCKED", "❌ preflight blocked"))

_sentinel_log = _unrelated_log + [
    {"tool": "__approval_queued__", "content": "⚠️ duplicate", "ok": False,
     "contract_id": None, "terminal_outcome": "APPROVAL_QUEUE_ERROR", "action_tool": "airtable_add"},
]
_found_sentinel = app._pa01_structured_terminal_outcome(_sentinel_log, "airtable_add")
chk("_pa01_structured_terminal_outcome: the __approval_queued__ sentinel is matched via "
    "its action_tool key, not its literal 'tool' field",
    _found_sentinel == ("APPROVAL_QUEUE_ERROR", "⚠️ duplicate"))

# Integration variant: an unrelated PERMISSION_DENIED must not suppress a real
# Phantom block for the intent actually being evaluated.
with patch.object(app, "enforce", side_effect=ToolDenied("❌ owner אינו מורשה להפעיל 'gmail_send_draft'")):
    reply_unrelated, _ = _run_agent(
        "unrelated_outcome", "צור לי משימה וגם תכין טיוטת מייל", role=Role.OWNER,
        intent=Intent.CREATE_TASK, allowed_tool_names=("airtable_add", "gmail_send_draft"),
        anthropic_responses=[
            _tool_use_response([{"name": "gmail_send_draft", "input": {"to": "x@y.com", "body": "..."}}]),
            _text_response("המשימה מוכנה, שלח מאשר"),
        ],
        pa01_state="enforce",
    )
chk("a PERMISSION_DENIED for an unrelated tool (gmail_send_draft) does not suppress the "
    "Phantom check for this turn's own CREATE_TASK intent -> Phantom fallback still fires",
    reply_unrelated == PHANTOM)


# ══════════════════════════════════════════════════
# K2. Row-2 predicate: created_this_turn is required, a non-None contract_id
# alone is NOT sufficient (R1/R2/R3, the three required reproductions).
# ══════════════════════════════════════════════════

# --- R1: rejected/dedup contract_id — a real contract_id is present, but it
# points at an EXISTING contract the Gateway found via dedup, not one
# created this turn. Row 2 must not fire.
_r1_log = [{
    "tool": "__approval_queued__", "content": "⏳ כבר יש בקשת אישור פתוחה לפעולה זו.",
    "ok": False, "contract_id": "existing-contract-999",
    "terminal_outcome": "APPROVAL_QUEUE_ERROR", "action_tool": "airtable_add",
    "created_this_turn": False,
}]
chk("R1 (unit): contract_id present but created_this_turn=False -> "
    "_pa01_contract_created_for_expected_tool is False",
    app._pa01_contract_created_for_expected_tool(_r1_log, "airtable_add") is False)

with patch.object(app, "_queue_approval_detailed", return_value={
    "message": "⏳ כבר יש בקשת אישור פתוחה לפעולה זו.", "contract_id": "existing-contract-999",
    "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR", "action_tool": "airtable_add",
    "created_this_turn": False,
}):
    reply_r1, _ = _run_agent(
        "r1_rejected_dedup", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
        allowed_tool_names=("airtable_add",),
        anthropic_responses=[
            _tool_use_response([{"name": "airtable_add",
                                  "input": {"table": "Tasks", "fields": {"Task": "R1"}}}]),
            _text_response("איזה כיף, זה כבר בטיפול"),
        ],
        pa01_state="enforce",
    )
chk("R1 (integration): a rejected/dedup contract_id does NOT satisfy row 2 -> "
    "final_reply is replaced with the real terminal_outcome message (row 3), not left as "
    "a raw agent reply and not the generic Phantom fallback",
    reply_r1 == "⏳ כבר יש בקשת אישור פתוחה לפעולה זו.")

# --- R2: shadow proposal failure — no ActionContract was ever created.
# Exercise the REAL _queue_approval_detailed() (not mocked) with
# FEATURE_ACTION_GATEWAY off (shadow mode) and ActionGateway.propose_action()
# itself failing (persistence_failed).
from core.action_gateway import GatewayResult  # noqa: E402

with patch("feature_flags.is_enabled", return_value=False), \
     patch.object(_canon_gw, "propose_action", return_value=GatewayResult(
         ok=False, reason="לא ניתן לשמור את בקשת הפעולה באופן עמיד.",
         user_message="❌ לא ניתן לשמור כרגע את בקשת האישור. הפעולה לא הועברה לאישור ולא תבוצע.",
         failure_code="persistence_failed",
     )):
    _r2_result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "R2"}},
        "r2_shadow_fail", "telegram", "צור לי משימה",
    )
chk("R2 (unit): shadow proposal failure -> ok=False, contract_id=None, "
    "terminal_outcome=APPROVAL_QUEUE_ORPHANED (Codex re-audit of 818c8a6, P1-3: "
    "ExecutionLedger.save() raising via failure_code=persistence_failed does not prove "
    "the write never landed -- ownership/acknowledgment is uncertain, not verified-clean), "
    "created_this_turn=False",
    _r2_result["ok"] is False and _r2_result["contract_id"] is None
    and _r2_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _r2_result["created_this_turn"] is False)

with patch.object(app, "_queue_approval_detailed", return_value=_r2_result):
    reply_r2, _ = _run_agent(
        "r2_integration", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
        allowed_tool_names=("airtable_add",),
        anthropic_responses=[
            _tool_use_response([{"name": "airtable_add",
                                  "input": {"table": "Tasks", "fields": {"Task": "R2b"}}}]),
            _text_response("מעולה, זה ממתין לאישור"),
        ],
        pa01_state="enforce",
    )
chk("R2 (integration): shadow proposal failure -> no Gateway-success prompt (row 2 does not "
    "fire), final_reply is the deterministic persistence-failure message, never the raw "
    "agent reply",
    reply_r2 == _r2_result["message"] and reply_r2 != "מעולה, זה ממתין לאישור")

# --- R3: the expected tool is the SECOND tool_results_log entry, not the
# first. The scan must not stop at (or be determined by) entry #1.
_r3_log = [
    {"tool": "gmail_send_draft", "content": "❌ owner אינו מורשה", "ok": False,
     "terminal_outcome": "PERMISSION_DENIED"},
    {"tool": "__approval_queued__", "content": "⏳ ההוספה ממתינה לאישור",
     "ok": True, "contract_id": "contract-r3-1", "terminal_outcome": None,
     "action_tool": "airtable_add", "created_this_turn": True},
]
chk("R3 (unit): the first entry (unrelated tool) does not determine the outcome for this intent",
    app._pa01_contract_created_for_expected_tool(_r3_log[:1], "airtable_add") is False)
chk("R3 (unit): the scan is not stopped by the first entry -> the SECOND (matching) entry "
    "is found and satisfies row 2",
    app._pa01_contract_created_for_expected_tool(_r3_log, "airtable_add") is True)

# R3 (integration): a real turn where tool_use #1 is denied (unrelated tool,
# does not consume the "first mutating approval this turn" slot) and tool_use
# #2 is the expected tool, genuinely queued as the turn's one live contract.
with patch.object(app, "enforce", side_effect=lambda name, ident: (
    (_ for _ in ()).throw(ToolDenied("❌ owner אינו מורשה להפעיל 'gmail_send_draft'"))
    if name == "gmail_send_draft" else tool_registry.enforce(name, ident)
)):
    reply_r3, _ = _run_agent(
        "r3_batch_second", "תכין טיוטת מייל וגם צור לי משימה", role=Role.OWNER,
        intent=Intent.CREATE_TASK, allowed_tool_names=("airtable_add", "gmail_send_draft"),
        anthropic_responses=[
            _tool_use_response([
                {"name": "gmail_send_draft", "input": {"to": "x@y.com", "body": "..."}},
                {"name": "airtable_add", "input": {"table": "Tasks", "fields": {"Task": "R3"}}},
            ]),
            _text_response("סיימתי, שלח מאשר להוספה"),
        ],
        pa01_state="enforce",
    )
_r3_contracts = _canon_gw.find_live_contracts("boss_hq:r3_batch_second")
chk("R3 (integration): a real contract for the expected tool (airtable_add) was created "
    "even though it was the SECOND tool call this turn",
    len(_r3_contracts) == 1 and _r3_contracts[0].tool_name == "airtable_add")
chk("R3 (integration): row 2 fires from the matching second entry -> final_reply untouched "
    "by PA-01, despite the unrelated first entry being a PERMISSION_DENIED",
    reply_r3 == "סיימתי, שלח מאשר להוספה")


# ══════════════════════════════════════════════════
# P1. Codex re-audit of commit b7eb2bb (verdict: FIX_REQUIRED) — the return
# state of _queue_approval_detailed() must match the CANONICAL state (real
# ActionContract status, real EventBus pending items, real batch_queue
# contents), never just the structured GatewayResult.ok/failure_code shapes
# R1/R2/R3 above already covered. Three findings:
#   P1-A — a REAL exception from propose_action() (not a structured
#          GatewayResult failure) must not fall through to the legacy
#          EventBus path.
#   P1-B — an expected-tool call genuinely deferred to batch_queue (mixed
#          batch, wrong-tool contract created first) must be represented in
#          tool_results_log, not silently invisible to PA-01.
#   P1-C — if a contract IS durably persisted but a later step (EventBus
#          publish / owner notification) fails, the orphaned live contract
#          must be revoked, never left live while the return denies it.
# ══════════════════════════════════════════════════

from event_bus import bus as _real_bus, pending as _real_pending, batch_queue as _real_batch_queue  # noqa: E402

# --- P1-A / R2-real: propose_action() raises a REAL exception (RuntimeError),
# not a structured GatewayResult(ok=False, failure_code=...). Pre-fix, the
# shadow-mode try/except around propose_action() caught this at DEBUG level
# and fell straight through to bus.request_approval() below it, producing a
# real legacy EventBus pending item with no canonical ActionContract behind
# it, and a success-shaped return once execution reached the bottom of the
# function (created_this_turn computed off a None _gw_result -> False, but
# the MESSAGE still claimed "⏳ הפעולה ממתינה לאישור").
with patch("feature_flags.is_enabled", return_value=False), \
     patch.object(_canon_gw, "propose_action", side_effect=RuntimeError("boom")):
    _r2real_result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "R2real"}},
        "r2real_exc", "telegram", "צור לי משימה",
    )
chk("P1-A / R2-real: propose_action() raising a real exception -> no ActionContract exists "
    "for this identity afterwards",
    len(_canon_gw.find_live_contracts("boss_hq:r2real_exc")) == 0)
chk("P1-A / R2-real: structured failure returned -- ok=False, contract_id=None, "
    "terminal_outcome=APPROVAL_QUEUE_ORPHANED (Codex re-audit of 818c8a6: propose_action() "
    "raising without ever returning a GatewayResult means ownership of any contract_id is "
    "NOT proven for this call -- the conservative/unattributable outcome, not verified-clean), "
    "created_this_turn=False (never a raw exception, never a phantom-success shape)",
    _r2real_result["ok"] is False and _r2real_result["contract_id"] is None
    and _r2real_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _r2real_result["created_this_turn"] is False)
chk("P1-A / R2-real: no EventBus pending representation was created for this identity -- "
    "the exception must not fall through to bus.request_approval()",
    len(_real_pending.list_for_chat("r2real_exc")) == 0)

with patch.object(app, "_queue_approval_detailed", return_value=_r2real_result):
    reply_r2real, _ = _run_agent(
        "r2real_integration", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
        allowed_tool_names=("airtable_add",),
        anthropic_responses=[
            _tool_use_response([{"name": "airtable_add",
                                  "input": {"table": "Tasks", "fields": {"Task": "R2real-b"}}}]),
            _text_response("מעולה, זה ממתין לאישור"),
        ],
        pa01_state="enforce",
    )
chk("P1-A / R2-real (integration): no row 2, no false 'pending' message -> final_reply is "
    "the deterministic queue-error message, never the raw agent reply claiming success",
    reply_r2real == _r2real_result["message"] and reply_r2real != "מעולה, זה ממתין לאישור")

# Gateway enforcement state (FEATURE_ACTION_GATEWAY) vs PA-01's own state
# (FEATURE_PA01_ENFORCEMENT_STATE) are independent axes. The fix lives in
# _queue_approval_detailed_impl() itself, unconditionally on every call --
# prove the safe return contract holds with PA-01 fully unset (off), not
# just when the outer harness happens to set pa01_state="enforce" above.
_old_pa01_env = os.environ.pop("FEATURE_PA01_ENFORCEMENT_STATE", None)
try:
    with patch("feature_flags.is_enabled", return_value=False), \
         patch.object(_canon_gw, "propose_action", side_effect=RuntimeError("boom")):
        _r2real_off_result = app._queue_approval_detailed(
            "airtable_add", {"table": "Tasks", "fields": {"Task": "R2real-off"}},
            "r2real_off", "telegram", "צור לי משימה",
        )
finally:
    if _old_pa01_env is not None:
        os.environ["FEATURE_PA01_ENFORCEMENT_STATE"] = _old_pa01_env
chk("P1-A / R2-real: PA-01 state=off (unset) -> identical safe return contract -- this is a "
    "_queue_approval_detailed_impl() plumbing fix, not a PA-01-gated behavior",
    _r2real_off_result["ok"] is False and _r2real_off_result["contract_id"] is None
    and _r2real_off_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _r2real_off_result["created_this_turn"] is False)

# Gateway ENFORCE mode (FEATURE_ACTION_GATEWAY=True) was already safe for
# this exact exception shape pre-fix -- propose_action() raising there
# propagates out of _queue_approval_detailed_impl() entirely (bus.
# request_approval() is unconditionally AFTER the whole if/else block, so an
# exception from inside the "if" branch never reaches it) and is caught only
# by _queue_approval_detailed()'s own outer exception-normalizing wrapper.
# Confirmed here so both Gateway modes are provably covered by this suite,
# not just the one (shadow) that needed a real code change.
with patch("feature_flags.is_enabled", return_value=True), \
     patch.object(_canon_gw, "propose_action", side_effect=RuntimeError("boom")):
    _r2real_enforce_gw_result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "R2real-enforce-gw"}},
        "r2real_enforce_gw", "telegram", "צור לי משימה",
    )
chk("P1-A / R2-real: FEATURE_ACTION_GATEWAY=True (Gateway enforce mode) -- already safe for "
    "this exception shape pre-fix, confirmed still safe post-fix",
    _r2real_enforce_gw_result["ok"] is False and _r2real_enforce_gw_result["contract_id"] is None
    and _r2real_enforce_gw_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _r2real_enforce_gw_result["created_this_turn"] is False)
chk("...and no EventBus pending representation was created for this identity either",
    len(_real_pending.list_for_chat("r2real_enforce_gw")) == 0)


# --- P1-B / R3-real: mixed batch -- a real, live contract is created for an
# UNRELATED tool (calendar_create_event, tool call #1 this turn), and the
# intent's own expected tool (airtable_add, tool call #2) is blocked by the
# BUG-122 single-unresolved-action policy. It is not retained for promotion.
_r3real_inputs = {"table": "Tasks", "fields": {"Task": "P1B"}}
_r3real_expected_blocked_msg = (
    "⛔ הפעולה הנוספת לא נשמרה. יש לפתור את הפעולה "
    "הממתינה ואז לשלוח את הבקשה מחדש."
)

reply_r3real, _ = _run_agent(
    "r3real_mixed_batch", "קבע לי פגישה וגם צור משימה", role=Role.OWNER,
    intent=Intent.CREATE_TASK, allowed_tool_names=("airtable_add", "calendar_create_event"),
    anthropic_responses=[
        _tool_use_response([
            {"name": "calendar_create_event",
             "input": {"summary": "פגישה", "start_time": "2026-07-20T10:00"}},
            {"name": "airtable_add", "input": _r3real_inputs},
        ]),
        _text_response("קבעתי וגם אוסיף את המשימה"),
    ],
    pa01_state="enforce",
)
_r3real_contracts = _canon_gw.find_live_contracts("boss_hq:r3real_mixed_batch")
chk("P1-B / R3-real: a real contract WAS created -- for calendar_create_event (the FIRST "
    "mutating call this turn), not airtable_add",
    len(_r3real_contracts) == 1 and _r3real_contracts[0].tool_name == "calendar_create_event")
chk("P1-B / R3-real: airtable_add was not retained in batch_queue",
    _real_batch_queue.count_pending("boss_hq:r3real_mixed_batch") == 0)
chk("P1-B / R3-real: row 2 does NOT fire (no __approval_queued__ sentinel for airtable_add "
    "this turn) and the Phantom fallback does NOT fire either -- final_reply is the "
    "structured pending-policy block",
    reply_r3real == _r3real_expected_blocked_msg)
chk("P1-B / R3-real: the wrong-tool contract (calendar_create_event) is not mistaken for "
    "evidence about airtable_add, and the raw agent reply is not left standing either",
    reply_r3real != PHANTOM and reply_r3real != "קבעתי וגם אוסיף את המשימה")

# Unit-level pin on the scoped lookup itself (mirrors R3's own unit/
# integration split above): a blocked entry for a DIFFERENT tool must
# not satisfy the expected tool's lookup, and an entry for the actual
# expected tool must be found regardless of position in the log.
_r3real_log = [
    {"tool": "__approval_queued__", "content": "irrelevant", "ok": True,
     "contract_id": "c-1", "terminal_outcome": None, "action_tool": "calendar_create_event",
     "created_this_turn": True},
    {"tool": "__approval_blocked_pending__", "content": _r3real_expected_blocked_msg,
     "ok": False, "contract_id": None, "terminal_outcome": "APPROVAL_BLOCKED_PENDING",
     "action_tool": "airtable_add", "created_this_turn": False},
]
chk("P1-B (unit): _pa01_contract_created_for_expected_tool is False for airtable_add "
    "(it was blocked, never a live contract this turn)",
    app._pa01_contract_created_for_expected_tool(_r3real_log, "airtable_add") is False)
chk("P1-B (unit): _pa01_structured_terminal_outcome finds the blocked entry for "
    "airtable_add, scanning past the unrelated calendar_create_event entry first",
    app._pa01_structured_terminal_outcome(_r3real_log, "airtable_add")
    == ("APPROVAL_BLOCKED_PENDING", _r3real_expected_blocked_msg))


# --- P1-C / R4: a canonical tool's ActionContract IS durably persisted, but
# a LATER step in the same _queue_approval_detailed_impl() call fails. The
# orphaned live contract must be revoked -- not left live while the return
# value claims (contract_id=None) that nothing was created.

# R4a: bus.request_approval() itself raises, immediately after a successful
# propose_action(). requested tool is sheets_append (no explicit Sheets
# wording in user_text) -> canonicalizes to airtable_add; the return's
# action_tool must be the canonical name throughout, never the raw request.
with patch("feature_flags.is_enabled", return_value=False), \
     patch.object(_real_bus, "request_approval", side_effect=RuntimeError("eventbus down")):
    _r4a_result = app._queue_approval_detailed(
        "sheets_append", {"table": "Tasks", "fields": {"Task": "R4a"}},
        "r4a_eventbus_fail", "telegram", "צור לי משימה",
    )
chk("P1-C / R4a: canonical tool (sheets_append -> airtable_add) was persisted, then "
    "bus.request_approval() raises -> the persisted contract is revoked, not left live",
    len(_canon_gw.find_live_contracts("boss_hq:r4a_eventbus_fail")) == 0)
chk("P1-C / R4a: return contract denies the contract truthfully -- contract_id=None, "
    "ok=False, terminal_outcome=APPROVAL_QUEUE_ERROR, created_this_turn=False, and "
    "action_tool is the CANONICAL tool (airtable_add), never the raw requested tool "
    "(sheets_append)",
    _r4a_result["contract_id"] is None and _r4a_result["ok"] is False
    and _r4a_result["terminal_outcome"] == "APPROVAL_QUEUE_ERROR"
    and _r4a_result["created_this_turn"] is False
    and _r4a_result["action_tool"] == "airtable_add")

# R4b: bus.request_approval() succeeds (a real EventBus pending item is
# created) but the owner-notification step that follows raises. By this
# point BOTH a live ActionContract AND a live EventBus pending item exist --
# both must be revoked/cancelled, not just silently denied in the return.
from unittest.mock import MagicMock  # noqa: E402

_old_owner_env = os.environ.get("OWNER_TELEGRAM_ID")
os.environ["OWNER_TELEGRAM_ID"] = "999999"
_mock_bot_r4b = MagicMock()
_mock_bot_r4b.send_message.side_effect = RuntimeError("telegram down")
try:
    with patch("feature_flags.is_enabled", return_value=False), \
         patch.object(app, "bot", _mock_bot_r4b):
        _r4b_result = app._queue_approval_detailed(
            "airtable_add", {"table": "Tasks", "fields": {"Task": "R4b"}},
            "r4b_notify_fail", "telegram", "צור לי משימה",
        )
finally:
    if _old_owner_env is None:
        os.environ.pop("OWNER_TELEGRAM_ID", None)
    else:
        os.environ["OWNER_TELEGRAM_ID"] = _old_owner_env
chk("P1-C / R4b: contract persisted, then owner notification fails -> the contract is "
    "revoked (not left live+approvable with no owner ever notified)",
    len(_canon_gw.find_live_contracts("boss_hq:r4b_notify_fail")) == 0)
chk("P1-C / R4b: the legacy EventBus pending item created just before the notify failure "
    "is also cancelled, not left orphaned either",
    len(_real_pending.list_for_chat("r4b_notify_fail")) == 0)
chk("P1-C / R4b: return contract is truthful -- contract_id=None, ok=False, "
    "terminal_outcome=APPROVAL_QUEUE_ERROR, created_this_turn=False",
    _r4b_result["contract_id"] is None and _r4b_result["ok"] is False
    and _r4b_result["terminal_outcome"] == "APPROVAL_QUEUE_ERROR"
    and _r4b_result["created_this_turn"] is False)


# ══════════════════════════════════════════════════
# P2. Codex re-audit of commit 8e05d67 (verdict: FIX_REQUIRED) — the P1
# fix's own cleanup was still not verified in every failure mode:
#   P1(4-finding-1) — propose_action() raising AFTER persist left _gw_result
#                      None, so the old cleanup (keyed off _gw_result) could
#                      not find anything to revoke.
#   P1(4-finding-2) — revocation was "best-effort" and never checked
#                      reject()'s own outcome; a durable-transition failure
#                      there leaves the contract "pending" while the old
#                      code still returned contract_id=None.
#   P1(4-finding-3) — the same best-effort gap for EventBus pending.cancel().
#   P1(4-finding-4) — the outer wrapper's action_tool fell back to the RAW
#                      (pre-canonicalization) tool name on any exception,
#                      contradicting the documented "always canonical" field
#                      contract.
# ══════════════════════════════════════════════════

from event_bus import executed_action_cache as _real_eac  # noqa: E402
from core.action_contract_repository import ActionContractTransitionError  # noqa: E402
import core.action_gateway as _action_gateway_module  # noqa: E402

# --- P2-1 (REVISED per Codex re-audit of 818c8a6 -- architectural ruling):
# propose_action() raises AFTER ExecutionLedger.save() has already durably
# persisted the contract, but BEFORE returning a GatewayResult. _gw_result
# therefore stays None inside _impl -- there is no contract_id PROVEN to
# belong to this call. The PREVIOUS fix (818c8a6) relocated the orphan via a
# fingerprint match and revoked it -- but a fingerprint proves the business
# action is identical, not that THIS call created the contract found under
# it (it could be a pre-existing or concurrently-created one from a totally
# different call). That fingerprint-based mutation has been REMOVED. The new,
# correct expectation is the opposite of the old one: the contract this
# mock genuinely persists is left COMPLETELY UNTOUCHED (still "pending"),
# and the return is the conservative APPROVAL_QUEUE_ORPHANED state with
# contract_id=None (unknown/unattributable -- not "verified absent").
def _raise_after_persist(msg, *args, **kwargs):
    if isinstance(msg, str) and msg.startswith("[ActionGateway] propose_action:"):
        raise RuntimeError("simulated crash after ExecutionLedger.save()")
    return None


with patch("feature_flags.is_enabled", return_value=False), \
     patch.object(_action_gateway_module.logger, "info", side_effect=_raise_after_persist):
    _p2_1_result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "P2-1-shadow"}},
        "p2_1_shadow_after_persist", "telegram", "צור לי משימה",
    )
_p2_1_live = _canon_gw.find_live_contracts("boss_hq:p2_1_shadow_after_persist")
chk("P2-1 (shadow mode): a contract WAS durably saved before the simulated crash, and is "
    "left COMPLETELY UNTOUCHED -- still live/pending -- since this call never proved it "
    "owns any contract_id (no fingerprint-based mutation is attempted)",
    len(_p2_1_live) == 1 and _p2_1_live[0].status == "pending")
chk("P2-1 (shadow mode): return is the conservative ORPHANED state -- contract_id=None "
    "(meaning 'not attributable to this call', not 'verified absent'), ok=False, "
    "terminal_outcome=APPROVAL_QUEUE_ORPHANED, created_this_turn=False, action_tool canonical",
    _p2_1_result["contract_id"] is None and _p2_1_result["ok"] is False
    and _p2_1_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _p2_1_result["created_this_turn"] is False
    and _p2_1_result["action_tool"] == "airtable_add")

with patch("feature_flags.is_enabled", return_value=True), \
     patch.object(_action_gateway_module.logger, "info", side_effect=_raise_after_persist):
    _p2_1_enforce_result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "P2-1-enforce"}},
        "p2_1_enforce_after_persist", "telegram", "צור לי משימה",
    )
_p2_1_enforce_live = _canon_gw.find_live_contracts("boss_hq:p2_1_enforce_after_persist")
chk("P2-1 (Gateway enforce mode): same crash-after-persist shape -- also left untouched, "
    "still live/pending",
    len(_p2_1_enforce_live) == 1 and _p2_1_enforce_live[0].status == "pending")
chk("P2-1 (Gateway enforce mode): return is the conservative ORPHANED state",
    _p2_1_enforce_result["contract_id"] is None and _p2_1_enforce_result["ok"] is False
    and _p2_1_enforce_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _p2_1_enforce_result["created_this_turn"] is False)


# --- P2-2: ActionGateway.reject()'s own durable transition fails (returns a
# failure STRING, does not raise) -- the contract remains "pending". The old
# fix treated reject() not raising as proof of success; the fix must verify
# via a fresh find_live_contracts() query instead.
with patch("feature_flags.is_enabled", return_value=False), \
     patch.object(_real_bus, "request_approval", side_effect=RuntimeError("eventbus down")), \
     patch.object(_canon_gw._ledger, "update_status",
                   side_effect=ActionContractTransitionError("simulated durable transition failure")):
    _p2_2_result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "P2-2"}},
        "p2_2_durable_reject_fail", "telegram", "צור לי משימה",
    )
_p2_2_live = _canon_gw.find_live_contracts("boss_hq:p2_2_durable_reject_fail")
chk("P2-2: reject()'s durable transition failed -- the contract is HONESTLY still "
    "live (this is the correct, verified state -- not silently claimed clean)",
    len(_p2_2_live) == 1)
chk("P2-2: the return does NOT falsely claim contract_id=None -- it carries the REAL "
    "(still-live) contract_id and a DISTINCT terminal_outcome (APPROVAL_QUEUE_ORPHANED), "
    "never the generic APPROVAL_QUEUE_ERROR shape other (genuinely clean) branches use",
    _p2_2_result["contract_id"] == _p2_2_live[0].contract_id
    and _p2_2_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _p2_2_result["ok"] is False and _p2_2_result["created_this_turn"] is False)


# --- P2-3: PendingActionsStore.cancel() itself raises (not just a silent
# failure) after the contract WAS successfully revoked. The EventBus pending
# item must be honestly reported as still-live, not silently assumed gone.
_old_owner_env_p23 = os.environ.get("OWNER_TELEGRAM_ID")
os.environ["OWNER_TELEGRAM_ID"] = "999999"
_mock_bot_p23 = MagicMock()
_mock_bot_p23.send_message.side_effect = RuntimeError("telegram down")
try:
    with patch("feature_flags.is_enabled", return_value=False), \
         patch.object(app, "bot", _mock_bot_p23), \
         patch.object(_real_pending, "cancel", side_effect=RuntimeError("eventbus cancel broken")):
        _p2_3_result = app._queue_approval_detailed(
            "airtable_add", {"table": "Tasks", "fields": {"Task": "P2-3"}},
            "p2_3_pending_cancel_fail", "telegram", "צור לי משימה",
        )
finally:
    if _old_owner_env_p23 is None:
        os.environ.pop("OWNER_TELEGRAM_ID", None)
    else:
        os.environ["OWNER_TELEGRAM_ID"] = _old_owner_env_p23
chk("P2-3: the contract itself WAS successfully revoked (verified) despite the "
    "EventBus cancel() failure -- the two cleanups are independent",
    len(_canon_gw.find_live_contracts("boss_hq:p2_3_pending_cancel_fail")) == 0)
chk("P2-3: cancel() raising is not silently swallowed -- the return signals the "
    "unverified EventBus state via APPROVAL_QUEUE_ORPHANED, not the generic "
    "APPROVAL_QUEUE_ERROR shape that would imply everything is confirmed clean",
    _p2_3_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _p2_3_result["ok"] is False and _p2_3_result["created_this_turn"] is False)


# --- P2-4: action_tool must stay canonical even when the exception happens
# BEFORE propose_action() is ever reached (no contract could possibly exist
# yet) -- this is a pure "outer wrapper's own return value" bug, independent
# of P2-1/2/3's contract-cleanup concerns.
with patch.object(_real_eac, "compute", side_effect=RuntimeError("cache compute broken")):
    _p2_4_result = app._queue_approval_detailed(
        "sheets_append", {"table": "Tasks", "fields": {"Task": "P2-4"}},
        "p2_4_canonical_action_tool", "telegram", "צור לי משימה",
    )
chk("P2-4: action_tool is CANONICAL (airtable_add, not the raw sheets_append) even "
    "though the crash happened before _impl's own canonicalized local variable could "
    "ever be read by the outer wrapper's exception handler",
    _p2_4_result["action_tool"] == "airtable_add")
chk("P2-4: no contract exists either way (the crash predates propose_action() entirely)",
    len(_canon_gw.find_live_contracts("boss_hq:p2_4_canonical_action_tool")) == 0)
chk("P1-2 (Codex re-audit of 818c8a6): the outer wrapper never attempts a fingerprint "
    "lookup for this unattributed exception -- return is the conservative ORPHANED state "
    "with contract_id=None (unattributable, not 'verified absent'), not APPROVAL_QUEUE_ERROR",
    _p2_4_result["contract_id"] is None
    and _p2_4_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _p2_4_result["ok"] is False and _p2_4_result["created_this_turn"] is False)

with patch("core.action_gateway.resolve_canonical_tool", side_effect=RuntimeError("canonicalization itself broke")):
    _p2_4b_result = app._queue_approval_detailed(
        "sheets_append", {"table": "Tasks", "fields": {"Task": "P2-4b"}},
        "p2_4b_canonicalization_itself_fails", "telegram", "צור לי משימה",
    )
chk("P2-4b: when canonicalization ITSELF is what fails (the one case where 'canonical' "
    "is genuinely unknowable), falls back to the raw pre-canonicalization name rather "
    "than raising or inventing a value",
    _p2_4b_result["action_tool"] == "sheets_append")
chk("P1-2: no fingerprint lookup is attempted when canonicalization itself fails either -- "
    "ORPHANED, contract_id=None",
    _p2_4b_result["contract_id"] is None
    and _p2_4b_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _p2_4b_result["ok"] is False and _p2_4b_result["created_this_turn"] is False)


# ══════════════════════════════════════════════════
# P3. Codex re-audit of commit 818c8a6 (verdict: FIX_REQUIRED) —
# architectural ruling: a business-action fingerprint proves two calls
# describe the same action, never that THIS call's ActionContract found
# under it. The 8 required reproductions from the re-audit; #5 (structured
# persistence_failed must not return verified-clean) is R2 above, #8 (exact
# owned contract ID + durable reject failure stays ORPHANED) is P2-2 above —
# both already updated/covered. The remaining 6 are added here.
# ══════════════════════════════════════════════════

# --- P3-1: a PRE-EXISTING pending contract for the identical fingerprint
# already exists (created by an earlier, unrelated call) when OUR call fails
# with an unattributed exception. Must be left completely untouched.
_p3_1_preexisting = _canon_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:p3_preexisting", tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "pre-existing"}},
    origin_channel="telegram", origin_chat_id="p3_preexisting", requires_approval=True,
    identity=Identity(user_id="p3_preexisting", role=Role.OWNER), user_text="",
)
assert _p3_1_preexisting.ok, "test setup: pre-existing contract must be created successfully"

with patch("feature_flags.is_enabled", return_value=False), \
     patch.object(_canon_gw, "propose_action",
                   side_effect=RuntimeError("our own call crashes, same fingerprint")):
    _p3_1_result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "pre-existing"}},
        "p3_preexisting", "telegram", "",
    )
chk("P3-1: a pre-existing same-fingerprint contract is left COMPLETELY UNTOUCHED (still "
    "'pending') when our own call fails without ever proving ownership of any contract_id",
    _canon_gw.find_contract(_p3_1_preexisting.contract_id).status == "pending")
chk("P3-1: our call's own return is the conservative ORPHANED state, never attributing "
    "the pre-existing contract's ID to us",
    _p3_1_result["contract_id"] is None
    and _p3_1_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _p3_1_result["ok"] is False and _p3_1_result["created_this_turn"] is False)


# --- P3-2: a CONCURRENT turn creates a contract for the identical
# fingerprint (modeled here as happening right after our own call fails,
# proving timing/ordering has no bearing -- nothing in our failure path ever
# scans by fingerprint, so it cannot matter whether the other contract
# existed before, during, or after).
with patch("feature_flags.is_enabled", return_value=False), \
     patch.object(_canon_gw, "propose_action",
                   side_effect=RuntimeError("our own call crashes; a concurrent turn will "
                                             "create the real contract for this fingerprint")):
    _p3_2_result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "concurrent"}},
        "p3_concurrent", "telegram", "",
    )
_p3_2_concurrent = _canon_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:p3_concurrent", tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "concurrent"}},
    origin_channel="telegram", origin_chat_id="p3_concurrent", requires_approval=True,
    identity=Identity(user_id="p3_concurrent", role=Role.OWNER), user_text="",
)
chk("P3-2: the concurrent turn's own contract creation succeeds normally, completely "
    "unaffected by our earlier failed call for the identical fingerprint",
    _p3_2_concurrent.ok is True
    and _canon_gw.find_contract(_p3_2_concurrent.contract_id).status == "pending")
chk("P3-2: our failed call's own return never attributes the concurrent contract's ID "
    "to itself either",
    _p3_2_result["contract_id"] is None
    and _p3_2_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED")


# --- P3-3: a failure BEFORE propose_action() is ever reached
# (executed_action_cache.compute()) must not touch a pre-existing
# same-fingerprint contract either.
_p3_3_preexisting = _canon_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:p3_before_propose", tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "before-propose"}},
    origin_channel="telegram", origin_chat_id="p3_before_propose", requires_approval=True,
    identity=Identity(user_id="p3_before_propose", role=Role.OWNER), user_text="",
)
with patch.object(_real_eac, "compute", side_effect=RuntimeError("cache compute broken")):
    _p3_3_result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {"Task": "before-propose"}},
        "p3_before_propose", "telegram", "",
    )
chk("P3-3: a failure before propose_action() is ever reached does not touch the "
    "pre-existing same-fingerprint contract",
    _canon_gw.find_contract(_p3_3_preexisting.contract_id).status == "pending")
chk("P3-3: return is the conservative ORPHANED state",
    _p3_3_result["contract_id"] is None
    and _p3_3_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED")


# --- P3-4: a canonicalization failure must not touch a pre-existing
# contract genuinely stored under the raw (sheets_append) tool name either.
# Explicit Sheets wording ("גיליון") ensures resolve_canonical_tool()
# preserves sheets_append rather than rewriting it to airtable_add, so the
# pre-existing contract is genuinely raw-tool-named.
_p3_4_preexisting = _canon_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:p3_canon_fail", tool_name="sheets_append",
    tool_inputs={"table": "Tasks", "fields": {"Task": "raw-tool"}},
    origin_channel="telegram", origin_chat_id="p3_canon_fail", requires_approval=True,
    identity=Identity(user_id="p3_canon_fail", role=Role.OWNER),
    user_text="תוסיף את זה לגיליון בבקשה",
)
assert _canon_gw.find_contract(_p3_4_preexisting.contract_id).tool_name == "sheets_append", (
    "test setup: pre-existing contract must genuinely be stored under the raw tool name"
)

with patch("core.action_gateway.resolve_canonical_tool",
           side_effect=RuntimeError("canonicalization broke")):
    _p3_4_result = app._queue_approval_detailed(
        "sheets_append", {"table": "Tasks", "fields": {"Task": "raw-tool"}},
        "p3_canon_fail", "telegram", "",
    )
chk("P3-4: canonicalization failure does not touch a pre-existing raw-tool-named contract",
    _canon_gw.find_contract(_p3_4_preexisting.contract_id).status == "pending")
chk("P3-4: action_tool falls back to the raw tool name for telemetry only; no lookup/revoke "
    "was attempted (ORPHANED, contract_id=None)",
    _p3_4_result["action_tool"] == "sheets_append"
    and _p3_4_result["contract_id"] is None
    and _p3_4_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED")


# --- P3-6: a lifecycle race -- a contract this call PROVES it owns (a real
# contract_id from a genuine, unmocked propose_action() success) is moved to
# "approved" by a concurrent turn's own approval flow WHILE our cleanup
# would run. reject() itself is a no-op on a non-pending contract (core/
# action_gateway.py's own reject() body: "if contract.status != 'pending':
# return ..." without attempting any transition) -- our cleanup must not
# report success, and must not disturb the concurrently-approved contract.
_p3_6_owned = _canon_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:p3_race", tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "race"}},
    origin_channel="telegram", origin_chat_id="p3_race", requires_approval=True,
    identity=Identity(user_id="p3_race", role=Role.OWNER), user_text="",
)
assert _p3_6_owned.ok
_canon_gw._ledger.update_status(
    _p3_6_owned.contract_id, "approved", approved_by="a_concurrent_turn", approved_at=0,
)
_p3_6_cleanup_ok = app._revoke_and_verify_contract(
    "boss_hq:p3_race", _p3_6_owned.contract_id, "test_lifecycle_race",
)
chk("P3-6: cleanup does NOT report success for a contract that raced to 'approved' "
    "concurrently -- reject() is a no-op on a non-pending contract, and 'approved' is "
    "not in the safe-cancelled status set",
    _p3_6_cleanup_ok is False)
chk("P3-6: the concurrently-approved contract is undisturbed -- our reject() attempt "
    "never mutated its status",
    _canon_gw.find_contract(_p3_6_owned.contract_id).status == "approved")


# --- P3-7: the positive case -- an OWNED contract_id (proven via a genuine,
# unmocked propose_action() success) that reject() genuinely transitions to
# "rejected" IS reported as a successful, verified cleanup.
_p3_7_owned = _canon_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:p3_success", tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "success"}},
    origin_channel="telegram", origin_chat_id="p3_success", requires_approval=True,
    identity=Identity(user_id="p3_success", role=Role.OWNER), user_text="",
)
assert _p3_7_owned.ok
_p3_7_cleanup_ok = app._revoke_and_verify_contract(
    "boss_hq:p3_success", _p3_7_owned.contract_id, "test_genuine_success",
)
chk("P3-7: a genuine reject() success on an owned contract_id IS verified and reported "
    "as successful cleanup",
    _p3_7_cleanup_ok is True)
chk("P3-7: the contract's exact status is confirmed 'rejected' via the authoritative "
    "find_contract() lookup by ID -- not inferred from find_live_contracts() membership",
    _canon_gw.find_contract(_p3_7_owned.contract_id).status == "rejected")


# ══════════════════════════════════════════════════
# P4. Codex re-audit of commit 0d658c1 (verdict: FIX_REQUIRED) — the
# ownership-proven cleanup path (P3-7 above) still had a TOCTOU race: the
# dangerous window is AFTER reject() checks status == "pending" but BEFORE
# ExecutionLedger.update_status() writes. On the default RAM path
# (FEATURE_ACTION_CONTRACT_PERSISTENCE off) that write was unconditional, so
# a concurrent turn moving the contract pending -> approved inside the window
# was clobbered to "rejected", and _revoke_and_verify_contract() then read
# "rejected" and falsely reported success. Fixed by making the transition an
# ATOMIC conditional pending -> rejected (reject_if_pending() /
# update_status(require_status="pending")).
#
# Deterministic reproduction of the exact window: wrap the ledger's
# update_status so the concurrent approval lands right as the write is about
# to happen. Both the old racy reject() and the new atomic
# reject_if_pending() funnel through update_status(), so the SAME injection
# seam exercises both -- red against 0d658c1 (old unconditional overwrite
# clobbers the approval and reports success), green against the fix (the
# atomic guard refuses to overwrite the now-approved contract).
# ══════════════════════════════════════════════════

_p4_owned = _canon_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:p4_race", tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "race-window"}},
    origin_channel="telegram", origin_chat_id="p4_race", requires_approval=True,
    identity=Identity(user_id="p4_race", role=Role.OWNER), user_text="",
)
assert _p4_owned.ok and _canon_gw.find_contract(_p4_owned.contract_id).status == "pending"

_p4_cid = _p4_owned.contract_id
_p4_ledger = _canon_gw._ledger
_p4_orig_update = _p4_ledger.update_status
_p4_injected = {"done": False}


def _p4_inject_concurrent_approval(contract_id, status, **kwargs):
    # Simulate a concurrent turn approving THIS contract in the exact window
    # between the caller's "is it pending?" check and this write. Fires once,
    # only for our contract's rejection write, then delegates to the real
    # update_status with whatever args the caller passed (crucially including
    # require_status for the new atomic path, or its absence for the old one).
    if contract_id == _p4_cid and status == "rejected" and not _p4_injected["done"]:
        _p4_injected["done"] = True
        _p4_ledger._store[_p4_cid].status = "approved"
    return _p4_orig_update(contract_id, status, **kwargs)


with patch.object(_p4_ledger, "update_status", side_effect=_p4_inject_concurrent_approval):
    _p4_cleanup_ok = app._revoke_and_verify_contract(
        "boss_hq:p4_race", _p4_cid, "test_toctou_race",
    )

chk("P4 (TOCTOU race): a concurrent approval landing between the pending-check and the "
    "ledger write is NOT clobbered -- the atomic conditional transition refuses to "
    "overwrite the now-approved contract (final status stays 'approved')",
    _canon_gw.find_contract(_p4_cid).status == "approved")
chk("P4 (TOCTOU race): cleanup does NOT report success for the raced-approval contract "
    "(the exact false-success the fix targets)",
    _p4_cleanup_ok is False)

# Unit-level pin on the atomic primitive itself: reject_if_pending() returns
# False and mutates nothing when the contract is already non-pending, and
# True (transitioning to 'rejected') only from a genuine pending state.
_p4_np = _canon_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:p4_nonpending", tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "non-pending"}},
    origin_channel="telegram", origin_chat_id="p4_nonpending", requires_approval=True,
    identity=Identity(user_id="p4_nonpending", role=Role.OWNER), user_text="",
)
_canon_gw._ledger.update_status(_p4_np.contract_id, "approved", approved_by="x", approved_at=0)
chk("P4 (unit): reject_if_pending() returns False on an already-approved contract and does "
    "not mutate it",
    _canon_gw.reject_if_pending(_p4_np.contract_id) is False
    and _canon_gw.find_contract(_p4_np.contract_id).status == "approved")

_p4_p = _canon_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:p4_pending", tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "pending-ok"}},
    origin_channel="telegram", origin_chat_id="p4_pending", requires_approval=True,
    identity=Identity(user_id="p4_pending", role=Role.OWNER), user_text="",
)
chk("P4 (unit): reject_if_pending() returns True and transitions a genuinely pending "
    "contract to 'rejected'",
    _canon_gw.reject_if_pending(_p4_p.contract_id) is True
    and _canon_gw.find_contract(_p4_p.contract_id).status == "rejected")


# ══════════════════════════════════════════════════
# P5. Codex re-audit of commit ce990a0 (verdict: FIX_REQUIRED) — the atomic
# RAM guard is only atomic for the RAM-only ledger. When a DURABLE Airtable
# repository is active, ActionContractRepository.transition() is read-check-
# PATCH (no CAS), so a conditional destructive cleanup through it is TOCTOU-
# prone AND its idempotent shortcut ran before the expected-status/version
# check (returning success for expected=pending/actual=rejected). Two fixes:
#   fix 1 — the ledger fails closed (no PATCH, returns False) for a
#           require_status transition when the durable repository does not
#           declare supports_atomic_conditional_transition.
#   fix 2 — ActionContractRepository.transition() checks expected
#           status/version BEFORE the idempotent shortcut.
# The 5 required reproductions D1–D5.
# ══════════════════════════════════════════════════

from core.action_gateway import ExecutionLedger as _ExecutionLedger, ActionGateway as _ActionGateway  # noqa: E402
from core.action_contract_repository import (  # noqa: E402
    ActionContractRepository as _RealRepo,
    ActionContractTransitionConflictError as _ConflictError,
    _contract_to_fields as _to_fields,
)
from airtable_schema import ActionContractsFields as _ACF  # noqa: E402


class _NoCASRepo:
    """A durable repository stand-in that, like the real Airtable one, does
    NOT declare supports_atomic_conditional_transition — so the ledger must
    fail closed rather than route a conditional destructive write through it.
    Records every transition() call so the test can assert none was made."""
    # deliberately no supports_atomic_conditional_transition attribute
    def __init__(self):
        self.records = {}
        self.transition_calls = []

    def save(self, contract):
        self.records[contract.contract_id] = contract
        return True

    def get(self, contract_id):
        return self.records.get(contract_id)

    def find_by_business_fingerprint(self, fingerprint):
        return next((c for c in self.records.values()
                     if c.business_action_fingerprint == fingerprint), None)

    def find_pending_by_canonical_user(self, canonical_user_id):
        return [c for c in self.records.values()
                if c.canonical_user_id == canonical_user_id and c.status == "pending"]

    def transition(self, contract_id, *, expected_status, expected_version, new_status, updates=None):
        self.transition_calls.append((expected_status, expected_version, new_status))
        c = self.records.get(contract_id)
        if c is None:
            raise _ConflictError("missing")
        if c.status != expected_status or c.version != expected_version:
            raise _ConflictError("stale")
        c.status = new_status
        c.version += 1
        return c


def _d_propose(gw, uid, chat, task):
    r = gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=uid, tool_name="airtable_add",
        tool_inputs={"table": "Tasks", "fields": {"Task": task}},
        origin_channel="telegram", origin_chat_id=chat, requires_approval=True,
        identity=Identity(user_id=chat, role=Role.OWNER), user_text="",
    )
    assert r.ok
    return r.contract_id


# --- D1: durable TOCTOU — repository active, no atomic conditional primitive.
# reject_if_pending() must fail closed: transitioned=False, and NO transition
# (PATCH) is attempted at all, so a concurrent approval cannot be clobbered.
_d1_repo = _NoCASRepo()
_d1_gw = _ActionGateway(ledger=_ExecutionLedger(repository=_d1_repo))
_d1_cid = _d_propose(_d1_gw, "boss_hq:d1", "d1", "durable-toctou")
# a concurrent turn approves the durable contract
_d1_repo.records[_d1_cid].status = "approved"
_d1_repo.records[_d1_cid].version += 1
_d1_transitioned = _d1_gw.reject_if_pending(_d1_cid)
chk("D1 (durable): reject_if_pending() fails closed on a non-CAS durable repository -> "
    "returns False",
    _d1_transitioned is False)
chk("D1 (durable): NO durable transition/PATCH was attempted at all (the ledger refuses to "
    "route a conditional destructive write through a non-atomic repository)",
    _d1_repo.transition_calls == [])
chk("D1 (durable): the concurrent approval is not clobbered -- durable status stays 'approved'",
    _d1_repo.records[_d1_cid].status == "approved")


# --- D2: already-rejected shortcut — the real ActionContractRepository.
# transition() must check expected status/version BEFORE the idempotent
# shortcut. expected=pending/v1 against an actual rejected/v2 record must
# CONFLICT, never return success, and never PATCH.
_d2_seed_cid = _d_propose(_canon_gw, "boss_hq:d2", "d2", "shortcut")
_d2_pending_contract = _canon_gw.find_contract(_d2_seed_cid)
_d2_fields = dict(_to_fields(_d2_pending_contract))
_d2_fields.update({_ACF.STATUS: "rejected", _ACF.VERSION: 2})
_d2_record = {"id": "rec-d2", "fields": _d2_fields}

_d2_repo = _RealRepo()
_d2_conflict = False
with patch("core.action_contract_repository.at_get_by_field", return_value=_d2_record), \
     patch("core.action_contract_repository.airtable_patch") as _d2_patch:
    try:
        _d2_repo.transition(
            _d2_seed_cid, expected_status="pending", expected_version=1, new_status="rejected",
        )
    except _ConflictError:
        _d2_conflict = True
chk("D2 (shortcut): expected_status=pending against an actual rejected/v2 record raises a "
    "conflict -- the idempotent shortcut never fires before the expected-state check",
    _d2_conflict is True)
chk("D2 (shortcut): no PATCH is attempted on the stale/already-rejected contract",
    _d2_patch.call_count == 0)


# --- D3: RAM-only atomic success. No repository -> the single-lock guarded
# set genuinely performs pending -> rejected.
_d3_cid = _d_propose(_canon_gw, "boss_hq:d3", "d3", "ram-success")
chk("D3 (RAM): reject_if_pending() on a genuinely pending contract returns True and "
    "transitions it to 'rejected'",
    _canon_gw.reject_if_pending(_d3_cid) is True
    and _canon_gw.find_contract(_d3_cid).status == "rejected")


# --- D4: RAM-only concurrent approval wins first. reject_if_pending() must
# refuse (atomic guard), leaving the approval intact.
_d4_cid = _d_propose(_canon_gw, "boss_hq:d4", "d4", "ram-race")
_canon_gw._ledger.update_status(_d4_cid, "approved", approved_by="concurrent", approved_at=0)
chk("D4 (RAM): a concurrent approval that won first is not overwritten -- reject_if_pending() "
    "returns False and the status stays 'approved'",
    _canon_gw.reject_if_pending(_d4_cid) is False
    and _canon_gw.find_contract(_d4_cid).status == "approved")


# --- D5: PA-01 durable cleanup outcome. A post-persistence failure (owner
# notification) triggers cleanup while a durable repository is active. There
# must be no overwrite, no cleanup-success claim; the result is
# APPROVAL_QUEUE_ORPHANED, row 2 is not triggered, and the message does not
# claim the request was cancelled.
_d5_repo = _NoCASRepo()
_d5_saved_repo = _canon_gw._ledger._repository
_d5_old_owner = os.environ.get("OWNER_TELEGRAM_ID")
os.environ["OWNER_TELEGRAM_ID"] = "999999"
_d5_bot = MagicMock()
_d5_bot.send_message.side_effect = RuntimeError("telegram down")
try:
    _canon_gw._ledger._repository = _d5_repo
    with patch("feature_flags.is_enabled", return_value=False), \
         patch.object(app, "bot", _d5_bot):
        _d5_result = app._queue_approval_detailed(
            "airtable_add", {"table": "Tasks", "fields": {"Task": "d5-durable"}},
            "d5_durable", "telegram", "צור לי משימה",
        )
finally:
    _canon_gw._ledger._repository = _d5_saved_repo
    if _d5_old_owner is None:
        os.environ.pop("OWNER_TELEGRAM_ID", None)
    else:
        os.environ["OWNER_TELEGRAM_ID"] = _d5_old_owner

chk("D5 (PA-01 durable cleanup): owner-notify failure under a durable non-CAS repository -> "
    "terminal_outcome=APPROVAL_QUEUE_ORPHANED (not verified-clean APPROVAL_QUEUE_ERROR), "
    "ok=False, created_this_turn=False",
    _d5_result["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED"
    and _d5_result["ok"] is False and _d5_result["created_this_turn"] is False)
chk("D5 (PA-01 durable cleanup): the real (owned) contract_id is surfaced, and the durable "
    "contract was NOT overwritten (no transition/PATCH attempted, still 'pending')",
    _d5_result["contract_id"] is not None
    and _d5_repo.transition_calls == []
    and _d5_repo.records[_d5_result["contract_id"]].status == "pending")
chk("D5 (PA-01 durable cleanup): the message does NOT claim the request was cancelled or is "
    "pending approval",
    "בוטלה" not in _d5_result["message"] and "ממתינה לאישור" not in _d5_result["message"])
chk("D5 (PA-01 durable cleanup): this outcome does NOT satisfy row 2 (contract_created)",
    app._pa01_contract_created_for_expected_tool(
        [{"tool": "__approval_queued__", "content": _d5_result["message"],
          "ok": _d5_result["ok"], "contract_id": _d5_result["contract_id"],
          "terminal_outcome": _d5_result["terminal_outcome"],
          "action_tool": _d5_result["action_tool"],
          "created_this_turn": _d5_result["created_this_turn"]}],
        "airtable_add") is False)


# ══════════════════════════════════════════════════
# L. Pending approval from a PRIOR turn — unaffected, PA-01 never reached
# ══════════════════════════════════════════════════

from core.action_gateway import action_gateway as _real_gw  # noqa: E402

_prior_identity = Identity(user_id="prior_turn_user", role=Role.OWNER)
_real_gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=_prior_identity.memory_key,
    tool_name="airtable_add", tool_inputs={"table": "Tasks", "fields": {"Task": "משהו ישן"}},
    origin_channel="telegram", origin_chat_id="prior_turn_user",
    requires_approval=True, identity=_prior_identity, user_text="צור משימה ישנה",
)

with patch.object(app, "resolve_identity", return_value=_prior_identity), \
     patch.object(app.client.messages, "create") as _mock_create:
    os.environ["FEATURE_PA01_ENFORCEMENT_STATE"] = "enforce"
    try:
        _confirm_reply = app.run_agent("מאשר", "prior_turn_user", channel="telegram")
    finally:
        os.environ.pop("FEATURE_PA01_ENFORCEMENT_STATE", None)

chk("a bare confirm word for a PRIOR turn's pending approval never reaches the Anthropic "
    "call at all (resolved by ActionGateway before the tool loop) -> PA-01 has zero effect",
    _mock_create.call_count == 0)
chk("...and the confirmation is answered by ActionGateway's own reply, never PA-01's fallbacks",
    bool(_confirm_reply) and _confirm_reply not in (PHANTOM, CAPABILITY))


# ══════════════════════════════════════════════════
# M. memory.add() receives only the text actually sent to the user
# ══════════════════════════════════════════════════

reply_mem, extra_mem = _run_agent(
    "memory_check", "צור לי משימה", role=Role.OWNER, intent=Intent.CREATE_TASK,
    allowed_tool_names=("airtable_add",),
    anthropic_response=_text_response("המשימה מוכנה להוספה, שלח מאשר"),
    pa01_state="enforce", capture_memory=True,
)
_assistant_memory_writes = [text for (role_, text) in extra_mem["memory_calls"] if role_ == "assistant"]
chk("memory.add('assistant', ...) receives the replaced Phantom fallback, never the "
    "original phantom-claim text",
    len(_assistant_memory_writes) == 1 and _assistant_memory_writes[0] == PHANTOM
    and reply_mem == PHANTOM)


# ══════════════════════════════════════════════════
# N. Policy source sanity — all 10 mappings point to real, requires_approval=True tools
# ══════════════════════════════════════════════════

from core.router.risk_router import _NORMAL_INTENTS  # noqa: E402

chk("_CONTRACT_REQUIRED_INTENT_TO_TOOL has exactly 10 entries",
    len(_CONTRACT_REQUIRED_INTENT_TO_TOOL) == 10)
chk("_CONTRACT_REQUIRED_INTENT_TO_TOOL is a subset of _NORMAL_INTENTS",
    set(_CONTRACT_REQUIRED_INTENT_TO_TOOL) <= _NORMAL_INTENTS)

_all_tools_valid = True
for _intent, _tool in _CONTRACT_REQUIRED_INTENT_TO_TOOL.items():
    _meta = tool_registry.get(_tool)
    if _meta is None or not _meta.requires_approval:
        _all_tools_valid = False
        print(f"   ⚠ {_intent} -> {_tool}: meta={_meta}")
chk("every mapped tool is a real tool_registry entry with requires_approval=True",
    _all_tools_valid)


# ══════════════════════════════════════════════════
# O. Flag default — off unless explicitly set
# ══════════════════════════════════════════════════

from feature_flags import get_pa01_enforcement_state  # noqa: E402

_had_env = "FEATURE_PA01_ENFORCEMENT_STATE" in os.environ
_saved_env = os.environ.pop("FEATURE_PA01_ENFORCEMENT_STATE", None)
chk("get_pa01_enforcement_state() defaults to 'off' when the env var is unset",
    get_pa01_enforcement_state() == "off")
if _had_env:
    os.environ["FEATURE_PA01_ENFORCEMENT_STATE"] = _saved_env


print(f"\n{'='*50}")
print(f"PA-01 phantom approval enforcement tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
