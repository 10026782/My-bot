# BOSS Design System v1

**Date:** 13/08/2026
**Status:** `V1 PROPOSAL — CONCRETE INTERACTION CONTRACT; VISUAL CALIBRATION PENDING UIDROP`
**Authority:** Implements the owner-approved SCOREBOS UX Constitution and BOSS Unified Screen Contract. It does not change product navigation, schema, runtime, permissions, or action authority.

## 1. System rule

Core contracts are uniform across SCOREBOS. A workspace may vary only through approved composition and density modes. New screens must reuse these foundations and components before proposing a new pattern.

The first proving surface is Ventures. Values below are deliberately small and anchored to the current TMA Tailwind vocabulary. UIDrop may calibrate visual values, but may not reopen the interaction, semantic, accessibility, action, or responsive contracts.

## 2. Foundations

### 2.1 Spacing

Use one six-step spacing scale:

| Token | Provisional value | Use |
|---|---:|---|
| `space-1` | 4px | icon/label micro-gap |
| `space-2` | 8px | compact control gap |
| `space-3` | 12px | row/card internal gap |
| `space-4` | 16px | default card and mobile page padding |
| `space-6` | 24px | section separation |
| `space-8` | 32px | major page separation |

Do not introduce local 6px/10px/14px/18px spacing unless a shared component documents the exception. Density modes change component recipes, not the base scale.

### 2.2 Typography

| Role | Provisional size/line-height | Weight | Rule |
|---|---|---:|---|
| Page Title | 24/32 | 700–800 | One per screen |
| Section Title | 18/26 | 700 | Names a decision/work group |
| Entity/Card Title | 16/24 | 600–700 | May wrap to two lines |
| Body | 14/22 | 400 | Default Hebrew reading text |
| Label/Action | 14/20 | 600 | Controls and important labels |
| Metadata | 12/18 | 400–500 | Never carries the only critical meaning |
| KPI | 30/36 | 700–800 | Must include a semantic label and drill-down purpose |
| Status | 12/18 | 600 | Text label required; color is secondary |

Use semantic roles, not local font sizes. Hebrew line-height must allow niqqud-free text, mixed numbers, and two-line labels without clipping. Final font family and exact optical weights are UIDrop/brand inputs.

### 2.3 Radius

Use four roles only:

- `radius-control`: 8px for inputs and compact controls.
- `radius-surface`: 12px for cards, list rows, alerts, and sections.
- `radius-overlay`: 16px for sheets/drawers/modals.
- `radius-pill`: fully rounded for status and filter chips only.

These values match recurring current TMA shapes and remain provisional pending UIDrop comparison.

### 2.4 Surface hierarchy

| Level | Purpose | Current anchor |
|---|---|---|
| Canvas | App background and scroll field | neutral gray (`gray-100`) |
| Surface | Cards, sections, headers | white |
| Subtle | Grouping inside a surface | neutral gray (`gray-50/100`) |
| Raised | Sticky action area, drawer, overlay | white + border/elevation |
| Inverse | High-emphasis system/action surface | near-black (`gray-900`) |

Surface level communicates hierarchy; card type does not invent a new background. Exact colors remain UIDrop/brand inputs.

### 2.5 Borders and elevation

- Border: one semantic 1px neutral border for separation, with info/success/warning/danger variants only when meaning requires it.
- Elevation 0: canvas/subtle grouping.
- Elevation 1: clickable card or sticky header.
- Elevation 2: sheet/drawer/action bar.
- Elevation 3: temporary critical overlay only.
- Do not combine heavy shadow, strong border, and colored background unless the state is critical.

Exact shadow blur, spread, and opacity remain UIDrop inputs.

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

## 6. UIDROP INPUT REQUIRED

UIDrop is needed to calibrate visual tokens, not to decide product behavior.

| Decision still requiring extraction | Best reference to Snap | What to measure | What is already decided |
|---|---|---|---|
| Exact surface/card radius | Linear entity surface + Attio collection/detail | card, row, drawer, control radii | Four BOSS radius roles only |
| Default card/list padding | Attio collection and Linear entity detail | internal padding at mobile/desktop densities | Six-step BOSS spacing scale and semantic recipes |
| Button/control height | Retool input/readiness surface + Raycast action entry | default, compact, sticky action controls | Minimum 44×44 mobile target and one-primary-action rule |
| Type scale and Hebrew rhythm | Linear hierarchy + Attio dense business fields | title/body/metadata/KPI ratios; then validate in Hebrew | Semantic typography roles and no local font scale |
| Shadow/elevation strength | Linear/Attio layered detail states | header, card, drawer, sticky bar shadow values | Four elevation roles and restrained use |
| Surface/background colors | Attio light surfaces + current TMA screenshot | canvas/surface/subtle/border contrast | Semantic surface hierarchy; final palette remains BOSS-owned |
| Input styling and validation | Retool readiness states + JSON Crack validation | focus, invalid, disabled, ready treatments | Canonical readiness/validation semantics |
| Density recipes | BentoPDF compact/full-width controls + Attio collection | row height, metadata count, comfortable/standard/dense deltas | Only three approved density modes; switch UI not approved |
| Search/action entry styling | Raycast launcher + Retool search | field prominence, shortcut hint, result grouping | Global/context action concepts; mobile remains touch-first |

### Supported now vs waiting for UIDrop

Supported now: hierarchy, component responsibilities, action lifecycle, status semantics, mobile/RTL rules, density modes, collection/detail continuity, validation, receipts, and accessibility contracts.

Waiting for UIDrop: exact radius, padding, control height, type scale calibration, shadow strength, surface palette, and detailed input/search visual styling.

UIDrop findings must be recorded as BOSS-owned tokens and reviewed against Hebrew text, 390px mobile, contrast, and Telegram safe-area behavior. They cannot be copied wholesale from a reference.

## 7. Admission gate

A new component or variant is accepted only when:

1. An existing primitive cannot serve the same user need.
2. The need is system-level, not a one-screen styling preference.
3. States, responsive behavior, accessibility, and action/data authority are documented.
4. The primitive is reusable by every relevant screen.
5. Review confirms it does not resolve an open product/navigation decision implicitly.
