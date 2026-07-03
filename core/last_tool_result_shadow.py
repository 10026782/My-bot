# core/last_tool_result_shadow.py — F52 Safe Refactor #4
#
# Passive "Last Tool Result" recorder — Shadow Mode.
#
# Records that *some* write happened (id, source, tool/action, timestamp)
# strictly *after* the real write already completed, purely as an
# observation. It never changes a return value, never raises into the
# caller's control flow, and never participates in any success/failure
# decision — see docs/f52/F52_CONTRACT_COVERAGE_MAP.md §11.
#
# RAM-only for Phase 1 (bounded dict + short TTL) — not Airtable, not
# durable. Durable evidence storage is the open question in §11, out of
# scope here.
#
# Flag: FEATURE_LAST_TOOL_RESULT_SHADOW (default off). Callers should still
# guard with feature_flags.is_enabled(...) before calling record(), but
# record() itself is a no-op safety net even if called unconditionally —
# it never raises.

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

Source = Literal["agent_tool", "approval", "tma_route", "media", "scheduler", "worker", "command"]

_MAX_ENTRIES = 200
_TTL_SECONDS = 15 * 60  # 15 minutes


@dataclass(frozen=True)
class LastToolResultShadow:
    id: str
    source: Source
    tool_or_action: str
    timestamp: float = field(default_factory=time.time)


_STORE: dict[str, LastToolResultShadow] = {}


def _evict_expired() -> None:
    now = time.time()
    expired = [k for k, v in _STORE.items() if now - v.timestamp > _TTL_SECONDS]
    for k in expired:
        _STORE.pop(k, None)


def record(*, source: Source, tool_or_action: str) -> str | None:
    """Passively records a shadow entry. Never raises — any failure here
    must never affect the caller's own control flow or return value."""
    try:
        _evict_expired()
        while len(_STORE) >= _MAX_ENTRIES:
            oldest_id = min(_STORE, key=lambda k: _STORE[k].timestamp)
            _STORE.pop(oldest_id, None)
        entry_id = uuid.uuid4().hex
        _STORE[entry_id] = LastToolResultShadow(
            id=entry_id, source=source, tool_or_action=tool_or_action,
        )
        return entry_id
    except Exception as e:
        logger.debug(f"[LastToolResultShadow] record failed (non-fatal): {e}")
        return None


def recent(limit: int = 20) -> list[LastToolResultShadow]:
    """Read-only accessor for diagnostics — most recent first."""
    _evict_expired()
    return sorted(_STORE.values(), key=lambda v: v.timestamp, reverse=True)[:limit]


def clear() -> None:
    """Test helper — wipes the in-RAM store."""
    _STORE.clear()


def _self_test() -> None:
    clear()
    assert recent() == []

    eid = record(source="agent_tool", tool_or_action="airtable_add")
    assert eid is not None
    assert len(recent()) == 1
    assert recent()[0].source == "agent_tool"
    assert recent()[0].tool_or_action == "airtable_add"

    for i in range(_MAX_ENTRIES + 10):
        record(source="tma_route", tool_or_action=f"patch_{i}")
    assert len(_STORE) <= _MAX_ENTRIES

    clear()
    print("✅ last_tool_result_shadow self-test: 6/6 assertions passed")


if __name__ == "__main__":
    _self_test()
