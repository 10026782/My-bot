# contact_resolver.py — N03 Contact Resolver
# "שלח מייל לדניאל" → fuzzy search ב-Contacts → אם כפילות → אישור → מבצע
#
# flag: CONTACT_RESOLVER (כבוי ברירת מחדל)
# רישום: tool_registry.py + schemas.py + dispatcher.py (patch מצורף)
#
# זרימה:
#   resolve(name, identity) → ResolveResult
#     FOUND_ONE   → מבצע מיד
#     AMBIGUOUS   → מחזיר אפשרויות לאישור משתמש
#     NOT_FOUND   → מדווח בצורה נקייה
#
# חוק ברזל: לא מבצע פעולה על קשר לא מזוהה בוודאות.

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════

class ResolveStatus(str, Enum):
    FOUND_ONE  = "found_one"   # התאמה ברורה אחת
    AMBIGUOUS  = "ambiguous"   # כמה אפשרויות — צריך אישור
    NOT_FOUND  = "not_found"   # לא נמצא כלל


@dataclass
class ContactMatch:
    record_id:    str
    name:         str
    email:        str  = ""
    phone:        str  = ""
    contact_type: str  = ""
    company:      str  = ""
    score:        float = 0.0   # 0–1, גבוה = יותר טוב


@dataclass
class ResolveResult:
    status:   ResolveStatus
    query:    str
    matches:  list[ContactMatch] = field(default_factory=list)
    message:  str = ""          # מה להציג למשתמש

    @property
    def contact(self) -> Optional[ContactMatch]:
        """מחזיר את ההתאמה הראשונה (כשיש FOUND_ONE)."""
        return self.matches[0] if self.matches else None


# ══════════════════════════════════════════════════
# Fuzzy Matching Engine (ללא ספרייה חיצונית)
# ══════════════════════════════════════════════════

def _normalize(text: str) -> str:
    """מנרמל טקסט להשוואה: lowercase, ללא ניקוד, חיתוך רווחים."""
    text = text.strip().lower()
    # הסרת ניקוד עברי (Unicode range U+05B0–U+05C7)
    text = re.sub(r'[\u05B0-\u05C7]', '', text)
    return text


def _score_match(query_norm: str, name_norm: str) -> float:
    """
    מחזיר ציון 0–1 לפי מידת ההתאמה.
    שיטות (מהחלטי לפחות):
    1. Exact match → 1.0
    2. Starts with → 0.9
    3. Query מכיל ב-name (substring) → 0.75
    4. כל מילה בquery מופיעה ב-name → 0.65
    5. אחוז אותיות משותפות → 0.3–0.6
    """
    if not query_norm or not name_norm:
        return 0.0

    # 1. Exact
    if query_norm == name_norm:
        return 1.0

    # 2. Starts with
    if name_norm.startswith(query_norm) or query_norm.startswith(name_norm):
        return 0.9

    # 3. Substring
    if query_norm in name_norm:
        return 0.75

    # 4. Word overlap (לשמות מרובי מילים)
    q_words = set(query_norm.split())
    n_words = set(name_norm.split())
    if q_words and q_words.issubset(n_words):
        return 0.80
    if q_words and n_words:
        overlap = len(q_words & n_words)
        if overlap > 0:
            return 0.65 * (overlap / max(len(q_words), len(n_words)))

    # 5. Character overlap (Jaccard)
    q_chars = set(query_norm)
    n_chars = set(name_norm)
    union   = q_chars | n_chars
    if not union:
        return 0.0
    jaccard = len(q_chars & n_chars) / len(union)
    return 0.3 * jaccard  # ציון נמוך — fallback בלבד


# ── Threshold ─────────────────────────────────────
_SCORE_MIN       = 0.50   # מתחת → מתעלמים
_SCORE_CONFIDENT = 0.80   # מעל + יחיד → FOUND_ONE
_SCORE_AMBIGUOUS = 0.50   # מעל → נכנס לרשימת אפשרויות


# ══════════════════════════════════════════════════
# Search in Airtable Contacts
# ══════════════════════════════════════════════════

def _fetch_contacts(identity=None) -> list[dict]:
    """
    שולף אנשי קשר מ-Airtable דרך crm.
    מחזיר list[dict] עם {record_id, name, email, phone, type, company}.
    """
    try:
        from crm import crm_list_contacts  # type: ignore
        raw = crm_list_contacts(identity=identity)
        return _parse_contacts_output(raw)
    except ImportError:
        logger.warning("[ContactResolver] crm not available — using mock")
        return _mock_contacts()
    except Exception as e:
        logger.error(f"[ContactResolver] fetch error: {e}")
        return []


def _parse_contacts_output(raw: str) -> list[dict]:
    """
    Parser ל-string שמחזיר crm_list_contacts.
    format per line: "• *Name* [Type] | 📞 Phone | 🏢 Company\n  ID: `recXXX`"
    """
    contacts = []
    lines    = raw.splitlines() if raw else []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("•"):
            # שורת קשר
            record_id = ""
            # שורה הבאה — ID
            if i + 1 < len(lines) and "ID:" in lines[i + 1]:
                id_match = re.search(r'`(rec\w+)`', lines[i + 1])
                if id_match:
                    record_id = id_match.group(1)
                i += 1  # דלג גם על שורת ID

            # Name בין ** **
            name_match = re.search(r'\*(.+?)\*', line)
            name       = name_match.group(1) if name_match else ""

            # Type בין []
            type_match = re.search(r'\[(.+?)\]', line)
            ctype      = type_match.group(1) if type_match else ""

            # Phone אחרי 📞
            phone_match = re.search(r'📞\s*([\d+\-]+)', line)
            phone       = phone_match.group(1) if phone_match else ""

            # Company אחרי 🏢
            company_match = re.search(r'🏢\s*(.+?)(\s*\|.*)?$', line)
            company       = company_match.group(1).strip() if company_match else ""

            if name:
                contacts.append({
                    "record_id": record_id,
                    "name":      name,
                    "email":     "",      # crm_list_contacts לא מחזיר email ישירות
                    "phone":     phone,
                    "type":      ctype,
                    "company":   company,
                })
        i += 1
    return contacts


def _mock_contacts() -> list[dict]:
    """מוק לסביבת בדיקה."""
    return [
        {"record_id": "rec001", "name": "דניאל כהן",    "email": "daniel@example.com", "phone": "050-1111111", "type": "Client",   "company": "כהן נדל\"ן"},
        {"record_id": "rec002", "name": "דניאל לוי",    "email": "dlevy@import.com",   "phone": "050-2222222", "type": "Supplier",  "company": "לוי ייבוא"},
        {"record_id": "rec003", "name": "רחל שמיר",     "email": "rachel@law.co.il",   "phone": "03-3333333",  "type": "Lawyer",    "company": "שמיר ושות'"},
        {"record_id": "rec004", "name": "משה גרינברג",  "email": "moshe@moshe.com",    "phone": "052-4444444", "type": "Partner",   "company": "גרינברג השקעות"},
        {"record_id": "rec005", "name": "יוסי אברהם",   "email": "yossi@yossi.co.il",  "phone": "054-5555555", "type": "Client",    "company": ""},
    ]


# ══════════════════════════════════════════════════
# Core Resolver
# ══════════════════════════════════════════════════

def resolve(query: str, identity=None) -> ResolveResult:
    """
    מחפש קשר לפי שם (fuzzy).
    מחזיר ResolveResult עם status + matches.

    השתמש בתוצאה:
      FOUND_ONE  → result.contact → בצע פעולה
      AMBIGUOUS  → הצג result.message לuser → בקש בחירה
      NOT_FOUND  → result.message → הסבר ידידותי
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("CONTACT_RESOLVER"):
            logger.info("[ContactResolver] flag OFF — falling back to raw query")
            return ResolveResult(
                status  = ResolveStatus.NOT_FOUND,
                query   = query,
                message = f"🔍 חיפוש קשר לא פעיל. ציין כתובת מייל ישירה.",
            )
    except ImportError:
        pass  # dev mode — ממשיך

    if not query or not query.strip():
        return ResolveResult(
            status  = ResolveStatus.NOT_FOUND,
            query   = query,
            message = "❓ לא ניתן לחפש — שם ריק.",
        )

    query_norm = _normalize(query)
    contacts   = _fetch_contacts(identity)

    if not contacts:
        return ResolveResult(
            status  = ResolveStatus.NOT_FOUND,
            query   = query,
            message = "📭 אין אנשי קשר במערכת.",
        )

    # ── Scoring ───────────────────────────────────
    scored: list[ContactMatch] = []
    for c in contacts:
        name_norm = _normalize(c.get("name", ""))
        score     = _score_match(query_norm, name_norm)
        if score >= _SCORE_MIN:
            scored.append(ContactMatch(
                record_id    = c.get("record_id", ""),
                name         = c.get("name", ""),
                email        = c.get("email", ""),
                phone        = c.get("phone", ""),
                contact_type = c.get("type", ""),
                company      = c.get("company", ""),
                score        = score,
            ))

    scored.sort(key=lambda x: x.score, reverse=True)

    # ── NOT_FOUND ─────────────────────────────────
    if not scored:
        return ResolveResult(
            status  = ResolveStatus.NOT_FOUND,
            query   = query,
            message = (
                f"❌ לא נמצא קשר בשם *{query}*.\n"
                f"ניתן להוסיף אותו למערכת או לחפש בשם אחר."
            ),
        )

    # ── FOUND_ONE ─────────────────────────────────
    top = scored[0]
    if top.score >= _SCORE_CONFIDENT:
        # בדוק שאין מתחרה קרוב מאוד (פחות מ-0.05 פחות)
        rival = scored[1] if len(scored) > 1 else None
        if rival is None or (top.score - rival.score) >= 0.10:
            logger.info(f"[ContactResolver] FOUND_ONE: {top.name} (score={top.score:.2f})")
            return ResolveResult(
                status  = ResolveStatus.FOUND_ONE,
                query   = query,
                matches = [top],
                message = f"✅ נמצא: *{top.name}*" + (f" ({top.company})" if top.company else ""),
            )

    # ── AMBIGUOUS ─────────────────────────────────
    # מגבלה: עד 5 אפשרויות
    candidates = scored[:5]
    lines = [f"🔍 מצאתי {len(candidates)} אפשרויות עבור *{query}* — בחר:"]
    for i, m in enumerate(candidates, 1):
        detail = f"{m.contact_type}" + (f" | {m.company}" if m.company else "")
        lines.append(f"{i}. *{m.name}* ({detail})")
    lines.append("\nהשב עם מספר הקשר הרצוי.")

    logger.info(f"[ContactResolver] AMBIGUOUS: {len(candidates)} candidates for '{query}'")
    return ResolveResult(
        status  = ResolveStatus.AMBIGUOUS,
        query   = query,
        matches = candidates,
        message = "\n".join(lines),
    )


# ══════════════════════════════════════════════════
# Tool Interface — resolve_contact()
# (זו הפונקציה שה-dispatcher קורא לה)
# ══════════════════════════════════════════════════

def resolve_contact(name_query: str, identity=None) -> str:
    """
    ממשק כלי ל-dispatcher.
    מחזיר string מוכן לתצוגה.
    """
    result = resolve(name_query, identity)

    if result.status == ResolveStatus.FOUND_ONE:
        c = result.contact
        parts = [result.message]
        if c.email:
            parts.append(f"📧 {c.email}")
        if c.phone:
            parts.append(f"📞 {c.phone}")
        parts.append(f"🆔 `{c.record_id}`")
        return "\n".join(parts)

    # AMBIGUOUS / NOT_FOUND — המסר כבר בנוי ב-result.message
    return result.message


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc: str, cond: bool):
        nonlocal passed, failed
        if cond:
            print(f"✅ {desc}")
            passed += 1
        else:
            print(f"❌ {desc}")
            failed += 1

    # ── _normalize ────────────────────────────────
    chk("normalize lowercase",     _normalize("DANIEL") == "daniel")
    chk("normalize strip spaces",  _normalize("  דניאל  ") == "דניאל")

    # ── _score_match ──────────────────────────────
    chk("score exact = 1.0",       _score_match("daniel", "daniel") == 1.0)
    chk("score startswith = 0.9",  _score_match("דניאל", "דניאל כהן") >= 0.85)
    chk("score substring = 0.75",  _score_match("שמיר", "רחל שמיר")  >= 0.70)
    chk("score unrelated < 0.3",   _score_match("xyz123", "daniel")   < 0.30)

    # ── resolve with mocks ────────────────────────

    # דניאל — שני קשרים → AMBIGUOUS
    r = resolve("דניאל")
    chk("'דניאל' → AMBIGUOUS (שני דניאלים)",
        r.status == ResolveStatus.AMBIGUOUS)
    chk("AMBIGUOUS has 2+ matches", len(r.matches) >= 2)

    # רחל — יחידה → FOUND_ONE
    r2 = resolve("רחל")
    chk("'רחל' → FOUND_ONE", r2.status == ResolveStatus.FOUND_ONE)
    chk("FOUND_ONE name contains 'רחל'", "רחל" in r2.contact.name)

    # שם לא קיים → NOT_FOUND
    r3 = resolve("אלברט איינשטיין")
    chk("unknown name → NOT_FOUND", r3.status == ResolveStatus.NOT_FOUND)

    # שם ריק → NOT_FOUND
    r4 = resolve("")
    chk("empty query → NOT_FOUND", r4.status == ResolveStatus.NOT_FOUND)

    # resolve_contact string output
    out = resolve_contact("רחל")
    chk("resolve_contact returns string", isinstance(out, str) and len(out) > 0)
    chk("resolve_contact includes email", "rachel@law.co.il" in out)

    print(f"\n{'='*40}")
    print(f"N03 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    ok = _run_tests()
    exit(0 if ok else 1)
