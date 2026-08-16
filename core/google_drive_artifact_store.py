"""Least-privilege Google Drive artifact store for MPT outputs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from core.artifact_store import ArtifactStoreError, StoredArtifact


_SCOPES = ("https://www.googleapis.com/auth/drive.file",)
_MAX_RETRIES = 2
_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


class GoogleDriveArtifactStore:
    def __init__(self, *, folder_id=None, service_account_json=None, service=None):
        self.folder_id = folder_id or os.environ.get("GOOGLE_DRIVE_ARTIFACT_FOLDER_ID")
        raw_credentials = service_account_json or os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
        if not self.folder_id or not raw_credentials:
            raise ArtifactStoreError("drive_configuration_missing")
        self._service = service or self._build_service(raw_credentials)

    @staticmethod
    def _build_service(raw_credentials):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            credentials = service_account.Credentials.from_service_account_info(
                json.loads(raw_credentials), scopes=list(_SCOPES)
            )
            return build("drive", "v3", credentials=credentials, cache_discovery=False)
        except Exception as exc:
            raise ArtifactStoreError("drive_auth_failed") from exc

    def put(self, *, path, identity: str, metadata: dict) -> StoredArtifact:
        path = Path(path)
        if not path.is_file() or path.is_symlink():
            raise ArtifactStoreError("artifact_missing")
        size = path.stat().st_size
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        name = f"mpt_{_SAFE_ID.sub('-', identity)}.mp4"
        app_properties = {"mpt_identity": identity, "mpt_sha256": sha256}

        existing = self._find_existing(identity)
        if existing:
            return self._verify(existing, name=name, size=size, sha256=sha256, identity=identity)

        body = {"name": name, "parents": [self.folder_id], "mimeType": "video/mp4", "appProperties": app_properties}
        try:
            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True)
            response = None
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    response = self._service.files().create(
                        body=body, media_body=media,
                        fields="id,name,mimeType,size,parents,appProperties,md5Checksum",
                        supportsAllDrives=True,
                    ).execute()
                    break
                except Exception as exc:
                    if attempt >= _MAX_RETRIES or not _transient(exc):
                        raise ArtifactStoreError("drive_upload_uncertain", uncertain=True) from exc
                    time.sleep(2 ** attempt)
            verified = self._service.files().get(
                fileId=(response or {}).get("id", ""),
                fields="id,name,mimeType,size,parents,appProperties,md5Checksum",
                supportsAllDrives=True,
            ).execute()
            return self._verify(verified, name=name, size=size, sha256=sha256, identity=identity)
        except ArtifactStoreError:
            raise
        except Exception as exc:
            raise ArtifactStoreError("drive_upload_failed") from exc

    def _find_existing(self, identity: str):
        query = (
            f"'{self.folder_id}' in parents and trashed = false and "
            f"appProperties has {{ key='mpt_identity' and value='{_quote(identity)}' }}"
        )
        try:
            result = self._service.files().list(
                q=query, spaces="drive", pageSize=10,
                fields="files(id,name,mimeType,size,parents,appProperties,md5Checksum)",
                supportsAllDrives=True,
            ).execute()
            files = result.get("files", [])
            if len(files) > 1:
                raise ArtifactStoreError("drive_duplicate_identity")
            return files[0] if files else None
        except ArtifactStoreError:
            raise
        except Exception as exc:
            raise ArtifactStoreError("drive_lookup_failed", uncertain=True) from exc

    def _verify(self, file, *, name, size, sha256, identity):
        if (
            not file.get("id") or file.get("name") != name or file.get("mimeType") != "video/mp4"
            or str(file.get("size", "")) != str(size) or self.folder_id not in file.get("parents", [])
            or file.get("appProperties", {}).get("mpt_identity") != identity
        ):
            raise ArtifactStoreError("drive_verification_failed", uncertain=True)
        return StoredArtifact(
            result_ref=json.dumps({
                "provider": "google_drive", "drive_file_id": file["id"],
                "folder_id": self.folder_id, "sha256": sha256,
                "size": size, "mime_type": "video/mp4",
            }, separators=(",", ":")),
            file_id=file["id"], size=size, sha256=sha256,
        )

    def cleanup(self, *, identity: str) -> None:
        # The local job directory is owned by the adapter; Drive artifacts are retained.
        return None


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _transient(exc: Exception) -> bool:
    status = getattr(getattr(exc, "resp", None), "status", None)
    return status in {408, 429, 500, 502, 503, 504} or isinstance(exc, (TimeoutError, OSError))
