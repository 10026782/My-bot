# test_c94_stage_d_whatsapp.py — C94 Stage ד: WhatsApp (Twilio) ingress adapter
#
# Proves:
#   1. build_whatsapp_envelope() schema conformance (source_channel=whatsapp,
#      provider=twilio_whatsapp via mapping — never the bare "twilio" string,
#      BUG-071 pattern — source_ref, no raw_ref field).
#   2. run_agent() builds a valid WhatsApp envelope end-to-end when a real
#      raw_event_id (Twilio MessageSid) is passed, through the ACTUAL
#      run_agent() entrypoint (not just route_request()) — and produces an
#      IDENTICAL reply whether or not raw_event_id is passed (equivalence).
#   3. A failure inside envelope construction itself degrades gracefully —
#      run_agent() still replies normally, never blocked by C94 plumbing.
#   4. The Telegram branch (Stage ג) is unaffected by adding the WhatsApp
#      branch to the same dispatch block — regression check.
#   5. Meta WhatsApp Cloud API's webhook never passes raw_event_id (source-
#      level proof) — confirms it stays untouched/gated, per BUG-071's
#      "one channel at a time" principle; only Twilio is wired.
#
# Reuses Stage ג's already channel-agnostic router-level exception-safety
# proof (capture_router.classify_capture_ic() degrades gracefully on a
# classify_ingress() failure) — that fix already covers WhatsApp since
# Stage ג. This file only tests what's NEW in Stage ד: the adapter itself
# and its wiring into run_agent()/the Twilio webhook.

import inspect
import logging
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-c94-stage-d-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:C94_STAGE_D_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patC94StageDTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appC94StageDTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
from core.whatsapp_ingress_adapter import build_whatsapp_envelope  # noqa: E402
from core.ingress_envelope import IngressEnvelope  # noqa: E402
from identity import Identity, Role  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}{(' — ' + extra) if extra else ''}")
        failed += 1


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


OWNER_WHATSAPP_IDENTITY = Identity(
    user_id="owner_1", role=Role.OWNER, tenant_id="boss_hq",
    channel="whatsapp", external_id="+972500000000",
)

# Ambiguous phrase → Handler.CLARIFY (per core/router/test_router.py's own
# table) — short-circuits run_agent() before it ever reaches Claude/dispatch,
# so this end-to-end test needs no Anthropic/tool mocking.
AMBIGUOUS_TEXT = "בדיקת מערכת"


# ══════════════════════════════════════════════════
# 1. build_whatsapp_envelope() — schema conformance
# ══════════════════════════════════════════════════
env = build_whatsapp_envelope(identity=OWNER_WHATSAPP_IDENTITY, raw_event_id="SM123456", text="שלום")
chk("envelope source_channel == 'whatsapp'", env.source_channel == "whatsapp")
chk("envelope provider == 'twilio_whatsapp' (via mapping, not hardcoded inline)", env.provider == "twilio_whatsapp")
chk("envelope provider is NOT bare 'twilio' (BUG-071 pattern)", env.provider != "twilio")
chk("envelope sender_identity == identity.memory_key", env.sender_identity == OWNER_WHATSAPP_IDENTITY.memory_key)
chk("envelope source_ref references the raw_event_id", "SM123456" in env.source_ref)
chk("envelope has no raw_ref field", "raw_ref" not in IngressEnvelope.__dataclass_fields__)
try:
    env.validate()
    chk("build_whatsapp_envelope() output passes validate()", True)
except Exception as exc:
    chk("build_whatsapp_envelope() output passes validate()", False, str(exc))


# ══════════════════════════════════════════════════
# 2. run_agent() end-to-end — equivalence with/without raw_event_id (WhatsApp)
# ══════════════════════════════════════════════════
with patch.object(app, "resolve_identity", return_value=OWNER_WHATSAPP_IDENTITY):
    reply_no_envelope = app.run_agent(AMBIGUOUS_TEXT, "+972500000000", channel="whatsapp")
    reply_with_envelope = app.run_agent(
        AMBIGUOUS_TEXT, "+972500000000", channel="whatsapp", raw_event_id="SM_equiv_1",
    )

chk(
    "run_agent() reply is identical with/without raw_event_id (WhatsApp, normal path)",
    reply_no_envelope == reply_with_envelope,
    f"{reply_no_envelope!r} vs {reply_with_envelope!r}",
)


# ══════════════════════════════════════════════════
# 3. Envelope construction failure degrades gracefully — never blocks the reply
# ══════════════════════════════════════════════════
with patch.object(app, "resolve_identity", return_value=OWNER_WHATSAPP_IDENTITY), \
     patch("core.whatsapp_ingress_adapter.build_whatsapp_envelope", side_effect=RuntimeError("boom")):
    reply_on_build_failure = app.run_agent(
        AMBIGUOUS_TEXT, "+972500000000", channel="whatsapp", raw_event_id="SM_fail_1",
    )
chk(
    "run_agent() still replies normally even if envelope construction itself raises",
    reply_on_build_failure == reply_no_envelope,
    f"{reply_on_build_failure!r} vs {reply_no_envelope!r}",
)


# ══════════════════════════════════════════════════
# 4. Telegram branch unaffected by adding the WhatsApp branch (regression)
# ══════════════════════════════════════════════════
OWNER_TELEGRAM_IDENTITY = Identity(
    user_id="owner_1", role=Role.OWNER, tenant_id="boss_hq",
    channel="telegram", external_id="111",
)
with patch.object(app, "resolve_identity", return_value=OWNER_TELEGRAM_IDENTITY):
    tg_reply_no_env = app.run_agent(AMBIGUOUS_TEXT, "111", channel="telegram")
    tg_reply_with_env = app.run_agent(AMBIGUOUS_TEXT, "111", channel="telegram", raw_event_id="upd_equiv_1")
chk(
    "Telegram run_agent() reply is still identical with/without raw_event_id (no Stage ג regression)",
    tg_reply_no_env == tg_reply_with_env,
)


# ══════════════════════════════════════════════════
# 5. Meta WhatsApp Cloud API path never passes raw_event_id (source-level proof)
# ══════════════════════════════════════════════════
_meta_source = inspect.getsource(app.webhook_meta_whatsapp)
chk(
    "webhook_meta_whatsapp()'s run_agent() call has no raw_event_id (Meta stays untouched/gated)",
    "raw_event_id" not in _meta_source,
)

_twilio_source = inspect.getsource(app._webhook_whatsapp_impl)
chk(
    "_webhook_whatsapp_impl() (Twilio) DOES pass raw_event_id=msg_sid",
    "raw_event_id" in _twilio_source and "msg_sid" in _twilio_source,
)


# ══════════════════════════════════════════════════
# 6. [IngressEnvelope] accepted marker (Track D observability) — WhatsApp
# ══════════════════════════════════════════════════
with patch.object(app, "resolve_identity", return_value=OWNER_WHATSAPP_IDENTITY):
    logger_obs, handler_obs = _capture_logs("app")
    obs_reply = app.run_agent(
        AMBIGUOUS_TEXT, "+972500000000", channel="whatsapp", raw_event_id="SM_obs_1",
    )
    logger_obs.removeHandler(handler_obs)

wa_marker_lines = [m for m in handler_obs.records if m.startswith("[IngressEnvelope] accepted")]
chk(
    "run_agent() emits exactly one [IngressEnvelope] accepted marker for a valid WhatsApp envelope",
    len(wa_marker_lines) == 1, str(wa_marker_lines),
)
chk(
    "marker includes source_channel=whatsapp and provider=twilio_whatsapp",
    bool(wa_marker_lines) and "source_channel=whatsapp" in wa_marker_lines[0] and "provider=twilio_whatsapp" in wa_marker_lines[0],
    str(wa_marker_lines),
)
chk(
    "marker classifies source_ref_kind=message_id (never logs the raw source_ref)",
    bool(wa_marker_lines) and "source_ref_kind=message_id" in wa_marker_lines[0],
    str(wa_marker_lines),
)
chk(
    "marker never contains the user's message text",
    all(AMBIGUOUS_TEXT not in m for m in wa_marker_lines),
    str(wa_marker_lines),
)
chk(
    "adding the marker does not change the reply (equivalence with the no-raw_event_id baseline)",
    obs_reply == reply_no_envelope,
)

# Envelope build/validate failure → no marker logged (reuses section 3's failure patch)
with patch.object(app, "resolve_identity", return_value=OWNER_WHATSAPP_IDENTITY), \
     patch("core.whatsapp_ingress_adapter.build_whatsapp_envelope", side_effect=RuntimeError("boom")):
    logger_fail, handler_fail = _capture_logs("app")
    app.run_agent(AMBIGUOUS_TEXT, "+972500000000", channel="whatsapp", raw_event_id="SM_obs_fail")
    logger_fail.removeHandler(handler_fail)
chk(
    "no [IngressEnvelope] accepted marker is emitted when WhatsApp envelope construction fails",
    not any(m.startswith("[IngressEnvelope] accepted") for m in handler_fail.records),
    str(handler_fail.records),
)


# ══════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════
print(f"\n{passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
