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


# BUG-101a: invisible bidi control characters (RLM/LRM/embedding-override
# marks) are a common artifact of copy-pasting mixed Hebrew/English text from
# a phone (e.g. WhatsApp chat exports) — e.g. "[נייד] ‏ +972 54-211-6211
# ‏" from a real production incident. Left in place, they silently break
# every downstream regex that expects a contiguous match (_TIMESTAMP_RE,
# _WHATSAPP_EXPORT_RE, _BLOCK_SEP, _SENDER_LINE_RE) — a single such mark
# inside a "[DD.MM.YYYY, HH:MM]" bracket is enough to defeat Tier-4 detection
# entirely, letting export/log text fall through into lead extraction (see
# BUG-101 umbrella). Stripped once, at the top of classification, so every
# regex below always sees the same clean text — not patched individually.
_BIDI_CONTROL_RE = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def _strip_bidi_controls(text: str) -> str:
    return _BIDI_CONTROL_RE.sub("", text)


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
# BUG-116: a bare "\b(?:fld|rec)[A-Za-z0-9]{8,}\b" also matches ordinary
# English words like "recruitment" ("rec" + "ruitment", 8 letters) typed as
# a literal domain hint — a real production false positive that blocked an
# otherwise plain lead-creation sentence before extraction ever ran. Real
# Airtable record/field IDs are random base62 strings; every genuine-ID test
# fixture in this suite (e.g. "recABC1234567890", "recRvK6hFTNgyj8ag")
# mixes letters and digits, while a real word never contains a digit.
# Requiring at least one digit in the matched run keeps true-positive
# detection of pasted IDs intact while ruling out plain-English words.
_AIRTABLE_ID_RE = re.compile(r"\b(?:fld|rec)(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{8,}\b")

# JSON/code block
# BUG-111: a leading "[" alone is not enough — a WhatsApp-style short-date
# timestamp bracket with no year ("[18.7, 22:02] אורי צדוק: ...", day.month
# only) also starts with "[" and was being misclassified as "json_block"
# (an accidental, wrong-reason Tier-4 hit) purely because it happens to open
# with a bracket. A leading "[" immediately followed by a day[./]month digit
# pair is a timestamp, never a JSON array — excluded via negative lookahead.
# A genuine JSON array/object is untouched (its content is never shaped like
# a date prefix at the very first characters).
_JSON_BLOCK_RE = re.compile(r"^\s*(?:\{|\[(?!\d{1,2}[./]\d{1,2}))", re.MULTILINE)

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
#
# BUG-111: mobile numbers grouped as "05X-XXX-XXXX" (a SECOND internal
# separator between the 3-digit prefix and the 3-digit block, e.g.
# "053-311-6744") and international numbers grouped the same way (e.g.
# "+972 53-396-8395") were not matched by any prior alternative — each one
# only tolerated a single internal separator. BUG-101's own comment already
# flagged the international case as a known, deliberately-deferred gap
# ("+972 54-211-6211 ... not fixed here"); this closes it. The two NEW
# alternatives below are added FIRST (both other alternatives remain,
# unchanged, for formats they already covered) so a two-separator number is
# matched in one shot instead of arbitrarily via a shorter alternative.
_PHONE_RE = re.compile(
    r"(?:0\d{2}[-\s]?\d{3}[-\s]?\d{4}"                  # NEW: 05X-XXX-XXXX (mobile, 2-separator)
    r"|\+?972[-\s]?\d{2}[-\s]?\d{3}[-\s]?\d{4}"          # NEW: +972-XX-XXX-XXXX (intl, 2-separator)
    r"|0\d[-\s]?\d{3}[-\s]?\d{4,5}"
    r"|0\d{2}[-\s]?\d{7}"
    r"|[\+]?972[-\s]?\d{8,9})"
)

_NAME_STOP = frozenset({
    "טלפון", "מספר", "פלאפון", "נייד", "תשמור", "שמור", "שמרי",
    "תרשום", "רשום", "תוסיף", "הוסף", "save", "add", "כליד",
    "ליד", "לקוח", "חדש", "בשם", "השם",
    # BUG-111 follow-up: plural forms of "ליד"/"חדש" ("לידים חדשים" = "new
    # leads", as in "צור 3 לידים חדשים ..."). Only the singular forms were
    # ever added (BUG-111 original), so a batch-creation header using the
    # plural survived segmentation and got accepted as a fake candidate name
    # whenever no block/line separator isolated it first (compact/glued
    # WhatsApp paste with no boundary between the header and the first
    # phone). Nouns, not verbs — unlike "צור" (see the BUG-111 comment
    # above), adding these does not reopen the "בדירת" tie-break regression
    # from test_bug099b1_no_name_validation.py, since neither word appears
    # in that test's property-description text.
    "לידים", "חדשים",
    "טבריה", "חיפה", "תלאביב", "ירושלים", "נתניה", "אשדוד", "באר", "שבע",
    "רמת", "גן", "פתח", "תקווה", "ראשון", "לציון", "רחובות", "בנייה",
    "פרויקט", "פרוייקט", "דירה", "דירות", "נדלן", "נכס",
    # common chat noise
    "לא", "אני", "כן", "גם", "של", "עם", "על", "את",
    "הוא", "היא", "הם", "אנחנו", "אתם", "היום", "מחר", "ביקש", "יצר",
    # BUG-097: interest/intent verbs that follow a name with no separator
    # the block/window logic recognizes (e.g. "משה אבני מעוניין ב3 חדרים
    # 0546..." — phone at the end of the block, not right after the name).
    # _HEBREW_NAME_RE greedily matches the whole contiguous Hebrew-word run,
    # so without these in _NAME_STOP the trailing-word trim in
    # _extract_name_from_window() has nothing to strip and the verb gets
    # kept as if it were part of the person's name.
    "מעוניין", "מעוניינת", "רוצה", "רוצים", "רוצות", "מחפש", "מחפשת",
    "צריך", "צריכה", "מבקש", "מבקשת",
    # BUG-099a: property-description vocabulary. When a description sits
    # between the name and phone (outside _extract_name_from_window()'s
    # +-80-char window around the phone), _HEBREW_NAME_RE's first match
    # inside the window used to be accepted as the "name" verbatim — e.g.
    # "חדרים קומה ראשונה" written to Leads.Name in production
    # (recRvK6hFTNgyj8ag, BUG-099). None of these words were previously
    # in _NAME_STOP (only cities/streets were covered) — the existing
    # stop-word rejection logic already handles this correctly once the
    # vocabulary is present (see _is_name_stop_token, BUG-099b.1); no new
    # extraction logic needed.
    "קומה", "חדרים", "ראשונה", "שנייה", "שניה", "שלישית", "רביעית",
    "חמישית", "שישית", "שביעית", "מרפסת", "מטבח", "חניה", "מעלית",
    "נוף", "משופץ", "משופצת", "צמודה", "צמוד", "קרקעית", "תת",
    "לגמרי", "מאוד", "שמש",
    # BUG-111: the domain/routing-context keyword itself ("דומיין"/
    # "לדומיין" — the "ל" prefix is stripped by _is_name_stop_token()'s
    # existing single-letter-prefix check, so bare "דומיין" here also
    # covers "לדומיין"), kept as defense-in-depth for the rare case where
    # _strip_domain_hint() below doesn't apply (e.g. "דומיין" with nothing
    # recognizable after it). The primary fix for "צור ליד דומיין גיוס..."
    # is _strip_domain_hint()/_extract_domain_hint() below — removing the
    # WHOLE "דומיין X" phrase (keyword + hint word) from the name-extraction
    # window before segmentation ever runs, not adding words to this list.
    # Deliberately does NOT add "צור" (create) here: it is already too
    # short (3 chars) to ever survive _extract_name_from_window()'s length
    # check on its own, and adding it as a stop-word instead changes the
    # stop-word split points and reopens a case that BUG-099b.1 (see
    # test_bug099b1_no_name_validation.py T9) already covers — "בדירת" in
    # "צור ליד חדש מעוניין בדירת 4 חדרים..." would win an unintended
    # segment tie-break and be accepted as a fake name.
    "דומיין",
    # BUG-135: the bot's OWN confirmation-template verb ("📋 זיהיתי ליד:
    # *X* (phone)"). When inbound text quotes/forwards/echoes that template
    # (e.g. a user pasting the bot's own prior reply back), "זיהיתי" sat
    # right before the real name inside one contiguous _HEBREW_NAME_RE run
    # ("זיהיתי ליד: *משה חביב* (0501112222)" → one match "זיהיתי ליד",
    # a SECOND separate match "משה חביב"). "ליד" was already a stop-word so
    # segmentation isolated "זיהיתי" alone as a (bogus, but >=4-char)
    # candidate — and _extract_name_from_window() RETURNS on the first
    # regex match that clears validation, so the second, correct match
    # ("משה חביב") was never reached. Adding "זיהיתי" here empties that
    # first match's only segment, so the loop correctly moves on to the
    # real name in the second match.
    "זיהיתי",
    # BUG-135: delete-command verbs. Mirrors the router's own DELETE_TASK
    # verb set (core/router/intent_router.py: r"(מחק|הסר)...") — this
    # module has no delete-specific handling of its own, so a bare
    # "תמחק/מחק/הסר איש קשר <phone>" (no real name, just the generic
    # "contact" role-noun) falls through to the same generic name+phone
    # extraction as create/update commands. Without these as stop-words,
    # the verb survived as part of the "name" segment (e.g. "תמחק איש קשר"
    # written as a fake lead name) instead of being stripped like the
    # existing create-verbs (תוסיף/הוסף/תרשום/רשום) already are.
    "תמחק", "מחק", "הסר",
})

# BUG-135: exact-phrase reject list — generic role-noun phrases that survive
# _NAME_STOP segmentation as a >=4-char segment but are still not a name
# (e.g. "תמחק איש קשר 0536272637": "תמחק" is a stop-word above, but "איש"/
# "קשר" individually are NOT — deliberately, since "איש קשר X" ("contact
# person <name>") is a legitimate way to phrase a real candidate name, e.g.
# "תוסיף איש קשר בדיקה טלפון X" must still extract "איש קשר בדיקה" verbatim
# (existing, working production behavior — do not regress it). Only the
# EXACT bare phrase, with nothing else surviving alongside it, is rejected;
# any additional surviving word (like "בדיקה" above) keeps the whole segment.
_GENERIC_NAME_PHRASES = frozenset({"איש קשר"})

_HEBREW_WORD_RE = re.compile(r"[א-ת]{2,}")
_HEBREW_NAME_RE = re.compile(r"(?<!\w)([א-ת]{2,}(?:\s+[א-ת]{2,})+)(?!\w)")

# BUG-099b.1: single-letter Hebrew prepositions/conjunctions (ב/ל/כ/מ/ש/ו/ה)
# attach directly to the following word with no space — "קומה" (floor) is in
# _NAME_STOP, but "בקומה" ("on/at-the-floor") is a different token and was
# not recognized as a stop-word at all, so a message with NO real name at all
# ("...בקומה חמישית טלפון 0501234571") had "בקומה" survive segmentation as
# the only non-empty segment and get written as the lead's Name.
#
# _is_name_stop_token() is the SINGLE shared helper for this check — every
# call site in the name-segmentation/name-validation path must go through it
# instead of a direct `token in _NAME_STOP`, or a bare/prefixed form could
# get inconsistent treatment between call sites (exactly what happened here:
# the segmentation loop and _candidate_confidence()'s "no stop-words" bonus
# were two separate direct-membership checks before this fix).
#
# Deliberately narrow: checks ONE single-letter prefix only. Does not
# recurse (no handling of stacked prefixes like "ובקומה" = ו+ב+קומה — no
# production reproduction for that shape yet), does no stemming/morphology.
# "מהדירה" (מ + ה + דירה, two stacked prefixes) is intentionally NOT matched
# — stripping one prefix leaves "הדירה", which is not itself in _NAME_STOP.
# A real name is never rejected just for starting with one of these letters
# unless the remainder, on its own, is already a known stop-word (checked
# below in the test suite: "בנימין"/"משה"/"הלל"/"שחר" all stay valid).
_HEBREW_SINGLE_LETTER_PREFIXES = frozenset("בלכמשוה")


def _is_name_stop_token(token: str) -> bool:
    token = token.strip()
    if token in _NAME_STOP:
        return True
    return (
        len(token) > 1
        and token[0] in _HEBREW_SINGLE_LETTER_PREFIXES
        and token[1:] in _NAME_STOP
    )

# BUG-101b/c: date/time bracket prefix used by pasted WhatsApp chat exports,
# e.g. "[12.9.2023, 14:25] אורי צדוק: ...". Day/month 1-2 digits, "." or "/"
# separator, year 2-4 digits, seconds optional — covers the variety actually
# seen in real export text (BUG-101 evidence). Shared between _BLOCK_SEP
# (needs the full header incl. sender name to treat it as a high-confidence
# new-message boundary) and _SENDER_LINE_RE (needs only the bracket, as an
# optional prefix before the existing name+colon capture) so the two never
# drift apart on what counts as "an export timestamp".
#
# BUG-111: the year group is OPTIONAL — some WhatsApp exports/manual pastes
# use a short "[D.M, HH:MM]" stamp with no year at all (e.g. "[18.7, 22:02]
# אורי צדוק: 0504142604"). Without this, that header matched neither
# _BLOCK_SEP's boundary lookahead nor _SENDER_LINE_RE's optional prefix, so
# the sender name was never recognized and leaked into candidate extraction
# as if it were the lead's name (same failure shape as BUG-101c, narrower
# trigger). The mandatory day/month + time portion is unchanged, so every
# full "D.M.YYYY, HH:MM" timestamp already covered keeps matching exactly as
# before — this only adds coverage, it does not narrow anything.
_CHAT_EXPORT_TIMESTAMP = r"\[\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?,?\s*\d{1,2}:\d{2}(?::\d{2})?\]"
_CHAT_EXPORT_HEADER = _CHAT_EXPORT_TIMESTAMP + r"\s*[^\n:]{1,40}:"

# BUG-096: block separator — new line starting with a Hebrew letter / bullet /
# numbering / blank line. Used to bound per-candidate windows at block
# boundaries, not just at neighboring recognized phone numbers (see
# _extract_lead_candidates below).
# BUG-101b: a chat-export message header ("[date, time] sender:") starts a
# new block too — without this, none of the four prior conditions fire on a
# line like "[8.4.2024, 20:18] אליהו: ..." (it starts with "[", not a Hebrew
# letter, and there's no blank line/bullet/numbering before it), so the whole
# header gets swallowed into the PRECEDING block — the root cause of the
# cross-message name/phone bleed in BUG-101's production evidence.
#
# BUG-111 follow-up: real production text sometimes has NO newlines between
# WhatsApp export headers at all (a compact/newline-stripped paste — e.g.
# "...לידים חדשים [18.7, 22:02] אורי צדוק: +972 53-396-8395[18.7, 22:02]
# אורי צדוק: 0533123482..." — every header glued directly onto the previous
# message with no separator whatsoever). Every alternative above requires a
# `\n` immediately before the boundary, so none of them fired: the whole
# message stayed ONE block, and command/header text ("לידים חדשים") ended up
# directly adjacent to the first phone's extraction window. The last
# alternative below is a bare, unanchored lookahead for the same header
# shape — it splits right before a chat-export header WHEREVER it appears,
# newline or not. A header that IS newline-preceded still gets a (harmless,
# filtered-empty-block) redundant split from both alternatives; this only
# ADDS coverage, it narrows nothing.
_BLOCK_SEP = re.compile(
    r"\n\s*\n|\n[-•*]\s+|\n\d+[.)]\s+|\n(?=[א-ת])|\n(?=" + _CHAT_EXPORT_HEADER + r")"
    r"|(?=" + _CHAT_EXPORT_HEADER + r")"
)

# Sender-name line pattern for WhatsApp-style chat logs (not exports):
# "דני:" or "דני כהן:" at start of line — name before colon is a SENDER, not a lead.
# BUG-101c: the `^` anchor alone missed a sender name preceded by an export
# timestamp ("[12.9.2023, 14:25] אורי צדוק: ..." — "אורי צדוק" is not at the
# literal start of the line, so it was never recognized as a sender and got
# extracted as if it were a lead's name). The bracket prefix is optional so
# the plain "דני:" case still matches exactly as before.
#
# BUG-111 follow-up: the SAME compact/newline-stripped paste that defeated
# _BLOCK_SEP above also defeats this — `^` (MULTILINE) only matches at the
# very start of the string or right after a real `\n`, so a timestamp+sender
# header sitting mid-line (never preceded by any newline at all) was invisible
# to this regex, and sender_names ended up empty for the whole message —
# "אורי צדוק" then leaked through as a candidate NAME for every phone after
# the first. Restructured so the two forms have independent anchoring
# requirements instead of sharing one `^` over the whole optional-bracket
# group: the BARE "Name:" form (no bracket) still requires `^` — unanchored
# bare "word:" matching anywhere in free text would be far too eager, a much
# higher false-positive risk than before. The BRACKET-prefixed form no
# longer requires `^` at all — the literal timestamp text immediately
# preceding it is already a high-precision signal on its own (same shape
# _CHAT_EXPORT_HEADER/_BLOCK_SEP already trust unanchored, above), so it now
# matches wherever that exact shape occurs, line-start or not.
_SENDER_LINE_RE = re.compile(
    r"(?:^|" + _CHAT_EXPORT_TIMESTAMP + r"\s*)([א-ת]{2,}(?:\s+[א-ת]{2,})?)\s*:\s*",
    re.MULTILINE,
)


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
    if not any(_is_name_stop_token(w) for w in words):
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
    # BUG-111: an explicit "דומיין X" annotation is usually a message-level
    # command header, not necessarily inside any one candidate's +-80-char
    # phone window (e.g. a batch header line followed by separate per-person
    # blocks) — resolved once from the FULL original text and carried onto
    # every candidate this message produces, never re-guessed per block.
    domain_hint = _extract_domain_hint(text)

    for block in _BLOCK_SEP.split(text):
        if not block.strip():
            continue
        _extract_candidates_from_block(block, candidates, seen_phones, sender_names, domain_hint)

    return candidates


def _extract_candidates_from_block(
    block: str,
    candidates: list[dict],
    seen_phones: set[str],
    sender_names: set,
    domain_hint: Optional[str] = None,
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
            "name":        name,
            "phone":       phone,
            "confidence":  conf,
            "context":     ctx,
            "raw_text":    block.strip(),
            "domain_hint": domain_hint,
        })


def _extract_name_from_window(window: str, sender_names: set) -> Optional[str]:
    """מחלץ שם עברי מחלון טקסט, מסנן sender names ומילות עצירה.

    BUG-099b: a single _HEBREW_NAME_RE match is one CONTIGUOUS run of Hebrew
    words (broken only by digits/punctuation) — a real name can sit inside
    that same run, flanked by stop-words with no such break between them
    (e.g. "צור ליד חדש יעל רייס מעוניינת בדירת..." is ONE match; "ליד"/"חדש"
    sit between the command prefix and "יעל רייס", "מעוניינת" right after
    it). The prior logic (trim stop-words off the END only, reject the whole
    match if a stop-word remained ANYWHERE) safely dropped candidates like
    this rather than writing garbage (BUG-099a) — safer, but the real name
    was still lost, not recovered.
    Fix: stop-words split the run into segments (they act as separators, not
    just a suffix to strip), and the LONGEST surviving segment is used —
    isolating "יעל רייס" out of the larger run instead of discarding the
    whole thing. This does not touch the +-80-char phone window, the
    neighbor-phone clipping, or _BLOCK_SEP (BUG-096/097/101b's fixes) at
    all — it only changes which words *within* an already correctly-bounded
    match are picked as the name.

    BUG-111: an explicit 'דומיין X' / 'לדומיין X' routing annotation is
    stripped from the window FIRST (see _strip_domain_hint) — the hint word
    alone (e.g. "גיוס") would otherwise survive as the longest segment once
    "דומיין" itself splits the run, and a blanket word-count rule can't be
    used to reject it instead (single-word Hebrew names are legitimate, see
    BUG-101 T16 / "שמואל"). The hint's routing value is not lost by this —
    it is extracted separately, from the un-stripped text, by
    _extract_domain_hint().
    """
    window = _strip_domain_hint(window)
    for m in _HEBREW_NAME_RE.finditer(window):
        raw   = m.group(1).strip().rstrip(",;:")
        words = raw.split()

        segments: list[list[str]] = [[]]
        for w in words:
            if _is_name_stop_token(w):
                segments.append([])
            else:
                segments[-1].append(w)
        name = " ".join(max(segments, key=len))

        if not name or len(name) < 4:
            continue
        if name in sender_names:
            continue
        if name in _GENERIC_NAME_PHRASES:
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
# BUG-111 — explicit domain/routing hint ("דומיין X" / "לדומיין X")
#
# A command like "צור ליד דומיין גיוס 0504025707" carries an EXPLICIT routing
# annotation ("דומיין גיוס" — "domain: recruiting") that is not part of the
# lead's name at all. Two separate defects had to both be fixed for this:
#   1. The hint word ("גיוס") is not a stop-word, so once "דומיין" itself is
#      excluded (see _NAME_STOP) the segmentation in _extract_name_from_window
#      still isolates the hint word alone as the longest surviving segment —
#      the architecture deliberately allows single-word Hebrew names (e.g.
#      "שמואל", see BUG-101 T16), so a blanket "names need >=2 words" rule
#      would be wrong; the hint word specifically must never reach name
#      extraction at all, not just fail a word-count check.
#   2. Even once excluded from the name, the routing signal itself must not
#      be silently discarded — the caller (core/lead_candidate_handler.py)
#      needs it to resolve the lead's Domain field instead of falling back to
#      "general" when the Router's own content-based domain guess misses it
#      (e.g. "ליד" alone routes to the RouterDomain.CRM meta-domain, which the
#      Leads Domain field never accepts, see _lead_domain_key()).
#
# _DOMAIN_HINT_RE captures the WHOLE two-token phrase (the optional "ל" is a
# single attached prefix on "דומיין" itself, mirroring the single-letter-
# prefix convention _is_name_stop_token() already uses) so callers can strip
# it out of a name-extraction window in one operation, not two.
# Phase 1 (Lead System E2E Audit, golden failure case): the golden failure
# case itself was typed as "domain recruitment" — the ENGLISH word "domain",
# not "דומיין" — which this regex never matched at all, so the explicit
# annotation was silently invisible to _extract_domain_hint() even before
# considering that its caller was unreachable (see core/lead_service.py's
# resolve_domain(), now the actual live consumer). "domain" is added as an
# alternative trigger, case-insensitive, alongside the original Hebrew form.
_DOMAIN_HINT_RE = re.compile(
    r"(?:(?:ל)?דומיין|domain)\s+([א-ת]{2,}|[A-Za-z]{2,})", re.IGNORECASE
)

# Best-effort canonical mapping to the live Leads/Lead Events Domain
# singleSelect values (airtable_schema.py: "real_estate | import | recruitment
# | saas | finance | general" — see CLAUDE.md's documented verticals plus
# BUG-094-C's "recruiting" note; the live field value is "recruitment").
# An explicit "דומיין <word>" hint whose word is not in this map is still
# EXCLUDED from the name (the regex above catches it regardless), it just has
# no canonical routing value to offer — never invented, never guessed beyond
# this fixed table.
_DOMAIN_HINT_CANONICAL = {
    "גיוס":     "recruitment",
    "גיוסים":   "recruitment",
    "recruiting": "recruitment",
    "recruitment": "recruitment",
    "נדלן":     "real_estate",
    'נדל"ן':    "real_estate",
    "נדלן.":    "real_estate",
    "יבוא":     "import",
    "ייבוא":    "import",
    "import":   "import",
    "מדיה":     "media",
    "שיווק":    "media",
    "media":    "media",
    "כספים":    "finance",
    "פיננסי":   "finance",
    "finance":  "finance",
    "saas":     "saas",
    # BUG-DIAMOND-ENRICHMENT-RUNTIME-SWEEP (06/09/2026, owner bug sweep,
    # item 6): "כללי" was already a recognized Domain alias in
    # domain_utils.py's separate BUSINESS_DOMAIN_ALIASES table, but this
    # is the actual table parse_deterministic_create_deal() consults (via
    # core.lead_service.resolve_domain_word()) — its absence here, not
    # there, is why "...בתחום כללי" failed to parse a Deal while every
    # other domain word worked. One shared vocabulary; no parser-local
    # special case added.
    "כללי":     "general",
    "general":  "general",
}


def _strip_domain_hint(text: str) -> str:
    """Removes any 'דומיין X' / 'לדומיין X' phrase entirely (both the
    keyword and its hint word) — used before name extraction so neither
    token can be mistaken for a person/business name. Not the same as
    _extract_domain_hint(): this only cleans text for name-extraction
    purposes and does not resolve or lose the hint's routing value (the
    caller extracts that separately, from the ORIGINAL text)."""
    return _DOMAIN_HINT_RE.sub(" ", text)


def _extract_domain_hint(text: str) -> Optional[str]:
    """Returns the canonical Leads-Domain value for an explicit 'דומיין X' /
    'לדומיין X' / 'domain X' command annotation in text, or None if no such
    annotation is present or its hint word has no known canonical mapping.
    Never guesses — only the fixed _DOMAIN_HINT_CANONICAL table is
    consulted. Lookup is case-insensitive (.lower() is a no-op on Hebrew,
    so this only affects the English "domain X" form)."""
    m = _DOMAIN_HINT_RE.search(text)
    if not m:
        return None
    return _DOMAIN_HINT_CANONICAL.get(m.group(1).strip().lower())


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

    # BUG-101a: strip invisible bidi marks BEFORE Tier-4 detection (and
    # everything downstream) — see _strip_bidi_controls's own docstring.
    text = _strip_bidi_controls(text)

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

    # BUG-111 follow-up — defense in depth: a SINGLE extracted candidate is
    # not trustworthy when the raw text actually contains MORE distinct
    # phone numbers than were captured as candidates. That mismatch means at
    # least one phone's name-extraction window found no safe name (correctly
    # dropped) while exactly one OTHER window produced a "name" — in every
    # production case seen so far, that lone survivor was command/header
    # text bleeding into a phone's window, not a real person's name (e.g.
    # "לידים חדשים" attached to the first of three phones). Rather than
    # trust it, this degrades to the same Tier 5/no_lead_candidates outcome
    # a fully-nameless batch already gets — the multi-phone clarification
    # path (_maybe_start_lead_clarification, which independently re-scans
    # the FULL text for every phone via .finditer()) takes over instead of
    # silently creating one lead under a name nobody actually gave.
    # "Doubt → degrade toward safe, never toward fast" (this module's own
    # design principle, see the file's own top-of-file comment).
    if len(candidates) == 1:
        distinct_phones = {_normalize_phone(m.group()) for m in _PHONE_RE.finditer(text)}
        if len(distinct_phones) > 1:
            candidates = []

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
