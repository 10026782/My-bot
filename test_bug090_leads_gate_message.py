#!/usr/bin/env python3
"""
test_bug090_leads_gate_message.py — BUG-090 regression suite.

enforce_leads_write_gate()'s single fixed message ("כתיבה ישירה ל-Leads
חסומה. השתמש ב-capture_inbound_lead() בלבד.") was wrong for the
airtable_update case (capture_inbound_lead() is the inbound-create path,
irrelevant to updating an existing Lead) and leaked an internal function
name to the end user. Fixed to split by tool_name, without touching the
gate's blocking behavior itself (scope: message content only).

מאמת:
1. airtable_update on Leads (source=agent) is still blocked (gate behavior
   unchanged — BUG-090 is message-only, per explicit scope).
2. The update message points the user to the TMA/Leads screen, not
   capture_inbound_lead().
3. Neither message (create or update) mentions capture_inbound_lead() or
   any other internal function name.
4. Neither message includes the old debug suffix ("tool=... source=...") —
   single clean user-facing message, debug detail stays in the log only.
5. airtable_add on Leads (source=agent) is still blocked, with its own
   (create-oriented) message, distinct from the update message.
6. Non-Leads tables and authorized sources are unaffected (gate behavior
   regression, not just message content).
"""

from __future__ import annotations

import sys

from tools.airtable_security import (
    enforce_leads_write_gate,
    LeadsDirectWriteBlocked,
    _leads_write_blocked_message,
)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _blocked_message(tool_name: str, table: str = "Leads", source: str = "agent") -> str:
    try:
        enforce_leads_write_gate(tool_name, {"table": table}, source=source)
        return ""
    except LeadsDirectWriteBlocked as e:
        return str(e)


# ══════════════════════════════════════════════════════════════════
# 1. Gate behavior unchanged — still blocks
# ══════════════════════════════════════════════════════════════════
print("\n── gate still blocks (message-only scope) ────")

update_msg = _blocked_message("airtable_update")
chk("airtable_update source=agent on Leads is still blocked", update_msg != "")

add_msg = _blocked_message("airtable_add")
chk("airtable_add source=agent on Leads is still blocked", add_msg != "")

# ══════════════════════════════════════════════════════════════════
# 2. Update message points to the TMA / Leads screen
# ══════════════════════════════════════════════════════════════════
print("\n── update message: correct guidance ──────────")

chk("update message tells the user to use the Leads screen in the app",
    "מסך הלידים באפליקציה" in update_msg)
chk("update message explicitly names it as an update-existing-lead scenario",
    "עדכון ליד קיים" in update_msg)

# ══════════════════════════════════════════════════════════════════
# 3. Neither message exposes capture_inbound_lead() or any internal name
# ══════════════════════════════════════════════════════════════════
print("\n── no internal function names leaked ─────────")

chk("update message does not mention capture_inbound_lead()",
    "capture_inbound_lead" not in update_msg)
chk("create message does not mention capture_inbound_lead()",
    "capture_inbound_lead" not in add_msg)
chk("update message has no bare '()' suggesting a function name",
    "()" not in update_msg)
chk("create message has no bare '()' suggesting a function name",
    "()" not in add_msg)

# ══════════════════════════════════════════════════════════════════
# 4. No debug suffix (tool=/source=) in the user-facing message
# ══════════════════════════════════════════════════════════════════
print("\n── single clean message, no debug suffix ─────")

chk("update message has no 'tool=' debug suffix", "tool=" not in update_msg)
chk("update message has no 'source=' debug suffix", "source=" not in update_msg)
chk("create message has no 'tool=' debug suffix", "tool=" not in add_msg)
chk("create message has no 'source=' debug suffix", "source=" not in add_msg)

# ══════════════════════════════════════════════════════════════════
# 5. Create vs update messages are distinct
# ══════════════════════════════════════════════════════════════════
print("\n── create/update messages are distinct ───────")

chk("create and update messages are not identical", add_msg != update_msg)
chk("create message talks about new leads being created automatically",
    "נוצרים אוטומטית" in add_msg)

# airtable_patch (legacy alias in _LEADS_WRITE_OPS) groups with update.
patch_msg_direct = _leads_write_blocked_message("airtable_patch")
chk("airtable_patch groups with the update message (same wording)",
    patch_msg_direct == _leads_write_blocked_message("airtable_update"))

# ══════════════════════════════════════════════════════════════════
# 6. Regression: non-Leads tables and authorized sources unaffected
# ══════════════════════════════════════════════════════════════════
print("\n── regression: gate scope unchanged ──────────")

no_block_other_table = _blocked_message("airtable_update", table="Business Memory")
chk("non-Leads table is never blocked by this gate", no_block_other_table == "")

no_block_authorized = _blocked_message("airtable_update", source="lead_capture")
chk("source=lead_capture on Leads is still authorized (not blocked)", no_block_authorized == "")

no_block_read = _blocked_message("airtable_get")
chk("airtable_get (not a write op) is never blocked by this gate", no_block_read == "")

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
