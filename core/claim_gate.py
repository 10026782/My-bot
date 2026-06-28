# core/claim_gate.py — CXX: Claim Gate
#
# לפני שהבוט אומר "נוצר" / "נשלח" / "מצאתי" — עובר Claim Gate.
# Gate בודק ActionResult.claim_type + evidence, לא text.replace על עברית.
#
# למה לא text.replace:
#   עברית = morphology עשיר. "נשלח" יכול להופיע ב"נשלחה", "שנשלח", "שנשלחה".
#   text.replace לא מטפל בזה ויחליף מילים לא נכון.
#   הפתרון: gateway מחזיק claim_type מפורש, Gate בודק לפיו.

from __future__ import annotations

import logging
from typing import Optional

from core.action_result import ActionResult, ClaimType

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Evidence Rules — מה נדרש לכל claim_type
# ══════════════════════════════════════════════════

def _check_created(r: ActionResult) -> bool:
    return r.business_success and bool(r.record_id)

def _check_updated(r: ActionResult) -> bool:
    return r.business_success and r.affected_records > 0

def _check_sent(r: ActionResult) -> bool:
    return r.delivery_success  # stub לא עובר

def _check_found(r: ActionResult) -> bool:
    return r.tool_called and r.tool_http_ok

def _check_scheduled(r: ActionResult) -> bool:
    return r.business_success and bool(r.record_id)

def _check_deleted(r: ActionResult) -> bool:
    return r.business_success and r.affected_records > 0


_CLAIM_CHECKS = {
    ClaimType.CREATED:   _check_created,
    ClaimType.UPDATED:   _check_updated,
    ClaimType.SENT:      _check_sent,
    ClaimType.FOUND:     _check_found,
    ClaimType.SCHEDULED: _check_scheduled,
    ClaimType.DELETED:   _check_deleted,
}


# ══════════════════════════════════════════════════
# Fallback Messages — מה להגיד כשאין evidence
# ══════════════════════════════════════════════════

_FALLBACK: dict[ClaimType, str] = {
    ClaimType.CREATED:   "ניסיתי ליצור את הרשומה — אנא בדוק ב-Airtable.",
    ClaimType.UPDATED:   "ניסיתי לעדכן — אנא בדוק שהשינוי התבצע.",
    ClaimType.SENT:      "ההודעה הועברה לעיבוד — ייתכן שלא נשלחה עדיין.",
    ClaimType.FOUND:     "חיפשתי — לא ניתן לאמת את התוצאה כרגע.",
    ClaimType.SCHEDULED: "ניסיתי לקבוע — אנא בדוק ביומן.",
    ClaimType.DELETED:   "ניסיתי למחוק — אנא בדוק שהרשומה הוסרה.",
}


# ══════════════════════════════════════════════════
# ClaimResult — תוצאת Gate
# ══════════════════════════════════════════════════

class ClaimResult:
    """תוצאת בדיקת ClaimGate."""

    def __init__(self, approved: bool, claim_type: Optional[ClaimType],
                 fallback_message: str = "", reason: str = ""):
        self.approved         = approved
        self.claim_type       = claim_type
        self.fallback_message = fallback_message
        self.reason           = reason

    @property
    def ok(self) -> bool:
        return self.approved

    def __repr__(self) -> str:
        status = "✅" if self.approved else "❌"
        return f"ClaimResult({status} {self.claim_type} reason={self.reason!r})"


# ══════════════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════════════

def check_claim(result: ActionResult) -> ClaimResult:
    """
    בדוק אם ActionResult מאפשר את הטענה שבו.

    קורא: כל מקום שעומד לאמר ללקוח "נוצר" / "נשלח" / "מצאתי" וכו'.

    דוגמה:
        ar = ActionResult.from_airtable_add(res, source="lead_capture")
        ar.claim_type = ClaimType.CREATED
        gate = check_claim(ar)
        if gate.ok:
            reply = "הליד נוצר בהצלחה ✅"
        else:
            reply = gate.fallback_message
    """
    claim_type = result.claim_type

    if claim_type is None:
        # אין claim — לא צריך לבדוק
        return ClaimResult(approved=True, claim_type=None, reason="no_claim")

    check_fn = _CLAIM_CHECKS.get(claim_type)
    if check_fn is None:
        logger.warning(f"[ClaimGate] unknown claim_type: {claim_type}")
        return ClaimResult(approved=True, claim_type=claim_type, reason="unknown_type")

    passed = check_fn(result)

    if not passed:
        reason = _build_denial_reason(result, claim_type)
        logger.warning(
            f"[ClaimGate] DENIED | claim={claim_type} | {reason} | "
            f"src={result.source} rec={result.record_id or '-'}"
        )
        return ClaimResult(
            approved         = False,
            claim_type       = claim_type,
            fallback_message = _FALLBACK.get(claim_type, "הפעולה לא הושלמה."),
            reason           = reason,
        )

    logger.debug(f"[ClaimGate] APPROVED | claim={claim_type} | src={result.source}")
    return ClaimResult(approved=True, claim_type=claim_type, reason="evidence_ok")


def _build_denial_reason(result: ActionResult, claim_type: ClaimType) -> str:
    """מייצר הסבר קצר למה הclaim נדחה — לlog בלבד, לא ללקוח."""
    parts = []
    if not result.tool_called:
        parts.append("tool_not_called")
    elif not result.tool_http_ok:
        parts.append("tool_http_failed")
    elif not result.business_success:
        parts.append("business_failed")

    if claim_type == ClaimType.SENT:
        if not result.delivery_success:
            mode = result.adapter_mode or "unknown"
            parts.append(f"delivery_not_confirmed(adapter={mode})")

    if claim_type in (ClaimType.CREATED, ClaimType.SCHEDULED):
        if not result.record_id:
            parts.append("no_record_id")

    if result.fatal_error:
        parts.append(f"fatal={result.fatal_error[:40]}")

    return " | ".join(parts) if parts else "evidence_insufficient"


# ══════════════════════════════════════════════════
# Convenience wrapper for delivery claims
# ══════════════════════════════════════════════════

def check_delivery_claim(
    output_approved: bool,
    delivery_attempted: bool,
    delivery_success: bool,
    adapter_mode: str,
    source: str = "",
) -> ClaimResult:
    """
    בדיקת claim שליחה בלי לבנות ActionResult מלא.
    שימושי ב-_gateway_whatsapp_reply כשאין ActionResult מלא זמין.
    """
    result = ActionResult(
        tool_called        = delivery_attempted,
        tool_http_ok       = delivery_success,
        business_success   = delivery_success,
        output_approved    = output_approved,
        delivery_attempted = delivery_attempted,
        delivery_success   = delivery_success,
        adapter_mode       = adapter_mode,
        claim_type         = ClaimType.SENT,
        source             = source,
    )
    return check_claim(result)


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond:
            print(f"✅ {desc}"); passed += 1
        else:
            print(f"❌ {desc}"); failed += 1

    # T01 — CREATED requires record_id
    r = ActionResult(business_success=True, record_id="recABC", claim_type=ClaimType.CREATED)
    chk("CREATED: ok when record_id", check_claim(r).ok)

    r2 = ActionResult(business_success=True, record_id="", claim_type=ClaimType.CREATED)
    chk("CREATED: denied when no record_id", not check_claim(r2).ok)

    # T02 — SENT requires delivery_success, not just output_approved
    r3 = ActionResult(output_approved=True, delivery_attempted=True,
                      delivery_success=False, adapter_mode="stub",
                      claim_type=ClaimType.SENT)
    gate3 = check_claim(r3)
    chk("SENT: denied on stub (delivery_success=False)", not gate3.ok)
    chk("SENT: fallback_message present", bool(gate3.fallback_message))

    r4 = ActionResult(output_approved=True, delivery_attempted=True,
                      delivery_success=True, adapter_mode="live",
                      claim_type=ClaimType.SENT)
    chk("SENT: approved on live delivery", check_claim(r4).ok)

    # T03 — FOUND only needs tool_called + http_ok
    r5 = ActionResult(tool_called=True, tool_http_ok=True, claim_type=ClaimType.FOUND)
    chk("FOUND: approved when tool ran ok", check_claim(r5).ok)

    r6 = ActionResult(tool_called=False, claim_type=ClaimType.FOUND)
    chk("FOUND: denied when tool not called", not check_claim(r6).ok)

    # T04 — UPDATED requires affected_records > 0
    r7 = ActionResult(business_success=True, affected_records=1, claim_type=ClaimType.UPDATED)
    chk("UPDATED: approved when affected_records=1", check_claim(r7).ok)

    r8 = ActionResult(business_success=True, affected_records=0, claim_type=ClaimType.UPDATED)
    chk("UPDATED: denied when affected_records=0", not check_claim(r8).ok)

    # T05 — no claim_type = always approved
    r9 = ActionResult(business_success=False, claim_type=None)
    chk("None claim_type: always approved", check_claim(r9).ok)

    # T06 — from_airtable_add helper
    ar = ActionResult.from_airtable_add({"ok": True, "external_id": "rec123"}, source="test")
    chk("from_airtable_add: business_success", ar.business_success)
    chk("from_airtable_add: record_id", ar.record_id == "rec123")

    ar2 = ActionResult.from_airtable_add("not a dict", source="test")
    chk("from_airtable_add: fatal on wrong type", bool(ar2.fatal_error))
    chk("from_airtable_add: not business_success on wrong type", not ar2.business_success)

    # T07 — check_delivery_claim convenience wrapper
    cr = check_delivery_claim(True, True, False, "stub", "webhook")
    chk("check_delivery_claim: stub denied", not cr.ok)
    chk("check_delivery_claim: fallback present", bool(cr.fallback_message))

    print(f"\n{'='*40}")
    print(f"ClaimGate Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
