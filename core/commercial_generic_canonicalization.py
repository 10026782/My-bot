# core/commercial_generic_canonicalization.py
"""Generic Airtable → canonical commercial tool translation (single authority).

BusinessDraft Phase 4B. The generic tools the model is still offered
(``airtable_add``/``airtable_update``) can name a protected commercial table
(Deals / Payment Terms / Payments). Before Phase 4B the only translation of
such a call into its canonical commercial writer happened inside
``tools/dispatcher.py`` -- i.e. AFTER approval, so the ActionContract was
minted under the generic tool identity and the BusinessDraft /
ConfirmedSnapshot seam in ``app._queue_approval_detailed_impl()`` never saw
the mutation.

This module is the ONE place the generic-column → canonical-kwarg mapping
lives. It is consumed by:

  1. ``core.action_gateway.resolve_canonical_call()`` — pre-proposal
     canonicalization (via :func:`canonicalize_generic_commercial_call`), so
     a new generic commercial proposal becomes the dedicated tool +
     primitive payload BEFORE BusinessDraft / fingerprinting / ActionContract.
  2. ``tools/dispatcher.py`` — the pre-existing execution-time redirect,
     kept only as a backward-compatible fallback for ActionContracts minted
     under a generic tool identity before Phase 4B (see that module).

Pure: no Airtable I/O, no identity, no mutation of its inputs, deterministic
and idempotent (a dedicated canonical tool passed in is returned untouched as
``None`` = "not applicable"). Identity-sensitive canonicalization (Owner →
Profile record, role enforcement) stays where it already lives: the
BusinessDraft seams in app.py and the dispatcher's dedicated cases.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from airtable_schema import (
    ChargeFields, DealFields, OrganizationFields, PaymentFields,
    PaymentTermFields, Tables,
)


# ══════════════════════════════════════════════════
# Commercial CRM write-boundary closure (Deals/Payment Terms/Payments)
#
# (Moved verbatim from tools/dispatcher.py in Phase 4B -- history:) Contacts
# already had a redirect in the generic "airtable_add" case into
# crm.create_contact_from_fields(). Deals/Payment Terms/Payments had NO
# equivalent redirect: a raw airtable_add call to those tables fell straight
# through to the generic `airtable_add(table, fields)` write, skipping
# commercial_crm.py's required-field/calc_type/VAT validation entirely.
# Worse, "airtable_add"'s own registry role set (_INTERNAL, tool_registry.py)
# includes "employee", while crm_create_deal/crm_create_payment_term/
# crm_create_payment are _MANAGEMENT-only. Found during the R10 write-path
# golden-writer audit, 01/09/2026.
#
# A raw Airtable payload uses real Airtable column names (DealFields.NAME
# etc.), not the canonical writer's own parameter names, so a mapping step
# is required; an unmapped field must never be silently dropped.
#
# Map value = (canonical kwarg name, link mode):
#   None     -> scalar, passed through as-is
#   "single" -> linked-record field; Airtable gives a 1-element list or a
#               bare record-id string, the writer wants a bare string
#   "list"   -> linked-record field where the writer itself wants a list
#               (currently only Deal.contact_ids)
# ══════════════════════════════════════════════════

DEAL_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    DealFields.NAME:          ("name", None),
    DealFields.DOMAIN:        ("domain", None),
    DealFields.OWNER:         ("owner_id", "single"),
    DealFields.ORIGIN_LEAD:   ("origin_lead_id", "single"),
    DealFields.CONTACTS_LINK: ("contact_ids", "list"),
    DealFields.VENTURE_LINK:  ("venture_id", "single"),
    DealFields.STAGE:         ("stage", None),
    DealFields.PRIORITY:      ("priority", None),
    DealFields.RISK_LEVEL:    ("risk_level", None),
    DealFields.NOTES:         ("notes", None),
    # BUG-DIAMOND-OPTIONAL-ENRICHMENT-GATES-CREATION: these four V2 fields
    # are collected as post-creation enrichment (commercial_completion.py)
    # via a generic airtable_update on an already-created Deal.
    DealFields.DEAL_TYPE_CODE:   ("deal_type_code", None),
    DealFields.RELATIONSHIP_TYPE: ("relationship_type", None),
    # DIAMOND — BUSINESS FIELDS MIGRATION (06/09/2026): canonical
    # replacement for the two entries above (see DealFields.
    # BUSINESS_DEAL_TYPE's own comment in airtable_schema.py) — the old
    # entries stay in this allowlist for compatibility, never removed.
    DealFields.BUSINESS_DEAL_TYPE: ("business_deal_type", None),
    DealFields.RELATIONSHIP_ROLE:  ("relationship_role", None),
    DealFields.ENGAGEMENT_DURATION: ("engagement_duration", None),
    DealFields.CURRENCY:         ("currency", None),
    DealFields.COMMERCIAL_STATUS: ("commercial_status", None),
    # BUG-DIAMOND-EXPECTED-VALUE-RANGE: canonical replacement for
    # DealFields.AMOUNT ("סכום"), which is deliberately NOT in this
    # allowlist — commercial_crm.create_deal() no longer accepts `amount`.
    DealFields.ESTIMATED_VALUE_BASIS: ("estimated_value_basis", None),
    DealFields.ESTIMATED_VALUE_RANGE: ("estimated_value_range", None),
    DealFields.ESTIMATED_VALUE_NOTES: ("estimated_value_notes", None),
    # PHASE 4B mapping-drift closure: commercial_crm.create_deal()/
    # update_deal() (and the dedicated crm_create_deal/crm_update_deal
    # dispatcher cases) have long accepted these three kwargs, and
    # ENTITY_CONTRACTS["deal"] requires one_of(counterparty_contact,
    # counterparty_organization) on CREATE — without these entries NO generic
    # Deal CREATE could ever be represented losslessly as crm_create_deal,
    # and a generic update naming them failed closed as "unsupported" even
    # though the writer supports them.
    DealFields.COUNTERPARTY_CONTACT:      ("counterparty_contact_id", "single"),
    DealFields.COUNTERPARTY_ORGANIZATION: ("counterparty_organization_id", "single"),
    DealFields.START_DATE:                ("start_date", None),
}
PAYMENT_TERM_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    PaymentTermFields.DEAL:         ("deal_id", "single"),
    PaymentTermFields.NAME:         ("name", None),
    PaymentTermFields.CALC_TYPE:    ("calc_type", None),
    PaymentTermFields.DIRECTION:    ("direction", None),
    PaymentTermFields.CURRENCY:     ("currency", None),
    PaymentTermFields.FIXED_AMOUNT: ("fixed_amount", None),
    PaymentTermFields.RATE_PCT:     ("rate_pct", None),
    PaymentTermFields.CALC_BASIS:   ("calc_basis", None),
    PaymentTermFields.TRIGGER_TYPE: ("trigger_type", None),
    PaymentTermFields.TRIGGER_DATE: ("trigger_date", None),
    PaymentTermFields.TRIGGER_DELAY_DAYS: ("trigger_delay_days", None),
    PaymentTermFields.CADENCE:      ("cadence", None),
    PaymentTermFields.VAT_RULE:     ("vat_rule", None),
    PaymentTermFields.START_DATE:   ("start_date", None),
    PaymentTermFields.END_DATE:     ("end_date", None),
    PaymentTermFields.NOTES:        ("notes", None),
}
# Legacy (V1, flat) Payment shape — the crm_create_payment writer's kwargs.
PAYMENT_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    PaymentFields.AMOUNT:       ("amount", None),
    PaymentFields.DOMAIN:       ("domain", None),
    PaymentFields.OWNER:        ("owner_id", "single"),
    PaymentFields.DEAL_LINK:    ("deal_id", "single"),
    PaymentFields.PAYMENT_TERM: ("payment_term_id", "single"),
    PaymentFields.ORIGIN_LEAD:  ("origin_lead_id", "single"),
    PaymentFields.REF:          ("reference", None),
    PaymentFields.DATE:         ("due_date", None),
    PaymentFields.BASE_AMOUNT:  ("base_amount", None),
    PaymentFields.RATE_PCT:     ("rate_pct", None),
    PaymentFields.VAT_RULE:     ("vat_rule", None),
    PaymentFields.VAT_AMOUNT:   ("vat_amount", None),
    PaymentFields.TRIGGER_EVIDENCE: ("trigger_evidence", None),
    PaymentFields.NOTES:        ("notes", None),
}
ORGANIZATION_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    OrganizationFields.NAME: ("organization_name", None),
}
CHARGE_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    ChargeFields.REFERENCE: ("reference", None),
    ChargeFields.DEAL: ("deal_id", "single"),
    ChargeFields.BILLING_TERM: ("billing_term_id", "single"),
    ChargeFields.DIRECTION: ("direction", None),
    ChargeFields.AMOUNT: ("amount", None),
    ChargeFields.CURRENCY_CODE: ("currency", None),
    ChargeFields.ORIGINAL_DUE_DATE: ("original_due_date", None),
    ChargeFields.CURRENT_EXPECTED_DATE: ("current_expected_date", None),
    ChargeFields.STATUS: ("status", None),
    ChargeFields.COLLECTION_STATE: ("collection_state", None),
    ChargeFields.BASE_AMOUNT: ("base_amount", None),
    ChargeFields.RATE_PCT: ("rate_pct", None),
    ChargeFields.QUANTITY: ("quantity", None),
    ChargeFields.UNIT_RATE: ("unit_rate", None),
    ChargeFields.VAT_RULE: ("vat_rule", None),
    ChargeFields.VAT_AMOUNT: ("vat_amount", None),
    ChargeFields.TRIGGER_EVIDENCE: ("trigger_evidence", None),
    ChargeFields.ORIGINAL_TERMS_SNAPSHOT: ("original_terms_snapshot", None),
    ChargeFields.PROMISED_PAYMENT_DATE: ("promised_payment_date", None),
    ChargeFields.PROMISED_PAYMENT_AMOUNT: ("promised_payment_amount", None),
    ChargeFields.DOCUMENT_REQUIREMENT: ("document_requirement", None),
    ChargeFields.DOCUMENT_STATUS: ("document_status", None),
    ChargeFields.NOTES: ("notes", None),
}
# V2 (Charge-linked) Payment shape — the crm_create_charge_payment writer.
PAYMENT_V2_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    PaymentFields.CHARGE: ("charge_id", "single"),
    PaymentFields.DEAL_LINK: ("deal_id", "single"),
    PaymentFields.DIRECTION: ("direction", None),
    PaymentFields.AMOUNT: ("amount", None),
    PaymentFields.CURRENCY: ("currency", None),
    PaymentFields.PAID_AT: ("paid_at", None),
    PaymentFields.STATUS: ("status", None),
    PaymentFields.PAYMENT_TERM: ("payment_term_id", "single"),
    PaymentFields.REF: ("reference", None),
    PaymentFields.METHOD: ("method", None),
    PaymentFields.COUNTERPARTY_CONTACT: ("counterparty_contact_id", "single"),
    PaymentFields.COUNTERPARTY_ORGANIZATION: ("counterparty_organization_id", "single"),
    PaymentFields.DOCUMENT_REQUIREMENT: ("document_requirement", None),
    PaymentFields.DOCUMENT_STATUS: ("document_status", None),
    PaymentFields.NOTES: ("notes", None),
}
# PHASE 4B mapping-drift closure: a Payments UPDATE may name either shape's
# columns — update_payment() (commercial_crm._PAYMENT_UPDATE_ALLOWED)
# accepts method / counterparty_* / document_* which exist only in the V2
# column set. Every column shared by both maps translates to the SAME kwarg
# (asserted below), so the union is unambiguous. Column recognition is the
# wider layer only: the writer's / BusinessDraft's own narrower UPDATE
# allowlist still fails closed on every financial (immutable) field.
PAYMENT_UPDATE_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    **PAYMENT_FIELD_MAP, **PAYMENT_V2_FIELD_MAP,
}
assert all(
    PAYMENT_FIELD_MAP[k] == PAYMENT_V2_FIELD_MAP[k]
    for k in set(PAYMENT_FIELD_MAP) & set(PAYMENT_V2_FIELD_MAP)
), "Payment V1/V2 column maps disagree on a shared column"

# Keys the dispatcher itself injects into `fields` (see the _TENANT_AWARE
# block in dispatch_tool()) — never user/agent-supplied, never mapped, and
# never counted as an "unrecognized field" fail-closed trigger.
GENERIC_WRITE_IGNORED_KEYS: frozenset[str] = frozenset({"tenant_id"})

PROTECTED_CRM_ALIASES: dict[str, str] = {
    "עסקאות (Deals)": Tables.DEALS,
    "Deals": Tables.DEALS,
    "Payment Terms": Tables.PAYMENT_TERMS,
    "Payments": Tables.PAYMENTS,
    "Charge": Tables.CHARGES,
    "Charges": Tables.CHARGES,
    "Organization": Tables.ORGANIZATIONS,
    "Organizations": Tables.ORGANIZATIONS,
}

# table -> (dedicated CREATE tool name to authority-check, its field map, its
# required-kwarg names that have no Python default and must never be
# omitted from a direct writer call).
CRM_TABLE_ROUTING: dict[str, tuple[str, dict[str, tuple[str, str | None]], tuple[str, ...]]] = {
    Tables.DEALS:         ("crm_create_deal", DEAL_FIELD_MAP, ("name", "domain", "owner_id")),
    Tables.PAYMENT_TERMS: ("crm_create_payment_term", PAYMENT_TERM_FIELD_MAP, ("deal_id", "name", "calc_type", "direction", "currency")),
    Tables.PAYMENTS:      ("crm_create_payment", PAYMENT_FIELD_MAP, ("amount", "domain", "owner_id")),
    Tables.CHARGES:       (
        "crm_create_charge", CHARGE_FIELD_MAP,
        ("deal_id", "direction", "amount", "currency", "status", "collection_state",
         "vat_rule", "document_requirement", "document_status"),
    ),
    Tables.ORGANIZATIONS: (
        "crm_find_or_create_organization", ORGANIZATION_FIELD_MAP, ("organization_name",),
    ),
}

PAYMENT_V2_ROUTE = (
    "crm_create_charge_payment", PAYMENT_V2_FIELD_MAP,
    ("charge_id", "deal_id", "direction", "amount", "currency", "paid_at", "status",
     "document_requirement", "document_status"),
)

# Canonical UPDATE tool + the column map that recognizes its generic input.
CRM_UPDATE_ROUTING: dict[str, tuple[str, dict[str, tuple[str, str | None]]]] = {
    Tables.DEALS:         ("crm_update_deal", DEAL_FIELD_MAP),
    Tables.PAYMENT_TERMS: ("crm_update_payment_term", PAYMENT_TERM_FIELD_MAP),
    Tables.PAYMENTS:      ("crm_update_payment", PAYMENT_UPDATE_FIELD_MAP),
}

# Phase 4B scope: the BusinessDraft-covered commercial entities only.
# Charges/Organizations keep their existing (dispatcher-only) Phase state.
BUSINESS_DRAFT_COVERED_TABLES: frozenset[str] = frozenset(CRM_UPDATE_ROUTING)

# The legacy flat Payment writer is NOT BusinessDraft Payment CREATE
# authority (owner decision, Phase 4A/4B) — a generic CREATE that resolves
# to it must fail closed before any ActionContract exists.
LEGACY_PAYMENT_CREATE_TOOL = "crm_create_payment"

GENERIC_COMMERCIAL_TOOLS: frozenset[str] = frozenset({"airtable_add", "airtable_update"})


def normalize_table_name(table: str) -> str:
    return re.sub(r"\s+", " ", str(table).strip()).casefold()


def resolve_protected_crm_table(table: str) -> tuple[str | None, bool]:
    """Resolve known aliases; flag protected-looking unknown aliases."""
    normalized = normalize_table_name(table)
    for alias, canonical in PROTECTED_CRM_ALIASES.items():
        if normalized == normalize_table_name(alias):
            return canonical, False
    compact = re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)
    protected_compact = {
        re.sub(r"[^\w]+", "", normalize_table_name(alias), flags=re.UNICODE)
        for alias in PROTECTED_CRM_ALIASES
    }
    return None, compact in protected_compact


def crm_create_route(table: str, fields: Mapping[str, Any]) -> tuple[str, dict, tuple[str, ...]] | None:
    """Select legacy versus V2 Payment without changing the legacy contract."""
    if table == Tables.PAYMENTS and (
        PaymentFields.CHARGE in fields
        or any(key in fields for key in set(PAYMENT_V2_FIELD_MAP) - set(PAYMENT_FIELD_MAP))
    ):
        return PAYMENT_V2_ROUTE
    return CRM_TABLE_ROUTING.get(table)


def crm_update_field_map(table: str) -> dict[str, tuple[str, str | None]]:
    """The column map recognizing a generic UPDATE for one covered table."""
    return CRM_UPDATE_ROUTING[table][1]


def map_generic_fields_to_canonical(
    fields: Mapping[str, Any], field_map: Mapping[str, tuple[str, str | None]],
) -> tuple[dict, str]:
    """Maps a raw Airtable `fields` dict onto a canonical writer's own
    kwargs using an explicit, closed field_map. Returns (kwargs, error) —
    error is non-empty (and kwargs is {}) the moment any field can't be
    represented, so a caller never silently drops part of what was asked
    for. Never inspects field VALUES for business validity (empty name,
    bad calc_type, amount<=0, ...) — that stays the canonical writer's /
    BusinessDraft's job."""
    kwargs: dict = {}
    for key, value in fields.items():
        if key in GENERIC_WRITE_IGNORED_KEYS:
            continue
        if key not in field_map:
            return {}, f"שדה לא נתמך בכתיבה ישירה לטבלה זו: {key!r}."
        kwarg_name, link_mode = field_map[key]
        if link_mode == "single":
            if isinstance(value, list):
                if len(value) != 1:
                    return {}, f"ערך לא תקין לשדה מקושר {key!r} — נדרש בדיוק ערך אחד."
                value = value[0]
            elif not isinstance(value, str):
                return {}, f"ערך לא תקין לשדה מקושר {key!r}."
        elif link_mode == "list":
            if isinstance(value, str):
                value = [value]
            elif not isinstance(value, list):
                return {}, f"ערך לא תקין לשדה מקושר {key!r} — נדרש רשימה."
            else:
                value = list(value)
        kwargs[kwarg_name] = value
    return kwargs, ""


# ══════════════════════════════════════════════════
# Pre-proposal canonicalization (Phase 4B)
# ══════════════════════════════════════════════════

class CommercialCanonicalizationError(ValueError):
    """A generic call names a protected commercial table but cannot be
    represented losslessly as its canonical commercial tool. Always raised
    BEFORE any BusinessDraft / fingerprint / ActionContract exists.

    ``user_message`` is safe, user-facing Hebrew text (no internal tool
    names); ``str(exc)`` is the operator/log reason."""

    def __init__(self, reason: str, user_message: str):
        super().__init__(reason)
        self.user_message = user_message


def _fail(reason: str, detail: str) -> CommercialCanonicalizationError:
    return CommercialCanonicalizationError(
        reason, f"❌ לא ניתן להעביר את הבקשה לאישור: {detail}",
    )


def canonicalize_generic_commercial_call(
    tool_name: str, tool_inputs: Mapping[str, Any],
) -> tuple[str, dict] | None:
    """Translate a generic ``airtable_add``/``airtable_update`` call on a
    BusinessDraft-covered commercial table (Deals / Payment Terms / Payments)
    into its dedicated canonical tool + primitive writer-space payload.

    Returns ``None`` when not applicable — any other tool (including every
    dedicated canonical tool, which makes this idempotent), a non-protected
    table (Tasks, Contacts, Leads, ...), or a protected table outside Phase
    4B scope (Charges/Organizations keep their existing Phase state).

    Raises :class:`CommercialCanonicalizationError` (fail closed, never a
    fall-through to a generic business write) when the call names a covered
    table but cannot be represented losslessly: malformed/ambiguous table
    alias, absent table, non-dict ``fields``, unmapped column, invalid
    link cardinality, malformed UPDATE ``record_id``, unrecognized Deal
    Domain word, or a Payments CREATE resolving to the legacy flat writer.
    """
    if tool_name not in GENERIC_COMMERCIAL_TOOLS:
        return None
    inputs = tool_inputs if isinstance(tool_inputs, Mapping) else {}
    table = inputs.get("table")
    if not isinstance(table, str) or not table.strip():
        raise _fail(
            f"{tool_name} without a target table",
            "לא צוינה טבלת יעד תקינה.",
        )

    resolved_table, ambiguous_alias = resolve_protected_crm_table(table)
    if ambiguous_alias:
        raise _fail(
            f"unrecognized or ambiguous protected CRM table alias {table!r}",
            f"שם טבלת CRM לא מוכר או דו-משמעי: {table!r}.",
        )
    if resolved_table not in BUSINESS_DRAFT_COVERED_TABLES:
        return None

    fields = inputs.get("fields")
    if not isinstance(fields, Mapping):
        raise _fail(
            f"{tool_name} on {resolved_table!r} with non-dict fields",
            "מבנה השדות בבקשה אינו תקין.",
        )

    if tool_name == "airtable_update":
        record_id = inputs.get("record_id")
        from commercial_crm import _valid_record_id  # single record-id authority
        if not _valid_record_id(record_id):
            raise _fail(
                f"airtable_update on {resolved_table!r} with malformed record_id",
                "עדכון דורש מזהה רשומה (record_id) תקין.",
            )
        canonical_tool, field_map = CRM_UPDATE_ROUTING[resolved_table]
        mapped, map_error = map_generic_fields_to_canonical(fields, field_map)
        if map_error:
            raise _fail(f"{tool_name}->{canonical_tool}: {map_error}", map_error)
        if not mapped:
            raise _fail(
                f"{tool_name}->{canonical_tool}: no updatable fields",
                "לא צוינו שדות לעדכון.",
            )
        if resolved_table == Tables.DEALS and "domain" in mapped:
            # Same free-text/Hebrew-word → slug normalization the generic
            # dispatcher redirect has always applied to a Deal Domain edit
            # (BUG-CRM-BYPASS-UPDATE); the writer maps slug → live value.
            # Pure lookup — no identity, no I/O.
            from core.lead_service import resolve_domain_word
            canonical_domain = resolve_domain_word(str(mapped["domain"]))
            if not canonical_domain:
                raise _fail(
                    f"{tool_name}->{canonical_tool}: unrecognized Deal domain",
                    f"תחום לא מוכר: {mapped['domain']!r}.",
                )
            mapped["domain"] = canonical_domain
        return canonical_tool, {"record_id": record_id, **mapped}

    route = crm_create_route(resolved_table, fields)
    canonical_tool, field_map, _required = route
    if canonical_tool == LEGACY_PAYMENT_CREATE_TOOL:
        raise _fail(
            "generic Payments CREATE resolves to the legacy crm_create_payment "
            "writer, which is not BusinessDraft Payment CREATE authority",
            "יצירת תשלום במבנה הישן (ללא חיוב מקושר) אינה נתמכת יותר. "
            "יש לרשום תשלום מול חיוב (Charge) קיים.",
        )
    mapped, map_error = map_generic_fields_to_canonical(fields, field_map)
    if map_error:
        raise _fail(f"{tool_name}->{canonical_tool}: {map_error}", map_error)
    if not mapped:
        raise _fail(
            f"{tool_name}->{canonical_tool}: no fields",
            "לא צוינו שדות ליצירה.",
        )
    return canonical_tool, mapped
