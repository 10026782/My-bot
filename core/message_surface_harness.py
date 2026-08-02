"""Pure WS3 verification harness for public message surfaces.

The harness deliberately accepts only the frozen ``MessageContract``.  It does
not inspect lifecycle objects, resolve evidence, import ``app.py``, or send
anything.  Every surface is therefore tested against the same public contract
and the existing formatter.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from core.message_contract import MessageContract, format_message_contract_with_meta


SUPPORTED_SURFACES = ("telegram", "whatsapp", "tma", "api")
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_AIRTABLE_RECORD_RE = re.compile(r"\brec[a-zA-Z0-9]{10,}\b")


@dataclass(frozen=True)
class SurfaceRender:
    """One deterministic, user-facing rendering produced for a surface."""

    surface: str
    text: str
    state: str
    redaction_count: int


@dataclass(frozen=True)
class SurfaceVerification:
    """Readiness evidence for one contract across all supported surfaces."""

    renders: tuple[SurfaceRender, ...]
    leaks: tuple[str, ...]

    @property
    def ready(self) -> bool:
        """Whether all selected surfaces are identical and leak-free."""
        return bool(self.renders) and not self.leaks and len({r.text for r in self.renders}) == 1


def _validate_surfaces(surfaces: Iterable[str]) -> tuple[str, ...]:
    """Validate and normalize the closed list of supported public surfaces."""
    selected = tuple(surfaces)
    if not selected:
        raise ValueError("at least one surface is required")
    if len(set(selected)) != len(selected):
        raise ValueError("surfaces must be unique")
    unknown = set(selected) - set(SUPPORTED_SURFACES)
    if unknown:
        raise ValueError(f"unsupported surface: {sorted(unknown)[0]}")
    return selected


def render_surface(contract: MessageContract, surface: str) -> SurfaceRender:
    """Render one surface without allowing it to reinterpret contract state."""
    if not isinstance(contract, MessageContract):
        raise TypeError("contract must be a MessageContract")
    _validate_surfaces((surface,))
    text, meta = format_message_contract_with_meta(contract)
    return SurfaceRender(
        surface=surface,
        text=text,
        state=meta["formatter_state"],
        redaction_count=meta["redaction_count"],
    )


def verify_surface_parity(
    contract: MessageContract,
    *,
    surfaces: Iterable[str] = SUPPORTED_SURFACES,
    forbidden_tokens: Iterable[str] = (),
) -> SurfaceVerification:
    """Return deterministic parity and leak evidence for a public contract."""
    selected = _validate_surfaces(surfaces)
    renders = tuple(render_surface(contract, surface) for surface in selected)
    tokens = tuple(token for token in forbidden_tokens if token)
    leaks: set[str] = set()
    for render in renders:
        if _UUID_RE.search(render.text):
            leaks.add("uuid")
        if _AIRTABLE_RECORD_RE.search(render.text):
            leaks.add("airtable_record_id")
    for token in tokens:
        if any(token in render.text for render in renders):
            leaks.add(token)
    return SurfaceVerification(renders=renders, leaks=tuple(sorted(leaks)))


def assert_surface_ready(
    contract: MessageContract,
    *,
    surfaces: Iterable[str] = SUPPORTED_SURFACES,
    forbidden_tokens: Iterable[str] = (),
) -> SurfaceVerification:
    """Fail closed for a canary/readiness gate; no rollout or flag mutation."""
    verification = verify_surface_parity(
        contract, surfaces=surfaces, forbidden_tokens=forbidden_tokens
    )
    if not verification.ready:
        raise AssertionError(
            "surface readiness failed: "
            f"states={[render.state for render in verification.renders]}, "
            f"leaks={verification.leaks}"
        )
    return verification


def rollback_is_safe(verification: SurfaceVerification) -> bool:
    """Rollback is safe when the harness has no side effects to undo."""
    return isinstance(verification, SurfaceVerification)
