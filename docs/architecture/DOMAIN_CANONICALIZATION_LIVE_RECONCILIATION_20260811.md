# D1 live Airtable reconciliation — 2026-08-11

Base inspected: `app4bcgoX7t0HUVnm`.

Status: **LIVE SCHEMA/DATA VERIFIED** by read-only inspection after the manual
Airtable updates. No Airtable writes were performed by this verification.

## Canonical business domain

`real_estate`, `import`, `media`, `saas`, `finance`, `recruitment`, `general`.

`crm` and `internal` remain Router-only namespaces. Decisions remain a
separate Decision Hub taxonomy.

## Live fields verified

| Table / field | Verified live options | Records | Result |
|---|---|---:|---|
| Marketing Demand.Domain | `real_estate`, `import`, `media`, `saas`, `finance`, `general`, `recruitment` | 0 | canonical option present |
| TRAFFIC_SOURCES.Suitable Domains | `real_estate`, `import`, `media`, `saas`, `finance`, `general`, `recruitment` | 0 | canonical eligibility option present |
| Business Memory.Domain | `General`, `Real Estate `, `Saas`, `Import`, `Media`, `Finance`, `recruitment` | 34, empty | live recruitment storage option is lowercase |
| Lead Events.Domain | includes `recruitment` and legacy `recruiting` | 61 | new writes use canonical `recruitment`; legacy option retained |

## Business Memory adapter contract

`domain_utils.py` keeps `recruitment` as the canonical business value.

- `business_domain_to_airtable(..., vocabulary="business_memory_legacy")`
  emits live lowercase `recruitment`.
- `business_domain_from_airtable(..., vocabulary="business_memory_legacy")`
  accepts lowercase `recruitment` and legacy title-case `Recruitment` through
  the adapter's case-insensitive read path.
- No Marketing-local domain mapping was introduced.

## Post-manual-update status

No schema mutation remains pending for these D1 fields. No records require
rewriting. Lead Events `recruiting` remains a read-compatible legacy option;
its record count is zero, and it is not emitted by current writers.

Other legacy display values in Ventures, Tasks, and Business Memory remain
behind their explicit adapters. Decision Hub values and unrelated fields such
as Assets.Domain were not migrated.

## Scope notes

Marketing implementation files named in the brief were absent from this
worktree, so no M1 runtime behavior was added or changed here. This document
records only the D1 live schema/data reconciliation.
