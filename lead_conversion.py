# lead_conversion.py — Lead → Contact conversion, Lead → Deal resolution
#
# קובץ עצמאי. לא נוגע ב-app.py מעבר לרישום פקודות /convert ו-/dealfromlead
# (כמו /done, /quest). convert_lead_to_contact() מומר רק כש-LEAD_AUTO_CONVERT
# דלוק; resolve_lead_for_deal() רק כש-LEAD_TO_DEAL דלוק (שניהם כבויים
# כברירת מחדל — Iron Rule #1).
#
# למה /convert הוא owner-only command ולא agent tool עם approval flow:
# ה-event_bus approval flow קיים אך לא תמיד מחווט עד הסוף (ראה lead_recovery).
# פקודת /done קיימת כבר כתבנית: owner מקליד פקודה מפורשת = האישור עצמו.
# אותה תבנית כאן — בטוחה, פשוטה, ועובדת היום.
#
# resolve_lead_for_deal() (LEAD-TO-DEAL-ORIGIN-LINK, 02/09/2026) שונה: היא
# resolve בלבד, לא ביצוע. הכתיבה בפועל (crm_create_deal) עוברת דרך
# app.py's _queue_deterministic_create_deal() — אותו writer יחיד שהמסלול
# הטקסטואלי "צור עסקה בשם X בתחום Y" כבר משתמש בו, כולל בקשת אישור
# אינטראקטיבית רגילה (לא "הקלדה=אישור" כמו /convert).
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
from crm import crm_add_contact, describe_contact_failure

logger = logging.getLogger(__name__)

FLAG = "LEAD_AUTO_CONVERT"
FLAG_DEAL = "LEAD_TO_DEAL"


def _resolve_single_lead_by_query(query: str) -> tuple[dict | None, str]:
    """מחפש ליד יחיד לפי שם/טלפון. מחזיר (lead_record, error_message) — בדיוק
    אחד מהשניים ריק. חולץ מ-convert_lead_to_contact() כדי ש-resolve_lead_for_deal()
    (LEAD-TO-DEAL-ORIGIN-LINK) ישתמש באותה לוגיקת חיפוש בדיוק, במקום להעתיק
    אותה בשנית."""
    from tma_api import _at_list, record_fields  # lazy import — כמו שאר הקובץ

    leads = _at_list(
        Tables.LEADS,
        any_of(contains("Name", query), contains("phone", query)),
        max_records=5,
    )
    if not leads:
        return None, f"🔍 לא נמצא ליד התואם '{query}'."
    if len(leads) > 1:
        names = ", ".join(record_fields(l).get(LeadFields.NAME, "?") for l in leads)
        return None, f"⚠️ נמצאו כמה לידים תואמים: {names}.\nנסה שם או טלפון מדויקים יותר."
    return leads[0], ""


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

    from tma_api import _at_patch, record_fields, record_id  # lazy import — כמו ב-/done

    lead, err = _resolve_single_lead_by_query(query)
    if lead is None:
        return False, err
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
        # BUG-LEAD-03-class gap (R10 write-path audit, 01/09/2026): this used
        # to be a local, incomplete status->message map (missing the
        # invalid_phone/missing_name split, and any future ContactResult
        # status would silently fall through to a generic message here).
        # describe_contact_failure() is the single shared source for this
        # now — see crm.py.
        return False, f"{describe_contact_failure(contact_result)}\nההמרה נעצרה."

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


def resolve_lead_for_deal(query: str) -> tuple[str, str, str, str]:
    """LEAD-TO-DEAL-ORIGIN-LINK (02/09/2026): מחפש ליד לפי שם/טלפון ומחלץ
    ממנו את מה ש-app.py's _queue_deterministic_create_deal() צריך כדי
    לפתוח עסקה מקושרת — (name, domain, lead_id, error). בדיוק אחד מ-error
    ומ-(name/domain/lead_id) לא ריק.

    אינו מבצע שום כתיבה — resolve בלבד. הכתיבה היחידה (crm_create_deal)
    קורית ב-_queue_deterministic_create_deal() עצמה, שם גם עובר enforce()
    התפקיד ומתועד ה-Turn Coordinator; שומר על אותו writer יחיד שהמסלול
    הטקסטואלי ("צור עסקה בשם X בתחום Y") כבר משתמש בו.

    domain: נקרא ישירות משדה ה-Domain של הליד (LeadFields.DOMAIN) — הוא כבר
    נשמר שם כ-slug קנוני (core/lead_service.py's resolve_domain(), אותה
    טבלה קנונית ש-CRM Deal expects) בזמן יצירת הליד, ולא כמילה בשפה
    חופשית. resolve_domain_word() מופעל בכל זאת כשער אימות/מעבר (ולא
    כניחוש) — בדיוק אותה טבלת מילים משותפת שה-Deal-from-text path כבר
    עובר דרכה (core/router/router.py's parse_deterministic_create_deal),
    ולא טבלת ניחוש שנייה — כדי לתפוס ליד עם domain ריק/לא-קנוני ולהיכשל
    ל-CLARIFY במקום לכתוב ערך שגוי.
    """
    if not is_enabled(FLAG_DEAL):
        return "", "", "", f"⚠️ יצירת עסקה מליד כבויה. הפעל עם משתנה הסביבה {FLAG_DEAL}=true."

    if not query:
        return "", "", "", "❌ חסר שם או טלפון לחיפוש."

    lead, err = _resolve_single_lead_by_query(query)
    if lead is None:
        return "", "", "", err

    from tma_api import record_fields, record_id  # lazy import — כמו שאר הקובץ

    lf = record_fields(lead)
    name = lf.get(LeadFields.NAME, "").strip()
    if not name:
        return "", "", "", "❌ לליד אין שם — לא ניתן לפתוח ממנו עסקה."

    from core.lead_service import resolve_domain_word
    domain = resolve_domain_word(lf.get(LeadFields.DOMAIN, ""))
    if not domain:
        return "", "", "", f"❌ תחום הליד לא מוכר/חסר ({lf.get(LeadFields.DOMAIN, '') or '—'})."

    return name, domain, record_id(lead, required=True), ""
