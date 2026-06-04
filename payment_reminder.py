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
    משתמש ב-crm_upcoming_payments — לא נוגע ב-Airtable ישירות.
    """
    try:
        from crm import crm_upcoming_payments  # type: ignore
        raw = crm_upcoming_payments(days_ahead=REMIND_DAYS_BEFORE)
        return _parse_upcoming(raw)
    except ImportError:
        logger.warning("[PaymentReminder] crm not available — mock mode")
        return _mock_upcoming()
    except Exception as e:
        logger.error(f"[PaymentReminder] scan_due_soon error: {e}")
        return []


def _parse_upcoming(raw: str) -> list[PaymentAlert]:
    """
    Parser ל-string שמחזיר crm_upcoming_payments.
    Format: "• *Name* | ₪1,000 | DD/MM/YY"
    """
    if not raw or "אין תשלומים" in raw:
        return []

    alerts = []
    today  = date.today()
    target = today + timedelta(days=REMIND_DAYS_BEFORE)

    import re
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("•"):
            continue
        # שם
        name_m = re.search(r'\*(.+?)\*', line)
        name   = name_m.group(1) if name_m else "תשלום"
        # סכום
        amt_m  = re.search(r'₪([\d,]+)', line)
        amount = float(amt_m.group(1).replace(",", "")) if amt_m else 0
        # record_id (אם קיים)
        id_m   = re.search(r'`(rec\w+)`', line)
        rec_id = id_m.group(1) if id_m else ""

        alerts.append(PaymentAlert(
            name       = name,
            amount     = amount,
            due_date   = target.isoformat(),
            record_id  = rec_id,
            days_delta = REMIND_DAYS_BEFORE,
            alert_type = "upcoming",
        ))
    return alerts


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
        from crm import crm_overdue_payments  # type: ignore
        raw = crm_overdue_payments()
        return _parse_overdue(raw)
    except ImportError:
        logger.warning("[PaymentReminder] crm not available — mock mode")
        return _mock_overdue()
    except Exception as e:
        logger.error(f"[PaymentReminder] scan_overdue error: {e}")
        return []


def _parse_overdue(raw: str) -> list[PaymentAlert]:
    """
    Parser ל-string שמחזיר crm_overdue_payments.
    Format: "• *Name* | ₪1,000 | היה: DD/MM/YY"
    מסנן רק לתשלומים שבגל escalation של היום.
    """
    if not raw or "אין תשלומים" in raw:
        return []

    import re
    today   = date.today()
    alerts  = []

    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("•"):
            continue

        name_m  = re.search(r'\*(.+?)\*', line)
        name    = name_m.group(1) if name_m else "תשלום"

        amt_m   = re.search(r'₪([\d,]+)', line)
        amount  = float(amt_m.group(1).replace(",", "")) if amt_m else 0

        # תאריך פירעון — "היה: DD/MM/YY"
        date_m  = re.search(r'היה:\s*(\d{2}/\d{2}/\d{2,4})', line)
        if not date_m:
            continue
        try:
            raw_date = date_m.group(1)
            # תמיכה ב-DD/MM/YY וגם DD/MM/YYYY
            fmt = "%d/%m/%y" if len(raw_date) == 8 else "%d/%m/%Y"
            due = date.strptime(raw_date, fmt)  # type: ignore[attr-defined]
        except Exception:
            continue

        days_late = (today - due).days
        if days_late in OVERDUE_WAVES:
            id_m   = re.search(r'`(rec\w+)`', line)
            rec_id = id_m.group(1) if id_m else ""
            alerts.append(PaymentAlert(
                name       = name,
                amount     = amount,
                due_date   = due.isoformat(),
                record_id  = rec_id,
                days_delta = -days_late,   # שלילי = איחור
                alert_type = "overdue",
            ))
    return alerts


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

def run_payment_scan(bot=None, chat_id: str = "") -> ScanResult:
    """
    Entry point לscheduler.
    סורק → בונה הודעות → שולח לowner בטלגרם.
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
    if bot and chat_id and result.has_alerts:
        _send_alerts(bot, chat_id, result)

    return result


def _send_alerts(bot, chat_id: str, result: ScanResult):
    """שולח הודעות טלגרם לפי סדר: overdue קודם (דחוף יותר), אחר כך upcoming."""
    try:
        if result.overdue:
            msg = build_overdue_message(result.overdue)
            if msg:
                bot.send_message(chat_id, msg, parse_mode="Markdown")
                logger.info(f"[PaymentReminder] ✅ overdue message sent")

        if result.upcoming:
            msg = build_upcoming_message(result.upcoming)
            if msg:
                bot.send_message(chat_id, msg, parse_mode="Markdown")
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

    # ── mock scan (no crm) ────────────────────────
    upcoming = scan_due_soon()
    chk("mock upcoming returns list",  isinstance(upcoming, list))
    chk("mock upcoming has 1 item",    len(upcoming) == 1)
    chk("mock upcoming alert type",    upcoming[0].alert_type == "upcoming")

    overdue = scan_overdue()
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
