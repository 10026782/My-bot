# core/deterministic_commercial_update.py — Phase 4C: Deterministic
# Commercial UPDATE Routing.
#
# Removes Agent tool-selection AND record-selection from the common,
# structurally-simple case of a conversational Deal/Payment Term/Payment
# field UPDATE ("עדכן בעסקה X את הסטטוס ל-Y"). This module owns ONLY:
#   1. deterministic recognition (bounded regex grammar, never an LLM)
#   2. deterministic entity/field extraction
#   3. deterministic record-reference *classification* (explicit id /
#      "just created" / typed name) — actual record RESOLUTION (the
#      Airtable lookup / session-marker read) lives in
#      resolve_deterministic_update_record() below, kept separate from
#      parsing so the parser itself never performs I/O.
#
# It does NOT create a second UPDATE writer, a second validation contract,
# or a second field allowlist: field names are validated against the SAME
# closed allowlists commercial_crm.py's update_deal()/update_payment_term()/
# update_payment() already enforce (imported below, not duplicated), and a
# successful parse+resolve here is handed to the EXACT SAME
# _queue_approval_detailed() → BusinessDraft → Sessions/CAS → ConfirmedSnapshot
# → ActionGateway → approval → canonical writer lifecycle every other
# deterministic Turn Coordinator flow (create_task, create_deal, S2C
# commercial completion) already uses — see app.py's Handler.TOOL dispatch
# block. Phase 4B (core/commercial_generic_canonicalization.py) remains
# fully intact and unmodified: it stays the defense-in-depth boundary for
# any UNEXPECTED generic commercial proposal (Agent-chosen or otherwise),
# not the normal path this module exists to make exceptional.
#
# BOUNDED GRAMMAR — deliberately not an NLP engine. Two closed shapes:
#
#   Pattern A (entity-first):
#     <verb> [ב]<entity>[ <reference>] את [ה]<field> ל[-]<value>
#     e.g. "תעדכן בעסקה X את הסטטוס ל-סגור"
#
#   Pattern B (field-first — the exact live-incident shape):
#     <verb> [ב-Airtable] את שדה [ה]<field> [ב]<entity>[ <reference>] ל[-]<value>
#     e.g. "תעדכן ב-Airtable את שדה ההערות בתנאי התשלום שיצרנו עכשיו ל-X"
#
# Any text that doesn't match either shape returns matched=False and the
# caller MUST fall through to the normal Agent pipeline unchanged — this
# module never guesses, never partially matches, never widens itself to
# "close enough."

from __future__ import annotations

import re
from dataclasses import dataclass, field as _dc_field
from typing import Optional

from commercial_crm import (
    _DEAL_UPDATE_ALLOWED as DEAL_UPDATE_ALLOWED_FIELDS,
    _PAYMENT_TERM_UPDATE_ALLOWED as PAYMENT_TERM_UPDATE_ALLOWED_FIELDS,
    _PAYMENT_UPDATE_ALLOWED as PAYMENT_UPDATE_ALLOWED_FIELDS,
    _valid_record_id,
)

# ══════════════════════════════════════════════════
# Entity aliases — longest/most-specific alternative first so "תנאי תשלום"
# never gets swallowed by the bare "תשלום" alternative at the same position.
# ══════════════════════════════════════════════════

ENTITY_DEAL = "deal"
ENTITY_PAYMENT_TERM = "payment_term"
ENTITY_PAYMENT = "payment"

_ENTITY_ALT_RE = r"(?:תנאי\s+ה?תשלום|עסקה|עסק|תשלום)"

_ENTITY_ALIAS_TO_KEY: dict[str, str] = {
    "תנאי תשלום": ENTITY_PAYMENT_TERM,
    "תנאי התשלום": ENTITY_PAYMENT_TERM,
    "עסקה": ENTITY_DEAL,
    "עסק": ENTITY_DEAL,
    "תשלום": ENTITY_PAYMENT,
}


def _entity_key(raw: str) -> Optional[str]:
    normalized = " ".join(str(raw or "").split())
    return _ENTITY_ALIAS_TO_KEY.get(normalized)


# ══════════════════════════════════════════════════
# Field aliases — bounded, explicit, non-financial. Every canonical value
# below is cross-checked at module import time against the real update-
# writer allowlists (assert block at the bottom) so this module cannot
# silently drift from commercial_crm.py's own authority.
# ══════════════════════════════════════════════════

FIELD_ALIASES: dict[str, dict[str, str]] = {
    ENTITY_DEAL: {
        "סטטוס מסחרי": "commercial_status",
        "סטטוס": "commercial_status",
        "שלב": "stage",
        "הערות": "notes",
        "עדיפות": "priority",
        "מטבע": "currency",
    },
    ENTITY_PAYMENT_TERM: {
        "הערות": "notes",
        "שם": "name",
    },
    ENTITY_PAYMENT: {
        "אמצעי תשלום": "method",
        "אמצעי התשלום": "method",
        "אמצעי": "method",
        "הערות": "notes",
        "אסמכתא": "reference",
        "מספר אסמכתא": "reference",
    },
}

_UPDATE_ALLOWED_BY_ENTITY: dict[str, frozenset[str]] = {
    ENTITY_DEAL: DEAL_UPDATE_ALLOWED_FIELDS,
    ENTITY_PAYMENT_TERM: PAYMENT_TERM_UPDATE_ALLOWED_FIELDS,
    ENTITY_PAYMENT: PAYMENT_UPDATE_ALLOWED_FIELDS,
}

for _entity, _aliases in FIELD_ALIASES.items():
    _bad = set(_aliases.values()) - _UPDATE_ALLOWED_BY_ENTITY[_entity]
    assert not _bad, f"Phase 4C field alias targets a field {_entity} update writer doesn't allow: {_bad!r}"
del _entity, _aliases, _bad

CANONICAL_UPDATE_TOOL_BY_ENTITY: dict[str, str] = {
    ENTITY_DEAL: "crm_update_deal",
    ENTITY_PAYMENT_TERM: "crm_update_payment_term",
    ENTITY_PAYMENT: "crm_update_payment",
}


def _field_key(entity: str, raw: str) -> Optional[str]:
    normalized = " ".join(str(raw or "").strip(" \t:").split())
    aliases = FIELD_ALIASES.get(entity, {})
    # Longest alias first so "אמצעי תשלום" wins over the shorter "אמצעי".
    for alias in sorted(aliases, key=len, reverse=True):
        if normalized == alias:
            return aliases[alias]
    return None


# ══════════════════════════════════════════════════
# "Just created" reference recognition — classification only, no I/O.
# ══════════════════════════════════════════════════

_RECENT_MARKER_RE = re.compile(
    r"^(?:ש?(?:יצרנו|נוצר(?:ה)?)\s*(?:הרגע|עכשיו|זה\s*עתה)|האחרונ(?:ה|ות)|האחרון)$"
)

_QUOTE_CHARS = "\"'“”׳״`"


def _strip_value_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] in _QUOTE_CHARS and v[-1] in _QUOTE_CHARS:
        v = v[1:-1].strip()
    return v


# ══════════════════════════════════════════════════
# Grammar
# ══════════════════════════════════════════════════

_VERB = r"(?:עדכן|תעדכן|שנה|תשנה)"

_PATTERN_A = re.compile(
    rf"^\s*{_VERB}\s+"
    rf"(?:ב|ל)?(?:ה)?(?P<entity>{_ENTITY_ALT_RE})\s*"
    rf"(?P<record_ref>.*?)\s*"
    rf"את\s+(?:ה)?(?P<field>.+?)\s+"
    rf"ל[-־]?\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

_PATTERN_B = re.compile(
    rf"^\s*{_VERB}\s+"
    rf"(?:ב[\s-]?Airtable\s+)?"
    rf"את\s+שדה\s+(?:ה)?(?P<field>.+?)\s+"
    rf"(?:ב|ל)?(?:ה)?(?P<entity>{_ENTITY_ALT_RE})\s*"
    rf"(?P<record_ref>.*?)\s*"
    rf"ל[-־]?\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DeterministicCommercialUpdateParse:
    entity: Optional[str] = None
    field: Optional[str] = None
    field_raw: str = ""
    value: Optional[str] = None
    record_ref_text: str = ""
    record_ref_kind: str = ""  # "explicit_id" | "recent" | "name" | ""
    matched: bool = False
    uncertain: bool = False
    unknown_field: bool = False
    missing_record_ref: bool = False
    grammar_incomplete: bool = False

    @property
    def certain(self) -> bool:
        return self.matched and not self.uncertain and self.field is not None

    @property
    def tool_name(self) -> Optional[str]:
        return CANONICAL_UPDATE_TOOL_BY_ENTITY.get(self.entity) if self.entity else None


# ══════════════════════════════════════════════════
# Commercial-update GUARD — the required invariant: "once a request is
# recognizably a commercial UPDATE for Deal/Payment Term/Payment, the model
# must not regain authority to choose the record or tool." The two strict
# Patterns above only recognize a small closed set of well-formed phrasings.
# Anything that clearly carries an update/change verb AND names exactly one
# protected commercial entity, but doesn't fit either strict pattern (field
# before entity, colon/equals syntax, a reference with no field/value at
# all, ...), must still be OWNED here and deterministically CLARIFIED —
# never silently handed to the Agent because parsing came up short.
#
# Deliberately narrow: not a second parser, not an NLP classifier. It reuses
# the exact same bounded verb/entity vocabulary the strict patterns already
# use, with two differences from them: (1) it searches anywhere in the text
# rather than anchoring to a fixed shape, so word order doesn't matter, and
# (2) it requires the entity mention to be bare or ב/ל-prefixed (never a
# bare "ה"-prefixed mention alone, e.g. "העסקה") — a deliberate precision
# cut so an unrelated sentence that merely refers back to "the deal" (e.g.
# "תעדכן אותי כשהעסקה תיסגר" — "let me know when the deal closes") doesn't
# trip the guard just because it happens to share a word with an update
# verb. If more than one distinct entity type is mentioned, or none, the
# guard does not fire — that is a genuinely unclear message, out of this
# narrow guard's scope, not a case it should force a decision on.
# ══════════════════════════════════════════════════

_GUARD_VERB_RE = re.compile(rf"(?<![א-ת]){_VERB}(?![א-ת])", re.IGNORECASE)
_GUARD_ENTITY_RE = re.compile(rf"(?<![א-ת])(?:ב|ל)?{_ENTITY_ALT_RE}(?![א-ת])", re.IGNORECASE)


def _guard_entity(text: str) -> Optional[str]:
    found = set()
    for m in _GUARD_ENTITY_RE.finditer(text):
        key = _entity_key(re.sub(r"^(?:ב|ל)", "", m.group(0)))
        if key:
            found.add(key)
    if len(found) == 1:
        return next(iter(found))
    return None


def parse_deterministic_commercial_update(text: str) -> DeterministicCommercialUpdateParse:
    """Recognize the two explicit closed shapes above, falling back to the
    narrow commercial-update GUARD when a message clearly names an update
    verb and exactly one protected commercial entity but doesn't fit either
    strict shape. A message with neither signal returns matched=False and
    the caller must fall through to the normal Agent pipeline unchanged —
    but a message the guard recognizes is ALWAYS matched=True, never a
    silent fall-through, per the Phase 4C invariant: recognizable protected
    commercial UPDATE -> deterministic UPDATE / CLARIFY / FAIL_CLOSED,
    never Handler.AGENT because parsing was incomplete."""
    raw = str(text or "")
    match = _PATTERN_A.match(raw) or _PATTERN_B.match(raw)
    if not match:
        guard_entity = _guard_entity(raw) if _GUARD_VERB_RE.search(raw) else None
        if guard_entity is None:
            return DeterministicCommercialUpdateParse()
        return DeterministicCommercialUpdateParse(
            entity=guard_entity, matched=True, uncertain=True, grammar_incomplete=True,
        )

    entity = _entity_key(match.group("entity"))
    if entity is None:
        return DeterministicCommercialUpdateParse()

    field_raw = " ".join(match.group("field").split())
    value_raw = match.group("value").strip()
    record_ref = " ".join(match.group("record_ref").split())

    if not value_raw:
        return DeterministicCommercialUpdateParse(
            entity=entity, field_raw=field_raw, matched=True, uncertain=True,
        )

    field_key = _field_key(entity, field_raw)
    value = _strip_value_quotes(value_raw)

    if not record_ref:
        record_ref_kind = ""
        missing_ref = True
    elif _RECENT_MARKER_RE.match(record_ref):
        record_ref_kind = "recent"
        missing_ref = False
    elif _valid_record_id(record_ref):
        record_ref_kind = "explicit_id"
        missing_ref = False
    else:
        record_ref_kind = "name"
        missing_ref = False

    return DeterministicCommercialUpdateParse(
        entity=entity,
        field=field_key,
        field_raw=field_raw,
        value=value,
        record_ref_text=record_ref,
        record_ref_kind=record_ref_kind,
        matched=True,
        uncertain=(field_key is None or missing_ref),
        unknown_field=(field_key is None),
        missing_record_ref=missing_ref,
    )


# ══════════════════════════════════════════════════
# Record resolution — the only function here that performs I/O (Airtable
# read via commercial_crm.lookup_human_reference, and a session-store read
# for the "just created" marker). Resolution priority, never negotiable:
#   1. explicit Airtable record id (already validated by the parser)
#   2. exact/unique typed name (bounded exact-label lookup, same one
#      lead_deal_link.resolve_deal_by_query() already uses for Deal)
#   3. the "authoritative recent record" session marker, ONLY when exactly
#      one candidate of that entity type is on record for this chat
#   4. otherwise CLARIFY — never a fuzzy guess, never "first result"
#
# Returns (status, record_id_or_none, message_or_none):
#   status == "resolved" -> record_id is the one to use
#   status == "clarify"  -> message is the deterministic clarification —
#                            this is ALSO the terminal status for an
#                            entity/kind combination with no deterministic
#                            resolver at all (documented Phase 4C boundary —
#                            e.g. Payment has no human-typed-name lookup in
#                            this codebase). The absence of a resolver is a
#                            UX limitation, not permission to delegate
#                            entity resolution back to the model: the
#                            REQUIRED invariant is that a recognizable
#                            protected commercial UPDATE never reaches
#                            Handler.AGENT merely because parsing or record
#                            resolution was incomplete, so there is no
#                            third "fall through to Agent" status here.
# ══════════════════════════════════════════════════

_ENTITY_LABEL_HE: dict[str, str] = {
    ENTITY_DEAL: "עסקה",
    ENTITY_PAYMENT_TERM: "תנאי תשלום",
    ENTITY_PAYMENT: "תשלום",
}

# Only entities commercial_crm.lookup_human_reference() actually supports a
# human-typed-name lookup for today — Payment has no Name-like field and no
# resolver; see that function's own table_by_entity/field_by_entity maps.
_NAME_LOOKUP_SUPPORTED_ENTITIES = frozenset({ENTITY_DEAL, ENTITY_PAYMENT_TERM})

_RECENT_MARKER_MAX_AGE_SECONDS = 3600


def resolve_deterministic_update_record(
    entity: str, record_ref_kind: str, record_ref_text: str, *, identity, chat_id: str, channel: str,
) -> tuple[str, Optional[str], Optional[str]]:
    label = _ENTITY_LABEL_HE.get(entity, entity)

    if record_ref_kind == "explicit_id":
        if _valid_record_id(record_ref_text):
            return "resolved", record_ref_text, None
        return "clarify", None, f"❌ מזהה הרשומה שסופק אינו תקין עבור {label}."

    if record_ref_kind == "recent":
        from session_store import lead_sessions
        marker = lead_sessions.get_last_commercial_create(chat_id, entity, channel=channel)
        if not marker or not marker.get("record_id"):
            return (
                "clarify", None,
                f"לא מצאתי {label} שנוצר לאחרונה בשיחה הזו. אפשר לציין שם או מזהה רשומה?",
            )
        age = marker.get("age_seconds")
        if isinstance(age, (int, float)) and age > _RECENT_MARKER_MAX_AGE_SECONDS:
            return (
                "clarify", None,
                f"ה-{label} האחרון שנוצר בשיחה הזו ישן מדי כדי להתייחס אליו כ'עכשיו'. אפשר לציין שם או מזהה רשומה?",
            )
        return "resolved", marker["record_id"], None

    if record_ref_kind == "name":
        if entity not in _NAME_LOOKUP_SUPPORTED_ENTITIES:
            return (
                "clarify", None,
                f"לא ניתן לזהות בוודאות את ה{label} לפי השם הזה.\n"
                f"אפשר לציין מזהה {label}, או לומר \"ה{label} שיצרנו עכשיו\".",
            )
        from commercial_crm import lookup_human_reference
        matches = lookup_human_reference(
            entity, record_ref_text, scope=str(getattr(identity, "user_id", "") or ""),
            identity=identity, limit=6,
        )
        if not matches:
            return "clarify", None, f"🔍 לא נמצא {label} התואם '{record_ref_text}'."
        if len(matches) > 1:
            name_field = {
                ENTITY_DEAL: "Name", ENTITY_PAYMENT_TERM: "Name",
            }
            from airtable_schema import DealFields, PaymentTermFields
            field_by_entity = {ENTITY_DEAL: DealFields.NAME, ENTITY_PAYMENT_TERM: PaymentTermFields.NAME}
            fname = field_by_entity.get(entity, "Name")
            names = ", ".join(m.get("fields", {}).get(fname, "?") for m in matches)
            return "clarify", None, f"מצאתי כמה {label} תואמים: {names}. איזה מהם לעדכן?"
        return "resolved", matches[0].get("id") or "", None

    return (
        "clarify", None,
        f"לאיזה {label} להתייחס? אפשר לציין שם, מזהה רשומה, או שזו הרשומה שיצרנו עכשיו.",
    )
