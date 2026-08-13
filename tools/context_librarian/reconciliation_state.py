"""Mechanical, repo-level reconciliation state: the new-source scan baseline
plus classification provenance for every path the engine has ever
auto-registered.

Deliberately separate from any node's own provenance fields
(last_verified_commit / last_observed_commit): those track drift on
*registered* nodes, while this file tracks (a) how far the *new-source
discovery* scan has progressed, and (b) *why* automation was allowed to
place each auto-registered path where it is, so that decision can be
continuously re-proven rather than trusted forever. See
docs/context_librarian/RECONCILIATION.md.

The only writer is reconcile.py's apply_auto_maintenance(). Section
`last_source_scan_commit` only ever advances after a scan window came back
with an empty decision_queue -- a SHA is never recorded as scanned while a
genuine OWNER_DECISION_REQUIRED item from that window is still unresolved.
Section `auto_registrations` records exactly the metadata item 2 of the
Message E correction requires per path; it is refreshed (not silently
trusted) every time reconcile.py's revalidation pass proves the path still
satisfies its policy's current predicate.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from tools.context_librarian.librarian import ContextLibrarianError

STATE_FILENAME = "reconciliation_state.json"
# Retained for external reference (e.g. librarian.py's infra allowlist,
# which is keyed off repo-relative paths of files as they exist on disk) --
# the functions below key off Catalog.catalog_root, not this literal, so
# they stay correct under the CATALOG_RELATIVE_ROOT test-isolation seam
# librarian.py's own tests already rely on.
STATE_RELATIVE_PATH = Path("docs/context_librarian") / STATE_FILENAME
_SCHEMA_VERSION = "1.1"
_DEFAULT_STATE: dict[str, Any] = {
    "schema_version": _SCHEMA_VERSION,
    "last_source_scan_commit": None,
    "auto_registrations": {},
}


def load_reconciliation_state(catalog_root: Path | str) -> dict[str, Any]:
    path = Path(catalog_root) / STATE_FILENAME
    if not path.exists():
        # Migration fallback: no state file yet means no prior scan/
        # registration has been recorded.
        return dict(_DEFAULT_STATE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextLibrarianError(f"cannot load {path}: {exc}") from exc
    if not isinstance(data, dict) or "last_source_scan_commit" not in data:
        raise ContextLibrarianError(f"{path}: malformed reconciliation state")
    # Migration: a 1.0 state file (pre-Message-E-correction) has no
    # auto_registrations section yet.
    data.setdefault("auto_registrations", {})
    return data


def _write_state(catalog_root: Path | str, state: dict[str, Any]) -> None:
    """Atomic tempfile+os.replace write, mirroring reconcile.stamp_observed()."""
    path = Path(catalog_root) / STATE_FILENAME
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_source_scan_commit(catalog_root: Path | str, sha: str) -> None:
    state = load_reconciliation_state(catalog_root)
    state["last_source_scan_commit"] = sha
    state["schema_version"] = _SCHEMA_VERSION
    _write_state(catalog_root, state)


def update_auto_registrations(
    catalog_root: Path | str, entries: dict[str, dict[str, Any] | None]
) -> None:
    """Merges `entries` into the stored auto_registrations map. A value of
    None removes that path's entry entirely (used when a path is no longer
    registered in any node -- see reconcile._revalidate_auto_registrations).
    Every other value fully replaces the prior entry for that path (no
    partial-field merge -- a revalidation always writes a complete, fresh
    provenance record)."""
    state = load_reconciliation_state(catalog_root)
    registrations = state["auto_registrations"]
    for path, entry in entries.items():
        if entry is None:
            registrations.pop(path, None)
        else:
            registrations[path] = entry
    state["schema_version"] = _SCHEMA_VERSION
    _write_state(catalog_root, state)
