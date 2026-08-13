# Ventures Reference Implementation Plan

**Date:** 13/08/2026
**Status:** `IMPLEMENTATION SPEC — REVIEW REQUIRED BEFORE CODING`
**Purpose:** Define Ventures as the first narrow proof of the shared BOSS screen system. No frontend/runtime change is made by this document.

## 1. Business purpose

Ventures answers one question:

> Where does this opportunity stand, and what decision or next action moves it forward?

It is an owner-only, upstream business-development workspace. It begins before a Lead or Deal necessarily exists and must not be collapsed into CRM.

The target business lifecycle is:

`Opportunity → research → evaluation → feasibility → business/financial review → negotiation → readiness → downstream activation`

The current canonical data supports only part of that wording. The implementation must display the actual schema rather than inventing missing stages.

## 2. Current canonical support

### 2.1 Schema and domain

`airtable_schema.py` defines `Tables.VENTURES`, `VentureFields`, `VentureStage`, `VentureDomain`, and `VentureConviction`.

Current canonical stages:

1. `Research`
2. `Supplier/Source Contact`
3. `Due Diligence`
4. `Legal/Tax Review`
5. `Smoke Test`
6. `GO`
7. `NO-GO`
8. `Converted`

Current fields exposed by the API:

- identity: name, domain, owner, created date;
- decision context: stage, conviction, estimated potential, target decision date, decision log, next action, notes;
- relationships: linked contacts and converted deal IDs.

`Interaction Log` and `Business Memory` exist as schema field names but are not returned by `_fmt_venture()` and have no Ventures UI/API contract. `Converted To Deal` is read but not editable through the current route.

### 2.2 Backend/API

Existing owner-only routes in `tma_api.py`:

| Route | Support | Limits |
|---|---|---|
| `GET /api/ventures` | List up to 100 Ventures; optional exact `stage` filter | No text search, sorting, pagination, aggregate facets, or permission variants beyond owner/403 |
| `GET /api/ventures/<id>` | One formatted Venture | No timeline/related-record expansion |
| `POST /api/ventures` | Create using editable field map; defaults stage to Research | No preview/receipt object; direct Airtable write |
| `PATCH /api/ventures/<id>` | Update mapped fields | No transition policy/readiness validation/receipt; direct Airtable write |
| Owner Control strategic pipeline | Stage counts, total, active | Summary only; not a Ventures collection endpoint |

The current F52 audit identifies Venture create/update as direct TMA Airtable writes outside centralized ActionGateway contracts. The reference UI must not imply an approval, execution, conversion, or receipt capability that the backend does not provide.

### 2.3 Frontend

`tma-frontend/src/components/Ventures.tsx` currently provides:

- owner entry from `App.tsx` and Owner Control;
- list loading/error/empty states;
- horizontal stage filter chips;
- Venture cards with name, potential, domain, stage, conviction, next action, and decision date;
- detail view with facts and decision log;
- inline edits for stage, conviction, next action, and notes;
- create sheet for name/domain;
- save flow followed by detail refetch;
- local fixed action bar and transient toast.

The current implementation is useful domain content. It should be refactored incrementally, not discarded.

## 3. Lifecycle mapping

| Business concept | Current support | Implementation rule |
|---|---|---|
| Opportunity intake | Venture record + create route | Supported; label as a Venture/opportunity, not a Lead |
| Research | `Research` | Supported canonical stage |
| Supplier/source contact | `Supplier/Source Contact` | Supported; may represent outreach/sourcing, not a generic negotiation contract |
| Evaluation/due diligence | `Due Diligence` | Supported canonical stage |
| Legal/business review | `Legal/Tax Review` | Supported, with exact current label |
| Feasibility/smoke test | `Smoke Test` | Supported canonical stage |
| Financial review | Fields include potential only | `OPEN`; show existing potential, date, notes, and decision log; do not create a financial-review stage |
| Commercial negotiation | No canonical stage/contract | `OPEN`; do not add a transition or status |
| Readiness | `GO`/`NO-GO` may relate, but rule is undocumented | `BUSINESS-CONTRACT GAP`; no new readiness score/gate |
| Activation/conversion | `Converted` + read-only linked deal IDs | `API/BUSINESS-CONTRACT GAP`; do not add “Convert” action until transition rules and destination ownership are approved |
| Marketing/CRM/Operations activation | No Venture transition endpoints | Future enhancement only |

## 4. Proposed screen structure

### 4.1 Page Header

- Title: Ventures.
- Context: owner-only upstream opportunities.
- Primary action: Create Venture, using the existing route.
- Secondary: refresh; other global/navigation actions remain outside this screen.
- Preserve the current entry/back behavior until the application navigation contract is implemented.

### 4.2 Lifecycle/stage representation

- Mobile default: stage rail/filter + stage-aware list, because a full eight-column board is not usable at 390px.
- Tablet/desktop candidate: board or split collection/detail using the same records and stage semantics.
- Counts may come from the loaded collection or a future API facet; do not mix Owner Control counts silently.
- Stage change remains an edit requiring validation and verified refetch. GO, NO-GO, and Converted need stronger business rules before becoming prominent transition CTAs.

### 4.3 Summary/status

Show only decision-useful summary:

- total visible opportunities;
- current filtered stage/count;
- number with a target decision date due/overdue only if dates can be computed reliably;
- active count only when the API/source definition is explicit.

Avoid a generic KPI dashboard. Every summary item must filter, drill down, or explain a decision.

### 4.4 Search and filters

- Existing stage filter: supported and reusable.
- Search: desirable from repeated reference evidence, but the API has no text query contract. A local search over the currently loaded ≤100 records is allowed only if labeled/scoped as current results and never presented as complete server search.
- Domain/conviction/date filters: schema-supported values but not current server filters. Treat as frontend-only over loaded results or API-gap work; choose one explicitly per PR.
- Saved views, sorting, and pagination remain future enhancements.

### 4.5 Venture collection

Each item must prioritize:

1. Venture name and stage;
2. next action or decision date;
3. domain and conviction;
4. estimated potential;
5. owner/related context only when human-readable data is available.

The card cannot expose record IDs. Stage/risk/conviction cannot rely on color or emoji alone.

### 4.6 Venture detail

Canonical order:

1. identity + stage;
2. key facts;
3. next action;
4. decision log/history;
5. related contacts/deal when names and destinations are available;
6. contextual actions/More.

Quick review should use a sheet/drawer that preserves collection context. Deep editing may use a full detail surface later. The first implementation can preserve the existing full-depth component behavior while extracting a shared detail structure.

### 4.7 Next action

`next_action` is already editable. It should be the dominant detail action/fact, with visible saved/saving/error state. It is text, not proof that an external task or action was created.

### 4.8 Timeline

The current API exposes `decision_log` as text but does not expose structured timeline events. The first implementation may render Decision Log as a section. It must not fabricate timestamps, sources, or events. A canonical Timeline waits for a defined Interaction Log/Business Memory/receipt source.

### 4.9 Related records

The API returns linked record IDs for contacts and converted deals, not display records. Do not render raw IDs. Hide the section or show an honest unavailable state until a relationship projection returns safe business labels and destinations.

### 4.10 Contextual actions

Supported now:

- create Venture;
- edit mapped Venture fields;
- refresh/refetch verified state.

Not supported as a safe canonical action:

- convert to Deal/Project/Marketing Demand;
- activate CRM/Operations/Marketing;
- approve GO/NO-GO as a formal gate;
- create external tasks from next-action text;
- AI-generated or automatic transitions.

Future actions must use the existing BOSS Action UX contract and existing runtime authority. Ventures must not create a parallel action architecture.

## 5. Section support classification

| Section | Existing backend support | Existing frontend support | Frontend-only work | API gap | Business-contract gap | Future enhancement |
|---|---|---|---|---|---|---|
| PageHeader | Route/data count | Inline header/back/create | Shared header, hierarchy, accessible targets | None | Final global navigation/action surface open | Shared AppShell |
| Lifecycle/stages | Canonical stage enum + stage filter | Chips and stage badges | Stage rail/list composition, non-color semantics | Facet/count query optional | Transition rules for GO/NO-GO/Converted | Desktop board |
| Summary/status | Owner Control counts; list count | List count only | Decision-useful summary from current response | Unified/faceted summary endpoint if needed | Meaning of “active/readiness” | Due/overdue summary |
| Search/filters | Exact stage only | Stage chips | Scoped local search/domain/conviction filters | Server search/sort/pagination | Query relevance rules | Saved views |
| Collection | List route with Venture fields | Venture cards | Shared ListItem/BoardCard, context preservation | None for current ≤100 list | None | Board/table modes |
| Detail | Detail route | Facts, log, editable fields | Shared detail hierarchy and safe actions | Related projections/timeline | Deep edit vs quick review rules | Split desktop view |
| Next action | Read/write text field | Inline input | Promote to canonical next-action section/state | Task/capability link if desired | Whether text creates executable work | Guided action |
| Timeline | Decision log text only | Decision Log section | Honest text section | Structured source/timestamps/events | Activity/Memory authority | Canonical Timeline |
| Related records | Linked IDs returned | Not shown | None until safe labels exist | Relationship projection with names/links | Destination ownership | RelatedContext component |
| Contextual actions | Create/PATCH direct routes | Create sheet, save bar, toast | Validation, preview, verified result after refetch | Receipt/transition endpoint | Approval/risk/conversion rules | Canonical activation flows |

## 6. Current implementation gap table

| Area | Exists | Reusable | Needs refactor | Missing |
|---|---|---|---|---|
| App entry/navigation | Boolean Ventures view in `App.tsx`; Owner Control link | Existing entry/back callbacks | Shared depth/navigation state later | Final AppShell/navigation contract |
| Header | Inline header with back/count/create | Business title/count/action | Shared PageHeader, RTL arrow, target sizes | Global/context action placement decision |
| Tokens/styles | Tailwind defaults; repeated gray/white/blue recipes | Existing 4/8/12/16 spacing and neutral surfaces | Implement the normalized BOSS dark-canvas/light-surface/blue-action tokens, 4px rhythm, restrained radii, flat elevation, focus, and motion recipes | Screenshot-level density calibration; semantic status palette |
| Collection | Venture list/cards and stage filter | Field hierarchy and load flow | Shared list/card/status primitives; preserve context | Search/sort/pagination/board |
| Detail | Facts, decision log, edit controls | Current data/state/refetch | Shared detail hierarchy; move next action upward | Timeline/related projections/receipt |
| Create | Name/domain sheet | Existing POST and form | Shared Confirmation/Sheet/validation states | Broader business intake fields if approved |
| Update | PATCH mapped fields + refetch | Existing API client and state | Explicit validation/execution/result UI | Canonical receipt and transition policy |
| Loading/error/empty | Local states | Copy/state branches | Shared state components and retry | Permission/stale/partial states |
| Status | Local stage/conviction maps | Canonical stage labels | Semantic StatusBadge; remove emoji/color-only reliance | Approved cross-domain vocabulary mapping |
| Timeline | Decision log text | Current text content | Section semantics | Structured event source/API |
| Related | IDs in response | None user-facing | None until projection exists | Safe names, destinations, permissions |
| Tests | TypeScript build; no Ventures-specific suite found | Existing build pipeline | Add focused tests when harness exists | Route/component behavior tests and screenshot regression |

## 7. Reusable current frontend concepts

- `Ventures.tsx`: fetch/state/refetch logic, stage/domain/conviction business content, create/detail forms.
- `GlobalKpis/KpiPill`: metric label/value hierarchy, after conversion into a shared semantic KPI variant.
- `ProjectCard` and `LeadCard`: clickable entity-card patterns, after removing local semantic color rules.
- `ActivityFeed` detail sheet: useful overlay composition concept; focus/scroll/safe-area behavior needs hardening.
- `OwnerControlCenter` local `Section`: useful grouping semantics; extract rather than duplicate.
- Current loading/error/empty branches: useful state inventory; unify copy and behavior.
- Current API client/auth headers and Venture TypeScript types.

## 8. Responsive reference behavior

At 390px:

- one-column collection;
- stage rail/chips with visible scroll affordance;
- full-width search/filter controls;
- detail as full-height sheet or depth view;
- one sticky primary action that respects safe-area and keyboard;
- metadata wraps safely; long next actions remain readable;
- no eight-column board requirement.

At tablet/desktop:

- collection/detail split is preferred for preserved context;
- board is optional only if stage scanning is the primary job;
- the same actions, data, statuses, and permissions remain available.

## 9. Protected product decisions

This plan does not decide:

- final primary navigation count;
- Actions full screen vs global `+` vs hybrid;
- final Operations boundary;
- Contacts/Deals placement;
- Business Memory surface;
- legacy screen deletion or consolidation.

The Ventures implementation must remain compatible with every option above.

## 10. Acceptance boundary for the reference screen

The reference implementation is successful when it proves shared BOSS hierarchy, semantic states, responsive RTL behavior, collection/detail continuity, and honest action feedback using existing Ventures data. It is not successful merely because it looks more polished.

No production claim is made by this plan. Implementation and production verification require separate work, review, deployment, and environment-specific evidence.
