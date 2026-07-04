# test_c89_raw_obs.py — C89 RAW-OBS: wire raw capture and classification observation
#
# core.ingress_classifier.classify_ingress() used to leave IngressClassification.raw_ref
# permanently empty ("future — empty for now") and never recorded any observation of its
# own classification decision. This proves:
#   1. raw_ref is always non-empty, for every tier (1/4/5 explicitly required).
#   2. an AgentObservation kind="capture_classification" is recorded for every
#      classify_ingress() call, via ActionGateway's existing record_agent_observation()
#      API only (contract_id=None) — no change to ActionGateway's core.
#   3. FEATURE_RAW_CAPTURE gates the live Decision Inbox write; raw_ref stays
#      non-empty (local fallback) regardless of the flag.

import sys
from unittest.mock import patch

from core.ingress_classifier import classify_ingress
import core.action_gateway as action_gateway_mod

passed = failed = 0


def chk(desc: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}{(' — ' + extra) if extra else ''}")
        failed += 1


def _capture_observations():
    """Patches ActionGateway.record_agent_observation and returns the call list."""
    calls = []
    orig = action_gateway_mod.action_gateway.record_agent_observation

    def _spy(contract_id, kind, text):
        calls.append({"contract_id": contract_id, "kind": kind, "text": text})
        return orig(contract_id, kind, text)

    return calls, _spy


# ══════════════════════════════════════════════════
# 1. raw_ref non-empty for Tier 1 / Tier 4 / Tier 5
# ══════════════════════════════════════════════════
with patch("feature_flags.is_enabled", return_value=False):
    ic_tier1 = classify_ingress("משה כהן 0501234567 לחזור מחר")
    ic_tier4 = classify_ingress("Name, Phone, City, Status\nA, 050, X, Y\nB, 052, X, Y")
    ic_tier5 = classify_ingress("שלום מה נשמע")
    ic_empty = classify_ingress("")
    ic_other_source = classify_ingress("x", source_type="voice")

chk("Tier 1: raw_ref is non-empty", ic_tier1.tier == 1 and bool(ic_tier1.raw_ref), f"tier={ic_tier1.tier} raw_ref={ic_tier1.raw_ref!r}")
chk("Tier 4: raw_ref is non-empty", ic_tier4.tier == 4 and bool(ic_tier4.raw_ref), f"tier={ic_tier4.tier} raw_ref={ic_tier4.raw_ref!r}")
chk("Tier 5 (no candidates): raw_ref is non-empty", ic_tier5.tier == 5 and bool(ic_tier5.raw_ref), f"tier={ic_tier5.tier} raw_ref={ic_tier5.raw_ref!r}")
chk("Tier 5 (empty text): raw_ref is non-empty", ic_empty.tier == 5 and bool(ic_empty.raw_ref), f"tier={ic_empty.tier} raw_ref={ic_empty.raw_ref!r}")
chk("Tier 5 (unsupported source_type): raw_ref is non-empty", ic_other_source.tier == 5 and bool(ic_other_source.raw_ref), f"tier={ic_other_source.tier} raw_ref={ic_other_source.raw_ref!r}")

# raw_ref must differ per call (not a hardcoded constant)
chk("raw_ref values are distinct across calls", len({ic_tier1.raw_ref, ic_tier4.raw_ref, ic_tier5.raw_ref}) == 3)


# ══════════════════════════════════════════════════
# 2. capture_classification observation recorded for every call, all tiers
# ══════════════════════════════════════════════════
calls, spy = _capture_observations()
with patch("feature_flags.is_enabled", return_value=False), \
     patch.object(action_gateway_mod.action_gateway, "record_agent_observation", spy):
    classify_ingress("משה כהן 0501234567 לחזור מחר")                              # tier 1
    classify_ingress("משה כהן 0501234567\nדנה לוי 0521234567")                     # tier 2
    classify_ingress("Name, Phone, City\nA, 050, X\nB, 052, X")                    # tier 4
    classify_ingress("שלום מה נשמע")                                               # tier 5

chk("observation recorded for every classify_ingress call (4 calls -> 4 observations)", len(calls) == 4, f"got {len(calls)}")
chk("every observation has kind='capture_classification'", all(c["kind"] == "capture_classification" for c in calls))
chk("every observation has contract_id=None (no ActionContract coupling)", all(c["contract_id"] is None for c in calls))
chk(
    "observation text matches 'tier=<n> confidence=<f> reason=<r> raw_ref=<ref>' shape",
    all(
        c["text"].startswith(f"tier={t} confidence=")
        and "reason=" in c["text"] and "raw_ref=" in c["text"]
        for c, t in zip(calls, (1, 2, 4, 5))
    ),
    str([c["text"] for c in calls]),
)
chk("observed tiers cover 1, 2, 4, 5", [c["text"].split()[0] for c in calls] == ["tier=1", "tier=2", "tier=4", "tier=5"], str(calls))


# ══════════════════════════════════════════════════
# 3. FEATURE_RAW_CAPTURE gates the live Decision Inbox write only —
#    raw_ref stays non-empty either way, and classification never breaks.
# ══════════════════════════════════════════════════
with patch("feature_flags.is_enabled", return_value=False):
    ic_flag_off = classify_ingress("משה כהן 0501234567")
chk("flag OFF: raw_ref still non-empty (local fallback)", bool(ic_flag_off.raw_ref) and ic_flag_off.raw_ref.startswith("local:"), f"raw_ref={ic_flag_off.raw_ref!r}")

with patch("feature_flags.is_enabled", return_value=True), \
     patch("tools.airtable_gateway.airtable_create", return_value={"id": "recRAWOBS0000001"}):
    ic_flag_on = classify_ingress("משה כהן 0501234567")
chk("flag ON + successful write: raw_ref is the real Airtable record id", ic_flag_on.raw_ref == "recRAWOBS0000001", f"raw_ref={ic_flag_on.raw_ref!r}")

with patch("feature_flags.is_enabled", return_value=True), \
     patch("tools.airtable_gateway.airtable_create", side_effect=RuntimeError("boom")):
    ic_flag_on_fail = classify_ingress("משה כהן 0501234567")
chk(
    "flag ON + write failure: classification still succeeds with local fallback raw_ref",
    ic_flag_on_fail.tier == 1 and bool(ic_flag_on_fail.raw_ref) and ic_flag_on_fail.raw_ref.startswith("local:"),
    f"tier={ic_flag_on_fail.tier} raw_ref={ic_flag_on_fail.raw_ref!r}",
)


print(f"\n{'='*50}")
print(f"C89 RAW-OBS tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
