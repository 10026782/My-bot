# Patch Report

- Issue fixed: C1/C2 approval callback authorization
- File changed: `app.py`
- What changed:
  - Approval and rejection callbacks now verify the Telegram user who clicked the callback before acting.
  - Pending approval actions are no longer consumed before authorization checks pass.
  - Approved actions re-run registry enforcement with `enforce(tool_name, identity)` for the original requester immediately before `dispatch_tool()`.
  - If enforcement fails, the tool is not executed.
- Manual compile verification:
  - `py -3 -m py_compile app.py` PASS
  - `python -m py_compile app.py` PASS
- Runtime test still pending
- Next recommended issue: C3 tenant isolation

## C3 Phase 1 — tenant-scope airtable_get

- File changed: `tools/dispatcher.py`
- What changed:
  - `airtable_get` now requires an `identity`.
  - Airtable read filters now pass through the existing `enforce_tenant_scope()` helper.
  - External identities can no longer override tenant/user scope with a model-supplied filter.
  - Allowed and blocked Airtable reads are logged through the existing `audit_log_airtable()` helper.
- Manual compile verification:
  - `python -m py_compile tools\dispatcher.py` PASS
  - `py -3 -m py_compile tools\dispatcher.py` PASS
- Remaining C3 work:
  - `airtable_add`
  - `airtable_update`
