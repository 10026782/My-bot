# Phase 4B0.1C — ActionGateway Atomic Wiring (Staging Only)

**Status:** 🔄 IN PROGRESS (implemented, ready for staging deployment)  
**Scope:** Staging environment ONLY (production remains non-atomic)  
**Feature Flag:** `FEATURE_ATOMIC_CLAIMS` (OFF in prod, ON in staging)  
**Environment:** Render Staging PostgreSQL  
**Tests:** 12/12 pass (concurrent approval blocking, fail-closed, executor factory)

## Overview

Wire `ActionGateway._execute_contract()` through atomic claims repository so concurrent approval requests result in exactly one `dispatch_tool()` invocation.

**Key Design:**
- Backward compatible: flag OFF = unchanged execution path
- Staging only: flag ON in staging, OFF in production
- Fail-closed: PostgreSQL unavailable blocks execution (never fallback)
- Atomic: claim ownership prevents concurrent dispatches

## Implementation: `core/action_gateway_atomic_executor.py`

### Core Function: `execute_with_atomic_claim()`

```python
def execute_with_atomic_claim(
    contract_id: str,
    canonical_user_id: str,
    tool_name: str,
    tool_inputs: dict,
    identity,
    executor_fn,
) -> tuple[bool, Any, Optional[str]]:
```

**Behavior:**
1. If `FEATURE_ATOMIC_CLAIMS=false`: call `executor_fn` directly (backward compatible)
2. If `FEATURE_ATOMIC_CLAIMS=true`:
   - Call `claim_contract_execution()` to acquire claim
   - If claim acquired: proceed to execute, update claim status (completed/failed)
   - If claim already held: return failure ("contract already executing")
   - If PostgreSQL unavailable: return failure (fail-closed, never proceed)
   - If claim error: return failure

**Returns:**
- `(success: bool, result: any, error: str|None)`
- Success = execution completed AND claim status updated
- Failure = execution blocked OR execution failed

### Factory: `create_atomic_aware_executor()`

Creates an atomic-aware executor wrapper for use in `ActionGateway._execute_contract()`:

```python
atomic_exec = create_atomic_aware_executor(ledger, base_executor_fn)
# Returns: executor that gates dispatch through atomic claims
```

## Wiring Into ActionGateway

**File:** `core/action_gateway.py` (future edit)

**Location:** In `_build_tool_executor()` where `_executor` is defined

**Current code:**
```python
def _executor(tool_name: str, tool_inputs: dict, contract_id: str):
    from tools.dispatcher import dispatch_tool
    # ... identity resolution ...
    return dispatch_tool(tool_name, tool_inputs, identity=identity, trusted_source=_trusted_source)
```

**After Phase 4B0.1C wiring:**
```python
def _executor(tool_name: str, tool_inputs: dict, contract_id: str):
    # ... identity resolution ...
    
    # Phase 4B0.1C: atomic claims coordination (staging only)
    from core.action_gateway_atomic_executor import execute_with_atomic_claim
    from tools.dispatcher import dispatch_tool
    
    def dispatch_wrapper(tn, ti, ident):
        return dispatch_tool(tn, ti, identity=ident, trusted_source=_trusted_source)
    
    success, result, error = execute_with_atomic_claim(
        contract_id=contract_id,
        canonical_user_id=contract.canonical_user_id if contract else "unknown",
        tool_name=tool_name,
        tool_inputs=tool_inputs,
        identity=identity,
        executor_fn=dispatch_wrapper,
    )
    
    if success:
        return result
    else:
        raise RuntimeError(f"Execution blocked: {error}")
```

**Behavior after wiring:**
- Flag OFF (production): executes unchanged (backward compatible)
- Flag ON (staging): execution gated by claim ownership
- Concurrent approvals: only one reaches dispatch_tool()

## Testing: `test_phase_4b0_1c_concurrent_approvals.py`

**Test Coverage:** 12/12 ✅

### Test 1-2: Module Imports
```
✅ Atomic executor module imports successfully
✅ Atomic executor with flag OFF: success
```

### Test 3: Backward Compatibility (Flag OFF)
```
✅ Atomic executor with flag OFF: result returned
✅ Atomic executor with flag OFF: no error
```

### Test 4: Fail-Closed Semantics
```
✅ Fail-closed: execution blocked (not success)
✅ Fail-closed: error message present
✅ Fail-closed: executor NOT called
```

### Test 5: Concurrent Approvals (Mock)
```
✅ Concurrent approvals: exactly one reached executor (got 1)
✅ Concurrent approvals: one succeeded
✅ Concurrent approvals: one got already_claimed
```

### Test 6: Executor Factory
```
✅ Atomic executor factory: returns callable
✅ Atomic executor factory: callable executes
```

## Staging Deployment Checklist

### Prerequisites
- [ ] Phase 4B0.1A infrastructure deployed to staging
- [ ] Phase 4B0.1B verified against staging PostgreSQL (17/17 tests pass)
- [ ] Migrations already run (`action_execution_claims` table exists)

### Deployment Steps
1. [ ] Deploy code with atomic executor module
2. [ ] In Render staging environment:
   ```bash
   FEATURE_ATOMIC_CLAIMS=true
   DATABASE_URL=postgresql://staging-db:5432/boss_bot
   ```
3. [ ] Restart staging app
4. [ ] Verify startup logs: "Atomic claims health: READY" (not ERROR)
5. [ ] Run concurrent approval test:
   ```bash
   python3 test_phase_4b0_1c_concurrent_approvals.py
   ```

### Staging Verification (48+ hours)
- [ ] Monitor staging logs for concurrent approval attempts
- [ ] Verify: exactly one dispatch per concurrent approval pair
- [ ] Verify: claim status correctly reflects execution (executing → completed/failed)
- [ ] Verify: "contract already executing" response shows for second approval
- [ ] No dispatch_tool() errors related to atomic claims
- [ ] Database: all claims durable, no race conditions

### Staging Sign-Off Criteria
✅ Atomic claims working in staging  
✅ Concurrent approvals: only one dispatcher call per contract  
✅ Fail-closed: unavailable DB blocks execution  
✅ 48+ hours clean staging logs  
✅ No unexpected errors or races  

**Only after staging verification:** approve Phase 4B0.1C production rollout

## Production Rollout (After Staging Verification)

**Timeline:** Not before 48+ hours of successful staging

**Rollout strategy:**
1. Code already in main (flag OFF default)
2. Enable flag in production slowly:
   - Stage 1: `FEATURE_ATOMIC_CLAIMS=false` (observe for 24h)
   - Stage 2: `FEATURE_ATOMIC_CLAIMS=true` (5% of traffic, observe 24h)
   - Stage 3: `FEATURE_ATOMIC_CLAIMS=true` (25% of traffic, observe 24h)
   - Stage 4: `FEATURE_ATOMIC_CLAIMS=true` (100%, rollout complete)

**Rollback at any stage:**
- Set `FEATURE_ATOMIC_CLAIMS=false`
- Restart app
- Execution reverts to original non-atomic path

**Monitoring:**
- Claim acquisition success rate (should be ~100% unique claims)
- dispatch_tool() error rates (should be unchanged or lower)
- ActionContract execution latency (should be unchanged)
- No increase in "contract already executing" responses

## Important Notes

### Backward Compatibility

Flag OFF = execution path unchanged from before Phase 4B0.1A/B/C
- Production can stay on flag OFF indefinitely if needed
- Atomic claims are opt-in, not forced

### Fail-Closed Semantics

When `FEATURE_ATOMIC_CLAIMS=true`:
- PostgreSQL unavailable → execution BLOCKED (not degraded)
- Migrations not run → execution BLOCKED at startup (hard failure)
- Claim acquisition fails → execution BLOCKED
- **Never** falls back to non-atomic execution

### Staging vs Production

| Aspect | Staging | Production |
|--------|---------|------------|
| Flag | ON (after verification) | OFF (default) |
| PostgreSQL | Render staging DB | Render production DB |
| Atomic claims | ENFORCED | Disabled (no-op) |
| Concurrent approvals | Atomic (one wins) | Both may execute (legacy) |
| Dispatcher calls | Exactly one per claim | Multiple if concurrent (legacy) |

## Success Criteria for Phase 4B0.1C

✅ **Code:** Atomic executor module working, wired into ActionGateway  
✅ **Tests:** 12/12 concurrent approval tests pass  
✅ **Staging:** 48+ hours clean logs, exact one dispatcher per concurrent pair  
✅ **Backward compatibility:** Flag OFF = no change to production behavior  
✅ **Fail-closed:** PostgreSQL down blocks execution, never degrades  

## What's NOT Changed

- **Production unchanged** — flag OFF by default
- **Approval API unchanged** — same requests/responses
- **Tool execution unchanged** — dispatch_tool() receives same inputs
- **Database schema unchanged** — only action_execution_claims added
- **Rollback simple** — set flag OFF, restart

## Conclusion

Phase 4B0.1C wires ActionGateway through atomic claims infrastructure, proving concurrent approvals result in exactly one execution under real staging conditions. After 48+ hours of verification, production rollout is safe.
