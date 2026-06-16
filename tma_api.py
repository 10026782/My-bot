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
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Blueprint, jsonify, request
from identity import resolve_identity, Role
from airtable_schema import (
    LeadFields, TaskFields, PaymentStatus, BusinessMemoryFields, InteractionLogFields, Tables,
    DealFields, DealStatus,
    QuestsFields, CoinsLogFields, WorldsFields, QuestStatus, WorldStatus,
    DailyTaskFields, DailyTaskStatus, ApprovalsFields, ApprovalStatus,
    RoadmapTaskFields, RoadmapTaskStatus,
)
from tools.airtable_gateway import airtable_patch as _gw_patch, airtable_create as _gw_create
from health_monitor import get_health_status

logger = logging.getLogger(__name__)

tma_api = Blueprint("tma_api", __name__)

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
            "Content-Type, X-Telegram-Init-Data, Authorization"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
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
def _preflight():
    return "", 204


@tma_api.route("/api/approvals/<approval_id>", methods=["OPTIONS"])
def _preflight_approval(_approval_id=None):
    return "", 204


@tma_api.route("/api/assets", methods=["OPTIONS"])
def _preflight_assets():
    return "", 204


@tma_api.route("/api/assets/<asset_id>", methods=["OPTIONS"])
def _preflight_asset(_asset_id=None):
    return "", 204


@tma_api.route("/api/game/status", methods=["OPTIONS"])
def _preflight_game_status():
    return "", 204


@tma_api.route("/api/game/quests/<quest_id>", methods=["OPTIONS"])
def _preflight_game_quest(_quest_id=None):
    return "", 204


@tma_api.route("/api/game/today", methods=["OPTIONS"])
def _preflight_game_today():
    return "", 204


@tma_api.route("/api/game/tasks/<task_id>/done", methods=["OPTIONS"])
def _preflight_game_task_done(_task_id=None):
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


def _at_patch(table: str, record_id: str, fields: dict) -> bool:
    """PATCH single record via gateway (normalize → validate → audit → httpx)."""
    return _gw_patch(table, record_id, fields, source="tma")


def _at_post(table: str, fields: dict) -> dict | None:
    """POST new record via gateway → created record dict or None."""
    return _gw_create(table, fields, source="tma")


def _coins_running_total(new_coins: int) -> int:
    """
    Application-side running total for Coins_Log.Total_Running.
    Total_Running must be a Number field (not a Formula) — Airtable formulas
    cannot reliably compute a running total across records, so we compute it
    here: sum of all existing Coins_Log.Coins + the coins being awarded now.
    """
    log_recs = _at_list(Tables.COINS_LOG, "", max_records=1000)
    existing_total = sum(int(r.get("fields", {}).get(CoinsLogFields.COINS, 0) or 0) for r in log_recs)
    return existing_total + new_coins


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


def _try_bus_action(context_id: str, decision: str) -> None:
    """Try to confirm/reject a matching in-memory event_bus pending action. Silent on miss."""
    if not context_id:
        return
    try:
        from event_bus import bus  # noqa: PLC0415
        if decision == "approve":
            bus.confirm(context_id)
        else:
            bus.reject(context_id)
    except Exception as e:
        logger.debug(f"[event_bus] no matching action for {context_id}: {e}")


# ══════════════════════════════════════════════════════════════════
# Stateless Telegram initData validation
# https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
# ══════════════════════════════════════════════════════════════════

def _identity_ref(identity) -> str:
    return str(getattr(identity, "user_id", "") or getattr(identity, "display_name", "") or "unknown")


def _queue_tma_write_approval(action: str, payload: dict, identity, label: str) -> tuple[str, dict]:
    approval_payload = {
        "type": "tma_write",
        "action": action,
        "requested_by": _identity_ref(identity),
        **payload,
    }
    rec = _at_post("Approvals", {
        ApprovalsFields.ACTION: label,
        ApprovalsFields.REQUESTED_BY: _identity_ref(identity),
        ApprovalsFields.REQUESTED_AT: datetime.now(timezone.utc).isoformat(),
        ApprovalsFields.RISK_LEVEL: "high",
        ApprovalsFields.CONTEXT_TYPE: "tma_write",
        ApprovalsFields.CONTEXT_ID: action,
        ApprovalsFields.CONTEXT_DATA: json.dumps(approval_payload, ensure_ascii=False),
        ApprovalsFields.STATUS: ApprovalStatus.PENDING,
    })
    if not rec:
        logger.error(f"_queue_tma_write_approval: Approvals POST failed for action={action}")
        raise RuntimeError(f"approval_queue_failed: {action}")
    approval_id = rec["id"]
    return approval_id, {
        "status": "pending_approval",
        "approval_id": approval_id,
        "message": "Approval required",
    }


def _receipt(action: str, table: str, record_id: str, requested_by: str, approved_by: str) -> dict:
    return {
        "action": action,
        "table": table,
        "record_id": record_id,
        "requested_by": requested_by,
        "approved_by": approved_by,
        "status": "executed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _persist_receipt(receipt: dict) -> str | None:
    """Persist approval execution receipt to Interaction Log; never rolls back writes."""
    try:
        rec = _at_post(Tables.INTERACTION_LOG, {
            InteractionLogFields.TITLE: f"[TMA receipt] {receipt.get('action', '')}",
            InteractionLogFields.SUMMARY: json.dumps(receipt, ensure_ascii=False),
            InteractionLogFields.TIMESTAMP: receipt.get("timestamp", ""),
            InteractionLogFields.PARTICIPANTS: receipt.get("approved_by", ""),
            InteractionLogFields.KEY_INSIGHTS: (
                f"{receipt.get('status', '')} {receipt.get('table', '')}/{receipt.get('record_id', '')}"
            ).strip(),
        })
        if rec:
            return None
        warning = "receipt persistence failed: Interaction Log write returned no record"
        logger.warning(f"[Receipt] {warning}")
        return warning
    except Exception as e:
        warning = f"receipt persistence failed: {type(e).__name__}"
        logger.warning(f"[Receipt] {warning}: {e}")
        return warning


def _clean_fields_select_values(table: str, fields: dict) -> dict:
    """Unwrap embedded quotes from select field values before writing to Airtable."""
    if table not in ("Leads",):
        return fields
    cleaned = dict(fields)
    for k in _LEAD_SELECT_FIELDS:
        if k in cleaned:
            cleaned[k] = _clean_select_value(cleaned[k])
    return cleaned


# Allowlist of tables that TMA write-through-approval is permitted to touch.
_TMA_WRITE_ALLOWED_TABLES = {
    "Leads",
    "משימות (Tasks)", "Tasks",
    "ProjectsHub",
    "Approvals",
    "אנשי קשר (Contacts)", "Contacts",
}


def _execute_tma_write(payload: dict, approved_by_identity) -> dict:
    action = payload.get("action", "")
    table = payload.get("table", "")
    requested_by = payload.get("requested_by", "unknown")
    approved_by = _identity_ref(approved_by_identity)

    if table not in _TMA_WRITE_ALLOWED_TABLES:
        logger.error(f"_execute_tma_write: table '{table}' not in allowlist — rejected")
        return {"ok": False, "error": f"table '{table}' is not permitted for TMA writes"}

    if payload.get("op") == "post":
        rec = _at_post(table, payload.get("fields", {}))
        if not rec:
            return {"ok": False, "error": f"failed to create record in {table}"}
        record_id = rec.get("id", "")
    elif payload.get("op") == "patch":
        record_id = payload.get("record_id", "")
        fields = _clean_fields_select_values(table, payload.get("fields", {}))
        ok = _at_patch(table, record_id, fields)
        if not ok:
            return {"ok": False, "error": f"failed to update record in {table}", "record_id": record_id}
    else:
        return {"ok": False, "error": "unsupported TMA write operation"}

    _audit(payload.get("audit_action", action), approved_by_identity, details=payload.get("audit_details", ""))
    receipt = _receipt(action, table, record_id, requested_by, approved_by)
    receipt_warning = _persist_receipt(receipt)
    result = {
        "ok": True,
        "action": "approve",
        "receipt": receipt,
    }
    if receipt_warning:
        result["warning"] = receipt_warning
    return result


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


def _log_projects_auth_debug(stage: str) -> None:
    """Temporary safe auth diagnostics for /api/projects only."""
    if request.path != "/api/projects":
        return

    logger.info(
        "[TMA auth debug] path=/api/projects stage=%s "
        "has_x_telegram_init_data=%s has_origin=%s",
        stage,
        bool(request.headers.get("X-Telegram-Init-Data", "").strip()),
        bool(request.headers.get("Origin", "").strip()),
    )


def require_tma_auth(f):
    """
    Decorator: reads X-Telegram-Init-Data header, validates HMAC on every request.
    Injects keyword arg `identity` into the wrapped handler.
    HMAC validation is always required — there is no dev bypass.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        _log_projects_auth_debug("start")
        _log_projects_auth_debug("telegram_branch")
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        if not init_data:
            _log_projects_auth_debug("401_prod_missing_x_telegram_init_data")
            return jsonify({"error": "missing X-Telegram-Init-Data header"}), 401

        user_data = _validate_initdata(init_data)
        if not user_data:
            _log_projects_auth_debug("401_prod_invalid_or_expired_initdata")
            return jsonify({"error": "invalid or expired initData"}), 401

        telegram_id = str(user_data.get("id", ""))
        identity = resolve_identity("telegram", telegram_id)
        _log_projects_auth_debug("telegram_success")
        return f(*args, identity=identity, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════
# O0 aggregation helpers — same source as daily_digest.py
# ══════════════════════════════════════════════════════════════════

def _get_global_kpis() -> dict:
    """
    Aggregates KPIs for Projects Hub.
    Uses the same Airtable queries as daily_digest.py so O0 and the
    morning Telegram digest always reflect identical data.
    """
    today       = date.today()
    month_start = today.replace(day=1).isoformat()
    week_ahead  = (today + timedelta(days=7)).isoformat()
    tomorrow    = (today + timedelta(days=1)).isoformat()

    # Income this month — received payments
    received = _at_list(
        "תשלומים (Payments)",
        f"AND({{סטטוס}}='התקבל', IS_AFTER({{תאריך}}, '{month_start}'))",
        max_records=200,
    )
    income = sum(
        r.get("fields", {}).get("סכום", 0) or 0
        for r in received
        if isinstance(r.get("fields", {}).get("סכום"), (int, float))
    )

    # Pending payments in next 7 days (same formula as _upcoming_payments)
    pending_recs = _at_list(
        "תשלומים (Payments)",
        (
            f"AND({{סטטוס}}!='התקבל', "
            f"IS_BEFORE({{תאריך}}, '{week_ahead}'), "
            f"IS_AFTER({{תאריך}}, '{today.isoformat()}'))"
        ),
        max_records=50,
    )
    pending_amount = sum(
        r.get("fields", {}).get("סכום", 0) or 0
        for r in pending_recs
        if isinstance(r.get("fields", {}).get("סכום"), (int, float))
    )

    # Overdue tasks (same filter as _urgent_tasks)
    overdue = _at_list(
        "משימות (Tasks)",
        f"AND(IS_BEFORE({{תאריך יעד}}, '{tomorrow}'), {{סטטוס}}!='בוצע')",
        max_records=50,
    )

    hot_leads = _at_list(
        "Leads",
        f"{{{LeadFields.SCORE}}}>=70",  # tier הוא formula — מסנן לפי ציון בלבד
        max_records=20,
    )

    return {
        "income_this_month":      income,
        "pending_payments_count": len(pending_recs),
        "pending_payments_amount": pending_amount,
        "overdue_tasks":          len(overdue),
        "hot_leads_count":        len(hot_leads),
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


def _get_project_cards(identity) -> list:
    """
    Returns project status cards from ProjectsHub table.
    Fields: Name, emoji, slug, mode, project_type, status,
            kpi_fields, quick_actions, owner_ids, tenant_id, domain.
    slug and domain are independent — domain drives lead filtering.
    Returns [] if the table is empty or does not exist yet.
    """
    records = _at_list("ProjectsHub", "", max_records=20)
    if not records:
        return []

    cards = []
    for r in records:
        f      = r.get("fields", {})
        slug   = f.get("slug", "")
        domain = f.get("domain", "")

        # Non-owners: filter to projects where their user_id appears in owner_ids
        if not identity.is_owner:
            if identity.user_id not in str(f.get("owner_ids", "") or ""):
                continue

        # Live KPI: same query as get_project_dashboard leads_count.
        # Status filtering done in Python (case-insensitive) to avoid Airtable formula issues.
        _CLOSED = {"closed", "lost", "won", "cancelled", "done",
                   "completed", "הושלם", "נסגר", "בוטל"}
        if domain:
            all_leads = _at_list("Leads", f"{{domain}}='{domain}'", max_records=50)
            leads = [
                l for l in all_leads
                if (l.get("fields", {}).get("status") or "").lower() not in _CLOSED
            ]
            hot = [
                l for l in leads
                if (l.get("fields", {}).get(LeadFields.SCORE) or 0) >= 70
                or (l.get("fields", {}).get("status") or "").lower() == "hot"
            ]
        else:
            leads, hot = [], []

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
    return cards


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

    kpis     = _get_global_kpis()
    projects = _get_project_cards(identity)

    exceptions = []
    if kpis["overdue_tasks"] > 0:
        exceptions.append(f"⚡ {kpis['overdue_tasks']} משימות עבר מועד")
    if kpis["pending_payments_count"] > 0:
        exceptions.append(f"💰 {kpis['pending_payments_count']} תשלומים קרובים")
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
    _, response = _queue_tma_write_approval(
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
    return jsonify(response), 202


@tma_api.route("/api/projects/<project_slug>/dashboard", methods=["GET"])
@require_tma_auth
def get_project_dashboard(project_slug, identity):
    """
    Project Dashboard — owner + partner with domain access.
    project_slug is the slug field value (e.g. 'blueview', 'boss-saas').
    Looks up the ProjectsHub record to get the canonical domain for filtering.
    """
    # Step 1: resolve slug → ProjectsHub record to get domain
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

    # Step 2: permission check using the resolved domain
    if not (identity.is_owner or identity.can_access_domain(domain)):
        return jsonify({"error": "forbidden"}), 403

    # Step 3: fetch data filtered by domain
    try:
        leads = _at_list("Leads", f"{{domain}}='{domain}'", max_records=20, strict=True)
        deals = _at_list(
            "עסקאות (Deals)",
            f"AND({{domain}}='{domain}', NOT(OR({{{DealFields.STAGE}}}='סגור-ניצחון', {{{DealFields.STAGE}}}='סגור-הפסד')))",
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
    """
    allowed = {Role.OWNER, Role.MANAGER, Role.PARTNER}
    if identity.role not in allowed:
        return jsonify({"error": "forbidden"}), 403

    domain_q = request.args.get("domain", "")
    domain_q, err = _safe_formula_param(domain_q, "domain")
    if err: return err

    status_q = request.args.get("status", "")
    status_q, err = _safe_formula_param(status_q, "status")
    if err: return err

    # Resolve project_slug → domain via ProjectsHub
    slug_q = request.args.get("project_slug", "")
    slug_q, err = _safe_formula_param(slug_q, "project_slug")
    if err: return err
    if slug_q and not domain_q:
        hub = _at_list("ProjectsHub", f"{{slug}}='{slug_q}'", max_records=1)
        if hub:
            domain_q = hub[0].get("fields", {}).get("domain", "")

    parts = []
    if domain_q:
        parts.append(f"{{domain}}='{domain_q}'")
    if status_q:
        parts.append(f"{{status}}='{status_q}'")
    if identity.role == Role.PARTNER and identity.allowed_domains:
        d_conds = ", ".join(f"{{domain}}='{d}'" for d in identity.allowed_domains)
        parts.append(f"OR({d_conds})")

    formula  = f"AND({', '.join(parts)})" if parts else ""
    records  = _at_list("Leads", formula, max_records=100)

    return jsonify({
        "count": len(records),
        "leads": [_fmt_lead_summary(r) for r in records],
    })


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

    return jsonify({
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
    })


@tma_api.route("/api/leads/<lead_id>/status", methods=["PATCH"])
@require_tma_auth
def update_lead_status(lead_id, identity):
    """Update lead status. Owner + Manager only."""
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    data       = request.get_json(force=True) or {}
    new_status = data.get("status", "")
    if not new_status:
        return jsonify({"error": "missing field: status"}), 400

    _, response = _queue_tma_write_approval(
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
    return jsonify(response), 202


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
_VALID_LEAD_OUTCOMES = {
    "open",
    "needs_followup",
    "meeting_scheduled",
    "converted",
    "not_relevant",
    "lost",
    "duplicate",
    "archived",
}
_OUTCOME_STATUS_MAP = {
    "open": "active",
    "needs_followup": "waiting_response",
    "meeting_scheduled": "active",
    "converted": "done",
    "archived": "archived",
    "lost": "lost",
    "duplicate": "duplicate",
    "not_relevant": "not_relevant",
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

    if not fields or all(v == "" for v in fields.values()):
        return jsonify({"error": "no editable fields provided"}), 400

    if identity.is_owner:
        ok = _at_patch("Leads", lead_id, fields)
        if not ok:
            return jsonify({"error": "update failed"}), 500
        _audit("lead_patch", identity, details=f"{lead_id}: {list(fields.keys())}")
        return jsonify({"ok": True, "lead_id": lead_id, "updated": list(fields.keys())})

    _, response = _queue_tma_write_approval(
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
    return jsonify(response), 202


@tma_api.route("/api/leads/<lead_id>/outcome", methods=["POST"])
@require_tma_auth
def set_lead_outcome(lead_id, identity):
    """קביעת תוצאה עסקית. Outcomes סופיים מעדכנים status=done. Owner — מיידי; Manager — approval."""
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True) or {}
    outcome = _clean_select_value(data.get("outcome")).lower()
    if not outcome:
        return jsonify({"error": "missing field: outcome"}), 400
    outcome = {
        "followup_needed": "needs_followup",
        "meeting_booked": "meeting_scheduled",
    }.get(outcome, outcome)
    if outcome not in _VALID_LEAD_OUTCOMES:
        return jsonify({"error": "invalid outcome", "valid": sorted(_VALID_LEAD_OUTCOMES)}), 400

    fields: dict = {LeadFields.OUTCOME: outcome}
    if outcome in _OUTCOME_STATUS_MAP:
        fields[LeadFields.STATUS] = _OUTCOME_STATUS_MAP[outcome]

    if identity.is_owner:
        ok = _at_patch("Leads", lead_id, fields)
        if not ok:
            return jsonify({"error": "update failed"}), 500
        _audit("lead_outcome", identity, details=f"{lead_id}: {outcome}")
        return jsonify({"ok": True, "lead_id": lead_id, "outcome": outcome})

    _, response = _queue_tma_write_approval(
        "tma_set_lead_outcome",
        {
            "op": "patch",
            "table": "Leads",
            "record_id": lead_id,
            "fields": fields,
            "audit_action": "lead_outcome",
            "audit_details": f"{lead_id}: {outcome}",
        },
        identity,
        f"Set lead outcome: {outcome}",
    )
    return jsonify(response), 202


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
    lead_domain = lf.get(LeadFields.DOMAIN, "")
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
    _, response = _queue_tma_write_approval(
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
    return jsonify(response), 202


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
    _, response = _queue_tma_write_approval(
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
    return jsonify(response), 202

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

    today      = date.today()
    month_start = today.replace(day=1).isoformat()
    today_str   = today.isoformat()

    # ── Payments ──────────────────────────────────────────────────
    try:
        all_payments = _at_list("תשלומים (Payments)", "", max_records=200, strict=True)
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
        amount = float(f.get("סכום", 0) or 0)
        status = (f.get("סטטוס", "") or "").strip()
        d_str  = (f.get("תאריך", "") or "")[:10]

        if status == PaymentStatus.CANCELLED:
            continue  # בוטל — לא נספר בשום קטגוריה

        if status == PaymentStatus.RECEIVED:
            if d_str >= month_start:
                income_amount += amount
                income_count  += 1
                recent.append({
                    "ref":    f.get("אסמכתא", "—"),
                    "amount": amount,
                    "date":   d_str,
                    "status": status,
                })
        else:
            if d_str and d_str < today_str:
                overdue_amount += amount
                overdue_count  += 1
            else:
                pending_amount += amount
                pending_count  += 1

    recent.sort(key=lambda x: x["date"], reverse=True)
    recent = recent[:5]

    # ── Expenses ──────────────────────────────────────────────────
    expense_amount = 0
    expense_count  = 0
    all_expenses   = _at_list("הוצאות (Expenses)", "", max_records=200)
    for rec in all_expenses:
        f     = rec.get("fields", {})
        amt   = float(f.get("סכום", 0) or 0)
        d_str = (f.get("תאריך", "") or "")[:10]
        if d_str >= month_start:
            expense_amount += amt
            expense_count  += 1

    net = income_amount - expense_amount

    return jsonify({
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


def _fmt_approval(rec: dict) -> dict:
    f = rec.get("fields", {})
    return {
        "id":           rec["id"],
        "action":       f.get("פעולה", ""),
        "requested_by": f.get("מבוקש על ידי", ""),
        "requested_at": f.get("בוקש בתאריך", ""),
        "risk_level":   f.get("רמת סיכון", ""),
        "context_type": f.get("סוג הקשר", ""),
        "context_id":   f.get("מזהה הקשר", ""),
        "status":       f.get("סטטוס", "ממתין"),
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


def _owner_approvals_snapshot() -> tuple[dict, list[str]]:
    warnings: list[str] = []
    pending: list[dict] = []
    executed: list[dict] = []

    try:
        pending_formula = f"{{{ApprovalsFields.STATUS}}}='\u05de\u05de\u05ea\u05d9\u05df'"
        pending = [_fmt_approval(r) for r in _at_list("Approvals", pending_formula, max_records=50)]
    except Exception as e:
        logger.warning(f"[OwnerControlCenter] pending approvals read failed: {e}")
        warnings.append(f"pending approvals read failed: {type(e).__name__}")

    try:
        recs = _at_list("Approvals", "", max_records=25)
        for rec in recs:
            item = _fmt_approval(rec)
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


def _owner_strategic_pipeline() -> dict:
    """Strategic Layer — מספר עסקאות לפי שלב הערכה (לפני קבלת החלטה)."""
    try:
        stage = DealFields.STAGE
        ideas   = _at_list(Tables.DEALS, f"{{{stage}}}='{DealStatus.IDEA}'", max_records=50)
        in_eval = _at_list(
            Tables.DEALS,
            f"OR({{{stage}}}='{DealStatus.FEASIBILITY}', {{{stage}}}='{DealStatus.LEGAL_REVIEW}')",
            max_records=50,
        )
        pending = _at_list(Tables.DEALS, f"{{{stage}}}='{DealStatus.PENDING_DECISION}'", max_records=50)
        return {
            "new_opportunities": len(ideas),
            "in_evaluation":     len(in_eval),
            "pending_decision":  len(pending),
        }
    except Exception as e:
        logger.warning(f"[StrategicPipeline] {e}")
        return {"new_opportunities": 0, "in_evaluation": 0, "pending_decision": 0}


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

    approvals, approval_warnings = _owner_approvals_snapshot()
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
    approvals = [_fmt_approval(r) for r in recs]
    return jsonify({"count": len(approvals), "approvals": approvals})


@tma_api.route("/api/approvals/bulk", methods=["POST"])
@require_tma_auth
def bulk_approve(identity):
    """Approve ALL low-risk pending approvals. High/medium risk are NEVER bulk-approved."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    recs     = _at_list("Approvals", "{סטטוס}='ממתין'", max_records=100)
    approved = []
    skipped  = []

    for rec in recs:
        risk = (rec.get("fields", {}).get("רמת סיכון", "") or "").strip()
        # Hard rule: NEVER bulk-approve high risk
        if risk.lower() not in _RISK_LOW:
            skipped.append(rec["id"])
            continue
        ok = _at_patch("Approvals", rec["id"], {"סטטוס": "אושר"})
        if ok:
            approved.append(rec["id"])
            ctx_id = rec.get("fields", {}).get("מזהה הקשר", "")
            _try_bus_action(ctx_id, "approve")
        else:
            skipped.append(rec["id"])

    if approved:
        _audit("bulk_approve", identity, details=f"{len(approved)} low-risk approvals")
        _notify_owner(
            f"✅ TMA: {len(approved)} פעולות Low Risk אושרו\n"
            f"על ידי: {identity.display_name or identity.user_id}\n"
            f"דחויות (לא low-risk): {len(skipped)}"
        )

    return jsonify({"ok": True, "approved": len(approved), "skipped": len(skipped)})


@tma_api.route("/api/approvals/<approval_id>", methods=["POST"])
@require_tma_auth
def act_on_approval(approval_id, identity):
    """Approve or reject a single pending approval."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True) or {}
    decision = data.get("action", "").strip().lower()   # "approve" | "reject"
    note = data.get("note", "").strip()

    if decision not in ("approve", "reject"):
        return jsonify({"error": "action must be 'approve' or 'reject'"}), 400

    rec = _at_get_record("Approvals", approval_id)
    if not rec:
        return jsonify({"error": "approval not found"}), 404

    f = rec.get("fields", {})
    status = f.get(ApprovalsFields.STATUS, "")
    if status != "\u05de\u05de\u05ea\u05d9\u05df":
        return jsonify({"error": f"approval already {status}"}), 409

    new_status = "\u05d0\u05d5\u05e9\u05e8" if decision == "approve" else "\u05e0\u05d3\u05d7\u05d4"
    patch_fields: dict = {ApprovalsFields.STATUS: new_status}
    if decision == "reject" and note:
        patch_fields[ApprovalsFields.REJECTION_NOTE] = note

    action_label = f.get(ApprovalsFields.ACTION, approval_id)
    ctx_id = f.get(ApprovalsFields.CONTEXT_ID, "")
    execution_result = None
    context_data = f.get(ApprovalsFields.CONTEXT_DATA, "")
    if decision == "approve" and context_data:
        try:
            payload = json.loads(context_data)
        except (TypeError, ValueError):
            payload = {}
        if isinstance(payload, dict) and payload.get("type") == "tma_write":
            execution_result = _execute_tma_write(payload, identity)
            if not execution_result.get("ok"):
                return jsonify({
                    "error": "approval execution failed",
                    "detail": execution_result,
                }), 500

    ok = _at_patch("Approvals", approval_id, patch_fields)
    if not ok:
        return jsonify({"error": "update failed"}), 500

    if execution_result is None:
        _try_bus_action(ctx_id, decision)
    _audit(f"approval_{decision}", identity, details=f"{action_label[:100]} | note: {note[:80]}")

    icon = "OK" if decision == "approve" else "REJECTED"
    _notify_owner(
        f"{icon} TMA: {new_status} - {action_label}\n"
        f"approved_by: {identity.display_name or identity.user_id}"
        + (f"\nnote: {note}" if note else "")
    )

    response = {"ok": True, "approval_id": approval_id, "new_status": new_status}
    if execution_result is not None:
        response.update(execution_result)
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

@tma_api.route("/api/game/status", methods=["GET"])
@require_tma_auth
def game_status(identity):
    """Active world + this week's quests + total coins. Owner only."""
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    week_start_str = monday.isoformat()

    # ── Active world ───────────────────────────────────────────────
    worlds = _at_list(Tables.WORLDS, f"{{{WorldsFields.STATUS}}}='{WorldStatus.ACTIVE}'", max_records=1)
    active_world = None
    if worlds:
        w  = worlds[0]
        wf = w.get("fields", {})
        coins_target = int(wf.get(WorldsFields.TOTAL_COINS_TARGET, 0) or 0)
        coins_earned = int(wf.get(WorldsFields.COINS_EARNED, 0) or 0)
        pct = round(100 * coins_earned / coins_target, 1) if coins_target > 0 else 0.0
        active_world = {
            "id":           w["id"],
            "name":         wf.get(WorldsFields.NAME, ""),
            "number":       wf.get(WorldsFields.NUMBER, 1),
            "boss":         wf.get(WorldsFields.BOSS, ""),
            "prize":        wf.get(WorldsFields.PRIZE, ""),
            "coins_earned": coins_earned,
            "coins_target": coins_target,
            "progress_pct": pct,
            "start_date":   wf.get(WorldsFields.START_DATE, ""),
        }

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

    ok = _at_patch(Tables.QUESTS, quest_id, patch_fields)
    if not ok:
        return jsonify({"error": "update failed"}), 500

    # Auto-write Coins_Log only on first completion
    coins_awarded = 0
    if new_status == QuestStatus.DONE and old_status != QuestStatus.DONE:
        coins = int(qf.get(QuestsFields.COINS, 0) or 0)
        if coins > 0:
            _at_post(Tables.COINS_LOG, {
                CoinsLogFields.ACTION:        quest_name,
                CoinsLogFields.COINS:         coins,
                CoinsLogFields.DATE:          date.today().isoformat(),
                CoinsLogFields.QUEST:         [quest_id],
                CoinsLogFields.NOTE:          "Quest completed via TMA",
                CoinsLogFields.TOTAL_RUNNING: _coins_running_total(coins),
            })
            coins_awarded = coins

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


def _map_roadmap_task_status(status) -> str:
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

    # ── Roadmap Tasks — fetch all, filter in Python by owner + due ≤ today ──
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
            "status": _map_roadmap_task_status(status),
            "who":    f.get(RoadmapTaskFields.OWNER, ""),
        })

    # ── Active World ─────────────────────────────────────────────
    active_world = None
    worlds = _at_list(Tables.WORLDS, f"{{{WorldsFields.STATUS}}}='{WorldStatus.ACTIVE}'", max_records=1)
    if worlds:
        wf = worlds[0].get("fields", {})
        target = int(wf.get(WorldsFields.TOTAL_COINS_TARGET, 0) or 0)
        earned = int(wf.get(WorldsFields.COINS_EARNED, 0) or 0)
        pct    = round(100 * earned / target, 1) if target > 0 else 0.0
        active_world = {
            "id":           worlds[0]["id"],
            "name":         wf.get(WorldsFields.NAME, ""),
            "number":       int(wf.get(WorldsFields.NUMBER, 0) or 0),
            "boss":         wf.get(WorldsFields.BOSS, ""),
            "prize":        wf.get(WorldsFields.PRIZE, ""),
            "coins_earned": earned,
            "coins_target": target,
            "progress_pct": pct,
        }

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

    ok = _at_patch(Tables.ROADMAP_TASKS, task_id, {RoadmapTaskFields.STATUS: RoadmapTaskStatus.DONE})
    if not ok:
        return jsonify({"error": "update failed"}), 500

    coins = int(f.get(RoadmapTaskFields.COINS, 0) or 0)
    coins_awarded = 0
    if coins > 0:
        quest_ids = f.get(RoadmapTaskFields.QUEST, []) or []
        log_fields: dict = {
            CoinsLogFields.ACTION:        task_name,
            CoinsLogFields.COINS:         coins,
            CoinsLogFields.DATE:          date.today().isoformat(),
            CoinsLogFields.NOTE:          "Roadmap task completed via TMA",
            CoinsLogFields.TOTAL_RUNNING: _coins_running_total(coins),
        }
        if quest_ids:
            log_fields[CoinsLogFields.QUEST] = quest_ids
        log_rec = _at_post(Tables.COINS_LOG, log_fields)
        if not log_rec:
            return jsonify({
                "error": "coins log failed",
                "task_id": task_id,
                "status": RoadmapTaskStatus.DONE,
                "coins_awarded": 0,
            }), 500
        coins_awarded = coins

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

