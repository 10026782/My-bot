# tma_api.py — BOSS TMA REST API Blueprint
#
# Stateless Telegram Mini App backend.
# Every request carries X-Telegram-Init-Data — HMAC validated on each call.
# No session tokens. No state.
#
# Week 1  → full implementation
# Week 2+ → stubbed with {"status": "TODO"} responses

import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
from datetime import date, timedelta
from functools import wraps

from flask import Blueprint, jsonify, request
from identity import resolve_identity, Role
from airtable_schema import LeadFields, PaymentStatus

logger = logging.getLogger(__name__)

tma_api = Blueprint("tma_api", __name__)

# ── env ────────────────────────────────────────────────────────────
_BOT_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "")
_AT_KEY     = os.environ.get("AIRTABLE_API_KEY", "")
_AT_BASE    = os.environ.get("AIRTABLE_BASE_ID", "")
# TMA_DEV_MODE=1 skips Telegram HMAC — for local/staging testing only.
# Set X-Dev-Telegram-Id header to the owner's Telegram numeric ID.
# NEVER enable on production.
_DEV_MODE   = os.environ.get("TMA_DEV_MODE", "").strip().lower() in ("1", "true", "yes")


# ══════════════════════════════════════════════════════════════════
# CORS — allow TMA frontend (Vercel + Telegram webview)
# ══════════════════════════════════════════════════════════════════

@tma_api.after_request
def _cors(response):
    origin = request.headers.get("Origin", "")
    if (
        origin in {"https://web.telegram.org", "http://localhost:5173", "http://localhost:3000"}
        or origin.endswith(".vercel.app")
    ):
        response.headers["Access-Control-Allow-Origin"]  = origin
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-Telegram-Init-Data, X-Dev-Telegram-Id, Authorization"
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


# ══════════════════════════════════════════════════════════════════
# Raw Airtable JSON helpers — TMA only, do NOT touch airtable_tools.py
# ══════════════════════════════════════════════════════════════════

def _at_url(table: str) -> str:
    return f"https://api.airtable.com/v0/{_AT_BASE}/{urllib.parse.quote(table, safe='')}"


def _at_headers() -> dict:
    return {"Authorization": f"Bearer {_AT_KEY}"}


def _at_list(table: str, formula: str = "", max_records: int = 50) -> list:
    """Direct Airtable REST call → list[{id, fields}]. Returns [] on error."""
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
    except Exception as e:
        logger.warning(f"_at_list({table}) error: {e}")
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
    """PATCH single record. Returns True on success."""
    try:
        import httpx
        r = httpx.patch(
            f"{_at_url(table)}/{record_id}",
            headers={**_at_headers(), "Content-Type": "application/json"},
            json={"fields": fields},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        logger.warning(f"_at_patch error: {e}")
    return False


def _at_post(table: str, fields: dict) -> dict | None:
    """POST new record → created record dict or None."""
    try:
        import httpx
        r = httpx.post(
            _at_url(table),
            headers={**_at_headers(), "Content-Type": "application/json"},
            json={"fields": fields},
            timeout=10,
        )
        if r.status_code in (200, 201):
            return r.json()
        logger.warning(f"_at_post({table}) → {r.status_code}: {r.text[:120]}")
    except Exception as e:
        logger.warning(f"_at_post error: {e}")
    return None


# ══════════════════════════════════════════════════════════════════
# Audit Trail — every write action creates an activity record
# ══════════════════════════════════════════════════════════════════

def _audit(action: str, identity, details: str = "") -> None:
    """Write audit record to Business Memory table. Fails silently."""
    try:
        _at_post("Business_Memory", {
            "channel":     "tma",
            "participant": identity.display_name or identity.user_id,
            "summary":     f"[TMA] {action}: {details[:200]}",
            "keywords":    json.dumps(["tma", action.split(":")[0]]),
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

    if not hmac.compare_digest(received_hash, expected_hash):
        return None

    # Reject data older than 24 hours
    try:
        auth_date = int(params.get("auth_date", 0))
        if time.time() - auth_date > 86_400:
            return None
    except (TypeError, ValueError):
        return None

    try:
        return json.loads(params.get("user", "{}"))
    except Exception:
        return None


def require_tma_auth(f):
    """
    Decorator: reads X-Telegram-Init-Data header, validates HMAC on every request.
    Injects keyword arg `identity` into the wrapped handler.

    DEV MODE (TMA_DEV_MODE=1): skips HMAC; reads telegram_id from X-Dev-Telegram-Id.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if _DEV_MODE:
            dev_id = request.headers.get("X-Dev-Telegram-Id", "").strip()
            if not dev_id:
                return jsonify({
                    "error": "DEV_MODE active — send X-Dev-Telegram-Id: <telegram_id>",
                    "hint": "Set TMA_DEV_MODE=1 in Render env vars, then pass your Telegram numeric ID",
                }), 401
            identity = resolve_identity("telegram", dev_id)
            logger.warning(f"[TMA DEV_MODE] bypassing HMAC for telegram_id={dev_id} role={identity.role}")
            return f(*args, identity=identity, **kwargs)

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

    # Hot leads — {tier} field name unknown, removed to avoid 422.
    # score>=70 OR status='hot' is sufficient.
    hot_leads = _at_list(
        "Leads",
        f"OR({{status}}='hot', {{{LeadFields.SCORE}}}>=70)",
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
    rec = _at_post("ProjectsHub", fields)
    if not rec:
        return jsonify({"error": "failed to create project — ProjectsHub table may not exist yet"}), 500

    _audit("create_project", identity, details=data["name"])
    return jsonify({"ok": True, "id": rec["id"], "name": data["name"]}), 201


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
    leads = _at_list("Leads", f"{{domain}}='{domain}'", max_records=20)
    deals = _at_list(
        "עסקאות (Deals)",
        "NOT(OR({שלב}='סגור-ניצחון', {שלב}='סגור-הפסד'))",
        max_records=20,
    )
    tasks = _at_list(
        "משימות (Tasks)",
        "{סטטוס}!='בוצע'",
        max_records=10,
    )

    return jsonify({
        "project_slug": project_slug,
        "domain":       domain,
        "name":         hub_fields.get("Name", ""),
        "leads_count":  len(leads),
        "open_deals":   len(deals),
        "open_tasks":   len(tasks),
        "leads":        [_fmt_lead_summary(r) for r in leads[:10]],
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
    status_q = request.args.get("status", "")

    # Resolve project_slug → domain via ProjectsHub
    slug_q = request.args.get("project_slug", "")
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

    # Timeline from Business Memory — interactions logged for this lead
    timeline_recs = _at_list(
        "Business_Memory",
        f"SEARCH('{lead_id}', {{summary}})",
        max_records=20,
    )
    timeline = [
        {
            "summary": t.get("fields", {}).get("summary", ""),
            "channel": t.get("fields", {}).get("channel", ""),
        }
        for t in timeline_recs
    ]

    score       = int(f.get(LeadFields.SCORE, 0) or 0)
    score_color = "red" if score >= 70 else ("yellow" if score >= 40 else "blue")

    return jsonify({
        "id":          rec["id"],
        "name":        f.get("Name", ""),
        "phone":       f.get("phone", ""),
        "domain":      f.get("domain", ""),
        "status":      f.get("status", ""),
        "score":       score,
        "score_color": score_color,
        "source":      f.get("source", ""),
        "summary":     f.get("summary", ""),
        "next_step":   f.get("next_step", ""),
        "created_at":  f.get("created_at", ""),
        "timeline":    timeline,
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

    ok = _at_patch("Leads", lead_id, {"status": new_status})
    if not ok:
        return jsonify({"error": "update failed"}), 500

    _audit("lead_status_update", identity, details=f"{lead_id} → {new_status}")
    return jsonify({"ok": True, "lead_id": lead_id, "status": new_status})


# ══════════════════════════════════════════════════════════════════
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

    rec = _at_post("משימות (Tasks)", {
        "כותרת המשימה": f"מעקב: {lead_name}",
        "תיאור":         note,
        "תאריך יעד":    tomorrow,
        "סטטוס":         "ממתין",
    })
    if not rec:
        return jsonify({"error": "failed to create task"}), 500

    _audit("followup_created", identity, details=f"{lead_name}: {note[:80]}")
    return jsonify({"ok": True, "task_id": rec["id"], "lead_name": lead_name}), 201


# ══════════════════════════════════════════════════════════════════
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
        import anthropic
        from context import build_context
        from memory_store import memory

        ctx      = build_context(identity, full_question)
        history  = memory.get_for_claude(ctx.memory_key)
        messages = history + [{"role": "user", "content": full_question}]

        _client  = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        response = _client.messages.create(
            model       = ctx.model,
            max_tokens  = ctx.max_tokens,
            temperature = 0.2,
            system      = ctx.system_prompt,
            messages    = messages,
            # No tools — TMA Ask AI is a single-turn contextual answer
        )

        text_blocks = [b for b in response.content if b.type == "text"]
        answer = text_blocks[0].text if text_blocks else "⚠️ לא התקבלה תשובה."

    except Exception as e:
        logger.error(f"[AskAI] error: {e}", exc_info=True)
        return jsonify({"error": "AI service unavailable"}), 503

    return jsonify({"answer": answer, "context": context_type})


# ══════════════════════════════════════════════════════════════════
# WEEK 2 stubs — Finance, Approvals, Activity, Assets
# ══════════════════════════════════════════════════════════════════

def _todo(screen: str):
    return jsonify({"status": "TODO", "screen": screen, "week": 2}), 200


@tma_api.route("/api/finance/pulse", methods=["GET"])
@require_tma_auth
def finance_pulse(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    today      = date.today()
    month_start = today.replace(day=1).isoformat()
    today_str   = today.isoformat()

    # ── Payments ──────────────────────────────────────────────────
    all_payments = _at_list("תשלומים (Payments)", "", max_records=200)

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

    data     = request.get_json(force=True) or {}
    decision = data.get("action", "").strip().lower()   # "approve" | "reject"
    note     = data.get("note", "").strip()

    if decision not in ("approve", "reject"):
        return jsonify({"error": "action must be 'approve' or 'reject'"}), 400

    rec = _at_get_record("Approvals", approval_id)
    if not rec:
        return jsonify({"error": "approval not found"}), 404

    f      = rec.get("fields", {})
    status = f.get("סטטוס", "")
    if status != "ממתין":
        return jsonify({"error": f"approval already {status}"}), 409

    new_status = "אושר" if decision == "approve" else "נדחה"
    patch_fields: dict = {"סטטוס": new_status}
    if decision == "reject" and note:
        patch_fields["הערת דחייה"] = note

    ok = _at_patch("Approvals", approval_id, patch_fields)
    if not ok:
        return jsonify({"error": "update failed"}), 500

    action_label = f.get("פעולה", approval_id)
    ctx_id       = f.get("מזהה הקשר", "")

    _try_bus_action(ctx_id, decision)
    _audit(f"approval_{decision}", identity, details=f"{action_label[:100]} | note: {note[:80]}")

    icon = "✅" if decision == "approve" else "❌"
    _notify_owner(
        f"{icon} TMA: {new_status} — {action_label}\n"
        f"על ידי: {identity.display_name or identity.user_id}"
        + (f"\nהערה: {note}" if note else "")
    )

    return jsonify({"ok": True, "approval_id": approval_id, "new_status": new_status})


@tma_api.route("/api/activity", methods=["GET"])
@require_tma_auth
def activity_feed(identity):
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403

    domain_q = request.args.get("domain", "").strip()
    limit    = min(int(request.args.get("limit", 50) or 50), 100)

    formula  = f"{{domain}}='{domain_q}'" if domain_q else ""
    recs     = _at_list("Business_Memory", formula, max_records=limit)

    entries = []
    for rec in recs:
        f = rec.get("fields", {})
        entries.append({
            "id":        rec["id"],
            "title":     f.get("title", "") or (f.get("summary", "")[:60]),
            "summary":   f.get("summary", ""),
            "channel":   f.get("channel", ""),
            "domain":    f.get("domain", ""),
            "timestamp": f.get("timestamp", ""),
            "sentiment": f.get("sentiment", ""),
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
    if not _can_assets(identity):
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

