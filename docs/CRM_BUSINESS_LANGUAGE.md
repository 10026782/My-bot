# Canonical CRM Business Language

**Status:** documentation-only SSOT  
**Scope:** CRM entity semantics and lifecycle relationships  
**Authority:** existing lifecycle audit findings and current business decision documents

This document freezes the business meaning of the CRM entities. It does not add
runtime gates, change schema, or make a missing writer a lifecycle defect.

## Canonical entities

### Lead

**Lead = opportunity intake / inbound prospect.**

A Lead is an initial opportunity entering the funnel. It is not yet the
canonical Person/Organization identity. It carries intake data, source,
qualification, status, score, follow-up, and related funnel state.

The existing Leads audit remains authoritative for Lead fields and conversion
status semantics; this document does not re-audit or replace that audit.

### Contact

**Contact = canonical Person / Organization identity.**

A Contact is the canonical relationship registry/rolodex entry for the person
or organization itself. A Contact may exist without a Deal and without a
Payment. A Contact is not a Deal and is not a financial stage.

Current code creates or reuses Contacts through the canonical deduplication gate
`find_or_create_contact()` / `crm_add_contact()` ([`crm.py`](../crm.py:228)).

### Deal

**Deal = specific commercial opportunity / engagement / transaction context.**

A Deal represents a concrete business engagement. It is separate from the
Contact identity. One Contact may be related to multiple Deals; the existence
of a Contact does not imply that a Deal exists.

The documented business layer treats Leads, Contacts, Deals, and Payments as
separate entities ([`BOSS_UNIFIED_MASTER_PLAN_v2.md`](../archive/BOSS_UNIFIED_MASTER_PLAN_v2.md:237)).

### Payment

**Payment = transaction / financial obligation or receipt.**

A Payment represents a payment, charge, or financial commitment. Its canonical
business relationship is the Deal. Payment is not a lifecycle stage of a
Contact.

Current code creates Payments explicitly through `crm_add_payment()` and links
them to a Deal when `deal_id` is supplied ([`crm.py`](../crm.py:417)). Deal
creation does not create a Payment automatically.

### Task

**Task = required action / next action.**

A Task is work that must be performed. It is an action record, not an identity,
commercial engagement, or financial record.

### Interaction

**Interaction = historical event / communication / activity record.**

An Interaction records something that happened: communication, activity, or
another historical event. It is not itself a Contact, Deal, or Payment.

## Canonical relationships

### Lead → Contact

Lead → Contact is an explicit conversion of a Lead that has entered active CRM
handling.

Current behavior is an explicit owner/admin action through `/convert`:

1. `convert_lead_to_contact()` calls `crm_add_contact()` with the Lead ID as
   `lead_source_id`.
2. The Contact is created or found and receives `Origin Lead`.
3. The Lead is then marked converted using the canonical Lead conversion
   fields.

Evidence: [`app.py`](../app.py:682),
[`lead_conversion.py`](../lead_conversion.py:67), and
[`lead_conversion.py`](../lead_conversion.py:97).

There is currently no deterministic canonical readiness gate. Do not assume
that a particular score, status, tier, reply, meeting, or other field
automatically requires conversion.

### Contact → Deal

Contact → Deal is not an automatic conversion.

A Deal is created explicitly when there is business context that justifies a
specific commercial engagement. Current code permits explicit Deal creation
with an optional Contact link, but does not enforce a business-readiness gate
or require a prior Contact status ([`crm.py`](../crm.py:325)).

Therefore:

- explicit creation is supported;
- automatic creation is not supported;
- business-readiness enforcement is not currently implemented.

### Lead → Deal

Lead → Deal is not a mandatory canonical lifecycle transition.

`Deal.Origin Lead` is **provenance / attribution / traceability**, not a
required lifecycle edge. The business decision language uses the existing
`Origin Lead` backlink for source-to-revenue attribution:

`source → leads → hot leads → deals → revenue`

([`BOSS_UNIFIED_MASTER_PLAN_v2.md`](../archive/BOSS_UNIFIED_MASTER_PLAN_v2.md:454)).

The absence of a Lead-to-Deal writer is therefore an optional traceability gap,
not by itself a lifecycle bug. A future requirement for mandatory Lead
provenance would require a new business decision.

### Deal → Payment

Deal → Payment is the canonical financial relationship.

Payment creation is explicit. Creating a Deal does not automatically create a
Payment. The canonical conceptual path for identifying the person or
organization associated with a Payment is:

`Payment → Deal → Contact`

`Payment.Contact` is not currently a canonical business requirement. A direct
Payment-to-Contact link would be a redundant denormalization unless a future
decision establishes a separate payment-party concept.

## What must not be assumed

Without a new business decision, do not assume:

- Every Lead must become a Deal.
- Every Contact must have a Deal.
- Every Deal must originate from a Lead.
- Every Contact must originate from a Lead.
- Every Deal automatically creates a Payment.
- A Payment must directly link to a Contact.
- Lead score automatically determines conversion.
- Contact is equivalent to Deal.

## Historical terminology

Historical terminology is not authoritative.

Older planning material included a broader CRM data-program concept and
references to a unified stage vocabulary. The current audit records that the
implemented model instead has distinct Lead, Contact, and Deal semantics, with
independent status/stage vocabularies ([`C95A_ARCHIVE_CARRY_FORWARD_GAP_REPORT.md`](audit/C95A_ARCHIVE_CARRY_FORWARD_GAP_REPORT.md:147)).

Any older use of Contacts or another entity with a different stage-oriented
meaning is a historical note only. It does not change the current canonical
meaning defined here.

## Non-goals

This SSOT does not:

- change code or Airtable schema;
- introduce a Lead-to-Deal writer;
- add a Contact-to-Deal readiness gate;
- make `deal_id` mandatory for Payments;
- re-define Lead fields or replace the existing Leads audit;
- define a single shared status vocabulary across entities.
