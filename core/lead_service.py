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

# A stable, numbered ordering of the same set — lets a reply be a bare
# digit ("3") instead of typing the exact canonical word, for the Lead
# Draft Card's domain prompt (UX follow-up: choosing by number). Sorted
# alphabetically so the displayed list is deterministic and matches what
# error messages already show via sorted(CANONICAL_LEAD_DOMAINS).
CANONICAL_LEAD_DOMAINS_ORDERED = tuple(sorted(CANONICAL_LEAD_DOMAINS))


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
    Canonicalizes a BARE domain token — e.g. the `domain` column of the
    structured `ליד חדש | ...` command below, or a reply to the Lead Draft
    Card's domain prompt (word OR a 1-based number into
    CANONICAL_LEAD_DOMAINS_ORDERED, per render_lead_draft_card's numbered
    list) — not a sentence to scan. Word-lookup reuses the SAME hint
    vocabulary core.ingress_classifier's _DOMAIN_HINT_CANONICAL uses for
    free-text "דומיין X" annotations, one shared mapping table, never a
    second guess table. Returns None (never guesses/falls back) when the
    word/number has no known canonical mapping.
    """
    if not word:
        return None
    key = word.strip().lower()
    if key.isdigit():
        idx = int(key)
        if 1 <= idx <= len(CANONICAL_LEAD_DOMAINS_ORDERED):
            return CANONICAL_LEAD_DOMAINS_ORDERED[idx - 1]
        return None
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


# Referral fee taxonomy — kept as a fixed, small vocabulary (not free text)
# so it stays reportable/joinable, per the audit's "no invented completion,
# structured fields not squashed text" requirement.
REFERRAL_FEE_TYPES = frozenset({"none", "fixed", "percent"})
REFERRAL_FEE_STATUSES = frozenset({"not_relevant", "pending", "eligible", "paid"})


@dataclass
class LeadPayload:
    name: str
    phone: str
    domain: str = "general"      # already-resolved canonical value — see resolve_domain()
    domain_explicit: bool = False
    owner_user_id: str = ""      # "" => default to creator, see resolve_owner()
    source: str = "manual"       # technical origin: Telegram/WhatsApp/Facebook/Website/Manual
    channel: str = "telegram"
    summary: str = ""
    status: str = "new"
    score: int = 0
    tenant_id: str = "boss_hq"

    # ── Campaign attribution — distinct from `source` (technical origin) ──
    # accepted, not yet written — no live Airtable column exists for any of
    # these today (see build_lead_fields); defined now in the payload per
    # the Phase 1 follow-up decision, so the model is locked in before the
    # live schema is, rather than the other way around.
    campaign: str = ""
    adset: str = ""
    ad: str = ""

    # ── Referral — a SEPARATE concept from `source`/campaign attribution:
    # "did a person introduce this lead, and what do they get for it."
    # Deliberately five distinct fields, never squashed into one text blob
    # (e.g. "facebook - משה - 500") — reports/learning/attribution need to
    # join on these independently. ─────────────────────────────────────
    is_referral: bool = False
    referrer_id: str = ""        # preferred — an existing Contact's record id
    referrer_name: str = ""      # fallback display when the referrer isn't a known contact
    referral_fee_type: str = "none"       # none | fixed | percent
    referral_fee_value: float = 0.0
    referral_fee_trigger: str = ""        # e.g. "on_deal_close", or a business-defined rule
    referral_fee_status: str = "not_relevant"  # not_relevant | pending | eligible | paid


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

    if payload.referral_fee_type not in REFERRAL_FEE_TYPES:
        raise LeadValidationError(
            "referral_fee_type",
            f"ערך לא קנוני {payload.referral_fee_type!r} — אפשרי: {', '.join(sorted(REFERRAL_FEE_TYPES))}",
        )
    if payload.referral_fee_status not in REFERRAL_FEE_STATUSES:
        raise LeadValidationError(
            "referral_fee_status",
            f"ערך לא קנוני {payload.referral_fee_status!r} — אפשרי: {', '.join(sorted(REFERRAL_FEE_STATUSES))}",
        )
    if payload.is_referral and not (payload.referrer_id or payload.referrer_name):
        # Rule 4 (no invented completion): "יש הפניה" without saying by whom
        # is an incomplete answer, not a value to guess or leave blank.
        raise LeadValidationError("referrer", "סומן 'הפניה: כן' אך לא צוין מי הפנה (referrer_id/referrer_name)")
    if payload.referral_fee_type != "none" and not payload.is_referral:
        raise LeadValidationError("referral_fee_type", "עמלת הפניה הוגדרה בלי שסומן 'הפניה: כן'")


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
    """Pure field-construction — no I/O, no invented fields. campaign/adset/
    ad and the whole referral group are deliberately NOT written: no column
    for any of them exists in the live Airtable schema (or in
    airtable_schema.py) today — see the audit's marketing-attribution
    findings. Writing them would silently fail the same way
    ad_attribution.py's writes already do; accepting-but-dropping with a
    clear log is the honest Phase 1 choice pending a real attribution-schema
    decision (adding the columns is explicitly out of Phase 1 scope — the
    payload model is locked in now, the live schema catches up later)."""
    if payload.campaign or payload.adset or payload.ad:
        logger.info(
            "[LeadService] campaign attribution fields provided but not written — no live "
            "schema column exists yet (campaign=%r adset=%r ad=%r)",
            payload.campaign, payload.adset, payload.ad,
        )
    if payload.is_referral:
        logger.info(
            "[LeadService] referral fields provided but not written — no live schema column "
            "exists yet (referrer_id=%r referrer_name=%r fee_type=%r fee_value=%r fee_trigger=%r fee_status=%r)",
            payload.referrer_id, payload.referrer_name, payload.referral_fee_type,
            payload.referral_fee_value, payload.referral_fee_trigger, payload.referral_fee_status,
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

    # Owner Contract (hardened per Phase 1 follow-up decision): a Lead is
    # NEVER saved "half-canonical." An unresolvable Owner — whether an
    # explicit owner_user_id that doesn't exist in Profile, or the
    # creator-fallback failing to resolve — blocks creation outright,
    # exactly like a missing name/phone. This replaced an earlier
    # warn-and-proceed fallback, which the audit's own author flagged as
    # contradicting the Owner invariant before this went to main.
    owner_record_id, resolved_owner_user_id = resolve_owner(identity, payload.owner_user_id)
    if not owner_record_id:
        logger.error(
            "[LeadService] Owner could not be resolved for creator=%r (source=%s) — "
            "lead NOT created (Owner invariant is hard-enforced)",
            resolved_owner_user_id, source_module,
        )
        reason = (
            f"owner_user_id: {payload.owner_user_id!r} לא נמצא בטבלת Profile"
            if payload.owner_user_id else
            f"owner: לא ניתן לשייך Owner ליוצר {resolved_owner_user_id!r} — ליד לא נשמר ללא Owner"
        )
        return LeadCreateResult(ok=False, action="invalid", reason=reason)

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

from core.structured_command import build_structured_trigger_re, parse_positional_command

# N18 Phase 2: trigger/delimiter mechanics live in core/structured_command.py
# (shared across future entity writers) — only the trigger words and field
# semantics below are Lead-specific.
_STRUCTURED_TRIGGER_RE = build_structured_trigger_re(r"ליד\s+חדש")

STRUCTURED_COMMAND_HELP = (
    "ליצירת ליד בפורמט מובנה:\n"
    "ליד חדש | שם | טלפון | domain | הערה\n\n"
    "לדוגמה:\n"
    "ליד חדש | עידן מושקוביץ | 0506872216 | recruitment | תשתיות חיצוניות, בעל מספר צוותים\n\n"
    "אפשר גם עם / במקום |.\n\n"
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
    parsed = parse_positional_command(text, _STRUCTURED_TRIGGER_RE)
    if parsed is None or parsed.get("prompt"):
        return parsed

    parts = parsed["parts"]
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


# ══════════════════════════════════════════════════
# Lead Draft Card — the primary creation UX (Phase 1 follow-up)
#
# "ליד חדש" -> an empty card, filled in one field at a time.
# "ליד חדש <free text>" -> a pre-filled card (reusing the SAME candidate
# extraction natural-language capture already uses — never a second
# parser), shown for confirmation before anything is written.
# The pipe-delimited structured command above remains the deterministic
# power-user/testing/integration fallback — unchanged, still an immediate
# write with no draft/confirm step, since it's already fully unambiguous.
# All three converge on create_lead().
# ══════════════════════════════════════════════════

DRAFT_FIELD_ORDER = ("name", "phone", "domain", "source", "note")
DRAFT_REQUIRED_FIELDS = ("name", "phone", "domain")

DRAFT_FIELD_HE = {
    "name": "שם", "phone": "טלפון", "domain": "תחום", "source": "מקור", "note": "הערה",
}

def _domain_prompt_text() -> str:
    numbered = "\n".join(f"{i}. {d}" for i, d in enumerate(CANONICAL_LEAD_DOMAINS_ORDERED, 1))
    return f"מה התחום? בחר/י מספר או הקלד/י שם:\n{numbered}"


DRAFT_FIELD_PROMPT_HE = {
    "name": "מה שם הליד?",
    "phone": "מה מספר הטלפון?",
    "domain": _domain_prompt_text(),
}

# Free-text tokens that identify which field an "ערוך" reply means —
# matched loosely (token appears in the reply), never guessed beyond this
# fixed table.
_DRAFT_EDIT_LABELS: dict[str, str] = {
    "שם": "name",
    "טלפון": "phone", "פלאפון": "phone", "נייד": "phone",
    "תחום": "domain", "domain": "domain",
    "מקור": "source", "source": "source",
    "הערה": "note", "הערות": "note", "note": "note",
}

_SOURCE_BY_CHANNEL = {"telegram": "Telegram", "whatsapp": "WhatsApp"}


def default_source_for_channel(channel: str) -> str:
    return _SOURCE_BY_CHANNEL.get((channel or "").lower(), (channel or "Manual").capitalize())


def new_empty_draft(channel: str) -> dict:
    return {
        "name": "", "phone": "", "domain": "",
        "source": default_source_for_channel(channel), "note": "",
        "channel": channel, "mode": "filling", "awaiting_field": "name",
    }


def build_draft_from_text(text: str, channel: str, router_domain: str = "") -> dict:
    """Builds a pre-filled draft from free text typed right after the
    'ליד חדש' trigger. Reuses core.ingress_classifier's own candidate
    extraction (the SAME extractor natural-language capture uses) for
    name/phone/context, and resolve_domain() for domain — never a second,
    parallel guesser. Domain is only considered "filled" when there is real
    signal (an explicit annotation, or a real non-general Router
    classification) — the bare 'general' fallback is deliberately left
    blank so the user confirms it explicitly, the same principle that
    drove the golden-failure-case fix."""
    name, phone, note = "", "", ""
    try:
        from core.ingress_classifier import classify_ingress
        ic = classify_ingress(text, source_type="text") if text else None
        if ic and ic.tier in (1, 2, 3) and ic.candidates:
            c = ic.candidates[0]
            name = c.get("name", "") or ""
            phone = c.get("phone", "") or ""
            ctx = c.get("context", [])
            note = ", ".join(ctx) if ctx else ""
    except Exception as exc:
        logger.warning("[LeadService] draft prefill extraction failed: %s", exc)

    domain, is_explicit = resolve_domain(text, router_domain)
    domain_confident = is_explicit or (router_domain in CANONICAL_LEAD_DOMAINS and router_domain != "general")
    domain = domain if domain_confident else ""

    draft = new_empty_draft(channel)
    draft.update({"name": name, "phone": phone, "domain": domain, "note": note})
    missing = first_missing_required_field(draft)
    draft["mode"] = "filling" if missing else "review"
    draft["awaiting_field"] = missing
    return draft


def first_missing_required_field(draft: dict) -> Optional[str]:
    for key in DRAFT_REQUIRED_FIELDS:
        if not draft.get(key):
            return key
    return None


def match_edit_field_label(text: str) -> Optional[str]:
    stripped = (text or "").strip()
    return _DRAFT_EDIT_LABELS.get(stripped)


def set_draft_field(draft: dict, field_key: str, raw_value: str) -> tuple[bool, str]:
    """Validates + normalizes a raw reply into draft[field_key]. Returns
    (ok, error_message) — on failure the draft is left untouched and the
    caller must re-ask, never silently accept an invalid value."""
    raw_value = (raw_value or "").strip()

    if field_key == "phone":
        from core.ingress_classifier import _normalize_phone, _PHONE_RE
        if not raw_value or not _PHONE_RE.fullmatch(raw_value.replace(" ", "")):
            return False, f"מספר טלפון לא תקין: {raw_value!r}. נסה שוב."
        draft["phone"] = _normalize_phone(raw_value)
        return True, ""

    if field_key == "domain":
        canonical = resolve_domain_word(raw_value)
        if not canonical:
            return False, (
                f"domain לא מוכר: {raw_value!r}. "
                f"ערכים אפשריים: {', '.join(sorted(CANONICAL_LEAD_DOMAINS))}"
            )
        draft["domain"] = canonical
        return True, ""

    if field_key == "name":
        if not raw_value:
            return False, "שם ריק אינו תקין. מה שם הליד?"
        draft["name"] = raw_value
        return True, ""

    # source / note — free text, no canonical vocabulary to enforce
    draft[field_key] = raw_value
    return True, ""


def render_lead_draft_card(draft: dict) -> str:
    lines = ["📇 ליד חדש", ""]
    for key in DRAFT_FIELD_ORDER:
        value = draft.get(key) or "______"
        lines.append(f"{DRAFT_FIELD_HE[key]}: {value}")
    lines.append("")
    lines.append("ענה/י כן לשמירה, ערוך לשינוי שדה, או לא לביטול.")
    return "\n".join(lines)


def draft_to_payload(draft: dict) -> LeadPayload:
    return LeadPayload(
        name=draft.get("name", ""),
        phone=draft.get("phone", ""),
        domain=draft.get("domain") or "general",
        domain_explicit=True,
        source=draft.get("source") or default_source_for_channel(draft.get("channel", "")),
        channel=draft.get("channel", "telegram"),
        summary=draft.get("note", ""),
    )


# N18 Phase 2: the generic Draft/filling/edit-choice/review state machine
# lives in core/draft_flow.py — this DraftSpec is Lead's own plug-in (field
# semantics only), consumed by core/lead_candidate_handler.py's
# _resolve_lead_draft(). field_prompts is fully populated (not just
# DRAFT_FIELD_PROMPT_HE's 3 required-field entries) so the generic resolver
# never needs entity-aware fallback logic — same fallback text
# ("מה הערך החדש עבור <label>?") the old inline edit_choice branch used for
# source/note, just precomputed once.
_DRAFT_FIELD_PROMPT_FULL_HE = {
    key: DRAFT_FIELD_PROMPT_HE.get(key, f"מה הערך החדש עבור {DRAFT_FIELD_HE[key]}?")
    for key in DRAFT_FIELD_ORDER
}

from core.draft_flow import DraftSpec as _DraftSpec  # noqa: E402

LEAD_DRAFT_SPEC = _DraftSpec(
    required_fields=DRAFT_REQUIRED_FIELDS,
    field_prompts=_DRAFT_FIELD_PROMPT_FULL_HE,
    edit_labels=_DRAFT_EDIT_LABELS,
    set_field=set_draft_field,
    render=render_lead_draft_card,
    unknown_field_message="לא זיהיתי שדה. אילו שדות: שם / טלפון / תחום / מקור / הערה.",
    edit_choice_prompt="איזה שדה לערוך? שם / טלפון / תחום / מקור / הערה.",
)
