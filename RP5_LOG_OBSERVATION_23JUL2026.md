# RP5 — Production/Staging Log Observation (23/07/2026)

**Status:** data-collection checkpoint only. No code, schema, flag, or runtime change in this document.
**Source of truth:** `RP5_PREFLIGHT_BLOCKER.md` (blocker/decisions), `BOSS_AGENT_RELIABILITY_AND_PERMISSION_HARDENING_SPEC.md` §4 R4/R5, `docs/architecture/action-gateway/STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md` (PR #449 — the code-level forensic analysis of this same staging session; §3 below identifies the overlap).
**Correction from this doc's first draft:** the first pass exported only `srv-d80ehsf7f7vs73cq5rn0` (`My-bot`, production), which genuinely had zero real chat traffic today (see §4). The owner pointed out today's actual test activity was on **staging** — `my-bot-approval-staging`, service id `srv-d99uq63eo5us73967cj0` (confirmed against `https://dashboard.render.com/web/srv-d99uq63eo5us73967cj0`). That service id wasn't recorded anywhere in the repo (`PHASE_2_SHADOW_PLANNING_GATE.md` §6.2 explicitly flags it as an unresolved unknown), so it was resolved here via a read-only `GET /v1/services` call against Render's API (same API key, same GET-only/no-mutation posture as `scripts/render_log_export.py`; not itself run through that script since it only supports `/v1/logs`).
**Method:** `scripts/render_log_export.py export --owner-id tea-d804tr8sfn5c7398geag --service-id srv-d99uq63eo5us73967cj0 --marker "[EvidenceFinalizerShadow]" --catch-up-days 1 --ssl-no-revoke --export-dir render_logs/staging_rp5`. Window `2026-07-22T20:54Z → 2026-07-23T20:54Z`. Raw export: `render_logs/staging_rp5/srv-d99uq63eo5us73967cj0/2026-07-23.jsonl` (`.gitignore`d, not committed).

## 1. Sample coverage today: 15 real `[EvidenceFinalizerShadow]` lines, 5 of 9 states, 47% mismatch rate

| evidence_status | response_claim | mismatch | count |
|---|---|---|---|
| no_evidence | neutral | false | 5 |
| no_evidence | **failure** | **true** | **5** |
| no_evidence | mixed | true | 1 |
| mixed | neutral | true | 1 |
| approval_pending | sent_for_approval | false | 1 |
| failure | failure | false | 1 |
| verified_read_only | neutral | false | 1 |

States **not** observed today: `verified_write_success`, `outcome_unknown`, `unverified_effect`, `mixed_with_unknown`.

## 2. Headline finding: a repeating, reproducible false-failure-claim pattern

**5 of 15 samples (33%) are `evidence_status=no_evidence` paired with `response_claim=failure`** — the bot's own text response claimed something failed, while the evidence layer found **zero tool calls at all** in that turn. Per `RP5_PREFLIGHT_BLOCKER.md` §3's own table: *"`no_evidence` — `response_claim` is `empty` or `neutral` — any other claim is a false-evidence bug."* This is exactly that bug class, and it recurred across two separate sessions today, not once:
- `13:10:39Z`, `13:10:55Z`, `13:15:25Z` (one cluster)
- `19:21:38Z`, `19:22:06Z` (a second, later cluster — same pattern, different session)

A 6th related mismatch (`13:16:06Z`, `no_evidence → response_claim=mixed`) and a 7th (`10:17:02Z`, `evidence_status=mixed → response_claim=neutral`, i.e. a turn with 1 verified read + 1 failed call reported back as plain "neutral") round out 7/15 mismatches total.

**Ruled out — not a fault-injection artifact.** The initial hypothesis was that this staging service's fault-injection helper (`claude/rp5-staging-fault-injection-v4akit`, `core/rp5_fault_injection.py`) might be producing these mismatches deliberately. Checked directly: that code logs an unambiguous `[RP5FaultInjection] scenario=... user=... tool=...` line every time it actually intercepts a tool call. A same-window export of that exact marker against this same staging service returned **0 entries** — no fault-injection event fired today. Structurally this also couldn't have produced this pattern anyway: the helper only intercepts a tool call already in flight, so it can never be the cause of `evidence_status=no_evidence` (which means zero tool calls happened that turn — nothing for it to intercept). The mismatch is therefore a real, unexplained pattern — not an injection side-effect — logged by RP4's own comparison logic (`code=status_claim_mismatch`).

## 3. `[Approval]` activity today (staging) — likely the same batch as Findings #8/#9 (scenarios 26/27)

8 lines, all from one cluster (`13:17:07Z–13:19:20Z`): 4× `queued {action_id} | airtable_add | user=2baafc9c` each immediately followed by `✅ sent to owner`. **No `[Approval] ✅ confirmed` line appears today** on staging — none of these 4 queued approvals were resolved (confirmed/rejected) via the Telegram callback path within this window, so **today's data adds nothing new toward verifying or refuting BUG-138** (the inline-keyboard-not-clearing hypothesis, which specifically requires a *confirmed* callback to reproduce). Still open, still unverified against real Telegram behavior.

This 4-item `airtable_add` batch matches `docs/architecture/action-gateway/STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md`'s Findings #8/#9 — a "4-task `ActionContract` batch-approval flow" from a second staging sample, documented as TurnCoordinator Acceptance Corpus scenarios 26/27 (stale Tier-2 batch preview surviving the flow, and completion/next-item messages sent out of order). Count, tool shape, and timing (`13:17Z–13:19Z`) line up closely — see `docs/architecture/turn-coordinator/LOG_OBSERVATION_23JUL2026.md` §2.1 for the full correlation. Neither finding is implemented yet (both deferred to TurnCoordinator's own infrastructure); this export doesn't add new diagnostic value beyond confirming the raw traffic shape.

## 4. Production (`srv-d80ehsf7f7vs73cq5rn0`) for comparison

Confirmed separately: zero `[EvidenceFinalizerShadow]`/`[TurnEnvelope]`/`[Approval]` lines in production today. The only production activity was a 21-call TMA-dashboard REST session (09:42–09:46Z) plus background scheduler/restart noise — no real `run_agent()` turns. See `docs/architecture/turn-coordinator/LOG_OBSERVATION_23JUL2026.md` §1 for the full evidence chain (BUG-134 recurrence observed there too, independently of this staging data).

## 5. Related already-registered bugs — not otherwise covered above

For completeness of "full bug picture" (this session's original ask): two other bugs registered in `AI_CONTEXT.md`/`BUG_AUDIT_LOG.md` from the earlier `claude/crm-bot-staging-findings-k6lfbi` merge weren't checked against today's logs when this report was first drafted. Checked now, on request:
- **BUG-136** ("בצע שוב `<code>`" wrapped in markdown bold falls through to Agent) — attempted a targeted export with marker `"בצע שוב"` against today's staging window; it failed with `HTTP 500` (the same non-ASCII/curl-on-Windows issue seen earlier this session with other Hebrew markers, not a "no results" signal — inconclusive, not ruled out or confirmed).
- **BUG-137** (`_describe_contract_for_reconfirmation()` leaking an unlabeled `domain` into "✅ בוצע: עדכון ליד") — an ASCII proxy marker (`"reconfirmation"`) returned 19 hits, but all are `[AUDIT:gateway] source=action_contract_repository op=create` lines (contract creation audit events, an unrelated code path that happens to share a substring) — not the actual success-message text. No real signal either way today.

Both remain **registered, not verified against today's logs, not fixed** — same status as in `BUG_AUDIT_LOG.md`. Listed here so this report doesn't silently omit them from the day's picture.

## 6. Recommendation

1. **Filed as BUG-139** (`BUG_AUDIT_LOG.md`) — the `no_evidence → response_claim=failure` pattern (§2), confirmed not a fault-injection artifact, recurring across two independent sessions today, matching RP5's own documented false-evidence bug definition. Root cause in `core/turn_evidence.py`'s `response_claim` derivation still needs to be traced next.
2. Pull a wider staging window (multiple days) filtered to `no_evidence.*response_claim=failure` to see if the ~33% rate holds or was specific to today's session.
3. RP5 9-state coverage (§1) is meaningfully further along than the production-only view suggested (5/9 states with real staging data vs. 0/9 from production alone) — worth reflecting in `RP5_PREFLIGHT_BLOCKER.md` §3's tracking the next time that document is updated.
4. BUG-138 still needs a real confirmed-callback reproduction — today's data doesn't provide one on either service. BUG-136/137 (§5) need a working non-ASCII marker export to check against today's logs at all — worth fixing the exporter's Hebrew-marker/curl issue if these come up again.
