# Portfolio Lab — PL-1

**Evidence level: STATIC_VERIFIED on `codex/portfolio-lab-phase1` only.**
Implementation is not merged, wired, deployed or verified in production.
Local research library; no trades, broker connection, bot routes or external I/O.

## Run

From the repository root, Python 3.10+; standard library only:

```bash
python3 -m portfolio_lab < docs/portfolio_lab/base.json > /tmp/portfolio-base.json
python3 -m portfolio_lab < docs/portfolio_lab/comparison.json > /tmp/portfolio-comparison.json
python3 -m portfolio_lab < docs/portfolio_lab/crises.json > /tmp/portfolio-crises.json
python3 -m pytest test_portfolio_lab.py -q
```

Redirect stdout to keep the **complete** reproducibility artifact: normalized
inputs, provenance, dated sources (or null/unverified), assumptions, engine version,
annual results, purchase lots, optional tax assessment and digest. Replaying
`Scenario.from_dict(result['inputs'])` with the same engine yields the same result.
For a custom tax adapter, also retain its exact code/version and parameters; engine
JSON alone cannot recreate third-party code. Currency is ILS; return inputs must
already include any FX effects. No FX conversion or market-data fetching occurs.

## Local API

```python
from portfolio_lab import Asset, Scenario, simulate, compare, strategy_assets

base = Scenario(assets=(Asset(annual_return=0.08, annual_fee=0.0015),))
result = simulate(base)
comparison = compare({"baseline": base, "lower_cost": Scenario(
    assets=(Asset(annual_return=0.08, annual_fee=0.001),))})
```

JSON accepts a scenario or `{"strategies": {"name": scenario, ...}}`. Unknown
fields, duplicate keys, nonfinite values, invalid allocations and differing
comparison cash flows fail with stderr JSON and exit 2. No partial stdout results.
Four templates: `global`, `world_em`, `three_funds`, `experimental_90_10`.
`strategy_assets(template, assumptions, weights)` requires each component's
explicit Asset assumptions; editable weights must sum to 1. Templates' example
weights and sample return rates are illustrative, not research-backed allocations.
No equal-return assumption across markets; no rebalancing of existing capital.

## Mathematics

Default: 8000 ILS/month, 60 years, end-month deposits, 8% **effective** annual
return, 2% annual inflation, 0.15% annual management fee, no initial capital or
withdrawals. Initial investment is purchased at month 0; end deposits receive
no return in their purchase month. Start date defaults to 2026-01-01 and must be
month-start; annual rows end after 12-month periods, not necessarily December.

`effective_annual` uses `(1+r)**(1/12)`; `nominal_annual_monthly` uses `1+r/12`.
Fee retention is `(1-fee)**(1/12)` after each month's growth, before end deposits.
Buy fees reduce new investment; sell fees apply only to hypothetical full sale.
No fixed/minimum commission, dividend/withholding/swap model yet. A gross total
return supplied here must state which of these are already included. A
`net_recurring` return requires `annual_fee=0`; before-cost values then remain
null because unobserved gross returns cannot be reconstructed honestly.

Scalar contributions/inflation/returns apply every year; arrays need exactly
`years` entries (a singleton is a scalar equivalent). Indexed contributions
multiply their current annual base amount by CPI **at deposit time**. Real profit
subtracts the start-date purchasing power of each separate deposit from deflated
final value. It does not subtract nominal deposits from real final wealth.

`costs_paid` excludes the hypothetical sale; `total_costs_if_sold` includes it.
`cost_impact` is the terminal difference against the same flows without costs,
including forgone compounding. TWR links monthly portfolio growth and excludes
buy/sell fees and tax; nominal/real profits include transaction fees as labelled.
The gross TWR uses the zero-cost counterfactual holdings; net TWR uses actual
holdings. These can have different drifting component weights. TWR is not IRR.

## Verified local examples

Base scenario (full evidence: [EVIDENCE.json](EVIDENCE.json)):

| Measure | ILS |
|---|---:|
| Contributions | 5,760,000.00 |
| Final value before costs | 124,658,494.85 |
| Final value after costs | 116,085,877.61 |
| Final purchasing power | 35,380,916.88 |
| Nominal profit after costs | 110,325,877.61 |
| Real profit using deflated cash flows | 32,013,391.55 |
| Fees paid during accumulation | 2,201,761.15 |
| Cost impact including forgone compounding | 8,572,617.25 |
| Tax / proceeds after tax | null — no model supplied |

Effective nominal return after recurring fees: 7.838%; real: 5.7235294%.
This is arithmetic under assumptions, not a forecast confidence interval.

The comparison fixture supplies independent component assumptions (global 8%,
World 7.5%, emerging 6.5%, S&P 8.5%, Europe 7%, stocks 6%; each fee 0.15%).
Final after costs: global 116.086m; World/EM 90.062m; three funds 113.987m;
experimental 90/10 109.395m. These inputs are unverified examples; results cannot
rank actual ETFs or validate stock picking.

Crisis fixture relocates the **same annual sequence**: 40% decline then 94.4%
recovery in years 1/2, 30/31 or 40/41. The product .6*1.944 = 1.08² preserves
8% geometric annual mean. Arithmetic mean is 8.64%, identical across the three
crisis placements but different from the constant 8% baseline. With continued
DCA: 122.041m, 116.753m and 116.400m respectively. Annual returns are smoothed
monthly; these are not instantaneous crashes, drawdown measures or probabilities.
10–50% annual declines and reordered sequences are unit-tested. Recovery durations
and intra-year observations belong to the next crisis phase.

## Verification and limits

55 unit/CLI tests passed locally (the initial EVIDENCE.json snapshot records 51). Independent annuity formulas verify beginning
and end deposits, nominal/effective conversion, and the base fee-adjusted result.
Zero return uses direct cash-flow sums. Cost identities, purchase-unit valuations,
CPI-adjusted deposits and independent sleeves provide additional oracles.
Import with `python -S` confirms no bot, Flask, NumPy, Airtable or LLM dependency.

External check fetched 2026-10-13: [Calculator.net Investment Calculator](https://www.calculator.net/investment-calculator.html?ctype=endamount&ctargetamountv=1000000&cstartingprinciplev=0&cyearsv=60&cinterestratev=8&ccompound=monthly&ccontributeamountv=8000&cadditionat1=end&ciadditionat1=monthly&printit=0&x=Calculate)
returned 142,308,219.78 for 8000/month, 60 years, 8% **nominal APR**, monthly
compounding, end deposits, zero fees. Engine agrees to cents. Calculator uses
currency-neutral dollar labels; no USD/ILS conversion is implied. Its rate
converter returned 8.29995% APY; independently verified in tests. Investor.gov's
direct request returned HTTP 403; no numerical comparison claimed for that site.
External snapshots corroborate formulas; external sites are not test dependencies.

Tax extension: `simulate(scenario, tax_model)` invokes a callable exactly once
at hypothetical terminal full sale. It receives `SaleContext`: dated lots,
synthetic units/prices, cash paid, buy fees, purchase CPI, closing prices, sale
cost and proceeds. Return `TaxAssessment` with amount, rule ID/version, parameters,
dated source and externally_verified flag. Negative taxes/refunds or tax greater
than proceeds are rejected. The library does not verify tax law; any verification
flag is the adapter provider's attestation. Unverified adapters are labelled
`scenario`. Test adapter is explicitly synthetic, not an Israeli tax calculation.
Lot selection, partial sales, CPI/FX tax bases, loss-offset rules and dividend tax
inside funds have not been implemented or legally verified.

Deferred: stock data/corporate actions, delisted companies, historical backtesting,
OOS, risk metrics, optimization, instantaneous crises, full tax engine and TMA UI.
Float arithmetic without currency rounding is intentional for research; not a
broker accounting ledger. Inputs producing overflow/underflow fail rather than
emit nonfinite JSON. Effective annual losses must exceed -100%; total wipeouts
need a separate explicit state model.

Smallest next step: monthly return paths and externally sourced crash/recovery
fixtures; then an independently reviewed tax adapter for one identified instrument.
Dependencies considered and rejected for this phase are recorded in [SPEC.md](SPEC.md).

## Governance completion record

- Status Documents Inspected: ROADMAP.md, BOSS_UNIFIED_MASTER_PLAN.md, HORIZON.md,
  CHANGE_CONTROL_LOG.md, MAINTENANCE_AUDIT_LEDGER.md, this initiative's SPEC.
- Status Documents Updated: ROADMAP.md, BOSS_UNIFIED_MASTER_PLAN.md, HORIZON.md,
  this README and EVIDENCE.json, explicitly branch-only.
- Documents Intentionally Unchanged: CHANGE_CONTROL_LOG.md (merge-owned log),
  MAINTENANCE_AUDIT_LEDGER.md (historical numbered audits); production state docs
  (no production change).
- Evidence Level Before: absent on main / owner-requested planned module.
- Evidence Level After This PR: CODE_DONE + STATIC_VERIFIED on PR branch.
- Merge Verification Required: owner review; after merge verify reachability and
  source content on current origin/main; refresh librarian only after real merge.
- Deployment Verification Required: N/A for local library; no deploy requested.
- Runtime Verification Required: N/A for bot; CLI covered by local subprocess tests.
- Remaining Work: review/merge, CI outcome, then deferred phases above.
- AGENTS.md: isolated worktree, explicit staging, pre-session gate, review-only PR;
  no main merge and no production success claim.

Pre-merge governance follow-up (2026-10-13): the owner authorized bounded
registration of the eight previously unregistered sources. One candidate,
non-authoritative REGISTER_SUPPORTING catalog node now references only their
exact paths; no policy or future-source permission changed. Local reconcile-pr
is CLEAN; 323 focused calculation/status/catalog/reconciliation tests passed.
The decision and verification ledger are in [REVIEW_DECISIONS.md](REVIEW_DECISIONS.md).
Hosted CI must be checked at the pushed head; merge/production remain unverified.
