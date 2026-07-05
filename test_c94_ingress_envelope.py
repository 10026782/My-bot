# test_c94_ingress_envelope.py — C94 Stage א: IngressEnvelope + EvidenceTrace schemas
#
# Proves:
#   1. IngressEnvelope.validate() accepts a fully-populated envelope for every
#      known logical channel, and rejects each of the 7 required fields when
#      missing/empty.
#   2. source_channel/provider are never interchangeable — a provider name in
#      source_channel is rejected with a distinct error (BUG-071 pattern).
#   3. EvidenceTrace.validate() accepts a fully-empty trace and a partial
#      trace (e.g. Tier 3/4 — classified, no approval needed, no write) as
#      valid states, and rejects only the ordering violation (a later-stage
#      field set without the classification that must precede it).

from core.ingress_envelope import (
    IngressEnvelope,
    EvidenceTrace,
    EnvelopeValidationError,
    TraceValidationError,
)

passed = failed = 0


def chk(desc: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}{(' — ' + extra) if extra else ''}")
        failed += 1


def _envelope(**overrides) -> IngressEnvelope:
    base = dict(
        source_channel="telegram",
        provider="telegram_bot_api",
        raw_event_id="upd_123",
        sender_identity="boss_hq:eliyahu",
        normalized_text="שלום",
        attachments=(),
        raw_ref="local:abc123",
    )
    base.update(overrides)
    return IngressEnvelope(**base)


# ══════════════════════════════════════════════════
# 1. Valid envelope per known channel — must validate cleanly
# ══════════════════════════════════════════════════
_CHANNEL_PROVIDER = {
    "telegram":    "telegram_bot_api",
    "whatsapp":    "twilio_whatsapp",
    "file_upload": "telegram_bot_api",
    "voice":       "twilio_whatsapp",
    "text":        "telegram_bot_api",
}
for channel, provider in _CHANNEL_PROVIDER.items():
    env = _envelope(source_channel=channel, provider=provider)
    try:
        env.validate()
        chk(f"valid envelope validates cleanly: source_channel={channel}", True)
    except EnvelopeValidationError as exc:
        chk(f"valid envelope validates cleanly: source_channel={channel}", False, str(exc))

# ══════════════════════════════════════════════════
# 2. Each of the 7 required fields, missing/empty → EnvelopeValidationError
# ══════════════════════════════════════════════════
_REQUIRED_STRING_FIELDS = [
    "source_channel", "provider", "raw_event_id",
    "sender_identity", "normalized_text", "raw_ref",
]
for f in _REQUIRED_STRING_FIELDS:
    env = _envelope(**{f: ""})
    try:
        env.validate()
        chk(f"empty {f} is rejected", False, "no exception raised")
    except EnvelopeValidationError:
        chk(f"empty {f} is rejected", True)

env_none_attachments = _envelope(attachments=None)
try:
    env_none_attachments.validate()
    chk("attachments=None is rejected", False, "no exception raised")
except EnvelopeValidationError:
    chk("attachments=None is rejected", True)

env_empty_attachments = _envelope(attachments=())
try:
    env_empty_attachments.validate()
    chk("attachments=() (no media) is a valid state, not a failure", True)
except EnvelopeValidationError as exc:
    chk("attachments=() (no media) is a valid state, not a failure", False, str(exc))

# ══════════════════════════════════════════════════
# 3. source_channel/provider must never be interchangeable (BUG-071 pattern)
# ══════════════════════════════════════════════════
env_leak = _envelope(source_channel="twilio", provider="twilio_whatsapp")
try:
    env_leak.validate()
    chk("source_channel='twilio' (provider leak) is rejected", False, "no exception raised")
except EnvelopeValidationError as exc:
    chk("source_channel='twilio' (provider leak) is rejected", True)
    chk("provider-leak error message references provider=", "provider=" in str(exc), str(exc))

env_unknown = _envelope(source_channel="carrier_pigeon")
try:
    env_unknown.validate()
    chk("unrelated unknown source_channel is rejected", False, "no exception raised")
except EnvelopeValidationError:
    chk("unrelated unknown source_channel is rejected", True)

env_bad_provider = _envelope(provider="unknown_sdk")
try:
    env_bad_provider.validate()
    chk("unknown provider is rejected", False, "no exception raised")
except EnvelopeValidationError:
    chk("unknown provider is rejected", True)


# ══════════════════════════════════════════════════
# 4. EvidenceTrace — fully empty and partial states are valid
# ══════════════════════════════════════════════════
trace_empty = EvidenceTrace()
try:
    trace_empty.validate()
    chk("fully-empty trace (nothing happened yet) is valid", True)
except TraceValidationError as exc:
    chk("fully-empty trace (nothing happened yet) is valid", False, str(exc))
chk("fully-empty trace is_complete=False", trace_empty.is_complete is False)

# Tier 3/4: classified, no approval needed (auto-write path never reached),
# no observation yet — this is the exact "partial trace" the spec requires
# to be treated as a pass, not a failure.
trace_tier4 = EvidenceTrace(classification_result={"tier": 4, "confidence": 1.0})
try:
    trace_tier4.validate()
    chk("Tier 3/4 partial trace (classified, no approval/write) is valid", True)
except TraceValidationError as exc:
    chk("Tier 3/4 partial trace (classified, no approval/write) is valid", False, str(exc))
chk("Tier 3/4 partial trace is_complete=False", trace_tier4.is_complete is False)

# classified + observed, no approval required
trace_no_approval = EvidenceTrace(
    classification_result={"tier": 1, "confidence": 0.9},
    agent_observation="lead capture, high confidence",
)
try:
    trace_no_approval.validate()
    chk("classified+observed, no-approval-required trace is valid", True)
except TraceValidationError as exc:
    chk("classified+observed, no-approval-required trace is valid", False, str(exc))

# fully populated
trace_full = EvidenceTrace(
    classification_result={"tier": 1, "confidence": 0.9},
    approval_contract_id="contract-abc",
    agent_observation="lead capture, high confidence",
)
try:
    trace_full.validate()
    chk("fully-populated (3/3) trace is valid", True)
except TraceValidationError as exc:
    chk("fully-populated (3/3) trace is valid", False, str(exc))
chk("fully-populated trace is_complete=True", trace_full.is_complete is True)

# ══════════════════════════════════════════════════
# 5. Ordering violations — later-stage field without classification_result
# ══════════════════════════════════════════════════
trace_bad_approval = EvidenceTrace(approval_contract_id="contract-abc")
try:
    trace_bad_approval.validate()
    chk("approval_contract_id without classification_result is rejected", False, "no exception raised")
except TraceValidationError:
    chk("approval_contract_id without classification_result is rejected", True)

trace_bad_observation = EvidenceTrace(agent_observation="some reasoning")
try:
    trace_bad_observation.validate()
    chk("agent_observation without classification_result is rejected", False, "no exception raised")
except TraceValidationError:
    chk("agent_observation without classification_result is rejected", True)


# ══════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════
print(f"\n{passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
