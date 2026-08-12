# Retool — Reference Inspection

**Inspected:** 12/08/2026  
**URL:** https://retool.com/  
**Viewport:** browser default desktop; exact viewport not captured  
**Evidence:** no screenshot saved; DOM observation only

## Access and limits

`OBSERVED`: public Retool homepage rendered an app-builder prompt surface and enterprise/internal-tool positioning. The authenticated builder and operational apps were not opened. Dense table behavior, approvals and permissions are `NOT VERIFIED`.

## Observations

- `OBSERVED`: a prompt input is presented as an entry point for building an app, with starter prompts and a disabled submit state before input.
- `OBSERVED`: the page groups integrations and workflows around internal business software.
- `OBSERVED`: search is exposed in the global header with a keyboard shortcut hint.
- `NOT VERIFIED`: actual operations dashboard, data-table behavior, action lifecycle, restricted UX and responsive behavior.

## SCOREBOS mapping

| Pattern | Why it helps | Constitution mapping | Reuse classification |
|---|---|---|---|
| Explicit input readiness state | Prevents unclear submission behavior | DEC-UX-12 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Global search affordance | Supports capability/data discoverability | DEC-UX-07, DEC-UX-10 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Prompt-to-application composition | Useful only as an AI composition reference | DEC-UX-14 | `REJECT FOR SCOREBOS` |

## Not verified

Retool's logged-in operational workflows, approval interaction and data density.
