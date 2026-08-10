# crm.py
# CRM Module — אנשי קשר, עסקאות, תשלומים
# כל פונקציה מחזירה string מוכן לשליחה בטלגרם

import os
import re
import httpx
import logging
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, date, timedelta

from airtable_schema import (
    Tables,
    ContactFields, ContactType, ContactRoleCategory, ContactStatus,
    DealFields, DealStage, DealStatus, RiskLevel,
    PaymentFields, PaymentStatus,
    validate_funding_cost,
)
from tools.airtable_gateway import airtable_create, airtable_patch

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Helpers — קוראים env בכל קריאה (לא module-level)
# ══════════════════════════════════════════════════

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('AIRTABLE_API_KEY', '')}",
        "Content-Type":  "application/json",
    }

def _base_url(table: str) -> str:
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    return f"https://api.airtable.com/v0/{base}/{urllib.parse.quote(table, safe='')}"

def _creds_ok() -> bool:
    return bool(os.environ.get("AIRTABLE_API_KEY")) and bool(os.environ.get("AIRTABLE_BASE_ID"))

def _get(table: str, formula: str = "", fields: list = None, identity=None) -> list:
    """GET records מטבלה.

    [SEC] identity — אם עובר ו-is_external, מוסיף tenant filter אוטומטי.
    scheduler / daily_digest קוראים בלי identity → עוברים כ-internal.
    """
    tenant_id   = getattr(identity, "tenant_id", None)
    is_external = identity is not None and not getattr(identity, "is_internal", True)

    if is_external and tenant_id and tenant_id != "unknown":
        tenant_filter = f"{{tenant_id}}='{tenant_id}'"
        formula = f"AND({formula}, {tenant_filter})" if formula else tenant_filter

    params = {}
    if formula:
        params["filterByFormula"] = formula
    if fields:
        for i, f in enumerate(fields):
            params[f"fields[{i}]"] = f

    r = httpx.get(_base_url(table), headers=_headers(), params=params, timeout=10)
    if r.status_code == 401:
        raise RuntimeError(f"401 AIRTABLE_API_KEY לא תקין | body: {r.text[:200]}")
    if r.status_code == 403:
        raise RuntimeError(f"403 אין הרשאה לטבלה '{table}' | body: {r.text[:200]}")
    if r.status_code == 404:
        raise RuntimeError(f"404 טבלה '{table}' לא נמצאה | body: {r.text[:200]}")
    r.raise_for_status()
    return r.json().get("records", [])

def _post(table: str, fields: dict) -> dict:
    record = airtable_create(table, fields, source="crm")
    if record is None:
        raise RuntimeError(f"Airtable create failed for table '{table}'")
    return record

def _patch(table: str, record_id: str, fields: dict) -> dict:
    if not airtable_patch(table, record_id, fields, source="crm"):
        raise RuntimeError(f"Airtable update failed for table '{table}', record '{record_id}'")
    return {"id": record_id}

def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%y")
    except Exception:
        return iso or "—"


# ══════════════════════════════════════════════════
# CONTACTS
# ══════════════════════════════════════════════════

@dataclass(frozen=True)
class ContactResult:
    status: str
    record_id: str = ""
    normalized_phone: str = ""
    matches: tuple = ()
    error: str = ""


def _normalize_contact_phone(phone) -> str:
    """Return the exact Contact lookup/write representation, or empty if invalid."""
    if phone is None:
        return ""
    raw = str(phone).strip()
    if not raw or not re.fullmatch(r"[+\d\s().-]+", raw):
        return ""
    if "+" in raw[1:]:
        return ""

    has_plus = raw.startswith("+")
    digits = re.sub(r"[\s().-]", "", raw[1:] if has_plus else raw)
    if not digits.isdigit():
        return ""
    if digits.startswith("00972"):
        digits = digits[2:]

    if digits.startswith("972"):
        return f"+{digits}" if re.fullmatch(r"972\d{9}", digits) else ""
    if not has_plus and re.fullmatch(r"0\d{8,9}", digits):
        return f"+972{digits[1:]}"
    if has_plus and re.fullmatch(r"\d{8,15}", digits):
        return f"+{digits}"
    return ""


def _contact_phone_equivalents(normalized: str) -> tuple:
    """Return the bounded exact-lookup set for one canonical phone."""
    if normalized.startswith("+972"):
        national = normalized[4:]
        return (normalized, normalized[1:], f"00{normalized[1:]}", f"0{national}")
    return (normalized,)


def find_or_create_contact(phone, name, *, email="", company="",
                           contact_type="Client", notes="", lead_source_id="",
                           identity=None, source="", create_writer=None) -> ContactResult:
    """Find exactly by canonical phone, creating only when lookup is empty."""
    normalized = _normalize_contact_phone(phone)
    if not normalized or not name:
        return ContactResult("invalid")
    if not _creds_ok():
        return ContactResult("lookup_error", normalized_phone=normalized,
                             error="missing Airtable credentials")

    records_by_id = {}
    lookup_error = ""
    for equivalent in _contact_phone_equivalents(normalized):
        formula = f"{{{ContactFields.PHONE}}} = '{equivalent}'"
        try:
            records = _get(Tables.CONTACTS, formula, identity=identity)
        except Exception as exc:
            lookup_error = str(exc)
            continue
        for record in records:
            record_id = record.get("id")
            if record_id:
                records_by_id[record_id] = record
    if lookup_error:
        return ContactResult("lookup_error", normalized_phone=normalized,
                             error=lookup_error)
    records = tuple(records_by_id.values())

    if len(records) > 1:
        matches = tuple({"record_id": record.get("id", "")} for record in records)
        return ContactResult("ambiguous", normalized_phone=normalized, matches=matches)
    if records:
        return ContactResult("existing", record_id=records[0].get("id", ""),
                             normalized_phone=normalized)

    fields = {
        ContactFields.NAME: name,
        ContactFields.PHONE: normalized,
        ContactFields.STATUS: ContactStatus.ACTIVE,
    }
    if email:
        fields[ContactFields.EMAIL] = email
    if company:
        fields[ContactFields.COMPANY] = company
    contact_role = {
        ContactType.CLIENT: ContactRoleCategory.CLIENT,
        ContactType.SUPPLIER: ContactRoleCategory.SUPPLIER,
        ContactType.PARTNER: ContactRoleCategory.PARTNER,
        ContactType.LAWYER: ContactRoleCategory.EXPERT,
        ContactType.ACCOUNTANT: ContactRoleCategory.EXPERT,
    }.get(contact_type, contact_type)
    if contact_role:
        fields[ContactFields.ROLE_CATEGORY] = contact_role
    if lead_source_id:
        fields[ContactFields.ORIGIN_LEAD] = [lead_source_id]
    try:
        if create_writer is None:
            record = _post(Tables.CONTACTS, fields)
        else:
            provider_result = create_writer(fields)
            outcome = getattr(provider_result, "status", "")
            if outcome == "outcome_unknown":
                return ContactResult("outcome_unknown", normalized_phone=normalized,
                                     error=getattr(provider_result, "error", ""))
            if outcome == "failed":
                return ContactResult("create_error", normalized_phone=normalized,
                                     error=getattr(provider_result, "error", ""))
            if outcome and outcome != "created":
                return ContactResult("create_error", normalized_phone=normalized,
                                     error=f"unexpected provider outcome: {outcome}")
            record = getattr(provider_result, "record", provider_result)
        record_id = (record or {}).get("id", "")
    except Exception as exc:
        if create_writer is not None:
            return ContactResult("outcome_unknown", normalized_phone=normalized,
                                 error=str(exc))
        return ContactResult("lookup_error", normalized_phone=normalized, error=str(exc))
    if not record_id:
        status = "outcome_unknown" if create_writer is not None else "lookup_error"
        return ContactResult(status, normalized_phone=normalized,
                             error="Contact create returned no record id")
    return ContactResult("created", record_id=record_id,
                         normalized_phone=normalized)

def crm_add_contact(name: str, phone: str = "", email: str = "",
                    contact_type: str = ContactType.CLIENT,
                    company: str = "", notes: str = "",
                    lead_source_id: str = "") -> ContactResult:
    """Find or create a Contact through the canonical deduplication gate."""
    return find_or_create_contact(
        phone, name,
        email=email,
        company=company,
        contact_type=contact_type,
        notes=notes,
        lead_source_id=lead_source_id,
        source="crm_add_contact",
    )


def crm_find_contact(query: str, identity=None) -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"
    try:
        safe = str(query).replace("'", "\\'")
        formula = (
            f"OR(FIND(LOWER('{safe}'), LOWER({{{ContactFields.NAME}}})), "
            f"FIND(LOWER('{safe}'), LOWER({{{ContactFields.COMPANY}}})))"
        )
        records = _get(Tables.CONTACTS, formula, identity=identity)
        if not records:
            return f"🔍 לא נמצא איש קשר עם '{query}'"

        lines = [f"🔍 *נמצאו {len(records)} תוצאות:*\n"]
        for r in records:
            f = r.get("fields", {})
            lines.append(
                f"• *{f.get(ContactFields.NAME, '?')}*"
                f" | {f.get(ContactFields.STATUS, '?')}"
                f" | 📞 {f.get(ContactFields.PHONE, '—')}"
                f" | 🏢 {f.get(ContactFields.COMPANY, '—')}"
                f"\n  ID: `{r['id']}`"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"crm_find_contact: {e}")
        return f"❌ שגיאה בחיפוש: {e}"


def crm_update_last_contact(record_id: str) -> str:
    if not record_id:
        return "❌ חסר record_id"
    try:
        _patch(Tables.CONTACTS, record_id,
               {ContactFields.FOLLOWUP_DATE: date.today().isoformat()})
        return f"✅ תאריך קשר אחרון עודכן ל-{date.today().strftime('%d/%m/%y')}"
    except Exception as e:
        return f"❌ שגיאה בעדכון: {e}"


def crm_list_contacts(contact_type: str = "", identity=None) -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"
    try:
        formula = f"{{סטטוס}} = '{ContactStatus.ACTIVE}'"
        if contact_type:
            formula = f"AND({formula}, {{{ContactFields.ROLE_CATEGORY}}} = '{contact_type}')"
        records = _get(Tables.CONTACTS, formula, identity=identity)
        if not records:
            return "📭 אין אנשי קשר פעילים"

        lines = [f"👥 *אנשי קשר פעילים ({len(records)}):*\n"]
        for r in records:
            f = r.get("fields", {})
            followup = _fmt_date(f.get(ContactFields.FOLLOWUP_DATE, ""))
            lines.append(
                f"• *{f.get(ContactFields.NAME, '?')}*"
                f" [{f.get(ContactFields.STATUS, '?')}]"
                f" | פולו אפ: {followup}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ שגיאה: {e}"


# ══════════════════════════════════════════════════
# DEALS
# ══════════════════════════════════════════════════

def crm_add_deal(name: str, address: str, price: float,
                 funding_cost_pct: float, contact_id: str = "",
                 deadline: str = "", notes: str = "") -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"

    ok, warning = validate_funding_cost(funding_cost_pct)
    prefix = warning + "\n\n" if not ok else ""

    try:
        roi = round(((price * 0.15) / price) * 100, 2)
        fields = {
            DealFields.NAME:         name,
            DealFields.ADDRESS:      address,
            DealFields.STATUS:       DealStage.OPPORTUNITY,
            DealFields.PRICE:        price,
            DealFields.FUNDING_COST: funding_cost_pct,
            DealFields.ROI:          roi,
            DealFields.RISK_LEVEL:   RiskLevel.MEDIUM,
        }
        if contact_id: fields[DealFields.CONTACT]  = [contact_id]
        if deadline:   fields[DealFields.DEADLINE]  = deadline
        if notes:      fields[DealFields.NOTES]     = notes

        rec = _post(Tables.DEALS, fields)
        return (
            f"{prefix}"
            f"🏠 *עסקה נוספה:* {name}\n"
            f"📍 {address}\n"
            f"💰 ₪{price:,.0f} | מימון: {funding_cost_pct}%\n"
            f"ID: `{rec['id']}`"
        )
    except Exception as e:
        logger.error(f"crm_add_deal: {e}")
        return f"❌ שגיאה בהוספת עסקה: {e}"


def crm_update_deal_status(record_id: str, status: str, notes: str = "") -> str:
    canonical_status = {
        DealStatus.PROSPECT: DealStage.OPPORTUNITY,
        DealStatus.DUE_DILIGENCE: DealStage.NEGOTIATION,
        DealStatus.ACTIVE: DealStage.NEGOTIATION,
        DealStatus.CLOSED: DealStage.CLOSED_WIN,
        DealStatus.CANCELLED: DealStage.CLOSED_LOSS,
    }.get(status, status)
    valid = [DealStatus.PROSPECT, DealStatus.DUE_DILIGENCE,
             DealStatus.ACTIVE, DealStatus.CLOSED, DealStatus.CANCELLED]
    if status not in valid:
        return f"❌ סטטוס לא חוקי. אפשרויות: {', '.join(valid)}"
    try:
        fields = {DealFields.STATUS: canonical_status}
        if notes: fields[DealFields.NOTES] = notes
        _patch(Tables.DEALS, record_id, fields)
        return f"✅ עסקה `{record_id}` עודכנה → *{status}*"
    except Exception as e:
        return f"❌ שגיאה: {e}"


def crm_list_deals(status: str = "", identity=None) -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"
    try:
        if status == "Active":
            formula = f"NOT(OR({{{DealFields.STAGE}}}='{DealStage.CLOSED_WIN}', {{{DealFields.STAGE}}}='{DealStage.CLOSED_LOSS}'))"
        elif status:
            formula = f"{{שלב}} = '{status}'"
        else:
            formula = ""
        records = _get(Tables.DEALS, formula, identity=identity)
        if not records:
            return "📭 אין עסקאות" + (f" בסטטוס '{status}'" if status else "")

        lines = [f"🏠 *עסקאות ({len(records)}):*\n"]
        for r in records:
            f = r.get("fields", {})
            funding = f.get(DealFields.FUNDING_COST, 0)
            flag    = " ⚠️" if funding > 9 else ""
            lines.append(
                f"• *{f.get(DealFields.NAME, '?')}*"
                f" | {f.get(DealFields.STATUS, '?')}"
                f" | ₪{f.get(DealFields.PRICE, 0):,.0f}"
                f" | מימון: {funding}%{flag}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ שגיאה: {e}"


# ══════════════════════════════════════════════════
# PAYMENTS
# ══════════════════════════════════════════════════

def crm_add_payment(name: str, amount: float, due_date: str,
                    deal_id: str = "", contact_id: str = "", notes: str = "") -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"
    try:
        fields = {
            PaymentFields.NAME:     name,
            PaymentFields.AMOUNT:   amount,
            PaymentFields.DUE_DATE: due_date,
            PaymentFields.STATUS:   PaymentStatus.IN_PROGRESS,
        }
        if deal_id:    fields[PaymentFields.DEAL]    = [deal_id]

        rec = _post(Tables.PAYMENTS, fields)

        due_dt     = datetime.fromisoformat(due_date)
        remind_str = (due_dt - timedelta(days=3)).strftime("%d/%m/%y")

        return (
            f"✅ *תשלום נרשם:* {name}\n"
            f"💰 ₪{amount:,.0f} | לתשלום: {_fmt_date(due_date)}\n"
            f"🔔 תזכורת תישלח: {remind_str} (חוק #8)\n"
            f"ID: `{rec['id']}`"
        )
    except Exception as e:
        logger.error(f"crm_add_payment: {e}")
        return f"❌ שגיאה בהוספת תשלום: {e}"


def crm_upcoming_payments(days_ahead: int = 7, identity=None) -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"
    try:
        today    = date.today()
        deadline = today + timedelta(days=days_ahead)
        formula  = (
            f"AND("
            f"{{{PaymentFields.STATUS}}} = '{PaymentStatus.IN_PROGRESS}', "
            f"IS_BEFORE({{{PaymentFields.DUE_DATE}}}, '{deadline.isoformat()}'), "
            f"IS_AFTER({{{PaymentFields.DUE_DATE}}}, '{today.isoformat()}')"
            f")"
        )
        records = _get(Tables.PAYMENTS, formula, identity=identity)
        if not records:
            return f"✅ אין תשלומים ב-{days_ahead} הימים הקרובים"

        lines = [f"💳 *תשלומים קרובים ({len(records)}):*\n"]
        total = 0
        for r in records:
            f      = r.get("fields", {})
            amount = f.get(PaymentFields.AMOUNT, 0)
            total += amount
            due    = _fmt_date(f.get(PaymentFields.DUE_DATE, ""))
            lines.append(
                f"• *{f.get(PaymentFields.NAME, '?')}*"
                f" | ₪{amount:,.0f} | {due}"
            )
        lines.append(f"\n💰 *סה\"כ: ₪{total:,.0f}*")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ שגיאה: {e}"


def crm_mark_payment_paid(record_id: str) -> str:
    if not record_id:
        return "❌ חסר record_id"
    try:
        _patch(Tables.PAYMENTS, record_id, {PaymentFields.STATUS: PaymentStatus.PAID})
        return f"✅ תשלום `{record_id}` סומן כ-*שולם*"
    except Exception as e:
        return f"❌ שגיאה: {e}"


def crm_overdue_payments(identity=None) -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"
    try:
        today   = date.today().isoformat()
        formula = (
            f"AND("
            f"{{{PaymentFields.STATUS}}} = '{PaymentStatus.IN_PROGRESS}', "
            f"IS_BEFORE({{{PaymentFields.DUE_DATE}}}, '{today}')"
            f")"
        )
        records = _get(Tables.PAYMENTS, formula, identity=identity)
        if not records:
            return "✅ אין תשלומים שעברו מועד"

        updated = 0
        lines   = [f"🚨 *{len(records)} תשלומים באיחור:*\n"]
        for r in records:
            f      = r.get("fields", {})
            amount = f.get(PaymentFields.AMOUNT, 0)
            due    = _fmt_date(f.get(PaymentFields.DUE_DATE, ""))
            lines.append(f"• *{f.get(PaymentFields.NAME, '?')}* | ₪{amount:,.0f} | היה: {due}")
            try:
                _patch(Tables.PAYMENTS, r["id"], {PaymentFields.STATUS: PaymentStatus.OVERDUE})
                updated += 1
            except Exception:
                pass

        lines.append(f"\n⚠️ {updated} רשומות עודכנו ל-Overdue ב-Airtable")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ שגיאה: {e}"
