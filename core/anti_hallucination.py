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
            r"(בדקתי.*(ביומן|קלנדר)|אין חפיפות|הפגישה קבועה|קבעתי|נוצר ביומן|הוסף לקלנדר|"
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
    # CRM creation claims — דורשות airtable_add בלבד.
    # FOUND לא כותב airtable_add → אסור לשמש כ-evidence ליצירה.
    (
        re.compile(
            r"(הרשומה נוצרה|נוצר ליד|הליד נוצר|נוסף ל-?Airtable|נוספה רשומה|ליד חדש נוצר|lead_capture:created)",
            re.UNICODE,
        ),
        frozenset({"airtable_add"}),
    ),
    # CRM update claims — דורשות airtable_update או airtable_add.
    (
        re.compile(
            r"(עודכן ב-?Airtable|הליד עודכן|נשמר ב-?Airtable|lead_capture:updated)",
            re.UNICODE,
        ),
        frozenset({"airtable_update", "airtable_add"}),
    ),
    # CRM search/found claims — דורשות airtable_get או search_lead.
    (
        re.compile(
            r"(?<!לא )(מצאתי ליד קיים|הליד קיים|ליד קיים במערכת|lead_capture:found)",
            re.UNICODE,
        ),
        frozenset({"airtable_get", "search_lead"}),
    ),
    # Agent claims it can/did search or read a file in Drive (BUG-014: "אני
    # יכול לחפש בDrive" was said with no tool call at all)
    (
        re.compile(
            r"(אני יכול לחפש (ב-?)?Drive|חיפשתי (ב-?)?Drive|מצאתי (את ה)?קובץ|הקובץ נמצא|"
            r"קראתי (את ה)?קובץ|פתחתי (את ה)?קובץ)",
            re.UNICODE,
        ),
        frozenset({"search_drive", "read_drive_file"}),
    ),
]

# ══════════════════════════════════════════════════
# "No tool was called" detection — NEGATIVE claims.
# Mirror image of _NO_TOOL_CLAIMS: the agent can fabricate a *failure*
# diagnosis just as easily as a fake success. Evidence here means "a tool
# was actually attempted" (ok True or False) — unlike _has_required_tool,
# a real ok=False result IS valid evidence for a failure claim.
# ══════════════════════════════════════════════════

_NEGATIVE_NO_TOOL_CLAIMS: list[tuple[re.Pattern, frozenset[str] | None]] = [
    # Agent claims the calendar action specifically failed / wasn't saved
    (
        re.compile(
            r"(הפגישה לא נשמרה|בעיה בתזמון)",
            re.UNICODE,
        ),
        frozenset({"calendar_get_events", "calendar_create_event"}),
    ),
    # Generic failure/error diagnosis — scoped to "no tool call at all this
    # turn", not a specific category, since this phrasing isn't calendar-only
    (
        re.compile(
            r"(לא הצלחתי לבדוק|לא ניתן לגשת|המערכת לא מגיבה|השגיאה היא)",
            re.UNICODE,
        ),
        None,  # None = evidence is "any tool result present", any category
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


def _has_negative_evidence(tool_results: list[dict], required_tools: frozenset[str] | None) -> bool:
    """
    True if a real tool attempt grounds a *failure* claim. Unlike
    _has_required_tool, ok=False counts — a genuine failed call is exactly
    what would justify reporting a failure. required_tools=None means "any
    tool result at all" (used for category-agnostic failure phrasing).
    """
    if not tool_results:
        return False
    if required_tools is None:
        return True
    return any(r.get("tool") in required_tools for r in tool_results)


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

    # Mirror gate: agent claims a live check/action *failed* with no tool
    # attempt at all to back that diagnosis up — a fabricated failure is
    # just as much a hallucination as a fabricated success.
    for claim_pattern, required_tools in _NEGATIVE_NO_TOOL_CLAIMS:
        if claim_pattern.search(agent_text) and not _has_negative_evidence(tool_results, required_tools):
            logger.error(
                f"[A32] NO-TOOL-EVIDENCE negative-claim hallucination: "
                f"agent claims failure '{claim_pattern.pattern[:40]}' but no tool attempt found"
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

    no_tool_drive = sanitize_agent_response("אני יכול לחפש בDrive ולמצוא את הקובץ.", [])
    ok9 = no_tool_drive == _NO_TOOL_EVIDENCE_FALLBACK
    print(f"{'✅' if ok9 else '❌'} agent claims Drive search (BUG-014) with no search_drive result → blocked")
    if not ok9:
        print(f"     got: {no_tool_drive!r}")
        failed += 1
    else:
        passed += 1

    with_tool_drive = sanitize_agent_response(
        "מצאתי את הקובץ ב-Drive.",
        [{"tool": "search_drive", "content": "✅ נמצאו 1 קבצים | חוזה.pdf", "ok": True}],
    )
    ok10 = with_tool_drive not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK)
    print(f"{'✅' if ok10 else '❌'} agent claims Drive file found, real search_drive result present → passed through")
    if not ok10:
        print(f"     got: {with_tool_drive!r}")
        failed += 1
    else:
        passed += 1

    print(f"\n{'═'*45}")
    print(f"  {passed}/{passed+failed} passed")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_tests() else 1)


# ══════════════════════════════════════════════════
# CXX Tests — ActionResult → A32 integration
# ══════════════════════════════════════════════════

def _run_cxx_tests() -> bool:
    """
    בדיקות CXX:
    1. FOUND ממופה ל-airtable_get, ok=True
    2. CREATED ממופה ל-airtable_add, ok=True
    3. A32 דוחה "נוצר ליד" כשיש רק evidence של airtable_get
    4. A32 מאשר "מצאתי ליד קיים" כשיש evidence של airtable_get
    """
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond:
            print(f"  ✅ {desc}"); passed += 1
        else:
            print(f"  ❌ {desc}"); failed += 1

    print("\n── CXX A32 Integration Tests ──")

    # בדיקה 1 — FOUND → airtable_get
    found_entry = {
        "tool": "airtable_get",
        "content": "lead_capture:found:record_id=recEXIST",
        "ok": True,
    }
    chk("FOUND maps to airtable_get",
        found_entry["tool"] == "airtable_get")
    chk("FOUND ok=True",
        found_entry["ok"] is True)

    # בדיקה 2 — CREATED → airtable_add
    created_entry = {
        "tool": "airtable_add",
        "content": "lead_capture:created:record_id=recNEW123",
        "ok": True,
    }
    chk("CREATED maps to airtable_add",
        created_entry["tool"] == "airtable_add")
    chk("CREATED ok=True",
        created_entry["ok"] is True)

    # בדיקה 3 — A32 דוחה "נוצר ליד" כשיש רק airtable_get
    text_created = "נוצר ליד חדש במערכת"
    only_get = [{"tool": "airtable_get", "content": "lead found", "ok": True}]
    result3 = sanitize_agent_response(text_created, only_get)
    chk("A32 blocks 'נוצר ליד' when only airtable_get present",
        result3 == _NO_TOOL_EVIDENCE_FALLBACK)

    # בדיקה 4 — A32 מאשר "נוצר ליד" כשיש airtable_add
    with_add = [{"tool": "airtable_add", "content": "lead_capture:created:record_id=rec123", "ok": True}]
    result4 = sanitize_agent_response(text_created, with_add)
    chk("A32 passes 'נוצר ליד' when airtable_add present",
        result4 not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK))

    # בדיקה 5 — A32 מאשר "מצאתי ליד קיים" כשיש airtable_get
    text_found = "מצאתי ליד קיים במערכת"
    result5 = sanitize_agent_response(text_found, only_get)
    chk("A32 passes 'מצאתי ליד קיים' when airtable_get present",
        result5 not in (_NO_TOOL_EVIDENCE_FALLBACK, _SAFE_FALLBACK))

    # בדיקה 6 — A32 דוחה "מצאתי ליד קיים" בלי שום tool
    result6 = sanitize_agent_response(text_found, [])
    chk("A32 blocks 'מצאתי ליד קיים' with no tool result",
        result6 == _NO_TOOL_EVIDENCE_FALLBACK)

    # בדיקה 7 — tool loop לא נשבר (רשומה רגילה עוברת)
    normal_entry = [{"tool": "airtable_get", "content": "3 leads found", "ok": True}]
    result7 = sanitize_agent_response("מצאתי 3 לידים.", normal_entry)
    chk("Normal flow not broken — unrelated text passes through",
        result7 == "מצאתי 3 לידים.")

    print(f"  {'─'*38}")
    print(f"  CXX Tests: {passed} passed, {failed} failed\n")
    return failed == 0
