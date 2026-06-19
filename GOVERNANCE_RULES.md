# GOVERNANCE ADDITIONS — June 2026

## RULE 13 — MAIN IS REALITY

All audits, status reports, recommendations, and executive summaries must be based on:

- main branch
- deployed production state

Unless explicitly marked otherwise.

Branches, sandboxes, experiments, and local work are not considered system reality.

---

## RULE 14 — AUDIT CANNOT MODIFY

Audit processes may:

- inspect
- verify
- compare
- report

Audit processes may not:

- create branches
- modify code
- create fixes
- open PRs automatically

Audit and implementation must remain separate responsibilities.

---

## RULE 15 — NO CLAIM WITHOUT VERIFICATION

The following words require evidence:

- fixed
- resolved
- deployed
- completed
- working

Required verification:

1. merged to main
2. deployment completed
3. production verification passed

Without verification, status must be reported as:

"Implemented but not yet verified."

---

## RULE 16 — ROOT CAUSE BEFORE FIX

No fix may be implemented before:

- reproduction
- evidence
- root cause identification

Patch-first behavior is prohibited.

---

## RULE 17 — SINGLE SOURCE OF STATUS

System status must have one authoritative source.

Conflicting status documents are not permitted.

ROADMAP, CURRENT_STATE, audits and reports must remain synchronized.

---

## RULE 18 — FIX THE PROCESS, NOT ONLY THE INCIDENT

Any incident that occurs more than once must trigger:

- process review
- guard evaluation
- prevention mechanism

The goal is prevention, not repeated recovery.
