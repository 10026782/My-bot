# test_approval_requeue.py — Regression tests for approval requeue / cross-channel dedup
#
# Tests:
#   1-3: ExecutedActionCache (event_bus) — already in main via PR #188, verified here
#   4-6: Cross-channel canonical fingerprint (Stage A — BUG-V1-CROSS-CHANNEL-FINGERPRINT-SPLIT)

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-requeue-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:REQUEUE_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patRequeueTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appRequeueTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from event_bus import ExecutedActionCache, PendingActionsStore

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# Tests 1-3: ExecutedActionCache (PR #188 behaviour, kept on main)
# ══════════════════════════════════════════════════
cache = ExecutedActionCache()

fp = cache.compute("chat1", "sheets_append", {"spreadsheet_name": "X", "row": "1"})
fp_same = cache.compute("chat1", "sheets_append", {"row": "1", "spreadsheet_name": "X"})
chk("Test1: compute is order-independent (json sort_keys)", fp == fp_same)

fp_other = cache.compute("chat1", "sheets_append", {"spreadsheet_name": "Y", "row": "1"})
chk("Test1: different inputs → different fingerprint", fp != fp_other)

chk("Test2: not recently executed before mark", not cache.is_recently_executed(fp))
cache.mark_executed(fp)
chk("Test2: recently executed after mark", cache.is_recently_executed(fp))
chk("Test2: different fp unaffected", not cache.is_recently_executed(fp_other))

# TTL expiry simulation
cache2 = ExecutedActionCache()
fp2 = cache2.compute("chat2", "gmail_send_draft", {"draft_id": "d1"})
cache2._cache[fp2] = time.time() - 1   # expired
chk("Test3: expired entry is not recently executed", not cache2.is_recently_executed(fp2))


# ══════════════════════════════════════════════════
# Test 4: PendingActionsStore canonical fingerprint — cross-channel dedup
# Two different chat_ids for the same canonical_user_id must collide.
# ══════════════════════════════════════════════════
store = PendingActionsStore()

store.add(
    chat_id="whatsapp:972501234567",
    action="sheets_append",
    payload={
        "tool_name":         "sheets_append",
        "tool_inputs":       {"spreadsheet_name": "Sales", "row": "VIP"},
        "origin_channel":    "whatsapp",
        "origin_chat_id":    "whatsapp:972501234567",
        "canonical_user_id": "boss_hq:user_42",
        "user_chat_id":      "whatsapp:972501234567",
        "channel":           "whatsapp",
    },
    label="הוסף שורה לשיט Sales",
)

existing = store.find_pending_by_business_fingerprint(
    canonical_user_id="boss_hq:user_42",
    tool_name="sheets_append",
    normalized_inputs={"spreadsheet_name": "Sales", "row": "VIP"},
)
chk("Test4: cross-channel duplicate detected via canonical_user_id", existing is not None)
chk("Test4: origin_channel preserved in result", existing and existing.get("origin_channel") == "whatsapp")

existing_other = store.find_pending_by_business_fingerprint(
    canonical_user_id="boss_hq:user_99",
    tool_name="sheets_append",
    normalized_inputs={"spreadsheet_name": "Sales", "row": "VIP"},
)
chk("Test4: different canonical_user_id does not collide", existing_other is None)


# ══════════════════════════════════════════════════
# Test 5: find_pending_tool_approval + has_pending_for
# ══════════════════════════════════════════════════
store2 = PendingActionsStore()
store2.add(
    chat_id="telegram:7228089151",
    action="gmail_send_draft",
    payload={
        "tool_name":         "gmail_send_draft",
        "tool_inputs":       {"to": "a@b.com"},
        "canonical_user_id": "boss_hq:owner_1",
        "origin_channel":    "telegram",
        "origin_chat_id":    "telegram:7228089151",
        "user_chat_id":      "telegram:7228089151",
        "channel":           "telegram",
    },
    label="שלח מייל ל-a@b.com",
)

chk("Test5: has_pending_for True when tool approval exists",
    store2.has_pending_for("boss_hq:owner_1"))
chk("Test5: has_pending_for False for different user",
    not store2.has_pending_for("boss_hq:nobody"))

found = store2.find_pending_tool_approval("boss_hq:owner_1")
chk("Test5: find_pending_tool_approval returns correct label",
    found is not None and "שלח מייל" in found.get("label", ""))


# ══════════════════════════════════════════════════
# Test 6: mark_equivalent_pending_completed removes matching entries
# ══════════════════════════════════════════════════
store3 = PendingActionsStore()
store3.add(
    chat_id="whatsapp:972501234567",
    action="sheets_append",
    payload={
        "tool_name":         "sheets_append",
        "tool_inputs":       {"spreadsheet_name": "Budget", "row": "99"},
        "canonical_user_id": "boss_hq:owner_1",
        "origin_channel":    "whatsapp",
        "origin_chat_id":    "whatsapp:972501234567",
        "user_chat_id":      "whatsapp:972501234567",
        "channel":           "whatsapp",
    },
    label="הוסף שורה לשיט Budget",
)
chk("Test6: pending exists before mark_equivalent_pending_completed",
    store3.has_pending_for("boss_hq:owner_1"))

store3.mark_equivalent_pending_completed(
    "boss_hq:owner_1", "sheets_append", {"spreadsheet_name": "Budget", "row": "99"}
)
chk("Test6: equivalent pending cleared after mark_equivalent_pending_completed",
    not store3.has_pending_for("boss_hq:owner_1"))


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Approval requeue tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
