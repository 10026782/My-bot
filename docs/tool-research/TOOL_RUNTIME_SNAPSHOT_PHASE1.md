# SCOREBOS Tool Runtime Snapshot — Phase 1

## Scope

This phase proves the bounded runtime boundary: the existing curated seed is converted into one generated, validated, read-only snapshot. It does not add a database, Airtable, crawler ingestion, Mini-App, ActionGateway change, approval path, or external production service.

## Current seed

`business_tool_registry.py` remains the transition seed and compatibility layer. `tool_registry.py` remains the internal SCOREBOS execution/permission registry and is not merged with this catalog.

## Snapshot contract

`data/tool_registry/runtime_snapshot.json` contains `schema_version`, `generated_at`, `source_revision`, `content_hash`, `tools`, `capabilities`, and `tool_capabilities`. The file is generated; it must not be hand-edited. Records use stable slugs and deterministic relation IDs (`tool_id:capability_id`).

Runtime Tool records contain only identity, URL, class/tags, lifecycle and decision gates, privacy class, verification, enabled/runtime-visible state, and the formatter playbook fields. Editorial seed fields are not copied unless they affect runtime behavior.

## Generator and validator

`tools/tool_runtime_snapshot.py` reads the seed, normalizes its existing capability phrases, deduplicates pair relations, sorts all collections, calculates a content hash, validates, and writes only after validation succeeds. It rejects duplicate IDs, broken references, unknown enums, malformed HTTPS URLs, and an eligible relation whose parent is not runtime-visible.

Runtime visibility requires an approved, verified, enabled Business Tool. Operator, infrastructure, deferred, rejected, deprecated, unverified, disabled, and POC records remain source evidence but are excluded from normal recommendations.

## Runtime loader and resolution

`load_tool_runtime_snapshot()` performs local read-only loading and strict validation. There is no network, database, mutation, or candidate fallback. `business_tool_registry.list_tools()`, direct lookup, and deterministic matching now construct runtime Tool records from the validated snapshot. The seed is not read for runtime name, URL, playbook, privacy guidance, agent mode, execution mode, aliases, or capability IDs. Matching resolves current wording to snapshot-published aliases and capability IDs; the existing formatter and direct-link UX remain unchanged.

If the snapshot is missing or invalid, the recommendation path returns no recommendation and the existing normal SCOREBOS routing continues.

## Capability mapping

The generator maps only current seed capability wording. The first snapshot contains 28 normalized capabilities and 30 explicit relations, including `pdf_merge`, `pdf_split`, `pdf_compress`, `image_resize`, `image_compress`, `csv_repair`, `csv_validate`, `data_chart`, `json_visualize`, and `file_convert`. Ambiguous source phrases use the smallest existing semantic mapping; no new business capability research was added.

## Migration matrix

| Source class | Records | Runtime result | Mode |
|---|---:|---|---|
| Business | 13 | Runtime-visible when approved and verified | `GUIDED_EXTERNAL` |
| Operator | 2 | Preserved in seed/snapshot; hidden from normal users | `OPERATOR_ONLY` |
| Infrastructure candidates | 4 | Deferred; hidden | `POC_ONLY` |

The current 13 Business Tools remain reachable: BentoPDF, VERT, Squoosh, PairDrop, RAWGraphs, csv.repair, SQL for Files, CyberChef, SVGOMG, Mr. Data Converter, JSON Crack, Metadata Remover, and ShareClean. No operator or infrastructure candidate is exposed by business matching.

## Fail-closed evidence

The test module covers valid loading, schema/ID/reference/URL corruption, ineligible runtime records, deterministic generation, capability matching, direct lookup, operator/deferred hiding, missing snapshots, and malformed snapshots. Syntax validation also passes with `python3 -m py_compile`.

## Remaining Phase 2 work

One bounded next step: define the canonical editorial storage contract and owner-write workflow. Do not implement it as part of Phase 1.

## VERDICT

### SNAPSHOT GENERATION

`PASS`

### SNAPSHOT VALIDATION

`PASS`

### RUNTIME CONSUMPTION

`PASS`

### FAIL-CLOSED

`PASS`

### CURRENT TOOLS MIGRATED

`19 total records; 13 runtime-visible Business Tools`

### CAPABILITIES NORMALIZED

`28`

### STATIC SEED STATUS

`TRANSITION SEED`

`TOOL_REGISTRY` is used by generation only; runtime reads the validated snapshot.

### DYNAMIC STORE

`NOT IMPLEMENTED`

### NEXT PHASE

Define the canonical editorial storage and owner-write workflow only.
