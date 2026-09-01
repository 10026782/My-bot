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
chk("certain structured request parses name+domain", _certain.certain
    and _certain.name == "רכישת ציוד" and _certain.domain == "יבוא")

_reversed = parse_deterministic_create_deal("פתח עסקה בתחום יבוא בשם רכישת ציוד")
chk("reversed field order also parses (name/domain order-independent)",
    _reversed.certain and _reversed.name == "רכישת ציוד" and _reversed.domain == "יבוא")

_self_owner = parse_deterministic_create_deal("צור עסקה בשם X בתחום יבוא בבעלותי")
chk("trailing self-ownership marker (בבעלותי) does not break the parse",
    _self_owner.certain and _self_owner.name == "X" and _self_owner.domain == "יבוא")

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
chk("loose phrasing -> Handler.AGENT (deliberately narrow gate, same as CREATE_TASK's)",
    route_loose.handler == Handler.AGENT)

route_lead = route_request("צור עסקה בשם רכישת ציוד בתחום יבוא", "telegram", _lead())
chk("lead role never gets Handler.TOOL even for a certain structured request",
    route_lead.handler == Handler.AGENT)


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

chk("a real user_message came back (no crash, no silent no-op)", bool(reply))
chk("Single Speaker: source_module=action_gateway", metadata.get("source_module") == "action_gateway")

contracts = action_gateway.find_live_contracts(_owner_e2e.memory_key)
deal_contracts = [
    item for item in contracts
    if item.tool_name == "crm_create_deal"
    and item.normalized_payload.get("name") == "רכישת ציוד תעשייתי"
    and item.normalized_payload.get("domain") == "יבוא"
]
chk("exactly one pending crm_create_deal contract was created — the "
    "dedicated canonical tool, never generic airtable_add",
    len(deal_contracts) == 1 and deal_contracts[0].status == "pending")
chk("no owner_id was fabricated into the fingerprint (dispatcher resolves "
    "it from identity at execution time, not the router)",
    "owner_id" not in deal_contracts[0].normalized_payload)


print()
print("=" * 50)
print("BUG-CRM-BYPASS create_deal deterministic route tests: PASS")
