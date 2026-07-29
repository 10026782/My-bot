# FIRST_REAL_CONSUMPTION_PILOT.md — Context Librarian Consumption Enforcement, first real pilot

**Status:** PREPARED, NOT RUN. This document defines the pilot; it does not claim the pilot happened, passed, or failed. No task has yet consumed a bundle end-to-end through `build → checklist → ledger → verify-consumption`.
**Owner:** אליהו.
**Scope:** Phase 1 (self-attested Consumption Ledger, machine-verified for accounting completeness) only. Phase 3 (CI-blocking gate) is **not** activated by this document or by running this pilot.
**Depends on:** `docs/context_librarian/CONSUMPTION_ENFORCEMENT_PLAN.md` (the approved design), `docs/context_librarian/AGENT_CONSUMPTION_CONTRACT.md` (the bundle-consumption contract this layers on top of), `docs/governance/BOSS_BUSINESS_INTENT.md` (what the pilot task itself is scoping against), `AGENTS.md`'s Context Librarian bootstrap section.

---

## 0. Why this document exists

PR #490 (`feat(context-librarian): Consumption Enforcement Phase 1`, merged `7ee5c5b`) implemented the entire mechanism `CONSUMPTION_ENFORCEMENT_PLAN.md` §5 designed: the `## Consumption Checklist` bundle section, `consumption_checklist()`, the Consumption Ledger schema, `verify_consumption()`, and the `verify-consumption` CLI subcommand — backed by 112 passing tests in `test_context_librarian.py` (verified directly in this session, §1 below).

That code has never been exercised on a real task. Every ledger in the test suite is synthetic, built by a test fixture, not by an agent actually reading a bundle and doing work. **Do not read PR #490's tests as proof the workflow itself has been piloted** — they prove the mechanism is internally correct, not that it is usable end-to-end by an agent under real task pressure. This document defines that first real run.

---

## 1. Audit of what already exists (verified this session, against `main`/current branch)

This section is the literal answer to the "document precisely" requirement — every claim below was directly re-verified in this session by reading the source or executing the command, not inferred from `CONSUMPTION_ENFORCEMENT_PLAN.md`'s own (partly stale) status header.

| Question | Answer | Evidence |
|---|---|---|
| Is Phase 1 implemented? | **Yes, fully**, contrary to `CONSUMPTION_ENFORCEMENT_PLAN.md`'s top-of-file `STATUS` line, which is stale (written before PR #490 merged and never updated after). | `git log --oneline -- tools/context_librarian/librarian.py` shows `7ee5c5b feat(context-librarian): Consumption Enforcement Phase 1 (N17 item 10) (#490)`, after `abf2804` (the planning-only PR). `consumption_checklist()` and `verify_consumption()` exist in `tools/context_librarian/librarian.py`. |
| What is the build command? | `python -m tools.context_librarian build --task-type <profile_id> --query "<text>" [--output <path>] [--production-claim] [--verified-production-evidence <path>] [--assert-on-main-history\|--assert-at-origin-main-tip\|--assert-main]` | `tools/context_librarian/__main__.py:29-60`; executed live this session (see §5). |
| What is the input? | A profile id (one of `approval_ux`, `tool_execution`, `turn_coordinator_routing`, `core_reasoning_change`, `rp5_evidence_mismatch`, `ux_f52_message`, `cross_layer_architecture`) plus a free-text query. The query only ranks/enables already-allowed nodes; it cannot pull in excluded layers or drop mandatory ones. | `docs/context_librarian/task_profiles/profiles.json`; `docs/context_librarian/README.md` §"Selection model". |
| What is a bundle? | A deterministic Markdown document: provenance, Agent Consumption Contract pointer, **Consumption Checklist** (new in Phase 1), Agent Workflow Gate, canonical decisions, selected layers, canonical documents, code, tests, production evidence, feature flags, freshness, traversed edges. | `tools/context_librarian/librarian.py::_render()`, confirmed by direct execution (§5). |
| What is the checklist? | `consumption_checklist(catalog, profile, production_claim)` — item ids in the form `code:<path>`, `test:<path>`, `doc:<path>`, `decision:<id>`, `expansion:<path>#<anchor>`, and `evidence:<path>` (only with `--production-claim`). Deterministic, sorted, and **already rendered inline in the bundle** under `## Consumption Checklist` — an agent does not need a separate tool call to see it. | `tools/context_librarian/librarian.py:792-843` (function), `:1336-1352` (bundle rendering). |
| How is a ledger created? | **Manually, by the agent, as a JSON file** — there is no `python -m tools.context_librarian scaffold-ledger` command. The agent copies the exact item ids printed under the bundle's `## Consumption Checklist` section into the ledger's `required_sources` field, then adds one `review_receipts` or `waived_sources` entry per item as it actually consumes (or waives) that source. | `docs/context_librarian/CONSUMPTION_ENFORCEMENT_PLAN.md` §5.2 (schema); confirmed no scaffold subcommand exists in `tools/context_librarian/__main__.py`. |
| What does `verify-consumption` check? | Fail-closed: every `required_sources` item has exactly one `review_receipts`/`waived_sources` entry; every entry has non-empty `reason`/`evidence_reference`/attribution fields and an `item_id`→`path` match; every waiver has a **distinct** `approved_by` ≠ `reviewed_by` and is not placeholder-worded; the ledger's declared `required_sources` matches a **live-recomputed** `consumption_checklist()` for the same profile+production-claim; the ledger's top-level `commit`/`branch`/`profile`/`query` matches the actual current checkout, and every entry's own identity fields match the ledger's top-level identity. Duplicate boilerplate `reason`/`evidence_reference` across items is a non-blocking `WARNING`, not a failure. | `tools/context_librarian/librarian.py::verify_consumption()` (`:1025-1169`), executed live in this session (§5) for both a passing and a failing ledger. |
| Exit codes? | `0` = `CONSUMPTION: COMPLETE`. `2` = `CONCLUSION_BLOCKED` (any accounting gap, forged field, identity mismatch, or malformed entry) — same convention as every other `context-librarian` fail-closed error (`ContextLibrarianError` also exits `2`). There is no distinct "warning-only" exit code; warnings print alongside a `0` exit. | `tools/context_librarian/__main__.py:105-127`; `ConsumptionVerificationResult.exit_code` (`:918-925`). |
| What is still manual? | (a) Building the ledger JSON by hand from the bundle's printed checklist — no scaffold tool. (b) Deciding, per item, whether it was genuinely reviewed vs. needs a waiver — this is deliberately never automated (Section 4/6 of the plan: self-attestation can never prove truth). (c) The independent-review trigger (production claim / Cross-Layer-Authority-gated layer / any waiver) is **not enforced by any tool** — it is a documented rule an agent must self-apply; nothing blocks a task from skipping it. (d) There was, until this session, no preflight stopping a task from starting "perform the task" before the bundle+ledger-skeleton actually existed — see §7. | `CONSUMPTION_ENFORCEMENT_PLAN.md` §4/§6 (by design); confirmed by grep — no independent-review-trigger check exists anywhere in `librarian.py` or `__main__.py`. |
| Was Phase 1 ever piloted end-to-end? | **No.** `CONSUMPTION_ENFORCEMENT_PLAN.md` §8 Phase 4 explicitly reserves that for later, reusing the 5 tasks from `PHASE1_NON_INFERIORITY_PILOT.md`. That reuse has not happened. The user's own framing for this document (PR2's manual-discipline session did not build a bundle, run `consumption_checklist()`, create a ledger, or run `verify-consumption`) is confirmed correct by this audit — no such artifacts exist anywhere in the repository or its git history for any real task. | `git log --all --diff-filter=A -- '*.ledger.json'` and `find . -name '*ledger*'` (outside `test_context_librarian.py`'s fixtures) both return nothing. |

**Conclusion: the mechanism does not need to be rebuilt.** It is code-complete, tested, and directly executable today. What this document adds is (a) the audit above, (b) a defined pilot task and required sequence, (c) a small, additive, tested preflight gate (§7) so the next task cannot silently skip straight to "perform the task" without the bundle and ledger skeleton actually existing.

---

## 2. Pilot task

**Unify and scope Stages 3–5 of the multi-layer plan (UX Formatter, Turn Coordinator, RP5 evidence finalization) against `docs/governance/BOSS_BUSINESS_INTENT.md`.**

This document does **not** perform that scoping — doing so is explicitly out of scope for this session (governance + tooling readiness only; see the originating task instructions). Identifying the exact source document(s) that number "Stages 3–5" (candidates include `docs/architecture/f52-unified-approval-runtime/rollout/UNIFIED_MESSAGE_IMPLEMENTATION_PLAN.md`'s PR sequence and the four-layer boundary in `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`) and reconciling their numbering **is part of the pilot task itself**, not a prerequisite decided here. The `cross_layer_architecture` profile (see `docs/context_librarian/task_profiles/profiles.json`) is the most likely fit — a change that intentionally spans multiple authority boundaries — but profile selection is never made by this document (see step 2 of the Required Sequence and `AGENT_CONSUMPTION_CONTRACT.md`'s own rule that suggestions are advisory only).

---

## 3. Required sequence

1. Build the context bundle.
2. Inspect the generated bundle.
3. Read the generated consumption checklist (already inline in the bundle — no separate step needed to produce it, see §1).
4. Create the Consumption Ledger skeleton (`required_sources` populated from the checklist; `review_receipts`/`waived_sources` still empty).
5. Perform the task using the bundle.
6. Record consumed and skipped sources (fill in `review_receipts`/`waived_sources` as the task proceeds — every waiver needs a genuine, independent `approved_by`).
7. Run `verify-consumption`.
8. Run an independent review (mandatory here regardless of risk tier — this pilot task both makes a production/architecture claim about a Cross-Layer-Authority-gated area **and** exists specifically to test the mechanism, so the Section 4 trigger rule applies unconditionally for this run).
9. Compare the independent reviewer's findings against the bundle (gold-set style, per `PHASE1_NON_INFERIORITY_PILOT.md`'s existing protocol — reused, not reinvented).
10. Issue a pilot verdict (relevance, coverage, false positives, omissions, overhead, usability, traceability — see §6) and record it as a `## Results` entry appended to **this** document, mirroring `PHASE1_NON_INFERIORITY_PILOT.md`'s own `## Results` convention.

---

## 4. Output artifacts

No new artifact-naming convention is invented here beyond what the existing mechanism and repo conventions already define:

| Artifact | Location / form | Committed? |
|---|---|---|
| Context bundle | `docs/context_librarian/generated/<slug>.md`, produced by `build --output` | No — `docs/context_librarian/generated/*.md` is already git-ignored (disposable navigation artifact, per `README.md`). |
| Source manifest | **Not a separate file.** The bundle's own `## Consumption Checklist` section *is* the manifest — it is the literal, deterministic output of `consumption_checklist()`. Inventing a second file would duplicate a single source of truth in violation of `BOSS_BUSINESS_INTENT.md` §3 ("מקור אמת אחד לכל אחריות"). | N/A |
| Consumption Ledger | `docs/context_librarian/generated/<slug>.ledger.json`, hand-built by the agent per §1/§3 | No — disposable and local by owner decision (`CONSUMPTION_ENFORCEMENT_PLAN.md` §5.2/§9); this session added `docs/context_librarian/generated/*.json` to `.gitignore` (§7) so this is enforced, not just documented. |
| `verify-consumption` result | Captured as command output (`CONSUMPTION: COMPLETE` / `CONCLUSION_BLOCKED` + reasons) and transcribed into this document's `## Results` entry — not committed as a separate file, mirroring how `PHASE1_NON_INFERIORITY_PILOT.md` records raw command output inline rather than as attachments. | Inline in this doc's `## Results` section. |
| Independent review result | Recorded inline in this document's `## Results` entry, following `PHASE1_NON_INFERIORITY_PILOT.md`'s "Per-run records" structure (reviewer identity, gold set, misses found, severity). | Inline in this doc's `## Results` section. |
| Final pilot report | The `## Results` section of **this** document (§10 of the sequence). No separate report file. | Committed as part of this document. |

---

## 5. Runbook — exact commands (verified by direct execution this session)

All commands assume the repository root as the working directory and `python3` (per `AGENTS.md`'s VM guidance).

```bash
# Step 1 (mandatory bootstrap first — see AGENTS.md's Context Librarian
# bootstrap section, not optional for any task in its trigger scope):
python3 -m tools.context_librarian suggest-profile \
  --query "unify and scope stages 3-5 of the multi-layer plan against BOSS_BUSINESS_INTENT.md" \
  --all
# Record: "Selected profile: <profile_id>" — manual choice, not automatic
# (score=0 or a tie is common for a novel cross-layer query and does not by
# itself justify the cross_layer_architecture profile — confirm by judgment).

# Step 1 (build):
python3 -m tools.context_librarian build \
  --task-type <selected_profile_id> \
  --query "unify and scope stages 3-5 of the multi-layer plan against BOSS_BUSINESS_INTENT.md" \
  --output docs/context_librarian/generated/pilot_stage3_5_scoping.md

# Step 2: open and read the file just written in full.

# Step 3: the checklist is the bundle's own "## Consumption Checklist"
# section — no extra command.

# Step 4: hand-build the ledger skeleton (required_sources = the exact item
# ids from step 3, in order; review_receipts/waived_sources start empty):
#   docs/context_librarian/generated/pilot_stage3_5_scoping.ledger.json
# Then confirm steps 1-4 are actually done before proceeding to step 5:
python3 -m tools.context_librarian.pilot_preflight \
  --task-type <selected_profile_id> \
  --bundle docs/context_librarian/generated/pilot_stage3_5_scoping.md \
  --ledger docs/context_librarian/generated/pilot_stage3_5_scoping.ledger.json
# Exit 0 + a line starting "PROCEED:" is required before step 5 begins.

# Steps 5-6: perform the task; as each mandatory source is opened (or
# deliberately waived with independent approval), append a review_receipts
# (or waived_sources) entry to the same ledger file.

# Step 7:
python3 -m tools.context_librarian verify-consumption \
  --task-type <selected_profile_id> \
  --query "unify and scope stages 3-5 of the multi-layer plan against BOSS_BUSINESS_INTENT.md" \
  --ledger docs/context_librarian/generated/pilot_stage3_5_scoping.ledger.json
# Exit 0 + "CONSUMPTION: COMPLETE" is required before treating the ledger as
# accounted-for. Exit 2 + "CONCLUSION_BLOCKED" + reasons means fix the ledger
# (or genuinely go back and consume the missing source) and re-run — it does
# not mean override or skip.

# Steps 8-9: independent review — see docs/context_librarian/PHASE1_NON_INFERIORITY_PILOT.md's
# "Independent Authority Gold Set" protocol; reused verbatim, not redefined here.

# Step 10: append a `## Results` section to this document with the verdict.
```

This session executed the `suggest-profile` and `build` commands live (against `cross_layer_architecture`, a throwaway query, output discarded — not the pilot's own run) purely to confirm the commands above are accurate, not guessed. The bundle rendered its `## Consumption Checklist` section as documented in §1. No ledger was created and no pilot task was performed — this session is preparation only, per its own scope (see the header of this document).

---

## 6. Acceptance criteria the pilot verdict must address

Per the originating instructions, this is a manual, structured Phase 1 pilot — not yet a CI gate (§8). The `## Results` entry (step 10) must speak to each of:

- **relevance** — did the checklist's mandatory tier actually match what the task needed, or did it include clearly immaterial items?
- **coverage** — did the independent reviewer's gold set (step 8) find any mandatory source the checklist should have listed but didn't?
- **false positives** — did the checklist demand review of sources that turned out to be irrelevant to the actual change?
- **omissions** — any mandatory source silently skipped without a receipt or waiver that `verify-consumption` should have caught but didn't (would indicate a real bug in `verify_consumption()`, not just a process gap)?
- **overhead** — how much time/effort did building and maintaining the ledger by hand actually cost, relative to the task?
- **usability** — was the manual ledger-authoring process (§1's documented gap) a meaningful source of friction or error?
- **traceability** — can a third party reconstruct, from the ledger alone, exactly what was reviewed and why?

This mirrors `CONSUMPTION_ENFORCEMENT_PLAN.md` §8's "Acceptance criteria for a new pilot on new tasks" — reused, not redefined.

---

## 7. Preflight

**Implemented, this session, as the smallest safe additive change identified by the audit in §1.**

`tools/context_librarian/pilot_preflight.py` (new file; does not modify `librarian.py`, `__main__.py`, or any of their 112 existing tests) exposes `run_preflight()` / a CLI entry point:

```bash
python3 -m tools.context_librarian.pilot_preflight \
  --task-type <profile_id> \
  [--production-claim] \
  --bundle <path> \
  --ledger <path>
```

It reuses `load_catalog()` and `consumption_checklist()` directly (read-only, no re-derivation of mandatory-tier logic, so it cannot drift from what `verify-consumption` itself computes) to check, before step 5 of §3 may begin:

- the bundle file exists and is non-empty (exit `1` if not);
- the bundle's own title line and `## Consumption Checklist` section are bound to the selected `--task-type` and the **live-recomputed** `consumption_checklist()` output for that profile+claim (exit `1` if not — catches a stale, wrong-profile, or hand-written bundle; fixed post-review, see the `## Post-review corrections` entry below);
- the ledger file exists, is valid JSON, and has every `LEDGER_TOP_LEVEL_REQUIRED_FIELDS` top-level field (exit `2` if not);
- the ledger's declared `task_type`/`production_claim` match the ones passed on the command line, and `required_sources` is a list of strings, not e.g. objects or nested lists (exit `2` if not — the string-type check is also a post-review fix, same entry below);
- the ledger's `required_sources` set exactly equals the same live-recomputed `consumption_checklist()` output (exit `3` if not, printing the missing/extra ids).

Exit `0` prints a line starting `PROCEED:`. This is **not** a replacement for `verify-consumption` (§1/§5) — it only proves the bundle matches the selected profile/live tier and the ledger skeleton is correctly shaped and complete *before* the task starts consuming sources; `verify-consumption` is still required afterward to prove every item ended up with a genuine receipt or approved waiver, checked against exact commit/branch/query identity.

**What this preflight deliberately does not do (Phase 2 follow-up, not implemented here):**

- It is not wired into any hook, CI step, or session-start check — nothing today *forces* an agent to run it. Making it self-enforcing (e.g. a `.claude` hook that blocks tool calls associated with "step 5" until this exits 0) would require new surface area (hook configuration, a way to detect "the task has moved to step 5") outside this session's scope, per the "if it needs a broad change, don't implement it — record as Phase 2" instruction.
- It does not check or enforce the independent-review trigger rule (§1's row "What is still manual? (c)") — that remains a self-applied rule for the next task to honor per §3 step 8.
- **Explicit instruction for the next task:** run the `pilot_preflight` command in §5 manually, by hand, immediately before starting step 5, and paste its output into the eventual `## Results` entry. Do not skip it because no automated hook currently forces it.

### Tests

`test_pilot_preflight.py` (new file, plain-script convention per `CLAUDE.md`, run via `python3 test_pilot_preflight.py`) covers, against real `approval_ux`/`tool_execution` profiles and real bundles produced by `build_bundle()` (no mocking of `librarian.py`):

1. missing bundle → exit `1`;
2. hand-written/fake bundle (non-empty, no real checklist section) → exit `1`;
3. real bundle built for a different profile than `--task-type` → exit `1`;
4. bundle present and valid, ledger missing → exit `2`;
5. ledger present but `required_sources` doesn't match the live-recomputed tier → exit `3`;
6. ledger's declared `task_type` disagrees with `--task-type` → exit `2`;
7. `required_sources` containing a malformed (non-string) entry → exit `2`, does not raise `TypeError`;
8. fully matching skeleton → exit `0` with a `PROCEED:` message;
9. invalid JSON ledger → exit `2` (fails closed, does not crash).

All 11 assertions passed when run in this session (§9), including after the post-review corrections below.

---

## 8. Explicit non-goals for this document and this session

- **Phase 3 (CI-blocking gate) is not activated.** No CI workflow change was made. `verify-consumption` is not called from `.github/workflows/ci.yml`.
- **This pilot has not been run.** No claim is made that Consumption Enforcement has been validated end-to-end, that it works well in practice, or that its overhead is acceptable — §6's criteria are unanswered until step 10 actually happens.
- **Stages 3–5 of the multi-layer plan (UX Formatter, Turn Coordinator, RP5) are not scoped, planned, or implemented by this document.** That is the pilot task itself (§2), reserved for the next session.
- **`CONSUMPTION_ENFORCEMENT_PLAN.md` is not rewritten or reissued.** Its stale top-of-file `STATUS` line (predating PR #490's merge) is flagged here (§1) but left as-is — correcting it is a documentation cleanup outside this session's stated scope (governance + tooling readiness, not plan editing), and it does not block anything: the actual code and tests are the authority, already verified directly.
- **No independent-review trigger enforcement mechanism was built.** Flagged in §1/§7 as a real gap, deferred.

---

## Post-review corrections (CodeRabbit, PR #501)

CodeRabbit reviewed `tools/context_librarian/pilot_preflight.py` and opened two threads, both verified against the actual code in this session and fixed:

1. **Bundle provenance/profile binding (Major).** The original preflight only checked that the bundle file existed and was non-empty — a stale bundle, a bundle built for the wrong profile, or a hand-written file (the review's own example: a file containing just `# fake bundle`) would satisfy the gate and let step 5 begin against context that doesn't actually match the selected task. **Fixed:** `run_preflight()` now also checks the bundle's title line against the exact `# BOSS Context Bundle — <task_type>` format `_render()` produces, and parses the bundle's own `## Consumption Checklist` section, requiring its item-id set to exactly equal the live-recomputed `consumption_checklist()` output for the same profile+production-claim. Both checks fail closed with exit `1`. Regression tests: "hand-written bundle → exit 1" and "wrong-profile bundle → exit 1" in `test_pilot_preflight.py`, using a real second bundle built via `build_bundle(task_type="tool_execution", ...)` rather than a synthetic fixture.
2. **`required_sources` type validation (Major/quick win).** `set(ledger["required_sources"])` was called without first checking that every element was a string; a syntactically valid JSON list containing an object or nested list (e.g. `{}`) is unhashable and raised an uncaught `TypeError` inside `main()`, instead of the documented fail-closed exit `2`. **Fixed:** added `elif not all(isinstance(item, str) for item in required_sources): messages.append(...)`, per CodeRabbit's own suggested diff, before `required_sources` is ever passed to `set()`. Regression test: "malformed required_sources entry does not crash" / "-> exit 2" in `test_pilot_preflight.py`, using `list(live_required) + [{}]` exactly as CodeRabbit's comment requested.

Both findings were real (confirmed by reproducing the crash/gap locally before fixing), not false positives. No other CodeRabbit findings were open on this PR at the time of this correction.

---

## 9. Test results (this session)

```
$ python3 -m pytest test_context_librarian.py -q
112 passed in 1.88s

$ python3 test_pilot_preflight.py
=== pilot_preflight smoke tests ===
  [PASS] missing bundle -> exit 1
  [PASS] hand-written bundle -> exit 1
  [PASS] wrong-profile bundle -> exit 1
  [PASS] missing ledger -> exit 2
  [PASS] required_sources mismatch -> exit 3
  [PASS] task_type mismatch -> exit 2
  [PASS] malformed required_sources entry does not crash
  [PASS] malformed required_sources entry -> exit 2
  [PASS] matching skeleton -> exit 0 (PROCEED)
  [PASS] PROCEED message present
  [PASS] invalid JSON ledger -> exit 2

✅ 11/11 passed
```

Both suites were executed directly in this session against the current branch, not assumed from a prior run.

---

## 10. Results

*(Not yet populated — append here after the pilot task in §2 actually runs, per §3 step 10 and §6.)*
