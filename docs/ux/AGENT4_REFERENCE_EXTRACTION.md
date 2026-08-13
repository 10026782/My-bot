# Agent 4 — SCOREBOS UX Reference Extraction

**Date:** 13/08/2026  
**Status:** Constrained public evidence pass  
**Source catalogs:** [NoSignups](https://nosignups.net/) and [Free for Developers](https://free-for.dev/)

## Scope and selection

The selection prioritizes public rendered evidence for shell, collection/tool discovery, entity/context framing, search, actions, readiness, lifecycle and responsive questions. It does not attempt to inspect every catalog entry and does not adopt a product's branding or business vocabulary.

Selected set: **8 references** — Linear, Attio, Raycast, Retool, monday CRM, Pipedrive, JSON Crack and BentoPDF.

The first six already had public evidence in this branch. JSON Crack and BentoPDF were added because their public pages expose concrete tool-shell states without requiring an account. Hoppscotch, RAWGraphs, CSV Repair and Excalidraw were not promoted because the accessible fetch did not expose enough stable rendered states to meet the evidence rule.

## Evidence discipline

- `OBSERVED` means a public rendered state or saved screenshot/DOM observation was available.
- `INFERRED` is interpretation only and is not a binding UX decision.
- `NOT VERIFIED` means login-only, blocked, unstable, or not inspected at the required state/viewport.
- Public marketing copy is not treated as proof of authenticated behavior.

## Cross-reference matrix

| Pattern | Products Observed | Evidence Strength | SCOREBOS DEC | Recommendation |
|---|---|---|---|---|
| Compact shell with global entry points | Linear, Raycast, JSON Crack | `OBSERVED` in 3 public states | DEC-UX-02, DEC-UX-06, DEC-UX-07 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Context-preserving entity/detail framing | Linear, Attio | `OBSERVED` in public demos | DEC-UX-09, DEC-UX-11, DEC-UX-14 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Searchable collection/tool discovery | Attio, Retool, BentoPDF | `OBSERVED` in public states | DEC-UX-07, DEC-UX-10 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Visible readiness/validation | Retool, JSON Crack | `OBSERVED` in public entry/editor states | DEC-UX-12 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Lifecycle grouping | Attio, monday CRM, Pipedrive | `OBSERVED` public examples; authenticated runtime not verified | DEC-UX-09, DEC-UX-11 | `USE AS COMPOSITION INSPIRATION` |
| Verb-oriented action discovery | Raycast, Retool | `OBSERVED` public entry examples | DEC-UX-06, DEC-UX-07, DEC-UX-14 | `USE AS COMPOSITION INSPIRATION` |
| Density/display preference | BentoPDF | `OBSERVED` single reference | DEC-UX-16 | `SINGLE-REFERENCE CANDIDATE`; validate with SCOREBOS operators |
| Keyboard-first command model | Raycast | `OBSERVED` public presentation only | DEC-UX-02, DEC-UX-16 | `SYSTEM-LEVEL PATTERN CANDIDATE`; device/context validation required |

## Rejected or deferred patterns

- Product-specific branding, logos, illustrations and vocabulary — `REJECT FOR SCOREBOS`.
- Prompt-to-application composition as a primary SCOREBOS workflow — `REJECT FOR SCOREBOS`; it is not the product's core operator model.
- Any authenticated CRUD, permissions, role, save/share, failure, or mobile workflow — `NOT VERIFIED` and excluded from binding conclusions.

## System-level lessons (non-binding)

Only the following lessons repeat across more than one selected reference and are supported as public evidence:

1. Keep a compact global entry point for frequent search/create/action work.
2. Keep entity context and next-step context together where the public state demonstrates a lifecycle object.
3. Make readiness or validation visible before an action is submitted.
4. Group tools or records by an understandable lifecycle/task model before exposing advanced controls.

These are composition inputs, not a new Constitution and not final screen/navigation decisions.

## Evidence gaps

Still required before Full Reference Synthesis Gate: authenticated collection/detail behavior, real role/permission UX, advanced filters and sorting, action confirmation/error flows, persistent AI side-panel behavior, and authenticated mobile workflows. Retool's private app remains `NOT VERIFIED` despite the user's description of its sample order page.

