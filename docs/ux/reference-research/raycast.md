# Raycast — Reference Inspection

**Inspected:** 12/08/2026  
**URL:** https://www.raycast.com/  
**Viewport:** browser default desktop; exact viewport not captured  
**Evidence:** `docs/ux/reference-evidence/raycast/raycast-home-viewport.png`

## Access and limits

`OBSERVED`: public Raycast homepage rendered its launcher metaphor and keyboard-first interaction story. The saved screenshot captures the visible public header/hero viewport; the installed desktop launcher was not tested. Actual command execution and permissions are `NOT VERIFIED`.

## Observations

- `OBSERVED`: the primary product promise is a fast, extendable launcher for tools and actions.
- `OBSERVED`: the page visibly communicates keyboard-first behavior and shortcut affordances.
- `OBSERVED`: extensions are organized by functional categories such as Productivity, Engineering, Design and Writing.
- `OBSERVED`: extensions expose direct verbs such as create/search/modify issues, control music, navigate tabs or retrieve credentials.
- `NOT VERIFIED`: command palette search ranking, keyboard navigation, action confirmation, error feedback and mobile behavior.

## SCOREBOS mapping

| Pattern | Why it helps | Constitution mapping | Reuse classification |
|---|---|---|---|
| Global command/quick action entry | Makes capabilities discoverable from anywhere | DEC-UX-06, DEC-UX-07 | `MAP TO EXISTING SCOREBOS PATTERN` |
| Verb-oriented action catalog | Organizes capabilities by user intent | DEC-UX-06 | `USE AS COMPOSITION INSPIRATION` |
| Keyboard-first speed model | Supports frequent operators without extra navigation | DEC-UX-02, DEC-UX-16 | `SYSTEM-LEVEL PATTERN CANDIDATE` |

The keyboard-first pattern is only a candidate because SCOREBOS is also a Telegram/WebView product and its input/device context differs.
