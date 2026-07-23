# TurnCoordinator Phase 0 — Log Observation (23/07/2026)

**Status:** observation only. No runtime, routing, reply, approval, or flag change. Cross-Layer Authority Contract gate (`docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`) not triggered — this reads existing Phase-0 `[TurnEnvelope]` log lines only (`core/turn_envelope.py`, confirmed log-only/no-side-effects per `PHASE_2_SHADOW_PLANNING_GATE.md` §1.2); no Phase 2 Shadow Decision code exists yet to observe beyond that.
**Correction from this doc's first draft:** first pass only queried `srv-d80ehsf7f7vs73cq5rn0` (production), which had zero real chat traffic today. Today's actual TurnCoordinator-relevant activity is on staging — `my-bot-approval-staging`, `srv-d99uq63eo5us73967cj0` (owner-confirmed against the Render dashboard URL). See `RP5_LOG_OBSERVATION_23JUL2026.md` for how that service id was resolved.
**Method:** `scripts/render_log_export.py export --marker "[TurnEnvelope]" --catch-up-days 1 --ssl-no-revoke --export-dir render_logs/staging_turn_coordinator`, service `srv-d99uq63eo5us73967cj0`, window `2026-07-22T20:54Z → 2026-07-23T20:54Z`. 63 entries, `render_logs/staging_turn_coordinator/srv-d99uq63eo5us73967cj0/2026-07-23.jsonl` (gitignored, not committed).

## 1. Real activity today: 63 lines, two sessions, single test user

All 63 lines are from one fingerprinted user (`b2320d31`), across two clusters: `10:15–10:17Z` and `13:10–19:27Z`. Breakdown by line type:

| line type | count |
|---|---|
| `turn_mode=approval_pending` | 28 |
| `ownership_signal` | 15 |
| `turn_mode=free_agent` | 11 |
| `case_c_signal` (kind=C1) | 9 |

## 2. Headline finding: sustained pending-approval backlog for one user, all day — now identified as the exact session `docs/architecture/action-gateway/STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md` analyzes

28 of 63 turns (44%) carried `"turn_mode": "approval_pending", "queue_sources": ["action_gateway"], "multi_contract_conflict": true`. The accompanying `case_c_signal kind=C1 detail=live_contracts=N` lines show the backlog shrinking slowly across the day rather than clearing:

- `10:15:35Z` → `live_contracts=7`
- ...
- `19:27:34Z` → `live_contracts=3`

Never zero, never spiking back up sharply — a slow, partial drain over ~9 hours.

**Identified, not just "consistent with":** `STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md` §1.1 documents the owner's real `ActionContracts` export for "the 7-contract batch," with a disambiguation moment derived at **2026-07-23 13:16:03 Israel time = 10:16:03 UTC** — inside this session's very first cluster, one second after this report's own `live_contracts=7` reading at `10:15:35Z`. This is the same event, not a separately-inferred pattern:
- **Finding #1** (🟡 partially fixed): `ExecutionLedger.find_live_by_user()` skipped `_is_expired()`/`CONTRACT_PENDING_TTL_SECONDS` entirely on the warm-cache path — a contract could stay "live" forever once cached, regardless of the 24h TTL. Fixed for the warm/cold-path inconsistency itself; the TTL *window* question for this interactive flow (as opposed to TMA's 24h) is still an open owner decision.
- **Finding #2** (documented, not implemented): the sibling-auto-reject-on-pick behavior (§21, `route_disambiguation()`) is why picking any one of the 7 contracts silently rejected the others — by design for same-turn alternative interpretations, but firing here on independent contracts accumulated over hours because of Finding #1's gap.
- **Findings #5/#6** (confirmed pre-fix artifacts, not live gaps): two of the 7 (`ac30218d` "זיהיתי", 37.9h old; `02ad21bc` "תמחק איש קשר", 27.4h old) were BUG-129/BUG-135 residue predating fix commit `9285106` — both would be hidden today by Finding #1's fix. The contract that *did* execute (`7fed5be6`, "איש קשר דני לוי", 14.65h old) is inside the 24h TTL either way — its silent execution on an unrelated disambiguation pick is exactly what motivated Finding #1's age-warning display addition.

So the already-registered bugs this report previously cited — **BUG-130** and **BUG-134** — remain correctly flagged as *related*, but the audit doc's Finding #1 is the more precise, now-partially-fixed root cause for the specific backlog observed here; BUG-134 (the generic `ActionContractRepository` TTL racing C84's TMA-specific reject+sync) is a distinct, still-fully-open bug on a different code path (TMA sync, not `find_live_by_user()`'s warm-cache read), not the same defect as Finding #1.

Per the audit doc's own closing line: **"Fix not yet production-verified"** — Finding #1's code fix landed, but hasn't been observed running against live traffic yet. This report's data predates that fix being live (or at least doesn't confirm it), so it can't yet say whether the drain pattern (7→3 over 9h) would look different post-fix.

## 2.1 Second cluster (13:10–19:27Z) — likely the Finding #8/#9 (scenarios 26/27) sample

The audit doc's Findings #8/#9 (new, discovered from "a second, independent staging sample after PR #449/#450 merged," documented as TurnCoordinator Acceptance Corpus **scenarios 26 and 27**) describe **"an entire 4-task `ActionContract` batch-approval flow (Tier 1)"** — a stale Tier-2 batch preview surviving it (#8) and completion/next-item messages arriving out of order (#9).

This report's own `[Approval]` export (see `RP5_LOG_OBSERVATION_23JUL2026.md` §3) shows exactly a 4-item batch: `queued {action_id} | airtable_add | user=2baafc9c` × 4 at `13:17:07Z, 13:18:35Z, 13:19:04Z, 13:19:20Z`, and this report's own `[TurnEnvelope]` data has a matching `approval_pending` reading at `13:17:11Z` with `approvals_pending=4` (from the RP5 report's `[EvidenceFinalizerShadow]` export, same timestamp). The count, the tool (`airtable_add`, task-shaped), and the timing all match "4-task ActionContract batch-approval flow" closely enough that this is very likely the same sample #8/#9 were built from — though the audit doc's excerpt read here doesn't give exact UTC timestamps to confirm 1:1, so this is a strong correlation, not a proven identity.

Neither #8 nor #9 is implemented (both explicitly deferred to TurnCoordinator's own send-gateway/reconfirmation-gate work, per the audit doc's §1 reasoning) — this report doesn't add new diagnostic value beyond confirming the raw batch-approval traffic shape lines up.

## 3. `ownership_signal` samples — who actually replies

Two representative lines from the end of the session:
```
19:27:30Z ownership_signal {"recognized_intent": "smalltalk", "selected_handler": "agent", "tool_use_emitted": false, "approval_queued": false, "agent_claimed_approval": false, "reply_owner": "agent", "final_reply_nonempty": true}
19:27:36Z ownership_signal {"recognized_intent": "unknown", "selected_handler": "agent", "tool_use_emitted": false, "approval_queued": false, "agent_claimed_approval": false, "reply_owner": "agent", "final_reply_nonempty": true}
```
Both are plain free-agent replies with no tool/approval involvement — unremarkable, included here only as a content sample of what `ownership_signal` actually captures in practice, for whoever eventually builds the Phase 2 comparison logic against it.

## 4. What this does and doesn't tell us about Phase 2 planning

`PHASE_2_SHADOW_PLANNING_GATE.md` (§9, §13) documents the *design* for a Shadow Decision Coordinator (`ShadowDecisionRecord`, `coordinator_selected_handler`, etc.) — none of that is implemented yet (`core/turn_coordinator_shadow.py` doesn't exist, per that doc's own §11 scope note). So today's data is pure Phase-0 observation, not a Phase-2 comparison. It is, however, a genuinely useful real-world sample of the exact `multi_contract_conflict`/Case-C scenario family §9 of that doc discusses in the abstract — worth pulling into that document's scenario catalogue (it already has "scenarios 26-27 from a second staging production sample" per today's `9a1202a`/`22ee744` merge, so this would be additive, not duplicate).

## 5. Cross-reference

- `RP5_LOG_OBSERVATION_23JUL2026.md` (this session, same staging service, same day) — 47% mismatch rate in `[EvidenceFinalizerShadow]` samples, most concentrated in a separate no-tool-call/false-failure-claim pattern (now filed as BUG-139). Both reports draw from the same underlying staging session; read together for the fuller picture.
- `docs/architecture/action-gateway/STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md` (PR #449, 23/07/2026) — the deep, code-level forensic analysis of the same staging session this report observed at the raw-log level (§2, §2.1 above). That doc is authoritative on root cause, fix status, and the Cross-Layer Impact Matrix; this report only confirms the raw `TurnEnvelope`/`Approval` signal matches its timeline.

## 6. Recommendation

No new code action indicated beyond what the audit doc already covers (Finding #1 partially fixed, #2/#6/#7/#8/#9 explicitly deferred to TurnCoordinator's own approval, per its §1/§3/§4). Two things worth flagging to the owner:
1. The 9-hour, only-partially-clearing pending-queue backlog (§2) is now explained, not just observed — it's Finding #1's warm-cache TTL gap, whose fix has landed in code but is explicitly **not yet production-verified** (audit doc §"Fix not yet production-verified"). A follow-up log pull after that fix is confirmed deployed to staging would show whether the drain pattern changes.
2. Ruled out as a fault-injection artifact — see `RP5_LOG_OBSERVATION_23JUL2026.md` §2: zero `[RP5FaultInjection]` events fired on this service today, so both this backlog and RP5's mismatch pattern are organic, not injected.
