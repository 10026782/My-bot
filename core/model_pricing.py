# core/model_pricing.py — Cost Telemetry Reliability PR2 (shadow only)
#
# ONE canonical (provider, service, model) -> price mapping, keyed by the
# exact strings this repo actually sends to each provider's API (verified
# by grep across context.py, interaction_engine.py, creative_generator.py,
# daily_collector.py, lead_qualifier.py, core/anti_hallucination.py,
# llm_fallback.py, voice_stt_adapter.py).
#
# cost_monitor.py's OWN pricing table (_PRICE, keyed "claude-haiku-4-5" —
# a string nothing in the codebase actually sends, every real call sends
# "claude-haiku-4-5-20251001") is UNCHANGED by this PR — this module does
# not replace it, and the EMERGENCY_STOP_AI trigger still uses
# cost_monitor.py's own pricing/accumulators. Fixing that mismatch is a
# separate, later PR that also cuts over the trigger to durable data;
# doing both at once is exactly the risk this multi-PR split exists to
# avoid. This module exists so NEW instrumentation (usage_events) records
# a correct cost from day one, without waiting for that later cutover.
#
# Two independent pricing shapes, because "tokens" and "audio seconds"
# aren't the same kind of quantity:
#   - service="text": priced per 1M tokens, split input/output.
#   - service="stt":  priced per minute of audio (quantity_out carries
#                      duration_seconds; quantity_in is unused/NULL).

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

# (provider, model) -> ($ per 1M input tokens, $ per 1M output tokens)
_TEXT_PRICE_TABLE: dict[tuple[str, str], tuple[float, float]] = {
    ("anthropic", "claude-haiku-4-5-20251001"): (1.00, 5.00),
    ("anthropic", "claude-sonnet-4-6"):         (3.00, 15.00),
    ("anthropic", "claude-opus-4-6"):           (5.00, 25.00),
    ("anthropic", "claude-opus-4-7"):           (5.00, 25.00),
    ("anthropic", "claude-opus-4-8"):           (5.00, 25.00),
    # OPENAI_FALLBACK_MODEL default (.env.example) — llm_fallback.call_openai_text.
    ("openai", "gpt-4o-mini"):                  (0.15, 0.60),
    ("openai", "gpt-4o"):                       (2.50, 10.00),
}

# (provider, model) -> $ per minute of audio.
# OPENAI_STT_PRICE_PER_MINUTE lets an operator correct this without a code
# change if OpenAI's published Whisper price moves — this default is a
# point-in-time figure, not guaranteed current; verify against
# https://openai.com/api/pricing before relying on the $ total.
_STT_PRICE_TABLE: dict[tuple[str, str], float] = {
    ("openai", "whisper-1"): float(os.environ.get("OPENAI_STT_PRICE_PER_MINUTE", "0.006")),
}

# Documented fail-safe for a (provider, service, model) this module doesn't
# recognize. Deliberately the most expensive known price for that service —
# never underestimate spend for a call we can't price precisely — but every
# use is logged as ERROR and counted (get_pricing_mismatch_count), unlike
# a silent dict.get(..., default) fallback.
TEXT_PRICING_FAIL_SAFE: tuple[float, float] = (5.00, 25.00)
STT_PRICING_FAIL_SAFE_PER_MINUTE: float = 0.02

_lock = threading.Lock()
_mismatch_count = 0
_unrecognized: dict[tuple[str, str, str], int] = {}


def _record_mismatch(provider: str, service: str, model: str) -> None:
    with _lock:
        global _mismatch_count
        _mismatch_count += 1
        key = (provider, service, model)
        _unrecognized[key] = _unrecognized.get(key, 0) + 1


def compute_cost(
    provider: str,
    service: str,
    model: str,
    quantity_in: float | None,
    quantity_out: float,
) -> tuple[float, bool]:
    """
    Returns (cost_usd, was_exact_match).

    service="text":  quantity_in/quantity_out are token counts.
    service="stt":    quantity_out is duration_seconds; quantity_in is ignored.

    was_exact_match=False means (provider, model) isn't in the canonical
    table for this service and the documented fail-safe price was used
    instead — the caller must treat the returned cost as a conservative
    estimate, not a measured value (usage_events.cost_is_estimate).
    """
    if service == "text":
        price = _TEXT_PRICE_TABLE.get((provider, model))
        if price is not None:
            price_in, price_out = price
            tin = quantity_in or 0.0
            return (tin * price_in + quantity_out * price_out) / 1_000_000, True

        _record_mismatch(provider, service, model)
        logger.error(
            "[ModelPricing] unrecognized text model provider=%s model=%r — not in canonical "
            "price table. Using documented fail-safe ($%.2f/$%.2f per 1M) instead of silently "
            "guessing. Add this exact (provider, model) to _TEXT_PRICE_TABLE.",
            provider, model, *TEXT_PRICING_FAIL_SAFE,
        )
        price_in, price_out = TEXT_PRICING_FAIL_SAFE
        tin = quantity_in or 0.0
        return (tin * price_in + quantity_out * price_out) / 1_000_000, False

    if service == "stt":
        price_per_min = _STT_PRICE_TABLE.get((provider, model))
        if price_per_min is not None:
            return (quantity_out / 60.0) * price_per_min, True

        _record_mismatch(provider, service, model)
        logger.error(
            "[ModelPricing] unrecognized STT model provider=%s model=%r — not in canonical "
            "price table. Using documented fail-safe ($%.3f/min) instead of silently guessing. "
            "Add this exact (provider, model) to _STT_PRICE_TABLE.",
            provider, model, STT_PRICING_FAIL_SAFE_PER_MINUTE,
        )
        return (quantity_out / 60.0) * STT_PRICING_FAIL_SAFE_PER_MINUTE, False

    # Unknown service entirely (a new call site landed without a pricing
    # model) — loud, conservative, and counted, same policy as an
    # unrecognized model.
    _record_mismatch(provider, service, model)
    logger.error(
        "[ModelPricing] unrecognized service=%r (provider=%s model=%r) — no pricing shape "
        "defined. Treating quantity_out as fail-safe-priced output tokens; add a real pricing "
        "branch in compute_cost() for this service.",
        service, provider, model,
    )
    _, price_out = TEXT_PRICING_FAIL_SAFE
    return (quantity_out * price_out) / 1_000_000, False


def get_pricing_mismatch_count() -> int:
    """Total number of compute_cost() calls that hit a fail-safe (process lifetime)."""
    with _lock:
        return _mismatch_count


def get_unrecognized() -> dict[tuple[str, str, str], int]:
    """(provider, service, model) -> number of times it hit the fail-safe (process lifetime)."""
    with _lock:
        return dict(_unrecognized)


def known_text_models() -> frozenset[tuple[str, str]]:
    return frozenset(_TEXT_PRICE_TABLE.keys())


def known_stt_models() -> frozenset[tuple[str, str]]:
    return frozenset(_STT_PRICE_TABLE.keys())
