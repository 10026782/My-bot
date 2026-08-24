# Context Librarian — Consumption Enforcement: Plan (N17 item 8)

**Mandatory gate for this document:** `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— this plan's owner-approved trigger rule (Section 4) references production
claims and the Durable Atomic Approval layer's own gate, so it is a Planning
Gate document under that contract's §0. See "Cross-Layer Impact Matrix"
below for the required 4-layer analysis.

**STATUS: PLANNING APPROVED BY OWNER — Phase 1 implementation is merged and
available, while later enforcement phases remain planned.** The Cross-Layer
Impact Matrix found no unresolved cross-layer risk — all four layers are
either untouched or touched only by reference/illustrative catalog metadata,
with explicit proof below. Section 9's owner-decisions are now resolved (see
below for each); the parallel, independent Codex audit has been received,
reviewed, and merged as PR #489.

**Implemented and wired:** Consumption Enforcement Phase 1 (PR #490) added
the mandatory checklist/ledger validation, `verify_consumption()`, and the
`verify-consumption` CLI subcommand. The validator is fail-closed when it is
invoked and returns `CONSUMPTION: COMPLETE` or `CONCLUSION_BLOCKED` with the
corresponding exit code. This is static/code evidence, not production
verification.

**Still planned:** the Phase 3 CI step that invokes `verify-consumption` on a
ledger artifact and blocks the job on `CONCLUSION_BLOCKED`; the plan's
broader rollout and operational enforcement remain unimplemented. Written
against the current implementation on `origin/main` at the final Track F
truth-reset SHA `7e38c8e4274285bb548e02830d8ef959148fb31a` (24/08/2026).

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
   truth (an agent could still declare a source reviewed without having
   read anything).
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
flag is on). PR #487 confirmed by direct grep this was still absent as of
`a205dea`. **Update:** this has since been fixed on `main` by the separate,
independent PR #489 (merge `20914f2`) — not by this plan or PR #488. It
remains described here, historically, because a checklist built before
that catalog fix would have silently under-listed the mandatory set for
this profile; the same reasoning is the general argument for Section 3's
design options, independent of this one instance now being resolved.

## 3. Design options

**Option A — Self-attested Consumption Ledger, verified for internal
completeness by a new CLI subcommand (fail-closed).**
The agent produces a structured ledger declaring receipts and waivers for
every mandatory item; a new `verify-consumption` command recomputes the
same mandatory set `build_bundle()` would produce and reports
`CONCLUSION_BLOCKED` if any item is unaccounted for, or a receipt/waiver is
missing required fields or an empty reason. Fully inside the librarian's
existing architectural boundary — deterministic, no LLM, no runtime, same
"fail closed absent an explicit attestation" pattern already used by
`--assert-main`. Cannot detect a false or lazy attestation: an agent that
skips reading a file can also skip honestly reporting that it skipped it,
and nothing here can force honesty. Does not, by itself, reproduce what
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

**Option D — Status quo:** rely on the existing prose contract plus
PR #485/#487's catalog-completeness fixes, with no further mechanism.
Already shown insufficient: 2 of the 4 gaps the pilot found were pure
investigation-discipline failures that a catalog fix could not close
(Section 1).

## 4. Decision — approved by owner

**Layer Option A (self-attested Consumption Ledger, for every governed
task) with Option B (mandatory independent review, risk-triggered) — not
Option A alone, and not an attempt to solve everything with automation.**
Option C is deferred to a separate, future, separately-scoped proposal
(Section 9) — approved as deferred, not merely "recommended against."

Approved trigger rule for when Option B (independent review) is mandatory:

- the task makes a production claim, or
- the task's selected profile includes a layer or
  `mandatory_canonical_decisions` entry that
  `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` already gates, or
- **any mandatory source is waived** — a waiver is precisely the situation
  self-attestation alone cannot make trustworthy.

**Waivers, approved rule:** every waiver requires both a specific,
checkable reason (Section 6) **and** independent reviewer approval — a
self-attested waiver alone is never sufficient, on any task, regardless of
risk tier; the independent-review trigger above exists specifically so a
waiver is never accepted at face value. **A waiver expires** the moment the
bundle's `commit`, `branch`, `profile`, or `query` changes — it is scoped
to the exact task identity it was reviewed against (5.2/5.3's four
identity fields), not to the task in the abstract; a changed identity
requires a fresh waiver and fresh independent approval, not a carried-over
one.

For everything else — routine, low-risk, investigation-only tasks with no
completion claim and no waivers — Option A's self-attested, internally-
verified ledger is proportionate and sufficient. This mirrors the existing
risk-proportionate philosophy already in the catalog: production claims need
qualifying evidence; cross-layer changes need a Cross-Layer Impact Matrix
(this document's own, below); routine reads need neither.

**Consumption verification proves completeness of accounting, not truth or
comprehension** — `verify-consumption` reporting `CONSUMPTION: COMPLETE`
means every mandatory source has a receipt or an approved, unexpired
waiver; it never means the agent understood what it read correctly. This
is why risk-triggered independent review remains required regardless of
how clean a ledger looks — it is the only check in this design that
verifies substance, not just accounting.

This rule is itself the reason this document is a Planning Gate document
under `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — it references, and depends
on, that contract's authority over the Durable Atomic Approval layer without
redefining it. See the Cross-Layer Impact Matrix for the explicit proof.

## 5. Proposed schema/CLI changes (illustrative — none applied in this PR)

**5.1 Bundle format addition — new `## Consumption Checklist` section.**
Enumerates one row per `required_sources` entry (terminology adopted from
the independent Codex audit's `SOURCE_CONSUMPTION_GATE_PLAN.md` — see 5.2)
with a stable, deterministic `item_id`, across exactly these categories:

- `code:<path>` and `test:<path>` for every path in the primary layer(s)'
  and required-dependency layers' `code_paths`/`test_paths` — **primary/
  required code and required tests**;
- `doc:<path>` for every `canonical_docs` entry reachable via a
  `mandatory_canonical_decisions` entry, a primary layer, or a
  required-dependency layer — **mandatory canonical documents**;
- `evidence:<path>` for every `production_evidence` entry, **but only when
  `--production-claim` is set** — without a production claim, no evidence
  entry is mandatory, mirroring `build_bundle()`'s own existing
  `evidence_budget` logic, which already allocates zero evidence budget
  without a claim;
- `decision:<id>` for every entry in `mandatory_canonical_decisions`;
- `expansion:<path>#<anchor>` for every `bounded_local_expansions` entry
  **marked `required_for_conclusion: true`** — a new, optional, additive
  profile field proposed in 5.5. Every currently-existing
  `bounded_local_expansions` entry (e.g. the BUG-140 window in
  `turn_coordinator_routing`) would default to `true`, since each was added
  specifically to force a miss-prone read.

`optional_evidence` and `conditional_optional_evidence` are **not** included
— they stay query-triggered and advisory exactly as today, so the checklist
cannot grow the bundle or force reading of non-material sources; it is
bounded by the same `maximum_documents` budget already enforced, and adds
only a compact list of ids for sources already named elsewhere in the
bundle.

**5.2 New artifact — Consumption Ledger (JSON), disposable and local, not
part of the catalog.**

Converges with the independent Codex audit's own
`SOURCE_CONSUMPTION_GATE_PLAN.md` (proposed on `codex/context-librarian-audit-remediation`
at commit `1e4be33`, same base commit as this PR, `origin/main` at
`a205dea`), which independently proposed the same shape under the names
`required_sources`/`review_receipt`/`waived_sources`/`unreviewed_sources`.
This section adopts that vocabulary so the two independent plans converge
on one model instead of diverging over naming — an encouraging cross-check,
since two independent authors reached the same receipt-based structure.
Codex itself removed that file before merging (PR #489, merge `20914f2`),
explicitly deferring to this document as the canonical plan — there is no
longer a duplicate planning doc on `main`. **This convergence is
planning-only.** The rest of that same PR's code (the `on_main_history`/
`at_origin_main_tip` provenance split, the `FEATURE_AUTO_CAPTURE` catalog
entry, and a POSIX/Windows path-validation fix) **is now merged to `main`**
(PR #489) — real, live code, but still not part of PR #488, not applied by
this
document, and nothing below should be read as claiming any of it is closed
here.

Illustrative shape:

```json
{
  "schema_version": "1.0",
  "task_type": "turn_coordinator_routing",
  "profile": "turn_coordinator_routing",
  "query": "lead routing",
  "bundle_generated_commit": "a205dea...",
  "bundle_generated_branch": "claude/...",
  "required_sources": [
    "code:core/lead_candidate_handler.py",
    "decision:cross_layer_authority",
    "expansion:BUG_AUDIT_LOG.md#BUG-130"
  ],
  "review_receipts": [
    {
      "item_id": "code:core/lead_candidate_handler.py",
      "path": "core/lead_candidate_handler.py",
      "commit": "a205dea...",
      "branch": "claude/...",
      "profile": "turn_coordinator_routing",
      "query": "lead routing",
      "reviewed_by": "claude-sonnet-5 / session <id>",
      "reviewed_at": "2026-07-28T15:00:00Z",
      "reason": "confirmed _handle_single_candidate() lines 1189-1234, exact-match phone lookup at _at_find_lead()",
      "evidence_reference": "lines 1189-1234, 341-378"
    }
  ],
  "waived_sources": [
    {
      "item_id": "decision:cross_layer_authority",
      "path": null,
      "commit": "a205dea...",
      "branch": "claude/...",
      "profile": "turn_coordinator_routing",
      "query": "lead routing",
      "reviewed_by": "claude-sonnet-5 / session <id>",
      "reviewed_at": "2026-07-28T15:00:00Z",
      "reason": "core/lead_candidate_handler.py mentions ActionContract/ActionGateway only in comments/docstrings/log strings, never as an import or a class/function-level dependency — confirmed the distinction actually holds before using it as an illustrative example, not a claim about this planning document, which discusses those identifiers narratively throughout",
      "evidence_reference": "grep -n '^import\\|^from' core/lead_candidate_handler.py -> no ActionContract/ActionGateway import; grep -n 'class ActionContract\\|class ActionGateway' core/lead_candidate_handler.py -> zero matches (illustrative; scoped to import/class-level coupling, not textual mentions)",
      "approved_by": "independent-reviewer-agent / session <id>",
      "approved_at": "2026-07-28T15:04:00Z"
    }
  ]
}
```

Field reconciliation: `required_sources` entries use the `item_id` scheme
from 5.1 uniformly (code/test/doc/evidence/decision/expansion), since a
canonical-decision entry has no literal file path to key on. Each
`review_receipts`/`waived_sources` entry therefore carries **both**
`item_id` (always present, the join key against `required_sources`) **and**
`path` (the literal file path when the item is a real path; `null` for
`decision:*` entries) — together with the full field set: `commit`,
`branch`, `profile`, `query`, `reviewed_by`, `reviewed_at`, `reason`,
`evidence_reference`. **Every `waived_sources` entry additionally requires
`approved_by`/`approved_at`** — a distinct independent reviewer's identity
and timestamp, never the same identity as `reviewed_by` — per Section 4's
approved rule that self-attestation alone is never sufficient for a
waiver.

**Top-level vs. per-item identity — both validated, not just one.** The
ledger's top-level `bundle_generated_commit`/`bundle_generated_branch`/
`profile`/`query` are the single canonical identity for the whole ledger;
`verify-consumption` (5.3) checks that tuple against a bundle actually
recomputable right now. Every `review_receipts`/`waived_sources` entry's
own `commit`/`branch`/`profile`/`query` fields must then equal that
top-level tuple exactly — an entry that disagrees with its own ledger's
declared identity is rejected the same as one that disagrees with the live
bundle, since disagreeing with the (now-validated) top level transitively
means disagreeing with the live bundle too. This closes a real gap: without
this check, a ledger could carry a correct top-level identity while one
entry silently carried a stale or forged identity of its own.

`unreviewed_sources` and the overall pass/fail status are **never written
by the agent** — they are computed exclusively by `verify-consumption`
(5.3) as `required_sources − (review_receipts ∪ waived_sources)`,
specifically so an agent cannot self-report an empty `unreviewed_sources`
list. A ledger that includes either field by hand is itself a
`verify-consumption` failure (a forged computed field).

**Waiver expiry** is not a separate stored field — it falls directly out
of the identity check `verify-consumption` already performs (5.3): a
waiver's `commit`/`branch`/`profile`/`query` must match a bundle actually
recomputable right now for that exact profile+query. The moment any of
those four change, the existing waiver no longer matches and
`verify-consumption` reports `CONCLUSION_BLOCKED` for that item — the same
mechanism that catches a stale receipt also expires a stale waiver; no new
mechanism is needed.

**Ledger location — approved by owner, resolved.** The ledger is a small
JSON file, **disposable and local** — never committed to the repository,
treated the same way as a generated bundle
(`docs/context_librarian/generated/*.md`, already git-ignored) — and is
**uploaded as a CI artifact** (via `actions/upload-artifact`, scoped to the
workflow run that produced it) rather than committed. The PR body records
only the verification result (`CONSUMPTION: COMPLETE` or
`CONCLUSION_BLOCKED` plus the blocked item ids) and a reference to that
artifact (the workflow run URL and artifact name) — never the ledger's
full content. This reverses an earlier draft of this section, which had
resolved the same contradiction by committing the ledger instead; the
owner's approved resolution keeps the ledger disposable and moves the
CI-discoverability burden onto artifact upload instead. **One mechanical
detail is left to the Phase 1 implementation PR, not decided here:**
exactly how the ledger's content reaches the CI run that uploads it as an
artifact, since a GitHub Actions job only sees the checked-out git tree by
default, not an agent's local disk. Two workable approaches, either
acceptable:
(a) the agent includes the ledger in a commit that opens or updates the
PR (so the normal `pull_request`-triggered CI run can read it from the
checkout and archive it as an artifact), then removes it in a later,
pre-merge commit so it never persists in the merged history; or
(b) the agent triggers a dedicated `workflow_dispatch` run, passing the
ledger's content as a workflow input, and that run's own
`verify-consumption` step uploads the artifact. Either way, the ledger
itself is never read back by `build_bundle()`, `_select_nodes()`, or the
freshness/staleness computation, carries no authority over `main`, and
makes no claim beyond "this specific review action happened, attested by
this agent, on this commit" — consistent with
`decision.no_new_source_of_truth`.

**5.3 New CLI subcommand:**
`python -m tools.context_librarian verify-consumption --task-type <id> --query <q> --ledger <path>`

- **Canonical checkout identity, specified explicitly (closes a real CI
  ambiguity):** `verify-consumption` compares the ledger's recorded
  `commit` against the **PR head SHA**
  (`github.event.pull_request.head.sha`), never the default
  `pull_request`-event checkout, which is a synthetic merge ref/detached
  `HEAD` that does not equal the commit the agent actually worked from.
  Any CI job that runs `verify-consumption` must check out that exact SHA
  explicitly (`actions/checkout@v4` with `ref:
  ${{ github.event.pull_request.head.sha }}`), not rely on the workflow's
  default ref — otherwise every ledger would spuriously mismatch in CI
  regardless of correctness. Outside CI (local runs), `commit` is simply
  `git rev-parse HEAD`.
- Recomputes the same `required_sources` set 5.1 defines for that exact
  profile, query, and current commit — reusing `_select_nodes()` and the
  profile fields directly; no parallel selection logic.
- Computes `unreviewed_sources = required_sources − (item_ids in
  review_receipts ∪ item_ids in waived_sources)`.
- Validates the ledger's **top-level** `bundle_generated_commit`/
  `bundle_generated_branch`/`profile`/`query` against the live-recomputed
  bundle first (per 5.2's top-level-vs-per-item note), then validates
  every `review_receipts`/`waived_sources` entry's own identity fields
  against that same top-level tuple — both checks must pass, not just one.
- Reports `CONCLUSION_BLOCKED` (exit 2) and lists `unreviewed_sources` by
  name when that set is non-empty, or when: a `review_receipts`/
  `waived_sources` entry is missing `commit`/`branch`/`profile`/`query`/
  `reviewed_by`/`reviewed_at`/`reason`/`evidence_reference`; a
  `waived_sources` entry is additionally missing `approved_by`/
  `approved_at`, or `approved_by` equals `reviewed_by` (self-approval is
  not independent approval); the ledger's top-level identity, or any
  entry's identity, does not match a bundle actually recomputable right
  now for that exact profile+query — this is also how a waiver expires
  (Section 4/5.2): a changed identity field means the approved waiver no
  longer applies, same as a stale receipt; a waiver's `reason` is empty or
  placeholder-looking; or the ledger sets `unreviewed_sources` or a
  pass/fail field directly (a forged computed field, rejected outright).
- **Duplicate/boilerplate evidence — deterministic, non-blocking outcome
  (resolves an earlier draft's ambiguity):** identical `reason`/
  `evidence_reference` strings repeated across items produce a `WARNING`
  line naming the affected items, printed alongside a `CONSUMPTION:
  COMPLETE` result — exit code and pass/fail status are unaffected. This
  is deliberately a warning, not `CONCLUSION_BLOCKED`, because the
  heuristic (string equality) can have legitimate false positives (two
  genuinely-reviewed items can honestly share similar phrasing); it exists
  to surface a smell for human/reviewer attention, not to fail a ledger
  outright the way a missing or forged field does.
- Reports `CONSUMPTION: COMPLETE` (exit 0) only when `unreviewed_sources`
  is empty and every identity check (top-level and per-item) passes —
  optionally with a `WARNING` line for duplicate evidence, which does not
  change the exit code.

**5.4 `AGENT_CONSUMPTION_CONTRACT.md` changes:** a new "Consumption Ledger"
section between the existing "Context expansion record" and "After coding"
sections, stating: the ledger is mandatory before a final conclusion, for
every governed task; the fail-closed rule ("no final conclusion is
permitted while `verify-consumption` reports `CONCLUSION_BLOCKED` for the
active bundle"); the waiver bar (a specific, checkable reason **and**
independent reviewer approval — never self-attested alone — expiring the
moment commit/branch/profile/query changes); the mandatory-review trigger rule
from Section 4; and the explicit caveat that a clean ledger proves
accounting completeness, never comprehension or correctness.

**5.5 Schema changes: none required as new *node* fields.** The checklist
is fully derivable from fields the schema already requires
(`primary_layers`, `required_dependency_layers`,
`mandatory_canonical_decisions`, `bounded_local_expansions`, `code_paths`,
`test_paths`) — same "derived, not stored" philosophy as
`VERIFICATION_COVERAGE_MODEL_PLAN.md`. Two optional, backward-compatible
additions under consideration:

- a stable `item_id` field on `bounded_local_expansions` entries (currently
  addressed only by `path`+`anchor`), to make checklist ids stable without
  re-deriving them from free text;
- a `required_for_conclusion` boolean on `bounded_local_expansions` entries
  (5.1), defaulting to `true` for backward compatibility with every
  existing entry.

**5.6 `turn_coordinator` `FEATURE_AUTO_CAPTURE` catalog gap — RESOLVED
elsewhere, kept here only as historical reasoning, not a pending action.**

This gap (Section 2, "Secondary") was independently identified and fixed as
real code on `codex/context-librarian-audit-remediation`, and that fix is
now merged to `main` via PR #489 (`20914f2`) — `turn_coordinator.json`'s
`feature_flags` list now includes `FEATURE_AUTO_CAPTURE` with
`feature_flags.py:98`/`core/lead_candidate_handler.py:1118-1156` as its
`code_reference`. The illustrative diff originally drafted here (before
PR #489 merged) is kept below only so 5.1's checklist-scope reasoning
stays self-contained and auditable against what this document originally
identified — **it is no longer a proposal; it is a record of what this
plan asked for and what PR #489 independently delivered, outside PR #488's
own scope:**

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

Confirmed via direct grep against `main` (`a205dea`) at the time this plan
was first drafted, not assumed from any prior document. PR #488 itself
still applies none of this — the fix landed via PR #489, a separate,
already-merged PR, not this planning document.

**5.7 CI:** per 5.2's approved ledger-location decision, CI runs
`verify-consumption` as part of the same job that receives the ledger
(via a transient PR commit or a `workflow_dispatch` input — 5.2's two
candidate mechanisms), then uploads the ledger as a build artifact via
`actions/upload-artifact`, scoped to that workflow run. The PR body is
updated with only the verification result and a link to that artifact —
never the ledger's full content. Phase 1 (Section 8) only adds the CLI
command; CI does not call it yet. Phase 3 (Section 8) wires an actual CI
step that runs `verify-consumption`, uploads the artifact, and **fails the
step** (not merely warns) if the result is `CONCLUSION_BLOCKED` — a real,
blocking gate once wired, not an "informational check that a ledger
exists."

## 6. Failure modes

- **Self-approved waiver** — an agent labeling itself as both `reviewed_by`
  and `approved_by` to satisfy the independent-approval requirement (5.2)
  without genuine independence. `verify-consumption` structurally rejects
  identical `reviewed_by`/`approved_by` strings (5.3), but cannot detect
  the same underlying human or agent operating under two different labels
  — that remains a process/organizational control, not a machine-checkable
  one; flagged explicitly rather than oversold as solved.
- **Rubber-stamp ledger** — every item covered by a receipt with an
  identical, non-specific `reason`/`evidence_reference` ("reviewed the
  file"). `verify-consumption` rejects empty `reason`/`evidence_reference`
  outright (a hard `CONCLUSION_BLOCKED`, not a heuristic), and prints a
  non-blocking `WARNING` for duplicated-across-items strings (5.3) — a
  weak heuristic by design, since it can false-positive on genuinely
  similar legitimate phrasing. The real backstop is the risk-gated
  mandatory review in Section 4, which does not trust the ledger's
  content at all.
- **Ledger built against the wrong bundle** (different commit, branch,
  profile, or query) — mitigated by the live commit/branch/profile/query
  cross-check in 5.3, exercised by four separate regression tests (Section
  7), not just a commit check.
- **Checklist scope creep enlarging the bundle** — mitigated by strictly
  excluding `optional_evidence`/`conditional_optional_evidence` from the
  checklist (5.1); those remain query-triggered and advisory, unchanged.
- **Waiver abuse** (waiving everything to avoid reading anything) —
  mitigated by requiring a specific, checkable `reason` **and** independent
  `approved_by`/`approved_at` on every waiver, with no exception for
  low-risk tasks (Section 4's approved rule) — self-attestation alone is
  never sufficient for any waiver, not just consequential ones.
- **Forged computed fields** — a ledger that writes `unreviewed_sources` or
  a pass/fail status directly, instead of leaving them for
  `verify-consumption` to compute, is rejected outright (5.2/5.3). An agent
  cannot self-report a clean bill of health.
- **False sense of security** — a `CONSUMPTION: COMPLETE` result proves
  *process compliance* (every mandatory item was attested), never
  *comprehension* or *correctness*. This must be stated in
  `AGENT_CONSUMPTION_CONTRACT.md` itself, not just this plan, precisely
  because it is the overclaim risk that would make Option A alone
  dangerous if presented as sufficient.
- **CI artifact retention/discoverability** — since 5.2 resolves the
  location question by keeping ledgers disposable and uploading them as CI
  artifacts rather than committing them, a real failure mode is that
  GitHub Actions artifacts expire after a retention period (default 90
  days, configurable). Mitigation: the PR body's recorded verification
  *result* (`CONSUMPTION: COMPLETE`/`CONCLUSION_BLOCKED`) is the permanent
  record; the artifact is transient supporting evidence, consistent with
  the ledger being disposable by design — if a longer-lived audit trail is
  ever needed, that is a later owner decision (e.g. a longer retention
  policy for consumption artifacts specifically), not something this plan
  needs to solve now.
- **Multi-session/parallel-agent races on a shared ledger path** — since
  the ledger is disposable and local (5.2), this is the same low risk as
  any other locally-generated, non-shared file; not a fix for
  Multi-session Coordination (N17 item 6), which remains separately
  unplanned, but this design does not make that problem worse.
- **Backward compatibility** — `verify-consumption` must be strictly
  additive/opt-in. None of the 69 currently-passing tests in
  `test_context_librarian.py` (62 when this plan was first drafted; now 69
  on `main` after PR #489's merge), nor `build`/`suggest-profile`/
  `validate`'s existing output, should need to change for this design to be
  implementable — a de-risking property worth verifying explicitly in the
  implementation PR,
  not assumed here.

## 7. Regression tests required (for the eventual implementation PR — none exist yet, none run now)

Following the existing house test-naming convention in
`test_context_librarian.py`:

- `test_consumption_checklist_lists_exactly_the_mandatory_tier(catalog)` —
  for a known profile, checklist `required_sources` equal
  primary/required-dependency code+test paths, mandatory canonical
  documents, mandatory canonical decisions, and bounded local expansions
  marked `required_for_conclusion`; excludes optional/conditional evidence
  even when the query matches their trigger terms; excludes production
  evidence when no production claim is made.
- `test_consumption_checklist_item_ids_are_stable_and_deterministic(catalog)` —
  same profile+query+commit produces identical item ids across repeated
  builds (mirrors the existing
  `test_output_is_deterministic_including_provenance_and_expansion`).
- `test_verify_consumption_fails_closed_on_missing_item(tmp_path)` — a
  ledger missing one `required_sources` item from both `review_receipts`
  and `waived_sources` reports `CONCLUSION_BLOCKED` and names the missing
  id in `unreviewed_sources`.
- `test_verify_consumption_fails_closed_on_empty_waiver_reason(tmp_path)` —
  a waived item with an empty or whitespace-only `reason` reports
  `CONCLUSION_BLOCKED`.
- `test_verify_consumption_fails_closed_on_missing_evidence_reference(tmp_path)` —
  a review receipt with empty `evidence_reference` reports
  `CONCLUSION_BLOCKED`.
- `test_verify_consumption_fails_closed_on_bundle_commit_mismatch(tmp_path, monkeypatch)` —
  a receipt's `commit` doesn't match a bundle rebuilt live for the same
  profile+query (mirrors `test_assert_main_fails_closed_unless_proven`'s
  pattern).
- `test_verify_consumption_fails_closed_on_bundle_branch_mismatch(tmp_path, monkeypatch)` —
  same pattern, `branch` mismatch only, all other identity fields matching.
- `test_verify_consumption_fails_closed_on_bundle_profile_mismatch(tmp_path)` —
  same pattern, `profile` mismatch only.
- `test_verify_consumption_fails_closed_on_bundle_query_mismatch(tmp_path)` —
  same pattern, `query` mismatch only — confirms a ledger cannot be reused
  across a differently-worded task on the same profile/commit.
- `test_verify_consumption_rejects_forged_unreviewed_sources_field(tmp_path)` —
  a ledger that writes `unreviewed_sources` (or any pass/fail field)
  directly is rejected regardless of its content.
- `test_verify_consumption_fails_closed_on_missing_waiver_approval(tmp_path)` —
  a `waived_sources` entry missing `approved_by`/`approved_at` reports
  `CONCLUSION_BLOCKED`.
- `test_verify_consumption_fails_closed_on_self_approved_waiver(tmp_path)` —
  a `waived_sources` entry whose `approved_by` equals its `reviewed_by`
  reports `CONCLUSION_BLOCKED`.
- `test_verify_consumption_treats_identity_change_as_waiver_expiry(tmp_path)` —
  a previously-valid waiver's `profile` (or `commit`/`branch`/`query`)
  no longer matches a freshly-recomputed bundle and reports
  `CONCLUSION_BLOCKED` for that item, confirming Section 4/5.2's waiver-
  expiry rule is enforced by the same identity check as a stale receipt.
- `test_verify_consumption_succeeds_when_all_mandatory_items_accounted_for(tmp_path)` —
  a fully valid ledger exits 0 and prints `CONSUMPTION: COMPLETE`.
- `test_verify_consumption_warns_on_duplicate_boilerplate_evidence_across_items(tmp_path)` —
  every item sharing the exact same `reason`/`evidence_reference` prints a
  `WARNING` line naming them, but still exits 0 with `CONSUMPTION:
  COMPLETE` — confirms the deterministic warn-only (not blocking) outcome
  (5.3), a weak heuristic by design.
- `test_verify_consumption_validates_top_level_identity_independently_of_per_item(tmp_path)` —
  a ledger whose top-level `bundle_generated_commit`/`branch`/`profile`/
  `query` mismatches the live bundle reports `CONCLUSION_BLOCKED` even
  when every per-item entry's own identity fields look internally
  consistent with each other (5.2/5.3's top-level-vs-per-item check).
- `test_cli_verify_consumption_subcommand_exists_and_is_wired(capsys)` —
  mirrors `test_phase0_cli_commands_remain_compatible`.
- `test_bounded_local_expansion_gains_stable_item_id_and_required_for_conclusion_without_changing_existing_output(catalog)` —
  confirms the optional schema additions in 5.5 are additive and do not
  perturb any of the 62 (64 on the Codex branch) existing tests' expected
  output.
- `test_optional_and_conditional_evidence_never_appear_in_consumption_checklist(catalog)` —
  parametrized across all 7 profiles (mirrors the existing
  `test_query_cannot_pull_in_an_excluded_layer_via_matching_terms` pattern).
- `test_production_evidence_only_required_with_production_claim(catalog)` —
  the same profile's checklist includes `evidence:*` ids with
  `--production-claim` and excludes them without it.
- `test_turn_coordinator_feature_flags_includes_auto_capture(catalog)` —
  originally proposed to lock in 5.6's patch; the underlying fix is now
  merged via PR #489 (separate from this plan), so this specific test may
  already be redundant with whatever regression coverage that PR added —
  the implementation PR for this plan should check before adding a
  duplicate.

## 8. Rollout plan

- **Phase 0 (this PR):** planning only. No code, no catalog change, no CLI
  change. `STATUS: PLANNING APPROVED BY OWNER` (top of document) — Section
  9's owner-decisions are resolved and the parallel, independent Codex
  audit has been received and checked (merged as PR #489). The only
  remaining gate is procedural: no implementation PR opens until this
  corrected planning PR is itself reviewed and merged.
- **Phase 1 (separate, reviewed implementation PR):** 5.1–5.3 (checklist
  rendering, ledger format, `verify-consumption` CLI, including the
  waiver-approval and waiver-expiry checks from Section 4) plus the
  Section 7 regression tests. Strictly additive/opt-in — no existing
  command's behavior changes.
- **Phase 2:** the `FEATURE_AUTO_CAPTURE` catalog patch (5.6) — already
  resolved by events; PR #489 merged it independently of this rollout,
  exactly as anticipated when this phase was first sequenced. No action
  needed here.
- **Phase 3 (separate PR, only after Phase 1 has been used at least once
  for a real task):** promote the approved mandatory-review trigger rule
  (Section 4) into a hard "must" in `AGENT_CONSUMPTION_CONTRACT.md`, and
  wire the CI step (5.7) that runs `verify-consumption`, uploads the
  ledger as a build artifact, and **fails the job** on
  `CONCLUSION_BLOCKED` — blocking from day one, decided (Section 9), not
  a warn-only bake-in period.
- **Phase 4 (deferred, per owner decision):** evaluate Option C
  (harness-level hook tracking) as its own separately-scoped proposal,
  informed by whether Phases 1–3 show the rubber-stamp or self-approved-
  waiver failure modes (Section 6) actually occurring in practice.

### Phase 4 pilot cohort — reuse the 5 tasks from `PHASE1_NON_INFERIORITY_PILOT.md`

The Phase 4 pilot (evaluating Option C, harness-level tool-call tracking)
may use the same 5 real tasks already documented in
`docs/context_librarian/PHASE1_NON_INFERIORITY_PILOT.md`'s 28/07
non-inferiority pilot (`approval_ux`/BUG-150, `tool_execution`/the
`ActionGateway` fail-open, `turn_coordinator_routing`/BUG-130+BUG-140,
`core_reasoning_change`, `rp5_evidence_mismatch`) as its real-task cohort —
that pilot did not establish Phase 1 acceptance the first time, and its own
"What remains unproven" section already calls for exactly this kind of
follow-up. This reuses already-investigated, already-approved-scope work;
it does **not** merge those 5 tasks' own real fixes (still gated by
`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`, still not implemented anywhere) into
this planning document's implementation scope, and does not authorize
runtime or CLI changes.

For each selected task, the agent must:

1. declare the task, branch, mode, and planned paths before work;
2. check open PRs, branches, and canonical documents for overlap;
3. stop before creating a duplicate canonical artifact;
4. update the declaration before a material scope expansion; and
5. compare declared paths with the actual diff before commit.

The pilot records:

- overlaps detected before writing;
- duplicate canonical artifacts avoided;
- scope updates;
- declared-path versus actual-diff mismatches;
- review requests; and
- coordination time and false-positive warnings.

Each task remains governed by `PHASE1_NON_INFERIORITY_PILOT.md`'s own
determination and by `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`'s existing gate
on BUG-150/BUG-130/BUG-140/the fail-open — not by this document. This
section only supplies a realistic pilot cohort for the lightweight
coordination check; it does not replace the independent review and
consumption-verification criteria below, and it does not authorize
implementing any of those 3 real defects.

### Acceptance criteria for a new pilot on new tasks (after Phase 1 ships — not this pilot, not a re-run of the 28/07 pilot)

A future pilot validating Consumption Enforcement itself, on tasks not used
in the 28/07 pilot, should require, per task:

- an independent blind Gold Set and independent blind review, as in the
  28/07 pilot (Section 2 of `PHASE1_NON_INFERIORITY_PILOT.md`'s existing
  protocol — reused, not reinvented);
- the ledger's `required_sources` enumerates 100% of the mandatory tier for
  the selected profile (verified by `verify-consumption` reporting
  `CONSUMPTION: COMPLETE`);
- zero mandatory items in `waived_sources` without a genuine, distinct
  `approved_by` independent reviewer (Section 4) — self-approval or a
  missing approval is a hard failure for this criterion, not a soft one;
- zero receipts with generic/duplicated `reason`/`evidence_reference`
  strings across the ledger (the weak heuristic in Section 7 catching what
  it can);
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

## 9. Owner decisions

Resolved:

- ✅ **Overall layered design approved:** self-attested Consumption Ledger
  for every governed task, plus mandatory independent review for
  risk-triggered tasks (Section 4).
- ✅ **Mandatory-review trigger conditions approved as drafted:** a
  production claim, a Cross-Layer-Authority-gated layer/decision, or any
  waived mandatory source (Section 4).
- ✅ **Mandatory-source categories approved as drafted:** primary/
  required-dependency code, required tests, mandatory canonical documents,
  production evidence only for production claims, and expansions marked
  `required_for_conclusion` (5.1).
- ✅ **Waiver rules approved and strengthened:** every waiver requires a
  specific reason **and** independent reviewer approval (`approved_by` ≠
  `reviewed_by`), with no low-risk exception; a waiver expires the moment
  the bundle's commit, branch, profile, or query changes (Section 4/5.2).
- ✅ **Ledger location approved, reversing an earlier draft:** disposable
  and local, uploaded as a CI artifact rather than committed; the PR body
  records only the verification result and an artifact reference (5.2).
  The exact mechanism for transmitting the ledger's content into the CI
  run that uploads it (a transient pre-merge commit vs. a
  `workflow_dispatch` input — 5.2) is left to the Phase 1 implementation
  PR as a mechanical detail, not an open policy question.
- ✅ **Scope of consumption verification approved:** it proves completeness
  of accounting, never truth or comprehension; risk-triggered independent
  review remains required regardless (Section 4/6).
- ✅ **Option C (harness-level tool-call tracking) deferred** to a separate,
  future, separately-scoped proposal (Section 3/8, Phase 4).
- ✅ **Parallel, independent Codex audit received and reviewed** — merged as
  PR #489, its content independently reviewed earlier in this session, its
  fixes cross-referenced throughout this document (Section 2, 5.6, Cross-
  Layer Impact Matrix).
- ✅ **`FEATURE_AUTO_CAPTURE` sequencing** — resolved by events; PR #489
  merged it independently of this plan's own rollout (5.6, Section 8 Phase
  2).

- ✅ **CI enforcement mode decided: blocking from the start, not a
  warn-only bake-in.** (Resolves an earlier draft's self-contradiction
  between 5.7 and this section.) Once Phase 3 wires the CI step, it fails
  the job on `CONCLUSION_BLOCKED` — consistent with `CONCLUSION_BLOCKED`
  being a hard, fail-closed gate everywhere else in this design (mirroring
  `--assert-main`'s existing fail-closed precedent), not a soft advisory
  status. There is no separate warn-only phase to design or remove later.

Still open (narrower, mechanical, deferred to the Phase 1 implementation PR):

- Whether the optional `bounded_local_expansions` `item_id` and
  `required_for_conclusion` fields (5.5) should be added ahead of Phase 1
  as their own small, additive schema change, or land together with
  Phase 1.

**No implementation PR opens until this corrected planning PR is itself
reviewed and merged** — the one remaining gate, procedural rather than
substantive, per explicit instruction for this planning cycle.

## Cross-Layer Impact Matrix (required by `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §0/§2)

This is the grep-based matrix for this document's own proposed mechanism
(Sections 3–8), not a fill-in-later template. Without it, status would stay
`PLANNING BLOCKED` for cross-layer-risk reasons; with it — and with
Section 9's owner-decisions now resolved — the only remaining gate is this
corrected planning PR's own review and merge.

### Layer 1 — Core Reasoning / BUG-104
**touched: not touched.** Proof of non-impact:
1. **grep evidence:** the only Layer 1 identifiers in this document
   (`decision_adapter.py`, `FEATURE_CORE_REASONING_LEADS_STATE`,
   `tma_api.py`, the reasoning-engine/orchestrator chain) appear solely in
   Section 1 as narrative evidence of the 28/07 pilot's own
   `core_reasoning_change` finding — not as a proposed change to that
   layer's code or catalog entry.
2. **unchanged-tests evidence:** none of the `test_bug104_*.py` suites are
   referenced by Section 7's proposed regression tests; the proposed
   mechanism operates generically over profile metadata
   (`primary_layers`/`required_dependency_layers`/
   `mandatory_canonical_decisions`/`bounded_local_expansions`), never over
   Layer 1's own runtime code.
3. **no-new-coupling evidence:** the proposed `verify-consumption`
   subcommand (5.3) reuses `_select_nodes()` — the same selection logic
   `build_bundle()` already runs — and introduces no new import of or
   dependency on any Layer 1 module.

### Layer 2 — TurnCoordinator
**touched: not touched by this document at all** — this document adds no
code, no catalog change, no schema change (unchanged from the top-of-file
status). Historical note only: Section 5.6 originally proposed an
illustrative, unapplied `FEATURE_AUTO_CAPTURE` catalog patch; that exact
patch has since landed as real, merged code via the separate PR #489, not
via this document. Proof, for completeness:
- **input impact:** none — this document reads no catalog file at all; it
  is prose only.
- **output impact:** none from this document itself. The
  `FEATURE_AUTO_CAPTURE` entry now on `main` (`turn_coordinator.json`,
  post PR #489) is pure catalog metadata describing an **existing** flag
  (`feature_flags.py:98`), not a new flag, not a behavior change to
  `core/lead_candidate_handler.py` — and it was authored and merged outside
  this document's own change set.
- **authority impact:** none — this document does not change
  `_should_auto_write()`'s behavior and does not touch BUG-130/BUG-140's
  actual routing logic; both are explicit non-goals.
- **shared identifiers:** `FEATURE_AUTO_CAPTURE` is not new (already
  defined in `feature_flags.py`); the illustrative catalog entry only
  documents it, using the existing `feature_flag_required` schema fields.
- **invariants:** none asserted or modified.
- **failure semantics:** n/a — no runtime path exercises this document's
  proposals yet.
- **observability:** none added.
- **cross-layer tests:** Section 7 originally proposed
  `test_turn_coordinator_feature_flags_includes_auto_capture` to lock in
  5.6's patch once applied; that test's subject matter is now real on
  `main` via PR #489, though the specific test itself is not part of this
  planning PR either way.

### Layer 3 — F52 / Phase 4C Action & Tool Contract
**touched: not touched.** Proof of non-impact:
1. **grep evidence:** no mention of `ToolMeta`/`tool_registry`/
   `dispatch_tool`/`action_validator`/`_EVIDENCE_VALIDATORS` anywhere in
   this document.
2. **unchanged-tests evidence:** none of
   `test_bug_canonical_tool_wiring.py`/`test_a32_enforcement.py`/
   `test_c53a.py` are referenced by Section 7's proposed tests.
3. **no-new-coupling evidence:** the proposed Consumption Ledger/checklist
   mechanism has no dependency on the tool-dispatch pipeline — it is an
   investigation-discipline mechanism, not an execution-evidence mechanism
   (that remains RP4/RP5/A32's job, explicitly out of scope here).

### Layer 4 — Durable Atomic Approval (ActionContract/ActionGateway)
**touched: indirectly, by reference/deference only — not redefinition.**
- **input impact:** Section 4's owner-approved trigger rule for mandatory
  independent review references a production claim and "a layer/decision
  `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` already gates" as an escalation
  input — it consumes Layer 4's existing authority as a trigger condition;
  it does not define new Layer 4 semantics. The waiver-approval and
  waiver-expiry rules (Section 4) are likewise process controls over the
  ledger itself, not new Layer 4 semantics.
- **output impact:** none — no proposed change to `ActionContract`,
  `ActionGateway`, `ExecutionLedger`, or any of their outputs.
- **authority impact:** **none.** The whole design explicitly defers to
  `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`'s own gate rather than creating a
  competing one; Section 6's "False sense of security" caveat and the
  Explicit Non-Goals both state this mechanism proves process compliance,
  never a completion/production claim, and the 3 real defects the pilot
  found in this territory (BUG-150, BUG-130/BUG-140, the ActionGateway
  fail-open) are explicitly listed as untouched.
- **shared identifiers:** none created; `ActionContract`/`ActionGateway`
  are named only in Section 4's trigger rule as a reference to the
  existing gate, never redefined.
- **invariants:** none asserted.
- **failure semantics:** n/a.
- **observability:** none added.
- **cross-layer tests:** n/a — no runtime code proposed.

### Cross-Cutting Guard — RP5 Evidence Finalization
**applies: no.** `rp5_evidence_mismatch` is named in Section 1 only as
narrative evidence of the 28/07 pilot's own finding (the third
evidence-shadow layer miss). The proposed mechanism does not touch
`core/turn_evidence.py`, `core/anti_hallucination.py`, or
`core/last_tool_result_shadow.py`.

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
- No claim that the cross-platform path-validation fix, the
  `on_main_history`/`at_origin_main_tip` provenance split, or the
  `FEATURE_AUTO_CAPTURE` catalog entry are closed **by this PR** — all
  three are real code, now merged to `main` via the separate, independent
  PR #489, not by anything in PR #488 or this document.
- No PR implementing any part of Sections 5–8 until this corrected
  planning PR is itself reviewed and merged — Section 9's owner-decisions
  are resolved and the parallel, independent Codex audit has been received
  and checked (merged as PR #489), but that does not itself authorize
  implementation; the review-and-merge step is still required, per
  explicit instruction for this planning cycle.
