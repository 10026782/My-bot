#!/usr/bin/env python3
"""
test_bug161_agent_no_reconfirmation_promise.py — BUG-161 regression suite.

Root cause: when a create_task request lands in the generic Agent tool-use
loop (Handler.AGENT fallback — e.g. via BUG-160's unbalanced-quote bypass,
or any other fallback reason) and its fingerprint matches an already-
`rejected` ActionContract, the Agent free-generated an invitation to
"explicitly reconfirm" ("אם אתה רוצה ליצור משימה זו בכל זאת — אנא אשר זאת
בבירור.") — a promise the runtime cannot honor. `core/action_gateway.py`'s
`ActionGateway.propose_action()` (lines ~1622-1643) already, and
unconditionally, blocks any subsequent real tool_use attempt from
`trusted_source != "deterministic_create_task"` against a rejected
fingerprint (BUG-153's carve-out stays narrow, per the owner's BUG-161
policy decision, 07/08/2026: "do not expand Agent reconfirmation").

Fix (this round): a new explicit honesty rule was added to
`core_knowledge.py`'s `STATIC_MANIFEST` (the "חוקי כנות" / honesty-rules
block, same location as the pre-existing Telegram-buttons-only approval
rule) instructing the Agent to never offer free-text reconfirmation for an
already-rejected action, and instead to state the action was cancelled and
point the user at sending a new, explicit create request. This is a
prompt-level constraint, not a code-logic change — there is no regex/code
path that can reliably classify arbitrary LLM-generated free text as "an
invented reconfirmation promise" (see BUG-127C's own conclusion: this class
of semantic distinction is not safely solvable at the A32/regex layer).

This file does NOT (and cannot) prove the Agent will never emit the
fabricated phrasing again — that would require live model behavior, out of
scope for a static test. It proves the STRUCTURAL preconditions this fix
depends on:
  1. The new honesty-rule line is present in STATIC_MANIFEST, phrased as an
     unconditional "🔴" hard rule matching the file's existing convention.
  2. It sits inside the same "חוקי כנות — אסור לעבור עליהם" block as the
     pre-existing Telegram-buttons-only approval rule (BUG-161 is the same
     category of gap: an Agent free-text invention of an approval/
     reconfirmation mechanism that does not structurally exist).
  3. The Gateway's own already-unmodified block message for this exact
     scenario (`build_approval_lifecycle_result(existing,
     canonical_state="rejected", repeated=True)`, is_task_creation=True) is
     truthful and non-fabricated ("יצירת המשימה כבר בוטלה") — confirming
     the deterministic backstop this prompt rule defers to has not
     regressed and did not need to change.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from core_knowledge import STATIC_MANIFEST  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


HONESTY_BLOCK_MARKER = "חוקי כנות — אסור לעבור עליהם:"
EXISTING_APPROVAL_RULE = "אישור = כפתורי Telegram בלבד"
NEW_RULE_MARKER = "פעולה שכבר בוטלה/נדחתה"

chk(
    "STATIC_MANIFEST contains the BUG-161 honesty rule "
    "(no free-text reconfirmation promise)",
    NEW_RULE_MARKER in STATIC_MANIFEST,
)

honesty_block_start = STATIC_MANIFEST.find(HONESTY_BLOCK_MARKER)
chk("the honesty-rules block itself exists (pre-existing anchor)",
    honesty_block_start != -1)

new_rule_pos = STATIC_MANIFEST.find(NEW_RULE_MARKER)
approval_rule_pos = STATIC_MANIFEST.find(EXISTING_APPROVAL_RULE)
chk(
    "the new rule sits after the honesty-block marker (same block, not "
    "a stray line elsewhere in the manifest)",
    honesty_block_start != -1 and new_rule_pos > honesty_block_start,
)
chk(
    "the new rule sits immediately after the existing "
    "Telegram-buttons-only approval rule (same category of gap, adjacent "
    "placement)",
    approval_rule_pos != -1
    and new_rule_pos != -1
    and 0 < (new_rule_pos - approval_rule_pos) < 250,
)
chk(
    "the new rule is phrased as an unconditional 🔴 hard rule, matching "
    "the file's existing convention for non-negotiable honesty rules",
    "🔴 פעולה שכבר בוטלה/נדחתה" in STATIC_MANIFEST,
)

# ── Gateway backstop: confirm the deterministic block message this prompt
#    rule defers to is still truthful and unmodified — no code path in
#    action_gateway.py changed as part of BUG-161. ───────────────────────
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug161-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG161_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug161Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug161Test")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.action_gateway import ActionContract, build_approval_lifecycle_result  # noqa: E402

_fake_contract = ActionContract(
    contract_id="fake-rejected-contract-id",
    tenant_id="boss_hq",
    canonical_user_id="test_user",
    tool_name="airtable_add",
    normalized_payload={"table": "Tasks", "fields": {"title": "בדיקת BUG-161"}},
    business_action_fingerprint="fp-bug161-test",
    origin_channel="telegram",
    origin_chat_id="test_user",
    requires_approval=True,
    status="rejected",
    created_at=1.0,
)

result = build_approval_lifecycle_result(
    _fake_contract, canonical_state="rejected", repeated=True,
)
chk(
    "Gateway's rejected/repeated block message is truthful ('כבר בוטלה'), "
    "not a fabricated reconfirmation invitation — unmodified backstop",
    result.safe_user_message.startswith("יצירת המשימה כבר בוטלה")
    and "אשר" not in result.safe_user_message,
)
chk(
    "Gateway's block message declares reply_owner=gateway (single-speaker "
    "backstop still intact)",
    result.reply_owner == "gateway",
)

print(f"\n{'═'*45}")
print(f"  {passed}/{passed+failed} passed")

sys.exit(0 if failed == 0 else 1)
