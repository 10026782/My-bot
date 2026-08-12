# Attio — Reference Inspection

**Inspected:** 12/08/2026  
**URL:** https://attio.com/  
**Viewport:** browser default desktop; exact viewport not captured  
**Evidence:** `docs/ux/reference-evidence/attio/attio-home-viewport.png`

## Access and limits

`OBSERVED`: public Attio homepage rendered product demonstrations for CRM, pipeline and AI in the DOM. The saved screenshot captures the visible public header/hero viewport; the authenticated app was not opened. Live permissions and CRUD behavior are `NOT VERIFIED`.

## Observations

- `OBSERVED`: the public demonstration shows a company collection with visible company names, ICP scores and owners.
- `OBSERVED`: the demonstration exposes a pipeline question and an AI answer in the context of revenue work.
- `OBSERVED`: product messaging links pipeline, leads, deals and account growth rather than presenting isolated screens.
- `OBSERVED`: the platform navigation groups product and resource areas while keeping sign-in/start actions separate.
- `NOT VERIFIED`: actual record drawers, linked-record transitions, filters, sorting, mobile behavior and restricted actions.

## SCOREBOS mapping

| Pattern | Why it helps | Constitution mapping | Reuse classification |
|---|---|---|---|
| Collection with business fields and scores | Makes records comparable and actionable | DEC-UX-09, DEC-UX-10 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Lifecycle-oriented CRM framing | Supports connected business context | DEC-UX-11 | `USE AS COMPOSITION INSPIRATION` |
| Contextual AI answer against current work | Separates assistant from raw data | DEC-UX-14 | `MAP TO EXISTING SCOREBOS PATTERN` |

## Not verified

Authenticated Attio shell, exact entity detail behavior, permission states, action confirmations and responsive adaptation.
