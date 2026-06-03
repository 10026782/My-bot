# crm.py
# CRM Module — אנשי קשר, עסקאות, תשלומים
# כל פונקציה מחזירה string מוכן לשליחה בטלגרם

import os
import httpx
import logging
import urllib.parse
from datetime import datetime, date, timedelta

from airtable_schema import (
    Tables,
    ContactFields, ContactType, ContactStatus,
    DealFields, DealStatus, RiskLevel,
    PaymentFields, PaymentStatus,
    validate_funding_cost,
)

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
    r = httpx.post(_base_url(table), headers=_headers(),
                   json={"fields": fields}, timeout=10)
    if r.status_code == 401:
        raise RuntimeError("AIRTABLE_API_KEY לא תקין או פג — עדכן ב-Render")
    if r.status_code == 403:
        raise RuntimeError(f"אין הרשאה לטבלה '{table}' — בדוק שהטבלה קיימת ושה-token מורשה")
    r.raise_for_status()
    return r.json()

def _patch(table: str, record_id: str, fields: dict) -> dict:
    r = httpx.patch(f"{_base_url(table)}/{record_id}", headers=_headers(),
                    json={"fields": fields}, timeout=10)
    if r.status_code == 401:
        raise RuntimeError("AIRTABLE_API_KEY לא תקין או פג — עדכן ב-Render")
    if r.status_code == 403:
        raise RuntimeError(f"אין הרשאה לטבלה '{table}' / רשומה '{record_id}'")
    r.raise_for_status()
    return r.json()

def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%y")
    except Exception:
        return iso or "—"


# ══════════════════════════════════════════════════
# CONTACTS
# ══════════════════════════════════════════════════

def crm_add_contact(name: str, phone: str = "", email: str = "",
                    contact_type: str = ContactType.CLIENT,
                    company: str = "", notes: str = "") -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"
    if not name:
        return "❌ שם הוא שדה חובה"
    try:
        fields = {
            ContactFields.NAME:         name,
            ContactFields.STATUS:       ContactStatus.ACTIVE,
            ContactFields.TYPE:         contact_type,
            ContactFields.LAST_CONTACT: date.today().isoformat(),
        }
        if phone:   fields[ContactFields.PHONE]   = phone
        if email:   fields[ContactFields.EMAIL]   = email
        if company: fields[ContactFields.COMPANY] = company
        if notes:   fields[ContactFields.NOTES]   = notes

        rec = _post(Tables.CONTACTS, fields)
        return f"✅ איש קשר נוסף: *{name}* | ID: `{rec['id']}`"
    except Exception as e:
        logger.error(f"crm_add_contact: {e}")
        return f"❌ שגיאה בהוספת איש קשר: {e}"


def crm_find_contact(query: str, identity=None) -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"
    try:
        safe = str(query).replace("'", "\\'")
        formula = (
            f"OR(FIND(LOWER('{safe}'), LOWER({{Name}})), "
            f"FIND(LOWER('{safe}'), LOWER({{Company}})))"
        )
        records = _get(Tables.CONTACTS, formula, identity=identity)
        if not records:
            return f"🔍 לא נמצא איש קשר עם '{query}'"

        lines = [f"🔍 *נמצאו {len(records)} תוצאות:*\n"]
        for r in records:
            f = r.get("fields", {})
            lines.append(
                f"• *{f.get(ContactFields.NAME, '?')}*"
                f" | {f.get(ContactFields.TYPE, '?')}"
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
               {ContactFields.LAST_CONTACT: date.today().isoformat()})
        return f"✅ תאריך קשר אחרון עודכן ל-{date.today().strftime('%d/%m/%y')}"
    except Exception as e:
        return f"❌ שגיאה בעדכון: {e}"


def crm_list_contacts(contact_type: str = "", identity=None) -> str:
    if not _creds_ok():
        return "❌ חסרים מפתחות Airtable"
    try:
        formula = f"{{סטטוס}} = '{ContactStatus.ACTIVE}'"
        if contact_type:
            formula = f"AND({formula}, {{Type}} = '{contact_type}')"
        records = _get(Tables.CONTACTS, formula, identity=identity)
        if not records:
            return "📭 אין אנשי קשר פעילים"

        lines = [f"👥 *אנשי קשר פעילים ({len(records)}):*\n"]
        for r in records:
            f = r.get("fields", {})
            last = _fmt_date(f.get(ContactFields.LAST_CONTACT, ""))
            lines.append(
                f"• *{f.get(ContactFields.NAME, '?')}*"
                f" [{f.get(ContactFields.TYPE, '?')}]"
                f" | קשר אחרון: {last}"
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
            DealFields.STATUS:       DealStatus.PROSPECT,
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
    valid = [DealStatus.PROSPECT, DealStatus.DUE_DILIGENCE,
             DealStatus.ACTIVE, DealStatus.CLOSED, DealStatus.CANCELLED]
    if status not in valid:
        return f"❌ סטטוס לא חוקי. אפשרויות: {', '.join(valid)}"
    try:
        fields = {DealFields.STATUS: status}
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
            formula = "NOT(OR({שלב}='סגור-ניצחון', {שלב}='סגור-הפסד'))"
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
            PaymentFields.STATUS:   PaymentStatus.PENDING,
        }
        if deal_id:    fields[PaymentFields.DEAL]    = [deal_id]
        if contact_id: fields[PaymentFields.CONTACT] = [contact_id]
        if notes:      fields[PaymentFields.NOTES]   = notes

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
            f"{{סטטוס}} = '{PaymentStatus.PENDING}', "
            f"IS_BEFORE({{תאריך}}, '{deadline.isoformat()}'), "
            f"IS_AFTER({{תאריך}}, '{today.isoformat()}')"
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
            f"{{סטטוס}} = '{PaymentStatus.PENDING}', "
            f"IS_BEFORE({{תאריך}}, '{today}')"
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
