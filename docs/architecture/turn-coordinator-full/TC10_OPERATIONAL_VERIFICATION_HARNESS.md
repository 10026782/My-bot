# TC10 — operational verification harness

TC10 is not a runtime architecture layer. It changes no ActionGateway,
TC7/TC8/TC9, F14, router, or approval-policy behavior. It exists to make the
existing architecture's regression evidence deterministic, isolated, and
repeatable, and to give TC9's MessageContract boundary an actual runtime
canary instead of only isolated unit coverage.

Base commit at start of this work: `origin/main` = `2bfda03` (PR #589).

## 1. Initial classification

**TC10: PARTIAL**, not MISSING as `AI_CONTEXT.md`'s "still PLANNING, zero
code" line claimed before this change (that line was itself stale — see
§7). A large amount of the isolated-regression requirement already existed
implicitly in `.github/workflows/ci.yml`'s "Run test_*.py scripts" step;
what was actually missing was (a) a name for that mode usable outside CI,
immune to ambient credentials, and provably repeatable, and (b) a fix for
the one concrete, previously-undiagnosed contamination bug in
`scripts/verify_tc8_staging.py` that caused the BUG-122 collision the TC8
handoff describes.

## 2. Existing verification infrastructure inventory

| Component | Purpose | Deterministic? | External deps | Safe for Staging | Suitable for isolated regression |
|---|---|---|---|---|---|
| `.github/workflows/ci.yml` "Run test_*.py scripts" | Runs every `test_*.py` at repo root as a script, job-level fake `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID`, `api.airtable.com` blocked via `/etc/hosts` | Yes (fresh container/DB per run) | Postgres service (ephemeral), open internet to Telegram/Anthropic API endpoints (unblocked, but calls use fake tokens) | N/A — never runs against staging | Yes — this is most of the isolation TC10 needed, just not named/exposed as a standalone mode |
| `conftest.py` | Registers `airtable`/`integration`/`live` pytest markers, excluded by default | N/A | N/A | N/A | Marks which pytest-collected tests are unit-safe |
| `scripts/verify_tc8_staging.py` (pre-TC10) | TC8 staging closure: migration/schema/repository checks against real staging Postgres, **and** ran `REGRESSION_GROUPS`/`FULL_REGRESSION` as subprocesses inheriting the ambient shell environment | PG checks: yes. Regression subprocess run: **no** — env inherited from caller, test files only `setdefault()` fake Airtable creds | Real staging PostgreSQL (dedicated, non-production) + whatever Airtable creds the caller's shell held | PG checks: yes. Regression run: **this was the contamination source** | No — this is exactly the shared-state problem TC8 handed off |
| `scripts/schema_snapshot.py`, `tools/check_airtable_schema_runtime.py` | Schema governance, not regression | N/A | Real Airtable (read-only) | Yes | No |
| `docs/staging-validation-reports/` | Historical staging validation writeups (e.g. PR #546) | N/A (prose) | N/A | N/A | N/A |
| `core/database_migrations.py` | Applies `core/migrations/*.sql` | Yes, idempotent | Real or CI PostgreSQL | Yes | Yes |
| Individual `test_*.py` files (200+) | Unit/integration coverage per bug/feature, most `unittest.mock`-based | Yes when run isolated (see below) | None when Airtable is mocked at the `tools.dispatcher`/`ActionGateway`-boundary level; a handful (TC6, PA-01) exercise the real `core.action_gateway.action_gateway` singleton and the real owner-notify Telegram call path | No (see §3) | Yes, given forced credentials |
| No pytest fixtures/factories for ActionContracts, no context-librarian-specific verification profile | — | — | — | — | — |

Nothing here was a parallel harness worth avoiding-by-reuse — the gap was
narrow and is closed by extension, not by a new framework.

## 3. Isolation gaps found (root cause of the TC8 handoff contamination)

`scripts/verify_tc8_staging.py`'s regression step ran each file as
`subprocess.run(..., env=os.environ.copy())`. Individual test files (e.g.
`test_bug_approval_callback_hardening.py`) set fake credentials via
`os.environ.setdefault("AIRTABLE_API_KEY", ...)` — a no-op once the ambient
shell already exports a real value, which is exactly the shell state of
someone about to run *staging* verification. A handful of files in
`FULL_REGRESSION` (`test_tc6_app_reply_ownership.py`,
`test_pa01_phantom_approval_enforcement.py`, others) deliberately exercise
the real `core.action_gateway.action_gateway` singleton and real
`app._queue_approval_detailed()` — including its real owner-notify Telegram
call and, when persistence-shaped flags are toggled on inside the test, real
`ActionContractRepository` reads (`find_live_contracts()` ->
`at_list_by_formula` against `Tables.ACTION_CONTRACTS`). Every one of these
files also reuses a small number of hand-written, fixed identity strings
(e.g. literal `"owner_1"`, `"tc6_rollback_r2_on"`). Put together: run this
matrix twice against the same real staging Airtable base and the second run
finds the first run's still-pending contracts under the same identity ->
`existing_pending_blocks_agent` (BUG-122). This is a test-harness defect,
not a TC8/TC9 runtime defect — confirmed by the fact that the exact same
production code paths behave correctly under the isolated mode below (no
collisions across two full repeated runs — §6).

## 4. Isolation strategy established

**Airtable.** No mock/fake layer was introduced for the isolated mode
because one already existed and was already sufficient: forced,
non-defaultable fake `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` for every
subprocess, set as a hard override in `scripts/run_isolated_regression.py`
(`_ISOLATED_ENV_OVERRIDES`), not `setdefault`. This is the actual fix —
`os.environ.setdefault(...)` inside individual test files can never again
be defeated by an ambient shell holding real secrets, because the runner
never lets those secrets reach the subprocess in the first place. The same
override list also covers `TELEGRAM_TOKEN` and `ANTHROPIC_API_KEY` — the
investigation for this change surfaced that the TC6/PA-01 tests make a real
outbound call to `api.telegram.org` as part of their normal, by-design
control flow (owner-notify-on-propose), so an isolated runner that forced
only Airtable would still be able to spam a real Telegram chat if invoked
from a shell holding a real bot token. `scripts/verify_tc8_staging.py` no
longer runs `REGRESSION_GROUPS`/`FULL_REGRESSION` at all (§3) — the full
matrix runs only through the isolated runner now.

**Identities.** `scripts/staging_identity.py` provides
`unique_identity(role, run_id=...)`, building a real `identity.Identity`
with production-equivalent role semantics but a `tenant_id` namespaced to a
fresh per-run identifier (`new_run_namespace()`). Since
`canonical_user_id == f"{tenant_id}:{user_id}"` (`Identity.memory_key`) and
every ActionGateway lookup keys off that string, two runs can never
collide regardless of what role/label string they pass — this does not
touch `identity.resolve_identity()` or any production identity-resolution
semantics, it only chooses disposable values for verification callers.

**ActionContracts.** Proven clean-start/no-cross-test-visibility by
construction (unique `tenant_id` per run) rather than by an explicit
"contracts are empty" precondition check — a stronger guarantee, since it
holds even if a previous run's cleanup failed. `scripts/staging_identity.py`
also provides `cleanup_run_contracts(run_id)`, scoped by a hard-coded
namespace-prefix guard so it can only ever delete records whose
`tenant_id` matches the calling run — never a broad delete, never another
run's or another engineer's data. Idempotency-style tests that
*intentionally* reuse one identity within a single run still work exactly
as before (untouched — this only changes cross-run isolation, not the
identity a given test chooses to reuse in-run).

**PostgreSQL.** No change from TC8's own approach: CI provisions a fresh,
ephemeral `postgres:16` service per run (`.github/workflows/ci.yml`), and
this session additionally proved the isolated matrix runs correctly against
a disposable local `postgres:16` cluster (`boss_bot_ci` database, dropped
after use) — see §6. Real staging PostgreSQL verification remains
`scripts/verify_tc8_staging.py`'s job, unchanged, and continues to run
migrations idempotently and clean up only the rows it creates (unchanged
from before this work).

## 5. Runner / mode design

Two explicit modes, matching the repository's existing script-runner
convention (no new CLI framework, no pytest-marker redesign — `conftest.py`
already had `airtable`/`integration`/`live` markers that this doesn't need
to touch since none of these runners are pytest-collected):

1. **Isolated regression mode** — `scripts/run_isolated_regression.py`.
   Owns the full regression matrix (`scripts/regression_matrix.py`:
   `REGRESSION_GROUPS` + `FULL_REGRESSION`, extracted as the single source
   of truth both this runner and `verify_tc8_staging.py`'s docstring point
   at). `--repeat N` runs the whole matrix N times and asserts every run
   produces the same pass tally — the automated form of "repeated runs
   produce stable results." Never touches real Airtable/Telegram/staging
   Postgres.
2. **Staging runtime mode** — `scripts/verify_tc8_staging.py` (now PG-only:
   preflight, migration, schema, real repository/CAS-race tests, authority
   invariants) and the new `scripts/verify_tc9_staging.py` (TC9
   MessageContract runtime canary, §6.4). Both require an explicit
   non-production confirmation env var before touching anything, matching
   the existing `TC8_NON_PRODUCTION`/`_preflight()` pattern.

The task description's proposed `--staging-only`/`--full-regression` CLI
split wasn't used — the existing per-purpose script convention
(`verify_tc8_staging.py`, now `verify_tc9_staging.py`, now
`run_isolated_regression.py`) already expresses the same two modes more
plainly, without inventing a shared CLI surface three unrelated scripts
would have to agree on.

## 6. Evidence

Evidence classes, per the task's requirement to distinguish them and never
mislabel Staging as Production:

### 6.1 Local isolated-integration evidence (this session, this sandbox)

Produced by installing `requirements.txt` + `psycopg2-binary`, starting a
disposable local PostgreSQL 16 cluster (`boss_bot_ci` database, dropped
after use, never a shared or staging resource), and running
`python scripts/run_isolated_regression.py --repeat 2`:

```
Named regression gates
  Callback hardening       PASS — 39 passed, 0 failed
  PR-0C callbacks          PASS — 8 passed, 0 failed
  BUG-158 recovery         PASS — 11 passed, 0 failed

Full isolated regression matrix: 21/21 passed (both runs — stable)
```

Repeated-run stability: **STABLE** — both runs produced the identical
21/21 tally.

**Correction, recorded rather than silently overwritten:** the first
version of this runner pushed to this branch's PR reported a stable
`17/19`, with `test_tc6_app_reply_ownership.py` and
`test_pa01_phantom_approval_enforcement.py` failing every time — both
locally and, once pushed, in this PR's own real GitHub Actions CI run. This
document's first draft attributed that to a local-sandbox network
restriction ("`api.telegram.org` blocked by this sandbox's proxy") and
predicted real CI would be green. **That prediction was checked against
this PR's actual CI run and was wrong.** Real CI failed identically
(`test_tc6_app_reply_ownership.py`: 44/52, same reason,
`owner_notify_failed`), which disproved the sandbox-artifact theory and
pointed at the runner itself.

Root cause: the first version of `_ISOLATED_ENV_OVERRIDES` force-overrode
`TELEGRAM_TOKEN` and `ELIYAHU_CHAT_ID` to fake values, on a defense-in-depth
theory (no test in an "isolated" matrix should be able to reach real
Telegram). `test_tc6_app_reply_ownership.py` and
`test_pa01_phantom_approval_enforcement.py` have scenarios that deliberately
leave `app.bot` unmocked around certain seed calls, by design, to exercise
the real owner-notify path and assert it *succeeds* (the contract must stay
`pending`, not get revoked by the `owner_notify_failed` fail-safe). Forcing
those two variables made every one of those calls fail — comparing this
PR's own CI run of the pre-existing "Run test_*.py scripts" step (which
uses real `secrets.TELEGRAM_TOKEN` and gets 52/52 on that file) against this
runner's step on the identical commit (44/52, forced-fake token) confirmed
it precisely.

Fix: `TELEGRAM_TOKEN`/`ELIYAHU_CHAT_ID`/`ANTHROPIC_API_KEY` are no longer
overridden at all — they pass through from the ambient environment exactly
like the pre-existing CI step already does. The hard override stays scoped
to `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` only — the one credential with a
*proven* cross-run contamination mechanism (§3); Telegram never had one.
With ambient `TELEGRAM_TOKEN`/`ELIYAHU_CHAT_ID` unset (this sandbox has
neither), `app.py`'s own notify path has nothing to send to and no longer
attempts a network call at all, so both files now pass locally too — the
21/21 reported above, this session's own local evidence, reproduced on this
corrected commit. Real CI (real `secrets.TELEGRAM_TOKEN`) is *expected* to
reach the same passing outcome by a different, equally legitimate path (the
call actually succeeding rather than never being attempted) — that is a
prediction from reading the code path, not yet a confirmed CI result; §10
states plainly that a fresh CI run on this corrected commit had not landed
as of this writing, and this section should not be read as claiming
otherwise. Overriding Telegram credentials here would have silently
narrowed what these tests exercise — exactly the "weaken a suite to reach
green" failure mode this harness is required not to introduce; the correct
fix was recognizing the override was wrong, not adjusting the tests.

A second-pass code review (CodeRabbit, on this PR) additionally found and
this session fixed: `test_tc8_runtime_integration.py` and
`test_turn_state_repository.py` were listed in
`scripts/regression_matrix.py`'s `PYTEST_MODE_FILES` but never actually in
`FULL_REGRESSION`, making them dead/unreachable entries (now added — both
pass, 9/9 combined); `--repeat 0` would have silently reported `PASS` having
run nothing (now rejected); repeated-run stability compared only the
aggregate tally, so two runs with different failing files but the same
count would have reported `STABLE` (now compares the full per-file outcome
set); `scripts/staging_identity.py`'s run namespace kept only 32 bits of the
run UUID (now the full value); `scripts/verify_tc9_staging.py` dispatched
the tool a second time after `gw.approve()` already executes it internally
— a real duplicate write against staging Airtable on every run (removed —
the executed/failed checks now derive their `ActionFact` from the contract's
real post-`approve()` status instead); its `_failed_check()` counted a
structural proposal-boundary rejection as if it had verified
`MessageState.FAILURE`, which it hadn't (now recorded as a distinct,
honestly-labeled `INCONCLUSIVE` outcome unless a real failure lifecycle is
reached); and its `_preflight()` trusted a caller-set boolean alone (now
also requires `AIRTABLE_BASE_ID`/`DATABASE_URL` to name-match
staging/sandbox/test/dev, matching `verify_tc8_staging.py`'s existing
heuristic).

`test_phase_4b0_1a_atomic_claims.py` required the same
`NO_DATABASE_URL_FILES` handling CI already special-cases (it asserts the
no-DB fail-closed path) — `scripts/regression_matrix.py` codifies that so
the isolated runner gets it right without hand-holding.

### 6.2 CI evidence

`.github/workflows/ci.yml` gained a "TC10 isolated regression matrix" step
(`scripts/run_isolated_regression.py --repeat 2`) immediately after the
existing "Run test_*.py scripts" step, uploading its evidence JSON as a
build artifact. This makes the named gates (39/39, 8/8, 11/11) and the full
matrix tally an explicit, visible CI check on every PR and every push to
`main`, rather than an implicit side effect of the generic `for f in
test_*.py` loop. It requires no new secrets — same fake-credential
convention the job already used.

**Confirmed real CI result** (this is CI evidence, not local evidence —
GitHub Actions hosted runner, PR #590, commit `2b6ecb3`, `backend-ci` job
`93373876198`, run
[31362450916](https://github.com/10026782/My-bot/actions/runs/31362450916/job/93373876198),
completed `2026-08-10T06:38:03Z`, conclusion `success`): the "TC10 isolated
regression matrix" step's own printed output reads

```
Repeated-run stability (2 runs): STABLE — per-file outcomes identical across runs, tallies: ['21/21', '21/21']
FINAL: PASS
```

with `test_tc6_app_reply_ownership.py` (52/52) and
`test_pa01_phantom_approval_enforcement.py` (108/108) both passing — the
exact two files the pre-fix version of this runner had regressed (§6.1).
This closes the "fresh CI run on the corrected commit" gap this document
previously listed as outstanding. §10's verdict is updated accordingly.

### 6.3 Staging runtime evidence

**Confirmed real staging evidence (2026-08-10)** — run by the operator from
the deployed Render staging shell (`~/project/src`, deploy SHA
`f8686a58` = `agent/f15-crm-write-migration` rebased onto `main`),
`DATABASE_URL`/`AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID`/`TELEGRAM_TOKEN` real,
pasted output relayed back to this session (no secrets in the pasted
output — the scripts never print them, per design):

`TC8_NON_PRODUCTION=true python3 scripts/verify_tc8_staging.py`:
`FINAL: TC8: DONE` — Deploy SHA matched, `database=my_bot_atomic_claims_staging`
(a genuinely dedicated non-production PostgreSQL — this is independently
verifiable from the connection string itself, not just the operator's
say-so), migration/schema/persistence/CAS-race/tenant-isolation/replay/
terminal/authority checks all `PASS`.

`TC9_STAGING_NON_PRODUCTION=true python3 scripts/verify_tc9_staging.py`
(run_id `tc10verify-20260810T141048Z-c450d8e8…`): `FINAL: TC9 STAGING
CANARY: DONE` —

- Pending: `PASS`, `MessageState.APPROVAL_PENDING`.
- turn_id: `PASS`, propagated when real, never fabricated when absent.
- Executed: `PASS`, real success this time (unlike the earlier dry run) —
  `ok=True real_status=completed state=MessageState.SUCCESS`, a genuine
  Airtable `Tasks` record was created (`recxu9l3SwAzmqjkA`) and the
  `MessageContract`'s evidence_ref reflected it.
- Failed: `PASS`, `real_status=failed state=MessageState.FAILURE` via the
  deliberately-invalid-table path — no false success.
- outcome_unknown: `DEFERRED` as designed, pointing at
  `test_tc9_messagecontract_runtime_wiring.py`.
- Cleanup: `PASS`, `deleted=2` — both `ActionContracts` records this run
  created (the pending-seed and the failed-seed; the `Tasks` record from
  the successful execution is real created business data, same as any
  other successful `airtable_add`, and is correctly *not* deleted by
  cleanup) were removed, scoped to this run's own `tenant_id`, confirmed by
  the DELETE requests and the `deleted=2` count in the pasted log.

**One honest caveat, not glossed over**: `DATABASE_URL`'s non-production
status is independently verifiable (the name itself says
`..._staging`, matching `verify_tc8_staging.py`'s heuristic). Airtable base
ids are opaque (`app4bcgoX7t0HUVnm` here — see §6.1/PR #592) — there is no
equivalent independent check for whether that specific base is a genuinely
separate non-production Airtable instance or the single shared base this
repo's own TC8 doc calls "shared Airtable Staging." This document does not
claim to have independently verified that distinction; it relies on the
operator's `TC9_STAGING_NON_PRODUCTION=true` assertion for it, exactly as
the script's own preflight documents. What *is* independently confirmed
from the pasted evidence: the canary's actual write footprint was fully
disposable and fully cleaned up (2 created, 2 deleted, 0 residue) except
for the one real `Tasks` record its own "Executed" scenario is designed to
create — the same footprint any single real approved `airtable_add` action
leaves, not an accumulating or contamination-prone one.

Both `tc8_evidence.json` and `tc9_evidence.json` were written on the
staging host; this document quotes the pasted stdout, not those files
directly (they were not transferred into this session).

### 6.4 TC9 MessageContract coverage summary

| State | Where verified | Class |
|---|---|---|
| pending | `scripts/verify_tc9_staging.py`, `MessageState.APPROVAL_PENDING` | isolated-integration + **staging (confirmed 2026-08-10)** |
| executed/completed | same script — real `airtable_add` write, real record `recxu9l3SwAzmqjkA` created, `MessageState.SUCCESS`, evidence_ref preserved | isolated-integration + **staging (confirmed, real success — not just the failure branch the pre-fix sandbox run could reach)** |
| failed | same script, deterministic (bad table name), `MessageState.FAILURE`, no false success | isolated-integration + **staging (confirmed)** |
| outcome_unknown | **not attempted against staging** — no safe, deterministic way to force it without fabricating evidence or destabilizing staging (explicitly disallowed by this task) | `test_tc9_messagecontract_runtime_wiring.py` (isolated unit evidence only — accepted, stated limitation) |
| turn_id propagated when real | `scripts/verify_tc9_staging.py` — asserts a real-shaped id passed through `compose_status_reply()` is returned unmodified | isolated-integration + **staging (confirmed)** |
| turn_id never fabricated when absent | same check, asserts `None` stays `None` | isolated-integration + **staging (confirmed)** |
| exactly one final response | existing coverage only: `test_turn_envelope.py`, TC6/PA-01 ownership tests already assert single-final-response invariants at the `app.py` integration boundary. `scripts/verify_tc9_staging.py` calls `core.action_gateway.action_gateway` directly and never reaches `app.py`'s callback/text handlers or `app.bot`, so it has nothing meaningful to assert a call count on — it does not add coverage here, and its module docstring says so explicitly rather than implying otherwise | isolated-integration |

## 7. Documentation updates

- `docs/architecture/turn-coordinator-full/TC8_DURABLE_TURN_STATE.md` gets
  a closure note recording that the TC10 handoff (deterministic isolated
  regression harness) is now satisfied — see that file's own new section.
- `AI_CONTEXT.md`'s TC10 line ("עדיין PLANNING, אפס קוד") is corrected —
  it was stale as of this change.
- `ROADMAP.md`/`CHANGELOG.md` record this PR per repository convention.

## 8. Cross-track defects discovered

None inside TC10's ownership boundary that required a runtime-code fix.
The one defect found (§3, staging regression contamination) was a
test-harness/verification-tooling defect, which is exactly what TC10 owns
and was authorized to fix directly (`scripts/verify_tc8_staging.py` is
verification tooling, not TC8 runtime behavior — no change to
`core/turn_state_repository.py`, `app.py`'s TC8 wiring, or any
ActionGateway/TC9 semantics). No ActionGateway, TC7 evidence authority,
TC8 persistence, TC9 schema, F14, router, or approval-policy code was
touched by this change.

TC10's own first draft introduced (and then corrected within the same PR,
before merge) a self-inflicted regression in the isolated runner itself
(§6.1: forcing `TELEGRAM_TOKEN`/`ELIYAHU_CHAT_ID` broke two real,
previously-passing tests). That is recorded here rather than smoothed over,
per the same evidence-honesty standard this harness holds everything else
to — a claim of "isolated regression gate satisfied" was made in this
document's first draft against a run that was, in fact, 17/19, and that
claim was wrong. It is corrected in §6.1 and this verdict now reflects only
what has actually been reproduced (locally, stably, 21/21) and what is
still pending independent confirmation (a fresh real-CI run on the
corrected commit).

## 9. Confirmation — no runtime contract weakened

- No file under `core/action_gateway.py`, `core/message_contract.py`,
  `core/turn_state_repository.py`, `core/claim_authorization.py`,
  `identity.py`, `tool_registry.py`, `tools/dispatcher.py`, or `app.py` was
  modified by this change.
- No test assertion was deleted, skipped, or weakened. `verify_tc8_staging.py`
  lost a code path (`_run_regressions`), not an assertion — the assertions
  it used to run against contaminated staging state now run, unchanged,
  against isolated state instead, via `run_isolated_regression.py`.
- No source-window size, timeout, or fail-closed behavior was changed.

## 10. Final verdict

**TC10 — COMPLETE AND VERIFIED**

Isolated regression mode is built, wired into CI, and has confirmed real-CI
evidence (§6.2, PR #590 commit `2b6ecb3`, `backend-ci` run 31362450916,
`FINAL: PASS`, `21/21` stable across 2 runs) for the required named gates
(39/39, 8/8, 11/11) and the full matrix — including
`test_tc6_app_reply_ownership.py` and
`test_pa01_phantom_approval_enforcement.py`, the two files an earlier,
over-broad credential override in this same PR had regressed. The TC8
handoff's specific contamination bug is fixed at its root cause.

The TC9 staging runtime canary was run against real staging on 2026-08-10
(§6.3) — `FINAL: TC9 STAGING CANARY: DONE` — pending, turn_id, a real
successful execution (genuine Airtable write, not just the failure branch
the earlier sandbox dry run could reach), the deterministic failure branch,
and clean scoped cleanup (2 created, 2 deleted, 0 residue) all confirmed.
`scripts/verify_tc8_staging.py` also ran clean against real staging in the
same session (§6.3) — migration/schema/persistence/CAS-race/tenant-
isolation/replay/terminal/authority all `PASS`, deploy SHA matched. Getting
there took two self-caught bugs along the way — an over-broad Telegram
credential override (§6.1, fixed in PR #590) and an Airtable-base-id name
check that could never pass for any real base (§6.1/PR #592) — both
root-caused from real failures, not assumed, and both fixed at the
credential/check level rather than by loosening what the scripts verify.

**CORE OPERATIONAL VERIFICATION GATE — READY.** Isolated regression: CI
gate. TC8 handoff's deferred regression matrix: closed. TC9 MessageContract
runtime wiring: confirmed on real staging for every state that can safely
be forced there; `outcome_unknown` remains isolated-unit-only by design,
stated as an accepted limitation, not a gap. No ActionGateway/TC7/TC8/TC9/
F14/router/approval-policy runtime code was touched anywhere in TC10.
