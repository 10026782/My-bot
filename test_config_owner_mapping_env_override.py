"""config.py::OWNER_USER_ID_MAPPINGS was a hardcoded, always-empty Python
dict — every non-interactive canonical Lead writer (WhatsApp/Voice/Email/
Furniture) therefore always failed closed with no way to configure it short
of a code change. This tests the new OWNER_USER_ID_MAPPINGS env-JSON
override (mirrors identity.py::_load_registry()'s IDENTITY_MAP pattern),
called directly rather than via module reload — same style as
test_identity_smoke.py's use of identity._load_registry().
"""
import json
import logging

import config


def test_unset_env_falls_back_to_empty_fail_closed(monkeypatch):
    monkeypatch.delenv("OWNER_USER_ID_MAPPINGS", raising=False)
    result = config._load_owner_user_id_mappings()
    assert result == {"whatsapp_destination": {}, "email_recipient": {}, "voice_destination": {}}


def test_valid_env_json_is_used(monkeypatch):
    payload = {
        "whatsapp_destination": {"whatsapp:+972500000000": "eliyahu"},
        "email_recipient": {"leads@example.com": "eliyahu"},
        "voice_destination": {"+972500000000": "eliyahu"},
    }
    monkeypatch.setenv("OWNER_USER_ID_MAPPINGS", json.dumps(payload))
    assert config._load_owner_user_id_mappings() == payload


def test_malformed_json_fails_closed_not_loud_crash(monkeypatch, caplog):
    monkeypatch.setenv("OWNER_USER_ID_MAPPINGS", "{not valid json")
    with caplog.at_level(logging.ERROR, logger="config"):
        result = config._load_owner_user_id_mappings()
    assert result == {"whatsapp_destination": {}, "email_recipient": {}, "voice_destination": {}}
    assert any("OWNER_USER_ID_MAPPINGS" in r.message for r in caplog.records)


def test_non_dict_source_value_ignored_source_stays_empty(monkeypatch, caplog):
    monkeypatch.setenv("OWNER_USER_ID_MAPPINGS", json.dumps({"whatsapp_destination": ["not", "a", "dict"]}))
    with caplog.at_level(logging.ERROR, logger="config"):
        result = config._load_owner_user_id_mappings()
    assert result["whatsapp_destination"] == {}
    assert any("whatsapp_destination" in r.message for r in caplog.records)


def test_unknown_top_level_key_warns_but_does_not_block_known_ones(monkeypatch, caplog):
    payload = {"whatsapp_destination": {"whatsapp:+972500000000": "eliyahu"}, "typo_key": {}}
    monkeypatch.setenv("OWNER_USER_ID_MAPPINGS", json.dumps(payload))
    with caplog.at_level(logging.WARNING, logger="config"):
        result = config._load_owner_user_id_mappings()
    assert result["whatsapp_destination"] == {"whatsapp:+972500000000": "eliyahu"}
    assert any("typo_key" in r.message for r in caplog.records)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
