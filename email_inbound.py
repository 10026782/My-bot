# email_inbound.py — F06 Email Channel (Inbound)
# קובץ: email_inbound.py (flat, root)
# flag: FEATURE_EMAIL_INBOUND (כבוי ברירת מחדל)
#
# זרימה:
#   poll_inbox() → parse_email() → route_email() → draft_reply() → request_approval()
#
# תלויות:
#   gmail_tools (google_tools.gmail_read קיים ✅)
#   event_bus (approval flow קיים ✅)
#   identity (resolve_identity קיים ✅)
#
# חוק ברזל: לא שולח תשובה ללא אישור owner.
# email → channel="email", identity מ-sender address.

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── כמה מיילים לסרוק בכל ריצה ──────────────────
POLL_MAX = int(os.environ.get("EMAIL_POLL_MAX", "10"))

# ── Senders לדלג עליהם (newsletters, noreply) ───
_SKIP_SENDERS_RE = re.compile(
    r"(noreply|no-reply|donotreply|newsletter|unsubscribe|mailer-daemon)",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════

@dataclass
class InboundEmail:
    msg_id:   str
    sender:   str       # כתובת מייל מלאה
    subject:  str
    snippet:  str       # תקציר מהGmail API
    body:     str = ""  # גוף מלא (אם נשלף)
    thread_id: str = ""


@dataclass
class EmailRouteResult:
    email:      InboundEmail
    domain:     str  = "general"
    intent:     str  = "ask_question"
    priority:   str  = "normal"   # urgent / normal / low
    draft:      str  = ""
    action_id:  str  = ""
    skipped:    bool = False
    skip_reason: str = ""


@dataclass
class PollResult:
    scanned:  int = 0
    routed:   int = 0
    skipped:  int = 0
    approved: int = 0
    errors:   list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════
# 1. Poll Inbox
# ══════════════════════════════════════════════════

def poll_inbox(max_results: int = POLL_MAX) -> list[InboundEmail]:
    """
    שולף מיילים נכנסים חדשים.
    מחזיר list[InboundEmail].
    """
    try:
        from google_tools import get_google_token  # type: ignore
        import httpx

        token = get_google_token()
        if not token:
            logger.warning("[EmailInbound] Google token not available")
            return _mock_emails()

        headers = {"Authorization": f"Bearer {token}"}

        # שלוף רשימת IDs
        r = httpx.get(
            "https://www.googleapis.com/gmail/v1/users/me/messages",
            headers=headers,
            params={"maxResults": max_results, "q": "is:unread"},
            timeout=10,
        )
        if r.status_code != 200:
            logger.error(f"[EmailInbound] Gmail list error {r.status_code}")
            return []

        messages = r.json().get("messages", [])
        emails   = []

        for msg in messages:
            try:
                info = httpx.get(
                    f"https://www.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
                    headers=headers,
                    params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
                    timeout=10,
                ).json()

                headers_list = info.get("payload", {}).get("headers", [])
                hmap = {h["name"]: h["value"] for h in headers_list}

                emails.append(InboundEmail(
                    msg_id    = msg["id"],
                    sender    = hmap.get("From", ""),
                    subject   = hmap.get("Subject", "(ללא נושא)"),
                    snippet   = info.get("snippet", ""),
                    thread_id = info.get("threadId", ""),
                ))
            except Exception as e:
                logger.warning(f"[EmailInbound] parse msg {msg.get('id','?')}: {e}")

        return emails

    except ImportError:
        logger.warning("[EmailInbound] google_tools not available — mock mode")
        return _mock_emails()
    except Exception as e:
        logger.error(f"[EmailInbound] poll_inbox error: {e}")
        return []


def _mock_emails() -> list[InboundEmail]:
    return [
        InboundEmail(
            msg_id="mock001", thread_id="t001",
            sender="dani@example.com",
            subject="שאלה לגבי הנכס ברחוב הרצל",
            snippet="שלום, ראיתי את המודעה לנכס ברחוב הרצל 5. האם עדיין זמין?",
        ),
        InboundEmail(
            msg_id="mock002", thread_id="t002",
            sender="supplier@china-import.com",
            subject="Invoice Q2 2026 — Order #4521",
            snippet="Please find attached the invoice for order 4521. Payment due 30 days.",
        ),
        InboundEmail(
            msg_id="noreply003", thread_id="t003",
            sender="noreply@newsletter.com",
            subject="Weekly digest",
            snippet="Your weekly newsletter is ready.",
        ),
    ]


# ══════════════════════════════════════════════════
# 2. Should Skip
# ══════════════════════════════════════════════════

def should_skip(email: InboundEmail) -> tuple[bool, str]:
    """האם לדלג על המייל הזה?"""
    sender_local = email.sender.split("@")[0] if "@" in email.sender else email.sender

    if _SKIP_SENDERS_RE.search(sender_local):
        return True, f"sender pattern: {sender_local}"

    if not email.snippet and not email.body:
        return True, "empty content"

    return False, ""


# ══════════════════════════════════════════════════
# 3. Route Email → Domain + Intent
# ══════════════════════════════════════════════════

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "real_estate": ["נכס", "דירה", "שכירות", "קרקע", "נדל", "הרצל", "property", "rental", "apartment"],
    "import":     ["invoice", "order", "supplier", "shipping", "china", "ייבוא", "ספק", "חשבונית"],
    "finance":    ["תשלום", "payment", "transfer", "bank", "חשבון", "מס", "tax"],
}

_URGENCY_KEYWORDS = ["דחוף", "urgent", "asap", "מיידי", "immediately", "today", "היום"]


def route_email(email: InboundEmail) -> tuple[str, str, str]:
    """
    מחזיר (domain, intent, priority).
    rule-based בלבד — ללא LLM.
    """
    text = f"{email.subject} {email.snippet}".lower()

    # domain
    domain   = "general"
    best_hit = 0
    for d, kws in _DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw.lower() in text)
        if hits > best_hit:
            best_hit = hits
            domain   = d

    # intent
    intent = "ask_question"
    if any(w in text for w in ["invoice", "חשבונית", "payment", "תשלום"]):
        intent = "payment_request"
    elif any(w in text for w in ["quote", "הצעת מחיר", "offer", "מחיר"]):
        intent = "request_quote"

    # priority
    priority = "urgent" if any(w in text for w in _URGENCY_KEYWORDS) else "normal"

    return domain, intent, priority


# ══════════════════════════════════════════════════
# 4. Build Draft Reply
# ══════════════════════════════════════════════════

_DRAFT_TEMPLATES: dict[str, dict[str, str]] = {
    "real_estate": {
        "ask_question":  "שלום,\n\nתודה על פנייתך לגבי הנכס.\nנשמח לענות על שאלותיך ולקבוע פגישה.\n\nבברכה,\nBoss HQ",
        "default":       "שלום,\n\nקיבלנו את פנייתך ונחזור אליך בהקדם.\n\nבברכה,\nBoss HQ",
    },
    "import": {
        "payment_request": "Hello,\n\nThank you for the invoice. We will process it and confirm payment within 3 business days.\n\nBest regards,\nBoss HQ",
        "default":         "Hello,\n\nThank you for your message. We will review and respond shortly.\n\nBest regards,\nBoss HQ",
    },
    "general": {
        "default": "שלום,\n\nתודה על פנייתך. נחזור אליך בהקדם האפשרי.\n\nבברכה,\nBoss HQ",
    },
}


def build_draft_reply(email: InboundEmail, domain: str, intent: str) -> str:
    """
    בונה טיוטת תשובה לפי domain + intent.
    לא שולח — draft בלבד.
    """
    domain_tpls = _DRAFT_TEMPLATES.get(domain, _DRAFT_TEMPLATES["general"])
    template    = domain_tpls.get(intent, domain_tpls.get("default", "שלום,\n\nנחזור אליך בהקדם.\n\nבברכה"))
    return template


# ══════════════════════════════════════════════════
# 5. Request Approval
# ══════════════════════════════════════════════════

def request_email_approval(
    email: InboundEmail,
    draft: str,
    domain: str,
    owner_chat_id: str,
) -> tuple[str, str]:
    """
    שולח לאישור owner דרך event_bus.
    לא שולח תשובה ללקוח!
    """
    try:
        from event_bus import bus  # type: ignore

        subject_preview = email.subject[:40]
        label = f"📧 מייל → {email.sender[:30]} | {subject_preview}"

        payload = {
            "action_type": "send_email_reply",
            "to":          _extract_email(email.sender),
            "subject":     f"Re: {email.subject}",
            "body":        draft,
            "thread_id":   email.thread_id,
            "domain":      domain,
        }

        action_id, btn_label = bus.request_approval(
            action  = "send_email_reply",
            payload = payload,
            chat_id = owner_chat_id,
            label   = label,
        )
        logger.info(f"[EmailInbound] Approval requested: {action_id} for {email.sender}")
        return action_id, btn_label

    except ImportError:
        logger.warning("[EmailInbound] event_bus not available — dry-run")
        return "dry-run", f"[DRY-RUN] → {email.sender}"
    except Exception as e:
        logger.error(f"[EmailInbound] request_approval error: {e}")
        return "", str(e)


def _extract_email(sender_str: str) -> str:
    """'Name <email@domain.com>' → 'email@domain.com'"""
    m = re.search(r'<([^>]+)>', sender_str)
    return m.group(1) if m else sender_str.strip()


# ══════════════════════════════════════════════════
# 6. Main Entry — run_email_poll()
# ══════════════════════════════════════════════════

def run_email_poll(owner_chat_id: str = "") -> PollResult:
    """
    Entry point לscheduler.
    סורק inbox → route → draft → אישור owner.
    לא שולח ללקוח!
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("EMAIL_INBOUND"):
            logger.info("[EmailInbound] EMAIL_INBOUND flag OFF — skipping")
            return PollResult()
    except ImportError:
        logger.warning("[EmailInbound] feature_flags not available — dev mode")

    result  = PollResult()
    emails  = poll_inbox()
    result.scanned = len(emails)

    for email in emails:
        try:
            # skip?
            skip, reason = should_skip(email)
            if skip:
                logger.debug(f"[EmailInbound] Skip {email.msg_id}: {reason}")
                result.skipped += 1
                continue

            # route
            domain, intent, priority = route_email(email)

            # draft
            draft = build_draft_reply(email, domain, intent)

            result.routed += 1
            logger.info(f"[EmailInbound] Routed: {email.sender} → domain={domain} intent={intent} priority={priority}")

            # approval
            if owner_chat_id:
                action_id, _ = request_email_approval(email, draft, domain, owner_chat_id)
                if action_id:
                    result.approved += 1

        except Exception as e:
            msg = f"error for {email.msg_id}: {e}"
            logger.error(f"[EmailInbound] {msg}")
            result.errors.append(msg)

    logger.info(
        f"[EmailInbound] Done | scanned={result.scanned} "
        f"routed={result.routed} skipped={result.skipped} "
        f"approved={result.approved} errors={len(result.errors)}"
    )
    return result


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc: str, cond: bool):
        nonlocal passed, failed
        if cond:
            print(f"✅ {desc}"); passed += 1
        else:
            print(f"❌ {desc}"); failed += 1

    # ── should_skip ──────────────────────────────
    noreply = InboundEmail("x","noreply@test.com","sub","snip")
    chk("noreply → skip",            should_skip(noreply)[0] is True)

    real = InboundEmail("y","dani@example.com","שאלה","תוכן")
    chk("real sender → no skip",     should_skip(real)[0] is False)

    empty = InboundEmail("z","user@x.com","sub","")
    chk("empty content → skip",      should_skip(empty)[0] is True)

    # ── route_email ──────────────────────────────
    re_email = InboundEmail("1","x@y.com","שאלה לגבי נכס","האם הדירה זמינה?")
    d, i, p = route_email(re_email)
    chk("real_estate email → domain=real_estate", d == "real_estate")
    chk("real_estate email → intent=ask_question", i == "ask_question")

    inv_email = InboundEmail("2","supplier@china.com","Invoice Q2","Please pay invoice 4521")
    d2, i2, _ = route_email(inv_email)
    chk("invoice email → domain=import",           d2 == "import")
    chk("invoice email → intent=payment_request",  i2 == "payment_request")

    urgent_email = InboundEmail("3","x@y.com","URGENT request","Need response today")
    _, _, p3 = route_email(urgent_email)
    chk("urgent keyword → priority=urgent",        p3 == "urgent")

    # ── build_draft_reply ─────────────────────────
    draft = build_draft_reply(re_email, "real_estate", "ask_question")
    chk("draft not empty",           len(draft) > 10)
    chk("draft contains Boss HQ",    "Boss HQ" in draft)

    draft2 = build_draft_reply(inv_email, "import", "payment_request")
    chk("import draft not empty",    len(draft2) > 10)

    # ── _extract_email ────────────────────────────
    chk("extract from 'Name <email>'", _extract_email("Dani <dani@test.com>") == "dani@test.com")
    chk("extract bare email",          _extract_email("dani@test.com") == "dani@test.com")

    # ── run_email_poll — flag OFF ─────────────────
    import sys, types, importlib.util
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff

    spec = importlib.util.spec_from_file_location("email_inbound", __file__)
    ei   = importlib.util.module_from_spec(spec)
    sys.modules["email_inbound"] = ei
    spec.loader.exec_module(ei)

    r = ei.run_email_poll()
    chk("flag=OFF → scanned=0",      r.scanned == 0)
    chk("flag=OFF → no approvals",   r.approved == 0)

    # flag ON → mock emails
    ff.is_enabled = lambda x: True
    r2 = ei.run_email_poll("chat_id")
    chk("flag=ON → scanned=3 (mock)", r2.scanned == 3)
    chk("flag=ON → skipped noreply",  r2.skipped >= 1)
    chk("flag=ON → routed >= 2",      r2.routed >= 2)

    print(f"\n{'='*40}")
    print(f"F06 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
