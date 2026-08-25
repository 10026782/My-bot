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
# NOTE: crm_add_contact עוקף את airtable_gateway write-path (אין tenant scope / gateway validation).
# Mitigated: owner-only + LEAD_AUTO_CONVERT=false default + audit log added here.
# TODO (future): migrate to gateway when crm.py is refactored.

import logging
from datetime import datetime, timezone

from feature_flags import is_enabled
from airtable_schema import Tables, LeadFields, LeadStatus, LeadOutcome
from core.query_contract import any_of, contains
from crm import crm_add_contact

logger = logging.getLogger(__name__)

FLAG = "LEAD_AUTO_CONVERT"


def convert_lead_to_contact(query: str) -> tuple[bool, str]:
    """
    מחפש ליד לפי שם או טלפון, יוצר ממנו איש קשר ב-CRM,
    ומסמן את הליד כ-converted (status + converted_at).
    מחזיר (success, הודעה למשתמש).
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
                                      lead_source_id=record_id(lead, required=True))
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

        class _SystemIdentity:
            tenant_id = "system"
            user_id   = "lead_conversion"
            role      = "system"

        audit_log_airtable(
            "create_contact_from_lead",
            _SystemIdentity(),
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
