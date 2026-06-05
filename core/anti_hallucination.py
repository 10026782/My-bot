# core/anti_hallucination.py — A32 Anti-Hallucination Layer
#
# Principle: if the tool didn't confirm it, the agent didn't do it.
# Three gates:
#   1. verify_execution  — did the tool actually succeed?
#   2. verify_result_claim — does the agent's text match reality?
#   3. sanitize_agent_response — replace hallucinated text with safe copy.

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Evidence Markers — expected substrings in tool output
# when a tool succeeds (beyond the ❌ / empty checks).
# ══════════════════════════════════════════════════

_EVIDENCE_MARKERS: dict[str, list[str]] = {
    # calendar_create_event returns "✅ אירוע '…' נוצר ביומן" or "⚠️ כבר קיים ביומן"
    "calendar_create_event": ["נוצר ביומן", "⚠️ כבר קיים ביומן"],
    # gmail_send_draft returns "📧 טיוטה … נשלחה בהצלחה!"
    "gmail_send_draft":      ["נשלחה בהצלחה"],
    # gmail_read returns either email content or "✅ אין הודעות"
    "gmail_read":            ["הודעה מ-", "מ:", "אין הודעות"],
}

# ══════════════════════════════════════════════════
# "No tool was called" detection patterns.
# If agent text matches AND no tool result contains expected evidence
# → agent hallucinated a live check / action.
# ══════════════════════════════════════════════════

_NO_TOOL_CLAIMS: list[tuple[re.Pattern, list[str]]] = [
    # Agent claims it checked / created a calendar event
    (
        re.compile(
            r"(בדקתי.*ביומן|אין חפיפות|הפגישה קבועה|קבעתי|נוצר ביומן|הוסף לקלנדר)",
            re.UNICODE,
        ),
        ["נוצר ביומן", "⚠️ כבר קיים ביומן", "אירועים קרובים", "אין אירועים"],
    ),
    # Agent claims it read / sent email
    (
        re.compile(
            r"(בדקתי.*מייל|קראתי.*הודעות|לא.*מצאתי.*מייל|המייל.*נשלח|שלחתי.*מייל)",
            re.UNICODE,
        ),
        ["הודעה מ-", "נשלחה בהצלחה", "אין הודעות", "draft"],
    ),
]


# ══════════════════════════════════════════════════
# Result Type
# ══════════════════════════════════════════════════

@dataclass
class VerifyResult:
    status: str   # "ok" | "warn" | "failed" | "hallucination" | "mismatch"
    reason: str = ""


# ══════════════════════════════════════════════════
# 1. verify_execution
# ══════════════════════════════════════════════════

def verify_execution(tool_name: str, raw_output: str | None) -> VerifyResult:
    """
    Checks whether a tool call actually succeeded.
    Called immediately after validate_tool_output().
    """
    if not raw_output:
        return VerifyResult("failed", "output is empty or None")

    if raw_output.lstrip().startswith("❌"):
        return VerifyResult("failed", raw_output[:120])

    if tool_name == "airtable_add" and "rec" not in raw_output:
        return VerifyResult(
            "failed",
            f"airtable_add: no record ID ('rec...') in output — record may not have been created"
        )

    if tool_name == "gmail_draft" and "draft" not in raw_output.lower():
        return VerifyResult(
            "warn",
            "gmail_draft: 'draft' not found in output — verify draft was created"
        )

    # Evidence markers: tool-specific expected substrings in success output.
    # Only checked when no ❌ was detected above (i.e., tool didn't explicitly error).
    markers = _EVIDENCE_MARKERS.get(tool_name)
    if markers and not any(m in raw_output for m in markers):
        return VerifyResult(
            "failed",
            f"{tool_name}: output contains no expected evidence markers — possible silent failure",
        )

    return VerifyResult("ok")


# ══════════════════════════════════════════════════
# 2. verify_result_claim
# ══════════════════════════════════════════════════

_POSITIVE_CLAIMS = re.compile(r"(נשלח|בוצע|נוצר|נשמר|הוסף|עודכן|נרשם)", re.UNICODE)
_NEGATIVE_CLAIMS = re.compile(r"לא מצאתי|אין תוצאות|לא נמצא", re.UNICODE)


def _all_failed(tool_results: list[dict]) -> bool:
    """True if every tool result content starts with ❌."""
    if not tool_results:
        return False
    return all(
        isinstance(r.get("content"), str) and r["content"].lstrip().startswith("❌")
        for r in tool_results
    )


def _has_data(tool_results: list[dict]) -> bool:
    """True if any tool result contains non-error, non-empty content."""
    for r in tool_results:
        content = r.get("content", "")
        if (isinstance(content, str)
                and content.strip()
                and not content.lstrip().startswith("❌")):
            return True
    return False


def verify_result_claim(agent_text: str, tool_results: list[dict]) -> VerifyResult:
    """
    Cross-checks what the agent says against what the tools actually returned.
    """
    if _POSITIVE_CLAIMS.search(agent_text) and _all_failed(tool_results):
        return VerifyResult(
            "hallucination",
            "agent claims success but all tool calls failed"
        )

    if _NEGATIVE_CLAIMS.search(agent_text) and _has_data(tool_results):
        return VerifyResult(
            "mismatch",
            "agent says 'not found' but tool results contain data"
        )

    return VerifyResult("ok")


# ══════════════════════════════════════════════════
# 3. sanitize_agent_response
# ══════════════════════════════════════════════════

_SAFE_FALLBACK  = "לא הצלחתי לבצע את הפעולה. אנא נסה שוב."
_MISMATCH_PREFIX = "⚠️ שים לב — ייתכן שהתוצאה אינה מדויקת.\n"


def _tool_results_contain(tool_results: list[dict], keywords: list[str]) -> bool:
    """True if any tool result content contains at least one keyword."""
    return any(
        kw in r.get("content", "")
        for r in tool_results
        for kw in keywords
    )


def sanitize_agent_response(agent_text: str, tool_results: list[dict]) -> str:
    """
    Final gate before the reply reaches the user.
    Replaces hallucinated text; adds a warning for mismatches.
    """
    check = verify_result_claim(agent_text, tool_results)

    if check.status == "hallucination":
        logger.error(f"[A32] HALLUCINATION detected: {check.reason}")
        return _SAFE_FALLBACK

    if check.status == "mismatch":
        logger.warning(f"[A32] MISMATCH detected: {check.reason}")
        return _MISMATCH_PREFIX + agent_text

    # "No tool called" gate: agent claims a live check/action but
    # no tool result contains the expected evidence.
    for claim_pattern, evidence_keywords in _NO_TOOL_CLAIMS:
        if claim_pattern.search(agent_text) and not _tool_results_contain(tool_results, evidence_keywords):
            logger.error(
                f"[A32] NO-TOOL-EVIDENCE hallucination: "
                f"agent claims '{claim_pattern.pattern[:40]}' but no supporting tool result found"
            )
            return _SAFE_FALLBACK

    return agent_text


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def check(desc: str, got, expected_status: str):
        nonlocal passed, failed
        ok = got.status == expected_status
        print(f"{'✅' if ok else '❌'} {desc}")
        if not ok:
            print(f"     got={got.status!r}  expected={expected_status!r}  reason={got.reason!r}")
            failed += 1
        else:
            passed += 1

    # ── verify_execution ─────────────────────────
    check("airtable_add success (has rec...)",
          verify_execution("airtable_add", "Created: rec1234abc"),
          "ok")

    check("airtable_add returns ❌",
          verify_execution("airtable_add", "❌ Airtable error 422: field missing"),
          "failed")

    check("airtable_add empty output",
          verify_execution("airtable_add", ""),
          "failed")

    check("airtable_add no rec ID",
          verify_execution("airtable_add", "Created successfully"),
          "failed")

    check("gmail_draft ok",
          verify_execution("gmail_draft", "Draft created (id=draft_xyz)"),
          "ok")

    check("gmail_draft missing 'draft' in output",
          verify_execution("gmail_draft", "Email queued"),
          "warn")

    check("calendar_create_event success marker present",
          verify_execution("calendar_create_event", "✅ אירוע 'פגישה' נוצר ביומן ל-01/06/2025 14:00."),
          "ok")

    check("calendar_create_event conflict marker present",
          verify_execution("calendar_create_event", "⚠️ כבר קיים ביומן: 'אירוע אחר' (14:00). לקבוע בכל זאת?"),
          "ok")

    check("calendar_create_event no evidence → failed",
          verify_execution("calendar_create_event", "Done."),
          "failed")

    check("gmail_send_draft success marker",
          verify_execution("gmail_send_draft", "📧 טיוטה draft_abc נשלחה בהצלחה!"),
          "ok")

    check("gmail_send_draft no evidence → failed",
          verify_execution("gmail_send_draft", "Sent."),
          "failed")

    check("gmail_read has content → ok",
          verify_execution("gmail_read", "הודעה מ-: test@example.com | נושא: test"),
          "ok")

    check("gmail_read no evidence → failed",
          verify_execution("gmail_read", "OK"),
          "failed")

    # ── verify_result_claim ──────────────────────
    failed_results = [{"content": "❌ connection error"}]
    ok_results     = [{"content": "rec1234 created"}]
    empty_results  = []

    check("agent says 'נשלח' but tool failed → hallucination",
          verify_result_claim("המייל נשלח בהצלחה!", failed_results),
          "hallucination")

    check("agent says 'בוצע' but tool failed → hallucination",
          verify_result_claim("הפעולה בוצעה.", failed_results),
          "hallucination")

    check("agent says 'לא מצאתי' but tool has data → mismatch",
          verify_result_claim("לא מצאתי כלום במערכת.", ok_results),
          "mismatch")

    check("agent says 'לא מצאתי' with empty results → ok",
          verify_result_claim("לא מצאתי כלום.", empty_results),
          "ok")

    check("agent correct success claim",
          verify_result_claim("הרשומה נוצרה.", ok_results),
          "ok")

    # ── sanitize_agent_response ──────────────────
    hallucinated = sanitize_agent_response("המייל נשלח!", failed_results)
    ok1 = hallucinated == _SAFE_FALLBACK
    print(f"{'✅' if ok1 else '❌'} agent says 'נשלח' but tool failed → sanitized to safe message")
    if not ok1:
        print(f"     got: {hallucinated!r}")
        failed += 1
    else:
        passed += 1

    normal = sanitize_agent_response("לא מצאתי לידים.", empty_results)
    ok2 = normal == "לא מצאתי לידים."
    print(f"{'✅' if ok2 else '❌'} agent says 'לא מצאתי' correctly → returned as-is")
    if not ok2:
        print(f"     got: {normal!r}")
        failed += 1
    else:
        passed += 1

    # ── "no tool called" gate ────────────────────
    calendar_results = [{"content": "✅ אירוע 'פגישה' נוצר ביומן ל-01/06/2025 14:00."}]

    no_tool_calendar = sanitize_agent_response(
        "בדקתי את הביומן שלך — אין חפיפות. הפגישה קבועה.", []
    )
    ok3 = no_tool_calendar == _SAFE_FALLBACK
    print(f"{'✅' if ok3 else '❌'} agent claims calendar check with no tool result → sanitized")
    if not ok3:
        print(f"     got: {no_tool_calendar!r}")
        failed += 1
    else:
        passed += 1

    with_tool_calendar = sanitize_agent_response(
        "בדקתי את הביומן שלך — אין חפיפות. הפגישה קבועה.", calendar_results
    )
    ok4 = with_tool_calendar != _SAFE_FALLBACK
    print(f"{'✅' if ok4 else '❌'} agent claims calendar but tool result present → passed through")
    if not ok4:
        print(f"     got: {with_tool_calendar!r}")
        failed += 1
    else:
        passed += 1

    no_tool_gmail = sanitize_agent_response(
        "בדקתי את המיילים שלך — לא מצאתי הודעות חדשות.", []
    )
    ok5 = no_tool_gmail == _SAFE_FALLBACK
    print(f"{'✅' if ok5 else '❌'} agent claims gmail read with no tool result → sanitized")
    if not ok5:
        print(f"     got: {no_tool_gmail!r}")
        failed += 1
    else:
        passed += 1

    print(f"\n{'═'*45}")
    print(f"  {passed}/{passed+failed} passed")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_tests() else 1)
