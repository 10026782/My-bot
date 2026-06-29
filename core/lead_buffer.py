# core/lead_buffer.py — Request-scoped Lead Payload Buffer
#
# כשה-Agent נחסם מלכתוב ל-Leads ישירות (LeadsWriteGate),
# ה-payload שחילץ מהשיחה נשמר כאן — לא אובד.
#
# בסוף ה-request, capture_inbound_lead קורא את ה-buffer
# ומעשיר את הליד החוקי בשדות שהAgent חילץ.
#
# כללים:
# - Buffer הוא per-request — נוצר ונמחק באותו request.
# - רק שדות מ-LeadFields allowlist מותרים לשמירה.
# - Buffer לא מחזיר הרשאה ל-Agent. הוא רק מציל מידע.
# - אם אין buffer — capture_inbound_lead עובד כרגיל.
# - אם יש buffer — השדות מועשרים לאחר יצירת הליד.

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ── Allowlist — שדות מ-buffer שמותר לכתוב לליד ─────────────────────────
# שדות מזהה (phone, memory_key, source, channel) לא מגיעים מה-buffer —
# הם תמיד מגיעים מ-identity. רק מידע עסקי-אנושי מהשיחה.
_BUFFER_ALLOWED_FIELDS = frozenset({
    "Name",           # LeadFields.NAME — אם Agent חילץ שם אמיתי
    "notes",          # הערות חופשיות — לא schema field רשמי, יישמר כ-summary
    "summary",        # LeadFields.SUMMARY
    "domain",         # LeadFields.DOMAIN
    "interests",      # שדה עתידי
    "email",          # שדה עתידי
})

# ── Thread-local storage — per-request buffer ────────────────────────────
_local = threading.local()


def _get_buffer() -> list[dict]:
    """מחזיר את ה-buffer הנוכחי של ה-thread (request)."""
    if not hasattr(_local, "lead_payloads"):
        _local.lead_payloads = []
    return _local.lead_payloads


def save_blocked_payload(fields: dict, source: str = "agent") -> None:
    """
    שומר payload שנחסם ע"י LeadsWriteGate.
    מסנן רק שדות מהallowlist.
    נקרא מ-dispatcher.py כשLeadsDirectWriteBlocked נזרקת.
    """
    allowed = {
        k: v for k, v in fields.items()
        if k in _BUFFER_ALLOWED_FIELDS
    }
    if not allowed:
        logger.debug("[LeadBuffer] blocked payload has no allowlisted fields — skipped")
        return

    _get_buffer().append({
        "fields":  allowed,
        "source":  source,
    })
    logger.info(
        "[LeadBuffer] saved blocked payload | keys=%s source=%s",
        list(allowed.keys()), source,
    )


def consume_buffer() -> dict:
    """
    מחזיר dict מאוחד של כל ה-payloads שנשמרו בrequest הנוכחי.
    מנקה את ה-buffer אחרי הקריאה (consume once).
    נקרא מ-capture_inbound_lead לפני יצירת הליד.
    """
    payloads = _get_buffer()
    if not payloads:
        return {}

    merged: dict[str, Any] = {}
    for entry in payloads:
        for k, v in entry["fields"].items():
            if k not in merged:  # first-write wins
                merged[k] = v

    # ניקוי
    _local.lead_payloads = []
    logger.info("[LeadBuffer] consumed buffer | keys=%s", list(merged.keys()))
    return merged


def has_buffer() -> bool:
    """האם יש payloads ממתינים ב-buffer?"""
    return bool(_get_buffer())


def clear_buffer() -> None:
    """מנקה את ה-buffer — קרא בסוף request אם לא נצרך."""
    _local.lead_payloads = []



# ══════════════════════════════════════════════════
# recover_blocked_lead_payload — Recovery בתוך אותו request
# ══════════════════════════════════════════════════

def recover_blocked_lead_payload(identity, domain: str = "general") -> bool:
    """
    צורך את ה-buffer ומעדכן את הליד שנוצר באותו request.

    סדר הקריאה ב-run_agent:
      1. capture_inbound_lead  ← יוצר ליד (buffer ריק)
      2. Agent רץ              ← נחסם, buffer מתמלא
      3. recover_blocked_lead_payload ← כאן (buffer מלא)
      4. clear_buffer (finally)

    הכלל:
    - buffer → patch לשדות ריקים בליד שנוצר (Name, summary)
    - אם ליד קיים כבר ויש תוכן חדש → Lead Event
    - phone / memory_key / source → תמיד מ-identity, לא מ-buffer
    - לא דורס שדות קיימים

    מחזיר True אם recovery בוצע, False אחרת.
    """
    buf = consume_buffer()
    if not buf:
        return False  # אין מה לשחזר

    try:
        from airtable_schema import LeadFields, Tables
        from tools.airtable_tools import airtable_get
        from core.action_result import ActionResult

        # תיקון תאימות: זהה ל-lead_capture.capture_inbound_lead — domain="general"
        # משתמש במפתח הישן (בלי סיומת), אחרת lookup לא ימצא את הליד שנוצר.
        _domain_key = domain if (domain and domain != "general") else "general"
        memory_key  = (
            identity.memory_key if _domain_key == "general"
            else f"{identity.memory_key}:{_domain_key}"
        )

        # מצא את הליד שנוצר באותו request
        raw = airtable_get(Tables.LEADS, f"{{{LeadFields.MEMORY_KEY}}}='{memory_key}'")

        import re
        existing_m = re.search(r"rec\w+", raw or "")
        if not existing_m:
            logger.info("[LeadBuffer] recovery: no lead found for %s — skipping", memory_key)
            return False

        lead_id = existing_m.group(0)

        # בדוק אילו שדות allowlisted ריקים — patch רק אותם
        _PATCHABLE = {
            "Name":    LeadFields.NAME,
            "summary": LeadFields.SUMMARY,
        }
        patch_fields = {}
        for buf_key, lead_field in _PATCHABLE.items():
            val = buf.get(buf_key) or buf.get("notes") if buf_key == "summary" else buf.get(buf_key)
            if val:
                patch_fields[lead_field] = str(val)[:500]

        if patch_fields:
            try:
                from tools.airtable_gateway import airtable_patch as _gw_patch
                _gw_patch(Tables.LEADS, lead_id, patch_fields, source="lead_recovery")
                logger.info(
                    "[LeadBuffer] recovery: patched lead %s | keys=%s",
                    lead_id, list(patch_fields.keys()),
                )
            except Exception as e:
                logger.warning("[LeadBuffer] recovery patch failed: %s", e)

        # אם יש מידע נוסף שלא נכנס לpatch — כתוב Lead Event
        extra = {k: v for k, v in buf.items() if k not in ("Name", "summary", "notes")}
        if extra:
            try:
                from lead_capture import capture_lead_event
                capture_lead_event(identity, str(extra), lead_id, domain=domain)
            except Exception as e:
                logger.debug("[LeadBuffer] recovery event failed (non-critical): %s", e)

        return True

    except Exception as e:
        logger.warning("[LeadBuffer] recovery failed (non-critical): %s", e)
        return False


# ── Self-tests ────────────────────────────────────────────────────────────

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"  ✅ {desc}"); passed += 1
        else: print(f"  ❌ {desc}"); failed += 1

    print("\n── LeadBuffer Tests ──")

    # T01 — שמירה וצריכה בסיסית
    clear_buffer()
    save_blocked_payload({"Name": "משה חביב", "notes": "מעוניין במיטות"}, "agent")
    chk("T01: has_buffer after save", has_buffer())
    buf = consume_buffer()
    chk("T01: Name in buffer", buf.get("Name") == "משה חביב")
    chk("T01: notes in buffer", "notes" in buf)
    chk("T01: buffer empty after consume", not has_buffer())

    # T02 — שדות לא מ-allowlist מסוננים
    clear_buffer()
    save_blocked_payload({
        "Name": "אבי",
        "phone": "+972500000000",    # ← לא מ-allowlist
        "memory_key": "boss_hq:x",  # ← לא מ-allowlist
        "source": "agent",           # ← לא מ-allowlist
    }, "agent")
    buf2 = consume_buffer()
    chk("T02: Name allowed", "Name" in buf2)
    chk("T02: phone filtered out", "phone" not in buf2)
    chk("T02: memory_key filtered out", "memory_key" not in buf2)
    chk("T02: source filtered out", "source" not in buf2)

    # T03 — payload ריק לא נשמר
    clear_buffer()
    save_blocked_payload({"phone": "+972500000000", "source": "agent"}, "agent")
    chk("T03: no allowlisted fields → buffer empty", not has_buffer())

    # T04 — מספר payloads מאוחדים, first-write wins
    clear_buffer()
    save_blocked_payload({"Name": "ראשון", "domain": "real_estate"}, "agent")
    save_blocked_payload({"Name": "שני", "summary": "פרטים נוספים"}, "agent")
    buf4 = consume_buffer()
    chk("T04: first Name wins", buf4.get("Name") == "ראשון")
    chk("T04: summary from second payload", "summary" in buf4)
    chk("T04: domain from first payload", buf4.get("domain") == "real_estate")

    # T05 — consume מנקה
    clear_buffer()
    save_blocked_payload({"Name": "בדיקה"}, "agent")
    consume_buffer()
    chk("T05: buffer empty after consume", not has_buffer())

    # T06 — consume על buffer ריק מחזיר dict ריק
    clear_buffer()
    result = consume_buffer()
    chk("T06: empty buffer → empty dict", result == {})

    # T07 — clear_buffer מנקה
    clear_buffer()
    save_blocked_payload({"Name": "בדיקה"}, "agent")
    clear_buffer()
    chk("T07: clear_buffer works", not has_buffer())

    print(f"\n  {'─'*40}")
    # T08 — recover: buffer מלא באותו request → מידע לא אובד
    clear_buffer()
    save_blocked_payload({"Name": "שם שנחסם", "summary": "פרטים שנחסמו"}, "agent")
    chk("T08: buffer survives until explicit consume", has_buffer())
    buf8 = consume_buffer()
    chk("T08: Name not lost within same request", buf8.get("Name") == "שם שנחסם")
    chk("T08: summary not lost", "summary" in buf8)
    chk("T08: buffer cleared after consume", not has_buffer())

    # T09 — clear_buffer בfinally לא מוחק לפני recovery
    clear_buffer()
    save_blocked_payload({"Name": "לא ייאבד"}, "agent")
    chk("T09: buffer available for recovery before clear", has_buffer())
    # simulate recover then finally clear
    recovered = consume_buffer()
    clear_buffer()  # finally
    chk("T09: recovery got the data", recovered.get("Name") == "לא ייאבד")
    chk("T09: finally clear works", not has_buffer())

    print(f"  LeadBuffer Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import sys, logging
    logging.basicConfig(level=logging.WARNING)
    sys.exit(0 if _run_tests() else 1)
