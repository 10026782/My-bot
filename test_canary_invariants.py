import ast
from pathlib import Path


def _harness_invariant_function():
    source = Path(__file__).parent / "scripts" / "verify_bug161_162_callback_staging.py"
    tree = ast.parse(source.read_text())
    node = next(n for n in tree.body if getattr(n, "name", None) == "canary_invariant_failures")
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {}
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["canary_invariant_failures"]


def test_failed_contract_with_zero_provider_writes_is_not_a_pass():
    failures = _harness_invariant_function()(
        contract_count=1,
        claim_count=1,
        executor_count=1,
        provider_write_count=0,
        final_reply_count=1,
        final_state="failed",
        legacy_callback_dispatch_count=0,
    )

    assert "provider_write_count=0" in failures
    assert "final_state=failed" in failures
