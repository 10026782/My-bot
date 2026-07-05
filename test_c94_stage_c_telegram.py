# test_c94_stage_c_telegram.py — C94 Stage ג: Telegram ingress adapter + router hardening
#
# Proves the three conditions required before Stage ג was approved:
#   1. A classify_ingress() exception (inside capture_router.classify_capture_ic())
#      no longer fails the WHOLE router to Handler.APPROVAL/intent=UNKNOWN via
#      app.py's _safe_route() blanket catch — it degrades to capture_ic=None,
#      the rest of routing (intent/domain/risk) proceeds unaffected.
#   2. intent/domain/risk continue to work correctly and independently — e.g.
#      a message that legitimately needs approval (SEND_EMAIL) still gets
#      Handler.APPROVAL for the RIGHT reason (risk gate, matched_rule from
#      intent_router) even when capture_ic fails, not coincidentally via the
#      router-level generic fallback.
#   3. app.py's _safe_route() blanket try/except is UNCHANGED for every OTHER
#      kind of router exception — this narrows fail-closed only at the one
#      capture_router.py call site, not the router's general safety net.
#
# Also covers: build_telegram_envelope() schema conformance, PII-safety of
# the sanitized classification_error (type(exc).__name__ only — never
# str(exc)/exc_info=True, same discipline as C94 Stage ב), and equivalence
# (identical RouteDecision whether or not an envelope_id is threaded through,
# for the normal/non-exception path).

import io
import logging
import os
import sys
from dataclasses import dataclass, field
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

from core.router.router import route_request
from core.router.route_decision import Intent, RouterDomain, Risk, Handler
from core.router import capture_router
from core.telegram_ingress_adapter import build_telegram_envelope
from core.ingress_envelope import IngressEnvelope, EvidenceTrace
from identity import Identity, Role

passed = failed = 0


def chk(desc: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}{(' — ' + extra) if extra else ''}")
        failed += 1


@dataclass
class MockIdentity:
    user_id:         str  = "test_user"
    role:            str  = "owner"
    tenant_id:       str  = "boss_hq"
    domain_id:       str  = "general"
    display_name:    str  = "Test"
    allowed_domains: list = field(default_factory=list)

    @property
    def is_internal(self) -> bool:
        return self.role in ("owner", "partner", "manager", "employee")

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"


OWNER = MockIdentity(role="owner")


class _ListLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


def _capture_logs(logger_name):
    handler = _ListLogHandler()
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    return logger, handler


# ══════════════════════════════════════════════════
# 1. build_telegram_envelope() — schema conformance
# ══════════════════════════════════════════════════
real_identity = Identity(user_id="owner_1", role=Role.OWNER, tenant_id="boss_hq", channel="telegram", external_id="111")
env = build_telegram_envelope(identity=real_identity, raw_event_id="upd_555", text="שלום")

chk("envelope source_channel == 'telegram'", env.source_channel == "telegram")
chk("envelope provider == 'telegram_bot_api' (via mapping, not hardcoded inline)", env.provider == "telegram_bot_api")
chk("envelope sender_identity == identity.memory_key", env.sender_identity == real_identity.memory_key)
chk("envelope source_ref references the raw_event_id", "upd_555" in env.source_ref)
chk("envelope has no raw_ref field", "raw_ref" not in IngressEnvelope.__dataclass_fields__)
try:
    env.validate()
    chk("build_telegram_envelope() output passes validate()", True)
except Exception as exc:
    chk("build_telegram_envelope() output passes validate()", False, str(exc))


# ══════════════════════════════════════════════════
# 2. capture_router.classify_capture_ic() — exception safety + PII discipline
# ══════════════════════════════════════════════════
PII_TEXT = "משה כהן 0501234567"


def _boom(*args, **kwargs):
    raise ValueError(f"boom — must never leak: {PII_TEXT}")


logger_cr, handler_cr = _capture_logs("core.router.capture_router")

with patch.object(capture_router, "classify_ingress", side_effect=_boom):
    result = capture_router.classify_capture_ic(PII_TEXT, chat_id="boss_hq:owner_1", envelope_id="env-x1")

chk("classify_capture_ic() returns None on classify_ingress() exception (no propagation)", result is None)
chk(
    "no raw exception text/PII leaks into the log",
    all(PII_TEXT not in msg and "boom" not in msg for msg in handler_cr.records),
    str(handler_cr.records),
)
chk(
    "log includes the sanitized error type name",
    any("ValueError" in msg for msg in handler_cr.records),
    str(handler_cr.records),
)
logger_cr.removeHandler(handler_cr)

# classify_capture() tuple API degrades the same way
with patch.object(capture_router, "classify_ingress", side_effect=_boom):
    tier, reason, raw_ref = capture_router.classify_capture(PII_TEXT, envelope_id="env-x2")
chk("classify_capture() returns (None, '', '') on failure, doesn't raise", (tier, reason, raw_ref) == (None, "", ""))

# Success path still records a Trace (envelope_id given) without altering the returned ic
with patch.object(capture_router, "EvidenceTrace") as _mock_trace_cls:
    _mock_trace = _mock_trace_cls.return_value
    ic = capture_router.classify_capture_ic("שלום מה נשמע", envelope_id="env-ok-1")
chk("classify_capture_ic() success path still returns a real IngressClassification", ic is not None and hasattr(ic, "tier"))
chk("EvidenceTrace constructed with the given envelope_id on success", _mock_trace_cls.call_args.kwargs.get("envelope_id") == "env-ok-1")
chk("record_classification() called with raw_ref on success", _mock_trace.record_classification.call_args.kwargs.get("raw_ref") == ic.raw_ref)


# ══════════════════════════════════════════════════
# 3. route_request() — condition 1: exception doesn't fail the WHOLE router
# ══════════════════════════════════════════════════
with patch.object(capture_router, "classify_ingress", side_effect=_boom):
    d = route_request("שלום", "telegram", OWNER, envelope_id="env-route-1")

chk("greeting still resolves to real intent (GREETING), not fail-closed UNKNOWN", d.intent == Intent.GREETING)
chk("greeting still resolves to Handler.AGENT, not the router-level fallback APPROVAL", d.handler == Handler.AGENT)
chk("matched_rule is NOT the generic router fallback", d.matched_rule != "fallback")
chk("capture_tier degrades to None (observability only) instead of crashing routing", d.capture_tier is None)


# ══════════════════════════════════════════════════
# 4. route_request() — condition 2: risk gate still fires for the RIGHT reason
# ══════════════════════════════════════════════════
with patch.object(capture_router, "classify_ingress", side_effect=_boom):
    d2 = route_request("שלח מייל לעורך הדין", "telegram", OWNER, envelope_id="env-route-2")

chk("SEND_EMAIL intent still correctly detected despite capture_ic failure", d2.intent == Intent.SEND_EMAIL)
chk("Handler.APPROVAL fires via the REAL risk gate, not the generic router fallback", d2.handler == Handler.APPROVAL)
chk("confidence is real (risk-gated), not the fallback's 0.0", d2.confidence > 0.0)
chk("matched_rule is NOT 'fallback'", d2.matched_rule != "fallback")


# ══════════════════════════════════════════════════
# 5. Equivalence — identical RouteDecision with/without envelope_id (normal path)
# ══════════════════════════════════════════════════
d_no_env = route_request("קבע פגישה עם הספק מחר", "whatsapp", MockIdentity(role="manager"), domain_from_channel="import")
d_with_env = route_request("קבע פגישה עם הספק מחר", "whatsapp", MockIdentity(role="manager"), domain_from_channel="import", envelope_id="env-equiv")

chk("route_request() output is identical with/without envelope_id (to_log())", d_no_env.to_log() == d_with_env.to_log())
chk(
    "capture_tier/reason identical with/without envelope_id",
    (d_no_env.capture_tier, d_no_env.capture_reason) == (d_with_env.capture_tier, d_with_env.capture_reason),
)
chk(
    "raw_ref is non-empty in both cases (raw_ref itself is a fresh id per call by design — C89 RAW-OBS, not expected to be equal)",
    bool(d_no_env.raw_ref) and bool(d_with_env.raw_ref),
)


# ══════════════════════════════════════════════════
# 6. app.py's _safe_route() — blanket catch UNCHANGED for OTHER exceptions
# ══════════════════════════════════════════════════
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-c94-stage-c-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:C94_STAGE_C_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patC94StageCTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appC94StageCTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

with patch("core.router.router.detect_intent", side_effect=RuntimeError("unrelated router failure")):
    fallback_route = app._safe_route("שלום", "telegram", OWNER)

chk("_safe_route() still falls back to intent=UNKNOWN for a non-capture router failure", fallback_route.intent == Intent.UNKNOWN)
chk("_safe_route() still falls back to Handler.APPROVAL (fail-closed) for a non-capture router failure", fallback_route.handler == Handler.APPROVAL)
chk("_safe_route() still marks matched_rule='fallback' for a non-capture router failure", fallback_route.matched_rule == "fallback")

# A classify_ingress()-only failure must NOT trigger this same fallback anymore.
with patch.object(capture_router, "classify_ingress", side_effect=_boom):
    non_fallback_route = app._safe_route("שלום", "telegram", OWNER, envelope_id="env-safe-route")
chk(
    "_safe_route() does NOT fall back to the generic fallback for a classify_ingress()-only failure",
    non_fallback_route.matched_rule != "fallback" and non_fallback_route.intent == Intent.GREETING,
)


# ══════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════
print(f"\n{passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
