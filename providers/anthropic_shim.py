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
