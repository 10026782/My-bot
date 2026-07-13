"""Phase 4B rollout tooling — readiness, reconciliation, legacy marking,
projection repair (tools/phase_4b_rollout_readiness.py,
tools/phase_4b_reconciliation.py, tools/phase_4b_mark_legacy_approvals.py,
tools/phase_4b_repair_projections.py).

All four tools are report-only by default; these tests assert that
guarantee directly (mocked Airtable/PostgreSQL writers are never invoked
unless a test explicitly passes --apply + the exact confirmation token).
"""

from __future__ import annotations

import io
import json
import time
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from core.action_gateway import ActionContract
from airtable_schema import ApprovalsFields

import tools.phase_4b_reconciliation as recon_mod
import tools.phase_4b_mark_legacy_approvals as legacy_mod
import tools.phase_4b_repair_projections as repair_mod
import tools.phase_4b_rollout_readiness as readiness_mod


# ══════════════════════════════════════════════════
# Shared fixtures
# ══════════════════════════════════════════════════

def _contract(contract_id, *, status="pending", tool_name="tma_write",
              trusted_source="tma_api", origin_channel="tma",
              approval_policy="approval", tenant_id="boss_hq",
              fingerprint=None, created_at=None) -> ActionContract:
    return ActionContract(
        contract_id=contract_id,
        tenant_id=tenant_id,
        canonical_user_id=f"{tenant_id}:owner",
        tool_name=tool_name,
        normalized_payload={"action": "tma_create_lead_task"},
        business_action_fingerprint=fingerprint or f"fp-{contract_id}",
        origin_channel=origin_channel,
        origin_chat_id="chat-1",
        requires_approval=True,
        status=status,
        created_at=created_at if created_at is not None else time.time(),
        actor_display_name="Owner One",
        actor_user_id="owner-1",
        approval_policy=approval_policy,
        trusted_source=trusted_source,
    )


def _row(record_id, *, action_contract_id="", legacy_read_only=False,
         projected_status=None, context_data=""):
    fields = {
        ApprovalsFields.ACTION_CONTRACT_ID: action_contract_id,
        ApprovalsFields.LEGACY_READ_ONLY: legacy_read_only,
        ApprovalsFields.CONTEXT_DATA: context_data,
    }
    if projected_status is not None:
        fields[ApprovalsFields.PROJECTED_LIFECYCLE_STATUS] = projected_status
    return {"id": record_id, "fields": fields}


def _clean_row(record_id, contract: ActionContract):
    from core.approvals_projection import project_lifecycle_status
    return _row(
        record_id, action_contract_id=contract.contract_id, legacy_read_only=False,
        projected_status=project_lifecycle_status(contract.status), context_data="",
    )


# ══════════════════════════════════════════════════
# Reconciliation — one combined dataset exercising all 15 checks
# ══════════════════════════════════════════════════

def _build_reconciliation_fixture():
    contracts = []
    rows = []
    claims = []

    ct_r1 = _contract("ct-r1")  # canonical pending, no row -> R1
    contracts.append(ct_r1)

    ct_r3 = _contract("ct-r3")  # canonical pending, 2 rows -> R3
    contracts.append(ct_r3)
    rows.append(_clean_row("rowA-r3", ct_r3))
    rows.append(_clean_row("rowB-r3", ct_r3))

    rows.append(_row("row-r2", action_contract_id="cid-does-not-exist",
                      projected_status="pending", context_data=""))  # -> R2

    ct_r4 = _contract("ct-r4")  # projected status wrong -> R4
    contracts.append(ct_r4)
    rows.append(_row("row-r4", action_contract_id=ct_r4.contract_id,
                      projected_status="approved", context_data=""))

    ct_r5 = _contract("ct-r5")  # non-empty CONTEXT_DATA -> R5
    contracts.append(ct_r5)
    rows.append(_row("row-r5", action_contract_id=ct_r5.contract_id,
                      projected_status="pending", context_data='{"leftover": true}'))

    ct_r6 = _contract("ct-r6")  # contract-linked but legacy_read_only=True -> R6
    contracts.append(ct_r6)
    rows.append(_row("row-r6", action_contract_id=ct_r6.contract_id,
                      legacy_read_only=True, projected_status="pending", context_data=""))

    rows.append(_row("row-r7", action_contract_id="", legacy_read_only=False))  # -> R7

    ct_r8 = _contract("ct-r8")  # missing projected_lifecycle_status -> R8
    contracts.append(ct_r8)
    rows.append(_row("row-r8", action_contract_id=ct_r8.contract_id,
                      projected_status=None, context_data=""))

    ct_r9 = _contract("ct-r9", tool_name="gmail_send_draft", trusted_source="agent",
                       origin_channel="telegram", approval_policy="approval")  # non-canonical
    contracts.append(ct_r9)
    rows.append(_row("row-r9", action_contract_id=ct_r9.contract_id,
                      projected_status="pending", context_data=""))  # -> R9

    ct_r10a = _contract("ct-r10a", tool_name="airtable_add", trusted_source="agent",
                         origin_channel="telegram", tenant_id="boss_hq", fingerprint="fp-shared-tenant")
    ct_r10b = _contract("ct-r10b", tool_name="airtable_add", trusted_source="agent",
                         origin_channel="telegram", tenant_id="other_tenant", fingerprint="fp-shared-tenant")
    contracts += [ct_r10a, ct_r10b]  # -> R10 (same fingerprint, different tenant_id)

    ct_r11 = _contract("ct-r11", status="completed")  # terminal but row still "pending" -> R11
    contracts.append(ct_r11)
    rows.append(_row("row-r11", action_contract_id=ct_r11.contract_id,
                      projected_status="pending", context_data=""))

    ct_claims_base = _contract("ct-claims-base")
    contracts.append(ct_claims_base)
    rows.append(_clean_row("row-claims-base", ct_claims_base))
    claims.append({
        "contract_id": ct_claims_base.contract_id, "claimant_id": "owner-1",
        "execution_id": "exec-1", "status": "outcome_unknown",
        "claimed_at": time.time(), "completed_at": None,
        "idempotency_key": "idem-1", "last_error": "ambiguous",
    })  # -> R12

    ct_claims_stuck = _contract("ct-claims-stuck")
    contracts.append(ct_claims_stuck)
    rows.append(_clean_row("row-claims-stuck", ct_claims_stuck))
    claims.append({
        "contract_id": ct_claims_stuck.contract_id, "claimant_id": "owner-1",
        "execution_id": "exec-stuck", "status": "executing",
        "claimed_at": time.time() - 7200, "completed_at": None,
        "idempotency_key": "idem-stuck", "last_error": None,
    })  # -> R12 (stuck executing)

    claims.append({
        "contract_id": "cid-orphan-claim", "claimant_id": "owner-1",
        "execution_id": "exec-2", "status": "executing",
        "claimed_at": time.time(), "completed_at": None,
        "idempotency_key": "idem-2", "last_error": None,
    })  # -> R13

    ct_r14 = _contract("ct-r14", status="completed")
    contracts.append(ct_r14)
    rows.append(_clean_row("row-r14", ct_r14))
    claims.append({
        "contract_id": ct_r14.contract_id, "claimant_id": "owner-1",
        "execution_id": "exec-3", "status": "failed",
        "claimed_at": time.time() - 10, "completed_at": time.time(),
        "idempotency_key": "idem-3", "last_error": "provider write failed",
    })  # -> R14

    ct_r15a = _contract("ct-r15a", tool_name="airtable_add", trusted_source="agent",
                         origin_channel="telegram", fingerprint="fp-shared-active")
    ct_r15b = _contract("ct-r15b", tool_name="airtable_add", trusted_source="agent",
                         origin_channel="telegram", fingerprint="fp-shared-active")
    contracts += [ct_r15a, ct_r15b]
    claims.append({
        "contract_id": ct_r15a.contract_id, "claimant_id": "owner-1",
        "execution_id": "exec-4a", "status": "executing",
        "claimed_at": time.time(), "completed_at": None,
        "idempotency_key": "idem-4a", "last_error": None,
    })
    claims.append({
        "contract_id": ct_r15b.contract_id, "claimant_id": "owner-1",
        "execution_id": "exec-4b", "status": "executing",
        "claimed_at": time.time(), "completed_at": None,
        "idempotency_key": "idem-4b", "last_error": None,
    })  # -> R15

    contracts_raw = [(c, f"rec-{c.contract_id}") for c in contracts]
    return contracts_raw, rows, claims


def test_reconciliation_detects_every_listed_anomaly():
    contracts_raw, rows, claims = _build_reconciliation_fixture()
    with patch.object(recon_mod, "fetch_all_action_contracts", return_value=contracts_raw), \
         patch.object(recon_mod, "fetch_all_approvals", return_value=rows), \
         patch.object(recon_mod, "fetch_all_claims", return_value=claims):
        result = recon_mod.run_reconciliation()

    by_id = {f["check_id"]: f for f in result["findings"]}

    assert by_id["R1_contract_missing_projection"]["items"] == ["ct-r1"]
    assert by_id["R2_orphaned_projection"]["items"] == ["row-r2"]
    assert set(by_id["R3_duplicate_projection"]["items"]) == {"ct-r3"}
    assert "row-r4" in by_id["R4_status_mismatch"]["items"]
    assert by_id["R5_nonempty_context_data"]["items"] == ["row-r5"]
    assert by_id["R6_contract_linked_marked_legacy"]["items"] == ["row-r6"]
    assert by_id["R7_unmarked_legacy_row"]["items"] == ["row-r7"]
    assert by_id["R8_missing_projected_status"]["items"] == ["row-r8"]
    assert by_id["R9_non_tma_contract_exposed"]["items"] == ["row-r9"]
    assert set(by_id["R10_cross_tenant_mismatch"]["items"]) == {"ct-r10a", "ct-r10b"}
    assert "row-r11" in by_id["R11_stale_pending_projection"]["items"]
    assert set(by_id["R12_claims_needing_manual_attention"]["items"]) == {
        "ct-claims-base", "ct-claims-stuck",
    }
    assert by_id["R13_orphaned_claim"]["items"] == ["cid-orphan-claim"]
    assert by_id["R14_completed_contract_claim_mismatch"]["items"] == ["ct-r14"]
    assert set(by_id["R15_duplicate_active_ownership"]["items"]) == {"ct-r15a", "ct-r15b"}

    assert result["rollout_target_met"] is False
    assert len(result["blocking_findings"]) == 15


def test_reconciliation_clean_state_is_zero_findings():
    ct = _contract("ct-clean")
    contracts_raw = [(ct, "rec-ct-clean")]
    rows = [_clean_row("row-clean", ct)]
    claims = []
    with patch.object(recon_mod, "fetch_all_action_contracts", return_value=contracts_raw), \
         patch.object(recon_mod, "fetch_all_approvals", return_value=rows), \
         patch.object(recon_mod, "fetch_all_claims", return_value=claims):
        result = recon_mod.run_reconciliation()

    assert result["blocking_findings"] == []
    assert result["rollout_target_met"] is True


def test_reconciliation_performs_zero_writes():
    """The reconciliation tool has no write path at all — assert it never
    even imports a mutation-capable helper."""
    import inspect
    source = inspect.getsource(recon_mod)
    for forbidden in ("airtable_patch", "airtable_create", "airtable_delete",
                      "dispatch_tool", "claim_contract_execution", ".approve(", ".reject("):
        assert forbidden not in source, f"reconciliation tool must never reference {forbidden!r}"


def test_reconciliation_json_report_deterministic_and_machine_readable():
    ct = _contract("ct-det")
    contracts_raw = [(ct, "rec-ct-det")]
    rows = [_clean_row("row-det", ct)]
    with patch.object(recon_mod, "fetch_all_action_contracts", return_value=contracts_raw), \
         patch.object(recon_mod, "fetch_all_approvals", return_value=rows), \
         patch.object(recon_mod, "fetch_all_claims", return_value=[]):
        result1 = recon_mod.run_reconciliation()
        result2 = recon_mod.run_reconciliation()

    def _strip_volatile(d):
        d = dict(d)
        d.pop("generated_at", None)
        return d

    blob1 = json.dumps(_strip_volatile(result1), sort_keys=True)
    blob2 = json.dumps(_strip_volatile(result2), sort_keys=True)
    assert blob1 == blob2

    # Machine-readable: round-trips cleanly.
    assert json.loads(json.dumps(result1)) == result1


# ══════════════════════════════════════════════════
# Legacy marking tool
# ══════════════════════════════════════════════════

def test_legacy_tool_defaults_to_report_only():
    rows = [
        _row("row-legacy-1", action_contract_id="", legacy_read_only=False),
        _row("row-legacy-2", action_contract_id="ct-1", legacy_read_only=False),
    ]
    with patch.object(legacy_mod, "fetch_all_approvals", return_value=rows), \
         patch("tools.airtable_gateway.airtable_patch") as mock_patch:
        result = legacy_mod.run(apply=False, confirm=None)

    assert result["mode"] == "report-only"
    assert result["candidate_record_ids"] == ["row-legacy-1"]
    assert result["applied_record_ids"] == []
    mock_patch.assert_not_called()


def test_legacy_apply_without_confirm_token_performs_zero_writes():
    rows = [_row("row-legacy-1", action_contract_id="", legacy_read_only=False)]
    with patch.object(legacy_mod, "fetch_all_approvals", return_value=rows), \
         patch("tools.airtable_gateway.airtable_patch") as mock_patch:
        result = legacy_mod.run(apply=True, confirm=None)
        result_wrong_token = legacy_mod.run(apply=True, confirm="not-the-token")

    assert result["mode"] == "report-only"
    assert "refused_reason" in result
    assert result_wrong_token["mode"] == "report-only"
    mock_patch.assert_not_called()


def test_legacy_apply_changes_only_legacy_read_only_field():
    rows = [
        _row("row-legacy-1", action_contract_id="", legacy_read_only=False),
        _row("row-already-marked", action_contract_id="", legacy_read_only=True),
        _row("row-contract-linked", action_contract_id="ct-1", legacy_read_only=False),
    ]
    with patch.object(legacy_mod, "fetch_all_approvals", return_value=rows), \
         patch("tools.airtable_gateway.airtable_patch", return_value=True) as mock_patch:
        result = legacy_mod.run(apply=True, confirm="APPLY_LEGACY_READ_ONLY")

    assert result["mode"] == "apply"
    assert result["applied_record_ids"] == ["row-legacy-1"]
    mock_patch.assert_called_once_with(
        "Approvals", "row-legacy-1", {ApprovalsFields.LEGACY_READ_ONLY: True},
        source="phase_4b_mark_legacy_approvals",
    )


def test_legacy_apply_is_idempotent_on_second_run():
    rows = [_row("row-legacy-1", action_contract_id="", legacy_read_only=True)]
    with patch.object(legacy_mod, "fetch_all_approvals", return_value=rows), \
         patch("tools.airtable_gateway.airtable_patch") as mock_patch:
        result = legacy_mod.run(apply=True, confirm="APPLY_LEGACY_READ_ONLY")

    assert result["candidate_record_ids"] == []
    mock_patch.assert_not_called()


# ══════════════════════════════════════════════════
# Projection repair tool
# ══════════════════════════════════════════════════

def test_repair_tool_defaults_to_report_only_and_performs_no_execution():
    ct = _contract("ct-repair-1")
    contracts_raw = [(ct, "rec-ct-repair-1")]
    rows = []  # missing projection candidate
    with patch.object(repair_mod, "fetch_all_action_contracts", return_value=contracts_raw), \
         patch.object(repair_mod, "fetch_all_approvals", return_value=rows), \
         patch("tools.airtable_gateway.airtable_create") as mock_create, \
         patch("tools.airtable_gateway.airtable_patch") as mock_patch:
        result = repair_mod.run(apply=False, confirm=None)

    assert result["mode"] == "report-only"
    assert len(result["plan"]["create_projection"]) == 1
    assert result["plan"]["create_projection"][0]["contract_id"] == "ct-repair-1"
    mock_create.assert_not_called()
    mock_patch.assert_not_called()


def test_repair_tool_never_touches_execution_or_lifecycle_apis():
    """Scan actual code lines only (skip comments/docstrings, which
    legitimately describe what must NOT happen) for a real import or call of
    any execution/lifecycle API."""
    import inspect
    source = inspect.getsource(repair_mod)
    code_lines = [
        line for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    code_only = "\n".join(code_lines)
    for forbidden in ("import dispatch_tool", "dispatch_tool(", "claim_contract_execution(",
                      ".approve(", ".reject(", "import action_gateway"):
        assert forbidden not in code_only, f"repair tool must never reference {forbidden!r}"


def test_repair_tool_never_auto_repairs_outcome_unknown():
    ct = _contract("ct-outcome-unknown", status="outcome_unknown")
    contracts_raw = [(ct, "rec-1")]
    rows = [_row("row-ou", action_contract_id=ct.contract_id,
                  projected_status="pending", context_data="")]
    with patch.object(repair_mod, "fetch_all_action_contracts", return_value=contracts_raw), \
         patch.object(repair_mod, "fetch_all_approvals", return_value=rows):
        result = repair_mod.run(apply=False, confirm=None)

    assert result["plan"]["skipped_outcome_unknown"] == ["row-ou"]
    assert result["plan"]["set_projected_status"] == []


def test_repair_apply_requires_both_flag_and_confirm_token():
    ct = _contract("ct-repair-2")
    contracts_raw = [(ct, "rec-1")]
    with patch.object(repair_mod, "fetch_all_action_contracts", return_value=contracts_raw), \
         patch.object(repair_mod, "fetch_all_approvals", return_value=[]), \
         patch("tools.airtable_gateway.airtable_create") as mock_create:
        result = repair_mod.run(apply=True, confirm="wrong-token")

    assert result["mode"] == "report-only"
    assert "refused_reason" in result
    mock_create.assert_not_called()


# ══════════════════════════════════════════════════
# Readiness tool
# ══════════════════════════════════════════════════

class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._last_sql = sql
        self._last_params = params
        if "INSERT INTO action_execution_claims" in sql:
            self._conn.inserted.append(params[0])

    def fetchone(self):
        sql = self._last_sql
        if sql.strip().startswith("SELECT 1;"):
            return (1,)
        if "information_schema.tables" in sql:
            return (self._conn.table_exists,)
        if "action_execution_claims WHERE contract_id" in sql:
            probe_id = self._last_params[0]
            return (1,) if probe_id in self._conn.leaked_ids else None
        return None

    def fetchall(self):
        sql = self._last_sql
        if "information_schema.columns" in sql:
            return [(c,) for c in self._conn.columns]
        if "table_constraints" in sql:
            return self._conn.constraints
        return []


class _FakeConn:
    def __init__(self, table_exists=True, columns=None, constraints=None, leaked_ids=None):
        self.table_exists = table_exists
        self.columns = columns if columns is not None else [
            "contract_id", "claimant_id", "execution_id", "status", "claimed_at",
            "completed_at", "idempotency_key", "last_error", "created_at", "updated_at",
        ]
        self.constraints = constraints if constraints is not None else [
            ("PRIMARY KEY", "contract_id"), ("UNIQUE", "idempotency_key"),
        ]
        self.leaked_ids = leaked_ids or set()
        self.inserted = []

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass


def _live_meta_schema():
    from airtable_schema import ActionContractsFields
    approvals_fields = [
        {"name": "action_contract_id", "type": "singleLineText"},
        {"name": "legacy_read_only", "type": "checkbox"},
        {"name": "projected_lifecycle_status", "type": "singleSelect", "options": {"choices": [
            {"name": n} for n in (
                "pending", "approved", "rejected", "executing", "completed",
                "failed", "outcome_unknown", "superseded", "legacy",
            )
        ]}},
    ]
    action_contracts_fields = [
        {"name": v, "type": "singleLineText"}
        for k, v in vars(ActionContractsFields).items()
        if not k.startswith("_") and isinstance(v, str)
    ]
    return {"tables": [
        {"name": "Approvals", "fields": approvals_fields},
        {"name": "ActionContracts", "fields": action_contracts_fields},
    ]}


def _run_readiness_with_mocks(*, acp_enabled, atc_enabled, pool_ok, claims_table_ok=True,
                               claims_columns=None, claims_constraints=None,
                               live_schema=None, env=None):
    env = dict(env or {})
    env.setdefault("AIRTABLE_API_KEY", "fake-key")
    env.setdefault("AIRTABLE_BASE_ID", "fake-base")
    if pool_ok:
        env.setdefault("DATABASE_URL", "postgresql://user:pass@host/db")

    fake_conn = _FakeConn(table_exists=claims_table_ok, columns=claims_columns,
                          constraints=claims_constraints)
    fake_pool = MagicMock() if pool_ok else None

    def _is_enabled(name):
        if name == "FEATURE_ACTION_CONTRACT_PERSISTENCE":
            return acp_enabled
        if name == "FEATURE_ATOMIC_CLAIMS":
            return atc_enabled
        return False

    fake_repo = MagicMock()
    fake_repo.find_pending_by_canonical_user.return_value = []

    import feature_flags
    import core.database as db_mod
    from core.action_gateway import action_gateway as real_gateway

    original_repository = real_gateway._ledger._repository
    try:
        with patch.dict("os.environ", env, clear=False), \
             patch.object(feature_flags, "is_enabled", side_effect=_is_enabled), \
             patch.object(db_mod, "get_pool", return_value=fake_pool), \
             patch.object(db_mod, "get_conn", return_value=(fake_conn if pool_ok else None)), \
             patch.object(db_mod, "release_conn"), \
             patch("tools.schema_snapshot.fetch_live_schema",
                   return_value=(live_schema if live_schema is not None else _live_meta_schema())):
            real_gateway._ledger._repository = fake_repo if acp_enabled else None
            return readiness_mod.run_readiness()
    finally:
        real_gateway._ledger._repository = original_repository


def test_readiness_go_with_all_dependencies_available():
    result = _run_readiness_with_mocks(acp_enabled=True, atc_enabled=True, pool_ok=True)
    assert result["decision"] in ("GO", "WARNING")
    blocking_ids = {f["id"] for f in result["blocking_findings"]}
    assert blocking_ids == set()


def test_readiness_no_go_when_postgresql_unavailable():
    result = _run_readiness_with_mocks(acp_enabled=True, atc_enabled=True, pool_ok=False)
    assert result["decision"] == "NO-GO"
    ids = {f["id"] for f in result["blocking_findings"]}
    assert "C.pool" in ids or "C.env_present" in ids
    assert "D.atomic_claims_available" in ids


def test_readiness_no_go_when_only_one_flag_enabled():
    result = _run_readiness_with_mocks(acp_enabled=True, atc_enabled=False, pool_ok=True)
    assert result["decision"] == "NO-GO"
    ids = {f["id"] for f in result["blocking_findings"]}
    assert "B.no_mismatched_flags" in ids


def test_readiness_no_go_when_claims_table_missing():
    result = _run_readiness_with_mocks(acp_enabled=True, atc_enabled=True, pool_ok=True,
                                        claims_table_ok=False)
    assert result["decision"] == "NO-GO"
    ids = {f["id"] for f in result["blocking_findings"]}
    assert "C.table_exists" in ids


def test_readiness_no_go_when_claims_constraints_missing():
    result = _run_readiness_with_mocks(
        acp_enabled=True, atc_enabled=True, pool_ok=True,
        claims_constraints=[],  # no PK, no UNIQUE
    )
    assert result["decision"] == "NO-GO"
    ids = {f["id"] for f in result["blocking_findings"]}
    assert "C.pk" in ids
    assert "C.unique_idem" in ids


def test_readiness_no_go_when_claims_columns_missing():
    result = _run_readiness_with_mocks(
        acp_enabled=True, atc_enabled=True, pool_ok=True,
        claims_columns=["contract_id", "status"],  # missing most required columns
    )
    assert result["decision"] == "NO-GO"
    ids = {f["id"] for f in result["blocking_findings"]}
    assert "C.columns" in ids


def test_readiness_detects_approvals_schema_drift():
    schema = _live_meta_schema()
    # Corrupt the projected_lifecycle_status choices to simulate live drift.
    for table in schema["tables"]:
        if table["name"] == "Approvals":
            for f in table["fields"]:
                if f["name"] == "projected_lifecycle_status":
                    f["options"]["choices"] = [{"name": "pending"}, {"name": "approved"}]
    result = _run_readiness_with_mocks(acp_enabled=True, atc_enabled=True, pool_ok=True,
                                        live_schema=schema)
    ids = {f["id"] for f in result["blocking_findings"]}
    assert "E.projected_lifecycle_choices" in ids


def test_readiness_detects_action_contracts_schema_drift():
    schema = _live_meta_schema()
    for table in schema["tables"]:
        if table["name"] == "ActionContracts":
            table["fields"] = [f for f in table["fields"] if f["name"] != "idempotency_key"]
    result = _run_readiness_with_mocks(acp_enabled=True, atc_enabled=True, pool_ok=True,
                                        live_schema=schema)
    ids = {f["id"] for f in result["blocking_findings"]}
    assert "E.action_contracts_fields" in ids


def test_readiness_never_logs_secret_values():
    secret_key = "SECRET_MARKER_AIRTABLE_KEY_abc123"
    secret_pw = "SECRET_MARKER_DB_PASSWORD_xyz789"
    result = _run_readiness_with_mocks(
        acp_enabled=True, atc_enabled=True, pool_ok=True,
        env={"AIRTABLE_API_KEY": secret_key,
             "DATABASE_URL": f"postgresql://user:{secret_pw}@host/db"},
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        readiness_mod._print_human(result)
    blob = json.dumps(result) + buf.getvalue()
    assert secret_key not in blob
    assert secret_pw not in blob


def test_readiness_json_report_deterministic_and_machine_readable():
    result1 = _run_readiness_with_mocks(acp_enabled=True, atc_enabled=True, pool_ok=True)
    result2 = _run_readiness_with_mocks(acp_enabled=True, atc_enabled=True, pool_ok=True)

    def _strip_volatile(d):
        d = dict(d)
        d.pop("generated_at", None)
        return d

    assert json.dumps(_strip_volatile(result1), sort_keys=True) == \
        json.dumps(_strip_volatile(result2), sort_keys=True)
    assert json.loads(json.dumps(result1)) == result1


def test_no_tool_source_contains_direct_secret_interpolation():
    """Static guard: none of the 4 tools should ever f-string/format a raw
    secret env var (API keys, DB passwords/URLs) directly into a print/log
    call. Presence checks (bool(key)) and passing the value to a library
    call (headers=..., psycopg2 dsn=...) are fine and excluded."""
    import inspect
    modules = [readiness_mod, recon_mod, legacy_mod, repair_mod]
    forbidden_patterns = ["f\"{key}\"", "f'{key}'", "print(key)", "print(base)",
                          "logger.info(key)", "logger.info(base)"]
    for mod in modules:
        source = inspect.getsource(mod)
        for pattern in forbidden_patterns:
            assert pattern not in source, f"{mod.__name__} contains suspicious secret usage: {pattern}"


# ══════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [v for n, v in list(globals().items()) if n.startswith("test_") and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"FAIL {test.__name__}: {type(exc).__name__}: {exc}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {len(tests)}")
    if failed:
        raise SystemExit(1)
