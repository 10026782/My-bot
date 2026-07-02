# test_integration.py — CORE_02.6 Integration Tests
#
# בודק את הזרימה המלאה: Identity → Router → Decision
# ללא Flask, ללא Anthropic, ללא DB.

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch
from core.router import route_request, Handler, Intent, RouterDomain, Risk


# ══════════════════════════════════════════════════
# Mock Identity
# ══════════════════════════════════════════════════

@dataclass
class MockIdentity:
    user_id:         str  = "test_user"
    role:            str  = "owner"
    tenant_id:       str  = "boss_hq"
    domain_id:       str  = "general"
    display_name:    str  = "Test"
    is_owner:        bool = False
    allowed_domains: list = field(default_factory=list)

    def __post_init__(self):
        self.is_owner = self.role == "owner"

    # Mirrors identity.Identity.is_internal — router.py's capture_router
    # step (SPEC 1) reads this directly, same as the real Identity class.
    @property
    def is_internal(self) -> bool:
        return self.role in ("owner", "partner", "manager", "employee")

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"


# ══════════════════════════════════════════════════
# _safe_route — מדמה את הפונקציה ב-app.py
# ══════════════════════════════════════════════════

def _safe_route(text, channel, identity, domain_from_channel=""):
    """עותק של _safe_route מ-app.py לצורך בדיקה."""
    try:
        return route_request(
            text                = text,
            channel_raw         = channel,
            identity            = identity,
            domain_from_channel = domain_from_channel,
        )
    except Exception as e:
        from core.router.route_decision import RouteDecision, Intent, RouterDomain, Risk, Handler
        return RouteDecision(
            channel="unknown", intent=Intent.UNKNOWN,
            domain=RouterDomain.GENERAL, risk=Risk.NORMAL,
            handler=Handler.AGENT, matched_rule="fallback",
        )


# ══════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════

def test_01_whatsapp_domain_routing():
    identity = MockIdentity(role="owner")
    route = _safe_route(
        text                = "פתח משימה לבדוק את המכולה",
        channel             = "whatsapp",
        identity            = identity,
        domain_from_channel = "import",
    )

    assert route.domain  == RouterDomain.IMPORT,    f"domain={route.domain}"
    assert route.intent  == Intent.CREATE_TASK,     f"intent={route.intent}"
    assert route.handler == Handler.AGENT,          f"handler={route.handler}"
    assert route.risk    == Risk.NORMAL,            f"risk={route.risk}"
    return "✅ Test 01: WhatsApp domain routing"


def test_02_lead_restricted():
    """lead מנסה לשלוח מייל → restricted flow: agent מדבר, tools חסומים."""
    identity = MockIdentity(role="lead")
    route = _safe_route(
        text    = "שלח מייל לעורך הדין",
        channel = "whatsapp",
        identity = identity,
    )

    assert route.handler      == Handler.AGENT, f"handler={route.handler} (expected agent)"
    assert route.restricted   == True,          "restricted must be True"
    assert route.tool_allowed == False,         "tool_allowed must be False"
    assert route.notify_owner == True,          "notify_owner must be True"
    return "✅ Test 02: Lead restricted — agent talks, tools blocked"


def test_03_router_fallback():
    identity = MockIdentity(role="owner")

    with patch("core.router.router.detect_intent", side_effect=RuntimeError("simulated failure")):
        route = _safe_route(
            text     = "כלשהו",
            channel  = "telegram",
            identity = identity,
        )

    assert route.handler      == Handler.AGENT,    f"handler={route.handler}"
    assert route.intent       == Intent.UNKNOWN,   f"intent={route.intent}"
    assert route.matched_rule == "fallback",       f"rule={route.matched_rule}"
    return "✅ Test 03: Router fallback — no crash"


def test_04_restricted_flow():
    """lead מנסה לשלוח מייל → handler=agent, restricted=True, tool_allowed=False."""
    identity = MockIdentity(role="lead")
    route = _safe_route("שלח מייל לחברה", "whatsapp", identity)

    assert route.handler      == Handler.AGENT, f"handler={route.handler}"
    assert route.restricted   == True,          "restricted must be True"
    assert route.tool_allowed == False,         "tool_allowed must be False"
    assert route.notify_owner == True,          "notify_owner must be True"
    return "✅ Test 04: Restricted flow — agent talks, tools blocked"


# ══════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════

def run():
    tests = [
        test_01_whatsapp_domain_routing,
        test_02_lead_restricted,
        test_03_router_fallback,
        test_04_restricted_flow,
    ]
    passed = failed = 0

    print("\nCORE_02.6 Integration Tests")
    print("═" * 40)

    for t in tests:
        try:
            msg = t()
            print(msg)
            passed += 1
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {t.__name__} EXCEPTION: {e}")
            failed += 1

    print(f"\n{'═' * 40}")
    print(f"  {passed}/{passed+failed} passed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
