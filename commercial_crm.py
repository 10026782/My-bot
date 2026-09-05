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
# These are the canonical commercial creation writers. S2B adds only universal
# Organization resolution, Charge creation, and Charge-required actual-movement
# Payment creation; the legacy Payment writer below remains quarantined.
# The legacy crm.py functions (crm_add_deal, crm_add_payment, ...) are
# orphaned/real-estate-shaped and are intentionally NOT reused or revived as
# a parallel path — do not call them from new code.

from __future__ import annotations

from datetime import date
import math
import re
import threading
from typing import Any

from airtable_schema import (
    ChargeFields,
    ChargeStatus,
    CollectionState,
    ContactFields,
    Currency,
    DealFields,
    DealStage,
    Direction,
    DocumentRequirement,
    DocumentStatus,
    OrganizationFields,
    PaymentFields,
    PaymentStatus,
    PaymentTermCadence,
    PaymentTermCalcType,
    PaymentTermFields,
    PaymentTermTrigger,
    Tables,
    VATRule,
)
import crm
from tools.airtable_gateway import airtable_create, escape_formula_value
from tools.airtable_read_adapter import get_record_fields, list_records
from tools.airtable_tools import _tool_result

# Israel VAT rate used by the VATRule.ADD/INCLUDED calculation branches.
# A plain business constant, not fetched dynamically — update here if the
# statutory rate changes.
VAT_RATE = 0.18

_RECORD_ID_RE = re.compile(r"^rec[A-Za-z0-9]{14}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ORGANIZATION_WRITE_LOCK = threading.RLock()


def _enum_values(namespace: type) -> frozenset[str]:
    return frozenset(
        value for name, value in vars(namespace).items()
        if name.isupper() and isinstance(value, str)
    )


_DIRECTIONS = _enum_values(Direction)
_CURRENCIES = _enum_values(Currency)
_CHARGE_STATUSES = _enum_values(ChargeStatus)
_COLLECTION_STATES = _enum_values(CollectionState)
_VAT_RULES = _enum_values(VATRule)
_DOCUMENT_REQUIREMENTS = _enum_values(DocumentRequirement)
_DOCUMENT_STATUSES = _enum_values(DocumentStatus)


def normalize_organization_name(value: str) -> tuple[str, str]:
    """Return (display spelling, deterministic comparison key)."""
    if not isinstance(value, str):
        return "", ""
    display_name = " ".join(value.split())
    return display_name, display_name.casefold()


def _valid_record_id(value: object) -> bool:
    return isinstance(value, str) and bool(_RECORD_ID_RE.fullmatch(value))


def _valid_number(value: object, *, positive: bool = False) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and (number > 0 if positive else number >= 0)


def _valid_iso_date(value: object) -> bool:
    if not isinstance(value, str) or not _ISO_DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _link_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        record_id = item.get("id", "") if isinstance(item, dict) else item
        if isinstance(record_id, str) and record_id:
            result.append(record_id)
    return result


def _read_fields(table: str, record_id: str, entity_label: str) -> tuple[dict | None, str]:
    if not _valid_record_id(record_id):
        return None, f"{entity_label} record id is invalid."
    try:
        return get_record_fields(table, record_id), ""
    except Exception:
        return None, f"{entity_label} record does not exist or could not be verified."


def _write_result(tool: str, table: str, fields: dict[str, Any], source: str) -> dict:
    outcome = airtable_create(table, fields, source=source, return_outcome=True)
    if outcome.status == "created":
        record_id = outcome.record.get("id", "")
        return _tool_result(
            ok=True,
            tool=tool,
            external_id=record_id,
            evidence={"record_id": record_id, "table": table, "fields": fields},
            user_message="✅ הרשומה המסחרית נוצרה.",
        )
    return _tool_result(
        ok=False,
        tool=tool,
        evidence={"table": table, "status": outcome.status},
        user_message=f"❌ יצירת הרשומה נכשלה: {outcome.error or 'בדוק את חוזה השדות.'}",
    )


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

def lookup_human_reference(
    entity: str, query: str, *, scope: str, identity=None, limit: int = 6,
) -> list[dict]:
    """Bounded exact-label lookup for the completion presentation adapter.

    This is read-only and returns provider records only to the internal
    resolver boundary.  User-facing code receives labels/choices, never IDs.

    Identity/domain scope is enforced through the same canonical gate every
    other Airtable read uses — tools.airtable_security.enforce_tenant_scope,
    called the same way tools/dispatcher.py calls it for "airtable_get" — so
    a partner is restricted to their allowed_domains (or blocked outright for
    tables that gate has no domain field for, e.g. Contacts), an external
    client/supplier is restricted to their tenant_id, and an internal
    owner/manager/employee passes through with only the query's own SEARCH()
    filter (no additional tenant/domain filter — same as every other internal
    read). Missing identity, an unresolvable scope, a blank query, or a
    TenantScopeViolation all fail closed to no results — never the full
    table.
    """
    table_by_entity = {
        "contact": Tables.CONTACTS, "organization": Tables.ORGANIZATIONS,
        "deal": Tables.DEALS, "payment_term": Tables.PAYMENT_TERMS,
        "charge": Tables.CHARGES,
    }
    field_by_entity = {
        "contact": ContactFields.NAME, "organization": OrganizationFields.NAME,
        "deal": DealFields.NAME, "payment_term": PaymentTermFields.NAME,
        "charge": ChargeFields.REFERENCE,
    }
    table = table_by_entity.get(entity)
    field_name = field_by_entity.get(entity)
    needle = " ".join(str(query or "").casefold().split())
    if not table or not field_name or not scope or limit < 1 or identity is None or not needle:
        return []
    from tools.airtable_security import TenantScopeViolation, enforce_tenant_scope
    # BUG-DIAMOND-CONTACT-SEARCH-BOUNDED (production-reported, 05/09/2026):
    # this used to send no query to Airtable at all — for an internal
    # identity enforce_tenant_scope() applies no filter, so the call fetched
    # only the first `limit + 1` records in default table order and matched
    # client-side; a real contact past those first rows was invisible no
    # matter how exact the name match was. A SEARCH() pre-filter (same
    # combining mechanism every other enforce_tenant_scope() call site
    # already relies on — AND'd with any tenant/domain filter, never
    # replacing it) now makes the actual query constrain what Airtable
    # returns; the client-side casefold/whitespace-normalized exact match
    # below remains the authoritative disambiguator, unchanged.
    search_formula = f"SEARCH('{escape_formula_value(needle)}', LOWER({{{field_name}}}))"
    try:
        secured_params = enforce_tenant_scope(
            "airtable_get", identity, {"table": table, "filterByFormula": search_formula},
        )
    except TenantScopeViolation:
        return []
    records = list_records(
        table, secured_params.get("filterByFormula", ""),
        max_records=limit + 1, fields=[field_name], paginate=False,
    )
    matches = []
    for record in records:
        fields = record.get("fields", {})
        label = " ".join(str(fields.get(field_name, "")).casefold().split())
        if label == needle:
            matches.append(record)
    return matches[:limit]

def find_or_create_organization(
    organization_name: str,
    *,
    source: str = "commercial_crm",
) -> dict:
    """Resolve the universal Organization by normalized name, or create it.

    Organization Name is the current approved deterministic key, not a claim
    that names are permanently sufficient identifiers. Matching is exact after
    whitespace normalization and case-folding; fuzzy/substring matching is
    deliberately absent.
    """
    tool = "crm_find_or_create_organization"
    display_name, normalized_name = normalize_organization_name(organization_name)
    if not normalized_name:
        return _tool_result(
            ok=False, tool=tool,
            user_message="❌ Organization Name must be non-empty.",
        )

    # The lock closes the in-process read/create race. Cross-process retries of
    # one approved business action are additionally owned by ActionGateway's
    # canonical fingerprint/idempotency contract.
    with _ORGANIZATION_WRITE_LOCK:
        try:
            records = list_records(
                Tables.ORGANIZATIONS,
                max_records=None,
                fields=[OrganizationFields.NAME],
                paginate=True,
            )
        except Exception:
            return _tool_result(
                ok=False, tool=tool,
                evidence={"table": Tables.ORGANIZATIONS},
                user_message="❌ Organization lookup could not be verified; no record was created.",
            )

        matches = []
        for record in records:
            existing_name = record.get("fields", {}).get(OrganizationFields.NAME, "")
            _, existing_key = normalize_organization_name(existing_name)
            if existing_key == normalized_name:
                matches.append(record)

        if len(matches) > 1:
            return _tool_result(
                ok=False, tool=tool,
                evidence={"table": Tables.ORGANIZATIONS, "match_count": len(matches)},
                user_message="❌ Organization Name is ambiguous; multiple canonical records match.",
            )
        if matches:
            record_id = matches[0].get("id", "")
            if not _valid_record_id(record_id):
                return _tool_result(
                    ok=False, tool=tool,
                    evidence={"table": Tables.ORGANIZATIONS},
                    user_message="❌ The matching Organization has no valid record identity.",
                )
            return _tool_result(
                ok=True,
                tool=tool,
                external_id=record_id,
                evidence={"record_id": record_id, "table": Tables.ORGANIZATIONS, "action": "reused"},
                user_message="✅ הארגון הקיים נמצא ונעשה בו שימוש חוזר.",
            )

        return _write_result(
            tool,
            Tables.ORGANIZATIONS,
            {OrganizationFields.NAME: display_name},
            source,
        )


def find_or_create_contact(
    name: str,
    *,
    phone: str = "",
    email: str = "",
    company: str = "",
    role_category: str = "",
    identity=None,
    source: str = "commercial_crm",
) -> dict:
    """Resolve or create a canonical Contact for S2C nested completion.

    Thin adapter over crm.create_contact_from_fields() — the one existing
    Contact writer this repo has (dedup-aware: matches by normalized phone
    before creating, per BUG-LEAD-03-class's ContactResult contract). No
    second writer: this function only translates between the Commercial V2
    primitive family's _tool_result() dict shape (matching
    find_or_create_organization()'s contract, so tools/dispatcher.py and
    core.anti_hallucination's evidence extraction handle it identically)
    and crm.py's own ContactResult.
    """
    tool = "crm_find_or_create_contact"
    if not str(name or "").strip():
        return _tool_result(
            ok=False, tool=tool,
            user_message="❌ Contact name must be non-empty.",
        )

    fields = {ContactFields.NAME: name, ContactFields.PHONE: phone}
    if email:
        fields[ContactFields.EMAIL] = email
    if company:
        fields[ContactFields.COMPANY] = company
    if role_category:
        fields[ContactFields.ROLE_CATEGORY] = role_category

    contact = crm.create_contact_from_fields(
        fields, identity=identity, source=source,
    )
    evidence = {"record_id": contact.record_id, "table": Tables.CONTACTS}
    if contact.matches:
        evidence["matches"] = list(contact.matches)

    if contact.status == "outcome_unknown":
        return _tool_result(
            ok=False, tool=tool, evidence=evidence,
            user_message="⚠️ תוצאת יצירת איש הקשר אינה ידועה. אין לנסות שוב אוטומטית.",
        )
    if contact.status in ("created", "existing"):
        return _tool_result(
            ok=True, tool=tool, external_id=contact.record_id, evidence=evidence,
            user_message="✅ איש הקשר נוצר" if contact.status == "created" else "✅ איש הקשר כבר קיים",
        )
    return _tool_result(
        ok=False, tool=tool, evidence=evidence,
        user_message=crm.describe_contact_failure(contact),
    )


def create_charge(
    deal_id: str,
    direction: str,
    amount: float,
    currency: str,
    status: str,
    collection_state: str,
    vat_rule: str,
    document_requirement: str,
    document_status: str,
    *,
    billing_term_id: str = "",
    reference: str = "",
    original_due_date: str = "",
    current_expected_date: str = "",
    base_amount: float | None = None,
    rate_pct: float | None = None,
    quantity: float | None = None,
    unit_rate: float | None = None,
    vat_amount: float | None = None,
    trigger_evidence: str = "",
    original_terms_snapshot: str = "",
    promised_payment_date: str = "",
    promised_payment_amount: float | None = None,
    notes: str = "",
    source: str = "commercial_crm",
) -> dict:
    """Create one canonical Charge; Deal is mandatory, Billing Term optional."""
    tool = "crm_create_charge"
    deal_fields, error = _read_fields(Tables.DEALS, deal_id, "Deal")
    if error:
        return _tool_result(ok=False, tool=tool, user_message=f"❌ {error}")

    if billing_term_id:
        term_fields, error = _read_fields(
            Tables.PAYMENT_TERMS, billing_term_id, "Billing Term"
        )
        if error:
            return _tool_result(ok=False, tool=tool, user_message=f"❌ {error}")
        if deal_id not in _link_ids(term_fields.get(PaymentTermFields.DEAL)):
            return _tool_result(
                ok=False, tool=tool,
                user_message="❌ Billing Term does not belong to the supplied Deal.",
            )

    if direction not in _DIRECTIONS:
        return _tool_result(ok=False, tool=tool, user_message="❌ Direction is invalid.")
    if currency not in _CURRENCIES:
        return _tool_result(ok=False, tool=tool, user_message="❌ Currency must be ILS, USD, or EUR.")
    if status not in _CHARGE_STATUSES:
        return _tool_result(ok=False, tool=tool, user_message="❌ Charge Status is invalid.")
    if collection_state not in _COLLECTION_STATES:
        return _tool_result(ok=False, tool=tool, user_message="❌ Collection State is invalid.")
    if vat_rule not in _VAT_RULES:
        return _tool_result(ok=False, tool=tool, user_message="❌ VAT Rule is invalid.")
    if document_requirement not in _DOCUMENT_REQUIREMENTS:
        return _tool_result(ok=False, tool=tool, user_message="❌ Document Requirement is invalid.")
    if document_status not in _DOCUMENT_STATUSES:
        return _tool_result(ok=False, tool=tool, user_message="❌ Document Status is invalid.")
    if (
        (document_requirement == DocumentRequirement.NONE)
        != (document_status == DocumentStatus.NOT_REQUIRED)
    ):
        return _tool_result(
            ok=False, tool=tool,
            user_message="❌ Document Status conflicts with Document Requirement.",
        )
    if not _valid_number(amount, positive=True):
        return _tool_result(ok=False, tool=tool, user_message="❌ Charge Amount must be greater than zero.")

    numeric_contracts = (
        ("Base Amount", base_amount, False),
        ("Rate %", rate_pct, False),
        ("Quantity", quantity, True),
        ("Unit Rate", unit_rate, True),
        ("VAT Amount", vat_amount, False),
        ("Promised Payment Amount", promised_payment_amount, True),
    )
    for label, value, positive in numeric_contracts:
        if value is not None and not _valid_number(value, positive=positive):
            return _tool_result(ok=False, tool=tool, user_message=f"❌ {label} is invalid.")
    if rate_pct is not None and float(rate_pct) > 100:
        return _tool_result(ok=False, tool=tool, user_message="❌ Rate % must be between 0 and 100.")
    for label, value in (
        ("Original Due Date", original_due_date),
        ("Current Expected Date", current_expected_date),
        ("Promised Payment Date", promised_payment_date),
    ):
        if value and not _valid_iso_date(value):
            return _tool_result(ok=False, tool=tool, user_message=f"❌ {label} must be YYYY-MM-DD.")

    fields: dict[str, Any] = {
        ChargeFields.DEAL: [deal_id],
        ChargeFields.DIRECTION: direction,
        ChargeFields.AMOUNT: amount,
        ChargeFields.CURRENCY_CODE: currency,
        ChargeFields.STATUS: status,
        ChargeFields.COLLECTION_STATE: collection_state,
        ChargeFields.VAT_RULE: vat_rule,
        ChargeFields.DOCUMENT_REQUIREMENT: document_requirement,
        ChargeFields.DOCUMENT_STATUS: document_status,
    }
    optional_fields = (
        (ChargeFields.BILLING_TERM, [billing_term_id] if billing_term_id else None),
        (ChargeFields.REFERENCE, reference),
        (ChargeFields.ORIGINAL_DUE_DATE, original_due_date),
        (ChargeFields.CURRENT_EXPECTED_DATE, current_expected_date),
        (ChargeFields.BASE_AMOUNT, base_amount),
        (ChargeFields.RATE_PCT, rate_pct),
        (ChargeFields.QUANTITY, quantity),
        (ChargeFields.UNIT_RATE, unit_rate),
        (ChargeFields.VAT_AMOUNT, vat_amount),
        (ChargeFields.TRIGGER_EVIDENCE, trigger_evidence),
        (ChargeFields.ORIGINAL_TERMS_SNAPSHOT, original_terms_snapshot),
        (ChargeFields.PROMISED_PAYMENT_DATE, promised_payment_date),
        (ChargeFields.PROMISED_PAYMENT_AMOUNT, promised_payment_amount),
        (ChargeFields.NOTES, notes),
    )
    for field_name, value in optional_fields:
        if value is not None and value != "":
            fields[field_name] = value

    # Total Paid, Remaining Balance, reverse links, formulas, and rollups are
    # intentionally absent: no parameter can inject them.
    return _write_result(tool, Tables.CHARGES, fields, source)


def create_charge_payment(
    charge_id: str,
    deal_id: str,
    direction: str,
    amount: float,
    currency: str,
    paid_at: str,
    status: str,
    document_requirement: str,
    document_status: str,
    *,
    payment_term_id: str = "",
    reference: str = "",
    method: str = "",
    counterparty_contact_id: str = "",
    counterparty_organization_id: str = "",
    notes: str = "",
    source: str = "commercial_crm",
) -> dict:
    """Create an actual monetary movement linked to exactly one Charge."""
    tool = "crm_create_charge_payment"
    charge_fields, error = _read_fields(Tables.CHARGES, charge_id, "Charge")
    if error:
        return _tool_result(ok=False, tool=tool, user_message=f"❌ {error}")

    charge_deals = _link_ids(charge_fields.get(ChargeFields.DEAL))
    if len(charge_deals) != 1:
        return _tool_result(
            ok=False, tool=tool,
            user_message="❌ Charge must resolve to exactly one Deal.",
        )
    if deal_id != charge_deals[0]:
        return _tool_result(ok=False, tool=tool, user_message="❌ Payment Deal does not match Charge Deal.")
    if direction not in _DIRECTIONS or direction != charge_fields.get(ChargeFields.DIRECTION):
        return _tool_result(ok=False, tool=tool, user_message="❌ Payment Direction does not match Charge.")
    if currency not in _CURRENCIES or currency != charge_fields.get(ChargeFields.CURRENCY_CODE):
        return _tool_result(ok=False, tool=tool, user_message="❌ Payment Currency does not match Charge.")
    if not _valid_number(amount, positive=True):
        return _tool_result(ok=False, tool=tool, user_message="❌ Payment Amount must be greater than zero.")
    if not _valid_iso_date(paid_at):
        return _tool_result(ok=False, tool=tool, user_message="❌ Paid At must be YYYY-MM-DD.")
    if status != PaymentStatus.RECEIVED:
        return _tool_result(ok=False, tool=tool, user_message="❌ V2 Payment status must be received.")
    if document_requirement not in _DOCUMENT_REQUIREMENTS:
        return _tool_result(ok=False, tool=tool, user_message="❌ Document Requirement is invalid.")
    if document_status not in _DOCUMENT_STATUSES:
        return _tool_result(ok=False, tool=tool, user_message="❌ Document Status is invalid.")
    if (
        (document_requirement == DocumentRequirement.NONE)
        != (document_status == DocumentStatus.NOT_REQUIRED)
    ):
        return _tool_result(
            ok=False, tool=tool,
            user_message="❌ Document Status conflicts with Document Requirement.",
        )

    charge_terms = _link_ids(charge_fields.get(ChargeFields.BILLING_TERM))
    if payment_term_id:
        term_fields, error = _read_fields(Tables.PAYMENT_TERMS, payment_term_id, "Payment Term")
        if error:
            return _tool_result(ok=False, tool=tool, user_message=f"❌ {error}")
        if payment_term_id not in charge_terms:
            return _tool_result(ok=False, tool=tool, user_message="❌ Payment Term does not match Charge.")
        if deal_id not in _link_ids(term_fields.get(PaymentTermFields.DEAL)):
            return _tool_result(ok=False, tool=tool, user_message="❌ Payment Term does not belong to Charge Deal.")

    for table, record_id, label in (
        (Tables.CONTACTS, counterparty_contact_id, "Counterparty Contact"),
        (Tables.ORGANIZATIONS, counterparty_organization_id, "Counterparty Organization"),
    ):
        if record_id:
            _, error = _read_fields(table, record_id, label)
            if error:
                return _tool_result(ok=False, tool=tool, user_message=f"❌ {error}")

    fields: dict[str, Any] = {
        PaymentFields.CHARGE: [charge_id],
        PaymentFields.DEAL_LINK: [deal_id],
        PaymentFields.DIRECTION: direction,
        PaymentFields.AMOUNT: amount,
        PaymentFields.CURRENCY: currency,
        PaymentFields.PAID_AT: paid_at,
        PaymentFields.STATUS: status,
        PaymentFields.DOCUMENT_REQUIREMENT: document_requirement,
        PaymentFields.DOCUMENT_STATUS: document_status,
    }
    optional_fields = (
        (PaymentFields.PAYMENT_TERM, [payment_term_id] if payment_term_id else None),
        (PaymentFields.REF, reference),
        (PaymentFields.METHOD, method),
        (PaymentFields.COUNTERPARTY_CONTACT, [counterparty_contact_id] if counterparty_contact_id else None),
        (PaymentFields.COUNTERPARTY_ORGANIZATION, [counterparty_organization_id] if counterparty_organization_id else None),
        (PaymentFields.NOTES, notes),
    )
    for field_name, value in optional_fields:
        if value is not None and value != "":
            fields[field_name] = value

    return _write_result(tool, Tables.PAYMENTS, fields, source)

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
    counterparty_contact_id: str = "",
    counterparty_organization_id: str = "",
    deal_type_code: str = "",
    relationship_type: str = "",
    currency: str = "",
    commercial_status: str = "",
    start_date: str = "",
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

    # BUG-CRM-BYPASS-DOMAIN-SELECT-CASING (02/09/2026): `domain` here is
    # always the business-canonical slug (e.g. "import") -- resolve_domain_word()
    # upstream must keep returning that, never Airtable's own display
    # casing. But Deal's live Domain single-select's actual configured
    # option is "Import" (capital), not "import" -- writing the canonical
    # slug straight through 422'd in production ("Insufficient permissions
    # to create new select option"). This is the persistence-boundary
    # mapping step, not a parser fix -- see resolve_live_select_value()'s
    # own docstring for the full USER LANGUAGE -> BUSINESS CANONICAL ->
    # AIRTABLE LIVE VALUE contract.
    from core.runtime_schema_provider import resolve_live_select_value
    domain_value = resolve_live_select_value(Tables.DEALS, DealFields.DOMAIN, domain)
    if domain_value is None:
        return _tool_result(
            ok=False, tool="crm_create_deal",
            user_message=f"❌ תחום לא מוכר בטבלת העסקאות: {domain!r}.",
        )

    fields: dict[str, Any] = {
        DealFields.NAME: name.strip(),
        DealFields.DOMAIN: domain_value,
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
    if counterparty_contact_id:
        fields[DealFields.COUNTERPARTY_CONTACT] = [counterparty_contact_id]
    if counterparty_organization_id:
        fields[DealFields.COUNTERPARTY_ORGANIZATION] = [counterparty_organization_id]
    if deal_type_code:
        fields[DealFields.DEAL_TYPE_CODE] = deal_type_code
    if relationship_type:
        fields[DealFields.RELATIONSHIP_TYPE] = relationship_type
    if currency:
        fields[DealFields.CURRENCY] = currency
    if commercial_status:
        fields[DealFields.COMMERCIAL_STATUS] = commercial_status
    if start_date:
        fields[DealFields.START_DATE] = start_date

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

    # BUG-CRM-BYPASS-DOMAIN-SELECT-CASING follow-up: same persistence-
    # boundary mapping as create_deal() -- see that function's comment and
    # resolve_live_select_value()'s docstring for the full contract.
    from core.runtime_schema_provider import resolve_live_select_value
    domain_value = resolve_live_select_value(Tables.PAYMENTS, PaymentFields.DOMAIN, domain)
    if domain_value is None:
        return _tool_result(
            ok=False, tool="crm_create_payment",
            user_message=f"❌ תחום לא מוכר בטבלת התשלומים: {domain!r}.",
        )

    fields: dict[str, Any] = {
        PaymentFields.AMOUNT: amount,
        PaymentFields.DOMAIN: domain_value,
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
