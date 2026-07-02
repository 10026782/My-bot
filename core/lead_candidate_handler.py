# core/lead_candidate_handler.py — Section 4B: Deterministic LeadCandidate Handler
#
# Short-circuits the agent loop for explicit owner/staff lead-save patterns.
# Sender identity (אליהו) is immutable; subject (the lead) is resolved separately.
#
# זרימה: parse → find/create/update Airtable → Gateway ledger → GatewayReply
# Agent אינו מעורב בהחלטה — לא "האם לשמור", לא "איזה record_id", לא "הצליח".

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# Pattern extraction
# ══════════════════════════════════════════════════

_PHONE_RE = re.compile(r"(?:0\d{1,2}[-\s]?\d{7,8}|[\+]?972[-\s]?\d{8,9})")

_SAVE_WORDS = frozenset({
    "תשמור", "שמור", "שמרי", "תרשום", "רשום",
    "תוסיף", "הוסף", "תוסיפי", "save", "add",
    "שמור כליד", "הוסף כליד", "כליד",
})

# Hebrew full name: at least two words, each 2+ chars, Hebrew chars only
_HEBREW_NAME_RE = re.compile(
    r"(?<!\w)([א-ת]{2,}(?:\s+[א-ת]{2,})+)(?!\w)"
)

# Explicit prefixes: "אני", "שמו", "שמה", "ליד חדש:", "לקוח חדש:"
# מילות עצירה שמסמנות סוף שם וסוגיות נוספות
_NAME_STOP = frozenset({
    "טלפון", "מספר", "פלאפון", "נייד", "תשמור", "שמור", "שמרי",
    "תרשום", "רשום", "תוסיף", "הוסף", "save", "add", "כליד",
    "ליד", "לקוח", "חדש",
})

_PREFIXED_NAME_RE = re.compile(
    r"""(?:
        אני\s+
        | שמו\s+
        | שמה\s+
        | ליד\s+חדש[:\s]+
        | לקוח\s+חדש[:\s]+
        | תוסיף\s+ל
        | עדכן\s+את\s+
    )
    ([א-ת]{2,}(?:\s+[א-ת]{2,}){1,3})
    """,
    re.VERBOSE | re.UNICODE,
)


def _extract_phone(text: str) -> str:
    """מחלץ מספר טלפון ראשון מהטקסט — ממיר לפורמט נורמלי."""
    m = _PHONE_RE.search(text)
    if not m:
        return ""
    raw = re.sub(r"[\s\-]", "", m.group())
    if raw.startswith("+972"):
        raw = "0" + raw[4:]
    elif raw.startswith("972"):
        raw = "0" + raw[3:]
    return raw


def _has_save_intent(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in _SAVE_WORDS)


def _clean_name(raw: str) -> str:
    """מסיר מילות עצירה ידועות מסוף השם."""
    words = raw.strip().rstrip(",;:").split()
    while words and words[-1] in _NAME_STOP:
        words.pop()
    return " ".join(words)


def _extract_name(text: str) -> Optional[str]:
    """
    מחלץ שם ליד עברי מלא מהטקסט.
    מועדף: שם עם prefix מפורש; fallback: שם עברי כפול בלבד.
    """
    # Try prefixed first (highest confidence)
    m = _PREFIXED_NAME_RE.search(text)
    if m:
        name = _clean_name(m.group(1))
        if len(name) >= 4 and " " in name:
            return name

    # Fallback: any Hebrew two-word sequence not on a known stop-list
    _STOP = {"לא", "אני", "כן", "גם", "של", "עם", "על", "את", "הוא", "היא", "הם", "אנחנו"} | _NAME_STOP
    for m in _HEBREW_NAME_RE.finditer(text):
        raw = m.group(1).strip()
        name = _clean_name(raw)
        words = name.split()
        if len(words) >= 2 and len(name) >= 4:
            if not any(w in _STOP for w in words):
                return name
    return None


def parse_lead_dictation(text: str) -> Optional[dict]:
    """
    מחלץ {name, phone, raw_text} מהודעת הכתבת ליד מפורשת.
    מחזיר None אם:
    - אין שם עברי מלא
    - אין טלפון ואין כוונת שמירה
    - כוונת שמירה אבל לא ברורה מספיק (ספק)
    """
    if not text:
        return None

    name = _extract_name(text)
    if not name:
        return None

    phone = _extract_phone(text)
    has_phone = bool(phone)
    has_save = _has_save_intent(text)

    # חייב: שם + טלפון + (כוונת שמירה, או prefixed pattern שמספיק לבדו)
    # בלי טלפון: רק אם יש כוונת שמירה מפורשת
    if not has_phone and not has_save:
        return None

    # שם בלבד + כוונת שמירה בלי טלפון — דרוש בירור
    if not has_phone and has_save:
        return {"name": name, "phone": "", "raw_text": text, "needs_phone": True}

    return {"name": name, "phone": phone, "raw_text": text, "needs_phone": False}


# ══════════════════════════════════════════════════
# Airtable search — raw GET (reads don't go through airtable_gateway)
# ══════════════════════════════════════════════════

def _at_find_lead_by_name_phone(name: str, phone: str) -> Optional[str]:
    """
    מחפש ליד קיים לפי שם + טלפון.
    מחזיר record_id ראשון שנמצא, או None.
    """
    import os
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    key  = os.environ.get("AIRTABLE_API_KEY", "")
    if not base or not key:
        logger.warning("[LCH] Airtable env missing — cannot search lead")
        return None

    table_enc = urllib.parse.quote("Leads", safe="")
    url = f"https://api.airtable.com/v0/{base}/{table_enc}"
    headers = {"Authorization": f"Bearer {key}"}

    # נסה חיפוש לפי שם + טלפון תחילה
    candidates: list[dict] = []
    for formula in _search_formulas(name, phone):
        try:
            r = httpx.get(url, headers=headers,
                          params={"filterByFormula": formula, "maxRecords": 5},
                          timeout=8)
            if r.status_code == 200:
                records = r.json().get("records", [])
                if records:
                    candidates.extend(records)
                    break  # ראשון שמצא — מספיק
        except Exception as exc:
            logger.warning("[LCH] Airtable search error: %s", exc)

    if not candidates:
        return None

    # העדף record שהטלפון תואם
    if phone:
        for rec in candidates:
            rec_phone = re.sub(r"[\s\-]", "", str(rec.get("fields", {}).get("phone", "")))
            if rec_phone == phone:
                return rec["id"]

    return candidates[0]["id"]


def _search_formulas(name: str, phone: str) -> list[str]:
    """מחזיר רשימת formulas לנסות — מהמדויק לפחות מדויק."""
    safe_name  = name.replace("'", "\\'")
    formulas = []
    if phone:
        safe_phone = phone.replace("'", "\\'")
        formulas.append(f"AND(SEARCH('{safe_name}', {{Name}}), {{phone}}='{safe_phone}')")
        formulas.append(f"{{phone}}='{safe_phone}'")
    formulas.append(f"SEARCH('{safe_name}', {{Name}})")
    return formulas


# ══════════════════════════════════════════════════
# Main handler
# ══════════════════════════════════════════════════

def handle_lead_candidate(
    identity,
    text: str,
    chat_id: str,
    channel: str,
) -> Optional[str]:
    """
    מטפל דטרמיניסטית בהכתבת ליד של owner/staff.
    מחזיר מחרוזת תשובה (GatewayReply) אם הפעולה בוצעה/נחסמה/דורשת בירור.
    מחזיר None אם ההודעה לא תואמת לתבנית — ממשיכים לאייג'נט הרגיל.

    sender (identity) נשמר כפי שהוא לאורך כל הדרך.
    subject (הליד) מוחלץ ומטופל בנפרד.
    """
    # רק owner/staff
    if not getattr(identity, "is_internal", False):
        return None

    parsed = parse_lead_dictation(text)
    if parsed is None:
        return None  # not a lead-dictation pattern → normal agent

    name  = parsed["name"]
    phone = parsed.get("phone", "")

    # דרוש בירור: שם ברור אבל חסר טלפון
    if parsed.get("needs_phone"):
        logger.info("[LCH] clarification needed: name=%r no phone", name)
        return (
            f"כדי לשמור את {name} כליד — אשמח לקבל גם מספר טלפון. 📞"
        )

    # ── חיפוש ב-Airtable ─────────────────────────
    existing_id = _at_find_lead_by_name_phone(name, phone)
    action = "update" if existing_id else "create"

    # ── Gateway dedup check ───────────────────────
    tool_name   = "airtable_update" if action == "update" else "airtable_add"
    tool_inputs = {"table": "Leads", "name": name, "phone": phone}
    if existing_id:
        tool_inputs["record_id"] = existing_id

    try:
        from core.action_gateway import action_gateway as _gw, _ledger_singleton
        gw_result = _gw.propose_action(
            tenant_id         = getattr(identity, "tenant_id", "default"),
            canonical_user_id = identity.memory_key,
            tool_name         = tool_name,
            tool_inputs       = tool_inputs,
            origin_channel    = channel,
            origin_chat_id    = chat_id,
            requires_approval = False,
        )
        if not gw_result.ok:
            logger.info("[LCH] gateway blocked: %s", gw_result.reason)
            return gw_result.user_message or "⚠️ פעולה זו כבר בוצעה לאחרונה."
        contract_id = gw_result.contract_id
    except Exception as exc:
        logger.warning("[LCH] gateway propose failed (continuing): %s", exc)
        contract_id = None

    # ── Execute write ─────────────────────────────
    lead_fields = {
        "Name":  name,
        "phone": phone,
    }

    record_id = ""
    ok        = False

    try:
        from tools.airtable_gateway import airtable_create, airtable_patch

        if action == "update" and existing_id:
            ok_patch = airtable_patch("Leads", existing_id, {"phone": phone},
                                      source="lead_candidate_handler")
            if ok_patch:
                record_id = existing_id
                ok = True
        else:
            # add source + sender info for new leads
            lead_fields["source"]    = "owner_dictation"
            lead_fields["tenant_id"] = getattr(identity, "tenant_id", "")
            rec = airtable_create("Leads", lead_fields,
                                  source="lead_candidate_handler")
            if rec:
                record_id = rec.get("id", "")
                ok = bool(record_id)
    except Exception as exc:
        logger.error("[LCH] Airtable write failed: %s", exc)
        ok = False

    # ── Update ledger ─────────────────────────────
    if contract_id:
        try:
            status = "executed" if ok else "failed"
            _ledger_singleton.update_status(contract_id, status)
            if ok and record_id:
                contract = _ledger_singleton.find_by_id(contract_id)
                if contract:
                    contract.agent_observations.append({
                        "kind": "execution_fact",
                        "record_id": record_id,
                        "created_at": __import__("time").time(),
                    })
        except Exception as exc:
            logger.warning("[LCH] ledger update failed: %s", exc)

    # ── Persist to session ────────────────────────
    if ok and record_id:
        try:
            from session_store import lead_sessions as _ls
            _ls.set_active_lead_candidate(chat_id, name, record_id=record_id)
            _ls.set_current_lead_record_id(chat_id, record_id)
        except Exception as exc:
            logger.warning("[LCH] session persist failed: %s", exc)

    # ── GatewayReply ──────────────────────────────
    if not ok:
        logger.error("[LCH] write failed: action=%s name=%r", action, name)
        return f"❌ לא הצלחתי לשמור את {name}. נסה שוב או פנה לתמיכה."

    if action == "update":
        reply = f"✅ עדכנתי את {name} ({phone}) | record: {record_id}"
    else:
        reply = f"✅ שמרתי את {name} ({phone}) כליד חדש | record: {record_id}"

    logger.info("[LCH] %s: name=%r phone=%s record_id=%s", action, name, phone, record_id)
    return reply
