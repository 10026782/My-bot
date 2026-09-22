"""BUSINESSDRAFT PHASE 2 — Sessions-backed persistence coverage.

Standalone assert-based script (repo convention: `python3 test_business_draft_persistence.py`).
Covers session_store.py's save_business_draft/load_business_draft/
delete_business_draft/list_business_drafts_for_session/create_business_draft
added on top of the frozen Phase 1 core/business_draft.py envelope. Phase 1's
own object-level behavior (lifecycle guards, edit ops, confirm) is covered by
test_business_draft_core.py and is not re-tested here beyond what persistence
touches (serialize/deserialize round-trip, terminal-state immutability as
observed through the store).
"""

from __future__ import annotations

import sys

from core.business_draft import (
    BusinessDraftError,
    DraftConflictError,
    DraftIdentityMismatchError,
    DraftOperation,
    DraftState,
    create_draft,
)

# real imports first (session_store.py -> tma_api.py -> tools.airtable_gateway
# is a genuine package chain — replacing sys.modules["tools"] before these
# resolve breaks it, unlike session_store.py's own _run_tests(), which only
# mocks after all module-level imports already ran for real).
from session_store import PersistentSessionStore, set_request_channel  # noqa: E402
import tools.airtable_tools as _at  # noqa: E402

_at.airtable_add = lambda t, f: {"ok": True, "external_id": "rec001"}
_at.airtable_update = lambda t, r, f: {"ok": True, "external_id": r}
_at.airtable_get = lambda t, formula: "אין רשומות"
_at.airtable_get_records = lambda t, formula: []

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"  PASS: {desc}")
        passed += 1
    else:
        print(f"  FAIL: {desc}")
        failed += 1


set_request_channel("telegram")
TENANT = "t1"
CHANNEL = "telegram"


def _deal_draft(sender: str, actor: str = "recOWNER0000001") -> "BusinessDraft":  # noqa: F821
    return create_draft(
        entity_type="deal", operation=DraftOperation.CREATE, tenant_id=TENANT,
        actor_role="owner", actor_user_id=actor, source_channel=CHANNEL, sender=sender,
    )


def _contact_draft(sender: str, actor: str = "recOWNER0000001") -> "BusinessDraft":  # noqa: F821
    return create_draft(
        entity_type="contact", operation=DraftOperation.CREATE, tenant_id=TENANT,
        actor_role="owner", actor_user_id=actor, source_channel=CHANNEL, sender=sender,
    )


print("\n[save/load] CREATE draft round-trips")
store = PersistentSessionStore(maxsize=10)
draft = _deal_draft("s:1")
saved = store.create_business_draft("s:1", draft, channel=CHANNEL)
chk("save returns version 1", saved.idempotency_key == 1)
loaded = store.load_business_draft(
    "s:1", "deal", tenant_id=TENANT, actor_user_id="recOWNER0000001", source_channel=CHANNEL, channel=CHANNEL,
)
chk("load returns a draft", loaded is not None)
chk("loaded entity_type matches", loaded.entity_type == "deal")
chk("loaded lifecycle_state CAPTURED", loaded.lifecycle_state is DraftState.CAPTURED)

print("\n[save/load] UPDATE draft round-trips")
update_draft = create_draft(
    entity_type="deal", operation=DraftOperation.UPDATE, tenant_id=TENANT,
    actor_role="owner", actor_user_id="recOWNER0000001", source_channel=CHANNEL, sender="s:upd",
    original_fields={"stage": "Opportunity"},
)
store.create_business_draft("s:upd", update_draft, channel=CHANNEL)
loaded_upd = store.load_business_draft(
    "s:upd", "deal", tenant_id=TENANT, actor_user_id="recOWNER0000001", source_channel=CHANNEL, channel=CHANNEL,
)
chk("UPDATE operation preserved", loaded_upd.operation is DraftOperation.UPDATE)
chk("original_fields preserved", loaded_upd.original_fields == {"stage": "Opportunity"})

print("\n[identity binding] mismatches rejected")
try:
    store.load_business_draft(
        "s:1", "deal", tenant_id="OTHER_TENANT", actor_user_id="recOWNER0000001",
        source_channel=CHANNEL, channel=CHANNEL,
    )
    chk("tenant mismatch rejected", False)
except DraftIdentityMismatchError:
    chk("tenant mismatch rejected", True)

try:
    store.load_business_draft(
        "s:1", "deal", tenant_id=TENANT, actor_user_id="recSOMEONE_ELSE",
        source_channel=CHANNEL, channel=CHANNEL,
    )
    chk("actor/sender mismatch rejected", False)
except DraftIdentityMismatchError:
    chk("actor/sender mismatch rejected", True)

try:
    store.load_business_draft(
        "s:1", "deal", tenant_id=TENANT, actor_user_id="recOWNER0000001",
        source_channel="whatsapp", channel=CHANNEL,
    )
    chk("channel mismatch rejected", False)
except DraftIdentityMismatchError:
    chk("channel mismatch rejected", True)

chk(
    "entity mismatch: wrong entity_type -> None, not the other entity's draft",
    store.load_business_draft(
        "s:1", "payment", tenant_id=TENANT, actor_user_id="recOWNER0000001",
        source_channel=CHANNEL, channel=CHANNEL,
    ) is None,
)

print("\n[malformed payload] rejected, fails closed")
store2 = PersistentSessionStore(maxsize=10)
session = store2.get_or_create("s:bad", channel=CHANNEL)
session["business_drafts"] = {"deal": {"entity_type": "deal"}}  # missing everything else
chk(
    "malformed stored draft -> None, not a crash",
    store2.load_business_draft(
        "s:bad", "deal", tenant_id=TENANT, actor_user_id="x", source_channel=CHANNEL, channel=CHANNEL,
    ) is None,
)

print("\n[TTL] expired draft rejected for mutation/confirm")
store3 = PersistentSessionStore(maxsize=10)
fresh = _deal_draft("s:ttl")
saved3 = store3.create_business_draft("s:ttl", fresh, channel=CHANNEL)
# force expiry directly on the stored raw payload (avoids sleeping 1800s)
sess3 = store3.get("s:ttl", channel=CHANNEL)
sess3["business_drafts"]["deal"]["expires_at"] = 0.0
loaded3 = store3.load_business_draft(
    "s:ttl", "deal", tenant_id=TENANT, actor_user_id="recOWNER0000001", source_channel=CHANNEL, channel=CHANNEL,
)
chk("expired draft returned in EXPIRED state, not None", loaded3.lifecycle_state is DraftState.EXPIRED)
try:
    loaded3.set_field("name", "x")
    chk("expired draft rejects mutation", False)
except BusinessDraftError:
    chk("expired draft rejects mutation", True)
try:
    loaded3.confirm()
    chk("expired draft rejects confirm", False)
except BusinessDraftError:
    chk("expired draft rejects confirm", True)
reloaded3 = store3.load_business_draft(
    "s:ttl", "deal", tenant_id=TENANT, actor_user_id="recOWNER0000001", source_channel=CHANNEL, channel=CHANNEL,
)
chk("EXPIRED persisted -- second load sees it directly", reloaded3.lifecycle_state is DraftState.EXPIRED)

print("\n[concurrency] edit increments version, stale save conflicts")
store4 = PersistentSessionStore(maxsize=10)
d0 = _deal_draft("s:cas")
saved0 = store4.create_business_draft("s:cas", d0, channel=CHANNEL)
chk("version starts at 1", saved0.idempotency_key == 1)

d1 = saved0.set_field("name", "Acme")
saved1 = store4.save_business_draft("s:cas", d1, expected_version=1, channel=CHANNEL)
chk("version bumped to 2 after one save", saved1.idempotency_key == 2)

# a second, independent load still holding the stale (pre-edit) draft...
try:
    store4.save_business_draft("s:cas", d0.set_field("name", "Other"), expected_version=1, channel=CHANNEL)
    chk("stale version save returns DRAFT_CONFLICT", False)
except DraftConflictError:
    chk("stale version save returns DRAFT_CONFLICT", True)

print("\n[terminal states] confirmed cannot be edited, cancelled cannot resume")
store5 = PersistentSessionStore(maxsize=10)
d = _deal_draft("s:term")
d = d.set_field("name", "Acme deal")
d = d.set_field("domain", "import")
d = d.set_field("owner", "recOWNER0000001")
d = d.set_field("counterparty_contact", "recCONTACT00001")
saved_ready = store5.create_business_draft("s:term", d, channel=CHANNEL)
confirmed, _snapshot = saved_ready.confirm()
saved_confirmed = store5.save_business_draft("s:term", confirmed, expected_version=saved_ready.idempotency_key, channel=CHANNEL)
chk("confirmed draft persisted", saved_confirmed.lifecycle_state is DraftState.CONFIRMED)
loaded_confirmed = store5.load_business_draft(
    "s:term", "deal", tenant_id=TENANT, actor_user_id="recOWNER0000001", source_channel=CHANNEL, channel=CHANNEL,
)
try:
    loaded_confirmed.set_field("name", "changed")
    chk("confirmed draft cannot be edited", False)
except BusinessDraftError:
    chk("confirmed draft cannot be edited", True)
try:
    store5.create_business_draft("s:term", _deal_draft("s:term"), channel=CHANNEL)
    chk("new CREATE blocked while a CONFIRMED draft is pending", False)
except DraftConflictError:
    chk("new CREATE blocked while a CONFIRMED draft is pending", True)

store6 = PersistentSessionStore(maxsize=10)
d6 = _deal_draft("s:cancel")
saved6 = store6.create_business_draft("s:cancel", d6, channel=CHANNEL)
cancelled = saved6.cancel()
store6.save_business_draft("s:cancel", cancelled, expected_version=saved6.idempotency_key, channel=CHANNEL)
loaded_cancelled = store6.load_business_draft(
    "s:cancel", "deal", tenant_id=TENANT, actor_user_id="recOWNER0000001", source_channel=CHANNEL, channel=CHANNEL,
)
chk("cancelled draft stays CANCELLED (not resurrected)", loaded_cancelled.lifecycle_state is DraftState.CANCELLED)
try:
    loaded_cancelled.set_field("name", "x")
    chk("cancelled draft cannot be resumed", False)
except BusinessDraftError:
    chk("cancelled draft cannot be resumed", True)
# a fresh CREATE over a CANCELLED slot is allowed (only CONFIRMED blocks)
new_after_cancel = store6.create_business_draft("s:cancel", _deal_draft("s:cancel"), channel=CHANNEL)
chk("a fresh CREATE replaces a CANCELLED slot", new_after_cancel.lifecycle_state is DraftState.CAPTURED)

print("\n[delete]")
store7 = PersistentSessionStore(maxsize=10)
store7.create_business_draft("s:del", _deal_draft("s:del"), channel=CHANNEL)
store7.delete_business_draft("s:del", "deal", channel=CHANNEL)
chk(
    "deleted draft no longer loads",
    store7.load_business_draft(
        "s:del", "deal", tenant_id=TENANT, actor_user_id="recOWNER0000001", source_channel=CHANNEL, channel=CHANNEL,
    ) is None,
)

print("\n[multi-entity coexistence]")
store8 = PersistentSessionStore(maxsize=10)
store8.create_business_draft("s:multi", _deal_draft("s:multi"), channel=CHANNEL)
store8.create_business_draft("s:multi", _contact_draft("s:multi"), channel=CHANNEL)
all_drafts = store8.list_business_drafts_for_session("s:multi", channel=CHANNEL)
chk("two different-entity drafts coexist", set(all_drafts) == {"deal", "contact"})

print("\n[frozen v1 cardinality] second same-entity CREATE replaces the first (not CONFIRMED)")
store9 = PersistentSessionStore(maxsize=10)
first = store9.create_business_draft("s:replace", _deal_draft("s:replace"), channel=CHANNEL)
second_source = _deal_draft("s:replace").set_field("name", "Second Deal")
second = store9.create_business_draft("s:replace", second_source, channel=CHANNEL)
chk("replace bumps the version monotonically (1 -> 2), doesn't reset", second.idempotency_key == first.idempotency_key + 1)
chk("replace overwrites fields", second.fields.get("name") == "Second Deal")
only_one = store9.list_business_drafts_for_session("s:replace", channel=CHANNEL)
chk("still exactly one draft for that entity_type", list(only_one.keys()) == ["deal"])

print("\n[PHASE 3] CAS version reflects the STORED version, not the in-memory edit-bump count")
store10 = PersistentSessionStore(maxsize=10)
draft10 = _deal_draft("s:cas")
# Multiple in-memory edits BEFORE any persistence call -- each set_field()
# bumps idempotency_key locally; storage hasn't been touched yet. This is
# exactly the "build entirely in memory first, persist once" sequencing
# app.py's _run_deal_business_draft() uses.
draft10 = draft10.set_field("name", "Acme")
draft10 = draft10.set_field("domain", "import")
draft10 = draft10.set_field("owner", "recOWNER0000001")
draft10 = draft10.set_field("counterparty_contact", "recCONTACT00001")
chk("in-memory edits bumped idempotency_key well past 1", draft10.idempotency_key > 1)

persisted10 = store10.create_business_draft("s:cas", draft10, channel=CHANNEL)
chk(
    "first persist stamps version 1 regardless of how many in-memory edits preceded it",
    persisted10.idempotency_key == 1,
)

confirmed10, snapshot10 = persisted10.confirm()
stored_confirmed10 = store10.save_business_draft(
    "s:cas", confirmed10, expected_version=persisted10.idempotency_key, channel=CHANNEL,
)
chk("READY -> CONFIRMED persist increments exactly one stored version (1 -> 2)", stored_confirmed10.idempotency_key == 2)

reload10 = store10.load_business_draft(
    "s:cas", "deal", tenant_id=TENANT, actor_user_id="recOWNER0000001", source_channel=CHANNEL, channel=CHANNEL,
)
chk("an independent reload agrees with the returned stored object (both at version 2)", reload10.idempotency_key == 2)
chk(
    "ownership context built from the returned stored_confirmed matches the reload "
    "(the bug this regression catches: building it from the pre-save object would "
    "record version 1 while storage/reload are already at 2)",
    reload10.idempotency_key == stored_confirmed10.idempotency_key
    and reload10.snapshot.confirmed_at == stored_confirmed10.snapshot.confirmed_at,
)

print(f"\n{'=' * 40}")
print(f"BusinessDraft Persistence Tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
