#!/usr/bin/env python3
"""Deterministic tests for commercial_crm.py — the Canonical Deal / Payment
Architecture writers (create_deal, create_payment_term, create_payment) and
the calculate_payment() calculation contract.

No live Airtable access — tools.airtable_gateway.airtable_create is mocked
throughout. Uses this repo's plain chk()/run() convention (not pytest) so
`python3 test_commercial_crm.py` actually executes under CI's generic
"for f in test_*.py: python3 $f" loop — see .github/workflows/ci.yml.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import commercial_crm as ccrm
from airtable_schema import (
    DealFields,
    PaymentFields,
    PaymentTermCalcType,
    PaymentTermFields,
    Tables,
    VATRule,
)
from tools.airtable_gateway import AirtableCreateOutcome

# Static invariant (Track 8 schema/data-contract reconciliation, 30/08/2026):
# every field constant the three canonical writers below actually put on the
# wire must resolve against the checked-in schema_cache.json snapshot for its
# table. This is a name-only check (the cache carries no types/select
# options — see schema_validator.py) but it does catch a typo'd/renamed
# constant that the writer-contract tests above cannot, since those only
# assert internal consistency (constant in -> same constant out of the mock),
# never truth against the snapshot.
_WRITER_FIELDS: dict[str, list[str]] = {
    Tables.DEALS: [
        DealFields.NAME, DealFields.DOMAIN, DealFields.OWNER, DealFields.STAGE,
        DealFields.ORIGIN_LEAD, DealFields.VENTURE_LINK, DealFields.CONTACTS_LINK,
        DealFields.AMOUNT, DealFields.PRIORITY, DealFields.RISK_LEVEL, DealFields.NOTES,
    ],
    Tables.PAYMENT_TERMS: [
        PaymentTermFields.NAME, PaymentTermFields.DEAL, PaymentTermFields.CALC_TYPE,
        PaymentTermFields.TRIGGER_TYPE, PaymentTermFields.CADENCE, PaymentTermFields.VAT_RULE,
        PaymentTermFields.FIXED_AMOUNT, PaymentTermFields.RATE_PCT, PaymentTermFields.CALC_BASIS,
        PaymentTermFields.TRIGGER_DATE, PaymentTermFields.TRIGGER_DELAY_DAYS,
        PaymentTermFields.START_DATE, PaymentTermFields.END_DATE, PaymentTermFields.NOTES,
    ],
    Tables.PAYMENTS: [
        PaymentFields.AMOUNT, PaymentFields.DOMAIN, PaymentFields.STATUS, PaymentFields.OWNER,
        PaymentFields.REF, PaymentFields.DATE, PaymentFields.DEAL_LINK, PaymentFields.PAYMENT_TERM,
        PaymentFields.ORIGIN_LEAD, PaymentFields.BASE_AMOUNT, PaymentFields.RATE_PCT,
        PaymentFields.VAT_RULE, PaymentFields.VAT_AMOUNT, PaymentFields.TRIGGER_EVIDENCE,
        PaymentFields.NOTES,
    ],
}


def _check_snapshot_fidelity(chk) -> None:
    cache = json.loads((Path(__file__).parent / "schema_cache.json").read_text(encoding="utf-8"))
    tables = cache.get("tables", {})
    for table, field_constants in _WRITER_FIELDS.items():
        known = set(tables.get(table, []))
        chk(f"snapshot: {table!r} present in schema_cache.json", bool(known))
        for field in field_constants:
            chk(f"snapshot: {table!r} field {field!r} resolves in schema_cache.json", field in known)


def _created(record_id: str) -> AirtableCreateOutcome:
    return AirtableCreateOutcome("created", {"id": record_id})


def run() -> bool:
    passed = failed = 0

    def chk(desc: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            print(f"PASS {desc}")
            passed += 1
        else:
            print(f"FAIL {desc}")
            failed += 1

    # ── calculate_payment — calculation contract ──────────────────

    r = ccrm.calculate_payment("fixed", fixed_amount=1000, vat_rule=VATRule.NONE)
    chk("fixed/no-VAT: calculated == fixed_amount", r["calculated_amount"] == 1000.0)
    chk("fixed/no-VAT: vat_amount == 0", r["vat_amount"] == 0.0)
    chk("fixed/no-VAT: total == calculated", r["total_amount"] == 1000.0)

    r = ccrm.calculate_payment("percentage", rate_pct=15, basis_value=10000, vat_rule=VATRule.ADD)
    chk("percentage/VAT-add: base_amount == basis_value", r["base_amount"] == 10000.0)
    chk("percentage/VAT-add: calculated == 15% of basis", r["calculated_amount"] == 1500.0)
    chk("percentage/VAT-add: vat_amount == calculated * 0.18", r["vat_amount"] == 270.0)
    chk("percentage/VAT-add: total == calculated + vat", r["total_amount"] == 1770.0)

    r = ccrm.calculate_payment("percentage", rate_pct=10, basis_value=1180, vat_rule=VATRule.INCLUDED)
    chk("percentage/VAT-included: calculated unchanged", r["calculated_amount"] == 118.0)
    chk("percentage/VAT-included: vat_amount backed out", r["vat_amount"] == 18.0)
    chk("percentage/VAT-included: total == calculated (VAT not added again)", r["total_amount"] == 118.0)

    try:
        ccrm.calculate_payment("bogus")
        chk("unknown calc_type raises ValueError", False)
    except ValueError:
        chk("unknown calc_type raises ValueError", True)

    try:
        ccrm.calculate_payment("fixed", fixed_amount=100, vat_rule="bogus")
        chk("unknown vat_rule raises ValueError", False)
    except ValueError:
        chk("unknown vat_rule raises ValueError", True)

    # ── create_deal ────────────────────────────────────────────────

    with patch("commercial_crm.airtable_create") as create:
        r1 = ccrm.create_deal("", "real_estate", "recOwner")
        r2 = ccrm.create_deal("Name", "", "recOwner")
        r3 = ccrm.create_deal("Name", "real_estate", "")
        chk("create_deal: empty name blocked", r1["ok"] is False)
        chk("create_deal: empty domain blocked", r2["ok"] is False)
        chk("create_deal: empty owner_id blocked", r3["ok"] is False)
        chk("create_deal: no write attempted when validation fails", not create.called)

    with patch("commercial_crm.airtable_create", return_value=_created("recDEAL1")) as create:
        result = ccrm.create_deal(
            "New Deal", "saas", "recOwner1",
            origin_lead_id="recLead1", venture_id="recVenture1",
            contact_ids=["recContact1"], amount=5000,
        )
        table, fields = create.call_args.args[0], create.call_args.args[1]
        chk("create_deal: ok=True on success", result["ok"] is True)
        chk("create_deal: external_id == created record id", result["external_id"] == "recDEAL1")
        chk("create_deal: writes to Tables.DEALS", table == Tables.DEALS)
        chk("create_deal: Owner written as list", fields[DealFields.OWNER] == ["recOwner1"])
        chk("create_deal: Origin Lead written as list", fields[DealFields.ORIGIN_LEAD] == ["recLead1"])
        chk("create_deal: Ventures written as list", fields[DealFields.VENTURE_LINK] == ["recVenture1"])
        chk("create_deal: Contacts written as list", fields[DealFields.CONTACTS_LINK] == ["recContact1"])
        chk("create_deal: Domain written", fields[DealFields.DOMAIN] == "saas")
        chk("create_deal: never writes Address (real-estate-only)", DealFields.ADDRESS not in fields)
        chk("create_deal: never writes Funding Cost (real-estate-only)", DealFields.FUNDING_COST not in fields)
        chk("create_deal: never writes Roi (real-estate-only)", DealFields.ROI not in fields)

    with patch("commercial_crm.airtable_create", return_value=AirtableCreateOutcome("failed", error="422")):
        result = ccrm.create_deal("Name", "general", "recOwner")
        chk("create_deal: failed provider outcome → ok=False", result["ok"] is False)

    # ── create_deal: BUG-CRM-BYPASS-DOMAIN-SELECT-CASING ──────────────
    # Live production canary #10 (02/09/2026): "צור עסקה בשם X בתחום Import"
    # correctly resolved to the canonical slug "import" (BUG-CRM-BYPASS-
    # DOMAIN-TRANSLATION's fix works), but writing "import" straight to
    # Airtable's Domain single-select 422'd -- the live configured option
    # is "Import" (capital). resolve_live_select_value() is the missing
    # persistence-boundary mapping step; these tests prove create_deal()
    # actually calls it and respects both outcomes.
    with patch("commercial_crm.airtable_create", return_value=_created("recDEAL2")) as create, \
         patch("core.runtime_schema_provider.resolve_live_select_value", return_value="Import") as resolve:
        result = ccrm.create_deal("Canary Deal", "import", "recOwner1")
        table, fields = create.call_args.args[0], create.call_args.args[1]
        chk("create_deal: resolve_live_select_value called with the canonical slug",
            resolve.call_args.args == (Tables.DEALS, DealFields.DOMAIN, "import"))
        chk("create_deal: the LIVE resolved value is written, not the raw canonical slug",
            fields[DealFields.DOMAIN] == "Import")
        chk("create_deal: succeeds once the live value resolves", result["ok"] is True)

    with patch("commercial_crm.airtable_create") as create, \
         patch("core.runtime_schema_provider.resolve_live_select_value", return_value=None):
        result = ccrm.create_deal("Canary Deal", "שטויות", "recOwner1")
        chk("create_deal: an unresolvable domain fails closed (ok=False)", result["ok"] is False)
        chk("create_deal: never reaches Airtable for an unresolvable domain", not create.called)

    # ── create_payment_term ──────────────────────────────────────────

    with patch("commercial_crm.airtable_create") as create:
        result = ccrm.create_payment_term("", "Term", PaymentTermCalcType.FIXED, fixed_amount=100)
        chk("create_payment_term: missing deal_id blocked", result["ok"] is False)
        chk("create_payment_term: no write on missing deal_id", not create.called)

    with patch("commercial_crm.airtable_create") as create:
        result = ccrm.create_payment_term("recDeal1", "Term", PaymentTermCalcType.FIXED)
        chk("create_payment_term: fixed type requires fixed_amount", result["ok"] is False)
        chk("create_payment_term: no write on missing fixed_amount", not create.called)

    with patch("commercial_crm.airtable_create") as create:
        result = ccrm.create_payment_term(
            "recDeal1", "Term", PaymentTermCalcType.PERCENTAGE, rate_pct=15,
        )  # missing calc_basis
        chk("create_payment_term: percentage type requires calc_basis", result["ok"] is False)
        chk("create_payment_term: no write on missing calc_basis", not create.called)

    with patch("commercial_crm.airtable_create", return_value=_created("recTERM1")) as create:
        result = ccrm.create_payment_term(
            "recDeal1", "Commission", PaymentTermCalcType.PERCENTAGE,
            rate_pct=15, calc_basis="deal_amount",
        )
        table, fields = create.call_args.args[0], create.call_args.args[1]
        chk("create_payment_term: ok=True on success", result["ok"] is True)
        chk("create_payment_term: external_id == created record id", result["external_id"] == "recTERM1")
        chk("create_payment_term: writes to Tables.PAYMENT_TERMS", table == Tables.PAYMENT_TERMS)
        chk("create_payment_term: child writes Deal link (provenance)", fields[PaymentTermFields.DEAL] == ["recDeal1"])

    # ── create_payment ───────────────────────────────────────────────

    with patch("commercial_crm.airtable_create") as create:
        chk("create_payment: zero amount blocked", ccrm.create_payment(0, "general", "recOwner")["ok"] is False)
        chk("create_payment: negative amount blocked", ccrm.create_payment(-5, "general", "recOwner")["ok"] is False)
        chk("create_payment: empty domain blocked", ccrm.create_payment(100, "", "recOwner")["ok"] is False)
        chk("create_payment: empty owner_id blocked", ccrm.create_payment(100, "general", "")["ok"] is False)
        chk("create_payment: no write attempted when validation fails", not create.called)

    with patch("commercial_crm.airtable_create", return_value=_created("recPAY1")) as create:
        result = ccrm.create_payment(500, "general", "recOwner1")
        fields = create.call_args.args[1]
        chk("create_payment: ok=True with no deal at all (Payment does not depend on Deal)", result["ok"] is True)
        chk("create_payment: no Deal link written when omitted", PaymentFields.DEAL_LINK not in fields)
        chk("create_payment: no Payment Term link written when omitted", PaymentFields.PAYMENT_TERM not in fields)

    calc = ccrm.calculate_payment("percentage", rate_pct=15, basis_value=10000, vat_rule=VATRule.ADD)
    with patch("commercial_crm.airtable_create", return_value=_created("recPAY2")) as create:
        result = ccrm.create_payment(
            calc["total_amount"], "real_estate", "recOwner1",
            deal_id="recDeal1", payment_term_id="recTerm1",
            base_amount=calc["base_amount"], rate_pct=15,
            vat_rule=VATRule.ADD, vat_amount=calc["vat_amount"],
        )
        fields = create.call_args.args[1]
        chk("create_payment: amount == calculated total (authoritative field)", fields[PaymentFields.AMOUNT] == 1770.0)
        chk("create_payment: Base Amount snapshot written", fields[PaymentFields.BASE_AMOUNT] == 10000.0)
        chk("create_payment: Rate % snapshot written", fields[PaymentFields.RATE_PCT] == 15)
        chk("create_payment: VAT Rule snapshot written", fields[PaymentFields.VAT_RULE] == VATRule.ADD)
        chk("create_payment: VAT Amount snapshot written", fields[PaymentFields.VAT_AMOUNT] == 270.0)
        chk("create_payment: Deal link written as list", fields[PaymentFields.DEAL_LINK] == ["recDeal1"])
        chk("create_payment: Payment Term link written as list", fields[PaymentFields.PAYMENT_TERM] == ["recTerm1"])

    with patch("commercial_crm.airtable_create", return_value=_created("recPAY3")) as create:
        ccrm.create_payment(200, "general", "recOwner1", origin_lead_id="recLead9")
        fields = create.call_args.args[1]
        chk("create_payment: Origin Lead written as list when given", fields[PaymentFields.ORIGIN_LEAD] == ["recLead9"])

    # ── create_payment: BUG-CRM-BYPASS-DOMAIN-SELECT-CASING follow-up ──
    with patch("commercial_crm.airtable_create", return_value=_created("recPAY4")) as create, \
         patch("core.runtime_schema_provider.resolve_live_select_value", return_value="Import") as resolve:
        result = ccrm.create_payment(100, "import", "recOwner1")
        fields = create.call_args.args[1]
        chk("create_payment: resolve_live_select_value called with the canonical slug",
            resolve.call_args.args == (Tables.PAYMENTS, PaymentFields.DOMAIN, "import"))
        chk("create_payment: the LIVE resolved value is written, not the raw canonical slug",
            fields[PaymentFields.DOMAIN] == "Import")
        chk("create_payment: succeeds once the live value resolves", result["ok"] is True)

    with patch("commercial_crm.airtable_create") as create, \
         patch("core.runtime_schema_provider.resolve_live_select_value", return_value=None):
        result = ccrm.create_payment(100, "שטויות", "recOwner1")
        chk("create_payment: an unresolvable domain fails closed (ok=False)", result["ok"] is False)
        chk("create_payment: never reaches Airtable for an unresolvable domain", not create.called)

    _check_snapshot_fidelity(chk)

    print(f"\n{'='*40}")
    print(f"commercial_crm Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    ok = run()
    exit(0 if ok else 1)
