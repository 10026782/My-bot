import json

import daily_collector
from core import ExecutionContext
from core.router import ExecutionClass, Intent
from core.usage_telemetry import usage_attribution_from_context
from core.turn_coordinator_runtime import resolve_daily_persistence_gap_capability


VALID_RESULT = {
    "items": [{
        "text": "נתון עסקי",
        "category": "crm",
        "status": "unclear",
        "suggested_action": "בדיקה",
    }],
    "all_clear": False,
}


def _eligible_history():
    return [{
        "role": "user",
        "content": "שילמנו 5000 שח לספק אתמול, ולא בטוח בכלל שזה נרשם איפשהו במערכת",
    }]


def _patch_history(monkeypatch, history):
    import memory_store

    monkeypatch.setattr(memory_store.memory, "get_for_claude", lambda memory_key: history)


def test_daily_intent_and_capability_are_canonical():
    capability = resolve_daily_persistence_gap_capability()

    assert Intent.DETECT_DAILY_PERSISTENCE_GAPS in Intent.ALL
    assert capability.capability_id == "business.daily_persistence_gap_detection"
    assert capability.execution_class is ExecutionClass.NARROW_MODEL
    assert capability.executor_ref == "daily_collector.analysis"
    assert Intent.DETECT_DAILY_PERSISTENCE_GAPS not in {
        Intent.ASK_QUESTION, Intent.DRAFT_MESSAGE, Intent.GENERATE_REPORT,
    }


def test_no_operation_or_context_for_ineligible_history(monkeypatch):
    operations = []
    contexts = []
    monkeypatch.setattr(daily_collector, "create_operation", operations.append)
    monkeypatch.setattr(daily_collector, "create_execution_context", contexts.append)

    for history in ([], [{"role": "user", "content": "קצר"}]):
        _patch_history(monkeypatch, history)
        assert daily_collector.collect_daily("boss_hq:eliyahu") == {
            "items": [], "all_clear": True,
        }

    assert operations == []
    assert contexts == []


def test_eligible_history_creates_one_context_and_passes_it_to_paid_call(monkeypatch):
    _patch_history(monkeypatch, _eligible_history())
    operations = []
    contexts = []
    paid_calls = []
    real_create_operation = daily_collector.create_operation
    real_create_context = daily_collector.create_execution_context

    def create_operation(capability):
        operation = real_create_operation(capability)
        operations.append(operation)
        return operation

    def create_context(capability, operation):
        context = real_create_context(capability, operation)
        contexts.append(context)
        return context

    def paid_call(**kwargs):
        paid_calls.append(kwargs)
        return json.dumps(VALID_RESULT)

    monkeypatch.setattr(daily_collector, "create_operation", create_operation)
    monkeypatch.setattr(daily_collector, "create_execution_context", create_context)
    monkeypatch.setattr(daily_collector, "call_anthropic_text", paid_call)

    result = daily_collector.collect_daily("boss_hq:eliyahu")

    assert result == VALID_RESULT
    assert len(operations) == len(contexts) == 1
    assert isinstance(contexts[0], ExecutionContext)
    assert paid_calls[0]["execution_context"] is contexts[0]
    assert contexts[0].operation is operations[0]
    assert contexts[0].contract_id is None
    assert contexts[0].turn_id is None
    assert contexts[0].parent_operation_id is None
    assert usage_attribution_from_context(contexts[0]) == {
        "capability_id": "business.daily_persistence_gap_detection",
        "execution_class": "NARROW_MODEL",
        "operation_id": operations[0].operation_id,
    }


def test_structural_verifier_accepts_valid_result_and_rejects_invalid_shapes():
    assert daily_collector.verify_daily_collector_result(VALID_RESULT) == VALID_RESULT
    invalid_results = [
        [],
        {"items": {}, "all_clear": False},
        {"items": [], "all_clear": "false"},
        {"items": [{**VALID_RESULT["items"][0], "category": "other"}], "all_clear": False},
        {"items": [{**VALID_RESULT["items"][0], "status": "unknown"}], "all_clear": False},
        {"items": [{**VALID_RESULT["items"][0], "text": 1}], "all_clear": False},
        {"items": [{**VALID_RESULT["items"][0], "suggested_action": None}], "all_clear": False},
    ]
    for result in invalid_results:
        try:
            daily_collector.verify_daily_collector_result(result)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid result accepted: {result!r}")


def test_legacy_recovery_fallback_remains_safe_on_verifier_failure(monkeypatch, caplog):
    _patch_history(monkeypatch, _eligible_history())
    monkeypatch.setattr(daily_collector, "call_anthropic_text", lambda **kwargs: "{}")

    result = daily_collector.collect_daily("boss_hq:eliyahu")

    assert result == {"items": [], "all_clear": True}
    assert "LLM analysis failed" in caplog.text
