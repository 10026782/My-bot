# core/lead_service.py — Canonical Lead Creation Service (Phase 1)
#
# Single source of truth for creating/updating a Lead. Every Lead-creation
# entry point (chat capture via core/lead_candidate_handler.py, the
# structured `ליד חדש | ...` command below, and — over time — every other
# writer per the Phase 1 remediation plan) must build a LeadPayload and
# call create_lead(). No other code path should call
# tools.airtable_gateway.airtable_create/airtable_patch on table="Leads"
# directly.
#
# This module intentionally bypasses tools/dispatcher.py (Leads writes are
# explicitly blocked there for source="agent" — see
# tools/airtable_security.py::enforce_leads_write_gate — manual Lead
# creation is a trusted, non-agent path, same precedent as
# lead_capture.py). Safeguards the dispatcher would normally provide are
# reproduced here explicitly: EMERGENCY_STOP_ALL check, the ActionGateway
# dedup/idempotency ledger, and tenant_id stamped on every write.

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from airtable_schema import LeadFields

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Canonical domain contract
# ══════════════════════════════════════════════════

# The business verticals a Lead's Domain field may hold. Deliberately NOT
# core.router.route_decision.RouterDomain — that catalog also carries
# routing-only meta-domains (crm/internal) that are meaningless as a lead's
# business vertical and 422 against the live Airtable schema.
CANONICAL_LEAD_DOMAINS = frozenset({
    "real_estate", "import", "media", "saas", "finance", "recruitment", "general",
})


def resolve_domain(text: str, router_domain: str = "") -> tuple[str, bool]:
    """
    Single domain-resolution authority for Lead creation. Precedence:
      1. An explicit "domain X" / "דומיין X" annotation in `text` — always
         wins, never re-inferred or overridden by anything else (Phase 1
         Domain Contract: explicit beats inferred).
      2. `router_domain` (core.router.domain_router's own classification),
         when it is a real business vertical.
      3. "general" fallback — including when router_domain is a
         routing-only meta-domain (crm/internal) or unrecognized.

    Returns (canonical_domain, is_explicit).
    """
    from core.ingress_classifier import _extract_domain_hint
    hint = _extract_domain_hint(text) if text else None
    if hint:
        return hint, True

    if router_domain in CANONICAL_LEAD_DOMAINS:
        return router_domain, False

    return "general", False


def resolve_domain_word(word: str) -> Optional[str]:
    """
    Canonicalizes a BARE domain token (e.g. the `domain` column of the
    structured `ליד חדש | ...` command below) — not a sentence to scan.
    Reuses the SAME hint vocabulary core.ingress_classifier's
    _DOMAIN_HINT_CANONICAL uses for free-text "דומיין X" annotations, one
    shared mapping table, never a second guess table. Returns None (never
    guesses/falls back) when the word has no known canonical mapping.
    """
    if not word:
        return None
    key = word.strip().lower()
    if key in CANONICAL_LEAD_DOMAINS:
        return key
    from core.ingress_classifier import _DOMAIN_HINT_CANONICAL
    return _DOMAIN_HINT_CANONICAL.get(key)


# ══════════════════════════════════════════════════
# Canonical Owner contract
# ══════════════════════════════════════════════════

def resolve_owner(identity, owner_user_id: str = "") -> tuple[Optional[str], str]:
    """
    Returns (profile_record_id_or_None, resolved_user_id).

    Phase 1 Owner Contract: when no explicit owner is given, Owner defaults
    to the creator (identity.user_id) — a Lead is never created with an
    empty Owner when the creator's identity is known. Reuses
    tma_api._resolve_profile_record_id() — the SAME resolver
    tma_api.create_lead_task() already uses for Tasks.Owner, not a second
    implementation.
    """
    from tma_api import _resolve_profile_record_id

    target_user_id = owner_user_id.strip() if owner_user_id else (getattr(identity, "user_id", "") or "")
    if not target_user_id:
        return None, ""
    record_id = _resolve_profile_record_id(target_user_id)
    return record_id, target_user_id


# ══════════════════════════════════════════════════
# Payload / result
# ══════════════════════════════════════════════════

class LeadValidationError(Exception):
    """Raised when a payload is missing a required field or carries an
    unresolvable value. Never silently invented/defaulted (Phase 1 rule 4)."""

    def __init__(self, field_name: str, reason: str):
        self.field_name = field_name
        self.reason = reason
        super().__init__(f"{field_name}: {reason}")


@dataclass
class LeadPayload:
    name: str
    phone: str
    domain: str = "general"      # already-resolved canonical value — see resolve_domain()
    domain_explicit: bool = False
    owner_user_id: str = ""      # "" => default to creator, see resolve_owner()
    source: str = "manual"
    channel: str = "telegram"
    campaign: str = ""           # accepted, not yet written — no live schema column (see build_lead_fields)
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    summary: str = ""
    status: str = "new"
    score: int = 0
    tenant_id: str = "boss_hq"


@dataclass
class LeadCreateResult:
    ok: bool
    action: str                  # "created" | "updated" | "duplicate" | "blocked" | "invalid" | "lifecycle_persistence_failed"
    record_id: str = ""
    domain: str = ""
    owner_user_id: str = ""
    reason: str = ""
    evidence: dict = field(default_factory=dict)


def _validate(payload: LeadPayload) -> None:
    if not payload.name or not payload.name.strip():
        raise LeadValidationError("name", "שם הליד הוא שדה חובה")
    if not payload.phone or not payload.phone.strip():
        raise LeadValidationError("phone", "מספר טלפון הוא שדה חובה")


# ══════════════════════════════════════════════════
# Dedup — single implementation
# ══════════════════════════════════════════════════

def find_existing_lead(name: str, phone: str) -> Optional[str]:
    """מחפש ליד קיים לפי שם + טלפון. מחזיר record_id או None.

    The one dedup lookup for Lead creation (Phase 1 Step 7) — moved here
    from core/lead_candidate_handler.py's former private _at_find_lead, so
    every caller shares this single implementation. Callers that already
    have their own pre-resolved match (e.g. lead_candidate_handler.py,
    which still calls this directly under the same name for backward
    compatibility with its own regression tests) can pass it straight into
    create_lead()'s `existing_id` instead of triggering a second lookup.
    """
    import os
    import urllib.parse
    import httpx

    base = os.environ.get("AIRTABLE_BASE_ID", "")
    key = os.environ.get("AIRTABLE_API_KEY", "")
    if not base or not key:
        return None

    url = f"https://api.airtable.com/v0/{base}/{urllib.parse.quote('Leads', safe='')}"
    headers = {"Authorization": f"Bearer {key}"}

    for formula in _search_formulas(name, phone):
        try:
            r = httpx.get(url, headers=headers,
                          params={"filterByFormula": formula, "maxRecords": 5},
                          timeout=8)
            if r.status_code == 200:
                records = r.json().get("records", [])
                if records:
                    if phone:
                        # Only an exact phone match counts as "the same lead"
                        # — a shared/similar name alone is not enough (see
                        # BUG-094 in the original lead_candidate_handler.py).
                        for rec in records:
                            rec_phone = re.sub(r"[\s\-]", "", str(rec.get("fields", {}).get("phone", "")))
                            if rec_phone == phone:
                                return rec["id"]
                        continue
                    return records[0]["id"]
        except Exception as exc:
            logger.warning("[LeadService] Airtable search error: %s", exc)

    return None


def _search_formulas(name: str, phone: str) -> list[str]:
    from tools.airtable_gateway import _safe_formula_param
    safe_name = _safe_formula_param(name)
    formulas: list[str] = []
    if phone:
        safe_phone = _safe_formula_param(phone)
        formulas.append(f"AND(SEARCH('{safe_name}', {{Name}}), {{phone}}='{safe_phone}')")
        formulas.append(f"{{phone}}='{safe_phone}'")
    formulas.append(f"SEARCH('{safe_name}', {{Name}})")
    return formulas


# ══════════════════════════════════════════════════
# Field construction (pure — no I/O)
# ══════════════════════════════════════════════════

def build_memory_key(tenant_id: str, phone: str, name: str) -> str:
    phone_key = re.sub(r"[\s\-\+]", "", phone or "")
    if phone_key:
        return f"{tenant_id}/{phone_key}@lead"
    safe_name = re.sub(" ", "_", (name or "").lower()[:20])
    return f"{tenant_id}/dict_{safe_name}@lead"


def build_lead_fields(payload: LeadPayload, owner_record_id: Optional[str], memory_key: str) -> dict:
    """Pure field-construction — no I/O, no invented fields. campaign/UTM
    fields are deliberately NOT written: no column for them exists in the
    live Airtable schema (or in airtable_schema.py) today — see the audit's
    marketing-attribution findings. Writing them would silently fail the
    same way ad_attribution.py's writes already do; accepting-but-dropping
    with a clear log is the honest Phase 1 choice pending a real
    attribution-schema decision (explicitly out of Phase 1 scope)."""
    if payload.campaign or payload.utm_source or payload.utm_medium or payload.utm_campaign:
        logger.info(
            "[LeadService] campaign/UTM fields provided but not written — no live "
            "schema column exists yet (campaign=%r utm_source=%r utm_medium=%r utm_campaign=%r)",
            payload.campaign, payload.utm_source, payload.utm_medium, payload.utm_campaign,
        )

    fields: dict = {
        LeadFields.NAME:       payload.name,
        LeadFields.PHONE:      payload.phone,
        LeadFields.CHANNEL:    payload.channel,
        LeadFields.MEMORY_KEY: memory_key,
        LeadFields.DOMAIN:     payload.domain,
        LeadFields.SOURCE:     payload.source,
        LeadFields.STATUS:     payload.status,
        LeadFields.SUMMARY:    (payload.summary or "")[:500],
        LeadFields.SCORE:      payload.score,
        LeadFields.SENDER_ID:  payload.phone,
        LeadFields.TENANT_ID:  payload.tenant_id,
    }
    if owner_record_id:
        fields[LeadFields.OWNER] = [owner_record_id]
    return fields


# ══════════════════════════════════════════════════
# The canonical writer
# ══════════════════════════════════════════════════

def create_lead(
    identity,
    payload: LeadPayload,
    *,
    source_module: str,
    existing_id: Optional[str] = None,
) -> LeadCreateResult:
    """
    The single canonical entry point for writing a Lead record.

    existing_id: pass a pre-resolved dedup match when the caller already
    ran its own find_existing_lead() lookup (e.g.
    core/lead_candidate_handler.py, for backward compatibility with tests
    that patch its module-level `_at_find_lead`) to skip a second lookup
    here. None (default) makes this function do its own lookup — used by
    the structured-command path below, which has no caller-side lookup.
    """
    try:
        _validate(payload)
    except LeadValidationError as exc:
        return LeadCreateResult(ok=False, action="invalid", reason=str(exc))

    if payload.domain not in CANONICAL_LEAD_DOMAINS:
        return LeadCreateResult(ok=False, action="invalid",
                                 reason=f"domain: ערך לא קנוני {payload.domain!r}")

    import feature_flags as _ff
    from tool_registry import TOOLS_BLOCKED_BY_EMERGENCY
    if _ff.is_enabled("EMERGENCY_STOP_ALL") and "airtable_add" in TOOLS_BLOCKED_BY_EMERGENCY:
        logger.critical("[LeadService] blocked by EMERGENCY_STOP_ALL | source=%s", source_module)
        return LeadCreateResult(ok=False, action="blocked", reason="emergency_stop_all")

    tenant_id = getattr(identity, "tenant_id", "default") or "default"
    payload.tenant_id = tenant_id

    owner_record_id, resolved_owner_user_id = resolve_owner(identity, payload.owner_user_id)
    if payload.owner_user_id and not owner_record_id:
        return LeadCreateResult(ok=False, action="invalid",
                                 reason=f"owner_user_id: {payload.owner_user_id!r} לא נמצא בטבלת Profile")
    if not owner_record_id:
        logger.warning(
            "[LeadService] no Owner resolved for creator=%r (source=%s) — "
            "lead will be created without an Owner",
            resolved_owner_user_id, source_module,
        )

    memory_key = build_memory_key(tenant_id, payload.phone, payload.name)

    if existing_id is None:
        existing_id = find_existing_lead(payload.name, payload.phone)
    action = "updated" if existing_id else "created"

    fields = build_lead_fields(payload, owner_record_id, memory_key)

    # ActionGateway dedup fingerprint / idempotency ledger — the same
    # mechanism every Lead write already went through (BUG-077); preserved
    # here, not removed (Phase 1 Step 6: don't strip existing safeguards).
    contract_id = None
    contract_ledger = None
    try:
        from core.action_gateway import action_gateway as _gw
        tool_name = "airtable_update" if existing_id else "airtable_add"
        if existing_id:
            gw_fields = {
                k: v for k, v in fields.items()
                if k in (LeadFields.PHONE, LeadFields.SUMMARY, LeadFields.DOMAIN, LeadFields.OWNER)
            }
            gw_inputs = {"table": "Leads", "record_id": existing_id, "fields": gw_fields}
        else:
            gw_inputs = {"table": "Leads", "fields": fields}
        gw_result = _gw.propose_action(
            tenant_id=tenant_id,
            canonical_user_id=identity.memory_key,
            tool_name=tool_name,
            tool_inputs=gw_inputs,
            origin_channel=payload.channel,
            origin_chat_id=identity.memory_key,
            requires_approval=False,
            identity=identity,
        )
        if not gw_result.ok:
            logger.info("[LeadService] gateway blocked for %r: %s", payload.name, gw_result.reason)
            return LeadCreateResult(ok=False, action="duplicate", reason=gw_result.reason or "gateway_blocked")
        contract_id = gw_result.contract_id
        contract_ledger = _gw._ledger
    except Exception as exc:
        logger.warning("[LeadService] gateway propose failed: %s", exc)

    # Write
    record_id = ""
    ok = False
    try:
        from tools.airtable_gateway import airtable_create, airtable_patch
        if existing_id:
            patch_fields = {
                LeadFields.PHONE:   payload.phone,
                LeadFields.SUMMARY: (payload.summary or "")[:500],
                LeadFields.DOMAIN:  payload.domain,
            }
            if owner_record_id:
                patch_fields[LeadFields.OWNER] = [owner_record_id]
            ok_patch = airtable_patch("Leads", existing_id, patch_fields, source=source_module)
            if ok_patch:
                record_id = existing_id
                ok = True
        else:
            rec = airtable_create("Leads", fields, source=source_module)
            if rec:
                record_id = rec.get("id", "")
                ok = bool(record_id)
    except Exception as exc:
        logger.error("[LeadService] write failed for %r: %s", payload.name, exc)

    lifecycle_persistence_failed = False
    if contract_id:
        try:
            success_status = "completed" if contract_ledger._repository else "executed"
            if not contract_ledger.update_status(contract_id, success_status if ok else "failed"):
                raise RuntimeError("contract missing during lifecycle update")
            if ok and record_id:
                c = contract_ledger.find_by_id(contract_id)
                if c:
                    import time as _t
                    c.agent_observations.append({"kind": "execution_fact", "record_id": record_id, "created_at": _t.time()})
        except Exception as exc:
            lifecycle_persistence_failed = True
            logger.critical(
                "[LeadService] provider result could not be persisted to ActionContracts: "
                "contract=%s provider_ok=%s error=%s",
                contract_id, ok, exc,
            )

    if lifecycle_persistence_failed:
        return LeadCreateResult(ok=False, action="lifecycle_persistence_failed", record_id=record_id)

    if ok and record_id:
        _run_post_write_enrichment(identity, payload, record_id, action)

    return LeadCreateResult(
        ok=ok,
        action=action,
        record_id=record_id,
        domain=payload.domain,
        owner_user_id=resolved_owner_user_id if owner_record_id else "",
        reason="" if ok else "write_failed",
        evidence={"contract_id": contract_id or ""},
    )


def _run_post_write_enrichment(identity, payload: LeadPayload, record_id: str, action: str) -> None:
    """Non-blocking, flag-gated post-write hooks — unchanged behavior,
    relocated verbatim from the former _write_one_lead (Phase 1 explicitly
    does not touch memory/learning, only preserves what already ran)."""
    try:
        from lead_capture import capture_lead_event
        from feature_flags import is_enabled as _flag
        if _flag("LEAD_CAPTURE"):
            capture_lead_event(identity, payload.summary or payload.name, record_id, domain=payload.domain)
    except Exception as exc:
        logger.warning("[LeadService] lead_event failed: %s", exc)

    try:
        from feature_flags import is_enabled as _flagm
        if _flagm("LEAD_MEMORY"):
            from lead_memory import lead_memory
            memory_key = build_memory_key(payload.tenant_id, payload.phone, payload.name)
            lead_memory.update(
                memory_key, domain=payload.domain, channel=payload.channel,
                contact_name=payload.name, last_message=payload.summary,
                summary=(payload.summary or "")[:500],
            )
    except Exception as exc:
        logger.warning("[LeadService] lead_memory failed: %s", exc)

    if action == "created":
        try:
            from feature_flags import is_enabled as _flags
            if _flags("LEAD_SCORING"):
                from lead_capture import _score_inbound_message
                from tools.airtable_gateway import airtable_patch as _gw_patch
                score, _, _ = _score_inbound_message(payload.summary or payload.name, identity)
                _gw_patch("Leads", record_id, {LeadFields.SCORE: score}, source="lead_service_scoring")
        except Exception as exc:
            logger.warning("[LeadService] scoring failed: %s", exc)


# ══════════════════════════════════════════════════
# Structured creation mode — "ליד חדש | שם | טלפון | domain | הערה"
#
# Phase 1 Step 5: a fully deterministic alternative to natural-language
# capture. Never guesses where a name ends and a note begins — a missing or
# unrecognized field is always a clear, explicit error, never a silent
# invented default.
# ══════════════════════════════════════════════════

_STRUCTURED_TRIGGER_RE = re.compile(r"^\s*ליד\s+חדש\s*(\|.*)?$", re.DOTALL)

STRUCTURED_COMMAND_HELP = (
    "ליצירת ליד בפורמט מובנה:\n"
    "ליד חדש | שם | טלפון | domain | הערה\n\n"
    "לדוגמה:\n"
    "ליד חדש | עידן מושקוביץ | 0506872216 | recruitment | תשתיות חיצוניות, בעל מספר צוותים\n\n"
    f"ערכי domain אפשריים: {', '.join(sorted(CANONICAL_LEAD_DOMAINS))}"
)


def parse_structured_command(text: str) -> Optional[dict]:
    """
    Parses the deterministic `ליד חדש | שם | טלפון | domain | הערה`
    command.

    Returns:
      None                    — `text` isn't this format at all (caller
                                 should fall through to natural-language
                                 capture).
      {"prompt": True}        — bare "ליד חדש" trigger, no fields yet.
      {"error": "..."}        — trigger matched but a required field is
                                 missing/unrecognized.
      {"name","phone","domain","note"} — a fully valid, ready-to-use payload.
    """
    if not text:
        return None
    m = _STRUCTURED_TRIGGER_RE.match(text.strip())
    if not m:
        return None

    rest = (m.group(1) or "").lstrip("|").strip()
    if not rest:
        return {"prompt": True}

    parts = [p.strip() for p in rest.split("|")]
    if len(parts) < 3:
        return {"error": f"פורמט חסר.\n\n{STRUCTURED_COMMAND_HELP}"}

    name, phone, domain_word = parts[0], parts[1], parts[2]
    note = " | ".join(parts[3:]).strip() if len(parts) > 3 else ""

    if not name:
        return {"error": f"חסר שם.\n\n{STRUCTURED_COMMAND_HELP}"}

    from core.ingress_classifier import _normalize_phone, _PHONE_RE
    if not phone or not _PHONE_RE.fullmatch(phone.replace(" ", "")):
        return {"error": f"מספר טלפון לא תקין: {phone!r}.\n\n{STRUCTURED_COMMAND_HELP}"}
    phone = _normalize_phone(phone)

    domain = resolve_domain_word(domain_word)
    if not domain:
        return {"error": (
            f"domain לא מוכר: {domain_word!r}. "
            f"ערכים אפשריים: {', '.join(sorted(CANONICAL_LEAD_DOMAINS))}"
        )}

    return {"name": name, "phone": phone, "domain": domain, "note": note}
