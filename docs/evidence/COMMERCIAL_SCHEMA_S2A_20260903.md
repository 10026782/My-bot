# Commercial Schema S2A — live schema evidence

- Observed: 03/09/2026, Asia/Jerusalem.
- Environment: live Airtable base `בסיס עיקרי`.
- Method: direct read-only Airtable MCP schema and record-count queries.
- Counts: Deals 5; Payments 1 legacy; Payment Terms, Charges, Allocation Rules,
  Allocation Snapshots, Deal Economics, and Organizations 0.
- Confirmed gaps: incomplete Payment Term selects; no tier/custom or dedicated
  due-date detail fields; Charges.Currency text; missing Deal Start Date and
  aggregates; Contact-only allocation beneficiaries.
- Mutation result at this checkpoint: none.

## Post-approval additive write checkpoint

- Thirteen native fields were created and read back from the live schema:
  Payment Terms canonical `Calculation Type Code`, `Calculation Basis Code`,
  `Trigger Type Code`, and `Cadence Code` selects; `Tier Configuration` and
  `Custom Calculation Rule` multiline text; `Specific Due Date` and
  `Schedule Anchor Date` dates; Deals `Deal Type Code` select and `Start Date`;
  Charges `Currency Code` select; and `Beneficiary Organization` links on both
  Allocation Rules and Allocation Snapshots.
- Canonical choices read back exactly: Deal Type = `one_off`, `recurring`,
  `commission`, `service`, `other`; Currency = `ILS`, `USD`, `EUR`; Payment
  Term choices match the approved V2 vocabularies recorded in
  `airtable_schema.py`.
- Both beneficiary links read back as native links to `Organizations`.
- No record was created or modified. Post-write counts remain: Deals 5;
  Payments 1 legacy; every other commercial V2 table 0.
- Charges `Total Paid` remains a valid native rollup and `Remaining Balance`
  remains a valid formula.
- Native blocker: the installed schema connector cannot create `rollup` fields
  or edit select options, and the Windows schema UI helper failed before any UI
  action because this WSL task URI is unsupported. Deals `Total Charged` and
  `Total Collected` therefore remain absent; `Outstanding` must not be created
  before those dependencies exist.
