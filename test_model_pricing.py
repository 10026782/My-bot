#!/usr/bin/env python3
"""
test_model_pricing.py — Regression tests for core/model_pricing.py
(Cost Telemetry Reliability PR, Part D).

The retired cost_monitor.py pricing table keyed Haiku as
"claude-haiku-4-5" — a string nothing in the codebase actually sends
(every real call site sends "claude-haiku-4-5-20251001", see context.py,
creative_generator.py, daily_collector.py, lead_qualifier.py,
core/anti_hallucination.py) — so every Haiku call silently fell back to
the most-expensive-model (Opus) price: a 5x overcount on the model that
carries almost all traffic (context.py::_select_model runs Haiku for
every role except owner "#" research-mode messages).

Verifies:
  1. The exact model strings this repo actually sends are recognized
     (exact match, not a substring/prefix heuristic).
  2. An unrecognized model uses the documented fail-safe price AND is
     reported as not-exact-match AND is counted/logged — never silent.
  3. STT pricing (per-minute, not per-token) is a separate shape from
     text pricing and doesn't collide with it.
"""

from __future__ import annotations

import logging
import sys

from core.model_pricing import compute_cost, get_pricing_mismatch_count, get_unrecognized

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


print("\n── canonical text pricing (exact match) ────────────────")

cost, exact = compute_cost("anthropic", "text", "claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
chk("claude-haiku-4-5-20251001 (the real model string) is an exact match", exact is True)
chk("haiku cost = $1.00 in + $5.00 out per 1M = $6.00", abs(cost - 6.00) < 1e-6)

cost, exact = compute_cost("anthropic", "text", "claude-sonnet-4-6", 1_000_000, 1_000_000)
chk("claude-sonnet-4-6 is an exact match", exact is True)
chk("sonnet cost = $3.00 in + $15.00 out per 1M = $18.00", abs(cost - 18.00) < 1e-6)

print("\n── unrecognized model — loud fail-safe, not silent ────────────────")

before = get_pricing_mismatch_count()
cost_bad, exact_bad = compute_cost("anthropic", "text", "claude-haiku-4-5", 1_000_000, 1_000_000)
after = get_pricing_mismatch_count()

chk("the OLD wrong key ('claude-haiku-4-5', no date suffix) is NOT an exact match",
    exact_bad is False)
chk("unrecognized model uses the fail-safe (opus-tier, $5/$25 per 1M) price, not haiku's real price",
    abs(cost_bad - 30.0) < 1e-6 and cost_bad != 6.00)
chk("mismatch counter increments on every fail-safe use", after == before + 1)
chk("unrecognized model is tracked for later inspection",
    ("anthropic", "text", "claude-haiku-4-5") in get_unrecognized())

print("\n── STT pricing is a separate shape (per-minute, not per-token) ────────────────")

cost_stt, exact_stt = compute_cost("openai", "stt", "whisper-1", None, 60.0)
chk("whisper-1 (60s = 1 minute) is an exact match", exact_stt is True)
chk("STT cost scales with duration_seconds/60, not token counts",
    cost_stt > 0 and cost_stt < 1.0)

cost_stt_unknown, exact_stt_unknown = compute_cost("openai", "stt", "some-future-model", None, 120.0)
chk("unrecognized STT model also fails loud, not silent", exact_stt_unknown is False)

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
