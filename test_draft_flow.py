# test_draft_flow.py — N18 Phase 2: generic Draft-Card state machine
# (core/draft_flow.py), extracted from Lead's Draft Card. Verifies the
# primitive's own contract in isolation, using a synthetic non-Lead
# DraftSpec — Lead's own field semantics are covered separately by
# test_lead_service_phase1.py (sections 7, 9, 10).

from core.draft_flow import DraftSpec, resolve_draft_reply, first_missing_required_field, is_expired

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"✅ {desc}")
    else:
        failed += 1
        print(f"❌ {desc}")


def _set_field(draft, key, raw):
    raw = raw.strip()
    if key == "title" and not raw:
        return False, "empty title"
    draft[key] = raw
    return True, ""


SPEC = DraftSpec(
    required_fields=("title", "due"),
    field_prompts={"title": "what's the title?", "due": "when's it due?", "note": "any note?"},
    edit_labels={"כותרת": "title", "תאריך": "due"},
    set_field=_set_field,
    render=lambda d: f"title={d.get('title')} due={d.get('due')}",
    unknown_field_message="unknown field, try again",
    edit_choice_prompt="which field?",
)


def new_draft():
    return {"title": "", "due": "", "note": "", "mode": "filling", "awaiting_field": "title"}


# ── filling mode ─────────────────────────────────────────────
d = new_draft()
o = resolve_draft_reply("buy milk", d, SPEC)
chk("filling: valid value advances to next required field",
    o.kind == "reply" and o.draft["awaiting_field"] == "due" and o.message == "when's it due?")

o = resolve_draft_reply("tomorrow", o.draft, SPEC)
chk("filling: last required field filled -> switches to review mode",
    o.kind == "reply" and o.draft["mode"] == "review")

d2 = new_draft()
o = resolve_draft_reply("", d2, SPEC)
chk("filling: rejected value stays pending, draft returned for persistence (matches original quirk)",
    o.kind == "reply" and o.draft is not None and o.message == "❌ empty title")
chk("filling: rejected value does not advance awaiting_field", d2["awaiting_field"] == "title")

d3 = new_draft()
o = resolve_draft_reply("לא", d3, SPEC)
chk("filling: cancel word -> cancel outcome", o.kind == "cancel")

d4 = new_draft()
d4["awaiting_field"] = None
o = resolve_draft_reply("anything", d4, SPEC)
chk("filling: no awaiting_field -> abandon (silent, no message)", o.kind == "abandon" and o.message is None)

# ── edit_choice mode ─────────────────────────────────────────
d5 = {"title": "x", "due": "y", "note": "", "mode": "edit_choice"}
o = resolve_draft_reply("nonsense", d5, SPEC)
chk("edit_choice: unmatched label -> reply with unknown_field_message, draft NOT persisted",
    o.kind == "reply" and o.draft is None and o.message == "unknown field, try again")

o = resolve_draft_reply("כותרת", d5, SPEC)
chk("edit_choice: matched label -> filling mode for that field, shows current value",
    o.kind == "reply" and o.draft["mode"] == "filling" and o.draft["awaiting_field"] == "title"
    and o.message == "what's the title? (נוכחי: x)")

# ── review mode ───────────────────────────────────────────────
def new_review_draft():
    return {"title": "x", "due": "y", "note": "", "mode": "review"}


o = resolve_draft_reply("כן", new_review_draft(), SPEC)
chk("review: confirm word -> confirm outcome (caller does the actual write)", o.kind == "confirm")

o = resolve_draft_reply("לא", new_review_draft(), SPEC)
chk("review: cancel word -> cancel outcome", o.kind == "cancel")

o = resolve_draft_reply("ערוך", new_review_draft(), SPEC)
chk("review: edit word -> edit_choice mode", o.kind == "reply" and o.draft["mode"] == "edit_choice")

o = resolve_draft_reply("huh?", new_review_draft(), SPEC)
chk("review: unrecognized reply -> re-renders card, draft NOT persisted (unchanged)",
    o.kind == "reply" and o.draft is None and "title=x due=y" in o.message)

# ── helpers ──────────────────────────────────────────────────
chk("first_missing_required_field walks required_fields in order",
    first_missing_required_field({"title": "", "due": "y"}, SPEC) == "title")
chk("first_missing_required_field returns None when all required fields set",
    first_missing_required_field({"title": "x", "due": "y"}, SPEC) is None)

chk("is_expired: fresh draft is not expired", not is_expired({"set_at": __import__("time").time()}))
chk("is_expired: old draft is expired", is_expired({"set_at": 0}))

print()
print("=" * 50)
print(f"test_draft_flow.py: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
