import hashlib
import json

import pytest

from core.artifact_store import ArtifactStoreError
from core.google_drive_artifact_store import GoogleDriveArtifactStore


class _Request:
    def __init__(self, value=None, error=None):
        self.value, self.error = value, error

    def execute(self):
        if self.error:
            raise self.error
        return self.value


class _Files:
    def __init__(self, existing=None, create_errors=()):
        self.existing = existing or []
        self.create_errors = list(create_errors)
        self.create_calls = 0

    def list(self, **kwargs):
        return _Request({"files": self.existing})

    def create(self, **kwargs):
        self.create_calls += 1
        error = self.create_errors.pop(0) if self.create_errors else None
        return _Request({
            "id": "drive-file-1", "name": kwargs["body"]["name"],
            "mimeType": "video/mp4", "size": "4", "parents": ["folder-1"],
            "appProperties": kwargs["body"]["appProperties"],
        }, error=error)

    def get(self, **kwargs):
        return _Request(self.create_result)


class _Service:
    def __init__(self, existing=None, create_errors=()):
        self.files_api = _Files(existing, create_errors)
        self.files_api.create_result = {
            "id": "drive-file-1", "name": "mpt_contract-provider.mp4",
            "mimeType": "video/mp4", "size": "4", "parents": ["folder-1"],
            "appProperties": {"mpt_identity": "contract:provider"},
        }

    def files(self):
        return self.files_api


def _store(tmp_path, service):
    return GoogleDriveArtifactStore(
        folder_id="folder-1", service_account_json='{}', service=service
    )


def test_upload_verify_and_result_ref(tmp_path):
    artifact = tmp_path / "final-1.mp4"
    artifact.write_bytes(b"test")
    service = _Service()
    stored = _store(tmp_path, service).put(path=artifact, identity="contract:provider", metadata={})
    assert service.files_api.create_calls == 1
    assert json.loads(stored.result_ref)["drive_file_id"] == "drive-file-1"
    assert stored.sha256 == hashlib.sha256(b"test").hexdigest()


def test_existing_identity_is_reused_without_duplicate(tmp_path):
    artifact = tmp_path / "final-1.mp4"
    artifact.write_bytes(b"test")
    existing = {
        "id": "drive-file-1", "name": "mpt_contract-provider.mp4", "mimeType": "video/mp4",
        "size": "4", "parents": ["folder-1"],
        "appProperties": {"mpt_identity": "contract:provider"},
    }
    service = _Service(existing=[existing])
    store = _store(tmp_path, service)
    assert json.loads(store.put(path=artifact, identity="contract:provider", metadata={}).result_ref)["drive_file_id"] == "drive-file-1"
    assert service.files_api.create_calls == 0


def test_transient_upload_retries_bounded(tmp_path):
    artifact = tmp_path / "final-1.mp4"
    artifact.write_bytes(b"test")
    service = _Service(create_errors=[TimeoutError(), TimeoutError()])
    assert _store(tmp_path, service).put(path=artifact, identity="contract:provider", metadata={}).file_id == "drive-file-1"
    assert service.files_api.create_calls == 3


def test_uncertain_upload_is_fail_closed_after_retry_budget(tmp_path):
    artifact = tmp_path / "final-1.mp4"
    artifact.write_bytes(b"test")
    service = _Service(create_errors=[TimeoutError(), TimeoutError(), TimeoutError()])
    with pytest.raises(ArtifactStoreError) as error:
        _store(tmp_path, service).put(path=artifact, identity="contract:provider", metadata={})
    assert error.value.uncertain
    assert error.value.code == "drive_upload_uncertain"


def test_missing_credentials_fail_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", raising=False)
    with pytest.raises(ArtifactStoreError, match="drive_configuration_missing"):
        GoogleDriveArtifactStore(folder_id="folder-1", service_account_json=None, service=None)


def test_missing_or_wrong_folder_or_invalid_artifact_fails_closed(tmp_path):
    store = _store(tmp_path, _Service())
    with pytest.raises(ArtifactStoreError, match="artifact_missing"):
        store.put(path=tmp_path / "missing.mp4", identity="contract:provider", metadata={})

    artifact = tmp_path / "final-1.mp4"
    artifact.write_bytes(b"test")
    service = _Service()
    service.files_api.create_result["parents"] = ["other-folder"]
    with pytest.raises(ArtifactStoreError, match="drive_verification_failed"):
        _store(tmp_path, service).put(path=artifact, identity="contract:provider", metadata={})
