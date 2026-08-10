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
]

# Run under `python -m pytest -q <file>` instead of `python <file>` — these
# two use pytest fixtures/parametrize with no `if __name__ == "__main__"`
# runner, so invoking them as plain scripts silently executes zero tests.
PYTEST_MODE_FILES: frozenset[str] = frozenset({
    "test_tc8_runtime_integration.py",
    "test_turn_state_repository.py",
})

# test_phase_4b0_1a_atomic_claims.py deliberately asserts the no-DB
# fail-closed path (FEATURE_ATOMIC_CLAIMS on + PostgreSQL unavailable ->
# RuntimeError at startup). Running it with a live DATABASE_URL flips that
# specific scenario and fails for the wrong reason. Matches the existing
# special-case in .github/workflows/ci.yml's "Run test_*.py scripts" step.
NO_DATABASE_URL_FILES: frozenset[str] = frozenset({
    "test_phase_4b0_1a_atomic_claims.py",
})
