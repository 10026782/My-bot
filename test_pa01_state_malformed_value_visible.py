"""BUG: FEATURE_PA01_ENFORCEMENT_STATE="shadow." (stray trailing char) silently
resolved to "off" in production with no log signal — see Grade-A remediation
map. Execution still falls back to "off" either way (fail-closed, unchanged
policy) — the fix only makes a *malformed but set* value visible in logs,
it does not make the function raise or block.

Verifies get_pa01_enforcement_state() keeps falling back to "off" for a
malformed value while now logging a warning; unset and valid values stay
silent.
"""
import logging
import os

from feature_flags import get_pa01_enforcement_state


def test_malformed_value_falls_back_to_off_and_warns(caplog):
    os.environ["FEATURE_PA01_ENFORCEMENT_STATE"] = "shadow."
    try:
        with caplog.at_level(logging.WARNING, logger="feature_flags"):
            assert get_pa01_enforcement_state() == "off"
        assert any("FEATURE_PA01_ENFORCEMENT_STATE" in r.message for r in caplog.records)
    finally:
        del os.environ["FEATURE_PA01_ENFORCEMENT_STATE"]


def test_unset_value_falls_back_to_off_silently(caplog):
    os.environ.pop("FEATURE_PA01_ENFORCEMENT_STATE", None)
    with caplog.at_level(logging.WARNING, logger="feature_flags"):
        assert get_pa01_enforcement_state() == "off"
    assert not any("FEATURE_PA01_ENFORCEMENT_STATE" in r.message for r in caplog.records)


def test_valid_values_pass_through_silently(caplog):
    for state in ("off", "shadow", "enforce", "SHADOW", " enforce "):
        os.environ["FEATURE_PA01_ENFORCEMENT_STATE"] = state
        try:
            with caplog.at_level(logging.WARNING, logger="feature_flags"):
                assert get_pa01_enforcement_state() == state.strip().lower()
            assert not any("FEATURE_PA01_ENFORCEMENT_STATE" in r.message for r in caplog.records)
        finally:
            del os.environ["FEATURE_PA01_ENFORCEMENT_STATE"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
