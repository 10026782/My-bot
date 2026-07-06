# test_bug077_tier3_auto_capture_gate.py — BUG-077 fix: Tier 3 mixed-batch
# auto-write gate consistency.
#
# Bug: _handle_mixed_batch() (Tier 3, core/lead_candidate_handler.py) called
# _write_one_lead() unconditionally for every high-confidence candidate,
# regardless of FEATURE_AUTO_CAPTURE and regardless of whether the lead
# already existed. Tier 1 (_handle_single_candidate) and Tier 2
# (_handle_clean_batch) both gate on auto_capture (and Tier 1 additionally
# never auto-writes an update to an existing lead — C89 UX). Tier 3 had none
# of that, so a dictated batch with a mixed-confidence spread wrote
# high-confidence leads straight to Airtable with zero approval step, live
# in production, independent of the flag (see BUG_AUDIT_LOG.md BUG-077 and
# its 06/07/2026 addendum).
#
# Fix: a shared _should_auto_write(auto_capture, existing_id) gate, used by
# all three tiers. Tier 3 now proposes an ActionContract (like Tier 1) for
# any candidate that isn't a brand-new lead with auto_capture on.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from dataclasses import dataclass
from unittest.mock import patch

from core.action_gateway import ActionGateway, ExecutionLedger
from core.ingress_classifier import IngressClassification
import core.lead_candidate_handler as lch

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


@dataclass
class MockIdentity:
    user_id:   str = "owner_1"
    role:      str = "owner"
    tenant_id: str = "boss_hq"
    domain_id: str = "general"

    @property
    def is_internal(self) -> bool:
        return True

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"


def _ok_executor(tool_name, tool_inputs, contract_id):
    return {
        "ok": True, "tool": tool_name, "external_id": "recTIER3TESTREC001",
        "evidence": {"record_id": "recTIER3TESTREC001"},
        "user_message": "✅ רשומה נוספה | ID: recTIER3TESTREC001",
    }


def _new_gw(executor=None):
    return ActionGateway(ledger=ExecutionLedger(), tool_executor=executor)


def _tier3_ic(high_name="Dana Levi", high_phone="0501111111",
              low_name="Unclear Guy", low_phone="0502222222") -> IngressClassification:
    return IngressClassification(
        source_type="text", content_class="lead", tier=3, confidence=0.6,
        reason="test-mixed-batch",
        candidates=(
            {"name": high_name, "phone": high_phone, "confidence": 0.9, "context": []},
            {"name": low_name,  "phone": low_phone,  "confidence": 0.4, "context": []},
        ),
    )


TEXT = "דנה לוי 0501111111, מישהו לא ברור 0502222222"


def test_tier3_new_lead_auto_capture_off_no_immediate_write():
    """auto_capture=False -> high-confidence new lead must NOT be written
    immediately; it must instead become a pending ActionContract, matching
    Tier 1's preview behavior."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=False), \
         patch("tools.airtable_gateway.airtable_create") as mock_create:
        reply = lch.handle_lead_candidate(
            identity, TEXT, "chat_t3_1", "telegram", ic=_tier3_ic()
        )
    assert reply is not None
    assert mock_create.call_count == 0, \
        f"Tier 3 must not auto-write with FEATURE_AUTO_CAPTURE off, but airtable_create was called {mock_create.call_count}x"
    assert "ממתין לאישור" in reply, f"reply must show a pending-approval line: {reply!r}"
    live = gw.find_live_contracts(identity.memory_key)
    assert len(live) == 1 and live[0].tool_name == "airtable_add", \
        f"expected exactly 1 pending airtable_add contract, got {live}"
    return "OK"


def test_tier3_new_lead_auto_capture_on_writes_immediately():
    """Control: a genuinely new lead still auto-writes immediately when
    FEATURE_AUTO_CAPTURE=true — the fix must not regress the happy path."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=True), \
         patch("tools.airtable_gateway.airtable_create", return_value={"id": "recNEWLEAD00000099"}) as mock_create:
        reply = lch.handle_lead_candidate(
            identity, TEXT, "chat_t3_2", "telegram", ic=_tier3_ic()
        )
    assert reply is not None
    assert mock_create.call_count == 1, \
        f"new lead with auto_capture on must still write immediately, got {mock_create.call_count} calls"
    assert "שמרתי" in reply, f"reply must confirm the write: {reply!r}"
    live = gw.find_live_contracts(identity.memory_key)
    assert len(live) == 0, f"auto-written lead must not leave a pending contract: {live}"
    return "OK"


def test_tier3_existing_lead_requires_approval_even_with_auto_capture_on():
    """Core of BUG-077: an existing lead in a Tier 3 batch must go through
    approval even when FEATURE_AUTO_CAPTURE=true — this is exactly the gap
    that let _write_one_lead's dead requires_approval parameter bypass
    approval entirely before the fix."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value="recEXISTING0000009"), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=True), \
         patch("tools.airtable_gateway.airtable_patch") as mock_patch:
        reply = lch.handle_lead_candidate(
            identity, TEXT, "chat_t3_3", "telegram", ic=_tier3_ic()
        )
    assert reply is not None
    assert mock_patch.call_count == 0, \
        f"existing lead must never auto-update even with auto_capture on, but airtable_patch was called {mock_patch.call_count}x"
    assert "ממתין לאישור" in reply, f"reply must show a pending-approval line: {reply!r}"
    live = gw.find_live_contracts(identity.memory_key)
    assert len(live) == 1 and live[0].tool_name == "airtable_update", \
        f"expected exactly 1 pending airtable_update contract, got {live}"
    return "OK"


def test_tier3_header_counts_reflect_actual_outcome():
    """The batch summary header must not falsely claim leads were saved when
    they were only queued for approval (auto_capture off)."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=False), \
         patch("tools.airtable_gateway.airtable_create"):
        reply = lch.handle_lead_candidate(
            identity, TEXT, "chat_t3_4", "telegram", ic=_tier3_ic()
        )
    assert reply is not None
    assert "0 נשמרו" not in reply and "נשמרו" not in reply, \
        f"header must not claim anything was saved when only a pending contract was created: {reply!r}"
    assert "ממתינים לאישור" in reply, f"header must report the pending-approval count: {reply!r}"
    assert "ממתינים לבדיקה" in reply, f"header must still report the low-confidence needs_review count: {reply!r}"
    return "OK"


def test_call_site_passes_auto_capture_to_mixed_batch():
    """Static regression guard: the Tier 3 branch in handle_lead_candidate()
    must forward auto_capture into _handle_mixed_batch — this is the one-line
    wiring change that closes the gap; if it silently regresses, every other
    test above would still pass against a stale cached import in some other
    harness, so pin the source text directly."""
    src = open(os.path.join(os.path.dirname(__file__), "core", "lead_candidate_handler.py"),
                encoding="utf-8").read()
    marker = "if ic.tier == 3:"
    idx = src.index(marker)
    block = src[idx: idx + 400]
    assert "auto_capture=auto_capture" in block, \
        f"Tier 3 call site must pass auto_capture through to _handle_mixed_batch: {block!r}"
    return "OK"


TESTS = [
    test_tier3_new_lead_auto_capture_off_no_immediate_write,
    test_tier3_new_lead_auto_capture_on_writes_immediately,
    test_tier3_existing_lead_requires_approval_even_with_auto_capture_on,
    test_tier3_header_counts_reflect_actual_outcome,
    test_call_site_passes_auto_capture_to_mixed_batch,
]


def run():
    p = f = 0
    for t in TESTS:
        try:
            t()
            print(f"✅ {t.__name__}")
            p += 1
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            f += 1
        except Exception as e:
            print(f"❌ {t.__name__} EXCEPTION: {e}")
            f += 1
    print(f"\n{p}/{p + f} passed")
    return f == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
