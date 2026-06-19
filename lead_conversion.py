# lead_conversion.py — Lead → Contact conversion
#
# קובץ עצמאי. לא נוגע ב-app.py מעבר לרישום פקודת /convert (כמו /done, /quest).
# מומר רק כש-LEAD_AUTO_CONVERT דלוק (כבוי כברירת מחדל — Iron Rule #1).
#
# למה owner-only command ולא agent tool עם approval flow:
# ה-event_bus approval flow קיים אך לא תמיד מחווט עד הסוף (ראה lead_recovery).
# פקודת /done קיימת כבר כתבנית: owner מקליד פקודה מפורשת = האישור עצמו.
# אותה תבנית כאן — בטוחה, פשוטה, ועובדת היום.

import logging
import re
from datetime import datetime, timezone

from feature_flags import is_enabled
from airtable_schema import Tables, LeadFields
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

    from tma_api import _at_list, _at_patch  # lazy import — כמו ב-/done

    safe = query.replace("'", "\\'")
    formula = f"OR(SEARCH('{safe}', {{Name}}), SEARCH('{safe}', {{phone}}))"
    leads = _at_list(Tables.LEADS, formula, max_records=5)

    if not leads:
        return False, f"🔍 לא נמצא ליד התואם '{query}'."

    if len(leads) > 1:
        names = ", ".join(l.get("fields", {}).get(LeadFields.NAME, "?") for l in leads)
        return False, f"⚠️ נמצאו כמה לידים תואמים: {names}.\nנסה שם או טלפון מדויקים יותר."

    lead = leads[0]
    lf   = lead.get("fields", {})
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
                                      lead_source_id=lead["id"])
    if "❌" in contact_result:
        return False, f"❌ יצירת איש קשר נכשלה: {contact_result}"

    rec_m      = re.search(r'rec\w+', contact_result)
    contact_id = rec_m.group(0) if rec_m else ""

    patched = _at_patch(Tables.LEADS, lead["id"], {
        LeadFields.STATUS:       "converted",
        LeadFields.CONVERTED_AT: datetime.now(tz=timezone.utc).isoformat(),
    })

    msg = f"✅ הליד *{name}* הומר לאיש קשר חדש.\n{contact_result}"
    if not patched:
        msg += "\n⚠️ (סטטוס הליד לא עודכן ל-converted — בדוק ידנית ב-Airtable)"

    logger.info(f"[LeadConversion] '{query}' → {name} → contact {contact_id or '?'}")
    return True, msg
