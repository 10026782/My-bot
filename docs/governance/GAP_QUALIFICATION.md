# Gap Qualification Gate

**Docs-only. Records classification decisions; does not itself change any runtime behavior.**

## The rule

Before any open item becomes implementation work, it must first be **qualified**
against current code, the deployment contract, and runtime evidence — not
implemented from memory or from what a spec/roadmap *says* should exist.

**OPEN != IMPLEMENT.**

A documented open item is not implementation authority. Recording a gap is a
valid, complete outcome on its own — it does not create an obligation or a
license to write code.

**NO CODE CHANGE IS A VALID SUCCESSFUL ENGINEERING OUTCOME.**

Confirming that current behavior is already correct for the current deployment
shape, and recording *why* and *until when*, is success — not a stall.

## The six states

Every open item must be classified into exactly one of:

- **ACTIVE_DEFECT** — current code produces an observably wrong result today, under the current deployment shape. Fix now.
- **CONDITIONAL_GAP** — current code is correct today, but a *named, checkable* future condition (a deploy-shape change, a flag flip, a scale threshold) would make it wrong. Do not fix now; record the trigger and re-check when the trigger is crossed.
- **EVIDENCE_GAP** — the question can't be answered from what's currently verifiable (no logs, no test, no reproducible state). Fix the ability to observe, not the presumed defect.
- **COVERAGE_GAP** — a real thing exists with no owning layer/authority/registration, but nothing is behaving incorrectly. Needs an owner decision on where it belongs, not a code fix.
- **ALREADY_SATISFIED** — the gap was already closed by prior work; re-verify against current `main` and close the item.
- **OWNER_DECISION** — resolving it requires a judgment call only the owner can make (which layer owns this, is this in scope at all) — record the decision needed, don't guess it.

## Worked examples

### F14 Contact Gate — cross-instance dedup: CONDITIONAL_GAP

`find_or_create_contact()` (`crm.py:228`) serializes contact creation through
`_CONTACT_DEDUP_LOCK = threading.Lock()` (`crm.py:27`) — an **in-process**
lock. It correctly prevents duplicate-contact races between concurrent
requests handled by the *same* Python process. It provides **no** protection
against a race between two *separate* OS processes each holding their own
lock instance.

Current deployment (`docs/operations/DEPLOYMENT.md:85`): Start Command is
`gunicorn app:app` with no `--workers` flag — gunicorn defaults to a single
worker, and there is currently one Render service instance. Under that
shape, "in-process lock" and "cross-request lock" are the same guarantee, so
today's hardening is sufficient. This is not a defect: it's correct for the
current deployment contract, not for all conceivable ones.

**Activation trigger** (either flips this to ACTIVE_DEFECT and requires a
real fix — e.g. an Airtable-side unique-phone constraint, a DB-backed
lock/advisory lock, or routing dedup through a single-writer service):
- gunicorn `--workers` set above 1, **or**
- Render deployment instance count set above 1

**Until then:** no code change. Re-check this classification specifically
when either trigger is crossed — not on a calendar schedule, not because
main advanced for unrelated reasons.

### F15 write-path migration — ALREADY_SATISFIED

Recorded here as the second worked example, in place of the "Unified
Formatter" example referenced when this gate was requested — no artifact by
that name was found in this repository (searched docs and code), so
fabricating an example would violate this same document's own rule.
F15 (`crm.py` → `airtable_gateway.py` write-path migration, `ROADMAP.md`
around line 1905) is a real, already-resolved case of the same discipline:
it was an open COVERAGE_GAP (`crm.py` bypassed the "all writes go through
`airtable_gateway.py`" rule), qualified, implemented, and then closed with
real staging evidence (`ROADMAP.md`, "עדות Staging אמיתית 10/08/2026" —
`scripts/verify_f15_staging.py` run `f15-20260810T142420Z-01c6bc0a1f`, all 13
gates PASS, including `crm_static_no_direct_http_writes` and
`f14_gate_path`). A future agent encountering "F15" should classify it
ALREADY_SATISFIED and re-verify against current `main`, not reopen it as new
implementation work.

## Mandatory rules

1. **Qualify before implementing.** Every open item gets one of the six
   states above before any code is written for it.
2. **CONDITIONAL_GAP requires a named, checkable trigger**, not a vague
   "at scale" or "eventually." If you can't state the exact condition that
   would flip it, it isn't qualified yet — it's still an EVIDENCE_GAP.
3. **Re-classification is triggered by the condition, not by time or by
   unrelated repository activity.** An unrelated `main` commit does not
   reopen a CONDITIONAL_GAP or ALREADY_SATISFIED item.
4. **A documented gap is not a TODO with implied urgency.** Silence on an
   OWNER_DECISION or CONDITIONAL_GAP item is not technical debt accruing —
   it is the correct, complete state until its trigger/decision arrives.
