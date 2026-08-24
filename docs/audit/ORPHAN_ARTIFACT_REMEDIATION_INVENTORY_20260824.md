# #21 Orphan Artifact Remediation Inventory

Status snapshot: `origin/main` at `6b1f1d0375137810f8df070d0d0f7e58a9428b65`.

This is an inventory of the completed #21 work. It is not a deletion authorization,
retention policy, or replacement for the maintenance registers.

## Remediated artifacts

The following artifacts were confirmed orphan candidates, approved for retirement,
and are absent from the current `origin/main` tree:

| Artifact | Remediation evidence |
|---|---|
| `worker.py` | deletion commit `6b8573b` |
| `creative_generator.py` | deletion commit `72b91dc` |
| `knowledge_engine.py` | deletion commit `b393313` |
| root `router.py` | deletion commit `48efa3f` |
| `profile.py` | deletion commit `cb0e0ff` |
| root `memory.py` | deletion commit `4ff9604` |
| `lead_qualifier.py` | deletion commit `8b4a89d` |
| `config.json` | deletion commit `7a76754` |
| `import_knowledge_base.json` | deletion commit `97c256d` |

## Intentionally retained or parked

These artifacts remain present and were not approved for deletion:

| Artifact | Current disposition |
|---|---|
| `tools/context_librarian/benchmark_token_estimate.py` | Parked; intentional manual verification tool |
| `tenant_provisioner.py` | Parked; owner-blocked business/model decision |
| `review_diffs.txt` | Historical evidence retained |
| `reports/` | Live, generated, test-only, and historical report families; ownership handled under #12 |

The current live/parallel paths that remain include `config.py`,
`core/router/`, `memory_store.py`, `session_store.py`, `core_knowledge.py`, and
the canonical lead path. Their presence is not an orphan-remediation action.

## Boundary and follow-up

- #21 is closed for the identified orphan candidates.
- Stale maintenance-register and governance references are documentation work,
  not additional artifact deletions in this inventory.
- Existing cross-track notes remain: #20 stale documentation/governance references
  and #24 superseded architecture evidence.
- No Owner Context, capability-debt, retention, or replacement-path work is
  performed by this document.
