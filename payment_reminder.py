# payment_reminder.py — N04 Payment Reminder
# flag: PAYMENT_REMINDERS (כבוי ברירת מחדל)
#
# מה זה עושה:
#   scan_due_soon()   — תשלומים בעוד בדיוק 3 ימים → שולח התראה לowner
#   scan_overdue()    — תשלומים שעברו → 3 גלי escalation (1/3/7 ימים איחור)
#   run_payment_scan()— entry point לscheduler (רץ פעם ביום)
#
# כלל ברזל:
#   - Rule-based בלבד. ללא AI, ללא דינמיות.
#   - "טיפש אבל צפוי" — cash collection automation.
#   - לא שולח ללקוח. שולח לowner בטלגרם בלבד.
#   - crm.py = מקור האמת. לא נוגע ב-Airtable ישירות.

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# Escalation Config — "טיפש אבל צפוי"
# ══════════════════════════════════════════════════

# תזכורת מראש: כמה ימים לפני תאריך תשלום
REMIND_DAYS_BEFORE = 3

# גלי escalation באיחור (ימים אחרי due_date)
OVERDUE_WAVES = [1, 3, 7]

# סמלי urgency לפי ימי איחור
def _overdue_emoji(days_late: int) -> str:
    if days_late >= 7:
        return "🔴"
    if days_late >= 3:
        return "🟠"
    return "🟡"


# ══════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════

@dataclass
class PaymentAlert:
    name:       str
    amount:     float
    due_date:   str   # ISO format YYYY-MM-DD
    record_id:  str   = ""
    days_delta: int   = 0   # שלילי = איחור, חיובי = ימים עד תשלום
    alert_type: str   = "upcoming"  # "upcoming" | "overdue"

    @property
    def amount_str(self) -> str:
        return f"₪{self.amount:,.0f}"

    @property
    def due_str(self) -> str:
        try:
            d = date.fromisoformat(self.due_date)
            return d.strftime("%d/%m/%Y")
        except Exception:
            return self.due_date


@dataclass
class ScanResult:
    upcoming:  list[PaymentAlert] = field(default_factory=list)
    overdue:   list[PaymentAlert] = field(default_factory=list)
    errors:    list[str]          = field(default_factory=list)

    @property
    def total_upcoming_amount(self) -> float:
        return sum(a.amount for a in self.upcoming)

    @property
    def total_overdue_amount(self) -> float:
        return sum(a.amount for a in self.overdue)

    @property
    def has_alerts(self) -> bool:
        return bool(self.upcoming or self.overdue)


# ══════════════════════════════════════════════════
# 1. Scan Upcoming (3 ימים מראש)
# ══════════════════════════════════════════════════

def scan_due_soon() -> list[PaymentAlert]:
    """
    מחזיר תשלומים שמועדם בעוד בדיוק REMIND_DAYS_BEFORE ימים.
    משתמש בתוצאת Payment typed — לא נוגע ב-Airtable ישירות.
    """
    try:
        from crm import crm_upcoming_payment_records  # type: ignore
        records = crm_upcoming_payment_records(days_ahead=REMIND_DAYS_BEFORE)
        today = date.today()
        return [PaymentAlert(
            name=record.name,
            amount=record.amount,
            due_date=record.due_date,
            record_id=record.record_id,
            days_delta=(date.fromisoformat(record.due_date) - today).days,
            alert_type="upcoming",
        ) for record in records]
    except ImportError:
        logger.warning("[PaymentReminder] crm not available — mock mode")
        return _mock_upcoming()
    except Exception as e:
        logger.error(f"[PaymentReminder] scan_due_soon error: {e}")
        return []


def _mock_upcoming() -> list[PaymentAlert]:
    target = date.today() + timedelta(days=REMIND_DAYS_BEFORE)
    return [
        PaymentAlert(
            name="דמי שכירות — הרצל 5", amount=8500,
            due_date=target.isoformat(), days_delta=3, alert_type="upcoming",
        ),
    ]


# ══════════════════════════════════════════════════
# 2. Scan Overdue (escalation)
# ══════════════════════════════════════════════════

def scan_overdue() -> list[PaymentAlert]:
    """
    מחזיר תשלומים שעברו מועדם ב-1, 3, או 7 ימים בדיוק.
    (לא כל האיחורים — רק "גלי" escalation — למנוע spam.)
    """
    try:
        from crm import crm_overdue_payment_records  # type: ignore
        records = crm_overdue_payment_records()
        today = date.today()
        alerts = []
        for record in records:
            days_late = (today - date.fromisoformat(record.due_date)).days
            if days_late in OVERDUE_WAVES:
                alerts.append(PaymentAlert(
                    name=record.name,
                    amount=record.amount,
                    due_date=record.due_date,
                    record_id=record.record_id,
                    days_delta=-days_late,
                    alert_type="overdue",
                ))
        return alerts
    except ImportError:
        logger.warning("[PaymentReminder] crm not available — mock mode")
        return _mock_overdue()
    except Exception as e:
        logger.error(f"[PaymentReminder] scan_overdue error: {e}")
        return []


def _mock_overdue() -> list[PaymentAlert]:
    today = date.today()
    return [
        PaymentAlert(
            name="תשלום ספק סין — Q2", amount=15000,
            due_date=(today - timedelta(days=3)).isoformat(),
            days_delta=-3, alert_type="overdue",
        ),
    ]


# ══════════════════════════════════════════════════
# 3. Build Telegram Messages
# ══════════════════════════════════════════════════

def build_upcoming_message(alerts: list[PaymentAlert]) -> str:
    """הודעת תזכורת מראש — עדינה, בטון informational."""
    if not alerts:
        return ""
    total = sum(a.amount for a in alerts)
    lines = [
        f"🔔 *תזכורת תשלום — {REMIND_DAYS_BEFORE} ימים*\n",
        f"יש *{len(alerts)}* תשלום{'ים' if len(alerts) > 1 else ''} קרוב{'ים' if len(alerts) > 1 else ''}:\n",
    ]
    for a in alerts:
        lines.append(f"• *{a.name}* | {a.amount_str} | {a.due_str}")
    lines.append(f"\n💰 *סה\"כ: ₪{total:,.0f}*")
    lines.append("\nוודא שיש כיסוי מספיק בחשבון.")
    return "\n".join(lines)


def build_overdue_message(alerts: list[PaymentAlert]) -> str:
    """הודעת איחור — escalation לפי ימים."""
    if not alerts:
        return ""
    lines = [f"⚠️ *תשלומים באיחור — {date.today().strftime('%d/%m/%Y')}*\n"]
    for a in alerts:
        days_late = abs(a.days_delta)
        emoji     = _overdue_emoji(days_late)
        escalation = {
            1: "יום אחד איחור — נא לטפל",
            3: "3 ימים איחור — פנייה נדרשת",
            7: "שבוע איחור — טיפול דחוף!",
        }.get(days_late, f"{days_late} ימים איחור")

        lines.append(
            f"{emoji} *{a.name}*\n"
            f"   {a.amount_str} | היה: {a.due_str}\n"
            f"   {escalation}"
        )
    total = sum(abs(a.amount) for a in alerts)
    lines.append(f"\n🚨 *סה\"כ חוב: ₪{total:,.0f}*")
    return "\n".join(lines)


# ══════════════════════════════════════════════════
# 4. Main Entry — run_payment_scan()
# ══════════════════════════════════════════════════

def run_payment_scan(chat_id: str = "") -> ScanResult:
    """
    Entry point לscheduler.
    סורק → בונה הודעות → שולח לowner בטלגרם (דרך C52 Customer Output Gateway).
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("PAYMENT_REMINDERS"):
            logger.info("[PaymentReminder] PAYMENT_REMINDERS flag is OFF — skipping")
            return ScanResult()
    except ImportError:
        logger.warning("[PaymentReminder] feature_flags not available — dev mode")

    result = ScanResult()

    # ── Upcoming ──────────────────────────────────
    try:
        result.upcoming = scan_due_soon()
        if result.upcoming:
            logger.info(f"[PaymentReminder] upcoming: {len(result.upcoming)} alerts, ₪{result.total_upcoming_amount:,.0f}")
    except Exception as e:
        msg = f"scan_due_soon error: {e}"
        logger.error(f"[PaymentReminder] {msg}")
        result.errors.append(msg)

    # ── Overdue ───────────────────────────────────
    try:
        result.overdue = scan_overdue()
        if result.overdue:
            logger.info(f"[PaymentReminder] overdue: {len(result.overdue)} alerts, ₪{result.total_overdue_amount:,.0f}")
    except Exception as e:
        msg = f"scan_overdue error: {e}"
        logger.error(f"[PaymentReminder] {msg}")
        result.errors.append(msg)

    # ── Send ──────────────────────────────────────
    if chat_id and result.has_alerts:
        _send_alerts(chat_id, result)

    return result


def _send_alerts(chat_id: str, result: ScanResult):
    """שולח הודעות לowner דרך C52 Customer Output Gateway, לפי סדר: overdue קודם (דחוף יותר), אחר כך upcoming."""
    from core.output_gateway import send_outbound, OutboundEnvelope, AudienceClass, OutputChannel

    def _send(body: str, ref: str):
        envelope = OutboundEnvelope(
            channel=OutputChannel.TELEGRAM_OWNER,
            recipient=chat_id,
            body=body,
            audience=AudienceClass.INTERNAL,
            source_module="payment_reminder",
            source_ref=ref,
            domain="finance",
        )
        send_outbound(envelope)

    try:
        if result.overdue:
            msg = build_overdue_message(result.overdue)
            if msg:
                _send(msg, "overdue")
                logger.info(f"[PaymentReminder] ✅ overdue message sent")

        if result.upcoming:
            msg = build_upcoming_message(result.upcoming)
            if msg:
                _send(msg, "upcoming")
                logger.info(f"[PaymentReminder] ✅ upcoming message sent")

    except Exception as e:
        logger.error(f"[PaymentReminder] send error: {e}")


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    from datetime import timedelta
    today = date.today()
    passed = failed = 0

    def chk(desc: str, cond: bool):
        nonlocal passed, failed
        if cond:
            print(f"✅ {desc}")
            passed += 1
        else:
            print(f"❌ {desc}")
            failed += 1

    # ── PaymentAlert helpers ───────────────────────
    a = PaymentAlert(
        name="בדיקה", amount=5000,
        due_date=(today + timedelta(days=3)).isoformat(),
        days_delta=3, alert_type="upcoming",
    )
    chk("amount_str format",   a.amount_str == "₪5,000")
    chk("due_str not empty",   len(a.due_str) > 0)

    # ── _overdue_emoji ─────────────────────────────
    chk("emoji 1d late = 🟡",  _overdue_emoji(1)  == "🟡")
    chk("emoji 3d late = 🟠",  _overdue_emoji(3)  == "🟠")
    chk("emoji 7d late = 🔴",  _overdue_emoji(7)  == "🔴")

    # ── build_upcoming_message ─────────────────────
    upcoming_alerts = [
        PaymentAlert("שכירות", 8500, (today + timedelta(days=3)).isoformat(), days_delta=3, alert_type="upcoming"),
        PaymentAlert("הלוואה", 3000, (today + timedelta(days=3)).isoformat(), days_delta=3, alert_type="upcoming"),
    ]
    msg = build_upcoming_message(upcoming_alerts)
    chk("upcoming message not empty",     len(msg) > 20)
    chk("upcoming message has total",     "11,500" in msg)
    chk("upcoming message has emoji 🔔",  "🔔" in msg)

    # ── build_overdue_message ──────────────────────
    overdue_alerts = [
        PaymentAlert("ספק סין", 15000, (today - timedelta(days=3)).isoformat(), days_delta=-3, alert_type="overdue"),
    ]
    msg2 = build_overdue_message(overdue_alerts)
    chk("overdue message not empty",    len(msg2) > 20)
    chk("overdue message has 🟠",       "🟠" in msg2)
    chk("overdue message has amount",   "15,000" in msg2)

    # ── build_upcoming_message empty ──────────────
    chk("empty upcoming → empty string", build_upcoming_message([]) == "")
    chk("empty overdue → empty string",  build_overdue_message([])  == "")

    # ── mock helpers (unit test — bypass live crm) ───
    upcoming = _mock_upcoming()
    chk("mock upcoming returns list",  isinstance(upcoming, list))
    chk("mock upcoming has 1 item",    len(upcoming) == 1)
    chk("mock upcoming alert type",    upcoming[0].alert_type == "upcoming")

    overdue = _mock_overdue()
    chk("mock overdue returns list",   isinstance(overdue, list))

    # ── ScanResult ────────────────────────────────
    sr = ScanResult(upcoming=upcoming_alerts, overdue=overdue_alerts)
    chk("has_alerts = True",             sr.has_alerts)
    chk("total_upcoming = 11500",        sr.total_upcoming_amount == 11500)
    chk("total_overdue = 15000",         sr.total_overdue_amount  == 15000)

    print(f"\n{'='*40}")
    print(f"N04 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
