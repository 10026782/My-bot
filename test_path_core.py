"""P3 stage 1 — the shared core of the path comparison: frame, the single tax-rate record, growth from the existing engine, the PathResult validator."""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from portfolio_lab import tax_assumptions
from portfolio_lab.path_comparison import core

PKG = Path("portfolio_lab/path_comparison")


def frame(**over):
    raw = {"today": "2026-10-25", "compare_at": "2029-10-25", "inflation_pct": [2.5, 2.5, 2.5], "alternative_return_pct": 6, "owner_inputs_label": "הנחות בעלים 25/10"}
    raw.update(over)
    return core.make_frame(raw)


# ═══ the tax rate lives in ONE place ═══

def test_the_tax_rate_number_appears_only_in_tax_assumptions():
    for path in list(PKG.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"(?<![\d.])0\.25(?!\d)", text) and "25%" not in text, f"{path} embeds the tax rate"
    assert len(re.findall(r"_DEFAULT_RATE\s*=\s*0\.25", Path("portfolio_lab/tax_assumptions.py").read_text(encoding="utf-8"))) == 1


def test_the_tax_record_is_preliminary_never_verified_and_an_override_is_marked():
    rec = tax_assumptions.tax_record()
    assert rec["rate"] == 0.25 and rec["status"] == "preliminary_estimate" and rec["externally_verified"] is False and rec["owner_override"] is False
    assert rec["basis"] == "real_return_after_inflation" and rec["version"] and rec["as_of"] and rec["source"]
    over = tax_assumptions.tax_record(0.3)
    assert over["rate"] == 0.3 and over["owner_override"] is True and over["externally_verified"] is False and over["version"] != rec["version"]
    for bad in (-0.1, 1.5, "0.2", True, float("nan")):
        with pytest.raises(ValueError):
            tax_assumptions.tax_record(bad)


def test_tax_is_rate_times_the_positive_real_gain_a_loss_is_zero_and_a_missing_basis_is_none():
    rec = tax_assumptions.tax_record()
    assert tax_assumptions.tax_on(1000, rec) == 250.0 and tax_assumptions.tax_on(-500, rec) == 0.0 and tax_assumptions.tax_on(0, rec) == 0.0
    assert tax_assumptions.tax_on(None, rec) is None


# ═══ frame ═══

def test_a_frame_carries_the_one_basis_and_a_digest_that_changes_with_any_assumption():
    f = frame()
    assert f["months"] == 36 and f["tax_basis"] == "after_latent_tax" and f["tax"]["externally_verified"] is False and f["frame_digest"]
    assert frame()["frame_digest"] == f["frame_digest"]
    assert frame(inflation_pct=[3, 3, 3])["frame_digest"] != f["frame_digest"]
    assert frame(tax_rate_override=0.3)["frame_digest"] != f["frame_digest"]
    assert frame(assumptions_version="assumptions-2")["frame_digest"] != f["frame_digest"]


@pytest.mark.parametrize("over", [
    {"compare_at": "2026-10-30"}, {"compare_at": "2026-10-25"}, {"compare_at": "2026-09-01"}, {"compare_at": "2060-01-01"}, {"inflation_pct": None}, {"inflation_pct": []},
    {"inflation_pct": [200]}, {"inflation_pct": "2"}, {"owner_inputs_label": ""}, {"owner_inputs_label": None}, {"today": "yesterday"}, {"alternative_return_pct": 90},
    {"live_index": 3},
])
def test_a_bad_frame_is_rejected(over):
    with pytest.raises(ValueError):
        frame(**over)


def test_a_frame_changed_after_it_was_built_is_refused():
    f = frame()
    core.check_frame(f)
    tampered = copy.deepcopy(f)
    tampered["inflation_pct"] = [0.0]
    with pytest.raises(ValueError):
        core.check_frame(tampered)
    with pytest.raises(ValueError):
        core.check_frame({"today": "2026-10-25"})


# ═══ growth comes from the existing engine ═══

def test_lump_growth_matches_the_closed_form_for_one_year_and_three():
    f1 = core.make_frame({"today": "2026-10-25", "compare_at": "2027-10-25", "inflation_pct": 2, "owner_inputs_label": "x"})
    v = core.lump_value(f1, 100000, 6)
    assert v["nominal"] == pytest.approx(106000, abs=0.01) and v["real"] == pytest.approx(106000 / 1.02, abs=0.01) and v["cpi"] == pytest.approx(1.02, abs=1e-9)
    v3 = core.lump_value(frame(), 100000, 6)
    assert v3["nominal"] == pytest.approx(100000 * 1.06 ** 3, abs=0.01)
    assert core.cpi_factor(frame()) == pytest.approx(1.025 ** 3, abs=1e-9)


def test_a_management_fee_lowers_the_value_and_a_short_yearly_list_carries_its_last_year_on():
    f = frame()
    assert core.lump_value(f, 100000, 6, 0.5)["nominal"] < core.lump_value(f, 100000, 6, 0.0)["nominal"]
    long = core.make_frame({"today": "2026-10-25", "compare_at": "2046-10-25", "inflation_pct": [2.0, 3.0], "owner_inputs_label": "x"})
    assert core.cpi_factor(long) == pytest.approx(1.02 * 1.03 ** 19, abs=1e-6)


def test_the_tax_on_growth_is_taxed_only_on_the_real_part():
    f1 = core.make_frame({"today": "2026-10-25", "compare_at": "2027-10-25", "inflation_pct": 2, "owner_inputs_label": "x"})
    assert core.tax_on_growth(f1, 100000, 6000) == pytest.approx(0.25 * (6000 - 100000 * 0.02), abs=0.01)        # 1,000
    assert core.tax_on_growth(f1, 100000, 1000) == 0.0                                                            # growth below inflation: a real loss -> no tax


# ═══ the PathResult contract ═══

def good_result():
    f = frame()
    r = core.blank_result(f, path_id="p", module="m", module_version="m-1", type_="t", label="l", movement_kind="liability", purpose="fund_amount", funds_amount=100.0)
    r["not_applicable"] = ["cost.holding_costs"]
    return core.finalize(r)


def test_a_finalized_result_has_the_standing_caveat_the_three_separate_measures_and_both_net_worth_rows():
    r = good_result()
    assert {c["caveat_id"] for c in r["caveats"]} >= {"preliminary", "assumption_based"} and all(c["version"] and c["text"] for c in r["caveats"])
    assert set(r["measures"]) == {"liquidity", "net_worth", "economic_cost"} and set(r["measures"]["net_worth"]) == {"before_latent_tax", "after_latent_tax"}
    assert r["basis"]["tax_basis"] == "after_latent_tax" and r["calc_version"]["tax_rate"] and r["calc_version"]["core"] == core.CORE_VERSION


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(score=1), lambda r: r["measures"].update(best=1), lambda r: r["result"].update(recommended=True), lambda r: r["cost"].update(total_available=5),
    lambda r: r["measures"].update(combined=1), lambda r: r["measures"]["net_worth"].pop("after_latent_tax"), lambda r: r.pop("caveats"),
    lambda r: r.update(caveats=[]), lambda r: r.update(movement_kind="gift"), lambda r: r.update(certainty="sure"), lambda r: r["basis"].update(tax_basis="gross"),
    lambda r: r["tax"].update(status="externally_verified"), lambda r: r.update(not_applicable=["result.balance_effect"]),
    lambda r: r["cash_flows"].append({"date": "2026-10-25", "amount": 1}),
])
def test_the_validator_rejects_ranking_merged_measures_unverified_tax_and_malformed_parts(mutate):
    r = copy.deepcopy(good_result())
    r["result"]["balance_effect"] = "x"
    mutate(r)
    with pytest.raises(ValueError):
        core.validate_path_result(r)


def test_missing_inputs_require_the_missing_is_not_zero_caveat_and_a_total_with_a_missing_part_is_none():
    f = frame()
    r = core.blank_result(f, path_id="p", module="m", module_version="m-1", type_="t", label="l", movement_kind="new_money", purpose="fund_amount", funds_amount=None)
    r["missing_inputs"] = ["fees"]
    assert any(c["caveat_id"] == "missing_is_missing" for c in core.finalize(r)["caveats"])
    assert core.total_or_none([1.0, 2.5]) == 3.5 and core.total_or_none([1.0, None]) is None and core.total_or_none([]) == 0.0


def test_net_worth_rows_are_nominal_and_real_and_none_stays_none():
    f = frame()
    block = core.net_worth_block(f, -1000.0, -800.0)
    assert block["before_latent_tax"]["nominal"] == -1000.0 and block["before_latent_tax"]["real"] == pytest.approx(-1000 / 1.025 ** 3, abs=0.01)
    assert block["after_latent_tax"]["real"] == pytest.approx(-800 / 1.025 ** 3, abs=0.01)
    none = core.net_worth_block(f, None, None)
    assert none["before_latent_tax"] == {"nominal": None, "real": None}


def test_the_core_has_no_io_does_not_import_the_ranking_helpers_and_uses_no_ranking_identifiers():
    import ast
    for path in PKG.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any("payoff" in m or "airtable" in m or "requests" in m or "sqlite" in m for m in imported), (path, imported)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & {"balanced_score", "rankings", "optimal", "score", "rank"}, (path, names)
        assert "open" not in {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}, path
