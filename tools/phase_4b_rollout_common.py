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

from airtable_schema import ActionContractsFields, ActionContractStatus, ApprovalsFields, Tables
from tools.airtable_read_adapter import AirtableReadError, get_record, list_records_page

logger = logging.getLogger(__name__)

# Expected live field types for ActionContractsFields, mirroring the
# reproducible schema spec documented in ActionContractsFields' own
# docstring (airtable_schema.py). Kept here as ONE machine-readable source
# so readiness checks compare against this instead of re-deriving it from
# prose each time.
ACTION_CONTRACTS_EXPECTED_TYPES: dict[str, str] = {
    ActionContractsFields.CONTRACT_ID: "singleLineText",
    ActionContractsFields.TENANT_ID: "singleLineText",
    ActionContractsFields.CANONICAL_USER_ID: "singleLineText",
    ActionContractsFields.TOOL_NAME: "singleLineText",
    ActionContractsFields.NORMALIZED_PAYLOAD: "multilineText",
    ActionContractsFields.BUSINESS_FINGERPRINT: "singleLineText",
    ActionContractsFields.ORIGIN_CHANNEL: "singleLineText",
    ActionContractsFields.ORIGIN_CHAT_ID: "singleLineText",
    ActionContractsFields.REQUIRES_APPROVAL: "checkbox",
    ActionContractsFields.STATUS: "singleSelect",
    ActionContractsFields.CREATED_AT: "number",
    ActionContractsFields.APPROVED_BY: "singleLineText",
    ActionContractsFields.APPROVED_AT: "number",
    ActionContractsFields.VERSION: "number",
    ActionContractsFields.ACTOR_ROLE: "singleLineText",
    ActionContractsFields.ACTOR_USER_ID: "singleLineText",
    ActionContractsFields.ACTOR_DISPLAY_NAME: "singleLineText",
    ActionContractsFields.ACTOR_DOMAIN_ID: "singleLineText",
    ActionContractsFields.ACTOR_EXTERNAL_ID: "singleLineText",
    ActionContractsFields.ACTOR_ALLOWED_DOMAINS: "multilineText",
    ActionContractsFields.APPROVAL_POLICY: "singleLineText",
    ActionContractsFields.TRUSTED_SOURCE: "singleLineText",
    ActionContractsFields.CONTEXT_INTERRUPTED: "checkbox",
    ActionContractsFields.RECONFIRMATION_REQUIRED: "checkbox",
    ActionContractsFields.CONTEXT_INTEGRITY_UNKNOWN: "checkbox",
    ActionContractsFields.IDEMPOTENCY_KEY: "singleLineText",
}

# Reused directly from ActionContractStatus (airtable_schema.py) — the
# single canonical source of these values — rather than a second hardcoded
# literal set that could drift from it.
ACTION_CONTRACTS_STATUS_CHOICES: set[str] = {
    v for k, v in vars(ActionContractStatus).items()
    if not k.startswith("_") and isinstance(v, str)
}

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
            try:
                page, offset = list_records_page(
                    table,
                    formula,
                    page_size=min(page_size, 100),
                    offset=offset or "",
                    timeout=15,
                )
            except AirtableReadError as exc:
                if exc.status_code is not None:
                    raise RuntimeError(f"{table} list: HTTP {exc.status_code}") from exc
                if exc.cause is not None:
                    raise exc.cause from exc
                raise
            records.extend(page)
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


def fetch_record_by_id(table: str, record_id: str) -> dict | None:
    """Read-only GET of exactly one record by its Airtable record ID (used
    by tools/phase_4b_canary_verify.py to confirm a supplied Approvals/
    provider record actually exists — never a write). Returns None on any
    failure (network error, non-200, 404) — this helper does not distinguish
    "not found" from "unreachable"; callers that need that distinction
    should use fetch_all_records() + an id match instead."""
    try:
        return get_record(table, record_id, timeout=15)
    except AirtableReadError as exc:
        if exc.status_code is not None:
            return None
        original = exc.cause or exc
        logger.error(
            "[phase_4b_rollout_common] fetch_record_by_id(%s, %s) failed: %s",
            table, record_id, original,
        )
        return None
    except Exception as exc:
        logger.error(
            "[phase_4b_rollout_common] fetch_record_by_id(%s, %s) failed: %s",
            table, record_id, exc,
        )
        return None


def fetch_all_claims(limit: int = 100_000) -> list[dict] | None:
    """All action_execution_claims rows (read-only SELECT, no locking).
    Returns None if PostgreSQL is unavailable/not configured, or if the fetch
    would be truncated — `limit` is a generous safety bound, not a silent
    cap: a COUNT(*) is taken first and compared against what was actually
    fetched, so a dataset larger than `limit` is reported as a fetch failure
    (None) rather than silently handed to callers as a complete-looking but
    partial list. Callers must never derive rollout_target_met=true from a
    truncated claims fetch — returning None here routes straight into the
    existing "claims unavailable" / fetch_errors path.
    Returns [] if the table is genuinely empty."""
    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM action_execution_claims;")
            total = cur.fetchone()[0]

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

        if len(rows) < total:
            logger.error(
                "[phase_4b_rollout_common] fetch_all_claims truncated: fetched=%d total=%d "
                "(limit=%d) — treating as a fetch failure rather than returning a partial "
                "dataset; raise `limit` or paginate if this table has genuinely grown this large",
                len(rows), total, limit,
            )
            return None

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
