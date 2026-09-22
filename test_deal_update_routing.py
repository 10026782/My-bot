#!/usr/bin/env python3
"""
test_deal_update_routing.py — DEAL UPDATE LIVE ROUTING REMEDIATION.

Phase 3 runtime canary found that natural-language Deal-update requests
never reached crm_update_deal/BusinessDraft: three live attempts all fell
through to the generic airtable_get -> airtable_update path instead. Root
cause: crm_update_deal was a registered, _MANAGEMENT-authorized tool
(tool_registry.py) that was simply never added to context.py's per-role
tool-exposure set, so the agent could never select it — plus a stale
core/router/risk_router.py PA-01 policy entry that still pointed
Intent.UPDATE_DEAL_STAGE at "airtable_update". A separate regression
(reported alongside): the canonical stage value "במשא ומתן" was extracted
as "משא ומתן" (leading "ב" dropped), rejected by update_deal()'s closed
stage validation.

Asserts:
1. crm_update_deal is exposed to owner/partner/manager (the routing fix).
2. crm_create_deal stays UNexposed (Deal CREATE's deterministic-parser path
   is out of scope and must not change).
3. Intent.UPDATE_DEAL_STAGE's PA-01 contract-expected tool is
   crm_update_deal, not the stale airtable_update.
4. update_deal() accepts the "ב"-dropped stage alias and persists the exact
   canonical value; the canonical value itself still passes through
   unchanged (no broad loosening).
5. update_deal() fails closed (never reaches the Airtable write) for a
   malformed record_id and for a well-formed-but-nonexistent one.
"""

from __future__ import annotations

from unittest.mock import patch

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# 1-2. Tool exposure (context.py::_ROLE_TOOLS)
# ══════════════════════════════════════════════════

from identity import Role
from context import _ROLE_TOOLS

for _role in (Role.OWNER, Role.PARTNER, Role.MANAGER):
    chk(f"crm_update_deal exposed to {_role}", "crm_update_deal" in _ROLE_TOOLS[_role])
    chk(f"crm_create_deal stays unexposed to {_role} (CREATE path unchanged)",
        "crm_create_deal" not in _ROLE_TOOLS[_role])

# ══════════════════════════════════════════════════
# 3. PA-01 contract-expected-tool policy (core/router/risk_router.py)
# ══════════════════════════════════════════════════

from core.router.route_decision import Intent
from core.router.risk_router import expected_tool_for_intent

chk(
    "Intent.UPDATE_DEAL_STAGE now expects crm_update_deal",
    expected_tool_for_intent(Intent.UPDATE_DEAL_STAGE) == "crm_update_deal",
)
chk(
    "Intent.CREATE_DEAL still expects crm_create_deal (unchanged)",
    expected_tool_for_intent(Intent.CREATE_DEAL) == "crm_create_deal",
)

# ══════════════════════════════════════════════════
# 4-5. commercial_crm.update_deal() — stage alias + fail-closed record_id
# ══════════════════════════════════════════════════

import commercial_crm

VALID_RECORD_ID = "recAAAAAAAAAAAAAA"      # well-formed, matches rec[A-Za-z0-9]{14}
MALFORMED_RECORD_ID = "not-a-real-id"


def _update_with_mocked_write(record_id, fields, *, patch_returns=True):
    """Runs update_deal() with airtable_patch mocked so no live Airtable call
    is ever made — this test never touches Airtable, live or otherwise."""
    with patch.object(commercial_crm, "airtable_patch", return_value=patch_returns) as mock_patch, \
         patch(
             "core.runtime_schema_provider.resolve_live_select_value",
             side_effect=lambda table, field, value: value,
         ):
        result = commercial_crm.update_deal(record_id, fields, source="test")
    return result, mock_patch


result, mock_patch = _update_with_mocked_write(VALID_RECORD_ID, {"stage": "משא ומתן"})
chk("stage alias 'משא ומתן' (no ב) is accepted", result.get("ok") is True)
chk(
    "stage alias is normalized to the exact canonical value 'במשא ומתן' before write",
    mock_patch.call_args.args[2].get("שלב") == "במשא ומתן",
)

result, mock_patch = _update_with_mocked_write(VALID_RECORD_ID, {"stage": "במשא ומתן"})
chk("canonical stage value 'במשא ומתן' still passes through unchanged", result.get("ok") is True)
chk(
    "canonical value is preserved exactly (no drift introduced by the alias map)",
    mock_patch.call_args.args[2].get("שלב") == "במשא ומתן",
)

result, _ = _update_with_mocked_write(VALID_RECORD_ID, {"stage": "לא קיים"})
chk("an unrelated invalid stage value is still rejected (no broad loosening)", result.get("ok") is False)

result, mock_patch = _update_with_mocked_write(VALID_RECORD_ID, {"notes": "canary phase3 update test"})
chk("notes update reaches the canonical 'Notes' column (not a guessed Hebrew name)", result.get("ok") is True)
chk("notes value written verbatim", mock_patch.call_args.args[2].get("Notes") == "canary phase3 update test")

# Fail-closed: malformed record_id must never reach the Airtable write.
with patch.object(commercial_crm, "airtable_patch") as mock_patch:
    result = commercial_crm.update_deal(MALFORMED_RECORD_ID, {"stage": "במשא ומתן"}, source="test")
chk("malformed record_id fails closed", result.get("ok") is False)
chk("malformed record_id never reaches the Airtable write call", mock_patch.call_count == 0)

# Fail-closed: well-formed but nonexistent record_id — the write layer itself
# reports failure (airtable_patch returns falsy), update_deal() must not
# claim success.
result, mock_patch = _update_with_mocked_write(
    VALID_RECORD_ID, {"stage": "במשא ומתן"}, patch_returns=False,
)
chk("nonexistent (but well-formed) record_id fails closed on a failed write", result.get("ok") is False)


print(f"\n{passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
