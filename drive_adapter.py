# drive_adapter.py — F16 Media Layer: Google Drive file storage
#
# Uploads file bytes to a caller-supplied Drive folder. Raw httpx REST
# calls, consistent with tools/google_tools.py's existing style — no
# Google SDK dependency.

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
_LOGICAL_MEDIA_APP_PROPERTY = "logical_media_key"

# Drive supports UTF-8 filenames natively (Hebrew included) — only strip
# characters that are illegal in a Drive file name.
_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')

_MIME_EXT = {
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}


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


def _safe_filename(filename: str) -> str:
    """Drive API accepts UTF-8 names (Hebrew included) — only forbidden chars are cleaned."""
    return _UNSAFE_FILENAME_RE.sub("_", filename)


def _mime_to_ext(mime_type: str) -> str:
    return _MIME_EXT.get(mime_type, ".bin")


def _bytes_to_tempfile(file_bytes: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(file_bytes)
        return path
    except Exception:
        os.close(fd)
        raise


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
    """Resolves the BOSS root's <domain>/<YYYY-MM>/ folder, creating it as needed.

    GOOGLE_DRIVE_FOLDER_ID already points at the pre-created BOSS root folder
    in Drive (see .env.example) — it is the parent, not a folder to create.
    """
    root = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip() or "root"
    domain_folder = get_or_create_folder(domain or "general", root)
    if not domain_folder:
        return None
    month = datetime.now().strftime("%Y-%m")
    return get_or_create_folder(month, domain_folder)


def _upload_to_drive(
    tmp_path: str, filename: str, mime_type: str, parent_folder_id: str,
    logical_media_key: str = "",
) -> DriveFile:
    token = get_google_token()
    if not token:
        return DriveFile(error=MediaError("GOOGLE_AUTH_MISSING", "Google OAuth env vars missing", True))

    with open(tmp_path, "rb") as f:
        file_bytes = f.read()

    metadata = {"name": filename, "parents": [parent_folder_id]}
    if logical_media_key:
        metadata["appProperties"] = {_LOGICAL_MEDIA_APP_PROPERTY: logical_media_key}
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
            return DriveFile(error=MediaError("UPLOAD_FAILED", f"Drive upload HTTP {r.status_code}", True))

        data = r.json()
        return DriveFile(
            file_id=data.get("id", ""),
            web_url=data.get("webViewLink", ""),
            download_url=f"https://drive.google.com/uc?id={data.get('id', '')}",
            name=data.get("name", filename),
            size_bytes=len(file_bytes),
        )
    except Exception as e:
        logger.warning("[drive_adapter] upload error: %s", e)
        return DriveFile(error=MediaError("UPLOAD_EXCEPTION", str(e), True))


def find_existing_by_logical_media_key(logical_media_key: str, parent_folder_id: str) -> DriveFile:
    """Find and verify one Drive object tagged with the canonical media key."""
    token = get_google_token()
    if not token:
        return DriveFile(error=MediaError("GOOGLE_AUTH_MISSING", "Google OAuth env vars missing", True))
    safe_key = logical_media_key.replace("\\", "\\\\").replace("'", "\\'")
    try:
        response = httpx.get(
            _DRIVE_FILES_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "q": (
                    f"'{parent_folder_id}' in parents and trashed = false and "
                    f"appProperties has {{ key='{_LOGICAL_MEDIA_APP_PROPERTY}' "
                    f"and value='{safe_key}' }}"
                ),
                "pageSize": 10,
                "fields": "files(id,name,mimeType,size,parents,appProperties,webViewLink)",
            },
            timeout=10,
        )
        if response.status_code != 200:
            return DriveFile(error=MediaError("DRIVE_LOOKUP_FAILED", "Drive lookup failed", True))
        files = response.json().get("files", [])
        if len(files) > 1:
            return DriveFile(error=MediaError("DRIVE_DUPLICATE_KEY", "duplicate Drive media key", False))
        if not files:
            return DriveFile(error=MediaError("DRIVE_NOT_FOUND", "no Drive object found", False))
        file = files[0]
        if (
            not file.get("id")
            or file.get("appProperties", {}).get(_LOGICAL_MEDIA_APP_PROPERTY) != logical_media_key
            or parent_folder_id not in file.get("parents", [])
        ):
            return DriveFile(error=MediaError("DRIVE_VERIFICATION_FAILED", "Drive object verification failed", True))
        return DriveFile(
            file_id=file["id"], web_url=file.get("webViewLink", ""),
            download_url=f"https://drive.google.com/uc?id={file['id']}",
            name=file.get("name", ""), size_bytes=int(file.get("size") or 0),
        )
    except Exception as exc:
        logger.warning("[drive_adapter] logical media lookup failed error_type=%s", type(exc).__name__)
        return DriveFile(error=MediaError("DRIVE_LOOKUP_FAILED", "Drive lookup failed", True))


def upload_file(
    file_bytes: bytes, filename: str, mime_type: str, parent_folder_id: str,
    logical_media_key: str = "",
) -> DriveFile:
    """
    Uploads file_bytes to Drive under parent_folder_id (caller resolves the
    target folder, e.g. via _get_upload_folder/get_or_create_folder).
    Never raises — returns DriveFile with .error set on failure.
    """
    if not file_bytes:
        return DriveFile(error=MediaError("EMPTY_FILE", "no file bytes provided", False))

    safe_name = _safe_filename(filename)
    tmp_path = _bytes_to_tempfile(file_bytes, suffix=_mime_to_ext(mime_type))
    try:
        return _upload_to_drive(tmp_path, safe_name, mime_type, parent_folder_id, logical_media_key)
    finally:
        os.remove(tmp_path)


if __name__ == "__main__":
    assert _safe_filename('שלום/עולם:test?.mp3') == "שלום_עולם_test_.mp3"
    assert _safe_filename("normal_file.pdf") == "normal_file.pdf"
    print("✅ _safe_filename cleans forbidden chars only, preserves Hebrew")

    try:
        upload_file(b"data", "f.txt", "text/plain")  # type: ignore[call-arg]
        raise AssertionError("upload_file must require parent_folder_id explicitly")
    except TypeError:
        pass
    print("✅ upload_file requires explicit parent_folder_id (no default)")

    empty = upload_file(b"", "x.mp3", "audio/mpeg", "fakeParent")
    assert not empty.ok and empty.error.error_code == "EMPTY_FILE"
    print("✅ empty file bytes → EMPTY_FILE")

    import sys
    from unittest.mock import patch

    _this = sys.modules[__name__]

    with patch.object(_this, "get_google_token", return_value=None):
        no_auth_folder = get_or_create_folder("general", "root")
        assert no_auth_folder is None
        no_auth_upload = upload_file(b"fake-bytes", "x.mp3", "audio/mpeg", "fakeParent")
        assert not no_auth_upload.ok and no_auth_upload.error.error_code == "GOOGLE_AUTH_MISSING"
    print("✅ missing Google OAuth → GOOGLE_AUTH_MISSING (folder + upload)")

    _tmp_paths: list[str] = []
    _orig_mkstemp = tempfile.mkstemp

    def _spy_mkstemp(*a, **kw):
        fd, path = _orig_mkstemp(*a, **kw)
        _tmp_paths.append(path)
        return fd, path

    class _FakeResp:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)

        def json(self):
            return self._payload

    with patch.object(_this, "get_google_token", return_value="fake-token"), \
         patch("tempfile.mkstemp", side_effect=_spy_mkstemp), \
         patch("httpx.get", return_value=_FakeResp(200, {"files": []})), \
         patch("httpx.post") as mock_post:
        mock_post.side_effect = [
            _FakeResp(200, {"id": "folder123"}),
            _FakeResp(200, {"id": "file123", "name": "x.mp3", "webViewLink": "https://drive/x"}),
        ]
        folder_id = get_or_create_folder("general", "root")
        assert folder_id == "folder123"
        result = upload_file(b"audio-bytes", "x.mp3", "audio/mpeg", folder_id)
        assert result.ok and result.file_id == "file123"
    assert _tmp_paths and not os.path.exists(_tmp_paths[-1])
    print("✅ folder creation + upload succeed; temp file cleaned up after")

    _tmp_paths.clear()
    with patch.object(_this, "get_google_token", return_value="fake-token"), \
         patch("tempfile.mkstemp", side_effect=_spy_mkstemp), \
         patch("httpx.post", side_effect=RuntimeError("network down")):
        failed = upload_file(b"audio-bytes", "x.mp3", "audio/mpeg", "folder123")
        assert not failed.ok and failed.error.error_code == "UPLOAD_EXCEPTION"
    assert _tmp_paths and not os.path.exists(_tmp_paths[-1])
    print("✅ temp file removed even when upload raises (finally)")

    print("drive_adapter.py self-test OK")
