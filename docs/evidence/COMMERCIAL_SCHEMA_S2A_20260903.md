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
- The connector used in the first checkpoint could not create native rollups;
  the owner resolved that blocker through an external schema-capable path.

## Final S2A closure verification

- Reverified directly on 03/09/2026 after the external schema update.
- Deals `Total Charged` (`fldR8hDLxXHBfmG1C`) is a valid native rollup through
  Deals.`Charges` (`fld37wAk0ZOuUnMQt`) to Charges.`Amount`
  (`fldwyUlpPGxDQB0S6`).
- Deals `Total Collected` (`fldFSdxBi1XY4FomM`) is a valid native rollup through
  the same Deals.`Charges` link to Charges.`Total Paid`
  (`fldTn9h7A4VM12UoC`).
- Deals `Outstanding` (`fldLbLZr73ZKnU6WI`) is a valid formula whose canonical
  name-form expression is
  `{Total Charged} - IF({Total Collected}, {Total Collected}, 0)`; live metadata
  resolves those references to the two field IDs above.
- The dependency chain is valid end to end: Charges.`Total Paid` remains a
  valid native rollup through Charges.`Payments` to Payments.`amount`.
- Final counts remain Deals 5; legacy Payments 1; Payment Terms, Charges,
  Allocation Rules, Allocation Snapshots, Deal Economics, and Organizations 0.
- No record was created, modified, migrated, or reinterpreted during S2A.
- Evidence level: `LIVE_SCHEMA_VERIFIED` for the complete S2A schema;
  repository alignment is separately `STATIC_VERIFIED_ON_BRANCH` until merge.
