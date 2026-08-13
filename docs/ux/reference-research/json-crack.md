# JSON Crack — Reference Inspection

**Source discovery:** NoSignups / Free for Developers
**Inspected:** 13/08/2026
**URL:** https://jsoncrack.com/editor
**Access:** public, no account used

## Evidence boundary

`OBSERVED` applies to the publicly rendered editor shell and its visible public states. This is not evidence of authenticated collaboration, permissions, persistence, or production data behavior.

## States inspected

- `OBSERVED`: editor shell with `File`, `View`, and `Tools` entry points.
- `OBSERVED`: validation/readiness state showing `Valid` and `Live Transform`.
- `OBSERVED`: format context showing `JSON` as the active input mode.
- `OBSERVED`: public product page exposes upload/type-in, visualization, export, and format conversion as distinct task states.
- `NOT VERIFIED`: real file upload, graph manipulation, search/filter, save/share, permissions, errors, and mobile adaptation.

## SCOREBOS mapping

| Pattern | Recommendation | SCOREBOS mapping |
|---|---|---|
| Visible validation/readiness | `MAP TO EXISTING SCOREBOS PATTERN` | DEC-UX-12 |
| Separate input → transform → output framing | `USE AS COMPOSITION INSPIRATION` | DEC-UX-09, DEC-UX-11 |
| Tool grouping under a compact shell | `MAP TO EXISTING SCOREBOS PATTERN` | DEC-UX-02, DEC-UX-07 |

