# test_c94_ingress_envelope.py — C94 Stage א: IngressEnvelope + EvidenceTrace schemas
#
# Proves:
#   1. IngressEnvelope.validate() accepts a fully-populated envelope for every
#      known logical channel, and rejects each of the 7 required fields when
#      missing/empty.
#   2. source_channel/provider are never interchangeable — a provider name in
#      source_channel is rejected with a distinct error (BUG-071 pattern).
#   3. C94-A.1: IngressEnvelope carries source_ref (adapter-level,
#      pre-classification pointer), NOT raw_ref — C89's raw_ref only exists
#      after classify_ingress() runs, so it lives on EvidenceTrace instead.
#   4. C94-A.2: envelope_id is a stable, auto-generated FK target; a Trace's
#      envelope_id is required once any other field is set; Traces are
#      append-only (record_classification() can't be called twice); a
#      classify_ingress() exception still produces evidence via
#      classification_error, mutually exclusive with classification_result.
#   5. EvidenceTrace.validate() accepts a fully-empty trace, a failed-
#      classification trace, and a partial trace (e.g. Tier 3/4 — classified,
#      no approval needed, no write) as valid states, and rejects only
#      ordering/append-only violations.
#   6. C94-A.3: trace_id is unique per attempt; attempt_no is 1-based and
#      strictly increasing per envelope_id via next_attempt(); latest_trace()
#      picks the highest attempt_no, not the first/oldest; status is a
#      read-only computed property (never a stored, driftable field) that
#      reports "classification_error" as valid evidence, not a failure; a
#      retry preserves BOTH the original and the new Trace (no overwrite).

from core.ingress_envelope import (
    IngressEnvelope,
    EvidenceTrace,
    EnvelopeValidationError,
    TraceValidationError,
    latest_trace,
    next_attempt,
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
        source_ref="telegram:msg:upd_123",
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
    "sender_identity", "normalized_text", "source_ref",
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

env_empty_envelope_id = _envelope(envelope_id="")
try:
    env_empty_envelope_id.validate()
    chk("empty envelope_id is rejected", False, "no exception raised")
except EnvelopeValidationError:
    chk("empty envelope_id is rejected", True)

# ══════════════════════════════════════════════════
# 3. C94-A.1: Envelope carries source_ref, never raw_ref
# ══════════════════════════════════════════════════
chk(
    "IngressEnvelope has no raw_ref field (moved to EvidenceTrace)",
    "raw_ref" not in IngressEnvelope.__dataclass_fields__,
)
chk(
    "IngressEnvelope has a source_ref field",
    "source_ref" in IngressEnvelope.__dataclass_fields__,
)
env_source_ref_only = _envelope(source_ref="file:leads.csv:row7")
try:
    env_source_ref_only.validate()
    chk("envelope validates with source_ref set and no raw_ref concept at all", True)
except EnvelopeValidationError as exc:
    chk("envelope validates with source_ref set and no raw_ref concept at all", False, str(exc))

# ══════════════════════════════════════════════════
# 4. C94-A.2: envelope_id — auto-generated, unique, stable FK target
# ══════════════════════════════════════════════════
env_a = _envelope()
env_b = _envelope()
chk("envelope_id is auto-generated (non-empty) by default", bool(env_a.envelope_id))
chk("envelope_id is distinct across separate envelopes", env_a.envelope_id != env_b.envelope_id)

env_explicit_id = _envelope(envelope_id="fixed-id-for-retry")
chk("envelope_id can be explicitly pinned (for a retry reusing the same id)", env_explicit_id.envelope_id == "fixed-id-for-retry")

# ══════════════════════════════════════════════════
# 5. source_channel/provider must never be interchangeable (BUG-071 pattern)
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
# 6. EvidenceTrace — fully empty and partial states are valid
# ══════════════════════════════════════════════════
trace_empty = EvidenceTrace()
try:
    trace_empty.validate()
    chk("fully-empty trace (nothing happened yet) is valid", True)
except TraceValidationError as exc:
    chk("fully-empty trace (nothing happened yet) is valid", False, str(exc))
chk("fully-empty trace is_complete=False", trace_empty.is_complete is False)

# Tier 3/4: classified (classification_result + raw_ref, both produced by
# the same classify_ingress() call), no approval needed, no observation yet
# — this is the exact "partial trace" the spec requires to pass, not fail.
trace_tier4 = EvidenceTrace(envelope_id="env-1")
trace_tier4.record_classification(classification_result={"tier": 4, "confidence": 1.0}, raw_ref="rec_abc123")
try:
    trace_tier4.validate()
    chk("Tier 3/4 partial trace (classified, no approval/write) is valid", True)
except TraceValidationError as exc:
    chk("Tier 3/4 partial trace (classified, no approval/write) is valid", False, str(exc))
chk("Tier 3/4 partial trace is_complete=False", trace_tier4.is_complete is False)

# classified + observed, no approval required
trace_no_approval = EvidenceTrace(envelope_id="env-2", agent_observation="lead capture, high confidence")
trace_no_approval.record_classification(classification_result={"tier": 1, "confidence": 0.9}, raw_ref="rec_def456")
try:
    trace_no_approval.validate()
    chk("classified+observed, no-approval-required trace is valid", True)
except TraceValidationError as exc:
    chk("classified+observed, no-approval-required trace is valid", False, str(exc))

# fully populated
trace_full = EvidenceTrace(envelope_id="env-3", approval_contract_id="contract-abc", agent_observation="lead capture, high confidence")
trace_full.record_classification(classification_result={"tier": 1, "confidence": 0.9}, raw_ref="rec_ghi789")
try:
    trace_full.validate()
    chk("fully-populated trace is valid", True)
except TraceValidationError as exc:
    chk("fully-populated trace is valid", False, str(exc))
chk("fully-populated trace is_complete=True", trace_full.is_complete is True)

# ══════════════════════════════════════════════════
# 7. Failed classification attempt — evidence preserved, never "vanishes"
# ══════════════════════════════════════════════════
trace_failed = EvidenceTrace(envelope_id="env-4")
trace_failed.record_classification(classification_error="ValueError: boom")
try:
    trace_failed.validate()
    chk("failed-classification trace (classification_error set) is valid", True)
except TraceValidationError as exc:
    chk("failed-classification trace (classification_error set) is valid", False, str(exc))
chk("failed-classification trace is_complete=False (can never complete)", trace_failed.is_complete is False)
chk("failed-classification trace has no raw_ref", trace_failed.raw_ref is None)

try:
    EvidenceTrace().record_classification()
    chk("record_classification() requires exactly one of result/error", False, "no exception raised")
except TraceValidationError:
    chk("record_classification() requires exactly one of result/error", True)

try:
    EvidenceTrace().record_classification(
        classification_result={"tier": 1}, classification_error="boom"
    )
    chk("record_classification() rejects both result AND error set", False, "no exception raised")
except TraceValidationError:
    chk("record_classification() rejects both result AND error set", True)

try:
    EvidenceTrace().record_classification(classification_result={"tier": 1})  # no raw_ref
    chk("record_classification() requires raw_ref alongside a successful result", False, "no exception raised")
except TraceValidationError:
    chk("record_classification() requires raw_ref alongside a successful result", True)

# ══════════════════════════════════════════════════
# 8. Append-only — a second record_classification() call is rejected
# ══════════════════════════════════════════════════
trace_retry = EvidenceTrace(envelope_id="env-5")
trace_retry.record_classification(classification_error="transient network error")
try:
    trace_retry.record_classification(classification_result={"tier": 1, "confidence": 0.9}, raw_ref="rec_retry")
    chk("second record_classification() on the same Trace is rejected (append-only)", False, "no exception raised")
except TraceValidationError:
    chk("second record_classification() on the same Trace is rejected (append-only)", True)

# The correct retry pattern: a NEW Trace, same envelope_id
trace_retry_v2 = EvidenceTrace(envelope_id=trace_retry.envelope_id)
trace_retry_v2.record_classification(classification_result={"tier": 1, "confidence": 0.9}, raw_ref="rec_retry")
chk(
    "retry creates a new Trace sharing the same envelope_id",
    trace_retry_v2.envelope_id == trace_retry.envelope_id and trace_retry_v2 is not trace_retry,
)
chk(
    "both the failed attempt and the retry are preserved (no overwrite)",
    trace_retry.classification_error == "transient network error"
    and trace_retry_v2.classification_result == {"tier": 1, "confidence": 0.9},
)

# ══════════════════════════════════════════════════
# 8b. C94-A.3 — trace_id, attempt_no, status, latest_trace()/next_attempt()
# ══════════════════════════════════════════════════
t1 = EvidenceTrace(envelope_id="env-multi")
t2 = EvidenceTrace(envelope_id="env-multi")
chk("trace_id is auto-generated (non-empty) by default", bool(t1.trace_id))
chk("trace_id is distinct across separate Trace instances", t1.trace_id != t2.trace_id)

chk("status='empty' before any classification is recorded", EvidenceTrace().status == "empty")

t_err = EvidenceTrace(envelope_id="env-status")
t_err.record_classification(classification_error="ValueError")
chk("status='classification_error' is reported as valid evidence, not a failure state", t_err.status == "classification_error")

t_ok = EvidenceTrace(envelope_id="env-status")
t_ok.record_classification(classification_result={"tier": 1}, raw_ref="rec_1")
chk("status='classified' once classification succeeds but trace isn't complete yet", t_ok.status == "classified")

t_ok.approval_contract_id = "contract-1"
t_ok.agent_observation = "obs"
chk("status='complete' once all 4 downstream fields are set", t_ok.status == "complete")

try:
    EvidenceTrace(attempt_no=0).validate()
    chk("attempt_no < 1 is rejected", False, "no exception raised")
except TraceValidationError:
    chk("attempt_no < 1 is rejected", True)

# next_attempt()/latest_trace() — one envelope_id, multiple attempts over time
attempt_1 = next_attempt("env-retry-flow", [])
attempt_1.record_classification(classification_error="TimeoutError")
chk("next_attempt() on an empty history starts at attempt_no=1", attempt_1.attempt_no == 1)

attempt_2 = next_attempt("env-retry-flow", [attempt_1])
attempt_2.record_classification(classification_result={"tier": 1, "confidence": 0.8}, raw_ref="rec_2")
chk("next_attempt() increments attempt_no to 2 for the same envelope_id", attempt_2.attempt_no == 2)
chk(
    "next_attempt() ignores traces belonging to OTHER envelope_ids",
    next_attempt("env-retry-flow", [attempt_1, attempt_2, EvidenceTrace(envelope_id="unrelated", attempt_no=99)]).attempt_no == 3,
)

history = [attempt_1, attempt_2]
chk("latest_trace() returns the highest attempt_no, not the first one recorded", latest_trace(history) is attempt_2)
chk("latest_trace() of empty list is None", latest_trace([]) is None)

# order-independence: latest_trace must not depend on list order
chk("latest_trace() is order-independent", latest_trace(list(reversed(history))) is attempt_2)

# ══════════════════════════════════════════════════
# 9. FK invariant — envelope_id required once any field is set
# ══════════════════════════════════════════════════
trace_missing_fk = EvidenceTrace()
trace_missing_fk.approval_contract_id = "contract-xyz"  # simulate a caller forgetting envelope_id
try:
    trace_missing_fk.validate()
    chk("trace with a field set but no envelope_id is rejected", False, "no exception raised")
except TraceValidationError:
    chk("trace with a field set but no envelope_id is rejected", True)

# ══════════════════════════════════════════════════
# 10. Ordering violations — later-stage field without classification_result
# ══════════════════════════════════════════════════
trace_bad_raw_ref = EvidenceTrace(envelope_id="env-6")
trace_bad_raw_ref.raw_ref = "rec_abc123"  # direct assignment, bypassing record_classification()
try:
    trace_bad_raw_ref.validate()
    chk("raw_ref without classification_result is rejected", False, "no exception raised")
except TraceValidationError:
    chk("raw_ref without classification_result is rejected", True)

trace_bad_approval = EvidenceTrace(envelope_id="env-7", approval_contract_id="contract-abc")
try:
    trace_bad_approval.validate()
    chk("approval_contract_id without classification_result is rejected", False, "no exception raised")
except TraceValidationError:
    chk("approval_contract_id without classification_result is rejected", True)

trace_bad_observation = EvidenceTrace(envelope_id="env-8", agent_observation="some reasoning")
try:
    trace_bad_observation.validate()
    chk("agent_observation without classification_result is rejected", False, "no exception raised")
except TraceValidationError:
    chk("agent_observation without classification_result is rejected", True)


# ══════════════════════════════════════════════════
# 11. Runtime observability — app._log_ingress_envelope_accepted() (Track D)
#
# Unit-level proof (see test_c94_stage_c_telegram.py / test_c94_stage_d_
# whatsapp.py for the same marker exercised end-to-end through the real
# run_agent() construction points): the marker exposes only safe identity/
# source metadata, classifies file_upload's filename-bearing source_ref as
# a safe "file" kind instead of logging the raw value, and never logs
# normalized_text.
# ══════════════════════════════════════════════════
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-c94-obs-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:C94_OBS_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patC94ObsTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appC94ObsTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)


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


PII_TEXT = "משה כהן 0501234567"

env_telegram = _envelope(
    source_channel="telegram", provider="telegram_bot_api",
    normalized_text=PII_TEXT, source_ref="telegram:msg:upd_obs_1",
)
logger_a, handler_a = _capture_logs("app")
app._log_ingress_envelope_accepted(env_telegram)
logger_a.removeHandler(handler_a)

chk(
    "_log_ingress_envelope_accepted() emits the '[IngressEnvelope] accepted' marker",
    any(m.startswith("[IngressEnvelope] accepted") for m in handler_a.records),
)
chk("marker includes envelope_id", any(env_telegram.envelope_id in m for m in handler_a.records))
chk("marker includes source_channel=telegram", any("source_channel=telegram" in m for m in handler_a.records))
chk("marker includes provider=telegram_bot_api", any("provider=telegram_bot_api" in m for m in handler_a.records))
chk(
    "marker never contains the sensitive normalized_text (PII)",
    all(PII_TEXT not in m for m in handler_a.records),
)

# file_upload: source_ref embeds the original filename (potentially
# identifying) — must classify as a safe kind, never log the raw value.
env_file = _envelope(
    source_channel="file_upload", provider="telegram_bot_api",
    source_ref="file:leads_יוסי_כהן.csv:row3",
)
logger_b, handler_b = _capture_logs("app")
app._log_ingress_envelope_accepted(env_file)
logger_b.removeHandler(handler_b)

chk(
    "file_upload envelope marker classifies source_ref_kind=file",
    any("source_ref_kind=file" in m for m in handler_b.records),
)
chk(
    "file_upload envelope marker never logs the raw filename-bearing source_ref",
    all("יוסי_כהן" not in m and "leads_" not in m for m in handler_b.records),
)

chk("telegram source_ref classifies as message_id", app._ingress_source_ref_kind("telegram") == "message_id")
chk("whatsapp source_ref classifies as message_id", app._ingress_source_ref_kind("whatsapp") == "message_id")
chk("file_upload source_ref classifies as file", app._ingress_source_ref_kind("file_upload") == "file")


# ══════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════
print(f"\n{passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
