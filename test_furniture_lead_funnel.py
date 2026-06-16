#!/usr/bin/env python3
"""Focused tests for the deterministic furniture WhatsApp funnel."""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import patch

import furniture_lead_funnel as funnel
from session_store import PersistentSessionStore


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

    store = PersistentSessionStore(maxsize=10)
    saved: list[tuple[str, str, dict]] = []

    session_mod = types.ModuleType("session_store")
    session_mod.lead_sessions = store

    at_tools = types.ModuleType("tools.airtable_tools")
    at_tools.airtable_get = lambda table, formula: ""

    at_gateway = types.ModuleType("tools.airtable_gateway")
    at_gateway.airtable_create = lambda table, fields, source="": (
        saved.append(("create", table, dict(fields))),
        {"id": "recLead1", "fields": fields},
    )[1]
    at_gateway.airtable_patch = lambda table, rec_id, fields, source="": (
        saved.append(("patch", rec_id, dict(fields))),
        True,
    )[1]

    with patch.dict(sys.modules, {
        "session_store": session_mod,
        "tools.airtable_tools": at_tools,
        "tools.airtable_gateway": at_gateway,
    }):
        sender = "+972501111111"
        replies = [
            funnel.handle_furniture_lead_message(sender, "שלום", funnel.DOMAIN),
            funnel.handle_furniture_lead_message(sender, "אני מעוניין במיטה", funnel.DOMAIN),
            funnel.handle_furniture_lead_message(sender, "דוד כהן", funnel.DOMAIN),
            funnel.handle_furniture_lead_message(sender, "ירושלים", funnel.DOMAIN),
            funnel.handle_furniture_lead_message(sender, "2", funnel.DOMAIN),
            funnel.handle_furniture_lead_message(sender, "צריך עד מחר", funnel.DOMAIN),
            funnel.handle_furniture_lead_message(sender, "ניתן להתקשר 9-11 בבוקר", funnel.DOMAIN),
        ]

    # ── Reply sequence ─────────────────────────────────────────────
    chk("step0: greeting", replies[0] == funnel.STEP_0_INTRO)
    chk("step1: includes product info", funnel.STEP_1_PRODUCT_INFO in replies[1])
    chk("step1: asks name", funnel.STEP_2_ASK_NAME in replies[1])
    chk("step2: asks city", replies[2] == funnel.STEP_3_ASK_CITY)
    chk("step3: asks bed count", replies[3] == funnel.STEP_4_ASK_BED_COUNT)
    chk("step4: asks needed date", replies[4] == funnel.STEP_5_ASK_NEEDED_DATE)
    chk("step5: asks call permission", replies[5] == funnel.STEP_6_ASK_CALL_PERMISSION)
    chk("step6: done message", replies[6] == funnel.STEP_7_DONE)

    # ── Session state ───────────────────────────────────────────────
    final_session = store.get(sender)
    chk("session is done", bool(final_session and final_session.get("done") is True))
    chk("conversation_step is step_7_done", final_session.get("conversation_step") == "step_7_done")

    # ── Saved fields ────────────────────────────────────────────────
    final_fields = saved[-1][2]
    chk("status qualified after name", final_fields.get("status") == "QUALIFIED_BASIC")
    chk("score is HOT threshold", final_fields.get("Score", 0) >= 60)
    chk("summary includes bed count", "מיטות" in (final_fields.get("summary") or ""))

    answers = json.loads(final_fields.get("answers", "{}"))
    chk("bed_count saved", bool(answers.get("bed_count")))
    chk("call_permission saved", bool(answers.get("call_permission")))
    chk("needed_date saved", bool(answers.get("needed_date")))
    chk("name saved", answers.get("name") == "דוד כהן")
    chk("city saved", answers.get("city") == "ירושלים")

    # ── Negative: no unexpected fields ─────────────────────────────
    chk("does not write tier", "tier" not in final_fields)
    chk("does not write created_at", "created_at" not in final_fields)
    chk("does not write updated_at", "updated_at" not in final_fields)

    # ── Wrong domain: funnel must not activate ──────────────────────
    store2 = PersistentSessionStore(maxsize=10)
    session_mod2 = types.ModuleType("session_store")
    session_mod2.lead_sessions = store2
    with patch.dict(sys.modules, {"session_store": session_mod2,
                                   "tools.airtable_tools": at_tools,
                                   "tools.airtable_gateway": at_gateway}):
        result = funnel.handle_furniture_lead_message("+972509999999", "שלום", "real_estate")
    chk("wrong domain returns None", result is None)

    print(f"\nFurniture funnel tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
