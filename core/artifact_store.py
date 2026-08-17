"""Durable artifact storage boundary used after provider validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredArtifact:
    result_ref: str
    file_id: str
    size: int
    sha256: str


class ArtifactStoreError(RuntimeError):
    def __init__(self, code: str, *, uncertain: bool = False):
        super().__init__(code)
        self.code = code
        self.uncertain = uncertain


class ArtifactStore(Protocol):
    def put(self, *, path, identity: str, metadata: dict) -> StoredArtifact: ...

    def cleanup(self, *, identity: str) -> None: ...
