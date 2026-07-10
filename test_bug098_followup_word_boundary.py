#!/usr/bin/env python3
"""
test_bug098_followup_word_boundary.py — BUG-098 hotfix regression suite.

_handle_batch_followup() used substring matching (`in`) against
_FOLLOWUP_WORDS — "ומה" matched inside "קומה" (floor), a completely
ordinary real-estate word, causing any lead-dictation message that
mentions a floor number to be swallowed as a stale "✅ כל הלידים..."
follow-up reply instead of reaching classify_ingress()/the Agent.

Fix: _FOLLOWUP_WORD_PATTERN, a \\b-bounded regex compiled once from the
same _FOLLOWUP_WORDS set — scope limited to the matching logic only, per
the Contract Chain (no change to last_lead_candidate_batch lifecycle, no
escalation-path change, no trigger broadening — those are separate
follow-up items).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

import core.lead_candidate_handler as lch  # noqa: E402

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


identity = MockIdentity()

# Real stale batch state — matches the actual production Session record
# (rec3YS5Zcr2FenX7z, BUG-098) that got falsely "consumed" by the
# "גיל חביב ... קומה שלישית" message.
_STALE_BATCH_SESSION = {
    "last_lead_candidate_batch": {
        "original_message_text": (
            "משה אבני  מעוניין ב3 חדרים 0546546345\n"
            "אורי כדורי 0768767  4 חדרים\n"
            "אלי חוטי 0768765678 דירת 5 חדרים"
        ),
        "detected_count": 2,
        "processed_count": 2,
        "per_lead": [
            {"name": "משה אבני מעוניין", "phone": "0546546345",
             "record_id": "recW8lw2SxrCH9dse", "action": "create", "ok": True},
            {"name": "אלי חוטי", "phone": "0768765678",
             "record_id": "recwFDw8UoxjnyMyP", "action": "create", "ok": True},
        ],
    },
}


def _fake_session_get(chat_id):
    return dict(_STALE_BATCH_SESSION)


# ══════════════════════════════════════════════════════════════════
# T1 — Regression: the exact production failure case
# ══════════════════════════════════════════════════════════════════
print("\n── T1: production repro — 'קומה שלישית' must NOT be swallowed ──")

_PROD_TEXT = (
    "צור ליד חדש גיל חביב מעוניין בדירת 4 חדרים קומה שלישית מאוד מאוד רציני "
    "מספר הטלפון 0545435362 כדאי מאוד לחזור אליו מהר לפני שיתחרט "
    "יש לו את ההון העצמי הנדרש"
)

with patch("session_store.lead_sessions.get", side_effect=_fake_session_get):
    reply = lch._handle_batch_followup(identity, _PROD_TEXT, "chat_t1", "telegram", "real_estate")

chk("T1: _handle_batch_followup returns None (not swallowed)", reply is None)
chk("T1: reply does not contain the stale batch names", reply is None or "משה אבני" not in reply)

# End-to-end through handle_lead_candidate() — must NOT return the stale
# "✅ כל הלידים..." string for this message, even with a live batch in session.
with patch("session_store.lead_sessions.get", side_effect=_fake_session_get), \
     patch("feature_flags.is_enabled", return_value=False):
    try:
        from core.ingress_classifier import classify_ingress
        e2e_reply = lch.handle_lead_candidate(identity, _PROD_TEXT, "chat_t1_e2e", "telegram")
    except Exception as exc:
        e2e_reply = f"__EXC__:{exc}"

chk(
    "T1 (e2e): handle_lead_candidate does not return the stale batch summary",
    not (isinstance(e2e_reply, str) and "משה אבני" in e2e_reply),
)


# ══════════════════════════════════════════════════════════════════
# T2 — Control: an already-working lead-creation message stays unaffected
# ══════════════════════════════════════════════════════════════════
print("\n── T2: control case — plain lead creation, no regression ──")

_CONTROL_TEXT = "צור ליד: ישראל כהן, טלפון 0521234567, מעוניין בדירת 3 חדרים"

with patch("session_store.lead_sessions.get", side_effect=_fake_session_get):
    reply = lch._handle_batch_followup(identity, _CONTROL_TEXT, "chat_t2", "telegram", "real_estate")

chk("T2: control lead-creation message not swallowed", reply is None)


# ══════════════════════════════════════════════════════════════════
# T3 — Similar-looking words that must NOT collide with trigger words
# ══════════════════════════════════════════════════════════════════
print("\n── T3: near-miss words (ישאר/נשאר/אישר) must not false-positive ──")

_NEAR_MISS_CASES = [
    ("צור ליד דני לוי, ישאר איתי בקשר, טלפון 0501112233", "ישאר"),
    ("צור ליד רותי כהן, נשאר בקשר, טלפון 0501112233", "נשאר"),
    ("אישר את הבקשה של הליד החדש רון מזרחי טלפון 0501112233", "אישר"),
]
for text, word in _NEAR_MISS_CASES:
    with patch("session_store.lead_sessions.get", side_effect=_fake_session_get):
        reply = lch._handle_batch_followup(identity, text, "chat_t3", "telegram", "real_estate")
    chk(f"T3: '{word}' does not false-positive as a follow-up word", reply is None)


# ══════════════════════════════════════════════════════════════════
# T4 — Real follow-up phrasing still works (fix must not break the feature)
# ══════════════════════════════════════════════════════════════════
print("\n── T4: real follow-up phrasing still recognized ──")

for text in ("ומה עם השאר?", "מה עם הנותרים", "תעדכן אותי על שאר הלידים"):
    with patch("session_store.lead_sessions.get", side_effect=_fake_session_get):
        reply = lch._handle_batch_followup(identity, text, "chat_t4", "telegram", "real_estate")
    chk(f"T4: '{text}' still recognized as follow-up", isinstance(reply, str) and "משה אבני" in reply)


# ══════════════════════════════════════════════════════════════════
# T5 — Unicode word-boundary sanity, directly on the compiled pattern
# ══════════════════════════════════════════════════════════════════
print("\n── T5: Unicode \\b boundary correctness (direct pattern check) ──")

chk("T5: 'קומה שלישית' — no match", not lch._FOLLOWUP_WORD_PATTERN.search("קומה שלישית מאוד"))
chk("T5: 'ישאר ער' — no match", not lch._FOLLOWUP_WORD_PATTERN.search("ישאר ער כל הלילה"))
chk("T5: standalone 'שאר' — matches", bool(lch._FOLLOWUP_WORD_PATTERN.search("תעדכן את שאר הפרטים")))
chk("T5: 'ומה עם השאר' — matches", bool(lch._FOLLOWUP_WORD_PATTERN.search("ומה עם השאר?")))
chk(
    "T5: word at start of string — matches",
    bool(lch._FOLLOWUP_WORD_PATTERN.search("שאר הלידים לא טופלו")),
)
chk(
    "T5: word at end of string — matches",
    bool(lch._FOLLOWUP_WORD_PATTERN.search("מה עם הנותרים")),
)


# ══════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
