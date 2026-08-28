# core/draft_flow.py — Canonical Write Infrastructure, Phase 2 (N18)
#
# Generic Draft-Card state machine: filling -> (edit_choice <-> filling) ->
# review -> confirm/cancel. Extracted from Lead's Draft Card (formerly
# core/lead_candidate_handler.py::_resolve_lead_draft +
# core/lead_service.py's draft helpers) — the ONLY thing generalized here
# is the mode-transition logic and the universal Hebrew confirm/cancel/edit
# vocabulary. Field names, prompts, validation, and rendering stay owned by
# each entity's own DraftSpec. See ROADMAP.md N18: "Parsing mechanics is
# shared. Field semantics belong to the entity schema."
#
# Pure state transitions only — no I/O, no session storage, no entity
# writes. A caller (e.g. lead_candidate_handler.py) is responsible for
# persisting draft["mutations"] and for actually writing the entity on a
# "confirm" outcome.

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

CONFIRM_WORDS = frozenset({"כן", "אשר", "מאשר", "מאשרת", "✅", "yes", "y", "ok", "אוקי", "שמור", "בצע"})
CANCEL_WORDS = frozenset({"לא", "בטל", "ביטול", "עצור", "cancel", "no", "❌"})
SKIP_WORDS = frozenset({"דלג", "ללא הערה", "skip"})
EDIT_WORDS = frozenset({"ערוך", "עריכה", "לתקן", "תקן", "edit"})

DRAFT_TTL_SECONDS = 1800


@dataclass(frozen=True)
class DraftSpec:
    """Entity-owned field semantics plugged into the generic state machine.

    required_fields   — order matters: first_missing_required_field() walks
                         this tuple in order.
    field_prompts     — fully populated for every field the entity's draft
                         can hold (not just required ones) — the generic
                         code does plain dict lookups, no fallback logic.
    edit_labels       — free-text reply (as typed in edit_choice mode) ->
                         field_key.
    set_field         — (draft, field_key, raw_value) -> (ok, error_message);
                         mutates draft in place on success, leaves it
                         untouched on failure.
    render            — draft -> full card text (review mode + the
                         catch-all "didn't understand" reply).
    unknown_field_message — shown when an edit_choice reply doesn't match
                         any edit_labels entry.
    edit_choice_prompt — shown when entering edit_choice mode (asks which
                         field to change).
    """
    required_fields: tuple[str, ...]
    field_prompts: dict[str, str]
    edit_labels: dict[str, str]
    set_field: Callable[[dict, str, str], tuple[bool, str]]
    render: Callable[[dict], str]
    unknown_field_message: str
    edit_choice_prompt: str
    optional_fields: tuple[str, ...] = ()


def first_missing_required_field(draft: dict, spec: DraftSpec) -> Optional[str]:
    for key in spec.required_fields:
        if not draft.get(key):
            return key
    return None


def is_expired(draft: dict, ttl_seconds: int = DRAFT_TTL_SECONDS) -> bool:
    return time.time() - draft.get("set_at", 0) > ttl_seconds


@dataclass
class DraftOutcome:
    """
    kind:
      "abandon" — caller should silently clear the stored draft and return
                  None (fall through to whatever else handles the message).
      "cancel"  — caller should clear the stored draft and show its own
                  cancellation message (the entity, not this module, owns
                  that wording).
      "confirm" — caller should validate + write the entity itself (the
                  generic state machine has no concept of "write"), then
                  clear the draft on success.
      "reply"   — caller should show `message`. If `draft` is not None, the
                  draft was mutated and the caller must persist it (still
                  pending); if `draft` is None, nothing changed and no
                  persistence is needed.
    """
    kind: str
    draft: Optional[dict] = None
    message: Optional[str] = None


def resolve_draft_reply(text: str, draft: dict, spec: DraftSpec) -> DraftOutcome:
    lower = text.strip().lower()
    mode = draft.get("mode", "filling")

    if mode == "filling":
        field_key = draft.get("awaiting_field")
        if not field_key:
            return DraftOutcome(kind="abandon")
        if lower in CANCEL_WORDS:
            return DraftOutcome(kind="cancel")
        if field_key in spec.optional_fields and lower in SKIP_WORDS:
            draft[field_key] = ""
            draft["mode"] = "review"
            draft["awaiting_field"] = None
            return DraftOutcome(kind="reply", draft=draft, message=spec.render(draft))
        ok, err = spec.set_field(draft, field_key, text)
        if not ok:
            return DraftOutcome(kind="reply", draft=draft, message=f"❌ {err}")
        missing = first_missing_required_field(draft, spec)
        if missing:
            draft["awaiting_field"] = missing
            return DraftOutcome(kind="reply", draft=draft, message=spec.field_prompts[missing])
        for optional in spec.optional_fields:
            if not draft.get(optional):
                draft["awaiting_field"] = optional
                return DraftOutcome(kind="reply", draft=draft, message=spec.field_prompts[optional])
        draft["mode"] = "review"
        draft["awaiting_field"] = None
        return DraftOutcome(kind="reply", draft=draft, message=spec.render(draft))

    if mode == "edit_choice":
        field_key = spec.edit_labels.get(text.strip())
        if not field_key:
            return DraftOutcome(kind="reply", message=spec.unknown_field_message)
        draft["mode"] = "filling"
        draft["awaiting_field"] = field_key
        current = draft.get(field_key) or "ריק"
        prompt = spec.field_prompts[field_key]
        return DraftOutcome(kind="reply", draft=draft, message=f"{prompt} (נוכחי: {current})")

    # review mode
    if lower in CANCEL_WORDS:
        return DraftOutcome(kind="cancel")
    if lower in EDIT_WORDS:
        draft["mode"] = "edit_choice"
        return DraftOutcome(kind="reply", draft=draft, message=spec.edit_choice_prompt)
    if lower in CONFIRM_WORDS:
        return DraftOutcome(kind="confirm")
    return DraftOutcome(kind="reply", message=spec.render(draft) + "\n\n(לא הבנתי — ענה/י כן / ערוך / לא)")


def demo() -> None:
    def _set_field(draft, key, raw):
        if key == "name" and not raw.strip():
            return False, "empty name"
        draft[key] = raw.strip()
        return True, ""

    spec = DraftSpec(
        required_fields=("name", "phone"),
        field_prompts={"name": "name?", "phone": "phone?", "note": "note?"},
        edit_labels={"שם": "name", "טלפון": "phone"},
        set_field=_set_field,
        render=lambda d: f"name={d.get('name')} phone={d.get('phone')}",
        unknown_field_message="unknown field",
        edit_choice_prompt="which field?",
    )

    draft = {"name": "", "phone": "", "mode": "filling", "awaiting_field": "name"}
    o = resolve_draft_reply("Moshe", draft, spec)
    assert o.kind == "reply" and o.draft["awaiting_field"] == "phone" and o.message == "phone?"

    o = resolve_draft_reply("0501234567", draft, spec)
    assert o.kind == "reply" and o.draft["mode"] == "review"

    draft["mode"] = "edit_choice"
    o = resolve_draft_reply("שם", draft, spec)
    assert o.kind == "reply" and o.draft["mode"] == "filling" and o.draft["awaiting_field"] == "name"

    draft["mode"] = "review"
    o = resolve_draft_reply("כן", draft, spec)
    assert o.kind == "confirm"

    o = resolve_draft_reply("לא", draft, spec)
    assert o.kind == "cancel"

    draft["mode"] = "filling"
    draft["awaiting_field"] = None
    o = resolve_draft_reply("anything", draft, spec)
    assert o.kind == "abandon"

    print("core/draft_flow.py: all demo() assertions passed")


if __name__ == "__main__":
    demo()
