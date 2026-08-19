"""Local-filesystem ArtifactStore — same put()/cleanup() contract as
core/google_drive_artifact_store.py, for capabilities that don't need (or
aren't approved for) Google Drive/OAuth artifact custody.

Fails closed if no root is configured; every write is atomic (temp file +
os.replace) and confined under root/<subdir>/ by a resolved-path check —
identity is sanitized into the filename, never used as a raw path segment.

The filename is <sanitized-identity>-<sha256(identity)><suffix>: the
sanitized identity stays as a human-readable prefix, but the actual
uniqueness guarantee comes from the SHA-256 digest of the *original*
(pre-sanitization) identity, so two different identities that happen to
sanitize to the same string (e.g. "job/1" and "job:1", both "-" for the
separator) can never collide on disk.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from core.artifact_store import ArtifactStoreError, StoredArtifact

_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


class LocalArtifactStore:
    def __init__(self, *, root, subdir: str, suffix: str):
        if not root:
            raise ArtifactStoreError("artifact_storage_unconfigured")
        self.root = (Path(root).resolve() / subdir)
        self.suffix = suffix

    def _target(self, identity: str) -> Path:
        safe_id = _SAFE_ID.sub("-", identity) or "artifact"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        target = (self.root / f"{safe_id}-{digest}{self.suffix}").resolve()
        if not _within(target, self.root):
            raise ArtifactStoreError("artifact_path_escape")
        return target

    def put(self, *, path, identity: str, metadata: dict) -> StoredArtifact:
        path = Path(path)
        if not path.is_file() or path.is_symlink():
            raise ArtifactStoreError("artifact_missing")
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._target(identity)
        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_bytes(data)
        os.replace(temp, target)
        return StoredArtifact(result_ref=str(target), file_id=str(target), size=len(data), sha256=sha256)

    def cleanup(self, *, identity: str) -> None:
        target = self._target(identity)
        if target.is_file():
            target.unlink(missing_ok=True)


def _within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((str(path), str(root))) == str(root)
    except ValueError:
        return False
