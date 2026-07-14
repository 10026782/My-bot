#!/usr/bin/env python3
# tools/phase_4b_rollout_readiness.py — Phase 4B rollout readiness diagnostic.
#
# Read-only by default (this tool has no --apply/mutation mode at all).
# Run manually before any Phase 4B cutover step:
#   python3 tools/phase_4b_rollout_readiness.py
#   python3 tools/phase_4b_rollout_readiness.py --json
#
# Produces reports/phase_4b_rollout_readiness.json and a GO/NO-GO/WARNING
# terminal summary. See docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md for how this
# fits into the overall rollout sequence.
#
# Never logs/prints secret values — only presence (yes/no) of configuration
# and booleans for feature flags.
#
# Exit codes:
#   0 = GO or WARNING (no mandatory gate failed)
#   1 = NO-GO (one or more mandatory gates failed)
#   2 = the diagnostic itself crashed / produced an unknown result

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.phase_4b_rollout_common import REPO_ROOT, dump_json_report, git_state, utc_now_iso  # noqa: E402

REPORT_PATH = REPO_ROOT / "reports" / "runtime" / "phase_4b_rollout_readiness.json"

_IMPORT_MODULES = [
    "core.action_gateway",
    "core.action_contract_repository",
    "core.atomic_claim_repository",
    "core.database",
    "core.database_migrations",
    "core.approvals_projection",
    "core.runtime_schema_provider",
    "tool_registry",
    "tools.dispatcher",
    "tools.approval_actions",
    "tma_api",
]

_REQUIRED_CLAIM_COLUMNS = {
    "contract_id", "claimant_id", "execution_id", "status", "claimed_at",
    "completed_at", "idempotency_key", "last_error", "created_at", "updated_at",
}

_PROJECTED_LIFECYCLE_CHOICES = {
    "pending", "approved", "rejected", "executing", "completed",
    "failed", "outcome_unknown", "superseded", "legacy",
}


def _finding(id_: str, section: str, description: str, mandatory: bool,
             status: str, detail: str = "") -> dict:
    assert status in ("PASS", "FAIL", "WARN", "SKIP")
    return {
        "id": id_, "section": section, "description": description,
        "mandatory": mandatory, "status": status, "detail": detail,
    }


def _safe_str(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


# ══════════════════════════════════════════════════
# A — Git / code state
# ══════════════════════════════════════════════════

def _check_code_state() -> list[dict]:
    findings = []

    for mod_name in _IMPORT_MODULES:
        try:
            import importlib
            importlib.import_module(mod_name)
            findings.append(_finding(
                f"A.import.{mod_name}", "A_code_state",
                f"module '{mod_name}' imports successfully", True, "PASS",
            ))
        except Exception as exc:
            findings.append(_finding(
                f"A.import.{mod_name}", "A_code_state",
                f"module '{mod_name}' imports successfully", True, "FAIL",
                _safe_str(exc),
            ))

    try:
        import tool_registry
        registered = tool_registry.get("tma_write") is not None
        findings.append(_finding(
            "A.tma_write_registered", "A_code_state",
            "tma_write is registered in tool_registry", True,
            "PASS" if registered else "FAIL",
            "found" if registered else "tool_registry.get('tma_write') returned None",
        ))
    except Exception as exc:
        findings.append(_finding(
            "A.tma_write_registered", "A_code_state",
            "tma_write is registered in tool_registry", True, "FAIL", _safe_str(exc),
        ))

    try:
        import tools.schemas as schemas_mod
        names = {t.get("name") for t in schemas_mod.TOOL_SCHEMAS}
        exposed = "tma_write" in names
        findings.append(_finding(
            "A.tma_write_not_exposed", "A_code_state",
            "tma_write is NOT exposed in tools/schemas.py", True,
            "FAIL" if exposed else "PASS",
            "present in TOOL_SCHEMAS (must not be)" if exposed else "absent, as required",
        ))
    except Exception as exc:
        findings.append(_finding(
            "A.tma_write_not_exposed", "A_code_state",
            "tma_write is NOT exposed in tools/schemas.py", True, "FAIL", _safe_str(exc),
        ))

    # Informational only — whether the durable repository is wired up right
    # now depends entirely on FEATURE_ACTION_CONTRACT_PERSISTENCE, which is
    # expected to be OFF before rollout. See section D for the mandatory gate.
    try:
        from core.action_gateway import action_gateway
        configured = getattr(action_gateway._ledger, "_repository", None) is not None
        findings.append(_finding(
            "A.ledger_repository_wiring", "A_code_state",
            "ActionGateway ledger repository wiring (informational)", False, "PASS",
            f"repository configured now: {configured}",
        ))
    except Exception as exc:
        findings.append(_finding(
            "A.ledger_repository_wiring", "A_code_state",
            "ActionGateway ledger repository wiring (informational)", False, "WARN",
            _safe_str(exc),
        ))

    return findings


# ══════════════════════════════════════════════════
# B — Feature flags
# ══════════════════════════════════════════════════

def _check_feature_flags(mode: str) -> list[dict]:
    """--mode preflight: flags may legitimately both be OFF — only a
    mismatched (exactly-one-enabled) state is ever blocking.
    --mode active: this is a post-cutover check, so both flags must
    actually be ON — an OFF flag here means the wiring this mode claims to
    verify was never actually enabled."""
    findings = []
    try:
        import feature_flags
        acp = feature_flags.is_enabled("FEATURE_ACTION_CONTRACT_PERSISTENCE")
        atc = feature_flags.is_enabled("FEATURE_ATOMIC_CLAIMS")

        findings.append(_finding(
            "B.acp_state", "B_feature_flags",
            "FEATURE_ACTION_CONTRACT_PERSISTENCE current state (informational)",
            False, "PASS", f"enabled={acp}",
        ))
        findings.append(_finding(
            "B.atc_state", "B_feature_flags",
            "FEATURE_ATOMIC_CLAIMS current state (informational)",
            False, "PASS", f"enabled={atc}",
        ))

        mismatched = acp != atc
        findings.append(_finding(
            "B.no_mismatched_flags", "B_feature_flags",
            "flags are not in a mismatched (exactly-one-enabled) state", True,
            "FAIL" if mismatched else "PASS",
            (f"FEATURE_ACTION_CONTRACT_PERSISTENCE={acp} FEATURE_ATOMIC_CLAIMS={atc} — "
             "never enable only one of these as a rollout state") if mismatched
            else f"both flags agree (enabled={acp})",
        ))

        if mode == "active":
            findings.append(_finding(
                "B.flags_both_on", "B_feature_flags",
                "both flags are ON (required for --mode active)", True,
                "PASS" if (acp and atc) else "FAIL",
                f"FEATURE_ACTION_CONTRACT_PERSISTENCE={acp} FEATURE_ATOMIC_CLAIMS={atc}",
            ))
    except Exception as exc:
        findings.append(_finding(
            "B.flags_readable", "B_feature_flags",
            "feature_flags module readable", True, "FAIL", _safe_str(exc),
        ))
    return findings


# ══════════════════════════════════════════════════
# C — PostgreSQL
# ══════════════════════════════════════════════════

def _check_postgresql() -> list[dict]:
    findings: list[dict] = []
    import os

    env_present = bool(
        os.environ.get("DATABASE_URL")
        or all(os.environ.get(v) for v in
               ("DATABASE_HOST", "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD"))
    )
    findings.append(_finding(
        "C.env_present", "C_postgresql",
        "DATABASE_URL (or legacy DB env vars) configured", True,
        "PASS" if env_present else "FAIL",
        "present" if env_present else "not configured",
    ))
    if not env_present:
        for check_id, desc in [
            ("C.pool", "get_pool() succeeds"),
            ("C.select1", "SELECT 1 succeeds"),
            ("C.table_exists", "action_execution_claims table exists"),
            ("C.columns", "required action_execution_claims columns exist"),
            ("C.pk", "contract_id primary-key protection exists"),
            ("C.unique_idem", "idempotency_key uniqueness exists"),
            ("C.rollback", "read/write transaction opens and rolls back cleanly"),
            ("C.migration_state", "migration state compatible with current code"),
        ]:
            findings.append(_finding(check_id, "C_postgresql", desc, True, "SKIP",
                                      "skipped: PostgreSQL not configured"))
        return findings

    try:
        from core.database import get_conn, get_pool, release_conn
    except Exception as exc:
        findings.append(_finding("C.pool", "C_postgresql", "get_pool() succeeds",
                                  True, "FAIL", _safe_str(exc)))
        return findings

    pool = get_pool()
    findings.append(_finding(
        "C.pool", "C_postgresql", "get_pool() succeeds", True,
        "PASS" if pool is not None else "FAIL",
        "pool initialized" if pool is not None else "get_pool() returned None",
    ))
    if pool is None:
        for check_id, desc in [
            ("C.select1", "SELECT 1 succeeds"),
            ("C.table_exists", "action_execution_claims table exists"),
            ("C.columns", "required action_execution_claims columns exist"),
            ("C.pk", "contract_id primary-key protection exists"),
            ("C.unique_idem", "idempotency_key uniqueness exists"),
            ("C.rollback", "read/write transaction opens and rolls back cleanly"),
            ("C.migration_state", "migration state compatible with current code"),
        ]:
            findings.append(_finding(check_id, "C_postgresql", desc, True, "SKIP",
                                      "skipped: pool unavailable"))
        return findings

    conn = get_conn()
    if conn is None:
        findings.append(_finding("C.select1", "C_postgresql", "SELECT 1 succeeds",
                                  True, "FAIL", "get_conn() returned None"))
        for check_id, desc in [
            ("C.table_exists", "action_execution_claims table exists"),
            ("C.columns", "required action_execution_claims columns exist"),
            ("C.pk", "contract_id primary-key protection exists"),
            ("C.unique_idem", "idempotency_key uniqueness exists"),
            ("C.rollback", "read/write transaction opens and rolls back cleanly"),
            ("C.migration_state", "migration state compatible with current code"),
        ]:
            findings.append(_finding(check_id, "C_postgresql", desc, True, "SKIP",
                                      "skipped: no connection"))
        return findings

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        findings.append(_finding("C.select1", "C_postgresql", "SELECT 1 succeeds",
                                  True, "PASS"))

        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'action_execution_claims');"
            )
            table_exists = bool(cur.fetchone()[0])
        findings.append(_finding(
            "C.table_exists", "C_postgresql", "action_execution_claims table exists",
            True, "PASS" if table_exists else "FAIL",
            "" if table_exists else "table not found",
        ))

        if table_exists:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'action_execution_claims';"
                )
                columns = {row[0] for row in cur.fetchall()}
            missing = _REQUIRED_CLAIM_COLUMNS - columns
            findings.append(_finding(
                "C.columns", "C_postgresql", "required action_execution_claims columns exist",
                True, "PASS" if not missing else "FAIL",
                "" if not missing else f"missing columns: {sorted(missing)}",
            ))

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tc.constraint_type, kcu.column_name "
                    "FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "  ON tc.constraint_name = kcu.constraint_name "
                    "WHERE tc.table_name = 'action_execution_claims';"
                )
                constraints = cur.fetchall()
            pk_on_contract_id = any(
                ctype == "PRIMARY KEY" and col == "contract_id" for ctype, col in constraints
            )
            unique_on_idempotency = any(
                ctype == "UNIQUE" and col == "idempotency_key" for ctype, col in constraints
            )
            findings.append(_finding(
                "C.pk", "C_postgresql", "contract_id primary-key protection exists",
                True, "PASS" if pk_on_contract_id else "FAIL",
                "" if pk_on_contract_id else "no PRIMARY KEY constraint on contract_id",
            ))
            findings.append(_finding(
                "C.unique_idem", "C_postgresql", "idempotency_key uniqueness exists",
                True, "PASS" if unique_on_idempotency else "FAIL",
                "" if unique_on_idempotency else "no UNIQUE constraint on idempotency_key",
            ))

            findings.append(_finding(
                "C.migration_state", "C_postgresql",
                "migration state compatible with current code", True,
                "PASS" if (not missing and pk_on_contract_id and unique_on_idempotency) else "FAIL",
                "derived from table/column/constraint checks above",
            ))
        else:
            for check_id, desc in [
                ("C.columns", "required action_execution_claims columns exist"),
                ("C.pk", "contract_id primary-key protection exists"),
                ("C.unique_idem", "idempotency_key uniqueness exists"),
                ("C.migration_state", "migration state compatible with current code"),
            ]:
                findings.append(_finding(check_id, "C_postgresql", desc, True, "FAIL",
                                          "table does not exist"))

        # Transaction probe: insert a throwaway row, then roll back. Never
        # committed — verified absent afterward on a fresh connection.
        probe_id = f"__phase4b_readiness_probe__{uuid.uuid4()}"
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO action_execution_claims "
                    "(contract_id, claimant_id, execution_id, status, claimed_at, idempotency_key) "
                    "VALUES (%s, %s, %s, %s, %s, %s);",
                    (probe_id, "readiness-probe", str(uuid.uuid4()), "executing",
                     0.0, str(uuid.uuid4())),
                )
            conn.rollback()

            conn2 = get_conn()
            try:
                with conn2.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM action_execution_claims WHERE contract_id = %s;",
                        (probe_id,),
                    )
                    leaked = cur.fetchone() is not None
            finally:
                release_conn(conn2)

            findings.append(_finding(
                "C.rollback", "C_postgresql",
                "read/write transaction opens and rolls back cleanly", True,
                "FAIL" if leaked else "PASS",
                "probe row persisted after rollback!" if leaked else "probe row absent, as expected",
            ))
        except Exception as exc:
            conn.rollback()
            findings.append(_finding(
                "C.rollback", "C_postgresql",
                "read/write transaction opens and rolls back cleanly", True, "FAIL",
                _safe_str(exc),
            ))

    except Exception as exc:
        findings.append(_finding(
            "C.unexpected", "C_postgresql", "PostgreSQL diagnostic ran without error",
            True, "FAIL", _safe_str(exc),
        ))
    finally:
        release_conn(conn)

    return findings


# ══════════════════════════════════════════════════
# D — ActionContract persistence.
#
# --mode active mirrors tma_api._queue_tma_write_approval's own fail-closed
# gate exactly (so this branch can never drift from the live authorization
# check it is validating readiness for): both flags must be ON AND the
# ActionGateway singleton's runtime wiring must already be active.
#
# --mode preflight deliberately does NOT require either flag to be on — it
# proves the underlying ActionContractRepository code path is reachable
# right now, independent of whatever the singleton's current wiring state
# is, so infra readiness can be confirmed *before* flipping any flag.
# ══════════════════════════════════════════════════

def _check_action_contract_persistence(mode: str) -> list[dict]:
    if mode == "active":
        return _check_action_contract_persistence_active()
    return _check_action_contract_persistence_preflight()


def _check_action_contract_persistence_active() -> list[dict]:
    findings = []
    try:
        import feature_flags
        import core.database as _db
        from core.action_gateway import action_gateway as _gw

        durable_persistence_available = (
            feature_flags.is_enabled("FEATURE_ACTION_CONTRACT_PERSISTENCE")
            and getattr(_gw._ledger, "_repository", None) is not None
        )
        atomic_claims_available = (
            feature_flags.is_enabled("FEATURE_ATOMIC_CLAIMS")
            and _db.get_pool() is not None
        )

        findings.append(_finding(
            "D.durable_persistence_available", "D_action_contract_persistence",
            "durable ActionContract persistence available (repository configured + reachable)",
            True, "PASS" if durable_persistence_available else "FAIL",
            f"FEATURE_ACTION_CONTRACT_PERSISTENCE and repository wiring: {durable_persistence_available}",
        ))
        findings.append(_finding(
            "D.atomic_claims_available", "D_action_contract_persistence",
            "PostgreSQL atomic claims execution available",
            True, "PASS" if atomic_claims_available else "FAIL",
            f"FEATURE_ATOMIC_CLAIMS and pool reachability: {atomic_claims_available}",
        ))

        if durable_persistence_available:
            try:
                repo = _gw._ledger._repository
                repo.find_pending_by_canonical_user("__phase4b_readiness_probe__")
                findings.append(_finding(
                    "D.repository_query", "D_action_contract_persistence",
                    "a read-only repository query succeeds", True, "PASS",
                ))
            except Exception as exc:
                findings.append(_finding(
                    "D.repository_query", "D_action_contract_persistence",
                    "a read-only repository query succeeds", True, "FAIL", _safe_str(exc),
                ))
        else:
            findings.append(_finding(
                "D.repository_query", "D_action_contract_persistence",
                "a read-only repository query succeeds", True, "SKIP",
                "skipped: durable persistence not available",
            ))

        no_fallback = durable_persistence_available and atomic_claims_available
        findings.append(_finding(
            "D.no_ram_fallback", "D_action_contract_persistence",
            "no fallback to RAM-only persistence or direct dispatch would be used",
            True, "PASS" if no_fallback else "FAIL",
            "both durable persistence and atomic claims are available" if no_fallback
            else "at least one dependency is unavailable — tma_api._queue_tma_write_approval "
                 "would refuse with HTTP 503 (correct fail-closed behavior, but not GO for cutover)",
        ))
    except Exception as exc:
        findings.append(_finding(
            "D.unexpected", "D_action_contract_persistence",
            "ActionContract persistence diagnostic ran without error", True, "FAIL",
            _safe_str(exc),
        ))
    return findings


def _check_action_contract_persistence_preflight() -> list[dict]:
    findings = []
    try:
        from core.action_contract_repository import ActionContractRepository
        repo = ActionContractRepository()
        repo.find_pending_by_canonical_user("__phase4b_readiness_probe__")
        findings.append(_finding(
            "D.repository_direct_reachable", "D_action_contract_persistence",
            "ActionContractRepository is directly reachable (independent of "
            "FEATURE_ACTION_CONTRACT_PERSISTENCE — proves the code path works before cutover)",
            True, "PASS",
        ))
    except Exception as exc:
        findings.append(_finding(
            "D.repository_direct_reachable", "D_action_contract_persistence",
            "ActionContractRepository is directly reachable (independent of "
            "FEATURE_ACTION_CONTRACT_PERSISTENCE — proves the code path works before cutover)",
            True, "FAIL", _safe_str(exc),
        ))
    return findings


# ══════════════════════════════════════════════════
# E — Airtable schema (live)
# ══════════════════════════════════════════════════

_EXPECTED_APPROVALS_PROJECTION_TYPES = {
    "action_contract_id": "singleLineText",
    "legacy_read_only": "checkbox",
    "projected_lifecycle_status": "singleSelect",
}

_ALL_E_CHECK_IDS = [
    ("E.action_contracts_exists", "ActionContracts table exists live"),
    ("E.approvals_exists", "Approvals table exists live"),
    ("E.approvals_projection_fields", "Approvals projection fields present with correct types"),
    ("E.projected_lifecycle_choices", "projected_lifecycle_status choices match exactly"),
    ("E.action_contracts_fields", "ActionContracts fields match ActionContractsFields (name)"),
    ("E.action_contracts_field_types", "ActionContracts fields match expected live field types"),
    ("E.action_contracts_status_choices", "ActionContracts status field singleSelect choices match exactly"),
]


def _check_airtable_schema() -> list[dict]:
    """Reuses tools.schema_snapshot.normalize_schema() — the same
    Meta-API-response parsing already centralized for PR3A's snapshot
    archive — instead of re-deriving field type/choice extraction here a
    second, potentially-incompatible way."""
    findings = []
    import os

    key = os.environ.get("AIRTABLE_API_KEY", "")
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    env_present = bool(key and base)
    findings.append(_finding(
        "E.env_present", "E_airtable_schema",
        "AIRTABLE_API_KEY / AIRTABLE_BASE_ID present", True,
        "PASS" if env_present else "FAIL",
        "present" if env_present else "missing",
    ))
    if not env_present:
        for check_id, desc in _ALL_E_CHECK_IDS:
            findings.append(_finding(check_id, "E_airtable_schema", desc, True, "SKIP",
                                      "skipped: Airtable credentials not present"))
        return findings

    fetch_error: str | None = None
    try:
        from tools.schema_snapshot import fetch_live_schema, normalize_schema
        raw = fetch_live_schema()
    except Exception as exc:
        raw = None
        fetch_error = _safe_str(exc)

    if raw is None:
        findings.append(_finding(
            "E.live_reachable", "E_airtable_schema", "live Meta API schema fetch reachable",
            True, "FAIL", fetch_error or "fetch_live_schema() returned None",
        ))
        for check_id, desc in _ALL_E_CHECK_IDS:
            findings.append(_finding(check_id, "E_airtable_schema", desc, True, "SKIP",
                                      "skipped: live schema unreachable"))
        return findings

    findings.append(_finding(
        "E.live_reachable", "E_airtable_schema", "live Meta API schema fetch reachable",
        True, "PASS",
    ))

    snapshot = normalize_schema(raw, base)
    tables_by_name = {t["table_name"]: t for t in snapshot["tables"]}

    ac_table = tables_by_name.get("ActionContracts")
    findings.append(_finding(
        "E.action_contracts_exists", "E_airtable_schema", "ActionContracts table exists live",
        True, "PASS" if ac_table else "FAIL",
        "" if ac_table else "'ActionContracts' not found in live base",
    ))

    approvals_table = tables_by_name.get("Approvals")
    findings.append(_finding(
        "E.approvals_exists", "E_airtable_schema", "Approvals table exists live",
        True, "PASS" if approvals_table else "FAIL",
        "" if approvals_table else "'Approvals' not found in live base",
    ))

    if approvals_table:
        fields_by_name = {f["field_name"]: f for f in approvals_table["fields"]}
        problems = []
        for fname, expected_type in _EXPECTED_APPROVALS_PROJECTION_TYPES.items():
            f = fields_by_name.get(fname)
            if f is None:
                problems.append(f"missing field '{fname}'")
            elif f["field_type"] != expected_type:
                problems.append(f"field '{fname}' has type {f['field_type']!r}, expected {expected_type!r}")
        findings.append(_finding(
            "E.approvals_projection_fields", "E_airtable_schema",
            "Approvals projection fields present with correct types", True,
            "PASS" if not problems else "FAIL", "; ".join(problems),
        ))

        status_field = fields_by_name.get("projected_lifecycle_status")
        if status_field is not None and status_field["field_type"] == "singleSelect":
            choices = set(status_field.get("choices") or [])
            matches = choices == _PROJECTED_LIFECYCLE_CHOICES
            findings.append(_finding(
                "E.projected_lifecycle_choices", "E_airtable_schema",
                "projected_lifecycle_status choices match exactly", True,
                "PASS" if matches else "FAIL",
                "" if matches else
                f"live={sorted(choices)} expected={sorted(_PROJECTED_LIFECYCLE_CHOICES)}",
            ))
        else:
            findings.append(_finding(
                "E.projected_lifecycle_choices", "E_airtable_schema",
                "projected_lifecycle_status choices match exactly", True, "FAIL",
                "field missing or not singleSelect — cannot compare choices",
            ))
    else:
        for check_id, desc in [
            ("E.approvals_projection_fields", "Approvals projection fields present with correct types"),
            ("E.projected_lifecycle_choices", "projected_lifecycle_status choices match exactly"),
        ]:
            findings.append(_finding(check_id, "E_airtable_schema", desc, True, "FAIL",
                                      "Approvals table missing live"))

    if ac_table:
        from tools.phase_4b_rollout_common import (
            ACTION_CONTRACTS_EXPECTED_TYPES, ACTION_CONTRACTS_STATUS_CHOICES,
        )
        ac_fields_by_name = {f["field_name"]: f for f in ac_table["fields"]}
        live_fields = set(ac_fields_by_name.keys())
        expected_fields = set(ACTION_CONTRACTS_EXPECTED_TYPES.keys())
        missing = expected_fields - live_fields
        findings.append(_finding(
            "E.action_contracts_fields", "E_airtable_schema",
            "ActionContracts fields match ActionContractsFields (name)", True,
            "PASS" if not missing else "FAIL",
            "" if not missing else f"missing live fields: {sorted(missing)}",
        ))

        type_problems = []
        for fname, expected_type in ACTION_CONTRACTS_EXPECTED_TYPES.items():
            f = ac_fields_by_name.get(fname)
            if f is None:
                continue  # already reported by E.action_contracts_fields above
            if f["field_type"] != expected_type:
                type_problems.append(
                    f"field '{fname}' has type {f['field_type']!r}, expected {expected_type!r}"
                )
        findings.append(_finding(
            "E.action_contracts_field_types", "E_airtable_schema",
            "ActionContracts fields match expected live field types", True,
            "PASS" if not type_problems else "FAIL", "; ".join(type_problems),
        ))

        status_field = ac_fields_by_name.get("status")
        if status_field is not None and status_field["field_type"] == "singleSelect":
            live_status_choices = set(status_field.get("choices") or [])
            matches = live_status_choices == ACTION_CONTRACTS_STATUS_CHOICES
            findings.append(_finding(
                "E.action_contracts_status_choices", "E_airtable_schema",
                "ActionContracts status field singleSelect choices match exactly", True,
                "PASS" if matches else "FAIL",
                "" if matches else
                f"live={sorted(live_status_choices)} expected={sorted(ACTION_CONTRACTS_STATUS_CHOICES)}",
            ))
        else:
            findings.append(_finding(
                "E.action_contracts_status_choices", "E_airtable_schema",
                "ActionContracts status field singleSelect choices match exactly", True, "FAIL",
                "status field missing or not singleSelect — cannot compare choices",
            ))
    else:
        for check_id, desc in [
            ("E.action_contracts_fields", "ActionContracts fields match ActionContractsFields (name)"),
            ("E.action_contracts_field_types", "ActionContracts fields match expected live field types"),
            ("E.action_contracts_status_choices", "ActionContracts status field singleSelect choices match exactly"),
        ]:
            findings.append(_finding(check_id, "E_airtable_schema", desc, True, "FAIL",
                                      "ActionContracts table missing live"))

    return findings


# ══════════════════════════════════════════════════
# F — Gateway / cache compatibility
# ══════════════════════════════════════════════════

def _check_gateway_cache_compat() -> list[dict]:
    findings = []
    try:
        cache_path = REPO_ROOT / "schema_cache.json"
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        approvals_fields = set(cache.get("tables", {}).get("Approvals", []))
        required = {"action_contract_id", "legacy_read_only", "projected_lifecycle_status"}
        missing = required - approvals_fields
        findings.append(_finding(
            "F.cache_has_projection_fields", "F_gateway_cache_compat",
            "schema_cache.json permits all three Approvals projection fields", True,
            "PASS" if not missing else "FAIL",
            "" if not missing else f"missing from schema_cache.json: {sorted(missing)}",
        ))

        action_contracts_in_cache = "ActionContracts" in cache.get("tables", {})
        findings.append(_finding(
            "F.action_contracts_in_cache", "F_gateway_cache_compat",
            "ActionContracts present in schema_cache.json seed (risk flag, non-mandatory)",
            False, "PASS" if action_contracts_in_cache else "WARN",
            "present" if action_contracts_in_cache else
            "ActionContracts is entirely absent from schema_cache.json — if "
            "FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE is ever 'enforce' and the live/"
            "snapshot tiers are both unavailable for this table, RuntimeSchemaProvider falls "
            "back to an empty seed field-set, and every ActionContracts write would have all "
            "its fields reported 'unknown' and dropped (SPEC A1 fail-closed block).",
        ))

        import feature_flags
        state = feature_flags.get_runtime_schema_provider_state()
        findings.append(_finding(
            "F.runtime_provider_state", "F_gateway_cache_compat",
            "RuntimeSchemaProvider state (informational)", False, "PASS", f"state={state}",
        ))

        if state == "off":
            findings.append(_finding(
                "F.validation_path_safe", "F_gateway_cache_compat",
                "the active schema-validation path will not drop the projection fields",
                True, "PASS" if not missing else "FAIL",
                "state=off uses schema_cache.json directly (see F.cache_has_projection_fields)",
            ))
        else:
            try:
                from core.runtime_schema_provider import RuntimeSchemaProvider
                provider = RuntimeSchemaProvider(ttl_seconds=0)
                contract = provider.get_table_contract("Approvals")
                known = set(contract.get("fields", {}).keys())
                still_missing = required - known
                findings.append(_finding(
                    "F.validation_path_safe", "F_gateway_cache_compat",
                    "the active schema-validation path will not drop the projection fields",
                    True, "PASS" if not still_missing else "FAIL",
                    f"provider source={contract.get('source')} mode={contract.get('mode')}"
                    + ("" if not still_missing else f" missing={sorted(still_missing)}"),
                ))
            except Exception as exc:
                findings.append(_finding(
                    "F.validation_path_safe", "F_gateway_cache_compat",
                    "the active schema-validation path will not drop the projection fields",
                    True, "FAIL", _safe_str(exc),
                ))
    except Exception as exc:
        findings.append(_finding(
            "F.unexpected", "F_gateway_cache_compat",
            "gateway/cache compatibility diagnostic ran without error", True, "FAIL",
            _safe_str(exc),
        ))
    return findings


# ══════════════════════════════════════════════════
# Orchestration
# ══════════════════════════════════════════════════

def run_readiness(mode: str = "preflight") -> dict:
    if mode not in ("preflight", "active"):
        raise ValueError(f"mode must be 'preflight' or 'active', got {mode!r}")

    findings: list[dict] = []
    findings += _check_code_state()
    findings += _check_feature_flags(mode)
    findings += _check_postgresql()
    findings += _check_action_contract_persistence(mode)
    findings += _check_airtable_schema()
    findings += _check_gateway_cache_compat()

    blocking = [f for f in findings if f["mandatory"] and f["status"] in ("FAIL", "SKIP")]
    warnings = [f for f in findings if f["status"] == "WARN"]

    if blocking:
        decision = "NO-GO"
        exit_code = 1
    elif warnings:
        decision = "WARNING"
        exit_code = 0
    else:
        decision = "GO"
        exit_code = 0

    return {
        "generated_at": utc_now_iso(),
        "git": git_state(),
        "mode": mode,
        "decision": decision,
        "exit_code": exit_code,
        "findings": findings,
        "blocking_findings": blocking,
        "warnings": warnings,
    }


def _print_human(result: dict) -> None:
    print("Phase 4B Rollout Readiness")
    print("=" * 60)
    print(f"generated_at: {result['generated_at']}")
    print(f"mode: {result['mode']}")
    print(f"git: commit={result['git']['commit_sha']} branch={result['git']['branch']}")
    print()
    for f in result["findings"]:
        marker = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "SKIP"}[f["status"]]
        tag = "mandatory" if f["mandatory"] else "info"
        print(f"  [{marker:4s}] ({tag:9s}) {f['id']}: {f['description']}")
        if f["detail"]:
            print(f"           {f['detail']}")
    print()
    print("=" * 60)
    print(f"DECISION: {result['decision']}")
    if result["blocking_findings"]:
        print(f"Blocking findings: {len(result['blocking_findings'])}")
    if result["warnings"]:
        print(f"Warnings: {len(result['warnings'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4B rollout readiness diagnostic (read-only)")
    parser.add_argument(
        "--mode", required=True, choices=["preflight", "active"],
        help=(
            "preflight: both flags may be OFF together — verifies infrastructure, migrations, "
            "database constraints, schema, and direct repository reachability, independent of "
            "flag state. active: both flags must be ON and the ActionGateway runtime "
            "repository/atomic-claim wiring must actually be active (post-cutover check)."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    args = parser.parse_args()

    try:
        result = run_readiness(mode=args.mode)
    except Exception as exc:
        err = {"decision": "UNKNOWN", "exit_code": 2, "error": _safe_str(exc)}
        print(json.dumps(err, indent=2), file=sys.stderr)
        dump_json_report(REPORT_PATH, err)
        return 2

    dump_json_report(REPORT_PATH, result)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_human(result)

    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
