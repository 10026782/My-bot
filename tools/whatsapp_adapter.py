# tools/whatsapp_adapter.py — C52 Customer Output Gateway Send Adapter
#
# Honest stub (ראה C38: "לא מעמיד פנים — מחזיר stub כנה"): שום שליחת Twilio REST
# אמיתית לא קיימת עדיין מחוץ ל-TwiML reply הסינכרוני בתוך webhook הוואטסאפ.
# הפונקציה הזו קיימת כדי ש-Gateway יוכל לנתב TWILIO_WHATSAPP בלי NotImplementedError,
# ומוכנה לחיווט Twilio REST client אמיתי כשהיציאה הזו תופעל בפועל.
#
# CXX — Action Integrity: ה-adapter מחזיר ActionResult מפורש. במצב stub אין
# delivery success; ה-TwiML response של ה-webhook הוא שמבצע את התשובה בפועל.

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping

from core.action_result import ActionResult, ClaimType
from core.message_contract import InteractionType, MessageContract, format_message_contract

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WhatsAppRenderResult:
    """Pure Twilio-facing presentation data; no lifecycle state or I/O."""

    body: str
    interactive: dict[str, Any] | None = None

    @property
    def interactive_used(self) -> bool:
        return self.interactive is not None


@dataclass(frozen=True)
class WhatsAppSemanticAction:
    """Provider-free action selected from one inbound WhatsApp event."""

    action: str
    value: str | None = None
    source: str = "unknown"


_ACTION_LABELS = {
    "confirm": "✅ אשר",
    "approve": "✅ אשר",
    "edit": "✏️ ערוך",
    "cancel": "↩️ בטל",
    "reject": "↩️ בטל",
}


def _label(value: str) -> str:
    normalized = value.strip().lower()
    return _ACTION_LABELS.get(normalized, value.strip())


def _quick_replies(interaction) -> list[dict[str, str]]:
    values = interaction.options if interaction.type in {
        InteractionType.SINGLE_CHOICE, InteractionType.MULTI_CHOICE,
    } else interaction.actions
    return [
        {"id": f"wa_{index}", "title": _label(value)}
        for index, value in enumerate(values, 1)
        if value.strip()
    ]


def render_whatsapp_message(
    contract: MessageContract, *, interactive_enabled: bool = False,
) -> WhatsAppRenderResult:
    """Render one MessageContract for Twilio, falling back to complete text.

    `interactive_enabled` is an explicit adapter capability, not account or
    template discovery. This function never approves, writes, or sends.
    """
    if not isinstance(contract, MessageContract):
        raise TypeError("contract must be a MessageContract")

    body = format_message_contract(contract)
    interaction = contract.interaction
    if interaction is None:
        return WhatsAppRenderResult(body=body)

    values = interaction.options if interaction.type in {
        InteractionType.SINGLE_CHOICE, InteractionType.MULTI_CHOICE,
    } else interaction.actions
    labels = tuple(_label(value) for value in values if value.strip())
    missing = tuple(label for label in labels if label not in body)
    if missing:
        body = f"{body}\n\n" + " | ".join(missing)

    controls = _quick_replies(interaction)
    if not interactive_enabled or not controls or interaction.type is InteractionType.FREE_TEXT:
        return WhatsAppRenderResult(body=body)
    return WhatsAppRenderResult(
        body=body,
        interactive={"type": "quick_reply", "buttons": controls},
    )


_TEXT_ACTIONS = {
    "כן": "confirm", "אשר": "confirm", "מאשר": "confirm", "מאשרת": "confirm",
    "✅": "confirm", "✅ אשר": "confirm", "yes": "confirm", "ok": "confirm",
    "ערוך": "edit", "✏️ ערוך": "edit", "עריכה": "edit", "edit": "edit",
    "לא": "cancel", "בטל": "cancel", "ביטול": "cancel", "↩️ בטל": "cancel",
    "cancel": "cancel", "no": "cancel", "↩️": "cancel",
}


def _normalize_text(value: str) -> str:
    """Apply the deterministic plain-text grammar normalization."""
    return " ".join(value.split()).casefold()


def _event_value(event: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _action_from_label(value: str, interaction) -> str | None:
    normalized = _normalize_text(value)
    action = _TEXT_ACTIONS.get(normalized)
    if action:
        return action
    if interaction is None:
        return None
    values = interaction.actions
    if interaction.type in {InteractionType.SINGLE_CHOICE, InteractionType.MULTI_CHOICE}:
        return None
    for candidate in values:
        if _normalize_text(candidate) == normalized:
            return _TEXT_ACTIONS.get(normalized, normalized)
    return None


def normalize_whatsapp_action(
    event: Mapping[str, Any], *, interaction=None,
) -> WhatsAppSemanticAction:
    """Normalize Twilio/Meta reply data into an existing semantic action.

    Provider IDs are used only transiently to resolve the adapter's own
    positional ``wa_N`` controls against the supplied interaction; they are
    never returned. Unknown payloads fail closed instead of guessing.
    """
    if not isinstance(event, Mapping):
        raise TypeError("event must be a mapping")

    nested = event.get("interactive")
    nested = nested if isinstance(nested, Mapping) else {}
    reply = nested.get("button_reply") or nested.get("list_reply")
    reply = reply if isinstance(reply, Mapping) else {}
    payload = _event_value(event, "ButtonPayload", "button_payload", "reply_id") or _event_value(reply, "id")
    label = _event_value(event, "ButtonText", "button_text", "reply_title") or _event_value(reply, "title")
    body = _event_value(event, "Body", "body", "text")

    if payload.startswith("wa_") and interaction is not None:
        try:
            index = int(payload[3:]) - 1
        except ValueError:
            index = -1
        values = interaction.options if interaction.type in {
            InteractionType.SINGLE_CHOICE, InteractionType.MULTI_CHOICE,
        } else interaction.actions
        if 0 <= index < len(values):
            selected = _label(values[index])
            action = _action_from_label(selected, interaction)
            if action:
                return WhatsAppSemanticAction(action, source="payload")
            if interaction.type in {InteractionType.SINGLE_CHOICE, InteractionType.MULTI_CHOICE}:
                return WhatsAppSemanticAction("choice", selected, "payload")

    for candidate, source in ((label, "reply"), (body, "text")):
        if not candidate:
            continue
        action = _action_from_label(candidate, interaction)
        if action:
            return WhatsAppSemanticAction(action, source=source)
        if interaction is not None and interaction.type in {
            InteractionType.SINGLE_CHOICE, InteractionType.MULTI_CHOICE,
        }:
            options = tuple(_label(value) for value in interaction.options)
            normalized = _normalize_text(candidate)
            normalized_options = {_normalize_text(option): option for option in interaction.options}
            if normalized in normalized_options:
                return WhatsAppSemanticAction("choice", normalized_options[normalized], source)

    if body:
        return WhatsAppSemanticAction("text", _normalize_text(body), "text")
    return WhatsAppSemanticAction("unknown")


def _assert_gateway_context() -> None:
    """
    מונע שליחה ישירה שעוקפת את ה-Gateway.
    production: AssertionError → crash מוקדם.
    staging:    log בלבד.
    """
    import core.output_gateway as _gw
    approved = getattr(_gw._gateway_context, "approved", False)
    if not approved:
        env = os.environ.get("APP_ENV", "production")
        if env == "production":
            raise AssertionError(
                "BOSS VIOLATION: direct send bypasses Customer Output Gateway. "
                "Use core.output_gateway.send_outbound()."
            )
        else:
            logging.getLogger(__name__).error(
                "[SecondaryGuard] bypass detected — staging mode, not raising"
            )


def send_whatsapp(to: str, body: str) -> ActionResult:
    """Record an honest stub attempt without claiming that delivery occurred."""
    _assert_gateway_context()   # ← Secondary Guard
    recipient_hash = hashlib.sha256(to.encode()).hexdigest()[:12]
    logger.info("[WhatsAppAdapter] honest stub — not sent | recipient_hash=%s len=%d",
                recipient_hash, len(body))
    return ActionResult(
        tool_called=True,
        tool_http_ok=True,
        business_success=False,
        delivery_attempted=True,
        delivery_success=False,
        adapter_mode="stub",
        claim_type=ClaimType.SENT,
        source="whatsapp_adapter",
    )
