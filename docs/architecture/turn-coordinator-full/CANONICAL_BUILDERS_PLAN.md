# Canonical Builders Plan

Builders are planned interfaces, not implementations. Each produces:

```text
intent, canonical_tool, resource, fields, risk, approval_required,
evidence_requirement, reply_policy
```

| Builder | Required fields | Optional | Canonical tool/resource | Approval/evidence | Clarification/failure | Reply owner |
|---|---|---|---|---|---|---|
| CreateTaskBuilder | title, identity scope | due date, assignee, notes, project | task create / Tasks | policy approval; verified write | missing title; invalid scope | handler/Gateway |
| UpdateTaskBuilder | stable reference + patch | title, due date, assignee, notes | task update / Tasks | approval; verified write | 0 or multiple matches | handler/Gateway |
| CompleteTaskBuilder | stable reference | completion note | task complete / Tasks | approval; completion evidence | unresolved reference | handler/Gateway |
| CreateLeadBuilder | identity scope + lead fields | phone, domain, source, notes | lead create / Leads | capture policy; write evidence | invalid/duplicate identity | handler/Gateway |
| UpdateLeadBuilder | stable lead reference + patch | status, notes, owner | lead update / Leads | approval; verified write | 0/multiple matches | handler/Gateway |
| ApprovalStatusBuilder | contract/reference or identity scope | limit, status filter | AC read / ActionContracts | no mutation; lifecycle evidence | no/multiple pending | Gateway |
| ExecutionStatusBuilder | contract/reference | execution attempt | execution read / claims/results | execution evidence only | unknown/outcome_unknown | Gateway |

All builders must reject positional payload ambiguity, require named canonical
fields, and never recover a missing canonical field by asking Agent text to
guess. ActionContracts remain lifecycle authority.
