from pathlib import Path

import pytest

from core import create_execution_context, create_operation
from core.router.ownership_contracts import ExecutionClass
from core.turn_coordinator_runtime import resolve_tma_contextual_answer_capability
from tma_api import verify_tma_contextual_answer


def test_tma_contextual_answer_uses_one_narrow_model_capability():
    resolved = resolve_tma_contextual_answer_capability()
    operation = create_operation(resolved)
    context = create_execution_context(resolved, operation)

    assert resolved.capability_id == "general.contextual_answer"
    assert resolved.execution_class is ExecutionClass.NARROW_MODEL
    assert resolved.executor_ref == "tma.contextual_answer"
    assert context.operation is operation


def test_all_context_variants_share_the_same_fixed_capability():
    resolved = resolve_tma_contextual_answer_capability()

    assert resolved.capability_id == "general.contextual_answer"


@pytest.mark.parametrize("answer", ["answer", "  answer  ", "תשובה תקינה"])
def test_tma_answer_verifier_accepts_non_empty_strings(answer):
    assert verify_tma_contextual_answer(answer) == answer


@pytest.mark.parametrize("answer", ["", "   ", None, 42])
def test_tma_answer_verifier_rejects_structurally_invalid_output(answer):
    with pytest.raises(ValueError):
        verify_tma_contextual_answer(answer)


def test_tma_wiring_reuses_context_and_does_not_enter_agent_loop():
    source = Path("tma_api.py").read_text(encoding="utf-8")

    assert "execution_context=execution_context" in source
    assert "run_agent(" not in source
    assert 'general.reasoning' not in source
    assert "workflow_id" not in source
    assert "workflow_run_id" not in source
