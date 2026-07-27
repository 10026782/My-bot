# Agent Consumption Contract

This contract governs how coding agents consume Context Librarian bundles.

## Before coding

1. Run `suggest-profile --all` with the complete task description. Display the
   ranking, scores, and matched terms before choosing anything.
2. Choose an explicit task profile and record `Selected profile: <profile_id>`.
   Suggestions are advisory: manual selection wins, `score=0` is not a valid
   recommendation, ties are unresolved, and cross-layer tasks require explicit
   architectural judgment. No phase silently chooses a profile.
3. Build a fresh bundle from the current checkout only after selection and read
   the whole bundle. Use `--production-claim` for an operational-state claim.
4. Open the cited code, tests, canonical documents, and production evidence that
   are material to the change. A bundle is an index, not a substitute for them.
5. Treat every node marked stale as requiring direct re-verification. Staleness
   is detected from code changes since `last_verified_commit`, not merely from
   path existence.
6. Follow the bundle's `Agent Workflow Gate`, `Do Not Assume`, and `Out of
   Scope` sections.

The bundle is mandatory minimum context, not a reading ceiling. When an import,
caller, callee, schema, flag, shared identifier, contract, test dependency,
execution path, evidence path, or authority boundary reveals material context
outside the bundle, open it and record a `context expansion`. Token and document
budgets never justify ignoring a dependency.

## Authority and safety

- `main` overrides planning documents and generated bundles.
- ActionContracts is the sole authority for approval lifecycle state.
- The librarian and its generated output never become runtime sources of truth.
- `shadow`, `flag_off`, and `planning_only` material is not production-active.
- A completion claim requires merge, deployment, and production verification.
- Historical failures do not override later verified evidence.
- UX work must not expose internal tool names or user-facing/internal IDs.

## Agent stop conditions

Stop before planning or changing code when:

- a selected node is stale;
- mandatory authority coverage is below 100%;
- an excluded layer leaks into the selection;
- production evidence is absent for a production claim;
- two sources conflict and current `main` does not resolve the conflict.

Bundle generation itself remains available when a node is stale so the bundle
can explain the drift and point to the sources that require re-verification.
A stale STOP allows only direct source re-verification. Refresh verification
metadata in a separate reviewed task after the source is verified on `main`,
then rebuild; never continue the original task by treating inspection as an
implicit override.
Production evidence only qualifies when its status and scope prove the claim;
`shadow`, `checkpoint`, `stale_briefing`, and planning evidence do not prove a
live production state. The agent must first read the exact evidence, verify
that its environment, observation date, scope, and represented state match the
claim, and then explicitly identify that evidence when rebuilding. Metadata or
keyword matching alone never validates a production claim.

## Context expansion record

Record the task, selected profile, source opened, reason, discovery path,
whether it was required for the solution, and whether the same dependency has
appeared in earlier tasks. A recurring expansion is a possible profile, edge,
node-metadata, mandatory-decision, or coverage gap. Record it during Phase 1;
do not change the catalog as part of the experiment.

## After coding

Do not edit catalog verification commits speculatively. Update metadata only
after the referenced code and tests are on `main`; record production evidence
separately and only when it actually exists.

## Future automatic profile selection

Phase 0 exposes deterministic `suggest-profile` ranking but keeps `build`
explicit. A future selector may propose a profile through a versioned selector
interface, confidence score, and explainable matched terms. It must require
confirmation on low confidence or ties, may not relax exclusions, and must
remain testable without an LLM. LLM-assisted classification, if ever proposed,
must be a separate reviewed phase and may only recommend a profile; it may not
change authority or traversal rules.
