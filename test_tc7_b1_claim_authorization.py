"""TC7-B1: focused tests for core/claim_authorization.py.

Plain-script style (no pytest harness in this repo, see CLAUDE.md) --
run directly: python3 test_tc7_b1_claim_authorization.py
"""

import ast

from core.claim_authorization import ClaimCategory, authorize_claim

_ALL_EVIDENCE_STATES = (
    "no_evidence",
    "verified_read_only",
    "verified_write_success",
    "failure",
    "outcome_unknown",
    "approval_pending",
    "unverified_effect",
    "mixed",
    "mixed_with_unknown",
)

# Required Blocker 2 table: evidence alone (no lifecycle).
_EXPECTED_EVIDENCE_ONLY = {
    "no_evidence": ClaimCategory.NEUTRAL,
    "verified_read_only": ClaimCategory.NEUTRAL,
    "verified_write_success": ClaimCategory.SUCCESS,
    "failure": ClaimCategory.FAILURE,
    "outcome_unknown": ClaimCategory.UNKNOWN,
    "approval_pending": ClaimCategory.PENDING,
    "unverified_effect": ClaimCategory.UNKNOWN,
    "mixed": ClaimCategory.MIXED,
    "mixed_with_unknown": ClaimCategory.MIXED,
}

_EXPECTED_FOR_COMPLETED = {
    "no_evidence": ClaimCategory.UNKNOWN,
    "verified_read_only": ClaimCategory.NEUTRAL,
    "verified_write_success": ClaimCategory.SUCCESS,
    "failure": ClaimCategory.FAILURE,
    "outcome_unknown": ClaimCategory.UNKNOWN,
    "approval_pending": ClaimCategory.UNKNOWN,  # conflict, not PENDING
    "unverified_effect": ClaimCategory.UNKNOWN,
    "mixed": ClaimCategory.MIXED,
    "mixed_with_unknown": ClaimCategory.MIXED,
}


# 1. all 9 evidence-only mappings with lifecycle=None
def test_all_9_evidence_only_mappings_with_no_lifecycle():
    for evidence in _ALL_EVIDENCE_STATES:
        state, _ = authorize_claim(evidence)
        assert state == _EXPECTED_EVIDENCE_ONLY[evidence], (evidence, state)
        state2, _ = authorize_claim(evidence, None)
        assert state2 == _EXPECTED_EVIDENCE_ONLY[evidence]


# 2. only verified_write_success -> SUCCESS
def test_only_verified_write_success_is_success():
    for evidence in _ALL_EVIDENCE_STATES:
        for lifecycle in (None, "completed", "executed"):
            state, _ = authorize_claim(evidence, lifecycle)
            if evidence == "verified_write_success" and lifecycle in (None, "completed", "executed"):
                assert state == ClaimCategory.SUCCESS, (evidence, lifecycle, state)
            else:
                assert state != ClaimCategory.SUCCESS, (evidence, lifecycle, state)


# 3. verified_read_only -> NEUTRAL
def test_verified_read_only_is_neutral():
    assert authorize_claim("verified_read_only") == (ClaimCategory.NEUTRAL, "verified_read_only")
    assert authorize_claim("verified_read_only", "completed") == (ClaimCategory.NEUTRAL, "verified_read_only")


def test_verified_read_only_never_authorizes_success():
    for lifecycle in (None, "completed", "executed", "pending", "approved", "executing", "failed", "rejected", "cancelled"):
        state, _ = authorize_claim("verified_read_only", lifecycle)
        assert state != ClaimCategory.SUCCESS, (lifecycle, state)


# 4. completed/executed + verified_write_success -> SUCCESS
def test_completed_and_executed_with_verified_write_success_is_success():
    for lifecycle in ("completed", "executed"):
        assert authorize_claim("verified_write_success", lifecycle) == (ClaimCategory.SUCCESS, None)


# 5. pending + failure does not resolve to PENDING
def test_pending_plus_failure_is_not_pending():
    state, reason = authorize_claim("failure", "pending")
    assert state != ClaimCategory.PENDING
    assert state == ClaimCategory.UNKNOWN
    assert reason == "conflict_incomplete_lifecycle_with_failure_evidence"


# 6. approved/executing + failure does not resolve to the in-progress baseline
def test_approved_and_executing_plus_failure_is_not_pending():
    for lifecycle in ("approved", "executing"):
        state, reason = authorize_claim("failure", lifecycle)
        assert state != ClaimCategory.PENDING, (lifecycle, state)
        assert state == ClaimCategory.UNKNOWN
        assert reason == "conflict_incomplete_lifecycle_with_failure_evidence"


# 7. completed + approval_pending is a conflict, not PENDING
def test_completed_plus_approval_pending_is_a_conflict():
    state, reason = authorize_claim("approval_pending", "completed")
    assert state != ClaimCategory.PENDING
    assert state == ClaimCategory.UNKNOWN
    assert reason == "conflict_completed_with_approval_pending"
    for lifecycle in ("completed", "executed"):
        state, _ = authorize_claim("approval_pending", lifecycle)
        assert state == ClaimCategory.UNKNOWN


# 8. unknown/unverified evidence cannot be hidden by optimistic lifecycle
def test_outcome_unknown_and_unverified_effect_never_hidden():
    for evidence in ("outcome_unknown", "unverified_effect"):
        for lifecycle in (None, "completed", "executed", "pending", "approved", "executing"):
            state, _ = authorize_claim(evidence, lifecycle)
            assert state == ClaimCategory.UNKNOWN, (evidence, lifecycle, state)
            assert state != ClaimCategory.SUCCESS
            assert state != ClaimCategory.PENDING


# additional explicit conflict cases from the review
def test_pending_approved_executing_plus_outcome_unknown_or_unverified_effect_conflicts():
    for lifecycle in ("pending", "approved", "executing"):
        for evidence in ("outcome_unknown", "unverified_effect"):
            state, reason = authorize_claim(evidence, lifecycle)
            assert state == ClaimCategory.UNKNOWN, (lifecycle, evidence, state)
            assert reason == "conflict_incomplete_lifecycle_with_uncertain_evidence"


def test_incomplete_lifecycle_plus_completed_shaped_evidence_conflicts():
    for lifecycle in ("pending", "approved", "executing"):
        for evidence in ("verified_write_success", "verified_read_only", "mixed", "mixed_with_unknown"):
            state, reason = authorize_claim(evidence, lifecycle)
            assert state != ClaimCategory.SUCCESS
            assert state == ClaimCategory.UNKNOWN, (lifecycle, evidence, state)
            assert reason == "conflict_incomplete_lifecycle_with_completed_evidence"


def test_incomplete_lifecycle_compatible_evidence_resolves_to_pending():
    assert authorize_claim("no_evidence", "pending") == (ClaimCategory.PENDING, "lifecycle_pending")
    assert authorize_claim("approval_pending", "pending") == (ClaimCategory.PENDING, "lifecycle_pending")
    for lifecycle in ("approved", "executing"):
        assert authorize_claim("no_evidence", lifecycle) == (ClaimCategory.PENDING, "lifecycle_in_progress")
        assert authorize_claim("approval_pending", lifecycle) == (ClaimCategory.PENDING, "lifecycle_in_progress")


# 9. rejected/cancelled cannot authorize SUCCESS
def test_rejected_and_cancelled_never_authorize_success():
    for lifecycle in ("rejected", "cancelled"):
        for evidence in _ALL_EVIDENCE_STATES:
            state, reason = authorize_claim(evidence, lifecycle)
            assert state == ClaimCategory.FAILURE, (lifecycle, evidence, state)
            assert reason == "lifecycle_terminal_non_success"


def test_failed_lifecycle_is_always_failure_regardless_of_evidence():
    for evidence in _ALL_EVIDENCE_STATES:
        state, reason = authorize_claim(evidence, "failed")
        assert state == ClaimCategory.FAILURE, (evidence, state)
        assert reason == "lifecycle_failed"


def test_missing_and_expired_lifecycle_fail_closed():
    for lifecycle in ("missing", "expired"):
        state, reason = authorize_claim("verified_write_success", lifecycle)
        assert state == ClaimCategory.UNKNOWN
        assert reason == "lifecycle_unresolved"


# 10. whitespace/case variants of lifecycle/evidence fail closed
def test_whitespace_and_case_variants_fail_closed():
    noncanonical_evidence = (" verified_write_success", "verified_write_success ", "VERIFIED_WRITE_SUCCESS", "Verified_Write_Success")
    for value in noncanonical_evidence:
        state, reason = authorize_claim(value, "completed")
        assert state != ClaimCategory.SUCCESS, value
        assert state == ClaimCategory.UNKNOWN
        assert reason == "unsupported_evidence_status"

    noncanonical_lifecycle = (" completed", "completed ", "COMPLETED", "Completed")
    for value in noncanonical_lifecycle:
        state, reason = authorize_claim("verified_write_success", value)
        assert state != ClaimCategory.SUCCESS, value
        assert state == ClaimCategory.UNKNOWN
        assert reason == "unsupported_lifecycle_state"


def test_unsupported_evidence_string_fails_closed():
    state, reason = authorize_claim("some_made_up_status", "completed")
    assert state == ClaimCategory.UNKNOWN
    assert reason == "unsupported_evidence_status"
    state, reason = authorize_claim("some_made_up_status")
    assert state == ClaimCategory.UNKNOWN
    assert reason == "unsupported_evidence_status"


def test_unsupported_lifecycle_string_fails_closed():
    state, reason = authorize_claim("verified_write_success", "some_made_up_lifecycle")
    assert state == ClaimCategory.UNKNOWN
    assert reason == "unsupported_lifecycle_state"


def test_none_and_missing_values_fail_closed():
    assert authorize_claim(None, None) == (ClaimCategory.UNKNOWN, "unsupported_evidence_status")
    assert authorize_claim(None, "completed")[0] != ClaimCategory.SUCCESS
    assert authorize_claim("verified_write_success", None)[0] == ClaimCategory.SUCCESS  # lifecycle genuinely optional


# 11. no MessageState/MessageContract production dependency
def test_no_message_contract_or_message_state_dependency():
    with open("core/claim_authorization.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert imported_modules == {"__future__", "enum"}, imported_modules
    assert "message_contract" not in " ".join(imported_modules)


def test_no_raw_dispatcher_provider_or_text_parsing_imports():
    with open("core/claim_authorization.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    banned_substrings = ("dispatcher", "provider", "re", "regex", "action_gateway", "turn_evidence", "app")
    for module in imported_modules:
        for banned in banned_substrings:
            assert banned not in module.split("."), (module, banned)


def test_no_private_f52_tc9_helper_imports():
    with open("core/claim_authorization.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    forbidden = {
        "_state_from_lifecycle", "_lifecycle_projection",
        "_VERIFIED_SUCCESS_EVIDENCE", "_COMPLETED_EVIDENCE_STATES",
        "from_action_lifecycle_result", "lifecycle_message_adapter",
        "MessageState", "MessageContract", "message_contract",
    }
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.add(node.module or "")
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
    assert not (imported_names & forbidden), imported_names & forbidden


# 12. no runtime wiring
def test_no_runtime_wiring():
    with open("core/claim_authorization.py", "r", encoding="utf-8") as f:
        source = f.read()
    for forbidden in ("app.py", "action_gateway", "dispatch_tool", "run_agent"):
        assert forbidden not in source, forbidden


# 13. no new feature flag
def test_no_new_feature_flag():
    with open("core/claim_authorization.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "feature_flags" not in source
    assert "FEATURE_" not in source


def test_claim_category_enum_is_the_required_six_values():
    assert {member.value for member in ClaimCategory} == {
        "neutral", "success", "failure", "unknown", "pending", "mixed",
    }


def _run_all():
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    _run_all()
