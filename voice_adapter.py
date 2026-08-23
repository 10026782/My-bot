# voice_adapter.py — F07 Voice / IVR
# קו מוצר נפרד — שוק חרדי (אוקיינוס כחול)
# flag: FEATURE_VOICE_IVR (כבוי ברירת מחדל)
#
# פלטפורמות:
#   Phase 1: Twilio Voice (webhook → TwiML)
#   Phase 2: ימות המשיח (API נפרד — לא בקובץ זה)
#
# ארכיטקטורה:
#   שיחה נכנסת → Twilio webhook → voice_adapter.py
#   → VoiceSession (state machine) → שאלות בטקסט
#   → Twilio TTS (Say) + DTMFגיבוש תשובה (Gather)
#   → lead_qualifier → Airtable → הודעה לowner
#
# חוק ברזל: אותה לוגיקה כמו וואטסאפ, רק צינור שונה.
# voice_adapter לא מכיל לוגיקה עסקית — רק ממשק קולי.

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Voice Session State Machine
# ══════════════════════════════════════════════════

class VoiceState(str, Enum):
    WELCOME    = "welcome"
    DOMAIN     = "domain"      # איזה עניין? נדל"ן / ייבוא / אחר
    NAME       = "name"        # שם המתקשר
    INTEREST   = "interest"    # מה מעניין אותו
    BUDGET     = "budget"      # תקציב
    CALLBACK   = "callback"    # האם רוצה שנחזור? מתי?
    DONE       = "done"
    APPROVAL   = "approval"    # "הקש 1 לאישור"


@dataclass
class VoiceSession:
    call_sid:  str
    from_num:  str           # מספר המתקשר
    to_num:    str = ""      # Twilio destination number / service account
    state:     VoiceState = VoiceState.WELCOME
    domain:    str = ""
    answers:   dict = field(default_factory=dict)
    started_at: str = ""
    digits:    str = ""      # DTMF אחרון

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now(tz=timezone.utc).isoformat()


# ── Session Store (RAM, TTL 30 min) ──────────────
_sessions: dict[str, VoiceSession] = {}


def get_or_create_session(call_sid: str, from_num: str, to_num: str = "") -> VoiceSession:
    if call_sid not in _sessions:
        _sessions[call_sid] = VoiceSession(
            call_sid = call_sid,
            from_num = from_num,
            to_num = to_num,
        )
    return _sessions[call_sid]


def cleanup_sessions():
    """מנקה sessions ישנים (מעל 30 דקות)."""
    from datetime import timedelta
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=30)
    to_del = []
    for sid, sess in _sessions.items():
        try:
            started = datetime.fromisoformat(sess.started_at)
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started < cutoff:
                to_del.append(sid)
        except Exception:
            to_del.append(sid)
    for sid in to_del:
        _sessions.pop(sid, None)
    if to_del:
        logger.info(f"[Voice] cleaned {len(to_del)} old sessions")


# ══════════════════════════════════════════════════
# TwiML Builder
# תשובות מוחזרות כ-TwiML XML לTwilio
# ══════════════════════════════════════════════════

def _say(text: str, language: str = "he-IL") -> str:
    """TwiML Say element — Twilio TTS."""
    # ניקיון תווים שיכולים לשבור XML
    safe = text.replace("&", "ו").replace("<", "").replace(">", "")
    return f'<Say language="{language}" voice="Polly.Ayelet">{safe}</Say>'


def _gather(action_url: str, num_digits: int = 1, timeout: int = 5) -> tuple[str, str]:
    """TwiML Gather — ממתין ל-DTMF."""
    open_tag  = f'<Gather numDigits="{num_digits}" action="{action_url}" timeout="{timeout}">'
    close_tag = "</Gather>"
    return open_tag, close_tag


def _hangup() -> str:
    return "<Hangup/>"


def build_twiml(content: str) -> str:
    """עוטף תוכן ב-TwiML Response."""
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{content}</Response>'


# ══════════════════════════════════════════════════
# Flow Steps — כל שלב מחזיר TwiML
# ══════════════════════════════════════════════════

BASE_URL = os.environ.get("RENDER_APP_URL", "https://my-bot-jqz2.onrender.com")
VOICE_WEBHOOK = f"{BASE_URL}/voice/step"


def step_welcome(session: VoiceSession) -> str:
    """שלב 1: ברכה + בחירת דומיין."""
    session.state = VoiceState.DOMAIN
    g_open, g_close = _gather(VOICE_WEBHOOK, num_digits=1)
    body = (
        _say("שלום וברוכים הבאים ל-Boss HQ. "
             "לנדל\"ן לחצו 1, לייבוא סחורה לחצו 2, לאחר לחצו 3.") +
        g_open +
        _say("לנדל\"ן לחצו 1, לייבוא 2, לאחר 3.") +
        g_close
    )
    return build_twiml(body)


def step_domain(session: VoiceSession, digits: str) -> str:
    """שלב 2: קלט דומיין → שם."""
    domain_map = {"1": "real_estate", "2": "import", "3": "general"}
    session.domain = domain_map.get(digits, "general")
    session.answers["domain"] = session.domain
    session.state  = VoiceState.NAME

    domain_confirm = {
        "real_estate": "נדל\"ן",
        "import":     "ייבוא סחורה",
        "general":    "כללי",
    }.get(session.domain, "כללי")

    g_open, g_close = _gather(VOICE_WEBHOOK, num_digits=10, timeout=8)
    body = (
        _say(f"בחרתם {domain_confirm}. אנא אמרו את שמכם לאחר הצפצוף.") +
        g_open +
        _say("מה שמכם?") +
        g_close
    )
    return build_twiml(body)


def step_interest(session: VoiceSession, digits: str) -> str:
    """שלב 3: עניין → תקציב."""
    session.answers["interest"] = digits or "לא צוין"
    session.state = VoiceState.BUDGET

    g_open, g_close = _gather(VOICE_WEBHOOK, num_digits=1)
    budget_prompt = {
        "real_estate": "מה טווח התקציב? עד מיליון לחצו 1, מיליון עד שלושה לחצו 2, מעל שלושה מיליון לחצו 3.",
        "import":     "מה היקף ההזמנה? עד עשרת אלפים דולר לחצו 1, עד חמישים אלף לחצו 2, מעל חמישים אלף לחצו 3.",
        "general":    "מה דחיפות הפנייה? דחוף לחצו 1, בשבוע הקרוב לחצו 2, לא דחוף לחצו 3.",
    }.get(session.domain, "לחצו 1 להמשך.")

    body = (
        _say(budget_prompt) +
        g_open +
        _say(budget_prompt) +
        g_close
    )
    return build_twiml(body)


def step_budget(session: VoiceSession, digits: str) -> str:
    """שלב 4: תקציב → callback."""
    budget_map = {
        "real_estate": {"1": "עד מיליון", "2": "1-3 מיליון", "3": "מעל 3 מיליון"},
        "import":     {"1": "עד $10K",   "2": "עד $50K",    "3": "מעל $50K"},
        "general":    {"1": "דחוף",      "2": "שבוע",       "3": "לא דחוף"},
    }
    budget_label = budget_map.get(session.domain, {}).get(digits, "לא צוין")
    session.answers["budget"] = budget_label
    session.state = VoiceState.CALLBACK

    g_open, g_close = _gather(VOICE_WEBHOOK, num_digits=1)
    body = (
        _say("תודה. האם תרצו שנחזור אליכם? לחצו 1 לכן, 2 לא.") +
        g_open +
        _say("לחצו 1 לכן, 2 לא.") +
        g_close
    )
    return build_twiml(body)


def step_callback(session: VoiceSession, digits: str) -> str:
    """שלב 5: סיום + שמירת ליד."""
    wants_callback = digits == "1"
    session.answers["wants_callback"] = wants_callback
    session.state = VoiceState.DONE

    # שמירת ליד
    _save_voice_lead(session)

    closing = (
        "מצוין! אחד מנציגינו יחזור אליכם בהקדם. תודה ולהתראות!"
        if wants_callback
        else "תודה על פנייתכם. אתם מוזמנים לחזור ולהתקשר בכל עת. להתראות!"
    )

    return build_twiml(_say(closing) + _hangup())


# ══════════════════════════════════════════════════
# Lead Save + Owner Notification
# ══════════════════════════════════════════════════

def _save_voice_lead(session: VoiceSession) -> bool:
    """שומר ליד קולי לAirtable + מודיע לowner."""
    try:
        from feature_flags import is_enabled
        if is_enabled("VOICE_CANONICAL_LEAD_WRITE"):
            from core.noninteractive_lead_cutovers import create_voice_inbound_lead
            result = create_voice_inbound_lead(session, session.to_num)
            if not result.ok:
                logger.error("[Voice] canonical lead blocked: %s", result.reason)
            return result.ok
        from tools.airtable_tools import airtable_add  # type: ignore
        from airtable_schema import Tables        # type: ignore

        fields = {
            "memory_key":  f"voice:{session.from_num}",
            "Name":        session.answers.get("name", session.from_num),
            "phone":       session.from_num,
            "domain":      session.domain,
            "source":      "voice_ivr",
            "channel":     "voice",
            "status":      "new",
            "notes":       _format_answers(session.answers),
            "created_at":  session.started_at[:10],
        }

        result = airtable_add(Tables.LEADS, fields)
        ok = bool(result.get("ok"))
        if ok:
            logger.info(f"[Voice] Lead saved: {session.from_num} | {session.domain}")
            _notify_owner(session)
        return ok

    except ImportError:
        logger.warning(f"[Voice] dry-run lead: {session.from_num}")
        _notify_owner(session)
        return False
    except Exception as e:
        logger.error(f"[Voice] save lead error: {e}")
        return False


def _format_answers(answers: dict) -> str:
    labels = {
        "domain":          "דומיין",
        "interest":        "עניין",
        "budget":          "תקציב",
        "wants_callback":  "מבקש חזרה",
    }
    lines = ["📞 ליד קולי — IVR"]
    for k, v in answers.items():
        label = labels.get(k, k)
        lines.append(f"• {label}: {v}")
    return "\n".join(lines)


def _notify_owner(session: VoiceSession):
    """שולח הודעת טלגרם לowner."""
    try:
        import telebot  # type: ignore
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            return

        bot  = telebot.TeleBot(token)
        name = session.answers.get("name", session.from_num)
        domain_he = {"real_estate": "נדל\"ן", "import": "ייבוא", "general": "כללי"}.get(session.domain, session.domain)
        budget = session.answers.get("budget", "לא צוין")
        callback = "✅ כן" if session.answers.get("wants_callback") else "❌ לא"

        msg = (
            f"📞 *ליד קולי חדש*\n\n"
            f"👤 *{name}* | 📱 {session.from_num}\n"
            f"🏢 דומיין: {domain_he}\n"
            f"💰 תקציב: {budget}\n"
            f"📲 מבקש חזרה: {callback}\n"
            f"⏰ {session.started_at[:16].replace('T',' ')}"
        )
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        logger.info(f"[Voice] Owner notified for {session.from_num}")

    except ImportError:
        logger.debug("[Voice] telebot not available — dry-run notify")
    except Exception as e:
        logger.error(f"[Voice] notify_owner error: {e}")


# ══════════════════════════════════════════════════
# Main Handler — process_voice_step()
# נקרא מ-Flask webhook בכל שלב בשיחה
# ══════════════════════════════════════════════════

def process_voice_step(
    call_sid: str,
    from_num: str,
    digits:   str = "",
    to_num:   str = "",
) -> str:
    """
    Entry point מה-Flask webhook.
    מחזיר TwiML XML.
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("VOICE_IVR"):
            return build_twiml(
                _say("מערכת הקול אינה פעילה כעת. נסו שנית מאוחר יותר.") +
                _hangup()
            )
    except ImportError:
        pass  # dev mode

    # שבת/חג guard — IVR לא עובד בשבת
    try:
        from shabbat_guard import should_send_now, next_allowed_time  # type: ignore
        if not should_send_now("voice"):
            next_t = next_allowed_time()
            return build_twiml(
                _say(f"הקו אינו פעיל בשבת ובחגים. ניתן להתקשר לאחר {next_t}.") +
                _hangup()
            )
    except ImportError:
        pass

    session = get_or_create_session(call_sid, from_num, to_num)
    session.digits = digits

    logger.info(f"[Voice] {call_sid} | state={session.state} | digits={digits!r}")

    try:
        if session.state == VoiceState.WELCOME:
            return step_welcome(session)

        elif session.state == VoiceState.DOMAIN:
            return step_domain(session, digits)

        elif session.state == VoiceState.NAME:
            session.answers["name"] = digits or session.from_num
            return step_interest(session, digits)

        elif session.state == VoiceState.INTEREST:
            return step_interest(session, digits)

        elif session.state == VoiceState.BUDGET:
            return step_budget(session, digits)

        elif session.state == VoiceState.CALLBACK:
            return step_callback(session, digits)

        elif session.state == VoiceState.DONE:
            return build_twiml(_say("השיחה הסתיימה. תודה!") + _hangup())

        else:
            return build_twiml(_say("שגיאה פנימית. נסו שנית.") + _hangup())

    except Exception as e:
        logger.error(f"[Voice] process_voice_step error: {e}")
        return build_twiml(_say("שגיאה פנימית. נסו שנית.") + _hangup())


# ══════════════════════════════════════════════════
# Flask Routes (להוסיף ב-app.py)
# ══════════════════════════════════════════════════

FLASK_ROUTES_PATCH = '''
# ── F07 Voice IVR — הוסף ב-app.py לפני if __name__ == "__main__" ──

@app.route("/voice/incoming", methods=["POST"])
def voice_incoming():
    """Twilio webhook — שיחה נכנסת חדשה."""
    from feature_flags import flags
    if not flags.VOICE_IVR:
        from flask import Response
        from voice_adapter import build_twiml, _say, _hangup
        return Response(build_twiml(_say("השירות לא פעיל.") + _hangup()),
                        mimetype="text/xml")
    from flask import request, Response
    from voice_adapter import process_voice_step
    call_sid = request.form.get("CallSid", "")
    from_num = request.form.get("From", "").replace("whatsapp:", "")
    twiml    = process_voice_step(call_sid, from_num)
    return Response(twiml, mimetype="text/xml")


@app.route("/voice/step", methods=["POST"])
def voice_step():
    """Twilio webhook — שלב בשיחה (Gather callback)."""
    from flask import request, Response
    from voice_adapter import process_voice_step
    call_sid = request.form.get("CallSid", "")
    from_num = request.form.get("From", "").replace("whatsapp:", "")
    digits   = request.form.get("Digits", "")
    twiml    = process_voice_step(call_sid, from_num, digits)
    return Response(twiml, mimetype="text/xml")
'''


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

    # ── TwiML builders ──────────────────────────
    say = _say("שלום עולם")
    chk("_say returns XML",          "<Say" in say and "שלום עולם" in say)
    chk("_say has language",         'language="he-IL"' in say)

    twiml = build_twiml(say)
    chk("build_twiml has Response",  "<Response>" in twiml)
    chk("build_twiml has XML decl",  '<?xml' in twiml)

    hangup = _hangup()
    chk("_hangup returns Hangup",    "<Hangup" in hangup)

    g_open, g_close = _gather("/test")
    chk("_gather has action",        'action="/test"' in g_open)
    chk("_gather closes",            "</Gather>" in g_close)

    # ── Session ──────────────────────────────────
    sess = get_or_create_session("SID001", "+972501111111")
    chk("session created",           isinstance(sess, VoiceSession))
    chk("initial state=WELCOME",     sess.state == VoiceState.WELCOME)
    chk("same session on 2nd call",  get_or_create_session("SID001", "+972501111111") is sess)

    # ── Flow steps ───────────────────────────────
    twiml_w = step_welcome(sess)
    chk("welcome returns TwiML",     "<Response>" in twiml_w)
    chk("welcome transitions DOMAIN", sess.state == VoiceState.DOMAIN)
    chk("welcome has Say",           "<Say" in twiml_w)
    chk("welcome has Gather",        "<Gather" in twiml_w)

    twiml_d = step_domain(sess, "1")
    chk("domain '1' → real_estate",   sess.domain == "real_estate")
    chk("domain transitions NAME",   sess.state == VoiceState.NAME)

    twiml_i = step_interest(sess, "אשמח לדירה בתל אביב")
    chk("interest transitions BUDGET", sess.state == VoiceState.BUDGET)

    twiml_b = step_budget(sess, "2")
    chk("budget saves answer",       "budget" in sess.answers)
    chk("budget transitions CALLBACK", sess.state == VoiceState.CALLBACK)

    twiml_c = step_callback(sess, "1")
    chk("callback wants_callback=True", sess.answers.get("wants_callback") is True)
    chk("callback state=DONE",       sess.state == VoiceState.DONE)
    chk("callback has Hangup",       "<Hangup" in twiml_c)

    # ── process_voice_step — flag OFF ─────────────
    import sys, types, importlib.util
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff

    spec = importlib.util.spec_from_file_location("voice_adapter", __file__)
    va   = importlib.util.module_from_spec(spec)
    sys.modules["voice_adapter"] = va
    spec.loader.exec_module(va)

    result_off = va.process_voice_step("SID_OFF", "+972509999999")
    chk("flag=OFF → returns TwiML",  "<Response>" in result_off)
    chk("flag=OFF → has Hangup",     "<Hangup" in result_off)

    # flag ON → full flow
    ff.is_enabled = lambda x: True
    result_on = va.process_voice_step("SID_NEW", "+972508888888")
    chk("flag=ON → welcome TwiML",   "<Gather" in result_on)

    # _format_answers
    answers = {"domain": "real_estate", "budget": "1-3 מיליון", "wants_callback": True}
    fmt = _format_answers(answers)
    chk("_format_answers not empty",  len(fmt) > 10)
    chk("_format_answers has IVR",    "IVR" in fmt)

    print(f"\n{'='*40}")
    print(f"F07 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
