"""TC10 — unique, disposable staging identities and their cleanup.

Staging is real Airtable/PostgreSQL shared with other work. A staging
canary that reuses a fixed identity (a literal "owner_1" string, say) can
collide with a pending ActionContract a *previous* canary run left behind
for that same identity — that is exactly the BUG-122
proposal_boundary_blocked contamination documented in
docs/architecture/turn-coordinator-full/TC8_DURABLE_TURN_STATE.md's TC10
handoff. This module gives every staging verification run its own
namespace so that can't happen, while keeping the same role semantics
(`identity.Role`) production code depends on — this does not change or
weaken production identity resolution, it only chooses disposable
tenant_id/user_id values for verification runs.

Usage:
    from scripts.staging_identity import new_run_namespace, unique_identity

    run_id = new_run_namespace()
    owner = unique_identity(Role.OWNER, run_id=run_id)
    ... exercise the runtime with `owner` ...
    cleanup_run_contracts(run_id)  # best-effort, scoped to this run only
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from identity import Identity, Role  # noqa: E402

logger = logging.getLogger(__name__)

_NAMESPACE_PREFIX = "tc10verify"


def new_run_namespace() -> str:
    """A fresh, sortable, collision-resistant identifier for one verification run.

    Uses the full UUID4 (not a truncated prefix) — a cleanup call scoped to
    the wrong namespace due to a collision would delete another run's
    ActionContracts, so this namespace keeps the UUID's complete entropy
    rather than trading it away for a shorter string.
    """
    return f"{_NAMESPACE_PREFIX}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex}"


def unique_identity(
    role: str = Role.OWNER,
    *,
    run_id: str | None = None,
    channel: str = "telegram",
    label: str = "",
) -> Identity:
    """A disposable Identity with production-equivalent role semantics.

    tenant_id is namespaced per run, so canonical_user_id (tenant_id:user_id,
    see Identity.memory_key) can never collide with a contract left behind by
    an earlier run against the same real staging Airtable base — regardless
    of what identity strings that earlier run used.
    """
    run_id = run_id or new_run_namespace()
    suffix = f"{label or role}-{uuid.uuid4().hex[:6]}"
    user_id = f"{run_id}-{suffix}"
    return Identity(
        user_id=user_id,
        role=role,
        tenant_id=run_id,
        channel=channel,
        external_id=user_id,
        display_name=f"TC10 verification ({role})",
    )


def cleanup_run_contracts(run_id: str) -> int:
    """Best-effort delete of ActionContracts created under this run's tenant_id.

    Scoped strictly to ``run_id`` (used as tenant_id) — never touches any
    record outside this run's own namespace. Safe to call even if nothing
    was created (returns 0) or if Airtable is unreachable (logs and returns
    0 rather than raising — cleanup failing must never fail the canary that
    already recorded its evidence).
    """
    if not run_id.startswith(_NAMESPACE_PREFIX):
        raise ValueError(
            f"refusing to clean up run_id={run_id!r} — does not look like a "
            f"scripts.staging_identity run namespace (expected prefix "
            f"{_NAMESPACE_PREFIX!r}); this guard exists so a typo here can "
            f"never turn into a broad delete."
        )
    try:
        from airtable_schema import ActionContractsFields, Tables
        from tools.airtable_gateway import escape_formula_value, airtable_delete, at_list_by_formula
    except Exception:
        logger.warning("[TC10] cleanup_run_contracts: Airtable gateway unavailable, skipping", exc_info=True)
        return 0

    formula = (
        f"{{{ActionContractsFields.TENANT_ID}}} = "
        f"'{escape_formula_value(run_id)}'"
    )
    try:
        records = at_list_by_formula(Tables.ACTION_CONTRACTS, formula)
    except Exception:
        logger.warning("[TC10] cleanup_run_contracts: lookup failed for run_id=%s", run_id, exc_info=True)
        return 0

    deleted = 0
    for record in records or []:
        record_id = record.get("id")
        if not record_id:
            continue
        try:
            if airtable_delete(Tables.ACTION_CONTRACTS, record_id, source="tc10_staging_cleanup"):
                deleted += 1
        except Exception:
            logger.warning("[TC10] cleanup_run_contracts: delete failed for record=%s", record_id, exc_info=True)
    logger.info("[TC10] cleanup_run_contracts: run_id=%s deleted=%d", run_id, deleted)
    return deleted
