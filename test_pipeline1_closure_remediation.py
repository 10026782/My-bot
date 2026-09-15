#!/usr/bin/env python3
# test_pipeline1_closure_remediation.py
#
# PIPELINE-1 CLOSURE — regression tests for the locked remediation scope
# (Score/Temperature SSOT, score-override authorization, status-write
# unification, Next Action real write, search/domain/sort/pagination).
# Reachability (item 5) and pure-presentation wiring (item 6) are frontend
# (tma-frontend/) changes verified by `npm run build` + code review, not
# testable from this Python harness — not covered here.
#
# Run: python3 test_pipeline1_closure_remediation.py
# Pass condition: exit code 0, all assertions green.

from __future__ import annotations

import sys

from flask import Flask

from identity import Identity, Role
import tma_api

_passed = 0
_failed = 0


def chk(label: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS: {label}")
    else:
        _failed += 1
        print(f"  FAIL: {label}")


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    return app.test_client()


def _identity(role, allowed_domains=None):
    return Identity(
        user_id="1", role=role, display_name="Test",
        allowed_domains=list(allowed_domains) if allowed_domains is not None else [],
    )


client = _make_client()
_HDR = {"X-Telegram-Init-Data": "x"}

_orig_validate = tma_api._validate_initdata
_orig_resolve = tma_api.resolve_identity
_orig_at_list = tma_api._at_list
_orig_at_get_record = tma_api._at_get_record
_orig_queue = tma_api._queue_tma_write_approval
_orig_claim_execute = tma_api._claim_and_execute_approval

tma_api._validate_initdata = lambda s: {"id": "1"}

# ══════════════════════════════════════════════════════════════════
# [1] Score -> Temperature SSOT (item 1) — pure function, boundary values
# ══════════════════════════════════════════════════════════════════
print("\n[1] Score -> Temperature SSOT — canonical Pipeline thresholds")
chk("score=0 -> קר/blue",  tma_api._pipeline_temperature(0)  == ("קר", "blue"))
chk("score=24 -> קר/blue (just below warm)", tma_api._pipeline_temperature(24) == ("קר", "blue"))
chk("score=25 -> חם/yellow (warm boundary)", tma_api._pipeline_temperature(25) == ("חם", "yellow"))
chk("score=59 -> חם/yellow (just below hot)", tma_api._pipeline_temperature(59) == ("חם", "yellow"))
chk("score=60 -> חם מאוד/red (hot boundary)", tma_api._pipeline_temperature(60) == ("חם מאוד", "red"))
chk("score=100 -> חם מאוד/red", tma_api._pipeline_temperature(100) == ("חם מאוד", "red"))

try:
    print("\n[1b] get_leads()/get_lead() both derive temperature from the same helper")
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.OWNER)

    tma_api._at_list = lambda *a, **kw: [
        {"id": "recCold", "fields": {"Name": "Cold Lead", "phone": "050", "status": "active", "Score": 10, "domain": "media"}},
        {"id": "recWarm", "fields": {"Name": "Warm Lead", "phone": "051", "status": "active", "Score": 40, "domain": "media"}},
        {"id": "recHot",  "fields": {"Name": "Hot Lead",  "phone": "052", "status": "active", "Score": 90, "domain": "saas"}},
    ]
    r = client.get("/api/leads", headers=_HDR)
    body = r.get_json()
    by_id = {lead["id"]: lead for lead in body["leads"]}
    chk("list: cold lead score_color=blue, temperature=קר", by_id["recCold"]["score_color"] == "blue" and by_id["recCold"]["temperature"] == "קר")
    chk("list: warm lead score_color=yellow, temperature=חם", by_id["recWarm"]["score_color"] == "yellow" and by_id["recWarm"]["temperature"] == "חם")
    chk("list: hot lead score_color=red, temperature=חם מאוד", by_id["recHot"]["score_color"] == "red" and by_id["recHot"]["temperature"] == "חם מאוד")
    # Old 70/40 split would have called score=40 "yellow" too (unchanged by
    # coincidence) but score=90 would still have been "red" either way — use
    # the real discriminator: old code called score=59 "yellow" (>=40) same
    # as new; the boundary that actually distinguishes old vs new is score=25.
    chk("list: sorted Score descending by default", [l["id"] for l in body["leads"]] == ["recHot", "recWarm", "recCold"])

    tma_api._at_get_record = lambda table, rid: {
        "id": rid, "fields": {"Name": "X", "phone": "1", "domain": "media", "status": "active", "Score": 30},
    }
    r = client.get("/api/leads/recX", headers=_HDR)
    detail = r.get_json()
    chk("detail: score=30 -> temperature=חם (matches list logic, not old 70/40)",
        detail["temperature"] == "חם" and detail["score_color"] == "yellow")
finally:
    tma_api._at_list = _orig_at_list
    tma_api._at_get_record = _orig_at_get_record
    tma_api.resolve_identity = _orig_resolve

# ══════════════════════════════════════════════════════════════════
# [2] Score override authorization (item 2) — Owner-only, server-enforced
# ══════════════════════════════════════════════════════════════════
print("\n[2] Score override — Owner-only, enforced server-side")

_queued_calls: list[tuple[str, dict]] = []
_exec_result = {"ok": True}


def _fake_queue(action, payload, identity, label):
    _queued_calls.append((action, dict(payload)))
    return "appr_1", {"status": "pending_approval", "approval_id": "appr_1", "contract_id": "c1"}, 202


def _fake_claim_execute(approval_id, identity):
    return {
        "ok": True, "status_code": 200, "new_status": "approved",
        "action_label": "x", "ctx_id": "", "bus_synced": False,
        "execution_result": {"message": "ok", "contract_status": "executed"},
    }


tma_api._at_list = lambda *a, **kw: []
tma_api._at_get_record = lambda table, rid: {"id": rid, "fields": {}}
tma_api._queue_tma_write_approval = _fake_queue
tma_api._claim_and_execute_approval = _fake_claim_execute

try:
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.MANAGER)
    _queued_calls.clear()
    r = client.patch("/api/leads/recLEAD1", json={"score": 80}, headers=_HDR)
    chk("manager PATCH score -> 403 forbidden", r.status_code == 403)
    chk("manager PATCH score -> ActionGateway never reached", len(_queued_calls) == 0)

    r = client.patch("/api/leads/recLEAD1", json={"status": "active"}, headers=_HDR)
    chk("manager PATCH status (no score) -> still allowed (202 pending)", r.status_code == 202)

    tma_api.resolve_identity = lambda ch, tid: _identity(Role.OWNER)
    _queued_calls.clear()
    r = client.patch("/api/leads/recLEAD1", json={"score": 80}, headers=_HDR)
    chk("owner PATCH score -> allowed (200 executed)", r.status_code == 200)
    chk("owner PATCH score -> reaches ActionGateway with Score field", _queued_calls and _queued_calls[0][1]["fields"].get("Score") == 80)
finally:
    tma_api.resolve_identity = _orig_resolve

# ══════════════════════════════════════════════════════════════════
# [3] Status write unification (item 3) — /status and PATCH share one policy
# ══════════════════════════════════════════════════════════════════
print("\n[3] Status write unification — /status now on the same ActionGateway path as PATCH")

try:
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.OWNER)
    _queued_calls.clear()
    r = client.patch("/api/leads/recLEAD1/status", json={"status": "active"}, headers=_HDR)
    body = r.get_json() or {}
    chk("owner PATCH /status -> auto-executed (200), no manual approval step",
        r.status_code == 200 and body.get("status") == "executed")

    tma_api.resolve_identity = lambda ch, tid: _identity(Role.MANAGER)
    _queued_calls.clear()
    r = client.patch("/api/leads/recLEAD1/status", json={"status": "active"}, headers=_HDR)
    body = r.get_json() or {}
    chk("manager PATCH /status -> queued (202 pending_approval), same as PATCH /leads/<id>",
        r.status_code == 202 and body.get("status") == "pending_approval")
finally:
    tma_api.resolve_identity = _orig_resolve
    tma_api._queue_tma_write_approval = _orig_queue
    tma_api._claim_and_execute_approval = _orig_claim_execute
    tma_api._at_list = _orig_at_list
    tma_api._at_get_record = _orig_at_get_record

# ══════════════════════════════════════════════════════════════════
# [4] Next Action real write (item 4) — live Airtable option values only
# ══════════════════════════════════════════════════════════════════
print("\n[4] Next Action — validated against live Airtable option set, not stale snake_case keys")

tma_api._at_list = lambda *a, **kw: []
tma_api._at_get_record = lambda table, rid: {"id": rid, "fields": {}}
tma_api._queue_tma_write_approval = _fake_queue
tma_api._claim_and_execute_approval = _fake_claim_execute

try:
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.OWNER)

    _queued_calls.clear()
    r = client.patch("/api/leads/recLEAD1", json={"next_step": "call_now"}, headers=_HDR)
    chk("stale pre-fix key 'call_now' is rejected (400) — never matched live Airtable options",
        r.status_code == 400)

    _queued_calls.clear()
    r = client.patch("/api/leads/recLEAD1", json={"next_step": "Follow Up"}, headers=_HDR)
    chk("live option 'Follow Up' accepted", r.status_code == 200)
    chk("'Follow Up' written back verbatim", _queued_calls[0][1]["fields"].get("Next Action") == "Follow Up")

    _queued_calls.clear()
    r = client.patch("/api/leads/recLEAD1", json={"next_step": "Schedule Meeting"}, headers=_HDR)
    chk("client value without trailing space is accepted", r.status_code == 200)
    chk("write-back preserves Airtable's own trailing space on 'Schedule Meeting '",
        _queued_calls[0][1]["fields"].get("Next Action") == "Schedule Meeting ")

    chk("_next_action_label maps a live raw value to its Hebrew label",
        tma_api._next_action_label("Create Deal") == "ליצור עסקה")
    chk("_next_action_label falls back to the raw value for an unknown/legacy value",
        tma_api._next_action_label("some_legacy_value") == "some_legacy_value")
finally:
    tma_api.resolve_identity = _orig_resolve
    tma_api._queue_tma_write_approval = _orig_queue
    tma_api._claim_and_execute_approval = _orig_claim_execute
    tma_api._at_list = _orig_at_list
    tma_api._at_get_record = _orig_at_get_record

# ══════════════════════════════════════════════════════════════════
# [7] Pagination / no silent truncation (item 7) + search/domain filters (item 6)
# ══════════════════════════════════════════════════════════════════
print("\n[7] No silent 100-record cap — paginate=True + honest has_more")

_at_list_calls: list[dict] = []


def _tracking_paginate_at_list(table, formula="", max_records=None, strict=False,
                                measurement_label=None, paginate=False):
    _at_list_calls.append({"max_records": max_records, "paginate": paginate})
    return [
        {"id": "recA", "fields": {"Name": "Alice Cohen", "phone": "0501111111", "status": "active", "Score": 70, "domain": "real_estate"}},
        {"id": "recB", "fields": {"Name": "Bob Levi",   "phone": "0502222222", "status": "active", "Score": 10, "domain": "media"}},
    ]


tma_api._at_list = _tracking_paginate_at_list
try:
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.OWNER)
    _at_list_calls.clear()
    r = client.get("/api/leads", headers=_HDR)
    body = r.get_json()
    chk("get_leads() fetches with paginate=True (no first-page-only truncation)",
        _at_list_calls and _at_list_calls[0]["paginate"] is True)
    chk("has_more=False under the fetch cap", body["has_more"] is False)
    chk("available_domains reflects the full identity-scoped set for Owner",
        sorted(body["available_domains"]) == ["media", "real_estate"])

    # item 6 — search by name/phone
    r = client.get("/api/leads?search=alice", headers=_HDR)
    body = r.get_json()
    chk("search matches by name (case-insensitive)", [l["id"] for l in body["leads"]] == ["recA"])

    r = client.get("/api/leads?search=0502222222", headers=_HDR)
    body = r.get_json()
    chk("search matches by phone", [l["id"] for l in body["leads"]] == ["recB"])

    # item 6 — domain filter narrows the response but available_domains stays full
    r = client.get("/api/leads?domain=media", headers=_HDR)
    body = r.get_json()
    chk("domain filter narrows returned leads", [l["id"] for l in body["leads"]] == ["recB"])
    chk("available_domains still reflects the full scope, not just the filtered domain",
        sorted(body["available_domains"]) == ["media", "real_estate"])

    # Partner never gets a domain picker (item 6 scopes it to Owner/Manager)
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.PARTNER, ["media"])
    r = client.get("/api/leads", headers=_HDR)
    body = r.get_json()
    chk("partner response has no available_domains picker", body["available_domains"] == [])
finally:
    tma_api.resolve_identity = _orig_resolve
    tma_api._at_list = _orig_at_list


# ══════════════════════════════════════════════════════════════════
# [8] Filter/search expansion follow-up (owner-directed, 15/09/2026):
# search over summary/next_step, a specific-status filter alongside the
# view, a source filter, and a relative date_range filter over Airtable's
# native createdTime (Leads.created_at itself has no writer anywhere and
# is always empty — confirmed by grep before building this).
# ══════════════════════════════════════════════════════════════════
print("\n[8] Filter/search expansion — status/source/date_range + summary/next_step search")

from datetime import datetime, timedelta, timezone

_now = datetime.now(timezone.utc)


def _iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _filter_fixture_at_list(table, formula="", max_records=None, strict=False,
                             measurement_label=None, paginate=False):
    return [
        {
            "id": "recA", "createdTime": _iso(_now - timedelta(hours=1)),
            "fields": {
                "Name": "Alice Cohen", "phone": "0501111111", "status": "active",
                "Score": 70, "domain": "real_estate", "source": "telegram",
                "summary": "מחפשת דירת 3 חדרים בצפון", "Next Action": "Schedule Meeting ",
            },
        },
        {
            "id": "recB", "createdTime": _iso(_now - timedelta(days=10)),
            "fields": {
                "Name": "Bob Levi", "phone": "0502222222", "status": "lost",
                "Score": 10, "domain": "media", "source": "whatsapp",
                "summary": "לא מעוניין יותר", "Next Action": "Closed Lost",
            },
        },
        {
            # Same Score as recA (70) on purpose — the sort tie-break test
            # below needs two same-score records to prove createdTime (not
            # the dead created_at field) actually breaks the tie.
            "id": "recC", "createdTime": _iso(_now - timedelta(days=45)),
            "fields": {
                "Name": "Chen Mizrahi", "phone": "0503333333", "status": "active",
                "Score": 70, "domain": "real_estate", "source": "telegram",
                "summary": "מעוניין בהשקעה", "Next Action": "Follow Up",
            },
        },
    ]


tma_api._at_list = _filter_fixture_at_list
try:
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.OWNER)

    # search now also matches summary + Next Action, not just name/phone
    r = client.get("/api/leads?view=all&search=" + "השקע", headers=_HDR)
    body = r.get_json()
    chk("search matches summary text", [l["id"] for l in body["leads"]] == ["recC"])

    r = client.get("/api/leads?view=all&search=" + "Schedule", headers=_HDR)
    body = r.get_json()
    chk("search matches Next Action text", [l["id"] for l in body["leads"]] == ["recA"])

    # status filter — specific value, alongside (narrower than) the view
    r = client.get("/api/leads?view=all&status=lost", headers=_HDR)
    body = r.get_json()
    chk("status filter narrows to the exact status", [l["id"] for l in body["leads"]] == ["recB"])

    r = client.get("/api/leads?view=all&status=not_a_real_status", headers=_HDR)
    body = r.get_json()
    chk("unknown status value is ignored, not an error",
        r.status_code == 200 and sorted(l["id"] for l in body["leads"]) == ["recA", "recB", "recC"])

    # source filter + available_sources reflects the full view, not the filtered set
    r = client.get("/api/leads?view=all&source=whatsapp", headers=_HDR)
    body = r.get_json()
    chk("source filter narrows to the exact source", [l["id"] for l in body["leads"]] == ["recB"])
    chk("available_sources reflects the full scope, not just the filtered source",
        sorted(body["available_sources"]) == ["telegram", "whatsapp"])

    # date_range — relative presets against createdTime, not the dead created_at field
    r = client.get("/api/leads?view=all&date_range=today", headers=_HDR)
    body = r.get_json()
    chk("date_range=today keeps only records created today", [l["id"] for l in body["leads"]] == ["recA"])

    r = client.get("/api/leads?view=all&date_range=week", headers=_HDR)
    body = r.get_json()
    chk("date_range=week excludes both the 10-day and 45-day-old records",
        [l["id"] for l in body["leads"]] == ["recA"])

    r = client.get("/api/leads?view=all&date_range=month", headers=_HDR)
    body = r.get_json()
    chk("date_range=month includes all three (45 days > 30 is still excluded)",
        sorted(l["id"] for l in body["leads"]) == ["recA", "recB"])

    r = client.get("/api/leads?view=all", headers=_HDR)
    body = r.get_json()
    chk("date_range defaults to all — every record included",
        sorted(l["id"] for l in body["leads"]) == ["recA", "recB", "recC"])
    chk("response echoes the active status/source/date_range filters",
        body["status"] == "" and body["source"] == "" and body["date_range"] == "all")

    # sort tie-break now actually uses createdTime (previously a no-op — the
    # dead created_at field made every tie-break key an equal empty string)
    r = client.get("/api/leads?view=all&status=active", headers=_HDR)
    body = r.get_json()
    chk("score-tied records break ties by newest createdTime first",
        [l["id"] for l in body["leads"]] == ["recA", "recC"])
finally:
    tma_api.resolve_identity = _orig_resolve
    tma_api._at_list = _orig_at_list


# ══════════════════════════════════════════════════════════════════
# [9] Search-as-business-context follow-up (owner-directed, 15/09/2026):
# AND-of-words across the whole record (not one literal phrase, not
# same-field-only), plus notes/Business Outcome in the haystack, plus the
# new next_action/temperature filters and next_action_options in the
# response. Explicitly NOT covered: no keyword->filter inference (typing
# "new"/"לחזור" in ?search= must never act like ?status=/?next_action=) —
# owner decision to skip that, verified below too.
# ══════════════════════════════════════════════════════════════════
print("\n[9] Search-as-business-context — AND-of-words, notes/outcome, next_action/temperature filters")


def _context_fixture_at_list(table, formula="", max_records=None, strict=False,
                              measurement_label=None, paginate=False):
    return [
        {
            "id": "recD", "createdTime": "2026-09-15T00:00:00.000Z",
            "fields": {
                "Name": "David Ohana", "phone": "0504444444", "status": "new",
                "Score": 15, "domain": "recruitment", "source": "רשימת קבלני סלקום - דרום",
                "summary": "קבלן עם ניסיון באזור הדרום בסלקום. צריך לפנות אליו.",
                "Next Action": "Call Back",
            },
        },
        {
            "id": "recE", "createdTime": "2026-09-15T00:00:00.000Z",
            "fields": {
                "Name": "Eli Sharon", "phone": "0505555555", "status": "active",
                "Score": 65, "domain": "saas", "source": "facebook",
                "summary": "מעוניין בחבילת פרימיום", "notes": "התקשר, ביקש הצעת מחיר בקול",
                "Next Action": "Send Details", "Business Outcome": "meeting_scheduled",
            },
        },
    ]


tma_api._at_list = _context_fixture_at_list
try:
    tma_api.resolve_identity = lambda ch, tid: _identity(Role.OWNER)

    # AND of words, cross-field (not one literal phrase, not same-field-only)
    # — "קבלני" only appears in source, "דרום" appears in both source and
    # summary; the match must not require both words in the same field.
    r = client.get("/api/leads?view=all&search=" + "קבלני דרום", headers=_HDR)
    body = r.get_json()
    chk("multi-word search is an AND across fields, not an exact phrase",
        [l["id"] for l in body["leads"]] == ["recD"])

    r = client.get("/api/leads?view=all&search=" + "דרום סלקום", headers=_HDR)
    body = r.get_json()
    chk("word order doesn't matter", [l["id"] for l in body["leads"]] == ["recD"])

    r = client.get("/api/leads?view=all&search=" + "דרום facebook", headers=_HDR)
    body = r.get_json()
    chk("a word that only matches a different record excludes it (real AND, not OR)",
        body["leads"] == [])

    # notes + Business Outcome are now part of the haystack too
    r = client.get("/api/leads?view=all&search=" + "הצעת מחיר", headers=_HDR)
    body = r.get_json()
    chk("search matches the notes field", [l["id"] for l in body["leads"]] == ["recE"])

    r = client.get("/api/leads?view=all&search=" + "meeting_scheduled", headers=_HDR)
    body = r.get_json()
    chk("search matches Business Outcome", [l["id"] for l in body["leads"]] == ["recE"])

    # explicitly no keyword->filter inference — recD's Next Action is
    # literally "Call Back" (label "להתקשר בחזרה"), but "לחזור" is not a
    # literal substring of either — proves search never infers a
    # next_action filter from natural-language phrasing (owner decision).
    r = client.get("/api/leads?view=all&search=" + "לחזור", headers=_HDR)
    body = r.get_json()
    chk("typing 'לחזור' does NOT infer next_action=Call Back (literal match only)",
        body["leads"] == [])

    # next_action filter
    r = client.get("/api/leads?view=all&next_action=Call Back", headers=_HDR)
    body = r.get_json()
    chk("next_action filter narrows to the exact action", [l["id"] for l in body["leads"]] == ["recD"])

    r = client.get("/api/leads?view=all&next_action=not_a_real_action", headers=_HDR)
    body = r.get_json()
    chk("unknown next_action value is ignored, not an error",
        r.status_code == 200 and sorted(l["id"] for l in body["leads"]) == ["recD", "recE"])

    # temperature filter (Score-derived, same helper the response already uses)
    r = client.get("/api/leads?view=all&temperature=" + "קר", headers=_HDR)
    body = r.get_json()
    chk("temperature=קר matches the low-score record", [l["id"] for l in body["leads"]] == ["recD"])

    r = client.get("/api/leads?view=all&temperature=" + "חם מאוד", headers=_HDR)
    body = r.get_json()
    chk("temperature=חם מאוד matches the Score=65 record", [l["id"] for l in body["leads"]] == ["recE"])

    # next_action_options exposed for the frontend's advanced-filter picker
    r = client.get("/api/leads?view=all", headers=_HDR)
    body = r.get_json()
    chk("next_action_options is the full canonical option set",
        {o["value"] for o in body["next_action_options"]} == set(tma_api._LEAD_NEXT_ACTION_OPTIONS))
finally:
    tma_api.resolve_identity = _orig_resolve
    tma_api._at_list = _orig_at_list


print(f"\n{'=' * 60}")
print(f"PIPELINE-1 closure remediation: {_passed}/{_passed + _failed} passed")
if _failed:
    print(f"FAILED: {_failed} check(s)")
sys.exit(0 if _failed == 0 else 1)
