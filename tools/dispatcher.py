# tools/dispatcher.py — Tool Dispatcher v2
# נקודת כניסה יחידה לכל הכלים.
#
# זרימה: enforce(tool, identity) → dispatch_tool(tool, inputs, identity)

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from .drive_tools    import search_drive, read_drive_file
from .calendar_tools import calendar_get_events, calendar_create_event
from .gmail_tools    import gmail_draft, gmail_send_draft, gmail_read
from .sheets_tools   import sheets_append
from .airtable_tools    import airtable_get, airtable_add, airtable_update, airtable_get_schema
from .contact_resolver  import resolve_contact

if TYPE_CHECKING:
    from identity import Identity

logger = logging.getLogger(__name__)


def dispatch_tool(name: str, inputs: dict, identity: "Identity | None" = None) -> str:
    """
    מקבל שם כלי + inputs + identity ומחזיר תוצאה כטקסט.

    identity מועברת לכלים שצריכים לסנן לפי tenant/user.
    כלים שלא צריכים אותה — מתעלמים ממנה.
    """
    tenant_id = identity.tenant_id if identity else "unknown"
    user_id   = identity.user_id   if identity else "unknown"

    logger.info(f"[Dispatch] {name} | tenant={tenant_id} user={user_id} | inputs={str(inputs)[:80]}")

    try:
        match name:

            # ── Drive ────────────────────────────────
            case "search_drive":
                return search_drive(inputs["query"])
            case "read_drive_file":
                return read_drive_file(inputs["file_name"])

            # ── Calendar ─────────────────────────────
            case "calendar_get_events":
                return calendar_get_events(inputs.get("days_ahead", 7))
            case "calendar_create_event":
                return calendar_create_event(
                    inputs["summary"],
                    inputs["start_time"],
                    inputs.get("duration_minutes", 60)
                )

            # ── Gmail ─────────────────────────────────
            case "gmail_draft":
                return gmail_draft(inputs["to"], inputs["subject"], inputs["body"])
            case "gmail_send_draft":
                logger.warning(
                    f"[Dispatch] gmail_send_draft | "
                    f"tenant={tenant_id} user={user_id} draft_id={inputs.get('draft_id')}"
                )
                return gmail_send_draft(inputs["draft_id"])
            case "gmail_read":
                return gmail_read(inputs.get("max_results", 3))

            # ── Sheets ────────────────────────────────
            case "sheets_append":
                return sheets_append(inputs["sheet_name"], inputs["row_data"])

            # ── Airtable ─────────────────────────────
            case "airtable_get":
                filter_formula = inputs.get("filter", "")
                if identity and identity.is_external and not filter_formula:
                    # lead/guest רואה רק נתוני עצמו
                    filter_formula = f"{{user_id}}='{user_id}'"
                return airtable_get(inputs["table"], filter_formula)

            case "airtable_add":
                fields = dict(inputs["fields"])
                # הזרקת tenant_id ו-domain_id אוטומטית לכל רשומה חדשה
                if identity:
                    fields.setdefault("tenant_id", tenant_id)
                    fields.setdefault("domain_id", identity.domain_id)
                    fields.setdefault("owner_user_id", user_id)
                return airtable_add(inputs["table"], fields)

            case "airtable_update":
                return airtable_update(
                    inputs["table"], inputs["record_id"], inputs["fields"]
                )

            case "airtable_get_schema":
                return airtable_get_schema()

            # ── Contact Resolver (N03) ────────────────
            case "resolve_contact":
                return resolve_contact(inputs["name_query"], identity)

            # ── Unknown ───────────────────────────────
            case _:
                logger.warning(f"[Dispatch] Unknown tool: {name}")
                return f"⚠️ כלי לא מוכר: {name}"

    except KeyError as e:
        logger.error(f"[Dispatch] {name} missing param: {e}")
        return f"❌ פרמטר חסר בכלי {name}: {e}"
    except RuntimeError as e:
        logger.error(f"[Dispatch] {name} config error: {e}")
        return f"❌ {e}"
    except Exception as e:
        logger.error(f"[Dispatch] {name} error: {e}", exc_info=True)
        return f"❌ שגיאה בכלי {name}: {e}"
