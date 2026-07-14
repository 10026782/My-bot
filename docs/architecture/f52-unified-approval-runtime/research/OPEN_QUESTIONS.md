# Phase 4C — Open Questions

Program: F52 — Unified Approval Runtime Migration and Implementation
Document role: Decision and blocker register
Historical research identifier: Phase 4C
Status: Active planning register

Only questions not answerable from repository code/tests at `origin/main` `4d3787e6e6fcbc93bd5a30f62f0834136b706f06` are listed. “Blocks 4C-1” means implementation should not start without the answer; other questions block only their named later phase.

## Closed decisions

### Q3 — Claim requirement for all 11 approval-required tools

Status: CLOSED

Decision:
All 11 tools currently marked `requires_approval` remain in the
approval-required cohort for F52 migration.

Every one of these tools requires verified live PostgreSQL execution ownership
before provider execution.

This includes:

- `gmail_draft`
- `send_followup`
- `send_recovery`

Any future reclassification of drafts, notifications, or other low-risk actions
is a separate business-policy change and is not part of the F52 migration.

Effect:
Q3 no longer blocks implementation readiness.

## Q1 — Which feature-flag combinations are supported after Phase 4B cutover?

- Why it matters: source defaults ActionGateway, contract persistence and atomic claims off, and flag-off code preserves direct execution. 4C-1 must know whether it may make persistence+claims hard prerequisites or must support another fail-closed mode.
- Missing evidence: verified Render values on every active process, rollout/cutover completion record, and rollback policy.
- Decision owner: deployment/technical owner.
- Blocking: **Blocks 4C-1.**

## Q2 — What Telegram callback reference format is acceptable?

- Why it matters: buttons currently carry an 8-character EB ID. New buttons must resolve immutably to one AC while respecting Telegram callback-data size and preventing cross-recipient/stale use.
- Missing evidence: product preference for raw UUID versus signed compact opaque reference; retention/expiry expectation for old messages.
- Decision owner: technical owner with product/security review.
- Blocking: **Blocks 4C-1.**

## Q4 — What should happen to Telegram buttons created before 4C-1?

- Why it matters: EB-only callbacks cannot be safely linked to a contract after restart without recomputing mutable display data, and direct fallback must not remain.
- Missing evidence: acceptable UX—expire with explanation, locate a uniquely matching durable AC under strict rules, or ask user to reopen the approval list.
- Decision owner: product/technical owner.
- Blocking: **Blocks 4C-1 rollout**, not core implementation. Safe default is stale/read-only.

## Q5 — How do WhatsApp destination numbers map to tenant and domain?

- Why it matters: code maps destination to domain but tenant configuration currently proves only `boss_hq`; separate numbers per domain may later cross tenants. Approval replies must not authorize across those boundaries.
- Missing evidence: authoritative number inventory, tenant ownership, allowed cross-channel presentation, phone normalization and reassignment policy.
- Decision owner: business owner plus identity/security owner.
- Blocking: Phase 4C-3 only.

## Q6 — Which channel receives approval for a WhatsApp-originated proposal?

- Why it matters: current voice/follow-up paths present to the Telegram owner even when origin is WhatsApp. A WhatsApp-native adapter could instead reply in-channel, or policy could require an independent owner channel.
- Missing evidence: approver UX, delivery provider, timeout/escalation and cross-channel identity rules.
- Decision owner: product/business owner.
- Blocking: Phase 4C-3 only.

## Q7 — Are file uploads self-confirmed requests, approval-required business mutations, or bounded ingestion?

- Why it matters: uploads immediately write Drive and Airtable, and failure can leave an orphaned file. The correct policy determines whether a human approval is needed or only a typed idempotent handler/evidence contract.
- Missing evidence: business policy by channel/role/file type, retention/cleanup rules, and whether owner upload intent itself is sufficient authorization.
- Decision owner: business/data-governance owner.
- Blocking: Phase 4C-4 only.

## Q8 — What is the canonical durable provider receipt shape and retention policy?

- Why it matters: `agent_observations` is intentionally RAM-only. Multi-provider and reconciliation flows need durable bounded evidence without storing excessive personal/provider data.
- Missing evidence: audit retention, redaction requirements, acceptable Airtable field sizes, whether receipts belong on AC or a separate immutable audit table.
- Decision owner: technical/data-governance owner.
- Blocking: Phase 4C-4; 4C-1 can retain current verified lifecycle outcome but should not claim complete receipt durability.

## Q9 — Which scheduler mutations are formally pre-authorized?

- Why it matters: lead-memory flush, interaction audit, Tasks creation, quest reset, usage audit and schema snapshot differ materially. A generic “scheduler is trusted” rule would be too broad.
- Missing evidence: per-job owner, tenant, field/table scope, rate, expiry, retry and acceptable outcome behavior.
- Decision owner: business owner for business jobs; operations owner for telemetry/safety jobs.
- Blocking: Phase 4C-5 only.

## Q10 — What is the canonical system principal and delegation model?

- Why it matters: background actions need stable initiator identity and tenant/domain scope without pretending to be a human requester.
- Missing evidence: system identity namespace, policy owner, delegation version/expiry/revocation and audit requirements.
- Decision owner: identity/security architect.
- Blocking: Phase 4C-5 only.

## Q11 — Which owner-direct TMA mutations should remain immediate?

- Why it matters: owner lead patch/outcome/task branches skip AC while manager paths queue. Code proves the difference but not the intended policy. Owner role alone should not silently mean self-confirm for every mutation.
- Missing evidence: product decision per route/action and whether the TMA submit gesture is sufficient self-confirmation.
- Decision owner: business/product owner.
- Blocking: Phase 4C-4 or a dedicated TMA follow-up, not 4C-1.

## Q12 — What is the drain window for legacy EB/AP/router pending state?

- Why it matters: deletion requires proof that no live presentation/caller remains. Legacy AP rows already fail closed, but EB buttons and router RAM state disappear on process restart.
- Missing evidence: maximum supported approval age, active legacy counts/metrics and customer-facing expiry wording.
- Decision owner: product/operations owner.
- Blocking: Phase 4C-6; old Telegram button behavior in Q4 must still be decided for 4C-1 rollout.

## Q13 — Is ActionContracts Airtable transition conflict detection sufficient for lifecycle audit under expected load?

- Why it matters: repository transition uses expected version/status and readback, but Airtable does not provide atomic compare-and-swap. PostgreSQL protects provider execution, not necessarily concurrent audit-field edits.
- Missing evidence: observed conflict rate, desired audit consistency SLA, and whether lifecycle writes should be serialized/recorded in an append-only store.
- Decision owner: architecture/data owner.
- Blocking: later lifecycle hardening, not 4C-1, provided PG remains sole execution owner and conflicts fail visibly.
