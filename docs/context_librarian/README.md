# BOSS Context Librarian — Phase 0

The Context Librarian is a small, files-first index that helps coding agents
load the architectural context relevant to a task. It stores concise metadata,
typed relationships, and references to current sources in the repository.

It is not runtime memory, a new source of truth, a search index, a vector store,
a graph database, an MCP server, or an automatic extractor. Production code
does not import it. Generated bundles are disposable navigation aids.

Read `AGENT_CONSUMPTION_CONTRACT.md` before using a bundle.

## Usage

```text
python -m tools.context_librarian build \
  --task-type approval_ux \
  --query "repeated approval returns wrong message" \
  --max-tokens 4000
```

Write a bundle only when a durable local artifact is useful:

```text
python -m tools.context_librarian build \
  --task-type tool_execution \
  --query "dispatcher returned an unverified success" \
  --output docs/context_librarian/generated/tool_execution.md
```

Discover the deterministic future-selection recommendation without allowing it
to choose for `build`:

```text
python -m tools.context_librarian suggest-profile \
  --query "approval prompt claims completion without evidence" \
  --all
```

The command reports `no_match` for a zero-score ranking and `tie` when more than
one profile shares the top score. Neither status selects a profile. Even a
unique suggestion is advisory; record `Selected profile: <profile_id>` before
running `build`.

For an operational production-state claim, make the evidence requirement
explicit:

```text
python -m tools.context_librarian build \
  --task-type rp5_evidence_mismatch \
  --query "is the completion claim live in production?" \
  --production-claim
```

That first production-claim bundle normally remains `STOP`. After directly
reading a selected evidence source and verifying that its environment, date,
scope, and state match the exact claim, rebuild with
`--verified-production-evidence <selected-path>`. The option is an explicit
agent attestation, not automatic evidence validation.

Every bundle contains an `Agent Workflow Gate`. `STOP` blocks planning and code
changes but intentionally does not block bundle creation. The bundle is a
mandatory minimum context, not a reading ceiling; record material sources found
outside it as context expansions.

## Selection model

Profiles select primary layers, required dependency layers, conditional
evidence, exclusions, mandatory decisions, allowed edge types, and budgets.
The query only ranks already-allowed nodes using explicit terms. It cannot
override a status filter, exclusion, mandatory decision, or traversal rule.

Each profile's `selection_terms` and `conditional_optional_evidence[].
query_terms` (`task_profiles/profiles.json`) are the sole controlled
vocabulary the free-text query is matched against, by plain substring
containment — no fuzzy matching, no synonyms beyond what is explicitly
listed. Free text can only ever *add* a profile-declared conditional layer;
it can never drop a primary layer, a required dependency layer, or a
mandatory canonical decision, and it cannot pull in an excluded layer no
matter what terms it contains (N17 item 3 — see the query/profile-selection
hardening tests in `test_context_librarian.py` for the regression fixtures,
including adversarial and Hebrew/English-equivalent-phrasing cases).

Output order is deterministic: mandatory decisions, primary layers, required
dependencies, then optional evidence; ties are resolved by status, verification
date/commit, and node ID. Historical and superseded nodes are excluded by
default. Planning-only material must be explicitly allowed by the profile.

The token budget is enforced with `ceil(characters / 4)` — a character-count
proxy, not a real Anthropic tokenizer count. This heuristic has not yet been
benchmarked against real token counts, so it must not be treated as a
conservative (i.e. never-understating) ceiling; see
`TOKEN_ESTIMATION_BENCHMARK.md` for the pending measurement before relying on
it for anything beyond a rough estimate. Safety text and mandatory decisions
reserve budget first. If they cannot fit, the command fails closed.

## Freshness and evidence

Path existence is validation, not freshness. For each distinct
`last_verified_commit`, the CLI compares that commit to the current checkout.
It reports code, test, and documentation changes separately. A node is stale
when a tracked code path changed after verification; test/doc changes are
reported as review signals without being mislabeled as code drift.

Bundles display four separate provenance sections:

- canonical documents;
- code paths;
- test paths;
- production evidence.

Bundle provenance reports both `on_main_history` (the generated commit is an
ancestor of `origin/main`) and `at_origin_main_tip` (the generated commit is
exactly the current `origin/main` tip). `--assert-main` remains a backward-
compatible alias for the history assertion; use `--assert-on-main-history` or
`--assert-at-origin-main-tip` when the distinction matters.

These checks use the repository's local `origin/main` ref only; the librarian
does not run `git fetch` automatically. If that ref is unavailable,
`at_origin_main_tip` is `unknown` and `--assert-at-origin-main-tip` fails
closed. History assertion likewise fails closed when no usable main ref can be
resolved.

Repository code defaults are not production configuration proof. Production
evidence entries always include a date, scope, status, and source path.

## Quality metrics

Every bundle reports more than the character-estimate savings figure:

- primary/dependency layer coverage;
- mandatory authority coverage;
- freshness ratio and stale-node count;
- provenance completeness;
- excluded-layer leakage count;
- query-match precision proxy;
- document and approximate-char-estimate budget utilization.

These metrics are deterministic selection diagnostics, not proof that an
engineering decision is correct. The char-estimate savings figure in
particular is not a validated token-savings claim — see
`TOKEN_ESTIMATION_BENCHMARK.md`.

## Adding or changing knowledge

Add a candidate as concise metadata with references and a confidence score.
It becomes canonical only after the repository's normal review/merge process
establishes authority; changing a catalog status does not make it canonical.
Mark stale or replaced knowledge with `superseded`/`historical` and a typed
`supersedes` edge. Never delete useful historical evidence merely to improve a
freshness score.

## Extending to more layers

Catalog discovery loads every `layers/*.json` file. Layer IDs and owners are
not hard-coded to the initial six. A new layer uses schema version 1.x, unique
node IDs, the existing edge vocabulary, and an explicit profile opt-in. New
metadata belongs under a namespaced `extensions` object. Breaking changes
require a new schema major version; new edge types require a schema minor
version plus explicit traversal approval.
