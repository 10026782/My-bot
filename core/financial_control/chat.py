"""FCC chat adapter — the SAME conversation as the TMA, rendered as chat text.

Start: the agent's ``fcc_update`` tool calls ``start_turn`` (it only creates/continues a draft; it
cannot write). Continue: while a draft is open, ``maybe_handle`` claims the owner's next messages
before the agent runs, so answers/"אשר"/"ערוך"/"בטל" never get re-interpreted by the model.
On confirm the FROZEN canonical writes are queued through the existing chat approval path
(ActionGateway -> airtable gateway); nothing is re-derived here.
"""

from __future__ import annotations

import logging
from typing import Callable

from core.financial_control import conversation, gate

logger = logging.getLogger(__name__)


def to_canonical_call(write: dict) -> tuple[str, dict]:
    """A frozen write -> the existing canonical generic tool (owner stamping/link guards run there)."""
    if write["op"] == "post":
        return "airtable_add", {"table": write["table"], "fields": dict(write["fields"])}
    return "airtable_update", {"table": write["table"], "record_id": write["record_id"],
                               "fields": dict(write["fields"])}


def render_text(result: conversation.TurnResult) -> str:
    lines = [result.message]
    if result.state == "needs_goal" and result.candidates:
        lines += [f"{i}. {c['title']}" for i, c in enumerate(result.candidates, 1)]
        lines.append("כתוב את שם היעד.")
    return "\n".join(lines)


def start_turn(identity, text: str) -> str:
    """Used by the ``fcc_update`` tool: first/next turn of the shared FCC conversation."""
    if not gate.enabled_for(identity):
        return "המרכז הכלכלי עדיין לא פעיל עבורך."
    result = conversation.handle_turn(identity, text)
    if result.state == "confirmed":          # a confirm word reached the tool: execution belongs to maybe_handle
        return "כדי לאשר, כתוב ״אשר״ בהודעה נפרדת."
    return render_text(result)


def maybe_handle(identity, text: str, *, queue: Callable[[str, dict], dict]) -> tuple[str | None, dict | None]:
    """Claim the message iff an FCC draft is open. Returns (reply_text, last_queue_outcome).

    ``(None, None)`` = not an FCC turn (caller continues normally). ``(text, None)`` = reply to send.
    ``(None, outcome)`` = confirmed writes were queued; the caller finalizes the single public reply
    from the queue outcome (existing single-speaker rule)."""
    if not gate.enabled_for(identity) or not conversation.has_pending(identity):
        return None, None
    result = conversation.handle_turn(identity, text)
    if result.state == "unrelated":          # not an answer/command: the draft stays open, untouched, and the
        return None, None                    # message goes to the normal flow (the owner can still ask about leads)
    if result.state != "confirmed":
        return render_text(result), None
    outcome: dict = {}
    for write in result.snapshot["writes"]:
        tool, inputs = to_canonical_call(write)
        outcome = queue(tool, inputs) or {}
        if not outcome.get("ok"):            # the CONFIRMED draft stays; "אשר" retries
            return "⚠️ לא הצלחתי להעביר את הפעולה לאישור. כתוב ״אשר״ כדי לנסות שוב.", None
    conversation.complete_execution(identity, result.entity)
    return None, outcome
