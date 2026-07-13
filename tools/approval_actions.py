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

import json
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


# ══════════════════════════════════════════════════
# Phase 4B-2 wiring — tma_write
#
# Extracted from tma_api.py::_execute_tma_write (formerly called directly by
# tma_api.py::_claim_and_execute_approval / bulk_approve() with a raw payload
# dict deserialized from Approvals.CONTEXT_DATA). Approvals is now a
# non-authoritative display projection of ActionContracts — tma_api.py no
# longer performs this write itself; it only creates/approves an
# ActionContract whose approved execution reaches this function through
# dispatch_tool(), exactly like any other tool. Same allowlist, field-
# cleaning, audit-write, and receipt behavior as the original — repackaged
# into the C53-A structured result contract required by
# core.anti_hallucination.verify_execution() (tma_write has an evidence
# validator registered there — see _validate_airtable_evidence via
# tool_registry/anti_hallucination wiring).
# ══════════════════════════════════════════════════

# Allowlist of tables that TMA write-through-approval is permitted to touch.
# "Approvals" deliberately excluded: none of the six mapped TMA business-
# write callers (tma_create_project / tma_update_lead_status / tma_patch_lead
# / tma_set_lead_outcome / tma_create_lead_task / tma_create_followup) needs
# it, and tma_write must never be usable to mutate the Approvals projection
# itself — that table is written only by the propose/approve/reject flow in
# tma_api.py, never through this dispatcher tool.
_TMA_WRITE_ALLOWED_TABLES = {
    "Leads",
    "משימות (Tasks)", "Tasks",
    "ProjectsHub",
    "אנשי קשר (Contacts)", "Contacts",
}


def _clean_tma_write_select_value(value) -> str:
    """Strip whitespace and unwrap any surrounding quote chars from a select value.
    Mirrors tma_api.py::_clean_select_value exactly."""
    if value is None:
        return ""
    value = str(value).strip()
    while len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    return value


def _clean_tma_write_fields(table: str, fields: dict) -> dict:
    """Unwrap embedded quotes from Leads select field values before writing.
    Mirrors tma_api.py::_clean_fields_select_values exactly."""
    if table != "Leads":
        return fields
    from airtable_schema import LeadFields
    lead_select_fields = {LeadFields.STATUS, LeadFields.OUTCOME, LeadFields.NEXT_STEP}
    cleaned = dict(fields)
    for k in lead_select_fields:
        if k in cleaned:
            cleaned[k] = _clean_tma_write_select_value(cleaned[k])
    return cleaned


def _identity_ref(identity) -> str:
    """Mirrors tma_api.py::_identity_ref exactly."""
    return str(getattr(identity, "user_id", "") or getattr(identity, "display_name", "") or "unknown")


def _verify_active_execution_claim(contract_id: str, claim_execution_id: str, approved_by: str) -> bool:
    """Genuine proof of approval — never a caller-constructible dict.

    A plain execution_context dict (contract_id + approved_by) is forgeable
    by any in-process caller of dispatch_tool(); it proves nothing by itself.
    The only real proof that this specific call is the one ActionGateway
    authorized is a live row in PostgreSQL's action_execution_claims table —
    the sole execution-ownership primitive (core/atomic_claim_repository.py)
    — acquired via claim_contract_execution() and still in STATUS_EXECUTING.

    This queries that row directly via get_claim(contract_id) and checks:
      - a claim exists at all (None means no claim was ever acquired — e.g.
        FEATURE_ATOMIC_CLAIMS is OFF, so the legacy dispatch path never
        created one; tma_write fails closed rather than trusting a dict)
      - claim.execution_id matches the execution_id threaded in by
        execute_with_atomic_claim() for THIS acquisition (a forged id
        supplied directly to dispatch_tool cannot match a real row)
      - claim.status is still STATUS_EXECUTING (not completed/failed/
        outcome_unknown — an id copied from a finished claim doesn't count)
      - claim.claimant_id matches the approved_by the caller is asserting,
        so the dict's approved_by cannot be swapped for a different identity
        than the one that actually acquired the claim
    """
    if not contract_id or not claim_execution_id:
        return False
    from core.atomic_claim_repository import get_claim, STATUS_EXECUTING

    claim = get_claim(contract_id)
    if claim is None:
        return False
    return (
        claim.execution_id == claim_execution_id
        and claim.status == STATUS_EXECUTING
        and claim.claimant_id == approved_by
    )


def tma_write(
    op: str,
    table: str,
    action: str = "",
    requested_by: str = "",
    fields: dict | None = None,
    record_id: str = "",
    audit_action: str = "",
    audit_details: str = "",
    identity=None,
    trusted_source: str | None = None,
    execution_context: dict | None = None,
) -> dict:
    """Executes a TMA-originated Airtable write after ActionGateway approval.

    op: "post" (create) or "patch" (update). table must be in the allowlist.
    Mirrors tma_api.py's former _execute_tma_write() behavior exactly (same
    allowlist check, same Leads select-field cleaning, same Interaction Log
    audit write, same receipt shape + best-effort persistence) — only the
    outer envelope changed, from a raw {"ok": ...} dict to the C53-A
    structured contract every other dispatcher tool returns.

    Phase 4B-2 follow-up — direct-dispatch bypass closed: this function
    performs ZERO provider writes unless trusted_source == "tma_api" AND
    execution_context's contract_id + claim_execution_id resolve to a real,
    currently-EXECUTING claim in PostgreSQL (see
    _verify_active_execution_claim()) owned by the asserted approved_by.
    That claim can only exist because execute_with_atomic_claim() won a real
    claim_contract_execution() race and threaded its execution_id through
    core/action_gateway.py's _make_dispatch_executor() closure — a bare
    dispatch_tool("tma_write", ...) call with a hand-built execution_context
    dict (from the Agent tool_use loop, a future bug, or any caller that
    skips the propose/approve ceremony) has no way to produce a matching
    PostgreSQL row and is refused before touching Airtable, even if the
    dict's shape looks legitimate.

    identity here is the frozen REQUESTER's identity (bound at propose
    time, reconstructed by _make_dispatch_executor() from the ActionContract
    — see core/action_gateway.py's BUG-C89-APPROVAL-IDENTITY notes), used
    only for requested_by/audit attribution of who asked for this action.
    It is never the approver. approved_by — who actually authorized
    execution — comes exclusively from execution_context["approved_by"],
    which core/action_gateway.py populates from the ActionContract's own
    approved_by field (set by approve() at approval time, a materially
    different identity in the common TMA case of a manager requesting and
    the owner approving).
    """
    from datetime import datetime, timezone
    from airtable_schema import InteractionLogFields, Tables
    from tools.airtable_gateway import airtable_create, airtable_patch

    ctx = execution_context or {}
    _contract_id = ctx.get("contract_id") or ""
    _approved_by = ctx.get("approved_by") or ""
    _claim_execution_id = ctx.get("claim_execution_id") or ""
    if (
        trusted_source != "tma_api"
        or not _contract_id
        or not _approved_by
        or not _claim_execution_id
        or not _verify_active_execution_claim(_contract_id, _claim_execution_id, _approved_by)
    ):
        logger.error(
            "[approval_actions] tma_write: refused — requires trusted_source='tma_api' "
            "and an execution_context whose contract_id+claim_execution_id verify "
            "against a live, EXECUTING PostgreSQL claim (direct-dispatch bypass "
            "guard; a caller-constructed dict is never sufficient proof). "
            "trusted_source=%r has_contract_id=%s has_approved_by=%s has_claim_execution_id=%s",
            trusted_source, bool(_contract_id), bool(_approved_by), bool(_claim_execution_id),
        )
        return _tool_result(
            ok=False, tool="tma_write",
            user_message="❌ tma_write יכול לרוץ רק דרך זרימת האישור של ActionGateway",
        )

    if table not in _TMA_WRITE_ALLOWED_TABLES:
        logger.error("[approval_actions] tma_write: table '%s' not in allowlist — rejected", table)
        return _tool_result(
            ok=False, tool="tma_write",
            user_message=f"❌ טבלה '{table}' אינה מורשית לכתיבה מ-TMA",
        )

    fields = dict(fields or {})
    # Never derived from `identity` (the frozen requester) — see docstring.
    # Already verified above against the live PostgreSQL claim's claimant_id.
    approved_by = _approved_by

    if op == "post":
        rec = airtable_create(table, fields, source="tma_write")
        if not rec:
            return _tool_result(
                ok=False, tool="tma_write",
                user_message=f"❌ יצירת רשומה נכשלה ב-{table}",
            )
        result_record_id = rec.get("id", "") or ""
    elif op == "patch":
        result_record_id = record_id
        cleaned_fields = _clean_tma_write_fields(table, fields)
        ok = airtable_patch(table, result_record_id, cleaned_fields, source="tma_write")
        if not ok:
            return _tool_result(
                ok=False, tool="tma_write",
                external_id=result_record_id,
                evidence={"record_id": result_record_id, "table": table},
                user_message=f"❌ עדכון רשומה נכשל ב-{table}",
            )
    else:
        return _tool_result(
            ok=False, tool="tma_write",
            user_message=f"❌ פעולת כתיבה לא נתמכת: {op!r}",
        )

    # Audit — mirrors tma_api.py::_audit() exactly (fails silently, own try/except).
    try:
        airtable_create(Tables.INTERACTION_LOG, {
            InteractionLogFields.TITLE:        f"[TMA] {audit_action or action}",
            InteractionLogFields.SUMMARY:      (audit_details or audit_action or action)[:200],
            InteractionLogFields.PARTICIPANTS: getattr(identity, "display_name", "") or getattr(identity, "user_id", ""),
        }, source="tma_write_audit")
    except Exception as exc:
        logger.warning("[approval_actions] tma_write audit failed for '%s': %s", audit_action or action, exc)

    # Receipt — mirrors tma_api.py::_receipt()/_persist_receipt() exactly.
    receipt = {
        "action": action,
        "table": table,
        "record_id": result_record_id,
        "requested_by": requested_by or "unknown",
        "approved_by": approved_by,
        "status": "executed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    receipt_warning = ""
    try:
        rec = airtable_create(Tables.INTERACTION_LOG, {
            InteractionLogFields.TITLE:   f"[TMA receipt] {receipt['action']}",
            InteractionLogFields.SUMMARY: json.dumps(receipt, ensure_ascii=False),
            InteractionLogFields.TIMESTAMP: receipt["timestamp"],
            InteractionLogFields.PARTICIPANTS: receipt["approved_by"],
            InteractionLogFields.KEY_INSIGHTS: (
                f"{receipt['status']} {receipt['table']}/{receipt['record_id']}"
            ).strip(),
        }, source="tma_write_receipt")
        if not rec:
            receipt_warning = "receipt persistence failed: Interaction Log write returned no record"
            logger.warning("[approval_actions] %s", receipt_warning)
    except Exception as exc:
        receipt_warning = f"receipt persistence failed: {type(exc).__name__}"
        logger.warning("[approval_actions] %s: %s", receipt_warning, exc)

    evidence = {"record_id": result_record_id, "table": table, "receipt": receipt}
    if receipt_warning:
        evidence["receipt_warning"] = receipt_warning

    return _tool_result(
        ok=True,
        tool="tma_write",
        external_id=result_record_id,
        evidence=evidence,
        user_message=f"✅ בוצע: {action or audit_action} | מזהה: {result_record_id}",
    )
