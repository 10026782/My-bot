"""Focused Audit #3 contract tests for CRM and payment reminders."""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import crm
import payment_reminder
from airtable_schema import DealFields, DealStage, PaymentFields, PaymentStatus, Tables


def _payment_record(record_id="recPAY", due_date="2026-08-28", name="Rent", amount=1200):
    return {"id": record_id, "fields": {
        PaymentFields.NAME: name,
        PaymentFields.AMOUNT: amount,
        PaymentFields.DUE_DATE: due_date,
        PaymentFields.STATUS: PaymentStatus.IN_PROGRESS,
    }}


def test_deal_create_and_update_share_persisted_canonical_stage():
    with patch("crm._creds_ok", return_value=True), \
         patch("crm.airtable_create", return_value={"id": "recDEAL"}) as create:
        crm.crm_add_deal("Deal", "Address", 100, 5)
    assert create.call_args.args[1][DealFields.STATUS] == DealStage.OPPORTUNITY

    with patch("crm.airtable_patch", return_value=True) as update:
        result = crm.crm_update_deal_status("recDEAL", DealStage.CLOSED_LOSS)
    assert DealStage.CLOSED_LOSS in result
    assert update.call_args.args[2] == {DealFields.STATUS: DealStage.CLOSED_LOSS}


def test_legacy_deal_status_normalizes_at_boundary():
    with patch("crm.airtable_patch", return_value=True) as update:
        crm.crm_update_deal_status("recDEAL", "Active")
    assert update.call_args.args[2][DealFields.STATUS] == DealStage.NEGOTIATION


def test_invalid_deal_status_fails_without_write():
    with patch("crm.airtable_patch", return_value=True) as update:
        result = crm.crm_update_deal_status("recDEAL", "not-a-stage")
    assert "לא חוקי" in result
    update.assert_not_called()


def test_deal_list_normalizes_legacy_filter_and_displays_canonical_stage():
    records = [{"id": "recDEAL", "fields": {
        DealFields.NAME: "Deal", DealFields.STAGE: DealStage.NEGOTIATION,
        DealFields.PRICE: 100, DealFields.FUNDING_COST: 5,
    }}]
    with patch("crm._creds_ok", return_value=True), patch("crm._get", return_value=records) as get:
        result = crm.crm_list_deals("Active")
    assert DealStage.NEGOTIATION in result
    assert get.call_args.args[1]


def test_contact_notes_are_rejected_explicitly_when_schema_has_no_notes_field():
    with patch("crm._post") as post:
        result = crm.crm_add_contact("Dana", "0548212778", notes="important")
    assert result.status == "unsupported_field"
    assert "not supported" in result.error
    post.assert_not_called()


def test_typed_upcoming_result_preserves_persisted_due_date_and_public_format():
    record = _payment_record(due_date="2026-08-28")
    with patch("crm._creds_ok", return_value=True), patch("crm._get", return_value=[record]):
        typed = crm.crm_upcoming_payment_records(days_ahead=7)
        text = crm.crm_upcoming_payments(days_ahead=7)
    assert typed[0].due_date == "2026-08-28"
    assert "28/08/26" in text


def test_payment_reminder_consumes_typed_result_without_string_parsing():
    due = (date.today() + timedelta(days=payment_reminder.REMIND_DAYS_BEFORE)).isoformat()
    typed = [crm.PaymentRecord("Rent", 1200, due, "recPAY")]
    with patch("crm.crm_upcoming_payment_records", return_value=typed):
        alerts = payment_reminder.scan_due_soon()
    assert alerts[0].due_date == due
    assert alerts[0].record_id == "recPAY"

    source = Path(payment_reminder.__file__).read_text(encoding="utf-8")
    assert "_parse_upcoming" not in source
    assert "_parse_overdue" not in source


def test_empty_typed_payment_result_preserves_empty_public_behavior():
    with patch("crm._creds_ok", return_value=True), patch("crm._get", return_value=[]):
        assert crm.crm_upcoming_payment_records() == []
        assert "אין תשלומים" in crm.crm_upcoming_payments()
