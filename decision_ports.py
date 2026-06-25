# decision_ports.py — Decision Hub (Stage 0) Ports/Adapters
#
# Protocol-based boundary between decision_pipeline.py (the core) and the
# concrete systems it relies on (Airtable, contacts, anti_hallucination,
# Approval Gate). decision_pipeline.py must never import these concrete
# systems directly — only DecisionPorts, injected via build_default_ports().
#
# ב-V4 multi-tenant, tenant יכול לרשום שער מחמיר/מקל בלי לגעת בליבה —
# השערים הם plugins. build_default_ports() הוא נקודת ההזרקה היחידה
# שמכירה את Airtable; החלפת storage/verifier בעתיד = שינוי בקובץ הזה בלבד.

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Protocols
# ══════════════════════════════════════════════════

class StoragePort(Protocol):
    def add(self, table: str, fields: dict, source: str) -> str | None: ...
    def get(self, table: str, filter_formula: str = "") -> list: ...
    def update(self, table: str, record_id: str, fields: dict, source: str) -> bool: ...


class ContactPort(Protocol):
    def find_or_create(self, name: str, hint: str = "") -> dict: ...  # F12


class VerifierPort(Protocol):
    def verify(self, content: str, source: str) -> dict: ...  # anti_hallucination


class ApprovalPort(Protocol):
    def request(self, action: dict) -> str: ...  # Approval Gate


@dataclass
class DecisionPorts:
    storage:  StoragePort
    contacts: ContactPort
    verifier: VerifierPort
    approver: ApprovalPort


# ══════════════════════════════════════════════════
# Stage 0 adapters — thin wrappers על הקיים
# ══════════════════════════════════════════════════

class _AirtableStorageAdapter:
    """StoragePort over tools/airtable_gateway.py — the single write gateway."""

    def add(self, table: str, fields: dict, source: str) -> str | None:
        from tools.airtable_gateway import airtable_create
        record = airtable_create(table, fields, source=source)
        return record.get("id") if record else None

    def get(self, table: str, filter_formula: str = "") -> list:
        try:
            import httpx
            from tools.airtable_gateway import _at_url, _at_headers

            params: dict = {}
            if filter_formula:
                params["filterByFormula"] = filter_formula
            r = httpx.get(_at_url(table), headers=_at_headers(), params=params, timeout=10)
            if r.status_code == 200:
                return r.json().get("records", [])
            logger.warning(f"[DecisionPorts] storage.get({table}) -> {r.status_code}")
        except Exception as e:
            logger.warning(f"[DecisionPorts] storage.get({table}) error: {e}")
        return []

    def update(self, table: str, record_id: str, fields: dict, source: str) -> bool:
        from tools.airtable_gateway import airtable_patch
        return airtable_patch(table, record_id, fields, source=source)


class _ContactResolverAdapter:
    """ContactPort over tools/contact_resolver.py — finds, never creates (no create exists yet)."""

    def find_or_create(self, name: str, hint: str = "") -> dict:
        from tools.contact_resolver import resolve, ResolveStatus

        result = resolve(name)
        contact = result.matches[0] if result.status == ResolveStatus.FOUND_ONE and result.matches else None
        return {
            "status":  result.status.value,   # "found_one" | "ambiguous" | "not_found"
            "contact": contact,
            "matches": result.matches,
        }


class _AntiHallucinationVerifierAdapter:
    """VerifierPort over core/anti_hallucination.py — Stage 1 stub.

    No real claim-content verification exists yet (core/anti_hallucination.py only
    verifies tool-execution claims, a different domain). status="ok" so gate_trust's
    compute_trust() treats every event as unverified-but-not-failed until a real
    checker lands.
    """

    def verify(self, content: str, source: str) -> dict:
        return {"status": "ok", "reason": "Stage 1 stub — no claim-content verification yet"}


class _ApprovalGateAdapter:
    """ApprovalPort over the existing Approval Gate — Stage 0 stub, no high-risk actions yet."""

    def request(self, action: dict) -> str:
        logger.info(f"[DecisionPorts] approval.request stub — action={action}")
        return ""


def build_default_ports() -> DecisionPorts:
    """נקודת ההזרקה היחידה שמכירה את Airtable/contact_resolver/anti_hallucination."""
    return DecisionPorts(
        storage  = _AirtableStorageAdapter(),
        contacts = _ContactResolverAdapter(),
        verifier = _AntiHallucinationVerifierAdapter(),
        approver = _ApprovalGateAdapter(),
    )
