"""FCC planner routes (funding plan / save, accounts forecast): only VALIDATION text reaches the client.

A ValueError/TypeError/OverflowError raised from a computation or a data read is an internal fault -> logged generic 500 ("internal error", no text);
the planners' own fixed validation messages and the normalize_* errors on the client's input stay 400 with their text. In-memory fakes; no network."""

from __future__ import annotations

import json
import pathlib
import re

import pytest

import tma_api
from airtable_schema import FinGoalFields as GF
from airtable_schema import Tables
from core.financial_control import service
from test_fcc_net_worth import DB, ELIYAHU, H, acct, fakes, http, ident, snap, ELI, ACF  # noqa: F401  (fakes = the autouse Airtable fakes)
from identity import Role

SECRET = "SECRET_INTERNAL 120000"


@pytest.fixture(autouse=True)
def _seed_and_reset_limiter(fakes):
    tma_api._PL_LIMITER = None
    DB[Tables.FIN_GOALS] = [{"id": "recG1", "fields": {GF.TITLE: "מטרה", GF.STATUS: "active", GF.TARGET_AMOUNT: 100000, GF.END_DATE: "2028-12-31",
                                                        GF.CATEGORY: "future_goal", GF.FINANCIAL_OWNER: [ELI]}}]
    DB[Tables.FIN_ACCOUNTS] = [acct("recA1", "חשבון")]
    DB[Tables.FIN_EVENTS] = [snap("recS1", "recA1", 50000, "2026-10-01")]
    yield
    tma_api._PL_LIMITER = None


def post(monkeypatch, path, body, who=ELIYAHU):
    return http(monkeypatch, who).post(path, data=json.dumps(body), headers={**H, "Content-Type": "application/json"})


def boom(exc):
    def _raise(*a, **k):
        raise exc
    return _raise


def assert_generic_500(r):
    assert r.status_code == 500 and r.get_json() == {"error": "internal error"}
    assert "SECRET" not in r.get_data(as_text=True) and "120000" not in r.get_data(as_text=True)


PLAN, FORECAST, SAVE = "/api/fcc/funding/plan", "/api/fcc/accounts/forecast", "/api/fcc/funding/plan/save"


# ── an internal fault is never echoed ────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("exc", [ValueError(SECRET), TypeError(SECRET), OverflowError(SECRET), RuntimeError(SECRET)])
def test_funding_plan_internal_fault_in_the_plan_builder_is_a_generic_500(monkeypatch, exc):
    import portfolio_lab.funding_plan as fp
    monkeypatch.setattr(fp, "build_funding_plan", boom(exc))
    assert_generic_500(post(monkeypatch, PLAN, {"goal_id": "recG1"}))


@pytest.mark.parametrize("exc", [ValueError(SECRET), TypeError(SECRET)])
def test_funding_plan_internal_fault_in_the_sources_builder_is_a_generic_500(monkeypatch, exc):
    import portfolio_lab.funding_sources as fs
    monkeypatch.setattr(fs, "build_suggested_sources", boom(exc))
    assert_generic_500(post(monkeypatch, PLAN, {"goal_id": "recG1"}))


def test_funding_plan_save_route_shares_the_hardening(monkeypatch):
    import portfolio_lab.funding_plan as fp
    monkeypatch.setattr(fp, "build_funding_plan", boom(ValueError(SECRET)))
    assert_generic_500(post(monkeypatch, SAVE, {"goal_id": "recG1", "selected": []}))


@pytest.mark.parametrize("exc", [ValueError(SECRET), TypeError(SECRET), OverflowError(SECRET)])
def test_a_data_read_fault_is_a_generic_500_not_validation_text(monkeypatch, exc):
    monkeypatch.setattr(service, "funding_inputs", boom(exc))
    assert_generic_500(post(monkeypatch, PLAN, {"goal_id": "recG1"}))
    monkeypatch.setattr(service, "accounts_view", boom(exc))
    assert_generic_500(post(monkeypatch, FORECAST, {}))


@pytest.mark.parametrize("exc", [ValueError(SECRET), TypeError(SECRET), OverflowError(SECRET)])
def test_forecast_internal_fault_in_the_builder_is_a_generic_500(monkeypatch, exc):
    import portfolio_lab.accounts_forecast as af
    monkeypatch.setattr(af, "build_accounts_forecast", boom(exc))
    assert_generic_500(post(monkeypatch, FORECAST, {}))


def test_a_keyerror_never_names_its_key(monkeypatch):
    import portfolio_lab.accounts_forecast as af
    import portfolio_lab.funding_plan as fp
    monkeypatch.setattr(af, "build_accounts_forecast", boom(KeyError("secret_key_name")))
    r = post(monkeypatch, FORECAST, {})
    assert r.status_code == 400 and r.get_json() == {"error": "invalid request"}
    monkeypatch.setattr(fp, "build_funding_plan", boom(KeyError("secret_key_name")))
    r = post(monkeypatch, PLAN, {"goal_id": "recG1"})
    assert r.status_code == 400 and r.get_json() == {"error": "invalid request"}


# ── validation keeps its text and its 400 ────────────────────────────────────────────────────────────────────────────
def test_unknown_goal_stays_a_400_with_its_text(monkeypatch):
    r = post(monkeypatch, PLAN, {"goal_id": "recNotMine"})
    assert r.status_code == 400 and r.get_json() == {"error": "unknown goal"}


def test_request_validation_errors_stay_400_with_text(monkeypatch):
    r = post(monkeypatch, PLAN, {"goal_id": "recG1", "bogus": 1})
    assert r.status_code == 400 and "unknown fields: bogus" in r.get_json()["error"]
    r = post(monkeypatch, PLAN, {"goal_ids": []})
    assert r.status_code == 400 and "goal_ids must list" in r.get_json()["error"]
    r = post(monkeypatch, PLAN, {"goal_id": "recG1", "assumptions": {"annual_return_pct": 9999}})         # validated by the planners' own normalize_params
    assert r.status_code == 400 and "annual_return_pct must be from" in r.get_json()["error"]
    r = post(monkeypatch, FORECAST, {"years": 5})
    assert r.status_code == 400 and r.get_json() == {"error": "years must be an integer from 10 to 100"}
    r = post(monkeypatch, FORECAST, {"nope": 1})
    assert r.status_code == 400 and "unknown fields: nope" in r.get_json()["error"]


def test_forecast_unknown_account_stays_a_400_with_its_text(monkeypatch):
    r = post(monkeypatch, FORECAST, {"monthly_contributions": {"recZZ": 100}})
    assert r.status_code == 400 and r.get_json() == {"error": "monthly_contributions has an unknown account"}


def test_a_known_build_validation_message_from_a_planner_stays_a_400(monkeypatch):
    import portfolio_lab.funding_plan as fp
    monkeypatch.setattr(fp, "build_funding_plan", boom(ValueError("unknown account in options")))
    r = post(monkeypatch, PLAN, {"goal_id": "recG1"})
    assert r.status_code == 400 and r.get_json() == {"error": "unknown account in options"}


def test_happy_paths_are_unchanged(monkeypatch):
    r = post(monkeypatch, PLAN, {"goal_id": "recG1"})
    assert r.status_code == 200 and "suggested_sources" in r.get_json()
    tma_api._PL_LIMITER = None
    assert post(monkeypatch, FORECAST, {}).status_code == 200


def test_gate_and_denied_identity_are_unchanged(monkeypatch):
    assert http(monkeypatch, ELIYAHU, flag=False).post(PLAN, data="{}", headers={**H, "Content-Type": "application/json"}).status_code == 404
    assert post(monkeypatch, PLAN, {"goal_id": "recG1"}, who=ident("nobody", Role.OWNER)).status_code == 403
    tma_api._PL_LIMITER = None
    assert post(monkeypatch, FORECAST, {}, who=ident("nobody", Role.OWNER)).status_code == 403


def test_the_allow_list_has_not_rotted():
    """Every allowed text must still be raised somewhere in the planners (a renamed message would silently turn into a 500)."""
    root = pathlib.Path(__file__).parent / "portfolio_lab"
    source = "".join((root / f).read_text(encoding="utf-8") for f in ("funding_plan.py", "funding_sources.py", "accounts_forecast.py"))
    for text in tma_api._FCC_BUILD_VALIDATION:
        assert f'ValueError("{text}")' in source, text
    assert all(not re.search(r"[{}]", t) for t in tma_api._FCC_BUILD_VALIDATION), "texts must be fixed strings (no values)"
