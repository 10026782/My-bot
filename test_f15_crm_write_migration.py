"""Focused F15 proof: crm.py writes use the canonical Airtable gateway."""

from pathlib import Path
from unittest.mock import patch

import crm
from airtable_schema import DealFields, DealStage, DealStatus, PaymentFields, PaymentStatus, RiskLevel, Tables


def test_crm_create_uses_gateway_and_preserves_record_id():
    with patch("crm._creds_ok", return_value=True), \
            patch("crm.airtable_create", return_value={"id": "recDEAL"}) as create:
        result = crm.crm_add_deal("Deal", "Address", 100, 5)

    assert "recDEAL" in result
    create.assert_called_once()
    table, fields = create.call_args.args[:2]
    assert table == Tables.DEALS
    assert fields == {
        DealFields.NAME: "Deal",
        DealFields.ADDRESS: "Address",
        DealFields.STATUS: DealStage.OPPORTUNITY,
        DealFields.PRICE: 100,
        DealFields.FUNDING_COST: 5,
        DealFields.ROI: 15.0,
        DealFields.RISK_LEVEL: RiskLevel.MEDIUM,
    }
    assert create.call_args.kwargs["source"] == "crm"


def test_crm_update_uses_gateway_with_record_id():
    with patch("crm.airtable_patch", return_value=True) as update:
        result = crm.crm_update_deal_status("recDEAL", "Active", "note")

    assert "recDEAL" in result
    update.assert_called_once_with(
        Tables.DEALS,
        "recDEAL",
        {DealFields.STATUS: DealStage.NEGOTIATION, DealFields.NOTES: "note"},
        source="crm",
    )


def test_crm_payment_create_and_update_use_gateway():
    with patch("crm._creds_ok", return_value=True), \
            patch("crm.airtable_create", return_value={"id": "recPAY"}) as create:
        result = crm.crm_add_payment("Payment", 50, "2026-08-20")
    assert "recPAY" in result
    assert create.call_args.args[0] == Tables.PAYMENTS
    assert create.call_args.args[1][PaymentFields.AMOUNT] == 50

    with patch("crm.airtable_patch", return_value=True) as update:
        result = crm.crm_mark_payment_paid("recPAY")
    assert "recPAY" in result
    update.assert_called_once_with(
        Tables.PAYMENTS,
        "recPAY",
        {PaymentFields.STATUS: PaymentStatus.PAID},
        source="crm",
    )


def test_crm_has_no_direct_airtable_http_writes():
    source = Path(crm.__file__).read_text(encoding="utf-8")
    assert "httpx.post" not in source
    assert "httpx.patch" not in source


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
    print("test_f15_crm_write_migration: PASS")
