# core/ingress_classifier.py — C89 Stage 3: Capture Policy / IngressClassification
#
# classify_ingress() is the SINGLE entry point for all input classification.
# No module classifies input on its own — all input flows through this function.
# (Mirrors ActionContract on the output side: ActionContract unifies output,
#  IngressClassification unifies input.)
#
# Tier 1: SIMPLE_CAPTURE  — clear name+phone, auto-write via Gateway (FEATURE_AUTO_CAPTURE)
# Tier 2: CLEAN_BATCH     — multiple clean name+phone blocks, auto-write + summary
# Tier 3: MIXED_BATCH     — some clear, some ambiguous → clear ones write, rest → needs_review
# Tier 4: EXPORT/TABLE    — table/log/bot output pasted in → NEVER auto-write, preview only
# Tier 5: UNKNOWN_USEFUL  — some signal but no clear lead → Raw Capture / Inbox
#
# "Doubt → degrade toward safe, never toward fast." (§3.1 of SPEC)

from __future__ import annotations

import re
import uuid
import logging
from dataclasses import dataclass, field, replace
from typing import Optional

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# IngressClassification — the generic input contract (§10 of SPEC)
# ══════════════════════════════════════════════════

_RAW_REF_UNSET = "__unset__"  # never returned to callers — classify_ingress() always overwrites it (C89 RAW-OBS)


@dataclass(frozen=True)
class IngressClassification:
    source_type:   str          # "text" | "file" (C90) | "voice"/"email"/"image" (C91-C93, not yet implemented)
    content_class: str          # "lead" | "task" | "meeting" | "table" | "log" | "unknown"
    tier:          int          # 1-5
    confidence:    float        # 0.0 – 1.0
    reason:        str          # for AgentObservation + calibration
    raw_ref:       str = _RAW_REF_UNSET  # Decision Inbox record id or local fallback ref, set by classify_ingress() — never "" (C89 RAW-OBS)
    candidates:    tuple = ()   # extracted lead candidates for tier 1-3 (tuple of dicts, frozen)


# ══════════════════════════════════════════════════
# Tier-4 detection — must run FIRST (safety gate)
# ══════════════════════════════════════════════════

# Table/pipe separators
_TABLE_RE = re.compile(
    r"[│┃]"                                         # unicode box chars
    r"|[|]{2,}"                                     # consecutive ASCII pipes
    r"|[^|\n]+\|[^|\n]+\|[^|\n]+"                  # 2+ pipe-separated fields in a line
    r"|^\s*[\|\+][-\s\|\+]{5,}"                    # ASCII table border: |---|---|
    r"|\t[^\t]+\t[^\t]+\t",                         # TSV — 2+ tab-separated fields
    re.MULTILINE,
)

# Log/timestamp patterns
_TIMESTAMP_RE = re.compile(
    r"\[\d{1,2}/\d{1,2}/\d{4},?\s*\d{1,2}:\d{2}"   # [DD/MM/YYYY, HH:MM
    r"|\[\d{1,2}\.\d{1,2}\.\d{2,4},?\s*\d{1,2}:\d{2}"  # [DD.MM.YYYY, HH:MM] — BUG-C89-TIER4-PRECEDENCE
    r"|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"               # ISO 8601
    r"|\d{2}:\d{2}:\d{2}\s+[A-Z]{2,5}",             # HH:MM:SS UTC
)

# Bot output prefix (lines starting with status/marker emoji)
# BUG-C89-TIER4-PRECEDENCE: extended with 📋/🌤️/█ (progress bars/summaries),
# threshold lowered 3→2 lines — a genuine lead dictation never has even 2
# lines opening with these emoji, so this stays a safe, high-signal marker.
_BOT_OUTPUT_RE = re.compile(r"^[✅❌⚠️⏳🔴🟡🟢📋🌤️█]\s", re.MULTILINE)

# Airtable field/record IDs
_AIRTABLE_ID_RE = re.compile(r"\b(?:fld|rec)[A-Za-z0-9]{8,}\b")

# JSON/code block
_JSON_BLOCK_RE = re.compile(r"^\s*[\[{]", re.MULTILINE)

# WhatsApp export — sender prefix pattern "[DD/MM/YYYY, HH:MM:SS] Name:"
_WHATSAPP_EXPORT_RE = re.compile(
    r"\[\d{1,2}/\d{2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*[AP]?M?\]\s+[^:]{2,40}:"
)

# Consecutive CSV-like lines (3+ lines with ≥2 commas each)
_CSV_RE = re.compile(r"(?:[^\n,]+,[^\n,]+,[^\n]+\n){3,}")

# ── BUG-C89-TIER4-PRECEDENCE additions ──────────────────────────────
# System/tool-output field labels and literal markers — case-insensitive
# substring match. Any of these appearing anywhere means the text is a
# pasted export/log/status readout, never a fresh lead dictation.
_LITERAL_MARKERS = (
    "view in airtable", "use airtable",
    "record_id", "memory_key", "owner_dictation",
    "schedule follow-up", "status:", "score:",
    "@lead", "נקלט ליד", "זוהה ליד",
)

# memory_key literal format used by lead_candidate_handler.py:
# f"{tenant_id}/{phone_or_slug}@lead" e.g. "boss_hq/0501234567@lead"
_MEMORY_KEY_RE = re.compile(r"\b[\w.\-]+/[\w+\-]+@lead\b")

# score-like "NN/100" (e.g. "Score: 50/100")
_SCORE_LIKE_RE = re.compile(r"\b\d{1,3}\s*/\s*100\b")

# Known table-header words (English + Hebrew) — a header row (comma/tab/
# fixed-width separated) containing ≥2 of these is a table, not a lead line.
_HEADER_WORDS_EN = frozenset({"name", "phone", "city", "status", "email", "source", "domain", "score"})
_HEADER_WORDS_HE = frozenset({"שם", "טלפון", "עיר", "סטטוס", "נייד", "כתובת", "מקור", "דומיין", "ציון"})


def _looks_like_header_row(line: str) -> bool:
    parts = [p.strip() for p in re.split(r"\t|,|\s{2,}", line) if p.strip()]
    if len(parts) < 3:
        return False
    hits_en = sum(1 for p in parts if p.lower() in _HEADER_WORDS_EN)
    hits_he = sum(1 for p in parts if p in _HEADER_WORDS_HE)
    return (hits_en + hits_he) >= 2


def _has_table_header(text: str) -> bool:
    return any(_looks_like_header_row(line) for line in text.splitlines())


# Fixed-width columns: a line with ≥2 "word + 2-or-more-spaces" runs followed
# by a final word (i.e. ≥3 columns separated by 2+ spaces). Requiring ≥2 such
# lines (not just 1) keeps this from tripping on a single stray double-space.
_FIXED_WIDTH_LINE_RE = re.compile(r"^(?:\S+ {2,}){2,}\S+", re.MULTILINE)


def _has_fixed_width_table(text: str) -> bool:
    return len(_FIXED_WIDTH_LINE_RE.findall(text)) >= 2


def _is_tier4(text: str) -> tuple[bool, str]:
    """
    מחזיר (True, reason) אם הטקסט הוא פלט כלי / טבלה / לוג / ייצוא.
    בדיקות אלה רצות לפני כל פרסור (כולל חילוץ מועמדי-ליד) — Tier 4 מנצח תמיד.
    """
    if _TABLE_RE.search(text):
        return True, "table_separator"
    if _TIMESTAMP_RE.search(text):
        return True, "log_timestamp"
    if _WHATSAPP_EXPORT_RE.search(text):
        return True, "whatsapp_export"
    if _AIRTABLE_ID_RE.search(text):
        return True, "airtable_id"
    if _JSON_BLOCK_RE.match(text.strip()):
        return True, "json_block"
    if _CSV_RE.search(text):
        return True, "csv_block"
    # ≥2 lines starting with bot/system-output emoji (bot output pasted in)
    if len(_BOT_OUTPUT_RE.findall(text)) >= 2:
        return True, "bot_output_block"

    # BUG-C89-TIER4-PRECEDENCE — hard markers below run BEFORE lead
    # extraction, same as the checks above; any hit short-circuits Tier 4.
    text_lower = text.lower()
    for marker in _LITERAL_MARKERS:
        if marker in text_lower:
            return True, "system_field_leak"
    # Bare "airtable" is only a Tier-4 signal combined with other pasted-
    # content structure (colon field, newline, rec-id, memory_key) — a short
    # explicit command like "תבדוק עכשיו את Airtable" must still reach the
    # real SYSTEM_STATUS check (BUG-IC-01/C89), not get swallowed here.
    if "airtable" in text_lower and (
        "\n" in text or ":" in text
        or _AIRTABLE_ID_RE.search(text) or _MEMORY_KEY_RE.search(text)
    ):
        return True, "system_field_leak"
    if _MEMORY_KEY_RE.search(text):
        return True, "memory_key_leak"
    if _SCORE_LIKE_RE.search(text):
        return True, "score_like"
    if _has_table_header(text):
        return True, "table_header"
    if _has_fixed_width_table(text):
        return True, "fixed_width_table"

    return False, ""


# ══════════════════════════════════════════════════
# Lead candidate extraction (shared with LCH)
# ══════════════════════════════════════════════════

# requires ≥9 total digits after leading 0 — rules out "054" partial numbers
_PHONE_RE = re.compile(r"(?:0\d[-\s]?\d{3}[-\s]?\d{4,5}|0\d{2}[-\s]?\d{7}|[\+]?972[-\s]?\d{8,9})")

_NAME_STOP = frozenset({
    "טלפון", "מספר", "פלאפון", "נייד", "תשמור", "שמור", "שמרי",
    "תרשום", "רשום", "תוסיף", "הוסף", "save", "add", "כליד",
    "ליד", "לקוח", "חדש", "בשם", "השם",
    "טבריה", "חיפה", "תלאביב", "ירושלים", "נתניה", "אשדוד", "באר", "שבע",
    "רמת", "גן", "פתח", "תקווה", "ראשון", "לציון", "רחובות", "בנייה",
    "פרויקט", "פרוייקט", "דירה", "דירות", "נדלן", "נכס",
    # common chat noise
    "לא", "אני", "כן", "גם", "של", "עם", "על", "את",
    "הוא", "היא", "הם", "אנחנו", "אתם", "היום", "מחר", "ביקש", "יצר",
})

_HEBREW_WORD_RE = re.compile(r"[א-ת]{2,}")
_HEBREW_NAME_RE = re.compile(r"(?<!\w)([א-ת]{2,}(?:\s+[א-ת]{2,})+)(?!\w)")

# BUG-096: block separator — new line starting with a Hebrew letter / bullet /
# numbering / blank line. Used to bound per-candidate windows at block
# boundaries, not just at neighboring recognized phone numbers (see
# _extract_lead_candidates below).
_BLOCK_SEP = re.compile(r"\n\s*\n|\n[-•*]\s+|\n\d+[.)]\s+|\n(?=[א-ת])")

# Sender-name line pattern for WhatsApp-style chat logs (not exports):
# "דני:" or "דני כהן:" at start of line — name before colon is a SENDER, not a lead
_SENDER_LINE_RE = re.compile(r"^([א-ת]{2,}(?:\s+[א-ת]{2,})?)\s*:\s*", re.MULTILINE)


def _normalize_phone(raw: str) -> str:
    raw = re.sub(r"[\s\-]", "", raw)
    if raw.startswith("+972"):
        return "0" + raw[4:]
    if raw.startswith("972"):
        return "0" + raw[3:]
    return raw


def _candidate_confidence(name: str, phone: str, window: str) -> float:
    """
    מחשב confidence לצמד (שם, טלפון) בתוך חלון טקסט.
    0.0 – 1.0 — High ≥ 0.75, Low < 0.50.
    """
    score = 0.0
    words = name.split()

    # Phone valid
    if phone and re.match(r"^0[5-9]\d{8}$", phone):
        score += 0.40
    elif phone:
        score += 0.20

    # Name: 2+ Hebrew words
    if len(words) >= 2:
        score += 0.25
    elif len(words) == 1 and len(words[0]) >= 3:
        score += 0.10

    # Name: no stop-words
    if not any(w in _NAME_STOP for w in words):
        score += 0.20

    # Name: not a sender line (e.g. "דני: 050...")
    sender_names = {m.group(1).strip() for m in _SENDER_LINE_RE.finditer(window)}
    if name not in sender_names:
        score += 0.15

    return min(score, 1.0)


def _extract_lead_candidates(text: str) -> list[dict]:
    """
    מחלץ כל צמדי (שם, טלפון) מהטקסט עם confidence לכל אחד.
    משמש את classify_ingress לסיווג Tier 1/2/3 — זו המימוש היחיד שבאמת
    בשימוש בפרודקשן (core/lead_candidate_handler.py's parse_batch_dictation/
    parse_lead_dictation הם מימוש כפול ומת — 0 קוראים בכל הריפו, ראה BUG-096
    ב-BUG_AUDIT_LOG.md; אל תתקן שם בטעות שוב).

    BUG-096: הטקסט מפוצל קודם ל-בלוקים (_BLOCK_SEP — שורה חדשה שמתחילה
    באות עברית / bullet / מספור / שורה ריקה) לפני כל חילוץ טלפון/שם. כל
    בלוק מעובד בנפרד לגמרי (_extract_candidates_from_block), כדי שטלפון
    פגום/לא-ניתן-לזיהוי בבלוק אחד לא "יבלע" את הבלוק (כולל השם) לתוך החלון
    של הבלוק הבא — בדיוק המנגנון שגרם לחיבור שם+טלפון של שני אנשים שונים
    שנצפה בפרודקשן (ראה BUG-096).
    """
    candidates: list[dict] = []
    seen_phones: set[str] = set()
    sender_names = {m.group(1).strip() for m in _SENDER_LINE_RE.finditer(text)}

    for block in _BLOCK_SEP.split(text):
        if not block.strip():
            continue
        _extract_candidates_from_block(block, candidates, seen_phones, sender_names)

    return candidates


def _extract_candidates_from_block(
    block: str,
    candidates: list[dict],
    seen_phones: set[str],
    sender_names: set,
) -> None:
    """
    מחלץ candidates מתוך בלוק בודד (כבר מפוצל ע"י _BLOCK_SEP, ראה
    _extract_lead_candidates) ומוסיף ל-candidates.

    בתוך בלוק בודד יכולים עדיין להיות כמה זוגות שם+טלפון (למשל שורה אחת עם
    כמה לידים מופרדים בפסיקים) — לכן עדיין נדרש windowing per-phone: החלון
    מוגבל גם לגבולות הטלפון השכן *בתוך הבלוק הזה בלבד*, לא חוצה בין בלוקים,
    ולא רק ל-±80 תווים קבוע (BUG-096, ממשיך את אותו עיקרון).

    כל candidate נושא גם "raw_text" — הבלוק המקורי שלו בלבד, לא כל ההודעה —
    כדי ש-Summary/Lead Event/lead_memory לכל ליד ישקפו רק אותו (BUG-096-B:
    לפני זה כל הלידים בבאצ' קיבלו את אותו טקסט מלא כ-summary, כולל תוכן של
    אנשים אחרים).
    """
    phone_matches = list(_PHONE_RE.finditer(block))
    for i, phone_match in enumerate(phone_matches):
        phone = _normalize_phone(phone_match.group())
        if phone in seen_phones:
            continue
        seen_phones.add(phone)

        prev_end   = phone_matches[i - 1].end() if i > 0 else 0
        next_start = phone_matches[i + 1].start() if i + 1 < len(phone_matches) else len(block)
        start  = max(0, phone_match.start() - 80, prev_end)
        end    = min(len(block), phone_match.end() + 80, next_start)
        window = block[start:end]

        name = _extract_name_from_window(window, sender_names)
        if not name:
            continue

        conf = _candidate_confidence(name, phone, window)
        ctx  = _extract_context_kw(window, name, phone)

        candidates.append({
            "name":       name,
            "phone":      phone,
            "confidence": conf,
            "context":    ctx,
            "raw_text":   block.strip(),
        })


def _extract_name_from_window(window: str, sender_names: set) -> Optional[str]:
    """מחלץ שם עברי מחלון טקסט, מסנן sender names ומילות עצירה."""
    for m in _HEBREW_NAME_RE.finditer(window):
        raw   = m.group(1).strip().rstrip(",;:")
        words = raw.split()
        # Clean trailing stop-words
        while words and words[-1] in _NAME_STOP:
            words.pop()
        name = " ".join(words)
        if not name or len(name) < 4:
            continue
        if any(w in _NAME_STOP for w in name.split()):
            continue
        if name in sender_names:
            continue
        return name
    return None


_CONTEXT_WORDS = frozenset({
    "טבריה", "חיפה", "ירושלים", "נתניה", "אשדוד", "רחובות",
    "עכו", "נצרת", "אילת", "פתח", "תקווה", "ראשון", "לציון",
    "מעלה", "עמוס", "ערד", "דימונה", "קריות",
    "פרויקט", "פרוייקט", "דירה", "דירות", "נדלן", "נכס", "בנייה",
})


def _extract_context_kw(text: str, name: str, phone: str) -> list[str]:
    cleaned = text
    if name:
        cleaned = cleaned.replace(name, " ")
    if phone:
        cleaned = _PHONE_RE.sub(" ", cleaned)
    return [w for w in _HEBREW_WORD_RE.findall(cleaned) if w in _CONTEXT_WORDS]


# ══════════════════════════════════════════════════
# Tier thresholds
# ══════════════════════════════════════════════════

_HIGH_CONF = 0.75   # Tier 1/2: auto-write
_LOW_CONF  = 0.50   # below this → needs_review in Tier 3


# ══════════════════════════════════════════════════
# C89 RAW-OBS — raw capture + classification observation
# ══════════════════════════════════════════════════

def _save_raw_capture(text: str, source_type: str) -> str:
    """
    שומר את הטקסט הגולמי ל-Decision Inbox (Tables.DECISION_INBOX — "entry
    door for forwarded/raw input", RAW_INPUT field) ומחזיר reference.

    Best-effort ומאחורי FEATURE_RAW_CAPTURE (כבוי כברירת מחדל): כשל
    בכתיבה/Airtable לא מוגדר/הדגל כבוי — לעולם לא חוסם את הסיווג עצמו, ותמיד
    מחזיר reference לא-ריק (fallback מקומי אם אין כתיבה חיה).
    """
    local_ref = f"local:{uuid.uuid4().hex[:16]}"
    try:
        from feature_flags import is_enabled
        if not is_enabled("FEATURE_RAW_CAPTURE"):
            return local_ref
        from tools.airtable_gateway import airtable_create
        from airtable_schema import Tables, DecisionInboxFields, DecisionInboxChannel, DecisionInboxStatus
        rec = airtable_create(
            Tables.DECISION_INBOX,
            {
                DecisionInboxFields.RAW_INPUT: text,
                DecisionInboxFields.CHANNEL:   DecisionInboxChannel.MANUAL,
                DecisionInboxFields.STATUS:    DecisionInboxStatus.PENDING,
            },
            source="ingress_classifier",
        )
        if rec and rec.get("id"):
            return rec["id"]
        return local_ref
    except Exception as exc:
        logger.debug("[IngressClassifier] raw capture write failed (non-blocking): %s", exc)
        return local_ref


def _record_classification_observation(ic: IngressClassification) -> None:
    """
    רושם AgentObservation (kind="capture_classification") לכל סיווג — משתמש
    אך ורק ב-API הקיים של ActionGateway.record_agent_observation()
    (contract_id=None: אינו קשור לשום ActionContract ספציפי; לא נוגע בליבת
    ה-Gateway). Best-effort — כשל בייבוא/קריאה לעולם לא חוסם את הסיווג עצמו.
    """
    try:
        from core.action_gateway import action_gateway
        action_gateway.record_agent_observation(
            contract_id=None,
            kind="capture_classification",
            text=(
                f"tier={ic.tier} confidence={ic.confidence:.2f} "
                f"reason={ic.reason} raw_ref={ic.raw_ref}"
            ),
        )
    except Exception as exc:
        logger.debug("[IngressClassifier] capture_classification observation failed (non-blocking): %s", exc)


# ══════════════════════════════════════════════════
# classify_ingress — the single entry point
# ══════════════════════════════════════════════════

def classify_ingress(
    text: str,
    source_type: str = "text",
) -> IngressClassification:
    """
    מסווג קלט טקסט לאחד מ-5 Tiers.

    השתמש בזה לפני כל החלטת כתיבה. אסור לשום מודול לסווג קלט בעצמו.

    source_type: "text" | "file" (C90: same Tier 1-5 logic as text, no special-casing —
                 the caller decides *that* a row reaches here, not how it's classified) |
                 "voice"/"email"/"image" (C91-C93, not yet implemented, fallback Tier 5)

    C89 RAW-OBS: לכל קריאה (כל Tier 1-5, כולל empty_text/source_type לא
    נתמך) נשמר raw_ref לא-ריק (הפניה ל-Decision Inbox כש-FEATURE_RAW_CAPTURE
    פעיל, אחרת reference מקומי) ונרשם AgentObservation
    kind="capture_classification" — ראה _save_raw_capture/
    _record_classification_observation למעלה.
    """
    ic = _classify_ingress_core(text, source_type)
    raw_ref = _save_raw_capture(text, source_type)
    ic = replace(ic, raw_ref=raw_ref)
    _record_classification_observation(ic)
    return ic


def _classify_ingress_core(
    text: str,
    source_type: str,
) -> IngressClassification:
    """הלוגיקה המקורית של הסיווג — ללא raw_ref/observation, שמעליהם עוטף classify_ingress()."""
    # ── C90: source_type="file" reuses the EXACT SAME tier logic as text ──
    # No special-casing: a file row is an ingress-source-adapter concern
    # (app.py / core/file_ingress_adapter.py decide *that* a row reaches
    # here), not a classification concern. The row's text runs through the
    # identical Tier4-hard-marker/extraction/confidence pipeline below —
    # a row with a clear name+phone can legitimately resolve to Tier 1/2/3,
    # same as any text message. Only genuinely unimplemented source types
    # (voice/email/image, C91-C93) short-circuit here.
    if source_type not in ("text", "file"):
        return IngressClassification(
            source_type=source_type,
            content_class="unknown",
            tier=5,
            confidence=0.0,
            reason=f"source_type={source_type} not implemented (C91+)",
            candidates=(),
        )

    if not text or not text.strip():
        return IngressClassification(
            source_type=source_type,
            content_class="unknown",
            tier=5,
            confidence=0.0,
            reason="empty_text",
            candidates=(),
        )

    # ── Tier 4 gate — ALWAYS first ──────────────────
    is_t4, t4_reason = _is_tier4(text)
    if is_t4:
        return IngressClassification(
            source_type=source_type,
            content_class="table",
            tier=4,
            confidence=1.0,
            reason=t4_reason,
            candidates=(),
        )

    # ── Extract lead candidates ───────────────────
    candidates = _extract_lead_candidates(text)

    if not candidates:
        return IngressClassification(
            source_type=source_type,
            content_class="unknown",
            tier=5,
            confidence=0.0,
            reason="no_lead_candidates",
            candidates=(),
        )

    high  = [c for c in candidates if c["confidence"] >= _HIGH_CONF]
    low   = [c for c in candidates if c["confidence"] < _HIGH_CONF]

    # ── Tier 1: single high-confidence candidate ──
    if len(candidates) == 1 and high:
        c = candidates[0]
        return IngressClassification(
            source_type=source_type,
            content_class="lead",
            tier=1,
            confidence=c["confidence"],
            reason="single_high_confidence",
            candidates=tuple(candidates),
        )

    # ── Tier 2: multiple all high-confidence ─────
    if len(candidates) >= 2 and not low:
        avg_conf = sum(c["confidence"] for c in candidates) / len(candidates)
        return IngressClassification(
            source_type=source_type,
            content_class="lead",
            tier=2,
            confidence=avg_conf,
            reason=f"clean_batch_{len(candidates)}_items",
            candidates=tuple(candidates),
        )

    # ── Tier 3: mixed (some high, some low) ──────
    if high:
        avg_conf = sum(c["confidence"] for c in high) / len(high)
        return IngressClassification(
            source_type=source_type,
            content_class="lead",
            tier=3,
            confidence=avg_conf,
            reason=f"mixed_batch_high={len(high)}_low={len(low)}",
            candidates=tuple(candidates),
        )

    # ── All candidates low-confidence → Tier 5 ───
    return IngressClassification(
        source_type=source_type,
        content_class="unknown",
        tier=5,
        confidence=max((c["confidence"] for c in candidates), default=0.0),
        reason=f"all_low_confidence_{len(candidates)}_candidates",
        candidates=tuple(candidates),
    )


# ══════════════════════════════════════════════════
# AgentObservation helper
# ══════════════════════════════════════════════════

def log_classification(ic: IngressClassification, chat_id: str = "") -> None:
    """
    רושם את החלטת הסיווג כ-AgentObservation (לוג בלבד, לא user-facing).
    אחרי 2 שבועות — מנתחים Tier 5→1 drift ו-Tier 1 correction rate.
    """
    logger.info(
        "[IngressClassifier] tier=%d conf=%.2f class=%s reason=%s candidates=%d chat=%s",
        ic.tier, ic.confidence, ic.content_class, ic.reason,
        len(ic.candidates), chat_id,
    )
