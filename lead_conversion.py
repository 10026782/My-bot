# lead_conversion.py — Lead → Contact conversion
#
# קובץ עצמאי. לא נוגע ב-app.py מעבר לרישום פקודת /convert (כמו /done, /quest).
# מומר רק כש-LEAD_AUTO_CONVERT דלוק (כבוי כברירת מחדל — Iron Rule #1).
#
# למה owner-only command ולא agent tool עם approval flow:
# ה-event_bus approval flow קיים אך לא תמיד מחווט עד הסוף (ראה lead_recovery).
# פקודת /done קיימת כבר כתבנית: owner מקליד פקודה מפורשת = האישור עצמו.
# אותה תבנית כאן — בטוחה, פשוטה, ועובדת היום.
#
# F14 note: crm_add_contact() already routes through crm.py's canonical
# find_or_create_contact() dedup gate (tools/airtable_gateway.airtable_create
# underneath) — it is not a raw provider write. The remaining gap this file
# used to carry was that its own call omitted `identity`, so the dedup
# lookup ran untenant-scoped; convert_lead_to_contact() now accepts an
# `identity` and threads it through, matching the F14-migrated dispatcher/
# approval_actions call sites. Direct `from crm import ...` (rather than via
# tools/dispatcher.py) remains a deliberate, tracked LEGACY import per
# tools/audit_dispatcher_bypass.py — non-blocking, owner-only command,
# LEAD_AUTO_CONVERT=false default, audit-logged below.

import logging
from datetime import datetime, timezone

from feature_flags import is_enabled
from airtable_schema import Tables, LeadFields, LeadStatus, LeadOutcome
from core.query_contract import any_of, contains
from crm import crm_add_contact

logger = logging.getLogger(__name__)

FLAG = "LEAD_AUTO_CONVERT"


def convert_lead_to_contact(query: str, identity=None) -> tuple[bool, str]:
    """
    מחפש ליד לפי שם או טלפון, יוצר ממנו איש קשר ב-CRM,
    ומסמן את הליד כ-converted (status + converted_at).
    מחזיר (success, הודעה למשתמש).

    identity: the resolved caller (owner/admin) from app.py's /convert
    command, threaded through to crm_add_contact()'s dedup lookup (F14
    tenant-scoped matching) and used for the audit log entry instead of a
    fabricated system identity. None (default) preserves the prior
    behavior for callers that don't have one (tests).
    """
    if not is_enabled(FLAG):
        return False, f"⚠️ המרת לידים כבויה. הפעל עם משתנה הסביבה {FLAG}=true."

    if not query:
        return False, "❌ חסר שם או טלפון לחיפוש."

    from tma_api import _at_list, _at_patch, record_fields, record_id  # lazy import — כמו ב-/done

    leads = _at_list(
        Tables.LEADS,
        any_of(contains("Name", query), contains("phone", query)),
        max_records=5,
    )

    if not leads:
        return False, f"🔍 לא נמצא ליד התואם '{query}'."

    if len(leads) > 1:
        names = ", ".join(record_fields(l).get(LeadFields.NAME, "?") for l in leads)
        return False, f"⚠️ נמצאו כמה לידים תואמים: {names}.\nנסה שם או טלפון מדויקים יותר."

    lead = leads[0]
    lf   = record_fields(lead)
    name = lf.get(LeadFields.NAME, "ליד ללא שם")

    if lf.get(LeadFields.STATUS, "") == "converted" or lf.get(LeadFields.CONVERTED_AT, ""):
        return False, f"ℹ️ הליד *{name}* כבר הומר לאיש קשר בעבר."

    phone = lf.get(LeadFields.PHONE, "")
    notes_parts = []
    if lf.get(LeadFields.SUMMARY):
        notes_parts.append(f"תקציר ליד: {lf[LeadFields.SUMMARY]}")
    if lf.get(LeadFields.SOURCE):
        notes_parts.append(f"מקור: {lf[LeadFields.SOURCE]}")
    notes = "\n".join(notes_parts)

    contact_result = crm_add_contact(name=name, phone=phone, notes=notes,
                                      lead_source_id=record_id(lead, required=True),
                                      identity=identity)
    if contact_result.status not in ("created", "existing"):
        messages = {
            "ambiguous": "⚠️ נמצאו כמה אנשי קשר תואמים; ההמרה נעצרה.",
            "invalid": "❌ מספר הטלפון חסר או אינו תקין; ההמרה נעצרה.",
            "lookup_error": "❌ לא ניתן לאמת את איש הקשר; ההמרה נעצרה.",
        }
        return False, messages.get(contact_result.status,
                                   "❌ יצירת איש קשר נכשלה; ההמרה נעצרה.")

    try:
        from tools.airtable_security import audit_log_airtable

        audit_identity = identity
        if audit_identity is None:
            class _SystemIdentity:
                tenant_id = "system"
                user_id   = "lead_conversion"
                role      = "system"
            audit_identity = _SystemIdentity()

        audit_log_airtable(
            "create_contact_from_lead",
            audit_identity,
            {"table": Tables.CONTACTS},
            f"lead→contact: {name} | lead_id={record_id(lead, required=True)}",
        )
    except Exception as _audit_err:
        logger.warning(f"[LeadConversion] audit log failed (non-fatal): {_audit_err}")

    contact_id = contact_result.record_id

    patched = _at_patch(Tables.LEADS, record_id(lead, required=True), {
        LeadFields.STATUS:       LeadStatus.DONE,
        LeadFields.OUTCOME:      LeadOutcome.CONVERTED,
        LeadFields.CONVERTED_AT: datetime.now(tz=timezone.utc).isoformat(),
    })

    contact_kind = "חדש" if contact_result.status == "created" else "קיים"
    msg = f"✅ הליד *{name}* הומר לאיש קשר {contact_kind}."
    if not patched:
        msg += "\n⚠️ (סטטוס/Business Outcome של הליד לא עודכנו — בדוק ידנית ב-Airtable)"

    logger.info(f"[LeadConversion] '{query}' → {name} → contact {contact_id or '?'}")
    return True, msg
