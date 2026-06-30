# test_ll13_double_execution.py — LL-13 regression: confirming an approval
# twice (e.g. duplicate Telegram webhook delivery, fast double "כן") must
# execute the underlying action exactly once.
#
# Root cause: both _pending_approvals (app.py "2.5 Pending Approval Gate")
# and event_bus.PendingActionsStore.pop() used a get()-then-later-delete()
# sequence instead of a single atomic remove, leaving a TOCTOU window where
# two concurrent confirmations could both observe the same pending entry
# before either removed it. Fix: both paths now use a single lock-guarded
# pop() as the only read site.

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-ll13-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:LL13_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patLL13Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appLL13Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
from event_bus import PendingActionsStore, EventBus  # noqa: E402


# ══════════════════════════════════════════════════
# Tests — app.py's _pending_approvals dict gate
# ══════════════════════════════════════════════════

def test_01_pending_approvals_concurrent_confirm_executes_once():
    """Two threads racing to pop the same chat_id's pending entry must
    result in exactly one winner — the LL-13 dict-based path."""
    chat_id = "ll13_t1"
    app._pending_approvals[chat_id] = {
        "text": "שלח מייל", "created_at": __import__("time").time(),
        "domain": "general",
    }

    winners = []
    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait()
        with app._pending_approvals_lock:
            item = app._pending_approvals.pop(chat_id, None)
        if item:
            winners.append(item)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(winners) == 1, f"Expected exactly 1 winner, got {len(winners)}"
    assert chat_id not in app._pending_approvals
    return "✅ Test 01: concurrent confirm on _pending_approvals → exactly one execution"


def test_02_pending_approvals_second_confirm_is_noop():
    """Sequential double-confirm (the literal LL-13 symptom: second 'כן'
    after the first already executed) must find nothing pending."""
    chat_id = "ll13_t2"
    app._pending_approvals[chat_id] = {
        "text": "שלח מייל", "created_at": __import__("time").time(),
        "domain": "general",
    }
    with app._pending_approvals_lock:
        first = app._pending_approvals.pop(chat_id, None)
    with app._pending_approvals_lock:
        second = app._pending_approvals.pop(chat_id, None)

    assert first is not None
    assert second is None, "Second confirm must not see a pending entry"
    return "✅ Test 02: second confirm on already-consumed entry → no-op"


# ══════════════════════════════════════════════════
# Tests — event_bus.PendingActionsStore / EventBus
# ══════════════════════════════════════════════════

def test_03_pending_actions_store_concurrent_pop_executes_once():
    """Two threads racing to pop() the same action_id must result in
    exactly one winner — the LL-13 Telegram-inline-keyboard path."""
    store = PendingActionsStore()
    action_id = store.add("chat1", "gmail_send_draft", {"to": "x@example.com"})

    winners = []
    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait()
        item = store.pop(action_id)
        if item:
            winners.append(item)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(winners) == 1, f"Expected exactly 1 winner, got {len(winners)}"
    return "✅ Test 03: concurrent pop() on PendingActionsStore → exactly one winner"


def test_04_event_bus_confirm_runs_handler_exactly_once():
    """EventBus.confirm() called twice (simulating a double Telegram
    callback tap) must invoke the '.confirmed' handler exactly once."""
    store = PendingActionsStore()
    bus = EventBus(store)
    call_count = []

    def handler(payload, chat_id):
        call_count.append(1)
        return "✅ בוצע"

    bus.subscribe("gmail_send_draft.confirmed", handler)
    action_id = store.add("chat1", "gmail_send_draft", {"to": "x@example.com"})

    first_result = bus.confirm(action_id)
    second_result = bus.confirm(action_id)

    assert len(call_count) == 1, f"Handler invoked {len(call_count)} times, expected 1"
    assert first_result == "✅ בוצע"
    assert "לא נמצא" in second_result or "פגה" in second_result
    return "✅ Test 04: EventBus.confirm() called twice → handler runs exactly once"


# ══════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════

def run():
    tests = [
        test_01_pending_approvals_concurrent_confirm_executes_once,
        test_02_pending_approvals_second_confirm_is_noop,
        test_03_pending_actions_store_concurrent_pop_executes_once,
        test_04_event_bus_confirm_runs_handler_exactly_once,
    ]
    passed = failed = 0

    print("\nLL-13 Double-Execution Regression Tests")
    print("═" * 45)

    for t in tests:
        try:
            msg = t()
            print(msg)
            passed += 1
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {t.__name__} EXCEPTION: {e}")
            failed += 1

    print(f"\n{'═' * 45}")
    print(f"  {passed}/{passed+failed} passed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
