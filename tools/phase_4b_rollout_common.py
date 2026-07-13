# tools/phase_4b_rollout_common.py — shared read-only helpers for the Phase 4B
# rollout tooling (phase_4b_rollout_readiness.py, phase_4b_reconciliation.py,
# phase_4b_mark_legacy_approvals.py, phase_4b_repair_projections.py).
#
# Every function here is read-only unless its name says otherwise (only
# phase_4b_mark_legacy_approvals.py / phase_4b_repair_projections.py use the
# mutation helpers, and only behind their own --apply/--confirm gates).
#
# Never logs/prints secret values — only presence (yes/no) of configuration.

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx

from airtable_schema import ApprovalsFields, Tables
from tools.airtable_gateway import _at_headers, _at_url, AirtableLookupError

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_state() -> dict:
    """Current commit SHA + branch/ref. Never raises — reports 'unknown' on
    any failure (e.g. running outside a git checkout)."""
    def _run(args: list[str]) -> str | None:
        try:
            out = subprocess.run(
                args, cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
            )
            if out.returncode != 0:
                return None
            return out.stdout.strip() or None
        except Exception as exc:
            logger.warning("[phase_4b_rollout_common] git_state: %s", exc)
            return None

    return {
        "commit_sha": _run(["git", "rev-parse", "HEAD"]) or "unknown",
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown",
    }


def fetch_all_records(table: str, formula: str = "TRUE()", page_size: int = 100) -> list[dict] | None:
    """Full-table read, paginating through Airtable's `offset` token — unlike
    tools.airtable_gateway.at_list_by_formula(), which only returns a single
    page. Returns None (logged) on any network/HTTP failure — callers must
    treat that as "could not verify", never as "table is empty"."""
    records: list[dict] = []
    offset: str | None = None
    try:
        while True:
            params = {"filterByFormula": formula, "pageSize": min(page_size, 100)}
            if offset:
                params["offset"] = offset
            r = httpx.get(_at_url(table), headers=_at_headers(), params=params, timeout=15)
            if r.status_code != 200:
                raise AirtableLookupError(f"{table} list: HTTP {r.status_code}")
            data = r.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
        return records
    except Exception as exc:
        logger.error("[phase_4b_rollout_common] fetch_all_records(%s) failed: %s", table, exc)
        return None


def fetch_all_action_contracts() -> "list | None":
    """All ActionContracts rows, hydrated into core.action_gateway.ActionContract
    objects via the same serializer the durable repository uses. Returns None
    on fetch failure."""
    from core.action_contract_repository import _record_to_contract

    records = fetch_all_records(Tables.ACTION_CONTRACTS)
    if records is None:
        return None
    return [(_record_to_contract(r), r["id"]) for r in records]


def fetch_all_approvals() -> list[dict] | None:
    """All raw Approvals records (id + fields), unfiltered. Returns None on
    fetch failure."""
    return fetch_all_records("Approvals")


def fetch_all_claims(limit: int = 10000) -> list[dict] | None:
    """All action_execution_claims rows (read-only SELECT, no locking).
    Returns None if PostgreSQL is unavailable/not configured, [] if the table
    is empty."""
    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT contract_id, claimant_id, execution_id, status, claimed_at,
                       completed_at, idempotency_key, last_error
                FROM action_execution_claims
                ORDER BY claimed_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {
                "contract_id": row[0],
                "claimant_id": row[1],
                "execution_id": row[2],
                "status": row[3],
                "claimed_at": row[4],
                "completed_at": row[5],
                "idempotency_key": row[6],
                "last_error": row[7],
            }
            for row in rows
        ]
    except Exception as exc:
        logger.error("[phase_4b_rollout_common] fetch_all_claims failed: %s", exc)
        return None
    finally:
        release_conn(conn)


def is_canonical_tma_contract(contract, expect_tenant: str | None = None) -> bool:
    """Same structural definition as tma_api.py's _is_canonical_tma_contract(),
    reimplemented here against a plain ActionContract (no `identity` object
    available in an offline diagnostic) so a projection pointing at some
    other kind of pending contract is recognized as non-canonical the same
    way the live approve/reject path would refuse it. When expect_tenant is
    given, also requires contract.tenant_id == expect_tenant (the identity-
    bound check the live path performs); omit it to check tool/source/channel/
    policy shape only."""
    if contract is None:
        return False
    ok = (
        contract.tool_name == "tma_write"
        and getattr(contract, "trusted_source", "") == "tma_api"
        and contract.origin_channel == "tma"
        and getattr(contract, "approval_policy", "") == "approval"
    )
    if expect_tenant is not None:
        ok = ok and contract.tenant_id == expect_tenant
    return ok


def dump_json_report(path: Path, data: dict) -> None:
    """Deterministic (sorted keys), machine-readable JSON report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
