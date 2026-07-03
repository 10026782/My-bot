# Governance Enforcement — Minimal Package

## Scope

- `PR_TEMPLATE.md` — manual pre-merge checklist asking authors to run the checks and paste the output.
- `docs/governance/gov_enforcement_checks.sh` — read-only Bash heuristics that report governance findings.
- `docs/governance/GOV_ENFORCEMENT_MINIMAL.md` — usage and output reference.

## How to run

```bash
# Quick mode (default daily scan)
./docs/governance/gov_enforcement_checks.sh

# Include docs, tests, and output files
./docs/governance/gov_enforcement_checks.sh --include-docs

# Include local worktree/helper directories matching ./.c*/ and ./.claude/
./docs/governance/gov_enforcement_checks.sh --include-worktrees

# Flags may be combined
./docs/governance/gov_enforcement_checks.sh --include-docs --include-worktrees

# Full audit mode
./docs/governance/gov_enforcement_checks.sh --full

# Help
./docs/governance/gov_enforcement_checks.sh --help
```

## Default exclusions

Quick mode does not scan these directories by default:

- `./.c*/`
- `./.claude/`
- `./docs/`
- `./node_modules/`
- `./.git/`

`--include-worktrees` restores scanning of `./.c*/` and `./.claude/`.
`--include-docs` restores findings from docs, tests, and output files. `node_modules` and `.git` remain excluded.

## Quick-mode families

Quick mode reports four high-risk governance families and shows at most ten findings per family:

1. **Gateway bypass** — direct write, send, or upload calls outside the expected gateway/dispatcher path.
2. **Missing auth** — callback, approval, or action endpoints without an identity/role/ownership check in scope.
3. **False success** — success, counter, completion, or status changes without nearby evidence/result checks.
4. **Dual mechanism** — raw feature-flag environment access or direct tool imports bypassing the registry/dispatcher.

## Output

The header records the selected mode and inclusion flags:

```text
GOV CHECKS: mode=quick (include_docs=0 include_worktrees=0)
```

The summary prints one line per family:

```text
gateway: findings_shown=10 files_affected=4 capped=true
```

- `findings_shown` — number of findings printed for the family, after the ten-result cap.
- `files_affected` — number of unique files represented by the printed findings.
- `capped` — `true` when additional findings existed but were omitted; otherwise `false`.

Each finding includes its classification, `file:line`, and a concise explanation. Classifications are:

- `WARN_TRUE` — high-confidence governance violation.
- `WARN_REVIEW` — likely issue requiring human review.
- `WARN_NOISY` — informational result commonly expected in tests, tools, or docs.

## Design constraints

- No production-code logic is changed.
- Checks are read-only heuristics.
- No CI enforcement is introduced.
- No architecture layer is added.

## What remains manual

- Run the checks and attach the output to the PR.
- Review WARN findings and record evidence or follow-up work.
- Run broader audits such as `daily_git_audit.py` when required.

NO CODE LOGIC CHANGED — this package is advisory and minimally invasive.
