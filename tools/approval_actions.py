# tools/approval_actions.py — PR-0C ActionGateway adapters
#
# media_save_to_memory / send_followup / send_recovery were historically driven
# by ad-hoc event_bus.subscribe("<action>.confirmed", ...) handlers (app.py,
# media_handler.py) fed by event_bus.request_approval(). ActionGateway only
# knows how to execute a contract via dispatch_tool(tool_name, tool_inputs,
# contract_id) (core/action_gateway.py's _executor closure) — there is no
# generic "run an arbitrary callback" path. These three functions are the real
# tool implementations behind that contract, so the three actions can be
# proposed/approved/executed through ActionGateway like any other tool.
#
# Logic here mirrors app.py::_handle_send_followup_confirmed /
# _handle_send_recovery_confirmed and media_handler.py::_save_transcript_to_memory
# exactly (no behavior change) — only the call shape changed: explicit kwargs
# instead of a payload dict, and the C53-A structured {ok, tool, external_id,
# evidence, user_message} contract instead of a raw string.

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _tool_result(
    *,
    ok: bool,
    tool: str,
    external_id: str = "",
    evidence: dict | None = None,
    user_message: str = "",
) -> dict:
    """Structured C53-A result contract — same shape as tools/airtable_tools.py's _tool_result."""
    return {
        "ok": ok,
        "tool": tool,
        "external_id": external_id or "",
        "evidence": evidence or {},
        "user_message": user_message,
    }


def media_save_to_memory(transcript: str, domain: str = "general", source: str = "media_handler") -> dict:
    """Writes a voice transcript to Business Memory via the Airtable gateway.

    Mirrors media_handler.py::_save_transcript_to_memory exactly.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from airtable_schema import BusinessMemoryFields as BMF
    from airtable_schema import Tables
    from cmd_update import normalize_business_memory_fields
    from tools.airtable_gateway import airtable_create

    fields = {
        BMF.TITLE: f"הודעה קולית — {datetime.now(ZoneInfo('Asia/Jerusalem')).strftime('%d/%m/%Y')}",
        BMF.DESCRIPTION: transcript,
        BMF.DATE: datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
        BMF.EVENT_TYPE: "Other",
        BMF.IMPACT: "Voice Note",
    }
    fields = normalize_business_memory_fields(fields, domain)
    record = airtable_create(Tables.BUSINESS_MEMORY, fields, source=f"media_handler:{source}")
    if record:
        rec_id = record.get("id", "") or ""
        logger.info("[approval_actions] media_save_to_memory saved id=%s", rec_id)
        return _tool_result(
            ok=bool(rec_id),
            tool="media_save_to_memory",
            external_id=rec_id,
            evidence={"record_id": rec_id, "table": Tables.BUSINESS_MEMORY},
            user_message="✅ נשמר ב-Business Memory",
        )
    logger.warning("[approval_actions] media_save_to_memory failed")
    return _tool_result(
        ok=False, tool="media_save_to_memory",
        user_message="❌ שמירה ל-Business Memory נכשלה",
    )


def send_followup(
    chat_id: str, draft: str = "", contact_name: str = "", channel: str = "", memory_key: str = "",
) -> dict:
    """Delivers an approved followup draft to the owner for manual forwarding.

    Does NOT send outbound WhatsApp to the lead (blocked on Meta, N05-C).
    Mirrors app.py::_handle_send_followup_confirmed exactly (N05-B), including
    the lack of a delivery_success check before incrementing followup_count —
    an existing asymmetry vs send_recovery, not something this migration fixes.
    """
    from core.output_gateway import AudienceClass, OutboundEnvelope, OutputChannel, send_outbound

    msg = (f"📋 פולואפ מאושר — לשליחה ידנית ({channel}):\n"
           f"אל: {contact_name}\n\n{draft}")

    try:
        result = send_outbound(OutboundEnvelope(
            channel=OutputChannel.TELEGRAM_OWNER,
            recipient=chat_id,
            body=msg,
            audience=AudienceClass.INTERNAL,
            source_module="tools.approval_actions.send_followup",
            source_ref=memory_key,
            domain="followup",
        ))
    except Exception as e:
        logger.error(f"[approval_actions] send_followup notify owner failed: {e}")
        return _tool_result(ok=False, tool="send_followup", user_message=f"⚠️ שגיאה בהצגת הטיוטה: {e}")

    if memory_key:
        try:
            from lead_memory import lead_memory
            state = lead_memory.get(memory_key)
            lead_memory.update(memory_key, followup_count=state.followup_count + 1)
        except Exception as e:
            logger.warning(f"[approval_actions] send_followup followup_count update failed: {e}")

    return _tool_result(
        ok=True, tool="send_followup",
        external_id=getattr(result, "audit_id", "") or "",
        evidence={"audit_id": getattr(result, "audit_id", "") or ""},
        user_message="✅ הטיוטה נשלחה אליך להעברה ידנית",
    )


def send_recovery(
    chat_id: str, draft: str = "", contact_name: str = "", channel: str = "",
    memory_key: str = "", tier: str = "",
) -> dict:
    """Delivers an approved recovery draft to the owner for manual forwarding.

    Does NOT send outbound WhatsApp to the lead (blocked on Meta, N05-C).
    Mirrors app.py::_handle_send_recovery_confirmed exactly (C53 FIX-1),
    including leaving recovery_count untouched — TELEGRAM_OWNER delivery is
    only a draft preview, not evidence the customer received the message.
    """
    from core.output_gateway import AudienceClass, OutboundEnvelope, OutputChannel, send_outbound

    msg = (f"♻️ Recovery מאושר — לשליחה ידנית ({channel}, {tier}):\n"
           f"אל: {contact_name}\n\n{draft}")

    try:
        result = send_outbound(OutboundEnvelope(
            channel=OutputChannel.TELEGRAM_OWNER,
            recipient=chat_id,
            body=msg,
            audience=AudienceClass.INTERNAL,
            source_module="tools.approval_actions.send_recovery",
            source_ref=memory_key,
            domain="recovery",
        ))
    except Exception as e:
        logger.error(f"[approval_actions] send_recovery notify owner failed: {e}")
        return _tool_result(ok=False, tool="send_recovery", user_message=f"⚠️ שגיאה בהצגת הטיוטה: {e}")

    owner_delivery = getattr(result, "action_result", None)
    if not owner_delivery or not owner_delivery.delivery_success:
        logger.error(
            "[approval_actions] send_recovery owner delivery not verified | memory_key=%s audit=%s",
            memory_key, getattr(result, "audit_id", ""),
        )
        return _tool_result(
            ok=False, tool="send_recovery",
            user_message="⚠️ האישור נקלט, אך מסירת הטיוטה אליך לא אומתה. ה-recovery לא סומן כהושלם.",
        )

    return _tool_result(
        ok=True, tool="send_recovery",
        external_id=getattr(result, "audit_id", "") or "",
        evidence={"audit_id": getattr(result, "audit_id", "") or ""},
        user_message="✅ הטיוטה נשלחה אליך להעברה ידנית",
    )
