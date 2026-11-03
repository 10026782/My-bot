"""G7 — בדיקות מבניות עוינות למנוע המסלולים (PATH_ENGINE_ARCHITECTURE_SPEC §6ב).

מוכיחות: זהות חשבונאית לכל סוג מסלול (כל המדדים מול "לא עושים כלום"), דטרמיניזם ושחזור, דחיית קלט עוין בכל שדה מספרי, תוצאה סופית ובת-סריאליזציה,
אי-התאמה בין ודאות לנתון חסר, טקסט המלצה בתוך תווית, וחסמי גודל. אין כאן חישוב כספי חדש — רק בדיקה של מה שהמנוע כבר מחשב."""

from __future__ import annotations

import copy
import json
import math

import pytest

from portfolio_lab.path_comparison import compare_paths, core, evaluate_path, make_frame, sensitivity


def frame(**over):
    raw = {"today": "2026-10-25", "compare_at": "2029-10-25", "inflation_pct": [2.5, 2.5, 2.5], "alternative_return_pct": 6, "owner_inputs_label": "הנחות בעלים 25/10"}
    raw.update(over)
    return make_frame(raw)


LOAN = {"id": "loan", "label": "הלוואה", "type": "take_loan", "amount": 250000, "annual_rate_pct": 3, "term_months": 36, "fees": 1500, "approved": True}
CASH = {"id": "cash", "label": "מזומן", "type": "use_liquid_cash", "amount": 250000, "expected_return_pct": 6, "fee_pct": 0.5, "withdraw_fee": 0}
WAIT = {"id": "wait", "label": "להמתין", "type": "wait", "amount": 250000, "until": "2027-10-25", "price_change_pct": 3}
PREPAY = {"id": "prepay", "label": "פירעון מוקדם", "type": "prepay_loan", "balance": 100000, "annual_rate_pct": 6, "remaining_months": 60, "early_fee": 500,
          "source_return_pct": 4, "source_fee_pct": 0.5}
ALL = (LOAN, CASH, WAIT, PREPAY)


def walk(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, node


# ═══ זהות חשבונאית: כל המדדים מול "לא עושים כלום" ═══

@pytest.mark.parametrize("spec", ALL, ids=lambda s: s["type"])
def test_the_economic_cost_is_exactly_minus_the_after_latent_tax_net_worth_change_for_every_path_type(spec):
    r = evaluate_path(frame(), spec)
    cost = r["measures"]["economic_cost"]["net_cost"]
    after = r["measures"]["net_worth"]["after_latent_tax"]["nominal"]
    assert cost is not None and after is not None
    assert round(cost + after, 2) == 0.0


@pytest.mark.parametrize("spec", ALL, ids=lambda s: s["type"])
def test_the_headline_net_worth_change_equals_the_after_latent_tax_row(spec):
    r = evaluate_path(frame(), spec)
    assert r["result"]["net_worth_change_at_compare_date"] == r["measures"]["net_worth"]["after_latent_tax"]


@pytest.mark.parametrize("spec", ALL, ids=lambda s: s["type"])
def test_latent_tax_never_makes_a_path_look_worse_than_before_tax_and_the_real_row_never_exceeds_the_nominal_loss(spec):
    r = evaluate_path(frame(), spec)
    nw = r["measures"]["net_worth"]
    assert nw["after_latent_tax"]["nominal"] >= nw["before_latent_tax"]["nominal"] - 0.005     # tax can only reduce a forgone gain
    for row in nw.values():
        assert abs(row["real"]) <= abs(row["nominal"]) + 0.005 or row["nominal"] == 0           # discounting by positive inflation shrinks the magnitude


def test_a_loan_costs_exactly_interest_plus_fees_and_the_cash_effect_is_net_proceeds_minus_payments():
    f = frame()
    r = evaluate_path(f, LOAN)
    interest_through, fees = r["provenance"]["payment"] * r["provenance"]["payments_through_compare"] - (250000 - r["provenance"]["liability_at_compare"]), 1500
    assert abs(r["measures"]["economic_cost"]["net_cost"] - (interest_through + fees)) < 0.5      # the payment is rounded to the cent before it is multiplied
    expected_cash = 250000 - fees - r["provenance"]["payment"] * r["provenance"]["payments_through_compare"]
    assert abs(r["result"]["cash_at_compare_date"] - expected_cash) < 0.5


def test_using_cash_costs_forgone_growth_after_tax_plus_the_withdraw_fee_and_waiting_costs_only_the_price_change():
    f = frame()
    cash = evaluate_path(f, CASH | {"withdraw_fee": 700})
    before = cash["measures"]["net_worth"]["before_latent_tax"]["nominal"]
    tax = cash["provenance"]["tax_on_forgone_growth"]
    assert round(cash["measures"]["net_worth"]["after_latent_tax"]["nominal"] - (before + tax), 2) == 0.0
    assert round(cash["cost"]["fees_total"], 2) == 700.0
    assert round(-before - 700.0 - cash["cost"]["opportunity_cost"], 2) == 0.0              # before-tax change = -(forgone growth + withdraw fee)
    wait = evaluate_path(f, WAIT)
    assert round(wait["measures"]["economic_cost"]["net_cost"] - 250000 * 0.03, 2) == 0.0


# ═══ דטרמיניזם ושחזור ═══

@pytest.mark.parametrize("spec", ALL, ids=lambda s: s["type"])
def test_the_same_inputs_give_a_byte_identical_result_and_the_input_is_not_mutated(spec):
    f, s = frame(), copy.deepcopy(spec)
    a, b = evaluate_path(f, spec), evaluate_path(f, spec)
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)
    assert spec == s


def test_a_result_carries_the_versions_needed_to_reproduce_it_and_a_different_frame_changes_the_digest():
    a, b = evaluate_path(frame(), CASH), evaluate_path(frame(alternative_return_pct=5), CASH)
    cv = a["calc_version"]
    assert set(cv) == {"core", "module", "tax_rate", "assumptions"} and all(cv.values())
    assert a["frame_digest"] != b["frame_digest"]


# ═══ תוצאה סופית ובת-סריאליזציה ═══

@pytest.mark.parametrize("spec", ALL, ids=lambda s: s["type"])
def test_every_number_in_a_result_is_finite_and_the_result_round_trips_through_json(spec):
    r = evaluate_path(frame(), spec)
    for path, v in walk(r):
        assert not isinstance(v, float) or math.isfinite(v), path
    assert json.loads(json.dumps(r, ensure_ascii=False, allow_nan=False)) == r


def test_the_validator_rejects_a_non_finite_number_anywhere_in_a_result():
    for bad in (float("nan"), float("inf"), float("-inf")):
        r = evaluate_path(frame(), CASH)
        r["provenance"]["tax_on_forgone_growth"] = bad
        with pytest.raises(ValueError):
            core.validate_path_result(r)
        r = evaluate_path(frame(), CASH)
        r["after_action"]["given_up"]["assets"][0]["value"] = bad
        with pytest.raises(ValueError):
            core.validate_path_result(r)


# ═══ ודאות מול נתון חסר ═══

def test_a_result_with_a_missing_input_is_never_expected_or_confirmed():
    f = frame()
    for spec in (LOAN | {"fees": None}, CASH | {"withdraw_fee": None}, CASH | {"expected_return_pct": None}):
        spec = {k: v for k, v in spec.items() if v is not None}
        r = evaluate_path(f, spec)
        assert r["missing_inputs"] and r["certainty"] in ("unknown", "uncertain"), spec
    r = evaluate_path(f, CASH)
    r["missing_inputs"] = ["x"]
    r["certainty"] = "expected"
    with pytest.raises(ValueError):
        core.validate_path_result(r)


# ═══ קלט עוין ═══

HOSTILE = (float("nan"), float("inf"), float("-inf"), -1, True, "100", [1], {"a": 1}, 1e300)
NUMERIC = {
    "take_loan": ("amount", "annual_rate_pct", "term_months", "fees"),
    "use_liquid_cash": ("amount", "expected_return_pct", "fee_pct", "withdraw_fee", "balance"),
    "wait": ("amount", "price_change_pct"),
    "prepay_loan": ("balance", "annual_rate_pct", "remaining_months", "early_fee", "source_return_pct", "source_fee_pct"),
}


@pytest.mark.parametrize("spec", ALL, ids=lambda s: s["type"])
def test_every_numeric_field_rejects_hostile_values_with_a_value_error_and_never_echoes_the_value(spec):
    f = frame()
    for field in NUMERIC[spec["type"]]:
        for bad in HOSTILE:
            if field in ("annual_rate_pct", "expected_return_pct", "source_return_pct", "price_change_pct") and bad == -1:
                continue                                                  # a negative rate / price move is a legal input
            try:
                evaluate_path(f, spec | {field: bad})
            except ValueError as exc:
                assert str(bad) not in str(exc) or str(bad) in ("1", "-1"), (field, bad)
            else:
                pytest.fail(f"{spec['type']}.{field}={bad!r} was accepted")


@pytest.mark.parametrize("spec", ALL, ids=lambda s: s["type"])
def test_unknown_fields_and_malformed_ids_and_labels_are_rejected(spec):
    f = frame()
    for extra in ({"score": 1}, {"recommended": True}, {"__proto__": 1}, {"note": "x"}):
        with pytest.raises(ValueError):
            evaluate_path(f, spec | extra)
    for bad in ({"id": ""}, {"id": 5}, {"label": " "}, {"label": None}, {"id": "x" * 500}, {"label": "x" * 500}):
        with pytest.raises(ValueError):
            evaluate_path(f, spec | bad)


@pytest.mark.parametrize("label", ["הכי כדאי", "מומלץ ביותר", "Best option", "recommended", "הטוב ביותר", "עדיף", "cheapest"])
def test_a_label_that_reads_as_a_recommendation_is_rejected(label):
    for spec in ALL:
        with pytest.raises(ValueError):
            evaluate_path(frame(), spec | {"label": label})


def test_a_frame_with_hostile_values_is_rejected():
    for over in ({"inflation_pct": [float("nan")]}, {"inflation_pct": [1e9]}, {"alternative_return_pct": float("inf")}, {"compare_at": "2026-10-25"},
                 {"compare_at": "2099-01-01"}, {"today": "not a date"}):
        with pytest.raises(ValueError):
            frame(**over)


# ═══ חסמי גודל ═══

def test_the_comparator_rejects_too_many_paths_and_duplicate_ids_and_an_empty_list():
    f = frame()
    many = [evaluate_path(f, WAIT | {"id": f"w{i}"}) for i in range(13)]
    with pytest.raises(ValueError):
        compare_paths(f, many)
    with pytest.raises(ValueError):
        compare_paths(f, [])
    with pytest.raises(ValueError):
        compare_paths(f, [evaluate_path(f, WAIT), evaluate_path(f, WAIT)])
    assert len(compare_paths(f, many[:12])["paths"]) == 12


def test_sensitivity_is_bounded_and_cannot_vary_identity_fields():
    f = frame()
    with pytest.raises(ValueError):
        sensitivity(f, CASH, "expected_return_pct", list(range(21)))
    with pytest.raises(ValueError):
        sensitivity(f, CASH, "expected_return_pct", [])
    for p in ("id", "type", "label"):
        with pytest.raises(ValueError):
            sensitivity(f, CASH, p, ["x"])
