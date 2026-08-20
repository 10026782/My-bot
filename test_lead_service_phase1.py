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

# Bare "ליד חדש" trigger -> help prompt, no write, no guessing
reply3 = lch.handle_lead_candidate(identity, "ליד חדש", "phase1_bare", "telegram")
chk("integration: bare 'ליד חדש' trigger shows the format, writes nothing",
    isinstance(reply3, str) and "|" in reply3)


print(f"\n{'='*50}")
print(f"Phase 1 (Canonical Lead Foundation) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
