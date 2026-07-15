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
# ══════════════════════════════════════════════════

_PAR349_TEXT = "✅ המשימה מוכנה להוספה... שלח מאשר"

reply_off, _ = _run_agent(
    "par349_off", "צור משימה לבדוק פר 349 עד ל-8 בערב",
    anthropic_response=_text_response(_PAR349_TEXT), pa01_state="off",
)
chk("פר 349 transcript, state=off -> today's behavior unchanged (phantom text reaches final_reply)",
    reply_off == _PAR349_TEXT)

reply_shadow, extra_shadow = _run_agent(
    "par349_shadow", "צור משימה לבדוק פר 349 עד ל-8 בערב",
    anthropic_response=_text_response(_PAR349_TEXT), pa01_state="shadow",
    capture_warnings=True,
)
chk("פר 349 transcript, state=shadow -> final_reply still equals the phantom text (unmodified)",
    reply_shadow == _PAR349_TEXT)
chk("state=shadow -> a would_block PA-01 WARNING line fires",
    any("[PA-01]" in w and "would_block" in w for w in extra_shadow["warning_calls"]))

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
    "terminal_outcome": "APPROVAL_QUEUE_ERROR",
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
    "terminal_outcome": None,
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
    "terminal_outcome": None,
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
