# Ventures Implementation Sequence

**Date:** 13/08/2026
**Status:** `PR-SIZED IMPLEMENTATION PLAN — NO CODE EXECUTED`
**Target:** Prove the shared BOSS system on Ventures before redesigning other screens.

## 1. Sequence rules

- Preserve current Venture schema, routes, permissions, and entry points unless a phase explicitly introduces a reviewed backend dependency.
- Reuse current business data and state logic.
- Do not change final navigation, other screen architecture, Airtable schema, Action/CORE contracts, or legacy screen inventory.
- Every write state must distinguish validation, pending, verified result, and error. A toast alone is not acceptance evidence.
- If a phase discovers an authority or business-contract gap, stop that capability and continue with safe frontend work; do not infer a rule.

## 2. Recommended first coding PR

### VUX-0 — Ventures UI foundations

**Goal:** Add the smallest shared token/primitives set required to normalize Ventures, and use it immediately in Ventures. No backend or navigation change.

**Exact intended files**

- Modify `tma-frontend/src/index.css` — add the approved BOSS semantic CSS custom properties/recipes from `BOSS_DESIGN_SYSTEM_V1.md`: 4px spacing rhythm, dark canvas/light work surfaces, blue action colors, border/radius/elevation, focus, motion, safe-area, and touch targets. Do not import source-library token names.
- Add `tma-frontend/src/components/ui/PageHeader.tsx`.
- Add `tma-frontend/src/components/ui/Surface.tsx` (`Section`/`Card` variants only).
- Add `tma-frontend/src/components/ui/StatusBadge.tsx`.
- Add `tma-frontend/src/components/ui/ScreenState.tsx` (loading, empty, error with retry).
- Modify `tma-frontend/src/components/Ventures.tsx` to consume only those primitives while preserving data calls and behavior.

**Dependency:** Review/acceptance of `BOSS_DESIGN_SYSTEM_V1.md`. The owner-supplied UIDrop values are normalized and no longer block VUX-0; the missing reference screenshot blocks only a claim of visual fidelity, not implementation of the token foundation.

**Deliberately out of scope**

- `App.tsx` navigation rewrite or global AppShell rollout.
- Board, search, related records, timeline, new fields, stage-transition policy, receipt API, or other screens.
- New icon package unless an approved package already exists in the lockfile.

**Acceptance criteria**

- Ventures uses one PageHeader, Surface, StatusBadge, and ScreenState implementation.
- No API request, payload, route, permission, or schema changes.
- Statuses include text labels and do not rely on emoji/color alone.
- Back/create/retry controls have accessible names and ≥44px mobile targets.
- Existing list, detail, create, edit, stage filter, and refetch behavior remains available.
- No primitive contains Venture-specific business semantics.
- Primary button text uses the accessible BOSS on-action token; the extracted low-contrast `#D5EFFF`/`#5EB1EF` pairing is not implemented.
- Default cards remain flat; shadows appear only for interactive lift, sticky separation, or overlays.

**Tests**

- `npm run build` in `tma-frontend`.
- TypeScript compile as part of the build.
- Focused manual interaction pass: loading → list → filter → detail → edit/no-change/save/error → create/cancel.
- If a frontend test harness is introduced independently, add component tests for PageHeader action priority, StatusBadge label rendering, and ScreenState retry; do not add a large test framework only for this PR without review.

**Screenshot/manual verification**

- Capture 390×844: list, filtered empty, API error, detail, create sheet, saving, verified saved state.
- Capture 768×1024 and desktop list/detail for wrapping and spacing only.
- Verify Hebrew RTL, long Venture name, long next action, keyboard-open action bar, and safe-area.

**Rollback risk:** Low. Revert shared primitive files and the Ventures-only consumption diff. No backend/data rollback.

**Backend changes required:** No.

## 3. Subsequent phases

### VUX-1 — Ventures shell and context preservation

**Goal:** Normalize the Ventures workspace frame and preserve collection context across detail.

**Exact intended files**

- Add `tma-frontend/src/components/ui/WorkspaceShell.tsx` or promote an approved `AppShell.tsx` only if it does not encode navigation destinations.
- Modify `tma-frontend/src/components/Ventures.tsx`.
- Optionally add `tma-frontend/src/components/ventures/useVenturesViewState.ts` for filter/search/selected/scroll state when extraction materially simplifies the component.

**Dependency:** VUX-0.

**Out of scope:** Global navigation state, browser deep links, other screens, global Action Center.

**Acceptance criteria**

- Opening/closing detail restores selected stage, local query, and scroll position.
- Workspace has one scroll owner and safe-area-aware content/action regions.
- Header contains one primary action and bounded secondary actions.

**Tests:** Build; focused state restoration test if a test harness exists; manual back/close/refresh and keyboard checks.

**Screenshots:** Mobile collection → detail → returned collection at the same context; tablet split candidate only if implemented.

**Rollback risk:** Low–medium due to view-state changes.

**Backend changes required:** No.

### VUX-2 — Venture collection and lifecycle

**Goal:** Make lifecycle position and next decision legible using canonical current stages.

**Exact intended files**

- Add `tma-frontend/src/components/ventures/VentureCard.tsx`.
- Add `tma-frontend/src/components/ventures/VentureStageRail.tsx`.
- Add `tma-frontend/src/components/ventures/venturePresentation.ts` for canonical stage-to-semantic-status mapping.
- Modify `tma-frontend/src/components/Ventures.tsx`.
- Modify `tma-frontend/src/types.ts` only to narrow `stage` to the existing `VentureStage` type where responses permit.

**Dependency:** VUX-1.

**Out of scope:** New stages, drag/drop, automatic transitions, server search, saved views, pagination, conversion.

**Acceptance criteria**

- Canonical eight stages are the only lifecycle labels.
- List items prioritize name/stage/next action/decision date before secondary metadata.
- Mobile uses stage rail + list; no forced eight-column board.
- Stage state is readable without color/emoji.
- Local filtering is explicit and resettable.

**Tests:** Build; presentation-map unit tests if harness exists; manual all-stage/unknown-stage/empty filtered checks.

**Screenshots:** All stages, one selected stage, unknown/empty data, long labels at 390px and desktop.

**Rollback risk:** Low; presentation-only.

**Backend changes required:** No for current list/filter. A separate API PR is required for server search, sort, pagination, or stage facets.

### VUX-3 — Venture detail and next action

**Goal:** Restructure detail around identity, facts, next action, decision context, and honest update feedback.

**Exact intended files**

- Add `tma-frontend/src/components/ventures/VentureDetail.tsx`.
- Add `tma-frontend/src/components/ventures/VentureFacts.tsx`.
- Add `tma-frontend/src/components/ventures/VentureNextAction.tsx`.
- Add `tma-frontend/src/components/ui/DetailSheet.tsx` if the shared behavior is approved.
- Add `tma-frontend/src/components/ui/ActionBar.tsx`.
- Modify `tma-frontend/src/components/Ventures.tsx`.
- Modify `tma-frontend/src/api.ts` only if the existing PATCH response typing needs to represent its current response; no route change.

**Dependency:** VUX-0 and VUX-1.

**Out of scope:** Structured timeline, related-record names, conversion action, AI, new fields, schema changes.

**Acceptance criteria**

- Detail order follows identity → facts → next action → decision log → actions.
- No-change, validating, saving, verified-after-refetch, and error states are distinct.
- The save result states what changed without exposing IDs/tool/table details.
- Unsaved changes and close/back behavior are explicit.

**Tests:** Build; reducer/state tests if extracted; API-client mock tests when a harness exists; manual save success/failure/refetch/close-with-edits.

**Screenshots:** Detail read, editing, saving, verified result, failed save, long text, keyboard-open mobile.

**Rollback risk:** Medium because edit-state and close behavior change.

**Backend changes required:** No for existing fields. A canonical receipt contract is a separate backend dependency.

### VUX-4 — Timeline and related context

**Goal:** Add timeline/related information only after sources and projections are canonical.

**Exact intended files if the dependency is approved**

- Modify `tma_api.py` to add safe, owner-authorized Venture timeline/relationship projections; do not return raw linked IDs as UI content.
- Modify `tma-frontend/src/api.ts`.
- Modify `tma-frontend/src/types.ts`.
- Add `tma-frontend/src/components/ui/Timeline.tsx`.
- Add `tma-frontend/src/components/ventures/VentureRelatedContext.tsx`.
- Modify `tma-frontend/src/components/ventures/VentureDetail.tsx`.
- Add focused backend tests in a new/appropriate `test_tma_ventures.py`.

**Dependency:** Explicit authority decision for Interaction Log vs Business Memory vs receipts, plus safe related-record labels/destinations.

**Out of scope:** Airtable schema changes, new memory architecture, global Activity redesign.

**Acceptance criteria**

- Every timeline item has source, timestamp, human-safe summary, and related entity context.
- Related contacts/deal show business labels and authorized destinations, never raw IDs.
- Empty/unavailable states distinguish “none” from “not accessible/not supported.”

**Tests:** Backend authorization, missing relation, malformed data, empty timeline, safe redaction; frontend build and rendering states.

**Screenshots:** Populated/empty/unavailable timeline and related context on mobile/desktop.

**Rollback risk:** Medium–high because it adds an API projection.

**Backend changes required:** Yes. Skip this phase until authority is resolved.

### VUX-5 — Contextual actions

**Goal:** Present approved Venture actions through the existing BOSS action lifecycle.

**Exact intended files**

- Modify `tma-frontend/src/components/ventures/VentureDetail.tsx`.
- Add or reuse `tma-frontend/src/components/ui/Confirmation.tsx`.
- Add or reuse `tma-frontend/src/components/ui/ExecutionState.tsx`.
- Add or reuse `tma-frontend/src/components/ui/Receipt.tsx`.
- Modify `tma-frontend/src/api.ts` and `tma-frontend/src/types.ts` only for an approved existing backend result contract.
- Backend files/tests are determined by the existing canonical Action UX/runtime owner; this plan does not authorize changes to `core/` or ActionContracts.

**Dependency:** Approved capability, risk, transition, authorization, and receipt contract for each action.

**Out of scope:** New action runtime, direct frontend Airtable semantics, auto-conversion, AI-triggered writes, assumed GO/NO-GO/Converted rules.

**Acceptance criteria**

- Every action identifies intent, Venture, change, expected result, and blockers.
- Sensitive actions use preview/confirmation/approval as required by the canonical contract.
- Pending, verified result, partial/unknown, and error states are distinguishable.
- Updated business state is discoverable after completion.

**Tests:** Contract/API tests owned by the backend authority; frontend build and all action-state render tests; redaction checks.

**Screenshots:** Preview, blocked, pending, verified receipt, partial/unknown, error/retry.

**Rollback risk:** High for writes/transitions; feature flag or isolated action exposure may be required by the owning runtime plan.

**Backend changes required:** Yes for any action beyond current create/PATCH/refetch semantics.

### VUX-6 — Responsive, RTL, accessibility, and state closure

**Goal:** Close the reference-screen quality gate without broad application changes.

**Exact intended files**

- Modify only Ventures and shared UI files introduced by VUX-0–VUX-5.
- Modify `tma-frontend/src/index.css` for verified safe-area/focus/viewport fixes.
- Add focused frontend tests in the project's approved test location if a harness has been established.

**Dependency:** The implemented Ventures phases.

**Out of scope:** Other screen migrations, global navigation, visual brand redesign, dark mode unless separately required.

**Acceptance criteria**

- Complete task works at 390×844, tablet, and desktop without capability loss.
- RTL direction, focus order, visible focus, accessible names, long Hebrew text, target sizes, contrast, reduced motion, and keyboard viewport are checked.
- Initial loading, refresh/stale, first-use empty, filtered empty, permission, network error/retry, pending, verified result, partial/unknown, and recovery states are represented or explicitly not applicable.
- No screenshot shows cropped actions, hidden content, overlapping sticky bars, or unexplained status color.

**Tests:** Build; automated accessibility/component tests where available; manual keyboard/screen-reader smoke; backend permission/error fixtures for supported routes.

**Screenshots:** State matrix at 390×844 plus tablet/desktop reference captures.

**Rollback risk:** Low–medium; mostly styles/state rendering.

**Backend changes required:** Only test fixtures or explicit state support identified earlier; no schema/runtime redesign.

## 4. Dependencies and blockers

| Dependency/blocker | Blocks | Resolution owner/input |
|---|---|---|
| Referenced UIDrop screenshot not attached | Screenshot-level hierarchy/density fidelity only; does not block VUX-0 tokens | Attach the source screenshot for same-viewport visual QA before claiming a match |
| No frontend component-test harness identified | Automated UI coverage | Separate tooling decision or use existing CI/build/manual evidence |
| Venture writes bypass centralized ActionGateway according to current audit | VUX-5 canonical actions/receipts | Existing Action/runtime authority; separate reviewed backend work |
| No structured Venture timeline projection | VUX-4 Timeline | Business Memory/Interaction/receipt authority decision |
| Related records are raw IDs in current API | VUX-4 Related Context | Safe API projection with authorization and labels |
| GO/NO-GO/Converted/readiness rules undocumented | Prominent transitions and activation | Business owner + schema/action contract |
| No server search/sort/pagination | Complete collection query behavior | API contract; local search may be explicitly scoped |
| Final navigation/Actions/Operations decisions open | Global rollout only | Screen Architecture process; must not block isolated Ventures proof |

## 5. Delivery and rollback policy

Each phase is a separate PR unless review intentionally combines two low-risk frontend-only phases. Backend/API work is never hidden inside a visual refactor. Every PR states its source authority, files, test evidence, screenshots, and rollback path. No phase deletes a legacy screen or claims production completion without merge, deployment, and environment verification.
