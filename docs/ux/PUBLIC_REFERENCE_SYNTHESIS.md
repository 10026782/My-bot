# SCOREBOS Public Reference Synthesis

**Date:** 13/08/2026  
**Scope:** Public Evidence Synthesis מצומצם בלבד  
**Evidence rule:** `OBSERVED` בלבד הוא בסיס לממצא. `INFERRED` מופיע רק בסעיף נפרד ואינו החלטה מחייבת. `NOT VERIFIED` אינו נכנס ל־synthesis.

This document does not reopen the SCOREBOS UX Constitution, select screens, define final navigation, or approve any reference pattern for implementation.

## 1. Evidence Coverage

### References with rendered evidence

| Reference | Rendered states observed | Viewport / access boundary |
|---|---|---|
| Linear | Public homepage; embedded issue-detail demonstration; public responsive pass | Desktop public page and 390x844 public responsive viewport. Native/authenticated mobile app is not verified. |
| Attio | Public Home/work overview; Companies collection; meeting/transcript; pipeline/deal context; AI/action entry | Desktop and 390x844 public responsive pass. Authenticated workspace behavior and native mobile are not verified. |
| Raycast | Launcher/command entry; extension catalog; category grouping; verb-oriented action examples | Public marketing/demo presentation; real execution and permissions are not verified. |
| Retool | Global search; prompt entry; disabled-before-input state; starter prompts; integrations/workflow grouping | Public product presentation; operations dashboard behavior is not verified. |
| Pipedrive | Public product-family collection; sales-feature collection; public AI Sales Advisor / demo entry | Public product pages; authenticated pipeline, entity and action behavior are not verified. |
| monday CRM | Public CRM job entry; revenue-lifecycle tabs; agent-role panels | Public CRM demonstration; authenticated collection, entity and action behavior are not verified. |
| Linear Mobile | Public responsive rendering of the Linear homepage and embedded issue example | 390x844 public viewport; this is not native/authenticated mobile evidence. |

### Remaining limitations

- Authenticated collection/detail behavior is not covered meaningfully across the reference set.
- Native or authenticated mobile workflow coverage is not broad; Linear and Attio results are public responsive pages only.
- HubSpot is blocked by the local Nativ policy page.
- Intercom and Notion are blocked by the local Nativ policy page.
- Stripe Dashboard is login-only in this environment.
- Vercel Dashboard redirected to login.
- Figma did not reach a stable rendered public state in the inspection window.
- Airtable Interfaces resolved to an unavailable public target path; Tana remains not verified.
- Role/permission, advanced filtering, real mutations, confirmation, loading/error, and persistent AI behavior are mostly not verified.

### What must not be inferred

Public pages and product demonstrations must not be treated as proof of authenticated product behavior, actual information architecture, real task completion, permission handling, mobile app behavior, or production interaction semantics. Marketing language is not evidence of behavior.

## 2. Repeated Patterns Across References

Only patterns supported by more than one reference are listed here. These are evidence findings, not final SCOREBOS decisions.

### 2.1 Global action/search entry

- **Supporting references:** Linear, Raycast, Retool.
- **Evidence level:** `OBSERVED` as public shell, launcher, or search/input entry; the exact authenticated behavior is not verified.
- **User problem addressed:** users should be able to discover or start a common action without repeatedly traversing deep navigation.
- **Existing mapping:** DEC-UX-02, DEC-UX-06, DEC-UX-07.
- **Constitution coverage:** existing shared shell, Global Quick Action/Command entry, canonical action architecture, and capability discoverability already cover this finding.

### 2.2 Lifecycle or domain grouping

- **Supporting references:** Attio, Pipedrive, monday CRM.
- **Evidence level:** `OBSERVED` in public CRM/product demonstrations: pipeline/revenue framing, product or feature families, and lifecycle tabs. This does not prove SCOREBOS navigation or a specific domain model.
- **User problem addressed:** users need to understand where a record or task sits in a broader business lifecycle and what kind of work a surface supports.
- **Existing mapping:** DEC-UX-09, DEC-UX-10, DEC-UX-11.
- **Constitution coverage:** existing shared data/entity primitives, connected lifecycle rule, and approved Table/List/Board/workflow compositions already provide a framework for this learning.

### 2.3 Clear collection hierarchy

- **Supporting references:** Attio, Pipedrive, monday CRM.
- **Evidence level:** `OBSERVED` public collection or grouped-entry states, not authenticated dataset behavior.
- **User problem addressed:** users need a legible starting point that separates categories, work stages, records, and next areas of exploration.
- **Existing mapping:** DEC-UX-09, DEC-UX-10, DEC-UX-11.
- **Constitution coverage:** existing DataTable/List/Board primitives, shared sorting/filtering/pagination behavior, and connected lifecycle/context rules already cover the structural requirement without adding a new component family.

## 3. Strong Single-Reference Patterns

These findings are useful but are not approved and are not repeated-pattern conclusions.

### Context-preserving entity work — Linear

`SINGLE-REFERENCE CANDIDATE`

`OBSERVED`: the public Linear demonstration keeps issue title, status, priority, owner, labels, activity, and contextual AI near the current entity. This is useful because it reduces context loss between inspection and next action. More validation is required against authenticated SCOREBOS-like entity workflows, permissions, dense data, mobile detail, and real action receipts before adoption as a cross-system pattern.

### Explicit readiness state — Retool

`SINGLE-REFERENCE CANDIDATE`

`OBSERVED`: the public prompt surface visibly distinguishes an empty or unavailable submit state from an active input state. More validation is required against SCOREBOS canonical action states, validation, pending/blocked/error feedback, and non-AI forms before treating it as a system pattern.

### Responsive compression of public capability — Linear

`SINGLE-REFERENCE CANDIDATE`

`OBSERVED`: the public Linear page rendered at 390x844 while retaining the public header, hero, and embedded issue demonstration in the DOM. This is not evidence that native mobile preserves all authenticated capability. More mobile references and authenticated workflows are required before adopting any compression rule.

## 4. Patterns Already Covered by SCOREBOS Constitution

| Reference learning | Existing Constitution coverage | Classification |
|---|---|---|
| Global action/search entry | Fixed Shell + Flexible Zones; Global Quick Action/Command; canonical actions and capability discoverability | Existing shared primitive / existing action architecture |
| Entity context near the current work | Connected lifecycle; depth-based navigation; entity header, next action, related context, and preserved return context | Existing navigation/context rule |
| Collection hierarchy and reusable dataset views | DataTable, List, Board, Entity Header and Timeline; shared filtering, sorting, pagination, selection and responsive adaptation | Existing shared primitive |
| Lifecycle-oriented grouping | Shared entities, connected lifecycle and approved Table/List/Board/workflow composition | Existing navigation/context rule and approved variation mode |
| Contextual AI beside current work | Contextual Side Assistant; separate context selection; canonical action boundary; distinction between data, suggestion and verified result | Existing AI rule |
| Readiness, pending and feedback clarity | Verified Feedback and Responsive Contract; shared semantic states and action safety | Existing shared primitive / existing action architecture |
| Mobile adaptation | Desktop and Mobile as one conceptual Shell with responsive adaptation; approved responsive rules | Existing responsive rule |

The evidence therefore mostly maps to the approved system. It does not justify expanding the Constitution or selecting a final screen architecture.

## 5. System-Level Pattern Candidates

Only findings that do not map cleanly enough to the approved framework appear here. None is approved.

### Keyboard-first command model — Raycast

`SYSTEM-LEVEL PATTERN CANDIDATE`

Raycast presents a strongly keyboard-first launcher and verb-oriented command model. The existing Constitution covers Global Quick Action/Command, but does not by itself decide whether keyboard-first interaction should be a system-level priority across SCOREBOS. Validation still requires device/context fit for Telegram, WebView and desktop, accessibility, discoverability for non-keyboard users, and action safety for high-risk operations.

No other system-level candidate is promoted from the current public evidence. In particular, public AI prompt/app-builder behavior is not sufficient to create a new SCOREBOS AI interaction model.

## 6. Public Evidence Design Lessons

These are system-level lessons supported by the observed evidence, not screen specifications:

- Preserve the user's context while moving from collection or work item to detail and next action.
- Make lifecycle or domain position legible where work spans multiple stages.
- Keep global action and search entry discoverable from the shared shell.
- Use clear collection grouping so users can distinguish records, categories, stages and available work.
- Treat mobile as an adaptation of the same capability model; do not assume that a public responsive page proves native mobile parity.
- Keep dense data and contextual detail related but separable through the existing approved modes.
- Make readiness and action availability visible before a user submits or commits work.

## 7. Explicit Non-Decisions

The current evidence does not decide:

- authenticated entity/detail behavior;
- role and permission UX;
- advanced filters and saved-view behavior;
- real workspace actions, mutations, confirmations, receipts or error recovery;
- persistent AI side-panel behavior;
- authenticated mobile workflow;
- final screen count, primary navigation, workspace boundaries or consolidation;
- final component selection or Reference DNA per screen;
- whether any candidate should become a new system primitive.

## Verdict

`PUBLIC SYNTHESIS READY`

`FULL SYNTHESIS NOT READY`

Before the Full Reference Synthesis Gate, the following evidence is still required:

1. Authenticated collection and entity/detail states from several representative references, including real search, filtering, actions, confirmation and receipt behavior.
2. Authenticated mobile workflow coverage across more than one reference, including navigation, collection, detail and action states.
3. Permission and role-state evidence, including allowed, restricted and partially available actions.
4. Evidence for advanced filters, saved views, sorting, pagination, empty/loading/error states and return-context preservation.
5. Stable rendered inspection or authorized access for currently blocked, login-only and unstable references where those products are needed for comparison.

Stop condition: this document intentionally stops before final pattern selection, screen design, navigation decisions, Constitution changes, implementation or cloning.
