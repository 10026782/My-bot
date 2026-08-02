# Recovery after a failed refresh

1. Stop; do not hand-edit `last_verified_commit` to make a check pass.
2. Confirm the checkout is `main` and resolve the canonical main SHA.
3. Run `refresh-after-merge --check` and save its deterministic proposal.
4. If a write failed, verify that catalog files are unchanged with `git diff`.
5. Fix the underlying catalog/schema or review the new-source proposal, then
   rerun the check. Only after a clean proposal may `--write` be used.

No refresh failure authorizes a runtime, approval, ownership, queue, or evidence
change. The catalog must remain usable and unchanged on failure.
