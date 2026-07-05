# providers/meta_whatsapp_media_adapter.py
# F13 — WhatsApp Media Extraction for Meta Cloud API (BUG-071 fix)
#
# Extracts media from Meta Cloud API webhooks (image/video/audio/document).
# Meta provides media IDs, requiring a separate API call to get download URLs.
# This is async-friendly — media download can happen after webhook ACK.

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_meta_whatsapp_media(message_dict: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extract media metadata from Meta Cloud API message.

    Meta message structure:
    {
        "type": "image|video|audio|document|text",
        "image": {"id": "..."},
        "video": {"id": "..."},
        "audio": {"id": "..."},
        "document": {"id": "...", "filename": "..."},
        "id": "msg_id",
        "timestamp": "...",
        "from": "...",
        "text": {"body": "..."}  (optional caption)
    }

    Returns:
        {
            'media_type': str,          # "image", "video", "audio", "document"
            'media_id': str,            # Meta Media ID (requires API call to fetch URL)
            'message_id': str,          # Message ID for dedup
            'filename': str,            # Optional (documents only)
            'caption': str,             # Optional caption text
        }
        or None if no media present.
    """
    msg_type = message_dict.get("type", "text")
    msg_id = message_dict.get("id", "")

    # Map Meta media types to our file_type categories
    media_mapping = {
        "image": "image",
        "video": "video",
        "audio": "audio",
        "document": "document",
    }

    if msg_type not in media_mapping:
        return None

    # Extract media ID based on type
    media_id = None
    filename = None

    if msg_type == "image":
        media_id = message_dict.get("image", {}).get("id")
    elif msg_type == "video":
        media_id = message_dict.get("video", {}).get("id")
    elif msg_type == "audio":
        media_id = message_dict.get("audio", {}).get("id")
    elif msg_type == "document":
        doc = message_dict.get("document", {})
        media_id = doc.get("id")
        filename = doc.get("filename", "")

    if not media_id:
        logger.warning("[Meta WhatsApp] type=%s but no media ID found", msg_type)
        return None

    # Optional caption text
    caption = message_dict.get("text", {}).get("body", "")

    return {
        "media_type": media_mapping[msg_type],
        "media_id": media_id,
        "message_id": msg_id,
        "filename": filename,
        "caption": caption,
    }


def get_meta_media_download_url(media_id: str, access_token: str) -> str | None:
    """
    Fetch download URL from Meta Media API.

    Requires:
      - media_id: from extract_meta_whatsapp_media()
      - access_token: Meta Business Account access token (from env: META_BUSINESS_TOKEN)

    Returns:
        Download URL (https://.../media/...) or None on failure.
    """
    try:
        import requests

        url = f"https://graph.instagram.com/v19.0/{media_id}"
        params = {"fields": "media_product_type,url", "access_token": access_token}

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        media_url = data.get("url")

        if not media_url:
            logger.warning("[Meta WhatsApp] no URL in media response: %s", data)
            return None

        logger.info("[Meta WhatsApp] fetched download URL for media %s", media_id)
        return media_url

    except Exception as e:
        logger.error("[Meta WhatsApp] failed to fetch media URL: %s", e)
        return None


def infer_mime_type_from_meta_type(media_type: str, filename: str = "") -> str:
    """Map Meta media_type to MIME type."""
    if media_type == "image":
        return "image/jpeg"  # Meta normalizes to JPEG
    elif media_type == "video":
        return "video/mp4"   # Meta normalizes to MP4
    elif media_type == "audio":
        return "audio/ogg"   # Meta normalizes to OGG
    elif media_type == "document":
        # Try to infer from filename
        if filename.endswith(".pdf"):
            return "application/pdf"
        elif filename.endswith(".txt"):
            return "text/plain"
        return "application/octet-stream"
    return "application/octet-stream"
