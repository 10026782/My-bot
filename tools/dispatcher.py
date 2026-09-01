# tools/dispatcher.py — Tool Dispatcher v2
# נקודת כניסה יחידה לכל הכלים.
#
# זרימה: enforce(tool, identity) → dispatch_tool(tool, inputs, identity)

from __future__ import annotations
import logging
import os
import re
from typing import TYPE_CHECKING

from action_validator import ActionBlocked, validate_action

from .drive_tools    import search_drive, read_drive_file
from .calendar_tools import calendar_get_events, calendar_create_event
from .gmail_tools    import gmail_draft, gmail_send_draft, gmail_read
from .sheets_tools   import sheets_append
from .airtable_tools    import airtable_get, airtable_add, airtable_update, airtable_get_schema, search_lead, _tool_result
from airtable_schema import (
    DealStage, PaymentTermTrigger, PaymentTermCadence, VATRule,
    Tables, DealFields, PaymentTermFields, PaymentFields,
)
from .airtable_read_adapter import AirtableReadError, list_records
from .airtable_security import TenantScopeViolation, LeadsDirectWriteBlocked, audit_log_airtable, enforce_tenant_scope, enforce_leads_write_gate
try:
    from core.lead_buffer import save_blocked_payload as _save_lead_buffer
except ImportError:
    _save_lead_buffer = None  # fallback — לא שובר אם core חסר
from .contact_resolver  import resolve_contact
from . import approval_actions

from tool_registry import enforce, ToolDenied
import feature_flags as _ff
# BUG-147/Patch A — set of tools whose result must always be the C53-A
# structured dict (see the ActionBlocked branch in dispatch_tool() below).
from core.anti_hallucination import _EVIDENCE_VALIDATORS as _STRUCTURED_WRITE_TOOLS

if TYPE_CHECKING:
    from identity import Identity

logger = logging.getLogger(__name__)


# שדות dedup לפי טבלה — מונע כתיבה כפולה
_DEDUP_FIELDS: dict[str, str] = {
    "משימות (Tasks)":    "כותרת המשימה",
    "Tasks":             "כותרת המשימה",
    "משימות ודד ליינים": "שם המשימה",
    "Deadlines":         "שם המשימה",
    "Leads":             "phone",
}

# מיפוי alias → שם אמיתי (mirrors airtable_tools._TABLE_ALIAS_MAP)
# Track 8C: dropped a stale "Payments" -> "תשלומים (Payments)" entry — that
# Hebrew table no longer exists live (Track 8B), the live table is plain
# "Payments" (see airtable_schema.TABLE_ALIASES, which already maps
# "Payments" -> Tables.PAYMENTS == "Payments"), and no write path used this
# local map for Payments (writes go through the raw `table` value at the
# airtable_add()/airtable_update() call sites below, not through this dict).
_ALIAS_MAP: dict[str, str] = {
    "Tasks":    "משימות (Tasks)",
    "Contacts": "אנשי קשר (Contacts)",
    "Deals":    "עסקאות (Deals)",
    "Expenses": "הוצאות (Expenses)",
}


# ══════════════════════════════════════════════════
# Commercial CRM write-boundary closure (Deals/Payment Terms/Payments)
#
# Contacts already has this: the generic "airtable_add" case below
# redirects any raw write to the Contacts table into
# crm.create_contact_from_fields() (the canonical writer), so no caller can
# reach that table without its dedup/validation gate — see that block
# further down. Deals/Payment Terms/Payments had NO equivalent redirect:
# a raw airtable_add call to those tables fell straight through to the
# generic `airtable_add(table, fields)` write at the bottom of this case,
# skipping commercial_crm.py's required-field/calc_type/VAT validation
# entirely. Worse, "airtable_add"'s own registry role set (_INTERNAL,
# tool_registry.py) includes "employee", while crm_create_deal/
# crm_create_payment_term/crm_create_payment are _MANAGEMENT-only — so an
# employee identity, explicitly denied crm_create_deal by enforce(), could
# still reach the same business mutation through this generic tool. Found
# during the R10 write-path golden-writer audit, 01/09/2026.
#
# Fix mirrors the Contacts pattern exactly: recognize the protected table,
# map the generic Airtable field names onto the canonical writer's own
# keyword arguments, and call that writer — never reimplementing its
# validation. Two things Contacts' block didn't need to add explicitly:
#   1. An enforce("crm_create_X", identity) re-check, closing the wider-
#      role-reaches-narrower-tool gap above (Contacts creation has no
#      _MANAGEMENT-only canonical tool to under-cut, so it never needed
#      this).
#   2. A closed field map (_DEAL_FIELD_MAP / _PAYMENT_TERM_FIELD_MAP /
#      _PAYMENT_FIELD_MAP below) that FAILS CLOSED on any field name it
#      doesn't recognize — a raw airtable_add payload uses real Airtable
#      column names (DealFields.NAME etc.), not the canonical writer's own
#      parameter names, so a mapping step is required; an unmapped field
#      must never be silently dropped.
#
# Each map's exact key set matches the fields tools/dispatcher.py's own
# "crm_create_deal"/"crm_create_payment_term"/"crm_create_payment" cases
# already forward from the dedicated tool's `inputs` (see those cases
# further down) — writer-only parameters those cases don't expose either
# (venture_id/priority/risk_level for Deal; trigger_delay_days/start_date/
# end_date for PaymentTerm; base_amount/rate_pct/vat_amount/
# trigger_evidence for Payment) are intentionally absent here too, so this
# back-door path never offers a WIDER surface than the sanctioned tool.
#
# Map value = (canonical kwarg name, link mode):
#   None     -> scalar, passed through as-is
#   "single" -> linked-record field; Airtable gives a 1-element list or a
#               bare record-id string, the writer wants a bare string
#   "list"   -> linked-record field where the writer itself wants a list
#               (currently only Deal.contact_ids)
_DEAL_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    DealFields.NAME:          ("name", None),
    DealFields.DOMAIN:        ("domain", None),
    DealFields.OWNER:         ("owner_id", "single"),
    DealFields.ORIGIN_LEAD:   ("origin_lead_id", "single"),
    DealFields.CONTACTS_LINK: ("contact_ids", "list"),
    DealFields.AMOUNT:        ("amount", None),
    DealFields.STAGE:         ("stage", None),
    DealFields.NOTES:         ("notes", None),
}
_PAYMENT_TERM_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    PaymentTermFields.DEAL:         ("deal_id", "single"),
    PaymentTermFields.NAME:         ("name", None),
    PaymentTermFields.CALC_TYPE:    ("calc_type", None),
    PaymentTermFields.FIXED_AMOUNT: ("fixed_amount", None),
    PaymentTermFields.RATE_PCT:     ("rate_pct", None),
    PaymentTermFields.CALC_BASIS:   ("calc_basis", None),
    PaymentTermFields.TRIGGER_TYPE: ("trigger_type", None),
    PaymentTermFields.TRIGGER_DATE: ("trigger_date", None),
    PaymentTermFields.CADENCE:      ("cadence", None),
    PaymentTermFields.VAT_RULE:     ("vat_rule", None),
    PaymentTermFields.NOTES:        ("notes", None),
}
_PAYMENT_FIELD_MAP: dict[str, tuple[str, str | None]] = {
    PaymentFields.AMOUNT:       ("amount", None),
    PaymentFields.DOMAIN:       ("domain", None),
    PaymentFields.OWNER:        ("owner_id", "single"),
    PaymentFields.DEAL_LINK:    ("deal_id", "single"),
    PaymentFields.PAYMENT_TERM: ("payment_term_id", "single"),
    PaymentFields.ORIGIN_LEAD:  ("origin_lead_id", "single"),
    PaymentFields.REF:          ("reference", None),
    PaymentFields.DATE:         ("due_date", None),
    PaymentFields.VAT_RULE:     ("vat_rule", None),
    PaymentFields.NOTES:        ("notes", None),
}
# Keys the dispatcher itself injects into `fields` (see the _TENANT_AWARE
# block in dispatch_tool()) — never user/agent-supplied, never mapped, and
# never counted as an "unrecognized field" fail-closed trigger.
_GENERIC_WRITE_IGNORED_KEYS: frozenset[str] = frozenset({"tenant_id"})

# table -> (dedicated tool name to authority-check, its field map, its
# required-kwarg names that have no Python default and must never be
# omitted from the call).
_CRM_TABLE_ROUTING: dict[str, tuple[str, dict[str, tuple[str, str | None]], tuple[str, ...]]] = {
    Tables.DEALS:         ("crm_create_deal", _DEAL_FIELD_MAP, ("name", "domain", "owner_id")),
    Tables.PAYMENT_TERMS: ("crm_create_payment_term", _PAYMENT_TERM_FIELD_MAP, ("deal_id", "name", "calc_type")),
    Tables.PAYMENTS:      ("crm_create_payment", _PAYMENT_FIELD_MAP, ("amount", "domain", "owner_id")),
}


def _map_generic_fields_to_canonical(
    fields: dict, field_map: dict[str, tuple[str, str | None]],
) -> tuple[dict, str]:
    """Maps a raw airtable_add `fields` dict onto a canonical writer's own
    kwargs using an explicit, closed field_map. Returns (kwargs, error) —
    error is non-empty (and kwargs is {}) the moment any field can't be
    represented, so a caller never silently drops part of what was asked
    for. Never inspects field VALUES for business validity (empty name,
    bad calc_type, amount<=0, ...) — that stays the canonical writer's job."""
    kwargs: dict = {}
    for key, value in fields.items():
        if key in _GENERIC_WRITE_IGNORED_KEYS:
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
        kwargs[kwarg_name] = value
    return kwargs, ""


def _sanitize_formula_value(value: str) -> str:
    """Strip characters that could inject into an Airtable filterByFormula string."""
    return re.sub(r"""[\\'"``{}\[\]()]""", "", str(value))


def _assert_balanced_parens(formula: str) -> None:
    """Raise ValueError if formula contains unbalanced parentheses."""
    depth = 0
    for ch in formula:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth < 0:
            raise ValueError("unbalanced parentheses in formula")
    if depth != 0:
        raise ValueError("unbalanced parentheses in formula")


def _check_duplicate(real_table: str, field: str, value: str) -> dict | None:
    """מחזיר רשומה קיימת אם יש כפילות, אחרת None."""
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    key  = os.environ.get("AIRTABLE_API_KEY", "")
    if not base or not key:
        return None
    safe = _sanitize_formula_value(value)
    try:
        records = list_records(
            real_table,
            f"{{{field}}}='{safe}'",
            max_records=1,
            paginate=False,
            timeout=5,
        )
        return records[0] if records else None
    except AirtableReadError as e:
        if e.cause is not None:
            logger.warning(f"[Dedup] {real_table}/{field}: {e.cause}")
        return None
    except Exception as e:
        logger.warning(f"[Dedup] {real_table}/{field}: {e}")
    return None


def _validate_execution_proof(name: str, inputs: dict, identity, execution_context: dict | None, trusted_source: str | None) -> str | None:
    """Require the ActionGateway's canonical, action-bound proof for writes."""
    if not isinstance(execution_context, dict):
        if inputs.get("table") == "Leads" and trusted_source != "lead_capture":
            return "❌ עדכון ליד קיים דרך הצ׳אט חסום כרגע. לעדכון ליד קיים יש להשתמש במסך הלידים באפליקציה."
        return "approval-sensitive execution requires an approved ActionContract."
    if name in {"tma_write", "external_execution.submit"}:
        return None if execution_context.get("contract_id") else "approval-sensitive execution proof is incomplete."
    required = (
        "contract_id", "approved_by", "tool_name", "tenant_id",
        "canonical_user_id", "business_action_fingerprint", "status",
    )
    if any(not execution_context.get(key) for key in required):
        return "approval-sensitive execution proof is incomplete."
    if execution_context["status"] not in {"approved", "executing"}:
        return "approval-sensitive execution proof is stale."
    if execution_context["tool_name"] != name:
        return "approval-sensitive execution proof targets another tool."
    if execution_context["tenant_id"] != identity.tenant_id:
        return "approval-sensitive execution proof targets another tenant."
    if execution_context["canonical_user_id"] != identity.memory_key:
        return "approval-sensitive execution proof targets another identity."
    from core.action_gateway import ActionGateway
    expected = ActionGateway.compute_business_fingerprint(
        execution_context["tenant_id"], execution_context["canonical_user_id"], name,
        ActionGateway.normalize_payload(inputs),
    )
    if execution_context["business_action_fingerprint"] != expected:
        return "approval-sensitive execution proof does not match the action payload."
    return None


def dispatch_tool(
    name: str,
    inputs: dict,
    identity: "Identity | None" = None,
    trusted_source: str | None = None,
    execution_context: dict | None = None,
) -> str:
    """
    מקבל שם כלי + inputs + identity ומחזיר תוצאה כטקסט.

    identity מועברת לכלים שצריכים לסנן לפי tenant/user.
    כלים שלא צריכים אותה — מתעלמים ממנה.

    BUG-091: trusted_source הוא ה-source היחיד ש-enforce_leads_write_gate()
    סומך עליו — פרמטר Python מפורש שרק קוד קורא מהימן (app.py/
    core/action_gateway.py) יכול להעביר, לעולם לא נגזר מ-inputs (ה-JSON
    שקלוד יצר). ברירת מחדל None → "agent" (הכי לא-מהימן, fail-closed) —
    כל קורא שלא מעביר במפורש trusted_source נחשב "agent". inputs["_source"]
    (אם קיים) מתעלם ממנו לחלוטין — לא מקור אמון עוד.

    Phase 4B-2 follow-up: execution_context is a runtime-only dict supplied
    exclusively by core/action_gateway.py's _make_dispatch_executor() closure
    — never persisted, never part of the frozen tool_inputs an
    ActionContract stores, and never derived from anything the Agent/caller
    controls. Carries facts only the ActionGateway itself can know after a
    contract has actually been approved (currently: contract_id,
    approved_by). Tools that must never run outside the propose/approve
    ceremony (e.g. tma_write) require this to be present and populated —
    see tools/approval_actions.py::tma_write(). A direct dispatch_tool(...)
    call that omits it is exactly the "direct-dispatch bypass" this guards
    against: the tool refuses before performing any provider write.
    """
    tenant_id = identity.tenant_id if identity else "unknown"
    user_id   = identity.user_id   if identity else "unknown"

    logger.info(f"[Dispatch] {name} | tenant={tenant_id} user={user_id} | inputs={str(inputs)[:80]}")

    # ── Central Permission Enforcement (CORE_04 Fix 1) ────────────
    # כלל ברזל: אין Tool בלי בדיקת הרשאה — גם אם הקריאה עוקפת את app.py
    # ומגיעה ישירות ל-dispatch_tool, ה-registry עדיין נאכף כאן. Deny by default.
    if identity is None:
        logger.warning(f"[Dispatch] denied — missing identity | tool={name}")
        return f"❌ גישה נחסמה: נדרשת זהות מאומתת להפעלת '{name}'."
    try:
        meta = enforce(name, identity)
    except ToolDenied as e:
        logger.warning(f"[Dispatch] denied | tool={name} user={user_id} role={identity.role} | {e}")
        return f"❌ גישה נחסמה: {e}"

    # Emergency Stop — blocks all write/send tools; checks persistent flag store
    # so the in-app owner control (/api/health/emergency) takes effect immediately.
    # C83: emergency blocking is independent from human-approval policy.
    from tool_registry import TOOLS_BLOCKED_BY_EMERGENCY as _EMERGENCY_BLOCKED_TOOLS
    if _ff.is_enabled("EMERGENCY_STOP_ALL") and name in _EMERGENCY_BLOCKED_TOOLS:
        logger.critical(f"[EmergencyStop] BLOCKED {name} | tenant={tenant_id} user={user_id}")
        return "🚨 מצב חירום פעיל — כל פעולות הכתיבה חסומות. פנה לבעלים."

    if meta.requires_approval:
        proof_error = _validate_execution_proof(name, inputs, identity, execution_context, trusted_source)
        if proof_error:
            logger.warning("[Dispatch] denied — missing/invalid execution proof | tool=%s reason=%s", name, proof_error)
            return _tool_result(ok=False, tool=name, user_message=proof_error)

    validation = validate_action(name, inputs)
    if isinstance(validation, ActionBlocked):
        logger.warning(
            f"[Dispatch] blocked by action_validator | "
            f"tool={name} tenant={tenant_id} user={user_id} reason={validation.reason}"
        )
        # BUG-147/Patch A (actual root cause, corrected from an earlier
        # narrower hypothesis — see BUG_AUDIT_LOG.md): for a structured
        # write tool (C53-A contract, core.anti_hallucination._EVIDENCE_
        # VALIDATORS — airtable_add included), validation.reason is a bare
        # string (e.g. presence-check questions like "לאיזו טבלה?", no ❌
        # prefix) — verify_execution() misclassifies that as "expected
        # structured result dict with ok=true; got plain string" instead of
        # surfacing the real validation reason. This is exactly what a
        # BUG-143 malformed payload (row_data/sheet_name instead of table/
        # fields — missing both required airtable_add params) hits at
        # execution time. Read-only/unregistered tools keep the existing
        # plain-string behavior — verify_execution() already accepts a
        # non-empty plain string for those.
        if name in _STRUCTURED_WRITE_TOOLS:
            return _tool_result(ok=False, tool=name, user_message=str(validation.reason))
        return validation.reason

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
                    inputs.get("duration_minutes", 60),
                    inputs.get("force", False),
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
                if not identity:
                    logger.warning("[Dispatch] blocked airtable_get: missing identity")
                    return "❌ גישה נחסמה: אין זהות תקינה לקריאת Airtable."

                table = inputs["table"]
                filter_formula = inputs.get("filter", "").strip()
                params = {"table": table}

                if filter_formula:
                    try:
                        _assert_balanced_parens(filter_formula)
                    except ValueError:
                        logger.warning(
                            "[Dispatch] airtable_get: rejected unbalanced filter formula "
                            "for user=%s | formula=%s", user_id, filter_formula[:80]
                        )
                        return "❌ פרמטר סינון לא תקין."

                if identity.is_external:
                    user_filter = f"{{user_id}}='{identity.user_id}'"
                    filter_formula = (
                        f"AND({filter_formula}, {user_filter})"
                        if filter_formula else user_filter
                    )

                if filter_formula:
                    params["filterByFormula"] = filter_formula

                try:
                    secured_params = enforce_tenant_scope("airtable_get", identity, params)
                except TenantScopeViolation as e:
                    audit_log_airtable("airtable_get", identity, params, f"blocked: {e}")
                    return str(e)

                secured_filter = secured_params.get("filterByFormula", "")
                result = airtable_get(table, secured_filter)
                audit_log_airtable("airtable_get", identity, secured_params, result)
                return result

            case "airtable_add":
                table  = inputs["table"]
                fields = dict(inputs["fields"])

                # BUG-B FIX: חסום כתיבה ישירה ל-Leads מה-Agent.
                # Lead creation מותרת רק דרך capture_inbound_lead().
                # BUG-091: source נגזר אך ורק מ-trusted_source (פרמטר Python
                # מהקורא), לעולם לא מ-inputs["_source"] — זה key שקלוד יכול
                # לכתוב בעצמו ב-tool_use.input ולזייף מקור מהימן.
                _write_source = trusted_source or "agent"
                try:
                    enforce_leads_write_gate("airtable_add", {"table": table}, source=_write_source)
                except LeadsDirectWriteBlocked as e:
                    logger.warning(f"[Dispatcher] Leads write blocked | table={table} source={_write_source}")
                    # Buffer: שמור את ה-payload כדי שcapture_inbound_lead יוכל להעשיר את הליד
                    if _save_lead_buffer is not None:
                        try:
                            _save_lead_buffer(fields, source=_write_source)
                        except Exception as _buf_err:
                            logger.debug(f"[LeadBuffer] save failed (non-critical): {_buf_err}")
                    # BUG-147/Patch A: airtable_add is a structured write tool
                    # (C53-A contract) — a raw str(e) here was misclassified by
                    # verify_execution() as "expected structured result dict;
                    # got plain string" instead of the real blocked-write
                    # reason. This is always a block/failure, never a success —
                    # ok=False only.
                    return _tool_result(ok=False, tool="airtable_add", user_message=str(e))

                # Fix 1: dedup — מניעת רשומות כפולות
                real_t      = _ALIAS_MAP.get(table, table)
                dedup_field = _DEDUP_FIELDS.get(real_t) or _DEDUP_FIELDS.get(table)
                if dedup_field:
                    dedup_val = fields.get(dedup_field, "")
                    if dedup_val:
                        existing = _check_duplicate(real_t, dedup_field, str(dedup_val))
                        if existing:
                            # BUG-DUPLICATE-PLAIN-STRING: this used to return a
                            # plain string — airtable_add is a structured
                            # write tool (registered in A32's
                            # _EVIDENCE_VALIDATORS), so a plain-string result
                            # was misclassified by verify_execution() as
                            # "expected structured result dict; got plain
                            # string", a false execution failure for what is
                            # actually a correct no-op (record already
                            # exists, nothing duplicated). existing_record_id
                            # is a genuine Airtable id from the lookup, so it
                            # passes the same evidence validator a real write
                            # would.
                            f_data = existing.get("fields", {})
                            status = f_data.get("סטטוס", f_data.get("status", "?"))
                            existing_record_id = existing.get("id", "")
                            return {
                                "ok": True,
                                "tool": "airtable_add",
                                "outcome": "already_exists",
                                "external_id": existing_record_id,
                                "evidence": {"record_id": existing_record_id},
                                "user_message": (
                                    f"✋ הרשומה כבר קיימת ({dedup_field}='{dedup_val}' ב-{table}) — "
                                    f"לא נוצרה כפילות.\nסטטוס: {status} | ID: {existing_record_id or '?'}"
                                ),
                            }

                # בלוק external users מכתיבה לטבלאות שאינן Leads
                if identity and identity.is_external and table != "Leads":
                    audit_log_airtable("airtable_add", identity, {"table": table}, "blocked: external write to non-lead table")
                    return f"❌ גישה נחסמה: אין הרשאה לכתוב לטבלה '{table}'."

                # הזרקת tenant_id רק לטבלאות שמכירות את השדה
                _TENANT_AWARE = {
                    "Leads",
                    "אנשי קשר (Contacts)", "Contacts",
                    "עסקאות (Deals)",       "Deals",
                    "תשלומים (Payments)",   "Payments",
                }
                if identity and table in _TENANT_AWARE:
                    fields.setdefault("tenant_id", tenant_id)
                    if table == "Leads" and identity.domain_id:
                        fields.setdefault("domain", identity.domain_id)

                try:
                    enforce_tenant_scope("airtable_add", identity, {"table": table})
                except TenantScopeViolation as e:
                    audit_log_airtable("airtable_add", identity, {"table": table}, f"blocked: {e}")
                    # BUG-147/Patch A: same structured-shape fix as the
                    # LeadsDirectWriteBlocked branch above — always a
                    # blocked-write failure, never ok=True.
                    return _tool_result(ok=False, tool="airtable_add", user_message=str(e))

                if _ALIAS_MAP.get(table, table) == "אנשי קשר (Contacts)":
                    import crm
                    from core.dispatcher_outcome import DispatcherOutcome

                    def _finish_contact(result, audit_result=None):
                        audit_log_airtable(
                            "airtable_add", identity,
                            {"table": table, "fields_keys": list(fields.keys())},
                            result if audit_result is None else audit_result,
                        )
                        return result

                    contact = crm.create_contact_from_fields(
                        fields,
                        identity=identity,
                        source="agent",
                    )
                    evidence = {"record_id": contact.record_id, "table": table,
                                "contact_status": contact.status}
                    if contact.matches:
                        evidence["matches"] = list(contact.matches)
                    if contact.status == "outcome_unknown":
                        result = _tool_result(ok=False, tool="airtable_add", evidence=evidence,
                                              user_message="⚠️ תוצאת יצירת איש הקשר אינה ידועה. אין לנסות שוב אוטומטית.")
                        outcome = DispatcherOutcome("outcome_unknown", result["user_message"],
                                                    error=contact.error, raw_response=result)
                        return _finish_contact(outcome, result)
                    if contact.status in ("created", "existing"):
                        return _finish_contact(_tool_result(
                            ok=True, tool="airtable_add", external_id=contact.record_id,
                            evidence=evidence,
                            user_message="✅ איש הקשר נוצר" if contact.status == "created" else "✅ איש הקשר כבר קיים",
                        ))
                    return _finish_contact(_tool_result(
                        ok=False, tool="airtable_add", evidence=evidence,
                        user_message=crm.describe_contact_failure(contact),
                    ))

                # Commercial CRM write-boundary closure — see the long
                # comment above _DEAL_FIELD_MAP for why this exists and why
                # each of the three blocks below re-checks role authority
                # independently rather than trusting airtable_add's own
                # (wider) role grant.
                _resolved_table = _ALIAS_MAP.get(table, table)
                if _resolved_table in _CRM_TABLE_ROUTING:
                    _canonical_tool, _field_map, _required_kwargs = _CRM_TABLE_ROUTING[_resolved_table]

                    # BUG-CRM-BYPASS: airtable_add's own registry entry
                    # (roles_allowed=_INTERNAL, includes "employee") is
                    # wider than the canonical tool's (roles_allowed=
                    # _MANAGEMENT) — without this re-check, an identity
                    # already denied crm_create_deal/_payment_term/_payment
                    # by enforce() could still reach the identical business
                    # mutation through this generic tool. Never trust
                    # airtable_add's own role grant for a table with a
                    # narrower dedicated tool.
                    try:
                        enforce(_canonical_tool, identity)
                    except ToolDenied as e:
                        logger.warning(
                            "[Dispatcher] airtable_add->%s redirect denied | role=%s | %s",
                            _canonical_tool, getattr(identity, "role", "unknown"), e,
                        )
                        audit_log_airtable("airtable_add", identity, {"table": table}, f"blocked: {e}")
                        return _tool_result(ok=False, tool="airtable_add", user_message=f"❌ גישה נחסמה: {e}")

                    _mapped, _map_error = _map_generic_fields_to_canonical(fields, _field_map)
                    if _map_error:
                        audit_log_airtable(
                            "airtable_add", identity,
                            {"table": table, "fields_keys": list(fields.keys())},
                            f"blocked: {_map_error}",
                        )
                        return _tool_result(ok=False, tool="airtable_add", user_message=f"❌ {_map_error}")

                    # Required canonical kwargs have no Python default —
                    # default any missing one to a falsy placeholder so the
                    # call never raises TypeError; the canonical writer's
                    # OWN existing "if not name:"/"if amount is None:" etc.
                    # checks then produce the exact same validation-failure
                    # message a direct crm_create_* call would get. This is
                    # presence-safety for the function call, never a second
                    # copy of the writer's business rules.
                    for _req in _required_kwargs:
                        _mapped.setdefault(_req, None if _req == "amount" else "")

                    if _resolved_table == Tables.DEALS:
                        from commercial_crm import create_deal as _crm_writer
                    elif _resolved_table == Tables.PAYMENT_TERMS:
                        from commercial_crm import create_payment_term as _crm_writer
                    else:
                        from commercial_crm import create_payment as _crm_writer
                    result = _crm_writer(source="agent", **_mapped)
                    audit_log_airtable(
                        "airtable_add", identity,
                        {"table": table, "fields_keys": list(fields.keys())}, result,
                    )
                    return result

                result = airtable_add(table, fields)
                audit_log_airtable("airtable_add", identity, {"table": table, "fields_keys": list(fields.keys())}, result)
                return result

            case "airtable_update":
                table     = inputs["table"]
                record_id = inputs["record_id"]
                fields    = dict(inputs["fields"])

                # BUG-B FIX: חסום עדכון ישיר ל-Leads מה-Agent
                # BUG-091: ראה הערה מקבילה ב-airtable_add — trusted_source
                # בלבד, לעולם לא inputs["_source"].
                _write_source = trusted_source or "agent"
                try:
                    enforce_leads_write_gate("airtable_update", {"table": table}, source=_write_source)
                except LeadsDirectWriteBlocked as e:
                    logger.warning(f"[Dispatcher] Leads update blocked | table={table} source={_write_source}")
                    # Buffer: שמור גם update payload — יכול להכיל שדות שהAgent חילץ
                    if _save_lead_buffer is not None:
                        try:
                            _save_lead_buffer(fields, source=_write_source)
                        except Exception as _buf_err:
                            logger.debug(f"[LeadBuffer] save failed (non-critical): {_buf_err}")
                    return str(e)

                # בלוק external users מעדכון רשומות
                if identity and identity.is_external:
                    audit_log_airtable("airtable_update", identity, {"table": table, "record_id": record_id}, "blocked: external update")
                    return "❌ גישה נחסמה: אין הרשאה לעדכן רשומות."

                try:
                    enforce_tenant_scope("airtable_update", identity, {"table": table, "record_id": record_id})
                except TenantScopeViolation as e:
                    audit_log_airtable("airtable_update", identity, {"table": table, "record_id": record_id}, f"blocked: {e}")
                    return str(e)

                if _ALIAS_MAP.get(table, table) == "אנשי קשר (Contacts)":
                    import crm
                    ok = crm.update_contact(record_id, fields, source="agent")
                    result = _tool_result(
                        ok=ok,
                        tool="airtable_update",
                        external_id=record_id,
                        evidence={"record_id": record_id, "table": table, "fields": fields},
                        user_message=(
                            f"✅ רשומה {record_id} עודכנה."
                            if ok else "❌ שגיאה בעדכון — בדוק שמות השדות."
                        ),
                    )
                else:
                    result = airtable_update(table, record_id, fields)
                audit_log_airtable("airtable_update", identity, {"table": table, "record_id": record_id}, result)
                return result

            case "airtable_get_schema":
                return airtable_get_schema()

            case "search_lead":
                return search_lead(inputs["name"])

            # ── Contact Resolver (N03) ────────────────
            case "resolve_contact":
                return resolve_contact(inputs["name_query"], identity)

            # ── Daily Digest on-demand ───────────────
            case "get_daily_report":
                from daily_digest import build_digest
                return build_digest()

            # ── D06 — Business Memory ─────────────────
            case "search_business_memory":
                from interaction_engine import search_business_memory  # type: ignore
                return search_business_memory(
                    inputs.get("query", ""),
                    domain=inputs.get("domain", ""),
                )

            # ── CRM — Payments ────────────────────────
            case "crm_mark_payment_paid":
                record_id = inputs["record_id"]
                try:
                    enforce_tenant_scope("crm_mark_payment_paid", identity, {"record_id": record_id})
                except TenantScopeViolation as e:
                    audit_log_airtable("crm_mark_payment_paid", identity, {"record_id": record_id}, f"blocked: {e}")
                    return str(e)

                from crm import crm_mark_payment_paid
                result = crm_mark_payment_paid(record_id)
                audit_log_airtable("crm_mark_payment_paid", identity, {"record_id": record_id}, result)
                return result

            # ── commercial_crm.py — canonical Deal/PaymentTerm/Payment writers ──
            case "crm_create_deal":
                try:
                    enforce_tenant_scope("crm_create_deal", identity, inputs)
                except TenantScopeViolation as e:
                    audit_log_airtable("crm_create_deal", identity, inputs, f"blocked: {e}")
                    return _tool_result(ok=False, tool="crm_create_deal", user_message=str(e))

                from commercial_crm import create_deal
                result = create_deal(
                    name=inputs["name"],
                    domain=inputs["domain"],
                    owner_id=inputs["owner_id"],
                    origin_lead_id=inputs.get("origin_lead_id", ""),
                    contact_ids=inputs.get("contact_ids"),
                    amount=inputs.get("amount"),
                    stage=inputs.get("stage", DealStage.OPPORTUNITY),
                    notes=inputs.get("notes", ""),
                    source="agent",
                )
                audit_log_airtable("crm_create_deal", identity, inputs, result)
                return result

            case "crm_create_payment_term":
                try:
                    enforce_tenant_scope("crm_create_payment_term", identity, inputs)
                except TenantScopeViolation as e:
                    audit_log_airtable("crm_create_payment_term", identity, inputs, f"blocked: {e}")
                    return _tool_result(ok=False, tool="crm_create_payment_term", user_message=str(e))

                from commercial_crm import create_payment_term
                result = create_payment_term(
                    deal_id=inputs["deal_id"],
                    name=inputs.get("name", ""),
                    calc_type=inputs["calc_type"],
                    fixed_amount=inputs.get("fixed_amount"),
                    rate_pct=inputs.get("rate_pct"),
                    calc_basis=inputs.get("calc_basis", ""),
                    trigger_type=inputs.get("trigger_type", PaymentTermTrigger.IMMEDIATE),
                    trigger_date=inputs.get("trigger_date", ""),
                    cadence=inputs.get("cadence", PaymentTermCadence.ONCE),
                    vat_rule=inputs.get("vat_rule", VATRule.NONE),
                    notes=inputs.get("notes", ""),
                    source="agent",
                )
                audit_log_airtable("crm_create_payment_term", identity, inputs, result)
                return result

            case "crm_create_payment":
                try:
                    enforce_tenant_scope("crm_create_payment", identity, inputs)
                except TenantScopeViolation as e:
                    audit_log_airtable("crm_create_payment", identity, inputs, f"blocked: {e}")
                    return _tool_result(ok=False, tool="crm_create_payment", user_message=str(e))

                from commercial_crm import create_payment
                result = create_payment(
                    amount=inputs["amount"],
                    domain=inputs["domain"],
                    owner_id=inputs["owner_id"],
                    deal_id=inputs.get("deal_id", ""),
                    payment_term_id=inputs.get("payment_term_id", ""),
                    origin_lead_id=inputs.get("origin_lead_id", ""),
                    reference=inputs.get("reference", ""),
                    due_date=inputs.get("due_date", ""),
                    vat_rule=inputs.get("vat_rule", VATRule.NONE),
                    notes=inputs.get("notes", ""),
                    source="agent",
                )
                audit_log_airtable("crm_create_payment", identity, inputs, result)
                return result

            # ── PR-0C — ActionGateway adapters (former event_bus custom actions) ──
            case "media_save_to_memory":
                return approval_actions.media_save_to_memory(
                    transcript=inputs.get("transcript", ""),
                    domain=inputs.get("domain", "general"),
                    source=inputs.get("source", "media_handler"),
                )
            case "send_followup":
                return approval_actions.send_followup(
                    chat_id=inputs.get("chat_id", ""),
                    draft=inputs.get("draft", ""),
                    contact_name=inputs.get("contact_name", ""),
                    channel=inputs.get("channel", ""),
                    memory_key=inputs.get("memory_key", ""),
                )
            case "send_recovery":
                return approval_actions.send_recovery(
                    chat_id=inputs.get("chat_id", ""),
                    draft=inputs.get("draft", ""),
                    contact_name=inputs.get("contact_name", ""),
                    channel=inputs.get("channel", ""),
                    memory_key=inputs.get("memory_key", ""),
                    tier=inputs.get("tier", ""),
                )

            # ── Phase 4B-2 wiring — TMA write-through-approval adapter ──
            case "tma_write":
                return approval_actions.tma_write(
                    op=inputs.get("op", ""),
                    table=inputs.get("table", ""),
                    action=inputs.get("action", ""),
                    requested_by=inputs.get("requested_by", ""),
                    fields=inputs.get("fields", {}),
                    record_id=inputs.get("record_id", ""),
                    audit_action=inputs.get("audit_action", ""),
                    audit_details=inputs.get("audit_details", ""),
                    identity=identity,
                    trusted_source=trusted_source,
                    execution_context=execution_context,
                )

            case "external_execution.submit":
                if not execution_context or not execution_context.get("contract_id"):
                    return _tool_result(ok=False, tool=name, user_message="External execution requires an approved contract.")
                if not _ff.is_enabled("EXTERNAL_EXECUTION_ENABLED"):
                    from core.dispatcher_outcome import DispatcherOutcome
                    return DispatcherOutcome(
                        "failed",
                        "External execution is disabled until its readiness gate is enabled.",
                        error_code="external_execution_disabled",
                    )
                from core.external_execution_boundary import get_default_boundary
                return get_default_boundary().submit(
                    contract_id=execution_context["contract_id"],
                    idempotency_key=execution_context.get("idempotency_key", ""),
                    payload=inputs,
                )

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
    finally:
        # F52 #4 — passive, flag-gated shadow record. Runs after the real
        # dispatch (success or failure) via `finally`; never affects the
        # return value above. See core/last_tool_result_shadow.py.
        if _ff.is_enabled("FEATURE_LAST_TOOL_RESULT_SHADOW"):
            try:
                from core.last_tool_result_shadow import record as _shadow_record
                _shadow_record(source="agent_tool", tool_or_action=name)
            except Exception as _shadow_e:
                logger.debug(f"[Dispatch] shadow record failed (non-fatal): {_shadow_e}")
