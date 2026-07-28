# Context Librarian — Consumption Enforcement: Plan (N17 item 8)

**Status: planning only. Nothing in this document is implemented.** No code
changed, no CLI command added, no catalog node or schema field added, no
runtime change. Written against `origin/main` at `a205dea` (post PR #485 —
pilot-findings remediation — and PR #487 — targeted rerun verification).

Explicit precondition before any implementation PR for this plan: an
independent Codex audit of this same problem is running in parallel. No
implementation PR for anything in this document may open until that audit is
received and checked against this plan. This document does not, and cannot,
clear that precondition itself.

## 1. The problem

PR #485 and PR #487 closed the class of gap where a mandatory source was
**missing from the bundle** — the `notes[0]`-only rendering bug, the missing
`decision_adapter.py` reference, the missing parallel-sources-of-truth note,
the missing BUG-140 inline expansion, and the commit/branch mislabeling are
all fixed and directly re-verified against `main`. PR #487's own targeted
rerun then found something PR #485 could not fix, stated in its own words:

> the dominant root cause was investigation discipline (not reading
> everything listed), which a catalog fix cannot structurally guarantee.

Concretely, from that rerun:

- **`core_reasoning_change`**: of the ~5 sources the pilot's blind review
  said were missed, 4 were **already present in the bundle before PR #485**
  (`tma_api.py`, `FEATURE_CORE_REASONING_LEADS_STATE`,
  `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`, and the reasoning-engine/
  orchestrator chain) — the Librarian-track investigation simply never
  opened them.
- **`rp5_evidence_mismatch`**: the "missed third evidence-shadow layer"
  finding (`core/last_tool_result_shadow.py`) was never a catalog gap at
  all — `layer.tools` already listed the file and its flag, and
  `rp5_evidence_mismatch`'s own `required_dependency_layers` already
  declared `tools` as required. Nobody opened a dependency layer the
  profile itself already pulled in.

This is exactly the situation the current request describes: a mandatory
source already appears in the bundle, but the agent reaches a conclusion
without opening it. `AGENT_CONSUMPTION_CONTRACT.md` already says, in prose,
"Open the cited code, tests, canonical documents, and production evidence
that are material to the change. A bundle is an index, not a substitute for
them" — but nothing today checks, records, or blocks on whether that
actually happened. The contract is advisory; there is no machine-checkable
consequence for silently skipping a listed source.

## 2. Root cause

Two distinct root causes, at different depths:

**Primary (structural, cannot be fixed by more catalog content):**
`librarian.py` is a standalone dev CLI tool, invoked as a subprocess with no
production imports (`README.md`, `AGENT_CONSUMPTION_CONTRACT.md`). It has no
visibility into the calling agent's own tool-call history — Read/Grep calls
happen in the harness/session that invoked the CLI, not inside
`build_bundle()`. There is therefore no way for the librarian itself to
observe, from inside its own process, whether a path it printed in the
`## Code` / `## Tests` / `## Canonical Documents` sections was subsequently
opened. This is an architectural boundary, not an oversight: it is the same
boundary that keeps the librarian from being a runtime system
(`decision.no_new_source_of_truth`).

Given that boundary, exactly two categories of enforcement are structurally
possible:

1. **Self-attestation** — the agent declares, in a checkable, structured
   format, what it did with each mandatory item. Checkable for internal
   consistency (every item accounted for, no empty waivers) but never for
   truth (an agent could still declare "reviewed" without having read
   anything).
2. **External/independent verification** — a second party (human or an
   independent subagent with its own repository access) checks the first
   party's actual sources-opened and conclusion against the bundle's
   mandatory list. This is exactly what the 5 blind-review subagents in the
   28/07 non-inferiority pilot did by hand, and it is the only mechanism
   that caught the misses above — self-attestation never would have,
   because the investigation that missed 4/5 sources for
   `core_reasoning_change` would have had no reason to attest anything was
   wrong.

Nothing today formalizes either category as a repeatable, tool-supported
step. Both were manual, one-off constructions for the pilot.

**Secondary (a real but narrower catalog-completeness gap):** an
enforcement checklist is only as good as the mandatory-item list it is
built from. `turn_coordinator`'s `feature_flags` list
(`docs/context_librarian/layers/turn_coordinator.json`) is missing
`FEATURE_AUTO_CAPTURE`, even though `core/lead_candidate_handler.py` — the
exact file that flag governs — is already in that layer's `code_paths`.
Confirmed directly against `main` at `a205dea`:
`feature_flags.py:98` declares the flag; it is absent from
`feature_flags._DEFAULTS`, so it defaults `off`; its only two call sites are
`core/lead_candidate_handler.py:1118` (`_flag("FEATURE_AUTO_CAPTURE")`) and
the `_should_auto_write()` function at lines 1150-1156
(`return auto_capture and not existing_id` — the exact line the 28/07 pilot
found turns BUG-130 into a silent, no-approval direct-write path when the
flag is on). PR #487 confirmed by direct grep this is still absent. This is
a distinct, smaller gap from the consumption-enforcement problem, but it is
listed in this same plan because a checklist built today, before this one
catalog fix, would silently under-list the mandatory set for this profile.

## 3. Design options

**Option A — Self-attested Consumption Ledger, verified for internal
completeness by a new CLI subcommand (fail-closed).**
The agent produces a structured ledger declaring a status
(`opened`/`reviewed`/`waived`) for every mandatory item; a new
`verify-consumption` command recomputes the same mandatory set
`build_bundle()` would produce and fails closed if any item is missing, has
an invalid status, or (for a waiver) an empty reason. Fully inside the
librarian's existing architectural boundary — deterministic, no LLM, no
runtime, same "fail closed absent an explicit attestation" pattern already
used by `--assert-main`. Cannot detect a false or lazy attestation: an agent
that skips reading a file can also skip honestly reporting that it skipped
it, and nothing here can force honesty. Does not, by itself, reproduce what
actually caught the pilot's misses.

**Option B — Mandatory independent blind review for any task making a
completion/production claim or touching a `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`-gated
layer.**
Formalizes exactly what this session did by hand: a reviewer packet (task
text, the first agent's sources-opened list and conclusion) goes to an
independent reviewer — subagent or human — with its own repository access,
who is asked to verify specific claims and flag any mandatory item never
opened. This is the only mechanism that actually caught the pilot's misses,
because the reviewer re-derives facts independently rather than trusting a
self-report. Expensive per task (a second agent run or a human's time);
disproportionate for routine, low-risk, read-only investigations if applied
unconditionally.

**Option C — Harness-level tool-call tracking** (a Claude Code hook that
records actual `Read`/`Grep` calls during the session and cross-references
the paths against the active bundle's mandatory list, e.g. blocking a Stop
event if a mandatory path was never opened).
The only option that gives genuine, non-self-reported detection of
`opened` (not `reviewed` — comprehension still cannot be machine-verified
by any option here). It requires new surface area outside the librarian's
own boundary: `.claude/hooks`/`settings.json` configuration, a different
owner and review path, and a mechanism for the librarian to publish "here is
the current bundle's mandatory list" to a side-channel the hook can read.
Real value, but a materially larger and differently-scoped change.

**Option D — Status quo:** rely on the existing prose contract plus PR #485/
#487's catalog-completeness fixes, with no further mechanism. Already shown
insufficient: 2 of the 4 gaps the pilot found were pure investigation-
discipline failures that a catalog fix could not close (Section 1).

## 4. Recommended decision

**Layer Option A (always, cheap, structural) with Option B (risk-gated,
expensive, the only thing that catches dishonesty) — not Option A alone, and
not an attempt to solve everything with automation.** Option C is real but
is recommended against **for this phase**; it changes a different system
(the harness) with a different review surface and should be its own,
separately-scoped future proposal (Section 9), not bundled into this one.

Proposed trigger rule for when Option B (independent review) is mandatory
rather than optional — reusing gates that already exist elsewhere in this
catalog rather than inventing a new one:

- the task uses `--production-claim`, or
- the task's selected profile includes a layer or
  `mandatory_canonical_decisions` entry that
  `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` already gates, or
- **any mandatory item in the ledger is `waived` rather than
  `opened`/`reviewed`** — a waiver is precisely the situation
  self-attestation alone cannot make trustworthy, so a waiver on a
  consequential task should itself escalate to review, not be accepted at
  face value.

For everything else — routine, low-risk, investigation-only tasks with no
completion claim and no waivers — Option A's self-attested, internally-
verified ledger is proportionate and sufficient. This mirrors the existing
risk-proportionate philosophy already in the catalog: production claims need
qualifying evidence; cross-layer changes need a Cross-Layer Impact Matrix;
routine reads need neither.

## 5. Proposed schema/CLI changes (illustrative — none applied in this PR)

**5.1 Bundle format addition — new `## Consumption Checklist` section.**
Enumerates one row per mandatory item with a stable, deterministic
`item_id`:

- `code:<path>` and `test:<path>` for every path in the primary layer(s)'
  and required-dependency layers' `code_paths`/`test_paths`;
- `decision:<id>` for every entry in `mandatory_canonical_decisions`;
- `expansion:<path>#<anchor>` for every `bounded_local_expansions` entry.

`optional_evidence` and `conditional_optional_evidence` are **not** included
— they stay query-triggered and advisory exactly as today, so the checklist
cannot grow the bundle or force reading of non-material sources; it is
bounded by the same `maximum_documents` budget already enforced, and adds
only a compact list of ids for sources already named elsewhere in the
bundle.

**5.2 New artifact — Consumption Ledger (JSON), not part of the catalog, not
committed as durable state.** Illustrative shape:

```json
{
  "schema_version": "1.0",
  "task_type": "turn_coordinator_routing",
  "bundle_generated_commit": "a205dea...",
  "bundle_generated_branch": "claude/...",
  "items": [
    {
      "item_id": "code:core/lead_candidate_handler.py",
      "status": "reviewed",
      "evidence_quote_or_line_range": "lines 1189-1234, _handle_single_candidate()",
      "reviewed_at": "2026-07-28T15:00:00Z",
      "reviewer": "claude-sonnet-5 / session <id>",
      "branch": "claude/...",
      "commit": "a205dea..."
    },
    {
      "item_id": "decision:cross_layer_authority",
      "status": "waived",
      "waiver_reason": "no ActionContract/ActionGateway import or shared identifier touched by this task; confirmed by grep of the changed files",
      "reviewed_at": "2026-07-28T15:00:00Z",
      "reviewer": "claude-sonnet-5 / session <id>"
    }
  ]
}
```

Treated as disposable, like generated bundles
(`docs/context_librarian/generated/*.md`, already git-ignored) — e.g.
`docs/context_librarian/generated/consumption/<task>.json`, git-ignored. No
historical ledger accumulates in the repository; the durable trace of a
given PR's consumption record is whatever the PR body (or this document's
own "Per-run record" convention, already used in
`PHASE1_NON_INFERIORITY_PILOT.md`) chooses to echo. This explicitly avoids
creating a new persistent source of truth (`decision.no_new_source_of_truth`).

**5.3 New CLI subcommand:**
`python -m tools.context_librarian verify-consumption --task-type <id> --query <q> --ledger <path>`

- Recomputes the same mandatory-item set `build_bundle()` would produce for
  that exact profile, query, and current commit — reusing `_select_nodes()`
  and the profile fields directly; no parallel selection logic.
- Fails closed (non-zero exit) when: any mandatory `item_id` is absent from
  the ledger; any item's `status` is missing or not one of
  `opened`/`reviewed`/`waived`; a `waived` item has an empty or
  placeholder-looking `waiver_reason`; an `opened`/`reviewed` item is
  missing `evidence_quote_or_line_range` or it is empty; the ledger's
  `bundle_generated_commit`/`bundle_generated_branch` does not match a
  bundle actually recomputable right now for that profile+query (same spirit
  as `--assert-main` — a ledger cannot be checked in against a bundle it
  wasn't actually produced from).
- Exit 0 with `CONSUMPTION: COMPLETE` only when every mandatory item is
  accounted for.

**5.4 `AGENT_CONSUMPTION_CONTRACT.md` changes:** a new "Consumption Ledger"
section between the existing "Context expansion record" and "After coding"
sections, stating: the ledger is mandatory before a final conclusion; the
fail-closed rule ("no final conclusion is permitted until
`verify-consumption` reports `COMPLETE` for the active bundle"); the waiver
bar (a specific, checkable reason — not a generic phrase); and the
review-escalation rule from Section 4.

**5.5 Schema changes: none required as new *node* fields.** The checklist is
fully derivable from fields the schema already requires
(`primary_layers`, `required_dependency_layers`,
`mandatory_canonical_decisions`, `bounded_local_expansions`, `code_paths`,
`test_paths`) — same "derived, not stored" philosophy as
`VERIFICATION_COVERAGE_MODEL_PLAN.md`. One optional, backward-compatible
addition under consideration: a stable `item_id` field on
`bounded_local_expansions` entries (currently addressed only by
`path`+`anchor`), to make checklist ids stable without re-deriving them from
free text.

**5.6 `turn_coordinator` `FEATURE_AUTO_CAPTURE` catalog gap — proposed patch
(illustrative diff; NOT applied in this PR):**

```diff
   "feature_flags": [
     {"name": "FEATURE_PA01_ENFORCEMENT_STATE", ...},
+    {
+      "name": "FEATURE_AUTO_CAPTURE",
+      "default_state": "off",
+      "documented_state": "feature_flags.py:98 — Tiered auto-write via IngressClassification (Stage 3); core/lead_candidate_handler.py:1118 reads it directly (_flag(\"FEATURE_AUTO_CAPTURE\")); _should_auto_write() (lines 1150-1156) = auto_capture and not existing_id — governs whether Tier-1/2 writes bypass approval entirely",
+      "evidence_scope": "code accessor + direct call-site read, confirmed against main at a205dea"
+    },
     {"name": "FEATURE_SINGLE_SPEAKER_APPROVAL_UX", ...}
   ]
```

Confirmed via direct grep against current `main` (`a205dea`) before drafting
this patch, not assumed from any prior document. Presented here as a
ready-to-apply patch for a future implementation PR — not applied now.

**5.7 CI:** a non-blocking, informational check (mirroring the existing
warning-only audit-style steps in `.github/workflows/ci.yml`) noting whether
a PR touching `docs/context_librarian/` for a production-claim task included
a consumption ledger. Explicitly **not** a hard gate in this phase — making
it one requires deciding where a ledger is discoverable in CI, deferred to
Section 9.

## 6. Failure modes

- **Rubber-stamp ledger** — every item marked `reviewed` with an identical,
  non-specific `evidence_quote_or_line_range` ("reviewed the file").
  Mitigation: `verify-consumption` can reject empty, too-short, or
  duplicated-across-items evidence strings as a weak heuristic (Section 7);
  the real backstop is the risk-gated mandatory review in Section 4, which
  does not trust the ledger's content at all.
- **Ledger built against the wrong bundle** (stale commit, different query
  or profile) — mitigated by the live commit/branch cross-check in 5.3.
- **Checklist scope creep enlarging the bundle** — mitigated by strictly
  excluding `optional_evidence`/`conditional_optional_evidence` from the
  checklist (5.1); those remain query-triggered and advisory, unchanged.
- **Waiver abuse** (waiving everything to avoid reading anything) —
  mitigated by requiring a specific, checkable reason per waiver, and by the
  review-escalation rule making any waiver on a consequential task trigger
  mandatory independent review rather than accepting it at face value.
- **False sense of security** — a `CONSUMPTION: COMPLETE` result proves
  *process compliance* (every mandatory item was attested), never
  *comprehension* or *correctness*. This must be stated in
  `AGENT_CONSUMPTION_CONTRACT.md` itself, not just this plan, precisely
  because it is the overclaim risk that would make Option A alone
  dangerous if presented as sufficient.
- **Multi-session/parallel-agent races on a shared ledger path** — avoided
  by design: the ledger is per-task, per-session, disposable, never a
  shared mutable file. Not a fix for Multi-session Coordination (N17 item
  6), which remains separately unplanned; this design does not make that
  problem worse.
- **Backward compatibility** — `verify-consumption` must be strictly
  additive/opt-in. None of the 62 currently-passing tests in
  `test_context_librarian.py`, nor `build`/`suggest-profile`/`validate`'s
  existing output, should need to change for this design to be
  implementable — a de-risking property worth verifying explicitly in the
  implementation PR, not assumed here.

## 7. Regression tests required (for the eventual implementation PR — none exist yet, none run now)

Following the existing house test-naming convention in
`test_context_librarian.py`:

- `test_consumption_checklist_lists_exactly_the_mandatory_tier(catalog)` —
  for a known profile, checklist items equal primary/required-dependency
  code+test paths, mandatory canonical decisions, and bounded local
  expansions; excludes optional/conditional evidence even when the query
  matches their trigger terms.
- `test_consumption_checklist_item_ids_are_stable_and_deterministic(catalog)` —
  same profile+query+commit produces identical item ids across repeated
  builds (mirrors the existing
  `test_output_is_deterministic_including_provenance_and_expansion`).
- `test_verify_consumption_fails_closed_on_missing_item(tmp_path)` — a
  ledger missing one mandatory item id exits non-zero and names the missing
  id.
- `test_verify_consumption_fails_closed_on_empty_waiver_reason(tmp_path)` —
  a waived item with an empty or whitespace-only reason exits non-zero.
- `test_verify_consumption_fails_closed_on_missing_evidence_for_reviewed_item(tmp_path)` —
  a reviewed item with empty `evidence_quote_or_line_range` exits non-zero.
- `test_verify_consumption_fails_closed_on_bundle_commit_mismatch(tmp_path, monkeypatch)` —
  ledger's recorded commit doesn't match a bundle rebuilt live for the same
  profile+query (mirrors `test_assert_main_fails_closed_unless_proven`'s
  pattern).
- `test_verify_consumption_succeeds_when_all_mandatory_items_accounted_for(tmp_path)` —
  a fully valid ledger exits 0 and prints `CONSUMPTION: COMPLETE`.
- `test_verify_consumption_flags_duplicate_boilerplate_evidence_across_items(tmp_path)` —
  every item sharing the exact same evidence string is flagged (documented
  as a weak heuristic, not a strong guarantee).
- `test_cli_verify_consumption_subcommand_exists_and_is_wired(capsys)` —
  mirrors `test_phase0_cli_commands_remain_compatible`.
- `test_bounded_local_expansion_gains_stable_item_id_without_changing_existing_output(catalog)` —
  confirms the optional schema addition in 5.5 is additive and does not
  perturb any of the 62 existing tests' expected output.
- `test_optional_and_conditional_evidence_never_appear_in_consumption_checklist(catalog)` —
  parametrized across all 7 profiles (mirrors the existing
  `test_query_cannot_pull_in_an_excluded_layer_via_matching_terms` pattern).
- `test_turn_coordinator_feature_flags_includes_auto_capture(catalog)` — a
  small regression test locking in the 5.6 patch once it is actually
  applied in a future implementation PR; not part of this planning PR, and
  the patch itself is not applied here either.

## 8. Rollout plan

- **Phase 0 (this PR):** planning only. No code, no catalog change, no CLI
  change. Gated on this document being reviewed and on the parallel,
  independent Codex audit being received and checked — explicit
  precondition from the requester, not clearable by this document.
- **Phase 1 (separate, reviewed implementation PR):** 5.1–5.3 (checklist
  rendering, ledger format, `verify-consumption` CLI) plus the Section 7
  regression tests. Strictly additive/opt-in — no existing command's
  behavior changes.
- **Phase 2 (separate PR, does not depend on Phase 1):** apply the
  `FEATURE_AUTO_CAPTURE` catalog patch (5.6) as its own small, low-risk,
  catalog-only change. Could land before, after, or independently of Phase
  1 — sequencing is an owner choice (Section 9), not decided here.
- **Phase 3 (separate PR, only after Phase 1 has been used at least once
  for a real task):** promote the review-escalation rule (Section 4) from
  this plan into a hard "must" in `AGENT_CONSUMPTION_CONTRACT.md`, and wire
  the CI informational check (5.7).
- **Phase 4 (future, explicitly deferred, owner decision):** evaluate
  Option C (harness-level hook tracking) as its own separately-scoped
  proposal, informed by whether Phases 1–3 show the rubber-stamp failure
  mode (Section 6) actually occurring in practice.

### Acceptance criteria for a new pilot on new tasks (after Phase 1 ships — not this pilot, not a re-run of the 28/07 pilot)

A future pilot validating Consumption Enforcement itself, on tasks not used
in the 28/07 pilot, should require, per task:

- an independent blind Gold Set and independent blind review, as in the
  28/07 pilot (Section 2 of `PHASE1_NON_INFERIORITY_PILOT.md`'s existing
  protocol — reused, not reinvented);
- the ledger enumerates 100% of the mandatory tier for the selected profile
  (verified by `verify-consumption` reporting `COMPLETE`);
- zero mandatory items waived without the review-escalation rule (Section
  4) having actually fired when a waiver occurred;
- zero `reviewed` items with generic/duplicated evidence strings across the
  ledger (the weak heuristic in Section 7 catching what it can);
- **the specific failure mode this mechanism targets — a mandatory,
  already-included source never opened before a conclusion — has a measured
  miss rate of zero** across the new tasks, evaluated by the independent
  reviewer exactly as in the 28/07 pilot;
- optional/conditional-evidence misses are explicitly **not** counted
  against this criterion — those remain advisory by design (Section 6),
  and conflating the two would misattribute an intentional scope choice as
  a defect;
- Phase 1 acceptance (per `PHASE1_NON_INFERIORITY_PILOT.md`'s existing
  criteria — dual-vendor bundle-hash equality, zero Critical/High
  architecture defects, etc.) is a separate, larger bar this narrower pilot
  does not attempt to establish by itself.

## 9. What requires an owner decision

- Approve, reject, or amend the overall layered design (Option A always +
  risk-gated Option B; Option C deferred) — Section 4.
- Where the Consumption Ledger physically lives per PR: git-ignored local
  file only, versus also echoed into the PR body as a fenced block
  (matching the existing "Per-run record" convention already used in
  `PHASE1_NON_INFERIORITY_PILOT.md`) — affects auditability versus repo
  cleanliness.
- The exact trigger conditions for mandatory independent review (Section
  4's drafted rule: `--production-claim` OR a Cross-Layer-Authority-gated
  layer/decision OR any waived mandatory item) — owner may want to broaden
  or narrow this.
- Whether CI's informational consumption-ledger check (5.7) should ever
  become a hard gate, and for which class of PR.
- Sequencing of the `FEATURE_AUTO_CAPTURE` catalog patch (5.6): bundle with
  Phase 1, or land immediately as its own tiny, independent PR — it depends
  on nothing else in this plan.
- Whether the optional `bounded_local_expansions` `item_id` field (5.5)
  should be added ahead of Phase 1 as its own small, additive schema
  change, or deferred to land together with Phase 1.
- **Confirmation that the parallel, independent Codex audit has been
  received and reviewed before any Phase 1 implementation PR is opened** —
  an explicit precondition stated for this planning cycle; this document
  cannot self-clear it.

## Explicit non-goals for this document and phase

- No implementation. No code, no CLI, no catalog change, no schema change
  in this PR.
- No fix for BUG-130, BUG-140, BUG-150, or the `ActionGateway` fail-open
  evidence check — all remain exactly as gated by
  `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`, unchanged from the 28/07 pilot and
  its remediation.
- No re-run of the non-inferiority pilot (old or new). Phase 1 acceptance
  remains not established, unchanged from
  `PHASE1_NON_INFERIORITY_PILOT.md`'s existing determination.
- No PR implementing any part of Sections 5–8 until (a) this plan is
  reviewed and (b) the parallel, independent Codex audit is received and
  checked, per explicit instruction for this planning cycle.
