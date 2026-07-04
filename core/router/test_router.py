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

    # Mirrors identity.Identity.is_internal — router.py's capture_router
    # step (SPEC 1) reads this directly, same as the real Identity class.
    @property
    def is_internal(self) -> bool:
        return self.role in ("owner", "partner", "manager", "employee")

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"


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
    ("employee + send → agent", "שלח מייל לעורך הדין",   "telegram",  "employee", "",             Intent.SEND_EMAIL,       RouterDomain.GENERAL,     Handler.AGENT),
    ("lead + delete → agent",   "תמחק את המשימה",          "whatsapp",  "lead",     "",             Intent.DELETE_TASK,      RouterDomain.GENERAL,     Handler.AGENT),

    # ── Channel detection ────────────────────────────────────────────────────
    ("channel whatsapp",        "שלום",                    "whatsapp",  "owner",    "import",       Intent.GREETING,         RouterDomain.IMPORT,      Handler.AGENT),
    ("channel telegram",        "שלום",                    "telegram",  "owner",    "",             Intent.GREETING,         RouterDomain.GENERAL,     Handler.AGENT),

    # ── Soft Router — CORE_02 rules 1-8 ─────────────────────────────────────
    ("wa readonly שלום → agent",    "שלום",                 "whatsapp", "readonly", "", Intent.GREETING,   RouterDomain.GENERAL, Handler.AGENT),
    ("wa readonly unknown → agent", "ספר לי משהו מעניין",  "whatsapp", "readonly", "", Intent.UNKNOWN,    RouterDomain.GENERAL, Handler.AGENT),
    ("readonly send_email → agent", "שלח מייל לעורך הדין", "telegram", "readonly", "", Intent.SEND_EMAIL, RouterDomain.GENERAL, Handler.AGENT),
    ("owner unknown → agent",       "ספר לי משהו מעניין",  "telegram", "owner",    "", Intent.UNKNOWN,    RouterDomain.GENERAL, Handler.AGENT),

    # ── CORE_02.10 — Restricted External Request ─────────────────────────────
    ("guest + greeting",   "שלום",                "whatsapp", "guest",    "", Intent.GREETING,   RouterDomain.GENERAL, Handler.AGENT),
    ("guest + unknown",    "בלה בלה",             "whatsapp", "guest",    "", Intent.UNKNOWN,    RouterDomain.GENERAL, Handler.AGENT),
    ("guest + send_email", "שלח מייל לחברה",      "whatsapp", "guest",    "", Intent.SEND_EMAIL, RouterDomain.GENERAL, Handler.AGENT),
    ("lead + delete",      "תמחק את כל המשימות",  "whatsapp", "lead",     "", Intent.DELETE_TASK,RouterDomain.GENERAL, Handler.AGENT),
    ("owner + delete",     "תמחק את כל המשימות",  "telegram", "owner",    "", Intent.DELETE_TASK,RouterDomain.GENERAL, Handler.APPROVAL),
    ("owner + greeting",   "שלום",                "telegram", "owner",    "", Intent.GREETING,   RouterDomain.GENERAL, Handler.AGENT),

    # ── BUG-056 / BUG-IC-01 — ambiguous short-phrase regex coverage ─────────
    # Singular/plural/status variants must all clarify; explicit action-verb
    # + integration-name phrases must still reach the real system check.
    ("בדיקת מערכת (יחיד) → clarify",   "בדיקת מערכת",              "telegram", "owner", "", Intent.UNKNOWN,       RouterDomain.GENERAL, Handler.CLARIFY),
    ("בדיקות מערכת (רבים) → clarify",  "בדיקות מערכת",             "telegram", "owner", "", Intent.UNKNOWN,       RouterDomain.GENERAL, Handler.CLARIFY),
    ("בדיקת מערכת? → clarify",         "בדיקת מערכת?",             "telegram", "owner", "", Intent.UNKNOWN,       RouterDomain.GENERAL, Handler.CLARIFY),
    ("סטטוס (בלי פועל) → clarify",     "סטטוס",                    "telegram", "owner", "", Intent.UNKNOWN,       RouterDomain.GENERAL, Handler.CLARIFY),
    ("מה המצב → clarify",              "מה המצב",                  "telegram", "owner", "", Intent.UNKNOWN,       RouterDomain.GENERAL, Handler.CLARIFY),
    ("למלא משימות → clarify",          "למלא משימות",              "telegram", "owner", "", Intent.UNKNOWN,       RouterDomain.GENERAL, Handler.CLARIFY),
    ("תבדוק Airtable מפורש → agent",   "תבדוק עכשיו את Airtable",  "telegram", "owner", "", Intent.SYSTEM_STATUS, RouterDomain.GENERAL, Handler.AGENT),
    ("בדוק חיבורי מערכת מפורש → agent","בדוק חיבורי מערכת",        "telegram", "owner", "", Intent.SYSTEM_STATUS, RouterDomain.GENERAL, Handler.AGENT),

    # ── BUG-IC-01B — prefixed ambiguous phrases ──────────────────────────────
    # Common natural-language prefixes (אני צריך, צריך, תעזור לי) before
    # ambiguous task/status phrases should clarify, not fall through to Agent.
    ("אני צריך למלא משימות → clarify",              "אני צריך למלא משימות",              "telegram", "owner", "", Intent.UNKNOWN, RouterDomain.GENERAL, Handler.CLARIFY),
    ("צריך למלא משימות → clarify",                  "צריך למלא משימות",                  "telegram", "owner", "", Intent.UNKNOWN, RouterDomain.GENERAL, Handler.CLARIFY),
    ("תעזור לי למלא משימות → clarify",              "תעזור לי למלא משימות",              "telegram", "owner", "", Intent.UNKNOWN, RouterDomain.GENERAL, Handler.CLARIFY),
    ("אני צריך לראות סטטוס → clarify",              "אני צריך לראות סטטוס",              "telegram", "owner", "", Intent.UNKNOWN, RouterDomain.GENERAL, Handler.CLARIFY),
    ("צריך סטטוס → clarify",                        "צריך סטטוס",                        "telegram", "owner", "", Intent.UNKNOWN, RouterDomain.GENERAL, Handler.CLARIFY),
    ("אני צריך בדיקות מערכת → clarify",             "אני צריך בדיקות מערכת",             "telegram", "owner", "", Intent.UNKNOWN, RouterDomain.GENERAL, Handler.CLARIFY),

    # ── BUG-056 — C89 Tier 4 stop-gate ──────────────────────────────────────
    # Pasted bot output containing "הוסף משימה" still matches CREATE_TASK at
    # the intent_router layer, but Tier 4 (bot_output_block) must force
    # handler=CLARIFY / tool_allowed=False so it never reaches the Agent.
    (
        "pasted bot output w/ 'הוסף משימה' → clarify, not create_task agent",
        "✅ בוצע: משימה 1\n✅ בוצע: משימה 2\n❌ נכשל: הוסף משימה חדשה ללקוח\n",
        "telegram", "owner", "", Intent.CREATE_TASK, RouterDomain.CRM, Handler.CLARIFY,
    ),
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

    # ── BUG-056 extra assertions: Tier 4 stop-gate must also set
    # tool_allowed=False (no tools), and handle_lead_candidate() must still
    # refuse to write given the exact same capture_ic the router computed
    # (no duplicate classification, no write on Tier 4). ──────────────────
    try:
        import core.lead_candidate_handler as _lch
        _tier4_text = "✅ בוצע: משימה 1\n✅ בוצע: משימה 2\n❌ נכשל: הוסף משימה חדשה ללקוח\n"
        _identity = MockIdentity(role="owner")
        _d = route_request(_tier4_text, "telegram", _identity, domain_from_channel="")
        ok_tool_allowed = _d.tool_allowed is False
        print(f"{'✅' if ok_tool_allowed else '❌'} Tier 4 stop-gate: tool_allowed=False")
        ok_tier4_ic = _d.capture_ic is not None and _d.capture_ic.tier == 4
        print(f"{'✅' if ok_tier4_ic else '❌'} Tier 4 stop-gate: capture_ic.tier == 4")
        _lch_reply = _lch.handle_lead_candidate(
            _identity, _tier4_text, "chat_t4", "telegram",
            domain=_d.domain, ic=_d.capture_ic,
        )
        ok_no_write = _lch_reply is None
        print(f"{'✅' if ok_no_write else '❌'} Tier 4 stop-gate: handle_lead_candidate() → None (no write)")

        all_ok = failed == 0 and ok_tool_allowed and ok_tier4_ic and ok_no_write
    except ImportError:
        # httpx not available in test environment, but main test passed
        print("⚠️  Skipping Tier 4 extra assertions (httpx not available)")
        all_ok = failed == 0

    return all_ok


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
