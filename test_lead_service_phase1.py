# test_lead_service_phase1.py — Phase 1: Canonical Lead Foundation
#
# Regression suite for the Lead System E2E Audit's Phase 1 remediation:
#   - Domain contract: explicit "domain X"/"דומיין X" always beats inferred
#     keyword-scan, and the root-cause "מס" substring-match bug
#     (recruitment -> finance, the golden failure case: "...בעל מספר
#     צוותים...") is closed at the source (core/router/domain_router.py).
#   - Owner contract: a new Lead always gets an Owner; default = creator.
#   - Structured creation command: "ליד חדש | שם | טלפון | domain | הערה"
#     never guesses where the name ends and the note begins.
#   - Canonical writer: create_lead() validates, dedups once, and never
#     double-writes.
#
# Plain script (no pytest dependency), matching this repo's existing
# test_*.py convention — see CLAUDE.md "Tests".

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("ELIYAHU_CHAT_ID", "123456")

from unittest.mock import patch
from types import SimpleNamespace

from core.router.domain_router import detect_domain
from core.lead_service import (
    LeadPayload, LeadCreateResult, CANONICAL_LEAD_DOMAINS,
    resolve_domain, resolve_domain_word, resolve_owner,
    parse_structured_command, create_lead, build_lead_fields, build_memory_key,
)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


class MockIdentity:
    is_internal = True
    tenant_id   = "boss_hq"
    user_id     = "eliyahu"
    memory_key  = "boss_hq/eliyahu@owner"
    domain_id   = "general"
    role        = "owner"


identity = MockIdentity()

GOLDEN_TEXT = (
    "צור ליד חדש domain recruitment 0506872216 עידן מושקוביץ תשתיות "
    "חיצוניות עובד רציני בעל מספר צוותים ממתין להצעה רצינית"
)


# ══════════════════════════════════════════════════
# 1. Domain contract — golden failure case + root-cause regex
# ══════════════════════════════════════════════════
print("── 1. Domain contract ──")

chk("Router: golden case resolves to recruitment (root-cause regex fix)",
    detect_domain(GOLDEN_TEXT, domain_from_channel="", domain_from_identity="general")[0] == "recruitment")

for word in ("מספר", "מסמך", "מסלול"):
    chk(f"Router: {word!r} alone must NOT match finance (word-boundary fix)",
        detect_domain(word, "", "")[0] != "finance")

for word in ("מס הכנסה", "לשלם מס"):
    chk(f"Router: {word!r} still correctly matches finance (real tax mention)",
        detect_domain(word, "", "")[0] == "finance")

# Explicit annotation always wins, even simulating the PRE-FIX router guess
# (finance) being passed in — proves the fix holds even if the router
# regressed again.
domain, explicit = resolve_domain(GOLDEN_TEXT, router_domain="finance")
chk("resolve_domain: explicit 'domain recruitment' wins over a wrong router guess",
    domain == "recruitment" and explicit is True)

domain2, explicit2 = resolve_domain("צור ליד דומיין גיוס 0501234567", router_domain="general")
chk("resolve_domain: Hebrew 'דומיין גיוס' also resolves explicitly",
    domain2 == "recruitment" and explicit2 is True)

domain3, explicit3 = resolve_domain("משה כהן 0501234567", router_domain="real_estate")
chk("resolve_domain: no hint -> router's own valid business-vertical guess wins",
    domain3 == "real_estate" and explicit3 is False)

domain4, explicit4 = resolve_domain("ליד חדש: משה כהן", router_domain="crm")
chk("resolve_domain: routing-only meta-domain ('crm') never leaks into a Lead's domain",
    domain4 == "general" and explicit4 is False)

chk("resolve_domain_word: 'recruitment' (structured-command token)",
    resolve_domain_word("recruitment") == "recruitment")
chk("resolve_domain_word: 'גיוס' (Hebrew alias)",
    resolve_domain_word("גיוס") == "recruitment")
chk("resolve_domain_word: unknown token -> None (never guessed)",
    resolve_domain_word("xyz_not_a_domain") is None)


# ══════════════════════════════════════════════════
# 2. Owner contract
# ══════════════════════════════════════════════════
print()
print("── 2. Owner contract ──")

with patch("tma_api._resolve_profile_record_id", return_value="recOWNER123") as m:
    record_id, resolved_user = resolve_owner(identity)
    chk("resolve_owner: no owner given -> defaults to creator (identity.user_id)",
        record_id == "recOWNER123" and resolved_user == "eliyahu")
    m.assert_called_once_with("eliyahu")

with patch("tma_api._resolve_profile_record_id", return_value="recOTHER999"):
    record_id, resolved_user = resolve_owner(identity, owner_user_id="dana")
    chk("resolve_owner: explicit owner_user_id is resolved, not overridden by creator",
        record_id == "recOTHER999" and resolved_user == "dana")

with patch("tma_api._resolve_profile_record_id", return_value=None):
    record_id, resolved_user = resolve_owner(identity, owner_user_id="ghost")
    chk("resolve_owner: unresolvable explicit owner returns None (caller must surface an error, never invent)",
        record_id is None and resolved_user == "ghost")


# ══════════════════════════════════════════════════
# 3. Structured creation command
# ══════════════════════════════════════════════════
print()
print("── 3. Structured creation command ──")

parsed = parse_structured_command(
    "ליד חדש | עידן מושקוביץ | 0506872216 | recruitment | תשתיות חיצוניות, בעל מספר צוותים"
)
chk("structured: full valid command parses name/phone/domain/note without guessing",
    parsed == {
        "name": "עידן מושקוביץ", "phone": "0506872216",
        "domain": "recruitment", "note": "תשתיות חיצוניות, בעל מספר צוותים",
    })

chk("structured: bare trigger -> prompt, not a guess",
    parse_structured_command("ליד חדש") == {"prompt": True})

chk("structured: missing domain -> explicit error, not a silent default",
    "error" in (parse_structured_command("ליד חדש | עידן | 0506872216") or {}))

chk("structured: unrecognized domain word -> explicit error, never invented",
    "error" in (parse_structured_command("ליד חדש | עידן | 0506872216 | not_a_real_domain") or {}))

chk("structured: invalid phone -> explicit error",
    "error" in (parse_structured_command("ליד חדש | עידן | not-a-phone | recruitment") or {}))

chk("structured: not the trigger at all -> None (falls through to NL capture)",
    parse_structured_command("משה כהן 0501234567") is None)

chk("structured: empty text -> None",
    parse_structured_command("") is None)


# ══════════════════════════════════════════════════
# 4. Canonical writer — create_lead()
# ══════════════════════════════════════════════════
print()
print("── 4. create_lead() ──")


def _make_ok_gateway_result(contract_id="c1"):
    return SimpleNamespace(ok=True, contract_id=contract_id, reason="", user_message="")


def _make_blocked_gateway_result(reason="duplicate pending"):
    return SimpleNamespace(ok=False, contract_id=None, reason=reason, user_message=reason)


class _FakeLedger:
    _repository = None
    def update_status(self, contract_id, status):
        return True
    def find_by_id(self, contract_id):
        return None


def _mocked_create_lead(**overrides):
    """Runs create_lead() with every external I/O boundary mocked, so this
    test never touches a real Airtable/feature-flag/tool-registry. Returns
    the LeadCreateResult plus the mocks, for assertion."""
    payload_kwargs = dict(
        name="עידן מושקוביץ", phone="0506872216", domain="recruitment",
        source="structured_command", channel="telegram", summary="תשתיות חיצוניות",
    )
    payload_kwargs.update(overrides.pop("payload_overrides", {}))
    payload = LeadPayload(**payload_kwargs)

    with patch("feature_flags.is_enabled", return_value=False) as mock_ff, \
         patch("tool_registry.TOOLS_BLOCKED_BY_EMERGENCY", frozenset({"airtable_add"})), \
         patch("tma_api._resolve_profile_record_id", return_value="recOWNER123"), \
         patch("core.lead_service.find_existing_lead", return_value=overrides.get("existing_id_lookup")) as mock_find, \
         patch("core.action_gateway.action_gateway") as mock_gw, \
         patch("tools.airtable_gateway.airtable_create") as mock_create, \
         patch("tools.airtable_gateway.airtable_patch") as mock_patch:

        mock_gw.propose_action.return_value = overrides.get("gateway_result", _make_ok_gateway_result())
        mock_gw._ledger = _FakeLedger()
        mock_create.return_value = overrides.get("create_return", {"id": "recLEAD001"})
        mock_patch.return_value = overrides.get("patch_return", True)

        result = create_lead(
            identity, payload,
            source_module="test", existing_id=overrides.get("existing_id"),
        )
        return result, mock_create, mock_patch, mock_gw, mock_find


# 4a. Happy path — brand-new lead
result, mock_create, mock_patch, mock_gw, mock_find = _mocked_create_lead()
chk("create_lead: brand-new lead -> ok, action=created", result.ok and result.action == "created")
chk("create_lead: record_id comes from the write", result.record_id == "recLEAD001")
chk("create_lead: domain carried through to the result", result.domain == "recruitment")
chk("create_lead: Owner defaulted to creator and surfaced in the result", result.owner_user_id == "eliyahu")
chk("create_lead: airtable_create called exactly once (no double write)", mock_create.call_count == 1)
chk("create_lead: airtable_patch never called for a brand-new lead", mock_patch.call_count == 0)

written_fields = mock_create.call_args[0][1]
from airtable_schema import LeadFields
chk("create_lead: written fields include Owner as a record-id list",
    written_fields.get(LeadFields.OWNER) == ["recOWNER123"])
chk("create_lead: written fields include tenant_id",
    written_fields.get(LeadFields.TENANT_ID) == "boss_hq")
chk("create_lead: written fields include the canonical domain",
    written_fields.get(LeadFields.DOMAIN) == "recruitment")

# 4b. Validation — missing required fields, never invented
result, *_ = _mocked_create_lead(payload_overrides={"name": ""})
chk("create_lead: missing name -> invalid, not a silent default", not result.ok and result.action == "invalid")

result, *_ = _mocked_create_lead(payload_overrides={"phone": ""})
chk("create_lead: missing phone -> invalid, not a silent default", not result.ok and result.action == "invalid")

result, *_ = _mocked_create_lead(payload_overrides={"domain": "not_a_real_domain"})
chk("create_lead: non-canonical domain -> invalid, never written as-is", not result.ok and result.action == "invalid")

# 4c. Dedup — existing_id passed in short-circuits the lookup and updates
result, mock_create, mock_patch, mock_gw, mock_find = _mocked_create_lead(existing_id="recEXISTING")
chk("create_lead: pre-resolved existing_id -> action=updated", result.ok and result.action == "updated")
chk("create_lead: update path calls airtable_patch, not airtable_create",
    mock_patch.call_count == 1 and mock_create.call_count == 0)
chk("create_lead: caller-supplied existing_id skips a second dedup lookup",
    mock_find.call_count == 0)

# 4d. No caller-supplied existing_id -> service does exactly one lookup
result, mock_create, mock_patch, mock_gw, mock_find = _mocked_create_lead(
    existing_id_lookup="recEXISTING2",
)
chk("create_lead: no pre-resolved id -> service performs exactly one dedup lookup",
    mock_find.call_count == 1)
chk("create_lead: that lookup's match drives an update, not a create",
    result.action == "updated" and mock_patch.call_count == 1 and mock_create.call_count == 0)

# 4e. Gateway dedup fingerprint blocks a duplicate write outright
result, mock_create, mock_patch, mock_gw, mock_find = _mocked_create_lead(
    gateway_result=_make_blocked_gateway_result(),
)
chk("create_lead: gateway-blocked (duplicate fingerprint) -> ok=False, action=duplicate",
    not result.ok and result.action == "duplicate")
chk("create_lead: no write attempted at all when the gateway blocks",
    mock_create.call_count == 0 and mock_patch.call_count == 0)

# 4f. EMERGENCY_STOP_ALL blocks the write before any I/O
with patch("feature_flags.is_enabled", return_value=True), \
     patch("tool_registry.TOOLS_BLOCKED_BY_EMERGENCY", frozenset({"airtable_add"})), \
     patch("core.action_gateway.action_gateway") as mock_gw2, \
     patch("tools.airtable_gateway.airtable_create") as mock_create2:
    payload = LeadPayload(name="X", phone="0501234567", domain="general")
    result = create_lead(identity, payload, source_module="test")
    chk("create_lead: EMERGENCY_STOP_ALL blocks before any write",
        not result.ok and result.action == "blocked")
    chk("create_lead: no gateway/write call at all under emergency stop",
        mock_gw2.propose_action.call_count == 0 and mock_create2.call_count == 0)


# ══════════════════════════════════════════════════
# 5. Full integration — handle_lead_candidate() reproducing the golden
#    failure case end-to-end, through the real chat-capture entry point
#    (not just the service in isolation).
# ══════════════════════════════════════════════════
print()
print("── 5. Full integration: golden failure case via handle_lead_candidate() ──")

import core.lead_candidate_handler as lch
from session_store import lead_sessions

# Only FEATURE_AUTO_CAPTURE is on (needed for Tier-1 immediate write) —
# everything else (including EMERGENCY_STOP_ALL) stays off, unlike a
# blanket return_value=True which would incorrectly self-block the write.
def _ff_only_auto_capture(flag_name, *a, **kw):
    return flag_name == "FEATURE_AUTO_CAPTURE"


with patch("feature_flags.is_enabled", side_effect=_ff_only_auto_capture), \
     patch("tool_registry.TOOLS_BLOCKED_BY_EMERGENCY", frozenset({"airtable_add"})), \
     patch("tma_api._resolve_profile_record_id", return_value="recOWNER123"), \
     patch("core.lead_service.find_existing_lead", return_value=None), \
     patch("core.action_gateway.action_gateway") as mock_gw3, \
     patch("tools.airtable_gateway.airtable_create") as mock_create3:

    mock_gw3.propose_action.return_value = _make_ok_gateway_result()
    mock_gw3._ledger = _FakeLedger()
    mock_create3.return_value = {"id": "recIDAN001"}

    chat_id = "phase1_golden_case"
    # Simulates app.py passing the Router's ACTUAL (pre-fix-era) guess —
    # "finance" — as resolved_route_domain, exactly as happened in
    # production. The explicit "domain recruitment" annotation in the text
    # itself must still win.
    reply = lch.handle_lead_candidate(
        identity, GOLDEN_TEXT, chat_id, "telegram",
        domain="finance", intent="create_lead", session=lead_sessions.get_or_create(chat_id),
    )

    # airtable_create is a shared, table-agnostic write function — other
    # subsystems triggered along the way (e.g. raw-capture observability)
    # may also call it, so isolate the Leads-table write specifically
    # rather than assuming it was the only (or first) call.
    lead_calls = [c for c in mock_create3.call_args_list if c.args and c.args[0] == "Leads"]

    chk("integration: golden case produces a success reply, not a silent drop",
        isinstance(reply, str) and reply.startswith("✅"))
    chk("integration: exactly one write to the Leads table (no double write)",
        len(lead_calls) == 1)

    if lead_calls:
        written = lead_calls[0].args[1]
        chk("integration: the ACTUAL written domain is 'recruitment', not 'finance'",
            written.get(LeadFields.DOMAIN) == "recruitment")
        chk("integration: the written record has an Owner (never empty when creator is known)",
            written.get(LeadFields.OWNER) == ["recOWNER123"])
        chk("integration: tenant_id was stamped on the write",
            written.get(LeadFields.TENANT_ID) == "boss_hq")


# ══════════════════════════════════════════════════
# 6. Full integration — structured command via handle_lead_candidate()
# ══════════════════════════════════════════════════
print()
print("── 6. Full integration: structured command via handle_lead_candidate() ──")

with patch("feature_flags.is_enabled", return_value=False), \
     patch("tool_registry.TOOLS_BLOCKED_BY_EMERGENCY", frozenset({"airtable_add"})), \
     patch("tma_api._resolve_profile_record_id", return_value="recOWNER123"), \
     patch("core.lead_service.find_existing_lead", return_value=None), \
     patch("core.action_gateway.action_gateway") as mock_gw4, \
     patch("tools.airtable_gateway.airtable_create") as mock_create4:

    mock_gw4.propose_action.return_value = _make_ok_gateway_result()
    mock_gw4._ledger = _FakeLedger()
    mock_create4.return_value = {"id": "recIDAN002"}

    chat_id2 = "phase1_structured"
    reply2 = lch.handle_lead_candidate(
        identity,
        "ליד חדש | עידן מושקוביץ | 0506872216 | recruitment | תשתיות חיצוניות, בעל מספר צוותים",
        chat_id2, "telegram", session=lead_sessions.get_or_create(chat_id2),
    )
    chk("integration: structured command bypasses NL parsing entirely and succeeds",
        isinstance(reply2, str) and reply2.startswith("✅"))
    chk("integration: structured command also produces exactly one write",
        mock_create4.call_count == 1)
    if mock_create4.call_count == 1:
        written2 = mock_create4.call_args[0][1]
        chk("integration: structured command's name/note are never mixed up",
            written2.get(LeadFields.NAME) == "עידן מושקוביץ"
            and "תשתיות חיצוניות" in written2.get(LeadFields.SUMMARY, ""))
        chk("integration: structured command's domain is exactly 'recruitment'",
            written2.get(LeadFields.DOMAIN) == "recruitment")

# ══════════════════════════════════════════════════
# 7. Lead Draft Card — the primary creation UX
# ══════════════════════════════════════════════════
print()
print("── 7. Lead Draft Card ──")

# 7a. Bare "ליד חדש" -> starts filling mode, asks for name, writes nothing.
chat_bare = "phase1_draft_bare"
reply_bare = lch.handle_lead_candidate(identity, "ליד חדש", chat_bare, "telegram",
                                        session=lead_sessions.get_or_create(chat_bare))
chk("draft: bare trigger asks for the first missing field (name), no card yet",
    reply_bare == "מה שם הליד?")
draft_state = lead_sessions.get_lead_draft(chat_bare)
chk("draft: session now holds a filling-mode draft awaiting 'name'",
    draft_state is not None and draft_state["mode"] == "filling" and draft_state["awaiting_field"] == "name")

# 7b. Sequential fill: name -> phone -> domain -> review card.
r1 = lch.handle_lead_candidate(identity, "עידן מושקוביץ", chat_bare, "telegram",
                                session=lead_sessions.get_or_create(chat_bare))
chk("draft: after name, asks for phone next", r1 == "מה מספר הטלפון?")

r2 = lch.handle_lead_candidate(identity, "0506872216", chat_bare, "telegram",
                                session=lead_sessions.get_or_create(chat_bare))
chk("draft: after phone, asks for domain next",
    isinstance(r2, str) and r2.startswith("מה התחום?"))

r3 = lch.handle_lead_candidate(identity, "recruitment", chat_bare, "telegram",
                                session=lead_sessions.get_or_create(chat_bare))
chk("draft: once all required fields are filled, shows the full review card",
    isinstance(r3, str) and "👤 ליד חדש" in r3 and "עידן מושקוביץ" in r3 and "0506872216" in r3 and "גיוס" in r3)
draft_state2 = lead_sessions.get_lead_draft(chat_bare)
chk("draft: state switched to review mode", draft_state2["mode"] == "review")

# invalid phone during filling -> re-asks the SAME field, never silently accepted
chat_badphone = "phase1_draft_badphone"
lch.handle_lead_candidate(identity, "ליד חדש", chat_badphone, "telegram",
                           session=lead_sessions.get_or_create(chat_badphone))
lch.handle_lead_candidate(identity, "דנה כהן", chat_badphone, "telegram",
                           session=lead_sessions.get_or_create(chat_badphone))
r_badphone = lch.handle_lead_candidate(identity, "not-a-phone", chat_badphone, "telegram",
                                        session=lead_sessions.get_or_create(chat_badphone))
chk("draft: invalid phone during filling is rejected, not silently accepted",
    isinstance(r_badphone, str) and r_badphone.startswith("❌"))
chk("draft: still awaiting phone after a rejected value",
    lead_sessions.get_lead_draft(chat_badphone)["awaiting_field"] == "phone")

# 7c. Prefilled draft from free text after the trigger (explicit domain
# annotation in the text -> domain counts as confidently filled).
chat_prefill = "phase1_draft_prefill"
reply_prefill = lch.handle_lead_candidate(
    identity, "ליד חדש עידן מושקוביץ domain recruitment 0506872216 תשתיות חיצוניות",
    chat_prefill, "telegram", session=lead_sessions.get_or_create(chat_prefill),
)
chk("draft: prefilled from free text goes straight to the review card (all required fields found)",
    isinstance(reply_prefill, str) and "👤 ליד חדש" in reply_prefill
    and "עידן מושקוביץ" in reply_prefill and "0506872216" in reply_prefill and "גיוס" in reply_prefill)

# 7d. Confirm ("כן") writes the lead through the SAME canonical create_lead().
with patch("feature_flags.is_enabled", return_value=False), \
     patch("tool_registry.TOOLS_BLOCKED_BY_EMERGENCY", frozenset({"airtable_add"})), \
     patch("tma_api._resolve_profile_record_id", return_value="recOWNER123"), \
     patch("core.lead_service.find_existing_lead", return_value=None), \
     patch("core.action_gateway.action_gateway") as mock_gw5, \
     patch("tools.airtable_gateway.airtable_create") as mock_create5:

    mock_gw5.propose_action.return_value = _make_ok_gateway_result()
    mock_gw5._ledger = _FakeLedger()
    mock_create5.return_value = {"id": "recDRAFT001"}

    reply_confirm = lch.handle_lead_candidate(identity, "כן", chat_prefill, "telegram",
                                               session=lead_sessions.get_or_create(chat_prefill))
    chk("draft: confirming ('כן') writes the lead and reports success",
        isinstance(reply_confirm, str) and reply_confirm.startswith("✅"))
    chk("draft: confirming writes exactly once", mock_create5.call_count == 1)
    chk("draft: session draft is cleared after a successful write",
        lead_sessions.get_lead_draft(chat_prefill) is None)

# 7e. Edit flow: pick a field, change it, land back on the review card.
chat_edit = "phase1_draft_edit"
lch.handle_lead_candidate(
    identity, "ליד חדש עידן מושקוביץ domain recruitment 0506872216 תשתיות חיצוניות",
    chat_edit, "telegram", session=lead_sessions.get_or_create(chat_edit),
)
r_edit1 = lch.handle_lead_candidate(identity, "ערוך", chat_edit, "telegram",
                                     session=lead_sessions.get_or_create(chat_edit))
chk("draft: 'ערוך' asks which field to change", "שדה" in r_edit1)

r_edit2 = lch.handle_lead_candidate(identity, "טלפון", chat_edit, "telegram",
                                     session=lead_sessions.get_or_create(chat_edit))
chk("draft: picking 'טלפון' asks for the new phone, showing the current one",
    isinstance(r_edit2, str) and "0506872216" in r_edit2)

r_edit3 = lch.handle_lead_candidate(identity, "0501112222", chat_edit, "telegram",
                                     session=lead_sessions.get_or_create(chat_edit))
chk("draft: after supplying the new value, lands back on the full review card",
    isinstance(r_edit3, str) and "👤 ליד חדש" in r_edit3 and "0501112222" in r_edit3
    and "0506872216" not in r_edit3)

# 7f. Cancel at any stage clears the draft, no write.
chat_cancel = "phase1_draft_cancel"
lch.handle_lead_candidate(identity, "ליד חדש", chat_cancel, "telegram",
                           session=lead_sessions.get_or_create(chat_cancel))
r_cancel = lch.handle_lead_candidate(identity, "לא", chat_cancel, "telegram",
                                      session=lead_sessions.get_or_create(chat_cancel))
chk("draft: cancelling during filling mode clears the draft",
    r_cancel == "↩️ בוטל" and lead_sessions.get_lead_draft(chat_cancel) is None)

# 7g. Owner Contract hardened: unresolved Owner blocks creation outright —
# no half-canonical Lead, no write attempted.
with patch("feature_flags.is_enabled", return_value=False), \
     patch("tool_registry.TOOLS_BLOCKED_BY_EMERGENCY", frozenset({"airtable_add"})), \
     patch("tma_api._resolve_profile_record_id", return_value=None), \
     patch("tools.airtable_gateway.airtable_create") as mock_create6:
    payload = LeadPayload(name="X", phone="0501234567", domain="general")
    result = create_lead(identity, payload, source_module="test")
    chk("create_lead: unresolved Owner (creator not found in Profile) hard-blocks creation",
        not result.ok and result.action == "invalid")
    chk("create_lead: no write attempted when Owner cannot be resolved",
        mock_create6.call_count == 0)

# 7h. N18 Phase 2 (clarification/validation-loop wiring): a single
# continuous chain through the real orchestration entry point
# (handle_lead_candidate(), never resolve_draft_reply()/set_draft_field()
# called directly) proving invalid replies for TWO DIFFERENT required
# fields each re-ask the same field without advancing, and a valid reply
# for each advances/completes — the exact scenario the shared draft_flow.py
# state machine (not a Lead-specific duplicate) must preserve.
chat_chain = "phase1_draft_chain"
lch.handle_lead_candidate(identity, "ליד חדש", chat_chain, "telegram",
                           session=lead_sessions.get_or_create(chat_chain))
lch.handle_lead_candidate(identity, "אור לוי", chat_chain, "telegram",
                           session=lead_sessions.get_or_create(chat_chain))
chk("chain: after name, awaiting phone",
    lead_sessions.get_lead_draft(chat_chain)["awaiting_field"] == "phone")

r_chain_badphone = lch.handle_lead_candidate(identity, "abc", chat_chain, "telegram",
                                              session=lead_sessions.get_or_create(chat_chain))
chk("chain: invalid phone rejected", isinstance(r_chain_badphone, str) and r_chain_badphone.startswith("❌"))
chk("chain: still awaiting phone after the rejected value",
    lead_sessions.get_lead_draft(chat_chain)["awaiting_field"] == "phone")

lch.handle_lead_candidate(identity, "0501112222", chat_chain, "telegram",
                           session=lead_sessions.get_or_create(chat_chain))
chk("chain: valid phone advances to domain",
    lead_sessions.get_lead_draft(chat_chain)["awaiting_field"] == "domain")

r_chain_baddomain = lch.handle_lead_candidate(identity, "בלה בלה לא קיים", chat_chain, "telegram",
                                               session=lead_sessions.get_or_create(chat_chain))
chk("chain: invalid domain rejected", isinstance(r_chain_baddomain, str) and r_chain_baddomain.startswith("❌"))
chk("chain: still awaiting domain after the rejected value",
    lead_sessions.get_lead_draft(chat_chain)["awaiting_field"] == "domain")

r_chain_final = lch.handle_lead_candidate(identity, "recruitment", chat_chain, "telegram",
                                           session=lead_sessions.get_or_create(chat_chain))
chk("chain: valid domain completes required fields -> review card",
    isinstance(r_chain_final, str) and "👤 ליד חדש" in r_chain_final and "אור לוי" in r_chain_final)
chk("chain: mode switched to review", lead_sessions.get_lead_draft(chat_chain)["mode"] == "review")


# ══════════════════════════════════════════════════
# 8. Attribution model — campaign/adset/ad + referral (separate concepts,
#    never squashed into one text field)
# ══════════════════════════════════════════════════
print()
print("── 8. Attribution model ──")

result, mock_create7, *_ = _mocked_create_lead(
    payload_overrides={"is_referral": True, "referrer_name": "משה", "referral_fee_type": "fixed", "referral_fee_value": 500},
)
chk("attribution: a well-formed referral payload creates successfully",
    result.ok and result.action == "created")
if mock_create7.call_count:
    written_ref = mock_create7.call_args[0][1]
    chk("attribution: referral fields are NOT squashed into the source/summary text",
        "משה" not in str(written_ref.get(LeadFields.SOURCE, ""))
        and "500" not in str(written_ref.get(LeadFields.SOURCE, "")))

result, *_ = _mocked_create_lead(payload_overrides={"is_referral": True})
chk("attribution: is_referral=True with no referrer_id/referrer_name -> invalid, never guessed",
    not result.ok and result.action == "invalid")

result, *_ = _mocked_create_lead(payload_overrides={"referral_fee_type": "fixed"})
chk("attribution: a fee type set without is_referral=True -> invalid (inconsistent payload)",
    not result.ok and result.action == "invalid")

result, *_ = _mocked_create_lead(
    payload_overrides={"is_referral": True, "referrer_name": "משה", "referral_fee_type": "bogus"},
)
chk("attribution: an unrecognized referral_fee_type -> invalid, not silently accepted",
    not result.ok and result.action == "invalid")

payload_campaign = LeadPayload(name="X", phone="0501234567", domain="general",
                                campaign="קמפיין קיץ", adset="adset1", ad="ad1")
fields_campaign = build_lead_fields(payload_campaign, "recOWNER123", "boss_hq/0501234567@lead")
chk("attribution: campaign/adset/ad are accepted in the payload but not written (no live schema column)",
    LeadFields.NAME in fields_campaign
    and "קמפיין קיץ" not in str(fields_campaign)
    and "adset1" not in str(fields_campaign))


# ══════════════════════════════════════════════════
# 9. Staging regression (2026-08-20): "כן" against a review-mode draft
#    fell through to app.py's EARLIER ActionGateway confirm-word dispatch
#    (core/action_gateway.py's "אין פעולה שממתינה לאישור") because that
#    branch runs BEFORE handle_lead_candidate() and had no knowledge of
#    lead_draft. Fixed via should_prefer_lead_draft() / resolve_lead_
#    draft_confirmation() — this section tests app.py's actual call
#    pattern (self-fetching, no session snapshot), not handle_lead_
#    candidate()'s in-flow path (already covered by section 7).
# ══════════════════════════════════════════════════
print()
print("── 9. Staging regression: early confirm/cancel-word dispatch for a review-mode draft ──")

chat_early = "phase1_draft_early_dispatch"
lch.handle_lead_candidate(
    identity, "ליד חדש יונתן רפאל domain recruitment 0548155880 מחפש עבודה בחיפה",
    chat_early, "telegram", session=lead_sessions.get_or_create(chat_early),
)
chk("regression: should_prefer_lead_draft is True for a fresh review-mode card with no competing bookmark",
    lch.should_prefer_lead_draft(identity.memory_key, chat_early))

with patch("feature_flags.is_enabled", return_value=False), \
     patch("tool_registry.TOOLS_BLOCKED_BY_EMERGENCY", frozenset({"airtable_add"})), \
     patch("tma_api._resolve_profile_record_id", return_value="recOWNER123"), \
     patch("core.lead_service.find_existing_lead", return_value=None), \
     patch("core.action_gateway.action_gateway") as mock_gw6, \
     patch("tools.airtable_gateway.airtable_create") as mock_create8:

    mock_gw6.propose_action.return_value = _make_ok_gateway_result()
    mock_gw6._ledger = _FakeLedger()
    mock_create8.return_value = {"id": "recYONATAN001"}

    # Exactly app.py's call signature/pattern: no session snapshot, self-fetching.
    from core.turn_result import TurnResult as _TurnResult, STATUS_CONFIRMED as _STATUS_CONFIRMED
    reply_early = lch.resolve_lead_draft_confirmation(identity, chat_early, "telegram",
                                                        is_confirm=True, is_cancel=False)
    chk("regression: the early-dispatch path (app.py's actual call shape) resolves 'כן', "
        "not 'אין פעולה שממתינה לאישור'",
        isinstance(reply_early, _TurnResult) and reply_early.message.startswith("✅")
        and reply_early.status == _STATUS_CONFIRMED)
    chk("regression: the early-dispatch confirm wrote exactly once", mock_create8.call_count == 1)
    chk("regression: draft cleared after the early-dispatch confirm",
        lead_sessions.get_lead_draft(chat_early) is None)

# A cancel word against a review-mode draft, same early-dispatch shape.
chat_early_cancel = "phase1_draft_early_cancel"
lch.handle_lead_candidate(
    identity, "ליד חדש רונית ברק domain recruitment 0521234567",
    chat_early_cancel, "telegram", session=lead_sessions.get_or_create(chat_early_cancel),
)
from core.turn_result import STATUS_CANCELLED as _STATUS_CANCELLED
reply_early_cancel = lch.resolve_lead_draft_confirmation(identity, chat_early_cancel, "telegram",
                                                          is_confirm=False, is_cancel=True)
chk("regression: early-dispatch cancel resolves against the review-mode draft",
    reply_early_cancel.message == "↩️ בוטל"
    and reply_early_cancel.status == _STATUS_CANCELLED)
chk("regression: draft cleared after early-dispatch cancel",
    lead_sessions.get_lead_draft(chat_early_cancel) is None)

# No draft pending at all -> early-dispatch helper is a clean no-op (None),
# letting app.py's existing ActionGateway/Tier-2 logic run unaffected.
chk("regression: should_prefer_lead_draft is False with nothing pending",
    not lch.should_prefer_lead_draft(identity.memory_key, "phase1_no_draft_at_all"))
chk("regression: resolve_lead_draft_confirmation is a no-op (None) with nothing pending",
    lch.resolve_lead_draft_confirmation(identity, "phase1_no_draft_at_all", "telegram",
                                         is_confirm=True, is_cancel=False) is None)

# 9b. "Stuck until pending is reset": a fresh 'ליד חדש ...' trigger must
# abandon a stale/stuck draft instead of being swallowed by its catch-all.
chat_stuck = "phase1_draft_stuck_then_fresh"
lch.handle_lead_candidate(
    identity, "ליד חדש יונתן רפאל domain recruitment 0548155880",
    chat_stuck, "telegram", session=lead_sessions.get_or_create(chat_stuck),
)
# Simulate the observed stuck state: still in review mode (as if the
# earlier 'כן' had been swallowed elsewhere), then a brand-new "ליד חדש"
# for a DIFFERENT person arrives.
reply_fresh_over_stuck = lch.handle_lead_candidate(
    identity, "ליד חדש זיאד פחמאווי 0548878210",
    chat_stuck, "telegram", session=lead_sessions.get_or_create(chat_stuck),
)
chk("regression: a fresh 'ליד חדש' trigger is never swallowed by a stuck review-mode draft "
    "(no longer echoes the OLD card / '(לא הבנתי)')",
    isinstance(reply_fresh_over_stuck, str) and "לא הבנתי" not in reply_fresh_over_stuck
    and "יונתן רפאל" not in reply_fresh_over_stuck)
new_draft_state = lead_sessions.get_lead_draft(chat_stuck)
chk("regression: the session now holds a draft for the NEW person, not the stuck old one",
    new_draft_state is not None and "0548878210" in str(new_draft_state))

# 9c. Second staging round (2026-08-20, same day, AFTER 2f76a50 was deployed):
# "כן" against a review-mode draft STILL returned "אין פעולה שממתינה לאישור".
# Root cause: app.py's PR2 fast path (_resolve_pr2_deterministic_approval,
# called at the top of run_agent when FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS
# + FEATURE_ACTION_GATEWAY are both on) intercepts bare "כן"/"לא" EARLIER than
# the _CONFIRM_WORDS/_CANCEL_WORDS branch 2f76a50 fixed, and had no knowledge
# of lead_draft either -- confirmed here that the trap function itself still
# unconditionally answers "no_contract" on its own, and that
# should_prefer_lead_draft() (the guard now added at its call site in
# run_agent) correctly identifies this exact scenario so run_agent skips
# calling it.
import app as _app

chat_pr2 = "phase1_draft_pr2_fastpath"
lch.handle_lead_candidate(
    identity, "ליד חדש דנה כהן domain recruitment 0501112222",
    chat_pr2, "telegram", session=lead_sessions.get_or_create(chat_pr2),
)
_pr2_identity = SimpleNamespace(memory_key="phase1_draft_pr2_fastpath", role="owner")
with patch("feature_flags.is_enabled", return_value=True):
    _pr2_trap_reply = _app._resolve_pr2_deterministic_approval(
        user_text="כן", identity=_pr2_identity, live_contracts=[], out_meta=None,
    )
chk("regression: _resolve_pr2_deterministic_approval alone (no lead_draft "
    "awareness) still answers 'no_contract' for a bare 'כן' with no live "
    "contracts -- proving why the run_agent-level guard is required",
    _pr2_trap_reply == "אין פעולה שממתינה לאישור")
chk("regression: should_prefer_lead_draft is True for this exact scenario, "
    "so run_agent's guard (added after this incident) skips the PR2 fast "
    "path entirely and lets the real draft-confirmation logic run instead",
    lch.should_prefer_lead_draft("phase1_draft_pr2_fastpath", chat_pr2))


# ══════════════════════════════════════════════════
# 10. Staging feedback (2026-08-20): numbered domain selection + no
#     literal asterisks in user-facing UI text (Telegram sends these
#     without parse_mode="Markdown" for action_gateway-sourced replies,
#     so "*כן*" rendered as literal asterisks, not bold — fixed by
#     removing the markdown syntax from fixed UI strings rather than
#     enabling parse_mode globally, which would risk breaking message
#     delivery whenever a lead's own name/note contains an unescaped
#     markdown special character).
# ══════════════════════════════════════════════════
print()
print("── 10. Numbered domain selection + asterisk cleanup ──")

from core.lead_service import CANONICAL_LEAD_DOMAINS_ORDERED

chk("domain-by-number: '1' resolves to the first entry in the ordered list",
    resolve_domain_word("1") == CANONICAL_LEAD_DOMAINS_ORDERED[0])
chk("domain-by-number: a valid index anywhere in range resolves correctly",
    resolve_domain_word(str(len(CANONICAL_LEAD_DOMAINS_ORDERED))) == CANONICAL_LEAD_DOMAINS_ORDERED[-1])
chk("domain-by-number: out-of-range number -> None, never guessed",
    resolve_domain_word("99") is None)
chk("domain-by-number: '0' (out of range, 1-based) -> None",
    resolve_domain_word("0") is None)
chk("domain-by-word: still works exactly as before (number is additive, not a replacement)",
    resolve_domain_word("recruitment") == "recruitment")

chat_numbered = "phase1_domain_by_number"
lch.handle_lead_candidate(identity, "ליד חדש", chat_numbered, "telegram",
                           session=lead_sessions.get_or_create(chat_numbered))
lch.handle_lead_candidate(identity, "בדיקת מספר", chat_numbered, "telegram",
                           session=lead_sessions.get_or_create(chat_numbered))
r_numbered = lch.handle_lead_candidate(identity, "0501234567", chat_numbered, "telegram",
                                        session=lead_sessions.get_or_create(chat_numbered))
chk("draft: domain prompt shows a numbered list", "1." in r_numbered and "2." in r_numbered)
recruitment_index = CANONICAL_LEAD_DOMAINS_ORDERED.index("recruitment") + 1
r_pick = lch.handle_lead_candidate(identity, str(recruitment_index), chat_numbered, "telegram",
                                    session=lead_sessions.get_or_create(chat_numbered))
chk("draft: picking the domain by number lands on the review card with the right domain",
    isinstance(r_pick, str) and "👤 ליד חדש" in r_pick and "גיוס" in r_pick)

no_asterisks_texts = [
    r3,                      # section 7's full review card
    reply_prefill,           # section 7's prefilled review card
    r_edit1, r_edit2, r_edit3,
]
chk("UX: no literal '*' survives in any Lead Draft Card text shown to the user",
    all("*" not in t for t in no_asterisks_texts if isinstance(t, str)))


# ══════════════════════════════════════════════════
# 11. Staging QA report (2026-08-20): structured command with "/" delimiter
#     dropped the note field. The documented format only recognized "|" —
#     "/" fell through to the free-text NLP draft path instead, which has
#     no concept of "5th token = note" and silently lost it. Fixed by
#     accepting "/" as an equal alternate delimiter (detected from the
#     matched trigger and used consistently), rather than teaching the NLP
#     fallback to fake structured parsing.
# ══════════════════════════════════════════════════
print()
print("── 11. Structured command: '/' delimiter (staging QA report) ──")

r_slash = parse_structured_command("ליד חדש/משה בדיקה/0502222222/recruitment/בעל מספר צוותים")
chk("structured '/' delimiter: name/phone/domain/note all parsed correctly",
    r_slash == {"name": "משה בדיקה", "phone": "0502222222", "domain": "recruitment",
                "note": "בעל מספר צוותים"})

r_pipe_unchanged = parse_structured_command(
    "ליד חדש | עידן מושקוביץ | 0506872216 | recruitment | תשתיות חיצוניות, בעל מספר צוותים")
chk("structured '|' delimiter: unchanged, still works",
    r_pipe_unchanged is not None and r_pipe_unchanged["note"] == "תשתיות חיצוניות, בעל מספר צוותים")


print(f"\n{'='*50}")
print(f"Phase 1 (Canonical Lead Foundation) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
