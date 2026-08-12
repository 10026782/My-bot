# Attio — Reference Inspection

**Inspected:** 13/08/2026  
**URL:** https://attio.com/  
**Viewport:** browser default desktop plus 390x844 public responsive pass  
**Evidence:** `docs/ux/reference-evidence/attio/attio-home-viewport.png`

## Access and limits

`OBSERVED`: public Attio homepage rendered product demonstrations for CRM, pipeline, meetings/transcript and AI in the DOM. A 390x844 public responsive pass also rendered the same public product examples. The authenticated app was not opened. Live permissions and CRUD behavior are `NOT VERIFIED`.

## Observations

- `OBSERVED`: the public demonstration shows a company collection with visible company names, ICP scores and owners.
- `OBSERVED`: the demonstration exposes a pipeline question and an AI answer in the context of revenue work.
- `OBSERVED`: product messaging links pipeline, leads, deals and account growth rather than presenting isolated screens.
- `OBSERVED`: the platform navigation groups product and resource areas while keeping sign-in/start actions separate.
- `OBSERVED`: the public demo exposes a Home state with tasks, notes, calls, reports, automations, sequences, workflows, favorites and People/Companies records.
- `OBSERVED`: the public demo exposes a meeting detail/transcript state with participants, speakers, timestamps and follow-up context.
- `OBSERVED`: the public demo exposes a pipeline/attention state with stages, deal values, owners, next-step prompts and risk/forecast framing.
- `OBSERVED`: the public 390x844 responsive pass retains the same public Home, records, meetings/transcript, pipeline and AI/action-entry content in the rendered DOM.
- `NOT VERIFIED`: actual record drawers, linked-record transitions, filters, sorting, mobile behavior and restricted actions.

## SCOREBOS mapping

| Pattern | Why it helps | Constitution mapping | Reuse classification |
|---|---|---|---|
| Collection with business fields and scores | Makes records comparable and actionable | DEC-UX-09, DEC-UX-10 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Lifecycle-oriented CRM framing | Supports connected business context | DEC-UX-11 | `USE AS COMPOSITION INSPIRATION` |
| Contextual AI answer against current work | Separates assistant from raw data | DEC-UX-14 | `MAP TO EXISTING SCOREBOS PATTERN` |

## Not verified

Authenticated Attio shell, exact authenticated entity detail behavior, permission states, action confirmations and native mobile behavior.
