# Commercial Schema V2 — Add-Only Status

**Verified:** 03/09/2026 (Asia/Jerusalem)  
**Truth source:** live Airtable schema in the main commercial base  
**Status:** SCHEMA V2 ADD-ONLY IMPLEMENTED — WRITERS NOT SWITCHED

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
- Deals, Payment Terms, and Payments expose Currency as native single-selects.
  The pre-existing Charges.Currency field remains single-line text for add-only
  compatibility; code must validate it against the same vocabulary until a
  non-destructive replacement is approved.
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

The Deal fields `Start Date`, `Total Charged`, `Total Collected`, and
`Outstanding` are not live and require a follow-up native schema operation.

The approved expanded Payment Terms vocabularies are not fully represented in
the live select configurations: Calculation Type, Calculation Basis, Trigger
Type, and Cadence still expose their legacy option subsets. Future V2 writers
must remain blocked from unsupported options until those live options exist.
