# tma_api.py — BOSS TMA REST API Blueprint
#
# Stateless Telegram Mini App backend.
# Every request carries X-Telegram-Init-Data — HMAC validated on each call.
# No session tokens. No state.

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Blueprint, jsonify, request
from identity import resolve_identity, Role
from airtable_schema import (
    LeadFields, TaskFields, PaymentStatus, PaymentFields, ExpenseFields,
    BusinessMemoryFields, InteractionLogFields, Tables,
    DealFields,
    QuestsFields, CoinsLogFields, WorldsFields, QuestStatus, WorldStatus,
    ApprovalsFields, ApprovalStatus,
    RoadmapTaskFields, RoadmapTaskStatus, DailyCheckinFields,
    VentureFields, VentureStage,
    LeadStatus, LeadOutcome,
    LeadEventFields,
)
from tools.airtable_gateway import airtable_patch as _gw_patch, airtable_create as _gw_create
from health_monitor import get_health_status

logger = logging.getLogger(__name__)

tma_api = Blueprint("tma_api", __name__)


_TASK_DOMAIN_OPTIONS = (
    "Real Estate",
    "Income Properties",
    "Recruitment",
    "Import",
    "Saas",
)


def _normalize_task_domain(value: str) -> str:
    """Return the exact Airtable Tasks.Domain option for known domain keys."""
    raw = (value or "").strip()
    if not raw:
        return ""

    def key(text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("_", " ").replace("-", " ")).strip().lower()

    options_by_key = {key(option): option for option in _TASK_DOMAIN_OPTIONS}
    aliases = {
        "real estate": "Real Estate",
        "income properties": "Income Properties",
        "recruiting": "Recruitment",
        "recruitment": "Recruitment",
        "import": "Import",
        "imports": "Import",
        "saas": "Saas",
    }

    normalized = key(raw)
    return options_by_key.get(normalized) or aliases.get(normalized) or raw


@tma_api.errorhandler(RuntimeError)
def _handle_runtime_error(e):
    logger.error(f"[tma_api] unhandled RuntimeError: {e}")
    return jsonify({"error": "internal_error", "detail": str(e)}), 500


# ── env ────────────────────────────────────────────────────────────
_BOT_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "")
_AT_KEY     = os.environ.get("AIRTABLE_API_KEY", "")
_AT_BASE    = os.environ.get("AIRTABLE_BASE_ID", "")
_ENV        = os.environ.get("ENV", "production").strip().lower()

# TMA_DEV_MODE is permanently disabled — HMAC validation is always required.
# Remove TMA_DEV_MODE / ALLOW_TMA_DEV_MODE from env vars; they have no effect.
_DEV_MODE = False
if os.environ.get("TMA_DEV_MODE", "").strip().lower() in ("1", "true", "yes"):
    logger.critical(
        "🚨 TMA_DEV_MODE is set but the bypass is permanently disabled. "
        "Telegram HMAC validation is always enforced. Remove TMA_DEV_MODE from env vars."
    )


# ══════════════════════════════════════════════════════════════════
# CORS — allow TMA frontend (Vercel + Telegram webview)
# ══════════════════════════════════════════════════════════════════

def _build_allowed_origins() -> set[str]:
    base = {"https://web.telegram.org"}
    if _ENV != "production":
        # Development/staging: also allow localhost and broad Vercel previews
        base |= {"http://localhost:5173", "http://localhost:3000"}
        base.add(".vercel.app")   # sentinel value checked with endswith below
    # Production (and optionally staging): exact origins from env var
    raw = os.environ.get("TMA_ALLOWED_ORIGINS", "").strip()
    if raw:
        base |= {o.strip() for o in raw.split(",") if o.strip()}
    return base

_ALLOWED_ORIGINS = _build_allowed_origins()


@tma_api.after_request
def _cors(response):
    origin = request.headers.get("Origin", "")
    allow = (
        origin in _ALLOWED_ORIGINS
        or (".vercel.app" in _ALLOWED_ORIGINS and origin.endswith(".vercel.app"))
    )
    if allow:
        response.headers["Access-Control-Allow-Origin"]  = origin
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-Telegram-Init-Data, Authorization, X-TMA-Platform"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, OPTIONS"
    return response


@tma_api.route("/api/tma/auth", methods=["OPTIONS"])
@tma_api.route("/api/projects", methods=["OPTIONS"])
@tma_api.route("/api/leads", methods=["OPTIONS"])
@tma_api.route("/api/ai/ask", methods=["OPTIONS"])
@tma_api.route("/api/followup", methods=["OPTIONS"])
@tma_api.route("/api/activity", methods=["OPTIONS"])
@tma_api.route("/api/approvals", methods=["OPTIONS"])
@tma_api.route("/api/approvals/bulk", methods=["OPTIONS"])
@tma_api.route("/api/finance/pulse", methods=["OPTIONS"])
@tma_api.route("/api/owner/control-center", methods=["OPTIONS"])
@tma_api.route("/api/owner/health", methods=["OPTIONS"])
@tma_api.route("/api/tma/upload", methods=["OPTIONS"])
def _preflight():
    return "", 204


@tma_api.route("/api/approvals/<approval_id>", methods=["OPTIONS"])
def _preflight_approval(approval_id=None):
    return "", 204


@tma_api.route("/api/assets", methods=["OPTIONS"])
def _preflight_assets():
    return "", 204


@tma_api.route("/api/assets/<asset_id>", methods=["OPTIONS"])
def _preflight_asset(asset_id=None):
    return "", 204


@tma_api.route("/api/ventures", methods=["OPTIONS"])
def _preflight_ventures():
    return "", 204


@tma_api.route("/api/ventures/<venture_id>", methods=["OPTIONS"])
def _preflight_venture(venture_id=None):
    return "", 204


@tma_api.route("/api/game/status", methods=["OPTIONS"])
def _preflight_game_status():
    return "", 204


@tma_api.route("/api/game/quests/<quest_id>", methods=["OPTIONS"])
def _preflight_game_quest(quest_id=None):
    return "", 204


@tma_api.route("/api/game/today", methods=["OPTIONS"])
def _preflight_game_today():
    return "", 204


@tma_api.route("/api/game/checkin", methods=["OPTIONS"])
def _preflight_game_checkin():
    return "", 204


@tma_api.route("/api/game/tasks/<task_id>/done", methods=["OPTIONS"])
def _preflight_game_task_done(task_id):
    return "", 204


# ══════════════════════════════════════════════════════════════════
# Raw Airtable JSON helpers — TMA only, do NOT touch airtable_tools.py
# ══════════════════════════════════════════════════════════════════

def _at_url(table: str) -> str:
    return f"https://api.airtable.com/v0/{_AT_BASE}/{urllib.parse.quote(table, safe='')}"


def _at_headers() -> dict:
    return {"Authorization": f"Bearer {_AT_KEY}"}


class AirtableError(Exception):
    """Raised by _at_list(strict=True) on non-200 Airtable responses."""
    def __init__(self, table: str, http_status: int, body: str = ""):
        self.table       = table
        self.http_status = http_status
        self.safe_body   = body[:120]   # never expose auth headers
        super().__init__(f"Airtable {table} → HTTP {http_status}")


def _at_list(table: str, formula: str = "", max_records: int = 50,
             strict: bool = False) -> list:
    """
    Direct Airtable REST call → list[{id, fields}].
    strict=False (default): returns [] on any error (legacy behavior).
    strict=True:  raises AirtableError on non-200 so callers can return
                  a proper error response instead of silently showing zero.
    """
    try:
        import httpx
        params: dict = {}
        if formula:
            params["filterByFormula"] = formula
        if max_records:
            params["maxRecords"] = max_records
        r = httpx.get(_at_url(table), headers=_at_headers(), params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("records", [])
        logger.warning(f"_at_list({table}) → {r.status_code}: {r.text[:120]}")
        if strict:
            raise AirtableError(table, r.status_code, r.text)
    except AirtableError:
        raise
    except Exception as e:
        logger.warning(f"_at_list({table}) error: {e}")
        if strict:
            raise AirtableError(table, 0, str(e))
    return []


def _at_get_record(table: str, record_id: str) -> dict | None:
    """Fetch single record → {id, fields} or None."""
    try:
        import httpx
        r = httpx.get(f"{_at_url(table)}/{record_id}", headers=_at_headers(), timeout=10)
        if r.status_code == 200:
            return r.json()
        logger.warning(f"_at_get({table}/{record_id}) → {r.status_code}")
    except Exception as e:
        logger.warning(f"_at_get error: {e}")
    return None


def _shadow_record_tma(action: str) -> None:
    """Passive, flag-gated shadow record — never affects return value or
    control flow (F52 #4). See core/last_tool_result_shadow.py."""
    import feature_flags as _ff
    if not _ff.is_enabled("FEATURE_LAST_TOOL_RESULT_SHADOW"):
        return
    try:
        from core.last_tool_result_shadow import record as _shadow_record
        _shadow_record(source="tma_route", tool_or_action=action)
    except Exception as e:
        logger.debug(f"[tma_api] shadow record failed (non-fatal): {e}")


def _at_patch(table: str, record_id: str, fields: dict) -> bool:
    """PATCH single record via gateway (normalize → validate → audit → httpx)."""
    result = _gw_patch(table, record_id, fields, source="tma")
    _shadow_record_tma(f"patch:{table}")
    return result


def _at_post(table: str, fields: dict) -> dict | None:
    """POST new record via gateway → created record dict or None."""
    result = _gw_create(table, fields, source="tma")
    _shadow_record_tma(f"post:{table}")
    return result



def _linked_record_ids(value) -> list[str]:
    """Return only Airtable linked-record ids, never display text."""
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, str):
        candidates = [value]
    else:
        return []
    return [v for v in candidates if isinstance(v, str) and re.match(r"^rec\w+$", v)]


# ══════════════════════════════════════════════════════════════════
# Audit Trail — every write action creates an activity record
# ══════════════════════════════════════════════════════════════════

def _audit(action: str, identity, details: str = "") -> None:
    """Write audit record to Interaction Log. Fails silently."""
    try:
        _at_post(Tables.INTERACTION_LOG, {
            InteractionLogFields.TITLE:        f"[TMA] {action}",
            InteractionLogFields.SUMMARY:      details[:200] if details else action,
            InteractionLogFields.PARTICIPANTS: identity.display_name or identity.user_id,
        })
    except Exception as e:
        logger.warning(f"[Audit] failed for '{action}': {e}")


def _notify_owner(text: str) -> None:
    """Send Telegram message to owner. Fails silently."""
    owner_chat = os.environ.get("ELIYAHU_CHAT_ID", "")
    if not owner_chat or not _BOT_TOKEN:
        return
    try:
        import httpx
        httpx.post(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            json={"chat_id": owner_chat, "text": text},
            timeout=5,
        )
    except Exception as e:
        logger.warning(f"[notify_owner] {e}")


# PR-0C0 (BUG-TMA-APPROVAL-TRUTHFULNESS): the exact strings event_bus.py's
# EventBus.confirm()/reject() return when there was nothing to act on — used
# to tell "no matching pending action" (expected today; no live writer links
# an Airtable Approvals record to a real event_bus action_id yet, see the
# PR-0C0 Contract Chain in BUG_AUDIT_LOG.md) apart from an actual sync.
_BUS_MISS_MESSAGES = frozenset({
    "⚠️ הפעולה פגה או לא נמצאה.",                      # EventBus.confirm(): not found
    "⚠️ אין handler לפעולה זו — הפעולה לא בוצעה.",       # EventBus.confirm(): no .confirmed subscriber
    "⚠️ הפעולה כבר לא קיימת.",                          # EventBus.reject(): not found
})


def _try_bus_action(context_id: str, decision: str) -> bool:
    """
    Try to confirm/reject a matching in-memory event_bus pending action.

    Returns True only if a real pending item was found and event_bus did not
    itself report a miss (not-found / no-subscriber). Returns False both for
    "nothing to sync" (the expected case today) and for a genuine failure —
    this is an observability signal, not an approval-outcome signal: callers
    must not treat False as "the approval failed". What it replaces is the
    previous behavior of silently discarding event_bus's own miss/failure
    strings, which would have made a real sync failure indistinguishable
    from an intentional no-op the moment a future writer starts linking real
    event_bus action_ids into this table (see PR-0C).
    """
    if not context_id:
        return False
    try:
        from event_bus import bus  # noqa: PLC0415
        result = bus.confirm(context_id) if decision == "approve" else bus.reject(context_id)
        if result in _BUS_MISS_MESSAGES:
            logger.info(f"[event_bus] no matching pending action for context_id={context_id}: {result}")
            return False
        logger.info(f"[event_bus] synced {decision} for context_id={context_id}: {str(result)[:80]}")
        return True
    except Exception as e:
        logger.warning(f"[event_bus] sync failed for context_id={context_id}: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# Stateless Telegram initData validation
# https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
# ══════════════════════════════════════════════════════════════════

def _identity_ref(identity) -> str:
    return str(getattr(identity, "user_id", "") or getattr(identity, "display_name", "") or "unknown")


# ══════════════════════════════════════════════════════════════════
# Approval Policy gate — risk-tiered mobile/desktop enforcement
# See Approval_Policy_Spec.md. Gated behind EMERGENCY_WINDOW flag —
# flag off ⇒ this block is fully skipped, behavior identical to before.
# Emergency WINDOW (controlled High-risk exception) ≠ Emergency STOP
# (C33, freezes everything) — do not confuse the two.
# ══════════════════════════════════════════════════════════════════

# Risk tier per action — keyed off the existing `action` identifier already
# passed by every call site. Unmapped/future actions default to "High"
# (fail-closed) rather than "Low".
ACTION_RISK = {
    "tma_create_project":     "Medium",
    "tma_update_lead_status": "Low",
    "tma_patch_lead":         "Low",
    "tma_set_lead_outcome":   "Medium",
    "tma_create_lead_task":   "Low",
    "tma_create_followup":    "Low",
}
_DEFAULT_RISK = "High"

# Approvals."רמת סיכון" (fldHzJehlQ6EDctKn) live choices are lowercase
# English (high/medium/low) — no dedicated "Critical" choice exists, so it
# is recorded as the highest existing tier.
_RISK_LEVEL_AIRTABLE = {"Low": "low", "Medium": "medium", "High": "high", "Critical": "high"}

# Telegram.WebApp.platform values treated as desktop. Only native desktop
# clients qualify — "web" is excluded because Telegram Web can run inside a
# phone browser, which would hand a mobile user desktop-level permissions.
# Anything else (web / missing / unknown) is treated as mobile — fail-closed.
_DESKTOP_PLATFORMS = {"tdesktop", "macos"}


def _is_mobile_request() -> bool:
    platform = (request.headers.get("X-TMA-Platform") or "").strip().lower()
    if not platform:
        return True
    return platform not in _DESKTOP_PLATFORMS


def _reject(message: str, code: int = 403) -> tuple[str, dict, int]:
    return "", {"status": "rejected", "error": message}, code


def _otp_required_response(action: str, identity) -> tuple[str, dict, int]:
    from core import otp as _otp  # noqa: PLC0415
    request_id = _otp.request_otp(action, _identity_ref(identity))
    if not request_id:
        return _reject("failed to send OTP — contact owner", code=500)
    return "", {
        "status": "otp_required",
        "otp_request_id": request_id,
        "message": "OTP sent to owner — resend with otp_request_id + otp_code",
    }, 401


def _confirmation_required_response() -> tuple[str, dict, int]:
    return "", {
        "status": "confirmation_required",
        "message": "Action requires confirmation — resend with confirmed=true",
    }, 409


def _queue_tma_write_approval(action: str, payload: dict, identity, label: str) -> tuple[str, dict, int]:
    import feature_flags  # noqa: PLC0415

    risk = ACTION_RISK.get(action, _DEFAULT_RISK)

    if feature_flags.is_enabled("EMERGENCY_WINDOW"):
        from core import emergency_window, otp  # noqa: PLC0415

        mobile = _is_mobile_request()
        body = request.get_json(silent=True) or {}

        if risk == "Critical":
            # Critical NEVER allowed from mobile — Emergency Window cannot raise
            # the ceiling above High. OTP required in every case, even desktop.
            if mobile:
                return _reject("critical actions are never allowed from a mobile device")
            otp_request_id = body.get("otp_request_id")
            otp_code = body.get("otp_code")
            if not otp_request_id or not otp_code:
                return _otp_required_response(action, identity)
            if not otp.verify_otp(otp_request_id, otp_code):
                return _reject("invalid or expired OTP", code=401)

        elif risk == "High":
            if mobile:
                if not emergency_window.get_active_window():
                    return _reject(
                        "High-risk actions from mobile require an active Emergency Window", code=403
                    )
                otp_request_id = body.get("otp_request_id")
                otp_code = body.get("otp_code")
                if not otp_request_id or not otp_code:
                    return _otp_required_response(action, identity)
                if not otp.verify_otp(otp_request_id, otp_code):
                    return _reject("invalid or expired OTP", code=401)
                emergency_window.record_action(f"{action} by {_identity_ref(identity)}")

        elif risk == "Medium":
            if mobile and not body.get("confirmed"):
                return _confirmation_required_response()

        # Low — no gate.

    # ══════════════════════════════════════════════════════════════════
    # Phase 4B-2 wiring — Approvals is now a non-authoritative TMA display
    # projection of ActionContracts (core/action_gateway.py), never an
    # independent source of execution authority. Fail closed unless BOTH
    # durable ActionContract persistence (FEATURE_ACTION_CONTRACT_PERSISTENCE)
    # and PostgreSQL atomic execution claims (FEATURE_ATOMIC_CLAIMS) are
    # available — no fallback to a RAM-only ledger or direct execution. See
    # the Phase 4B-2 audit's authority split: ActionContracts = canonical
    # contract + lifecycle/audit store; PostgreSQL = the sole execution-
    # ownership primitive (reachable only through
    # ActionGateway._execute_contract()); Approvals = display-only
    # projection, never sufficient by itself to execute anything.
    # ══════════════════════════════════════════════════════════════════
    from core.action_gateway import action_gateway as _gw  # noqa: PLC0415
    import core.database as _db  # noqa: PLC0415

    durable_persistence_available = (
        feature_flags.is_enabled("FEATURE_ACTION_CONTRACT_PERSISTENCE")
        and getattr(_gw._ledger, "_repository", None) is not None
    )
    atomic_claims_available = (
        feature_flags.is_enabled("FEATURE_ATOMIC_CLAIMS")
        and _db.get_pool() is not None
    )
    if not (durable_persistence_available and atomic_claims_available):
        logger.error(
            "_queue_tma_write_approval: refusing action=%s — durable_persistence=%s "
            "atomic_claims=%s (both required; no RAM-only/direct-execution fallback)",
            action, durable_persistence_available, atomic_claims_available,
        )
        return _reject(
            "TMA write approvals require the durable approval infrastructure to be "
            "fully online — contact the owner.",
            code=503,
        )

    op = payload.get("op", "")
    table = payload.get("table", "")
    if op not in ("post", "patch"):
        return _reject(f"unsupported TMA write operation: {op!r}", code=400)
    from tools.approval_actions import _TMA_WRITE_ALLOWED_TABLES  # noqa: PLC0415
    if table not in _TMA_WRITE_ALLOWED_TABLES:
        return _reject(f"table '{table}' is not permitted for TMA writes", code=400)

    # Server-owned fields (op/table/action/requested_by) are applied AFTER
    # the payload spread, so nothing in payload — even a future call site
    # that starts forwarding request-body keys — can ever override them.
    tool_inputs = {
        **{k: v for k, v in payload.items() if k not in ("op", "table", "action", "requested_by")},
        "op": op,
        "table": table,
        "action": action,
        "requested_by": _identity_ref(identity),
    }

    # TurnCoordinator Phase 0 — observation only (see
    # docs/architecture/turn-coordinator/). TMA's "turn" fit is weak
    # (TURN_OWNERSHIP_EXTENSION.md finding 7 — stateless REST, not a
    # standing conversation) so this deliberately does not build a full
    # TurnEnvelope per HTTP response; it logs only the Case
    # C1 signal (multi_contract_conflict) for this identity, right before a
    # NEW contract is proposed — the one thing that's identical in meaning
    # across channels: this identity may already have live contracts from
    # Telegram/WhatsApp that TMA's own bulk-approval logic doesn't know
    # about. Deferred import: tma_api.py must not import app.py at module
    # level (app.py registers this blueprint — circular).
    try:
        from app import _build_and_log_turn_envelope  # noqa: PLC0415
        _build_and_log_turn_envelope(identity, identity.user_id, None, entry_point="tma")
    except Exception:
        logger.debug("[TurnEnvelope] TMA observation skipped due to error", exc_info=True)

    result = _gw.propose_action(
        tenant_id=identity.tenant_id,
        canonical_user_id=identity.memory_key,
        tool_name="tma_write",
        tool_inputs=tool_inputs,
        origin_channel="tma",
        origin_chat_id=identity.user_id,
        requires_approval=True,
        identity=identity,
        trusted_source="tma_api",
    )

    if not result.ok:
        if result.failure_code in ("persistence_failed", "persistence_lookup_failed"):
            logger.error(
                "_queue_tma_write_approval: propose_action persistence failure for "
                "action=%s: %s", action, result.reason,
            )
            return _reject(result.user_message or result.reason, code=503)
        contract_id = result.contract_id
        if not contract_id:
            return _reject(result.user_message or result.reason, code=409)
        existing_contract = _gw.find_contract(contract_id)
        if existing_contract and existing_contract.status == "pending":
            # Self-heal: the exact same request (same fingerprint) is still
            # pending — recover/ensure its projection instead of erroring,
            # in case an earlier attempt's projection write failed.
            rec = _ensure_approval_projection(contract_id, action, label, risk, identity)
            if rec:
                return rec["id"], {
                    "status": "pending_approval",
                    "approval_id": rec["id"],
                    "contract_id": contract_id,
                    "message": result.user_message or result.reason,
                }, 202
        # Any other duplicate state (approved/executing/executed/completed/
        # outcome_unknown) — do not touch Approvals; surface the Gateway's
        # own message rather than guessing at a display projection.
        return _reject(result.user_message or result.reason, code=409)

    contract_id = result.contract_id
    rec = _ensure_approval_projection(contract_id, action, label, risk, identity)
    if not rec:
        # Phase 4B-2 audit §6: a persisted canonical contract is never
        # deleted or duplicated because the projection write failed. Surface
        # an explicit visibility failure — the contract itself remains valid
        # and will still execute correctly once approved.
        logger.error(
            "_queue_tma_write_approval: projection write failed for new contract=%s "
            "action=%s — canonical ActionContract is valid; only the TMA display "
            "projection is missing.",
            contract_id, action,
        )
        return "", {
            # The contract is pending, not approved — "approved_pending_projection"
            # overstated its own state. Renamed to reflect reality: an
            # otherwise-valid pending contract whose display projection is
            # currently missing.
            "status": "pending_approval_projection_missing",
            "contract_id": contract_id,
            "message": (
                "הבקשה נקלטה לאישור, אך תצוגת ה-Approvals לא עודכנה כעת. "
                "הבקשה עצמה תקינה ולא תבוצע כפול."
            ),
        }, 202

    approval_id = rec["id"]
    return approval_id, {
        "status": "pending_approval",
        "approval_id": approval_id,
        "contract_id": contract_id,
        "message": "Approval required",
    }, 202


class _ProjectionLookupFailed(Exception):
    """Raised when the Approvals projection existence check itself could not
    be completed — distinct from "confirmed not found". Must never be
    treated as "safe to POST a new row": a POST after an unknown lookup
    result could create a duplicate projection for a contract that already
    has one."""


def _find_approval_projection_by_contract(contract_id: str) -> dict | None:
    """Idempotent lookup — is there already an Approvals projection row for
    this ActionContract? contract_id is always a server-generated uuid4
    (core.action_gateway.ActionGateway.propose_action), never user input, so
    no formula-injection risk from embedding it directly.

    strict=True: a lookup/network failure raises _ProjectionLookupFailed
    instead of silently returning [] — callers must never fall through to
    POST on an unknown lookup result."""
    try:
        recs = _at_list(
            "Approvals",
            f"{{{ApprovalsFields.ACTION_CONTRACT_ID}}}='{contract_id}'",
            max_records=2,
            strict=True,
        )
    except AirtableError as exc:
        raise _ProjectionLookupFailed(str(exc)) from exc
    return recs[0] if recs else None


def _repair_approval_projection(existing: dict, contract_id: str) -> dict | None:
    """An existing projection row was found for this contract at propose
    time — repair its canonical projection fields rather than trusting it
    untouched, since it may predate a field's existence or have been left
    inconsistent by a prior partial failure. Only touches the 3 Phase-4B-2
    projection fields plus CONTEXT_DATA (always re-blanked) — never the
    pre-existing display fields (ACTION/REQUESTED_BY/etc.), which were
    already correct at original creation.

    Only valid at propose time, when the contract is known to still be
    "pending" — do not call this once a contract has progressed further."""
    from core.approvals_projection import project_lifecycle_status  # noqa: PLC0415
    patch_fields = {
        ApprovalsFields.ACTION_CONTRACT_ID: contract_id,
        ApprovalsFields.LEGACY_READ_ONLY: False,
        ApprovalsFields.PROJECTED_LIFECYCLE_STATUS: project_lifecycle_status("pending"),
        ApprovalsFields.CONTEXT_DATA: "",
    }
    ok = _at_patch("Approvals", existing["id"], patch_fields)
    if not ok:
        return None
    merged = dict(existing)
    merged["fields"] = {**existing.get("fields", {}), **patch_fields}
    return merged


def _ensure_approval_projection(
    contract_id: str, action: str, label: str, risk: str, identity,
) -> dict | None:
    """Best-effort, idempotent create of the Approvals display projection for
    an already-persisted, still-pending ActionContract. Only ever called
    after the canonical contract is durably saved; its own failure never
    rolls back or duplicates that contract (Phase 4B-2 audit §6). CONTEXT_DATA
    is always left empty — the canonical payload lives in ActionContracts
    only. A lookup failure is treated exactly like a write failure (returns
    None — "projection visibility failure") rather than risking a duplicate
    row by falling through to POST on an unknown result."""
    try:
        existing = _find_approval_projection_by_contract(contract_id)
    except _ProjectionLookupFailed as exc:
        logger.error(
            "_ensure_approval_projection: projection lookup failed for contract=%s "
            "— refusing to POST (would risk a duplicate row): %s", contract_id, exc,
        )
        return None
    if existing:
        return _repair_approval_projection(existing, contract_id)
    from core.approvals_projection import project_lifecycle_status  # noqa: PLC0415
    return _at_post("Approvals", {
        ApprovalsFields.ACTION: label,
        ApprovalsFields.REQUESTED_BY: _identity_ref(identity),
        ApprovalsFields.REQUESTED_AT: datetime.now(timezone.utc).isoformat(),
        ApprovalsFields.RISK_LEVEL: _RISK_LEVEL_AIRTABLE.get(risk, "high"),
        ApprovalsFields.CONTEXT_TYPE: "tma_write",
        ApprovalsFields.CONTEXT_ID: action,
        ApprovalsFields.CONTEXT_DATA: "",
        ApprovalsFields.STATUS: ApprovalStatus.PENDING,
        ApprovalsFields.ACTION_CONTRACT_ID: contract_id,
        ApprovalsFields.LEGACY_READ_ONLY: False,
        ApprovalsFields.PROJECTED_LIFECYCLE_STATUS: project_lifecycle_status("pending"),
    })


def _validate_initdata(init_data_str: str) -> dict | None:
    """
    Validates HMAC of Telegram Mini App initData.
    Returns parsed user dict on success, None on failure/expiry.
    """
    if not init_data_str or not _BOT_TOKEN:
        return None

    params = dict(urllib.parse.parse_qsl(init_data_str, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

    # Derive secret_key = HMAC-SHA256(key="WebAppData", msg=bot_token)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=_BOT_TOKEN.encode(),
        digestmod=hashlib.sha256,
    ).digest()

    # Compute expected = HMAC-SHA256(key=secret_key, msg=data_check_string)
    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    hmac_ok = hmac.compare_digest(received_hash, expected_hash)

    # Reject data older than 24 hours
    auth_date = None
    age_seconds = None
    try:
        auth_date = int(params.get("auth_date", 0))
        age_seconds = int(time.time() - auth_date)
    except (TypeError, ValueError):
        pass

    logger.info(
        "[TMA initData debug] keys=%s hmac_ok=%s received_hash_prefix=%s expected_hash_prefix=%s "
        "auth_date=%s age_seconds=%s bot_token_set=%s bot_token_len=%s",
        sorted(params.keys()),
        hmac_ok,
        (received_hash or "")[:8],
        expected_hash[:8],
        auth_date,
        age_seconds,
        bool(_BOT_TOKEN),
        len(_BOT_TOKEN),
    )

    if not hmac_ok:
        return None

    if auth_date is None or age_seconds is None or age_seconds > 86_400:
        return None

    try:
        return json.loads(params.get("user", "{}"))
    except Exception:
        return None


def require_tma_auth(f):
    """
    Decorator: reads X-Telegram-Init-Data header, validates HMAC on every request.
    Injects keyword arg `identity` into the wrapped handler.
    HMAC validation is always required — there is no dev bypass.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        if not init_data:
            return jsonify({"error": "missing X-Telegram-Init-Data header"}), 401

        user_data = _validate_initdata(init_data)
        if not user_data:
            return jsonify({"error": "invalid or expired initData"}), 401

        telegram_id = str(user_data.get("id", ""))
        identity = resolve_identity("telegram", telegram_id)
        return f(*args, identity=identity, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════
# O0 aggregation helpers — same source as daily_digest.py
# ══════════════════════════════════════════════════════════════════

def _get_global_kpis() -> dict:
    """
    Aggregates KPIs for Projects Hub.

    Payments-derived KPIs (income_this_month/pending_payments_count/
    pending_payments_amount) were removed (TMA read-path optimization):
    Payments belongs to the finance screen (GET /api/finance/pulse) only,
    and the two queries this function used to run against
    "תשלומים (Payments)" always failed (403) — the live table is
    "Payments" (Tables.PAYMENTS); this endpoint should not query Payments
    at all, not just fix the table name.

    hot_leads_count is intentionally absent from this dict — the caller
    (get_projects()) fills it in from the same bulk Leads read
    _get_project_cards() already performs, so this endpoint never issues
    more than one Leads query total.
    """
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # Overdue tasks (same filter as _urgent_tasks)
    overdue = _at_list(
        "משימות (Tasks)",
        f"AND(IS_BEFORE({{תאריך יעד}}, '{tomorrow}'), {{סטטוס}}!='בוצע')",
        max_records=50,
    )

    return {
        "overdue_tasks": len(overdue),
    }


def _parse_json_field(value) -> dict | list:
    if not value:
        return {}
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


_PROJECT_CARDS_BULK_LEADS_MAX_RECORDS = 200


def _get_project_cards(identity) -> tuple[list, int]:
    """
    Returns (cards, hot_leads_count) — project status cards from ProjectsHub,
    and the total Score>=70 count across only the domains actually visible
    in `cards` (TMA read-path optimization).

    Fields: Name, emoji, slug, mode, project_type, status,
            kpi_fields, quick_actions, owner_ids, tenant_id, domain.
    slug and domain are independent — domain drives lead filtering.
    Returns ([], 0) if the table is empty or does not exist yet.

    Active/hot counts for every card come from a single bulk Leads read
    (OR of every visible card's domain, same exclude_statuses filter as
    before) instead of one Leads query per card — this is the only Leads
    read GET /api/projects performs. hot_leads_count is the same bulk
    result's total Score>=70 count, so it reflects only leads in domains
    with a visible card here, in the active statuses — not every hot lead
    in the base regardless of domain/status (see CHANGE_CONTROL_LOG for
    the approved semantics change).
    """
    records = _at_list("ProjectsHub", "", max_records=20)
    if not records:
        return [], 0

    # Filter to visible records BEFORE building the bulk Leads query, so the
    # OR-of-domains only ever reflects domains that will actually be shown.
    visible_records = []
    for r in records:
        f      = r.get("fields", {})
        domain = f.get("domain", "")

        # Temporarily hidden from Projects Hub display — record, slug, and
        # domain are untouched in Airtable; this only excludes the card from
        # this endpoint's response.
        if domain == "saas":
            continue

        # Non-owners: filter to projects where their user_id appears in owner_ids
        if not identity.is_owner:
            _owner_ids = [x.strip() for x in str(f.get("owner_ids", "") or "").split(",")]
            if identity.user_id not in _owner_ids:
                continue

        visible_records.append(r)

    if not visible_records:
        return [], 0

    hub_screen = SCREEN_CONFIGS["project_hub_kpi"]
    hub_cfg    = hub_screen["views"][hub_screen["default_view"]]
    exclude_statuses = hub_cfg.get("exclude_statuses") or []

    domains: list[str] = []
    for r in visible_records:
        d = r.get("fields", {}).get("domain", "")
        safe_d, _ = _safe_formula_param(d, "domain")
        if safe_d and safe_d not in domains:
            domains.append(safe_d)

    leads_by_domain: dict[str, list] = {d: [] for d in domains}
    if domains:
        domain_conds = ", ".join(f"{{domain}}='{d}'" for d in domains)
        or_domains = f"OR({domain_conds})" if len(domains) > 1 else domain_conds
        if exclude_statuses:
            status_conds = ", ".join(f"{{status}}='{s}'" for s in exclude_statuses)
            bulk_formula = f"AND({or_domains}, NOT(OR({status_conds})))"
        else:
            bulk_formula = or_domains
        bulk_leads = _at_list("Leads", bulk_formula,
                               max_records=_PROJECT_CARDS_BULK_LEADS_MAX_RECORDS)
        if len(bulk_leads) == _PROJECT_CARDS_BULK_LEADS_MAX_RECORDS:
            logger.warning(
                "[_get_project_cards] bulk Leads query returned exactly "
                "max_records=%d — active/hot counts may be truncated. domains=%s",
                _PROJECT_CARDS_BULK_LEADS_MAX_RECORDS, domains,
            )
        for lead in bulk_leads:
            d = lead.get("fields", {}).get("domain", "")
            if d in leads_by_domain:
                leads_by_domain[d].append(lead)

    cards = []
    total_hot = 0
    for r in visible_records:
        f      = r.get("fields", {})
        slug   = f.get("slug", "")
        domain = f.get("domain", "")

        leads = leads_by_domain.get(domain, [])
        hot = [
            l for l in leads
            if (l.get("fields", {}).get(LeadFields.SCORE) or 0) >= 70
        ]
        total_hot += len(hot)

        cards.append({
            "id":           r["id"],           # Airtable record_id — internal key
            "slug":         slug,              # URL-safe identifier for dashboard routes
            "name":         f.get("Name", ""),
            "emoji":        f.get("emoji", "📁"),
            "mode":         f.get("mode", "business"),
            "project_type": f.get("project_type", "custom"),
            "domain":       domain,
            "status":       f.get("status", "active"),
            "tenant_id":    f.get("tenant_id", ""),
            "status_color": "red" if hot else ("yellow" if leads else "green"),
            "kpi":          {"label": "לידים פעילים", "value": len(leads)},
            "exception":    f"{len(hot)} לידים חמים" if hot else None,
        })
    return cards, total_hot


# ══════════════════════════════════════════════════════════════════
# WEEK 1 — Auth
# ══════════════════════════════════════════════════════════════════

@tma_api.route("/api/tma/auth", methods=["POST"])
def tma_auth():
    """
    Validates Telegram Mini App initData.
    Returns role + allowed screens so the frontend knows what to render.
    Stateless — no session token issued. Pass initData on every request via
    X-Telegram-Init-Data header.
    """
    data      = request.get_json(force=True) or {}
    init_data = data.get("initData", "")

    user_data = _validate_initdata(init_data)
    if not user_data:
        return jsonify({"error": "invalid or expired initData"}), 401

    telegram_id = str(user_data.get("id", ""))
    identity    = resolve_identity("telegram", telegram_id)

    modes = ["business"]
    if identity.is_owner or "personal" in identity.allowed_domains:
        modes.append("personal")

    return jsonify({
        "ok":              True,
        "role":            identity.role,
        "name":            identity.display_name,
        "user_id":         identity.user_id,
        "allowed_domains": identity.allowed_domains,
        "modes_available": modes,
    })


# ══════════════════════════════════════════════════════════════════
# WEEK 1 — O0 Projects Hub
# ══════════════════════════════════════════════════════════════════

@tma_api.route("/api/projects", methods=["GET"])
@require_tma_auth
def get_projects(identity):
    """O0 — Projects Hub. Owner only."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden — owner only"}), 403

    kpis                       = _get_global_kpis()
    projects, hot_leads_count  = _get_project_cards(identity)
    kpis["hot_leads_count"]    = hot_leads_count

    exceptions = []
    if kpis["overdue_tasks"] > 0:
        exceptions.append(f"⚡ {kpis['overdue_tasks']} משימות עבר מועד")
    if kpis["hot_leads_count"] > 0:
        exceptions.append(f"🔥 {kpis['hot_leads_count']} לידים חמים")

    return jsonify({
        "global_kpis": kpis,
        "exceptions":  exceptions,
        "projects":    projects,
    })


@tma_api.route("/api/projects", methods=["POST"])
@require_tma_auth
def create_project(identity):
    """Create a dynamic project in ProjectsHub table. Owner only."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden — owner only"}), 403

    data = request.get_json(force=True) or {}
    if not data.get("name") or not data.get("mode"):
        return jsonify({"error": "missing required fields: name, mode"}), 400

    fields = {
        "Name":          data["name"],
        "slug":          data.get("slug", ""),
        "emoji":         data.get("emoji", "📁"),
        "mode":          data["mode"],
        "project_type":  data.get("project_type", "custom"),
        "domain":        data.get("domain", "general"),
        "kpi_fields":    json.dumps(data.get("kpi_fields", {})),
        "quick_actions": json.dumps(data.get("quick_actions", {})),
        "status":        "active",
        "owner_ids":     identity.user_id,
        "tenant_id":     identity.tenant_id,
    }
    _, response, status = _queue_tma_write_approval(
        "tma_create_project",
        {
            "op": "post",
            "table": "ProjectsHub",
            "fields": fields,
            "audit_action": "create_project",
            "audit_details": data["name"],
        },
        identity,
        f"Create project: {data['name']}",
    )
    return jsonify(response), status


@tma_api.route("/api/projects/<project_slug>/dashboard", methods=["GET"])
@require_tma_auth
def get_project_dashboard(project_slug, identity):
    """
    Project Dashboard — owner + partner with domain access.
    project_slug is the slug field value (e.g. 'blueview', 'boss-saas').
    Looks up the ProjectsHub record to get the canonical domain for filtering.
    """
    # Step 1: resolve slug → ProjectsHub record to get domain
    project_slug, err = _safe_formula_param(project_slug, "project_slug")
    if err:
        return err
    hub_records = _at_list(
        "ProjectsHub",
        f"{{slug}}='{project_slug}'",
        max_records=1,
    )
    if not hub_records:
        return jsonify({"error": f"project '{project_slug}' not found in ProjectsHub"}), 404

    hub_fields = hub_records[0].get("fields", {})
    domain = hub_fields.get("domain", "")
    if not domain:
        return jsonify({
            "error":   f"project '{project_slug}' has no domain configured",
            "fix":     "Set the 'domain' field in ProjectsHub for this project",
        }), 422

    safe_domain, domain_err = _safe_formula_param(domain, "domain")
    if domain_err:
        logger.warning("[dashboard/%s] unsafe domain value from Airtable: %r", project_slug, domain)
        return jsonify({"error": "invalid domain configuration"}), 422

    # Step 2: permission check using the resolved domain
    if not (identity.is_owner or identity.can_access_domain(safe_domain)):
        return jsonify({"error": "forbidden"}), 403

    # Step 3: fetch data filtered by domain
    try:
        _hub_cfg = SCREEN_CONFIGS["project_hub_kpi"]["views"]["active"]
        _hub_formula = _build_formula(
            entity="Lead",
            domain=safe_domain,
            exclude_statuses=_hub_cfg.get("exclude_statuses"),
        )
        leads = _at_list("Leads", _hub_formula, max_records=50, strict=True)
        deals = _at_list(
            "עסקאות (Deals)",
            f"AND({{domain}}='{safe_domain}', NOT(OR({{{DealFields.STAGE}}}='סגור-ניצחון', {{{DealFields.STAGE}}}='סגור-הפסד')))",
            max_records=20,
            strict=True,
        )
        tasks = _at_list(
            "משימות (Tasks)",
            "{סטטוס}!='בוצע'",
            max_records=10,
            strict=True,
        )
    except AirtableError as e:
        logger.error(f"[dashboard/{project_slug}] Airtable error: {e}")
        return jsonify({
            "error":       "data_unavailable",
            "table":       e.table,
            "http_status": e.http_status,
            "detail":      f"Airtable returned HTTP {e.http_status} for table '{e.table}'",
        }), 502

    return jsonify({
        "project_slug":  project_slug,
        "domain":        domain,
        "name":          hub_fields.get("Name", ""),
        "leads_count":   len(leads),
        "open_deals":    len(deals),
        "open_tasks":    len(tasks),
        "tasks_note":    "tasks table has no domain field — showing global open tasks",
        "leads":         [_fmt_lead_summary(r) for r in leads[:10]],
    })


# ══════════════════════════════════════════════════════════════════
# SCREEN FILTER GATEWAY
# ──────────────────────────────────────────────────────────────────
# עיקרון: Gateway מבצע. Screen מחליט.
# _build_formula() לא יודע מה "dead". SCREEN_CONFIGS יודע.
# עתידי: ProjectsHub.screen_overrides יוכל לדרוס per-tenant.
# ══════════════════════════════════════════════════════════════════

SCREEN_CONFIGS: dict[str, dict] = {

    # O2 Lead Pipeline + P1 My Leads + M1 CRM Dashboard
    "lead_pipeline": {
        "entity": "Lead",
        "default_view": "active",
        "views": {
            "active": {
                "exclude_statuses": ["archived", "duplicate", "not_relevant", "lost"],
                "label": "פעילים",
            },
            "monitoring": {
                "include_statuses": ["waiting_response", "waiting_call"],
                "label": "ממתינים",
            },
            "all": {
                "label": "הכל",
            },
        },
        "default_max_records": 100,
    },

    # O0 Projects Hub — ספירת לידים פעילים לכרטיס פרויקט
    "project_hub_kpi": {
        "entity": "Lead",
        "default_view": "active",
        "views": {
            "active": {
                "exclude_statuses": ["archived", "duplicate", "not_relevant", "lost"],
                "label": "פעילים",
            },
        },
        "default_max_records": 50,
    },

    # O4 Finance Pulse
    "finance_pulse": {
        "entity": "Payment",
        "default_view": "active",
        "views": {
            "active": {
                # הצג הכל חוץ מבוטל — חישוב Python מחלק לקטגוריות
                "exclude_statuses": ["cancelled"],
                "label": "פעילים",
            },
            "overdue": {
                # N11 fix: לפי תאריך בלבד (status field לא אמין ל"באיחור" —
                # תלוי בעדכון ידני). raw_formula דינמי נבנה ב-finance_pulse().
                "label": "באיחור",
            },
            "all": {
                "label": "הכל",
            },
        },
        "default_max_records": 200,
    },

    # PN1 Assets Overview — Personal Mode
    "assets_overview": {
        "entity": "Asset",
        "default_view": "active",
        "views": {
            "active": {
                "exclude_statuses": ["archived"],
                "label": "פעיל",
            },
            "all": {
                "label": "הכל",
            },
        },
        "default_max_records": 50,
    },

    # O7 Activity Feed — pagination בזמן, לא סטטוסים
    "activity_feed": {
        "entity": "Activity",
        "default_view": "recent",
        "views": {
            "recent": {
                "days_back": 30,
                "label": "אחרונים",
            },
            "all": {
                "label": "הכל",
            },
        },
        "default_max_records": 50,
    },
}


def _build_formula(
    *,
    entity: str,
    domain: str = "",
    identity=None,
    include_statuses: list | None = None,
    exclude_statuses: list | None = None,
    raw_formula: str = "",
    score_min: int = 0,
    status_field: str = "status",
) -> str:
    """
    Filter Gateway — מבצע בלבד, לא מחליט.
    הלוגיקה העסקית (מה להסתיר) מגיעה מ-SCREEN_CONFIGS בלבד.

    עדיפות:
      1. raw_formula — מחזיר כמו שהוא (המסך שולט הכל)
      2. include_statuses — רק הסטטוסים האלה
      3. exclude_statuses — כולם חוץ מאלה
      domain + identity מוסיפים תמיד מעל לכל config.

    עתידי:
      score_min — לסינון Hot leads
      status_field — לטבלאות עם שם שדה שונה (Assets.סטטוס)
    """
    # 0. raw_formula — escape hatch מלא
    if raw_formula:
        if domain:
            return f"AND({{domain}}='{domain}', {raw_formula})"
        return raw_formula

    parts: list[str] = []

    # 1. domain מפורש
    if domain:
        parts.append(f"{{domain}}='{domain}'")

    # 2. Partner: domain restriction מ-identity (אוטומטי)
    if identity is not None and getattr(identity, "role", None) == Role.PARTNER:
        allowed = getattr(identity, "allowed_domains", None) or []
        if allowed:
            d_conds = ", ".join(f"{{domain}}='{d}'" for d in allowed)
            parts.append(f"OR({d_conds})")

    # 3. include_statuses — OR של סטטוסים מותרים
    if include_statuses:
        s_conds = ", ".join(f"{{{status_field}}}='{s}'" for s in include_statuses)
        parts.append(f"OR({s_conds})" if len(include_statuses) > 1 else s_conds)

    # 4. exclude_statuses — AND של שלילות
    elif exclude_statuses:
        for s in exclude_statuses:
            parts.append(f"{{{status_field}}}!='{s}'")

    # 5. score_min (עתידי — Hot leads KPI)
    if score_min > 0:
        parts.append(f"{{{LeadFields.SCORE}}}>={score_min}")

    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"AND({', '.join(parts)})"


# ══════════════════════════════════════════════════════════════════
# WEEK 1 — O2 Lead Pipeline + O3 Lead Card
# ══════════════════════════════════════════════════════════════════

def _fmt_lead_summary(rec: dict) -> dict:
    f     = rec.get("fields", {})
    score = int(f.get(LeadFields.SCORE, 0) or 0)
    return {
        "id":     rec["id"],
        "name":   f.get("Name", ""),
        "phone":  f.get("phone", ""),
        "status": f.get("status", ""),
        "score":  score,
        "domain": f.get("domain", ""),
        "source": f.get("source", ""),
    }


# ══════════════════════════════════════════════════════════════════
# Formula-injection guard — all query params embedded in Airtable
# filterByFormula strings MUST pass through this allowlist first.
# ══════════════════════════════════════════════════════════════════
_SAFE_FORMULA_PARAM_RE = re.compile(
    r'^[\wא-׺\- \.]+$',   # ASCII word chars + Hebrew + hyphen/space/dot
    re.UNICODE,
)

def _safe_formula_param(value: str, name: str) -> tuple[str | None, object | None]:
    """Return (value, None) if safe, or (None, 400 response) if injection attempt."""
    if not value:
        return value, None
    if not _SAFE_FORMULA_PARAM_RE.match(value):
        logger.warning("[FormulaInjection] rejected %s=%r", name, value)
        return None, (jsonify({"error": f"invalid {name}"}), 400)
    return value, None


@tma_api.route("/api/leads", methods=["GET"])
@require_tma_auth
def get_leads(identity):
    """O2 — Lead Pipeline. Owner + Manager (all) + Partner (own domains).
    Accepts: ?domain=real_estate OR ?project_slug=blueview (resolves via ProjectsHub)
             ?view=active|monitoring|all  (default: active)
    """
    allowed = {Role.OWNER, Role.MANAGER, Role.PARTNER}
    if identity.role not in allowed:
        return jsonify({"error": "forbidden"}), 403

    domain_q = request.args.get("domain", "")
    domain_q, err = _safe_formula_param(domain_q, "domain")
    if err:
        return err

    # Resolve project_slug → domain via ProjectsHub
    slug_q = request.args.get("project_slug", "")
    slug_q, err = _safe_formula_param(slug_q, "project_slug")
    if err:
        return err
    if slug_q and not domain_q:
        hub = _at_list("ProjectsHub", f"{{slug}}='{slug_q}'", max_records=1)
        if hub:
            domain_q = hub[0].get("fields", {}).get("domain", "")

    # Screen config — lead_pipeline
    screen = SCREEN_CONFIGS["lead_pipeline"]
    view_q = request.args.get("view", screen["default_view"])
    if view_q not in screen["views"]:
        view_q = screen["default_view"]
    view_cfg = screen["views"][view_q]

    formula = _build_formula(
        entity="Lead",
        domain=domain_q,
        identity=identity,
        include_statuses=view_cfg.get("include_statuses"),
        exclude_statuses=view_cfg.get("exclude_statuses"),
        raw_formula=view_cfg.get("raw_formula", ""),
    )

    records = _at_list("Leads", formula, max_records=screen["default_max_records"])

    return jsonify({
        "view": view_q,
        "available_views": {
            k: v.get("label", k)
            for k, v in screen["views"].items()
        },
        "count": len(records),
        "leads": [_fmt_lead_summary(r) for r in records],
    })


# ══════════════════════════════════════════════════════════════════
# BUG-104 — Core Reasoning Activation Program · Phase 1
# Leads Read-Only Reasoning Projection (GET /api/leads/<id> only)
# ══════════════════════════════════════════════════════════════════

# Reverse-link field on a Leads record → list of Lead-Event record IDs.
_LEAD_EVENTS_LINK_FIELD = "Lead Events"
# Airtable record-ID shape — used to reject anything that is not a clean rec ID
# before it is embedded in a RECORD_ID() formula (defense in depth).
_REC_ID_RE = re.compile(r"^rec[A-Za-z0-9]+$")


def _event_linked_to_lead(event: dict, lead_id: str) -> bool:
    """
    BUG-104 Phase 1.1 — second, independent linkage proof. The reverse-link
    membership on the Lead snapshot only LOCATES candidate record IDs; it is
    not itself proof that the fetched event actually links back to this lead
    (e.g. a stale/misconfigured reverse link). An event is only admitted when
    its OWN LeadEventFields.LEAD_LINK field is a list that explicitly contains
    the current lead_id. Operates on the already-fetched record — no read.
    """
    own_link = event.get("fields", {}).get(LeadEventFields.LEAD_LINK)
    if not isinstance(own_link, list):
        return False   # malformed/missing own link field — excluded, fail closed
    return lead_id in own_link


def _read_lead_events(rec: dict):
    """
    Read the Lead Events for one lead using the reverse-link IDs already present
    on the loaded Lead snapshot — the endpoint owns the read; the projection
    never reads. Returns:
      - []                 when the lead has no linked events (available, count 0)
                           — NO Airtable call is made.
      - list[event]        the linked event records that also pass the
                           independent own-field linkage check
                           (_event_linked_to_lead) — exactly ONE Airtable call.
      - None (UNAVAILABLE) only on a real read failure.

    The formula matches the Lead-Event records by their own RECORD_ID() — the
    IDs come from the Lead snapshot's reverse link, never from the lead ID, and
    the whole table is never scanned/filtered locally. Deterministic cap: the
    first _MAX linked IDs (snapshot order) are used when a lead has more than the
    supported cap.
    """
    from core.leads_reasoning_projection import MAX_LEAD_EVENT_IDS

    lead_id = rec.get("id", "")
    raw_ids = rec.get("fields", {}).get(_LEAD_EVENTS_LINK_FIELD, []) or []
    event_ids = [e for e in raw_ids if isinstance(e, str) and _REC_ID_RE.match(e)]
    if not event_ids:
        return []   # available, empty — no Airtable read

    capped  = event_ids[:MAX_LEAD_EVENT_IDS]        # deterministic cap
    clause  = ",".join(f"RECORD_ID()='{eid}'" for eid in capped)
    formula = f"OR({clause})"
    try:
        fetched = _at_list(Tables.LEAD_EVENTS, formula, max_records=MAX_LEAD_EVENT_IDS, strict=True)
    except AirtableError as e:
        logger.warning("[BUG-104] lead events read failed for %s: %s", lead_id, e)
        return None   # EVENTS_UNAVAILABLE

    # Second linkage proof (Phase 1.1) — filter already-fetched records, no extra read.
    return [ev for ev in fetched if _event_linked_to_lead(ev, lead_id)]


def _format_lead_reasoning_log(
    lead_id: str,
    mode: str,
    raw_status,
    raw_business_outcome,
    projection: dict,
) -> str:
    """
    BUG-104 / CR_OBS_LOG — compact, single-line Lead reasoning observability
    log. Pure formatting, no I/O. Deliberately PII-free: only lead_id, status/
    outcome labels, event COUNT, lead_score value/state, and error COUNT —
    never phone/name/notes/message/event content, and never the full engine
    error text (only how many).

    Format: [LeadReasoning] lead=<id> mode=<off|shadow|on> status=<raw status>
    outcome=<raw Business Outcome> state=<phase> events=<count|unavailable>
    lead_score=<value|missing|invalid> degraded=<true|false> errors=<count>
    """
    def _raw(value) -> str:
        text = str(value or "").strip()
        return text if text else "<missing>"

    events = projection.get("events") or {}
    events_txt = "unavailable" if not events.get("available") else str(events.get("count", 0))

    lead_score = projection.get("lead_score") or {}
    score_state = lead_score.get("state")
    score_txt = str(lead_score.get("value")) if score_state == "present" else str(score_state or "missing")

    engine = projection.get("engine") or {}
    degraded_txt = str(bool(engine.get("degraded"))).lower()
    errors_count = len(engine.get("errors") or [])

    return (
        f"[LeadReasoning] lead={lead_id} mode={mode} "
        f"status={_raw(raw_status)} outcome={_raw(raw_business_outcome)} "
        f"state={projection.get('state')} events={events_txt} "
        f"lead_score={score_txt} degraded={degraded_txt} errors={errors_count}"
    )


def _apply_leads_reasoning_projection(payload: dict, rec: dict) -> None:
    """
    Attach (or, in shadow, only compute+log) the read-only reasoning projection
    according to FEATURE_CORE_REASONING_LEADS_STATE. Never mutates the lead,
    never persists, and never fails the GET because of a reasoning error.
    Mutates ``payload`` in place only in the 'on' state.
    """
    import feature_flags as _ff  # noqa: PLC0415
    state = _ff.get_core_reasoning_leads_state()
    if state == "off":
        return   # no extra read, no reasoning, response stays byte-compatible

    from core.leads_reasoning_projection import (  # noqa: PLC0415
        build_reasoning_projection, degraded_projection,
    )

    as_of  = datetime.now(timezone.utc)   # single request-scoped reference time
    lead_id = rec.get("id", "")
    fields  = rec.get("fields", {})
    try:
        events = _read_lead_events(rec)   # ≤1 Lead Events read, keyed by linked IDs
        projection = build_reasoning_projection(rec, events, as_of)
    except Exception as e:
        # 'on' must not fail the endpoint — return an honest degraded projection.
        logger.warning("[BUG-104] reasoning projection failed for %s: %s", lead_id, e)
        projection = degraded_projection(as_of, f"projection_error: {e}")

    # BUG-104 / CR_OBS_LOG — compact observability line for both shadow and on
    # (never for off — the projection above is never computed in that state).
    # No extra Airtable read: rec/projection are already loaded in memory.
    logger.info(_format_lead_reasoning_log(
        lead_id, state, fields.get(LeadFields.STATUS), fields.get(LeadFields.OUTCOME), projection,
    ))

    if state == "shadow":
        # Computed + verified + logged, but the API response is unchanged.
        logger.info("[BUG-104][shadow] lead=%s reasoning=%s", lead_id, projection)
        return

    # state == "on"
    payload["reasoning"] = projection


@tma_api.route("/api/leads/<lead_id>", methods=["GET"])
@require_tma_auth
def get_lead(lead_id, identity):
    """O3 — Lead Card. Owner + Manager + Partner (own domain only)."""
    allowed = {Role.OWNER, Role.MANAGER, Role.PARTNER}
    if identity.role not in allowed:
        return jsonify({"error": "forbidden"}), 403

    rec = _at_get_record("Leads", lead_id)
    if not rec:
        return jsonify({"error": "lead not found"}), 404

    f = rec.get("fields", {})

    if identity.role == Role.PARTNER and not identity.can_access_domain(f.get("domain", "")):
        return jsonify({"error": "forbidden"}), 403

    # Timeline from Interaction Log — automated interactions related to this lead
    timeline_recs = _at_list(
        Tables.INTERACTION_LOG,
        f"SEARCH('{lead_id}',{{{InteractionLogFields.SUMMARY}}})",
        max_records=20,
    )
    def _readable_timeline_value(value: str) -> str:
        value = re.sub(r"\brec\w+\b", "רשומה", str(value or ""))
        return value.strip()

    timeline = []
    for t in timeline_recs:
        tf = t.get("fields", {})
        title = _readable_timeline_value(tf.get(InteractionLogFields.TITLE, ""))
        summary = _readable_timeline_value(tf.get(InteractionLogFields.SUMMARY, ""))
        timestamp = tf.get(InteractionLogFields.TIMESTAMP, "")
        readable = summary
        if title and title not in readable:
            readable = f"{title}: {readable}" if readable else title
        timeline.append({
            "summary": readable,
            "channel": _readable_timeline_value(tf.get(InteractionLogFields.CHANNEL, "")),
            "timestamp": timestamp,
        })

    score       = int(f.get(LeadFields.SCORE, 0) or 0)
    score_color = "red" if score >= 70 else ("yellow" if score >= 40 else "blue")

    payload = {
        "id":            rec["id"],
        "name":          f.get(LeadFields.NAME, ""),
        "phone":         f.get(LeadFields.PHONE, ""),
        "domain":        f.get(LeadFields.DOMAIN, ""),
        "status":        f.get(LeadFields.STATUS, ""),
        "score":         score,
        "score_color":   score_color,
        "source":        f.get(LeadFields.SOURCE, ""),
        "summary":       f.get(LeadFields.SUMMARY, ""),
        "next_step":     f.get(LeadFields.NEXT_STEP, ""),
        "created_at":    f.get(LeadFields.CREATED_AT, ""),
        "timeline":      timeline,
        "tier":          f.get(LeadFields.TIER, ""),
        "outcome":       f.get(LeadFields.OUTCOME, ""),
        "next_followup": f.get(LeadFields.NEXT_FOLLOWUP, ""),
        "owner":         f.get(LeadFields.OWNER, ""),
    }

    # BUG-104 — Core Reasoning Activation Program, Phase 1 (read-only).
    # off:    no extra Lead-Events read, no reasoning, response byte-compatible.
    # shadow: reasoning computed + logged, response unchanged, no persistence.
    # on:     "reasoning" projection attached to the response, no persistence.
    _apply_leads_reasoning_projection(payload, rec)

    return jsonify(payload)


@tma_api.route("/api/leads/<lead_id>/status", methods=["PATCH"])
@require_tma_auth
def update_lead_status(lead_id, identity):
    """Update lead status. Owner + Manager only."""
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    data       = request.get_json(force=True) or {}
    new_status = _clean_select_value(data.get("status"))
    if not new_status:
        return jsonify({"error": "missing field: status"}), 400
    if new_status not in LeadStatus.ALL:
        return jsonify({"error": "invalid status", "valid": sorted(LeadStatus.ALL)}), 400

    _, response, status = _queue_tma_write_approval(
        "tma_update_lead_status",
        {
            "op": "patch",
            "table": "Leads",
            "record_id": lead_id,
            "fields": {"status": new_status},
            "audit_action": "lead_status_update",
            "audit_details": f"{lead_id} -> {new_status}",
        },
        identity,
        f"Update lead status: {lead_id} -> {new_status}",
    )
    return jsonify(response), status


# שדות עריכה מורשים ב-PATCH /api/leads/<id>
_LEAD_EDITABLE = {
    LeadFields.STATUS, LeadFields.SCORE,  # TIER הוא formula field — לא ניתן לכתיבה
    "Score", LeadFields.OUTCOME, "Next Followup", LeadFields.OWNER, LeadFields.NEXT_STEP,
}
_LEAD_FIELD_ALIASES = {
    "score": "Score",
    "next_step": LeadFields.NEXT_STEP,
    "next_followup": "Next Followup",
    "owner": LeadFields.OWNER,
}
_LEAD_IGNORED_PATCH_FIELDS = {"tier", "טמפרטורה"}


def _normalize_lead_patch_fields(data: dict) -> dict:
    """Map frontend aliases to Airtable field names before PATCH."""
    normalized = {}
    for key, value in data.items():
        if key in _LEAD_IGNORED_PATCH_FIELDS:
            continue
        airtable_key = _LEAD_FIELD_ALIASES.get(key, key)
        if airtable_key not in _LEAD_EDITABLE:
            continue
        if airtable_key != key and airtable_key in data:
            continue
        normalized[airtable_key] = value
    return normalized

# Single-select fields that must arrive as raw strings (no embedded quotes).
_LEAD_SELECT_FIELDS = {LeadFields.STATUS, LeadFields.OUTCOME, LeadFields.NEXT_STEP}

# Linked record coercion (Owner → list of rec IDs) is handled by airtable_gateway.LINKED_RECORD_FIELDS.


def _clean_select_value(value) -> str:
    """Strip whitespace and unwrap any surrounding quote chars from a select value."""
    if value is None:
        return ""
    value = str(value).strip()
    while len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    return value


# Lead outcomes/statuses must match Airtable single-select options exactly.
# Canonical (no-trailing-space) outcome keys -> Leads.status value to set alongside the outcome.
_OUTCOME_STATUS_MAP = {
    "open": LeadStatus.ACTIVE,
    "needs_followup": LeadStatus.WAITING_RESPONSE,
    "meeting_scheduled": LeadStatus.ACTIVE,
    "converted": LeadStatus.DONE,
    "archived": LeadStatus.ARCHIVED,
    "lost": LeadStatus.LOST,
    "duplicate": LeadStatus.DUPLICATE,
    "not_relevant": LeadStatus.NOT_RELEVANT,
}


@tma_api.route("/api/leads/<lead_id>", methods=["PATCH"])
@require_tma_auth
def patch_lead(lead_id, identity):
    """עדכון שדות ליד. Owner — מיידי; Manager — דרך approval."""
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True) or {}
    fields = _normalize_lead_patch_fields(data)
    if not fields:
        fields = {k: v for k, v in data.items() if k in _LEAD_EDITABLE}
    # Unwrap any embedded quotes from select fields (frontend may send '"value"')
    for k in _LEAD_SELECT_FIELDS:
        if k in fields:
            fields[k] = _clean_select_value(fields[k])

    if LeadFields.STATUS in fields:
        if fields[LeadFields.STATUS] not in LeadStatus.ALL:
            return jsonify({"error": "invalid status", "valid": sorted(LeadStatus.ALL)}), 400
    if LeadFields.OUTCOME in fields:
        outcome_value = LeadOutcome.BY_KEY.get(fields[LeadFields.OUTCOME].lower())
        if outcome_value is None:
            return jsonify({"error": "invalid outcome", "valid": sorted(LeadOutcome.BY_KEY)}), 400
        fields[LeadFields.OUTCOME] = outcome_value

    if not fields or all(v == "" for v in fields.values()):
        return jsonify({"error": "no editable fields provided"}), 400

    if identity.is_owner:
        ok = _at_patch("Leads", lead_id, fields)
        if not ok:
            return jsonify({"error": "update failed"}), 500
        _audit("lead_patch", identity, details=f"{lead_id}: {list(fields.keys())}")
        from core.lead_event_writer import write_tma_lead_event
        write_tma_lead_event(lead_id, "lead_patch", fields)
        return jsonify({"ok": True, "lead_id": lead_id, "updated": list(fields.keys())})

    _, response, status = _queue_tma_write_approval(
        "tma_patch_lead",
        {
            "op": "patch",
            "table": "Leads",
            "record_id": lead_id,
            "fields": fields,
            "audit_action": "lead_patch",
            "audit_details": f"{lead_id}: {list(fields.keys())}",
        },
        identity,
        f"Update lead fields: {list(fields.keys())}",
    )
    return jsonify(response), status


@tma_api.route("/api/leads/<lead_id>/outcome", methods=["POST"])
@require_tma_auth
def set_lead_outcome(lead_id, identity):
    """קביעת תוצאה עסקית. Outcomes סופיים מעדכנים status=done. Owner — מיידי; Manager — approval."""
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True) or {}
    outcome_key = _clean_select_value(data.get("outcome")).lower()
    if not outcome_key:
        return jsonify({"error": "missing field: outcome"}), 400
    outcome_key = {
        "followup_needed": "needs_followup",
        "meeting_booked": "meeting_scheduled",
    }.get(outcome_key, outcome_key)
    outcome_value = LeadOutcome.BY_KEY.get(outcome_key)
    if outcome_value is None:
        return jsonify({"error": "invalid outcome", "valid": sorted(LeadOutcome.BY_KEY)}), 400

    fields: dict = {LeadFields.OUTCOME: outcome_value}
    if outcome_key in _OUTCOME_STATUS_MAP:
        fields[LeadFields.STATUS] = _OUTCOME_STATUS_MAP[outcome_key]

    if identity.is_owner:
        ok = _at_patch("Leads", lead_id, fields)
        if not ok:
            return jsonify({"error": "update failed"}), 500
        _audit("lead_outcome", identity, details=f"{lead_id}: {outcome_key}")
        from core.lead_event_writer import write_tma_lead_event
        write_tma_lead_event(lead_id, "lead_outcome", fields)
        return jsonify({"ok": True, "lead_id": lead_id, "outcome": outcome_key})

    _, response, status = _queue_tma_write_approval(
        "tma_set_lead_outcome",
        {
            "op": "patch",
            "table": "Leads",
            "record_id": lead_id,
            "fields": fields,
            "audit_action": "lead_outcome",
            "audit_details": f"{lead_id}: {outcome_key}",
        },
        identity,
        f"Set lead outcome: {outcome_key}",
    )
    return jsonify(response), status


@tma_api.route("/api/leads/<lead_id>/task", methods=["POST"])
@require_tma_auth
def create_lead_task(lead_id, identity):
    """יצירת משימה מליד — מעתיק אוטומטית domain, owner, lead link."""
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "missing field: title"}), 400

    due_date = data.get("due_date") or (date.today() + timedelta(days=1)).isoformat()
    notes    = (data.get("notes") or "").strip()

    # קריאת נתוני הליד להעתקת domain, owner
    lead_rec = _at_get_record("Leads", lead_id)
    if not lead_rec:
        return jsonify({"error": "lead not found"}), 404
    lf = lead_rec.get("fields", {})
    lead_name   = lf.get(LeadFields.NAME, lead_id)
    lead_domain = _normalize_task_domain(lf.get(LeadFields.DOMAIN, ""))
    lead_owner  = lf.get(LeadFields.OWNER, "")

    task_fields: dict = {
        TaskFields.NAME:     title,
        TaskFields.STATUS:   "ממתין",
        TaskFields.DUE_DATE: due_date,
    }
    if notes:
        task_fields[TaskFields.DESCRIPTION] = notes
    if lead_domain:
        task_fields[TaskFields.DOMAIN] = lead_domain
    if lead_owner:
        task_fields[TaskFields.OWNER] = lead_owner
    # קישור ליד — linked record array
    task_fields[TaskFields.LEAD_LINK] = [lead_id]

    if identity.is_owner:
        rec = _at_post(Tables.TASKS, task_fields)
        if not rec:
            return jsonify({"error": "task creation failed"}), 500
        _audit("lead_task_created", identity, details=f"lead={lead_name} task={title}")
        return jsonify({"ok": True, "id": rec.get("id", ""), "lead_id": lead_id}), 201

    # Manager: queue for owner approval (consistent with patch_lead / set_lead_outcome)
    _, response, status = _queue_tma_write_approval(
        "tma_create_lead_task",
        {
            "op":            "post",
            "table":         Tables.TASKS,
            "fields":        task_fields,
            "audit_action":  "lead_task_created",
            "audit_details": f"lead={lead_name} task={title}",
        },
        identity,
        f"Create task for lead: {lead_name} — {title}",
    )
    return jsonify(response), status


# WEEK 1 — Follow-Up (O3 Action)
# ══════════════════════════════════════════════════════════════════

@tma_api.route("/api/followup", methods=["POST"])
@require_tma_auth
def create_followup(identity):
    """Create a follow-up task from Lead Card. Owner + Manager."""
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    data    = request.get_json(force=True) or {}
    lead_id = data.get("lead_id", "")
    note    = data.get("note", "מעקב")

    # Resolve lead name for readable task title
    lead_name = lead_id
    if lead_id:
        rec = _at_get_record("Leads", lead_id)
        if rec:
            lead_name = rec.get("fields", {}).get("Name", lead_id)

    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    task_fields = {
        "\u05db\u05d5\u05ea\u05e8\u05ea \u05d4\u05de\u05e9\u05d9\u05de\u05d4": f"\u05de\u05e2\u05e7\u05d1: {lead_name}",
        "\u05ea\u05d9\u05d0\u05d5\u05e8": note,
        "\u05ea\u05d0\u05e8\u05d9\u05da \u05d9\u05e2\u05d3": tomorrow,
        "\u05e1\u05d8\u05d8\u05d5\u05e1": "\u05de\u05de\u05ea\u05d9\u05df",
    }
    _, response, status = _queue_tma_write_approval(
        "tma_create_followup",
        {
            "op": "post",
            "table": "\u05de\u05e9\u05d9\u05de\u05d5\u05ea (Tasks)",
            "fields": task_fields,
            "audit_action": "followup_created",
            "audit_details": f"{lead_name}: {note[:80]}",
        },
        identity,
        f"Create follow-up: {lead_name}",
    )
    return jsonify(response), status

# WEEK 1 — Ask AI (routes through existing BOSS context layer)
# ══════════════════════════════════════════════════════════════════

@tma_api.route("/api/ai/ask", methods=["POST"])
@require_tma_auth
def ask_ai(identity):
    """
    Ask AI in context. Owner + Manager.
    Routes through build_context (existing BOSS context/agent layer) — single turn,
    no tool loop. Context data is injected from Airtable before calling the LLM.
    """
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    data         = request.get_json(force=True) or {}
    question     = data.get("question", "").strip()
    context_type = data.get("context", "general")   # lead_card | projects_hub | general
    context_id   = data.get("context_id", "")

    if not question:
        return jsonify({"error": "missing field: question"}), 400

    # Build context string injected before the question
    ctx_data = ""
    if context_type == "lead_card" and context_id:
        rec = _at_get_record("Leads", context_id)
        if rec:
            f = rec.get("fields", {})
            ctx_data = (
                f"ליד: {f.get('Name', '')} | "
                f"טלפון: {f.get('phone', '')} | "
                f"סטטוס: {f.get('status', '')} | "
                f"ציון: {f.get(LeadFields.SCORE, '')} | "
                f"תקציר: {f.get('summary', '')}"
            )
    elif context_type == "projects_hub":
        kpis = _get_global_kpis()
        ctx_data = (
            f"הכנסות החודש: ₪{kpis['income_this_month']:,} | "
            f"תשלומים ממתינים: {kpis['pending_payments_count']} | "
            f"משימות באיחור: {kpis['overdue_tasks']} | "
            f"לידים חמים: {kpis['hot_leads_count']}"
        )

    full_question = (
        f"[הקשר TMA — {context_type}]\n{ctx_data}\n\nשאלה: {question}"
        if ctx_data else question
    )

    try:
        # Route through existing BOSS context layer — build_context applies
        # role-based system prompt, model selection, and memory from memory_store.
        from context import build_context
        from llm_fallback import call_anthropic_text
        from memory_store import memory

        ctx      = build_context(identity, full_question)
        history  = memory.get_for_claude(ctx.memory_key)
        messages = history + [{"role": "user", "content": full_question}]

        answer = call_anthropic_text(
            source="tma_api.ask_ai",
            model=ctx.model,
            max_tokens=ctx.max_tokens,
            temperature=0.2,
            system=ctx.system_prompt,
            messages=messages,
        )
        if not answer:
            answer = "AI service returned no text."
        return jsonify({"answer": answer, "context": context_type})


    except Exception as e:
        logger.error(f"[AskAI] error: {e}", exc_info=True)
        return jsonify({"error": "AI service unavailable"}), 503

    return jsonify({"answer": answer, "context": context_type})


# ══════════════════════════════════════════════════════════════════
@tma_api.route("/api/finance/pulse", methods=["GET"])
@require_tma_auth
def finance_pulse(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    today       = date.today()
    month_start = today.replace(day=1).isoformat()
    today_str   = today.isoformat()

    # ── Screen config ──────────────────────────────────────────────
    screen   = SCREEN_CONFIGS["finance_pulse"]
    view_q   = request.args.get("view", screen["default_view"])
    if view_q not in screen["views"]:
        view_q = screen["default_view"]
    view_cfg = screen["views"][view_q]

    domain_q = request.args.get("domain", "")
    domain_q, err = _safe_formula_param(domain_q, "domain")
    if err:
        return err

    # N11 fix: overdue = לא שולם + תאריך עבר — לפי תאריך בלבד, לא לפי
    # status="overdue" (שדה שדורש עדכון ידני ולא אמין).
    raw_formula = view_cfg.get("raw_formula", "")
    if view_q == "overdue":
        raw_formula = (
            f"AND(NOT({{{PaymentFields.STATUS}}}='{PaymentStatus.RECEIVED}'), "
            f"IS_BEFORE({{{PaymentFields.DATE}}}, '{today_str}'))"
        )

    formula = _build_formula(
        entity           = "Payment",
        domain           = domain_q,
        include_statuses = view_cfg.get("include_statuses"),
        exclude_statuses = view_cfg.get("exclude_statuses"),
        raw_formula      = raw_formula,
        status_field     = PaymentFields.STATUS,
    )

    # ── Payments ───────────────────────────────────────────────────
    try:
        all_payments = _at_list(
            Tables.PAYMENTS,
            formula,
            max_records = screen["default_max_records"],
            strict      = True,
        )
    except AirtableError as e:
        logger.error(f"[finance_pulse] Airtable error: {e}")
        return jsonify({
            "error":       "data_unavailable",
            "table":       e.table,
            "http_status": e.http_status,
            "detail":      f"Airtable returned HTTP {e.http_status} for '{e.table}'",
        }), 502

    income_amount  = 0
    income_count   = 0
    pending_amount = 0
    pending_count  = 0
    overdue_amount = 0
    overdue_count  = 0
    recent: list   = []

    for rec in all_payments:
        f      = rec.get("fields", {})
        amount = float(f.get(PaymentFields.AMOUNT, 0) or 0)
        status = (f.get(PaymentFields.STATUS, "") or "").strip()
        d_str  = (f.get(PaymentFields.DATE, "") or "")[:10]

        # cancelled כבר סונן ב-formula (view=active) — double-check בטיחות
        if view_q != "all" and status == PaymentStatus.CANCELLED:
            continue

        if status == PaymentStatus.RECEIVED:
            if d_str >= month_start:
                income_amount += amount
                income_count  += 1
                recent.append({
                    "ref":    f.get(PaymentFields.REF, "—"),
                    "amount": amount,
                    "date":   d_str,
                    "status": status,
                })
        elif status == PaymentStatus.OVERDUE:
            overdue_amount += amount
            overdue_count  += 1
        else:
            # pending + כל status אחר שאינו received/cancelled/overdue
            if d_str and d_str < today_str:
                overdue_amount += amount
                overdue_count  += 1
            else:
                pending_amount += amount
                pending_count  += 1

    recent.sort(key=lambda x: x["date"], reverse=True)
    recent = recent[:5]

    # ── Expenses ───────────────────────────────────────────────────
    expense_amount = 0
    expense_count  = 0
    exp_formula    = _build_formula(
        entity = "Expense",
        domain = domain_q,
    )
    all_expenses = _at_list(Tables.EXPENSES, exp_formula, max_records=200)
    for rec in all_expenses:
        f     = rec.get("fields", {})
        amt   = float(f.get(ExpenseFields.AMOUNT, 0) or 0)
        d_str = (f.get(ExpenseFields.DATE, "") or "")[:10]
        if d_str >= month_start:
            expense_amount += amt
            expense_count  += 1

    net = income_amount - expense_amount

    return jsonify({
        "view":     view_q,
        "available_views": {
            k: v.get("label", k)
            for k, v in screen["views"].items()
        },
        "period":   f"{today.year}-{today.month:02d}",
        "income":   {"amount": income_amount,  "count": income_count},
        "pending":  {"amount": pending_amount, "count": pending_count},
        "overdue":  {"amount": overdue_amount, "count": overdue_count},
        "expenses": {"amount": expense_amount, "count": expense_count},
        "net":      net,
        "recent":   recent,
    })


_RISK_HIGH = {"גבוה", "high"}
_RISK_LOW  = {"נמוך", "low"}


def _derive_legacy_read_only(fields: dict) -> bool:
    """A projection row is legacy/read-only if EITHER the stored flag says
    so, OR it has no action_contract_id at all. Never trust the stored flag
    alone: a genuinely pre-Phase-4B-2 row never had either field populated,
    so a missing contract_id must independently force legacy_read_only=True
    even if the (absent) flag would otherwise default to False."""
    contract_id = fields.get(ApprovalsFields.ACTION_CONTRACT_ID, "")
    stored_flag = bool(fields.get(ApprovalsFields.LEGACY_READ_ONLY, False))
    return stored_flag or not contract_id


def _is_canonical_tma_contract(contract, identity) -> bool:
    """
    Phase 4B-2 follow-up: an Approvals row is only actionable — and only
    ever eligible for action_gateway.approve()/reject() — if its canonical
    ActionContract is unambiguously a TMA write-through-approval contract
    belonging to the acting identity's own tenant. A projection whose
    action_contract_id happens to point at some other kind of pending
    contract (gmail_send_draft, calendar_create_event, a lead-capture
    airtable_add proposed through an entirely different flow, or a
    different tenant's contract) must never be treated as actionable
    through this screen, and approve()/reject() must never be called on it
    from here — even though those contracts are individually legitimate,
    they did not enter their pending state through this TMA projection
    flow and this screen has no authority over them.

    Every condition is required:
      - contract.status == "pending"       — the only actionable state
      - contract.tool_name == "tma_write"  — the TMA adapter, nothing else
      - contract.trusted_source == "tma_api"
      - contract.origin_channel == "tma"
      - contract.approval_policy == "approval" — never self_confirm
      - contract.tenant_id == identity.tenant_id — no cross-tenant action
    """
    if contract is None:
        return False
    return (
        contract.status == "pending"
        and contract.tool_name == "tma_write"
        and getattr(contract, "trusted_source", "") == "tma_api"
        and contract.origin_channel == "tma"
        and getattr(contract, "approval_policy", "") == "approval"
        and contract.tenant_id == getattr(identity, "tenant_id", None)
    )


def _projection_actionable(contract_id: str, legacy_read_only: bool, identity) -> bool:
    """Whether this Approvals row is actionable, derived strictly from the
    canonical ActionContract via _is_canonical_tma_contract() — never from
    Approvals.STATUS. Legacy/no-contract rows are always False. Any lookup
    failure also degrades to False (fail closed for a display flag: better
    to under- than over-claim actionability) rather than raising out of a
    list-rendering path."""
    if not contract_id or legacy_read_only:
        return False
    try:
        from core.action_gateway import action_gateway as _gw  # noqa: PLC0415
        contract = _gw.find_contract(contract_id)
        return _is_canonical_tma_contract(contract, identity)
    except Exception as exc:
        logger.warning("_projection_actionable: lookup failed for contract=%s: %s", contract_id, exc)
        return False


def _fmt_approval(rec: dict, identity) -> dict:
    f = rec.get("fields", {})
    contract_id = f.get(ApprovalsFields.ACTION_CONTRACT_ID, "")
    legacy_read_only = _derive_legacy_read_only(f)
    return {
        "id":           rec["id"],
        "action":       f.get(ApprovalsFields.ACTION, ""),
        "requested_by": f.get(ApprovalsFields.REQUESTED_BY, ""),
        "requested_at": f.get(ApprovalsFields.REQUESTED_AT, ""),
        "risk_level":   f.get(ApprovalsFields.RISK_LEVEL, ""),
        "context_type": f.get(ApprovalsFields.CONTEXT_TYPE, ""),
        "context_id":   f.get(ApprovalsFields.CONTEXT_ID, ""),
        "status":       f.get(ApprovalsFields.STATUS, ApprovalStatus.PENDING),
        "action_contract_id":         contract_id,
        "legacy_read_only":           legacy_read_only,
        "projected_lifecycle_status": f.get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS, ""),
        "actionable":                 _projection_actionable(contract_id, legacy_read_only, identity),
    }


_CAPABILITY_MAP_PATH = Path(__file__).resolve().parent / "reports" / "capability_map.json"

_DEFAULT_SYSTEM_HEALTH = {
    "health_percent": 0,
    "working_count": 0,
    "partial_count": 0,
    "broken_count": 0,
}

_DEFAULT_CRITICAL_SYSTEMS = [
    {"name": "Leads", "status": "UNKNOWN", "color": "yellow"},
    {"name": "Tasks", "status": "UNKNOWN", "color": "yellow"},
    {"name": "Payments", "status": "UNKNOWN", "color": "yellow"},
    {"name": "Projects", "status": "UNKNOWN", "color": "yellow"},
    {"name": "Approvals", "status": "UNKNOWN", "color": "yellow"},
]

_PERMISSIONS_MATRIX = [
    {"role": "Owner", "read": "All", "write": "All / risk-gated", "approve": "Yes"},
    {"role": "Partner", "read": "Own domains", "write": "Limited / domain scoped", "approve": "No"},
    {"role": "Manager", "read": "Operations + CRM", "write": "Approval required", "approve": "No"},
    {"role": "Employee", "read": "Tasks", "write": "Status only", "approve": "No"},
]

_BUSINESS_LANGUAGE = {
    "lead_status": [
        {"value": "new", "label": "New lead"},
        {"value": "active", "label": "Active lead"},
        {"value": "waiting_call", "label": "Waiting for call"},
        {"value": "waiting_response", "label": "Waiting for response"},
        {"value": "done", "label": "Done"},
        {"value": "archived", "label": "Archived"},
        {"value": "lost", "label": "Lost lead"},
        {"value": "duplicate", "label": "Duplicate"},
        {"value": "not_relevant", "label": "Not relevant"},
    ],
    "lead_outcome": [
        {"value": "open", "label": "Still active"},
        {"value": "needs_followup", "label": "Needs follow-up"},
        {"value": "meeting_scheduled", "label": "Meeting scheduled"},
        {"value": "converted", "label": "Converted to business result"},
        {"value": "not_relevant", "label": "Not relevant"},
        {"value": "lost", "label": "Lost"},
        {"value": "duplicate", "label": "Duplicate"},
        {"value": "archived", "label": "Archived"},
    ],
    "lead_tier": [
        {"value": "cold",      "label": "קר (Cold)"},
        {"value": "warm",      "label": "חם (Warm)"},
        {"value": "hot",       "label": "לוהט (Hot)"},
        {"value": "ultra_hot", "label": "רותח (Ultra Hot)"},
    ],
}

_DEFAULT_BLOCKERS = [
    "Lead Scoring not active",
    "Lead Memory not wired",
    "Followup automation not active",
    "WhatsApp outbound not active",
    "Receipt display needs frontend surface",
]


def _status_color(status: str) -> str:
    normalized = (status or "").upper()
    if normalized == "WORKING":
        return "green"
    if normalized == "BROKEN":
        return "red"
    return "yellow"


def _load_capability_map() -> tuple[dict, list[str]]:
    try:
        if not _CAPABILITY_MAP_PATH.exists():
            return {}, [f"capability_map missing: {_CAPABILITY_MAP_PATH}"]
        return json.loads(_CAPABILITY_MAP_PATH.read_text(encoding="utf-8")), []
    except Exception as e:
        logger.warning(f"[OwnerControlCenter] capability_map load failed: {e}")
        return {}, [f"capability_map load failed: {type(e).__name__}"]


def _owner_system_health(capability_map: dict) -> dict:
    summary = capability_map.get("summary") or {}
    if not summary:
        return dict(_DEFAULT_SYSTEM_HEALTH)
    return {
        "health_percent": summary.get("system_health_percent", 0),
        "working_count": summary.get("working_count", 0),
        "partial_count": summary.get("partial_count", 0),
        "broken_count": summary.get("broken_count", 0),
    }


def _owner_critical_systems(capability_map: dict) -> list[dict]:
    systems = capability_map.get("critical_systems") or []
    if not systems:
        return list(_DEFAULT_CRITICAL_SYSTEMS)

    wanted = {
        "Leads": "Leads",
        "Tasks": "Tasks",
        "Payments": "Payments",
        "ProjectsHub": "Projects",
        "Projects": "Projects",
        "Approvals": "Approvals",
    }
    by_display: dict[str, dict] = {}
    for item in systems:
        display_name = wanted.get(item.get("name", ""))
        if not display_name:
            continue
        status = item.get("status", "UNKNOWN")
        by_display[display_name] = {
            "name": display_name,
            "status": status,
            "color": _status_color(status),
            "owner": item.get("owner", ""),
            "next_blocker": item.get("next_blocker", ""),
        }

    return [by_display.get(item["name"], item) for item in _DEFAULT_CRITICAL_SYSTEMS]


def _owner_blockers_and_actions(capability_map: dict) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    for item in capability_map.get("critical_systems") or []:
        blocker = item.get("next_blocker", "")
        status = (item.get("status", "") or "").upper()
        if blocker and status != "WORKING":
            blockers.append(blocker)

    for capabilities in (capability_map.get("domains") or {}).values():
        for item in capabilities:
            blocker = item.get("next_blocker", "")
            status = (item.get("status", "") or "").upper()
            if blocker and status in {"PARTIAL", "STUB", "BROKEN"}:
                blockers.append(blocker)

    deduped = []
    for blocker in blockers:
        if blocker not in deduped:
            deduped.append(blocker)

    if not deduped:
        deduped = list(_DEFAULT_BLOCKERS)

    return deduped[:5], [
        "Activate Lead Scoring",
        "Wire Lead Memory after scoring",
        "Turn on Followup automation for HOT leads",
    ]


def _owner_approvals_snapshot(identity) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    pending: list[dict] = []
    executed: list[dict] = []

    try:
        pending_formula = f"{{{ApprovalsFields.STATUS}}}='\u05de\u05de\u05ea\u05d9\u05df'"
        pending = [_fmt_approval(r, identity) for r in _at_list("Approvals", pending_formula, max_records=50)]
    except Exception as e:
        logger.warning(f"[OwnerControlCenter] pending approvals read failed: {e}")
        warnings.append(f"pending approvals read failed: {type(e).__name__}")

    try:
        recs = _at_list("Approvals", "", max_records=25)
        for rec in recs:
            item = _fmt_approval(rec, identity)
            if item.get("status") != "\u05de\u05de\u05ea\u05d9\u05df":
                executed.append(item)
        executed.sort(key=lambda x: x.get("requested_at", ""), reverse=True)
    except Exception as e:
        logger.warning(f"[OwnerControlCenter] executed approvals read failed: {e}")
        warnings.append(f"executed approvals read failed: {type(e).__name__}")

    return {
        "pending_count": len(pending),
        "pending": pending[:10],
        "recent_executed": executed[:10],
    }, warnings


def _owner_recent_receipts() -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    receipts: list[dict] = []
    try:
        formula = f"SEARCH('[TMA receipt]', {{{InteractionLogFields.TITLE}}})"
        recs = _at_list(Tables.INTERACTION_LOG, formula, max_records=10)
        for rec in recs:
            f = rec.get("fields", {})
            summary = f.get(InteractionLogFields.SUMMARY, "")
            try:
                receipt_data = json.loads(summary) if summary else {}
            except (TypeError, ValueError):
                receipt_data = {}
            receipts.append({
                "id": rec.get("id", ""),
                "title": f.get(InteractionLogFields.TITLE, ""),
                "timestamp": f.get(InteractionLogFields.TIMESTAMP, receipt_data.get("timestamp", "")),
                "receipt": receipt_data,
            })
        receipts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    except Exception as e:
        logger.warning(f"[OwnerControlCenter] receipts read failed: {e}")
        warnings.append(f"receipts read failed: {type(e).__name__}")
    return receipts, warnings


_VENTURE_STAGES = (
    VentureStage.RESEARCH, VentureStage.SUPPLIER_SOURCE, VentureStage.DUE_DILIGENCE,
    VentureStage.LEGAL_TAX_REVIEW, VentureStage.SMOKE_TEST, VentureStage.GO,
    VentureStage.NO_GO, VentureStage.CONVERTED,
)


def _owner_strategic_pipeline() -> dict:
    """Strategic Layer — ventures לפי שלב (count by stage). מקור: טבלת Ventures, לא Deals."""
    try:
        records = _at_list(Tables.VENTURES, "", max_records=200)
        counts = {stage: 0 for stage in _VENTURE_STAGES}
        for r in records:
            stage = r.get("fields", {}).get(VentureFields.STAGE, "")
            if stage in counts:
                counts[stage] += 1
        active = sum(
            v for k, v in counts.items()
            if k not in (VentureStage.NO_GO, VentureStage.CONVERTED)
        )
        return {"stage_counts": counts, "total": len(records), "active": active}
    except Exception as e:
        logger.warning(f"[StrategicPipeline] {e}")
        return {"stage_counts": {}, "total": 0, "active": 0}


@tma_api.route("/api/owner/health", methods=["GET"])
@require_tma_auth
def owner_health(identity):
    if not identity.is_owner:
        return jsonify({"error": "owner only"}), 403
    health_status = get_health_status(scheduler=None, memory=None)
    return jsonify({
        "status":  health_status["status"],
        "version": "3.0",
        "router":  "CORE_02.6",
        "checks":  health_status["checks"],
    }), 200


@tma_api.route("/api/owner/control-center", methods=["GET"])
@require_tma_auth
def owner_control_center(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    warnings: list[str] = []
    capability_map, map_warnings = _load_capability_map()
    warnings.extend(map_warnings)

    approvals, approval_warnings = _owner_approvals_snapshot(identity)
    warnings.extend(approval_warnings)

    receipts, receipt_warnings = _owner_recent_receipts()
    warnings.extend(receipt_warnings)

    blockers, next_actions = _owner_blockers_and_actions(capability_map)

    return jsonify({
        "ok": True,
        "system_health": _owner_system_health(capability_map),
        "critical_systems": _owner_critical_systems(capability_map),
        "approvals": {
            **approvals,
            "recent_receipts": receipts,
        },
        "strategic_pipeline": _owner_strategic_pipeline(),
        "permissions": _PERMISSIONS_MATRIX,
        "business_language": _BUSINESS_LANGUAGE,
        "blockers": blockers,
        "next_actions": next_actions,
        "warnings": warnings,
    })


@tma_api.route("/api/approvals", methods=["GET"])
@require_tma_auth
def get_approvals(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    recs = _at_list("Approvals", "{סטטוס}='ממתין'", max_records=50)
    approvals = [_fmt_approval(r, identity) for r in recs]
    return jsonify({"count": len(approvals), "approvals": approvals})


@tma_api.route("/api/approvals/bulk", methods=["POST"])
@require_tma_auth
def bulk_approve(identity):
    """Approve ALL low-risk pending approvals. High/medium risk are NEVER bulk-approved.

    Phase 4B-2: routes each low-risk record through the same
    claim -> load-contract -> approve -> re-read helper used by the
    single-item approve path (_claim_and_execute_approval), so "approved"
    only means "canonical ActionContract executed". Rows with no
    action_contract_id / legacy_read_only=True are skipped, never
    bulk-actioned — see the Phase 4B-2 audit's legacy policy (§8).
    """
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    recs     = _at_list("Approvals", "{סטטוס}='ממתין'", max_records=100)
    approved = []
    failed   = []
    skipped  = []
    projection_sync_pending_ids: list[str] = []

    from core.action_gateway import action_gateway as _gw  # noqa: PLC0415

    for rec in recs:
        f = rec.get("fields", {})
        risk = (f.get(ApprovalsFields.RISK_LEVEL, "") or "").strip()
        contract_id = f.get(ApprovalsFields.ACTION_CONTRACT_ID, "")
        legacy_read_only = _derive_legacy_read_only(f)
        # Hard rules: NEVER bulk-approve high risk, NEVER bulk-approve a
        # legacy/no-contract row (not actionable — Phase 4B-2 audit §8).
        if risk.lower() not in _RISK_LOW or not contract_id or legacy_read_only:
            skipped.append(rec["id"])
            continue
        # Phase 4B-2 follow-up: same shared scope check used by the
        # single-item approve/reject helpers and the read model — a row
        # whose contract_id points at a pending contract that is not a
        # canonical TMA write-through-approval contract for this identity's
        # own tenant is skipped, never bulk-actioned.
        if not _is_canonical_tma_contract(_gw.find_contract(contract_id), identity):
            skipped.append(rec["id"])
            continue
        outcome = _claim_and_execute_approval(rec["id"], identity)
        if outcome.get("projection_sync_pending"):
            projection_sync_pending_ids.append(rec["id"])
        if outcome.get("ok"):
            approved.append(rec["id"])
        else:
            logger.warning("[bulk_approve] record %s failed: %s", rec["id"], outcome)
            failed.append(rec["id"])

    if approved or failed:
        _audit("bulk_approve", identity, details=f"{len(approved)} approved, {len(failed)} failed")
        _notify_owner(
            f"✅ TMA: {len(approved)} פעולות Low Risk אושרו ובוצעו\n"
            f"על ידי: {identity.display_name or identity.user_id}\n"
            f"נכשלו: {len(failed)} | דחויות (לא low-risk / legacy): {len(skipped)}"
        )

    response = {
        "ok": True,
        "approved": len(approved),
        "failed": len(failed),
        "skipped": len(skipped),
    }
    if projection_sync_pending_ids:
        # Canonical execution/rejection outcomes above are unaffected by a
        # display-sync failure — surface it as its own count/list so the
        # caller can trigger reconciliation, never conflated with "failed".
        response["projection_sync_pending"] = len(projection_sync_pending_ids)
        response["projection_sync_pending_ids"] = projection_sync_pending_ids
    return jsonify(response)


# Per-approval in-process locks — reduce concurrent double-claim within a
# single worker process. The genuine cross-process execution-ownership
# boundary is the PostgreSQL atomic claim inside
# ActionGateway._execute_contract() (Phase 4B-2) — this lock is a same-
# process race-window guard only, not the source of truth.
_APPROVAL_LOCKS: dict[str, threading.Lock] = {}
_APPROVAL_LOCKS_GUARD = threading.Lock()


def _get_approval_lock(approval_id: str) -> threading.Lock:
    with _APPROVAL_LOCKS_GUARD:
        if approval_id not in _APPROVAL_LOCKS:
            _APPROVAL_LOCKS[approval_id] = threading.Lock()
        return _APPROVAL_LOCKS[approval_id]


def _sync_approval_projection_status(approval_id: str, contract) -> bool:
    """After approve()/reject() re-reads the canonical ActionContract, mirror
    its status into the Approvals projection fields — display-only, never
    authoritative for claim/execution. Never touches CONTEXT_DATA. The
    legacy Hebrew STATUS field is kept in sync purely so the existing
    get_approvals()/bulk_approve() '{סטטוס}=ממתין' list-formula continues to
    drop resolved rows — it is not read back for any authority decision.

    Returns whether the sync write succeeded. The canonical contract's own
    lifecycle transition already happened inside approve()/reject() before
    this is ever called — a False return means the *display* is stale, not
    that the execution/rejection itself is in doubt. Callers must surface
    projection_sync_pending=True and leave reconciliation to a later pass
    rather than treating this as an execution failure."""
    from core.approvals_projection import project_lifecycle_status  # noqa: PLC0415

    projected = project_lifecycle_status(contract.status)
    legacy_status = {
        "draft":            ApprovalStatus.PENDING,
        "pending":          ApprovalStatus.PENDING,
        "approved":         ApprovalStatus.PROCESSING,
        "executing":        ApprovalStatus.PROCESSING,
        "outcome_unknown":  ApprovalStatus.PROCESSING,
        "completed":        ApprovalStatus.APPROVED,
        "executed":         ApprovalStatus.APPROVED,
        "failed":           ApprovalStatus.FAILED,
        "rejected":         ApprovalStatus.REJECTED,
        "superseded":       ApprovalStatus.REJECTED,
    }.get(contract.status, ApprovalStatus.PROCESSING)
    ok = _at_patch("Approvals", approval_id, {
        ApprovalsFields.PROJECTED_LIFECYCLE_STATUS: projected,
        ApprovalsFields.STATUS: legacy_status,
    })
    if not ok:
        logger.error(
            "_sync_approval_projection_status: projection sync failed for approval=%s "
            "contract=%s canonical_status=%s — canonical outcome is authoritative and "
            "unaffected; this row needs reconciliation to reflect it.",
            approval_id, contract.contract_id, contract.status,
        )
    return ok


def _load_actionable_projection(approval_id: str) -> tuple[dict | None, dict]:
    """Shared precondition for both approve and reject: fetch the Approvals
    row and refuse (Phase 4B-2 audit §8) unless it carries a live
    action_contract_id and is not legacy_read_only. Returns
    (fields_dict_or_None, refusal_outcome_dict). fields_dict is None iff a
    refusal_outcome was produced."""
    fresh = _at_get_record("Approvals", approval_id)
    if not fresh:
        return None, {"ok": False, "status_code": 404, "error": "approval not found"}
    f = fresh.get("fields", {})
    action_label = f.get(ApprovalsFields.ACTION, approval_id)
    ctx_id = f.get(ApprovalsFields.CONTEXT_ID, "")
    contract_id = f.get(ApprovalsFields.ACTION_CONTRACT_ID, "")
    legacy_read_only = _derive_legacy_read_only(f)
    if not contract_id or legacy_read_only:
        return None, {
            "ok": False, "status_code": 409,
            "error": "this approval predates ActionContracts and cannot be actioned — submit a new request",
            "action_label": action_label, "ctx_id": ctx_id,
        }
    return f, {}


# Phase 4B-2: shared claim -> load-canonical-contract -> approve -> re-read
# flow for a single Approvals projection row. Used by both act_on_approval()
# (single) and bulk_approve(). Approvals.CONTEXT_DATA is never read or
# deserialized here — the canonical, frozen payload lives only in
# ActionContracts, and execution is driven entirely by
# ActionGateway.approve() -> _execute_contract(), which acquires the
# PostgreSQL atomic claim before any dispatcher call. On return, only the
# projection fields (projected_lifecycle_status + legacy display STATUS) are
# updated — the canonical contract's own lifecycle write already happened
# inside approve() and is never re-derived from this projection.
def _claim_and_execute_approval(approval_id: str, identity) -> dict:
    """
    Returns a dict, always including "ok" (bool) and "status_code" (int):
      success: {"ok": True, "status_code": 200, "new_status": APPROVED,
                "action_label": ..., "ctx_id": ..., "bus_synced": bool,
                "execution_result": dict | None}
      failure: {"ok": False, "status_code": int, "error": str, "detail": ... (optional)}
    """
    import feature_flags  # noqa: PLC0415
    from core.action_gateway import action_gateway as _gw  # noqa: PLC0415
    import core.database as _db  # noqa: PLC0415

    lock = _get_approval_lock(approval_id)
    with lock:
        f, refusal = _load_actionable_projection(approval_id)
        if f is None:
            return refusal
        action_label = f.get(ApprovalsFields.ACTION, approval_id)
        ctx_id = f.get(ApprovalsFields.CONTEXT_ID, "")
        contract_id = f.get(ApprovalsFields.ACTION_CONTRACT_ID, "")

        # Phase 4B-2: re-verify both flags at execution time, not just at
        # propose time — do not fall back to RAM-only/direct dispatch if
        # either was disabled since the contract was proposed.
        durable_persistence_available = (
            feature_flags.is_enabled("FEATURE_ACTION_CONTRACT_PERSISTENCE")
            and getattr(_gw._ledger, "_repository", None) is not None
        )
        atomic_claims_available = (
            feature_flags.is_enabled("FEATURE_ATOMIC_CLAIMS")
            and _db.get_pool() is not None
        )
        if not (durable_persistence_available and atomic_claims_available):
            logger.error(
                "_claim_and_execute_approval: refusing contract=%s — durable_persistence=%s "
                "atomic_claims=%s", contract_id, durable_persistence_available, atomic_claims_available,
            )
            return {
                "ok": False, "status_code": 503,
                "error": "durable approval infrastructure is not fully online",
                "action_label": action_label, "ctx_id": ctx_id,
            }

        contract = _gw.find_contract(contract_id)
        if not contract:
            return {
                "ok": False, "status_code": 404,
                "error": "canonical ActionContract not found — orphaned projection row",
                "action_label": action_label, "ctx_id": ctx_id,
            }
        if not _is_canonical_tma_contract(contract, identity):
            logger.warning(
                "_claim_and_execute_approval: refusing — contract=%s is not a canonical "
                "pending TMA contract for this identity's tenant (status=%s tool_name=%s "
                "trusted_source=%s origin_channel=%s approval_policy=%s tenant_id=%s)",
                contract_id, contract.status, contract.tool_name,
                getattr(contract, "trusted_source", ""), contract.origin_channel,
                getattr(contract, "approval_policy", ""), contract.tenant_id,
            )
            return {
                "ok": False, "status_code": 409,
                "error": f"approval is not an actionable TMA contract (status={contract.status})",
                "action_label": action_label, "ctx_id": ctx_id,
            }

        # approve() is the sole enforcement boundary (BUG-074) and drives
        # dispatch through _execute_contract() — released here only after
        # approve() itself returns (execution already completed by then).
        message = _gw.approve(contract_id, approver=_identity_ref(identity), approver_role=identity.role)
    # Lock released — canonical status re-read below is authoritative
    # regardless of message text.

    updated = _gw.find_contract(contract_id)
    sync_ok = True
    if updated:
        sync_ok = _sync_approval_projection_status(approval_id, updated)
    final_status = updated.status if updated else "outcome_unknown"
    execution_result = {"message": message, "contract_status": final_status}

    # Phase 4B-2 follow-up: Approvals.CONTEXT_ID is projection/display data,
    # not a live event_bus action_id — it must never be used to confirm or
    # reject an event_bus action (a tampered/coincidentally-matching
    # CONTEXT_ID could otherwise resolve an unrelated pending action).
    # event_bus sync is not part of the ActionContract-backed flow.
    bus_synced = False

    if final_status in ("completed", "executed"):
        result = {
            "ok": True, "status_code": 200, "new_status": ApprovalStatus.APPROVED,
            "action_label": action_label, "ctx_id": ctx_id, "bus_synced": bus_synced,
            "execution_result": execution_result,
        }
        if not sync_ok:
            result["projection_sync_pending"] = True
        return result
    if final_status == "outcome_unknown":
        # Never collapsed into failed, never auto-retried (Phase 4B-2 audit §5).
        result = {
            "ok": False, "status_code": 202,
            "error": "execution outcome unknown — do not retry automatically",
            "action_label": action_label, "ctx_id": ctx_id, "detail": execution_result,
        }
        if not sync_ok:
            result["projection_sync_pending"] = True
        return result
    if message.startswith("⛔"):
        result = {
            "ok": False, "status_code": 403, "error": message,
            "action_label": action_label, "ctx_id": ctx_id,
        }
        if not sync_ok:
            result["projection_sync_pending"] = True
        return result
    result = {
        "ok": False, "status_code": 500,
        "error": f"approval execution failed: {message}",
        "action_label": action_label, "ctx_id": ctx_id, "detail": execution_result,
    }
    if not sync_ok:
        result["projection_sync_pending"] = True
    return result


# Phase 4B-2: reject-path mirror of _claim_and_execute_approval() — same
# load-canonical-contract precondition, drives rejection through
# ActionGateway.reject() instead of approve(), then re-reads canonical
# status and updates only the projection fields.
def _claim_and_reject_approval(approval_id: str, identity, note: str = "") -> dict:
    """
    Returns a dict shaped like _claim_and_execute_approval()'s contract:
      success: {"ok": True, "status_code": 200, "new_status": REJECTED,
                "action_label": ..., "ctx_id": ..., "bus_synced": bool}
      failure: {"ok": False, "status_code": int, "error": str}
    """
    from core.action_gateway import action_gateway as _gw  # noqa: PLC0415

    lock = _get_approval_lock(approval_id)
    with lock:
        f, refusal = _load_actionable_projection(approval_id)
        if f is None:
            return refusal
        action_label = f.get(ApprovalsFields.ACTION, approval_id)
        ctx_id = f.get(ApprovalsFields.CONTEXT_ID, "")
        contract_id = f.get(ApprovalsFields.ACTION_CONTRACT_ID, "")

        contract = _gw.find_contract(contract_id)
        if not contract:
            return {
                "ok": False, "status_code": 404,
                "error": "canonical ActionContract not found — orphaned projection row",
                "action_label": action_label, "ctx_id": ctx_id,
            }
        if not _is_canonical_tma_contract(contract, identity):
            logger.warning(
                "_claim_and_reject_approval: refusing — contract=%s is not a canonical "
                "pending TMA contract for this identity's tenant (status=%s tool_name=%s "
                "trusted_source=%s origin_channel=%s approval_policy=%s tenant_id=%s)",
                contract_id, contract.status, contract.tool_name,
                getattr(contract, "trusted_source", ""), contract.origin_channel,
                getattr(contract, "approval_policy", ""), contract.tenant_id,
            )
            return {
                "ok": False, "status_code": 409,
                "error": f"approval is not an actionable TMA contract (status={contract.status})",
                "action_label": action_label, "ctx_id": ctx_id,
            }

        message = _gw.reject(contract_id, rejected_by=_identity_ref(identity))

    updated = _gw.find_contract(contract_id)
    sync_ok = True
    if updated:
        sync_ok = _sync_approval_projection_status(approval_id, updated)
        if note:
            note_ok = _at_patch("Approvals", approval_id, {ApprovalsFields.REJECTION_NOTE: note})
            sync_ok = sync_ok and note_ok

    if not message.startswith("🚫"):
        return {
            "ok": False, "status_code": 500, "error": message,
            "action_label": action_label, "ctx_id": ctx_id,
        }

    # Phase 4B-2 follow-up: see _claim_and_execute_approval — CONTEXT_ID is
    # projection/display data, never a live event_bus action_id.
    bus_synced = False
    result = {
        "ok": True, "status_code": 200, "new_status": ApprovalStatus.REJECTED,
        "action_label": action_label, "ctx_id": ctx_id, "bus_synced": bus_synced,
    }
    if not sync_ok:
        result["projection_sync_pending"] = True
    return result


@tma_api.route("/api/approvals/<approval_id>", methods=["POST"])
@require_tma_auth
def act_on_approval(approval_id, identity):
    """Approve or reject a single pending approval.

    Phase 4B-2: both branches load the canonical ActionContract behind this
    Approvals projection row and drive the decision through
    ActionGateway.approve()/reject() — never patches Approvals.STATUS
    directly as if it were authoritative. Rows with no action_contract_id /
    legacy_read_only=True are refused by the shared helpers before either
    branch runs.
    """
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True) or {}
    decision = data.get("action", "").strip().lower()   # "approve" | "reject"
    note = data.get("note", "").strip()

    if decision not in ("approve", "reject"):
        return jsonify({"error": "action must be 'approve' or 'reject'"}), 400

    if decision == "reject":
        outcome = _claim_and_reject_approval(approval_id, identity, note=note)
        if not outcome["ok"]:
            body = {"error": outcome["error"]}
            if outcome.get("projection_sync_pending"):
                body["projection_sync_pending"] = True
            return jsonify(body), outcome["status_code"]
        _audit("approval_reject", identity, details=f"{outcome['action_label'][:100]} | note: {note[:80]}")
        _notify_owner(
            f"REJECTED TMA: נדחה - {outcome['action_label']}\n"
            f"approved_by: {identity.display_name or identity.user_id}"
            + (f"\nnote: {note}" if note else "")
        )
        response = {
            "ok": True, "approval_id": approval_id, "new_status": ApprovalStatus.REJECTED,
            "bus_synced": outcome["bus_synced"],
        }
        if outcome.get("projection_sync_pending"):
            response["projection_sync_pending"] = True
        return jsonify(response)

    # ── approve path — shared claim -> canonical-contract -> approve helper,
    # used by both this endpoint and bulk_approve() (Phase 4B-2). ──────────
    outcome = _claim_and_execute_approval(approval_id, identity)
    if not outcome["ok"]:
        body = {"error": outcome["error"]}
        if "detail" in outcome:
            body["detail"] = outcome["detail"]
        if outcome.get("projection_sync_pending"):
            body["projection_sync_pending"] = True
        return jsonify(body), outcome["status_code"]

    _audit("approval_approve", identity, details=f"{outcome['action_label'][:100]} | note: {note[:80]}")
    _notify_owner(
        f"OK TMA: אושר - {outcome['action_label']}\n"
        f"approved_by: {identity.display_name or identity.user_id}"
        + (f"\nnote: {note}" if note else "")
    )

    response = {"ok": True, "approval_id": approval_id, "new_status": ApprovalStatus.APPROVED}
    if outcome.get("execution_result") is not None:
        response.update(outcome["execution_result"])
    if outcome.get("projection_sync_pending"):
        response["projection_sync_pending"] = True
    return jsonify(response)


@tma_api.route("/api/activity", methods=["GET"])
@require_tma_auth
def activity_feed(identity):
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    limit = min(int(request.args.get("limit", 50) or 50), 100)

    entries = []
    # Business Memory = strategic manual events; no domain filter (table has no domain field).
    # ?domain= param reserved for future Interaction Log endpoint.
    business_recs = _at_list(Tables.BUSINESS_MEMORY, "", max_records=limit)
    for rec in business_recs:
        f    = rec.get("fields", {})
        tags = f.get(BusinessMemoryFields.TAGS) or []
        entries.append({
            "id":        rec["id"],
            "source":    "business_memory",
            "title":     f.get(BusinessMemoryFields.TITLE, ""),
            "summary":   f.get(BusinessMemoryFields.DESCRIPTION, ""),
            "channel":   f.get(BusinessMemoryFields.EVENT_TYPE, ""),
            "domain":    ", ".join(tags) if isinstance(tags, list) else str(tags),
            "timestamp": f.get(BusinessMemoryFields.DATE, ""),
            "sentiment": f.get(BusinessMemoryFields.IMPACT, "")[:120] if f.get(BusinessMemoryFields.IMPACT) else "",
        })

    receipt_formula = f"SEARCH('[TMA receipt]', {{{InteractionLogFields.TITLE}}})"
    receipt_recs = _at_list(Tables.INTERACTION_LOG, receipt_formula, max_records=limit)
    for rec in receipt_recs:
        f = rec.get("fields", {})
        summary = f.get(InteractionLogFields.SUMMARY, "")
        try:
            receipt_data = json.loads(summary) if summary else {}
        except (TypeError, ValueError):
            receipt_data = {}
        entries.append({
            "id":        rec["id"],
            "source":    "receipt",
            "title":     f.get(InteractionLogFields.TITLE, ""),
            "summary":   summary,
            "channel":   f.get(InteractionLogFields.CHANNEL, "receipt"),
            "domain":    receipt_data.get("table", ""),
            "timestamp": f.get(InteractionLogFields.TIMESTAMP, receipt_data.get("timestamp", "")),
            "sentiment": f.get(InteractionLogFields.KEY_INSIGHTS, ""),
            "receipt":   receipt_data,
        })

    entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify({"count": len(entries), "entries": entries})


# ── Assets (Personal Mode) ─────────────────────────────────────

def _can_assets(identity) -> bool:
    return identity.is_owner or "personal" in (identity.allowed_domains or [])


def _fmt_asset(rec: dict) -> dict:
    f = rec.get("fields", {})
    return {
        "id":               rec["id"],
        "name":             f.get("Name", ""),
        "type":             f.get("Asset Type", ""),
        "current_value":    float(f.get("Current Value", 0) or 0),
        "mortgage_balance": float(f.get("Mortgage Balance", 0) or 0),
        # Equity and My Equity are Airtable formula fields — read directly, never compute
        "equity":           float(f.get("Equity", 0) or 0),
        "ownership_pct":    float(f.get("Ownership %", 100) or 100),
        "my_equity":        float(f.get("My Equity", 0) or 0),
        "monthly_income":   float(f.get("Monthly Income", 0) or 0),
        "status":           f.get("Status", ""),
    }


@tma_api.route("/api/assets", methods=["GET"])
@require_tma_auth
def get_assets(identity):
    if not _can_assets(identity):
        return jsonify({"error": "forbidden"}), 403

    recs   = _at_list("Assets", "", max_records=100)
    assets = [_fmt_asset(r) for r in recs]

    return jsonify({
        "count":          len(assets),
        "total_value":    sum(a["current_value"]    for a in assets),
        "total_debt":     sum(a["mortgage_balance"] for a in assets),
        "total_equity":   sum(a["equity"]           for a in assets),
        "my_equity":      sum(a["my_equity"]        for a in assets),
        "monthly_income": sum(a["monthly_income"]   for a in assets),
        "assets":         assets,
    })


@tma_api.route("/api/assets/<asset_id>", methods=["GET"])
@require_tma_auth
def get_asset(asset_id, identity):
    if not _can_assets(identity):
        return jsonify({"error": "forbidden"}), 403

    rec = _at_get_record("Assets", asset_id)
    if not rec:
        return jsonify({"error": "asset not found"}), 404

    return jsonify(_fmt_asset(rec))


# Equity and My Equity are Airtable formula fields — never PATCH them
_ASSET_EDITABLE = {"Current Value", "Mortgage Balance", "Monthly Income", "Status", "Ownership %"}


@tma_api.route("/api/assets/<asset_id>", methods=["PATCH"])
@require_tma_auth
def update_asset(asset_id, identity):
    # CORE_04 Fix 2 — write access requires owner; personal-domain read access
    # (_can_assets) is not sufficient for mutating Assets.
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data   = request.get_json(force=True) or {}
    fields = {k: v for k, v in data.items() if k in _ASSET_EDITABLE}
    if not fields:
        return jsonify({"error": "no editable fields provided"}), 400

    ok = _at_patch("Assets", asset_id, fields)
    if not ok:
        return jsonify({"error": "update failed"}), 500

    _audit("asset_update", identity, details=f"{asset_id}: {list(fields.keys())}")
    return jsonify({"ok": True, "asset_id": asset_id, "updated": list(fields.keys())})


# ══════════════════════════════════════════════════════════════════
# Ventures — Strategic Layer (pre-lead/pre-deal evaluation). Owner only.
# ══════════════════════════════════════════════════════════════════

def _fmt_venture(r: dict) -> dict:
    f = r.get("fields", {})
    return {
        "id":                    r.get("id", ""),
        "name":                  f.get(VentureFields.NAME, ""),
        "stage":                 f.get(VentureFields.STAGE, ""),
        "domain":                f.get(VentureFields.DOMAIN, ""),
        "conviction":            f.get(VentureFields.CONVICTION, ""),
        "estimated_potential":   f.get(VentureFields.ESTIMATED_POTENTIAL, 0) or 0,
        "target_decision_date":  f.get(VentureFields.TARGET_DECISION_DATE, ""),
        "decision_log":          f.get(VentureFields.DECISION_LOG, ""),
        "next_action":           f.get(VentureFields.NEXT_ACTION, ""),
        "notes":                 f.get(VentureFields.NOTES, ""),
        "linked_contacts":       f.get(VentureFields.LINKED_CONTACTS, []) or [],
        "owner":                 f.get(VentureFields.OWNER, []) or [],
        "converted_to_deal":     f.get(VentureFields.CONVERTED_TO_DEAL, []) or [],
        "created_at":            f.get(VentureFields.CREATED_AT, ""),
    }


_VENTURE_FIELD_MAP = {
    "name":                 VentureFields.NAME,
    "stage":                VentureFields.STAGE,
    "domain":               VentureFields.DOMAIN,
    "conviction":           VentureFields.CONVICTION,
    "estimated_potential":  VentureFields.ESTIMATED_POTENTIAL,
    "target_decision_date": VentureFields.TARGET_DECISION_DATE,
    "decision_log":         VentureFields.DECISION_LOG,
    "next_action":          VentureFields.NEXT_ACTION,
    "notes":                VentureFields.NOTES,
    "linked_contacts":      VentureFields.LINKED_CONTACTS,
    "owner":                VentureFields.OWNER,
}


@tma_api.route("/api/ventures", methods=["GET"])
@require_tma_auth
def get_ventures(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    stage = (request.args.get("stage", "") or "").strip()
    formula = f"{{{VentureFields.STAGE}}}='{stage}'" if stage else ""
    recs = _at_list(Tables.VENTURES, formula, max_records=100)
    ventures = [_fmt_venture(r) for r in recs]
    return jsonify({"count": len(ventures), "ventures": ventures})


@tma_api.route("/api/ventures/<venture_id>", methods=["GET"])
@require_tma_auth
def get_venture(venture_id, identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    rec = _at_get_record(Tables.VENTURES, venture_id)
    if not rec:
        return jsonify({"error": "venture not found"}), 404
    return jsonify(_fmt_venture(rec))


@tma_api.route("/api/ventures", methods=["POST"])
@require_tma_auth
def create_venture(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "missing required field: name"}), 400

    fields = {_VENTURE_FIELD_MAP[k]: v for k, v in data.items() if k in _VENTURE_FIELD_MAP}
    fields.setdefault(VentureFields.STAGE, VentureStage.RESEARCH)

    rec = _at_post(Tables.VENTURES, fields)
    if not rec:
        return jsonify({"error": "create failed"}), 500

    _audit("venture_create", identity, details=name)
    return jsonify(_fmt_venture(rec)), 201


@tma_api.route("/api/ventures/<venture_id>", methods=["PATCH"])
@require_tma_auth
def update_venture(venture_id, identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True) or {}
    fields = {_VENTURE_FIELD_MAP[k]: v for k, v in data.items() if k in _VENTURE_FIELD_MAP}
    if not fields:
        return jsonify({"error": "no editable fields provided"}), 400

    ok = _at_patch(Tables.VENTURES, venture_id, fields)
    if not ok:
        return jsonify({"error": "update failed"}), 500

    _audit("venture_update", identity, details=f"{venture_id}: {list(fields.keys())}")
    return jsonify({"ok": True, "venture_id": venture_id, "updated": list(fields.keys())})


# ══════════════════════════════════════════════════════════════════
# WEEK 3 stubs — System Health + Emergency Stop
# ══════════════════════════════════════════════════════════════════

@tma_api.route("/api/health", methods=["GET"])
@require_tma_auth
def system_health(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    import httpx as _httpx
    import feature_flags as ff

    checks: dict[str, str] = {}

    # ── Airtable — real list call ──────────────────────────────────
    try:
        r = _httpx.get(
            f"https://api.airtable.com/v0/{_AT_BASE}/Leads",
            headers={"Authorization": f"Bearer {_AT_KEY}"},
            params={"maxRecords": 1},
            timeout=5,
        )
        checks["airtable"] = "ok" if r.status_code == 200 else f"error:{r.status_code}"
    except Exception as e:
        checks["airtable"] = f"error:{e}"

    # ── Telegram — getMe ──────────────────────────────────────────
    if _BOT_TOKEN:
        try:
            r = _httpx.get(
                f"https://api.telegram.org/bot{_BOT_TOKEN}/getMe",
                timeout=5,
            )
            if r.status_code == 200 and r.json().get("ok"):
                bot_username = r.json().get("result", {}).get("username", "?")
                checks["telegram"] = f"ok:@{bot_username}"
            else:
                checks["telegram"] = f"error:{r.status_code}"
        except Exception as e:
            checks["telegram"] = f"error:{e}"
    else:
        checks["telegram"] = "error:TELEGRAM_TOKEN not set"

    # ── Anthropic — key presence only (no paid API call) ──────────
    checks["anthropic"] = "ok" if os.environ.get("ANTHROPIC_API_KEY") else "error:key_missing"

    # ── Active emergency flags ─────────────────────────────────────
    emergency_flags = {
        flag: ff.is_enabled(flag)
        for flag in (
            "EMERGENCY_STOP_ALL",
            "EMERGENCY_STOP_WHATSAPP",
            "EMERGENCY_STOP_EMAIL",
            "EMERGENCY_STOP_AUTOMATION",
        )
    }
    active_emergencies = [k for k, v in emergency_flags.items() if v]

    all_ok = all(v.startswith("ok") for v in checks.values())
    status = "ok" if all_ok else "degraded"
    if active_emergencies:
        status = "emergency"

    return jsonify({
        "status":           status,
        "services":         checks,
        "emergency_flags":  emergency_flags,
        "active_emergency": active_emergencies,
        "checked_at":       date.today().isoformat(),
    })


@tma_api.route("/api/health/emergency", methods=["POST"])
@require_tma_auth
def emergency_stop(identity):
    """
    Emergency stop — sets a runtime feature flag in feature_flags.py.
    The bot checks these flags before executing guarded actions.
    NOTE: flags are in-process only — reset on Render dyno restart.
    For permanent stop, also disable the relevant env var / bot token.
    """
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data   = request.get_json(force=True) or {}
    action = data.get("action", "")
    valid  = {"stop_all", "stop_whatsapp", "stop_email", "stop_automation"}

    if action not in valid:
        return jsonify({"error": f"unknown action — must be one of {sorted(valid)}"}), 400

    import feature_flags as ff
    flag = f"EMERGENCY_{action.upper()}"
    try:
        ff.set_flag(flag, True)
    except Exception as e:
        logger.error(f"[Emergency] set_flag failed: {e}")
        return jsonify({"error": "failed to set emergency flag"}), 500

    _audit("emergency_stop", identity, details=action)

    action_labels = {
        "stop_all":        "🛑 STOP ALL — כל הפעולות האוטומטיות הופסקו",
        "stop_whatsapp":   "🛑 STOP WhatsApp — הודעות WhatsApp הופסקו",
        "stop_email":      "🛑 STOP Email — שליחת מיילים הופסקה",
        "stop_automation": "🛑 STOP Automation — אוטומציות הופסקו",
    }
    _notify_owner(
        f"🚨 EMERGENCY STOP\n"
        f"{action_labels.get(action, action)}\n"
        f"על ידי: {identity.display_name or identity.user_id}\n"
        f"Flag: {flag}=True\n"
        f"⚠️ לביטול: הפעל מחדש את השרת או אפס ידנית."
    )

    return jsonify({"ok": True, "action": action, "flag": flag})


# ══════════════════════════════════════════════════════════════════
# Game — Worlds / Quests / Coins
# ══════════════════════════════════════════════════════════════════

def _get_active_world_dict() -> dict | None:
    """
    Active World row → dict for API responses.
    Shared by game_status / game_today / game_checkin so World-lookup logic
    lives in exactly one place (BOSS_Refactor_Plan.md Stage 0 #2).

    Only one World should ever be Status=Active at a time. There is no
    write path in this codebase that sets World status (done manually in
    Airtable), so this can't be a hard constraint here — instead, if more
    than one Active World is found, it's logged loudly and the lowest
    Number is used deterministically rather than whichever Airtable
    happens to return first (Stage 0 #3).

    coins_earned is computed live from Coins_Log (sum of entries whose
    Quest belongs to this World's Quests), never read from the static
    Worlds.Coins_Earned field — Coins_Log is the single source of truth,
    so there's no write-through counter that can drift out of sync.
    """
    worlds = _at_list(Tables.WORLDS, f"{{{WorldsFields.STATUS}}}='{WorldStatus.ACTIVE}'", max_records=5)
    if not worlds:
        return None
    if len(worlds) > 1:
        names = [w.get("fields", {}).get(WorldsFields.NAME, w["id"]) for w in worlds]
        logger.error(f"[Worlds] {len(worlds)} worlds are Status=Active simultaneously: {names} — using lowest Number")
        worlds.sort(key=lambda w: int(w.get("fields", {}).get(WorldsFields.NUMBER, 0) or 0))

    w  = worlds[0]
    wf = w.get("fields", {})
    coins_target = int(wf.get(WorldsFields.TOTAL_COINS_TARGET, 0) or 0)

    quest_ids = set(_linked_record_ids(wf.get(WorldsFields.QUESTS, []) or []))
    coins_earned = 0
    if quest_ids:
        log_recs = _at_list(Tables.COINS_LOG, "", max_records=500)
        for log in log_recs:
            log_quest_ids = _linked_record_ids(log.get("fields", {}).get(CoinsLogFields.QUEST, []) or [])
            if quest_ids.intersection(log_quest_ids):
                coins_earned += int(log.get("fields", {}).get(CoinsLogFields.COINS, 0) or 0)

    pct = round(100 * coins_earned / coins_target, 1) if coins_target > 0 else 0.0
    return {
        "id":           w["id"],
        "name":         wf.get(WorldsFields.NAME, ""),
        "number":       int(wf.get(WorldsFields.NUMBER, 0) or 0),
        "boss":         wf.get(WorldsFields.BOSS, ""),
        "prize":        wf.get(WorldsFields.PRIZE, ""),
        "coins_earned": coins_earned,
        "coins_target": coins_target,
        "progress_pct": pct,
        "start_date":   wf.get(WorldsFields.START_DATE, ""),
    }


@tma_api.route("/api/game/status", methods=["GET"])
@require_tma_auth
def game_status(identity):
    """Active world + this week's quests + total coins. Owner only."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    week_start_str = monday.isoformat()

    active_world = _get_active_world_dict()

    # ── This week's quests (filter in Python for date-field reliability) ──
    all_quests = _at_list(Tables.QUESTS, "", max_records=200)
    quests_this_week = [
        r for r in all_quests
        if (r.get("fields", {}).get(QuestsFields.WEEK_START, "") or "")[:10] == week_start_str
    ]
    if not quests_this_week:
        quests_this_week = [
            r for r in all_quests
            if r.get("fields", {}).get(QuestsFields.STATUS, "") in {QuestStatus.TODO, QuestStatus.IN_PROGRESS}
        ]

    quest_list = []
    for r in quests_this_week:
        qf = r.get("fields", {})
        quest_list.append({
            "id":     r["id"],
            "name":   qf.get(QuestsFields.NAME, ""),
            "status": qf.get(QuestsFields.STATUS, ""),
            "coins":  int(qf.get(QuestsFields.COINS, 0) or 0),
            "impact": bool(qf.get(QuestsFields.IMPACT, False)),
        })

    # ── Total coins from Coins_Log ─────────────────────────────────
    log_recs    = _at_list(Tables.COINS_LOG, "", max_records=500)
    total_coins = sum(int(r.get("fields", {}).get(CoinsLogFields.COINS, 0) or 0) for r in log_recs)

    return jsonify({
        "active_world":     active_world,
        "quests_this_week": quest_list,
        "total_coins":      total_coins,
        "week_start":       week_start_str,
    })


_QUEST_VALID_STATUSES = {QuestStatus.TODO, QuestStatus.IN_PROGRESS, QuestStatus.DONE, QuestStatus.SKIPPED}


@tma_api.route("/api/game/quests/<quest_id>", methods=["PATCH"])
@require_tma_auth
def update_quest(quest_id, identity):
    """Update quest status. Completing a quest auto-writes a Coins_Log entry. Owner only."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data       = request.get_json(force=True) or {}
    new_status = data.get("status", "").strip()
    if new_status not in _QUEST_VALID_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(_QUEST_VALID_STATUSES)}"}), 400

    rec = _at_get_record(Tables.QUESTS, quest_id)
    if not rec:
        return jsonify({"error": "quest not found"}), 404

    qf         = rec.get("fields", {})
    old_status = qf.get(QuestsFields.STATUS, "")
    quest_name = qf.get(QuestsFields.NAME, quest_id)

    patch_fields: dict = {QuestsFields.STATUS: new_status}
    if new_status == QuestStatus.DONE:
        patch_fields[QuestsFields.DONE_BY] = identity.display_name or identity.user_id

    # Auto-write Coins_Log before the status patch, only on first completion —
    # so a log failure doesn't leave a quest marked done with no coins recorded.
    coins_awarded = 0
    if new_status == QuestStatus.DONE and old_status != QuestStatus.DONE:
        coins = int(qf.get(QuestsFields.COINS, 0) or 0)
        if coins > 0:
            log_ok = _at_post(Tables.COINS_LOG, {
                CoinsLogFields.ACTION:        "Quest Completed",
                CoinsLogFields.COINS:         coins,
                CoinsLogFields.DATE:          date.today().isoformat(),
                CoinsLogFields.QUEST:         [quest_id],
                CoinsLogFields.NOTE:          f"Quest completed via TMA: {quest_name}",
            })
            if not log_ok:
                return jsonify({"error": "coins log failed — quest not marked done"}), 500
            coins_awarded = coins

    ok = _at_patch(Tables.QUESTS, quest_id, patch_fields)
    if not ok:
        if coins_awarded:
            logger.warning(f"[Coins] quest {quest_id} coins logged but status patch failed")
            return jsonify({"ok": True, "coins_awarded": coins_awarded, "warning": "status not updated"})
        return jsonify({"error": "update failed"}), 500

    _audit(
        "quest_done" if new_status == QuestStatus.DONE else "quest_update",
        identity,
        details=f"{quest_name} → {new_status}",
    )
    return jsonify({"ok": True, "quest_id": quest_id, "status": new_status, "coins_awarded": coins_awarded})


# ══════════════════════════════════════════════════════════════════
# Game — Daily Tasks screen
# ══════════════════════════════════════════════════════════════════

_ROADMAP_COMPLETE_STATUSES = {RoadmapTaskStatus.DONE, "Completed"}


def _is_roadmap_complete(status) -> bool:
    return _clean_select_value(status) in _ROADMAP_COMPLETE_STATUSES


def _map_rt_status(status) -> str:
    clean_status = _clean_select_value(status)
    if clean_status in _ROADMAP_COMPLETE_STATUSES:
        return "Done"
    if clean_status == RoadmapTaskStatus.BLOCKED:
        return "Skipped"
    return "Todo"


@tma_api.route("/api/game/today", methods=["GET"])
@require_tma_auth
def game_today(identity):
    """Today's Roadmap_Tasks (filtered by owner + due date) + active world + total coins. Owner only."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    today_str  = date.today().isoformat()
    owner_name = (identity.display_name or "").strip().lower()

    all_rt = _at_list(Tables.ROADMAP_TASKS, "", max_records=200)

    def _due_today_or_earlier(r: dict) -> bool:
        f   = r.get("fields", {})
        due = (f.get(RoadmapTaskFields.DUE_DATE, "") or "")[:10]
        return not due or due <= today_str

    def _owner_matches(r: dict) -> bool:
        if not owner_name:
            return True
        owner = (r.get("fields", {}).get(RoadmapTaskFields.OWNER, "") or "").lower()
        return owner_name in owner or owner in owner_name

    tasks = []
    for r in all_rt:
        f = r.get("fields", {})
        status = f.get(RoadmapTaskFields.STATUS, RoadmapTaskStatus.TODO)
        if _is_roadmap_complete(status):
            continue  # בוצע — לא מציג בכרטיסיה היומית
        task_name = str(f.get(RoadmapTaskFields.TASK, "") or "").strip()
        if not task_name:
            continue
        if not _owner_matches(r):
            continue
        if not _due_today_or_earlier(r):
            continue
        tasks.append({
            "id":     r["id"],
            "task":   task_name,
            "coins":  int(f.get(RoadmapTaskFields.COINS, 0) or 0),
            "status": _map_rt_status(status),
            "who":    f.get(RoadmapTaskFields.OWNER, ""),
        })

    # ── Active World ─────────────────────────────────────────────
    active_world = _get_active_world_dict()

    # ── Total Coins ───────────────────────────────────────────────
    log_recs    = _at_list(Tables.COINS_LOG, "", max_records=500)
    total_coins = sum(int(r.get("fields", {}).get(CoinsLogFields.COINS, 0) or 0) for r in log_recs)

    return jsonify({
        "today":       today_str,
        "tasks":       tasks,
        "world":       active_world,
        "total_coins": total_coins,
    })


@tma_api.route("/api/game/tasks/<task_id>/done", methods=["PATCH"])
@require_tma_auth
def complete_daily_task(task_id, identity):
    """Mark a Roadmap_Task as Done and auto-write a Coins_Log entry. Owner only."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    rec = _at_get_record(Tables.ROADMAP_TASKS, task_id)
    if not rec:
        return jsonify({"error": "task not found"}), 404

    f          = rec.get("fields", {})
    old_status = _clean_select_value(f.get(RoadmapTaskFields.STATUS, ""))
    task_name  = f.get(RoadmapTaskFields.TASK, task_id)

    if _is_roadmap_complete(old_status):
        return jsonify({"ok": True, "coins_awarded": 0, "already_done": True})

    coins = int(f.get(RoadmapTaskFields.COINS, 0) or 0)
    coins_awarded = 0
    if coins > 0:
        quest_ids = _linked_record_ids(f.get(RoadmapTaskFields.QUEST, []) or [])
        log_fields: dict = {
            CoinsLogFields.ACTION:        "Task Completed",
            CoinsLogFields.COINS:         coins,
            CoinsLogFields.DATE:          date.today().isoformat(),
            CoinsLogFields.NOTE:          f"Roadmap task completed via TMA: {task_name}",
        }
        if quest_ids:
            log_fields[CoinsLogFields.QUEST] = quest_ids
        log_ok = _at_post(Tables.COINS_LOG, log_fields)
        if not log_ok:
            return jsonify({"error": "coins log failed — task not marked done"}), 500
        coins_awarded = coins

    ok = _at_patch(Tables.ROADMAP_TASKS, task_id, {RoadmapTaskFields.STATUS: RoadmapTaskStatus.DONE})
    if not ok:
        logger.warning(f"[Coins] task {task_id} coins logged but DONE patch failed")
        return jsonify({"ok": True, "coins_awarded": coins_awarded, "warning": "status not updated"})

    _audit("roadmap_task_done", identity, details=f"{task_name} +{coins}🪙")
    return jsonify({"ok": True, "coins_awarded": coins_awarded})


@tma_api.route("/api/game/checkin/tasks/<task_id>", methods=["PATCH"])
@require_tma_auth
def update_checkin_task_status(task_id, identity):
    """שמירת Status לרשומת Roadmap_Task מתוך BossCheckin. Owner בלבד."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True) or {}
    new_status = _clean_select_value(data.get("status", ""))
    if not new_status:
        return jsonify({"error": "missing field: status"}), 400

    valid_statuses = {
        RoadmapTaskStatus.TODO,
        RoadmapTaskStatus.IN_PROGRESS,
        RoadmapTaskStatus.DONE,
        RoadmapTaskStatus.BLOCKED,
    }
    if new_status not in valid_statuses:
        return jsonify({"error": "invalid status", "valid": sorted(valid_statuses)}), 400

    rec = _at_get_record(Tables.ROADMAP_TASKS, task_id)
    if not rec:
        return jsonify({"error": "task not found"}), 404

    ok = _at_patch(Tables.ROADMAP_TASKS, task_id, {RoadmapTaskFields.STATUS: new_status})
    if not ok:
        return jsonify({"error": "update failed"}), 500

    _audit("roadmap_task_status_update", identity, details=f"{task_id} -> {new_status}")
    return jsonify({"ok": True, "task_id": task_id, "status": new_status})


# ══════════════════════════════════════════════════════════════════
# Game — Daily Check-in (freeform 3-things ritual, separate from
# Roadmap_Tasks — see BOSS_Refactor_Plan.md Stage 0 #4)
# ══════════════════════════════════════════════════════════════════

def _get_checkin_record(date_str: str) -> dict | None:
    """One Daily_Checkin record per calendar day — find today's, or None."""
    recs = _at_list(Tables.DAILY_CHECKIN, f"{{{DailyCheckinFields.DATE}}}='{date_str}'", max_records=1)
    return recs[0] if recs else None


@tma_api.route("/api/game/checkin", methods=["GET"])
@require_tma_auth
def game_checkin_get(identity):
    """Today's Daily_Checkin record (if any) + active world. Owner only."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    today_str = date.today().isoformat()
    rec = _get_checkin_record(today_str)
    cf  = rec.get("fields", {}) if rec else {}

    try:
        tasks = json.loads(cf.get(DailyCheckinFields.TASKS_JSON, "") or "[]")
    except (TypeError, ValueError):
        tasks = []

    return jsonify({
        "date":        today_str,
        "tasks":       tasks,
        "total_xp":    int(cf.get(DailyCheckinFields.TOTAL_XP, 0) or 0),
        "updated_at":  cf.get(DailyCheckinFields.UPDATED_AT, ""),
        "updated_by":  cf.get(DailyCheckinFields.UPDATED_BY, ""),
        "world":       _get_active_world_dict(),
    })


@tma_api.route("/api/game/checkin", methods=["PUT"])
@require_tma_auth
def game_checkin_put(identity):
    """
    Upsert today's Daily_Checkin record — write-through immediately on every
    change (no local-only/persisted distinction; BOSS_Refactor_Plan.md Stage
    0 #4 decision: immediate write, not a flag). One record per day — edits
    PATCH the same record in place, never delete+recreate.
    """
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data  = request.get_json(force=True) or {}
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return jsonify({"error": "tasks must be a list"}), 400

    today_str  = date.today().isoformat()
    total_xp   = sum(int(t.get("xp", 0) or 0) for t in tasks if isinstance(t, dict) and t.get("status") == "done")
    actor      = identity.display_name or identity.user_id
    now_iso    = datetime.now(timezone.utc).isoformat()

    fields = {
        DailyCheckinFields.TASKS_JSON: json.dumps(tasks, ensure_ascii=False),
        DailyCheckinFields.TOTAL_XP:   total_xp,
        DailyCheckinFields.UPDATED_AT: now_iso,
        DailyCheckinFields.UPDATED_BY: actor,
    }

    existing = _get_checkin_record(today_str)
    if existing:
        ok = _at_patch(Tables.DAILY_CHECKIN, existing["id"], fields)
        if not ok:
            return jsonify({"error": "update failed"}), 500
        record_id = existing["id"]
    else:
        rec = _at_post(Tables.DAILY_CHECKIN, {
            DailyCheckinFields.DATE:  today_str,
            DailyCheckinFields.OWNER: actor,
            **fields,
        })
        if not rec:
            return jsonify({"error": "create failed"}), 500
        record_id = rec["id"]

    _audit("daily_checkin_save", identity, details=f"{today_str} total_xp={total_xp}")
    return jsonify({
        "ok":          True,
        "record_id":   record_id,
        "date":        today_str,
        "total_xp":    total_xp,
        "updated_at":  now_iso,
        "updated_by":  actor,
    })


# ══════════════════════════════════════════════════════════════════
# F16 — Media Layer: TMA file upload
# ══════════════════════════════════════════════════════════════════

@tma_api.route("/api/tma/upload", methods=["POST"])
@require_tma_auth
def tma_upload(identity):
    """Photo/document upload from the TMA — Drive storage + Media Files metadata."""
    import feature_flags as ff

    if not ff.is_enabled("FEATURE_MEDIA_UPLOAD"):
        return jsonify({"coming_soon": True, "message": "Media upload not yet enabled"}), 200

    # BUG-075: every other TMA write endpoint gates on role — this one only
    # had @require_tma_auth (authentication, not authorization). Any resolved
    # identity (including lead/guest/readonly) could otherwise upload once
    # the flag above is enabled.
    if identity.role not in {Role.OWNER, Role.MANAGER, Role.PARTNER}:
        return jsonify({"error": "forbidden"}), 403

    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error": "missing 'file' in multipart form data"}), 400

    file_bytes = uploaded.read()
    if not file_bytes:
        return jsonify({"error": "empty file"}), 400

    # domain is always taken from the authenticated identity, never from the
    # client-supplied form field — tenant scope must not be client-controlled.
    linked_lead_id = request.form.get("linked_lead_id", "")

    from media_handler import handle_tma_upload

    result = handle_tma_upload(
        file_bytes=file_bytes,
        filename=uploaded.filename or "upload",
        mime_type=uploaded.mimetype or "application/octet-stream",
        user_id=identity.user_id,
        domain=identity.domain_id,
        linked_lead_id=linked_lead_id,
    )

    if not result.ok:
        return jsonify({"ok": False, "error": result.error.error_message}), 400

    return jsonify({
        "ok":         True,
        "asset_id":   result.asset_id,
        "drive_url":  result.drive_url,
        "file_size_tier": result.file_size_tier,
    })

