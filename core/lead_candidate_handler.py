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

# BUG-094-C: RouterDomain values that are routing/meta concepts, not business
# verticals — never valid values for Airtable's Leads/Lead Events "Domain"
# singleSelect field (live schema: real_estate/import/recruiting/general).
# core/router/domain_router.py classifies any message containing "ליד"/"lead"/
# "crm" as RouterDomain.CRM (0.85 confidence) — which a batch lead-dictation
# message like "ליד חדש: ..." naturally contains, so resolved_route_domain
# reaching handle_lead_candidate() can legitimately be "crm". Writing that
# straight into the Domain field 422s on Lead Events (Airtable rejects the
# value outright) and is meaningless on Leads either way — "crm"/"internal"
# describe the *routing intent*, not which business the lead belongs to.
_NON_BUSINESS_DOMAINS = frozenset({"crm", "internal"})


def _lead_domain_key(domain: str) -> str:
    """Normalizes a Router domain into a value safe to write to Airtable's
    Leads/Lead Events Domain field — meta-domains (crm/internal) and empty
    values fall back to 'general', same as the pre-existing empty-domain
    fallback."""
    if not domain or domain in _NON_BUSINESS_DOMAINS:
        return "general"
    return domain


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
    # BUG-111: recruiting/גיוס — a live Leads/Lead Events Domain value
    # ("recruitment", see airtable_schema.py) that had no detector at all.
    # Deliberately narrow ("candidate"/"מועמד" excluded — too generic, would
    # false-positive on unrelated usage, e.g. "the candidate apartment").
    (re.compile(r"גיוס|מגייס|מגייסת|recruiting|recruitment", re.I), "recruitment"),
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

    BUG-111: an explicit "דומיין X"/"לדומיין X" command annotation (e.g.
    "צור ליד דומיין גיוס ...") is a higher-precision signal than the generic
    content-keyword scan below — checked first via the SAME extractor/mapping
    ingress_classifier.py uses for candidates (core.ingress_classifier.
    _extract_domain_hint), so an explicit hint and the routing value actually
    used here can never drift apart. Falls through to the content scan when
    no explicit annotation is present or its hint word has no known mapping.
    """
    try:
        from core.ingress_classifier import _extract_domain_hint
        explicit_hint = _extract_domain_hint(text)
    except Exception:
        explicit_hint = None
    if explicit_hint:
        return explicit_hint

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

    בלוק = שם עברי + טלפון בקרבה (עד 60 תווים לפני/אחרי, לא חוצה למספר
    הטלפון השכן — ראה BUG-094). מ-BUG-095: הטקסט מפוצל קודם ל-_BLOCK_SEP
    (שורה חדשה שמתחילה באות עברית / bullet / מספור / שורה ריקה) — כל בלוק
    מעובד בנפרד לגמרי, כדי שטלפון פגום/לא-ניתן-לזיהוי בבלוק אחד לא "יבלע"
    לתוך החלון של הבלוק הבא (ראה תיעוד `_extract_batch_candidates_from_block`
    ו-BUG-095 ב-BUG_AUDIT_LOG.md).
    """
    candidates: list[dict] = []
    seen_phones: set[str] = set()

    for block in _BLOCK_SEP.split(text):
        if not block.strip():
            continue
        _extract_batch_candidates_from_block(block, candidates, seen_phones)

    # החזר רק אם ≥2 בלוקים שונים
    if len(candidates) >= 2:
        return candidates
    return []


def _extract_batch_candidates_from_block(
    block: str, candidates: list[dict], seen_phones: set[str],
) -> None:
    """
    מחלץ candidates מתוך בלוק בודד (כבר מפוצל ע"י _BLOCK_SEP) ומוסיף ל-candidates.

    בתוך בלוק בודד יכולים עדיין להיות כמה זוגות שם+טלפון (למשל שורה אחת עם
    כמה לידים מופרדים בפסיקים) — לכן עדיין נדרש אותו windowing per-phone
    (BUG-094): החלון מוגבל גם לגבולות הטלפון השכן *בתוך הבלוק הזה בלבד*,
    לא חוצה בין בלוקים (ראה BUG-095) ולא רק ל-±60 תווים קבוע.
    """
    phone_matches = list(_PHONE_RE.finditer(block))
    for i, phone_match in enumerate(phone_matches):
        raw_phone = re.sub(r"[\s\-]", "", phone_match.group())
        if raw_phone.startswith("+972"):
            raw_phone = "0" + raw_phone[4:]
        elif raw_phone.startswith("972"):
            raw_phone = "0" + raw_phone[3:]

        if raw_phone in seen_phones:
            continue
        seen_phones.add(raw_phone)

        prev_end   = phone_matches[i - 1].end() if i > 0 else 0
        next_start = phone_matches[i + 1].start() if i + 1 < len(phone_matches) else len(block)
        start  = max(0, phone_match.start() - 60, prev_end)
        end    = min(len(block), phone_match.end() + 60, next_start)
        window = block[start:end]

        name = _extract_name(window)
        if not name:
            continue

        context = _extract_context_keywords(window, name, raw_phone)
        candidates.append({"name": name, "phone": raw_phone, "context": context})


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
                    if phone:
                        # BUG-094: כשיש phone, רק התאמת phone מדויקת נחשבת
                        # "אותו ליד" — לא מספיק להסתמך על ה-formula האחרון
                        # (SEARCH(name, {Name}) ללא phone בכלל) ולהחזיר
                        # records[0] בלי אימות. שם דומה/משותף (נפוץ בעברית)
                        # היה גורם ל-false match על ליד קיים לא-קשור וכתיבת
                        # phone/summary שגויים על גביו — בדיוק המנגנון
                        # שהפך "שני מועמדים עם אותו שם" ל"שתי כתיבות לאותה
                        # רשומה" בפרודקשן. formula הבא (אם יש) ינוסה במקום.
                        for rec in records:
                            rec_phone = re.sub(r"[\s\-]", "", str(rec.get("fields", {}).get("phone", "")))
                            if rec_phone == phone:
                                return rec["id"]
                        continue
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
    contract_ledger = None
    try:
        from core.action_gateway import action_gateway as _gw
        from airtable_schema import LeadFields
        _tool = "airtable_update" if action == "update" else "airtable_add"
        _domain_key = _lead_domain_key(domain)
        # BUG-077: wrap under "fields" matching exactly what the Write step
        # below actually writes — this is what lets classify_approval_policy()
        # (core/action_gateway.py) correctly classify a brand-new safe lead
        # as self_confirm (BUG-076 carve-out), instead of always falling
        # through to the strict "approval" default and getting force-flagged
        # pending by the requires_approval cross-check even though the write
        # happens unconditionally right below regardless of contract status.
        if existing_id:
            _fields = {LeadFields.PHONE: phone, LeadFields.SUMMARY: text[:500]}
            if _domain_key != "general":
                _fields[LeadFields.DOMAIN] = _domain_key
            _inputs = {"table": "Leads", "record_id": existing_id, "fields": _fields}
        else:
            _inputs = {
                "table": "Leads",
                "fields": {
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
                },
            }
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
        contract_ledger = _gw._ledger
    except Exception as exc:
        logger.warning("[LCH] gateway propose failed: %s", exc)

    # Write
    record_id = ""
    ok        = False
    try:
        from tools.airtable_gateway import airtable_create, airtable_patch
        from airtable_schema import LeadFields
        _domain_key = _lead_domain_key(domain)

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
            _domain_key = _lead_domain_key(domain)
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

    # Update the durable lifecycle before reporting a normal success. The
    # provider may already have written the lead, so a persistence failure is
    # surfaced as an explicit unknown audit state and must not invite retry.
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
                "[LCH] provider result could not be persisted to ActionContracts: "
                "contract=%s provider_ok=%s error=%s",
                contract_id, ok, exc,
            )

    if lifecycle_persistence_failed:
        return False, record_id, "lifecycle_persistence_failed"

    # Post-write enrichment (non-blocking, flag-gated)
    if ok and record_id:
        _domain_key = _lead_domain_key(domain)
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
    direct one-off airtable_add. trusted_source="lead_capture" (BUG-091) is
    required to pass tools/dispatcher.py's enforce_leads_write_gate() for
    table=Leads — passed as an explicit propose_action() keyword argument,
    NOT embedded in tool_inputs (a "_source" dict key would be Claude-
    controlled data if this payload ever originated from a tool_use, so it
    can no longer serve as the trust boundary).

    Returns the GatewayResult (ok / contract_id / user_message) from
    propose_action() — dedup (pending/already-executed) is handled entirely
    by the Gateway's business-fingerprint match, same as _write_one_lead().
    """
    from core.action_gateway import action_gateway as _gw
    from airtable_schema import LeadFields

    tenant_id   = getattr(identity, "tenant_id", "default") or "default"
    existing_id = _at_find_lead(name, phone)
    _domain_key = _lead_domain_key(domain)

    if existing_id:
        tool_name = "airtable_update"
        fields: dict = {LeadFields.PHONE: phone, LeadFields.SUMMARY: text[:500]}
        if _domain_key != "general":
            fields[LeadFields.DOMAIN] = _domain_key
        tool_inputs = {
            "table": "Leads", "record_id": existing_id,
            "fields": fields,
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
        tool_inputs = {"table": "Leads", "fields": fields}

    return _gw.propose_action(
        tenant_id         = tenant_id,
        canonical_user_id = identity.memory_key,
        tool_name         = tool_name,
        tool_inputs       = tool_inputs,
        origin_channel    = channel,
        origin_chat_id    = identity.memory_key,
        requires_approval = True,
        identity          = identity,
        trusted_source    = "lead_capture",
    )


# ══════════════════════════════════════════════════
# BUG-099c — clarification instead of denial when the name is missing
# ══════════════════════════════════════════════════
#
# Scope: Leads-only. Deliberately does NOT build a general Understanding
# Layer — BUG-104 (ReasoningEntity/reasoning_engines, see BUG_AUDIT_LOG.md)
# remains open as the separate general-architecture decision; a future
# BUG-104 implementation may refactor this flow without invalidating its
# correctness.
#
# State lives in session_store's EXISTING active_lead_candidate key (no new
# store) — extended with a distinct {"state": "needs_clarification", ...}
# shape, never confused with the pre-existing post-write bookmark shape
# ({"name", "record_id", "set_at"}, written by _handle_single_candidate/
# _handle_batch AFTER a successful write — zero live readers today, see
# BUG-106's Contract Chain). Every consumer below checks "state" explicitly
# before touching the dict's other keys.

# Local duplicate of app.py's _CANCEL_WORDS content — app.py imports FROM
# this module, so importing back would be circular. Small and deliberate;
# not a shared-constants refactor (out of scope for this fix).
_LEAD_CLARIFY_CANCEL_WORDS = frozenset({"לא", "בטל", "ביטול", "עצור", "cancel", "no", "❌"})

# Intents that unambiguously mean "this message is a different command
# entirely," not a reply to "what's the lead's name?" — anything NOT in
# this exclusion set (UNKNOWN/GREETING/SMALLTALK/CREATE_LEAD/UPDATE_LEAD)
# is treated as an explicit new command. Reuses the Router's OWN
# classification (passed in as `intent`) rather than re-detecting intent
# locally — same principle as core/router/deterministic_denial.py.
# Imported at module scope: core/router/route_decision.py is a pure
# dataclass/constants leaf module (no imports back into this file, no
# circular-import risk — verified).
from core.router.route_decision import Intent as _Intent  # noqa: E402

_LEAD_CLARIFY_NON_INTERRUPTING_INTENTS = frozenset({
    _Intent.UNKNOWN, _Intent.GREETING, _Intent.SMALLTALK,
    _Intent.CREATE_LEAD, _Intent.UPDATE_LEAD,
})

# BUG-111: display-only Hebrew label for a canonical Leads-Domain value (the
# inverse of core.ingress_classifier._DOMAIN_HINT_CANONICAL) — used ONLY to
# phrase the batch-clarification prompt ("...לדומיין גיוס..."); never used
# for any write/validation decision. "general" is intentionally absent —
# that case omits the "לדומיין X" clause entirely (see
# _maybe_start_lead_clarification below).
_DOMAIN_DISPLAY_HE = {
    "recruitment": "גיוס",
    "real_estate": "נדל\"ן",
    "import":      "יבוא",
    "media":       "מדיה",
    "finance":     "פיננסי",
    "saas":        "SaaS",
}


def _validate_clarification_name(text: str) -> Optional[str]:
    """
    Validates a raw reply as a lead name for the clarification flow.
    Reuses _HEBREW_NAME_RE/_is_name_stop_token (core/ingress_classifier.py —
    the SAME building blocks normal dictation extraction uses, not new
    validation logic) but with fullmatch semantics: unlike
    _extract_name_from_window() (which segments noisy free text to FIND a
    name inside it), a clarification reply is expected to BE the name and
    nothing else — no segmentation, no partial credit. "בקומה" (a stop-word,
    even after BUG-099b.1's prefix-aware check) correctly returns None here.

    Word count is capped at exactly 2 (first+last name — the only shape the
    spec's own examples exercise, "יוסי כהן"). This is NOT just cosmetic:
    a stop-word blocklist alone is too permissive for a full-reply check —
    "נדבר אחר כך" ("we'll talk later," a real conversational sentence)
    contains no property/lead-dictation stop-words at all and would
    otherwise fullmatch as a 3-word "name." Capping at 2 words rejects it
    as an unclear reply instead of a false-positive name, without adding
    stemming/grammar detection (still out of scope).
    """
    from core.ingress_classifier import _HEBREW_NAME_RE, _is_name_stop_token

    stripped = text.strip()
    m = _HEBREW_NAME_RE.fullmatch(stripped)
    if not m:
        return None
    words = stripped.split()
    if len(words) != 2:
        return None
    if any(_is_name_stop_token(w) for w in words):
        return None
    return stripped


def _build_clarification_summary(text: str, phone: str) -> str:
    """Best-effort summary for the clarification's partial_payload — the
    original text with the phone number and the most common trigger words
    stripped, trimmed. Used only for display (preview/summary), not for any
    gate/validation decision, so this deliberately stays simple rather than
    inventing new extraction logic.

    Uses core.ingress_classifier's _PHONE_RE (the live extraction path's own
    regex) — NOT this module's own top-level _PHONE_RE, which is part of the
    dead parse_lead_dictation/parse_batch_dictation cluster (0 live callers,
    see BUG-096) and must not be reintroduced into a live code path."""
    from core.ingress_classifier import _PHONE_RE as _ic_phone_re

    cleaned = text
    if phone:
        cleaned = _ic_phone_re.sub(" ", cleaned)
    for trigger in ("צור ליד חדש", "צור ליד", "ליד חדש", "תוסיף ליד", "הוסף ליד", "טלפון", "פלאפון", "נייד"):
        cleaned = cleaned.replace(trigger, " ")
    return re.sub(r"\s+", " ", cleaned).strip(" ,:.")


def _maybe_start_lead_clarification(
    identity, text: str, chat_id: str, channel: str, domain: str,
) -> Optional[str]:
    """
    Entry point: called only when classify_ingress() already resolved Tier 5
    (no_lead_candidates) AND the Router already resolved Intent.CREATE_LEAD
    at whatever confidence it uses for routing — i.e. "the system understood
    what you want, just couldn't find a name." Never triggers on Tier 4
    (export/table/log content is not a lead-creation attempt at all) and
    never triggers without a phone number actually present in the text —
    "some free text that happens to not extract a name" is not the same as
    "a clear create-lead request missing exactly one field."

    BUG-111: a text can carry MORE THAN ONE phone number with no names at all
    (e.g. a WhatsApp-pasted batch of phone-only lines under a "create N
    leads" header) — the original single-`.search()` version only ever
    stored the FIRST phone it found and silently discarded the rest, which
    would have quietly turned a 3-phone batch into a 1-phone clarification.
    All distinct phones in the text are now detected (finditer, normalized,
    de-duplicated, order preserved) and handled in one of two ways:
      - exactly 1 phone  -> the original single-name clarification, wording
        and state shape UNCHANGED (existing callers/tests unaffected).
      - 2+ phones        -> a batch clarification: every phone is preserved
        in session state (never silently reduced to one), and the reply
        explicitly states the count (and domain, when known) instead of
        picking one phone arbitrarily.
    """
    from core.ingress_classifier import _PHONE_RE as _ic_phone_re, _normalize_phone as _ic_normalize_phone

    # BUG-111: the raw regex match ("+972 53-396-8395") was stored/shown
    # verbatim — spaces/dashes/leading "+972" and all — instead of the same
    # canonical local format (_normalize_phone: "0"+9 digits) every other
    # extraction path in this module writes to Airtable's Leads.Phone.
    phones: list[str] = []
    seen: set[str] = set()
    for m in _ic_phone_re.finditer(text):
        normalized = _ic_normalize_phone(m.group().strip())
        if normalized in seen:
            continue
        seen.add(normalized)
        phones.append(normalized)

    if not phones:
        return None

    from session_store import lead_sessions as _ls

    domain_key = _lead_domain_key(domain)

    if len(phones) == 1:
        phone = phones[0]
        partial_payload = {
            "phone":   phone,
            "summary": _build_clarification_summary(text, phone),
            "domain":  domain_key,
            "source":  "owner_dictation",
            "channel": channel,
        }
        _ls.set_lead_clarification(chat_id, "name", partial_payload, text)
        return f"זיהיתי בקשה ליצור ליד ואת מספר הטלפון {phone}, אבל לא מצאתי שם. מה שם הליד?"

    # 2+ distinct phones — batch clarification (BUG-111). ALL phones are
    # preserved in partial_payload["phones"] — none is dropped.
    partial_payload = {
        "phones":  phones,
        "domain":  domain_key,
        "source":  "owner_dictation",
        "channel": channel,
    }
    _ls.set_lead_clarification(chat_id, "names", partial_payload, text)

    domain_suffix = f" לדומיין {_DOMAIN_DISPLAY_HE.get(domain_key, domain_key)}" if domain_key != "general" else ""
    phones_list = "\n".join(f"• {p}" for p in phones)
    return (
        f"זיהיתי {len(phones)} מספרים{domain_suffix}, אבל חסרים שמות. איך לשמור אותם?\n"
        f"{phones_list}\n\n"
        f"שלח שם אחד בכל שורה, לפי הסדר (בסה\"כ {len(phones)} שמות), או *בטל* לביטול."
    )


def _resolve_lead_clarification(
    identity, text: str, chat_id: str, channel: str, domain: str, intent: str,
    session: Optional[dict],
) -> Optional[str]:
    """
    Checked FIRST in handle_lead_candidate() — before batch-followup and
    before classify_ingress() runs on the new message — because a pending
    clarification must interpret the NEXT message (a bare name like "יוסי
    כהן" would otherwise itself resolve to Tier 5/no_lead_candidates and
    silently vanish, never reaching this logic at all).

    session (LL-11): the caller's ALREADY-LOADED session snapshot
    (app.py's run_agent() reads Sessions via lead_sessions.get() exactly
    ONCE per request and threads that single dict through, same convention
    as resolve_context_pronouns()/_build_tool_context() — see
    test_session_snapshot.py). This function must read active_lead_candidate
    from THAT dict, never call lead_sessions.get()/get_active_lead_candidate()
    itself — doing so would be a second, redundant Sessions read per request,
    exactly the regression LL-11 exists to catch. None (no snapshot passed,
    e.g. any caller other than the live text-message path) means "nothing
    pending" — safe default, matches deterministic_denial.py's own
    fail-safe convention (missing info skips the optimization, never grants
    something incorrectly).

    Priority order (mandatory, matches the spec exactly):
      1. TTL expired      — checked here as a pure/no-I/O comparison against
                             the snapshot's own "set_at"; only the WRITE that
                             clears it touches session_store (rare path, same
                             precedent as the pre-existing
                             set_active_lead_candidate() write-after-read)
      2. cancellation      — explicit cancel word
      3. explicit new command — Router-classified intent that isn't this
                                 flow's own intent/unknown/small-talk
      4. valid reply        — a validated name completes the candidate
      5. unclear reply      — state stays, ask again
    """
    if not session:
        return None
    cand = session.get("active_lead_candidate")
    if not cand:
        return None
    if cand.get("state") != "needs_clarification":
        return None  # the OLD post-write bookmark shape — not our concern

    from session_store import lead_sessions as _ls
    import time as _time

    # Priority 1 — TTL expired (pure check against the snapshot already in
    # hand; only clearing it is a write)
    if _time.time() - cand.get("set_at", 0) > 1800:
        _ls.clear_active_lead_candidate(chat_id)
        return None

    lower = text.strip().lower()

    # Priority 2 — cancellation
    if lower in _LEAD_CLARIFY_CANCEL_WORDS:
        _ls.clear_active_lead_candidate(chat_id)
        return "ביטלתי את יצירת הליד."

    # Priority 3 — explicit new command (Router's own classification reused,
    # not re-detected here)
    if intent and intent not in _LEAD_CLARIFY_NON_INTERRUPTING_INTENTS:
        _ls.clear_active_lead_candidate(chat_id)
        return None  # let the new command fall through to normal routing

    # Priority 4 — valid reply for the expected field
    if cand.get("expected_field") == "name":
        name = _validate_clarification_name(text)
        if name is not None:
            payload = cand.get("partial_payload", {})
            original_text = cand.get("original_text", text)
            candidate = {
                "name":       name,
                "phone":      payload.get("phone", ""),
                "confidence": 1.0,
                "context":    [],
                "raw_text":   original_text,
            }
            return _handle_single_candidate(
                identity, candidate, original_text, chat_id, channel,
                payload.get("domain", domain), auto_write=False,
                clear_clarification=True,
            )
        # unclear reply for the single-phone case — state stays, ask again
        return "עדיין חסר לי שם הליד. מה השם?"

    # BUG-111 — Priority 4b: batch clarification (2+ phones, see
    # _maybe_start_lead_clarification). One name per line, matching the
    # phones in the SAME order they were originally listed — no attempt at
    # fuzzy/positional matching beyond that (kept simple and predictable,
    # matching this module's existing "no new extraction logic" convention
    # for clarification replies, see _validate_clarification_name).
    if cand.get("expected_field") == "names":
        return _resolve_batch_name_clarification(
            identity, text, chat_id, channel, domain, cand,
        )

    # Priority 5 — unrecognized expected_field: fail safe, ask again rather
    # than silently drop the pending clarification.
    return "עדיין חסר לי מידע כדי להשלים את הליד."


def _resolve_batch_name_clarification(
    identity, text: str, chat_id: str, channel: str, domain: str, cand: dict,
) -> str:
    """
    Resolves a BUG-111 batch clarification (2+ phones, no names) once the
    user replies. Expects exactly one name per line, in the same order as
    partial_payload["phones"] — a count mismatch or any invalid line asks
    again WITHOUT clearing state (no phone is ever silently dropped just
    because the reply couldn't be parsed).

    On a valid reply, routes through the SAME preview mechanism Tier-2 clean
    batches already use (_store_pending_preview / resolve_pending_lead_preview,
    BUG-058) rather than inventing a second batch-write path — "כן"/"לא"
    then resolves it exactly like any other multi-lead preview. That
    confirm-time rendering (per-lead record_id shown inline, "עובדתי" summary
    header) is pre-existing, tracked separately, and intentionally NOT
    touched here.
    """
    payload = cand.get("partial_payload", {})
    phones: list[str] = payload.get("phones", [])
    original_text = cand.get("original_text", text)
    resolved_domain = payload.get("domain", domain)

    if not phones:
        # Defensive only — _maybe_start_lead_clarification never stores this
        # state with an empty phones list.
        from session_store import lead_sessions as _ls
        _ls.clear_active_lead_candidate(chat_id)
        return "אירעה תקלה בזיהוי המספרים. נסה לשלוח את הבקשה מחדש."

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    if len(lines) != len(phones):
        return (
            f"צריך בדיוק {len(phones)} שמות — אחד לכל מספר, כל שם בשורה נפרדת "
            f"ולפי הסדר שבו הופיעו המספרים. שלח שוב, או *בטל* לביטול."
        )

    names: list[str] = []
    for line in lines:
        name = _validate_clarification_name(line)
        if name is None:
            return (
                f"'{line}' לא נראה כמו שם תקין. שלח {len(phones)} שמות, "
                f"אחד לכל מספר, כל שם בשורה נפרדת."
            )
        names.append(name)

    candidates = [
        {"name": n, "phone": p, "context": [], "raw_text": original_text}
        for n, p in zip(names, phones)
    ]

    from session_store import lead_sessions as _ls
    _ls.clear_active_lead_candidate(chat_id)
    _store_pending_preview(chat_id, candidates, original_text, channel, resolved_domain)

    lines_preview = [f"• {c['name']} ({c['phone']})" for c in candidates]
    return (
        f"📋 זיהיתי {len(candidates)} לידים אפשריים בקבוצה:\n" +
        "\n".join(lines_preview) +
        "\n\nענה \"כן\" לשמירת כולם, או \"לא\" לביטול. (בתוקף ל-30 דקות)"
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
    intent: str = "",
    session: Optional[dict] = None,
) -> Optional[str]:
    """
    מטפל דטרמיניסטית בהכתבת ליד (בודד או batch) של owner/staff.
    מחזיר GatewayReply string אם הפעולה הסתיימה, None אם לא תבנית — ממשיך לאייג'נט.

    C89: כל קלט עובר classify_ingress() לפני כל פרסור.
    Tier 4/5 → None (אסור לכתוב, מועבר לאייג'נט) — למעט BUG-099c (למטה).
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

    intent (BUG-099c): route.intent מ-router.py — Router's OWN classification,
    reused (לא מזוהה מחדש) לשני דברים: (1) לזהות "פקודה חדשה מפורשת" תוך כדי
    פתרון הבהרה ממתינה, (2) לקבוע אם להתחיל הבהרה בכלל (Tier 5 + intent
    create_lead + טלפון קיים = "הכוונה ברורה, חסר רק שם"). ריק כברירת מחדל —
    תאימות לאחור לכל caller אחר; ריק פירושו "לעולם לא להתחיל הבהרה חדשה",
    לא "להתיר הכל" (fail-safe זהה לעיצוב deterministic_denial.py).

    session (BUG-099c, LL-11): app.py's run_agent() כבר טוען session snapshot
    יחיד (_session_snapshot = lead_sessions.get(chat_id)) ומעביר אותו הלאה
    ל-resolve_context_pronouns/_build_tool_context — Sessions נקרא פעם אחת
    בלבד לכל request (test_session_snapshot.py). _resolve_lead_clarification
    קורא active_lead_candidate מה-snapshot הזה, לא קורא ל-lead_sessions.get()/
    get_active_lead_candidate() בעצמו — קריאה שנייה הייתה בדיוק הרגרסיה ש-
    LL-11 קיים כדי לתפוס. None (ברירת מחדל, לכל caller שלא מעביר snapshot,
    למשל נתיב הקובץ C90) = "אין כלום ממתין" — לא מפעיל שום לוגיקת הבהרה.
    """
    if not getattr(identity, "is_internal", False):
        return None

    # ── domain: Router (route.domain) is the source of truth when passed in;
    #    _detect_domain() stays as the fallback for any other caller ──────
    domain = domain or _detect_domain(text, getattr(identity, "domain_id", "general"))

    # ── BUG-099c: resolve a PENDING lead-clarification first — before batch-
    #    followup and before classify_ingress() even runs on this message.
    #    A bare name reply ("יוסי כהן") would otherwise itself resolve to
    #    Tier 5/no_lead_candidates and silently vanish before ever reaching
    #    this logic. ──────────────────────────────────────────────────────
    _clarify_reply = _resolve_lead_clarification(
        identity, text, chat_id, channel, domain, intent, session,
    )
    if _clarify_reply is not None:
        return _clarify_reply

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
        # BUG-099c: Tier 5 specifically (no_lead_candidates — some signal,
        # just no name found) + a Router-confirmed create_lead intent means
        # "the system understood the request, only one field is missing" —
        # ask for it instead of falling through to DeterministicDenial's
        # generic "manual creation blocked" message. Tier 4 (export/table/
        # log content) never triggers this — that's genuinely not a lead
        # dictation attempt at all.
        if ic.tier == 5 and ic.reason == "no_lead_candidates" and intent == _Intent.CREATE_LEAD:
            _start_reply = _maybe_start_lead_clarification(identity, text, chat_id, channel, domain)
            if _start_reply is not None:
                return _start_reply
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
    clear_clarification: bool = False,
) -> Optional[str]:
    """
    Tier 1: ליד בודד high-confidence.
    auto_write=True (FEATURE_AUTO_CAPTURE) → כותב מיד ליד חדש.
    עדכון ליד קיים (airtable_update) תמיד עובר דרך אישור — גם כש-auto_write=True
    (C89 UX: לעולם לא לעדכן ליד קיים בלי אישור מפורש).
    auto_write=False → מחזיר preview ומאחסן ActionContract ממתין.

    clear_clarification (BUG-099c): כשה-candidate הגיע מפתרון הבהרה
    (_resolve_lead_clarification, לא מחילוץ Tier 1 רגיל) — מנקה את
    active_lead_candidate's "needs_clarification" state, אבל **רק** אחרי
    ש-propose_action()/הכתיבה בפועל הצליחו (לא לפני) — כך שכשל משאיר את
    ה-state פעיל, ללא פעולה חלקית וללא אובדן payload (per spec).
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
            # clear_clarification NOT applied — propose_action() did not
            # succeed, the clarification state must survive (spec).
            return gw_result.user_message or gw_result.reason
        # BUG-115: a bare "כן"/"מאשר" reply to the preview below must resolve
        # THIS contract, not fall into ActionGateway's generic live-contract
        # -count disambiguation if older unrelated contracts also happen to
        # still be pending. See route_confirmation_word()'s bookmark check.
        if gw_result.contract_id:
            try:
                from session_store import lead_sessions as _ls_bm
                _ls_bm.set_last_prompted_contract(identity.memory_key, gw_result.contract_id, kind="lead_preview")
            except Exception as exc:
                logger.warning("[LCH] BUG-115 last-prompted-contract bookmark failed: %s", exc)
        if clear_clarification:
            try:
                from session_store import lead_sessions as _ls
                _ls.clear_active_lead_candidate(chat_id)
            except Exception as exc:
                logger.warning("[LCH] clarification clear failed: %s", exc)
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
            # set_active_lead_candidate() overwrites the whole
            # active_lead_candidate dict with the post-write bookmark shape
            # — the needs_clarification state (if any) is already gone by
            # replacement; clearing it separately here would instead ERASE
            # the bookmark this line just wrote (last-write-wins), so
            # clear_clarification is intentionally not applied in this
            # branch. In practice this branch never runs from the
            # clarification resolver anyway (auto_write is always False
            # there, per BUG-074/076's "existing lead never auto-writes"
            # convention followed for new leads here too).
            _ls.set_active_lead_candidate(chat_id, name, record_id=record_id)
            _ls.set_current_lead_record_id(chat_id, record_id)
        except Exception as exc:
            logger.warning("[LCH] session persist failed: %s", exc)

    if not ok:
        if action == "lifecycle_persistence_failed":
            return (
                "⚠️ ייתכן שהליד נשמר, אך סטטוס ActionContract לא נשמר "
                "באופן עמיד. אין לנסות שוב עד לבדיקת המערכת."
            )
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
    auto_write=False → BUG-058: preview עם resolver אמיתי — "כן"/"לא" נפתרים
    ע"י resolve_pending_lead_preview() ב-app.py section 2.55, אחרי שנבדק
    שאין contract Tier-1 חי (Tier-1 מנצח תמיד כששני המנגנונים חיים בו-זמנית
    לאותו chat_id — ראה תיעוד ב-app.py וב-resolve_pending_lead_preview()).
    """
    if not _should_auto_write(auto_write, None):
        _store_pending_preview(chat_id, candidates, text, channel, domain)
        lines = [
            f"• {c['name']} ({c['phone']})" + (f" [{', '.join(c['context'])}]" if c.get("context") else "")
            for c in candidates
        ]
        return (
            f"📋 זיהיתי {len(candidates)} לידים אפשריים בקבוצה:\n" +
            "\n".join(lines) +
            "\n\nענה \"כן\" לשמירת כולם, או \"לא\" לביטול. (בתוקף ל-30 דקות)"
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
        # BUG-096-B: use this candidate's own segment (raw_text, set by
        # core/ingress_classifier.py's block-based extraction) as their
        # Summary/Lead-Event/memory text — not the whole batch message,
        # which would leak other candidates' details into this lead's record.
        c_text = c.get("raw_text") or text
        existing_id = _at_find_lead(c["name"], c["phone"])
        ctx_str = _context_suffix(c.get("context", []), domain)
        if _should_auto_write(auto_capture, existing_id):
            ok, record_id, action = _write_one_lead(
                identity, c["name"], c["phone"], c_text, channel, domain
            )
            if ok and record_id:
                verb = "עדכנתי" if action == "update" else "שמרתי"
                results.append(f"✅ {verb} את {c['name']} ({c['phone']}){ctx_str}")
                written += 1
            elif action == "lifecycle_persistence_failed":
                results.append(
                    f"⚠️ {c['name']} ({c['phone']}) — ייתכן שנשמר; "
                    "הביקורת לא נשמרה. אין לנסות שוב."
                )
            else:
                results.append(f"❌ {c['name']} ({c['phone']}) — לא נשמר")
        else:
            gw_result = _propose_lead_write(
                identity, c["name"], c["phone"], c_text, channel, domain
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

def _store_pending_preview(
    chat_id: str, candidates: list[dict], raw_text: str,
    channel: str, domain: str,
) -> None:
    """שומר preview של batch (Tier 2) עם TTL 30 דקות — BUG-058 resolver.

    channel/domain נשמרים כאן (לא מבוקשים מחדש ב-resolve time) כי ב-app.py
    section 2.55 (נקודת ה-resolve, "כן"/"לא") ה-Router עוד לא רץ — אין
    resolved_route_domain זמין שם. _handle_clean_batch כבר מקבל את שניהם.

    ראו resolve_pending_lead_preview() למטה — הצרכן בפועל של השדה הזה.
    """
    try:
        from session_store import lead_sessions as _ls
        _ls.set_pending_lead_preview(chat_id, candidates, raw_text, channel, domain)
    except Exception as exc:
        logger.warning("[LCH] pending_preview store failed: %s", exc)


def resolve_pending_lead_preview(
    identity, chat_id: str, is_confirm: bool, is_cancel: bool,
) -> Optional[str]:
    """BUG-058 resolver: קורא pending_lead_preview בחזרה, מבצע batch confirm/cancel.

    מוחזר None אם: (א) אין preview ממתין / פג תוקפו, או (ב) לא confirm/cancel
    כלל — בשני המקרים app.py ממשיך כרגיל בזרימת ActionGateway/Agent הרגילה.
    מוחזר string אם ה-resolver "צרך" את ההודעה.

    channel/domain נשלפים מתוך ה-preview עצמו (נשמרו בזמן הכתיבה) — לא
    מהקורא, כי בנקודת ה-app.py הזו (2.55) ה-Router עוד לא רץ.

    לא נוגע ב-_pending_approvals או ActionGateway contracts — Tier 1
    (_propose_lead_write) ממשיך לעבוד בדיוק כפי שהוא, ללא שינוי.
    אין תמיכה ב-selection חלקי ("כן 1") — רק אישור/ביטול מלא לכל ה-batch.

    Precedence מול Tier 1 (BUG-058 caveat שנפתר): app.py קורא לפונקציה הזו
    רק *אחרי* שנבדק שאין contract ActionGateway חי לאותו chat_id (אותו
    gate שכבר קיים לשני ה-elif של _CONFIRM_WORDS/_CANCEL_WORDS, BUG-056
    precedent) — כלומר Tier 1 מנצח תמיד כששני המנגנונים חיים בו-זמנית.
    הפונקציה הזו לא בודקת בעצמה — ההכרעה ברמת ה-caller ב-app.py.
    """
    if not (is_confirm or is_cancel):
        return None

    try:
        from session_store import lead_sessions as _ls
    except Exception:
        return None

    preview = _ls.get_pending_lead_preview(chat_id)
    if preview is None:
        return None  # אין preview ממתין, או שפג תוקפו ונוקה בשקט

    if is_cancel:
        _ls.clear_pending_lead_preview(chat_id)
        return "ביטלתי את רשימת הלידים הממתינה."

    # is_confirm
    candidates = preview.get("candidates") or []
    raw_text   = preview.get("raw_text", "")
    channel    = preview.get("channel", "telegram")
    domain     = preview.get("domain", "general")
    _ls.clear_pending_lead_preview(chat_id)

    if not candidates:
        return "לא נמצאו לידים לשמירה — כנראה שהרשימה כבר טופלה."

    return _handle_batch(identity, raw_text, chat_id, channel, domain, candidates)


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
        # BUG-096-B: this candidate's own segment, not the whole batch text —
        # see identical reasoning in _handle_mixed_batch above.
        item_text = item.get("raw_text") or text
        ok, record_id, action = _write_one_lead(identity, name, phone, item_text, channel, domain)
        ctx = _context_suffix(item.get("context", []), domain)
        if ok and record_id:
            verb = "עדכנתי" if action == "update" else "שמרתי"
            results.append({"name": name, "phone": phone, "ok": True,
                            "record_id": record_id, "action": action,
                            "line": f"✅ {verb} את {name} ({phone}){ctx} | {record_id}"})
        elif action == "lifecycle_persistence_failed":
            results.append({"name": name, "phone": phone, "ok": False,
                            "record_id": record_id, "action": action,
                            "line": (
                                f"⚠️ {name} ({phone}) — ייתכן שנשמר; "
                                "הביקורת לא נשמרה. אין לנסות שוב."
                            )})
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

# BUG-098: word-boundary matching, not substring — "ומה" as a plain `in`
# check matched inside "קומה" (floor), a completely ordinary real-estate
# word, falsely triggering this branch for any lead message that mentions
# a floor number. \b is Unicode-aware in Python 3 (treats Hebrew letters
# as \w), so it correctly separates whole words — verified empirically
# against "קומה"/"ישאר"/"נשאר"/"אישר" (must NOT match) and real follow-up
# phrasing like "ומה עם השאר?" (must match) before landing this fix.
_FOLLOWUP_WORDS = frozenset({
    "ומה", "השאר", "שאר", "הנותרים", "נותרים", "שאר הלידים",
    "שאר הרשימה", "מה עם השאר", "מה עם הנותרים",
})
_FOLLOWUP_WORD_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _FOLLOWUP_WORDS) + r")\b"
)


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
    if not _FOLLOWUP_WORD_PATTERN.search(lower):
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
