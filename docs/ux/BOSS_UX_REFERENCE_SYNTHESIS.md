# BOSS UX Reference Synthesis

**Date:** 13/08/2026
**Status:** `CANONICAL UX SYNTHESIS — IMPLEMENTATION INPUT, NOT PRODUCTION STATE`
**Scope:** Consolidates the approved SCOREBOS UX rules, the current TMA audit, and all reference research on `codex/scorebos-reference-inspection`. It does not approve final navigation, new backend capabilities, or a production rewrite.

## 1. Authority and evidence rules

When sources conflict, this document applies the following order:

1. BOSS owner-approved product decisions in `reports/tma-audit/SCOREBOS_UX_CONSTITUTION_OWNER_DECISION_RECORD_HE.md`.
2. The BOSS Unified Screen Contract from `origin/docs/tma-screen-audit`, commit `0ef40af2d22863b90d51bb220c6c0d0a0e24b766`, path `docs/architecture/tma/BOSS_UNIFIED_SCREEN_CONTRACT.md`.
3. The current-state TMA audit in `reports/tma-audit/TMA_UX_AUDIT_HE.md` and its saved screenshots.
4. Repeated `OBSERVED` patterns across more than one external product.
5. `OBSERVED` single-reference inspiration.
6. `INFERRED` interpretation.

An external reference never overrides a BOSS product decision. `NOT VERIFIED` evidence cannot support an implementation decision. Public marketing/demo states do not prove authenticated behavior, permissions, mutations, mobile parity, error handling, or production semantics.

## 2. Consolidated decision

SCOREBOS should implement one shared screen system before consolidating screens. The system is defined by a stable shell, semantic hierarchy, shared collection/detail patterns, canonical action feedback, mobile/RTL behavior, and controlled density/composition variants. Workspaces may differ because their business questions differ; they may not create local navigation, status, action, state, or responsive systems.

For Ventures, the strongest supported composition is:

`Workspace header → lifecycle/collection → context-preserving venture detail → verified next action/result`

This combines BOSS authority with repeated evidence. It is not a copy of any reference and does not decide the final application navigation.

## 3. Pattern synthesis

| Pattern | Evidence products | Strength | BOSS screen/use-case | Recommendation | Reason | Implementation implication |
|---|---|---|---|---|---|---|
| One compact shell with clear global/context entry points | Linear, Raycast, JSON Crack; current TMA audit | `OBSERVED`, repeated | All workspaces | `ADOPT` | Directly supports DEC-UX-02, DEC-UX-06 and the Screen Contract; current TMA headers are duplicated and crowded. | Establish shared shell/header primitives, but do not set the final destination count or global action surface. |
| Context-preserving collection → detail | Linear, Attio | `OBSERVED`, repeated public demos | Ventures, Leads/CRM, other entity work | `ADOPT` | Matches DEC-UX-09–11 and preserves filters, origin, entity, and next action. | Ventures detail must return to the same stage/search/scroll context; use a sheet/drawer for quick review and a deeper surface only when required. |
| Lifecycle position and stage grouping | Attio, monday CRM, Pipedrive | `OBSERVED` public examples; authenticated behavior `NOT VERIFIED` | Ventures and future Marketing workflows | `ADAPT` | BOSS already authorizes Board/List composition. External stages do not define BOSS semantics. | Render only canonical Venture stages from `airtable_schema.py`; do not invent financial, negotiation, readiness, or conversion transitions. |
| Business-field collection hierarchy | Attio; monday/Pipedrive grouping | `OBSERVED`; detail behavior partly `NOT VERIFIED` | Venture collection | `ADAPT` | Supports comparison without turning the screen into a KPI dashboard. | Venture rows/cards should prioritize identity, stage, domain, conviction, potential, decision date, and next action. |
| Visible validation/readiness before action | Retool, JSON Crack | `OBSERVED`, repeated | Create/edit, stage change, future contextual actions | `ADOPT` | Directly reinforces DEC-UX-12 and the canonical action lifecycle. | Disable unavailable actions with a reason; show validation before mutation; show success only after a verified response/refetch. |
| Searchable collection/tool discovery | Attio, Retool, BentoPDF | `OBSERVED`, repeated public states | Ventures collection; future global action/search | `ADAPT` | Discoverability is supported, but current Ventures API has stage filtering only. | Stage filter is implementable now. Text search remains an API/query gap unless explicitly bounded to currently loaded records and labeled local. |
| Verb-first quick action discovery | Raycast, Retool | `OBSERVED`, repeated public entry states | Future Action Center/global action layer; contextual Venture actions | `ADAPT` | Helps users start by intent, but BOSS actions must enter the canonical capability/validation flow. | Use business verbs such as “Create venture” or “Update next action”; do not expose tools or create a Ventures-specific runtime path. |
| Contextual AI beside entity work | Linear, Attio | `OBSERVED` public demos | Future Venture assistance | `ADAPT` | Consistent with DEC-UX-14, but current Ventures has no approved AI surface or evidence contract. | Keep a reserved composition slot only. Do not implement AI actions or generated facts in the reference screen. |
| Explicit density/display modes | BentoPDF | `OBSERVED`, single reference | Dense collections | `REFERENCE ONLY` | DEC-UX-03 already permits Comfortable, Standard and Dense; one public tool shell is insufficient to choose controls or defaults. | Design components to accept an approved density mode; do not add a user-visible density switch in the first Ventures implementation. |
| Keyboard-first command model | Raycast | `OBSERVED`, single public presentation | Desktop operator acceleration | `REFERENCE ONLY` | Device/context fit for Telegram WebView, touch, accessibility, and risky actions is unverified. | Preserve keyboard extensibility in semantics/focus order; do not make keyboard-first behavior a mobile requirement. |
| Prompt-to-application composition | Retool | `OBSERVED` public presentation | None as a primary BOSS workflow | `REJECT` | Conflicts with BOSS's canonical capability/action architecture and contextual-assistant rule. | No prompt-built parallel app/action system. |
| Product-specific branding, stages, vocabulary, or IA | All references | `OBSERVED` but product-specific | None | `REJECT` | References are learning material, not product authority. | Use BOSS-owned tokens, schema values, Hebrew copy, and business contracts. |
| Authenticated CRUD, permissions, receipts, advanced filters, saved views, and native mobile behavior inferred from public demos | All references | `NOT VERIFIED` | All | `REJECT` as evidence; keep `OPEN` | Existing research explicitly lacks these states. | Validate through BOSS code/contracts and later targeted evidence; do not infer implementation behavior. |

## 4. Reference-by-reference verdict

### Linear + Attio — foundation, within BOSS authority

`ADOPT` the shared idea of compact hierarchy, connected collection/detail, entity context, and nearby next action. `ADAPT` composition to Hebrew RTL, Telegram mobile constraints, BOSS data, and BOSS action/feedback contracts. Do not infer authenticated permissions or mobile parity.

### Pipedrive + monday CRM — lifecycle composition only

`ADAPT` public lifecycle/stage visibility and role/job framing. Their public pages do not authorize a BOSS navigation model, CRM semantics, or stage transitions.

### Raycast — action inspiration, not mobile architecture

`ADAPT` verb-oriented discoverability for contextual/global action entry. Keep keyboard-first behavior `OPEN` and out of the mobile Ventures proof.

### Retool — readiness and validation

`ADOPT` explicit unavailable/ready/in-progress distinctions. `REJECT` prompt-to-application as the primary BOSS workflow.

### JSON Crack — visible state under a compact tool shell

`ADOPT` visible validation/readiness and `ADAPT` grouped tools/actions. Do not infer execution, persistence, or error behavior.

### BentoPDF — search and controlled density

`ADAPT` searchable discovery and separation of primary work from settings. Keep the visible density switch `REFERENCE ONLY` until UIDrop/operator validation.

### Blocked or unverified references

Airtable Interfaces, Figma, HubSpot, Intercom, Notion, Stripe Dashboard, Tana, Vercel, Hoppscotch, RAWGraphs, CSV Repair, and Excalidraw contribute no binding pattern in this synthesis. Their status remains `NOT VERIFIED` or insufficiently stable.

## 5. BOSS screen implications

| BOSS surface | Supported composition | What remains open |
|---|---|---|
| Ventures | Lifecycle collection + context-preserving detail + next decision/action | Exact readiness gates, conversion rules, timeline source, search contract, and deep-detail breakpoint |
| Leads/CRM | Collection/pipeline → detail → next action → related timeline | Contacts/Deals placement and final workspace/navigation structure |
| Finance | KPI summary → ledger/data view → record detail/action | Role-dependent placement and exact write/review actions |
| Command Center | Exceptions/decisions → selected KPIs → drill-down | Exact widgets and Digest overlap |
| Actions/My Work | Verb-first work/action entry using canonical capabilities | Full screen vs global `+` vs queue vs hybrid |
| Marketing/Media | Domain lifecycle using shared Board/List/action/state primitives | Business ownership, publication/approval contracts, and backend support |

## 6. Decisions already supported

- One BOSS screen system with 100% uniform core contracts.
- Mobile-first RTL shell and shared semantic hierarchy.
- One clear business question and next action per screen.
- Shared List/Board/Detail/Timeline/Action patterns with controlled variants.
- Preservation of originating collection/filter context when opening detail.
- Semantic status labels that never rely on color or emoji alone.
- Canonical action lifecycle: intent → validation/preview → execute/approve → verified result → receipt/error.
- Reuse of existing TMA domain content and useful component concepts before introducing replacements.
- BOSS-owned visual direction: dark application canvas, light work surfaces, blue action accent, 4px rhythm, restrained rounding, and flat-by-default elevation. This is an adaptation of owner-supplied token evidence, not a copy of source identity or CSS names.

## 7. Explicitly open

- Final primary navigation count.
- Actions as full screen, global `+`, queue, or hybrid.
- Operations boundaries.
- Contacts/Deals placement.
- Business Memory/Activity source and surface.
- Deletion, merge, or retirement of legacy screens.
- Final semantic status palette and screenshot-level hierarchy/density calibration. The owner supplied a token extraction, but the referenced screenshot was not attached.
- Venture financial-review, negotiation, readiness, GO/NO-GO, and conversion business rules beyond the current schema.

## 8. Source research consumed

### BOSS authority and current-state evidence

- `reports/tma-audit/SCOREBOS_UX_CONSTITUTION_OWNER_DECISION_RECORD_HE.md`
- `origin/docs/tma-screen-audit@0ef40af:docs/architecture/tma/BOSS_UNIFIED_SCREEN_CONTRACT.md`
- `reports/tma-audit/TMA_UX_AUDIT_HE.md`
- `reports/tma-audit/BOSS_SCREEN_CONSISTENCY_ARCHITECTURE_GATE_HE.md`
- `reports/tma-audit/01-hub.png` through `12-lead-detail.png`, with direct visual review of `10-ventures.png`

### Consolidated research and matrices

- `docs/ux/reference-evidence/uidrop/owner-supplied-visual-token-extraction.md`
- `docs/ux/PUBLIC_REFERENCE_SYNTHESIS.md`
- `docs/ux/AGENT4_REFERENCE_EXTRACTION.md`
- `docs/ux/REFERENCE_INSPECTION_PHASE_START.md`
- `docs/ux/REFERENCE_PATTERN_MATRIX.md`
- `docs/ux/SCOREBOS_REFERENCE_CANDIDATES.md`
- `docs/ux/reference-research/access-status.md`

### Reference reports and evidence

- Linear and Linear Mobile: `reference-research/linear.md`, `linear-mobile.md`, screenshots, and `reference-evidence/linear/mobile-public-390x844.md`
- Attio: `reference-research/attio.md`, screenshots, and `reference-evidence/attio/attio-public-states.md`
- Raycast: `reference-research/raycast.md`, screenshots, and `reference-evidence/raycast/raycast-public-states.md`
- Retool: `reference-research/retool.md` and `reference-evidence/retool/retool-public-states.md`
- monday CRM: `reference-research/monday-crm.md` and its public-demo evidence report
- Pipedrive: `reference-research/pipedrive.md` and its public-product evidence report
- JSON Crack: `reference-research/json-crack.md` and its public-editor evidence report
- BentoPDF: `reference-research/bentopdf.md` and its public-tool evidence report
- NOT VERIFIED reports: Airtable Interfaces, Figma, HubSpot Sales, Intercom, Notion, Stripe Dashboard, Tana, and Vercel Dashboard

## 9. Stop condition

This synthesis authorizes the documentation and narrowly scoped Ventures implementation planning that follows. It does not authorize a global navigation rewrite, screen deletion, Airtable schema change, new runtime architecture, Action/CORE contract change, or production claim.
