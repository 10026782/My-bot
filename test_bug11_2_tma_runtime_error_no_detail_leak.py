"""
Regression test — Audit #11 (#11-2): tma_api's blueprint-wide RuntimeError
handler must not leak exception text to the client.

Proves:
  1. HTTP 500 is still returned.
  2. The JSON body carries only {"error": "internal_error"} — no "detail"
     key, and the exception message text is not present anywhere in the
     response body.
  3. Server-side logging still records the full exception detail.
"""

import logging
import sys
from unittest.mock import patch

from flask import Flask

import tma_api

_SECRET_DETAIL = "internal table 'Leads_Shadow_Debug' has no field 'ghost_id'"


def _client():
    app = Flask(__name__)

    # Registered on the blueprint itself (not the raw Flask app) — Flask
    # scopes @blueprint.errorhandler() to routes owned by that blueprint,
    # so the route under test must be one too for _handle_runtime_error to
    # actually fire instead of falling through to Flask's own default
    # error page.
    @tma_api.tma_api.route("/__test_raise_runtime_error")
    def _raise():
        raise RuntimeError(_SECRET_DETAIL)

    app.register_blueprint(tma_api.tma_api)
    return app.test_client()


def run():
    client = _client()
    results = []

    with patch.object(tma_api.logger, "error") as mock_log_error:
        resp = client.get("/__test_raise_runtime_error")
        body = resp.get_json()

        results.append(("HTTP 500 preserved", resp.status_code == 500))
        results.append(("response has no 'detail' key", body is not None and "detail" not in body))
        results.append(("response body carries no exception text", _SECRET_DETAIL not in resp.get_data(as_text=True)))
        results.append(("response error code stable", body == {"error": "internal_error"}))
        results.append(("server-side logger.error still called", mock_log_error.called))
        logged_text = " ".join(str(a) for call in mock_log_error.call_args_list for a in call.args)
        results.append(("server-side log retains exception detail", _SECRET_DETAIL in logged_text))

    print("\n=== Audit #11 (#11-2) TMA RuntimeError detail-leak regression ===")
    failures = []
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            failures.append(name)

    if failures:
        print(f"\n❌ FAILED: {', '.join(failures)}")
    else:
        print("\n✅ no client-facing exception-detail leak; server logging intact")
    return not failures


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
