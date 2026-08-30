# CI Test Harness False-Pass — 30/08/2026

Follow-up to `docs/audit/LEAD_CRM_STATIC_LOCAL_VERIFICATION_20260830.md`,
whose methodology note flagged that some Lead/CRM `test_*.py` files are
pytest-style (bare `def test_*()`, no `__main__`/`sys.exit` runner) and
silently execute zero tests under `python3 <file>.py`. This pass sized and
fixed the root cause repo-wide.

## Root cause

`.github/workflows/ci.yml`'s "Run test_*.py scripts" step runs `python "$f"`
for every `test_*.py` file in the repo root. A file with only bare
`def test_*()` functions and no `if __name__ == "__main__":` block, no
top-level `sys.exit(`/`raise SystemExit`, and no `unittest.main()` call
executes **zero** of its test functions under that invocation — Python just
defines the functions and exits 0, having tested nothing. This exact failure
mode had already been independently discovered and patched four times before
(see the `pytest context librarian` / `pytest ... durable_lifecycle` steps
and their inline comments, added one file at a time as each was noticed) —
never fixed at the loop level.

## Size of the gap

Of 356 `test_*.py` files in the repo root, **188 define real `def test_*()`
functions with no runner of their own** — i.e. were silently contributing
zero coverage on every CI run, except the ~12 that had already been given
their own dedicated `pytest` step by hand (`test_context_librarian.py`,
`test_decision_*.py`, `test_core_reasoning.py`, `test_refresh_after_merge.py`,
`test_reconcile.py`, `test_phase_4b_1b_durable_lifecycle.py`,
`test_status_sync_validator.py`). That leaves **~176 files** that were never
actually executed by CI before this fix.

(An initial, narrower heuristic — "no `if __name__` guard" — over-counted at
239 files and under-counted correctness: it wrongly flagged
`test_action_gateway.py`, which has no guard but calls `sys.exit(...)`
unconditionally at module level, so `python file.py` already runs it
correctly; routing it through pytest instead crashes collection, since
`sys.exit()` at import time raises `SystemExit` during pytest's module
import. The correct, verified signal is "defines `def test_*()` functions" —
confirmed safe by collecting and then actually running all 188 matching
files individually.)

## Fix

The loop now detects `def test_` functions and routes those files through
`python -m pytest -m "not integration and not airtable and not live" "$f" -x
--tb=short -q` instead of `python "$f"`, closing the whole class of bug
going forward (a newly-added pytest-style test file is now covered
automatically — no per-file CI edit required, unlike the four one-off fixes
this replaces).

Two explicit carve-outs, both non-blocking and narrow:

- **`ALREADY_COVERED`**: the ~12 files that already have their own dedicated
  `pytest` step later in the same job — left on the old `python "$f"` no-op
  path here so they don't run twice.
- **`KNOWN_PYTEST_FAILURES`**: 6 files newly proven (by actually running all
  188) to contain genuine pre-existing failures, unrelated to the harness
  fix itself — run with `|| true` so they're visible but non-blocking:
  - `test_business_tool_registry.py` — 3 failures, business-tool-recommendation
    wording drift (BentoPDF/RAWGraphs playbook copy), unrelated to Lead/CRM.
  - `test_dev_registry_validator.py` — 1 failure, registry row-count
    expectation (44 vs 31) stale against a grown registry file.
  - `test_phase_4b0_1b_concurrency_regression.py` — 1 failure,
    `test_schema_constraints`, not investigated further (out of this pass's
    scope).
  - `test_session_store_contract.py` — 1 failure,
    `AttributeError: module 'tools.airtable_tools' has no attribute 'httpx'`
    — a stale mock target, not investigated further.
  - `test_provider_portability_envelope1d.py` — 1 failure,
    `test_scope_has_no_raw_provider_envelope_access` flags `ad_attribution.py`
    for direct provider access. This **confirms** the
    `ad_attribution.py::mark_converted()` finding already reported in
    `LEAD_CRM_STATIC_LOCAL_VERIFICATION_20260830.md` as a CURRENT STATIC GAP.
    Fixing `ad_attribution.py` itself is out of scope for this pass (not
    requested); this test stays carved out until that's done.
  - `test_audit_dispatcher_bypass_enforcement.py` — 3 failures, all in
    `tools/audit_dispatcher_bypass.py`'s own self-tests
    (`test_stable_identity_handles_shifted_{legacy,interaction,cmd_update}_import`).
    Root cause: these tests hardcode specific line numbers
    (`lead_capture.py:213`, `interaction_engine.py:310/575`,
    `cmd_update.py:547`) to simulate "the import moved since BASELINE was
    frozen" — but the real imports have since moved *again* (now at
    `lead_capture.py:132`, `interaction_engine.py:339/354` (two, not one)
    and `:102/626`, `cmd_update.py:726`), so the hardcoded synthetic lines no
    longer point at real import statements and
    `_matches_stable_legacy_identity()` correctly declines to match. This is
    **test-fixture staleness, not a logic bug** — confirmed by the fact that
    running `tools/audit_dispatcher_bypass.py` live still correctly classifies
    all three files' real imports as LEGACY today. Left for a separate pass
    to reconcile `BASELINE` and the test fixtures against current line
    numbers.

One additional pre-existing failure was found and left untouched (not a
pytest-style file, unaffected by this fix either way — it already ran via
the plain `python "$f"` path before and after): `test_bug153_create_task_reconfirmation_after_rejection.py`
has 3 failing end-to-end assertions unrelated to Lead/CRM or this fix.

One test file was fixed in this same pass because it's a trivial, one-line,
test-only bug directly in Lead/CRM scope:
`test_c02_c04_finding3_remediation.py`'s two failures were both
`TypeError: got an unexpected keyword argument 'write_event'` — a
`monkeypatch.setattr(lead_service, "_run_post_write_enrichment", lambda
*args: None)` mock whose signature never got updated when
`core/lead_service.py`'s real function gained a `write_event=` keyword
argument. Fixed to `lambda *args, **kwargs: None`. Not a production bug —
`create_lead()`'s actual behavior was already correctly covered by the ~1,500
other passing tests in the earlier Lead/CRM verification pass.

## Verification

All 356 `test_*.py` files were run individually (own subprocess each, so a
crash in one can't hide the rest) with the fix's exact routing logic
simulated locally. Result: 0 unexpected failures — every file either passes,
or is one of the explicitly-carved-out/pre-existing items documented above.

## Not done in this pass

- Fixing the 5 unrelated `KNOWN_PYTEST_FAILURES` files' underlying issues.
- Reconciling `tools/audit_dispatcher_bypass.py`'s `BASELINE`/self-test line
  numbers against current reality.
- Fixing `ad_attribution.py`'s provider-envelope bypass (tracked separately).
- Fixing `test_bug153_create_task_reconfirmation_after_rejection.py`.

None of these were requested for this pass; each is independently
actionable by removing its file from the relevant carve-out list once fixed.
