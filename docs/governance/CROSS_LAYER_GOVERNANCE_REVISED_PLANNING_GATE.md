# Cross-Layer Governance — Revised Planning Gate

**Status:** MANDATORY GOVERNANCE POLICY

This gate protects authority boundaries, shared contracts, lifecycle and
evidence semantics, persistence/write ownership, routing, and runtime wiring.
The full Cross-Layer Impact Matrix is risk-triggered; it is not required for
every code change.

## 1. Mandatory Cross-Layer Assessment

Before implementation, record answers to all of these questions:

1. Which architectural layer owns the change?
2. Does it modify an existing authority boundary?
3. Does it modify a shared contract, lifecycle, evidence, ownership, routing,
   persistence, or write path?
4. Does it introduce a new caller/callee relationship across layers?
5. Does it activate previously dormant or unwired code?
6. Does it create or modify a fallback or bypass path?
7. Can another layer now make a decision previously owned elsewhere?

The assessment is mandatory. Classify the change as `NONE`, `SINGLE-LAYER`,
`FULL`, or `UNCERTAIN`.

## 2. Local change — `NONE`

Use `Cross-Layer Impact: NONE` only when the change is local to one established
authority and does not affect another layer. Record exact files/functions, the
canonical owner, grep/call-site proof that no cross-layer contract changed, and
confirmation that no new bypass or authority was introduced.

## 3. Single-layer contract change — `SINGLE-LAYER`

For an owned contract change inside one layer that does not transfer authority
or change another layer's behavior, record:

| Field | Required |
| --- | --- |
| Owning layer | yes |
| Files/functions | yes |
| Contract changed | yes |
| Authority changed | yes/no |
| Other layers affected | yes/no |
| New caller/callee edge | yes/no |
| Bypass/fallback changed | yes/no |
| Required regression surfaces | yes |

If authority and other-layer impact are both `no`, a full matrix is not
required.

## 4. Full matrix — `FULL`

A reviewed Cross-Layer Impact Matrix is mandatory when any of these applies:

- authority moves, a second authority/source of truth is introduced, or an
  existing authority is bypassed;
- routing, reply, execution, task, or action ownership changes;
- ActionContract lifecycle, evidence, claim authorization, or
  success/failure/pending/unknown semantics change;
- a shared MessageContract, ActionFact, GatewayReply, identifier, schema, or
  result contract changes across boundaries;
- persistence authority, durable state, fail-closed persistence, or canonical
  CRM/Airtable write paths change;
- dormant/unwired code becomes a runtime caller, a new cross-layer edge is
  introduced, or feature-flag behavior changes runtime authority;
- a fallback or bypass path changes;
- two or more architectural layers require code changes for the same behavior.

Dormant-code activation must also document current authority, proposed
relationship (replace, decorate, project, or compete), rollback behavior, and
runtime/regression verification.

## 5. Fail-closed uncertainty

If classification is uncertain, record `Cross-Layer Impact: UNCERTAIN` and
complete the FULL matrix or obtain architecture review. Uncertainty never
bypasses governance.

## 6. PR evidence and freeze rule

Every implementation PR must contain exactly one declaration:

- `Cross-Layer Impact: NONE` with local evidence;
- `Cross-Layer Impact: SINGLE-LAYER` with the Mini Assessment; or
- `Cross-Layer Impact: FULL` with the completed matrix.

A CORE v1 freeze does not make every future edit a full-matrix change. The
trigger is architectural impact, not change size, file location, importance, or
test count. Existing matrices remain valid for the changes they describe and
are not retroactive.
