# test_router.py — בדיקות מבודדות ל-CORE_02_ROUTER
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dataclasses import dataclass, field
from core.router.router import route_request
from core.router.route_decision import Intent, RouterDomain, Risk, Handler
from core.router.channel_router import Channel

@dataclass
class MockIdentity:
    user_id:         str  = "test_user"
    role:            str  = "owner"
    tenant_id:       str  = "boss_hq"
    domain_id:       str  = "general"
    display_name:    str  = "Test"
    allowed_domains: list = field(default_factory=list)


TESTS = [
    # תיאור, טקסט, channel, role, domain_from_channel, exp_intent, exp_domain, exp_handler
    # ── Greeting / Smalltalk / Bot Status ───────────────────────────────────
    ("שלום",                  "שלום",              "telegram", "owner",   "", Intent.GREETING,         RouterDomain.GENERAL, Handler.AGENT),
    ("היי",                   "היי",               "telegram", "owner",   "", Intent.GREETING,         RouterDomain.GENERAL, Handler.AGENT),
    ("מה נשמע",               "מה נשמע",           "telegram", "owner",   "", Intent.SMALLTALK,        RouterDomain.GENERAL, Handler.AGENT),
    ("בדיקה",                 "בדיקה",             "telegram", "owner",   "", Intent.BOT_STATUS_CHECK, RouterDomain.GENERAL, Handler.AGENT),
    ("אתה עובד",              "אתה עובד?",         "telegram", "owner",   "", Intent.BOT_STATUS_CHECK, RouterDomain.GENERAL, Handler.AGENT),

    # ── Intent routing ──────────────────────────────────────────────────────
    ("משימה חדשה",            "פתח משימה להתקשר לספק",   "telegram",  "owner",    "",             Intent.CREATE_TASK,      RouterDomain.IMPORT,      Handler.AGENT),
    ("ליד נדלן",              "תוסיף ליד חדש על דירה",   "whatsapp",  "owner",    "real_estate",  Intent.CREATE_LEAD,      RouterDomain.REAL_ESTATE, Handler.AGENT),
    ("draft מייל",            "כתוב מייל לעורך הדין",    "telegram",  "owner",    "",             Intent.DRAFT_EMAIL,      RouterDomain.GENERAL,     Handler.AGENT),
    ("שליחת מייל — אישור",   "שלח מייל לעורך הדין",     "telegram",  "owner",    "",             Intent.SEND_EMAIL,       RouterDomain.GENERAL,     Handler.APPROVAL),
    ("דוח כספי",              "מה מצב התזרים",            "telegram",  "manager",  "",             Intent.FINANCIAL_REPORT, RouterDomain.FINANCE,     Handler.AGENT),
    ("סיכום",                 "תסכם את החוזה",            "telegram",  "owner",    "",             Intent.SUMMARIZE,        RouterDomain.GENERAL,     Handler.AGENT),
    ("אירוע יומן",            "קבע פגישה עם הספק מחר",   "whatsapp",  "manager",  "",             Intent.CREATE_EVENT,     RouterDomain.IMPORT,      Handler.AGENT),

    # ── Risk × Domain ────────────────────────────────────────────────────────
    ("finance + manager → ok",  "צור משימה בנושא תזרים", "telegram",  "manager",  "finance",      Intent.CREATE_TASK,      RouterDomain.FINANCE,     Handler.APPROVAL),
    ("crm + employee → ok",     "תוסיף ליד חדש",          "whatsapp",  "employee", "crm",          Intent.CREATE_LEAD,      RouterDomain.CRM,         Handler.AGENT),
    ("finance + employee → approval", "תוסיף ליד",         "whatsapp",  "employee", "finance",      Intent.CREATE_LEAD,      RouterDomain.FINANCE,     Handler.APPROVAL),

    # ── Role blocks ──────────────────────────────────────────────────────────
    ("employee + send → block", "שלח מייל לעורך הדין",   "telegram",  "employee", "",             Intent.SEND_EMAIL,       RouterDomain.GENERAL,     Handler.BLOCK),
    ("lead + delete → agent",   "תמחק את המשימה",          "whatsapp",  "lead",     "",             Intent.DELETE_TASK,      RouterDomain.GENERAL,     Handler.AGENT),

    # ── Channel detection ────────────────────────────────────────────────────
    ("channel whatsapp",        "שלום",                    "whatsapp",  "owner",    "import",       Intent.GREETING,         RouterDomain.IMPORT,      Handler.AGENT),
    ("channel telegram",        "שלום",                    "telegram",  "owner",    "",             Intent.GREETING,         RouterDomain.GENERAL,     Handler.AGENT),
]


def run_tests():
    passed = failed = 0

    for desc, text, channel_raw, role, domain_from_ch, exp_intent, exp_domain, exp_handler in TESTS:
        identity = MockIdentity(role=role)
        d = route_request(text, channel_raw, identity, domain_from_channel=domain_from_ch)

        ok = d.intent == exp_intent and d.domain == exp_domain and d.handler == exp_handler

        print(f"{'✅' if ok else '❌'} {desc}")
        if not ok:
            if d.intent  != exp_intent:  print(f"     intent:  got={d.intent!r:30} exp={exp_intent!r}")
            if d.domain  != exp_domain:  print(f"     domain:  got={d.domain!r:30} exp={exp_domain!r}")
            if d.handler != exp_handler: print(f"     handler: got={d.handler!r:30} exp={exp_handler!r}")
            failed += 1
        else:
            passed += 1

    print(f"\n{'═'*45}")
    print(f"  {passed}/{passed+failed} passed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
