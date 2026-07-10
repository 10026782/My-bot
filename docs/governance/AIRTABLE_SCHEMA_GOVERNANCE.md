# Airtable Schema Governance

Airtable schema/value bugs (drift, missing fields, tableId/fieldId mismatch, select-option
mismatch) have been fixed one-off, repeatedly, in this codebase (see `BUG_AUDIT_LOG.md`:
BUG-008, BUG-017 through BUG-021, BUG-038). This doc explains the layered governance pipeline
built to stop that pattern — five independent, feature-flagged PRs, each with its own scope.

**No single PR "solves" Airtable schema bugs.** Each layer below closes a specific class of
failure. Track what's actually fixed per bug in `BUG_AUDIT_LOG.md`'s `Closes:` field, not by
assuming this pipeline covers everything.

## Source of truth vs. seed vs. runtime provider vs. snapshot archive

Four distinct concepts, easy to conflate:

- **`airtable_schema.py`** — the canonical source of truth for table/field *names* in code
  (`Tables`, `*Fields` classes). Hand-maintained; drifts from live Airtable when tables/fields
  change without a matching code update (that drift is exactly what BUG-020 documented).
- **`schema_cache.json`** (repo root) — a **seed**, not a live snapshot. Its `fetched_at` field
  reads `"seed-from-schema-py"` — it was generated from `airtable_schema.py` itself, not fetched
  from Airtable. Used as the last-resort fallback when nothing else is available (see BUG-021).
- **`core/runtime_schema_provider.py`** (`RuntimeSchemaProvider`, PR3B) — the live read path.
  Resolves schema in priority order: fresh Meta API fetch → last-good in-memory → latest snapshot
  archive record (PR3A) → `schema_cache.json` seed. Captures field type + select choices, not just
  names. Ships behind `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE` (`off`/`shadow`/`enforce`,
  not a plain boolean — read via `get_runtime_schema_provider_state()`, not `is_enabled()`).
- **`tools/schema_snapshot.py`** (PR3A) — an archival job. Fetches the live Meta API schema,
  normalizes it (keeping table/field **IDs**, which nothing else in the repo kept before this),
  and archives JSON+XLSX to an Airtable `Schema_Snapshots`-style table for audit history. Behind
  `FEATURE_AIRTABLE_SCHEMA_SNAPSHOT` (default OFF, requires a manual pre-activation checklist —
  the target table must already exist; this job never auto-creates it).

## What PR2 validates

`tools/airtable_gateway.py`'s `validate_airtable_fields()` gained a value-validation step
(`_provider_invalid_select_values()`) on top of the pre-existing unknown-*field*-name check:
`singleSelect`/`multipleSelects` values are checked against the live choices `RuntimeSchemaProvider`
returns, before the write hits Airtable. Behind `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE`
(`off`/`shadow`/`enforce`) — only runs when the provider has real per-field choice data
(`mode="full"`); silently skips when only name-level seed data is available, to avoid false
positives. This blocks write-time value/casing mismatches (e.g. `"real_estate"` vs `"Real Estate"`,
trailing spaces — the exact BUG-008 failure mode). It does **not** fix upstream domain-propagation
bugs (Router → Agent → Output Gateway) if that turns out to be the actual root cause of a given
bug — that's a separate class of problem.

## What PR_RESPONSE_CONTRACT validates, and why it's a separate bug family

Unrelated to schema *names* or *values* — this is about how callers interpret Airtable write
*results*. Several callers did `"✅" in result` string/emoji matching against what
`airtable_add()`/`airtable_update()` actually return: a structured dict (`{ok, external_id, ...}`,
the C53-A contract). That check is always false against a dict, so success/failure was
misreported. Fixed callers now check `result.get("ok")` directly, or route through
`core/action_result.py`'s `ActionResult.from_airtable_add/update` where an object is more useful
than a bool. `tools/audit_result_parsing.py` is a static lint guard against reintroducing the
pattern. This is a response-contract bug family, not a schema-drift one — don't conflate the two
when triaging a new report.

## Running the diagnostic

`tools/check_airtable_schema_runtime.py` (PR3C, rev.2) is a manual, on-demand CLI — no scheduler
job, no feature flag. Run it directly:

```bash
python3 tools/check_airtable_schema_runtime.py
```

Reports env-present / Meta-API-reachable / tables-fetched-count / provider status / schema source,
as safe yes/no/count output — never logs secret values. Use it to sanity-check the pipeline after
a deploy or before flipping a state from `shadow` to `enforce`.

## Rule going forward

**Do not reintroduce ad-hoc schema validation outside `RuntimeSchemaProvider`.** The following
stay as their own, separate, orthogonal concerns and are *not* superseded by the above:
`READ_ONLY_FIELDS`/`LINKED_RECORD_FIELDS`/`_ALWAYS_FORBIDDEN` sentinel checks in
`tools/airtable_gateway.py` (security/coercion), `schema_audit.py` (manual offline compare+refresh
CLI), `tools/schema_governance.py` (drift report CLI), `check_alias_consistency()` (startup
consistency check), `action_validator.py` (pre-dispatch structural gate, not schema-aware).

## Related modules (see also `CLAUDE.md`'s module list)

`core/runtime_schema_provider.py`, `tools/schema_snapshot.py`,
`tools/check_airtable_schema_runtime.py`.
