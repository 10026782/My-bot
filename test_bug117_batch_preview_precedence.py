# test_bug117_batch_preview_precedence.py — BUG-117
#
# Same failure class as BUG-115 ("a fresh confirmation prompt hijacked by
# old, unrelated ActionContracts"), but one level up: a Tier-2 batch
# lead-preview ("📋 זיהיתי N לידים אפשריים בקבוצה... ענה כן לשמירת כולם",
# core/lead_candidate_handler.py's _handle_clean_batch / session_store.py's
# pending_lead_preview, BUG-058) has NO ActionContract at all — so BUG-115's
# bookmark (which lives on ActionContracts) never covers it. app.py's
# _CONFIRM_WORDS branch used to check "does ANY Tier-1 ActionContract exist"
# unconditionally (BUG-056 precedent) BEFORE ever considering the Tier-2
# batch preview — so a batch of 2+ leads, freshly previewed, got hijacked
# into generic disambiguation of old Tier-1 contracts the instant any were
# still live (which, per BUG-114 §2 Q6, is nearly always true, since
# pending ActionContracts never expire on their own).
#
# Production evidence: a "📋 זיהיתי 2 לידים אפשריים בקבוצה..." preview,
# followed by "כן", fell into "יש כמה פעולות הממתינות לאישור — איזו?"
# listing 9 unrelated old Tasks/Leads contracts, instead of confirming
# the batch.
#
# Fix: core.lead_candidate_handler.should_prefer_batch_preview() compares
# the Tier-2 preview's own set_at timestamp (already tracked, 1800s TTL)
# against BUG-115's Tier-1 last_prompted_contract bookmark's set_at
# (600s TTL) — whichever prompt is genuinely more recent wins. app.py's
# _CONFIRM_WORDS branch consults this BEFORE the unconditional Tier-1
# find_live_contracts() gate. Both underlying TTL/expiry mechanisms are
# untouched — this function only compares timestamps of whatever each
# existing getter already considers live.
#
# NOTE: chat_id (Tier-2's key) and canonical_user_id/identity.memory_key
# (Tier-1's key) are two DIFFERENT, pre-existing key spaces in this
# codebase (BUG-058 always keyed pending_lead_preview by chat_id; BUG-115
# always keyed last_prompted_contract by canonical_user_id) — this file
# deliberately uses two different string keys per test to mirror that,
# not a bug in the test.

from __future__ import annotations

import time

from core.lead_candidate_handler import should_prefer_batch_preview
from session_store import lead_sessions

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


CHAT_ID = "chat_bug117"
USER_ID = "boss_hq:bug117user"


def _clear():
    lead_sessions.clear_pending_lead_preview(CHAT_ID)
    lead_sessions.clear_last_prompted_contract(USER_ID)


def _set_preview(set_at_offset: float = 0.0):
    lead_sessions.set_pending_lead_preview(
        CHAT_ID,
        candidates=[{"name": "יצחק גלבר", "phone": "0527696084"},
                    {"name": "אהרון שמחה", "phone": "0548421060"}],
        raw_text="יצחק גלבר - 0527696084\nאהרון שמחה - 0548421060",
        channel="telegram", domain="general",
    )
    if set_at_offset:
        sess = lead_sessions.get(CHAT_ID)
        sess["pending_lead_preview"]["set_at"] = time.time() + set_at_offset


def _set_bookmark(set_at_offset: float = 0.0):
    lead_sessions.set_last_prompted_contract(USER_ID, "fake-contract-id-117", kind="lead_preview")
    if set_at_offset:
        sess = lead_sessions.get(USER_ID)
        sess["last_prompted_contract"]["set_at"] = time.time() + set_at_offset


# ══════════════════════════════════════════════════
# Test 1 — production reproduction: batch preview exists, no Tier-1
# bookmark at all (old contracts are live but were never bookmarked,
# exactly the reported scenario) -> prefer Tier-2.
# ══════════════════════════════════════════════════

_clear()
_set_preview()
chk("Test 1: fresh batch preview, no Tier-1 bookmark -> prefer Tier-2 (batch)",
    should_prefer_batch_preview(USER_ID, CHAT_ID) is True)

# ══════════════════════════════════════════════════
# Test 2 — regression: no batch preview at all -> never prefer Tier-2,
# regardless of Tier-1 bookmark state. Existing Tier-1-first logic in
# app.py is untouched in this case.
# ══════════════════════════════════════════════════

_clear()
chk("Test 2: no batch preview, no bookmark -> does not prefer Tier-2",
    should_prefer_batch_preview(USER_ID, CHAT_ID) is False)

_clear()
_set_bookmark()
chk("Test 2b: no batch preview, Tier-1 bookmark present -> does not prefer Tier-2",
    should_prefer_batch_preview(USER_ID, CHAT_ID) is False)

# ══════════════════════════════════════════════════
# Test 3 — both exist: Tier-2 batch preview is NEWER than the Tier-1
# bookmark -> prefer Tier-2.
# ══════════════════════════════════════════════════

_clear()
_set_bookmark(set_at_offset=-100)   # bookmarked 100s ago
_set_preview(set_at_offset=-10)     # previewed 10s ago (more recent)
chk("Test 3: batch preview newer than Tier-1 bookmark -> prefer Tier-2",
    should_prefer_batch_preview(USER_ID, CHAT_ID) is True)

# ══════════════════════════════════════════════════
# Test 4 — both exist: Tier-1 bookmark is NEWER than the Tier-2 batch
# preview -> do NOT prefer Tier-2 (existing BUG-115 Tier-1 path must win,
# e.g. user got a single-lead preview more recently than an older,
# still-unexpired batch preview from earlier in the conversation).
# ══════════════════════════════════════════════════

_clear()
_set_preview(set_at_offset=-100)    # previewed 100s ago
_set_bookmark(set_at_offset=-10)    # bookmarked 10s ago (more recent)
chk("Test 4: Tier-1 bookmark newer than batch preview -> does NOT prefer Tier-2",
    should_prefer_batch_preview(USER_ID, CHAT_ID) is False)

# ══════════════════════════════════════════════════
# Test 5 — batch preview EXPIRED (>1800s) -> get_pending_lead_preview()
# self-clears and returns None -> never prefer Tier-2, no crash.
# ══════════════════════════════════════════════════

_clear()
_set_preview(set_at_offset=-1900)
chk("Test 5: expired batch preview -> does not prefer Tier-2",
    should_prefer_batch_preview(USER_ID, CHAT_ID) is False)

# ══════════════════════════════════════════════════
# Test 6 — Tier-1 bookmark EXPIRED (>600s) but batch preview fresh ->
# get_last_prompted_contract() self-clears and returns None -> treated
# the same as "no bookmark at all" -> prefer Tier-2.
# ══════════════════════════════════════════════════

_clear()
_set_bookmark(set_at_offset=-700)
_set_preview()
chk("Test 6: expired Tier-1 bookmark + fresh batch preview -> prefer Tier-2",
    should_prefer_batch_preview(USER_ID, CHAT_ID) is True)

# ══════════════════════════════════════════════════
# Test 7 — user/chat isolation: a batch preview under a DIFFERENT chat_id
# must never be picked up for this chat_id.
# ══════════════════════════════════════════════════

_clear()
lead_sessions.clear_pending_lead_preview("chat_bug117_other")
lead_sessions.set_pending_lead_preview(
    "chat_bug117_other", candidates=[{"name": "X", "phone": "0500000000"}],
    raw_text="X - 0500000000", channel="telegram", domain="general",
)
chk("Test 7: batch preview under a different chat_id is not seen for this chat_id",
    should_prefer_batch_preview(USER_ID, CHAT_ID) is False)
lead_sessions.clear_pending_lead_preview("chat_bug117_other")

# ══════════════════════════════════════════════════
# Test 8 — end-to-end: resolve_pending_lead_preview() actually resolves
# the batch once should_prefer_batch_preview() says to prefer it,
# regardless of how many unrelated Tier-1 contracts exist (those are
# untouched — this is a pure Tier-2 resolution, no ActionGateway call).
# ══════════════════════════════════════════════════

from dataclasses import dataclass
from unittest.mock import patch
import core.lead_candidate_handler as lch


@dataclass
class _MockIdentity:
    user_id: str = "bug117user"
    role: str = "owner"
    tenant_id: str = "boss_hq"
    domain_id: str = "general"
    external_id: str = "tg_bug117user"

    @property
    def is_internal(self) -> bool:
        return True

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"


_clear()
_set_preview()
_identity8 = _MockIdentity()
assert _identity8.memory_key == USER_ID, "test setup: memory_key must match USER_ID"

with patch.object(lch, "_write_one_lead", return_value=(True, "rec00000000001", "create")):
    prefer8 = should_prefer_batch_preview(_identity8.memory_key, CHAT_ID)
    reply8 = lch.resolve_pending_lead_preview(_identity8, CHAT_ID, is_confirm=True, is_cancel=False) if prefer8 else None

chk("Test 8: should_prefer_batch_preview() said yes for the reproduction scenario",
    prefer8 is True)
chk("Test 8: resolve_pending_lead_preview() actually confirms both leads in the batch",
    reply8 is not None and "יצחק גלבר" in reply8 and "אהרון שמחה" in reply8)
chk("Test 8: preview cleared after resolution (no stale re-confirmation)",
    lead_sessions.get_pending_lead_preview(CHAT_ID) is None)

_clear()

print(f"\n{'='*50}")
print(f"BUG-117 batch-preview precedence tests: {passed} passed, {failed} failed")
import sys
sys.exit(1 if failed else 0)
