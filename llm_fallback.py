import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _fallback_enabled() -> bool:
    return os.getenv("OPENAI_FALLBACK_ENABLED", "false").lower() == "true"


def _extract_text_from_anthropic(response: Any) -> str:
    blocks = getattr(response, "content", []) or []
    texts = [getattr(block, "text", "") for block in blocks if getattr(block, "type", "") == "text"]
    if texts:
        return texts[0]
    if blocks:
        return getattr(blocks[0], "text", "")
    return ""


def _messages_to_text(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def should_fallback(error: Exception) -> bool:
    status = getattr(error, "status_code", None) or getattr(error, "status", None)
    text = str(error).lower()
    cls_name = error.__class__.__name__.lower()

    if "timeout" in cls_name or "timed out" in text or "timeout" in text:
        return True

    if status in (429, 529):
        return True
    if isinstance(status, int) and status >= 500:
        return True

    if any(marker in text for marker in ("credit", "billing", "insufficient_quota", "quota exceeded")):
        return True

    return False


def call_openai_text(
    *,
    source: str,
    model: str | None = None,
    max_tokens: int = 800,
    messages: list[dict[str, Any]],
    system: str | None = None,
    temperature: float | None = None,
) -> str:
    from openai import OpenAI

    selected_model = model or os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4o-mini")
    logger.warning(
        "[LLM] provider=openai_fallback source=%s model=%s max_tokens=%s",
        source,
        selected_model,
        max_tokens,
    )

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    kwargs: dict[str, Any] = {
        "model": selected_model,
        "input": _messages_to_text(messages),
        "max_output_tokens": max_tokens,
    }
    if system:
        kwargs["instructions"] = system
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = client.responses.create(**kwargs)
    return getattr(response, "output_text", "") or ""


def call_anthropic_text(
    *,
    source: str,
    model: str,
    max_tokens: int,
    messages: list[dict[str, Any]],
    system: str | None = None,
    temperature: float = 0.2,
    timeout: int | None = None,
) -> str:
    import anthropic

    logger.info(
        "[LLM] provider=anthropic source=%s model=%s max_tokens=%s",
        source,
        model,
        max_tokens,
    )
    try:
        client_kwargs: dict[str, Any] = {"api_key": os.environ.get("ANTHROPIC_API_KEY", "")}
        if timeout is not None:
            client_kwargs["timeout"] = timeout
        client = anthropic.Anthropic(**client_kwargs)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        return _extract_text_from_anthropic(response)
    except Exception as e:
        if _fallback_enabled() and os.environ.get("OPENAI_API_KEY") and should_fallback(e):
            logger.warning(
                "[LLM] anthropic_failed source=%s fallback=true error_type=%s",
                source,
                e.__class__.__name__,
            )
            return call_openai_text(
                source=source,
                max_tokens=max_tokens,
                messages=messages,
                system=system,
                temperature=temperature,
            )
        raise
