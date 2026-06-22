# drive_adapter.py — F16 Media Layer: Google Drive file storage
#
# Uploads file bytes to Drive and maintains a /BOSS/<domain>/<YYYY-MM>/
# folder structure. Raw httpx REST calls, consistent with
# tools/google_tools.py's existing style — no Google SDK dependency.

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime

import httpx

from tools.google_tools import get_google_token

logger = logging.getLogger(__name__)

_DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
_DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"

# Drive supports UTF-8 filenames natively — only strip characters that break
# filesystem/URL handling downstream, not Hebrew/non-ASCII text.
_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')


@dataclass
class MediaError:
    error_code: str
    error_message: str
    retryable: bool


@dataclass
class DriveFile:
    file_id: str = ""
    web_url: str = ""
    download_url: str = ""
    name: str = ""
    size_bytes: int = 0
    error: MediaError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _safe_filename(name: str) -> str:
    cleaned = _UNSAFE_FILENAME_RE.sub("_", name).strip()
    return cleaned or "file"


def _root_folder_id() -> str:
    """BOSS root folder — falls back to Drive's literal 'root' if unset."""
    return os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip() or "root"


def get_or_create_folder(name: str, parent_id: str) -> str | None:
    """Find a child folder by name under parent_id, creating it if absent. Returns folder id."""
    token = get_google_token()
    if not token:
        logger.warning("[drive_adapter] missing Google OAuth env vars")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    safe_name = name.replace("'", "\\'")

    try:
        r = httpx.get(
            _DRIVE_FILES_URL,
            headers=headers,
            params={
                "q": (
                    f"name = '{safe_name}' and '{parent_id}' in parents "
                    "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                ),
                "fields": "files(id, name)",
            },
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning("[drive_adapter] folder lookup HTTP %d: %s", r.status_code, r.text[:200])
            return None

        files = r.json().get("files", [])
        if files:
            return files[0]["id"]

        create = httpx.post(
            _DRIVE_FILES_URL,
            headers={**headers, "Content-Type": "application/json"},
            json={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            },
            timeout=10,
        )
        if create.status_code not in (200, 201):
            logger.warning("[drive_adapter] folder create HTTP %d: %s", create.status_code, create.text[:200])
            return None
        return create.json().get("id")
    except Exception as e:
        logger.warning("[drive_adapter] get_or_create_folder error: %s", e)
        return None


def _get_upload_folder(domain: str) -> str | None:
    """Resolves /BOSS/<domain>/<YYYY-MM>/ under the configured root, creating as needed."""
    root = _root_folder_id()
    domain_folder = get_or_create_folder(domain or "general", root)
    if not domain_folder:
        return None
    month_name = datetime.now().strftime("%Y-%m")
    return get_or_create_folder(month_name, domain_folder)


def upload_file(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    domain: str = "general",
) -> DriveFile:
    """
    Uploads file_bytes to Drive under /BOSS/<domain>/<YYYY-MM>/.
    Never raises — returns DriveFile with .error set on failure.
    """
    if not file_bytes:
        return DriveFile(error=MediaError("EMPTY_FILE", "no file bytes provided", False))

    token = get_google_token()
    if not token:
        return DriveFile(
            error=MediaError("GOOGLE_AUTH_MISSING", "Google OAuth env vars missing", True)
        )

    parent_id = _get_upload_folder(domain)
    if not parent_id:
        return DriveFile(
            error=MediaError("FOLDER_RESOLVE_FAILED", "could not resolve/create Drive folder", True)
        )

    safe_name = _safe_filename(filename)
    metadata = {"name": safe_name, "parents": [parent_id]}

    boundary = "boss_drive_upload_boundary"
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--".encode("utf-8")

    try:
        r = httpx.post(
            _DRIVE_UPLOAD_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            params={"uploadType": "multipart", "fields": "id,name,webViewLink,size"},
            content=body,
            timeout=60,
        )
        if r.status_code not in (200, 201):
            logger.warning("[drive_adapter] upload HTTP %d: %s", r.status_code, r.text[:300])
            return DriveFile(
                error=MediaError("UPLOAD_FAILED", f"Drive upload HTTP {r.status_code}", True)
            )

        data = r.json()
        return DriveFile(
            file_id=data.get("id", ""),
            web_url=data.get("webViewLink", ""),
            download_url=f"https://drive.google.com/uc?id={data.get('id', '')}",
            name=data.get("name", safe_name),
            size_bytes=len(file_bytes),
        )
    except Exception as e:
        logger.warning("[drive_adapter] upload error: %s", e)
        return DriveFile(error=MediaError("UPLOAD_EXCEPTION", str(e), True))


if __name__ == "__main__":
    assert _safe_filename("שלום/עולם:test?.mp3") == "שלום_עולם_test_.mp3"
    assert _safe_filename("normal_file.pdf") == "normal_file.pdf"
    assert _safe_filename("") == "file"

    empty = upload_file(b"", "x.mp3", "audio/mpeg")
    assert not empty.ok and empty.error.error_code == "EMPTY_FILE"

    saved = os.environ.pop("GOOGLE_CLIENT_ID", None)
    no_auth = upload_file(b"fake-bytes", "x.mp3", "audio/mpeg")
    assert not no_auth.ok and no_auth.error.error_code == "GOOGLE_AUTH_MISSING"
    if saved is not None:
        os.environ["GOOGLE_CLIENT_ID"] = saved

    fd, path = tempfile.mkstemp()
    os.close(fd)
    try:
        assert os.path.exists(path)
    finally:
        os.unlink(path)
    assert not os.path.exists(path)

    print("drive_adapter.py self-test OK")
