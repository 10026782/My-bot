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
            "Content-Type, X-Telegram-Init-Data, Authorization"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
    return response


@tma_api.route("/api/tma/auth", methods=["OPTIONS"])
@tma_api.route("/api/projects", methods=["OPTIONS"])
@tma_api.route("/api/leads", methods=["OPTIONS"])
@tma_api.route("/api/ai/ask", methods=["OPTIONS"])
@tma_api.route("/api/followup", methods=["OPTIONS"])
def _preflight():
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
        _at_post("Business Memory", {
            "channel":     "tma",
            "participant": identity.display_name or identity.user_id,
            "summary":     f"[TMA] {action}: {details[:200]}",
            "keywords":    json.dumps(["tma", action.split(":")[0]]),
        })
    except Exception as e:
        logger.warning(f"[Audit] failed for '{action}': {e}")


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

    # Hot leads (same filter as _hot_leads)
    hot_leads = _at_list(
        "Leads",
        "OR({status}='hot', {score ציון}>=70, {tier}='HOT')",
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
                if (l.get("fields", {}).get("score ציון") or 0) >= 70
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
    score = int(f.get("score ציון", 0) or 0)
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
    """O2 — Lead Pipeline. Owner + Manager (all) + Partner (own domains)."""
    allowed = {Role.OWNER, Role.MANAGER, Role.PARTNER}
    if identity.role not in allowed:
        return jsonify({"error": "forbidden"}), 403

    domain_q = request.args.get("domain", "")
    status_q = request.args.get("status", "")

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
        "Business Memory",
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

    score       = int(f.get("score ציון", 0) or 0)
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
                f"ציון: {f.get('score ציון', '')} | "
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
    return _todo("O4 Finance Pulse")


@tma_api.route("/api/approvals", methods=["GET"])
@require_tma_auth
def get_approvals(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403
    return _todo("O6 Approvals")


@tma_api.route("/api/approvals/bulk", methods=["POST"])
@require_tma_auth
def bulk_approve(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403
    return _todo("O6 Approvals — bulk")


@tma_api.route("/api/approvals/<approval_id>", methods=["POST"])
@require_tma_auth
def act_on_approval(approval_id, identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403
    return _todo(f"O6 Approvals — single {approval_id}")


@tma_api.route("/api/activity", methods=["GET"])
@require_tma_auth
def activity_feed(identity):
    if identity.role not in {Role.OWNER, Role.MANAGER}:
        return jsonify({"error": "forbidden"}), 403
    return _todo("O7 Activity Feed")


# ── Assets (Personal Mode) ─────────────────────────────────────

def _can_assets(identity) -> bool:
    return identity.is_owner or "personal" in (identity.allowed_domains or [])


@tma_api.route("/api/assets", methods=["GET"])
@require_tma_auth
def get_assets(identity):
    if not _can_assets(identity):
        return jsonify({"error": "forbidden"}), 403
    return _todo("PN1 Assets Overview")


@tma_api.route("/api/assets/<asset_id>", methods=["GET"])
@require_tma_auth
def get_asset(asset_id, identity):
    if not _can_assets(identity):
        return jsonify({"error": "forbidden"}), 403
    return _todo(f"PN2 Asset Card {asset_id}")


@tma_api.route("/api/assets/<asset_id>", methods=["PATCH"])
@require_tma_auth
def update_asset(asset_id, identity):
    if not _can_assets(identity):
        return jsonify({"error": "forbidden"}), 403
    return _todo(f"PN2 Asset Update {asset_id}")


# ══════════════════════════════════════════════════════════════════
# WEEK 3 stubs — System Health + Emergency Stop
# ══════════════════════════════════════════════════════════════════

@tma_api.route("/api/health", methods=["GET"])
@require_tma_auth
def system_health(identity):
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403
    return _todo("O8 System Health")


@tma_api.route("/api/health/emergency", methods=["POST"])
@require_tma_auth
def emergency_stop(identity):
    """
    Emergency stop — sets a feature flag only, does not kill processes.
    Checks feature_flags.is_enabled("EMERGENCY_<ACTION>") before executing actions.
    """
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    data   = request.get_json(force=True) or {}
    action = data.get("action", "")
    valid  = {"stop_all", "stop_whatsapp", "stop_email", "stop_automation"}

    if action not in valid:
        return jsonify({"error": f"unknown action — must be one of {sorted(valid)}"}), 400

    try:
        from feature_flags import set_flag
        flag = f"EMERGENCY_{action.upper()}"
        set_flag(flag, True)
        _audit("emergency_stop", identity, details=action)
        return jsonify({"ok": True, "action": action, "flag": flag})
    except Exception as e:
        logger.error(f"[Emergency] set_flag failed: {e}")
        return jsonify({"error": "failed to set emergency flag"}), 500


# ══════════════════════════════════════════════════════════════════
# DEV ONLY — Schema audit endpoint (TMA_DEV_MODE=1 required)
# Remove before production launch.
# ══════════════════════════════════════════════════════════════════

@tma_api.route("/api/dev/schema", methods=["GET"])
@require_tma_auth
def dev_schema_audit(identity):
    """Returns field names + sample values from each business table. Owner only."""
    if not _DEV_MODE:
        return jsonify({"error": "only available in DEV_MODE"}), 403
    if not identity.is_owner:
        return jsonify({"error": "forbidden"}), 403

    _CLOSED_STATUSES = {"Closed", "Won", "Lost", "Cancelled", "Done",
                        "Completed", "הושלם", "נסגר", "בוטל"}

    tables = ["Leads", "Deals", "משימות (Tasks)", "תשלומים (Payments)"]
    result = {}

    for table in tables:
        records = _at_list(table, "", max_records=3)
        if not records:
            result[table] = {"error": "empty or missing", "fields": []}
            continue

        all_fields: dict[str, set] = {}
        for rec in records:
            for k, v in rec.get("fields", {}).items():
                all_fields.setdefault(k, set()).add(str(v)[:80])

        domain_keys = [k for k in all_fields if any(
            x in k.lower() for x in ["domain", "project", "פרויקט", "דומיין", "tenant"]
        )]
        status_keys = [k for k in all_fields if "status" in k.lower() or "סטטוס" in k]

        result[table] = {
            "record_count_sample": len(records),
            "fields": {k: list(v) for k, v in all_fields.items()},
            "domain_project_candidates": domain_keys,
            "status_candidates": {k: list(all_fields[k]) for k in status_keys},
        }

    return jsonify(result)
