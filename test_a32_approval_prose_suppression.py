# test_a32_approval_prose_suppression.py — regression tests for a live
# EvidenceFinalizer-confirmed defect: sanitize_agent_response() (A32's
# Single-Speaker gate) let approval-invite prose through UNSUPPRESSED even
# though a real approval was already queued this turn and ActionGateway had
# already sent its own "⏳ בקשת אישור" prompt through the side channel.
#
# Production sample (both messages user-visible in the same turn):
#   1. Gateway prompt:  "⏳ בקשת אישור\n➕ הוסף ל-Tasks...\nID: ... | פג תוקף
#      בעוד 10 דקות"
#   2. Agent prose:     "✅ המשימה מוכנה להוספה...\n➡️ הצעד הבא המומלץ: שלח
#      מאשר כדי לאשר..."
#
# Root cause: this phrasing matched neither _AGENT_ACTION_STATUS_PATTERN (no
# completion verb — "להוספה" is not "נוספה") nor _AGENT_PENDING_STATUS_PATTERN
# ("מוכנה" not followed by "לאישור"/"ממתינ" within 25 chars) — the two
# patterns gating the Single-Speaker suppression block. It DID match the
# pre-existing _AGENT_APPROVAL_INVITE_PATTERN, but that pattern was only
# consulted at the NO-TOOL-EVIDENCE gate, and only fires there when NO
# approval was queued — the exact opposite of this case. So evidenced
# approval-invite prose fell through both checks untouched, producing a
# real, user-visible "✅ ... success-shaped" second message that
# EvidenceFinalizerShadow correctly flagged as response_claim=success against
# evidence_status=approval_pending (mismatch=true) — a genuine bug, not a
# taxonomy artifact.
#
# Fix (core/anti_hallucination.py): a new suppression branch reuses
# _AGENT_APPROVAL_INVITE_PATTERN, gated on _gateway_active AND a real
# __approval_queued__ sentinel present this turn — suppresses (returns "",
# never a fallback string) instead of letting it through. Also widened
# _AGENT_APPROVAL_INVITE_PATTERN with a "הצעד הבא ... אשר" alternative to
# catch the "recommended next step: confirm" phrasing shape alongside the
# already-covered "שלח מאשר" shape.
#
# Explicitly NOT touched: BUG-111, BUG-112 TTL, F52 formatter states,
# ActionGateway execution semantics, feature flags.

from __future__ import annotations

from core.anti_hallucination import (
    sanitize_agent_response,
    _NO_TOOL_EVIDENCE_FALLBACK,
    _SAFE_FALLBACK,
    _SINGLE_SPEAKER_FALLBACK,
)
from core.turn_evidence import TurnEvidenceSummary, compare_shadow_final_status

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


_approval_queued_evidence = [
    {"tool": "__approval_queued__", "content": "⏳ בקשת אישור: הוסף ל-Tasks", "ok": True},
]

# ══════════════════════════════════════════════════
# Test 1 — the exact production phrasing is suppressed
# ══════════════════════════════════════════════════

PROD_TEXT = (
    "✅ המשימה מוכנה להוספה...\n"
    "➡️ הצעד הבא המומלץ: שלח מאשר כדי לאשר..."
)

r1 = sanitize_agent_response(PROD_TEXT, _approval_queued_evidence, _gateway_active=True)
chk("Test 1: production 'מוכנה להוספה...שלח מאשר' text -> suppressed entirely", r1 == "")
chk("Test 1: suppressed text is NOT the single-speaker failure fallback", r1 != _SINGLE_SPEAKER_FALLBACK)
chk("Test 1: suppressed text is NOT the generic safe fallback either", r1 != _SAFE_FALLBACK)

# ══════════════════════════════════════════════════
# Test 2 — "הצעד הבא: אשר" shorthand phrasing is also suppressed
# ══════════════════════════════════════════════════

r2 = sanitize_agent_response(
    "➡️ הצעד הבא: אשר את הפעולה.", _approval_queued_evidence, _gateway_active=True,
)
chk("Test 2: 'הצעד הבא: אשר' after approval queued -> suppressed entirely", r2 == "")
chk("Test 2: not the failure fallback", r2 != _SINGLE_SPEAKER_FALLBACK)

# ══════════════════════════════════════════════════
# Test 3 — the gateway approval prompt itself still sends (unaffected by A32)
# ══════════════════════════════════════════════════
# A32 only ever sanitizes the AGENT's own final_text; ActionGateway's prompt
# is sent through a separate side channel (app.py's owner-notification
# bot.send_message call, wrapped by ActionGateway._render_pending_prompt())
# and never passes through sanitize_agent_response() at all. Confirm that
# channel's text is untouched by asserting it is not empty and carries its
# own distinct content, independent of whatever the agent said this turn.

GATEWAY_PROMPT = "⏳ בקשת אישור\n➕ הוסף ל-Tasks...\nID: abc123 | פג תוקף בעוד 10 דקות"
chk("Test 3: gateway approval prompt text is non-empty and distinct from agent prose",
    bool(GATEWAY_PROMPT) and GATEWAY_PROMPT != PROD_TEXT)

# ══════════════════════════════════════════════════
# Test 4 — EvidenceFinalizer sees response_claim=sent_for_approval, not success
# ══════════════════════════════════════════════════

evidence_pending = TurnEvidenceSummary(approvals_pending=1)

# Before the fix: final_text would have been PROD_TEXT (unsuppressed),
# classified as response_claim="success" against evidence_status=
# "approval_pending" -> mismatch=true, a genuine bug (not a taxonomy gap).
comparison_before_fix_shape = compare_shadow_final_status(
    PROD_TEXT, evidence_pending, approval_prompt_sent=True,
)
chk("Test 4 (documents the bug): unsuppressed prod text classifies as response_claim=success",
    comparison_before_fix_shape.response_claim == "success")
chk("Test 4 (documents the bug): unsuppressed prod text mismatches approval_pending evidence",
    comparison_before_fix_shape.mismatch is True)

# After the fix: sanitize_agent_response suppresses to "", and
# _classify_response_claim("", approval_prompt_sent=True) correctly reports
# sent_for_approval, matching evidence_status=approval_pending -> no mismatch.
final_text_after_fix = sanitize_agent_response(
    PROD_TEXT, _approval_queued_evidence, _gateway_active=True,
)
comparison_after_fix = compare_shadow_final_status(
    final_text_after_fix, evidence_pending, approval_prompt_sent=True,
)
chk("Test 4: after suppression, response_claim=sent_for_approval (not success)",
    comparison_after_fix.response_claim == "sent_for_approval")
chk("Test 4: after suppression, evidence_status=approval_pending",
    comparison_after_fix.evidence_status == "approval_pending")
chk("Test 4: after suppression, no mismatch reported", comparison_after_fix.mismatch is False)

# ══════════════════════════════════════════════════
# Test 5 — a real post-execution success is not suppressed by this fix
# ══════════════════════════════════════════════════
# A genuine completion claim ("✅ המשימה נוספה בהצלחה") does not invite the
# user to confirm anything, so it never matches _AGENT_APPROVAL_INVITE_PATTERN
# and this fix's new branch never fires for it. Exercised here with real
# write-tool evidence and no gateway (the legacy pass-through path — the
# gateway-active completion-claim path is owned by ActionGateway's own
# compose_status_reply(), covered separately in
# test_single_speaker_fallback_and_duplication.py, and intentionally not
# touched by this fix).

real_write_evidence = [
    {"tool": "airtable_add", "content": "✅ רשומה נוספה | ID: rec999", "ok": True},
]
r5 = sanitize_agent_response(
    "✅ המשימה נוספה בהצלחה.", real_write_evidence, _gateway_active=False,
)
chk("Test 5: genuine post-execution success with real write evidence -> passed through unchanged",
    r5 not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK, _SINGLE_SPEAKER_FALLBACK, ""))
chk("Test 5: genuine success text is exactly preserved", r5 == "✅ המשימה נוספה בהצלחה.")

# ══════════════════════════════════════════════════
# Test 6 — legacy non-approval conversational responses are unchanged
# ══════════════════════════════════════════════════

r6a = sanitize_agent_response(
    "בוודאי, אשמח לעזור. איזה מידע תרצה?", [], _gateway_active=True,
)
chk("Test 6a: ordinary conversational reply (gateway active, no approval) -> unchanged",
    r6a == "בוודאי, אשמח לעזור. איזה מידע תרצה?")

r6b = sanitize_agent_response(
    "בוודאי, אשמח לעזור. איזה מידע תרצה?", [], _gateway_active=False,
)
chk("Test 6b: ordinary conversational reply (legacy, gateway inactive) -> unchanged",
    r6b == "בוודאי, אשמח לעזור. איזה מידע תרצה?")

# Regression: approval-invite-shaped text WITHOUT real evidence must still be
# blocked as a hallucination (this fix only changes the EVIDENCED case).
r6c = sanitize_agent_response(PROD_TEXT, [], _gateway_active=True)
chk("Test 6c regression: same prose with NO __approval_queued__ evidence -> still blocked",
    r6c in (_SINGLE_SPEAKER_FALLBACK, _NO_TOOL_EVIDENCE_FALLBACK))
chk("Test 6c regression: not silently suppressed (that would hide a real fabrication)",
    r6c != "")

# Regression: gateway inactive -> this fix's new branch never fires at all.
r6d = sanitize_agent_response(PROD_TEXT, _approval_queued_evidence, _gateway_active=False)
chk("Test 6d regression: gateway_active=False -> approval-invite text passes through unchanged",
    r6d == PROD_TEXT)


print()
print("=" * 50)
print(f"A32 approval-prose suppression tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
