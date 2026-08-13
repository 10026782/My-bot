# scripts/regression_matrix.py — TC10
#
# Single source of truth for the "full regression matrix" file lists that
# both the isolated-regression runner (scripts/run_isolated_regression.py)
# and the staging verifier (scripts/verify_tc8_staging.py) need to agree on.
# Previously these lists were duplicated inline in verify_tc8_staging.py;
# TC10 extracts them here so the two runners cannot silently drift apart.
#
# REGRESSION_GROUPS are the three named gates called out explicitly in the
# TC8 staging closure handoff (BUG-122 contamination note) and in TC10's own
# required-gates list: callback hardening, PR-0C callbacks, BUG-158 recovery.
# FULL_REGRESSION is the broader Turn Coordinator / ActionGateway regression
# surface that must run isolated, never against shared Airtable Staging.

from __future__ import annotations

REGRESSION_GROUPS: dict[str, str] = {
    "Callback hardening": "test_bug_approval_callback_hardening.py",
    "PR-0C callbacks": "test_pr0c_telegram_callback_gateway.py",
    "BUG-158 recovery": "test_bug158_approval_callback_eventbus_ttl_recovery.py",
}

FULL_REGRESSION: list[str] = [
    "test_turn_envelope.py",
    "test_approval_concurrency.py",
    "test_pr0c_action_contract_repository.py",
    "test_pr0c_action_contracts_persistence.py",
    "test_phase_4b0_1a_atomic_claims.py",
    "test_bug_approval_callback_hardening.py",
    "test_bug_stale_callback_ux.py",
    "test_bug_post_completion_callback_fallthrough.py",
    "test_hotfix_e_shared_replay_policy.py",
    "test_tc6_app_reply_ownership.py",
    "test_tc7_rp5_gateway_execution_shadow.py",
    "test_pr0c_telegram_callback_gateway.py",
    "test_bug127a_stale_lifecycle_version_retry.py",
    "test_bug157_atomic_fingerprint_claim.py",
    "test_bug158_approval_callback_eventbus_ttl_recovery.py",
    "test_single_speaker_fallback_and_duplication.py",
    "test_bug056_legacy_cancel_replay_guard.py",
    "test_pa01_phantom_approval_enforcement.py",
    "test_pr1_single_speaker_approval_ux.py",
    "test_tc8_runtime_integration.py",
    "test_turn_state_repository.py",
    "test_turn_coordinator_task_runtime_integration.py",
    "test_lane_a_status_routing.py",
    "test_bug070_pending_approval_multi.py",
    "test_phase_4b0_1b_concurrency.py",
    "test_c94_stage_c_telegram.py",
    "test_c94_stage_d_whatsapp.py",
    "test_bug112_telegram_approval_ttl.py",
    "core/router/test_entity_resolvers.py",
    "test_cmd_marketing_status.py",
    "test_marketing_orchestrator.py",
    "test_f14_b2_contact_integration.py",
    "test_turn_evidence_shadow.py",
]

SCENARIO_MATRIX: list[dict[str, str]] = [
    {"id": "R01", "category": "routing", "name": "create", "file": "test_turn_coordinator_task_runtime_integration.py"},
    {"id": "R02", "category": "routing", "name": "update", "file": "test_turn_coordinator_task_runtime_integration.py"},
    {"id": "R03", "category": "routing", "name": "complete", "file": "test_turn_coordinator_task_runtime_integration.py"},
    {"id": "R04", "category": "routing", "name": "unknown", "file": "test_lane_a_status_routing.py"},
    {"id": "R05", "category": "routing", "name": "clarification", "file": "test_bug070_pending_approval_multi.py"},
    {"id": "R06", "category": "routing", "name": "fallback", "file": "test_single_speaker_fallback_and_duplication.py"},
    {"id": "R07", "category": "resolution", "name": "0 matches", "file": "core/router/test_entity_resolvers.py"},
    {"id": "R08", "category": "resolution", "name": "1 match", "file": "test_turn_coordinator_task_runtime_integration.py"},
    {"id": "R09", "category": "resolution", "name": "many matches", "file": "test_turn_coordinator_task_runtime_integration.py"},
    {"id": "R10", "category": "approval", "name": "approve", "file": "test_phase_4b_1b_durable_lifecycle.py"},
    {"id": "R11", "category": "approval", "name": "reject", "file": "test_bug_approval_callback_hardening.py"},
    {"id": "R12", "category": "approval", "name": "cancel", "file": "test_bug056_legacy_cancel_replay_guard.py"},
    {"id": "R13", "category": "approval", "name": "TTL", "file": "test_bug112_telegram_approval_ttl.py"},
    {"id": "R14", "category": "approval", "name": "replay", "file": "test_hotfix_e_shared_replay_policy.py"},
    {"id": "R15", "category": "approval", "name": "duplicate", "file": "test_phase_4b0_1b_concurrency.py"},
    {"id": "R16", "category": "callbacks", "name": "valid", "file": "test_pr0c_telegram_callback_gateway.py"},
    {"id": "R17", "category": "callbacks", "name": "expired", "file": "test_bug_stale_callback_ux.py"},
    {"id": "R18", "category": "callbacks", "name": "replayed", "file": "test_hotfix_e_shared_replay_policy.py"},
    {"id": "R19", "category": "channels", "name": "Telegram", "file": "test_c94_stage_c_telegram.py"},
    {"id": "R20", "category": "channels", "name": "WhatsApp", "file": "test_c94_stage_d_whatsapp.py"},
    {"id": "R21", "category": "execution", "name": "idempotency", "file": "test_phase_4b0_1b_concurrency.py"},
    {"id": "R22", "category": "execution", "name": "claim ownership", "file": "test_phase_4b0_1a_atomic_claims.py"},
    {"id": "R23", "category": "execution", "name": "failure", "file": "test_turn_evidence_shadow.py"},
    {"id": "R24", "category": "marketing", "name": "authorized demand", "file": "test_cmd_marketing_status.py"},
    {"id": "R25", "category": "marketing", "name": "unauthorized demand", "file": "test_cmd_marketing_status.py"},
    {"id": "R26", "category": "marketing", "name": "one pending creative", "file": "test_marketing_orchestrator.py"},
    {"id": "R27", "category": "marketing", "name": "multiple inconsistent pending creatives", "file": "test_marketing_orchestrator.py"},
    {"id": "R28", "category": "marketing", "name": "Next Action", "file": "test_marketing_orchestrator.py"},
]

# Run under `python -m pytest -q <file>` instead of `python <file>` — these
# two use pytest fixtures/parametrize with no `if __name__ == "__main__"`
# runner, so invoking them as plain scripts silently executes zero tests.
PYTEST_MODE_FILES: frozenset[str] = frozenset({
    "test_tc8_runtime_integration.py",
    "test_turn_state_repository.py",
    "core/router/test_entity_resolvers.py",
})

# test_phase_4b0_1a_atomic_claims.py deliberately asserts the no-DB
# fail-closed path (FEATURE_ATOMIC_CLAIMS on + PostgreSQL unavailable ->
# RuntimeError at startup). Running it with a live DATABASE_URL flips that
# specific scenario and fails for the wrong reason. Matches the existing
# special-case in .github/workflows/ci.yml's "Run test_*.py scripts" step.
NO_DATABASE_URL_FILES: frozenset[str] = frozenset({
    "test_phase_4b0_1a_atomic_claims.py",
})
