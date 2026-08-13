# BOSS Design System v1

**Date:** 13/08/2026
**Status:** `V1 PROPOSAL — UIDROP TOKEN INPUT INTEGRATED; SCREENSHOT CALIBRATION PENDING`
**Authority:** Implements the owner-approved SCOREBOS UX Constitution and BOSS Unified Screen Contract. It does not change product navigation, schema, runtime, permissions, or action authority.

## 1. System rule

Core contracts are uniform across SCOREBOS. A workspace may vary only through approved composition and density modes. New screens must reuse these foundations and components before proposing a new pattern.

The first proving surface is Ventures. The visual direction is vibrant, modern, compact, and flat: a dark application canvas, bright work surfaces, restrained rounding, and a blue action accent. The values below adapt the owner-supplied UIDrop extraction into BOSS-owned semantic tokens; source-library names, brand identity, and one-off implementation artifacts are not part of the system.

The token extraction was supplied without its referenced screenshot. Exact hierarchy and density therefore remain a visual QA item, while the normalized token set is sufficient for the first implementation PR. UIDrop input may calibrate visual values, but may not reopen the interaction, semantic, accessibility, action, or responsive contracts.

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
| `space-10` | 40px | large layout separation only |
| `space-12` | 48px | page-level separation only |

Do not introduce local 6px/10px/14px/18px spacing unless a shared component documents the exception. Density modes change component recipes, not the base scale. The source-style names (`toolbox-spacing-*`) are evidence only and must not become public BOSS token names.

### 2.2 Typography

| Role | Size/line-height | Weight | Rule |
|---|---|---:|---|
| Page Title | 24/32 | 700–800 | One per screen |
| Section Title | 18/26 | 700 | Names a decision/work group |
| Entity/Card Title | 16/24 | 600–700 | May wrap to two lines |
| Body | 14/22.4 | 350–400 | Default Hebrew reading text; `1.6` line-height |
| Label/Action | 14/20 | 600 | Controls and important labels |
| Metadata | 12/18 | 400–500 | Never carries the only critical meaning |
| KPI | 30/36 | 700–800 | Must include a semantic label and drill-down purpose |
| Status | 12/18 | 600 | Text label required; color is secondary |

Use `Inter var`, with the current system sans-serif stack as fallback. Use semantic roles, not local font sizes. Hebrew line-height must allow niqqud-free text, mixed numbers, and two-line labels without clipping. Because variable weight `350` is not equally legible in every Hebrew rendering environment, implementation must compare `350` and `400` at 390px before fixing the body weight.

### 2.3 Radius

Use four BOSS roles only:

- `radius-chip`: 4px for status and filter chips.
- `radius-control`: 6px for buttons, inputs, and compact controls.
- `radius-surface`: 8px for cards, list rows, alerts, and sections.
- `radius-overlay`: 12px for sheets, drawers, and modals.

Pill geometry is not a default token. It is allowed only when a component contract explicitly requires a capsule shape. This keeps the system subtly rounded instead of drifting back to the current oversized-card vocabulary.

### 2.4 Surface hierarchy

| Level | Purpose | BOSS token/value |
|---|---|---|
| Canvas | App background and scroll field | `canvas: #222222` |
| Surface | Cards, sections, data work | `surface: #FBFCFC` |
| Subtle | Grouping inside a light surface | `surface-subtle: #F6F6F6` |
| Raised | Sticky action area, drawer, overlay | `surface-raised: #FFFFFF` + border |
| Inverse | High-emphasis system/action surface | `surface-inverse: #0D0D0D` |

Text tokens are contextual: `text-on-dark: #FFFFFF`, `text-on-light: #222222`, `text-muted-on-dark: #B3B3B3`, and `text-muted-on-light: #555555`. The extracted `#838383` may be used for non-text decoration or large secondary text only; it does not meet the 4.5:1 body-text target on either `#222222` or `#FBFCFC`.

Action tokens are `action-primary: #5EB1EF`, `action-hover: #7EC1F2`, `action-pressed: #3C92DC`, and `action-soft: #DBEAFE`. Primary button text is `#222222`, not the extracted `#D5EFFF`: the supplied pairing measures approximately 1.96:1, while `#222222` on `#5EB1EF` measures approximately 6.83:1. Color remains secondary to labels for status meaning.

### 2.5 Borders and elevation

- Border: one semantic 1px neutral border (`#DFDFDF` on light surfaces; `#555555` on dark surfaces), with semantic variants only when meaning requires them.
- Elevation 0: default cards, rows, sections, and controls; no shadow.
- Elevation 1: interactive lift or sticky separation; `0 1px 2px rgba(0, 0, 0, .05)`.
- Elevation 2: sheet/drawer/action bar; `0 2px 6px rgba(0, 0, 0, .12), 0 6px 12px rgba(55, 55, 55, .08)`.
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

- Focus ring: `2px solid #BFDBFE` with a 2px dark or light offset chosen for the current surface. Focus must never depend on shadow alone.
- Motion: `150ms ease-out` for open/close and hover transitions; `75ms ease-out` for press feedback. Under `prefers-reduced-motion`, remove non-essential movement and retain immediate state changes.
- Hover may add Elevation 1 and a subtle color shift. Do not apply `opacity: .5` to the whole control because it weakens text/icon contrast; reserve reduced opacity for disabled states.
- Layer tokens: `content: 0`, `sticky: 10`, `dropdown: 100`, `modal: 200`, `tooltip: 300`. Source values such as `100001` and `2147483647` are rejected as implementation leakage.
- Canonical breakpoints: `compact: 576px`, `wide-mobile: 640px`, `tablet: 768px`, and `content-max: 800px`. Near-duplicate source queries at 575/576, 650/651, 767/768, and 780px are normalized rather than copied.
- The primary content frame is `min(100%, 800px)`. Mobile uses at least 16px inline page padding; the extracted 8px gutter is permitted only inside dense nested grids, not at the viewport edge.
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

Owner-supplied UIDrop token input has been normalized into the BOSS-owned foundations above. The raw evidence boundary is recorded in `docs/ux/reference-evidence/uidrop/owner-supplied-visual-token-extraction.md`. The extraction is evidence for design language, not permission to copy source branding or library internals.

| Input area | Disposition | BOSS decision | Remaining verification |
|---|---|---|---|
| Radius | `ADAPT` | chip 4px, control 6px, surface 8px, overlay 12px | Check sheet/card hierarchy against the missing screenshot |
| Spacing | `ADOPT` core; `ADAPT` extended | 4px grid with 4–24px core and 32–48px layout steps | Validate Hebrew density at 390px |
| Typography | `ADAPT` | Inter var; 14px body at 1.6; semantic role scale | Compare Hebrew body weight 350 vs 400 |
| Palette | `ADAPT` | dark canvas, light work surfaces, BOSS blue actions | Validate full semantic status palette and contrast |
| Elevation | `ADAPT` | flat by default; small/medium only for interaction and overlays | Compare sticky/detail separation visually |
| Inputs/focus | `ADOPT` focus concept | 6px controls; 2px `#BFDBFE` ring with offset | Capture default/hover/focus/invalid/disabled states |
| Motion | `ADOPT` | 150ms/75ms ease-out with reduced-motion fallback | Verify no essential meaning depends on motion |
| Breakpoints/layers | `REJECT` raw values; normalize | 576/640/768/800 and 0/10/100/200/300 layers | Confirm against real TMA content, not source selectors |
| Source CSS/library names | `REJECT` | BOSS semantic names only | None |

### Supported now vs waiting for visual QA

Supported now: hierarchy, component responsibilities, action lifecycle, status semantics, mobile/RTL rules, density modes, collection/detail continuity, validation, receipts, accessibility contracts, and the normalized visual token direction.

Waiting for screenshot/implementation QA: hierarchy and density fidelity, Hebrew weight calibration, semantic status colors, and complete input/search state captures. The screenshot referenced by the supplied brief was not attached to this task, so no claim of visual match is made.

UIDrop findings must be recorded as BOSS-owned tokens and reviewed against Hebrew text, 390px mobile, contrast, and Telegram safe-area behavior. They cannot be copied wholesale from a reference.

## 7. Admission gate

A new component or variant is accepted only when:

1. An existing primitive cannot serve the same user need.
2. The need is system-level, not a one-screen styling preference.
3. States, responsive behavior, accessibility, and action/data authority are documented.
4. The primitive is reusable by every relevant screen.
5. Review confirms it does not resolve an open product/navigation decision implicitly.
