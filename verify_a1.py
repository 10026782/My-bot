#!/usr/bin/env python3
"""
verify_a1.py — one-time production verification of SPEC A1
(Atomic Fail-Closed write path in tools/airtable_gateway.py).

NOT a production feature. NOT a permanent diagnostic tool.
Run once against production, read the output, delete this file.

Pure-invalid payloads only exercise the "clean is empty" guard (trivial —
there is nothing valid to write). The real SPEC A1 question is what happens
to a MIXED payload (one valid field + one invalid field): does the gateway
silently write the valid field via HTTP while dropping the invalid one
without telling the caller? That is what the mixed CREATE/PATCH cases below
test. Pure-invalid cases are kept only as controls.

Usage:
    ANTHROPIC_API_KEY=... AIRTABLE_API_KEY=... AIRTABLE_BASE_ID=... python3 verify_a1.py
"""

from __future__ import annotations

import os
import sys
import time

import httpx

# ── real gateway functions — no duplicated logic ────────────────────────────
from tools.airtable_gateway import (
    validate_airtable_fields,
    airtable_create,
    airtable_patch,
    airtable_delete,
)
from airtable_schema import LeadStatus

TABLE = "Leads"

if not os.environ.get("AIRTABLE_API_KEY") or not os.environ.get("AIRTABLE_BASE_ID"):
    print("VERIFY_A1 FAIL")
    print("ERROR: AIRTABLE_API_KEY / AIRTABLE_BASE_ID not set in this environment — "
          "cannot verify against live production.")
    sys.exit(2)

# ── monkey-patch httpx.post/httpx.patch to DETECT attempts only ─────────────
# Real network I/O is allowed through exactly once — for the single valid
# payload (case E) — everything else (pure-invalid AND mixed-invalid probes,
# CREATE and PATCH alike) is intercepted and blocked before it ever reaches
# the network, so no invalid payload can touch production.

_orig_post = httpx.post
_orig_patch = httpx.patch

_http = {"attempted": False, "method": None, "url": None}
_allow_real = {"flag": False}


def _guarded_post(url, *args, **kwargs):
    _http["attempted"] = True
    _http["method"] = "POST"
    _http["url"] = url
    if _allow_real["flag"]:
        return _orig_post(url, *args, **kwargs)
    raise RuntimeError("VERIFY_A1: blocked outgoing POST (invalid-payload probe)")


def _guarded_patch(url, *args, **kwargs):
    _http["attempted"] = True
    _http["method"] = "PATCH"
    _http["url"] = url
    if _allow_real["flag"]:
        return _orig_patch(url, *args, **kwargs)
    raise RuntimeError("VERIFY_A1: blocked outgoing PATCH (invalid-payload probe)")


httpx.post = _guarded_post
httpx.patch = _guarded_patch

# ── capture the real audit log line the gateway emits ───────────────────────
import logging

_audit_lines: list[str] = []


class _AuditCapture(logging.Handler):
    def emit(self, record):
        _audit_lines.append(record.getMessage())


_capture_handler = _AuditCapture()
_gateway_logger = logging.getLogger("tools.airtable_gateway")
_gateway_logger.addHandler(_capture_handler)
_gateway_logger.setLevel(logging.DEBUG)


def _reset():
    _http["attempted"] = False
    _http["method"] = None
    _http["url"] = None
    _audit_lines.clear()


def _is_success(kind: str, ret) -> bool:
    if kind == "create":
        return isinstance(ret, dict) and bool(ret.get("id"))
    return ret is True  # patch


def _return_contains_errors(ret, errors: list[str]) -> bool:
    """True only if the gateway's return value itself carries the error text —
    not just that errors were logged/printed separately."""
    if not errors:
        return False
    blob = repr(ret)
    return any(e in blob for e in errors)


def _report(case: str, clean, errors, gateway_return, kind: str) -> dict:
    attempted = _http["attempted"]
    success = _is_success(kind, gateway_return)
    audit = _audit_lines[-1] if _audit_lines else "(no audit line captured)"

    print("--------------------------------")
    print(f"CASE: {case}")
    print(f"Validator clean: {clean}")
    print(f"Validator errors: {errors}")
    print(f"HTTP attempted: {'YES' if attempted else 'NO'}")
    print(f"Gateway return: {gateway_return!r}")
    print(f"Audit result: {audit}")
    print("--------------------------------")

    if errors:
        print("VALIDATION_ERRORS_PRESENT")

    if attempted:
        print("HTTP_CALLED_WITH_PARTIAL_PAYLOAD" if errors else "HTTP_CALLED")
    else:
        print("HTTP_BLOCKED")

    if success:
        print("CALLER_RETURNED_SUCCESS")

    if _return_contains_errors(gateway_return, errors):
        print("ERRORS_PROPAGATED")

    return {"attempted": attempted, "success": success, "errors": bool(errors)}


# ═══════════════════════════════════════════════════════════════════════════
# Section 1 — pure-invalid CREATE probes (CONTROL cases only)
#
# These only prove the "clean payload ends up empty -> blocked" guard.
# They do NOT prove SPEC A1 atomicity for a payload that is partly valid.
# Excluded from the final verdict — informational only.
# ═══════════════════════════════════════════════════════════════════════════
control_create = {}

_reset()
p = {"__verify_a1_unknown_field__": "x"}
clean, errors = validate_airtable_fields(TABLE, dict(p))
ret = airtable_create(TABLE, dict(p), source="verify_a1")
control_create["A"] = _report("CONTROL A. Pure unknown field", clean, errors, ret, "create")

_reset()
p = {"status": "__verify_a1_invalid_status__"}
clean, errors = validate_airtable_fields(TABLE, dict(p))
ret = airtable_create(TABLE, dict(p), source="verify_a1")
control_create["B"] = _report("CONTROL B. Pure invalid select option", clean, errors, ret, "create")

_reset()
p = {"Owner": "not-a-valid-rec-id"}
clean, errors = validate_airtable_fields(TABLE, dict(p))
ret = airtable_create(TABLE, dict(p), source="verify_a1")
control_create["C"] = _report("CONTROL C. Pure malformed linked-record value", clean, errors, ret, "create")

_reset()
p = {"טמפרטורה": "בוער"}
clean, errors = validate_airtable_fields(TABLE, dict(p))
ret = airtable_create(TABLE, dict(p), source="verify_a1")
control_create["D"] = _report("CONTROL D. Pure read-only / formula field", clean, errors, ret, "create")


# ═══════════════════════════════════════════════════════════════════════════
# Section 2 — MIXED CREATE probes: one valid field + one invalid field.
# This is the actual SPEC A1 silent-partial-write test.
# ═══════════════════════════════════════════════════════════════════════════
mixed_create = {}

_reset()
p = {"Name": "VERIFY_A1_MIXED_UNKNOWN", "__verify_a1_unknown_field__": "x"}
clean, errors = validate_airtable_fields(TABLE, dict(p))
ret = airtable_create(TABLE, dict(p), source="verify_a1")
mixed_create["A"] = _report("MIXED A. valid field + unknown field (CREATE)", clean, errors, ret, "create")

_reset()
p = {"Name": "VERIFY_A1_MIXED_SELECT", "status": "__verify_a1_invalid_status__"}
clean, errors = validate_airtable_fields(TABLE, dict(p))
ret = airtable_create(TABLE, dict(p), source="verify_a1")
mixed_create["B"] = _report("MIXED B. valid field + invalid select option (CREATE)", clean, errors, ret, "create")

_reset()
p = {"Name": "VERIFY_A1_MIXED_LINK", "Owner": "not-a-valid-rec-id"}
clean, errors = validate_airtable_fields(TABLE, dict(p))
ret = airtable_create(TABLE, dict(p), source="verify_a1")
mixed_create["C"] = _report("MIXED C. valid field + malformed linked-record field (CREATE)", clean, errors, ret, "create")

_reset()
p = {"Name": "VERIFY_A1_MIXED_READONLY", "טמפרטורה": "בוער"}
clean, errors = validate_airtable_fields(TABLE, dict(p))
ret = airtable_create(TABLE, dict(p), source="verify_a1")
mixed_create["D"] = _report("MIXED D. valid field + read-only/formula field (CREATE)", clean, errors, ret, "create")


# ═══════════════════════════════════════════════════════════════════════════
# Section 3 — the ONE real write allowed in this script: a valid Lead,
# used as the target for the mixed PATCH probes below, deleted in finally.
# ═══════════════════════════════════════════════════════════════════════════
_reset()
_marker = f"VERIFY_A1_TEST_{int(time.time())}"
payload_e = {"Name": _marker, "status": LeadStatus.NEW, "source": "verify_a1_script"}
clean_e, errors_e = validate_airtable_fields(TABLE, dict(payload_e))

created_record = None
mixed_patch = {}

try:
    _allow_real["flag"] = True
    created_record = airtable_create(TABLE, dict(payload_e), source="verify_a1")
finally:
    _allow_real["flag"] = False
    e_result = _report("E. Valid payload (CREATE, real write)", clean_e, errors_e, created_record, "create")

    rec_id = created_record.get("id") if isinstance(created_record, dict) else None

    # ═════════════════════════════════════════════════════════════════════
    # Section 4 — MIXED PATCH probes against the real temp record.
    # Never allowed to touch the network for real — guard intercepts,
    # exactly like the mixed CREATE probes above.
    # ═════════════════════════════════════════════════════════════════════
    if rec_id:
        _reset()
        p = {"summary": "verify_a1_patch_probe", "__verify_a1_unknown_field__": "x"}
        clean, errors = validate_airtable_fields(TABLE, dict(p))
        ret = airtable_patch(TABLE, rec_id, dict(p), source="verify_a1")
        mixed_patch["A"] = _report("MIXED A. valid field + unknown field (PATCH)", clean, errors, ret, "patch")

        _reset()
        p = {"summary": "verify_a1_patch_probe", "status": "__verify_a1_invalid_status__"}
        clean, errors = validate_airtable_fields(TABLE, dict(p))
        ret = airtable_patch(TABLE, rec_id, dict(p), source="verify_a1")
        mixed_patch["B"] = _report("MIXED B. valid field + invalid select option (PATCH)", clean, errors, ret, "patch")

        _reset()
        p = {"summary": "verify_a1_patch_probe", "Owner": "not-a-valid-rec-id"}
        clean, errors = validate_airtable_fields(TABLE, dict(p))
        ret = airtable_patch(TABLE, rec_id, dict(p), source="verify_a1")
        mixed_patch["C"] = _report("MIXED C. valid field + malformed linked-record field (PATCH)", clean, errors, ret, "patch")

        _reset()
        p = {"summary": "verify_a1_patch_probe", "טמפרטורה": "בוער"}
        clean, errors = validate_airtable_fields(TABLE, dict(p))
        ret = airtable_patch(TABLE, rec_id, dict(p), source="verify_a1")
        mixed_patch["D"] = _report("MIXED D. valid field + read-only/formula field (PATCH)", clean, errors, ret, "patch")
    else:
        print("WARNING: valid payload (case E) did not succeed — mixed PATCH cases skipped")

    # cleanup happens no matter what happened above
    if rec_id:
        deleted = airtable_delete(TABLE, rec_id, source="verify_a1")
        print(f"CLEANUP: deleted temp record {rec_id} -> {deleted}")
        if not deleted:
            print(f"WARNING: manual cleanup required — record {rec_id} in {TABLE} was NOT deleted")

# ── restore httpx (best-effort, process is exiting anyway) ──────────────────
httpx.post = _orig_post
httpx.patch = _orig_patch
_gateway_logger.removeHandler(_capture_handler)

# ═══════════════════════════════════════════════════════════════════════════
# Verdict — driven ONLY by mixed cases (the actual SPEC A1 test) and the
# valid payload. Control (pure-invalid) cases are informational only.
# ═══════════════════════════════════════════════════════════════════════════
mixed_create_violations = [
    c for c, r in mixed_create.items() if r["attempted"] or r["success"]
]
mixed_patch_violations = [
    c for c, r in mixed_patch.items() if r["attempted"] or r["success"]
]
valid_case_ok = _is_success("create", created_record)

print("================================")
if mixed_create_violations:
    print(f"VIOLATION: mixed-invalid CREATE payload(s) reached HTTP or returned success: {mixed_create_violations}")
if mixed_patch_violations:
    print(f"VIOLATION: mixed-invalid PATCH payload(s) reached HTTP or returned success: {mixed_patch_violations}")
if not valid_case_ok:
    print("WARNING: valid payload (case E) did not succeed — happy path unverified")

if mixed_create_violations or mixed_patch_violations:
    print("VERIFY_A1 FAIL")
    sys.exit(1)
else:
    print("VERIFY_A1 PASS")
    sys.exit(0)
