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
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


_STRUCTURED_ID_TOOLS = {
    "calendar_create_event": "event_id",
    "gmail_draft":          "draft_id",
    "gmail_send_draft":     "message_id",
    "airtable_add":         "record_id",
    "airtable_update":      "record_id",
}

# ══════════════════════════════════════════════════
# "No tool was called" detection patterns.
# If agent text matches a claim AND no result from one of the required
# tools is present in tool_results (by tool name, not text-guessing)
# → agent hallucinated a live check / action on an external system.
# ══════════════════════════════════════════════════

_NO_TOOL_CLAIMS: list[tuple[re.Pattern, frozenset[str]]] = [
    # Agent claims it checked / created a calendar event
    (
        re.compile(
            r"(בדקתי.*ביומן|אין חפיפות|הפגישה קבועה|קבעתי|נוצר ביומן|הוסף לקלנדר|"
            r"יוצר (את ה)?(פגיש|אירוע)|קובע (את ה)?(פגיש|אירוע)|פגישה חדשה)",
            re.UNICODE,
        ),
        frozenset({"calendar_get_events", "calendar_create_event"}),
    ),
    # Agent claims it read / drafted / sent email
    (
        re.compile(
            r"(בדקתי.*מייל|קראתי.*הודעות|לא.*מצאתי.*מייל|המייל.*נשלח|שלחתי.*מייל|טיוטה.*נשמר)",
            re.UNICODE,
        ),
        frozenset({"gmail_read", "gmail_draft", "gmail_send_draft"}),
    ),
    # Agent claims it created / updated a CRM (Airtable) record
    (
        re.compile(
            r"(הרשומה נוצרה|נוצר ליד|הליד נוצר|נוסף ל-?Airtable|עודכן ב-?Airtable|הליד עודכן|נוספה רשומה|נשמר ב-?Airtable)",
            re.UNICODE,
        ),
        frozenset({"airtable_add", "airtable_update", "airtable_get", "search_lead"}),
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

def _content_text(content: Any) -> str:
    if isinstance(content, dict):
        return str(content.get("user_message") or content.get("external_id") or content)
    return str(content or "")


def _structured_result_id(raw_output: dict, id_key: str) -> str:
    external_id = str(raw_output.get("external_id", "") or "")
    evidence = raw_output.get("evidence", {})
    if external_id:
        return external_id
    if isinstance(evidence, dict):
        return str(evidence.get(id_key, "") or "")
    return ""


def verify_execution(tool_name: str, raw_output: Any) -> VerifyResult:
    """
    Checks whether a tool call actually succeeded.
    Called immediately after validate_tool_output().
    """
    if not raw_output:
        return VerifyResult("failed", "output is empty or None")

    if isinstance(raw_output, dict):
        if not raw_output.get("ok"):
            return VerifyResult("failed", _content_text(raw_output)[:160])

        id_key = _STRUCTURED_ID_TOOLS.get(tool_name)
        if id_key:
            external_id = _structured_result_id(raw_output, id_key)
            if not external_id:
                return VerifyResult(
                    "failed",
                    f"{tool_name}: missing external_id/{id_key} in structured result"
                )
            if tool_name == "calendar_create_event":
                evidence = raw_output.get("evidence", {})
                html_link = evidence.get("htmlLink", "") if isinstance(evidence, dict) else ""
                if not html_link:
                    return VerifyResult(
                        "failed",
                        "calendar_create_event: missing evidence.htmlLink"
                    )
            if tool_name.startswith("airtable_") and not external_id.startswith("rec"):
                return VerifyResult(
                    "failed",
                    f"{tool_name}: external_id '{external_id}' is not an Airtable record_id"
                )
        return VerifyResult("ok")

    raw_text = _content_text(raw_output)
    if raw_text.lstrip().startswith("❌"):
        return VerifyResult("failed", raw_text[:120])

    if tool_name in _STRUCTURED_ID_TOOLS:
        return VerifyResult(
            "failed",
            f"{tool_name}: expected structured result with ok=true and external_id"
        )

    return VerifyResult("ok")


# ══════════════════════════════════════════════════
# 2. verify_result_claim
# ══════════════════════════════════════════════════

_POSITIVE_CLAIMS = re.compile(r"(נשלח|בוצע|נוצר|נשמר|הוסף|עודכן|נרשם)", re.UNICODE)
_NEGATIVE_CLAIMS = re.compile(r"לא מצאתי|אין תוצאות|לא נמצא", re.UNICODE)


def _all_failed(tool_results: list[dict]) -> bool:
    """True if every tool result content is a failed structured result or starts with ❌."""
    if not tool_results:
        return False
    for r in tool_results:
        content = r.get("content")
        if isinstance(content, dict):
            if content.get("ok"):
                return False
            continue
        if not (isinstance(content, str) and content.lstrip().startswith("❌")):
            return False
    return True


def _has_data(tool_results: list[dict]) -> bool:
    """True if any tool result contains non-error, non-empty content."""
    for r in tool_results:
        content = r.get("content", "")
        if isinstance(content, dict):
            if content.get("ok") or content.get("external_id"):
                return True
            continue
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

_SAFE_FALLBACK   = "לא הצלחתי לבצע את הפעולה. אנא נסה שוב."
_MISMATCH_PREFIX = "⚠️ שים לב — ייתכן שהתוצאה אינה מדויקת.\n"
_NO_TOOL_EVIDENCE_FALLBACK = "לא הצלחתי לאמת את הפעולה מול הכלי. לא ביצעתי שינוי. אפשר לנסות שוב?"


def _has_required_tool(tool_results: list[dict], required_tools: frozenset[str]) -> bool:
    """
    True if a non-failed result from one of required_tools is present.
    Identity-based (by tool name), not text-guessing — a tool call that
    itself failed does not count as evidence for the agent's claim.
    """
    return any(
        r.get("tool") in required_tools and r.get("ok", True)
        for r in tool_results
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

    # "No tool called" gate: agent claims a live check/action on an
    # external system but no result from a required tool is present.
    for claim_pattern, required_tools in _NO_TOOL_CLAIMS:
        if claim_pattern.search(agent_text) and not _has_required_tool(tool_results, required_tools):
            logger.error(
                f"[A32] NO-TOOL-EVIDENCE hallucination: "
                f"agent claims '{claim_pattern.pattern[:40]}' but no {sorted(required_tools)} tool result found"
            )
            return _NO_TOOL_EVIDENCE_FALLBACK

    return agent_text


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _make_result(
    tool: str,
    external_id: str = "",
    ok: bool = True,
    evidence: dict | None = None,
    user_message: str = "ok",
) -> dict:
    return {
        "ok": ok,
        "tool": tool,
        "external_id": external_id,
        "evidence": evidence or {},
        "user_message": user_message,
    }


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

    # ── verify_execution — structured dict contract ──────────
    check("airtable_add success (structured dict, rec-id)",
          verify_execution("airtable_add", _make_result("airtable_add", "rec1234abc")),
          "ok")

    check("airtable_add ok=False → failed",
          verify_execution("airtable_add", _make_result("airtable_add", ok=False, user_message="❌ Airtable error 422")),
          "failed")

    check("airtable_add empty output → failed",
          verify_execution("airtable_add", ""),
          "failed")

    check("airtable_add non-rec external_id → failed",
          verify_execution("airtable_add", _make_result("airtable_add", "not_a_rec")),
          "failed")

    check("airtable_add plain string (old format) → failed",
          verify_execution("airtable_add", "Created: rec1234abc"),
          "failed")

    check("gmail_draft success (structured dict)",
          verify_execution("gmail_draft", _make_result("gmail_draft", "draft_xyz")),
          "ok")

    check("gmail_draft ok=False → failed",
          verify_execution("gmail_draft", _make_result("gmail_draft", ok=False, user_message="❌ Gmail 403")),
          "failed")

    check("gmail_draft plain string (old format) → failed",
          verify_execution("gmail_draft", "Draft created (id=draft_xyz)"),
          "failed")

    check("calendar_create_event success (structured dict with htmlLink)",
          verify_execution("calendar_create_event", _make_result(
              "calendar_create_event", "evt_abc123",
              evidence={"htmlLink": "https://calendar.google.com/event?eid=abc"},
          )),
          "ok")

    check("calendar_create_event ok=True but missing htmlLink → failed",
          verify_execution("calendar_create_event", _make_result("calendar_create_event", "evt_abc123")),
          "failed")

    check("calendar_create_event conflict (ok=False) → failed",
          verify_execution("calendar_create_event", _make_result(
              "calendar_create_event", ok=False,
              evidence={"conflict": "⚠️ כבר קיים ביומן: 'אירוע' (14:00)"},
              user_message="⚠️ כבר קיים ביומן: 'אירוע' (14:00). לקבוע בכל זאת?",
          )),
          "failed")

    check("calendar_create_event plain string (old format) → failed",
          verify_execution("calendar_create_event", "✅ אירוע 'פגישה' נוצר ביומן ל-01/06/2025 14:00."),
          "failed")

    check("gmail_send_draft success (structured dict)",
          verify_execution("gmail_send_draft", _make_result("gmail_send_draft", "msg_abc123")),
          "ok")

    check("gmail_send_draft ok=False → failed",
          verify_execution("gmail_send_draft", _make_result("gmail_send_draft", ok=False, user_message="❌ Gmail 500")),
          "failed")

    check("gmail_send_draft plain string (old format) → failed",
          verify_execution("gmail_send_draft", "📧 טיוטה draft_abc נשלחה בהצלחה!"),
          "failed")

    check("non-structured tool, plain string → ok",
          verify_execution("calendar_get_events", "📅 3 אירועים קרובים:"),
          "ok")

    check("non-structured tool, empty string → failed",
          verify_execution("calendar_get_events", ""),
          "failed")

    # ── verify_result_claim ──────────────────────
    failed_results = [{"content": _make_result("airtable_add", ok=False, user_message="❌ connection error")}]
    ok_results     = [{"content": _make_result("airtable_add", "rec1234")}]
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

    # ── "no tool called" gate — identity-based (by tool name), production format ──
    calendar_results = [{
        "tool": "calendar_create_event",
        "content": "✅ אירוע 'פגישה' נוצר ביומן ל-01/06/2025 14:00.",
        "ok": True,
    }]
    failed_calendar_results = [{
        "tool": "calendar_create_event",
        "content": "❌ הפעולה לא הושלמה: calendar_create_event: missing evidence.htmlLink",
        "ok": False,
    }]

    no_tool_calendar = sanitize_agent_response(
        "בדקתי את הביומן שלך — אין חפיפות. הפגישה קבועה.", []
    )
    ok3 = no_tool_calendar == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok3 else '❌'} agent claims calendar check with no tool result → blocked")
    if not ok3:
        print(f"     got: {no_tool_calendar!r}")
        failed += 1
    else:
        passed += 1

    with_tool_calendar = sanitize_agent_response(
        "בדקתי את הביומן שלך — אין חפיפות. הפגישה קבועה.", calendar_results
    )
    ok4 = with_tool_calendar not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok4 else '❌'} agent claims calendar, real tool result present → passed through")
    if not ok4:
        print(f"     got: {with_tool_calendar!r}")
        failed += 1
    else:
        passed += 1

    failed_tool_calendar = sanitize_agent_response(
        "בדקתי את הביומן שלך — אין חפיפות. הפגישה קבועה.", failed_calendar_results
    )
    ok4b = failed_tool_calendar == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok4b else '❌'} agent claims calendar but the tool call itself failed → blocked")
    if not ok4b:
        print(f"     got: {failed_tool_calendar!r}")
        failed += 1
    else:
        passed += 1

    no_tool_gmail = sanitize_agent_response(
        "בדקתי את המיילים שלך — לא מצאתי הודעות חדשות.", []
    )
    ok5 = no_tool_gmail == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok5 else '❌'} agent claims gmail read with no tool result → blocked")
    if not ok5:
        print(f"     got: {no_tool_gmail!r}")
        failed += 1
    else:
        passed += 1

    no_tool_gmail_draft = sanitize_agent_response("טיוטה נשמרה.", [])
    ok6 = no_tool_gmail_draft == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok6 else '❌'} agent claims 'טיוטה נשמרה' with no gmail_draft result → blocked")
    if not ok6:
        print(f"     got: {no_tool_gmail_draft!r}")
        failed += 1
    else:
        passed += 1

    no_tool_airtable = sanitize_agent_response("הרשומה נוצרה בהצלחה.", [])
    ok7 = no_tool_airtable == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok7 else '❌'} agent claims Airtable record created with no airtable tool result → blocked")
    if not ok7:
        print(f"     got: {no_tool_airtable!r}")
        failed += 1
    else:
        passed += 1

    with_tool_airtable = sanitize_agent_response(
        "הרשומה נוצרה בהצלחה.",
        [{"tool": "airtable_add", "content": "✅ רשומה נוספה | ID: rec123", "ok": True}],
    )
    ok8 = with_tool_airtable not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok8 else '❌'} agent claims Airtable record created, real tool result present → passed through")
    if not ok8:
        print(f"     got: {with_tool_airtable!r}")
        failed += 1
    else:
        passed += 1

    print(f"\n{'═'*45}")
    print(f"  {passed}/{passed+failed} passed")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_tests() else 1)
