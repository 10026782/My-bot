# providers/anthropic_shim.py
# F13 — AnthropicLLMProvider shim
# עוטף את הקריאה הקיימת ב-app.py ללא שינויה.

from __future__ import annotations
from typing import Any
import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class AnthropicLLMProvider:
    def generate(self, messages: list[dict[str, Any]], system: str,
                 model: str, max_tokens: int,
                 tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = dict(
            model=model, max_tokens=max_tokens,
            system=system, messages=messages,
        )
        if tools:
            kwargs["tools"] = tools

        response = _get_client().messages.create(**kwargs)

        # Cost Telemetry Reliability PR2 (shadow only): durable
        # provider/service/model-generic recording — additive, doesn't
        # feed AI_Usage_Daily or EMERGENCY_STOP_AI yet. This module has no
        # live caller today (see CLAUDE.md's F13 note), but any direct
        # provider SDK call is instrumented on principle rather than
        # relying on "it's currently unused" staying true.
        try:
            from core.usage_telemetry import record_llm_usage
            record_llm_usage(
                provider   = "anthropic",
                source     = "providers.anthropic_shim.AnthropicLLMProvider.generate",
                model      = model,
                tokens_in  = response.usage.input_tokens,
                tokens_out = response.usage.output_tokens,
                caller     = "anthropic_shim",
                request_id = getattr(response, "id", None),
            )
        except Exception:
            import logging
            logging.getLogger(__name__).error(
                "[AnthropicShim] usage recording failed (non-fatal)", exc_info=True
            )

        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        tool_calls  = [
            {"name": b.name, "input": b.input}
            for b in response.content if b.type == "tool_use"
        ]
        return {
            "content":       "\n".join(text_blocks),
            "tool_calls":    tool_calls,
            "input_tokens":  response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "stop_reason":   response.stop_reason,
        }
