# Phase 4B0 Wiring Bypass — Production Issue Analysis

**Date:** 2026-07-13  
**Status:** Identified, Not Yet Fixed  
**Severity:** CRITICAL — Atomic claims bypassed in production  

## Symptom

Production smoke test with `FEATURE_ATOMIC_CLAIMS=true`:
- Contract `4cce74c9-a910-4078-aa66-c46c58a85e8e` approved and dispatched
- **Result:** 0 rows in `action_execution_claims` table
- **Expected:** 1 row with claim status

```
Logs: route_confirmation_word → ActionGateway.approve() → tools.dispatcher → executed
      WITHOUT atomic claim acquisition
```

Production rolled back to `FEATURE_ATOMIC_CLAIMS=false`.

---

## Root Cause

### Complete Execution Path

```
user sends "כן" (confirmation word)
  ↓
app.py: _handle_telegram_message() → route_confirmation_word()
  ↓
ActionGateway.route_confirmation_word(canonical_user_id, approver_role)
  [Line 790: finds pending contracts for user]
  ↓
ActionGateway.approve(contract_id, approver, approver_role)
  [Line 1039: checks authorization]
  [Line 1111: marks status "approved" in ledger]
  ↓
ActionGateway._execute_contract(contract)
  [Line 1133: marks status "executing" in ledger]
  [Line 1140: calls self._tool_executor directly]
  ↓
_make_dispatch_executor._executor()
  [Line 1383: created by factory function]
  [Line 1417: calls dispatch_tool(tool_name, tool_inputs, identity, trusted_source)]
  ↓
tools.dispatcher.dispatch_tool()
  [EXECUTES TOOL DIRECTLY]
  ↓
[NO ATOMIC CLAIM CREATED — BYPASS COMPLETE]
```

### The Bypass Point

**File:** `core/action_gateway.py`  
**Function:** `_make_dispatch_executor()` (line 1370)  
**Issue:** Returns an `_executor` function (line 1383-1419) that calls `dispatch_tool()` directly

```python
def _make_dispatch_executor(ledger: ExecutionLedger):
    def _executor(tool_name: str, tool_inputs: dict, contract_id: str):
        # ... resolve identity ...
        return dispatch_tool(tool_name, tool_inputs, identity=identity, trusted_source=_trusted_source)
                ^^^^^^^^^^^^^^
                [DIRECT DISPATCH — NO ATOMIC COORDINATION]
    return _executor
```

This executor is assigned to `self._tool_executor` in `ActionGateway.__init__()` (line 517).

Then in `_execute_contract()` (line 1140):
```python
raw = self._tool_executor(
    tool_name=contract.tool_name,
    tool_inputs=contract.normalized_payload,
    contract_id=contract.contract_id,
)
```

**No check for `FEATURE_ATOMIC_CLAIMS`, no claim acquisition.**

---

## All Approval Paths Converge Here

1. **route_confirmation_word()** (line 790)
   - Single pending contract → calls `approve()` (line 821)
   - Multiple contracts → user selects via disambiguation

2. **route_disambiguation()** (line 898)
   - User picks contract number → calls `approve()` (line 926)

3. **route_combined_word()** (line 946)
   - "כן 1" or "לא 2" format → calls `approve()` (line 986)

4. **route_override_word()** (line 1000)
   - Manual override → calls `approve()` (line 1030)

**All paths:** `→ approve() → _execute_contract() → self._tool_executor() [BYPASS]`

---

## Required Wiring Fix

**Location:** `_make_dispatch_executor()` in `core/action_gateway.py`

**When FEATURE_ATOMIC_CLAIMS=true:**
1. Wrap `_executor` with `action_gateway_atomic_executor.execute_with_atomic_claim()`
2. Only dispatch if claim ACQUIRED
3. Transition claim to completed on success
4. Fail-closed on unavailable/conflict results

**When FEATURE_ATOMIC_CLAIMS=false:**
1. Execute dispatcher directly (current behavior)
2. No database writes, no claims

**Constraint:** Avoid circular import (atomic_executor imports action_gateway)

---

## Regression Test

**File:** `test_phase_4b0_wiring_regression.py`

**Assertion:** When `FEATURE_ATOMIC_CLAIMS=true`:
```
route_confirmation_word() 
  → must invoke execute_with_atomic_claim()
  → must create exactly 1 claim in action_execution_claims
  → must dispatch_tool() exactly once (no duplicates)
  → must transition claim status: executing → completed
```

---

## Production Impact

- **Current:** 0% atomic claim coverage for approvals (all bypass)
- **After fix:** 100% of approval paths protected by atomic claim acquisition
- **Rollout:** Enable `FEATURE_ATOMIC_CLAIMS=true` in staging after wiring verified
- **Gradual:** 5% → 25% → 100% (with 48h observation between steps)

---

## Next Steps

1. ✅ Identify bypass (this analysis)
2. ⏳ Modify `_make_dispatch_executor()` to check flag
3. ⏳ Wire atomic executor when flag enabled
4. ⏳ Run regression test
5. ⏳ Verify test passes (mock + real PostgreSQL on staging)
6. ⏳ Enable flag in staging for 48h verification
7. ⏳ Gradual production rollout
