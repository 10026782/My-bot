# F52 PR 6 — approval_pending Shadow Coverage + EvidenceFinalizer Plumbing

Program: F52 — Unified Approval Runtime Migration and Implementation
UX source of truth: `docs/architecture/f52-unified-approval-runtime/spec/UNIFIED_MESSAGE_UX_STANDARD.md`
Status: **verification only — no runtime behavior change, no flag turned on.**

## Why this PR exists

A third F52 gap in a row, found the same way PR4 and PR5 were: a real
production log.

```
A32 suppressed agent action-status text after approval was already queued.
ownership_signal:
  tool_use_emitted=true
  approval_queued=true
  agent_claimed_approval=false
  reply_owner=agent
EvidenceFinalizerShadow:
  evidence_status=approval_pending
  approvals_pending=1
  response_claim=empty
  mismatch=true
User-visible/owner-visible approval prompt was still sent:
  ⏳ בקשת אישור
  ➕ הוסף ל-Tasks...
  ID: ... | פג תוקף בעוד 10 דקות
No UnifiedStatusFormatterShadow was emitted.
```

Three compounding, independently-real gaps, all in the approval-pending
surface PR4/PR5 never covered:

1. **No formatter coverage at all.** `app.py`'s
   `_queue_approval_detailed_impl()` sends its own hardcoded
   `"⏳ בקשת אישור..."` text directly via `bot.send_message()` — never
   through `ActionGateway.compose_status_reply()`/`ActionFact`. The exact
   same shape of gap PR5 closed for rejections, now found on the
   pending-notification surface instead.
2. **A false EvidenceFinalizer mismatch.** A32's Single-Speaker gate
   (`sanitize_agent_response()`) correctly returns `""` for the agent's own
   text once a real approval was already queued this turn — the *real*
   message went out through the side channel in (1), not through
   `final_reply`. But `core.turn_evidence._classify_response_claim()` read
   any empty `final_text` as `"empty"` unconditionally, so
   `EvidenceFinalizerShadow` reported `response_claim=empty` against
   `evidence_status=approval_pending` — a mismatch that was never real.
3. **A stale ownership label.** `core.turn_envelope.build_ownership_signal()`
   already accepts a `reply_owner` override, but app.py's one call site never
   passed one, so it silently kept the function's own default (`"agent"`)
   even when a real approval was queued and the agent's own text was
   suppressed — contradicting `agent_claimed_approval=false` and
   `approval_queued=true` right next to it in the same log line.

## What this PR does

### 1. `core/action_gateway.py` — `_render_pending_prompt()`

A new `ActionGateway._render_pending_prompt(tool_name, contract_id,
legacy_text)`, applying the **exact same** off/shadow/on machinery PR4/PR5
already built:

- `off` (default): returns `legacy_text` unchanged, byte-identical.
- `shadow`: computes the unified text via the same
  `_compose_status_reply_unified()`/`_action_fact_to_message()` PR4 uses
  (an `ActionFact(outcome="pending", ...)` — `"pending"` was already a
  documented valid `ActionFact.outcome`, and `_action_fact_to_message()`
  already mapped it to the `"approval_pending"` canonical state; neither was
  ever modified, only finally exercised from a real call site), logs the
  same `[UnifiedStatusFormatterShadow]` safe-comparison record via the same,
  unmodified `_log_shadow_comparison()`/`_shadow_leak_flags()`, and still
  returns `legacy_text`.
- `on`: returns the unified text instead.

Wired into the single place the approval-pending prompt is actually built
and sent — `app.py`'s `_queue_approval_detailed_impl()`, immediately before
`bot.send_message()`. `contract_id` may be `None` (e.g. shadow-mode
`propose_action()` raised before returning one); `_action_fact_to_message()`
already handles a missing/unfound contract by falling back to an empty
`human_summary`, the same as every other outcome — this PR adds no new
fallback logic.

### 2. `core/turn_evidence.py` — `approval_prompt_sent`

`_classify_response_claim()`, `compare_shadow_final_status()`, and
`observe_shadow_finalizer()` all gain an `approval_prompt_sent: bool = False`
parameter. When `final_text` is empty **and** `approval_prompt_sent=True`,
the response claim is now `"sent_for_approval"` instead of `"empty"` — and
`"sent_for_approval"` is treated as compatible with (not a mismatch against)
`evidence_status="approval_pending"`. Compatibility is scoped specifically
to that one status: an empty text with `approval_prompt_sent=True` alongside
a **failure** evidence status (or any other) is still correctly flagged as a
mismatch — this does not become a blanket "empty is fine" exemption.

`approval_prompt_sent` defaults to `False` — any existing caller that
doesn't pass it gets byte-identical pre-PR6 behavior.

### 3. `app.py` — `owner_notified` proof + wiring

- `_queue_approval_detailed_impl()`'s return dict gains an `owner_notified`
  key, set `True` **only** on the one branch where `bot.send_message()`
  actually succeeded — proven, not assumed, mirroring this function's
  existing `created_this_turn`/`terminal_outcome` rigor. Every other
  (error/early-return) branch simply omits the key; callers read it via
  `.get("owner_notified", False)`, which is correctly `False` for all of
  them.
- The tool loop's `__approval_queued__` `tool_results_log` entry now carries
  `owner_notified` through from that dict.
- `run_agent()` computes `_approval_prompt_sent_this_turn` (`True` only if
  a `__approval_queued__` entry this turn has `owner_notified=True` —
  deliberately **not** inferred from `turn_evidence.approvals_pending`
  alone, since a deferred batch item, `__approval_deferred_batch__`, also
  counts as `approval_pending` evidence but never sends the owner a direct
  notification) and passes it into `observe_shadow_finalizer()`.
- The one `build_ownership_signal()` call site now passes
  `reply_owner="gateway" if _approval_queued_this_turn else "agent"` — the
  same `"gateway"` label `build_turn_envelope()` already uses elsewhere for
  this exact situation (`live_contract_reply_owner="gateway"`), no new
  vocabulary introduced. Scoped strictly to the approval-queued case — a
  plain conversational turn with no approval queued still reports
  `reply_owner="agent"` unchanged (see Test 5 below).

### 4. Follow-up (same PR, production-validated) — the "mixed" read+pending gap

After the above shipped, production shadow logs confirmed the fix (a real
`[UnifiedStatusFormatterShadow] outcome=pending mapped_state=approval_pending`
line, `reply_owner=gateway`, and `response_claim=sent_for_approval` all
observed live) — but also surfaced one more real case: a turn that ALSO
performs a verified read (e.g. an `airtable_get` lookup) before queuing the
approval classifies as `evidence_status="mixed"`
(`TurnEvidenceSummary.classification()`'s own first "mixed" branch:
`verified_reads>0 AND approvals_pending>0`), not `"approval_pending"` — so
the Section 2 fix above still reported a false mismatch for that turn shape:

```
[EvidenceFinalizerShadow] evidence_status=mixed response_claim=sent_for_approval
mismatch=true code=status_claim_mismatch counts={'verified_reads': 1, 'approvals_pending': 1, ...}
```

`compare_shadow_final_status()`'s compatibility check is narrowly widened
once more: `"sent_for_approval"` is now ALSO compatible with
`status == "mixed"` specifically when the only "non-success" contributor to
that mix is `approvals_pending` itself — zero `failed_calls`, zero
`unverified_effects`, zero `outcome_unknown`. A mixed turn that also carries
a genuine failure or an unverified/unknown effect is deliberately **not**
covered by this widening — those still need their own claim in the text,
and `"sent_for_approval"` alone would incorrectly hide them.

## What this PR does NOT do

- Does not touch BUG-111 lead parsing (`core/ingress_classifier.py`,
  `core/lead_candidate_handler.py`) or BUG-112's TTL enforcement.
- Does not change `FEATURE_UNIFIED_STATUS_FORMATTER`'s default (`off`) or
  set it to `shadow`/`on` anywhere.
- Does not change A32's actual suppression decision — `sanitize_agent_response()`
  still returns `""` for the agent's own text in this exact scenario; this
  PR only makes `EvidenceFinalizerShadow` correctly interpret that
  already-correct empty string, and correctly labels who actually replied.
- Does not add a new canonical formatter state — `"pending"` → `"approval_pending"`
  was already wired in `_action_fact_to_message()`, unmodified here.

## Shadow log fields

Same shape PR4/PR5 already established. For a pending prompt:

```
[UnifiedStatusFormatterShadow] outcome=pending mapped_state=approval_pending text_differs=True record_id_leak=False tool_name_leak=False contract_id_leak=False redaction_count=1 fallback_used=False formatter_version=1 legacy_len=90 unified_len=44
```

No raw record id, tool name, contract id, or free-form user text is ever
logged — only the same booleans/counts/state-names PR4/PR5's fields already
guarantee.

## EvidenceFinalizerShadow, before vs. after

Before this PR (the exact production finding):

```
[EvidenceFinalizerShadow] state=shadow evidence_status=approval_pending response_claim=empty mismatch=true code=status_claim_mismatch counts={...}
```

After:

```
[EvidenceFinalizerShadow] state=shadow evidence_status=approval_pending response_claim=sent_for_approval mismatch=false code=match counts={...}
```

## Recommended next operator action

Same as PR4/PR5: **shadow only**. Do not set
`FEATURE_UNIFIED_STATUS_FORMATTER=on` as a result of this PR. Once shadow is
enabled for the approval-pending surface, it now also produces comparison
samples for the pending-prompt notification — no separate flag exists for
this surface; it shares `FEATURE_UNIFIED_STATUS_FORMATTER` with PR4/PR5.
`FEATURE_EVIDENCE_FINALIZER=shadow` similarly now sees a correctly-classified
`approval_pending` turn instead of a false mismatch.

## Tests

`test_f52_pr6_pending_shadow.py` (55 checks):

- **Section 1** — `_render_pending_prompt()` off/shadow/on (mirrors PR4/PR5's
  own pattern): legacy text byte-identical when off, exactly one safe
  comparison line when shadow (`outcome=pending`, `mapped_state=approval_pending`,
  all leak flags `False`, `fallback_used=False`), non-empty differing unified
  text with no leaked identifiers when on, and a `contract_id=None` case that
  degrades cleanly instead of raising.
- **Section 2** — `core.turn_evidence`: reproduces the exact reported bug at
  the unit level (empty text + `approval_pending` evidence without the fix
  → `response_claim=empty`, `mismatch=True`), proves the fix
  (`approval_prompt_sent=True` → `response_claim=sent_for_approval`,
  `mismatch=False`), proves the compatibility is scoped to
  `approval_pending` only (a genuine `failure` evidence status is still
  flagged as a mismatch even with `approval_prompt_sent=True`), confirms
  `observe_shadow_finalizer()` never mutates `final_text`, and (the
  production-validated follow-up) proves the `"mixed"` read+pending
  widening: compatible when the mix is verified-read + approvals_pending
  only, still a mismatch when a genuine failure or unverified effect is
  also mixed in.
- **Section 3** — A32 regression: `sanitize_agent_response()`'s
  Single-Speaker suppression is explicitly unchanged (still returns `""` for
  gateway-active + pending-status text + real `__approval_queued__`
  evidence).
- **Section 4** — end-to-end via the real `run_agent()` (Identity/Router/
  Anthropic mocked, `bot.send_message` mocked): a `create_task` tool call
  that queues an approval, at flag off and flag shadow, verifying: the owner
  is notified exactly once with the byte-identical legacy prompt in *both*
  states (shadow never changes what's actually sent), a
  `[UnifiedStatusFormatterShadow]` line appears only in shadow mode,
  `final_reply` is still suppressed to `""` by A32 (unchanged), the
  `ownership_signal` reports `reply_owner="gateway"` and
  `agent_claimed_approval=False` (exactly matching the production report),
  and `EvidenceFinalizerShadow` now reports `response_claim=sent_for_approval`
  / `mismatch=False` instead of the old false mismatch.
- **Section 5** — regression: a plain conversational turn with no approval
  queued keeps `reply_owner="agent"` — the fix is scoped, not a blanket
  relabel.
- **Section 6** — regression: `FEATURE_UNIFIED_STATUS_FORMATTER`/
  `FEATURE_EVIDENCE_FINALIZER` still default to `off`; `core.ingress_classifier`
  (BUG-111's live path) unchanged.

Full `test_*.py` regression sweep (145+ files) passes with zero failures;
`smoke_tests.py`, `python3 -m compileall`, and `git diff --check` all pass
clean.
