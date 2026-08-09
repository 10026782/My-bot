"""TC7-B1: focused tests for core/claim_authorization.py.

Plain-script style (no pytest harness in this repo, see CLAUDE.md) --
run directly: python3 test_tc7_b1_claim_authorization.py
"""

import ast

from core.claim_authorization import authorize_claim
from core.message_contract import MessageState

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

_EXPECTED_FOR_COMPLETED = {
    "verified_write_success": MessageState.SUCCESS,
    "verified_read_only": MessageState.NEUTRAL,
    "failure": MessageState.FAILURE,
    "outcome_unknown": MessageState.OUTCOME_UNKNOWN,
    "approval_pending": MessageState.APPROVAL_PENDING,
    "unverified_effect": MessageState.UNVERIFIED_EFFECT,
    "mixed": MessageState.MIXED,
    "mixed_with_unknown": MessageState.MIXED_WITH_UNKNOWN,
    "no_evidence": MessageState.OUTCOME_UNKNOWN,
}


def test_all_9_evidence_states_resolve_for_completed_and_executed():
    for lifecycle in ("completed", "executed"):
        for evidence in _ALL_EVIDENCE_STATES:
            state, _ = authorize_claim(evidence, lifecycle)
            assert state == _EXPECTED_FOR_COMPLETED[evidence], (lifecycle, evidence, state)


def test_verified_write_success_is_success():
    assert authorize_claim("verified_write_success", "completed") == (MessageState.SUCCESS, None)


def test_verified_read_only_is_neutral():
    state, reason = authorize_claim("verified_read_only", "completed")
    assert state == MessageState.NEUTRAL
    assert reason == "verified_read_only"


def test_verified_read_only_never_authorizes_success():
    for lifecycle in ("completed", "executed", "pending", "approved", "executing", "failed", "rejected", "cancelled"):
        state, _ = authorize_claim("verified_read_only", lifecycle)
        assert state != MessageState.SUCCESS, (lifecycle, state)


def test_failure_beats_optimistic_lifecycle():
    state, _ = authorize_claim("failure", "completed")
    assert state == MessageState.FAILURE


def test_outcome_unknown():
    state, _ = authorize_claim("outcome_unknown", "completed")
    assert state == MessageState.OUTCOME_UNKNOWN


def test_unverified_effect():
    state, _ = authorize_claim("unverified_effect", "completed")
    assert state == MessageState.UNVERIFIED_EFFECT


def test_mixed():
    state, _ = authorize_claim("mixed", "completed")
    assert state == MessageState.MIXED


def test_mixed_with_unknown():
    state, _ = authorize_claim("mixed_with_unknown", "completed")
    assert state == MessageState.MIXED_WITH_UNKNOWN


def test_no_evidence_is_outcome_unknown():
    state, reason = authorize_claim("no_evidence", "completed")
    assert state == MessageState.OUTCOME_UNKNOWN
    assert reason == "no_evidence"


def test_rejected_and_cancelled_never_become_success_even_with_verified_write_success():
    for lifecycle in ("rejected", "cancelled"):
        state, reason = authorize_claim("verified_write_success", lifecycle)
        assert state == MessageState.CANCELLED, (lifecycle, state)
        assert reason == "lifecycle_terminal_non_success"


def test_pending_lifecycle_cannot_claim_success_regardless_of_evidence():
    for evidence in _ALL_EVIDENCE_STATES:
        state, _ = authorize_claim(evidence, "pending")
        assert state != MessageState.SUCCESS, (evidence, state)
    # "pending" itself resolves deterministically to APPROVAL_PENDING.
    assert authorize_claim("verified_write_success", "pending") == (MessageState.APPROVAL_PENDING, "lifecycle_pending")


def test_in_progress_lifecycle_cannot_claim_success_regardless_of_evidence():
    for lifecycle in ("approved", "executing"):
        for evidence in _ALL_EVIDENCE_STATES:
            state, reason = authorize_claim(evidence, lifecycle)
            assert state != MessageState.SUCCESS, (lifecycle, evidence, state)
            assert state == MessageState.APPROVED_PROCESSING and reason == "lifecycle_not_terminal"


def test_approved_and_executing_match_canonical_message_contract_mapping():
    # core.message_contract._state_from_lifecycle() maps both "approved" and
    # "executing" to MessageState.APPROVED_PROCESSING -- unlike the
    # verified_read_only override, there is no TC7-B policy conflict here,
    # so this module must reuse the canonical value exactly, not invent one.
    for lifecycle in ("approved", "executing"):
        state, reason = authorize_claim("verified_write_success", lifecycle)
        assert state == MessageState.APPROVED_PROCESSING, (lifecycle, state)
        assert reason == "lifecycle_not_terminal"


def test_unsupported_evidence_string_fails_closed():
    state, reason = authorize_claim("some_made_up_status", "completed")
    assert state == MessageState.OUTCOME_UNKNOWN
    assert reason == "unsupported_evidence_status"


def test_unsupported_lifecycle_string_fails_closed():
    state, reason = authorize_claim("verified_write_success", "some_made_up_lifecycle")
    assert state == MessageState.OUTCOME_UNKNOWN
    assert reason == "unsupported_lifecycle_state"
    assert state != MessageState.SUCCESS


def test_none_and_missing_values_fail_closed():
    assert authorize_claim(None, None) == (MessageState.OUTCOME_UNKNOWN, "unsupported_lifecycle_state")
    assert authorize_claim(None, "completed") == (MessageState.OUTCOME_UNKNOWN, "no_evidence")
    assert authorize_claim("verified_write_success", None)[0] != MessageState.SUCCESS


def test_missing_and_expired_lifecycle_fail_closed():
    for lifecycle in ("missing", "expired"):
        state, _ = authorize_claim("verified_write_success", lifecycle)
        assert state != MessageState.SUCCESS
        assert state == MessageState.OUTCOME_UNKNOWN


def test_failed_lifecycle_is_always_failure_regardless_of_evidence():
    for evidence in _ALL_EVIDENCE_STATES:
        state, reason = authorize_claim(evidence, "failed")
        assert state == MessageState.FAILURE, (evidence, state)
        assert reason == "lifecycle_failed"


def test_no_raw_dispatcher_provider_or_text_parsing_imports():
    with open("core/claim_authorization.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert imported_modules == {"core.message_contract", "__future__"}, imported_modules
    banned_substrings = ("dispatcher", "provider", "re", "regex", "action_gateway", "turn_evidence", "app")
    for module in imported_modules:
        for banned in banned_substrings:
            assert banned not in module.split("."), (module, banned)


def test_no_private_f52_tc9_helper_imports():
    # Documentation prose may name these symbols (to explain the known
    # conflict); the module must never import or call them. Checked via
    # AST import nodes, not a raw substring scan of the whole file.
    with open("core/claim_authorization.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    forbidden = {
        "_state_from_lifecycle",
        "_lifecycle_projection",
        "_VERIFIED_SUCCESS_EVIDENCE",
        "_COMPLETED_EVIDENCE_STATES",
        "from_action_lifecycle_result",
        "lifecycle_message_adapter",
    }
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.add(node.module or "")
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
    assert not (imported_names & forbidden), imported_names & forbidden


def test_no_new_feature_flag():
    with open("core/claim_authorization.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "feature_flags" not in source
    assert "FEATURE_" not in source


def test_message_state_enum_unchanged():
    expected = {
        "needs_input", "approval_pending", "approval_pending_batch",
        "approved_processing", "success", "failure", "outcome_unknown",
        "unverified_effect", "mixed", "mixed_with_unknown", "cancelled",
        "already_completed", "already_cancelled", "no_pending_action", "neutral",
    }
    actual = {member.value for member in MessageState}
    assert actual == expected, actual


def _run_all():
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    _run_all()
