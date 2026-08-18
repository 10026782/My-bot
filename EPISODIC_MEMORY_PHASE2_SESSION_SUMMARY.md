# Episodic Memory Phase 2 & 2B Session Summary

**Date**: 2026-08-18 to 2026-08-19  
**Status**: ✅ COMPLETE — Phase 2 + Phase 2B merged to `main`  
**Commits**: PR #726 (Phase 2), PR #731 (Phase 2B)

---

## Phase 2: Retrieval Contract + Shadow-Only Path (PR #726)

### Scope
- `core/memory_retrieval_contract.py`: `MemoryRetrievalRequest` → `MemorySnapshot` contract
- `core/memory_retrieval.py`: `build_memory_snapshot()` read-only function (no writes, no LLM calls)
- `core/memory_retrieval_shadow.py`: `compare_with_live_paths()` debug utility
- `test_memory_retrieval.py`: 14 tests covering tenant isolation, filtering, budgets, provenance, failure semantics

### Key Design Decisions
- **Hard filters in order**: tenant → entity/session → domain → recency (deterministic sort only)
- **Per-category budgets** (Business Memory: 5 default, Episodic: 20 default) — deterministic and testable
- **Business Memory constraint**: Airtable table has no `tenant_id` field — retrieval gates access to `boss_hq` only, returns empty (not error) for other tenants
- **Episodic scoped queries**: over-fetch + Python sort when entity/session filters apply (ceiling: 500 rows, marked with `ponytail:` comment)
- **Failure per-category**: store unavailability caught and recorded in metadata, never raises; only malformed requests raise
- **Shadow-only enforcement**: `context.py` and `memory_store.py` remain completely unchanged; verified by `git diff` and dedicated tests

### Test Coverage
- ✅ 14/14 tests pass (pytest)
- ✅ Tenant isolation, entity filtering, session filtering
- ✅ Deterministic recency ordering, budget enforcement
- ✅ Provenance preservation, empty/unavailable stores
- ✅ Cross-tenant leakage prevention
- ✅ Live context unchanged verification
- ✅ No LLM/ActionGateway/write calls

### Deliverables
- **Merge commit**: `db09fd73fc6f258153cf86fd2fff15992c5b7764` (with auto-fast-forward of stale base)
- **Catalog node**: `component.memory_retrieval` registered in `docs/context_librarian/layers/memory.json`
- **Documentation**: minimal status addendum to `docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md`

---

## Phase 2B: Owner-Only Shadow Observation (PR #731)

### Scope
- `/memory_shadow` Telegram command (owner-only, no-role-change pattern from `/boss_doctor`)
- `build_shadow_request()`: constructs request from proven identity fields only (tenant_id, canonical_user_id, domain_id)
- `format_shadow_comparison()`: human-readable diff (counts, availability, errors, truncation flags — never raw memory content)
- `test_memory_shadow_command.py`: 42 assertions covering gate, wiring, mutations, failure modes

### Flow
```
/memory_shadow → identity.role=="owner" only → build_shadow_request(identity)
  → compare_with_live_paths() [side-by-side read]
  → format_shadow_comparison() [readable diff]
  → send to Telegram
```

### Test Coverage
- ✅ 42/42 tests pass (custom test file)
- ✅ Owner allowed, non-owner denied, identity=None denied
- ✅ Comparison wiring (called exactly once, request built from proven identity only)
- ✅ No mutations (poisoned calls to dispatcher, feature_flags, EpisodicMemoryRepository.insert, airtable_create)
- ✅ Memory state unchanged before/after
- ✅ Category failures surfaced, emptiness handled
- ✅ Budget truncation and ordering differences reported honestly
- ✅ No secrets in output, insufficient context fails safely
- ✅ Regression: `/boss_doctor` and `/status` routing unaffected
- ✅ Real dispatch via bot.process_new_updates() succeeds

### Comparison Output Format
```
Memory Shadow

tenant=boss_hq user=1 domain=general

Legacy paths:
  conversation messages: 3
  business memory: 120 chars (opaque blob, no item boundaries)

New retrieval contract:
  business memory: 2 items (available=True) budget=5 truncated=no
  episodic: 5 items (available=True) budget=20 truncated=no

Items only in legacy / items only in new: not computable — legacy paths return
unstructured output (text blob / differently-shaped message list) with no item
identity comparable to the new structured items.
Ordering: new path is deterministic-recency sorted; legacy Business Memory has no
defined ordering (raw Airtable API order).
```

### Key Decisions
- **Request fields**: only `tenant_id`, `canonical_user_id`, `domain_id` from identity — `session_id`, `entity_type`, `entity_id` left unset (no provable source in current runtime)
- **Comparison limitations honest**: legacy paths return unstructured output with no comparable item identity — reported explicitly rather than inferred
- **No telemetry**: matching infra doesn't exist yet; per task scope, no new infra added
- **No scheduler**: on-demand command only
- **Zero impact**: `context.py`, `memory_store.py`, prompt, model behavior, memory writes all unchanged

### Deliverables
- **Merge commit**: `a764115` (Merge pull request #731)
- **Command**: `app.py::cmd_memory_shadow()` (line 567, 26 new lines)
- **Helpers**: `build_shadow_request()`, `format_shadow_comparison()` in `core/memory_retrieval_shadow.py` (69 new lines)
- **Tests**: `test_memory_shadow_command.py` (347 lines, 42 assertions)

---

## Integration & Verification

### Full Test Suite Results
- `test_memory_retrieval.py`: 14/14 ✅
- `test_memory_shadow_command.py`: 42/42 ✅
- `test_boss_doctor.py`: 17/17 ✅
- `test_cmd_boss_doctor.py`: 27/27 ✅
- `smoke_tests.py`: all passed ✅
- `test_context_librarian.py`: 8/8 profiles validate ✅

### No Regressions
- `git diff origin/main -- context.py memory_store.py`: 0 bytes changed ✅
- Existing command routing (`/status`, `/boss_doctor`) unaffected ✅
- Phase 2 tests remain green after Phase 2B wiring ✅

---

## Scope Boundaries (Explicitly Not Included)

- ❌ **Phase 3**: Business Memory provenance/conflict handling
- ❌ **Cutover**: no live prompt injection, no model behavior change
- ❌ **Scheduled observation**: only on-demand `/memory_shadow` command
- ❌ **Telemetry**: no new logging/event infra
- ❌ **Embeddings/Vector search**: deterministic recency only
- ❌ **Memory writes**: read-only throughout
- ❌ **Confidence ranking**: deferred (no confidence field in today's stores)

---

## Recommended Next Slice

Wire a scheduled/logged run of `compare_with_live_paths()` into a low-risk observation point (e.g., owner-only debug endpoint or low-frequency background job) to accumulate real comparison data before any cutover or Phase 3 work begins. Still zero prompt/behavior impact — purely observational infrastructure.

---

## Session Artifacts

| File | Lines | Purpose |
|------|-------|---------|
| `core/memory_retrieval_contract.py` | 91 | Request/response contract |
| `core/memory_retrieval.py` | 167 | Build snapshot from sources |
| `core/memory_retrieval_shadow.py` | 103 | Debug comparison + Phase 2B command support |
| `test_memory_retrieval.py` | 472 | 14 tests for Phase 2 contract |
| `app.py` | +26 | `/memory_shadow` handler |
| `test_memory_shadow_command.py` | 347 | 42 tests for Phase 2B command |
| `docs/context_librarian/layers/memory.json` | +1 node | Catalog registration for Phase 2B |

**Total committed**: 7 files, 1206 lines of code/tests, 2 merged PRs.
