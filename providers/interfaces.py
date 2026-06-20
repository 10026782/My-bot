# providers/interfaces.py
# F13 — Provider Interfaces (Protocol-based)
# חוזים בלבד. אפס לוגיקה.

from __future__ import annotations
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StorageProvider(Protocol):
    def get(self, table: str, formula: str = "", max_records: int = 100,
            fields: list[str] | None = None) -> list[dict[str, Any]]: ...
    def add(self, table: str, fields: dict[str, Any]) -> dict[str, Any]: ...
    def update(self, table: str, record_id: str,
               fields: dict[str, Any]) -> dict[str, Any]: ...
    def delete(self, table: str, record_id: str) -> dict[str, Any]: ...


@runtime_checkable
class LLMProvider(Protocol):
    def generate(self, messages: list[dict[str, Any]], system: str,
                 model: str, max_tokens: int,
                 tools: list[dict[str, Any]] | None = None) -> dict[str, Any]: ...


@runtime_checkable
class ChannelAdapter(Protocol):
    def send(self, to: str, message: str,
             media_url: str | None = None) -> dict[str, Any]: ...
    def parse_inbound(self, raw_payload: dict[str, Any]) -> dict[str, Any]: ...
    def validate_inbound(self, request_headers: dict[str, str],
                         request_body: bytes) -> bool: ...
