# test_c90_structured_file_capture.py — C90: Stage 3.1 Capture Policy — structured files (xlsx/csv)
#
# ROADMAP.md C90: "A file uploaded to the bot -> second client of
# classify_ingress(). File = Tier 4 by default (preview)." No auto-write, no
# new classifier, no direct Airtable write. Gated behind FEATURE_STRUCTURED_
# FILE_CAPTURE (default off) so xlsx/csv uploads keep their existing
# FEATURE_MEDIA_UPLOAD behavior unchanged unless explicitly turned on.

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-c90-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:C90_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patC90Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appC90Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
from core.ingress_classifier import classify_ingress  # noqa: E402
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


# ══════════════════════════════════════════════════
# 1. classify_ingress(source_type="file") — always Tier 4, preview only
# ══════════════════════════════════════════════════
ic_file = classify_ingress("leads.xlsx", source_type="file")
chk("file upload -> tier=4", ic_file.tier == 4, f"got {ic_file.tier}")
chk("file upload -> content_class='table'", ic_file.content_class == "table", f"got {ic_file.content_class}")
chk("file upload -> reason='file_upload_default_tier4'", ic_file.reason == "file_upload_default_tier4", f"got {ic_file.reason}")
chk("file upload -> no candidates (no new classifier)", ic_file.candidates == ())
chk("file upload -> raw_ref non-empty", bool(ic_file.raw_ref), f"raw_ref={ic_file.raw_ref!r}")

# Regression guard: other non-text source types must remain unimplemented (Tier 5) —
# only "file" changed behavior.
ic_voice = classify_ingress("x", source_type="voice")
chk("voice source_type unaffected -> still tier=5", ic_voice.tier == 5, f"got {ic_voice.tier}")
ic_image = classify_ingress("x", source_type="image")
chk("image source_type unaffected -> still tier=5", ic_image.tier == 5, f"got {ic_image.tier}")


# ══════════════════════════════════════════════════
# 2. _is_structured_file() — extension/mime detection
# ══════════════════════════════════════════════════
chk("'leads.xlsx' detected by extension", app._is_structured_file("leads.xlsx", ""))
chk("'leads.csv' detected by extension", app._is_structured_file("leads.csv", ""))
chk("xlsx mime type detected regardless of filename", app._is_structured_file("upload", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
chk("csv mime type detected regardless of filename", app._is_structured_file("upload", "text/csv"))
chk("'report.pdf' NOT detected", not app._is_structured_file("report.pdf", "application/pdf"))
chk("'photo.jpg' NOT detected", not app._is_structured_file("photo.jpg", "image/jpeg"))


# ══════════════════════════════════════════════════
# 3. _handle_telegram_media() wiring
# ══════════════════════════════════════════════════
OWNER_IDENTITY = Identity(user_id="owner_1", role=Role.OWNER, tenant_id="boss_hq",
                          channel="telegram", external_id="111")
LEAD_IDENTITY = Identity(user_id="lead_1", role=Role.LEAD, tenant_id="boss_hq",
                         channel="telegram", external_id="222")


def _make_document_message(filename: str, mime_type: str, from_user_id: str = "111"):
    document = SimpleNamespace(file_id="fileABC", file_name=filename, mime_type=mime_type, file_size=1024)
    return SimpleNamespace(
        chat=SimpleNamespace(id=int(from_user_id)),
        from_user=SimpleNamespace(id=from_user_id),
        content_type="document",
        document=document,
        caption=None,
        text=None,
    )


def _flag_only(name_to_enable: str):
    return lambda name: name == name_to_enable


msg_xlsx = _make_document_message("leads.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# 3a. Flag ON + structured file + internal sender -> preview reply, no media_handler call
with patch.object(app, "resolve_identity", return_value=OWNER_IDENTITY), \
     patch.object(app, "_flag_enabled", side_effect=_flag_only("FEATURE_STRUCTURED_FILE_CAPTURE")), \
     patch.object(app.bot, "send_message") as mock_send, \
     patch("media_handler.handle_file_upload") as mock_media_upload:
    app._handle_telegram_media(msg_xlsx)

chk("flag ON + xlsx + internal: bot replies with preview message", mock_send.called)
if mock_send.called:
    reply_text = mock_send.call_args.args[1] if len(mock_send.call_args.args) > 1 else mock_send.call_args.kwargs.get("text", "")
    chk("preview reply mentions the filename", "leads.xlsx" in reply_text, reply_text)
    chk("preview reply says preview-only / no automatic action", "תצוגה מקדימה" in reply_text, reply_text)
chk("flag ON + xlsx + internal: media_handler.handle_file_upload NOT called (no Drive/Airtable write)", not mock_media_upload.called)

# 3b. Flag OFF -> falls through to existing FEATURE_MEDIA_UPLOAD behavior unchanged
with patch.object(app, "resolve_identity", return_value=OWNER_IDENTITY), \
     patch.object(app, "_flag_enabled", return_value=False), \
     patch.object(app.bot, "send_message") as mock_send_off, \
     patch("media_handler.handle_file_upload") as mock_media_upload_off:
    app._handle_telegram_media(msg_xlsx)

chk("flag OFF: falls through to existing '📎 בקרוב' message", mock_send_off.called)
if mock_send_off.called:
    reply_text_off = mock_send_off.call_args.args[1] if len(mock_send_off.call_args.args) > 1 else mock_send_off.call_args.kwargs.get("text", "")
    chk("flag OFF: unchanged legacy message text", "בקרוב" in reply_text_off, reply_text_off)
chk("flag OFF: media_handler still not called (FEATURE_MEDIA_UPLOAD also off)", not mock_media_upload_off.called)

# 3c. Flag ON + structured file + EXTERNAL (non-internal) sender -> falls through, not the C90 preview
msg_xlsx_lead = _make_document_message("leads.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", from_user_id="222")
with patch.object(app, "resolve_identity", return_value=LEAD_IDENTITY), \
     patch.object(app, "_flag_enabled", side_effect=_flag_only("FEATURE_STRUCTURED_FILE_CAPTURE")), \
     patch.object(app.bot, "send_message") as mock_send_ext:
    app._handle_telegram_media(msg_xlsx_lead)

if mock_send_ext.called:
    reply_text_ext = mock_send_ext.call_args.args[1] if len(mock_send_ext.call_args.args) > 1 else mock_send_ext.call_args.kwargs.get("text", "")
    chk("external sender: does NOT get the C90 preview message", "תצוגה מקדימה" not in reply_text_ext, reply_text_ext)

# 3d. Flag ON + non-structured file (pdf) + internal sender -> falls through, not the C90 preview
msg_pdf = _make_document_message("contract.pdf", "application/pdf")
with patch.object(app, "resolve_identity", return_value=OWNER_IDENTITY), \
     patch.object(app, "_flag_enabled", side_effect=_flag_only("FEATURE_STRUCTURED_FILE_CAPTURE")), \
     patch.object(app.bot, "send_message") as mock_send_pdf, \
     patch("media_handler.handle_file_upload") as mock_media_upload_pdf:
    app._handle_telegram_media(msg_pdf)

if mock_send_pdf.called:
    reply_text_pdf = mock_send_pdf.call_args.args[1] if len(mock_send_pdf.call_args.args) > 1 else mock_send_pdf.call_args.kwargs.get("text", "")
    chk("pdf upload: does NOT get the C90 preview message", "תצוגה מקדימה" not in reply_text_pdf, reply_text_pdf)
chk("pdf upload: media_handler not called (FEATURE_MEDIA_UPLOAD off in this test)", not mock_media_upload_pdf.called)


print(f"\n{'='*50}")
print(f"C90 Structured File Capture tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
