from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

import schema_validator
from tools.airtable_gateway import AirtableLookupError


def _metadata() -> dict:
    return {"tables": [{"name": "Leads", "fields": [{"name": "Name"}]}]}


def test_refresh_cache_preserves_payload_and_calls_gateway_with_timeout(tmp_path: Path):
    cache_path = tmp_path / "schema_cache.json"
    with patch.object(schema_validator, "_CACHE_PATH", cache_path), \
         patch("tools.airtable_gateway.get_base_metadata", return_value=_metadata()) as fetch, \
         patch.dict(os.environ, {"AIRTABLE_API_KEY": "pat", "AIRTABLE_BASE_ID": "app"}):
        schema_validator._cache = None
        assert schema_validator.refresh_cache() == {"Leads": ["Name"]}

    fetch.assert_called_once_with(timeout=20)
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["tables"] == {"Leads": ["Name"]}
    assert payload["note"] == "auto-fetched by schema_audit.py"
    assert payload["fetched_at"]


def test_refresh_cache_missing_credentials_preserves_environment_error():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError, match="AIRTABLE_API_KEY / AIRTABLE_BASE_ID חסרים"):
            schema_validator.refresh_cache()


@pytest.mark.parametrize("status", [401, 403, 500])
def test_refresh_cache_http_failures_preserve_httpx_status_error(status: int):
    error = AirtableLookupError(
        f"HTTP {status}",
        status_code=status,
        response_text="failure",
        response_url="https://api.airtable.com/v0/meta/bases/app/tables",
    )
    with patch.dict(os.environ, {"AIRTABLE_API_KEY": "pat", "AIRTABLE_BASE_ID": "app"}), \
         patch("tools.airtable_gateway.get_base_metadata", side_effect=error):
        with pytest.raises(httpx.HTTPStatusError) as raised:
            schema_validator.refresh_cache()
    assert raised.value.response.status_code == status


def test_refresh_cache_transport_failure_preserves_original_exception():
    error = TimeoutError("timed out")
    wrapped = AirtableLookupError("metadata failed", cause=error)
    with patch.dict(os.environ, {"AIRTABLE_API_KEY": "pat", "AIRTABLE_BASE_ID": "app"}), \
         patch("tools.airtable_gateway.get_base_metadata", side_effect=wrapped):
        with pytest.raises(TimeoutError, match="timed out") as raised:
            schema_validator.refresh_cache()
    assert raised.value is error


def test_refresh_cache_keeps_load_cache_fail_open(tmp_path: Path):
    missing = tmp_path / "missing.json"
    with patch.object(schema_validator, "_CACHE_PATH", missing):
        schema_validator._cache = None
        assert schema_validator.get_known_fields("Leads") == set()


def test_schema_validator_contains_no_airtable_transport_knowledge():
    source = Path("schema_validator.py").read_text(encoding="utf-8")
    assert "api.airtable.com/v0/meta" not in source
    assert "_at_url" not in source
    assert "_at_headers" not in source
    assert "httpx.get(" not in source
