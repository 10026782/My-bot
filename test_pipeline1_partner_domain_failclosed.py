#!/usr/bin/env python3
# test_pipeline1_partner_domain_failclosed.py
# PIPELINE-1 discovery audit, blocker #1 — GET /api/leads fail-closed guard.
#
# Run: python3 test_pipeline1_partner_domain_failclosed.py
# Pass condition: exit code 0, all assertions green.
#
# Regression for the fix in tma_api.py::get_leads: a Partner identity with an
# empty/unconfigured allowed_domains list used to fall through _build_formula
# with NO domain restriction at all (its "if allowed:" guard only ever *adds*
# a filter, never blocks), so a misconfigured Partner saw every domain's
# leads. get_leads() now denies explicitly before ever building a formula or
# touching Airtable, mirroring the fail-closed pattern
# tools/airtable_security.py::enforce_tenant_scope() already uses for the
# identical Partner-with-no-domains case.

from __future__ import annotations

_passed = 0
_failed = 0


def check(label: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ✅ {label}")
    else:
        _failed += 1
        print(f"  ❌ {label}")


print("\n[1] GET /api/leads — Partner domain-scope fail-closed guard")

from flask import Flask
from identity import Identity, Role
import tma_api


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    return app.test_client()


_client = _make_client()
_HDR = {"X-Telegram-Init-Data": "x"}

_orig_validate = tma_api._validate_initdata
_orig_resolve = tma_api.resolve_identity
_orig_at_list = tma_api._at_list

_at_list_calls: list[tuple] = []


def _tracking_at_list(table, formula, max_records=None, **kw):
    _at_list_calls.append((table, formula))
    return []


def _identity(role, allowed_domains=None):
    return Identity(
        user_id="1", role=role, display_name="Test",
        allowed_domains=list(allowed_domains) if allowed_domains is not None else [],
    )


tma_api._validate_initdata = lambda s: {"id": "1"}
tma_api._at_list = _tracking_at_list

try:
    # -- Partner, no configured domains -> 403, Airtable never touched --
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.PARTNER, [])
    _at_list_calls.clear()
    r = _client.get("/api/leads", headers=_HDR)
    check("partner with empty allowed_domains -> 403 forbidden", r.status_code == 403)
    check("partner with empty allowed_domains -> Airtable never read (no cross-domain leak)",
          len(_at_list_calls) == 0)

    # -- Partner, allowed_domains explicitly None (defensive: malformed config) --
    ident_missing = _identity(Role.PARTNER, [])
    ident_missing.allowed_domains = None  # simulate a malformed identity-map entry
    tma_api.resolve_identity = lambda ch, tid: ident_missing
    _at_list_calls.clear()
    r = _client.get("/api/leads", headers=_HDR)
    check("partner with allowed_domains=None -> 403 forbidden (getattr fallback holds)",
          r.status_code == 403)
    check("partner with allowed_domains=None -> Airtable never read", len(_at_list_calls) == 0)

    # -- Partner WITH configured domains -> unaffected, still allowed through --
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.PARTNER, ["real_estate"])
    _at_list_calls.clear()
    r = _client.get("/api/leads", headers=_HDR)
    check("partner with configured domains -> 200, not blocked by the new guard",
          r.status_code == 200)
    check("partner with configured domains -> Airtable read happens (list still served)",
          len(_at_list_calls) == 1)

    # -- Owner / Manager with empty allowed_domains -> unaffected (guard is Partner-only) --
    for role_name, role in (("owner", Role.OWNER), ("manager", Role.MANAGER)):
        tma_api.resolve_identity = lambda ch, tid, r=role: _identity(r, [])
        _at_list_calls.clear()
        r_resp = _client.get("/api/leads", headers=_HDR)
        check(f"{role_name} with empty allowed_domains -> still 200 (guard is partner-only)",
              r_resp.status_code == 200)
finally:
    tma_api._validate_initdata = _orig_validate
    tma_api.resolve_identity = _orig_resolve
    tma_api._at_list = _orig_at_list

print("\n" + "=" * 50)
print(f"{_passed} passed, {_failed} failed")
print("=" * 50)

import sys
sys.exit(1 if _failed else 0)
