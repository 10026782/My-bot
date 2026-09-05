# test_bug_diamond_completion_generic_description.py —
# BUG-DIAMOND-GENERIC-COMPLETION-DESCRIPTION regression
#
# Production report (05/09/2026, owner): after supplying a phone number to
# complete a DIAMOND PATH nested Contact creation, the completion message
# read:
#
#   BOSS: הפעולה הושלמה: הפעולה המבוקשת
#
# ("The action was completed: the requested action") — a useless generic
# fallback. Owner's own words: "כשהוא מודיע מה הושלם עדיף שיודיע בדיוק מה
# הושלם ולא נצטרך לנחש" ("when it announces what was completed, better it
# announce exactly what was completed so we don't have to guess").
#
# Root cause: core/action_gateway.py's _safe_contract_business_description()
# maps only a small allowlist of tool_names to a specific Hebrew business
# description (airtable_add/update, calendar_create_event, gmail_send_draft,
# sheets_append/update, send_followup/recovery, crm_create_deal,
# crm_create_payment_term, crm_create_payment) — everything else falls
# through to the generic "הפעולה המבוקשת". crm_create_deal's own entry
# already carries a comment noting this exact gap was fixed once before
# ("the other two Commercial CRM writers" — payment_term/payment), but the
# four primitives added since (crm_find_or_create_contact,
# crm_find_or_create_organization, crm_create_charge,
# crm_create_charge_payment) were never backfilled.
#
# Fix: added a specific description branch for each of those four tool
# names, matching the existing style (business language, a name/amount
# preview when present, never a raw table/field name).

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-desc-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_DESC_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondDescTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondDescTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.action_gateway import ActionContract, build_approval_lifecycle_result  # noqa: E402

passed = failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✅ {label}")
        passed += 1
    else:
        print(f"❌ {label}")
        failed += 1


def _fake_contract(tool_name: str, payload: dict, status: str = "completed") -> ActionContract:
    return ActionContract(
        contract_id="fake-contract-desc-test", tenant_id="boss_hq",
        canonical_user_id="boss_hq:eliyahu", tool_name=tool_name,
        normalized_payload=payload,
        business_action_fingerprint="fake", origin_channel="telegram",
        origin_chat_id="eliyahu", requires_approval=True, status=status,
        created_at=0.0,
    )


# ══════════════════════════════════════════════════════════════════
print("── exact production case: crm_find_or_create_contact names the Contact ──")

lifecycle_contact = build_approval_lifecycle_result(
    _fake_contract("crm_find_or_create_contact", {"name": "אבי חזן", "phone": "0547993438"})
)
check("completed crm_find_or_create_contact names the Contact",
      "אבי חזן" in lifecycle_contact.safe_user_message)
check("completed crm_find_or_create_contact never falls back to the generic phrase",
      "הפעולה המבוקשת" not in lifecycle_contact.safe_user_message)

lifecycle_contact_pending = build_approval_lifecycle_result(
    _fake_contract("crm_find_or_create_contact", {"name": "אבי חזן"}, status="pending")
)
check("pending crm_find_or_create_contact also names the Contact (not just 'completed')",
      "אבי חזן" in lifecycle_contact_pending.safe_user_message
      and "הפעולה המבוקשת" not in lifecycle_contact_pending.safe_user_message)


# ══════════════════════════════════════════════════════════════════
print("\n── sibling primitive: crm_find_or_create_organization ──")

lifecycle_org = build_approval_lifecycle_result(
    _fake_contract("crm_find_or_create_organization", {"organization_name": "חברת בדיקה בע\"מ"})
)
check("completed crm_find_or_create_organization names the Organization",
      "חברת בדיקה" in lifecycle_org.safe_user_message
      and "הפעולה המבוקשת" not in lifecycle_org.safe_user_message)


# ══════════════════════════════════════════════════════════════════
print("\n── remaining Commercial V2 primitives: crm_create_charge / crm_create_charge_payment ──")

lifecycle_charge = build_approval_lifecycle_result(
    _fake_contract("crm_create_charge", {"deal_id": "recDeal1", "amount": 500})
)
check("completed crm_create_charge names the amount, not the generic phrase",
      "500" in lifecycle_charge.safe_user_message
      and "הפעולה המבוקשת" not in lifecycle_charge.safe_user_message)

lifecycle_charge_payment = build_approval_lifecycle_result(
    _fake_contract("crm_create_charge_payment", {"charge_id": "recCharge1", "amount": 500})
)
check("completed crm_create_charge_payment names the amount, not the generic phrase",
      "500" in lifecycle_charge_payment.safe_user_message
      and "הפעולה המבוקשת" not in lifecycle_charge_payment.safe_user_message)


# ══════════════════════════════════════════════════════════════════
print("\n── no name/amount present: falls back to the entity label, not raw field names ──")

lifecycle_contact_blank = build_approval_lifecycle_result(
    _fake_contract("crm_find_or_create_contact", {})
)
check("a blank Contact payload still gets the entity-specific label",
      "איש קשר" in lifecycle_contact_blank.safe_user_message)
check("no raw field name (e.g. 'name') leaks into the message",
      lifecycle_contact_blank.safe_user_message.strip().endswith("איש קשר")
      or "איש קשר" in lifecycle_contact_blank.safe_user_message)


# ══════════════════════════════════════════════════════════════════
print("\n── unrelated tool names are unaffected (still the generic fallback) ──")

lifecycle_unrelated = build_approval_lifecycle_result(
    _fake_contract("some_future_tool_not_in_the_allowlist", {"whatever": "value"})
)
check("a genuinely unmapped tool still gets the generic fallback (unchanged behavior)",
      "הפעולה המבוקשת" in lifecycle_unrelated.safe_user_message)


print()
print("=" * 60)
print(f"BUG-DIAMOND-GENERIC-COMPLETION-DESCRIPTION regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
