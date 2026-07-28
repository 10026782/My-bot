# Verification Coverage Model — Plan (N17 item 7)

**Status: planning only. Nothing in this document is implemented.** No code
changed, no catalog node added, no CLI command added. This is the design the
mandatory work order (`ROADMAP.md` N17, step 7) asked for before any
implementation: "לתכנן ... Verification Coverage Model — תכנון בלבד לפני
implementation."

## Problem this would address

Today, "is X verified, and to what degree?" is answered by an agent reading
a node's `status`, `confidence`, `last_verified_commit`, and freshness
output and forming a judgment. That judgment is not recorded anywhere, is
not comparable across nodes, and is not queryable ("which primary-authority
nodes have zero production evidence?" currently requires manually reading
every node). A Verification Coverage Model (VCM) would make that judgment a
deterministic, computed property of the catalog itself — narrowly, for
verification *coverage*, not correctness. It does not judge whether an
engineering decision is right; the existing Quality Metrics section already
carries that caveat and VCM inherits it.

## What VCM would track, per node

All of these are either already computed by `librarian.py` (freshness) or
directly derivable from fields the schema already requires — VCM adds no new
required schema fields, only a derived, computed report:

| Coverage dimension | Derived from | Already computed today? |
| --- | --- | --- |
| Schema conformance | `_validate_node()` — passing `load_catalog()` at all | Yes (fail-closed, not surfaced as a score) |
| Freshness | `_freshness()` — code/test/doc diff since `last_verified_commit` | Yes (per-bundle, not catalog-wide) |
| Production-evidence coverage | `production_evidence` non-empty + status in `QUALIFYING_PRODUCTION_EVIDENCE_STATUSES` | Partial (bundle-scoped `qualifying_production_evidence` count only) |
| Test-path coverage | `test_paths` non-empty, and (new territory) whether those tests currently pass | No — no node today records pass/fail, only paths |
| Authority-level justification | `authority_level` + `source_of_truth.is_authority` consistency (e.g. a `canonical_contract` node should generally have `canonical_docs`, a `planning` node should not claim `is_authority: true`) | No |
| Confidence justification | `confidence` vs. the above four dimensions — is a `0.95` node actually backed by production evidence + passing tests, or is a high number asserted without support? | No |

VCM's output would be a **coverage report**, not a modified node: for every
node, a computed row of the six dimensions above, plus an aggregate score
that is explicitly labeled a coverage proxy (same honesty rule as
`TOKEN_ESTIMATION_BENCHMARK.md` — a computed number is not a correctness
claim).

## How it would be computed (constraints carried over from the librarian itself)

- **Deterministic, no LLM, no embeddings** — same as `load_catalog()`/
  `build_bundle()` today. A coverage score is arithmetic over catalog fields
  and git/test state, not a judgment call.
- **No new runtime, no new source of truth.** VCM reads the catalog and the
  repository (git diffs, test results) exactly the way `_freshness()` reads
  git diffs today. It never writes back to the catalog automatically —
  updating a node's actual metadata stays a reviewed, manual act (per
  `README.md`'s "Adding or changing knowledge").
- **Test-path pass/fail** is the one dimension requiring new machinery: a
  way to run each node's `test_paths` and record pass/fail without turning
  the librarian into a test runner with production-shaped responsibilities.
  Likely shape: a thin wrapper invoking `pytest <paths> --collect-only` (to
  verify the paths still exist and are collectible) plus, optionally, an
  explicit `--run-tests` flag that actually executes them and records
  pass/fail in the coverage report only — never gating `build_bundle()`
  itself, which must stay fast and side-effect-free.
- **New CLI command only, additive to `__main__.py`** — e.g. `python -m
  tools.context_librarian coverage-report`. Does not change `build`,
  `suggest-profile`, or `validate`'s existing behavior or output.
- **Reuses `_freshness()` and `_validate_node()` as-is** rather than
  reimplementing catalog inspection — this plan explicitly rejects building
  a parallel catalog-reading path.

## Relationship to Dogfooding (N17 item 6)

N17 item 6 asks the librarian to eventually hold nodes about its own
components (catalog loader, schemas, profiles, bundle builder, workflow
gate, freshness, token estimation, CI validation). VCM is the mechanism that
would make dogfooding self-answering rather than just self-describing: once
the librarian has nodes for its own components, running `coverage-report`
against those nodes answers "what's built, what's verified, what's missing,
what's next" from the catalog itself, with the same coverage dimensions
applied uniformly to product nodes and to the librarian's own nodes. VCM
should therefore be built generically (works on any node) rather than
specific to product layers, so it needs no rework when dogfooding nodes are
added later.

Both remain planning-only per N17's mandatory work order (step 6 for
Multi-session Coordination is unrelated and separately planned; step 7
covers both VCM and Dogfooding together, and this document is step 7's VCM
half — Dogfooding's own node-authoring work is a separate, later, reviewed
task, not implied or started by this document).

## Explicit non-goals for this document and phase

- No implementation. No code in this PR.
- No new catalog nodes added (dogfooding nodes are a separate future task).
- No new required schema fields — coverage is derived, not stored.
- No automatic writes to node metadata. A human/agent still reviews and
  commits any metadata change, same as today.
- No change to `build_bundle()`'s behavior, budget enforcement, or output
  format.
- No claim that a high coverage score means an engineering decision is
  correct — same caveat the existing Quality Metrics section already states
  for `query_match_precision_proxy` and friends.
- No production verification implied or claimed by this document.

## Open questions for the eventual implementation PR

- Where does the coverage report live — stdout only (like `validate`), or
  also a durable artifact under `docs/context_librarian/generated/` (already
  git-ignored as disposable)?
- Should `--run-tests` be default-on or default-off? Running every node's
  full test suite on every invocation could be slow; default-off with an
  explicit flag matches the librarian's existing "fail closed, opt-in for
  expensive operations" pattern (`--production-claim` is the precedent).
- Should CI run `coverage-report` as an informational (non-blocking) step,
  mirroring the existing `schema_governance.py`/`audit_*.py` "warning only,
  never blocks" steps in `.github/workflows/ci.yml`? This document leans yes
  but defers the decision to the implementation PR's own review.
