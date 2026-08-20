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
from typing import Optional

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

# Phase 1 (Lead System E2E Audit): the dedup lookup is now a single
# implementation shared by every Lead-creation caller — see
# core/lead_service.py::find_existing_lead(). Re-exported here under the
# original private name so this module's own call sites (and existing
# regression tests, which patch `lch._at_find_lead` directly) are
# unaffected.
from core.lead_service import find_existing_lead as _at_find_lead


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
    מוצא (או יוצר/מעדכן) ליד אחד — עטיפה דקה סביב core/lead_service.py::
    create_lead(), השירות הקנוני היחיד לכתיבת Lead (Phase 1, Lead System
    E2E Audit). כל ה-validation/dedup/Owner/EmergencyStop/ActionGateway-
    lifecycle גרים כעת שם, לא כאן. חתימת ה-tuple המקורית (ok, record_id,
    action) נשמרת כדי לא לשבור את _handle_single_candidate/
    _handle_mixed_batch/_handle_batch.
    """
    from core.lead_service import LeadPayload, create_lead

    domain_key  = _lead_domain_key(domain)
    existing_id = _at_find_lead(name, phone)

    payload = LeadPayload(
        name=name, phone=phone, domain=domain_key,
        source="owner_dictation", channel=channel, summary=text,
        status="new", score=0,
    )
    result = create_lead(
        identity, payload, source_module="lead_candidate_handler", existing_id=existing_id,
    )

    action = {"created": "create", "updated": "update"}.get(result.action, result.action)
    return result.ok, result.record_id, action


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

    Phase 1 (Lead System E2E Audit): field construction for the "new lead"
    branch now goes through core/lead_service.py's build_lead_fields()/
    resolve_owner() — the SAME canonical helpers _write_one_lead() (via
    create_lead()) uses — so a lead proposed here for approval carries the
    same Owner/tenant_id as one auto-written by Path A, instead of a
    second, drifted field set. The actual WRITE on approval still goes
    through app.py's confirm-word handling -> dispatch_tool() (unchanged;
    out of Phase 1 scope — see the audit's remaining-work list).
    """
    from core.action_gateway import action_gateway as _gw
    from core.lead_service import LeadPayload, build_lead_fields, build_memory_key, resolve_owner
    from airtable_schema import LeadFields

    tenant_id   = getattr(identity, "tenant_id", "default") or "default"
    existing_id = _at_find_lead(name, phone)
    _domain_key = _lead_domain_key(domain)
    owner_record_id, _resolved_owner = resolve_owner(identity)

    if existing_id:
        tool_name = "airtable_update"
        fields: dict = {LeadFields.PHONE: phone, LeadFields.SUMMARY: text[:500]}
        if _domain_key != "general":
            fields[LeadFields.DOMAIN] = _domain_key
        if owner_record_id:
            fields[LeadFields.OWNER] = [owner_record_id]
        tool_inputs = {
            "table": "Leads", "record_id": existing_id,
            "fields": fields,
        }
    else:
        memory_key = build_memory_key(tenant_id, phone, name)
        tool_name = "airtable_add"
        payload = LeadPayload(
            name=name, phone=phone, domain=_domain_key, source="owner_dictation",
            channel=channel, summary=text, status="new", score=0, tenant_id=tenant_id,
        )
        fields = build_lead_fields(payload, owner_record_id, memory_key)
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

# N18 Phase 2: the confirm/cancel/edit Hebrew vocabulary is generic UI
# chrome, not lead-specific — canonical copy now lives in core/draft_flow.py
# (shared by any future Draft-Card entity). Re-exported under this module's
# original private name — _resolve_lead_clarification (a separate flow,
# below) also reuses it for cancellation.
from core.draft_flow import CANCEL_WORDS as _LEAD_CLARIFY_CANCEL_WORDS  # noqa: E402

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

# BUG-051-FU (פער עדיפות create_contact מול Leads, QA ידני 14/08/2026):
# BUG-051/PR#205 ניתק בכוונה את ה-auto-capture של LCH ב-Tier 1-3 מכוונת
# ה-Router — LCH רץ לפי identity.is_internal בלבד, ולכן ימשיך לתפוס
# מועמד Tier 1-3 גם כשה-Router סיווג את אותו turn בביטחון ככוונת mutation
# מפורשת שאינה ליד (למשל "צור איש קשר רמי לוי 0547653453" → Router
# intent=create_contact conf=0.90, אך LCH עדיין הציע כתיבת airtable_add/
# Leads). BUG-099c כבר הוסיף חריג צר Tier-5+CREATE_LEAD בכיוון ההפוך; זהו
# הגילדר הכללי החסר: כש-Router זיהה בביטחון יעד mutation מפורש שאינו ליד
# עבור turn זה, אותה כוונה בעלת ה-turn ו-LCH אסור לו לפרש אותו מחדש כליד.
#
# קבוצה סגורה, לא כלל גורף "כל intent שאינו CREATE_LEAD חוסם capture" —
# כל pattern למטה דורש שם-עצם יעד מפורש (איש קשר/משימה/אירוע/מייל) ללא
# חפיפה טקסטואלית עם ניסוח דיקטציית ליד אמיתית, כך שהודעת ליד אמיתית
# ("משה כהן 0501234567, מעוניין בדירה") לעולם לא תתאים לאחד מאלו ותאבד
# את ה-capture שלה. שני intents שנגישים בטבלת הכללים של
# core/router/intent_router.py הוצאו בכוונה למרות היותם "mutations":
#   - STORE_MEMORY: ה-pattern שלו כולל "שמור" בלבד — אחת ממילות ה-
#     _SAVE_WORDS של LCH עצמו; הכללתו הייתה מדכאת שמירות ליד רגילות
#     ("שמור את הליד") — מפר את האילוץ "לא לשנות סמנטיקת lead capture".
#   - ADMIN_ACTION: מתאים למילה "ניהול" בלבד ב-0.85 — כללי מדי (למשל
#     "מתעניין בניהול נכסים" הוא ליד נדל"ן אמיתי, לא בקשת admin/settings)
#     כדי לשער עליו capture בבטחה.
# נכללים רק intents שה-pattern שלהם ב-Router דורש מילת-מפתח יעד חד-משמעית
# שאין לה חפיפה עם ליד.
_NON_LEAD_MUTATION_INTENTS = frozenset({
    _Intent.CREATE_CONTACT, _Intent.UPDATE_CONTACT,
    _Intent.CREATE_TASK, _Intent.UPDATE_TASK,
    _Intent.COMPLETE_TASK, _Intent.DELETE_TASK,
    _Intent.CREATE_EVENT, _Intent.UPDATE_EVENT,
    _Intent.CANCEL_EVENT, _Intent.SCHEDULE_MEETING,
    _Intent.DRAFT_EMAIL, _Intent.SEND_EMAIL,
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
        f"שלח שם אחד בכל שורה, לפי הסדר (בסה\"כ {len(phones)} שמות), או בטל לביטול."
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
            f"ולפי הסדר שבו הופיעו המספרים. שלח שוב, או בטל לביטול."
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
# Lead Draft Card (Phase 1 follow-up) — the primary creation UX
# ══════════════════════════════════════════════════

# "ליד חדש" followed by anything that ISN'T a pipe continuation — checked
# only once core.lead_service.parse_structured_command() has already
# returned None for the same text (which happens for exactly bare "ליד
# חדש" -- caught separately as {"prompt": True} -- or "ליד חדש | ..." --
# a full pipe command). By the time this regex is even consulted, the text
# is guaranteed to carry free-text content after the trigger.
_DRAFT_TRIGGER_RE = re.compile(r"^\s*ליד\s+חדש\b\s*(.*)$", re.DOTALL)


def _start_lead_draft(identity, free_text: str, chat_id: str, channel: str, router_domain: str = "") -> str:
    from core.lead_service import build_draft_from_text, new_empty_draft, render_lead_draft_card, DRAFT_FIELD_PROMPT_HE
    from session_store import lead_sessions as _ls

    draft = build_draft_from_text(free_text, channel, router_domain) if free_text else new_empty_draft(channel)
    _ls.set_lead_draft(chat_id, draft)

    if draft["mode"] == "review":
        return render_lead_draft_card(draft)
    return DRAFT_FIELD_PROMPT_HE[draft["awaiting_field"]]


def _finalize_draft_cancel(chat_id: str) -> str:
    from session_store import lead_sessions as _ls
    _ls.clear_lead_draft(chat_id)
    return "ביטלתי את יצירת הליד."


def _finalize_draft_confirm(identity, chat_id: str, draft: dict) -> str:
    """Shared by _resolve_lead_draft (normal in-flow confirm) and
    resolve_lead_draft_confirmation (app.py's early confirm-word
    dispatch) — a single implementation of "כן actually writes the lead,"
    so the two entry points can never drift apart on what counts as a
    complete draft or what create_lead() gets called with."""
    from session_store import lead_sessions as _ls
    from core.lead_service import first_missing_required_field, draft_to_payload, create_lead, DRAFT_FIELD_PROMPT_HE

    missing = first_missing_required_field(draft)
    if missing:
        draft["mode"] = "filling"
        draft["awaiting_field"] = missing
        _ls.set_lead_draft(chat_id, draft)
        return f"עדיין חסר. {DRAFT_FIELD_PROMPT_HE[missing]}"

    payload = draft_to_payload(draft)
    result = create_lead(identity, payload, source_module="lead_candidate_handler_draft")
    if not result.ok:
        return f"❌ לא הצלחתי לשמור את הליד: {result.reason}"
    _ls.clear_lead_draft(chat_id)
    verb = "עודכן" if result.action == "updated" else "נוצר"
    owner_note = f", Owner: {result.owner_user_id}" if result.owner_user_id else ""
    return (
        f"✅ ליד {verb}: {draft.get('name')} ({draft.get('phone')}), "
        f"domain: {result.domain}{owner_note} | {result.record_id}"
    )


def should_prefer_lead_draft(canonical_user_id: str, chat_id: str) -> bool:
    """True if a review-mode Lead Draft Card was shown more recently than
    either the ActionGateway Tier-1 bookmark (BUG-115) or the Tier-2 batch
    preview (BUG-058/117) — same recency-comparison principle as
    should_prefer_batch_preview(), extended to lead_draft. app.py's
    confirm/cancel-word dispatch predates lead_draft and has no built-in
    knowledge of it; this is what lets it check the right thing instead of
    always falling through to "אין פעולה שממתינה לאישור" for a fully-formed,
    on-screen draft card."""
    try:
        from session_store import lead_sessions as _ls
    except Exception:
        return False

    draft = _ls.get_lead_draft(chat_id)
    if draft is None or draft.get("mode") != "review":
        return False  # only a fully-formed card (awaiting כן/ערוך/לא) counts

    draft_at = draft.get("set_at", 0)

    bookmark = _ls.get_last_prompted_contract(canonical_user_id)
    if bookmark is not None and bookmark.get("set_at", 0) > draft_at:
        return False

    preview = _ls.get_pending_lead_preview(chat_id)
    if preview is not None and preview.get("set_at", 0) > draft_at:
        return False

    return True


def resolve_lead_draft_confirmation(
    identity, chat_id: str, channel: str, is_confirm: bool, is_cancel: bool,
) -> Optional[str]:
    """Early-dispatch counterpart to _resolve_lead_draft(), for app.py's
    confirm/cancel-word branch — which runs BEFORE handle_lead_candidate()
    and has no session snapshot to pass in, same self-fetching style as
    resolve_pending_lead_preview(). Only resolves a draft that's in review
    mode; every other shape (nothing pending, or a draft still mid-fill/
    edit) returns None so the caller falls through to its existing logic
    unchanged — a mid-fill/edit reply isn't a bare confirm/cancel word in
    the first place, so it always reaches handle_lead_candidate() normally
    regardless of this function."""
    if not (is_confirm or is_cancel):
        return None
    from session_store import lead_sessions as _ls
    draft = _ls.get_lead_draft(chat_id)
    if draft is None or draft.get("mode") != "review":
        return None
    if is_cancel:
        return _finalize_draft_cancel(chat_id)
    return _finalize_draft_confirm(identity, chat_id, draft)


def _resolve_lead_draft(
    identity, text: str, chat_id: str, channel: str, intent: str, session: Optional[dict],
) -> Optional[str]:
    """Resolves a reply against a pending Lead Draft Card. Checked FIRST in
    handle_lead_candidate() — same LL-11 read-from-snapshot convention as
    _resolve_lead_clarification (session is the caller's already-loaded
    snapshot, never re-read here). NOTE: for review-mode כן/לא specifically,
    app.py's own confirm/cancel-word dispatch resolves it earlier via
    resolve_lead_draft_confirmation() before this function is ever reached
    (see should_prefer_lead_draft()) — this function's own review-mode
    branch below stays as the fallback for any caller that reaches
    handle_lead_candidate() directly (tests, other entry points)."""
    if not session:
        return None
    draft = session.get("lead_draft")
    if not draft:
        return None

    from session_store import lead_sessions as _ls
    from core.draft_flow import is_expired, resolve_draft_reply

    if is_expired(draft):
        _ls.clear_lead_draft(chat_id)
        return None

    # An explicit, unambiguous different command owns this turn -> abandon
    # the draft rather than force-feeding it an unrelated reply (same
    # escape hatch as _resolve_lead_clarification).
    if intent and intent in _NON_LEAD_MUTATION_INTENTS:
        _ls.clear_lead_draft(chat_id)
        return None

    # A fresh "ליד חדש ..." trigger always wins over a stale/stuck draft —
    # never force an unrelated new-lead attempt to be swallowed by this
    # draft's own catch-all (the exact "stuck until pending is reset"
    # complaint this guards against).
    from core.lead_service import parse_structured_command as _psc
    if _psc(text) is not None or _DRAFT_TRIGGER_RE.match(text.strip()):
        _ls.clear_lead_draft(chat_id)
        return None

    # N18 Phase 2: mode transitions (filling/edit_choice/review) are the
    # generic Draft-Card state machine in core/draft_flow.py — this handler
    # only owns session persistence and the actual write (via
    # _finalize_draft_confirm/_finalize_draft_cancel), driven by
    # core.lead_service.LEAD_DRAFT_SPEC's field semantics.
    from core.lead_service import LEAD_DRAFT_SPEC

    outcome = resolve_draft_reply(text, draft, LEAD_DRAFT_SPEC)

    if outcome.kind == "abandon":
        _ls.clear_lead_draft(chat_id)
        return None
    if outcome.kind == "cancel":
        return _finalize_draft_cancel(chat_id)
    if outcome.kind == "confirm":
        return _finalize_draft_confirm(identity, chat_id, draft)

    if outcome.draft is not None:
        _ls.set_lead_draft(chat_id, outcome.draft)
    return outcome.message


# ══════════════════════════════════════════════════
# Phase 1 (Lead System E2E Audit) — structured creation command
# ══════════════════════════════════════════════════

def _handle_structured_command(identity, parsed: dict, channel: str) -> str:
    """Resolves a core.lead_service.parse_structured_command() result into
    a user-facing reply. Called only for the two non-"prompt" shapes the
    caller (handle_lead_candidate) doesn't handle itself: {"error": "..."}
    (validation failure — never a silent invented default) or a fully
    valid {"name","phone","domain","note"} (immediate write — the pipe
    format is already fully unambiguous, no draft/confirm step needed).
    The bare-trigger {"prompt": True} shape is handled by the caller via
    _start_lead_draft(), never reaches this function."""
    if "error" in parsed:
        return f"❌ {parsed['error']}"

    from core.lead_service import LeadPayload, create_lead

    payload = LeadPayload(
        name=parsed["name"], phone=parsed["phone"], domain=parsed["domain"],
        domain_explicit=True, source="structured_command", channel=channel,
        summary=parsed.get("note", ""),
    )
    result = create_lead(identity, payload, source_module="lead_candidate_handler_structured")
    if not result.ok:
        return f"❌ לא הצלחתי ליצור את הליד: {result.reason}"

    verb = "עודכן" if result.action == "updated" else "נוצר"
    owner_note = f", Owner: {result.owner_user_id}" if result.owner_user_id else ""
    return (
        f"✅ ליד {verb}: {parsed['name']} ({parsed['phone']}), "
        f"domain: {result.domain}{owner_note} | {result.record_id}"
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

    # ── Lead Draft Card (Phase 1 follow-up): a reply against an
    #    already-pending draft is resolved FIRST — before any new-command
    #    detection below — same priority position as _resolve_lead_clarification. ──
    _draft_reply = _resolve_lead_draft(identity, text, chat_id, channel, intent, session)
    if _draft_reply is not None:
        return _draft_reply

    # ── Phase 1 (Lead System E2E Audit) — structured, fully deterministic
    #    creation command: "ליד חדש | שם | טלפון | domain | הערה" (immediate
    #    write, already unambiguous) or bare "ליד חדש" (starts a Lead Draft
    #    Card — the primary creation UX, see _start_lead_draft). Checked
    #    before any natural-language parsing or tier classification. ─────
    from core.lead_service import parse_structured_command
    _structured = parse_structured_command(text)
    if _structured is not None:
        if _structured.get("prompt"):
            return _start_lead_draft(identity, "", chat_id, channel)
        return _handle_structured_command(identity, _structured, channel)

    # ── "ליד חדש <free text>" (no pipe) -> a pre-filled Lead Draft Card,
    #    shown for confirmation before anything is written. Only reached
    #    once parse_structured_command() above has already ruled out both
    #    the bare trigger and the pipe format for this exact text. ────────
    _draft_trigger = _DRAFT_TRIGGER_RE.match(text.strip()) if text else None
    if _draft_trigger is not None:
        return _start_lead_draft(identity, _draft_trigger.group(1).strip(), chat_id, channel, router_domain=domain)

    # ── domain: Phase 1's single domain-resolution authority
    #    (core.lead_service.resolve_domain) — an explicit "domain X"/
    #    "דומיין X" annotation in `text` ALWAYS wins here, even when the
    #    Router already passed its own (possibly wrong) guess; only when no
    #    such annotation exists does the Router's domain (or the legacy
    #    local _detect_domain() guess, for callers that never pass one at
    #    all) apply. This is the direct fix for the golden failure case
    #    (recruitment -> finance): the Router's guess used to silently win
    #    unconditionally, so an explicit annotation was structurally
    #    unreachable in the live path. ──────────────────────────────────
    from core.lead_service import resolve_domain as _resolve_lead_domain
    if domain:
        domain, _ = _resolve_lead_domain(text, domain)
    else:
        domain = _detect_domain(text, getattr(identity, "domain_id", "general"))

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

    # BUG-051-FU: כוונת mutation מפורשת שאינה ליד ואושרה ע"י Router בעלת
    # ה-turn — LCH אסור לו לפרש אותו מחדש כ-lead capture גם כש-ic.tier הוא
    # 1-3 (ראו _NON_LEAD_MUTATION_INTENTS למעלה לקבוצה הסגורה ולהנמקת
    # ההוצאות). `intent` הוא ערך שאינו UNKNOWN כאן רק כש-detect_intent()
    # של ה-Router עצמו עבר את INTENT_CONFIDENCE_THRESHOLD
    # (core/router/router.py) — אין צורך בבדיקת confidence נפרדת.
    if intent in _NON_LEAD_MUTATION_INTENTS:
        logger.info(
            "[LCH] Tier %d capture suppressed — explicit non-lead intent=%s owns turn",
            ic.tier, intent,
        )
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
                f"📋 מצאתי ליד קיים: {name} ({phone}){ctx_str}\n"
                f"לעדכן אותו? ענה כן לאישור או לא לביטול."
            )
        return (
            f"📋 זיהיתי ליד: {name} ({phone}){ctx_str}\n"
            f"לשמור? ענה כן לאישור או לא לביטול."
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
                    f"📋 {c['name']} ({c['phone']}){ctx_str} — ממתין לאישור ({verb}). ענה כן לאשר."
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


def should_prefer_batch_preview(canonical_user_id: str, chat_id: str) -> bool:
    """BUG-117: True if the Tier-2 batch lead-preview (pending_lead_preview,
    BUG-058) was shown to this user more recently than any Tier-1
    ActionContract prompt bookmark (last_prompted_contract, BUG-115).

    Root cause this fixes: app.py's _CONFIRM_WORDS branch used to check
    "does ANY Tier-1 ActionContract exist" unconditionally, before ever
    considering the Tier-2 batch preview — so a batch of "📋 זיהיתי N
    לידים אפשריים בקבוצה..." followed by "כן" was hijacked into generic
    disambiguation of old, unrelated Tier-1 contracts, exactly the BUG-115
    failure mode one level up (pending ActionContracts never expire —
    BUG-114 §2 Q6 — so "Tier-1 has something live" is a near-permanently
    true, mostly-irrelevant signal). BUG-115 fixed this within Tier-1
    (bookmark beats blind live-count); this fixes it between Tier-1 and
    Tier-2 by comparing which prompt is actually more recent, instead of
    Tier-1 unconditionally winning by mere presence.

    Both bookmarks are already independently TTL'd and self-clearing on
    read (pending_lead_preview: 1800s, session_store.py's
    get_pending_lead_preview; last_prompted_contract: 600s, get_
    last_prompted_contract) — this function does no expiry logic of its
    own, it only compares set_at timestamps of whatever each getter
    already considers live.

    Returns False (never prefer Tier-2) when no Tier-2 preview is live at
    all — the caller's existing Tier-1-first logic is unaffected in that
    case. Returns True when a live Tier-2 preview exists and either no
    Tier-1 bookmark exists, or the Tier-2 preview is strictly newer.
    """
    try:
        from session_store import lead_sessions as _ls
    except Exception:
        return False

    preview = _ls.get_pending_lead_preview(chat_id)
    if preview is None:
        return False

    bookmark = _ls.get_last_prompted_contract(canonical_user_id)
    if bookmark is None:
        return True
    return preview.get("set_at", 0) > bookmark.get("set_at", 0)


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

    Precedence מול Tier 1 (BUG-058 caveat, מעודכן ב-BUG-117): app.py קורא
    לפונקציה הזו גם *לפני* בדיקת ה-contract החי (דרך should_prefer_batch_
    preview() לעיל, כשהתצוגה הזו טרייה יותר מהבוקמארק של Tier-1), וגם
    כ-fallback *אחרי* (כמו קודם, כשל-Tier-1 אין כלום). "Tier 1 מנצח תמיד"
    כבר לא נכון גורף — עכשיו זה "מי שהוצג לאחרונה מנצח". הפונקציה הזו
    עצמה לא בודקת recency — ההכרעה ברמת ה-caller ב-app.py/should_prefer_
    batch_preview().
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
