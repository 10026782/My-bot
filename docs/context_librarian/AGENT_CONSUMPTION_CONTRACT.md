# Agent Consumption Contract

This contract governs how coding agents consume Context Librarian bundles.

## Before coding

1. Choose an explicit task profile. Phase 0 never silently chooses one.
2. Build a fresh bundle from the current checkout and read the whole bundle.
3. Open the cited code, tests, canonical documents, and production evidence that
   are material to the change. A bundle is an index, not a substitute for them.
4. Treat every node marked stale as requiring direct re-verification. Staleness
   is detected from code changes since `last_verified_commit`, not merely from
   path existence.
5. Follow the bundle's `Do Not Assume` and `Out of Scope` sections.

## Authority and safety

- `main` overrides planning documents and generated bundles.
- ActionContracts is the sole authority for approval lifecycle state.
- The librarian and its generated output never become runtime sources of truth.
- `shadow`, `flag_off`, and `planning_only` material is not production-active.
- A completion claim requires merge, deployment, and production verification.
- Historical failures do not override later verified evidence.
- UX work must not expose internal tool names or user-facing/internal IDs.

## Agent stop conditions

Stop and inspect the cited source directly when:

- a selected node is stale;
- mandatory authority coverage is below 100%;
- an excluded layer leaks into the selection;
- production evidence is absent for a production claim;
- two sources conflict and current `main` does not resolve the conflict.

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
