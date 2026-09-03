# Commercial Schema V2 — Add-Only Status

**Verified:** 03/09/2026 (Asia/Jerusalem)  
**Truth source:** live Airtable schema in the main commercial base  
**Status:** S2A IN PROGRESS — NATIVE DEAL ROLLUPS BLOCKED; WRITERS NOT SWITCHED

## Live schema

The following tables exist with zero records: `Charges`, `Allocation Rules`,
`Allocation Snapshots`, and `Deal Economics`. `Organizations` exists with the
primary field `Organization Name` and no pre-created organization records.

The existing tables remain present and additive-only:

- Deals: 5 records
- Payment Terms: 0 records
- Payments: 1 legacy record

No records were created, updated, reinterpreted, or migrated.

## Commercial contract

`Deal → BillingTerm → Charge → Payment`

`Charge → AllocationSnapshot` and `Deal → AllocationRule` are separate
relationships. `Deal → DealEconomics` is an extension relationship.
Organizations are canonical business entities distinct from person Contacts.

## Native-field verification

- Currency vocabulary is exactly `ILS`, `USD`, `EUR` on the new currency selects.
- Deals, Payment Terms, Payments, and Charges expose canonical Currency as
  native single-selects. The pre-existing Charges.Currency text field remains
  untouched; V2 uses the additive `Currency Code` compatibility field.
- Charges has native currency/date fields, a valid `Total Paid` rollup over
  Payments through `Charge`, and a valid `Remaining Balance` formula.
- Deal Economics has valid `Total Cost` and `Gross Profit` formulas.
- Allocation Snapshots has native currency fields and a native `Resolved At`
  date-time field.
- Existing Deal Stage values and legacy domain-specific fields were preserved.

## Compatibility boundary

Legacy `Payments` remains quarantined. No production writer or reader was
switched, no BillingTerm-to-Charge scheduler was introduced, and no legacy
Payment row was interpreted as an actual V2 Payment.

Deal `Start Date` is live. `Total Charged` and `Total Collected` remain blocked
on a native rollup-capable schema path; `Outstanding` is intentionally deferred
until those rollup dependencies exist.

The approved expanded Payment Terms vocabularies are represented by additive
canonical `Calculation Type Code`, `Calculation Basis Code`, `Trigger Type
Code`, and `Cadence Code` selects. Legacy select fields and their existing
writers remain untouched. Tier/custom detail and deterministic due-date fields
are live. Deal Type is canonicalized in the additive `Deal Type Code` select.
Allocation Rules and Snapshots now support Organization beneficiaries through
parallel native links while retaining Contact beneficiaries.

## S2A native blocker

The current schema connector cannot create rollups. The remaining live steps
must use a native rollup-capable path on Deals:

1. `Total Charged`: roll up `Charges → Amount` with `SUM(values)`.
2. `Total Collected`: roll up `Charges → Total Paid` with `SUM(values)`.
3. Only then create `Outstanding` as
   `{Total Charged} - IF({Total Collected}, {Total Collected}, 0)`.

Until live readback validates all three, S2A is not closed and S2B mutation
primitives must not start.
