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
  `reconcile.py`'s `stamp_observed()` scanned this node against. Safe to
  auto-update on every reconcile run; carries zero semantic weight.
- **`last_semantic_review_commit`** — manual only. A human explicitly
  re-examined this node's authority/ownership boundary as of this commit.
  Nothing writes it automatically; set it the same way `last_verified_commit`
  is hand-edited today when registering or re-confirming a decision node.

Why not rename `last_verified_commit` itself into these two concepts? It
already has two independent, separately-tested writers (the CI write-path
and the local git hook). Retargeting either would ripple through both
modules' test suites for a marginal conceptual gain; adding two new
optional fields gets the same separation with zero blast radius.

## B. Policy registry

`docs/context_librarian/policies/policy_registry.json`
(`docs/context_librarian/schema/policy_schema.json`), loaded by
`tools/context_librarian/policy_registry.py`. Each policy is one
already-approved source class:

| id | what it covers | eligible_target |
|---|---|---|
| `DOCUMENTATION_REFERENCE_ASSET` | inert raster images under `docs/` | — (no node needed) |
| `STAGING_VERIFICATION_ARTIFACT` | `scripts/verify_*_staging.py` | `decision.f15_staging_verification_artifact` |
| `TEST_SUPPORT_ARTIFACT` | `*_test_repo_stub.py` fixture helpers | — (per-file judgment) |
| `SHARED_UI_PRIMITIVE` | `tma-frontend/src/components/ui/*.tsx` | `decision.tma_shared_ui_primitives` |
| `CROSS_LAYER_SUPPORTING_METADATA` | `domain_utils.py` (exact path) | `decision.business_domain_vocabulary` |
| `OFFLINE_RESEARCH_TOOL` | `scripts/research_crawler_poc/*`, `contact_merge.py`, `scripts/classify_contacts_for_airtable.py` | `decision.offline_research_support_tool` |
| `EXTERNAL_RECOMMENDATION_CATALOG` | `business_tool_registry.py` | `decision.external_business_tool_recommendation_catalog` |

Matching is **glob-only** (`fnmatch` against the full repo-relative path) —
never substring/keyword matching against arbitrary path text. That
distinction is exactly what the `docs/ux/reference-evidence/*` STOP false
positive (fixed alongside this in `classify_new_sources()`) was: an
`_AUTHORITY_TERMS` word matching a directory name by coincidence. A policy
can only ever fire for a path that matches a pattern an owner explicitly
wrote down.

Each policy declares `auto_registration_allowed`. When `true`, a match is
mechanically safe to register into `eligible_target`'s `code_paths`/
`test_paths` without a fresh human decision (e.g. a new
`scripts/verify_<x>_staging.py`). When `false` (e.g.
`SHARED_UI_PRIMITIVE`), the pattern only narrows *where to look* — a human
still confirms the specific file actually meets the policy's stated
characteristics (e.g. "no fetch/API/state") before it's registered.

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
push to `main`, runs `reconcile --check` and branches on the outcome:

- `CLEAN` → no-op.
- `AUTO_MAINTENANCE_REQUIRED` → pushes a **new** branch
  (`context-librarian/auto-maintenance-<sha>`) containing only a
  `--apply-observed` mechanical provenance commit, and opens a PR against
  `main` via `gh pr create`. **Never pushes to `main` directly, never
  merges** — the PR needs the same human review/merge as any other change.
- `OWNER_DECISION_REQUIRED` → opens no PR. Prints the compact decision
  queue to the job summary and fails the job so it stays visible.

`ci.yml`'s own gate (`Context Librarian authoritative post-merge
reconciliation`) now runs the same `reconcile --check` and only fails on
`OWNER_DECISION_REQUIRED` — an unrelated `main` advance, an inert doc/image,
or a source matching an already-approved policy class no longer fails CI by
themselves.

**Standing-automation note:** the new workflow is granted
`contents: write` / `pull-requests: write` so it can push its own branch
and open its own PR. That's a new, always-on capability once this file is
merged to `main` — review the permission grant before merging, same as any
other new CI automation with write access.

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

## Worked example

Running `reconcile --check` against `origin/main` today (before the 3
owner-decision catalog registrations in PR #628 land) already shows the
policy layer working end-to-end on real data:

- `business_tool_registry.py`, `domain_utils.py`,
  `scripts/research_crawler_poc/crawl.py`, and all three existing
  `scripts/verify_*_staging.py` scripts classify as
  `AUTO_MAINTENANCE_REQUIRED` via policy match.
- The 4 `tma-frontend/src/components/ui/*.tsx` primitives and
  `tc8_test_repo_stub.py` land in the decision queue *pre-labelled* with
  their matching policy and target node (a one-line confirmation, not a
  fresh investigation).
- Everything else genuinely unclassified (e.g.
  `marketing_orchestrator.py`, which predates any policy for its class)
  still correctly requires a real owner decision.
