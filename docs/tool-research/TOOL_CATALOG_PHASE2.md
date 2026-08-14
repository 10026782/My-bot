# SCOREBOS Tool Catalog — Phase 2

## Boundary

Phase 2 adds a small canonical editorial catalog inside the existing PostgreSQL database. The database is not a runtime dependency.

tools → capabilities → tool_capabilities → validated local runtime_snapshot.json → runtime.

Runtime continues to read only the local validated snapshot. A database outage, partial edit, invalid candidate, or failed generator cannot make the bot use a new record.

## Schema

Migration: core/migrations/002_tool_catalog.sql.

The three tables are:

- tools: stable tool identity, URL, class/tags, aliases/tasks, playbook, execution/agent mode, lifecycle, decision, privacy, verification, and enabled state.
- capabilities: normalized capability identity and lifecycle metadata.
- tool_capabilities: explicit many-to-many relations with relation-level execution, lifecycle, verification, enabled, and priority fields.

No Evidence, decision-history, crawler, Airtable, or admin tables are added in this phase. The playbook and tasks JSONB columns are runtime-read-model inputs, not a second catalog.

The migration is idempotent and is discovered by the existing PostgreSQL migration runner.

## Importer

tools/import_tool_catalog_seed.py calls import_seed_to_db().

The importer is intentionally one-way and bounded:

1. read the current Python seed;
2. normalize existing capability phrases to stable IDs;
3. upsert the three catalog tables;
4. commit the catalog transaction.

It does not publish a snapshot, enable candidates, delete records, or alter runtime state. Re-running it is safe and updates the canonical catalog from the transition seed while this migration is being established.

## DB-backed snapshot generator

tools/generate_tool_runtime_snapshot_from_db.py calls generate_snapshot_from_db().

The generator:

- reads only tools, capabilities, and tool_capabilities;
- builds the same versioned snapshot contract as Phase 1;
- calculates runtime visibility from DB lifecycle, verification, class, execution mode, and enabled gates;
- validates all IDs, URLs, enums, references, and runtime eligibility before writing;
- writes only after validation succeeds.

The generator is the only path from catalog DB to runtime snapshot. Runtime has no DB query and no seed fallback.

## One-time transition

The intended first rollout sequence is:

run migration
→ import current seed
→ generate snapshot from DB
→ validate snapshot
→ review diff/hash
→ publish snapshot with normal code delivery

The existing Python seed remains a transition/generation input until the catalog has been imported and independently reviewed. Runtime authority is the snapshot.

## Fail-closed rules

- Missing or invalid snapshot: no Business Tool recommendation; normal SCOREBOS routing continues.
- Missing DB: importer/generator fails clearly; runtime is unaffected.
- Invalid DB row: generator rejects the snapshot; no partial snapshot is written.
- Operator, infrastructure, deferred, unverified, rejected, deprecated, or POC records remain catalog evidence but are not runtime-visible.
- No crawler or UI can publish directly in this phase.

## Tests

test_tool_catalog_db.py covers:

- idempotent seed-import write behavior;
- DB-authored name, URL, playbook/privacy guidance, and capability relation appearing in the generated runtime record;
- infrastructure records remaining hidden.

Phase 1 snapshot validation and runtime tests remain unchanged.

## Status

This is an implementation branch only. No production database was changed, no import was run against a real database, and no runtime deployment was performed.

## VERDICT

### CANONICAL SOURCE

PostgreSQL Tool Catalog DB for editorial state; runtime_snapshot.json for runtime reads.

### TABLES

tools, capabilities, tool_capabilities

### IMPORTER

IMPLEMENTED — one-way, idempotent, transition-only

### DB SNAPSHOT GENERATOR

IMPLEMENTED — strict validation before write

### RUNTIME DB ACCESS

NONE

### AIRTABLE

NOT IMPLEMENTED

### CRAWLER PUBLISHING

NOT IMPLEMENTED

### EVIDENCE / DECISION HISTORY

NOT IMPLEMENTED — later bounded phase

### NEXT PHASE

Add tool_evidence only after the three-table catalog import and DB-generated snapshot are verified.
