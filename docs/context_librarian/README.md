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
  --query "approval prompt claims completion without evidence"
```

## Selection model

Profiles select primary layers, required dependency layers, conditional
evidence, exclusions, mandatory decisions, allowed edge types, and budgets.
The query only ranks already-allowed nodes using explicit terms. It cannot
override a status filter, exclusion, mandatory decision, or traversal rule.

Output order is deterministic: mandatory decisions, primary layers, required
dependencies, then optional evidence; ties are resolved by status, verification
date/commit, and node ID. Historical and superseded nodes are excluded by
default. Planning-only material must be explicitly allowed by the profile.

Approximate tokens are `ceil(characters / 4)`. Safety text and mandatory
decisions reserve budget first. If they cannot fit, the command fails closed.

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

Repository code defaults are not production configuration proof. Production
evidence entries always include a date, scope, status, and source path.

## Quality metrics

Every bundle reports more than token savings:

- primary/dependency layer coverage;
- mandatory authority coverage;
- freshness ratio and stale-node count;
- provenance completeness;
- excluded-layer leakage count;
- query-match precision proxy;
- document and token budget utilization.

These metrics are deterministic selection diagnostics, not proof that an
engineering decision is correct.

## Adding or changing knowledge

Add a candidate as concise metadata with references and a confidence score.
It becomes canonical only after the repository's normal review/merge process
establishes authority; changing a YAML status does not make it canonical.
Mark stale or replaced knowledge with `superseded`/`historical` and a typed
`supersedes` edge. Never delete useful historical evidence merely to improve a
freshness score.

## Extending to more layers

Catalog discovery loads every `layers/*.yaml` file. Layer IDs and owners are
not hard-coded to the initial six. A new layer uses schema version 1.x, unique
node IDs, the existing edge vocabulary, and an explicit profile opt-in. New
metadata belongs under a namespaced `extensions` object. Breaking changes
require a new schema major version; new edge types require a schema minor
version plus explicit traversal approval.
