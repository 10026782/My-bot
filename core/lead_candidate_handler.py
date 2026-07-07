# core/lead_candidate_handler.py — Section 4B/4C/C89: Deterministic LeadCandidate Handler
#
# Short-circuits the agent loop for explicit owner/staff lead-save patterns.
# Sender identity (אליהו) is immutable; subject (the lead) is resolved separately.
#
# Input flow (C89 Stage 3):
#   classify_ingress() → IngressClassification (tier 1–5)
#   Tier 4/5 → return None (fall through to agent, never auto-write)
#   Tier 1/2 + FEATURE_AUTO_CAPTURE=ON  → write through Gateway → GatewayReply
#   Tier 1/2 + FEATURE_AUTO_CAPTURE=OFF → preview + confirmation required
#   Tier 3   → clear ones write, ambiguous → needs_review message
#
# COG note: reply source_module must be "action_gateway" (set in app.py step 1.45)
# so COG's Single Speaker guard doesn't block the GatewayReply.

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════

_PHONE_RE = re.compile(r"(?:0\d{1,2}[-\s]?\d{7,8}|[\+]?972[-\s]?\d{8,9})")

_SAVE_WORDS = frozenset({
    "תשמור", "שמור", "שמרי", "תרשום", "רשום",
    "תוסיף", "הוסף", "תוסיפי", "save", "add",
    "שמור כליד", "הוסף כליד", "כליד",
})

# מילות עצירה — לא חלק משם פרטי
_NAME_STOP = frozenset({
    "טלפון", "מספר", "פלאפון", "נייד", "תשמור", "שמור", "שמרי",
    "תרשום", "רשום", "תוסיף", "הוסף", "save", "add", "כליד",
    "ליד", "לקוח", "חדש", "בשם", "השם",
    # ערים / מיקומים / פרויקטים — נשמרים כ-context, לא כשם
    "טבריה", "חיפה", "תלאביב", "ירושלים", "נתניה", "אשדוד", "באר", "שבע",
    "רמת", "גן", "פתח", "תקווה", "ראשון", "לציון", "רחובות", "בנייה",
    "פרויקט", "פרוייקט", "דירה", "דירות", "נדלן", "נכס",
})

# Hebrew full-name pattern — שניים עד ארבעה מילים עבריות
_HEBREW_NAME_RE = re.compile(
    r"(?<!\w)([א-ת]{2,}(?:\s+[א-ת]{2,})+)(?!\w)"
)

# Prefixed patterns — highest confidence
_PREFIXED_NAME_RE = re.compile(
    r"""(?:
        אני\s+
        | שמו\s+
        | שמה\s+
        | ליד\s+חדש[:\s]+
        | לקוח\s+חדש[:\s]+
        | תוסיף\s+ל(?!יד\b)   # "תוסיף ל[שם]" but NOT "תוסיף ליד"
        | עדכן\s+את\s+
    )
    ([א-ת]{2,}(?:\s+[א-ת]{2,}){1,3})
    """,
    re.VERBOSE | re.UNICODE,
)

# Domain detection from message content — mirrors domain_router._DOMAIN_RULES
_DOMAIN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"נדל.ן|דירה|דירות|קרקע|נכס|נכסים|שכירות|משכנתא|פינוי|בינוי|apartment|property", re.I), "real_estate"),
    (re.compile(r"יבוא|ייבוא|סין|ספק|מכולה|שילוח|רהיט|import|supplier|china|shipping|furniture", re.I), "import"),
    (re.compile(r"שיווק|מדיה|קמפיין|פרסום|תוכן|סושיאל|instagram|facebook|youtube|marketing|media", re.I), "media"),
    (re.compile(r"saas|מנוי|subscription|פיצ.ר|feature|product|api", re.I), "saas"),
    (re.compile(r"כסף|תזרים|הכנסה|הוצאה|רווח|חשבון|תשלום|חשבונית|finance|revenue|invoice|payment", re.I), "finance"),
]

# Minimal block separator — blank line, bullet, number+dot, or Hebrew item marker
_BLOCK_SEP = re.compile(r"\n\s*\n|\n[-•*]\s+|\n\d+[.)]\s+|\n(?=[א-ת])")


# ══════════════════════════════════════════════════
# Domain detection
# ══════════════════════════════════════════════════

def _detect_domain(text: str, identity_domain: str = "") -> str:
    """
    מזהה דומיין מתוכן ההודעה.
    חוזר ל-identity_domain אם לא נמצא במלל, ולבסוף "general".
    """
    for pattern, domain in _DOMAIN_PATTERNS:
        if pattern.search(text):
            return domain
    if identity_domain and identity_domain != "general":
        return identity_domain
    return "general"


# ══════════════════════════════════════════════════
# Name / phone extraction
# ══════════════════════════════════════════════════

def _extract_phone(text: str) -> str:
    """מחלץ מספר טלפון ראשון ומנרמל לפורמט ישראלי."""
    m = _PHONE_RE.search(text)
    if not m:
        return ""
    raw = re.sub(r"[\s\-]", "", m.group())
    if raw.startswith("+972"):
        raw = "0" + raw[4:]
    elif raw.startswith("972"):
        raw = "0" + raw[3:]
    return raw


def _extract_all_phones(text: str) -> list[str]:
    """מחלץ את כל מספרי הטלפון מהטקסט."""
    results = []
    for m in _PHONE_RE.finditer(text):
        raw = re.sub(r"[\s\-]", "", m.group())
        if raw.startswith("+972"):
            raw = "0" + raw[4:]
        elif raw.startswith("972"):
            raw = "0" + raw[3:]
        results.append(raw)
    return results


def _has_save_intent(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in _SAVE_WORDS)


def _clean_name(raw: str) -> str:
    """מסיר מילות עצירה מסוף השם."""
    words = raw.strip().rstrip(",;:").split()
    while words and words[-1] in _NAME_STOP:
        words.pop()
    return " ".join(words)


def _extract_name(text: str) -> Optional[str]:
    """
    מחלץ שם ליד עברי מלא.
    מועדף: prefix מפורש. Fallback: שם עברי כפול ללא מילות מיקום/עצירה.
    """
    # Prefixed (highest confidence)
    m = _PREFIXED_NAME_RE.search(text)
    if m:
        name = _clean_name(m.group(1))
        words = name.split()
        if len(name) >= 4 and " " in name and not any(w in _NAME_STOP for w in words):
            return name

    # Fallback — Hebrew multi-word sequence, filtered
    _STOP_ALL = _NAME_STOP | {"לא", "אני", "כן", "גם", "של", "עם", "על", "את",
                               "הוא", "היא", "הם", "אנחנו", "אתם"}
    for m in _HEBREW_NAME_RE.finditer(text):
        raw = m.group(1).strip()
        name = _clean_name(raw)
        words = name.split()
        if len(words) >= 2 and len(name) >= 4:
            if not any(w in _STOP_ALL for w in words):
                return name
    return None


def _extract_context_keywords(text: str, name: str, phone: str) -> list[str]:
    """
    מחלץ מילות הקשר (עיר/פרויקט/נושא) שאינן חלק מהשם.
    לדוגמה: "גבי אקבשב דרייבר 0539332665 טבריה" → ["טבריה"]
    """
    # Remove name and phone from text, then scan for location/project words
    cleaned = text
    if name:
        cleaned = cleaned.replace(name, " ")
    if phone:
        cleaned = _PHONE_RE.sub(" ", cleaned)
    # Location/project stop-words that ARE context keywords (subset of _NAME_STOP)
    _CONTEXT_WORDS = {
        "טבריה", "חיפה", "ירושלים", "נתניה", "אשדוד", "רחובות",
        "פרויקט", "פרוייקט", "דירה", "דירות", "נדלן", "נכס",
        "בנייה",
    }
    found = []
    for word in re.findall(r"[א-ת]{2,}", cleaned):
        if word in _CONTEXT_WORDS and word not in found:
            found.append(word)
    return found


# ══════════════════════════════════════════════════
# Single-lead parse
# ══════════════════════════════════════════════════

def parse_lead_dictation(text: str) -> Optional[dict]:
    """
    מחלץ {name, phone, context, needs_phone} מהודעת הכתבת ליד בודדת.
    מחזיר None אם אין תבנית ברורה.
    """
    if not text:
        return None

    name = _extract_name(text)
    if not name:
        return None

    phone   = _extract_phone(text)
    context = _extract_context_keywords(text, name, phone)

    has_phone = bool(phone)
    has_save  = _has_save_intent(text)

    if not has_phone and not has_save:
        return None

    if not has_phone and has_save:
        return {"name": name, "phone": "", "context": context, "raw_text": text, "needs_phone": True}

    return {"name": name, "phone": phone, "context": context, "raw_text": text, "needs_phone": False}


# ══════════════════════════════════════════════════
# Batch parse (Section 4C)
# ══════════════════════════════════════════════════

def parse_batch_dictation(text: str) -> list[dict]:
    """
    מנסה לחלץ מספר ליד-בלוקים מהודעה אחת.
    מחזיר רשימה של {name, phone, context} רק אם יש ≥2 בלוקים ברורים.
    אחרת מחזיר רשימה ריקה (→ fallback ל-parse_lead_dictation).

    בלוק = שם עברי + טלפון בקרבה (עד 60 תווים לפני/אחרי).
    """
    # אסטרטגיה: מצא את כל מספרי הטלפון, ולכל אחד חפש שם עברי בסביבתו
    candidates: list[dict] = []
    seen_phones: set[str] = set()

    for phone_match in _PHONE_RE.finditer(text):
        raw_phone = re.sub(r"[\s\-]", "", phone_match.group())
        if raw_phone.startswith("+972"):
            raw_phone = "0" + raw_phone[4:]
        elif raw_phone.startswith("972"):
            raw_phone = "0" + raw_phone[3:]

        if raw_phone in seen_phones:
            continue
        seen_phones.add(raw_phone)

        # חלון טקסט סביב הטלפון
        start  = max(0, phone_match.start() - 60)
        end    = min(len(text), phone_match.end() + 60)
        window = text[start:end]

        name = _extract_name(window)
        if not name:
            continue

        context = _extract_context_keywords(window, name, raw_phone)
        candidates.append({"name": name, "phone": raw_phone, "context": context})

    # החזר רק אם ≥2 בלוקים שונים
    if len(candidates) >= 2:
        return candidates
    return []


# ══════════════════════════════════════════════════
# Airtable search
# ══════════════════════════════════════════════════

def _at_find_lead(name: str, phone: str) -> Optional[str]:
    """מחפש ליד קיים לפי שם + טלפון. מחזיר record_id או None."""
    import os
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    key  = os.environ.get("AIRTABLE_API_KEY", "")
    if not base or not key:
        return None

    url     = f"https://api.airtable.com/v0/{base}/{urllib.parse.quote('Leads', safe='')}"
    headers = {"Authorization": f"Bearer {key}"}

    for formula in _search_formulas(name, phone):
        try:
            r = httpx.get(url, headers=headers,
                          params={"filterByFormula": formula, "maxRecords": 5},
                          timeout=8)
            if r.status_code == 200:
                records = r.json().get("records", [])
                if records:
                    # prefer exact phone match
                    if phone:
                        for rec in records:
                            rec_phone = re.sub(r"[\s\-]", "", str(rec.get("fields", {}).get("phone", "")))
                            if rec_phone == phone:
                                return rec["id"]
                    return records[0]["id"]
        except Exception as exc:
            logger.warning("[LCH] Airtable search error: %s", exc)

    return None


def _search_formulas(name: str, phone: str) -> list[str]:
    from tools.airtable_gateway import _safe_formula_param
    safe_name = _safe_formula_param(name)
    formulas  = []
    if phone:
        safe_phone = _safe_formula_param(phone)
        formulas.append(f"AND(SEARCH('{safe_name}', {{Name}}), {{phone}}='{safe_phone}')")
        formulas.append(f"{{phone}}='{safe_phone}'")
    formulas.append(f"SEARCH('{safe_name}', {{Name}})")
    return formulas


# ══════════════════════════════════════════════════
# Single-lead write
# ══════════════════════════════════════════════════

def _write_one_lead(
    identity,
    name: str,
    phone: str,
    text: str,
    channel: str,
    domain: str,
) -> tuple[bool, str, str]:
    """
    מוצא (או יוצר/מעדכן) ליד אחד.
    מחזיר (ok, record_id, action) — action = "create" | "update".
    """
    tenant_id = getattr(identity, "tenant_id", "default") or "default"

    # memory_key — phone-based so future inbound from same phone matches
    _phone_key = re.sub(r"[\s\-\+]", "", phone)
    memory_key = (
        f"{tenant_id}/{_phone_key}@lead"
        if _phone_key
        else f"{tenant_id}/dict_{re.sub(chr(32), '_', name.lower()[:20])}@lead"
    )

    existing_id = _at_find_lead(name, phone)
    action      = "update" if existing_id else "create"

    # Gateway dedup check
    contract_id = None
    try:
        from core.action_gateway import action_gateway as _gw, _ledger_singleton
        _tool = "airtable_update" if action == "update" else "airtable_add"
        _inputs = {"table": "Leads", "name": name, "phone": phone}
        if existing_id:
            _inputs["record_id"] = existing_id
        gw_result = _gw.propose_action(
            tenant_id         = tenant_id,
            canonical_user_id = identity.memory_key,
            tool_name         = _tool,
            tool_inputs       = _inputs,
            origin_channel    = channel,
            origin_chat_id    = identity.memory_key,
            requires_approval = False,
            identity          = identity,
        )
        if not gw_result.ok:
            logger.info("[LCH] gateway blocked for %r: %s", name, gw_result.reason)
            return False, "", "duplicate"
        contract_id = gw_result.contract_id
    except Exception as exc:
        logger.warning("[LCH] gateway propose failed: %s", exc)

    # Write
    record_id = ""
    ok        = False
    try:
        from tools.airtable_gateway import airtable_create, airtable_patch
        from airtable_schema import LeadFields
        _domain_key = domain if (domain and domain != "general") else "general"

        if action == "update" and existing_id:
            patch_fields = {
                LeadFields.PHONE:   phone,
                LeadFields.SUMMARY: text[:500],
            }
            if _domain_key != "general":
                patch_fields[LeadFields.DOMAIN] = _domain_key
            ok_patch = airtable_patch("Leads", existing_id, patch_fields,
                                      source="lead_candidate_handler")
            if ok_patch:
                record_id = existing_id
                ok = True
        else:
            _domain_key = domain if (domain and domain != "general") else "general"
            lead_fields = {
                LeadFields.NAME:       name,
                LeadFields.PHONE:      phone,
                LeadFields.CHANNEL:    channel,
                LeadFields.MEMORY_KEY: memory_key,
                LeadFields.DOMAIN:     _domain_key,
                LeadFields.SOURCE:     "owner_dictation",
                LeadFields.STATUS:     "new",
                LeadFields.SUMMARY:    text[:500],
                LeadFields.SCORE:      0,
                LeadFields.SENDER_ID:  phone,
            }
            rec = airtable_create("Leads", lead_fields,
                                  source="lead_candidate_handler")
            if rec:
                record_id = rec.get("id", "")
                ok = bool(record_id)
    except Exception as exc:
        logger.error("[LCH] write failed for %r: %s", name, exc)

    # Update ledger
    if contract_id:
        try:
            from core.action_gateway import _ledger_singleton
            _ledger_singleton.update_status(contract_id, "executed" if ok else "failed")
            if ok and record_id:
                c = _ledger_singleton.find_by_id(contract_id)
                if c:
                    import time as _t
                    c.agent_observations.append({"kind": "execution_fact", "record_id": record_id, "created_at": _t.time()})
        except Exception as exc:
            logger.warning("[LCH] ledger update failed: %s", exc)

    # Post-write enrichment (non-blocking, flag-gated)
    if ok and record_id:
        _domain_key = domain if (domain and domain != "general") else "general"
        try:
            from lead_capture import capture_lead_event
            from feature_flags import is_enabled as _flag
            if _flag("LEAD_CAPTURE"):
                capture_lead_event(identity, text, record_id, domain=_domain_key)
        except Exception as exc:
            logger.warning("[LCH] lead_event failed: %s", exc)

        try:
            from feature_flags import is_enabled as _flagm
            if _flagm("LEAD_MEMORY"):
                from lead_memory import lead_memory
                lead_memory.update(memory_key, domain=_domain_key, channel=channel,
                                   contact_name=name, last_message=text, summary=text[:500])
        except Exception as exc:
            logger.warning("[LCH] lead_memory failed: %s", exc)

        if action == "create":
            try:
                from feature_flags import is_enabled as _flags
                if _flags("LEAD_SCORING"):
                    from lead_capture import _score_inbound_message
                    from tools.airtable_gateway import airtable_patch as _gw_patch
                    from airtable_schema import LeadFields as _LF
                    score, _, _ = _score_inbound_message(text, identity)
                    _gw_patch("Leads", record_id, {_LF.SCORE: score},
                              source="lead_candidate_handler_scoring")
            except Exception as exc:
                logger.warning("[LCH] scoring failed: %s", exc)

    return ok, record_id, action


# ══════════════════════════════════════════════════
# BUG-056 — Tier 1 preview confirmation via Action Gateway
# ══════════════════════════════════════════════════

def _propose_lead_write(
    identity,
    name: str,
    phone: str,
    text: str,
    channel: str,
    domain: str,
):
    """
    Tier 1 preview (auto_write=False): proposes a REAL pending ActionContract
    via ActionGateway instead of writing directly or storing dead session
    state. "כן" resolves it through ActionGateway.approve() -> dispatch_tool()
    (app.py's confirm-word handling checks Gateway live contracts first,
    regardless of FEATURE_ACTION_GATEWAY) — so the confirmed write goes
    through the same dispatcher path as any other approved tool call, not a
    direct one-off airtable_add. "_source": "lead_capture" is required to
    pass tools/dispatcher.py's enforce_leads_write_gate() for table=Leads.

    Returns the GatewayResult (ok / contract_id / user_message) from
    propose_action() — dedup (pending/already-executed) is handled entirely
    by the Gateway's business-fingerprint match, same as _write_one_lead().
    """
    from core.action_gateway import action_gateway as _gw
    from airtable_schema import LeadFields

    tenant_id   = getattr(identity, "tenant_id", "default") or "default"
    existing_id = _at_find_lead(name, phone)
    _domain_key = domain if (domain and domain != "general") else "general"

    if existing_id:
        tool_name = "airtable_update"
        fields: dict = {LeadFields.PHONE: phone, LeadFields.SUMMARY: text[:500]}
        if _domain_key != "general":
            fields[LeadFields.DOMAIN] = _domain_key
        tool_inputs = {
            "table": "Leads", "record_id": existing_id,
            "fields": fields, "_source": "lead_capture",
        }
    else:
        _phone_key = re.sub(r"[\s\-\+]", "", phone)
        memory_key = (
            f"{tenant_id}/{_phone_key}@lead"
            if _phone_key
            else f"{tenant_id}/dict_{re.sub(chr(32), '_', name.lower()[:20])}@lead"
        )
        tool_name = "airtable_add"
        fields = {
            LeadFields.NAME:       name,
            LeadFields.PHONE:      phone,
            LeadFields.CHANNEL:    channel,
            LeadFields.MEMORY_KEY: memory_key,
            LeadFields.DOMAIN:     _domain_key,
            LeadFields.SOURCE:     "owner_dictation",
            LeadFields.STATUS:     "new",
            LeadFields.SUMMARY:    text[:500],
            LeadFields.SCORE:      0,
            LeadFields.SENDER_ID:  phone,
        }
        tool_inputs = {"table": "Leads", "fields": fields, "_source": "lead_capture"}

    return _gw.propose_action(
        tenant_id         = tenant_id,
        canonical_user_id = identity.memory_key,
        tool_name         = tool_name,
        tool_inputs       = tool_inputs,
        origin_channel    = channel,
        origin_chat_id    = identity.memory_key,
        requires_approval = True,
        identity          = identity,
    )


# ══════════════════════════════════════════════════
# Main handler — called from app.py step 1.45
# ══════════════════════════════════════════════════

def handle_lead_candidate(
    identity,
    text: str,
    chat_id: str,
    channel: str,
    domain: str = "",
    ic=None,
) -> Optional[str]:
    """
    מטפל דטרמיניסטית בהכתבת ליד (בודד או batch) של owner/staff.
    מחזיר GatewayReply string אם הפעולה הסתיימה, None אם לא תבנית — ממשיך לאייג'נט.

    C89: כל קלט עובר classify_ingress() לפני כל פרסור.
    Tier 4/5 → None (אסור לכתוב, מועבר לאייג'נט).
    Tier 1/2 + FEATURE_AUTO_CAPTURE → auto-write.
    Tier 3   → ברורים נכתבים, עמומים → needs_review.
    source_module בapp.py מוגדר ל-"action_gateway" כדי שCOG יאשר.

    domain: route.domain מ-core/router/router.py (Router רץ עכשיו *לפני*
    שהandler הזה נקרא — ראה app.py). כשמועבר, גובר על ה-content-regex guess
    המקומי (_detect_domain) — זו התוצאה האמיתית מ-domain_router, לא ניחוש
    כפול. ריק כברירת מחדל לכל caller אחר / תאימות לאחור.

    ic: IngressClassification מוכן מראש (route.capture_ic מ-router.py) —
    כשמועבר, נחסך classify_ingress() כפול על אותו טקסט (BUG-056). ריק
    כברירת מחדל — מסווג בעצמו, לתאימות לאחור לכל caller אחר / לבדיקות.
    """
    if not getattr(identity, "is_internal", False):
        return None

    # ── domain: Router (route.domain) is the source of truth when passed in;
    #    _detect_domain() stays as the fallback for any other caller ──────
    domain = domain or _detect_domain(text, getattr(identity, "domain_id", "general"))

    # ── Follow-up on stored batch? ────────────────
    _follow_up_reply = _handle_batch_followup(identity, text, chat_id, channel, domain)
    if _follow_up_reply is not None:
        return _follow_up_reply

    # ── C89: Input Source Gate — classify before parse ──
    if ic is None:
        try:
            from core.ingress_classifier import classify_ingress, log_classification
            ic = classify_ingress(text, source_type="text")
            log_classification(ic, chat_id=chat_id)
        except Exception as exc:
            logger.warning("[LCH] ingress_classifier failed (falling through to agent): %s", exc)
            return None

    # Tier 4 (table/export/bot output) or Tier 5 (no signal) → agent handles it
    if ic.tier >= 4:
        logger.info("[LCH] Tier %d — not a lead dictation (reason=%s), skip", ic.tier, ic.reason)
        return None

    # ── Tier 1/2/3 routing ───────────────────────
    from feature_flags import is_enabled as _flag
    auto_capture = _flag("FEATURE_AUTO_CAPTURE")

    candidates = list(ic.candidates)  # tuple → list for mutability

    if ic.tier == 1:
        # Single high-confidence lead
        c = candidates[0]
        return _handle_single_candidate(
            identity, c, text, chat_id, channel, domain, auto_write=auto_capture
        )

    if ic.tier == 2:
        # All candidates high-confidence batch
        return _handle_clean_batch(
            identity, candidates, text, chat_id, channel, domain, auto_write=auto_capture
        )

    if ic.tier == 3:
        # Mixed: high-confidence ones write, low ones → needs_review
        high = [c for c in candidates if c["confidence"] >= 0.75]
        low  = [c for c in candidates if c["confidence"] <  0.75]
        return _handle_mixed_batch(
            identity, high, low, text, chat_id, channel, domain, auto_capture=auto_capture
        )

    return None


# ══════════════════════════════════════════════════
# Tier-routing handlers (C89)
# ══════════════════════════════════════════════════

def _should_auto_write(auto_capture: bool, existing_id: Optional[str]) -> bool:
    """
    C89 gate, מאוחד לכל ה-Tiers: כתיבה אוטומטית רק ל-lead חדש לגמרי,
    וגם auto_capture דלוק. עדכון ליד קיים (existing_id) תמיד עובר אישור,
    ללא קשר ל-flag — עקבי עם BUG-074/076.
    """
    return auto_capture and not existing_id


def _handle_single_candidate(
    identity,
    candidate: dict,
    text: str,
    chat_id: str,
    channel: str,
    domain: str,
    auto_write: bool,
) -> Optional[str]:
    """
    Tier 1: ליד בודד high-confidence.
    auto_write=True (FEATURE_AUTO_CAPTURE) → כותב מיד ליד חדש.
    עדכון ליד קיים (airtable_update) תמיד עובר דרך אישור — גם כש-auto_write=True
    (C89 UX: לעולם לא לעדכן ליד קיים בלי אישור מפורש).
    auto_write=False → מחזיר preview ומאחסן ActionContract ממתין.
    """
    name  = candidate["name"]
    phone = candidate.get("phone", "")
    ctx   = candidate.get("context", [])

    if not phone:
        return f"כדי לשמור את {name} כליד — אשמח לקבל גם מספר טלפון. 📞"

    existing_id = _at_find_lead(name, phone)

    if not _should_auto_write(auto_write, existing_id):
        # BUG-056: preview mode now proposes a REAL pending ActionContract
        # (instead of the dead-end session["pending_lead_preview"]) so "כן"
        # can actually resolve it — see _propose_lead_write() + app.py's
        # confirm-word handling (checks ActionGateway live contracts first).
        # C89 UX: an existing lead (airtable_update) always goes through this
        # approval branch, even when FEATURE_AUTO_CAPTURE=true — only a
        # brand-new lead (airtable_add) can auto-write below.
        gw_result = _propose_lead_write(identity, name, phone, text, channel, domain)
        if not gw_result.ok:
            # Already-pending or duplicate-executed — Gateway's own message
            # (dedup by business fingerprint) is the correct user-facing reply.
            return gw_result.user_message or gw_result.reason
        ctx_str = f" [{', '.join(ctx)}]" if ctx else ""
        if existing_id:
            return (
                f"📋 מצאתי ליד קיים: *{name}* ({phone}){ctx_str}\n"
                f"לעדכן אותו? ענה *כן* לאישור או *לא* לביטול."
            )
        return (
            f"📋 זיהיתי ליד: *{name}* ({phone}){ctx_str}\n"
            f"לשמור? ענה *כן* לאישור או *לא* לביטול."
        )

    ok, record_id, action = _write_one_lead(identity, name, phone, text, channel, domain)

    if ok and record_id:
        try:
            from session_store import lead_sessions as _ls
            _ls.set_active_lead_candidate(chat_id, name, record_id=record_id)
            _ls.set_current_lead_record_id(chat_id, record_id)
        except Exception as exc:
            logger.warning("[LCH] session persist failed: %s", exc)

    if not ok:
        return f"❌ לא הצלחתי לשמור את {name}. נסה שוב."

    ctx_str = _context_suffix(ctx, domain)
    if action == "update":
        return f"✅ עדכנתי את {name} ({phone}){ctx_str} | {record_id}"
    return f"✅ שמרתי את {name} ({phone}){ctx_str} כליד חדש | {record_id}"


def _handle_clean_batch(
    identity,
    candidates: list[dict],
    text: str,
    chat_id: str,
    channel: str,
    domain: str,
    auto_write: bool,
) -> str:
    """
    Tier 2: כל הלידים high-confidence.
    auto_write=True → כותב הכל + סיכום.
    auto_write=False → BUG-058: תצפית בלבד — אין resolver ל-batch confirm
    (ראה _store_pending_preview), אז ההודעה לא רומזת שאישור קבוצתי אפשרי.
    """
    if not _should_auto_write(auto_write, None):
        _store_pending_preview(chat_id, candidates, text)
        lines = [
            f"• {c['name']} ({c['phone']})" + (f" [{', '.join(c['context'])}]" if c.get("context") else "")
            for c in candidates
        ]
        return (
            f"📋 זיהיתי {len(candidates)} לידים אפשריים בקבוצה:\n" +
            "\n".join(lines) +
            "\n\nלא שמרתי אותם ולא נפתחה פעולת אישור קבוצתית.\n"
            "אישור קבוצתי עדיין לא זמין.\n"
            "כדי לשמור ליד, שלח ליד אחד בכל פעם או בקש ממני להכין רשימה לבדיקה."
        )

    # auto-write
    return _handle_batch(identity, text, chat_id, channel, domain, candidates)


def _handle_mixed_batch(
    identity,
    high: list[dict],
    low: list[dict],
    text: str,
    chat_id: str,
    channel: str,
    domain: str,
    auto_capture: bool,
) -> str:
    """
    Tier 3: חלק ברור (high), חלק עמום (low).
    high + lead חדש + auto_capture דלוק → נכתב מיד.
    high + (ליד קיים, או auto_capture כבוי) → עובר אישור כמו Tier 1
    (BUG-077 fix: קודם נכתב תמיד ללא תלות ב-existing_id/flag — הפרה של
    אותו gate שקיים כבר ב-Tier 1/2).
    low (עמומים) → needs_review + הודעה, ללא שינוי.
    """
    results = []
    written = 0
    pending = 0
    for c in high:
        existing_id = _at_find_lead(c["name"], c["phone"])
        ctx_str = _context_suffix(c.get("context", []), domain)
        if _should_auto_write(auto_capture, existing_id):
            ok, record_id, action = _write_one_lead(
                identity, c["name"], c["phone"], text, channel, domain
            )
            if ok and record_id:
                verb = "עדכנתי" if action == "update" else "שמרתי"
                results.append(f"✅ {verb} את {c['name']} ({c['phone']}){ctx_str}")
                written += 1
            else:
                results.append(f"❌ {c['name']} ({c['phone']}) — לא נשמר")
        else:
            gw_result = _propose_lead_write(
                identity, c["name"], c["phone"], text, channel, domain
            )
            if gw_result.ok:
                verb = "לעדכון" if existing_id else "לשמירה"
                results.append(
                    f"📋 {c['name']} ({c['phone']}){ctx_str} — ממתין לאישור ({verb}). ענה *כן* לאשר."
                )
                pending += 1
            else:
                results.append(
                    f"❌ {c['name']} ({c['phone']}) — {gw_result.user_message or gw_result.reason}"
                )

    needs_review_lines = [
        f"⏳ {c['name'] or '?'} ({c['phone']}) — confidence נמוך, ממתין לבדיקה"
        for c in low
    ]

    lines = results + needs_review_lines
    header = f"📋 עובדתי {len(high) + len(low)} לידים:"
    parts = []
    if written:
        parts.append(f"{written} נשמרו")
    if pending:
        parts.append(f"{pending} ממתינים לאישור")
    if needs_review_lines:
        parts.append(f"{len(low)} ממתינים לבדיקה")
    if parts:
        header += " " + ", ".join(parts)
    return header + "\n" + "\n".join(lines)


# ── Pending preview store (FEATURE_AUTO_CAPTURE=OFF) ──────────────────────────

def _store_pending_preview(chat_id: str, candidates: list[dict], raw_text: str) -> None:
    """שומר preview של batch (Tier 2) ב-session — audit/future-design בלבד.

    INTENTIONAL (BUG-058): no resolver yet — batch-confirm design pending.
    Do not treat this as a live contract like Tier 1's ActionGateway contract
    (_propose_lead_write). Nothing in the codebase reads pending_lead_preview
    back; "כן"/"לא" never resolve it. Kept written (not removed) so the field
    is available for audit and for whatever resolver design eventually lands.
    The caller (_handle_clean_batch) is responsible for not implying to the
    user that a confirmation action exists for this state.

    BUG-056: היה `_ls.get(chat_id)` — מחזיר None בשקט ב-session חדש (סשן ראשון
    של chat_id), ואז ה-preview לעולם לא נשמר בפועל. `get_or_create()` מבטיח
    ש-session תמיד קיים לפני הכתיבה.
    """
    try:
        from session_store import lead_sessions as _ls
        session = _ls.get_or_create(chat_id)
        session["pending_lead_preview"] = {
            "candidates": candidates,
            "raw_text":   raw_text,
        }
        _ls._sync_to_db(chat_id, session)
    except Exception as exc:
        logger.warning("[LCH] pending_preview store failed: %s", exc)


# ══════════════════════════════════════════════════
# Batch handler (Section 4C / Tier 2 auto-write)
# ══════════════════════════════════════════════════

def _handle_batch(
    identity,
    text: str,
    chat_id: str,
    channel: str,
    domain: str,
    batch: list[dict],
) -> str:
    """מעבד batch של לידים ומחזיר סיכום per-lead."""
    results = []
    for item in batch:
        name  = item["name"]
        phone = item["phone"]
        ok, record_id, action = _write_one_lead(identity, name, phone, text, channel, domain)
        ctx = _context_suffix(item.get("context", []), domain)
        if ok and record_id:
            verb = "עדכנתי" if action == "update" else "שמרתי"
            results.append({"name": name, "phone": phone, "ok": True,
                            "record_id": record_id, "action": action,
                            "line": f"✅ {verb} את {name} ({phone}){ctx} | {record_id}"})
        else:
            results.append({"name": name, "phone": phone, "ok": False,
                            "record_id": "", "action": "failed",
                            "line": f"❌ {name} ({phone}) — לא נשמר"})

    # Persist batch state to session for follow-up routing
    _save_batch_state(chat_id, text, results)

    # Session — first successful lead as current
    for r in results:
        if r["ok"] and r["record_id"]:
            try:
                from session_store import lead_sessions as _ls
                _ls.set_active_lead_candidate(chat_id, r["name"], record_id=r["record_id"])
                _ls.set_current_lead_record_id(chat_id, r["record_id"])
            except Exception:
                pass
            break

    # Summary reply
    total   = len(results)
    success = sum(1 for r in results if r["ok"])
    failed  = total - success
    lines   = [r["line"] for r in results]

    header = f"📋 עובדתי {total} לידים"
    if failed:
        header += f" — {success} נשמרו, {failed} נכשלו"
    lines_str = "\n".join(lines)
    return f"{header}:\n{lines_str}"


def _context_suffix(context: list[str], domain: str) -> str:
    if context:
        return f" [{', '.join(context)}]"
    return ""


# ══════════════════════════════════════════════════
# Batch session state + follow-up routing (Section 4C)
# ══════════════════════════════════════════════════

_FOLLOWUP_WORDS = frozenset({
    "ומה", "השאר", "שאר", "הנותרים", "נותרים", "שאר הלידים",
    "שאר הרשימה", "מה עם השאר", "מה עם הנותרים",
})


def _save_batch_state(chat_id: str, original_text: str, results: list[dict]) -> None:
    """שומר מצב ה-batch ל-session לצורך follow-up."""
    try:
        from session_store import lead_sessions as _ls
        session = _ls.get(chat_id)
        if session is None:
            return
        session["last_lead_candidate_batch"] = {
            "original_message_text": original_text,
            "detected_count":  len(results),
            "processed_count": len(results),
            "per_lead": [
                {
                    "name":      r["name"],
                    "phone":     r["phone"],
                    "record_id": r.get("record_id", ""),
                    "action":    r["action"],
                    "ok":        r["ok"],
                }
                for r in results
            ],
        }
        _ls._sync_to_db(chat_id, session)
    except Exception as exc:
        logger.warning("[LCH] batch state save failed: %s", exc)


def _handle_batch_followup(
    identity,
    text: str,
    chat_id: str,
    channel: str,
    domain: str,
) -> Optional[str]:
    """
    אם ההודעה היא follow-up על batch קיים ("ומה עם השאר?") —
    מחזיר תשובה מבוססת על מצב ה-batch השמור.
    """
    lower = text.strip().lower()
    if not any(w in lower for w in _FOLLOWUP_WORDS):
        return None

    try:
        from session_store import lead_sessions as _ls
        session = _ls.get(chat_id)
        if not session:
            return None
        batch_state = session.get("last_lead_candidate_batch")
        if not batch_state:
            return None
    except Exception:
        return None

    per_lead   = batch_state.get("per_lead", [])
    failed     = [l for l in per_lead if not l.get("ok")]
    succeeded  = [l for l in per_lead if l.get("ok")]

    if not failed:
        success_names = ", ".join(l["name"] for l in succeeded)
        return f"✅ כל הלידים מהרשימה נשמרו בהצלחה: {success_names}"

    lines = []
    for l in failed:
        lines.append(f"❌ {l['name']} ({l['phone']}) — לא נשמר")
    for l in succeeded:
        lines.append(f"✅ {l['name']} ({l['phone']}) — {l['record_id']}")

    return f"מצב הרשימה ({len(per_lead)} לידים):\n" + "\n".join(lines)
