"""Mechanical, repo-level new-source scan baseline.

Deliberately separate from any node's own provenance fields
(last_verified_commit / last_observed_commit): those track drift on
*registered* nodes, while this file tracks how far the *new-source
discovery* scan (the "what unregistered files exist now" question) has
progressed. See docs/context_librarian/RECONCILIATION.md.

The only writer is reconcile.py's apply_auto_maintenance(), and only after
a scan window came back with an empty decision_queue -- a SHA is never
recorded as scanned while a genuine OWNER_DECISION_REQUIRED item from that
window is still unresolved, so advancing this baseline can never make an
unresolved item silently stop being discovered.
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
_SCHEMA_VERSION = "1.0"


def load_reconciliation_state(catalog_root: Path | str) -> dict[str, Any]:
    path = Path(catalog_root) / STATE_FILENAME
    if not path.exists():
        # Migration fallback: no state file yet means no prior scan has been
        # recorded -- callers fall back to the old anchor-based discovery.
        return {"schema_version": _SCHEMA_VERSION, "last_source_scan_commit": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextLibrarianError(f"cannot load {path}: {exc}") from exc
    if not isinstance(data, dict) or "last_source_scan_commit" not in data:
        raise ContextLibrarianError(f"{path}: malformed reconciliation state")
    return data


def write_source_scan_commit(catalog_root: Path | str, sha: str) -> None:
    """Atomic tempfile+os.replace write, mirroring reconcile.stamp_observed()."""
    path = Path(catalog_root) / STATE_FILENAME
    payload = (
        json.dumps(
            {"schema_version": _SCHEMA_VERSION, "last_source_scan_commit": sha},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)
