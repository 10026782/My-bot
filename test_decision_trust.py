#!/usr/bin/env python3
# test_decision_trust.py — Regression tests for Decision Hub Stage 1 Trust Layer.
#
# Run: python3 test_decision_trust.py
# Pass condition: exit code 0, all assertions green.
#
# Covers (SPEC_Decision_Hub_Stage1_Trust_Rev2.md):
#   - compute_trust(): authority/medium combination, medium ceiling, warn penalty,
#     verify-fail-on-high-authority → T0 direct
#   - score_to_level() boundaries
#   - extract_claim_topic(): priority order (filename > event type > delta type > keyword > None)
#   - maybe_supersede(): same-topic-only, strictly-higher-trust-only
#   - gate_trust(): T0/T1/T2/T3 branches, user_flag behavior, pressure+high-exposure override
#   - run_pipeline(): user_flag propagation through a fully-passing gate chain

from __future__ import annotations

import sys

from decision_pipeline import (
    compute_trust, score_to_level, extract_claim_topic,
    maybe_supersede, _trust_rank, gate_trust, run_pipeline,
)
from decision_ports import DecisionPorts
from airtable_schema import (
    DecisionSourceReliability as SRC,
    DecisionEventChannel as CH,
    DecisionTrustLevel as TL,
)

_passed = 0
_failed = 0


def check(desc: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        print(f"✅ {desc}")
        _passed += 1
    else:
        print(f"❌ {desc}")
        _failed += 1


class FakeStorage:
    def __init__(self, records: list | None = None):
        self.records = records or []
        self.updated = []

    def add(self, table, fields, source):
        return "recNEW"

    def get(self, table, filter_formula=""):
        return self.records

    def update(self, table, record_id, fields, source):
        self.updated.append((record_id, fields))
        return True


class FakeVerifier:
    def __init__(self, status="ok"):
        self.status = status

    def verify(self, content, source):
        return {"status": self.status}


def make_ports(verifier_status="ok", storage_records=None):
    return DecisionPorts(
        storage=FakeStorage(storage_records),
        contacts=None,
        verifier=FakeVerifier(verifier_status),
        approver=None,
    )


# ═════════════════════════════════════════════════════════════════
# compute_trust / score_to_level
# ═════════════════════════════════════════════════════════════════

check("score_to_level: 80 -> T3", score_to_level(80) == TL.T3)
check("score_to_level: 79 -> T2", score_to_level(79) == TL.T2)
check("score_to_level: 55 -> T2", score_to_level(55) == TL.T2)
check("score_to_level: 30 -> T1", score_to_level(30) == TL.T1)
check("score_to_level: 0 -> T0", score_to_level(0) == TL.T0)

level, conf = compute_trust(SRC.CONTRACT, CH.DOCUMENT, "ok")
check("compute_trust: contract+document -> T3", level == TL.T3 and conf == 90)

level, conf = compute_trust(SRC.RUMOR, CH.VOICE, "ok")
check("compute_trust: rumor+voice -> low trust", level in (TL.T0, TL.T1))

level, conf = compute_trust(SRC.LAWYER, CH.TELEGRAM, "failed")
check("compute_trust: verify-failed on authority>=65 -> T0 direct, conf=10", level == TL.T0 and conf == 10)

level, conf = compute_trust(SRC.LAWYER, CH.TELEGRAM, "hallucination")
check("compute_trust: hallucination on authority>=65 -> T0 direct", level == TL.T0 and conf == 10)

level, conf = compute_trust(SRC.CLIENT, CH.MANUAL, "failed")
check("compute_trust: verify-failed but authority<65 -> NOT forced T0,10 (still goes through combined formula)",
      not (level == TL.T0 and conf == 10))

level_a, conf_a = compute_trust(SRC.PARTNER, CH.DOCUMENT, "ok")
level_b, conf_b = compute_trust(SRC.PARTNER, CH.DOCUMENT, "warn")
check("compute_trust: warn applies 0.85 penalty vs ok", conf_b < conf_a)

level, conf = compute_trust(SRC.CONTRACT, CH.VOICE, "ok")
check("compute_trust: medium ceiling caps a strong authority on a weak channel", conf <= 45 + 15)


# ═════════════════════════════════════════════════════════════════
# extract_claim_topic — priority order
# ═════════════════════════════════════════════════════════════════

topic, source, conf = extract_claim_topic({"Attachment": {"filename": "הצעת_מחיר.pdf"}})
check("extract_claim_topic: filename keyword wins (priority 1)", topic == "price" and source == "Filename")

topic, source, conf = extract_claim_topic({"Event Type": "טיוטה"})
check("extract_claim_topic: Event Type mapping (priority 2)", topic == "draft" and source == "Event Type")

topic, source, conf = extract_claim_topic({"Delta Type": "מסמך"})
check("extract_claim_topic: Delta Type heuristic (priority 3)", topic == "document" and source == "Auto")

topic, source, conf = extract_claim_topic({"Raw Content": "דיברנו על תאריך האספקה"})
check("extract_claim_topic: Raw Content keyword (priority 4)", topic in ("date", "delivery") and source == "Keyword")

topic, source, conf = extract_claim_topic({"raw_content": "שיחה כללית בלי שום מילת מפתח"})
check("extract_claim_topic: no match -> None fallback", topic is None and source is None and conf == 0)

# priority ordering: filename should win over a conflicting Event Type
topic, source, conf = extract_claim_topic({
    "Attachment": {"filename": "תנאים.pdf"},
    "Event Type": "החלטה",
})
check("extract_claim_topic: filename beats Event Type when both present", topic == "terms" and source == "Filename")


# ═════════════════════════════════════════════════════════════════
# maybe_supersede — same-topic-only, strictly-higher-trust-only
# ═════════════════════════════════════════════════════════════════

prior = {"id": "recPRIOR", "fields": {"Trust Level": TL.T1}}
new_event = {"Claim Topic": "price", "Trust Level": TL.T3, "_decision_id": "recDEC"}
ports = make_ports(storage_records=[prior])
maybe_supersede(new_event, {"some": "decision"}, ports)
check("maybe_supersede: higher trust on same topic supersedes prior", new_event.get("Supersedes") == ["recPRIOR"])
check("maybe_supersede: prior record patched to Superseded", ports.storage.updated and ports.storage.updated[0][1] == {"Status": "Superseded"})

prior2 = {"id": "recPRIOR2", "fields": {"Trust Level": TL.T3}}
new_event2 = {"Claim Topic": "price", "Trust Level": TL.T1, "_decision_id": "recDEC"}
ports2 = make_ports(storage_records=[prior2])
maybe_supersede(new_event2, {"some": "decision"}, ports2)
check("maybe_supersede: lower trust does NOT supersede", "Supersedes" not in new_event2)

new_event3 = {"Claim Topic": "price", "Trust Level": TL.T3}  # no _decision_id
ports3 = make_ports(storage_records=[prior])
maybe_supersede(new_event3, {"some": "decision"}, ports3)
check("maybe_supersede: missing _decision_id -> no-op (no KeyError)", "Supersedes" not in new_event3)

new_event4 = {"Trust Level": TL.T3, "_decision_id": "recDEC"}  # no Claim Topic
ports4 = make_ports(storage_records=[prior])
maybe_supersede(new_event4, {"some": "decision"}, ports4)
check("maybe_supersede: missing Claim Topic -> no-op", "Supersedes" not in new_event4)

check("_trust_rank: T3 > T0", _trust_rank(TL.T3) > _trust_rank(TL.T0))
check("_trust_rank: unknown level -> 0", _trust_rank("bogus") == 0)


# ═════════════════════════════════════════════════════════════════
# gate_trust — T0/T1/T2/T3 branches
# ═════════════════════════════════════════════════════════════════

event = {"raw_content": "x", "Source Reliability": SRC.LAWYER, "Channel": CH.TELEGRAM}
result = gate_trust(event, None, make_ports(verifier_status="failed"))
check("gate_trust: T0 from verify-fail on high authority -> halt Review", not result.passed and result.halt_status == "Review")
check("gate_trust: T0 verify-fail flag mentions אמין שנכשל", "נכשל" in (result.user_flag or ""))

event = {"raw_content": "x", "Source Reliability": SRC.UNKNOWN, "Channel": CH.WHATSAPP}
result = gate_trust(event, None, make_ports(verifier_status="ok"))
check("gate_trust: T1 -> halt Draft, silent (user_flag=None)",
      not result.passed and result.halt_status == "Draft" and result.user_flag is None)

event = {"raw_content": "מדברים על המחיר", "Source Reliability": SRC.PARTNER, "Channel": CH.WHATSAPP}
result = gate_trust(event, None, make_ports(verifier_status="ok"))
check("gate_trust: T2 with claim topic found -> passes, no topic_flag", result.passed and result.user_flag is None)

event = {"raw_content": "שיחה כללית בלי מילות מפתח כלל", "Source Reliability": SRC.PARTNER, "Channel": CH.WHATSAPP}
result = gate_trust(event, None, make_ports(verifier_status="ok"))
check("gate_trust: T2 with no claim topic -> passes, topic_flag present", result.passed and result.user_flag is not None)

event = {
    "raw_content": "לחץ עכשיו או לעולם לא",
    "Delta Type": "לחץ",
    "Source Reliability": SRC.PARTNER,
    "Channel": CH.WHATSAPP,
}
decision = {"Exposure Type": "כספי"}
result = gate_trust(event, decision, make_ports(verifier_status="ok"))
check("gate_trust: pressure + financial exposure -> forced T0 Review", not result.passed and result.halt_status == "Review")
check("gate_trust: pressure_high_risk tag applied", "לחץ_סיכון_גבוה" in event.get("Tags", []))


# ═════════════════════════════════════════════════════════════════
# run_pipeline — user_flag propagation fix
# ═════════════════════════════════════════════════════════════════

event = {
    "raw_content": "אושר התשלום החדש",  # FACT_MARKERS hit, no PRESSURE_MARKERS -> passes gate_delta
    "attachment": False,
    "Source Reliability": SRC.PARTNER,
    "Channel": CH.WHATSAPP,
}
outcome = run_pipeline(event, None, make_ports(verifier_status="ok"))
check("run_pipeline: fully-passing chain propagates gate_trust's user_flag",
      outcome["halted_at"] is None and outcome["result"].user_flag is not None)


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'═'*50}")
    print(f"Decision Hub Stage 1 Trust Layer: {_passed}/{_passed+_failed} passed")
    if _failed:
        print(f"FAILED: {_failed} test(s)")
    sys.exit(0 if _failed == 0 else 1)
