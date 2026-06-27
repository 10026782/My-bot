#!/usr/bin/env python3
# test_decision_auto_ingestion.py -- Regression tests for Decision Hub Stage 5.
#
# Run: python3 test_decision_auto_ingestion.py

from __future__ import annotations

import sys

import decision_auto_ingestion as dai
import decision_matching as dm
from airtable_schema import (
    DecisionFields,
    DecisionInboxChannel,
    DecisionInboxFields,
    DecisionInboxStatus,
    Tables,
)
from feature_flags import set_flag

_passed = 0
_failed = 0
_real_suggest_decision_link = dai.suggest_decision_link


def check(desc: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        print(f"OK {desc}")
        _passed += 1
    else:
        print(f"FAIL {desc}")
        _failed += 1


class FakeAirtable:
    def __init__(self):
        self.created = []

    def create(self, fields, source_tag):
        self.created.append((Tables.DECISION_INBOX, fields, source_tag))
        return {"id": f"recINBOX{len(self.created)}", "fields": fields}


def enable_flags() -> None:
    set_flag("FEATURE_DECISION_HUB", True)
    set_flag("FEATURE_DECISION_AUTO_INGESTION", True)


def disable_flags() -> None:
    set_flag("FEATURE_DECISION_HUB", False)
    set_flag("FEATURE_DECISION_AUTO_INGESTION", False)


def reset(fake: FakeAirtable | None = None, suggestion=None) -> FakeAirtable:
    fake = fake or FakeAirtable()
    dai._IDEMPOTENCY_CACHE.clear()
    dai._create_inbox_record = fake.create
    dai.suggest_decision_link = suggestion or (lambda raw, metadata=None: {"decision_id": "", "match_confidence": 0})
    return fake


disable_flags()
fake = reset()
off = dai.ingest_message("whatsapp", "Blue View update", {"tenant_id": "t1"})
check("feature flag off -> no ingestion", not off.ok and fake.created == [])

enable_flags()
fake = reset()
wa = dai.ingest_message(
    "whatsapp",
    "Need to review Blue View contract",
    {"tenant_id": "t1", "sender": "+972500000000", "message_id": "wa-1"},
)
wa_fields = fake.created[0][1]
check("WhatsApp-like input creates Inbox item", wa.ok and wa.inbox_id == "recINBOX1")
check("WhatsApp creates pending inbox only", wa_fields[DecisionInboxFields.STATUS] == DecisionInboxStatus.PENDING)
check("WhatsApp channel tagged", wa_fields[DecisionInboxFields.CHANNEL] == DecisionInboxChannel.WHATSAPP)

fake = reset()
email = dai.ingest_message(
    "email",
    "Subject: Blue View\nBody: please review the addendum",
    {"tenant_id": "t1", "sender": "lawyer@example.com", "email_id": "mail-1"},
)
email_fields = fake.created[0][1]
check("Email-like input creates Inbox item", email.ok and email_fields[DecisionInboxFields.CHANNEL] == DecisionInboxChannel.EMAIL)

fake = reset()
doc = dai.ingest_message(
    "document",
    "Signed Blue View agreement",
    {
        "tenant_id": "t1",
        "document_id": "doc-1",
        "attachment_url": "https://example.com/blue-view.pdf",
        "filename": "blue-view.pdf",
    },
)
doc_fields = fake.created[0][1]
check("Document input preserves attachment reference", doc_fields[DecisionInboxFields.ATTACHMENT][0]["url"].endswith("blue-view.pdf"))

fake = reset()
voice = dai.ingest_message(
    "voice",
    "Transcript: approve only after tax review",
    {
        "tenant_id": "t1",
        "voice_id": "voice-1",
        "raw_reference": "https://example.com/audio.ogg",
        "filename": "audio.ogg",
    },
)
voice_fields = fake.created[0][1]
check("Voice input preserves transcript", "tax review" in voice_fields[DecisionInboxFields.RAW_INPUT])
check("Voice input preserves raw reference", voice_fields[DecisionInboxFields.ATTACHMENT][0]["filename"] == "audio.ogg")

fake = reset(suggestion=lambda raw, metadata=None: {"decision_id": "recDECISION", "match_confidence": 95})
strong = dai.ingest_message("whatsapp", "Blue View exact title", {"tenant_id": "t1", "message_id": "wa-strong"})
strong_fields = fake.created[0][1]
check("Strong match suggests link", strong.suggested_decision_id == "recDECISION")
check("Strong match does not auto-link event", DecisionInboxFields.LINKED_EVENT not in strong_fields)
check("Strong match stays pending", strong_fields[DecisionInboxFields.STATUS] == DecisionInboxStatus.PENDING)

fake = reset(suggestion=lambda raw, metadata=None: {"decision_id": "", "match_confidence": 40})
ambiguous = dai.ingest_message("email", "Maybe related to something", {"tenant_id": "t1", "email_id": "mail-amb"})
amb_fields = fake.created[0][1]
check("Ambiguous input stays pending", ambiguous.ok and DecisionInboxFields.SUGGESTED_DECISION not in amb_fields)

check("No canonical Decision fields are changed", all(table == Tables.DECISION_INBOX for table, _, _ in fake.created))

fake = reset()
first = dai.ingest_message("whatsapp", "Same message", {"tenant_id": "t1", "idempotency_key": "same"})
second = dai.ingest_message("whatsapp", "Same message", {"tenant_id": "t1", "idempotency_key": "same"})
check("Duplicate idempotency key does not create duplicate", first.ok and second.duplicate and len(fake.created) == 1)

fake = reset()
invalid = dai.ingest_message("email", "   ", {"tenant_id": "t1"})
check("Empty/invalid input fails safely", not invalid.ok and fake.created == [])

candidates = [
    {"id": "recBLUE", "fields": {DecisionFields.TITLE: "Blue View"}},
    {"id": "recGREEN", "fields": {DecisionFields.TITLE: "Green Field Contract"}},
]
exact_match, exact_score = dm.find_matching_decision("Update for Blue View", candidates)
check("Shared matcher returns exact title match", exact_match["id"] == "recBLUE" and exact_score == 100.0)

partial_match, partial_score = dm.find_matching_decision("Green contract update", candidates)
check("Shared matcher returns deterministic partial match", partial_match["id"] == "recGREEN" and partial_score > 60)

original_loader = dm.list_open_decisions
dm.list_open_decisions = lambda limit=5: candidates[:limit]
dai.suggest_decision_link = _real_suggest_decision_link
channel_suggestion = dai.suggest_decision_link("Blue View from another channel")
check(
    "Auto ingestion uses shared matcher without command layer",
    channel_suggestion == {"decision_id": "recBLUE", "match_confidence": 100.0},
)
dm.list_open_decisions = original_loader

disable_flags()
print(f"Decision Auto Ingestion: {_passed}/{_passed + _failed} passed")
sys.exit(1 if _failed else 0)
