# BOSS Design System v1

**Date:** 14/08/2026
**Status:** `V1 CALIBRATION — VUX-2.5B OWNER VISUAL REVIEW REQUIRED`
**Authority:** Implements the owner-approved SCOREBOS UX Constitution and BOSS Unified Screen Contract. It does not change product navigation, schema, runtime, permissions, or action authority.

## 1. System rule

Core contracts are uniform across SCOREBOS. A workspace may vary only through approved composition and density modes. New screens must reuse these foundations and components before proposing a new pattern.

The first proving surface is Ventures. VUX-2.5 calibrates the visual direction to feel alive, floating, soft, layered, tactile, and modern while retaining professional SaaS density. Base canvases remain flat; sections, interactive bubbles, selected states, and temporary layers use four controlled elevation levels. Light and dark themes share the same semantic token contract, vivid blue accent family, hierarchy, and interaction states. Source-library names, brand identity, marketing copy, and one-off implementation artifacts are not part of the system.

The owner-directed VUX-2.5 calibration supersedes the earlier dark-only/flat-only application constraint. The prior references still inform hierarchy, whitespace, and restraint, but neither theme copies a source product. None of the references is a Ventures workspace or mobile flow, so both themes require same-viewport review on the implemented Ventures screen.

VUX-2.5b normalizes Ventures interface copy to Hebrew. Canonical API values and raw business data remain unchanged; presentation helpers translate supported lifecycle and confidence values without changing their stored semantics.

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

Use five BOSS roles only:

- `radius-section`: 24px for low-elevation sections and state surfaces.
- `radius-surface`: 26px for interactive entity cards and large bubbles.
- `radius-control`: 16px for inputs and compact controls.
- `radius-chip`: 14px for compact lifecycle/status controls that are not full pills.
- `radius-overlay`: 28px for sheets, drawers, menus, and modals.
- `radius-pill`: 9999px for primary/secondary buttons and compact filter chips only.

Pill geometry communicates an action or compact selection; it is never applied to cards, sheets, data rows, or every surface. Sections, interactive cards, controls, and overlays remain visibly distinct rather than becoming equally rounded.

### 2.4 Surface hierarchy

| Role | Light | Dark |
|---|---|---|
| Canvas | `#F2F6FF` | `#0B1020` |
| Section surface | `#FFFFFF` / `#F7F9FF` | `#151C2F` / `#11182A` |
| Interactive surface | `#FBFCFF` | `#192238` |
| Inset surface | `#EDF2FF` | `#10182B` |
| Raised surface | `#FFFFFF` | `#1C2740` |
| Primary text | `#17213A` | `#F7F9FF` |
| Secondary text | `#3F4C68` | `#D8DEEC` |
| Muted text | `#68758E` | `#9BA8C1` |
| Primary action/accent | `#315EF8` | `#6D8CFF` |
| Readable accent text | `#274FD2` | `#9BB0FF` |

Theme selection follows `prefers-color-scheme` for the Ventures proof. Theme values are scoped semantic tokens; components consume roles such as canvas, section, interactive, inset, raised, text, border, status, and accent rather than hardcoded theme colors. Color remains secondary to labels for status meaning.

### 2.5 Borders and elevation

- Elevation 0 — Base background: flat canvas, no shadow.
- Elevation 1 — Section surface: soft outer shadow plus a subtle inner highlight; used for summary, grouping, and screen states.
- Elevation 2 — Interactive card/bubble: stronger but diffuse shadow; used for Venture cards, lifecycle bubbles, and actionable controls.
- Elevation 3 — Selected/modal/important action: accent halo or high diffuse shadow; reserved for selected lifecycle state, modal, raised editor, toast, and primary action.
- Borders use theme-semantic low/strong contrast tokens; dark and light values differ while component rules remain identical.
- Pressed state uses the semantic inset/pressed shadow and moves down by at most 1px.
- Do not combine strong glow, heavy border, saturated gradient, and high shadow on the same element. Gradients remain near-flat surface shifts only.

### 2.5.1 Bubble semantics

`Depth != Clickability`. Shape and elevation establish hierarchy; they never imply interaction by themselves. Ventures uses three canonical classes:

| Class | Role | Required interaction contract |
|---|---|---|
| `boss-bubble--action` | Primary/secondary actions and explicit entity-open affordances | Stronger accent/elevation plus visible hover, press, and focus. Mobile never depends on hover. |
| `boss-bubble--selectable` | Lifecycle stages, filters, and finite choices | Softer default depth than an action; selected state uses a restrained semantic halo/outline; hover, press, and focus remain visible. |
| `boss-bubble--information` | KPIs, summaries, and read-only context | Soft section depth only. No hover lift, action glow, pressed motion, pointer cursor, or other click signal. |

Every clickable bubble must expose at least one additional interaction signal beyond radius and shadow: an action label, selected state, focus ring, hover/press response, or a combination appropriate to the input method.

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
- Motion: `220ms cubic-bezier(.25, .46, .45, .94)` for elevation/surface changes and `180ms` for compact feedback. Under `prefers-reduced-motion`, remove non-essential movement and retain immediate state changes.
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

Four owner-supplied UIDrop inputs have been classified against the BOSS-owned foundations above. Their evidence boundaries are recorded in `docs/ux/reference-evidence/uidrop/owner-supplied-visual-token-extraction.md`, `docs/ux/reference-evidence/uidrop/owner-supplied-balanced-rounded-extraction.md`, `docs/ux/reference-evidence/uidrop/owner-supplied-light-layered-extraction.md`, and `docs/ux/reference-evidence/uidrop/owner-supplied-vibrant-collage-extraction.md`. The extractions are evidence for design language, not permission to copy source branding or library internals.

| Input area | Disposition | BOSS decision | Remaining verification |
|---|---|---|---|
| Radius | `ADAPT` | 24px sections, 26px interactive surfaces, 16px controls, 14px compact chips, 28px overlays, pill actions | Validate soft geometry does not overwhelm dense mobile rows |
| Spacing | `ADOPT` core; `ADAPT` extended | 4px grid with 4–24px core and 32–48px app layout steps; 96/128 display-only | Validate Hebrew density at 390px |
| Typography | `ADAPT` | Inter var; 16/24 body and application-specific role scale | Validate Hebrew text at 390px; keep 64/40 display sizes out of Ventures |
| Palette | `ADAPT` | semantic light/dark themes with bright/deep canvases and one vivid blue accent family | Validate full semantic status palette and contrast in both themes |
| Elevation | `ADAPT` | four levels: flat base, low section, medium interactive bubble, high selected/modal/action | Compare lifecycle/card separation visually |
| Inputs/focus | `ADAPT` | 16px controls; visible 2px readable-accent ring and theme-aware offset | Capture default/hover/focus/invalid/disabled states |
| Motion | `ADAPT` | 220ms/180ms ease-out; -1px hover and +1px press; disappearing hover rejected | Verify no essential meaning depends on motion |
| Breakpoints/layers | `REJECT` raw values; normalize | 560/640/768/1024/1280 and 0/10/100/200/300 layers | Confirm against real TMA content, not source selectors |
| Source CSS/library names | `REJECT` | BOSS semantic names only | None |
| Light layered reference | `REFERENCE ONLY`; `ADAPT` theme roles | Admit a light application theme through BOSS semantic tokens; no source palette or identity copying | Verify focus, status contrast, and hierarchy in both themes |
| Vibrant collage reference | `REFERENCE ONLY` | Future onboarding/empty-state composition with original BOSS assets; no Ventures token change | Validate only if a real explanatory/empty-state need emerges |

### Supported now vs waiting for visual QA

Supported now: hierarchy, component responsibilities, action lifecycle, status semantics, mobile/RTL rules, density modes, collection/detail continuity, validation, receipts, accessibility contracts, and the normalized visual token direction.

Screenshot-supported now: compact chrome, preserved workspace hierarchy, selective pill actions, high-contrast typography, generous whitespace around the primary decision/work state, and four semantic elevation levels across light and dark Ventures captures.

Waiting for owner visual QA: whether the 24–28px geometry and diffuse shadows are sufficiently lively without becoming toy-like; semantic status contrast, pill frequency, overlay focus/dismissal, and complete input/search interaction states remain implementation QA. The supplied screenshots are evidence for design language, not same-screen references, so no claim of source fidelity is made.

UIDrop findings must be recorded as BOSS-owned tokens and reviewed against Hebrew text, 390px mobile, contrast, and Telegram safe-area behavior. They cannot be copied wholesale from a reference.

## 7. Admission gate

A new component or variant is accepted only when:

1. An existing primitive cannot serve the same user need.
2. The need is system-level, not a one-screen styling preference.
3. States, responsive behavior, accessibility, and action/data authority are documented.
4. The primitive is reusable by every relevant screen.
5. Review confirms it does not resolve an open product/navigation decision implicitly.
