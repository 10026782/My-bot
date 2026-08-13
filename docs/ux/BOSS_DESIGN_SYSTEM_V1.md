# BOSS Design System v1

**Date:** 13/08/2026
**Status:** `V1 PROPOSAL — THREE UIDROP REFERENCES SYNTHESIZED; IMPLEMENTATION QA PENDING`
**Authority:** Implements the owner-approved SCOREBOS UX Constitution and BOSS Unified Screen Contract. It does not change product navigation, schema, runtime, permissions, or action authority.

## 1. System rule

Core contracts are uniform across SCOREBOS. A workspace may vary only through approved composition and density modes. New screens must reuse these foundations and components before proposing a new pattern.

The first proving surface is Ventures. The visual direction is balanced, modern, dark, and flat: a near-black application canvas, quiet dark work surfaces, high-contrast typography, compact information density, selective pill actions, restrained card rounding, a violet-blue accent, and layered elevation only for temporary overlays. The values below synthesize three owner-supplied UIDrop references into BOSS-owned semantic tokens; source-library names, brand identity, marketing copy, and one-off implementation artifacts are not part of the system.

The first 720×450 workbench screenshot supports compact split-pane hierarchy but is washed out. The second 1024×505 landing-page screenshot clearly supports the dark canvas, quiet chrome, high-contrast text, light pill CTA, flat borders, and generous decision-level whitespace. The third 720×450 light marketing screenshot supports whitespace-led grouping, rounded temporary layers, 6px inputs, and restrained overlay shadow, but not a light app theme. None is a Ventures workspace or mobile flow. The normalized token set is sufficient for the first implementation PR, while application density and same-viewport behavior must be proven on the implemented Ventures screen.

## 2. Foundations

### 2.1 Spacing

Use a 4px base grid. The core component rhythm is 4/8/12/16/20/24; larger layout steps are permitted only for page composition.

| Token | Value | Use |
|---|---:|---|
| `space-0` | 0px | Reset only |
| `space-hairline` | 2px | Optical/border adjustment; never general layout |
| `space-1` | 4px | icon/label micro-gap |
| `space-2` | 8px | compact control gap |
| `space-3` | 12px | row/card internal gap |
| `space-4` | 16px | default card and mobile page padding |
| `space-5` | 20px | comfortable card/page recipe |
| `space-6` | 24px | section separation |
| `space-8` | 32px | major page separation |
| `space-12` | 48px | page-level separation only |
| `space-24` | 96px | marketing/display composition only; not workspace rhythm |
| `space-32` | 128px | marketing/display composition only; not workspace rhythm |

Do not introduce local 6px/10px/14px/18px spacing unless a shared component documents the exception. Density modes change component recipes, not the base scale. The source-style names (`toolbox-spacing-*`) are evidence only and must not become public BOSS token names.

### 2.2 Typography

| Role | Size/line-height | Weight | Rule |
|---|---|---:|---|
| Page Title | 28/34 | 510–600 | One per application screen; 64px source display is not used in workspaces |
| Section Title | 20/28 | 510–600 | Names a decision/work group |
| Entity/Card Title | 16/24 | 510–600 | May wrap to two lines |
| Body | 16/24 | 400 | Default reading text; `1.5` line-height |
| Label/Action | 14/20 | 510–600 | Controls and important labels |
| Metadata/Eyebrow | 13/20 | 400–510 | Never carries the only critical meaning |
| KPI | 32/38 | 510–600 | Must include a semantic label and drill-down purpose |
| Status | 13/20 | 510–600 | Text label required; color is secondary |

Use `Inter var`, with the current system sans-serif stack as fallback. Use semantic roles, not local font sizes. Hebrew line-height must allow niqqud-free text, mixed numbers, and two-line labels without clipping. The supplied 64/40px display scale is admitted only for future marketing/editorial surfaces; Ventures uses the application roles above.

### 2.3 Radius

Use four BOSS roles only:

- `radius-surface`: 4px for cards, list rows, alerts, and sections.
- `radius-control`: 6px for inputs and compact controls.
- `radius-overlay`: 16px for sheets, drawers, menus, and modals.
- `radius-pill`: 9999px for primary/secondary buttons and compact filter chips only.

Pill geometry communicates an action or compact selection; it is never applied to cards, sheets, data rows, or every surface. This preserves the reference's rounded/flat balance without turning the workspace into a field of capsules.

### 2.4 Surface hierarchy

| Level | Purpose | BOSS token/value |
|---|---|---|
| Canvas | App background and scroll field | `canvas: #08090A` |
| Surface | Cards, sections, data work | `surface: #1C1D1E` |
| Subtle | Grouping inside a surface | `surface-subtle: #141516` |
| Raised | Sticky action area, drawer, overlay | `surface-raised: #242526` + border |
| Contrast | High-emphasis CTA/content | `surface-contrast: #E5E5E6` |

Text tokens are `text-primary: #F7F8F8`, `text-muted: #8A8F98`, and `text-on-contrast: #08090A`. The supplied muted text measures approximately 6.13:1 against the canvas and remains secondary rather than carrying critical meaning.

Action tokens are `action-primary: #E5E5E6`, `action-primary-text: #08090A`, `accent: #5E6AD2`, `accent-readable: #7E88DB`, and `accent-soft: #C2D2F2`. Neutral primary actions use the high-contrast light pill. `#5E6AD2` is reserved for non-text selection/fill or large text; it measures only about 4.42:1 against `#F7F8F8`. Text/icons on the dark canvas use `#7E88DB` when accent color is required. Color remains secondary to labels for status meaning.

### 2.5 Borders and elevation

- Border: `1px solid rgba(255, 255, 255, .12)` on dark surfaces. The extracted `0.666667px` value is normalized to a stable device-independent pixel.
- Elevation 0: default cards, rows, sections, and controls; no shadow.
- Elevation 1: interactive/sticky separation via border or background shift; no default shadow.
- Elevation 2: sheet/drawer/menu/action bar; `0 8px 32px rgba(0, 0, 0, .12)`.
- Elevation 3: temporary modal/critical overlay only; use the supplied large shadow recipe, never on ordinary cards.
- `shadow-inner` is reserved for pressed/inset controls. Extra-large shadow is not admitted into v1.
- Do not combine heavy shadow, strong border, and colored background unless the state is critical.

### 2.6 Icons and touch targets

- Icon sizes: 16px compact, 20px default, 24px prominent.
- Minimum mobile target box: 44×44px, including icon-only controls.
- Icon-only controls require an accessible name and should be rare in headers.
- Emoji may decorate but never define status, action, or navigation alone.
- Use one approved icon library during implementation; do not handcraft icons per screen.

### 2.7 Semantic status system

| Semantic state | Meaning | Required output |
|---|---|---|
| Neutral | Informational/unclassified | Label + neutral treatment |
| Info | Guidance/new context | Label + optional icon |
| Success | Verified completed business state | What changed + where it is available |
| Warning | Attention required, action still possible | Reason + next step |
| Danger | Failure, destructive risk, or blocked state | Reason + recovery/confirmation |
| Pending | Queued/running/waiting | Current state + what the user can do now |
| Stale/Unknown | Data may be outdated or result not verified | Timestamp/context + refresh/inspect action |

Business status, execution state, and presentation state remain separate. Domain statuses map into this semantic layer; they do not redefine it.

### 2.8 RTL behavior

- `dir="rtl"` belongs at shell level.
- Text aligns to the reading start; numeric/currency clusters preserve readable number direction.
- Back/forward icons and drawer entry direction follow Hebrew navigation meaning.
- Logical CSS properties (`padding-inline`, `margin-inline`, `inset-inline`) are preferred over left/right assumptions.
- Mixed Hebrew/English labels must wrap without reversing icon/action order.
- Timeline direction, stage progression, and chevrons must be tested rather than inferred.

### 2.9 Mobile-first rules

- Design the complete task at 390px first; tablet/desktop add room, not capabilities.
- Default page padding is `space-4`; sticky actions respect Telegram safe-area and the dynamic keyboard viewport.
- Dense boards become a stage rail + list or stacked columns; horizontal scroll requires a visible affordance.
- Detail opens as a bottom/full-height sheet for quick review and as a dedicated depth surface only for extended work.
- Primary action remains visible without covering content; secondary/rare actions move to an overflow/action sheet.
- Long Hebrew titles, empty/error states, focus order, and screen-reader labels are acceptance criteria.

### 2.10 Focus, motion, layers, and responsive normalization

- Focus ring: `2px solid #7E88DB` with a 2px `#08090A` offset. The source's shadow-only focus recipe is insufficient and is not adopted.
- Motion: `160ms cubic-bezier(.25, .46, .45, .94)` for open/close and `100ms` for press/hover feedback. The completed curve is a BOSS inference because the supplied source value was truncated. Under `prefers-reduced-motion`, remove non-essential movement and retain immediate state changes.
- Hover uses a subtle color/border shift and at most `translateY(-1px)`. The extracted `translateY(16px); opacity: 0` is treated as an exit/entrance artifact and rejected as hover behavior.
- Layer tokens: `content: 0`, `sticky: 10`, `dropdown: 100`, `modal: 200`, `tooltip: 300`. Source values such as `100001` and `2147483647` are rejected as implementation leakage.
- Canonical breakpoints: `compact: 560px`, `wide-mobile: 640px`, `tablet: 768px`, `desktop: 1024px`, and `wide: 1280px`. Intermediate source queries at 600/1120/1536px require a component-specific reason before admission.
- The application shell is `min(100%, 1264px)`; focused reading/form content remains capped at 800px. Mobile uses at least 16px inline page padding. A 4px gutter is an internal-grid token, never viewport padding.
- Radix UI is a candidate implementation substrate for accessible overlays, menus, tabs, and focus management. It is not a visual identity and is not required for VUX-0 unless dependency review approves adding it.

## 3. Approved variation

- Density: `Comfortable`, `Standard`, `Dense`.
- Collection: `List`, `Table`, `Board` where the business task justifies it.
- Detail depth: `Inline`, `Drawer/Sheet`, `Full Detail`.
- Layout: `Single Column`, `Split`, `Grid`, `Full-width`.

Variation changes composition, never capability, permission, status meaning, action lifecycle, or data source.

## 4. Component contracts

| Component | Purpose | Allowed variants | Mobile behavior | Interaction states | Must not vary per screen |
|---|---|---|---|---|---|
| `AppShell` | Own RTL, safe-area, canvas, scroll, content frame, and shared action/navigation zones | loading, content, error; single/split content | One scroll owner; safe-area padding; no capability loss | loading, ready, offline/error | RTL, safe-area, scroll ownership, global zones, back/close semantics |
| `PageHeader` | State the business context and one primary action | title-only, workspace, detail | Wrap context; one visible primary action; secondary actions collapse | default, sticky, loading context | title role, back behavior, action priority, target sizes |
| `Section` | Group one decision or related work block | titled, titled+action, collapsible | Stacked full-width; collapse only when content remains discoverable | default, expanded, collapsed, loading | spacing, heading semantics, action placement |
| `Card` | Represent one decision, entity, or action | static, clickable, selected, danger | Full-width; no hover-only meaning | default, pressed, focused, selected, disabled | surface/radius, focus, padding recipe, one-purpose rule |
| `KPI Card` | Show a metric that leads to a decision/drill-down | compact, dashboard | Horizontal strip or 2-column grid; label always visible | loading, ready, stale, focused | label/value roles, drill-down meaning, stale treatment |
| `List Item` | Present comparable entity/action data | entity, action, compact | Minimum 44px row; metadata wraps or truncates intentionally | default, pressed, selected, disabled | identity/metadata/action hierarchy, focus, target size |
| `Board Card` | Present an item inside a canonical lifecycle stage | venture, demand, project | Stage-filtered list or horizontal board with affordance | default, selected, blocked, dragging only if approved | entity identity, status label, next action, transition safety |
| `Status Badge` | Expose business/system state without color-only meaning | lifecycle, risk, system, execution | Wrap-safe; text remains visible | neutral, info, success, warning, danger, pending, stale | semantic mapping, label requirement, contrast, icon optionality |
| `Tabs` | Switch sibling views inside one context | primary, secondary, scrollable | Scrollable with edge affordance; does not become hidden nav | default, selected, focused, disabled | selection semantics, URL/context preservation where supported |
| `Search` | Retrieve records/actions using a defined query contract | workspace, global | Full-width; clear button and keyboard-safe placement | empty, typing, loading, results, no results, error | query ownership, labels, clear/reset behavior, no fake search |
| `Filters` | Narrow a collection using schema-backed fields | chips, select, filter sheet, saved view later | Chips for few values; sheet for advanced filters | default, applied, loading, unavailable, error | applied-count visibility, reset, query semantics, preserved context |
| `Action Bar` | Hold current primary/secondary contextual actions | inline, sticky, contextual | Safe-area aware; never covers fields/keyboard | ready, disabled-with-reason, pending, success handoff, error | one primary action, order, target sizes, action lifecycle entry |
| `Quick Action` | Start a frequent canonical capability | global, entity, guided next step | Touch-first labels; keyboard shortcut is additive | available, unavailable, validating, pending | business verb, capability mapping, no direct tool exposure |
| `Detail Drawer/Sheet` | Inspect/edit an entity without losing collection context | quick-review sheet, desktop drawer, inline expansion | Bottom/full-height sheet; explicit close/back; scroll lock | loading, ready, unsaved, saving, error | origin preservation, focus management, close behavior, safe-area |
| `Timeline` | Show ordered, sourced entity history | interaction, business event, receipt | Single column; metadata wraps | loading, ready, empty, filtered, error | source, timestamp, related entity, event/result distinction |
| `Empty State` | Explain why no content appears and what to do next | first-use, no-result, unavailable | Centered but compact; action remains reachable | default | reason, scope, next action; no decorative-only message |
| `Loading State` | Communicate pending data/action without inventing progress | initial, refresh, inline/action | Skeleton/spinner must not shift primary layout excessively | loading, long-running | honest copy, scope, accessible announcement |
| `Error State` | Explain a human-safe failure and recovery | network, permission, stale, action | Inline near scope; full-page only when screen cannot function | error, retrying, recovered | human category, no IDs/tool errors, next step/retry |
| `Confirmation` | Preview intent and impact before sensitive change | direct-confirm, destructive, approval-required | Sheet/modal with safe default and explicit cancel | validating, ready, blocked, pending | action/entity/change/expected result, authorization boundary |
| `Execution State` | Show queued/running/blocked mutation state | inline, background, approval-pending | Remains inspectable; user can leave when safe | queued, running, blocked, unknown | no invented reasoning, canonical state, continue/inspect path |
| `Receipt` | Show verified result and discoverable updated state | success, partial, failed | Inline summary with link/back to updated record | verified, partial, failed, stale | what changed, where, evidence/state source, next step |

## 5. Action and feedback contract

All persistent actions use:

`Intent → Capability → Validation → Preview/Approval if required → Execution → Verified Result → Updated Business State → Receipt/Error`

Rules:

- A disabled action explains what is missing.
- A toast may acknowledge a short interaction; it cannot replace a result/receipt.
- Success appears only after the API returns a canonical result and, where necessary, the UI refetches the updated business record.
- High-risk or irreversible transitions require an approved business contract before UI controls exist.
- Internal IDs, Airtable table names, tool names, payloads, and raw errors are never user-facing.

## 6. UIDrop input disposition

Three owner-supplied UIDrop inputs have been normalized into the BOSS-owned foundations above. Their evidence boundaries are recorded in `docs/ux/reference-evidence/uidrop/owner-supplied-visual-token-extraction.md`, `docs/ux/reference-evidence/uidrop/owner-supplied-balanced-rounded-extraction.md`, and `docs/ux/reference-evidence/uidrop/owner-supplied-light-layered-extraction.md`. The extractions are evidence for design language, not permission to copy source branding or library internals.

| Input area | Disposition | BOSS decision | Remaining verification |
|---|---|---|---|
| Radius | `ADAPT` | 4px surfaces, 6px inputs, 12px overlays, pill actions/chips | Validate pills do not overwhelm dense mobile rows |
| Spacing | `ADOPT` core; `ADAPT` extended | 4px grid with 4–24px core and 32–48px app layout steps; 96/128 display-only | Validate Hebrew density at 390px |
| Typography | `ADAPT` | Inter var; 16/24 body and application-specific role scale | Validate Hebrew text at 390px; keep 64/40 display sizes out of Ventures |
| Palette | `ADAPT` | `#08090A` canvas, `#1C1D1E` surfaces, light CTA, violet-blue accent | Validate full semantic status palette and contrast |
| Elevation | `ADAPT` | flat by default; small/medium only for interaction and overlays | Compare sticky/detail separation visually |
| Inputs/focus | `ADAPT` | 6px inputs; visible 2px `#7E88DB` ring and offset | Capture default/hover/focus/invalid/disabled states |
| Motion | `ADAPT` | 160ms/100ms inferred ease-out curve; disappearing hover rejected | Verify no essential meaning depends on motion |
| Breakpoints/layers | `REJECT` raw values; normalize | 560/640/768/1024/1280 and 0/10/100/200/300 layers | Confirm against real TMA content, not source selectors |
| Source CSS/library names | `REJECT` | BOSS semantic names only | None |
| Light layered reference | `REFERENCE ONLY` foundation; `ADAPT` overlays | Keep dark app foundation; use 16px temporary overlays, 6px inputs, and restrained Elevation 2 | Verify focus trap, dismissal, keyboard order, and dark-surface contrast |

### Supported now vs waiting for visual QA

Supported now: hierarchy, component responsibilities, action lifecycle, status semantics, mobile/RTL rules, density modes, collection/detail continuity, validation, receipts, accessibility contracts, and the normalized visual token direction.

Screenshot-supported now: compact chrome, border-led hierarchy, flat default surfaces, a narrow-control/wide-work desktop composition, near-black canvas, high-contrast typography, selective pill actions, generous whitespace around the primary decision/work state, and clearly layered temporary overlays.

Waiting for implementation QA: Ventures-specific hierarchy and density, Hebrew rendering, semantic status colors, pill frequency, overlay focus/dismissal, and complete input/search interaction states. The supplied screenshots are evidence for design language, not same-screen references, so no claim of visual match is made.

UIDrop findings must be recorded as BOSS-owned tokens and reviewed against Hebrew text, 390px mobile, contrast, and Telegram safe-area behavior. They cannot be copied wholesale from a reference.

## 7. Admission gate

A new component or variant is accepted only when:

1. An existing primitive cannot serve the same user need.
2. The need is system-level, not a one-screen styling preference.
3. States, responsive behavior, accessibility, and action/data authority are documented.
4. The primitive is reusable by every relevant screen.
5. Review confirms it does not resolve an open product/navigation decision implicitly.
