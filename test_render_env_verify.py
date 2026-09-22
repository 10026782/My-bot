"""Regression tests for Render environment-output redaction."""

import importlib.util
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "render_env_verify", Path(__file__).parent / "scripts" / "render_env_verify.py",
)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MODULE)


def test_safe_summary_never_renders_secret_values():
    secret = "postgresql://user:secret-password@host/database"
    lines = _MODULE.safe_summary([
        {"envVar": {"key": "FEATURE_ACTION_GATEWAY", "value": "true"}},
        {"envVar": {"key": "FEATURE_ACTION_CONTRACT_PERSISTENCE", "value": "true"}},
        {"envVar": {"key": "FEATURE_ATOMIC_CLAIMS", "value": "true"}},
        {"envVar": {"key": "DATABASE_URL", "value": secret}},
        {"envVar": {"key": "UNRELATED_SECRET", "value": "must-not-print"}},
    ])

    output = "\n".join(lines)
    assert output == (
        "FEATURE_ACTION_GATEWAY=true\n"
        "FEATURE_ACTION_CONTRACT_PERSISTENCE=true\n"
        "FEATURE_ATOMIC_CLAIMS=true\n"
        "DATABASE_URL=PRESENT"
    )
    assert secret not in output
    assert "must-not-print" not in output


def test_safe_summary_redacts_unexpected_flag_value():
    output = "\n".join(_MODULE.safe_summary([
        {"envVar": {"key": "FEATURE_ACTION_GATEWAY", "value": "secret-value"}},
    ]))

    assert "FEATURE_ACTION_GATEWAY=SET_NON_BOOLEAN" in output
    assert "secret-value" not in output
