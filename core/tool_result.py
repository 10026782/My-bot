"""Provider-neutral structured tool result shape."""

from __future__ import annotations

from typing import Any


def tool_result(*, ok: bool, tool: str, external_id: str = "",
                evidence: dict[str, Any] | None = None, user_message: str = "") -> dict:
    """Return the shared C53-A result contract without importing a provider tool."""
    return {
        "ok": ok,
        "tool": tool,
        "external_id": external_id or "",
        "evidence": evidence or {},
        "user_message": user_message,
    }
