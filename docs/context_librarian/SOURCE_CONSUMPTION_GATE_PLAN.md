# Source Consumption Gate — Design Plan

Status: planning only. This document does not change bundle generation or
runtime behavior.

## Purpose

The current bundle is a navigation index. A future consumption gate must prove
that an agent reviewed the mandatory sources before allowing a conclusion or
code change. A self-reported `opened_sources` list is insufficient.

## Proposed receipt model

Each selected primary or required-dependency source becomes a `required_sources`
entry. Coverage is established only by a matching `review_receipt` containing:

- `path`
- `commit`
- `reviewed_by`
- `reviewed_at`
- `reason`
- `evidence_reference`

The gate should also expose:

- `waived_sources`: each waiver requires a non-empty reason and reviewer;
- `unreviewed_sources`: required sources with neither a valid receipt nor a
  valid waiver.

## Gate semantics

`CONCLUSION_BLOCKED` is required when any primary or required-dependency source
is unreviewed. A receipt is valid only when its path and commit match the
bundle's selected source and generated commit, and its evidence reference is
traceable to the reviewed material. The gate must not infer review from bundle
rendering, path existence, token metrics, or a manually typed path list.

## Open design questions

1. Which local or hosted evidence store provides tamper-evident receipts?
2. How are receipts signed or bound to an authenticated agent identity?
3. How are source expansions added to `required_sources` before conclusion?
4. What review authority can approve a waiver, and how does expiry work?

Implementation requires a separately reviewed PR after this schema and its
trust boundary are approved.
