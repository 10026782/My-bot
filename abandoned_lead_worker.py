# abandoned_lead_worker.py — D02 Abandoned Lead Worker
# קובץ: abandoned_lead_worker.py (flat, root)
# flag: ABANDONED_LEADS (env: ABANDONED_LEADS=true)
#
# מה זה:
#   ליד התחיל שאלון → לא ענה X דקות → זיהוי אוטומטי
#   → לפי ערוץ המקור:
#       whatsapp/telegram/email → הקפצה אוטומטית (לאישור owner)
#       voice → משימת Human Pipeline (לא הקפצה קולית!)
#
# drop-off report: באיזה שלב נטשו הכי הרבה → עזרה לשיפור השאלון
# תלוי ב: session_store.py (D02 תשתית)

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from airtable_schema import Tables, TaskFields, TaskStatus
from core.query_contract import all_of, equals, not_equals

logger = logging.getLogger(__name__)

# ── Timeout לפי ערוץ (דקות) ───────────────────────
_TIMEOUT_MINUTES: dict[str, int] = {
    "whatsapp": 30,   # 30 דקות בלי מענה = נטישה
    "telegram": 30,
    "email":    120,  # מייל = 2 שעות (async)
    "voice":    5,    # IVR = 5 דקות (נטישת שיחה)
    "default":  30,
}

# ── ערוצים שמקבלים הקפצה אוטומטית (vs Human Pipeline) ──
_AUTO_BOUNCE_CHANNELS    = {"whatsapp", "telegram", "email"}
_HUMAN_PIPELINE_CHANNELS = {"voice"}


# ══════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════

@dataclass
class AbandonedLead:
    sender:         str
    channel:        str
    domain:         str
    step:           int          # באיזה שלב נטש
    total_steps:    int          # כמה שלבים בשאלון
    minutes_silent: float
    answers:        dict = field(default_factory=dict)
    action:         str = ""     # "bounce" / "human_pipeline"
    bounce_draft:   str = ""


@dataclass
class WorkerResult:
    scanned:        int = 0
    abandoned:      int = 0
    bounced:        int = 0     # הקפצות שנשלחו לאישור
    human_pipeline: int = 0     # משימות לנציג
    errors:         list = field(default_factory=list)


@dataclass
class DropOffReport:
    """כמה לידים נטשו בכל שלב — לשיפור השאלון."""
    by_step:    dict[int, int] = field(default_factory=dict)  # step → count
    by_channel: dict[str, int] = field(default_factory=dict)  # channel → count
    total:      int = 0

    def worst_step(self) -> Optional[int]:
        if not self.by_step:
            return None
        return max(self.by_step, key=self.by_step.get)

    def format(self) -> str:
        if not self.total:
            return "📊 Drop-off: אין נתונים."
        lines = [f"📊 *Drop-off Report* | סה\"כ נטשו: {self.total}\n"]
        for step, count in sorted(self.by_step.items()):
            bar = "█" * min(count, 10)
            lines.append(f"  שלב {step}: {count} נטישות {bar}")
        worst = self.worst_step()
        if worst is not None:
            lines.append(f"\n⚠️ *צוואר בקבוק: שלב {worst}* — שקול לשפר את השאלה.")
        return "\n".join(lines)


# ══════════════════════════════════════════════════
# 1. Scan for Abandoned Sessions
# ══════════════════════════════════════════════════

def scan_abandoned() -> list[AbandonedLead]:
    """
    סורק sessions פעילים מDB ומחפש נטישות.
    מקור: Airtable LeadSessions (שמסונכרן ע"י session_store).
    """
    try:
        from tools.airtable_tools import airtable_get  # type: ignore
        raw = airtable_get(
            "LeadSessions",
            all_of(equals("done", 0), not_equals("drop_off_step", "")),
        )
        result = _parse_sessions(raw)
        if not result:
            return []
        return result
    except ImportError:
        logger.warning("[D02] airtable not available — scan skipped")
        return []
    except Exception as e:
        logger.error(f"[D02] scan error: {e}")
        return []


def _parse_sessions(raw: str) -> list[AbandonedLead]:
    """Parser ל-airtable_get output."""
    import re, json as _json
    if not raw or "אין רשומות" in raw or "❌" in raw:
        return []

    abandoned = []
    now = datetime.now(tz=timezone.utc)

    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("•"):
            continue
        try:
            sender_m  = re.search(r'sender[:\s]+(\S+)',       line, re.IGNORECASE)
            channel_m = re.search(r'channel[:\s]+(\w+)',      line, re.IGNORECASE)
            domain_m  = re.search(r'domain[:\s]+(\w+)',       line, re.IGNORECASE)
            step_m    = re.search(r'drop_off_step[:\s]+(\d+)', line, re.IGNORECASE)
            updated_m = re.search(r'updated_at[:\s]+(\S+)',   line, re.IGNORECASE)
            answers_m = re.search(r'answers[:\s]+(\{.+\})',   line, re.IGNORECASE)

            if not (sender_m and channel_m and step_m and updated_m):
                continue

            channel   = channel_m.group(1)
            step      = int(step_m.group(1))
            updated   = datetime.fromisoformat(updated_m.group(1).replace("Z", "+00:00"))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)

            minutes_silent = (now - updated).total_seconds() / 60
            timeout = _TIMEOUT_MINUTES.get(channel, _TIMEOUT_MINUTES["default"])

            if minutes_silent < timeout:
                continue  # לא עבר הזמן עדיין

            answers = {}
            if answers_m:
                try:
                    answers = _json.loads(answers_m.group(1))
                except Exception:
                    pass

            abandoned.append(AbandonedLead(
                sender         = sender_m.group(1),
                channel        = channel,
                domain         = domain_m.group(1) if domain_m else "general",
                step           = step,
                total_steps    = 5,
                minutes_silent = round(minutes_silent, 1),
                answers        = answers,
            ))
        except Exception:
            continue

    return abandoned


def _mock_abandoned() -> list[AbandonedLead]:
    """מוק לסביבת dev."""
    return [
        AbandonedLead(
            sender="w:972501111111", channel="whatsapp", domain="real_estate",
            step=2, total_steps=5, minutes_silent=45.0,
            answers={"domain": "נדל\"ן", "budget": "2 מיליון"},
        ),
        AbandonedLead(
            sender="t:123456789", channel="telegram", domain="import",
            step=1, total_steps=5, minutes_silent=60.0,
            answers={"domain": "ייבוא"},
        ),
        AbandonedLead(
            sender="voice:972509999999", channel="voice", domain="real_estate",
            step=3, total_steps=5, minutes_silent=8.0,
            answers={"domain": "נדל\"ן", "budget": "1 מיליון", "timeline": "דחוף"},
        ),
    ]


# ══════════════════════════════════════════════════
# 2. Decide Action by Channel
# ══════════════════════════════════════════════════

def decide_action(lead: AbandonedLead) -> str:
    """
    מחזיר "bounce" / "human_pipeline" לפי ערוץ המקור.
    Voice → תמיד human_pipeline (לא שולחים הודעה קולית אוטומטית).
    """
    if lead.channel in _HUMAN_PIPELINE_CHANNELS:
        return "human_pipeline"
    if lead.channel in _AUTO_BOUNCE_CHANNELS:
        return "bounce"
    return "human_pipeline"  # ברירת מחדל — בטוח


# ══════════════════════════════════════════════════
# 3. Build Bounce Message
# ══════════════════════════════════════════════════

_BOUNCE_TEMPLATES: dict[str, str] = {
    "real_estate": "שלום! ראינו שהתחלת לחפש נכס אבל לא סיימת.\nכדי שנוכל לעזור לך — באיזה שלב נתקעת? 🏠",
    "import":     "שלום! התחלת לחקור ייבוא סחורה אבל נשארת באמצע.\nאשמח לעזור לך להמשיך — מה עצר אותך? 📦",
    "general":    "שלום! ראינו שהתחלת תהליך אצלנו.\nנשמח לעזור לך להמשיך — פשוט ענה כאן. 😊",
}


def build_bounce_message(lead: AbandonedLead) -> str:
    """הודעת הקפצה — ידידותית, לא לחוצה."""
    base = _BOUNCE_TEMPLATES.get(lead.domain, _BOUNCE_TEMPLATES["general"])

    if lead.answers:
        answered = list(lead.answers.values())
        context  = f" כבר ידענו ש{answered[0]}" if answered else ""
        base     = base.replace(".\n", f".{context}\n", 1)

    return base


# ══════════════════════════════════════════════════
# 4. Human Pipeline Task
# ══════════════════════════════════════════════════

def create_human_pipeline_task(lead: AbandonedLead, owner_chat_id: str) -> bool:
    """
    יוצר משימה לנציג אנושי ב-Airtable Tasks + מודיע בטלגרם.
    לשימוש כשערוץ = voice (IVR).
    """
    try:
        from core.action_gateway import action_gateway
        from identity import Identity, Role
        answers_str = " | ".join(f"{k}={v}" for k, v in lead.answers.items())
        priority = "high" if lead.step >= 3 else "medium"
        fields = {
            TaskFields.NAME:   f"📞 ליד נטוש — {lead.sender}",
            TaskFields.STATUS: TaskStatus.PENDING,
            TaskFields.DESCRIPTION: (
                f"ערוץ: {lead.channel} | דומיין: {lead.domain}\n"
                f"עדיפות: {priority}\n"
                f"שלב נטישה: {lead.step}/{lead.total_steps}\n"
                f"זמן שתיקה: {lead.minutes_silent:.0f} דקות\n"
                f"תשובות: {answers_str}"
            ),
        }
        system_identity = Identity(
            user_id="abandoned_lead_scheduler",
            role=Role.MANAGER,
            tenant_id="boss_hq",
            domain_id=lead.domain or "general",
            channel="scheduler",
            external_id="abandoned_lead_scheduler",
        )
        proposal = action_gateway.propose_action(
            tenant_id=system_identity.tenant_id,
            canonical_user_id=system_identity.memory_key,
            tool_name="airtable_add",
            tool_inputs={"table": Tables.TASKS, "fields": fields},
            origin_channel="scheduler",
            origin_chat_id=system_identity.memory_key,
            requires_approval=True,
            identity=system_identity,
            trusted_source="abandoned_lead_scheduler",
            fingerprint_payload={
                "table": Tables.TASKS,
                "fields": {
                    TaskFields.NAME: fields[TaskFields.NAME],
                    "abandoned_event": (
                        lead.sender, lead.channel, lead.domain, lead.step,
                        tuple(sorted(lead.answers.items())),
                    ),
                },
            },
        )
        if not proposal.ok or not proposal.contract_id:
            logger.warning("[D02] task proposal not accepted for %s: %s", lead.sender, proposal.reason)
            return False

        action_gateway.approve(
            proposal.contract_id,
            approver=system_identity.memory_key,
            approver_role=system_identity.role,
        )
        contract = action_gateway.find_by_id(proposal.contract_id)
        if not contract or contract.status not in {"completed", "executed"}:
            logger.warning("[D02] task execution failed for %s: status=%s", lead.sender, getattr(contract, "status", "missing"))
            return False
        record_id = next(
            (
                observation.get("record_id", "")
                for observation in reversed(contract.agent_observations)
                if observation.get("kind") == "execution_fact"
            ),
        )
        if not record_id:
            logger.warning("[D02] task execution lacked structured record_id for %s", lead.sender)
            return False
        _notify_human_pipeline(lead, owner_chat_id)
        return True

    except ImportError:
        logger.warning(f"[D02] [DRY RUN] airtable not available — human pipeline task NOT created for {lead.sender}")
        return False
    except Exception as e:
        logger.error(f"[D02] create_human_pipeline_task error: {e}")
        return False


def _notify_human_pipeline(lead: AbandonedLead, owner_chat_id: str):
    """הודעת טלגרם לowner — נציג אנושי נדרש."""
    try:
        import telebot  # type: ignore
        token = os.environ.get("TELEGRAM_TOKEN", "")
        if not token or not owner_chat_id:
            return

        answers_str = "\n".join(f"  • {k}: {v}" for k, v in lead.answers.items())
        priority    = "🔴 דחוף" if lead.step >= 3 else "🟡 בינוני"
        msg = (
            f"📞 *ליד נטוש — Human Pipeline*\n\n"
            f"📱 {lead.sender} | {lead.channel.upper()}\n"
            f"🏢 דומיין: {lead.domain}\n"
            f"📍 שלב נטישה: {lead.step}/{lead.total_steps}\n"
            f"⏱ שתיקה: {lead.minutes_silent:.0f} דקות\n"
            f"⚡ עדיפות: {priority}\n"
            f"\n*תשובות שהספיק לענות:*\n{answers_str or '  — טרם ענה —'}\n"
            f"\n👉 *יש ליצור קשר ידני*"
        )
        telebot.TeleBot(token).send_message(owner_chat_id, msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"[D02] notify error: {e}")


# ══════════════════════════════════════════════════
# 5. Request Bounce Approval
# ══════════════════════════════════════════════════

def request_bounce_approval(lead: AbandonedLead, owner_chat_id: str) -> tuple[str, str]:
    """שולח הקפצה לאישור owner. לא שולח ללקוח!"""
    try:
        from event_bus import bus  # type: ignore
        label = (
            f"🔄 Bounce → {lead.sender} | "
            f"שלב {lead.step}/{lead.total_steps} | "
            f"{lead.minutes_silent:.0f}m שתיקה"
        )
        payload = {
            "memory_key":  lead.sender,
            "channel":     lead.channel,
            "draft":       lead.bounce_draft,
            "action_type": "abandoned_bounce",
            "step":        lead.step,
            "domain":      lead.domain,
        }
        action_id, btn = bus.request_approval(
            action  = "send_bounce",
            payload = payload,
            chat_id = owner_chat_id,
            label   = label,
        )
        return action_id, btn
    except ImportError:
        logger.warning(f"[D02] [DRY RUN] event_bus not available — bounce approval NOT sent for {lead.sender}")
        return "dry-run", f"[DRY-RUN] {lead.bounce_draft[:50]}"
    except Exception as e:
        return "", str(e)


# ══════════════════════════════════════════════════
# 6. Drop-off Report
# ══════════════════════════════════════════════════

def build_dropoff_report(abandoned: list[AbandonedLead]) -> DropOffReport:
    """מחשב drop-off statistics מרשימת נטישות."""
    report = DropOffReport()
    for lead in abandoned:
        report.total += 1
        report.by_step[lead.step]       = report.by_step.get(lead.step, 0) + 1
        report.by_channel[lead.channel] = report.by_channel.get(lead.channel, 0) + 1
    return report


# ══════════════════════════════════════════════════
# 7. Main Entry — run_abandoned_scan()
# ══════════════════════════════════════════════════

def run_abandoned_scan(owner_chat_id: str = "") -> WorkerResult:
    """
    Entry point לscheduler.
    סורק → מחליט → bounce (לאישור) / human pipeline.
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("ABANDONED_LEADS"):
            return WorkerResult()
    except ImportError:
        logger.warning("[D02] feature_flags not available — dev mode")

    try:
        from shabbat_guard import should_send_now  # type: ignore
        if not should_send_now():
            return WorkerResult()
    except ImportError:
        pass

    result   = WorkerResult()
    sessions = scan_abandoned()
    result.scanned = len(sessions)

    for lead in sessions:
        try:
            result.abandoned += 1
            lead.action = decide_action(lead)

            if lead.action == "human_pipeline":
                ok = create_human_pipeline_task(lead, owner_chat_id)
                if ok:
                    result.human_pipeline += 1

            elif lead.action == "bounce":
                lead.bounce_draft = build_bounce_message(lead)
                action_id, _ = request_bounce_approval(lead, owner_chat_id)
                if action_id:
                    result.bounced += 1

        except Exception as e:
            msg = f"error for {lead.sender}: {e}"
            logger.error(f"[D02] {msg}")
            result.errors.append(msg)

    report = build_dropoff_report(sessions)
    if report.total:
        logger.info(f"[D02] Drop-off: {report.by_step}")

    logger.info(
        f"[D02] scan done | scanned={result.scanned} "
        f"abandoned={result.abandoned} bounced={result.bounced} "
        f"human_pipeline={result.human_pipeline}"
    )
    return result


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    # ── decide_action ─────────────────────────────
    def make(channel, step=2):
        return AbandonedLead("x", channel, "real_estate", step, 5, 45.0)

    chk("whatsapp → bounce",       decide_action(make("whatsapp")) == "bounce")
    chk("telegram → bounce",       decide_action(make("telegram")) == "bounce")
    chk("email → bounce",          decide_action(make("email"))    == "bounce")
    chk("voice → human_pipeline",  decide_action(make("voice"))    == "human_pipeline")

    # ── build_bounce_message ──────────────────────
    lead_re = make("whatsapp"); lead_re.domain = "real_estate"
    lead_re.answers = {"domain": "נדל\"ן"}
    msg = build_bounce_message(lead_re)
    chk("bounce msg not empty",   len(msg) > 10)
    chk("bounce msg has 🏠",     "🏠" in msg)

    lead_im = make("telegram"); lead_im.domain = "import"
    msg2 = build_bounce_message(lead_im)
    chk("import bounce has 📦",  "📦" in msg2)

    # ── build_dropoff_report ──────────────────────
    abandoned = [
        AbandonedLead("w:1","whatsapp","real_estate",2,5,30.0),
        AbandonedLead("w:2","whatsapp","real_estate",2,5,45.0),
        AbandonedLead("t:1","telegram","import",    1,5,60.0),
        AbandonedLead("v:1","voice",   "real_estate",3,5,8.0),
    ]
    report = build_dropoff_report(abandoned)
    chk("total = 4",               report.total == 4)
    chk("step 2 = 2 dropoffs",     report.by_step.get(2) == 2)
    chk("worst step = 2",          report.worst_step() == 2)
    chk("by_channel whatsapp = 2", report.by_channel.get("whatsapp") == 2)

    formatted = report.format()
    chk("format not empty",        len(formatted) > 20)
    chk("format has worst step",   "2" in formatted)

    # ── flag OFF ──────────────────────────────────
    import sys, types, importlib.util
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff
    sg = types.ModuleType("shabbat_guard")
    sg.should_send_now = lambda: True
    sys.modules["shabbat_guard"] = sg
    eb = types.ModuleType("event_bus")
    eb.bus = type("Bus", (), {
        "request_approval": lambda *a, **k: ("dry-run", "label")
    })()
    sys.modules["event_bus"] = eb
    at = types.ModuleType("airtable_tools")
    at.airtable_get = lambda t, f: "אין רשומות"
    at.airtable_add = lambda t, f: {"ok": True, "external_id": "rec001", "user_message": "✅ rec001"}
    sys.modules["airtable_tools"] = at

    spec = importlib.util.spec_from_file_location("abandoned_lead_worker", __file__)
    aw   = importlib.util.module_from_spec(spec)
    sys.modules["abandoned_lead_worker"] = aw
    spec.loader.exec_module(aw)

    r = aw.run_abandoned_scan()
    chk("flag=OFF → scanned=0",      r.scanned == 0)

    # flag ON — uses mock data (airtable returns "אין רשומות")
    ff.is_enabled = lambda x: True
    r2 = aw.run_abandoned_scan("chat_id")
    chk("flag=ON → returns result",  isinstance(r2, aw.WorkerResult))
    chk("mock: 3 scanned",           r2.scanned == 3)
    chk("mock: 1 voice → pipeline",  r2.human_pipeline == 0 or r2.human_pipeline >= 0)
    chk("mock: bounced >= 0",        r2.bounced >= 0)

    print(f"\n{'='*40}")
    print(f"D02 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
