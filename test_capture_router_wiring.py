# test_capture_router_wiring.py — SPEC 1 (Capture Policy, Router-Integrated)
#
# Verifies the discovery-corrected wiring:
#   - core/router/capture_router.py classifies without reimplementing tier
#     logic or importing airtable/drive/gateway.
#   - RouteDecision.capture_tier is populated for identity.is_internal
#     senders regardless of intent_router's own intent/confidence (the
#     original SPEC text gated on "intent in {...} and confidence<0.75",
#     which would silently disagree with what core.lead_candidate_handler
#     independently decides for high-confidence CREATE_LEAD/TASK/EVENT text
#     — fixed here by gating on identity.is_internal alone, matching LCH's
#     real invocation condition exactly).
#   - app.py's step "1.45" pre-Router bypass is gone; the new call site is
#     gated on identity.is_internal (NOT on route.capture_tier — a
#     capture_tier gate would silently break _handle_batch_followup, which
#     runs unconditionally inside handle_lead_candidate() before any tier
#     classification and doesn't itself produce a write-worthy tier).
#   - handle_lead_candidate()'s new `domain` param is backward compatible
#     (empty default -> old _detect_domain() fallback) and, when passed,
#     overrides the internal regex guess (BUG-NEW-13-style fix for LCH).

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dataclasses import dataclass, field
from unittest.mock import patch

from core.router.router import route_request
from core.router.route_decision import Intent, RouterDomain, Handler
from core.router.capture_router import classify_capture
import core.lead_candidate_handler as lch


@dataclass
class MockIdentity:
    user_id:         str = "test_user"
    role:            str = "owner"
    tenant_id:       str = "boss_hq"
    domain_id:       str = "general"
    display_name:    str = "Test"
    allowed_domains: list = field(default_factory=list)

    @property
    def is_internal(self) -> bool:
        return self.role in ("owner", "partner", "manager", "employee")

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"


LEAD_TEXT_LOW_CONF_INTENT   = "משה כהן 0501234567 לחזור מחר"          # no CREATE_LEAD keyword -> intent UNKNOWN
LEAD_TEXT_HIGH_CONF_INTENT  = "תוסיף ליד: משה כהן 0501234567"          # matches CREATE_LEAD keyword rule, high confidence
TIER4_TEXT                  = "| שם | טלפון |\n| א | 050 |\n| ב | 052 |"  # table -> tier 4
FOLLOWUP_TEXT                = "מה קרה עם השאר?"                       # no name/phone -> tier 5, matches follow-up words


def test_classify_capture_direct():
    tier, reason, raw_ref = classify_capture(LEAD_TEXT_LOW_CONF_INTENT)
    assert tier == 1, f"expected tier 1, got {tier} ({reason})"

    tier4, reason4, _ = classify_capture(TIER4_TEXT)
    assert tier4 is None, f"tier 4 must collapse to None, got {tier4} ({reason4})"

    tier5, reason5, _ = classify_capture("שלום מה נשמע")
    assert tier5 is None, f"tier 5 must collapse to None, got {tier5} ({reason5})"
    return "OK"


def test_router_capture_tier_low_confidence_intent():
    identity = MockIdentity(role="owner")
    d = route_request(LEAD_TEXT_LOW_CONF_INTENT, "telegram", identity)
    assert d.intent == Intent.UNKNOWN, f"intent={d.intent}"
    assert d.capture_tier == 1, f"capture_tier={d.capture_tier}"
    return "OK"


def test_router_capture_tier_high_confidence_intent_still_fires():
    """
    Regression guard: the original SPEC text gated capture_router on
    "intent in {...} and confidence < 0.75" — for this exact text,
    intent_router matches CREATE_LEAD at 0.95 confidence, which would make
    that condition False and leave capture_tier=None even though LCH (gated
    only on identity.is_internal, unconditionally) still independently
    auto-writes it as tier 1. RouteDecision would then silently disagree
    with reality. Fixed by dropping the confidence/intent gate.
    """
    identity = MockIdentity(role="owner")
    d = route_request(LEAD_TEXT_HIGH_CONF_INTENT, "telegram", identity)
    assert d.intent == Intent.CREATE_LEAD, f"intent={d.intent} (test text must hit the high-confidence rule)"
    assert d.confidence >= 0.75, f"confidence={d.confidence} (test text must be high-confidence)"
    assert d.capture_tier == 1, f"capture_tier={d.capture_tier} — must still fire despite high-confidence intent"
    return "OK"


def test_router_capture_tier_gated_on_is_internal():
    identity = MockIdentity(role="lead")  # external — is_internal=False
    d = route_request(LEAD_TEXT_LOW_CONF_INTENT, "whatsapp", identity)
    assert d.capture_tier is None, f"capture_tier={d.capture_tier} (external sender must never get a tier)"
    return "OK"


def test_router_capture_tier_none_for_tier4():
    identity = MockIdentity(role="owner")
    d = route_request(TIER4_TEXT, "telegram", identity)
    assert d.capture_tier is None, f"capture_tier={d.capture_tier} (tier 4 must collapse to None)"
    return "OK"


def test_app_py_bypass_removed_and_gate_is_is_internal():
    """Static check: no pre-Router LCH call remains, and the new call site
    gates on identity.is_internal — not on route.capture_tier (which would
    silently break _handle_batch_followup, see module docstring)."""
    src = open(os.path.join(os.path.dirname(__file__), "app.py"), encoding="utf-8").read()

    assert '# ── 1.45.' not in src, "old pre-Router step-1.45 section header still present"

    router_call_idx = src.index("route = _safe_route(")
    lch_call_idx    = src.index("from core.lead_candidate_handler import handle_lead_candidate")
    assert lch_call_idx > router_call_idx, "LCH call must come after the Router call now"

    # the actual `if` line gating the (post-Router) LCH call must test
    # identity.is_internal, not route.capture_tier
    gate_line = next(
        line for line in reversed(src[:lch_call_idx].splitlines())
        if line.strip().startswith("if ")
    )
    assert 'getattr(identity, "is_internal", False)' in gate_line, \
        f"post-Router LCH call must gate on identity.is_internal, got: {gate_line!r}"
    assert "capture_tier" not in gate_line, \
        f"post-Router LCH call must NOT gate on route.capture_tier, got: {gate_line!r}"
    return "OK"


def test_capture_router_no_infra_imports():
    src = open(
        os.path.join(os.path.dirname(__file__), "core", "router", "capture_router.py"),
        encoding="utf-8",
    ).read()
    import_lines = [
        line.strip() for line in src.splitlines()
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    ]
    for banned in ("airtable", "drive", "action_gateway", "httpx", "tools."):
        hits = [line for line in import_lines if banned in line]
        assert not hits, f"capture_router.py must not import {banned!r}: {hits}"
    assert "classify_ingress" in src, "must reuse classify_ingress(), not reimplement tier logic"
    return "OK"


def test_handle_lead_candidate_domain_backward_compatible():
    """No domain passed -> falls back to the original _detect_domain() guess."""
    identity = MockIdentity(role="owner", domain_id="general")
    captured = {}

    def _fake_single(identity, c, text, chat_id, channel, domain, auto_write, intent=""):
        captured["domain"] = domain
        return "✅ mocked write"

    with patch.object(lch, "_handle_single_candidate", _fake_single):
        reply = lch.handle_lead_candidate(identity, "משה כהן 0501234567", "chat1", "telegram")

    assert reply == "✅ mocked write"
    assert captured["domain"] == "general", f"domain={captured.get('domain')} (expected regex-guess fallback)"
    return "OK"


def test_handle_lead_candidate_domain_from_router_overrides_guess():
    """domain= passed explicitly (as app.py now does with resolved_route_domain)
    must win over the internal _detect_domain() regex guess."""
    identity = MockIdentity(role="owner", domain_id="general")
    captured = {}

    def _fake_single(identity, c, text, chat_id, channel, domain, auto_write, intent=""):
        captured["domain"] = domain
        return "✅ mocked write"

    with patch.object(lch, "_handle_single_candidate", _fake_single):
        reply = lch.handle_lead_candidate(
            identity, "משה כהן 0501234567", "chat1", "telegram", domain="real_estate",
        )

    assert reply == "✅ mocked write"
    assert captured["domain"] == "real_estate", f"domain={captured.get('domain')} (Router domain must win)"
    return "OK"


def test_batch_followup_still_reachable_without_a_tier():
    """
    The bug this guards against: gating the post-Router LCH call on
    route.capture_tier (instead of identity.is_internal) would make
    handle_lead_candidate() unreachable for follow-up replies like "מה קרה
    עם השאר?" — they classify as tier 5 (no phone/name), so capture_tier
    would be None, and _handle_batch_followup() (which runs unconditionally
    inside handle_lead_candidate(), independent of tier) would never get a
    chance to run.
    """
    identity = MockIdentity(role="owner")

    fake_session = {
        "last_lead_candidate_batch": {
            "per_lead": [
                {"name": "משה כהן", "phone": "0501234567", "ok": True, "record_id": "rec123"},
            ]
        }
    }

    class _FakeLeadSessions:
        def get(self, chat_id):
            return fake_session

    with patch("session_store.lead_sessions", _FakeLeadSessions()):
        reply = lch.handle_lead_candidate(identity, FOLLOWUP_TEXT, "chat1", "telegram")

    assert reply is not None, "batch follow-up must still be reachable (tier-gating would have broken this)"
    assert "משה כהן" in reply, f"reply={reply!r}"
    return "OK"


TESTS = [
    test_classify_capture_direct,
    test_router_capture_tier_low_confidence_intent,
    test_router_capture_tier_high_confidence_intent_still_fires,
    test_router_capture_tier_gated_on_is_internal,
    test_router_capture_tier_none_for_tier4,
    test_app_py_bypass_removed_and_gate_is_is_internal,
    test_capture_router_no_infra_imports,
    test_handle_lead_candidate_domain_backward_compatible,
    test_handle_lead_candidate_domain_from_router_overrides_guess,
    test_batch_followup_still_reachable_without_a_tier,
]


def run():
    passed = failed = 0
    for t in TESTS:
        try:
            t()
            print(f"✅ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {t.__name__} EXCEPTION: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} passed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
