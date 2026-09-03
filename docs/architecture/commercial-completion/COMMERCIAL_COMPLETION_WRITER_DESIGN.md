# Commercial Completion Writer — discovery, design, and pure foundation

## S2C routing boundary

`commercial_completion_routing.py` is the owner-approved production
orchestration adapter. It uses the single `CommercialCompletionWriter`
contract and `CompletionSession`, and returns only `CLARIFY`, `TOOL`, or
`BLOCK`. Complete payloads are translated by an explicit entity-to-primitive
mapping and passed to the existing approval queue supplied by the caller; the
router has no Airtable or generic mutation authority.

The approved S2C targets are Deal, Payment Term, Organization, Charge, and
Charge-required V2 Payment. Allocation Rule, Allocation Snapshot, and Deal
Economics remain foundation-only. ActionGateway/ActionContracts remain the
approval and execution boundary, and the legacy Payment writer remains
quarantined.

## Shared presentation metadata

Commercial UX uses the provider-neutral `core.draft_fields.FieldMetadata` shape
for field keys, user-facing labels/prompts, input type, choices, and resolver
metadata. Commercial ownership remains in `commercial_completion_ux.py`: it
defines the Commercial labels, link-resolution semantics, and choice behavior.
The generic `SET_FIELD`/`CLEAR_FIELD`/`MOVE_FIELD`/`SWAP_FIELDS` mechanics are
not connected to `CompletionSession` by this change.

**Date:** 03/09/2026  
**Evidence level:** S2B `CODE_DONE + STATIC_VERIFIED` on PR branch
**Runtime state:** unwired; no Airtable records created or modified  
**Cross-Layer Impact:** FULL (design/shared-schema contract; no runtime activation)

## S2B implementation addendum

S2B adds exactly three internal, approval-sensitive production mutation
primitives: `find_or_create_organization()`, `create_charge()`, and
`create_charge_payment()`. The branch is based on merged S2A `origin/main`
`23ab957e75961c7b50f929e263eddd3f0d6632c8`. The primitives are registered to
`decision.commercial_v2_mutation_primitives`, use the existing Airtable gateway,
and remain behind identity, role, tenant, emergency-stop, ActionContract,
approval, idempotency, execution-proof, payload-parity, evidence, and protected
generic-table dispatcher guards.

Organization matching is exact after trim, internal-whitespace collapse, and
case folding. Zero matches creates with the submitted display spelling, one
match reuses, and multiple matches fail closed. Organizations remain universal:
no Owner, tenant, user, or channel field was invented. Charge requires a valid
Deal and optionally validates a Billing Term against that Deal. V2 Payment
requires one Charge and rejects any Deal, Direction, Currency, or optional Term
that does not match the Charge; only an actual `received` movement with `Paid At`
can be created.

No completion-engine caller, deterministic route, reader, channel, Mini App,
scheduler, allocation writer, Contact writer, or Agent-facing schema was added.
The legacy `create_payment()` function and the single legacy Payment record were
not changed or reinterpreted. Live canary, deployment, merge, writer/read switch,
and runtime verification remain outside this PR.

## A. Truth reset

- Fetched `origin/main` and inspected current tip `05dc2de99c9ad47d70becbd55b2a877f633eb917`.
- The shared checkout was at `0f80122525c5bbc9e3b115a4f7c4e131ac47070b`
  with unrelated dirty work. Implementation was isolated in a worktree based on
  current `origin/main`; no shared-checkout branch switch or cleanup occurred.
- One unrelated unmerged branch, `github/claude/epic-volta-gjase4`, contains
  only an `AI_CONTEXT.md` briefing change and does not overlap this scope.
- Live Airtable readback: Leads 40, Contacts 421, Deals 5, Payment Terms 0,
  Payments 1, and Charges / Allocation Rules / Allocation Snapshots /
  Deal Economics / Organizations all 0.
- No Airtable mutation tool was called in this work.

The current source is newer than the earlier commercial schema work. It contains
the September write-boundary hardening: generic creates for Deals, Payment Terms,
and Payments are redirected through the narrow canonical writers; unsupported
fields fail closed; generic updates use closed field allowlists and canonical
domain conversion; Contacts use the deduplicating Contact gate.

## B. Current writer and mutation map

| Mutation | Current entry points | Canonical mutation primitive | Current safeguards | V2 finding |
| --- | --- | --- | --- | --- |
| Lead create/update | lead capture/service flows; generic Lead writes blocked | `core.lead_service` / approved lead capture | Lead write gate, owner resolution, dedup, Gateway | Keep outside this completion foundation |
| Contact create | dedicated tool, generic Airtable create redirect, TMA, `/convert` | `crm.create_contact_from_fields()` → `find_or_create_contact()` | serialized dedup, validation, identity-aware lookup | Wrap later for nested Contact completion; never bypass |
| Contact update | generic update redirect | `crm.update_contact()` | Contact boundary + dispatcher policy | Keep |
| Deal create | deterministic Telegram route, `/dealfromlead`, dedicated tool, protected generic-create redirect | `commercial_crm.create_deal()` | TurnDecision route, role policy, ActionContract/Gateway, emergency stop, owner resolution, closed field map | Wrap later; signature lacks most V2 fields |
| Payment Term create | dedicated tool and protected generic-create redirect | `commercial_crm.create_payment_term()` | role policy, ActionContract/Gateway, emergency stop, calculation checks | Wrap later; only legacy enum/field subset |
| Payment create | dedicated tool and protected generic-create redirect | `commercial_crm.create_payment()` | role policy, ActionContract/Gateway, emergency stop | Do not call for V2: permits no Charge and creates pending obligation-like rows |
| Deal/Term/Payment update | generic update with protected-table role re-check and closed field map | generic Airtable update | ActionContract execution proof, allowlist, domain normalization | Keep until narrow update primitives exist |
| Organization create/reuse | protected generic redirect; dedicated internal tool | `commercial_crm.find_or_create_organization()` | normalized exact match, ambiguity fail-closed, Gateway/dispatcher controls | S2B implemented; no caller wired |
| Charge create | protected generic redirect; dedicated internal tool | `commercial_crm.create_charge()` | Deal/Term relationship validation, closed fields, Gateway/dispatcher controls | S2B implemented; no caller wired |
| V2 actual-movement Payment create | protected V2 generic redirect; dedicated internal tool | `commercial_crm.create_charge_payment()` | Charge-required relationship validation, closed fields, Gateway/dispatcher controls | S2B implemented; legacy writer remains quarantined |
| Allocation / Economics create | none | none | none | New narrow primitives require a later slice |
| Allocation Snapshot create | none | none | n/a | Must be system-generated, immutable, and non-conversational |

ActionContracts remain the sole approval lifecycle authority. The completion
engine is not a writer despite its architectural name: it completes and validates
a payload, then stops. A later integration must submit that payload through the
existing TurnDecision → policy → ActionContract/ActionGateway chain.

## C. Field Completion Matrix

The exact 247-row field matrix is in
[`FIELD_COMPLETION_MATRIX.csv`](FIELD_COMPLETION_MATRIX.csv). It includes every
live field on all ten requested entities plus approved target fields that are not
live. Each row records requiredness, conditional rule, input type, target and live
choices, inheritance/derivation/defaults, manual/custom policy, example,
validation, exact Airtable field, live type, and completion disposition.

Important classifications:

- Examples are help text only and never participate in value resolution.
- Formula, rollup, lookup, AI, created-time, and last-modified fields are never
  requested or manually written.
- Allocation Snapshots are system-only; conversational completion is blocked.
- Deal requires one explicit counterparty link: Contact or Organization. Lead is
  optional. `Deal Type Code` is the additive canonical V2 select; legacy `Deal
  Type` text remains untouched.
- Payment Term requires Deal. Fixed, percentage, per-unit, usage-based, tiered,
  and custom terms have explicit conditional inputs. Specific/scheduled due rules
  require their dedicated deterministic date fields.
- Charge requires Deal; Billing Term is optional for direct one-off Charges.
- New V2 Payment requires Charge, positive amount, movement date, Direction, and
  Currency. Its status resolves deterministically to `received`; this contract is
  not passed to the current legacy-shaped Payment writer.

## D. Flow Matrix

| Source | Target | Auto-inherited | Auto-derived/defaulted | User-required | Optional | Blocking conditions |
| --- | --- | --- | --- | --- | --- | --- |
| Lead | Deal | Origin Lead, name, domain, owner; existing Contact when explicit | Deal Stage = opportunity | counterparty if absent, Deal Type, Relationship Type, Currency, Commercial Status, Expected Value | notes; Lead itself remains optional | current Deal writer lacks V2 signature parity |
| Direct | Deal | authenticated owner and source context when supplied | Deal Stage = opportunity | name, domain, counterparty, Deal Type, Relationship Type, Currency, Commercial Status, Expected Value | Origin Lead, notes | no Lead may be manufactured |
| Deal | Payment Term | Deal; Direction/Currency when supplied by Deal context | name, once cadence, immediate trigger, immediate due rule, zero grace, draft status, VAT none | Calculation Type and its conditional values | limits, dates, notes | no production Payment Term V2 writer switch |
| Deal / Payment Term | Charge | Deal, optional Billing Term, Direction, Currency, due context | draft/not-due state, VAT none, document state; future terms snapshot | amount unless deterministically calculable | direct Charge may omit Billing Term; expected/promised fields | primitive exists; completion caller remains unwired |
| Charge | Payment | Charge, Deal/Term, Direction, Currency, counterparty | status received; document state | amount and Paid At | method, reference, notes | Charge-required primitive exists; completion caller remains unwired |
| Deal | Allocation Rule | Deal; optional Term/Charge | priority 0, draft status | Contact or Organization beneficiary, allocation type, basis, conditional rate/fixed/unit value | dates, notes | custom type/basis lacks explicit detail field |
| Charge | Allocation Snapshot | Charge, Rule, beneficiary | basis, resolved amount, timestamp, snapshot | none | none | system-only; no immutable snapshot primitive exists |
| Deal | Deal Economics | Deal | missing amount components default to zero; total cost/profit/margin/ROI derived | none beyond Deal | amount components, notes | Margin/ROI are writable live fields and need a deterministic derivation primitive |
| Deal | nested Contact | source name/phone/email/company | none | Contact name and valid phone | email/company/role | must return through existing Contact gate |
| Deal | nested Organization | company name | none | Organization Name | none | primitive exists; nested completion caller remains unwired |

## E. Canonical architecture

```text
channel adapter / command / form
        ↓ values only
CommercialCompletionWriter(target_entity, current_values, source_context, identity)
        ↓ deterministic contracts
resolve existing → inherited → derived → default
        ↓
calculate required-minus-known fields
        ↓
validate one answer (chat) or the same field set (form/API)
        ↓
complete canonical Airtable-field payload
        ↓ future integration only
narrow entity mutation primitive
        ↓
TurnDecision + policy + ActionContract / ActionGateway
        ↓
canonical Airtable gateway mutation + evidence
```

`CommercialCompletionWriter` contains no Agent/LLM call, Airtable import,
dispatcher import, Gateway import, or channel code. `CompletionSession` provides a
pure stack for nested Contact/Organization completion and requires a canonical
record ID before resuming the parent Deal.

## F. Existing writer disposition

| Surface | Decision | Reason |
| --- | --- | --- |
| `commercial_crm.create_deal` | WRAP later, then REFACTOR signature | It is the current protected create primitive, but cannot accept the complete V2 Deal contract |
| `commercial_crm.create_payment_term` | WRAP later, then REFACTOR | Preserve current calculation checks and gateway boundary; expand only after live enum parity |
| `commercial_crm.create_payment` | DEFER / do not call for V2 | Its pending/no-Charge semantics conflict with actual-movement V2 Payment |
| Contact gate | KEEP and WRAP | It is the canonical dedup/security boundary for nested Contact creation |
| generic Airtable protected redirects | KEEP | They close role and validation bypasses; future maps must not broaden before primitive parity |
| legacy `crm_add_deal` / `crm_add_payment` | KEEP quarantined | Historical domain-shaped paths are not revived as V2 writers |
| new Organization/Charge/V2 Payment primitives | KEEP, internal and unwired | S2B narrow authority; no Agent or completion-engine caller |
| new Allocation/Economics primitives | DEFER | Require separate reviewed write-contract slice |

## G. Minimal code implemented

- `FieldContract`, `EntityContract`, deterministic `Condition`, input and source
  enums.
- Contracts for Lead, Contact, Organization, Deal, Payment Term, Charge, Payment,
  Allocation Rule, Allocation Snapshot, and Deal Economics.
- Existing/inherited/derived/default resolution according to source priority.
- Required, conditional, and one-of-group missing-field calculation.
- Chat one-field and form multi-field projections from the same contracts.
- Deterministic validation for choices, links, numbers, currency, percent, dates,
  email, and phone.
- Fail-closed unsupported-contract guards.
- Pure nested completion/resume stack.
- No production import or caller was added.

## H. Static verification

- Completion foundation tests: 19 passed.
- Existing commercial simulation and schema tests are included in the final
  verification command for this branch.
- No runtime, deployment, or live-write verification is claimed.

## I. S2A/S2B closure state and remaining implementation slices

S2A is closed at `LIVE_SCHEMA_VERIFIED + STATIC_VERIFIED_ON_BRANCH`: all
approved additive native fields, including the Deal rollups and dependent
formula, were directly read back as valid. S2B now implements the approved
Organization, Charge, and Charge-required Payment primitives at `CODE_DONE +
STATIC_VERIFIED` on the PR branch. Allocation Snapshot, Allocation Rule, Deal
Economics, update primitives, completion integration, and reader/writer cutover
remain separate explicitly gated work.

## J. Exact next implementation slice

After S2B review/merge, the next slice requires a separate owner decision. Valid
candidates are a controlled deployment/live-canary plan or completion-engine
integration through an approved deterministic caller and the existing
ActionGateway. Reader/writer cutover, updates, allocations, economics, automatic
Charge generation, and scheduler behavior remain outside S2B. The current
Payment primitive stays quarantined for legacy callers.

## Cross-layer impact matrix

| Layer / boundary | Touched | Inputs | Outputs | Side effects | Identity / approval / evidence | Failure semantics | Proof |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Core reasoning | no | none | none | none | unchanged | unchanged | no imports/callers from completion module |
| Turn coordination/routing | no | none | none | none | existing deterministic Deal route unchanged | unchanged | `app.py` and router diff-free |
| Tool/dispatcher contract | yes, dormant internal cases | exact named primitive inputs | structured write evidence | only after approved execution proof | existing policy/Gateway controls retained | unknown fields and generic bypasses fail closed | focused dispatcher and bypass tests |
| ActionContract/Gateway | no | none | none | none | remains sole lifecycle authority | unchanged | Gateway diff-free; no Gateway import |
| Airtable schema vocabulary | yes, additive declarations | approved V2 field names/enums | constants | none | no identity/approval effect | unsupported live parity is documented and blocked | schema tests + live readback |
| CRM mutation authority | yes, three exact S2B symbols | closed Organization/Charge/Payment inputs | canonical Airtable fields | gateway write only after dispatcher proof | new decision node and writer registry | relationship and vocabulary failures are deterministic | 27 focused tests; legacy writer diff-preserved |
| Channel UX | no | none | none | none | no reply ownership change | adapters not implemented | no Telegram/WhatsApp/TMA imports |
| RP5/evidence | no | none | none | none | no success claim path | unchanged | no evidence imports or status rendering |

S2B grants only the three owner-approved symbol-level mutation authorities. No
existing authority moved, no fallback was activated, no completion/channel
caller was introduced, and generic bypass handling was narrowed to converge on
or protect the canonical primitives.

## Context Librarian verification ledger

- Selected profile: `cross_layer_architecture`.
- Bundle status: REVIEW_REQUIRED, no STOP reason, mandatory authority coverage
  100%, six stale nodes.
- Directly reverified current `origin/main` source for commercial writers,
  dispatcher protected redirects, tool schemas/registry, action validator,
  deterministic Deal routing, ActionGateway authority, Contact gate, approved
  schema docs, and live Airtable schema/counts.
- Bundle estimate: 14,012 / 14,300 tokens, overflow 0; 48 / 48 document budget.
  The bundle is navigation metadata only and was not made a runtime or business
  source of truth.
# S2D-R1 Human Completion UX

`commercial_completion_ux.py` is a presentation and deterministic-resolution
adapter over the canonical completion contracts. It maps field contracts to
business-language prompts and finite-choice metadata, and accepts injected,
bounded resolver lookups for human Contact/Organization/Deal/etc. input.
Internal field keys and record references remain adapter/session data only;
they are never rendered in completion responses. The adapter does not persist
state, route requests, approve actions, or write Airtable, and it does not
introduce a second completion state machine or writer.
