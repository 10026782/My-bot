#!/usr/bin/env python3
"""Focused tests for the F06 inbound lead gate (inbound_handler.py)."""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

import inbound_handler as handler


def run() -> bool:
    passed = failed = 0

    def chk(desc: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            print(f"PASS {desc}")
            passed += 1
        else:
            print(f"FAIL {desc}")
            failed += 1

    adds: list[tuple[str, dict]] = []       # (table, fields) for every airtable_add call
    patches: list[tuple[str, str, dict]] = []
    existing_external: dict[str, str] = {}   # external_id -> record_id
    existing_sender: dict[str, str] = {}      # sender_id -> record_id

    def fake_airtable_get(table, formula):
        if "external_id" in formula:
            for ext_id, rec_id in existing_external.items():
                if ext_id in formula:
                    return f"[{rec_id}]"
        if "sender_id" in formula:
            for sender, rec_id in existing_sender.items():
                if sender in formula:
                    return f"[{rec_id}]"
        return "📭 אין רשומות"

    def fake_airtable_add(table, fields):
        adds.append((table, dict(fields)))
        return "✅ רשומה נוספה | ID: recNew123"

    def fake_airtable_patch(table, record_id, fields, source="unknown"):
        patches.append((table, record_id, dict(fields)))
        return True

    at_tools = types.ModuleType("tools.airtable_tools")
    at_tools.airtable_get = fake_airtable_get
    at_tools.airtable_add = fake_airtable_add

    at_gateway = types.ModuleType("tools.airtable_gateway")
    at_gateway.airtable_patch = fake_airtable_patch

    def leads(): return [t for t, f in adds if t == "Leads"]

    with patch.dict(sys.modules, {
        "tools.airtable_tools": at_tools,
        "tools.airtable_gateway": at_gateway,
    }), patch.object(handler, "is_enabled", lambda name: name == "LEAD_CAPTURE"):

        # A — duplicate external_id → skip, no create
        existing_external["gmail:msg123"] = "recDup1"
        handler.handle_inbound(
            sender_id="x@y.com", message="test", channel="email",
            domain="import", external_id="gmail:msg123",
        )
        chk("A: duplicate external_id → no create call", len(leads()) == 0)

        # C — brand new lead → create called
        handler.handle_inbound(
            sender_id="new@test.com", message="רוצה מיטה", channel="email",
            domain="import", external_id="gmail:abc123",
        )
        chk("C: new lead → create called once", len(leads()) == 1)
        table, fields = next(a for a in adds if a[0] == "Leads")
        chk("C: created in Leads table", table == "Leads")
        chk("C: external_id stored", fields.get("external_id") == "gmail:abc123")
        chk("C: sender_id stored", fields.get("sender_id") == "new@test.com")
        chk("C: domain stored", fields.get("domain") == "import")

        # B — known sender → update, not create
        existing_sender["dani@test.com"] = "recDani1"
        handler.handle_inbound(
            sender_id="dani@test.com", message="שאלה חדשה", channel="email",
            domain="real_estate", external_id="gmail:new_msg",
        )
        chk("B: known sender → update called", len(patches) == 1)
        chk("B: known sender → no new lead create", len(leads()) == 1)

        # E — flag OFF → zero Airtable calls
        adds.clear()
        patches.clear()
        with patch.object(handler, "is_enabled", lambda name: False):
            handler.handle_inbound(
                sender_id="ghost@test.com", message="hello", channel="email",
                domain="general", external_id="gmail:ghost1",
            )
        chk("E: flag OFF → no add", len(adds) == 0)
        chk("E: flag OFF → no patch", len(patches) == 0)

        # junk message → ignored even with flag on
        handler.handle_inbound(
            sender_id="junk@test.com", message="..", channel="email",
            domain="general", external_id="gmail:junk1",
        )
        chk("junk message → no create", len(leads()) == 0)

    print(f"\n{'='*40}")
    print(f"inbound_handler Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = run()
    exit(0 if ok else 1)
