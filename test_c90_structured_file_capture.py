# test_c90_structured_file_capture.py — C90: Stage 3.1 Capture Policy — structured files (xlsx/csv)
#
# Principle (per spec): file upload is a new INGRESS SOURCE ADAPTER only —
# NOT a new capture pipeline, NOT a new classifier, NOT a new write path.
# Every row is parsed (core/file_ingress_adapter.py) and dispatched, one at
# a time, through the EXACT SAME classify_ingress()/handle_lead_candidate()
# pipeline a text message would use. No special-casing: a row with a clear
# name+phone can legitimately resolve to Tier 1/2/3, same as text.
#
# Evidence this file proves:
#   - file upload produces N ingress events for N rows (no merging/dropping)
#   - every row passes through classify_ingress (no separate code path)
#   - every row produces an Observation with kind='capture_classification'
#   - default tier for file rows = Tier 4 unless legitimately resolved higher
#   - no row is auto-written without Approval (FEATURE_AUTO_CAPTURE=false)
#   - raw_ref present + distinct per row
#   - malformed row fails safely, never silently dropped, never auto-written

import io
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
import core.lead_candidate_handler as lch  # noqa: E402
import core.action_gateway as action_gateway_mod  # noqa: E402
from core.action_gateway import ActionGateway, ExecutionLedger  # noqa: E402
from core.ingress_classifier import classify_ingress  # noqa: E402
from core.file_ingress_adapter import parse_structured_file_rows, FileParseError  # noqa: E402
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


def _new_gw(executor=None):
    return ActionGateway(ledger=ExecutionLedger(), tool_executor=executor)


OWNER_IDENTITY = Identity(user_id="owner_1", role=Role.OWNER, tenant_id="boss_hq",
                          channel="telegram", external_id="111")


# ══════════════════════════════════════════════════
# 1. core/file_ingress_adapter.py — pure parsing, no merging/dropping
# ══════════════════════════════════════════════════
CSV_3_ROWS = (
    "Name,Phone,City\n"
    "משה כהן,0501234567,תל אביב\n"
    "דנה לוי,0521234567,חיפה\n"
    "יוסי מזרחי,0541234567,ירושלים\n"
)

rows = parse_structured_file_rows(CSV_3_ROWS.encode("utf-8"), "leads.csv")
chk("csv: 3 data rows -> 3 row-texts (header not emitted as a row)", len(rows) == 3, f"got {len(rows)}")
chk("csv row 1 contains header-labeled name", "Name: משה כהן" in rows[0], rows[0])
chk("csv row 1 contains header-labeled phone", "Phone: 0501234567" in rows[0], rows[0])

# Regression guard: a realistic 3-column row (Name/Phone/City) must resolve
# to Tier 1 through the REAL parser's output — not force-collide with the
# pipe-table Tier-4 marker just because the row happens to have 3+ columns.
ic_real_row = classify_ingress(rows[0], source_type="file")
chk("real 3-column parsed row resolves to Tier 1, not accidentally Tier 4", ic_real_row.tier == 1, f"row={rows[0]!r} tier={ic_real_row.tier} reason={ic_real_row.reason}")

CSV_WITH_BLANK_ROW = (
    "Name,Phone\n"
    "משה כהן,0501234567\n"
    ",\n"
    "דנה לוי,0521234567\n"
)
rows_blank = parse_structured_file_rows(CSV_WITH_BLANK_ROW.encode("utf-8"), "leads.csv")
chk("fully-empty row is skipped (zero info, not a dropped event)", len(rows_blank) == 2, f"got {len(rows_blank)}")

try:
    parse_structured_file_rows(b"", "empty.csv")
    chk("empty file raises FileParseError", False)
except FileParseError:
    chk("empty file raises FileParseError", True)

try:
    parse_structured_file_rows(b"whatever", "notes.txt")
    chk("unsupported extension raises FileParseError", False)
except FileParseError:
    chk("unsupported extension raises FileParseError", True)

# xlsx round-trip (openpyxl)
try:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Name", "Phone"])
    ws.append(["משה כהן", "0501234567"])
    ws.append(["דנה לוי", "0521234567"])
    buf = io.BytesIO()
    wb.save(buf)
    xlsx_rows = parse_structured_file_rows(buf.getvalue(), "leads.xlsx")
    chk("xlsx: 2 data rows -> 2 row-texts", len(xlsx_rows) == 2, f"got {len(xlsx_rows)}")
    chk("xlsx row contains header-labeled phone", "Phone: 0501234567" in xlsx_rows[0], xlsx_rows[0])
except ImportError:
    print("⚠️  openpyxl not installed — skipping xlsx parse tests")

# malformed row: header/row shape mismatch must never raise past the parser
MALFORMED_CSV = "Name,Phone\nמשה כהן,0501234567,extra,cells\n"
malformed_rows = parse_structured_file_rows(MALFORMED_CSV.encode("utf-8"), "leads.csv")
chk("malformed (ragged) row is never dropped — still produces a row-text", len(malformed_rows) == 1, f"got {malformed_rows}")


# ══════════════════════════════════════════════════
# 2. classify_ingress(source_type="file") — no special-casing
# ══════════════════════════════════════════════════
ic_clear_lead = classify_ingress("Name: משה כהן | Phone: 0501234567", source_type="file")
chk("clear name+phone row resolves to Tier 1 (NOT forced to Tier 4)", ic_clear_lead.tier == 1, f"got tier={ic_clear_lead.tier} reason={ic_clear_lead.reason}")
chk("Tier 1 row source_type is 'file'", ic_clear_lead.source_type == "file")

ic_no_lead = classify_ingress("Notes: follow up next week", source_type="file")
chk("row with no lead info resolves to Tier 5 (default, no special override)", ic_no_lead.tier == 5, f"got tier={ic_no_lead.tier}")

ic_export_row = classify_ingress("Status: Warm | Score: 50/100 | View in Airtable", source_type="file")
chk("row matching Tier-4 hard markers still resolves Tier 4 (reused, not bypassed)", ic_export_row.tier == 4, f"got tier={ic_export_row.tier}")

ic_1 = classify_ingress("Name: משה כהן | Phone: 0501234567", source_type="file")
ic_2 = classify_ingress("Name: דנה לוי | Phone: 0521234567", source_type="file")
chk("raw_ref present for each row", bool(ic_1.raw_ref) and bool(ic_2.raw_ref))
chk("raw_ref distinct across rows", ic_1.raw_ref != ic_2.raw_ref, f"{ic_1.raw_ref} vs {ic_2.raw_ref}")


# ══════════════════════════════════════════════════
# 3. Observation recorded per row (kind='capture_classification')
# ══════════════════════════════════════════════════
obs_calls = []
orig_obs = action_gateway_mod.action_gateway.record_agent_observation


def _obs_spy(contract_id, kind, text):
    obs_calls.append({"contract_id": contract_id, "kind": kind, "text": text})
    return orig_obs(contract_id, kind, text)


with patch.object(action_gateway_mod.action_gateway, "record_agent_observation", _obs_spy):
    for row in ["Name: משה כהן | Phone: 0501234567", "Name: דנה לוי | Phone: 0521234567", "Notes: x"]:
        classify_ingress(row, source_type="file")

chk("observation recorded for every row classified", len(obs_calls) == 3, f"got {len(obs_calls)}")
chk("every observation has kind='capture_classification'", all(c["kind"] == "capture_classification" for c in obs_calls))
chk("every observation has contract_id=None (no ActionContract coupling)", all(c["contract_id"] is None for c in obs_calls))


# ══════════════════════════════════════════════════
# 4. _process_structured_file_upload() — full per-row dispatch
# ══════════════════════════════════════════════════
CSV_2_LEADS = (
    "Name,Phone\n"
    "משה כהן,0501234567\n"
    "דנה לוי,0521234567\n"
)

gw = _new_gw(executor=None)  # fail-closed executor is fine — approval, not execution, is under test
with patch.object(lch, "_at_find_lead", return_value=None), \
     patch("core.action_gateway.action_gateway", gw), \
     patch("feature_flags.is_enabled", return_value=False):  # FEATURE_AUTO_CAPTURE=false, verified explicitly
    summary = app._process_structured_file_upload(
        OWNER_IDENTITY, "chat_c90_1", "telegram", "general",
        CSV_2_LEADS.encode("utf-8"), "leads.csv",
    )

chk("summary reply produced for 2-row file", summary is not None and "leads.csv" in summary, summary)
chk("summary reports Tier 1 rows", "Tier 1: 2" in summary, summary)
chk("2 rows -> 2 pending ActionGateway contracts (no bulk auto-approve)", len(gw._ledger._store) == 2, f"got {len(gw._ledger._store)}")
chk("no row auto-written without approval — all contracts still 'pending'",
    all(c.status == "pending" for c in gw._ledger._store.values()),
    str([c.status for c in gw._ledger._store.values()]))
chk("summary tells the user approval is required, not auto-write", "אישור" in summary, summary)
chk(
    "raw_ref distinct per row-derived contract's fingerprint (2 separate contracts, not merged into 1)",
    len({c.business_action_fingerprint for c in gw._ledger._store.values()}) == 2,
)

# Malformed row must never crash the whole file — still counted, never silently dropped.
CSV_WITH_MALFORMED_ROW = (
    "Name,Phone\n"
    "משה כהן,0501234567\n"
    "דנה לוי,0521234567,extra,cells\n"
)
gw2 = _new_gw(executor=None)
with patch.object(lch, "_at_find_lead", return_value=None), \
     patch("core.action_gateway.action_gateway", gw2), \
     patch("feature_flags.is_enabled", return_value=False):
    summary2 = app._process_structured_file_upload(
        OWNER_IDENTITY, "chat_c90_2", "telegram", "general",
        CSV_WITH_MALFORMED_ROW.encode("utf-8"), "leads.csv",
    )
total_rows_reported = sum(int(n) for n in __import__("re").findall(r"Tier \d+: (\d+)", summary2))
chk("malformed row still counted in the summary (never silently dropped)", total_rows_reported == 2, summary2)

# Unparseable file -> explicit error reply, not a crash / not silently ignored
gw3 = _new_gw(executor=None)
with patch("core.action_gateway.action_gateway", gw3):
    error_summary = app._process_structured_file_upload(
        OWNER_IDENTITY, "chat_c90_3", "telegram", "general", b"", "empty.csv",
    )
chk("unparseable file produces an explicit error reply", "❌" in error_summary, error_summary)


# ══════════════════════════════════════════════════
# 4b. C94 Stage ב — a classify_ingress() exception on ONE row must not crash
#     the rest of the file. Before this wiring, the row loop had no
#     try/except around classify_ingress() itself (only around
#     handle_lead_candidate()) — an exception here would propagate up and
#     abort processing of every remaining row in the file, silently.
# ══════════════════════════════════════════════════
CSV_WITH_CLASSIFY_EXPLOSION = (
    "Name,Phone\n"
    "משה כהן,0501234567\n"
    "בום,0009999999\n"
    "דנה לוי,0521234567\n"
)

_real_classify_ingress = classify_ingress


def _boom_classify_ingress(text, source_type="text"):
    if "0009999999" in text:
        raise ValueError(f"boom — this message must never reach user-facing text: {text}")
    return _real_classify_ingress(text, source_type=source_type)


gw4 = _new_gw(executor=None)
with patch.object(lch, "_at_find_lead", return_value=None), \
     patch("core.action_gateway.action_gateway", gw4), \
     patch("feature_flags.is_enabled", return_value=False), \
     patch("core.ingress_classifier.classify_ingress", side_effect=_boom_classify_ingress):
    summary4 = app._process_structured_file_upload(
        OWNER_IDENTITY, "chat_c90_4", "telegram", "general",
        CSV_WITH_CLASSIFY_EXPLOSION.encode("utf-8"), "leads.csv",
    )

chk("a classify_ingress() exception on one row does not crash the whole file", summary4 is not None, summary4)
chk("the other 2 (non-exploding) rows still get processed", len(gw4._ledger._store) == 2, f"got {len(gw4._ledger._store)}")
chk("the exploding row is counted as failed in the summary", "1 שורות נכשלו" in summary4, summary4)
chk(
    "raw exception text/PII never leaks into the user-facing summary",
    "0009999999" not in summary4 and "boom" not in summary4,
    summary4,
)


# ══════════════════════════════════════════════════
# 5. _is_structured_file() — extension/mime detection (unchanged from before)
# ══════════════════════════════════════════════════
chk("'leads.xlsx' detected by extension", app._is_structured_file("leads.xlsx", ""))
chk("'leads.csv' detected by extension", app._is_structured_file("leads.csv", ""))
chk("'report.pdf' NOT detected", not app._is_structured_file("report.pdf", "application/pdf"))


# ══════════════════════════════════════════════════
# 6. _handle_telegram_media() wiring — flag/identity gating
# ══════════════════════════════════════════════════
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

with patch.object(app, "resolve_identity", return_value=OWNER_IDENTITY), \
     patch.object(app, "_flag_enabled", side_effect=_flag_only("FEATURE_STRUCTURED_FILE_CAPTURE")), \
     patch.object(app.bot, "get_file", return_value=SimpleNamespace(file_path="x")), \
     patch.object(app.bot, "download_file", return_value=b"Name,Phone\nA,0501234567\n"), \
     patch.object(app.bot, "send_message") as mock_send, \
     patch.object(app, "_process_structured_file_upload", return_value="MOCKED SUMMARY") as mock_process, \
     patch("media_handler.handle_file_upload") as mock_media_upload:
    app._handle_telegram_media(msg_xlsx)

chk("flag ON + xlsx + internal: _process_structured_file_upload called (real row pipeline)", mock_process.called)
chk("flag ON + xlsx + internal: bot replies with the pipeline's summary", mock_send.called and mock_send.call_args.args[1] == "MOCKED SUMMARY")
chk("flag ON + xlsx + internal: media_handler.handle_file_upload NOT called (no Drive/Airtable write)", not mock_media_upload.called)

with patch.object(app, "resolve_identity", return_value=OWNER_IDENTITY), \
     patch.object(app, "_flag_enabled", return_value=False), \
     patch.object(app.bot, "send_message") as mock_send_off, \
     patch.object(app, "_process_structured_file_upload") as mock_process_off, \
     patch("media_handler.handle_file_upload") as mock_media_upload_off:
    app._handle_telegram_media(msg_xlsx)

chk("flag OFF: falls through to existing '📎 בקרוב' message, pipeline not invoked", mock_send_off.called and not mock_process_off.called)
chk("flag OFF: media_handler still not called (FEATURE_MEDIA_UPLOAD also off)", not mock_media_upload_off.called)

msg_xlsx_lead = _make_document_message("leads.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", from_user_id="222")
with patch.object(app, "resolve_identity", return_value=LEAD_IDENTITY), \
     patch.object(app, "_flag_enabled", side_effect=_flag_only("FEATURE_STRUCTURED_FILE_CAPTURE")), \
     patch.object(app.bot, "send_message"), \
     patch.object(app, "_process_structured_file_upload") as mock_process_ext:
    app._handle_telegram_media(msg_xlsx_lead)
chk("external (non-internal) sender never reaches the C90 pipeline", not mock_process_ext.called)

msg_pdf = _make_document_message("contract.pdf", "application/pdf")
with patch.object(app, "resolve_identity", return_value=OWNER_IDENTITY), \
     patch.object(app, "_flag_enabled", side_effect=_flag_only("FEATURE_STRUCTURED_FILE_CAPTURE")), \
     patch.object(app.bot, "send_message"), \
     patch.object(app, "_process_structured_file_upload") as mock_process_pdf:
    app._handle_telegram_media(msg_pdf)
chk("non-structured file (pdf) never reaches the C90 pipeline", not mock_process_pdf.called)


print(f"\n{'='*50}")
print(f"C90 Structured File Capture tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
