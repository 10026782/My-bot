# commercial_crm.py — Canonical Deal / Payment Architecture
#
# Channel-agnostic writers for the unified commercial model (Deal / Payment
# Term / Payment). No Telegram/WhatsApp/TMA-specific logic lives here — every
# function is callable identically from the agent, the scheduler, or a
# future channel. All writes route through tools.airtable_gateway (single
# write path — no direct httpx calls).
#
# INTERNAL PER-RECORD AUTHORIZATION = DEFERRED / KNOWN GAP. `owner_id` below
# is business ownership metadata only — it is NOT an authorization boundary.
# No caller of these writers may assume that setting `owner_id` restricts who
# can later read or act on the created record (see the Unified CRM Commercial
# Model audit, 30/08/2026, for the full Eliyahu/Avi scenario this defers).
#
# These are the ONLY canonical writers for Deal/PaymentTerm/Payment creation.
# The legacy crm.py functions (crm_add_deal, crm_add_payment, ...) are
# orphaned/real-estate-shaped and are intentionally NOT reused or revived as
# a parallel path — do not call them from new code.

from __future__ import annotations

from typing import Any

from airtable_schema import (
    DealFields,
    DealStage,
    PaymentFields,
    PaymentStatus,
    PaymentTermCadence,
    PaymentTermCalcType,
    PaymentTermFields,
    PaymentTermTrigger,
    Tables,
    VATRule,
)
from tools.airtable_gateway import airtable_create
from tools.airtable_tools import _tool_result

# Israel VAT rate used by the VATRule.ADD/INCLUDED calculation branches.
# A plain business constant, not fetched dynamically — update here if the
# statutory rate changes.
VAT_RATE = 0.18


# ══════════════════════════════════════════════════
# Calculation contract
# ══════════════════════════════════════════════════

def calculate_payment(
    calc_type: str,
    *,
    fixed_amount: float | None = None,
    rate_pct: float | None = None,
    basis_value: float | None = None,
    vat_rule: str = VATRule.NONE,
) -> dict[str, float]:
    """Pure calculation — no Airtable access, no side effects.

    fixed   → calculated_amount = fixed_amount
    percentage → calculated_amount = basis_value * rate_pct / 100

    Callers resolve basis_value themselves (e.g. look up a Deal's Amount for
    calc_basis="deal_amount", or supply an externally-known salary figure for
    "monthly_salary"/"first_salary") — this function never reaches into
    other tables.

    VAT none     → vat_amount = 0, total = calculated_amount
    VAT add      → vat_amount = calculated_amount * VAT_RATE, total = calculated_amount + vat_amount
    VAT included → calculated_amount already includes VAT; vat_amount is backed out, total = calculated_amount

    Returns {base_amount, calculated_amount, vat_amount, total_amount}, all
    rounded to 2 decimals. Result is meant to be snapshotted verbatim onto a
    Payment record at creation time — see PaymentFields.BASE_AMOUNT/RATE_PCT/
    VAT_RULE/VAT_AMOUNT. Never recompute or overwrite those fields after the
    fact from a possibly-since-edited Payment Term.
    """
    if calc_type == PaymentTermCalcType.FIXED:
        base_amount = float(fixed_amount or 0)
        calculated_amount = base_amount
    elif calc_type == PaymentTermCalcType.PERCENTAGE:
        base_amount = float(basis_value or 0)
        calculated_amount = base_amount * float(rate_pct or 0) / 100
    else:
        raise ValueError(f"unknown calculation type: {calc_type!r}")

    if vat_rule == VATRule.NONE:
        vat_amount = 0.0
        total_amount = calculated_amount
    elif vat_rule == VATRule.ADD:
        vat_amount = calculated_amount * VAT_RATE
        total_amount = calculated_amount + vat_amount
    elif vat_rule == VATRule.INCLUDED:
        vat_amount = calculated_amount - (calculated_amount / (1 + VAT_RATE))
        total_amount = calculated_amount
    else:
        raise ValueError(f"unknown VAT rule: {vat_rule!r}")

    return {
        "base_amount": round(base_amount, 2),
        "calculated_amount": round(calculated_amount, 2),
        "vat_amount": round(vat_amount, 2),
        "total_amount": round(total_amount, 2),
    }


# ══════════════════════════════════════════════════
# Writers
# ══════════════════════════════════════════════════

def create_deal(
    name: str,
    domain: str,
    owner_id: str,
    *,
    origin_lead_id: str = "",
    venture_id: str = "",
    contact_ids: list[str] | None = None,
    amount: float | None = None,
    stage: str = DealStage.OPPORTUNITY,
    priority: str = "",
    risk_level: str = "",
    notes: str = "",
    source: str = "commercial_crm",
) -> dict:
    """Create a Deal. Domain-agnostic — no real-estate-only fields are required
    (Address/Funding Cost/Roi stay real-estate-only and are never written here)."""
    if not name or not name.strip():
        return _tool_result(ok=False, tool="crm_create_deal", user_message="❌ שם עסקה חסר.")
    if not domain:
        return _tool_result(ok=False, tool="crm_create_deal", user_message="❌ domain חסר.")
    if not owner_id:
        return _tool_result(ok=False, tool="crm_create_deal", user_message="❌ owner_id חסר.")

    fields: dict[str, Any] = {
        DealFields.NAME: name.strip(),
        DealFields.DOMAIN: domain,
        DealFields.OWNER: [owner_id],
        DealFields.STAGE: stage,
    }
    if origin_lead_id:
        fields[DealFields.ORIGIN_LEAD] = [origin_lead_id]
    if venture_id:
        fields[DealFields.VENTURE_LINK] = [venture_id]
    if contact_ids:
        fields[DealFields.CONTACTS_LINK] = list(contact_ids)
    if amount is not None:
        fields[DealFields.AMOUNT] = amount
    if priority:
        fields[DealFields.PRIORITY] = priority
    if risk_level:
        fields[DealFields.RISK_LEVEL] = risk_level
    if notes:
        fields[DealFields.NOTES] = notes

    outcome = airtable_create(Tables.DEALS, fields, source=source, return_outcome=True)
    if outcome.status == "created":
        rec_id = outcome.record.get("id", "")
        return _tool_result(
            ok=True, tool="crm_create_deal", external_id=rec_id,
            evidence={"record_id": rec_id, "table": Tables.DEALS, "fields": fields},
            user_message=f"✅ עסקה נוצרה | ID: {rec_id}",
        )
    return _tool_result(
        ok=False, tool="crm_create_deal",
        evidence={"table": Tables.DEALS, "status": outcome.status},
        user_message=f"❌ יצירת עסקה נכשלה: {outcome.error or 'בדוק שמות שדות.'}",
    )


def create_payment_term(
    deal_id: str,
    name: str,
    calc_type: str,
    *,
    fixed_amount: float | None = None,
    rate_pct: float | None = None,
    calc_basis: str = "",
    trigger_type: str = PaymentTermTrigger.IMMEDIATE,
    trigger_date: str = "",
    trigger_delay_days: int | None = None,
    cadence: str = PaymentTermCadence.ONCE,
    vat_rule: str = VATRule.NONE,
    start_date: str = "",
    end_date: str = "",
    notes: str = "",
    source: str = "commercial_crm",
) -> dict:
    """Create a Payment Term attached to an existing Deal. A Payment Term is
    never created standalone — deal_id is required."""
    if not deal_id:
        return _tool_result(
            ok=False, tool="crm_create_payment_term",
            user_message="❌ Payment Term חייב להיות מקושר לעסקה קיימת (deal_id).",
        )
    if calc_type not in (PaymentTermCalcType.FIXED, PaymentTermCalcType.PERCENTAGE):
        return _tool_result(
            ok=False, tool="crm_create_payment_term",
            user_message=f"❌ calculation type לא תקין: {calc_type!r}",
        )
    if calc_type == PaymentTermCalcType.FIXED and not fixed_amount:
        return _tool_result(
            ok=False, tool="crm_create_payment_term",
            user_message="❌ calculation type=fixed דורש fixed_amount.",
        )
    if calc_type == PaymentTermCalcType.PERCENTAGE and (rate_pct is None or not calc_basis):
        return _tool_result(
            ok=False, tool="crm_create_payment_term",
            user_message="❌ calculation type=percentage דורש rate_pct + calc_basis.",
        )

    fields: dict[str, Any] = {
        PaymentTermFields.NAME: (name or "").strip() or "Payment Term",
        PaymentTermFields.DEAL: [deal_id],
        PaymentTermFields.CALC_TYPE: calc_type,
        PaymentTermFields.TRIGGER_TYPE: trigger_type,
        PaymentTermFields.CADENCE: cadence,
        PaymentTermFields.VAT_RULE: vat_rule,
    }
    if fixed_amount is not None:
        fields[PaymentTermFields.FIXED_AMOUNT] = fixed_amount
    if rate_pct is not None:
        fields[PaymentTermFields.RATE_PCT] = rate_pct
    if calc_basis:
        fields[PaymentTermFields.CALC_BASIS] = calc_basis
    if trigger_date:
        fields[PaymentTermFields.TRIGGER_DATE] = trigger_date
    if trigger_delay_days is not None:
        fields[PaymentTermFields.TRIGGER_DELAY_DAYS] = trigger_delay_days
    if start_date:
        fields[PaymentTermFields.START_DATE] = start_date
    if end_date:
        fields[PaymentTermFields.END_DATE] = end_date
    if notes:
        fields[PaymentTermFields.NOTES] = notes

    outcome = airtable_create(Tables.PAYMENT_TERMS, fields, source=source, return_outcome=True)
    if outcome.status == "created":
        rec_id = outcome.record.get("id", "")
        return _tool_result(
            ok=True, tool="crm_create_payment_term", external_id=rec_id,
            evidence={"record_id": rec_id, "table": Tables.PAYMENT_TERMS, "fields": fields},
            user_message=f"✅ Payment Term נוצר | ID: {rec_id}",
        )
    return _tool_result(
        ok=False, tool="crm_create_payment_term",
        evidence={"table": Tables.PAYMENT_TERMS, "status": outcome.status},
        user_message=f"❌ יצירת Payment Term נכשלה: {outcome.error or 'בדוק שמות שדות.'}",
    )


def create_payment(
    amount: float,
    domain: str,
    owner_id: str,
    *,
    deal_id: str = "",
    payment_term_id: str = "",
    origin_lead_id: str = "",
    reference: str = "",
    due_date: str = "",
    base_amount: float | None = None,
    rate_pct: float | None = None,
    vat_rule: str = VATRule.NONE,
    vat_amount: float | None = None,
    trigger_evidence: str = "",
    notes: str = "",
    source: str = "commercial_crm",
) -> dict:
    """Create a Payment. `amount` is always the final payable/total amount —
    the authoritative field every existing reader (crm_mark_payment_paid,
    scheduler jobs) already relies on.

    base_amount/rate_pct/vat_rule/vat_amount are an optional provenance
    snapshot — pass the dict returned by calculate_payment() when this
    Payment was generated from a Payment Term. They are written as plain
    values, never formulas, so editing the Term afterward cannot change a
    Payment already created from it.

    A Payment does not require a Deal — deal_id/payment_term_id are both
    optional, matching the deliberate "do not make Payment depend on Deal"
    constraint from the Unified CRM Commercial Model audit.
    """
    if amount is None or amount <= 0:
        return _tool_result(ok=False, tool="crm_create_payment", user_message="❌ סכום תשלום לא תקין.")
    if not domain:
        return _tool_result(ok=False, tool="crm_create_payment", user_message="❌ domain חסר.")
    if not owner_id:
        return _tool_result(ok=False, tool="crm_create_payment", user_message="❌ owner_id חסר.")

    fields: dict[str, Any] = {
        PaymentFields.AMOUNT: amount,
        PaymentFields.DOMAIN: domain,
        PaymentFields.STATUS: PaymentStatus.PENDING,
        PaymentFields.OWNER: [owner_id],
    }
    if reference:
        fields[PaymentFields.REF] = reference
    if due_date:
        fields[PaymentFields.DATE] = due_date
    if deal_id:
        fields[PaymentFields.DEAL_LINK] = [deal_id]
    if payment_term_id:
        fields[PaymentFields.PAYMENT_TERM] = [payment_term_id]
    if origin_lead_id:
        fields[PaymentFields.ORIGIN_LEAD] = [origin_lead_id]
    if base_amount is not None:
        fields[PaymentFields.BASE_AMOUNT] = base_amount
    if rate_pct is not None:
        fields[PaymentFields.RATE_PCT] = rate_pct
    if vat_rule:
        fields[PaymentFields.VAT_RULE] = vat_rule
    if vat_amount is not None:
        fields[PaymentFields.VAT_AMOUNT] = vat_amount
    if trigger_evidence:
        fields[PaymentFields.TRIGGER_EVIDENCE] = trigger_evidence
    if notes:
        fields[PaymentFields.NOTES] = notes

    outcome = airtable_create(Tables.PAYMENTS, fields, source=source, return_outcome=True)
    if outcome.status == "created":
        rec_id = outcome.record.get("id", "")
        return _tool_result(
            ok=True, tool="crm_create_payment", external_id=rec_id,
            evidence={"record_id": rec_id, "table": Tables.PAYMENTS, "fields": fields},
            user_message=f"✅ תשלום נוצר | ID: {rec_id}",
        )
    return _tool_result(
        ok=False, tool="crm_create_payment",
        evidence={"table": Tables.PAYMENTS, "status": outcome.status},
        user_message=f"❌ יצירת תשלום נכשלה: {outcome.error or 'בדוק שמות שדות.'}",
    )
