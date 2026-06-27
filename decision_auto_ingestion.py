#!/usr/bin/env python3
# decision_auto_ingestion.py -- Decision Hub Stage 5 auto-ingestion router.
#
# Read/write boundary:
# - writes only to Decision Inbox
# - never creates Decision Events
# - never updates canonical Decision fields
# - never executes actions or sends messages

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from airtable_schema import (
    DecisionInboxChannel,
    DecisionInboxFields,
    DecisionInboxStatus,
    Tables,
)
from decision_matching import find_matching_decision

logger = logging.getLogger(__name__)

FEATURE_FLAGS = ("FEATURE_DECISION_HUB", "FEATURE_DECISION_AUTO_INGESTION")
STRONG_MATCH_THRESHOLD = 60

_IDEMPOTENCY_CACHE: dict[str, "IngestionResult"] = {}


@dataclass(frozen=True)
class IngestionResult:
    ok: bool
    status: str
    channel: str = ""
    inbox_id: str = ""
    suggested_decision_id: str = ""
    match_confidence: float = 0.0
    idempotency_key: str = ""
    duplicate: bool = False
    canonical_changed: bool = False
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "status": self.status,
            "channel": self.channel,
            "inbox_id": self.inbox_id,
            "suggested_decision_id": self.suggested_decision_id,
            "match_confidence": self.match_confidence,
            "idempotency_key": self.idempotency_key,
            "duplicate": self.duplicate,
            "canonical_changed": self.canonical_changed,
            "warnings": list(self.warnings),
        }


def ingest_message(source: str, raw_content: str, metadata: dict | None = None) -> IngestionResult:
    """Route automatic channel input into Decision Inbox only."""
    metadata = metadata or {}
    if not _features_enabled():
        return IngestionResult(ok=False, status="skipped:feature_flag_off")

    channel = classify_channel({**metadata, "source": source})
    if not should_route_to_decision_inbox(raw_content, {**metadata, "channel": channel}):
        return IngestionResult(ok=False, status="error:invalid_or_empty_input", channel=channel)

    idempotency_key = _idempotency_key(source, raw_content, metadata)
    if idempotency_key and idempotency_key in _IDEMPOTENCY_CACHE:
        previous = _IDEMPOTENCY_CACHE[idempotency_key]
        return IngestionResult(
            ok=previous.ok,
            status="duplicate:already_ingested",
            channel=previous.channel,
            inbox_id=previous.inbox_id,
            suggested_decision_id=previous.suggested_decision_id,
            match_confidence=previous.match_confidence,
            idempotency_key=idempotency_key,
            duplicate=True,
            warnings=list(previous.warnings),
        )

    suggestion = suggest_decision_link(raw_content, metadata)
    result = create_decision_inbox_item(
        source=source,
        raw_content=raw_content,
        metadata=metadata,
        channel=channel,
        suggestion=suggestion,
        idempotency_key=idempotency_key,
    )
    if idempotency_key and result.ok:
        _IDEMPOTENCY_CACHE[idempotency_key] = result
    return result


def classify_channel(metadata: dict) -> str:
    """Normalize source metadata into existing Decision Inbox channel values."""
    raw = str(
        metadata.get("channel")
        or metadata.get("source")
        or metadata.get("type")
        or metadata.get("content_type")
        or ""
    ).strip().lower()

    mime_type = str(metadata.get("mime_type", "")).lower()
    if "whatsapp" in raw:
        return DecisionInboxChannel.WHATSAPP
    if "email" in raw or "mail" in raw:
        return DecisionInboxChannel.EMAIL
    if "voice" in raw or "audio" in raw or mime_type.startswith("audio/"):
        return DecisionInboxChannel.VOICE
    if any(token in raw for token in ("document", "file", "attachment")):
        return DecisionInboxChannel.DOCUMENT
    if metadata.get("attachment_url") or metadata.get("document_url") or metadata.get("file_url"):
        return DecisionInboxChannel.DOCUMENT
    return DecisionInboxChannel.MANUAL


def should_route_to_decision_inbox(raw_content: str, metadata: dict | None = None) -> bool:
    """Fail closed for empty unsupported automatic input."""
    metadata = metadata or {}
    if metadata.get("auto_ingest") is False:
        return False

    has_text = bool(str(raw_content or "").strip())
    has_reference = any(
        metadata.get(key)
        for key in (
            "attachment_url",
            "attachment_reference",
            "document_url",
            "file_url",
            "raw_reference",
            "transcript",
        )
    )
    if not has_text and not has_reference:
        return False

    channel = classify_channel(metadata)
    return channel in {
        DecisionInboxChannel.WHATSAPP,
        DecisionInboxChannel.EMAIL,
        DecisionInboxChannel.DOCUMENT,
        DecisionInboxChannel.VOICE,
        DecisionInboxChannel.MANUAL,
    }


def create_decision_inbox_item(
    *,
    source: str,
    raw_content: str,
    metadata: dict | None = None,
    channel: str | None = None,
    suggestion: dict | None = None,
    idempotency_key: str = "",
) -> IngestionResult:
    """Create one pending Decision Inbox record. Does not link or execute."""
    metadata = metadata or {}
    channel = channel or classify_channel({**metadata, "source": source})
    warnings: list[str] = []

    inbox_fields: dict[str, Any] = {
        DecisionInboxFields.RAW_INPUT: raw_content or metadata.get("transcript", ""),
        DecisionInboxFields.CHANNEL: channel,
        DecisionInboxFields.RECEIVED: _now_iso(),
        DecisionInboxFields.STATUS: DecisionInboxStatus.PENDING,
        DecisionInboxFields.TENANT_ID: str(metadata.get("tenant_id", "")),
    }

    attachment = _attachment(metadata)
    if attachment:
        inbox_fields[DecisionInboxFields.ATTACHMENT] = [attachment]
    elif any(metadata.get(key) for key in ("attachment_reference", "raw_reference")):
        warnings.append("raw reference was not a URL attachment")

    suggestion = suggestion or {}
    suggested_decision_id = str(suggestion.get("decision_id", ""))
    match_confidence = float(suggestion.get("match_confidence", 0.0) or 0.0)
    if suggested_decision_id and match_confidence > STRONG_MATCH_THRESHOLD:
        inbox_fields[DecisionInboxFields.SUGGESTED_DECISION] = [suggested_decision_id]
        inbox_fields[DecisionInboxFields.MATCH_CONFIDENCE] = match_confidence

    source_tag = _source_tag(source, metadata, idempotency_key)
    record = _create_inbox_record(inbox_fields, source_tag)
    if not record or not record.get("id"):
        return IngestionResult(
            ok=False,
            status="error:inbox_create_failed",
            channel=channel,
            idempotency_key=idempotency_key,
            warnings=warnings,
        )

    return IngestionResult(
        ok=True,
        status="created:decision_inbox",
        channel=channel,
        inbox_id=record["id"],
        suggested_decision_id=suggested_decision_id if match_confidence > STRONG_MATCH_THRESHOLD else "",
        match_confidence=match_confidence if match_confidence > STRONG_MATCH_THRESHOLD else 0.0,
        idempotency_key=idempotency_key,
        warnings=warnings,
    )


def suggest_decision_link(raw_content: str, metadata: dict | None = None) -> dict:
    """Suggest a Decision link using the shared channel-independent matcher."""
    del metadata
    try:
        match, score = find_matching_decision(raw_content or "")
    except Exception as e:
        logger.warning("[DecisionAutoIngestion] suggest_decision_link failed: %s", e)
        return {"decision_id": "", "match_confidence": 0.0}

    if not match or score <= STRONG_MATCH_THRESHOLD:
        return {"decision_id": "", "match_confidence": float(score or 0.0)}
    return {"decision_id": match.get("id", ""), "match_confidence": float(score)}


def _features_enabled() -> bool:
    try:
        from feature_flags import is_enabled

        return all(is_enabled(flag) for flag in FEATURE_FLAGS)
    except Exception:
        return False


def _create_inbox_record(fields: dict, source_tag: str) -> dict | None:
    from tools.airtable_gateway import airtable_create

    return airtable_create(Tables.DECISION_INBOX, fields, source=source_tag)


def _attachment(metadata: dict) -> dict | None:
    url = (
        metadata.get("attachment_url")
        or metadata.get("document_url")
        or metadata.get("file_url")
        or metadata.get("voice_url")
        or metadata.get("raw_reference")
    )
    if not url or not str(url).startswith(("http://", "https://")):
        return None
    filename = metadata.get("filename") or metadata.get("file_name") or "attachment"
    return {"url": str(url), "filename": str(filename)}


def _idempotency_key(source: str, raw_content: str, metadata: dict) -> str:
    explicit = (
        metadata.get("idempotency_key")
        or metadata.get("message_id")
        or metadata.get("msg_id")
        or metadata.get("email_id")
        or metadata.get("document_id")
        or metadata.get("voice_id")
        or metadata.get("sid")
    )
    if explicit:
        return f"{source}:{explicit}"
    payload = {
        "source": source,
        "raw_content": raw_content,
        "sender": metadata.get("sender", ""),
        "attachment": metadata.get("attachment_url") or metadata.get("raw_reference") or "",
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _source_tag(source: str, metadata: dict, idempotency_key: str) -> str:
    parts = ["decision_auto_ingestion", source]
    if metadata.get("tenant_id"):
        parts.append(str(metadata["tenant_id"]))
    if metadata.get("sender"):
        parts.append(str(metadata["sender"]))
    if idempotency_key:
        parts.append(idempotency_key[:24])
    return ":".join(part for part in parts if part)


def _now_iso() -> str:
    try:
        return datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()
