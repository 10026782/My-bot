"""Focused regression coverage for PR1 single-speaker approval UX."""

import time

from core.action_gateway import (
    ActionContract,
    ActionGateway,
    ExecutionLedger,
    build_approval_lifecycle_result,
    _describe_contract_for_disambiguation,
    _describe_contract_for_reconfirmation,
)


def _contract(*, status="pending", channel="telegram", suffix="1"):
    return ActionContract(
        contract_id=f"123e4567-e89b-12d3-a456-42661417400{suffix}",
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:owner",
        tool_name="airtable_add",
        normalized_payload={
            "table": "Leads",
            "fields": {"Name": "נועה", "record_id": "recABCDEFGHIJKLMN"},
        },
        business_action_fingerprint=f"fingerprint-{suffix}",
        origin_channel=channel,
        origin_chat_id="requester-chat",
        requires_approval=True,
        status=status,
        created_at=time.time(),
    )


def _task_contract(*, status="pending", channel="telegram", suffix="1", title="להתקשר ללקוח"):
    return ActionContract(
        contract_id=f"223e4567-e89b-12d3-a456-42661417400{suffix}",
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:owner",
        tool_name="airtable_add",
        normalized_payload={
            "table": "Tasks",
            "fields": {"Task": title, "record_id": "recABCDEFGHIJKLMN"},
        },
        business_action_fingerprint=f"task-fingerprint-{suffix}",
        origin_channel=channel,
        origin_chat_id="requester-chat",
        requires_approval=True,
        status=status,
        created_at=time.time(),
    )


def test_state_to_message_mapping_and_single_owner():
    pending = build_approval_lifecycle_result(_contract())
    completed = build_approval_lifecycle_result(_contract(status="completed"))
    repeated_completed = build_approval_lifecycle_result(
        _contract(status="completed"), repeated=True,
    )
    rejected = build_approval_lifecycle_result(_contract(status="rejected"))
    repeated_rejected = build_approval_lifecycle_result(
        _contract(status="rejected"), repeated=True,
    )
    missing = build_approval_lifecycle_result(canonical_state="no_contract")
    pending_conflict = build_approval_lifecycle_result(
        _contract(), canonical_state="pending_conflict",
    )

    assert pending.safe_user_message.startswith("יש פעולה שממתינה לאישור:")
    assert completed.safe_user_message.startswith("הפעולה הושלמה:")
    assert repeated_completed.safe_user_message == "הפעולה כבר הושלמה"
    assert rejected.safe_user_message.startswith("הפעולה בוטלה:")
    assert repeated_rejected.safe_user_message == "הפעולה כבר בוטלה"
    assert missing.safe_user_message == "אין פעולה שממתינה לאישור"
    assert "לשלוח מחדש" in pending_conflict.safe_user_message
    assert "לא נשמרה" in pending_conflict.safe_user_message
    assert pending_conflict.should_remove_keyboard is False
    for result in (
        pending, pending_conflict, completed, repeated_completed,
        rejected, repeated_rejected, missing,
    ):
        assert result.reply_owner == "gateway"
        assert result.is_final is True
        assert result.final_response_required is True
        assert result.final_response_count == 1


def test_identifiers_and_tool_names_are_never_user_visible():
    contract = _contract(status="completed")
    result = build_approval_lifecycle_result(
        contract,
        safe_reason=(
            f"airtable_add {contract.contract_id} recABCDEFGHIJKLMN"
        ),
    )
    assert "airtable_add" not in result.safe_user_message
    assert contract.contract_id not in result.safe_user_message
    assert "recABCDEFGHIJKLMN" not in result.safe_user_message


def test_authorization_denial_keeps_pending_contract_actionable_for_owner():
    contract = _contract()
    result = build_approval_lifecycle_result(
        contract, canonical_state="authorization_denied",
    )
    assert result.safe_user_message == "⛔ הפעולה דורשת אישור בעלים."
    assert result.reply_owner == "gateway"
    assert result.final_response_count == 1
    assert result.should_remove_keyboard is False
    assert contract.status == "pending"
    assert contract.tool_name not in result.safe_user_message
    assert contract.contract_id not in result.safe_user_message


def test_telegram_and_whatsapp_share_the_same_semantics():
    telegram = build_approval_lifecycle_result(_contract(channel="telegram"))
    whatsapp = build_approval_lifecycle_result(_contract(channel="whatsapp"))
    assert telegram.canonical_state == whatsapp.canonical_state == "pending"
    assert telegram.safe_user_message == whatsapp.safe_user_message


def test_multiple_pending_is_read_only_and_safe():
    first = _contract(suffix="1")
    second = _contract(suffix="2")
    before = (first.status, second.status)
    result = build_approval_lifecycle_result(contracts=[first, second])
    assert result.canonical_state == "multiple_pending"
    assert (first.status, second.status) == before
    assert "airtable_add" not in result.safe_user_message
    assert first.contract_id not in result.safe_user_message
    assert second.contract_id not in result.safe_user_message


def test_repeated_text_resolution_uses_recent_terminal_contract():
    ledger = ExecutionLedger()
    gateway = ActionGateway(ledger=ledger)
    completed = _contract(status="completed")
    ledger.save(completed)
    assert gateway.route_confirmation_word("boss_hq:owner") == "הפעולה כבר הושלמה"

    rejected = _contract(status="rejected", suffix="2")
    rejected.created_at += 1
    ledger.save(rejected)
    assert gateway.route_cancellation_word("boss_hq:owner") == "הפעולה כבר בוטלה"


# ── Follow-up UX patch: ניסוח פונה-לעסק, שמות טבלה מוסתרים ─────────────────

def test_task_creation_uses_dedicated_business_wording():
    title = "להתקשר ללקוח"
    pending = build_approval_lifecycle_result(_task_contract(title=title))
    completed = build_approval_lifecycle_result(_task_contract(status="completed", title=title))
    repeated_completed = build_approval_lifecycle_result(
        _task_contract(status="completed", title=title), repeated=True,
    )
    rejected = build_approval_lifecycle_result(_task_contract(status="rejected", title=title))
    repeated_rejected = build_approval_lifecycle_result(
        _task_contract(status="rejected", title=title), repeated=True,
    )

    assert pending.safe_user_message == f"יש משימה שממתינה לאישור: {title}"
    assert completed.safe_user_message == f"המשימה נוצרה: {title}"
    assert repeated_completed.safe_user_message == "המשימה כבר נוצרה"
    assert rejected.safe_user_message == f"יצירת המשימה בוטלה: {title}"
    assert repeated_rejected.safe_user_message == "יצירת המשימה כבר בוטלה"

    for result in (pending, completed, repeated_completed, rejected, repeated_rejected):
        assert "Tasks" not in result.safe_user_message
        assert "airtable_add" not in result.safe_user_message
        assert "recABCDEFGHIJKLMN" not in result.safe_user_message


def test_task_creation_wording_same_on_telegram_and_whatsapp():
    telegram = build_approval_lifecycle_result(_task_contract(channel="telegram"))
    whatsapp = build_approval_lifecycle_result(_task_contract(channel="whatsapp"))
    assert telegram.safe_user_message == whatsapp.safe_user_message


def test_non_task_airtable_actions_never_expose_the_raw_table_name():
    # Leads (וכל טבלה אחרת) לעולם לא אמורות להופיע כמחרוזת גולמית
    # בתיאור העסקי המוצג — רק הניסוח הגנרי, שאינו תלוי-טבלה, לפי הכלל
    # "אין שמות טבלה גולמיים ב-Airtable".
    pending = build_approval_lifecycle_result(_contract())
    completed = build_approval_lifecycle_result(_contract(status="completed"))
    rejected = build_approval_lifecycle_result(_contract(status="rejected"))
    for result in (pending, completed, rejected):
        assert "Leads" not in result.safe_user_message
        assert "ActionContracts" not in result.safe_user_message


# ── סבב 2: מרנדרי אישור-מחדש / disambiguation מסתירים שמות טבלה ───────────

def test_reconfirmation_description_hides_table_names():
    title = "לסדר את המחסן"
    task_desc = _describe_contract_for_reconfirmation(_task_contract(title=title))
    assert task_desc == f"יצירת משימה: {title}"
    assert "Tasks" not in task_desc and "משימות (Tasks)" not in task_desc

    lead_desc = _describe_contract_for_reconfirmation(_contract())
    assert lead_desc.startswith("יצירת ליד")
    assert "Leads" not in lead_desc

    generic_desc = _describe_contract_for_reconfirmation(
        ActionContract(
            contract_id="323e4567-e89b-12d3-a456-426614174099",
            tenant_id="boss_hq",
            canonical_user_id="boss_hq:owner",
            tool_name="airtable_add",
            normalized_payload={"table": "ActionContracts", "fields": {"Name": "בדיקה"}},
            business_action_fingerprint="generic-fp",
            origin_channel="telegram",
            origin_chat_id="requester-chat",
            requires_approval=True,
            status="pending",
            created_at=time.time(),
        )
    )
    assert generic_desc.startswith("הוספת רשומה")
    assert "ActionContracts" not in generic_desc


def test_disambiguation_description_matches_reconfirmation_and_hides_table_names():
    title = "לסדר את המחסן"
    task_contract = _task_contract(title=title)
    lead_contract = _contract()
    for contract in (task_contract, lead_contract):
        assert _describe_contract_for_disambiguation(contract) == \
            _describe_contract_for_reconfirmation(contract)
    disambig_desc = _describe_contract_for_disambiguation(task_contract)
    assert "Tasks" not in disambig_desc and "משימות (Tasks)" not in disambig_desc


# ── סבב 3: תיקון דליפת tool_name ב-reconfirmation (Reconfirmation
# tool_name Leak Fix — RECONFIRMATION_TOOL_NAME_LEAK_FIX_SCOPE_V1.md) ──────
# _describe_contract_for_reconfirmation() נפל בעבר ל-f"{tool_name} / {table}"
# עבור כל כלי שאינו airtable_add/airtable_update — דליפת מזהה טכני גולמי,
# חיה בפרודקשן ללא תלות ב-flag, ב-describe_pending_queue(),
# describe_superseded_reason(), ו-_resolve_single_contract(). התיקון מאציל
# ל-_safe_contract_business_description() עבור כל כלי שאינו Airtable —
# ראה core/action_gateway.py.

def _non_airtable_contract(*, tool_name: str, suffix: str = "9", payload: dict | None = None):
    return ActionContract(
        contract_id=f"423e4567-e89b-12d3-a456-42661417{suffix}00",
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:owner",
        tool_name=tool_name,
        normalized_payload=payload or {},
        business_action_fingerprint=f"non-airtable-fp-{suffix}",
        origin_channel="telegram",
        origin_chat_id="requester-chat",
        requires_approval=True,
        status="pending",
        created_at=time.time(),
    )


_PREVIOUSLY_LEAKING_TOOLS = [
    "calendar_create_event", "gmail_draft", "gmail_send_draft", "sheets_append",
    "crm_mark_payment_paid", "media_save_to_memory", "send_followup",
    "send_recovery", "tma_write",
]


def test_reconfirmation_description_never_leaks_raw_tool_name_for_non_airtable_tools():
    """Reconfirmation tool_name leak fix: none of the 9 non-Airtable
    requires_approval=True tools may leak their raw tool_name — was the
    unconditional fallback before this fix, for every one of them."""
    for i, tool_name in enumerate(_PREVIOUSLY_LEAKING_TOOLS):
        contract = _non_airtable_contract(tool_name=tool_name, suffix=str(i))
        desc = _describe_contract_for_reconfirmation(contract)
        assert tool_name not in desc, f"{tool_name} leaked into {desc!r}"
        assert desc, f"{tool_name} produced an empty description"


def test_reconfirmation_description_matches_safe_business_description_for_non_airtable_tools():
    """Single source of truth: the reconfirmation description must be
    identical to _safe_contract_business_description()'s output for every
    non-Airtable tool — no duplicated/drifting mapping."""
    from core.action_gateway import _safe_contract_business_description
    for i, tool_name in enumerate(_PREVIOUSLY_LEAKING_TOOLS):
        contract = _non_airtable_contract(
            tool_name=tool_name, suffix=str(10 + i),
            payload={"summary": "פגישה", "spreadsheet_name": "Sales"},
        )
        assert _describe_contract_for_reconfirmation(contract) == \
            _safe_contract_business_description(contract)


def test_reconfirmation_lead_and_task_branches_unchanged_by_leak_fix():
    """Regression guard: the fix only touches the non-Airtable fallback —
    Lead/Task-specific (richer) descriptions are untouched."""
    title = "לסדר את המחסן"
    task_desc = _describe_contract_for_reconfirmation(_task_contract(title=title))
    assert task_desc == f"יצירת משימה: {title}"

    lead_desc = _describe_contract_for_reconfirmation(_contract())
    assert lead_desc.startswith("יצירת ליד")


def test_disambiguation_description_also_leak_free_for_non_airtable_tools():
    """describe_pending_queue()'s list rendering calls
    _describe_contract_for_disambiguation() per item — must inherit the fix."""
    contract = _non_airtable_contract(tool_name="calendar_create_event", suffix="8")
    desc = _describe_contract_for_disambiguation(contract)
    assert "calendar_create_event" not in desc
    assert desc == _describe_contract_for_reconfirmation(contract)
