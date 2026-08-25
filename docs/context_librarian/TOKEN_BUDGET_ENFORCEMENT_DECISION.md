# Context Librarian Token Budget Enforcement

Status: APPROVED ARCHITECTURE / GOVERNANCE DECISION

The `ceil(characters / 4)` estimate remains a deterministic growth signal. It
is not a real tokenizer count and a small overflow is not, by itself, a hard
CI failure.

The enforcement split is:

1. Growth signal: report ordinary growth and small overflow as WARN.
2. Calibrated estimate: periodically compare representative bundles with the
   canonical provider token-count API and record model, commit, timestamp,
   profile, character count, proxy estimate, real count, ratio, and safety
   margin in `token_calibration.json`.
3. Hard safety limit: block only explicit strict budgets, structural document
   violations, or a deterministic overflow beyond the configured safety
   ceiling.

Calibration is never called from per-PR CI. Missing or stale calibration is
reported as `CALIBRATION_STALE`, not as a CI failure. Budget increases require
separate review of legitimate growth, duplication, stale context, bundle
composition, estimator noise, and actual capacity need.
