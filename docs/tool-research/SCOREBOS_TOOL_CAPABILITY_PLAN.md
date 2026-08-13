# SCOREBOS Tool Capability Plan

## Decision

SCOREBOS has two different concepts that must not be merged:

1. `tool_registry.py` is the execution/permission registry for internal SCOREBOS tools. It owns roles, approval, emergency blocking and availability. It is not a catalog of external links.
2. `business_tool_registry.py` is the single read-only catalog for curated external tool recommendations. It owns the user-facing tool record, capability tags, privacy guidance and verification status. Bot and future TMA reads must use this module.

This keeps one canonical external-tool source without turning a runtime database, Airtable, Markdown, or an external service into a new source of truth.

## Tool classes

### Business tool

Tools safe to recommend to a normal business user when the task matches: BentoPDF, VERT, Squoosh, PairDrop, RAWGraphs, csv.repair, SQL for Files, CyberChef, SVGOMG, Mr. Data Converter, JSON Crack, Metadata Remover and ShareClean.

### Operator/developer tool

Internal team utilities such as Hoppscotch, Log Voyager and CyberChef when used for technical inspection. They are not automatically exposed by business matching. CyberChef is deliberately tagged as a business tool only for bounded, non-secret transformations; operator use remains a separate policy decision.

### SCOREBOS infrastructure candidate

UptimeRobot, Checkly, Sentry and Socket remain research/POC candidates. They are not normal business recommendations and are not wired into SCOREBOS.

## Canonical record

`BusinessTool` contains the stable identity, URL, class, categories, capability/task aliases, guidance, privacy fields, processing/signup/free-status fields, verification status/date, source and enabled flag. The registry stores only curated entries from the completed Business Toolbox research.

Eligible normal-user results are limited to `business` records with `enabled=True` and status `verified` or `approved_with_restrictions`. `verify_first`, `deferred` and `rejected` records are never returned as approved recommendations.

## Matching and bot surface

`find_recommended_tools(task)` uses normalized task aliases and deterministic scoring, returning at most three ranked records. `maybe_recommend(task)` requires a tool-seeking phrase so ordinary conversation is not interrupted. The bot returns the tool name, purpose, fit, privacy guidance and direct URL. It never uploads data, executes the external tool, creates an approval, or adds an action path.

The exact first entry point is `app.run_agent()` immediately after identity resolution. The response is read-only and marked `source_module=business_tool_registry` in turn metadata.

## Seed and status

Seeded records: 13 business tools plus two operator tools and four deferred infrastructure candidates. Ten business tools are verified and three are `approved_with_restrictions` (JSON Crack, Metadata Remover and ShareClean); their restrictions are shown. Deferred infrastructure candidates are stored for classification only and are never returned by normal business matching.

## TMA decision

Deferred. TMA should consume the same `business_tool_registry` only after bot retrieval and evidence are stable. The first TMA slice is discovery/navigation, not a marketplace and not tool execution.

## Architecture boundaries

- No business source of truth is added.
- No file proxy, upload path, external execution, identity model, approval path or vendor integration is added.
- External tools remain direct-use links; SCOREBOS recommends and explains only.
- Research Markdown remains documentation, never runtime storage.

## Remaining gaps and next smallest step

The current catalog is code-seeded and manually verified; it has no refresh workflow or owner editing surface. The next smallest step is a focused review of URLs/privacy claims before expanding the seed, followed by a shared read-only TMA list if the bot response is accepted.
