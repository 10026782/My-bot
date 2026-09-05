# test_bug_diamond_contact_approval_and_search.py —
# Two production bugs (05/09/2026, live Telegram transcript + Render logs,
# owner) reported together on the SAME DIAMOND PATH nested-Contact-create
# transaction (create a Deal -> counterparty not found -> confirm create ->
# give phone -> approve):
#
#   BOSS: ❌ אושר אך נכשל בביצוע
#   לא הצלחתי להכין תיאור ברור לבקשה הזו. נא לנסח את הבקשה שוב.
#   הפעולה לא הושלמה
#
# The owner identified both root causes correctly from the log himself:
#
# BUG 1 — "הכלי לא נרשם ככותב מורשה" ("the tool isn't registered as an
# authorized writer"): the Render log shows
#   [ERROR] action_validator: Unknown tool blocked: crm_find_or_create_contact
# even though the tool IS registered in tool_registry.py and wired into
# tools/dispatcher.py's dispatch switch — action_validator.py's independent
# `_REQUIRED` allowlist gate (checked before either of those) was simply
# never updated when crm_find_or_create_contact was added, so ActionGateway
# approves the contract, the atomic executor claims it, and dispatch_tool()
# then blocks it anyway as an "unknown tool" -- the approved action can never
# execute. Fix: add "crm_find_or_create_contact": ["name"] to _REQUIRED
# (matching crm_find_or_create_organization's own entry) and to
# _SENSITIVE_TOOLS.
#
# BUG 2 — "המערכת לא באמת מחפשת באנשי קשר אלא רק 7 הראשונים" ("the system
# doesn't really search contacts, just the first 7"): the log's own
#   GET .../Contacts?maxRecords=7&fields[]=שם
# shows commercial_crm.lookup_human_reference() never sent the query text to
# Airtable at all -- for an internal/owner identity
# tools.airtable_security.enforce_tenant_scope() applies no filter, so the
# call fetched only the first `limit + 1` (= 7) records in default table
# order and matched the query client-side; a real contact anywhere past
# those first rows was invisible no matter how exact the name match was.
# Fix: build a SEARCH() pre-filter formula from the query and pass it through
# enforce_tenant_scope() the same way every other call site's filter is
# combined (AND'd with tenant/domain scope, never replacing it) -- the
# client-side casefold/whitespace-normalized exact match remains the
# authoritative disambiguator, unchanged.

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-contact-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_CONTACT_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondContactTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondContactTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import action_validator  # noqa: E402
import commercial_crm  # noqa: E402
from identity import Identity, Role  # noqa: E402

passed = failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✅ {label}")
        passed += 1
    else:
        print(f"❌ {label}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
print("── BUG 1: crm_find_or_create_contact must not be an 'unknown tool' ──")

allowed = action_validator.validate_action(
    "crm_find_or_create_contact", {"name": "אבי חזן", "phone": "0547993438"},
)
check("a fully-formed crm_find_or_create_contact call is ActionAllowed",
      isinstance(allowed, action_validator.ActionAllowed))

missing_name = action_validator.validate_action("crm_find_or_create_contact", {"phone": "0547993438"})
check("missing 'name' is a normal presence-check block, never 'unknown tool'",
      isinstance(missing_name, action_validator.ActionBlocked)
      and "אינו מוכר" not in str(missing_name))

check("crm_find_or_create_contact is registered in the presence-check allowlist",
      "crm_find_or_create_contact" in action_validator._REQUIRED)
check("crm_find_or_create_contact is flagged sensitive (matches crm_find_or_create_organization)",
      "crm_find_or_create_contact" in action_validator._SENSITIVE_TOOLS)


# ══════════════════════════════════════════════════════════════════
print("\n── BUG 2: lookup_human_reference must actually search, not just skim ──")


def _owner_identity():
    return Identity(user_id="owner-1", role=Role.OWNER, tenant_id="boss_hq")


def _fake_list_records(table, formula, *, max_records, fields, paginate):
    """Simulates a real Airtable table with 10 Contacts where the target
    ("אבי חזן") sits at position 8 -- past the first `limit + 1` (7) records
    a filterless call would have fetched. Only returns it when the caller's
    own formula actually names the contact (proving the query was sent to
    Airtable, not just relied on client-side post-filtering of an unfiltered
    page)."""
    filler = [{"id": f"recFiller{i}", "fields": {"שם": f"איש קשר {i}"}} for i in range(7)]
    target = {"id": "recAviHazan", "fields": {"שם": "אבי חזן"}}
    if "אבי חזן" in formula:
        return [target]
    return filler[:max_records]


with patch("commercial_crm.list_records", side_effect=_fake_list_records) as mock_list:
    records = commercial_crm.lookup_human_reference(
        "contact", "אבי חזן", scope="owner-1", identity=_owner_identity(), limit=6,
    )

check("a contact past the first 7 default-order rows is still found",
      len(records) == 1 and records[0]["id"] == "recAviHazan")
check("the query text was actually sent to Airtable as a filter formula",
      mock_list.call_args.args[1] and "אבי חזן" in mock_list.call_args.args[1])
check("the formula uses SEARCH() (substring, tolerant of stray whitespace) "
      "rather than a brittle exact-equality formula",
      "SEARCH(" in mock_list.call_args.args[1])


# ══════════════════════════════════════════════════════════════════
print("\n── blank query still fails closed (no formula = full-table scan risk) ──")

with patch("commercial_crm.list_records") as mock_list_blank:
    records_blank = commercial_crm.lookup_human_reference(
        "contact", "   ", scope="owner-1", identity=_owner_identity(), limit=6,
    )
check("a blank/whitespace-only query returns no results", records_blank == [])
check("a blank/whitespace-only query never calls list_records", not mock_list_blank.called)


print()
print("=" * 60)
print(f"BUG-DIAMOND-CONTACT-APPROVAL-AND-SEARCH regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
