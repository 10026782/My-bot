import logging
import os
from typing import Any

from feature_flags import is_enabled

logger = logging.getLogger(__name__)


def _fallback_enabled() -> bool:
    return is_enabled("LLM_FALLBACK")


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
    fallback_from: str | None = None,
) -> str:
    """
    fallback_from: set by call_anthropic_text() when this is an
    Anthropic-failed fallback, purely for usage_events.meta traceability —
    it does NOT cause a second/duplicate usage record. The failed Anthropic
    attempt never produced a usable response, so there is nothing real to
    record for it; this function records exactly one row for the OpenAI
    call it actually makes, whether called directly or via fallback.
    """
    from openai import OpenAI

    selected_model = model or os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4o-mini")
    logger.warning(
        "[LLM] provider=openai_fallback source=%s model=%s max_tokens=%s",
        source,
        selected_model,
        max_tokens,
    )

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

    # Build Chat Completions messages (stable API, supported in all openai package versions)
    chat_messages: list[dict[str, Any]] = []
    if system:
        chat_messages.append({"role": "system", "content": system})
    chat_messages.extend(messages)

    kwargs: dict[str, Any] = {
        "model": selected_model,
        "messages": chat_messages,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = client.chat.completions.create(**kwargs)

    try:
        from core.usage_telemetry import record_llm_usage
        usage = getattr(response, "usage", None)
        record_llm_usage(
            provider   = "openai",
            source     = source,
            model      = selected_model,
            tokens_in  = getattr(usage, "prompt_tokens", 0) if usage else 0,
            tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0,
            caller     = source,
            request_id = getattr(response, "id", None),
            meta       = {"fallback_from": fallback_from} if fallback_from else None,
        )
    except Exception as e:
        logger.error("[LLM] usage recording failed (non-fatal): %s", e)

    return (response.choices[0].message.content or "").strip()


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

        try:
            from core.usage_telemetry import record_llm_usage
            usage = getattr(response, "usage", None)
            record_llm_usage(
                provider   = "anthropic",
                source     = source,
                model      = model,
                tokens_in  = getattr(usage, "input_tokens", 0) if usage else 0,
                tokens_out = getattr(usage, "output_tokens", 0) if usage else 0,
                caller     = source,
                request_id = getattr(response, "id", None),
            )
        except Exception as e:
            logger.error("[LLM] usage recording failed (non-fatal): %s", e)

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
                fallback_from="anthropic",
            )
        raise
