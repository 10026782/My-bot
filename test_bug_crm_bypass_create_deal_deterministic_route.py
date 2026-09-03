"""בדיקות רגרסיה — Turn Coordinator ownership of structured Deal creation.

BUG-CRM-BYPASS follow-up (01/09/2026): Deal creation had no Intent at all —
it always fell to Handler.AGENT, meaning the LLM always chose between
crm_create_deal and the generic airtable_add. PR #1165/#1166/#1169 each
patched a different gap in the generic-write interception layer that exists
to catch whatever the agent chose; none of them kept the agent out of the
decision, which is the actual architecture decision for mutation intents
(Turn Coordinator / Single Speaker — see CREATE_TASK's own deterministic
route, core/router/router.py's parse_deterministic_create_task).

This mirrors that exact pattern for Intent.CREATE_DEAL: a structured
"<verb> עסקה בשם X בתחום Y" request is queued directly against the
canonical crm_create_deal tool — the Agent tool_use loop is never entered
for that turn (verified below by making a real LLM call raise).
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-create-deal-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:create-deal-test")
os.environ.setdefault("AIRTABLE_API_KEY", "patCreateDealTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCreateDealTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
from core.action_gateway import action_gateway  # noqa: E402
from core.router import Handler, Intent, route_request  # noqa: E402
from core.router.router import parse_deterministic_create_deal  # noqa: E402
from identity import Identity, Role  # noqa: E402


def _owner(user_id: str = "owner-deterministic-create-deal") -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id=user_id,
    )


def _lead(user_id: str = "lead-deterministic-create-deal") -> Identity:
    return Identity(
        user_id=user_id, role=Role.LEAD, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id=user_id,
    )


def chk(desc: str, cond: bool) -> None:
    assert cond, desc
    print(f"✅ {desc}")


# ══════════════════════════════════════════════════════════════════
print("── parser: certain/uncertain/no-match shape ──")

_certain = parse_deterministic_create_deal("צור עסקה בשם רכישת ציוד בתחום יבוא")
chk("certain structured request parses name+canonicalized domain "
    "(BUG-CRM-BYPASS-DOMAIN-TRANSLATION: 'יבוא' -> 'import', never the raw word)",
    _certain.certain and _certain.name == "רכישת ציוד" and _certain.domain == "import")

_reversed = parse_deterministic_create_deal("פתח עסקה בתחום יבוא בשם רכישת ציוד")
chk("reversed field order also parses (name/domain order-independent)",
    _reversed.certain and _reversed.name == "רכישת ציוד" and _reversed.domain == "import")

_self_owner = parse_deterministic_create_deal("צור עסקה בשם X בתחום יבוא בבעלותי")
chk("trailing self-ownership marker (בבעלותי) does not break the parse",
    _self_owner.certain and _self_owner.name == "X" and _self_owner.domain == "import")

_english_slug = parse_deterministic_create_deal("צור עסקה בשם X בתחום import")
chk("typing the canonical English slug directly also resolves (identity mapping)",
    _english_slug.certain and _english_slug.domain == "import")

_unrecognized_domain = parse_deterministic_create_deal("צור עסקה בשם X בתחום שטויות")
chk("an unrecognized domain word -> uncertain (CLARIFY), never guessed/written raw",
    _unrecognized_domain.matched and _unrecognized_domain.uncertain
    and _unrecognized_domain.domain is None)

_named_owner = parse_deterministic_create_deal("צור עסקה בשם X בתחום יבוא בבעלות אורי")
chk("explicit named owner -> uncertain, NEVER a corrupted domain field "
    "(regression: this used to silently absorb 'בבעלות אורי' into domain)",
    _named_owner.matched and _named_owner.uncertain
    and _named_owner.name is None and _named_owner.domain is None)

_missing_domain = parse_deterministic_create_deal("צור עסקה בתחום יבוא")
chk("missing 'בשם' clause -> no structural match at all (falls through to normal routing)",
    not _missing_domain.matched and not _missing_domain.certain)

_loose = parse_deterministic_create_deal("צריך לפתוח עסקה חדשה איתו")
chk("loose/unstructured phrasing -> no match", not _loose.matched)


# ══════════════════════════════════════════════════════════════════
print("\n── router: CREATE_DEAL deterministic gate ──")

owner = _owner()
route_certain = route_request("צור עסקה בשם רכישת ציוד בתחום יבוא", "telegram", owner)
chk("certain structured request -> Handler.TOOL", route_certain.handler == Handler.TOOL)
chk("certain structured request -> Intent.CREATE_DEAL", route_certain.intent == Intent.CREATE_DEAL)
chk("certain structured request -> needs_approval=True", route_certain.needs_approval is True)

route_uncertain = route_request("צור עסקה בשם X בתחום יבוא בבעלות אורי", "telegram", owner)
chk("named-owner request -> Handler.CLARIFY (never a bare Handler.AGENT tool menu)",
    route_uncertain.handler == Handler.CLARIFY)
chk("Handler.CLARIFY -> tool_allowed=False", route_uncertain.tool_allowed is False)

route_loose = route_request(
    "צור לי עסקה חדשה בתחום יבוא, אני אשלים פרטים אחר כך", "telegram", owner,
)
# BUG-CRM-BYPASS-DEAL-AGENT-FALLTHROUGH (live production, 02/09/2026): this
# used to assert Handler.AGENT here ("deliberately narrow gate, same as
# CREATE_TASK's") — but unlike Task, Deal creation has a standing
# architecture decision that the Agent is NEVER given a tool choice for
# this intent. Falling through to Handler.AGENT let the agent pick the
# generic airtable_add bypass tool (no owner-resolution fallback there),
# reproducing the exact BUG-CRM-BYPASS-OWNER-PRESENCE failure class this
# session already fixed for the deterministic route. Now: any intent=
# create_deal message that isn't .certain -- matched or not -- CLARIFIES.
chk("loose/unmatched phrasing -> Handler.CLARIFY, never a bare Agent tool menu "
    "(regression: this used to reach Handler.AGENT, which could pick the "
    "generic airtable_add bypass and fail on missing owner_id)",
    route_loose.handler == Handler.CLARIFY)
chk("Handler.CLARIFY for unmatched phrasing -> tool_allowed=False",
    route_loose.tool_allowed is False)

route_lead = route_request("צור עסקה בשם רכישת ציוד בתחום יבוא", "telegram", _lead())
chk("lead role never gets Handler.TOOL even for a certain structured request",
    route_lead.handler == Handler.AGENT)


# ══════════════════════════════════════════════════════════════════
print("\n── regression: exact live production canary inputs (02/09/2026) ──")

# Canary #6: "צור עסקה בשם בדיקת-קנרית 6 בתחום יבוא" -- approved, then failed
# execution with "provider returned HTTP 422" because the deterministic
# route sent the raw Hebrew word "יבוא" as the Domain value, which
# Airtable's single-select rejected outright (BUG-CRM-BYPASS-DOMAIN-
# TRANSLATION).
_canary_6 = parse_deterministic_create_deal("צור עסקה בשם בדיקת-קנרית 6 בתחום יבוא")
chk("canary #6 exact text now resolves domain to the canonical slug",
    _canary_6.certain and _canary_6.name == "בדיקת-קנרית 6" and _canary_6.domain == "import")

# Canary #7: "צור עסקה בשם בדיקת-קנרית 7 domain import" -- the English
# "domain" keyword (instead of "בתחום") never matched the structured regex
# at all, so this fell through to Handler.AGENT, which picked the generic
# airtable_add bypass tool and failed with "owner_id חסר" -- the exact
# BUG-CRM-BYPASS-OWNER-PRESENCE failure class, reopened via the one path
# that was never deterministically routed (BUG-CRM-BYPASS-DEAL-AGENT-
# FALLTHROUGH).
_canary_7_parse = parse_deterministic_create_deal("צור עסקה בשם בדיקת-קנרית 7 domain import")
chk("canary #7 exact text does not match the structured template at all",
    not _canary_7_parse.matched)
route_canary_7 = route_request("צור עסקה בשם בדיקת-קנרית 7 domain import", "telegram", owner)
chk("canary #7 now CLARIFIES instead of reaching Handler.AGENT",
    route_canary_7.handler == Handler.CLARIFY)


# ══════════════════════════════════════════════════════════════════
print("\n── app._queue_deterministic_create_deal: role gate before queuing ──")

from tool_registry import ToolDenied  # noqa: E402

with patch.object(app, "_queue_approval_detailed") as mock_queue:
    reply = app._queue_deterministic_create_deal(
        "X", "יבוא", _lead().user_id, "telegram", "צור עסקה בשם X בתחום יבוא", _lead(),
    )
chk("employee/lead denied before any ActionGateway proposal is attempted",
    mock_queue.call_count == 0 and isinstance(reply, str) and reply)


# ══════════════════════════════════════════════════════════════════
print("\n── end-to-end: structured Deal creation never calls the Agent ──")

metadata: dict = {}
_owner_e2e = _owner(user_id="owner-deterministic-create-deal-e2e")
text = "צור עסקה בשם רכישת ציוד תעשייתי בתחום יבוא"

with patch.object(app, "resolve_identity", return_value=_owner_e2e), \
     patch.object(app.rate_limiter, "is_allowed", return_value=True), \
     patch.object(
         app.client.messages, "create",
         side_effect=AssertionError("structured create-deal must not call the Agent"),
     ), \
     patch(
         "feature_flags.is_enabled",
         side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY",
     ):
    reply = app.run_agent(text, _owner_e2e.user_id, "telegram", _out_meta=metadata)
    # S2C completion is intentionally multi-turn. Complete the contract-owned
    # fields so this legacy bypass regression can continue to inspect the
    # canonical crm_create_deal ActionContract.
    for answer in ("recCONTACTCANARY0001", "service", "one_off", "ILS", "prospect", "100"):
        reply = app.run_agent(answer, _owner_e2e.user_id, "telegram", _out_meta=metadata)

chk("a real user_message came back (no crash, no silent no-op)", bool(reply))
chk("Single Speaker: source_module=action_gateway", metadata.get("source_module") == "action_gateway")

contracts = action_gateway.find_live_contracts(_owner_e2e.memory_key)
deal_contracts = [
    item for item in contracts
    if item.tool_name == "crm_create_deal"
    and item.normalized_payload.get("name") == "רכישת ציוד תעשייתי"
    and item.normalized_payload.get("domain") == "import"
]
chk("exactly one pending crm_create_deal contract was created — the "
    "dedicated canonical tool, never generic airtable_add",
    len(deal_contracts) == 1 and deal_contracts[0].status == "pending")
chk("owner_id in the dispatched payload is the caller's own raw identity "
    "self-reference (never a fabricated/guessed record id) — dispatcher's "
    "own _resolve_authenticated_crm_owner() turns this into a real Profile "
    "record ID at execution time",
    deal_contracts[0].normalized_payload.get("owner_id") == _owner_e2e.user_id)

# BUG-CRM-BYPASS-FINGERPRINT-PARITY (live production regression,
# 01-02/09/2026): the assertion this replaces only checked that
# fingerprint_payload's shape excluded owner_id — it never checked that
# shape against what actually gets recomputed at execution time, which is
# exactly the gap that let a real, divergent fingerprint_payload ship and
# break every approved contract with "approval-sensitive execution proof
# does not match the action payload." This is the real, unmocked
# round-trip check: build execution_context from the REAL contract
# _queue_deterministic_create_deal() (via run_agent() above) just
# proposed, and confirm the REAL _validate_execution_proof() accepts its
# own real payload. If app.py ever again passes a fingerprint_payload that
# structurally diverges from the real dispatched inputs, this fails.
from tools.dispatcher import _validate_execution_proof as _real_validate_execution_proof  # noqa: E402

_real_execution_context = {
    "contract_id": deal_contracts[0].contract_id,
    "approved_by": _owner_e2e.memory_key,
    "tool_name": deal_contracts[0].tool_name,
    "tenant_id": deal_contracts[0].tenant_id,
    "canonical_user_id": deal_contracts[0].canonical_user_id,
    "business_action_fingerprint": deal_contracts[0].business_action_fingerprint,
    "status": "approved",
}
_real_proof_error = _real_validate_execution_proof(
    "crm_create_deal", deal_contracts[0].normalized_payload, _owner_e2e,
    _real_execution_context, "deterministic_create_deal",
)
chk("REAL execution-proof check on the REAL contract from the deterministic "
    "route: the stored fingerprint matches what gets recomputed from the "
    "real dispatched payload (no divergent fingerprint_payload)",
    _real_proof_error is None)


# ══════════════════════════════════════════════════════════════════
print("\n── regression: full execution path (BUG-CRM-BYPASS-OWNER-PRESENCE) ──")
# 01/09/2026 live production incident: the deterministic route above
# proposed and got approved correctly, but execution failed with
# "מי הבעלים? (מזהה record)" — action_validator.py's presence gate
# (_REQUIRED_PARAMS["crm_create_deal"] includes "owner_id") runs BEFORE
# tools/dispatcher.py's per-tool owner-resolution logic and blocks any
# call missing the literal key, regardless of whether the dispatcher could
# have filled it in. The two tests above only proved the contract gets
# proposed — neither exercised execution, which is exactly where this
# broke. This exercises the real action_validator + dispatcher +
# owner-resolution chain together (only the Airtable network call itself
# is mocked).

from tools import dispatcher as _dispatcher_module  # noqa: E402
from tools.dispatcher import dispatch_tool as _dispatch_tool  # noqa: E402


def _dispatch_bypassing_proof(name, inputs, identity):
    with patch.object(_dispatcher_module, "_validate_execution_proof", return_value=None), \
         patch.object(_dispatcher_module._ff, "is_enabled", return_value=False), \
         patch.object(_dispatcher_module._owner_resolution, "resolve_profile_record_id",
                       return_value="recPROFILE0000001"):
        return _dispatch_tool(name, inputs, identity=identity, trusted_source="agent",
                               execution_context={"contract_id": "regression-owner-presence"})


_deal_owner = _owner(user_id="owner-deterministic-create-deal-exec")
_ok_deal_result = {
    "ok": True, "tool": "crm_create_deal", "external_id": "recDEALCANARY0001",
    "evidence": {"record_id": "recDEALCANARY0001"}, "user_message": "✅ עסקה נוצרה",
}

with patch("commercial_crm.create_deal", return_value=_ok_deal_result) as mock_create_deal:
    result = _dispatch_bypassing_proof(
        "crm_create_deal",
        {"name": "בדיקת-קנרית", "domain": "יבוא", "owner_id": _deal_owner.user_id},
        _deal_owner,
    )
chk("the exact payload _queue_deterministic_create_deal builds is NOT "
    "blocked by action_validator's presence gate (the live production bug)",
    result.get("ok") is True)
chk("commercial_crm.create_deal was actually reached and called once",
    mock_create_deal.call_count == 1)

with patch("commercial_crm.create_deal", return_value=_ok_deal_result) as mock_create_deal_missing:
    blocked_result = _dispatch_bypassing_proof(
        "crm_create_deal",
        {"name": "בדיקת-קנרית", "domain": "יבוא"},  # the OLD (broken) payload shape
        _deal_owner,
    )
chk("the OLD payload shape (no owner_id at all) genuinely reproduces the "
    "live failure — proves this regression test would have caught it "
    "before merge",
    blocked_result.get("ok") is False
    and "מי הבעלים" in blocked_result.get("user_message", ""))
chk("the writer is never reached when action_validator blocks first",
    mock_create_deal_missing.call_count == 0)


# ══════════════════════════════════════════════════════════════════
print("\n── UX: pending-approval message names the Deal, not a generic fallback ──")
# Live observation (02/09/2026): the owner's pending-approval message for a
# crm_create_deal contract read "יש פעולה שממתינה לאישור: הפעולה המבוקשת" —
# a useless generic fallback, because _safe_contract_business_description()
# only knew about the {"table":...,"fields":{...}} payload shape
# (airtable_add/update) and Task's own special-cased title, never
# crm_create_deal's flat {"name":..., "domain":...} kwargs shape.

from core.action_gateway import (  # noqa: E402
    ActionContract, build_approval_lifecycle_result,
)


def _fake_deal_contract(name: str) -> ActionContract:
    return ActionContract(
        contract_id="fake-contract-desc-test", tenant_id="boss_hq",
        canonical_user_id="boss_hq:eliyahu", tool_name="crm_create_deal",
        normalized_payload={"name": name, "domain": "יבוא", "owner_id": "eliyahu"},
        business_action_fingerprint="fake", origin_channel="telegram",
        origin_chat_id="eliyahu", requires_approval=True, status="pending",
        created_at=0.0,
    )


_lifecycle = build_approval_lifecycle_result(_fake_deal_contract("בדיקת-קנרית 5"))
chk("pending crm_create_deal contract names the Deal in the approval message",
    "בדיקת-קנרית 5" in _lifecycle.safe_user_message
    and "הפעולה המבוקשת" not in _lifecycle.safe_user_message)


print()
print("=" * 50)
print("BUG-CRM-BYPASS create_deal deterministic route tests: PASS")
