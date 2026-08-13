# BentoPDF — Reference Inspection

**Source discovery:** NoSignups
**Inspected:** 13/08/2026
**URL:** https://www.bentopdf.com/
**Access:** public, no account used

## Evidence boundary

`OBSERVED` applies to the public tool-shell and controls rendered on the page. Marketing claims about privacy, speed, or compatibility are not treated as interaction evidence.

## States inspected

- `OBSERVED`: tool-start state with a search input for finding PDF tools.
- `OBSERVED`: settings state with Shortcuts and Preferences entry points.
- `OBSERVED`: display preference state exposing Full Width Mode.
- `OBSERVED`: density preference state exposing Compact Mode, described as list instead of cards.
- `OBSERVED`: advanced settings and Import/Export entry points.
- `NOT VERIFIED`: actual file upload, tool execution, batch progress, errors, permissions, and native/mobile behavior.

## SCOREBOS mapping

| Pattern | Recommendation | SCOREBOS mapping |
|---|---|---|
| Searchable tool collection | `MAP TO EXISTING SCOREBOS PATTERN` | DEC-UX-07, DEC-UX-10 |
| Explicit density/display mode | `USE AS COMPOSITION INSPIRATION` | DEC-UX-16 |
| Settings separated from primary work | `MAP TO EXISTING SCOREBOS PATTERN` | DEC-UX-02, DEC-UX-12 |

