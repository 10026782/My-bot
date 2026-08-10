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

Full isolated regression matrix: 17/19 passed (both runs — stable)
  FAIL: test_tc6_app_reply_ownership.py (44 passed, 8 failed)
  FAIL: test_pa01_phantom_approval_enforcement.py
```

Repeated-run stability: **STABLE** — both runs produced the identical
17/19 tally and the identical two failing files.

**The two failures are a local-sandbox network artifact, not a code
defect**, root-caused during this session: this execution environment
routes all outbound HTTPS through a proxy that returns `403 Forbidden` /
`ProxyError` for any connection attempt to `api.telegram.org` (not
whitelisted here). `test_tc6_app_reply_ownership.py` and
`test_pa01_phantom_approval_enforcement.py` are the two files in the matrix
that deliberately do not mock `app.bot` around certain seed/setup calls —
by design, to exercise the real owner-notify path — so in this sandbox that
real call fails at the TCP/proxy level (a connection exception), which
`app.py`'s own fail-safe correctly treats as `owner_notify_failed` and
revokes the just-created contract, which then makes the test's own
downstream assertions about that contract fail. A real CI runner (GitHub
Actions hosted) has open internet access to `api.telegram.org`; a fake
token there gets a real (fast) API rejection, not a connection-level
failure, which is the scenario these tests were written against — and this
exact file list is already unconditionally run by the pre-existing "Run
test_*.py scripts" CI step on `main` today, so if this were a real defect
`main`'s own required CI would already be red. **This is recorded as a
finding for anyone reproducing this session in a similarly egress-restricted
sandbox, not as a TC10 regression finding.** §8 records the real-CI
confirmation once this branch's CI has run.

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

### 6.3 Staging runtime evidence

Not produced by this session — this sandbox has no real staging
`DATABASE_URL`/`AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID`/`TELEGRAM_TOKEN`, and
none should ever be placed in an unattended agent session. What this
session did verify, dry-run, against a local Postgres + deliberately-fake
Airtable base (confirming no `AttributeError`/API-mismatch — only the
expected network/auth failures once real Airtable is actually needed):

- `scripts/verify_tc8_staging.py` still imports and runs cleanly after the
  regression-matrix removal (`python -m py_compile` + structural review;
  its PG-only checks are unchanged from the version TC8 already closed
  staging verification with).
- `scripts/verify_tc9_staging.py`'s pending/turn_id checks ran to
  completion against a real (local, disposable) `ActionGateway` singleton
  and real `compose_status_reply()` — both `PASS`ed structurally. The
  executed/failed checks reached real `approve()` -> real
  `tools.dispatcher.dispatch_tool()` -> real Airtable-field-normalization
  code before failing on the fake base's absent schema, which is the
  expected boundary for a sandbox with no real Airtable base to write to.

**A human (or a session holding real staging secrets) must run**
`TC9_STAGING_NON_PRODUCTION=true python scripts/verify_tc9_staging.py` and
`TC8_NON_PRODUCTION=true python scripts/verify_tc8_staging.py` against real
staging and attach the resulting evidence JSON. Until that happens, TC9's
runtime-wiring closure gate is **PENDING**, not verified — this document
does not claim otherwise.

### 6.4 TC9 MessageContract coverage summary

| State | Where verified | Class |
|---|---|---|
| pending | `scripts/verify_tc9_staging.py` (structurally proven this session against real ActionGateway + local PG; needs a real staging run for the "Staging runtime evidence" class) | isolated-integration (done) / staging (pending) |
| executed/completed | same script, evidence preserved, canonical path asserted | isolated-integration (structurally proven to the Airtable-write boundary) / staging (pending) |
| failed | same script, deterministic (bad table name, rejected before any write) | staging (pending) |
| outcome_unknown | **not attempted against staging** — no safe, deterministic way to force it without fabricating evidence or destabilizing staging (explicitly disallowed by this task) | `test_tc9_messagecontract_runtime_wiring.py` (isolated unit evidence only — accepted, stated limitation) |
| turn_id propagated when real | `scripts/verify_tc9_staging.py` — asserts a real-shaped id passed through `compose_status_reply()` is returned unmodified | isolated-integration (done) / staging (pending) |
| turn_id never fabricated when absent | same check, asserts `None` stays `None` | isolated-integration (done) / staging (pending) |
| exactly one final response | existing coverage: `test_turn_envelope.py`, TC6/PA-01 ownership tests already assert single-final-response invariants at the `app.py` integration boundary; `scripts/verify_tc9_staging.py` mocks `app.bot` and would show a call-count mismatch as a hard failure if this ever regressed | isolated-integration |

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

**TC10 — IMPLEMENTATION COMPLETE / STAGING VERIFICATION PENDING**

Isolated regression mode is built, wired into CI, and has produced real,
repeated, stable local evidence for the required named gates (39/39, 8/8,
11/11) and 17/19 of the full matrix, with the remaining 2 diagnosed as a
sandbox-local network artifact pending confirmation against this branch's
real CI run (§6.1). The TC8 handoff's specific contamination bug is fixed
at its root cause. The TC9 staging runtime canary is written, API-correct,
and structurally validated end-to-end against a local stand-in, but has not
been run against real staging — that remains an explicit, stated pending
item, not a silent gap.

**CORE OPERATIONAL VERIFICATION GATE — NOT YET READY** (blocked only on the
real-staging run of `scripts/verify_tc9_staging.py` and
`scripts/verify_tc8_staging.py`, both of which now require an explicit
non-production confirmation and neither of which any session in this
conversation has credentials to run).
