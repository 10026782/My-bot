# Linear — Reference Inspection

**Inspected:** 12/08/2026  
**URL:** https://linear.app/  
**Viewport:** browser default desktop; exact viewport not captured  
**Evidence:** `docs/ux/reference-evidence/linear/linear-home-viewport.png`

## Access and limits

`OBSERVED`: public Linear homepage rendered and included a product UI demonstration in the DOM. The saved screenshot captures only the visible public header/hero viewport; the embedded product demonstration is DOM evidence, not a full app screenshot. The live authenticated workspace was not opened. Product behavior such as real keyboard shortcuts, permissions, loading and mobile behavior is `NOT VERIFIED`.

## Observations

- `OBSERVED`: the demonstrated shell has a compact left navigation with Search workspace, New issue, Inbox, My issues, Reviews, Pulse, Workspace, Initiatives, Projects and More.
- `OBSERVED`: the issue surface combines title, status, priority, owner, labels, activity and an AI/chat context in one entity detail.
- `OBSERVED`: the entity presents activity as a chronological stream, with related work and status changes visible without leaving the issue.
- `OBSERVED`: a command/search entry and a global New issue action are first-class shell actions.
- `NOT VERIFIED`: actual responsive adaptation, hover/focus states, permission states and authenticated empty/loading/error states.

## SCOREBOS mapping

| Pattern | Why it helps | Constitution mapping | Reuse classification |
|---|---|---|---|
| Compact shell with global search/create | Reduces navigation cost for frequent work | DEC-UX-02, DEC-UX-06 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Entity detail + activity + next action context | Preserves lifecycle continuity | DEC-UX-09, DEC-UX-11 | `MAP TO EXISTING SCOREBOS PATTERN` |
| AI alongside current entity | Keeps assistance contextual | DEC-UX-14 | `USE AS COMPOSITION INSPIRATION` |

## Not verified

Exact CSS measurements, mobile Linear app, real command palette behavior, permissions and runtime feedback.
