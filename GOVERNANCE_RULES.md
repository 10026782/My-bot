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

---

## Lead Lifecycle System Rules (נוספו 28-29/06/2026 — Lead Lifecycle Stabilization session)

### RULE 19 — BUSINESS SUCCESS CANNOT BE OVERWRITTEN
Business success cannot be overwritten by audit/logging/post-processing failure.
Lead created/found = `business_success`. Metadata patch failed = warning בלבד.

### RULE 20 — FOUND ≠ CREATED
FOUND ≠ CREATED — `airtable_get` evidence cannot justify "created" claims.
`airtable_get` or `search_lead` = evidence for FOUND, not for CREATED.

### RULE 21 — LEAD CREATION OWNERSHIP
Lead creation is owned by `capture_inbound_lead` only.
Agent must not create Leads through raw `airtable_add`.

### RULE 22 — LEAD EVENT OWNERSHIP
Lead follow-up/event logging is owned by `capture_lead_event` only.
Existing lead + new message → always write a Lead Event.

### RULE 23 — NO PARTIAL LEADS VIA AGENT
Agent must not create partial Leads through raw `airtable_add`.
All Leads must go through `capture_inbound_lead` → identity → domain → score flow.

### RULE 24 — OUTPUT APPROVED ≠ MESSAGE DELIVERED
Output approved does not mean message delivered.
WhatsApp stub must remain honest: "not sent" until real delivery confirmed.

### RULE 25 — WHATSAPP STUB HONESTY
WhatsApp stub must remain honest: "not sent" until real delivery confirmed.
Do not claim delivery without actual API confirmation.

### RULE 26 — SCHEMA DRIFT = WARNING ONLY
Schema drift / metadata patch failure is warning unless it breaks core business result.
Unknown fields in Airtable PATCH = `logger.warning`, not exception.

### RULE 27 — SMALL PRS
Each fix goes in its own small PR.
No bundling of unrelated fixes to avoid masking regressions.
