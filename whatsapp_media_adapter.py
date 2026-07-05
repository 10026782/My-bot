# providers/whatsapp_media_adapter.py
# F13 — WhatsApp Media Extraction for Twilio (BUG-071 fix)
#
# Extracts media from Twilio WhatsApp webhooks, downloads bytes from
# signed URLs, and routes to unified media handler pipeline.
# Reference: providers/twilio_shim.py (metadata extraction only).

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_whatsapp_media(request_values: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extract media metadata from Twilio WhatsApp webhook.

    Returns:
        {
            'media_url': str,           # MediaUrl0
            'mime_type': str,           # MediaContentType0
            'file_id': str,             # MessageSid (for dedup)
        }
        or None if no media present.
    """
    num_media_str = request_values.get("NumMedia", "0")
    try:
        num_media = int(num_media_str)
    except (ValueError, TypeError):
        num_media = 0

    if num_media < 1:
        return None

    media_url = request_values.get("MediaUrl0")
    mime_type = request_values.get("MediaContentType0", "application/octet-stream")
    file_id = request_values.get("MessageSid", "")

    if not media_url:
        logger.warning("[WhatsApp] NumMedia=%d but no MediaUrl0 found", num_media)
        return None

    return {
        "media_url": media_url,
        "mime_type": mime_type,
        "file_id": file_id,
    }


def download_whatsapp_media(media_url: str) -> bytes | None:
    """
    Download media bytes from Twilio-signed URL.

    Twilio provides publicly-accessible signed URLs; no auth needed.
    Respects 50MB limit (same as voice notes in media_handler.py).

    Returns:
        bytes if successful, None on failure.
    """
    try:
        import requests

        MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50MB

        resp = requests.get(media_url, timeout=30)
        resp.raise_for_status()

        if len(resp.content) > MAX_SIZE_BYTES:
            logger.warning(
                "[WhatsApp] media too large: %d bytes > %d limit",
                len(resp.content), MAX_SIZE_BYTES
            )
            return None

        logger.info(
            "[WhatsApp] media downloaded: %d bytes, mime=%s",
            len(resp.content), resp.headers.get("Content-Type", "unknown")
        )
        return resp.content

    except Exception as e:
        logger.error("[WhatsApp] media download failed: %s", e)
        return None


def infer_file_type(mime_type: str) -> str:
    """Map MIME type to media_handler.handle_file_upload() file_type."""
    if mime_type.startswith("audio/"):
        return "audio"
    elif mime_type.startswith("image/"):
        return "image"
    elif mime_type.startswith("video/"):
        return "video"
    else:
        return "document"


def infer_filename(media_url: str, mime_type: str, file_id: str) -> str:
    """
    Construct filename from media URL or file_id.

    Twilio MediaUrl0 format (example):
      https://api.twilio.com/2010-04-01/Accounts/AC.../MediaUrl/ME...
    We extract the file ID from the URL path only if it's clearly a filename
    (not a domain name), otherwise construct from file_id + mime extension.
    """
    # Known media file extensions to accept from URL
    known_extensions = {".ogg", ".mp3", ".wav", ".jpg", ".jpeg", ".png", ".pdf",
                       ".txt", ".mp4", ".mov", ".webm", ".gif", ".doc", ".docx",
                       ".xls", ".xlsx", ".zip", ".rar", ".gz"}

    # Try extracting filename from URL path
    path_parts = media_url.rstrip("/").split("/")
    if path_parts:
        potential_name = path_parts[-1]
        # Only return if it has a known media file extension
        if potential_name and not potential_name.startswith("?"):
            name_lower = potential_name.lower()
            for ext in known_extensions:
                if name_lower.endswith(ext):
                    return potential_name

    # Fallback: construct from file_id and mime extension
    extension_map = {
        "audio/ogg": ".ogg",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "application/pdf": ".pdf",
        "text/plain": ".txt",
    }
    ext = extension_map.get(mime_type, ".bin")
    return f"{file_id}{ext}"
