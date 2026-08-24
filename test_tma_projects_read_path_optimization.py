#!/usr/bin/env python3
# test_tma_projects_read_path_optimization.py
# TMA Projects Hub read-path optimization
#
# Run: python3 test_tma_projects_read_path_optimization.py
# Pass condition: exit code 0, all assertions green.
#
# Covers:
#   A. Payments removed entirely from GET /api/projects (no reads, no
#      response fields income_this_month/pending_payments_count/
#      pending_payments_amount).
#   B. _get_project_cards() bulk Leads read (one query across all visible
#      domains, in-memory aggregation) instead of one query per card;
#      hot_leads_count derived from the same bulk result.
#   C. GET /api/leads?domain=X performs zero ProjectsHub reads (domain
#      takes priority over project_slug — this was already true before
#      this change; locked in here as a regression guard) and the
#      project_slug fallback still works for back-compat.
#
# Explicitly OUT of scope (per owner decision — no code here touches these):
# Timeline lazy-load, BUG-104 reasoning, core/lead_event_writer.py,
# approval flow, Airtable schema, finance screen, slug/domain renaming.

from __future__ import annotations

import sys

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


import tma_api
from airtable_schema import LeadFields
from tools.airtable_read_adapter import render_query


class _FakeIdentity:
    def __init__(self, is_owner=True, user_id="1"):
        self.is_owner = is_owner
        self.user_id = user_id


_PROJECTSHUB = [
    {"id": "recFI", "fields": {"slug": "furniture-import", "domain": "import",
                               "Name": "Furniture Import", "owner_ids": ""}},
    {"id": "recRC", "fields": {"slug": "recruitment", "domain": "recruitment",
                               "Name": "Recruitment", "owner_ids": ""}},
    {"id": "recSA", "fields": {"slug": "boss-saas", "domain": "saas",
                               "Name": "BOSS SaaS", "owner_ids": ""}},
    {"id": "recBV", "fields": {"slug": "blueview", "domain": "real_estate",
                               "Name": "BlueView Real Estate", "owner_ids": ""}},
]

_LEADS = [
    {"id": "L1", "fields": {"domain": "import", "status": "active", LeadFields.SCORE: 80}},
    {"id": "L2", "fields": {"domain": "import", "status": "active", LeadFields.SCORE: 10}},
    {"id": "L3", "fields": {"domain": "recruitment", "status": "active", LeadFields.SCORE: 90}},
    {"id": "L4", "fields": {"domain": "real_estate", "status": "archived", LeadFields.SCORE: 95}},
    {"id": "L5", "fields": {"domain": "saas", "status": "active", LeadFields.SCORE: 99}},
]

_EXCLUDED_STATUSES = {"archived", "duplicate", "not_relevant", "lost"}


def _formula_domains(formula: str) -> set[str]:
    """Extract the set of domain values a bulk formula's OR(...) targets."""
    import re
    return set(re.findall(r"\{domain\}='([^']+)'", render_query(formula)))


class _CountingAirtable:
    """Fake _at_list — simulates Airtable filtering and counts calls per table."""

    def __init__(self, projectshub=None, leads=None, tasks=None, payments_should_fail=True,
                 leads_cap=None):
        self.projectshub = projectshub if projectshub is not None else _PROJECTSHUB
        self.leads = leads if leads is not None else _LEADS
        self.tasks = tasks if tasks is not None else []
        self.payments_should_fail = payments_should_fail
        self.leads_cap = leads_cap
        self.calls: list[tuple] = []  # (table, formula, max_records)

    def __call__(self, table, formula="", max_records=50, strict=False):
        self.calls.append((table, formula, max_records))
        if "Payments" in table or "תשלומים" in table:
            return []  # would 403 in real life; must never be called at all in the new path
        if table == "ProjectsHub":
            return self.projectshub
        if table == "משימות (Tasks)":
            return self.tasks
        if table == "Leads":
            domains = _formula_domains(formula)
            result = [
                l for l in self.leads
                if l["fields"]["domain"] in domains
                and l["fields"]["status"] not in _EXCLUDED_STATUSES
            ]
            if self.leads_cap is not None:
                result = result[: self.leads_cap]
            return result
        return []

    def count(self, table: str) -> int:
        return sum(1 for t, _, _ in self.calls if t == table)


# ═════════════════════════════════════════════════════════════════
# 1. _get_project_cards() — bulk query + aggregation (direct unit test)
# ═════════════════════════════════════════════════════════════════
print("\n[1] _get_project_cards() — bulk Leads read + in-memory aggregation")

_orig_at_list = tma_api._at_list
fake = _CountingAirtable()
tma_api._at_list = fake
try:
    cards, hot = tma_api._get_project_cards(_FakeIdentity())

    check("exactly one ProjectsHub read", fake.count("ProjectsHub") == 1)
    check("exactly one Leads read (bulk, not per-card)", fake.count("Leads") == 1)
    check("zero Payments reads", fake.count("Payments") == 0 and fake.count("תשלומים (Payments)") == 0)

    domains_shown = {c["domain"] for c in cards}
    check("saas excluded from cards", "saas" not in domains_shown)
    check("import/recruitment/real_estate all present",
          domains_shown == {"import", "recruitment", "real_estate"})

    leads_formula = render_query(next(f for t, f, _ in fake.calls if t == "Leads"))
    check("bulk Leads formula never references domain='saas'", "domain}='saas'" not in leads_formula)

    import_card = next(c for c in cards if c["domain"] == "import")
    recruitment_card = next(c for c in cards if c["domain"] == "recruitment")
    real_estate_card = next(c for c in cards if c["domain"] == "real_estate")

    check("import card active count = 2 (L1+L2)", import_card["kpi"]["value"] == 2)
    check("import card hot count = 1 (L1 only, L2 score<70)", import_card["exception"] == "1 לידים חמים")
    check("recruitment card active count = 1 (L3)", recruitment_card["kpi"]["value"] == 1)
    check("real_estate card active count = 0 (L4 excluded — archived)", real_estate_card["kpi"]["value"] == 0)
    check("real_estate card has no exception (no hot leads counted)", real_estate_card["exception"] is None)

    check("hot_leads_count = 2 (L1 import + L3 recruitment; L4 excluded status, L5 saas never queried)",
          hot == 2)
finally:
    tma_api._at_list = _orig_at_list


# ═════════════════════════════════════════════════════════════════
# 2. max_records=200 cap → explicit warning logged
# ═════════════════════════════════════════════════════════════════
print("\n[2] max_records cap warning")

import logging

_warnings: list[str] = []


class _CapturingHandler(logging.Handler):
    def emit(self, record):
        _warnings.append(record.getMessage())


handler = _CapturingHandler()
tma_api.logger.addHandler(handler)
tma_api.logger.setLevel(logging.WARNING)

capped_leads = [
    {"id": f"L{i}", "fields": {"domain": "import", "status": "active", LeadFields.SCORE: 50}}
    for i in range(200)
]
fake_capped = _CountingAirtable(leads=capped_leads)
tma_api._at_list = fake_capped
try:
    _warnings.clear()
    cards, hot = tma_api._get_project_cards(_FakeIdentity())
    check("warning logged when bulk Leads read hits max_records=200",
          any("max_records" in w for w in _warnings))
finally:
    tma_api._at_list = _orig_at_list
    tma_api.logger.removeHandler(handler)

# Sanity: no false-positive warning when well under the cap
tma_api._at_list = fake
try:
    _warnings.clear()
    tma_api.logger.addHandler(handler)
    tma_api._get_project_cards(_FakeIdentity())
    check("no warning logged when well under max_records", not any("max_records" in w for w in _warnings))
finally:
    tma_api._at_list = _orig_at_list
    tma_api.logger.removeHandler(handler)


# ═════════════════════════════════════════════════════════════════
# 3. GET /api/projects — real Flask test-client, full instrumentation
# ═════════════════════════════════════════════════════════════════
print("\n[3] Flask test-client — GET /api/projects")

from flask import Flask
from identity import Role


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    return app.test_client()


_client = _make_client()
_HDR = {"X-Telegram-Init-Data": "x"}

_orig_validate = tma_api._validate_initdata
_orig_resolve = tma_api.resolve_identity


class _RouteIdentity:
    role = Role.OWNER
    is_owner = True
    user_id = "1"


tma_api._validate_initdata = lambda s: {"id": "1"}
tma_api.resolve_identity = lambda ch, tid: _RouteIdentity()

fake_route = _CountingAirtable(tasks=[{"id": "T1", "fields": {}}])
tma_api._at_list = fake_route

try:
    r = _client.get("/api/projects", headers=_HDR)
    body = r.get_json()

    check("GET /api/projects -> 200", r.status_code == 200)
    check("exactly one ProjectsHub read", fake_route.count("ProjectsHub") == 1)
    check("exactly one Leads read", fake_route.count("Leads") == 1)
    check("exactly one Tasks read", fake_route.count("משימות (Tasks)") == 1)
    check("zero Payments reads", fake_route.count("Payments") == 0 and fake_route.count("תשלומים (Payments)") == 0)

    check("response has no income_this_month field", "income_this_month" not in body["global_kpis"])
    check("response has no pending_payments_count field", "pending_payments_count" not in body["global_kpis"])
    check("response has no pending_payments_amount field", "pending_payments_amount" not in body["global_kpis"])
    check("response still has overdue_tasks", "overdue_tasks" in body["global_kpis"])
    check("response still has hot_leads_count", "hot_leads_count" in body["global_kpis"])
    check("hot_leads_count reflects only visible active projects", body["global_kpis"]["hot_leads_count"] == 2)

    domains_in_response = {p["domain"] for p in body["projects"]}
    check("saas not present in /api/projects response", "saas" not in domains_in_response)
    check("import/recruitment/real_estate present in /api/projects response",
          domains_in_response == {"import", "recruitment", "real_estate"})
finally:
    tma_api._at_list = _orig_at_list


# ═════════════════════════════════════════════════════════════════
# 4. GET /api/leads?domain=recruitment — one Leads read, zero ProjectsHub
# ═════════════════════════════════════════════════════════════════
print("\n[4] Flask test-client — GET /api/leads?domain=recruitment")

fake_leads_route = _CountingAirtable()
tma_api._at_list = fake_leads_route
try:
    r = _client.get("/api/leads?domain=recruitment", headers=_HDR)
    check("GET /api/leads?domain=recruitment -> 200", r.status_code == 200)
    check("exactly one Leads read", fake_leads_route.count("Leads") == 1)
    check("zero ProjectsHub reads (domain takes priority over project_slug)",
          fake_leads_route.count("ProjectsHub") == 0)
finally:
    tma_api._at_list = _orig_at_list


# ═════════════════════════════════════════════════════════════════
# 5. GET /api/leads?project_slug=... — back-compat fallback still works
# ═════════════════════════════════════════════════════════════════
print("\n[5] project_slug back-compat fallback (backend unchanged)")

fake_slug_route = _CountingAirtable()
tma_api._at_list = fake_slug_route
try:
    r = _client.get("/api/leads?project_slug=recruitment", headers=_HDR)
    check("GET /api/leads?project_slug=recruitment -> 200", r.status_code == 200)
    check("project_slug (no domain given) still resolves via one ProjectsHub read",
          fake_slug_route.count("ProjectsHub") == 1)
finally:
    tma_api._at_list = _orig_at_list
    tma_api._validate_initdata = _orig_validate
    tma_api.resolve_identity = _orig_resolve


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════
print(f"\n{'═'*52}")
print(f"TMA Projects read-path optimization: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
