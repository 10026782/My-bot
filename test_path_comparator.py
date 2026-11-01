"""P3 stage 1 — the neutral comparator: one basis, signed gaps against a reference the owner chose, sensitivity and break-even. No ranking, no summing."""

from __future__ import annotations

import copy
import json
import re

import pytest

from portfolio_lab.path_comparison import break_even, compare_paths, core, describe_inputs, evaluate_path, make_frame, sensitivity


def frame(**over):
    raw = {"today": "2026-10-25", "compare_at": "2029-10-25", "inflation_pct": [2.5, 2.5, 2.5], "alternative_return_pct": 6, "owner_inputs_label": "הנחות בעלים 25/10"}
    raw.update(over)
    return make_frame(raw)


LOAN = {"id": "loan", "label": "הלוואה 3%", "type": "take_loan", "amount": 250000, "annual_rate_pct": 3, "term_months": 36, "fees": 0, "approved": False}
CASH = {"id": "cash", "label": "מזומן", "type": "use_liquid_cash", "amount": 250000, "expected_return_pct": 6, "fee_pct": 0.5, "withdraw_fee": 0}
WAIT = {"id": "wait", "label": "להמתין", "type": "wait", "amount": 250000, "until": "2027-10-25", "price_change_pct": 3}


def results(f, *specs):
    return [evaluate_path(f, s) for s in specs]


# ═══ one basis ═══

def test_paths_on_one_basis_compare_in_the_order_given_without_sorting_and_without_a_reference_there_are_no_gaps():
    f = frame()
    out = compare_paths(f, results(f, CASH, LOAN, WAIT))
    assert [p["path_id"] for p in out["paths"]] == ["cash", "loan", "wait"] and all(p["gap_vs_reference"] is None for p in out["paths"])
    assert out["result_type"] == "assumption_based_projection" and out["compare_at"] == f["compare_at"] and out["frame_echo"]["frame_digest"] == f["frame_digest"]
    assert [p["path_id"] for p in compare_paths(f, results(f, WAIT, LOAN, CASH))["paths"]] == ["wait", "loan", "cash"]


def test_results_from_a_different_frame_are_refused_so_there_is_no_gross_against_net():
    f, other = frame(), frame(inflation_pct=[4, 4, 4])
    with pytest.raises(ValueError):
        compare_paths(f, [evaluate_path(f, CASH), evaluate_path(other, LOAN)])
    with pytest.raises(ValueError):
        compare_paths(f, [evaluate_path(other, LOAN)])
    later = frame(compare_at="2030-10-25")
    with pytest.raises(ValueError):
        compare_paths(f, [evaluate_path(f, CASH), evaluate_path(later, CASH | {"id": "x"})])
    forged = evaluate_path(f, CASH)
    forged["basis"] = dict(forged["basis"], tax_basis="before_latent_tax")
    with pytest.raises(ValueError):
        compare_paths(f, [forged])
    forged2 = evaluate_path(f, LOAN)
    forged2["basis"] = dict(forged2["basis"], inflation_basis="constant")
    with pytest.raises(ValueError):
        compare_paths(f, [evaluate_path(f, CASH), forged2])


def test_paths_that_fund_different_amounts_or_serve_different_purposes_are_not_comparable():
    f = frame()
    with pytest.raises(ValueError):
        compare_paths(f, results(f, CASH, LOAN | {"amount": 200000}))
    prepay = {"id": "prepay", "label": "פירעון", "type": "prepay_loan", "balance": 100000, "annual_rate_pct": 6, "remaining_months": 60, "early_fee": 0, "source_return_pct": 4}
    with pytest.raises(ValueError):
        compare_paths(f, results(f, CASH, prepay))
    assert compare_paths(f, results(f, prepay))["purpose"] == "reduce_debt"


def test_duplicate_ids_unknown_reference_empty_and_a_tampered_frame_are_refused():
    f = frame()
    with pytest.raises(ValueError):
        compare_paths(f, results(f, CASH, CASH))
    with pytest.raises(ValueError):
        compare_paths(f, results(f, CASH), reference="nope")
    with pytest.raises(ValueError):
        compare_paths(f, [])
    tampered = copy.deepcopy(f)
    tampered["inflation_pct"] = [0.0]
    with pytest.raises(ValueError):
        compare_paths(tampered, results(f, CASH))
    with pytest.raises(ValueError):
        compare_paths(f, [{"path_id": "x"}])


# ═══ signed gaps against the chosen reference ═══

def test_gaps_are_signed_differences_from_the_reference_not_good_or_bad():
    f = frame()
    res = results(f, CASH, LOAN, WAIT)
    out = compare_paths(f, res, reference="cash")
    by = {p["path_id"]: p for p in out["paths"]}
    assert out["reference"] == "cash" and by["cash"]["gap_vs_reference"]["fields"]["net_cost"] == 0.0
    cash_cost, loan_cost = res[0]["measures"]["economic_cost"]["net_cost"], res[1]["measures"]["economic_cost"]["net_cost"]
    assert by["loan"]["gap_vs_reference"]["fields"]["net_cost"] == pytest.approx(loan_cost - cash_cost, abs=0.01)
    nw = lambda r: r["measures"]["net_worth"]["after_latent_tax"]["nominal"]            # noqa: E731
    assert by["loan"]["gap_vs_reference"]["fields"]["net_worth_after_latent_tax_nominal"] == pytest.approx(nw(res[1]) - nw(res[0]), abs=0.01)
    assert by["loan"]["gap_vs_reference"]["reference"] == "cash"
    assert any("חתום" in w for w in out["warnings"])


def test_a_gap_is_not_computed_when_either_side_is_missing():
    f = frame()
    res = results(f, CASH | {"withdraw_fee": None}, LOAN)
    out = compare_paths(f, res, reference="cash")
    gap = out["paths"][1]["gap_vs_reference"]["fields"]
    assert gap["net_cost"] is None and gap["net_worth_after_latent_tax_nominal"] is None
    assert any("חסר" in w for w in out["warnings"])


def test_the_comparator_output_has_no_ranking_summary_or_recommendation_and_does_not_change_its_inputs():
    f = frame()
    res = results(f, CASH, LOAN, WAIT)
    before = copy.deepcopy(res)
    out = compare_paths(f, res, reference="loan")
    assert res == before
    text = json.dumps(out, ensure_ascii=False)
    assert not re.search(r'"(score|rank|ranking|best|recommended|recommendation|better|cheapest|optimal|total_available)"', text.lower())
    assert not re.search(r"מומלץ|כדאי|הטוב ביותר|עדיף|הזול ביותר", text)
    assert set(out) == {"schema_version", "engine_version", "comparator_version", "result_type", "compare_at", "frame_echo", "purpose", "paths", "reference", "warnings"}


def test_the_comparison_is_deterministic_and_a_stored_run_replays_to_the_same_result():
    f = frame()
    a = compare_paths(f, results(f, CASH, LOAN, WAIT), reference="cash")
    assert a == compare_paths(f, results(f, CASH, LOAN, WAIT), reference="cash")
    stored = json.loads(json.dumps({"frame_inputs": {"today": "2026-10-25", "compare_at": "2029-10-25", "inflation_pct": [2.5, 2.5, 2.5], "alternative_return_pct": 6,
                                                    "owner_inputs_label": "הנחות בעלים 25/10"}, "specs": [CASH, LOAN, WAIT]}))
    f2 = make_frame(stored["frame_inputs"])
    assert f2["frame_digest"] == f["frame_digest"] and compare_paths(f2, results(f2, *stored["specs"]), reference="cash") == a
    changed = frame(tax_rate_override=0.30)                                   # a later assumption change is a different frame; the old result is untouched
    assert changed["frame_digest"] != f["frame_digest"] and a["frame_echo"]["tax"]["rate"] == 0.25


def test_the_wedding_example_three_paths_on_one_basis_match_the_independent_figures():
    f = frame()
    res = results(f, LOAN, CASH, WAIT)
    i = 3 / 1200
    pay = 250000 * i / (1 - (1 + i) ** -36)
    assert res[0]["measures"]["economic_cost"]["net_cost"] == pytest.approx(pay * 36 - 250000, abs=0.01)
    cpi = 1.025 ** 3
    grown = core.lump_value(f, 250000, 6, 0.5)["nominal"] - 250000
    assert res[1]["measures"]["economic_cost"]["net_cost"] == pytest.approx(grown - 0.25 * (grown - 250000 * (cpi - 1)), abs=0.01)
    assert res[2]["measures"]["economic_cost"]["net_cost"] == pytest.approx(250000 * 0.03, abs=0.01)
    assert {r["frame_digest"] for r in res} == {f["frame_digest"]} and {r["basis"]["tax_basis"] for r in res} == {"after_latent_tax"}


# ═══ sensitivity and break-even ═══

def test_sensitivity_reruns_the_same_path_at_explicit_alternatives_as_separate_rows_with_no_average():
    f = frame()
    out = sensitivity(f, LOAN, "annual_rate_pct", [0, 3, 6, 9])
    assert [r["value"] for r in out["rows"]] == [0, 3, 6, 9] and out["rows"][0]["net_cost"] == pytest.approx(0, abs=1e-6)
    metrics = [r["metric"] for r in out["rows"]]
    assert metrics == sorted(metrics, reverse=True) and out["path_id"] == "loan"
    assert not {"average", "mean", "median", "likely", "expected_value", "total", "sum"} & {k for row in out["rows"] for k in row} and set(out) == {"path_id", "parameter", "metric_path", "rows", "note"}
    with pytest.raises(ValueError):
        sensitivity(f, LOAN, "annual_rate_pct", [])
    with pytest.raises(ValueError):
        sensitivity(f, LOAN, "annual_rate_pct", list(range(30)))
    with pytest.raises(ValueError):
        sensitivity(f, LOAN, "type", ["wait"])
    with pytest.raises(ValueError):
        sensitivity(f, LOAN, "annual_rate_pct", [-5])


def test_break_even_finds_the_loan_rate_where_borrowing_and_using_cash_cost_the_same_and_it_is_a_threshold_not_a_conclusion():
    f = frame()
    out = break_even(f, LOAN, CASH, "annual_rate_pct", 0, 30)
    rate = out["value"]
    assert rate is not None and 0 < rate < 30 and "not a conclusion" in out["note"]
    a = evaluate_path(f, LOAN | {"annual_rate_pct": rate})["measures"]["net_worth"]["after_latent_tax"]["nominal"]
    b = evaluate_path(f, CASH)["measures"]["net_worth"]["after_latent_tax"]["nominal"]
    assert a == pytest.approx(b, abs=0.5)
    cheaper = evaluate_path(f, LOAN | {"annual_rate_pct": rate - 1})["measures"]["net_worth"]["after_latent_tax"]["nominal"]
    dearer = evaluate_path(f, LOAN | {"annual_rate_pct": rate + 1})["measures"]["net_worth"]["after_latent_tax"]["nominal"]
    assert cheaper > b > dearer


def test_break_even_says_when_there_is_no_crossing_or_an_input_is_missing_instead_of_inventing_one():
    f = frame()
    none = break_even(f, LOAN, CASH, "annual_rate_pct", 0, 2)
    assert none["value"] is None and none["reason"] == "no_crossing_in_range"
    gone = break_even(f, LOAN, CASH | {"expected_return_pct": None}, "annual_rate_pct", 0, 30)
    assert gone["value"] is None and gone["reason"] == "missing_inputs"
    with pytest.raises(ValueError):
        break_even(f, LOAN, CASH, "annual_rate_pct", 5, 5)


def test_describe_inputs_routes_by_type_and_rejects_unknown_types():
    assert describe_inputs("take_loan")["required"] and describe_inputs("wait")["required"] == ["amount", "until"]
    with pytest.raises(ValueError):
        describe_inputs("sell_asset")
    with pytest.raises(ValueError):
        evaluate_path(frame(), {"id": "x", "label": "x", "type": "sell_asset"})
