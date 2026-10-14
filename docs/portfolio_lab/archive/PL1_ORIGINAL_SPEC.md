# Portfolio Lab — PL-1

Status: planned on an isolated PR branch, 2026-10-13. No production integration.

## Gate 0 and scope

Verified origin/main: `5e20e6069e558e6e4a8bb8712c7b49a30177da08`.
Shared checkout clean; pre_session_gate exit 0. Open branches: database/Neon
`ccr-8ce58b74-gz57gr`, librarian `context-librarian/auto-maintenance`; no engine overlap.
Context Librarian bootstrap: N/A under AGENTS.md's explicit trigger scope.
Read AGENTS.md, CLAUDE.md, both PLANNING_GATE documents, GOVERNANCE_RULES,
MODULE_RULES, revised cross-layer gate, RELEASE_CHECKLIST and existing CI.
Search on main found no accumulation/strategy engine. Financial Control records
savings destinations; its CRM service is not a mathematical engine and is not reused.

Cross-Layer Impact: NONE. Owner: standalone research package `portfolio_lab`.
No existing caller, contract, authority, persistence, fallback or dormant runtime
changes. New callers are local CLI and unit tests only. Root package chosen over
core/portfolio_lab because core/__init__.py imports operation_identity and routing.
No change to core/__init__.py, app, TMA, Airtable, scheduler or dependency files.

Contract-chain check: existing production entry points excluded by source search;
this is a new local contract, not a guessed call to an existing API. Proposed chain:
stdin JSON -> CLI -> Scenario/Asset -> simulate/compare -> stdout JSON -> unit tests.
No external write/send execution point; stdout is the only output.

Eight planning answers: (1) owner requests reproducible long-term comparisons;
(2) no equivalent engine found; (3) monthly pure Python loop + comparison;
(4) no second bot execution path; (5) no gateway/router bypass;
(6) independent annuity formula, cash-flow sums and CLI round trip;
(7) research lacks an inspectable baseline without this engine;
(8) root-level test_portfolio_lab.py is executed by existing CI.
Architectural gates: no infrastructure imports, authorization or inbound handlers;
raw-first external capture and bot domain entity rules N/A for local mathematics;
no external state/evidence write path.

## Architecture and contracts

Standard library only. models.py holds immutable typed inputs; engine.py simulates
monthly cash flows, aggregates annual results and compares strategies; __main__.py
validates stdin JSON and emits strict JSON. __init__.py exposes only this API.

Scenario: ILS, initial capital, horizon 10–100 years (60 default), monthly contribution
(8000 default, scalar or exactly one value per year), scalar/yearly inflation,
optional inflation indexing, beginning/end-of-month deposits (end default), start
calendar month, provenance and result type. Asset: name, allocation, scalar or
exact yearly total returns, effective annual or nominal annual/monthly compounded
convention, gross/net recurring-cost basis, management fee, buy/sell proportional fees.
Weights nonnegative and sum to 1; no leverage, sales or withdrawals during accumulation.
Amounts/rates must be finite; effective annual returns must exceed -100% (total wipeouts are deferred).

End deposits: growth and recurring fee first, then deposit. Begin deposits: deposit
then growth and recurring fee. Initial purchase at month 0. Effective annual return
becomes (1+r)^(1/12); nominal annual becomes 1+r/12. Recurring annual fee is an
annual fraction of assets retained: monthly factor (1-fee)^(1/12), applied after
growth. Net returns reject a nonzero recurring fee to prevent double counting.
Annual observations are after each 12 months. Annual shocks are supplied as yearly
returns spread evenly across their year, NOT instantaneous crash/recovery paths.

Inflation grows monthly. Indexed contributions use CPI at their deposit time,
including changing annual base contributions. Real profit subtracts every deposit
in start-date purchasing power, not nominal contributions from deflated final value.
Parallel zero-cost balances distinguish fees actually paid from lost compounding.
No rebalancing: initial capital and deposits follow target weights; existing holdings
drift. Components have independently supplied returns and costs. Four named allocation
templates do not infer expected returns; 90/10 is experimental.

Outputs: normalized inputs, engine version, provenance/date, assumptions/warnings,
annual values before/after costs, contributions, real contributions/profit, recurring
and trading fees, cost opportunity impact, full-sale proceeds, and nullable tax/net
sale value. Portfolio time-weighted annualized gross/net-recurring returns exclude
transaction fees and tax; capital/profit include buy fees. No IRR claim.

Optional terminal tax port receives dated synthetic purchase lots and sale proceeds.
No Israeli rules, rates, lot-identification legality, CPI/FX tax basis or partial sales
implemented here. Adapter must return amount, rule identity, parameters, source/date
and verification state; unverified assessments always labelled scenario. No tax port
means tax/net-after-tax are null, never assumed zero. No tax during accumulation.
Synthetic units are accounting units, not broker security prices.

## Dependencies evaluated before adoption

Checked 2026-10-13 against upstream sources:
- QuantStats: Apache-2.0, release history maintained; NumPy, pandas, SciPy,
  matplotlib/seaborn, tabulate and yfinance. Return-series reports/risk analytics;
  does not replace the requested contribution timing/cost/tax-lot simulator.
  https://github.com/ranaroussi/quantstats/blob/main/pyproject.toml
  https://github.com/ranaroussi/quantstats/releases
- Riskfolio-Lib: BSD-3-Clause, maintained repository and changelog; NumPy, SciPy,
  pandas, CVXPY/solvers and plotting/statistics packages. Allocation optimization;
  not a dated accumulation/tax engine. Larger solver stack unnecessary for PL-1.
  https://github.com/dcajasn/Riskfolio-Lib
  https://github.com/dcajasn/Riskfolio-Lib/blob/master/LICENSE.txt
No dependency adopted. Reassess these for historical risk/optimization phases.

## Work and validation

1. Models + monthly engine; 2. comparison/templates + strict JSON CLI;
3. unit tests/independent formulas; 4. evidence/status documentation + review PR.
Tests: zero return and capital, fixed/changing/indexed deposits, both timings,
nominal/effective conversion, inflation purchasing power, fee reconciliation,
net-fee rejection, decline/recovery and reordered equal arithmetic/geometric means,
terminal tax port/lots, invalid JSON/types/nonfinite inputs, 100-year large values,
strategy weights/independent returns and deterministic replay.
Independent annuity oracle: P*(1+i)^n + C*((1+i)^n-1)/i for end deposits;
begin deposits multiply the annuity term by (1+i). It verifies the loop rather
than replacing it. Investor.gov calculator is an external reference:
https://www.investor.gov/financial-tools-calculators/calculators/compound-interest-calculator
Only claim external numerical cross-check if its output is actually obtained.

Deferred: calibrated historical prices, instantaneous crises and recovery paths,
probabilities, partial sales, validated tax rules, stock selection, survivorship,
OOS, dashboard and bot integration. Mathematical/assumption/historical labels do
not authenticate data. Long horizons amplify uncertain return assumptions.
