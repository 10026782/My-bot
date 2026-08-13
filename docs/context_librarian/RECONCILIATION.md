# Context Librarian: automatic reconciliation

Replaces manual, per-cycle "run refresh-after-merge --check, hand-classify
every blocker" with a bounded, three-outcome engine
(`tools/context_librarian/reconcile.py`) that reuses previously-approved
classification decisions instead of re-asking the same architectural
question every time `main` advances.

**This module never makes a semantic authority decision on its own.** It
only ever (a) mechanically reuses a decision an owner already wrote into
`docs/context_librarian/policies/policy_registry.json`, (b) reports
mechanical provenance drift on already-registered nodes, or (c) reports
what still needs a human. See `tools/context_librarian/reconcile.py`'s
module docstring for the same guarantee stated in code.

## A. Provenance: three fields, not one

`last_verified_commit` keeps its exact current meaning and both of its
existing writers, untouched:

- `librarian.refresh_after_merge(write=True)` (the authoritative CI/post-
  merge path, `refresh-after-merge --write`)
- the local `.githooks/post-merge` hook, via
  `tools/context_librarian/refresh_after_merge.py --apply`

Two new, purely additive, optional node fields sit alongside it — no
migration needed, nothing existing changes behavior:

- **`last_observed_commit`** — mechanical only. The last commit
  `reconcile.py` scanned this node against. Safe to auto-update on every
  reconcile run; carries zero semantic weight.
- **`last_semantic_review_commit`** — manual only. A human explicitly
  re-examined this node's authority/ownership boundary as of this commit.
  Nothing writes it automatically; set it the same way `last_verified_commit`
  is hand-edited today when registering or re-confirming a decision node.

Why not rename `last_verified_commit` itself into these two concepts? It
already has two independent, separately-tested writers (the CI write-path
and the local git hook). Retargeting either would ripple through both
modules' test suites for a marginal conceptual gain; adding two new
optional fields gets the same separation with zero blast radius.

**`reconcile.py` never reads `last_verified_commit` as its freshness gate.**
The first cut of this engine reused `librarian.refresh_proposal()` directly,
which meant its "mechanical drift" and "new source" outputs were still
secretly anchored on `last_verified_commit` — defeating the whole point of
the split above. Corrected model:

- **Node-level mechanical drift** (`reconcile()`'s `mechanical_updates`) is
  computed against each node's *effective observation baseline* —
  `last_observed_commit` if the node has ever been stamped, otherwise
  `last_verified_commit` as a one-time migration default for a
  never-observed node. Once a node has an `last_observed_commit`, it is
  used exclusively; advancing `last_verified_commit` (a semantic review)
  never demotes or resets it, and advancing `last_observed_commit` (a
  mechanical scan) never touches `last_verified_commit`.
- **New-source discovery** is anchored on a separate, repo-level mechanical
  marker — `last_source_scan_commit` — described in section B.1, not on any
  node's `last_verified_commit` at all.

Invariant this buys: after `apply_auto_maintenance()` advances a drifted
node's `last_observed_commit` to `main`'s current SHA, reconciling that
exact same SHA again returns zero drift for that node — across two
completely separate load/reconcile invocations, matching how the real CLI
runs as a fresh process each time (`test_apply_auto_then_reconcile_is_clean_on_reload`
in `test_reconcile.py`).

## A.1 New-source scan baseline

`docs/context_librarian/reconciliation_state.json`
(`tools/context_librarian/reconciliation_state.py`) holds exactly one
mechanical field: `last_source_scan_commit`. It is the *only* anchor
`reconcile()` uses to decide "what files were added since we last looked"
— never the per-node `last_verified_commit` anchors
`librarian.discover_new_sources()` uses for its own (older, still-supported
as a one-time migration fallback only) computation.

- **Migration fallback**: if `last_source_scan_commit` is `null` (a repo
  that has never run `--apply-auto`), `reconcile()` falls back to
  `librarian.discover_new_sources()`'s existing anchor logic for that one
  scan. The moment `apply_auto_maintenance()` runs once, this field is set
  and every subsequent scan uses it exclusively.
- **Only writer, only on a clean window**: `apply_auto_maintenance()` is the
  sole writer, and it only ever runs when `reconcile()`'s outcome is
  `AUTO_MAINTENANCE_REQUIRED` — which, by construction, never coexists with
  a non-empty `decision_queue`. So a SHA is recorded as scanned only after
  every new source discovered in that window was either non-blocking or
  successfully auto-registered. An unresolved `OWNER_DECISION_REQUIRED` item
  keeps the baseline exactly where it was, so the next scan re-discovers it
  (and everything since) rather than silently skipping past it.
- Once a SHA has been recorded as scanned, reconciling that exact SHA again
  finds zero newly-added files by construction (`git diff --diff-filter=A`
  between an unchanged base and target is empty) — the same SHA can never
  make the same sources reappear as "new".

## B. Policy registry

`docs/context_librarian/policies/policy_registry.json`
(`docs/context_librarian/schema/policy_schema.json`), loaded by
`tools/context_librarian/policy_registry.py`. Each policy is one
already-approved source class:

| id | what it covers | eligible_target | target_field | auto? |
|---|---|---|---|---|
| `DOCUMENTATION_REFERENCE_ASSET` | inert raster images under `docs/` | — | — | no |
| `STAGING_VERIFICATION_F15` | `scripts/verify_f15_staging.py` (exact file) | `decision.f15_staging_verification_artifact` | `test_paths` | yes |
| `STAGING_VERIFICATION_APPROVALS_BUG_FAMILY` | `scripts/verify_bug157_160_163_staging.py`, `scripts/verify_bug161_162_callback_staging.py` | `layer.approvals` | `test_paths` | yes |
| `STAGING_VERIFICATION_TURN_COORDINATOR` | `scripts/verify_tc8_staging.py`, `scripts/verify_tc9_staging.py` | `layer.turn_coordinator` | `test_paths` | yes |
| `TEST_SUPPORT_ARTIFACT` | `*_test_repo_stub.py` fixture helpers | — | — | no |
| `SHARED_UI_PRIMITIVE` | `tma-frontend/src/components/ui/*.tsx` | `decision.tma_shared_ui_primitives` | `code_paths` | no |
| `CROSS_LAYER_SUPPORTING_METADATA` | `domain_utils.py` (exact path) | `decision.business_domain_vocabulary` | `code_paths` | yes |
| `OFFLINE_RESEARCH_TOOL` | `scripts/research_crawler_poc/*`, `contact_merge.py`, `scripts/classify_contacts_for_airtable.py` | `decision.offline_research_support_tool` | `code_paths` | yes |
| `EXTERNAL_RECOMMENDATION_CATALOG` | `business_tool_registry.py` | `decision.external_business_tool_recommendation_catalog` | `code_paths` | yes |
| `EXTERNAL_RECOMMENDATION_CATALOG_TEST` | `test_business_tool_registry.py` | `decision.external_business_tool_recommendation_catalog` | `test_paths` | yes |

**Verification CLASS vs. registration OWNER/TARGET (correction, Message D
item 4):** the first cut of this registry had one `STAGING_VERIFICATION_ARTIFACT`
policy matching the whole `scripts/verify_*_staging.py` naming convention and
routing every match to the same F15 target — semantically wrong, since "is a
bounded staging verification script" (a reusable *class*) says nothing about
*which* layer a given script's evidence belongs to (a per-file *ownership*
fact). The registry now has one narrow, exact-file (or exact-family) policy
per real ownership decision an owner actually made — `STAGING_VERIFICATION_F15`,
`STAGING_VERIFICATION_APPROVALS_BUG_FAMILY`, `STAGING_VERIFICATION_TURN_COORDINATOR`
— and **no catch-all**. A brand new `scripts/verify_<x>_staging.py` matches
none of these three and correctly falls through to `OWNER_DECISION_REQUIRED`
with no `policy_id` at all, rather than being silently (and wrongly) assigned
to F15. When an owner resolves that decision and the target generalizes to a
reusable family, the same PR adds a new named family policy (per section E)
— it does not widen an existing family's glob.

Matching is **glob-only** (`fnmatch` against the full repo-relative path) —
never substring/keyword matching against arbitrary path text. That
distinction is exactly what the `docs/ux/reference-evidence/*` STOP false
positive (fixed alongside this in `classify_new_sources()`) was: an
`_AUTHORITY_TERMS` word matching a directory name by coincidence. A policy
can only ever fire for a path that matches a pattern an owner explicitly
wrote down.

**Multiple-match ambiguity**: if a path matches more than one policy and
those policies disagree on `(eligible_target, target_field)`,
`reconcile()` treats it as unresolved (`OWNER_DECISION_REQUIRED`,
no `policy_id`) rather than silently picking the first match — see
`_resolve_policy()` in `reconcile.py`. Two overlapping policies that happen
to agree on the exact same target are treated as a single unambiguous
match; today's registry has no overlapping patterns at all, so this only
matters as a structural guarantee, tested with a synthetic pair of
conflicting policies.

Each policy declares `auto_registration_allowed` **and** an explicit
`target_field` (`code_paths` or `test_paths`, required whenever
`eligible_target` is set, `null` when it is not) — `target_field` is never
inferred from a `test_`-prefixed filename or any other path convention.
When `auto_registration_allowed` is `true`, a match is mechanically safe to
register into `eligible_target`'s declared `target_field` without a fresh
human decision, **provided `eligible_target` is a catalog node that
actually exists** (see A.2 registration rule below) — a policy referencing
a not-yet-created node (e.g. `decision.business_domain_vocabulary`, not
created by any PR as of this writing) still routes its matches to
`OWNER_DECISION_REQUIRED`, pre-labelled with a clear "target does not exist
yet" note, rather than being silently trusted. When `auto_registration_allowed`
is `false` (e.g. `SHARED_UI_PRIMITIVE`), the pattern only narrows *where to
look* — a human still confirms the specific file actually meets the
policy's stated characteristics (e.g. "no fetch/API/state") before it's
registered.

### A.2 Real auto-registration

`apply_auto_maintenance()` is the only function that ever adds a path to a
node's `code_paths`/`test_paths`, and only for items already routed into
`reconcile()`'s `auto_maintenance_sources` — which by the time they reach
that list have already passed every one of: classification isn't `STOP`;
policy matched unambiguously; `auto_registration_allowed` is `true`;
`eligible_target` exists as a loaded catalog node; `target_field` is a real,
declared, non-inferred field; **the policy's structural/content predicate
(section E.1) returned `True`** — a glob match alone is never sufficient.
At apply time it additionally: skips a path already present (idempotent
no-op), deterministically sorts/dedupes the plan, records full
classification provenance for every newly-registered path, and
reloads+validates the catalog after writing. `--apply-auto`'s CLI handler
then reruns `reconcile()` against the freshly mutated tree and refuses to
exit 0 unless that second pass is `CLEAN` — the workflow in section D only
ever opens a PR after this second-pass check has already passed inside the
CLI call itself.

## C. Three outcomes

`reconcile()` replaces the old binary `OK`/`CHANGES_REQUIRED` with:

- **CLEAN** — nothing pending.
- **AUTO_MAINTENANCE_REQUIRED** — only mechanical provenance drift and/or
  policy-pre-approved (auto_registration_allowed) registrations remain.
  Automation may prepare a patch; it must never push it to `main` or merge it.
- **OWNER_DECISION_REQUIRED** — at least one source is neither mechanical
  nor policy-pre-approved. Automation must never guess this one; unknown
  runtime code always fails into this state.

`OWNER_DECISION_REQUIRED` always wins over `AUTO_MAINTENANCE_REQUIRED` when
both are present, so the decision queue is never silently hidden behind a
green "just maintenance" status.

One structural guarantee worth calling out: a `STOP` classification (the
authority-term escalation) is **never** eligible for
`AUTO_MAINTENANCE_REQUIRED`, regardless of whether some policy's glob
happens to match it — enforced in code, not left to registry-authoring
discipline (see `test_authority_named_path_never_auto_approved_even_with_hypothetical_policy_match`
in `test_reconcile.py`).

## D. Post-merge automation

`.github/workflows/context-librarian-reconcile.yml`, triggered on every
push to `main`, is split into two jobs by privilege (Message D correction,
item 6):

- **`check`** — `permissions: contents: read`, checkout with
  `persist-credentials: false`. Runs `reconcile --check` and reports the
  outcome. Cannot push or open a PR under any circumstance, even if the
  classification path itself misbehaved.
- **`prepare-maintenance-pr`** — only runs when `check`'s outcome is
  `AUTO_MAINTENANCE_REQUIRED`; only this job is granted
  `contents: write` / `pull-requests: write`.

Outcome handling:

- `CLEAN` → no-op (only `check` runs).
- `AUTO_MAINTENANCE_REQUIRED` → an **idempotency guard** first checks
  whether `context-librarian/auto-maintenance-<sha>` already exists on
  `origin` (a prior run for this exact SHA); if so, it skips entirely. If
  not, `reconcile --apply-auto` runs, a maintenance branch is created from
  the now-mutated tree and pushed, and a PR is opened only if one for that
  branch isn't already open (`gh pr list` check before `gh pr create`).
  **Never pushes to `main` directly, never merges** — the PR needs the same
  human review/merge as any other change. A workflow-level `concurrency`
  group additionally prevents two runs from racing each other.
- `OWNER_DECISION_REQUIRED` → opens no PR. Prints the compact decision
  queue to the job summary and fails the `check` job so it stays visible.

**Workflow-order correction (item 5):** the first cut of this workflow ran
`git checkout -b "$branch"` *before* `reconcile --apply-observed` — but
that writer's safety check requires the checked-out branch to literally be
named `main`, so it always failed once already on a feature branch. The new
`--apply-auto` entry point uses a different, CI-appropriate invariant
instead — **HEAD equals the canonical main SHA this result was computed
against, plus a clean working tree** — and the workflow now applies it
*before* creating the maintenance branch, matching that invariant exactly:
`reconcile --apply-auto` runs first (HEAD is still the plain pushed `main`
SHA at that point), *then* `git checkout -b "$branch"` picks up the
already-mutated tree.

`ci.yml`'s own gate (`Context Librarian authoritative post-merge
reconciliation`) now runs the same `reconcile --check` and only fails on
`OWNER_DECISION_REQUIRED` — an unrelated `main` advance, an inert doc/image,
or a source matching an already-approved policy class no longer fails CI by
themselves.

**Standing-automation note:** `prepare-maintenance-pr` is granted
`contents: write` / `pull-requests: write`, but only conditionally (it
never even runs on `CLEAN`/`OWNER_DECISION_REQUIRED`) and only after
`check` has already run read-only in a separate job. That's a new,
always-on capability once this file is merged to `main` — review the
permission grant before merging, same as any other new CI automation with
write access.

## E. Decision learning

`OWNER DECIDES A CLASS ONCE. THE SYSTEM REUSES THAT DECISION
DETERMINISTICALLY.`

Converting a resolved `OWNER_DECISION_REQUIRED` item into a reusable policy
is a semantic call — generalizing "this one file is fine" into "this whole
class of file is fine" is exactly the kind of authority decision this
system is designed to never make on its own. So the mechanical guarantee
and the semantic step are split:

- **Mechanical (code-enforced):** once a path is registered (added to any
  node's `code_paths`/`test_paths`), `_catalog_referenced_paths()` already
  excludes it from `new_sources` forever — it cannot reappear in a future
  decision queue no matter how many times `main` advances (see
  `test_registered_path_never_reappears_as_new_source`).
- **Semantic (human, process rule):** when resolving an `OWNER_DECISION_REQUIRED`
  item, if the decision generalizes beyond the single file, the same PR
  should add or extend a `policy_registry.json` entry with a glob pattern
  covering the class. The next instance of that class then classifies
  deterministically as `AUTO_MAINTENANCE_REQUIRED` instead of reopening the
  same question.

## E.1 Continuous revalidation and registration provenance (Message E correction)

**`REGISTRATION IS NOT PERMANENT PROOF.`** A first cut of this engine
recorded a path once and never looked at it again — a policy that was
correct on the day of registration could silently stop being true (a file
edited to add dispatch/execution wiring, a policy predicate tightened) and
the catalog would keep treating the old registration as valid forever. The
corrected model:

`OWNER DECIDES THE SEMANTIC CONTRACT. AUTOMATION REUSES IT ONLY WHILE ITS
PROOF STILL HOLDS. AUTO MAY REUSE A DECISION. AUTO MAY NOT PRESERVE A
DECISION AFTER ITS PROOF NO LONGER HOLDS. POLICY CHANGE REVALIDATES HISTORY.`

**Policy != path glob.** A policy's `path_patterns` is candidate selection
only. Every `auto_registration_allowed=true` policy must additionally have
a deterministic structural/content predicate registered in
`tools/context_librarian/policy_validators.py`
(`policy_registry.py`'s loader refuses to load the registry otherwise) —
"path match alone" is never sufficient to auto-register runtime-consumed
code. Predicates check real wiring (does `tools/dispatcher.py`/`app.py`
ever reference this module by name?), not vocabulary (a bounded staging
verification script legitimately mentions `ActionGateway` — that's its
whole purpose, not an authority grant, so predicates never reject on
keyword presence alone for that class). A predicate that cannot be
evaluated (unreadable file, no registered predicate for the policy id)
returns `None`, which every caller treats identically to `False` — fail
closed on validator uncertainty, never infer purity from filename,
directory, naming convention, or the mere fact of a prior registration.

**Classification provenance.** `docs/context_librarian/reconciliation_state.json`'s
`auto_registrations` map records, per auto-registered path: `policy_id`,
`policy_version`, `classification_mode` (currently always `"AUTO"`),
`validated_at_commit`, `content_hash` (sha256 of the file's bytes),
`validator_version` (`policy_validators.VALIDATOR_VERSION`), `target_node`,
`target_field`. Nothing is ever registered without this record — it is what
makes the decision explainable and reproducible after the fact, and what
the revalidation pass below diffs against.

**Continuous revalidation, every `reconcile()` call.** `_scan_auto_registrations()`
re-derives the current content hash for every path in `auto_registrations`
and compares it (plus the matching policy's current `policy_version` and
`policy_validators.VALIDATOR_VERSION`) against the stored record:

- **Unchanged** (hash, policy_version, and validator_version all still
  match): skipped — no I/O beyond the hash, no predicate re-run.
- **Changed but the current predicate still passes**: a mechanical
  *refresh* — the exact same approved contract, freshly re-proven. Safe for
  `apply_auto_maintenance()` to persist a fresh provenance record. This
  never touches `last_semantic_review_commit`: passing revalidation proves
  "this source still satisfies its previously-approved contract", never
  "the architectural contract itself was semantically re-approved" — that
  distinction is exactly why those two concepts have separate fields (see
  section A).
- **Changed and the current predicate now fails**: `STALE_REVALIDATION_REQUIRED`.
  Never silently re-approved, never silently deleted — the path stays
  registered (quarantined) and the flag forces `reconcile()`'s outcome to
  `OWNER_DECISION_REQUIRED` with the previous policy, the failed predicate,
  the commit the change was observed at, and the current target, so an
  owner has everything needed to resolve it without re-deriving it.

Because every already-registered path is rescanned on every call (not just
newly-touched ones), a `policy_version` bump on any policy is caught
automatically for **every** path ever registered under it the very next
time `reconcile()` runs — `POLICY CHANGE REVALIDATES HISTORY`, not only
future matches. `VALIDATOR_VERSION` gives the same guarantee when a
predicate function's own logic changes without a `policy_version` bump.

**Revocation states.** For an existing auto-classified entry: `VALID`
(nothing surfaced — either unchanged, or changed-and-refreshed) or
`STALE_REVALIDATION_REQUIRED` (surfaced in `revalidation_flags`, forcing
`reconcile()`'s outcome to `OWNER_DECISION_REQUIRED`). There is no
automatic third "delete/revoke" action — quarantine-and-report only; an
owner decides whether to fix the source, re-scope the policy, or manually
remove the registration.

## Worked example

`reconcile --check` against `origin/main` today, on this branch (based on
plain `main`, independent of PR #628's not-yet-merged registrations) shows
the corrected engine behaving honestly rather than optimistically:

- `business_tool_registry.py`, `domain_utils.py`, and
  `scripts/research_crawler_poc/crawl.py` each match their policy
  (`EXTERNAL_RECOMMENDATION_CATALOG`, `CROSS_LAYER_SUPPORTING_METADATA`,
  `OFFLINE_RESEARCH_TOOL`) but their `eligible_target` decision nodes
  (`decision.external_business_tool_recommendation_catalog`,
  `decision.business_domain_vocabulary`,
  `decision.offline_research_support_tool`) do not exist as loaded catalog
  nodes on this branch yet — so each lands in the decision queue,
  pre-labelled with its policy id *and* an explicit "target does not exist
  yet" note, instead of being wrongly claimed as `AUTO_MAINTENANCE_REQUIRED`.
  This is exactly the failure mode item 3's "target node exists" gate
  exists to catch — PR #628 (once merged and this branch rebased onto it)
  creates the first two of these three nodes; `decision.business_domain_vocabulary`
  is not created by any current PR and stays a genuine open decision either way.
- `scripts/verify_tc8_staging.py` / `verify_tc9_staging.py` are already
  registered (in both `layer.approvals` and `layer.turn_coordinator`), so
  they never appear as new sources at all — `STAGING_VERIFICATION_TURN_COORDINATOR`
  exists purely for traceability/precedent, per section B.
- `scripts/verify_bug157_160_163_staging.py` and
  `scripts/verify_bug161_162_callback_staging.py` are, in fact,
  **unregistered today** despite the first draft of this registry claiming
  otherwise (item 4's correction) — `STAGING_VERIFICATION_APPROVALS_BUG_FAMILY`
  now matches them and their target (`layer.approvals`) genuinely does
  exist, so they classify as real `AUTO_MAINTENANCE_REQUIRED` items ready
  for `--apply-auto` to register into `layer.approvals.test_paths`.
- A hypothetical brand-new `scripts/verify_somethingnew_staging.py` matches
  none of the three staging-verification family policies and correctly
  requires a fresh `OWNER_DECISION_REQUIRED` — no `policy_id` at all — per
  item 4's "no catch-all" correction.
- The 4 `tma-frontend/src/components/ui/*.tsx` primitives and
  `tc8_test_repo_stub.py` land in the decision queue *pre-labelled* with
  their matching policy and target node (a one-line confirmation, not a
  fresh investigation) — unchanged from the original design.
- Everything else genuinely unclassified (e.g. `marketing_orchestrator.py`,
  which predates any policy for its class) still correctly requires a real
  owner decision.

Run `python -m tools.context_librarian reconcile --check --main-ref origin/main`
for the exact current numbers on any given day — this section describes the
*shape* of the output, not a frozen snapshot.
