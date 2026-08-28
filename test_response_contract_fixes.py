#!/usr/bin/env python3
"""
test_response_contract_fixes.py — PR_RESPONSE_CONTRACT regression tests.

מאמת שהקוראים הבאים ל-tools.airtable_tools.airtable_add/airtable_update
בודקים הצלחה נכון דרך result["ok"] (חוזה C53-A), לא string/regex על ה-dict:
  - interaction_engine.save_to_interaction_log / create_tasks_from_analysis
  - ad_attribution.record_lead_source / mark_converted
  - voice_adapter._save_voice_lead
  - tenant_provisioner._save_tenant_to_airtable / suspend_tenant
  - inbound_handler._create_email_lead

כל טסט "הצלחה" כאן היה נכשל תחת ההתנהגות הישנה (`"✅" in result` / regex על
dict) — result הוא dict, ולעולם לא היה מכיל "✅" כמפתח, כך שקוד ישן היה
מדווח כשלון גם על הצלחה אמיתית. אלה הבדיקות שהיו תופסות רגרסיה לדפוס הישן.

בנוסף: static guard — סורק מחדש עם tools.audit_result_parsing.scan() (הכלי
הקיים, לא נערך) ומוודא שאף אחד מחמשת הקבצים האלה כבר לא מכיל את ה-anti-pattern.
"""

from __future__ import annotations

import ast
import logging
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch

logging.basicConfig(level=logging.WARNING)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _ok_result(external_id: str = "recABC123") -> dict:
    return {
        "ok": True,
        "tool": "airtable_add",
        "external_id": external_id,
        "evidence": {"record_id": external_id},
        "user_message": f"✅ נשמר | ID: {external_id}",
    }


def _fail_result() -> dict:
    return {
        "ok": False,
        "tool": "airtable_add",
        "external_id": "",
        "evidence": {},
        "user_message": "❌ שגיאה בשמירה.",
    }


# ══════════════════════════════════════════════════════════════════
# 1. interaction_engine.py
# ══════════════════════════════════════════════════════════════════
print("\n── interaction_engine.py ─────────────")

from interaction_engine import (
    save_to_interaction_log,
    create_tasks_from_analysis,
    InteractionSchema,
    InteractionAnalysis,
)

_interaction = InteractionSchema(source_channel="whatsapp", raw_id="raw1", title="Test Interaction")
_analysis = InteractionAnalysis(summary="summary", next_steps="follow up")

class _FakeInteractionGateway:
    def __init__(self, result):
        self.result = result
        self.contract = SimpleNamespace(
            status="completed" if result.ok else "failed",
            agent_observations=([{"kind": "execution_fact", "record_id": result.record_id}] if result.ok else []),
        )
        self._ledger = self

    def propose_action(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(ok=self.result.ok, contract_id="contract-1", reason="test")

    def approve(self, *args, **kwargs):
        return "test"

    def find_by_id(self, _contract_id):
        return self.contract

with patch("core.action_gateway.action_gateway", _FakeInteractionGateway(SimpleNamespace(ok=True, record_id="recINT1"))):
    record_id = save_to_interaction_log(_interaction, _analysis)
    chk("save_to_interaction_log: ok=True → returns external_id (not empty)", record_id == "recINT1")

with patch("core.action_gateway.action_gateway", _FakeInteractionGateway(SimpleNamespace(ok=False, record_id=""))):
    record_id = save_to_interaction_log(_interaction, _analysis)
    chk("save_to_interaction_log: ok=False → returns empty string", record_id == "")

_analysis_with_tasks = InteractionAnalysis(tasks=[{"title": "Task 1", "owner": "Eli"}])

with patch("core.action_gateway.action_gateway", _FakeInteractionGateway(
    SimpleNamespace(ok=True, record_id="recTASK1")
)):
    created = create_tasks_from_analysis(_analysis_with_tasks, _interaction)
    chk("create_tasks_from_analysis: ok=True → created counter increments", created == 1)

with patch("core.action_gateway.action_gateway", _FakeInteractionGateway(
    SimpleNamespace(ok=False, record_id="")
)):
    created = create_tasks_from_analysis(_analysis_with_tasks, _interaction)
    chk("create_tasks_from_analysis: ok=False → created counter stays 0", created == 0)

# ══════════════════════════════════════════════════════════════════
# 2. ad_attribution.py
# ══════════════════════════════════════════════════════════════════
print("\n── ad_attribution.py ─────────────────")

from ad_attribution import record_lead_source, mark_converted, UTMParams
from core.lead_service import LeadCreateResult
from identity import Identity, Role

_attribution_identity = Identity(
    user_id="+972500000000", role=Role.LEAD, channel="whatsapp",
)

_utm = UTMParams(source="meta", medium="cpc", campaign="apt_tlv")

with patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recLEAD1", "fields": {}}]), \
     patch("core.lead_service.update_lead_fields", return_value=LeadCreateResult(
         ok=True, action="updated", record_id="recLEAD1")):
    ok = record_lead_source("boss_hq:test", _utm, identity=_attribution_identity)
    chk("record_lead_source: ok=True → returns True", ok is True)

with patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recLEAD1", "fields": {}}]), \
     patch("core.lead_service.update_lead_fields", return_value=LeadCreateResult(
         ok=False, action="write_failed", record_id="recLEAD1")):
    ok = record_lead_source("boss_hq:test", _utm, identity=_attribution_identity)
    chk("record_lead_source: ok=False → returns False", ok is False)

with patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recLEAD2", "fields": {}}]), \
     patch("tools.airtable_tools.airtable_update", return_value=_ok_result("recLEAD2")):
    ok = mark_converted("boss_hq:test2", 5000)
    chk("mark_converted: ok=True → returns True", ok is True)

with patch("tools.airtable_tools.airtable_get_records", return_value=[{"id": "recLEAD2", "fields": {}}]), \
     patch("tools.airtable_tools.airtable_update", return_value=_fail_result()):
    ok = mark_converted("boss_hq:test2", 5000)
    chk("mark_converted: ok=False → returns False", ok is False)

# ══════════════════════════════════════════════════════════════════
# 3. voice_adapter.py
# ══════════════════════════════════════════════════════════════════
print("\n── voice_adapter.py ───────────────────")

from voice_adapter import _save_voice_lead, VoiceSession

_session = VoiceSession(call_sid="CA123", from_num="+972501234567", domain="general")

with patch("tools.airtable_tools.airtable_add", return_value=_ok_result("recVOICE1")), \
     patch("voice_adapter._notify_owner"):
    ok = _save_voice_lead(_session)
    chk("_save_voice_lead: ok=True → returns True", ok is True)

with patch("tools.airtable_tools.airtable_add", return_value=_fail_result()), \
     patch("voice_adapter._notify_owner") as mock_notify:
    ok = _save_voice_lead(_session)
    chk("_save_voice_lead: ok=False → returns False", ok is False)
    chk("_save_voice_lead: ok=False → owner NOT notified", not mock_notify.called)

# ══════════════════════════════════════════════════════════════════
# 4. tenant_provisioner.py
# ══════════════════════════════════════════════════════════════════
print("\n── tenant_provisioner.py ──────────────")

from tenant_provisioner import _save_tenant_to_airtable, suspend_tenant, TenantConfig

_tenant_config = TenantConfig(
    tenant_id="test_tenant", business_name="Test Biz", template="real_estate",
    owner_name="Eli", owner_phone="12345",
)

with patch("tools.airtable_tools.airtable_add", return_value=_ok_result("recTENANT1")):
    ok = _save_tenant_to_airtable(_tenant_config)
    chk("_save_tenant_to_airtable: ok=True → returns True", ok is True)

with patch("tools.airtable_tools.airtable_add", return_value=_fail_result()):
    ok = _save_tenant_to_airtable(_tenant_config)
    chk("_save_tenant_to_airtable: ok=False → returns False", ok is False)

with patch("tools.airtable_tools.airtable_get", return_value="• [recTENANT1] tenant_id: test_tenant"), \
     patch("tools.airtable_tools.airtable_update", return_value=_ok_result("recTENANT1")):
    msg = suspend_tenant("test_tenant")
    chk("suspend_tenant: ok=True → success message", "הושעה" in msg)

with patch("tools.airtable_tools.airtable_get", return_value="• [recTENANT1] tenant_id: test_tenant"), \
     patch("tools.airtable_tools.airtable_update", return_value=_fail_result()):
    msg = suspend_tenant("test_tenant")
    chk(
        "suspend_tenant: ok=False → does NOT claim success (BUG: was unconditional before fix)",
        "הושעה" not in msg and "❌" in msg,
    )

# ══════════════════════════════════════════════════════════════════
# 5. inbound_handler.py
# ══════════════════════════════════════════════════════════════════
print("\n── inbound_handler.py ─────────────────")

from inbound_handler import _create_email_lead

with patch("tools.airtable_tools.airtable_add", return_value=_ok_result("recEMAIL1")):
    try:
        _create_email_lead("sender@x.com", "Sender", "general", "hello", "ext1")
        chk("_create_email_lead: ok=True → no exception (dict is not regex-searched)", True)
    except TypeError:
        chk("_create_email_lead: ok=True → no exception (dict is not regex-searched)", False)

with patch("tools.airtable_tools.airtable_add", return_value=_fail_result()):
    try:
        _create_email_lead("sender@x.com", "Sender", "general", "hello", "ext1")
        chk("_create_email_lead: ok=False → no exception, handled gracefully", True)
    except TypeError:
        chk("_create_email_lead: ok=False → no exception, handled gracefully", False)

# ══════════════════════════════════════════════════════════════════
# 6. Static guard — the specific airtable_add/airtable_update call sites
#    fixed by this PR must no longer trip the existing, unmodified
#    tools/audit_result_parsing.py scanner. Scoped to exactly the
#    original offending (file, line, kind) tuples, not whole files —
#    ad_attribution.py/inbound_handler.py still legitimately parse
#    airtable_get() (a different, string-returning function) with regex
#    at other lines, which is out of scope for this PR and must keep
#    passing untouched.
# ══════════════════════════════════════════════════════════════════
print("\n── static guard (audit_result_parsing) ─")

from tools.audit_result_parsing import scan

# The exact (file, original_line, kind) tuples this PR fixes — sourced
# from tools/audit_result_parsing.py's own BASELINE (read-only reference,
# that script is not modified by this PR).
_FIXED_ENTRIES = {
    ("voice_adapter.py", 249, "emoji"),
    ("interaction_engine.py", 300, "emoji"),
    ("interaction_engine.py", 302, "rec"),
    ("interaction_engine.py", 386, "emoji"),
    ("tenant_provisioner.py", 176, "emoji"),
    ("ad_attribution.py", 176, "emoji"),
    ("ad_attribution.py", 201, "emoji"),
    ("inbound_handler.py", 129, "rec"),
}

current = set(scan())
still_present = _FIXED_ENTRIES & current
chk(
    "none of the 8 fixed airtable_add/airtable_update call sites still trip the scanner",
    not still_present,
)
if still_present:
    for file, line, kind in sorted(still_present):
        print(f"    ❌ still present: {file}:{line} ({kind})")

# Regression guard: if any of these 5 files' airtable_add/update call
# sites reintroduce the pattern at a NEW line, that would show up as a
# "new" (non-baseline) finding in the same file. Legitimate rec parsing is
# identified by the enclosing function's semantic call to airtable_get,
# rather than a brittle line-number allowlist.
def _airtable_get_function_ranges(path: str) -> list[tuple[int, int]]:
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    ranges = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        has_airtable_get = any(
            isinstance(child, ast.Call)
            and (
                (isinstance(child.func, ast.Name) and child.func.id in {"airtable_get", "_airtable_get"})
                or (isinstance(child.func, ast.Attribute) and child.func.attr == "airtable_get")
            )
            for child in ast.walk(node)
        )
        if has_airtable_get and node.end_lineno is not None:
            ranges.append((node.lineno, node.end_lineno))
    return ranges


def _is_legitimate_airtable_get_finding(finding: tuple[str, int, str]) -> bool:
    path, line, kind = finding
    return kind == "rec" and any(
        start <= line <= end for start, end in _airtable_get_function_ranges(path)
    )


_target_files = {"interaction_engine.py", "ad_attribution.py", "voice_adapter.py",
                  "tenant_provisioner.py", "inbound_handler.py"}
unexpected = {
    finding for finding in current
    if finding[0] in _target_files and not _is_legitimate_airtable_get_finding(finding)
}
chk(
    "no unexpected new false-success finding in these 5 files beyond the known airtable_get lines",
    not unexpected,
)
if unexpected:
    for file, line, kind in sorted(unexpected):
        print(f"    ❌ unexpected: {file}:{line} ({kind})")

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
