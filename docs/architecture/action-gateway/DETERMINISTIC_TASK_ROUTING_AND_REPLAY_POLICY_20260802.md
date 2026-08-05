# Deterministic task routing and replay policy

**Date:** 02/08/2026
**Scope:** deterministic create-task routing, ActionGateway business identity,
pending delivery, and rejection replay.
**Explicitly out of scope:** Turn Coordinator implementation and its separate
documentation update.

## What changed

The deterministic create-task path normalizes sender prefixes, quoted messages,
reply wrappers, non-breaking spaces, and repeated whitespace before matching.
The parser extracts a task title and safely canonicalizes date and time values.

Certain requests remain Agent-free and are queued through the existing
ActionGateway approval boundary. Uncertain or malformed date/time input is
clarified instead: it does not invoke the Agent and does not create an
ActionContract. The parser does not silently correct spelling when meaning may
change.

## Canonical business identity

The business fingerprint uses an identity-only canonical payload:

```text
table: Tasks
fields:
  title: <parsed title>
  due_date: <ISO date, when present>
  due_time: <24-hour time, when present>
```

This identity is separate from the persisted Airtable payload. Time participates
in deduplication without adding an Airtable schema field. Equivalent whitespace,
wrapper, punctuation, and date/time formatting map to the same identity;
materially different title/date/time values map to a new identity.

## Rejection and replay semantics

PR #540 (merge `6779c03`, 02/08/2026) tightened rejected-action replay after
the earlier behavior had allowed a repeated explicit create request to produce
a new approval attempt. The intended business rule is narrower than the
current guard:

- autonomous or implicit replay of a rejected action remains blocked;
- an explicit new create request from the user may create a new approval
  attempt, while the previously rejected contract remains immutable;
- a materially changed title, date, or time is also a new business action.

The fingerprint remains the business identity. The explicit-retry policy needs
an attempt-level proposal path at the ActionGateway boundary; it must not be
implemented by changing the canonical payload or mutating the rejected record.
Until that policy fix is shipped, identical explicit requests remain blocked by
the current PR #540 guard. This document records the gap rather than claiming
the runtime already supports the intended retry behavior.

## Single-speaker pending delivery

`_queue_approval_detailed_impl()` remains responsible for the owner-visible
pending notification. When it successfully notified the same chat that invoked
the deterministic route, the coordinator return value is suppressed so the
webhook cannot send the same prompt a second time. If the target differs from
the requester chat, the returned message remains available to the requester.

The suppression is observable through:

```text
duplicate_reply_suppressed=true reason=owner_notification_already_sent
```

Approval authority, queue ownership, execution claims, terminal transitions,
and evidence authority are unchanged.

## Verification evidence

The 02/08/2026 staging log for the `9/8/26 19:00` request showed:

- `handler=tool` and `agent_calls=0`;
- a new `airtable_add` ActionContract with `status=pending`;
- one owner notification;
- `duplicate_reply_suppressed=true`;
- no direct write before approval.

Subsequent `יצירת המשימה כבר בוטלה` responses for the same canonical request
are consistent with terminal rejection replay protection. They are not proof
that the initial deterministic route failed. A separate rejection-turn log is
required to diagnose any duplicated terminal response at the transport layer.

## Validation status

- `git diff --check`: passed for the implementation branch.
- Targeted Python suites and `compileall`: not executable in the Windows session
  because `python3`/`py` returned `A specified logon session does not exist` and
  WSL returned access denied.
- Production or staging flag changes: none.
- `FEATURE_UNIFIED_STATUS_FORMATTER`: unchanged; no activation is claimed.
