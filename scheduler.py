# scheduler.py — v3.4
# משימות רקע: דוח בוקר + מאסף יומי + ניקוי + תשלומים + תזכורת אבטחה

import os
import json
import logging
import threading
import schedule
import time
from datetime import date

logger = logging.getLogger(__name__)

# נכתב ע"י record_security_review() אחרי review מוצלח, נקרא ב-_get_last_review_date().
# בלי זה, התאריך תלוי לחלוטין בעדכון ידני של LAST_SECURITY_REVIEW ב-Render — שלא קרה בפועל
# (BUG-016: התזכורת הציגה 999 ימים תמיד כי אף קוד לא כתב תאריך).
_REVIEW_PERSIST_PATH = "/tmp/security_review.json"


def _job_cleanup_pending():
    try:
        from event_bus import pending
        pending.cleanup()
    except Exception as e:
        logger.error(f"cleanup_pending error: {e}")


def _job_external_execution_poll():
    """Bounded, lease-owned polling; provider adapters never own persistence."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("EXTERNAL_EXECUTION_ENABLED"):
            return
        from core.external_execution_boundary import get_default_boundary
        get_default_boundary().poll_due()
    except Exception as e:
        logger.error(f"external_execution_poll error: {e}")


def _job_daily_digest():
    logger.info("[Scheduler] job=daily_digest start")
    try:
        from daily_digest import send_daily_digest
        import telebot
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("[Scheduler] job=daily_digest skip — DIGEST_CHAT_ID לא מוגדר")
            return
        bot = telebot.TeleBot(token)
        send_daily_digest(bot=bot, chat_id=chat_id)
        logger.info(f"[Scheduler] job=daily_digest done — ✅ נשלח ל-{chat_id}")
    except ImportError:
        logger.info("[Scheduler] job=daily_digest skip — daily_digest לא קיים")
    except Exception as e:
        logger.error(f"[Scheduler] job=daily_digest error: {e}")


def _job_schema_snapshot_archive():
    """Feature flag: FEATURE_AIRTABLE_SCHEMA_SNAPSHOT (default off, PR3A).
    No scheduled job may modify git files — this only writes to Airtable."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("FEATURE_AIRTABLE_SCHEMA_SNAPSHOT"):
            return
        from tools.schema_snapshot import run_snapshot_archive
        result = run_snapshot_archive()
        if not result.get("ok"):
            logger.warning(f"[Scheduler] job=schema_snapshot_archive not ok: {result}")
    except ImportError:
        logger.info("tools.schema_snapshot לא קיים — דולג")
    except Exception as e:
        logger.error(f"[Scheduler] job=schema_snapshot_archive error: {e}")


def _job_overdue_payments():
    try:
        from crm import crm_overdue_payments
        result = crm_overdue_payments()
        if "🚨" in result:
            logger.info(f"Overdue payments: {result[:100]}")
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"overdue_payments error: {e}")


def _job_daily_collector():
    logger.info("[Scheduler] job=daily_collector start")
    try:
        from daily_collector import send_daily_collector
        import telebot
        token     = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id   = os.environ.get("DIGEST_CHAT_ID", "")
        owner_key = os.environ.get("OWNER_MEMORY_KEY", "boss_hq:eliyahu")
        if not token or not chat_id:
            logger.warning("[Scheduler] job=daily_collector skip — DIGEST_CHAT_ID לא מוגדר")
            return
        bot = telebot.TeleBot(token)
        send_daily_collector(bot=bot, chat_id=chat_id, memory_key=owner_key)
        logger.info("[Scheduler] job=daily_collector done")
    except ImportError:
        logger.info("[Scheduler] job=daily_collector skip — daily_collector לא קיים")
    except Exception as e:
        logger.error(f"[Scheduler] job=daily_collector error: {e}")


# ══════════════════════════════════════════════════
# N02 — Followup Scan
# ══════════════════════════════════════════════════

def _job_followup_scan():
    try:
        from feature_flags import is_enabled
        if is_enabled("EMERGENCY_STOP_AUTOMATION"):
            logger.warning("[Scheduler] EMERGENCY_STOP_AUTOMATION active — followup_scan skipped")
            return
        if not is_enabled("FOLLOWUP_AUTOMATION"):
            return

        from followup_engine import run_followup_scan
        owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        result = run_followup_scan(owner_chat_id=owner_chat_id)

        if result.candidates:
            logger.info(
                f"[Followup] scanned={result.scanned} "
                f"candidates={len(result.candidates)} queued={result.approved}"
            )
        for err in result.errors:
            logger.error(f"[Followup] {err}")

    except ImportError as e:
        logger.warning(f"[Followup] not available: {e}")
    except Exception as e:
        logger.error(f"[Followup] job error: {e}")


# ══════════════════════════════════════════════════
# N04 — Payment Reminders
# ══════════════════════════════════════════════════

def _job_payment_reminders():
    try:
        from feature_flags import is_enabled
        if is_enabled("EMERGENCY_STOP_AUTOMATION"):
            logger.warning("[Scheduler] EMERGENCY_STOP_AUTOMATION active — payment_reminders skipped")
            return
        if not is_enabled("PAYMENT_REMINDERS"):
            return

        from payment_reminder import run_payment_scan
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("[PaymentReminder] TELEGRAM_TOKEN / DIGEST_CHAT_ID חסרים")
            return

        result = run_payment_scan(chat_id=chat_id)

        if result.has_alerts:
            logger.info(
                f"[PaymentReminder] done | "
                f"upcoming={len(result.upcoming)} overdue={len(result.overdue)}"
            )
        for err in result.errors:
            logger.error(f"[PaymentReminder] {err}")

    except ImportError as e:
        logger.warning(f"[PaymentReminder] not available: {e}")
    except Exception as e:
        logger.error(f"[PaymentReminder] job error: {e}")


# ══════════════════════════════════════════════════
# F01 — Lead Recovery
# ══════════════════════════════════════════════════

def _job_lead_recovery():
    try:
        from feature_flags import is_enabled
        if not is_enabled("LEAD_RECOVERY"):
            return

        from core.lead_recovery import run_recovery_scan
        owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        result = run_recovery_scan(owner_chat_id=owner_chat_id)

        if result.candidates:
            logger.info(
                f"[Recovery] scanned={result.scanned} "
                f"candidates={len(result.candidates)} queued={result.queued}"
            )
        for err in result.errors:
            logger.error(f"[Recovery] {err}")

    except ImportError as e:
        logger.warning(f"[Recovery] not available: {e}")
    except Exception as e:
        logger.error(f"[Recovery] job error: {e}")


# ══════════════════════════════════════════════════
# F02 — Learning Cycle
# ══════════════════════════════════════════════════

def _job_learning_cycle():
    try:
        from feature_flags import is_enabled
        if not is_enabled("LEARNING_ENGINE"):
            return

        from core.learning_engine import run_learning_cycle, get_domain_insights
        import telebot

        result = run_learning_cycle(["real_estate", "import"])
        logger.info(f"[Learning] cycle done: {list(result.keys())}")

        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if token and chat_id and result:
            bot     = telebot.TeleBot(token)
            summary = get_domain_insights()
            if summary:
                bot.send_message(chat_id, summary, parse_mode="Markdown")
                logger.info("[Learning] ✅ Insights sent to owner")

    except ImportError as e:
        logger.warning(f"[Learning] not available: {e}")
    except Exception as e:
        logger.error(f"[Learning] job error: {e}")


# ══════════════════════════════════════════════════
# Security Review Reminder
# ══════════════════════════════════════════════════

def record_security_review(d: date | None = None) -> None:
    """כותב תאריך review מוצלח לקובץ persistent. קרא לפונקציה הזו אחרי כל review."""
    d = d or date.today()
    try:
        with open(_REVIEW_PERSIST_PATH, "w") as f:
            json.dump({"last_review": d.isoformat()}, f)
        logger.warning(f"[SecurityReview] last_review_date נכתב: {d.isoformat()}")
    except Exception as e:
        logger.error(f"[SecurityReview] כתיבת {_REVIEW_PERSIST_PATH} נכשלה: {e}")


def _get_last_review_date() -> date | None:
    """קורא תאריך review אחרון: קודם מהקובץ ה-persistent, אחרת מ-env var (תאימות לאחור)."""
    try:
        with open(_REVIEW_PERSIST_PATH) as f:
            raw = json.load(f).get("last_review", "")
        if raw:
            return date.fromisoformat(raw)
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"[SecurityReview] קריאת {_REVIEW_PERSIST_PATH} נכשלה: {e}")

    raw = os.environ.get("LAST_SECURITY_REVIEW", "")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _days_since_review() -> int:
    last = _get_last_review_date()
    if not last:
        return 999
    return (date.today() - last).days


def _build_security_reminder(days: int) -> str:
    """בונה הודעת תזכורת לפי כמה ימים עברו."""
    if days >= 90:
        urgency = "🔴 *review מלא נדרש*"
        detail  = "עברו 3 חודשים. זמן לסריקה מקיפה של כל שכבות האבטחה."
    elif days >= 28:
        urgency = "🟠 *סריקה מהירה — 4 שבועות*"
        detail  = "grep על dispatcher / crm / identity. 15 דקות מספיקות."
    else:
        return ""

    last_str = _get_last_review_date()
    last_str = last_str.strftime("%d/%m/%Y") if last_str else "לא ידוע"

    return (
        f"🔐 *תזכורת אבטחה — Boss Bot*\n\n"
        f"{urgency}\n"
        f"Review אחרון: {last_str} ({days} ימים)\n\n"
        f"{detail}\n\n"
        f"*צ'קליסט מהיר:*\n"
        f"• dispatch_tool מקבל identity בכל קריאה?\n"
        f"• כלים חדשים עברו דרך registry?\n"
        f"• endpoint חדש — יש auth?\n"
        f"• crm._get מסנן לפי tenant?\n\n"
        f"לאחר הבדיקה: `python3 -c \"from scheduler import record_security_review; record_security_review()\"`"
    )


def _job_security_reminder():
    """
    רץ פעם בשבוע (ראשון בבוקר).
    שולח תזכורת רק אם עברו 28+ ימים מהreview האחרון.
    """
    try:
        days = _days_since_review()
        msg  = _build_security_reminder(days)
        if not msg:
            logger.info(f"Security reminder: {days} ימים — עדיין מוקדם")
            return

        import telebot
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("Security reminder: DIGEST_CHAT_ID לא מוגדר")
            return

        bot = telebot.TeleBot(token)
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        logger.info(f"✅ Security reminder נשלח ({days} ימים מהreview)")

    except Exception as e:
        logger.error(f"security_reminder error: {e}")


def _job_weekly_summary():
    """כל ראשון 08:30 — סיכום Business Memory שבועי."""
    try:
        import telebot
        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("[C22] DIGEST_CHAT_ID לא מוגדר — weekly summary דולג")
            return
        from weekly_summary import send_weekly_summary
        bot = telebot.TeleBot(token)
        send_weekly_summary(bot=bot, chat_id=chat_id)
    except ImportError:
        logger.info("[C22] weekly_summary לא קיים — דולג")
    except Exception as e:
        logger.error(f"[C22] weekly_summary error: {e}")


# ══════════════════════════════════════════════════
# F06 — Email Inbound
# ══════════════════════════════════════════════════

def _job_email_inbound():
    try:
        from feature_flags import is_enabled
        if not is_enabled("EMAIL_INBOUND"):
            return

        from email_inbound import run_email_poll
        owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        result = run_email_poll(owner_chat_id=owner_chat_id)

        if result.routed:
            logger.info(
                f"[Email] scanned={result.scanned} "
                f"routed={result.routed} skipped={result.skipped}"
            )
        for err in result.errors:
            logger.error(f"[Email] {err}")

    except ImportError as e:
        logger.warning(f"[Email] not available: {e}")
    except Exception as e:
        logger.error(f"[Email] job error: {e}")


# ══════════════════════════════════════════════════
# D05 — Ad Attribution Report
# ══════════════════════════════════════════════════

def _job_attribution_report():
    """D05: Attribution Report שבועי — כל ראשון."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("AD_ATTRIBUTION"):
            return
        from ad_attribution import run_attribution_report
        run_attribution_report(os.environ.get("DIGEST_CHAT_ID", ""))
    except ImportError as e:
        logger.warning(f"[Attribution] not available: {e}")
    except Exception as e:
        logger.error(f"[Attribution] {e}")


# ══════════════════════════════════════════════════
# D02 — Abandoned Lead Scan
# ══════════════════════════════════════════════════

def _job_abandoned_scan():
    """D02: סריקת לידים נטושים כל 15 דקות."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("ABANDONED_LEADS"):
            return
        from abandoned_lead_worker import run_abandoned_scan
        owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        result = run_abandoned_scan(owner_chat_id)
        if result.abandoned:
            logger.info(
                f"[D02] abandoned={result.abandoned} "
                f"bounced={result.bounced} pipeline={result.human_pipeline}"
            )
    except ImportError as e:
        logger.warning(f"[D02] not available: {e}")
    except Exception as e:
        logger.error(f"[D02] {e}")


# ══════════════════════════════════════════════════
# D04 — Audience Intelligence
# ══════════════════════════════════════════════════

def _job_audience_report():
    """D04: דוח audience שבועי — כל ראשון."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("AUDIENCE_INTELLIGENCE"):
            return
        from audience_intelligence import run_audience_scan
        result = run_audience_scan(os.environ.get("DIGEST_CHAT_ID", ""))
        if result.total:
            logger.info(f"[Audience] total={result.total} segments={len(result.segments)}")
    except ImportError as e:
        logger.warning(f"[Audience] not available: {e}")
    except Exception as e:
        logger.error(f"[Audience] {e}")


# ══════════════════════════════════════════════════
# D06 — Interaction Intelligence
# ══════════════════════════════════════════════════

def _job_interaction_scan():
    """D06: ניתוח פגישות + זיכרון עסקי — כל 15 דקות.
    TODO: כשמפעילים INTERACTION_INTELLIGENCE=true בפרודקשן — שקול להגדיל ל-30 דק' (INTERACTION_INTERVAL_MIN) לחסוך 50% Google Calendar API calls."""
    try:
        if os.getenv("INTERACTION_INTELLIGENCE", "false").lower() != "true":
            logger.info("[D06] interaction intelligence disabled by env")
            return
        from interaction_engine import run_interaction_scan, send_upcoming_reminders
        owner_chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        send_upcoming_reminders(owner_chat_id)
        result = run_interaction_scan(owner_chat_id=owner_chat_id)
        if result.processed:
            logger.info(
                f"[D06] processed={len(result.processed)} "
                f"skipped={result.skipped} errors={len(result.errors)}"
            )
        for err in result.errors:
            logger.error(f"[D06] {err}")
    except ImportError as e:
        logger.warning(f"[D06] not available: {e}")
    except Exception as e:
        logger.error(f"[D06] {e}")


# ══════════════════════════════════════════════════
# GAME — daily digest / weekly reset / boss battle
# Feature flag: GAME_SCHEDULER (default off)
# ══════════════════════════════════════════════════

def _game_bot_send(token: str, chat_id: str, text: str) -> None:
    import telebot
    telebot.TeleBot(token).send_message(chat_id, text, parse_mode="Markdown")


_HE_DAY = ["ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳", "א׳"]  # Mon=0 … Sun=6


def _job_daily_game_digest():
    """Game: כל יום 07:00 — פורמט מלא: World progress + Quest log ממוספר + ספירה לBoss Battle."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("GAME_SCHEDULER"):
            return

        from datetime import date, timedelta
        from tma_api import _at_list
        from airtable_schema import (
            Tables, QuestsFields, CoinsLogFields, WorldsFields, WorldStatus, QuestStatus,
        )

        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("[Game] DIGEST_CHAT_ID חסר")
            return

        today    = date.today()
        week_str = (today - timedelta(days=today.weekday())).isoformat()

        # ── Active World ──────────────────────────────────────────────
        worlds = _at_list(Tables.WORLDS, f"{{{WorldsFields.STATUS}}}='{WorldStatus.ACTIVE}'", max_records=1)
        world_section = ""
        if worlds:
            wf     = worlds[0].get("fields", {})
            target = int(wf.get(WorldsFields.TOTAL_COINS_TARGET, 0) or 0)
            earned = int(wf.get(WorldsFields.COINS_EARNED, 0) or 0)
            pct    = round(100 * earned / target) if target > 0 else 0
            filled = round(pct / 10)
            bar    = "█" * filled + "░" * (10 - filled)
            world_section = (
                f"\n🌍 *World {wf.get(WorldsFields.NUMBER, '')} — {wf.get(WorldsFields.NAME, '')}*\n"
                f"`{bar}` {pct}% | {earned}🪙 מתוך {target}"
            )

        # ── This week's quests ────────────────────────────────────────
        all_quests  = _at_list(Tables.QUESTS, "", max_records=200)
        week_quests = [
            r for r in all_quests
            if (r.get("fields", {}).get(QuestsFields.WEEK_START, "") or "")[:10] == week_str
        ] or [
            r for r in all_quests
            if r.get("fields", {}).get(QuestsFields.STATUS, "") != QuestStatus.SKIPPED
        ]

        quest_lines = []
        for i, r in enumerate(week_quests, start=1):
            qf     = r.get("fields", {})
            status = qf.get(QuestsFields.STATUS, "")
            coins  = int(qf.get(QuestsFields.COINS, 0) or 0)
            name   = qf.get(QuestsFields.NAME, "?")
            if status == QuestStatus.DONE:
                quest_lines.append(f"{i}\\. ☑ {name} \\[{coins}🪙\\] ✅")
            elif status == QuestStatus.IN_PROGRESS:
                quest_lines.append(f"{i}\\. 🔄 {name} \\[{coins}🪙\\]")
            elif status == QuestStatus.SKIPPED:
                quest_lines.append(f"{i}\\. ⏭️ {name} \\[{coins}🪙\\]")
            else:
                quest_lines.append(f"{i}\\. ☐ {name} \\[{coins}🪙\\]")

        # ── Total coins ───────────────────────────────────────────────
        log_recs    = _at_list(Tables.COINS_LOG, "", max_records=500)
        total_coins = sum(int(r.get("fields", {}).get(CoinsLogFields.COINS, 0) or 0) for r in log_recs)

        # ── Days until Friday ─────────────────────────────────────────
        days_to_friday = (4 - today.weekday()) % 7
        if days_to_friday == 0:
            battle_line = "⏰ *Boss Battle: היום\\! ⚔️*"
        elif days_to_friday == 1:
            battle_line = "⏰ Boss Battle: מחר — 1 יום"
        else:
            battle_line = f"⏰ Boss Battle: יום שישי — {days_to_friday} ימים"

        # ── Build message ─────────────────────────────────────────────
        day_label = f"יום {_HE_DAY[today.weekday()]} {today.day}\\.{today.month}"
        open_count = sum(
            1 for r in week_quests
            if r.get("fields", {}).get(QuestsFields.STATUS, "") not in {QuestStatus.DONE, QuestStatus.SKIPPED}
        )
        lines = [
            f"🎮 *BOSS Daily Quest — {day_label}*",
            world_section,
            "",
            f"📋 *Quest Log היום:*",
            *quest_lines,
            "",
            battle_line,
            f"💰 סה\"כ מטבעות: {total_coins}🪙",
        ]
        if open_count:
            lines.append(f"\nלסמן Quest כהושלם: /done \\[מספר\\]")

        _game_bot_send(token, chat_id, "\n".join(lines))
        logger.info(f"[Game] daily digest sent | total={total_coins}🪙 open={open_count}")

    except ImportError as e:
        logger.warning(f"[Game] not available: {e}")
    except Exception as e:
        logger.error(f"[Game] daily_digest error: {e}")


def _job_weekly_quest_reset():
    """Game: כל ראשון 08:00 — סוגר שבוע שעבר, מגלגל Quests לשבוע הבא."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("GAME_SCHEDULER"):
            return

        from datetime import date, timedelta
        from tma_api import _at_list, _at_patch
        from airtable_schema import Tables, QuestsFields, CoinsLogFields, QuestStatus

        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("[Game] DIGEST_CHAT_ID חסר")
            return

        today       = date.today()                              # Sunday
        last_monday = (today - timedelta(days=6)).isoformat()  # Mon of ending week
        next_monday = (today + timedelta(days=1)).isoformat()  # Mon of new week

        all_quests       = _at_list(Tables.QUESTS, "", max_records=200)
        last_week_quests = [
            r for r in all_quests
            if (r.get("fields", {}).get(QuestsFields.WEEK_START, "") or "")[:10] == last_monday
        ]

        done_count   = 0
        rolled_count = 0
        coins_earned = 0

        for r in last_week_quests:
            qf     = r.get("fields", {})
            status = qf.get(QuestsFields.STATUS, "")
            coins  = int(qf.get(QuestsFields.COINS, 0) or 0)
            if status == QuestStatus.DONE:
                done_count   += 1
                coins_earned += coins
            else:
                # Roll unfinished quest forward to next Monday, reset to Todo
                _at_patch(Tables.QUESTS, r["id"], {
                    QuestsFields.STATUS:     QuestStatus.TODO,
                    QuestsFields.WEEK_START: next_monday,
                })
                rolled_count += 1

        # Total coins
        log_recs    = _at_list(Tables.COINS_LOG, "", max_records=500)
        total_coins = sum(int(r.get("fields", {}).get(CoinsLogFields.COINS, 0) or 0) for r in log_recs)

        # New week's open quests (freshly rolled + pre-scheduled)
        new_all    = _at_list(Tables.QUESTS, "", max_records=200)
        new_open   = [
            r for r in new_all
            if (r.get("fields", {}).get(QuestsFields.WEEK_START, "") or "")[:10] == next_monday
            and r.get("fields", {}).get(QuestsFields.STATUS, "") != QuestStatus.DONE
        ]

        lines = [
            f"📊 *Weekly Reset — שבוע {last_monday}*\n",
            f"✅ הושלם: {done_count} Quests  |  {coins_earned}🪙",
            f"🔄 הועבר לשבוע הבא: {rolled_count} Quests",
            f"🪙 סה\"כ כל הזמנים: {total_coins}\n",
            f"📋 *שבוע {next_monday} — {len(new_open)} Quests פתוחים:*",
        ]
        for r in new_open:
            qf = r.get("fields", {})
            lines.append(f"⬜ {qf.get(QuestsFields.NAME, '?')} — {int(qf.get(QuestsFields.COINS, 0) or 0)}🪙")

        _game_bot_send(token, chat_id, "\n".join(lines))
        logger.info(f"[Game] weekly reset | done={done_count} rolled={rolled_count} next_week={len(new_open)}")

    except ImportError as e:
        logger.warning(f"[Game] not available: {e}")
    except Exception as e:
        logger.error(f"[Game] weekly_reset error: {e}")


def _job_boss_battle_check():
    """Game: כל שישי 18:00 — האם Boss נוצח השבוע?"""
    try:
        from feature_flags import is_enabled
        if not is_enabled("GAME_SCHEDULER"):
            return

        from datetime import date, timedelta
        from tma_api import _at_list
        from airtable_schema import (
            Tables, QuestsFields, CoinsLogFields, WorldsFields, WorldStatus, QuestStatus,
        )

        token   = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("DIGEST_CHAT_ID", "")
        if not token or not chat_id:
            logger.warning("[Game] DIGEST_CHAT_ID חסר")
            return

        today    = date.today()
        week_str = (today - timedelta(days=today.weekday())).isoformat()

        all_quests  = _at_list(Tables.QUESTS, "", max_records=200)
        week_quests = [
            r for r in all_quests
            if (r.get("fields", {}).get(QuestsFields.WEEK_START, "") or "")[:10] == week_str
        ] or [
            r for r in all_quests
            if r.get("fields", {}).get(QuestsFields.STATUS, "") != QuestStatus.SKIPPED
        ]

        done_quests  = [r for r in week_quests if r.get("fields", {}).get(QuestsFields.STATUS, "") == QuestStatus.DONE]
        open_quests  = [r for r in week_quests if r.get("fields", {}).get(QuestsFields.STATUS, "") in {QuestStatus.TODO, QuestStatus.IN_PROGRESS}]
        coins_week   = sum(int(r.get("fields", {}).get(QuestsFields.COINS, 0) or 0) for r in done_quests)

        log_recs    = _at_list(Tables.COINS_LOG, "", max_records=500)
        total_coins = sum(int(r.get("fields", {}).get(CoinsLogFields.COINS, 0) or 0) for r in log_recs)

        worlds = _at_list(Tables.WORLDS, f"{{{WorldsFields.STATUS}}}='{WorldStatus.ACTIVE}'", max_records=1)
        world_section = ""
        if worlds:
            wf     = worlds[0].get("fields", {})
            target = int(wf.get(WorldsFields.TOTAL_COINS_TARGET, 0) or 0)
            earned = int(wf.get(WorldsFields.COINS_EARNED, 0) or 0)
            pct    = round(100 * earned / target, 1) if target > 0 else 0.0
            filled = int(pct / 10)
            bar    = "█" * filled + "░" * (10 - filled)
            world_section = (
                f"\n\n🌍 *{wf.get(WorldsFields.NAME, 'World')}*\n"
                f"`{bar}` {pct}%\n"
                f"{earned}/{target}🪙  |  פרס: {wf.get(WorldsFields.PRIZE, '?')}"
            )

        if not open_quests and week_quests:
            prize  = worlds[0].get("fields", {}).get(WorldsFields.PRIZE, "?") if worlds else "?"
            header = f"🏆 *Boss Defeated!*\nפרס: {prize}\n\n"
            body   = f"כל {len(week_quests)} Quests הושלמו 🎯\n+{coins_week}🪙 השבוע  |  סה\"כ: {total_coins}🪙"
        else:
            header = f"⚠️ *Boss לא מנוצח — מה נשאר:*\n\n"
            remaining = "\n".join(
                f"• {r.get('fields', {}).get(QuestsFields.NAME, '?')} — {int(r.get('fields', {}).get(QuestsFields.COINS, 0) or 0)}🪙"
                for r in open_quests
            )
            body = f"{remaining}\n\n✅ הושלם: {len(done_quests)}/{len(week_quests)}  |  +{coins_week}🪙 השבוע"

        _game_bot_send(token, chat_id, f"{header}{body}{world_section}")
        logger.info(f"[Game] boss_battle | defeated={not open_quests} done={len(done_quests)}/{len(week_quests)}")

    except ImportError as e:
        logger.warning(f"[Game] not available: {e}")
    except Exception as e:
        logger.error(f"[Game] boss_battle error: {e}")


def _job_cost_watchdog():
    """CORE_05 legacy: כל 60 דקות — בודק עלות שעתית/יומית בדולרים, שולח התראה/עצירת חירום."""
    try:
        from cost_monitor import job_cost_watchdog
        job_cost_watchdog()
    except Exception as e:
        logger.error(f"cost_watchdog error: {e}")


def _job_memory_shadow_scan():
    """Episodic Memory Phase 2B follow-up: low-frequency, owner-scoped
    comparison of the legacy memory-assembly paths vs. the new Phase 2
    retrieval contract, durably recorded as structured counts (never memory
    content) so a later Phase 3/cutover decision has owner-scoped scheduled
    comparison evidence — one sample/day for the single owner identity, not
    a broad or tenant-wide dataset; read that way before drawing conclusions
    from it. Flag-gated (FEATURE_MEMORY_SHADOW_LOGGING, default off); zero
    prompt or context impact — see core/memory_retrieval_shadow.py."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("FEATURE_MEMORY_SHADOW_LOGGING"):
            return
        from identity import resolve_identity
        from core.memory_retrieval_shadow import (
            build_shadow_request, compare_with_live_paths, record_shadow_comparison,
        )
        owner_chat = os.environ.get("ELIYAHU_CHAT_ID", "").strip()
        if not owner_chat:
            logger.warning("[Scheduler] job=memory_shadow_scan skip — ELIYAHU_CHAT_ID not configured")
            return
        identity = resolve_identity("telegram", owner_chat)
        request = build_shadow_request(identity)
        if request is None:
            logger.warning("[Scheduler] job=memory_shadow_scan skip — owner identity has no provable tenant/user id")
            return
        comparison = compare_with_live_paths(request, memory_key=identity.memory_key)
        record_shadow_comparison(comparison)
    except Exception as e:
        logger.error(f"memory_shadow_scan error: {e}")


def _job_daily_usage_report():
    """CORE_05 v2: כל יום 08:00 — מסכם usage.jsonl, בודק ספי Sonnet, כותב ל-AI_Usage_Daily."""
    try:
        from core.cost_watchdog import daily_watchdog
        daily_watchdog()
    except Exception as e:
        logger.error(f"daily_usage_report error: {e}")


# ══════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════

def _run_scheduler():
    logger.info("🕐 Scheduler thread started")
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error(f"Scheduler run error: {e}")
        time.sleep(30)


def _automation_guard(func, *, name: str | None = None):
    """
    Wrapper for scheduled jobs to centrally enforce the EMERGENCY_STOP_AUTOMATION
    flag.
    """
    def wrapper(*args, **kwargs):
        try:
            from feature_flags import is_enabled
            flag = is_enabled("EMERGENCY_STOP_AUTOMATION")
        except Exception as e:
            logger.error(f"[Scheduler] failed to read EMERGENCY_STOP_AUTOMATION: {e}")
            flag = True

        job_name = name or getattr(func, "__name__", str(func))
        if flag:
            logger.warning(f"[Scheduler] EMERGENCY_STOP_AUTOMATION active — {job_name} skipped")
            return None
        return func(*args, **kwargs)

    return wrapper


def start_scheduler() -> threading.Thread:
    # Guard: if jobs are already registered the module was imported twice.
    # Return the existing scheduler thread rather than doubling all jobs.
    if schedule.jobs:
        logger.info("[Scheduler] Already running — skipping init")
        for t in threading.enumerate():
            if t.name == "scheduler":
                return t
        # Thread not found but jobs exist — create a placeholder
        return threading.Thread(name="scheduler-placeholder", daemon=True)

    from lead_memory import job_flush_lead_memory
    from shabbat_guard import shabbat_safe
    digest_time           = os.environ.get("DIGEST_TIME",               "07:30")
    collector_time        = os.environ.get("COLLECTOR_TIME",            "23:00")
    cleanup_interval      = int(os.environ.get("CLEANUP_INTERVAL_MIN",  "360"))
    followup_interval     = int(os.environ.get("FOLLOWUP_INTERVAL_MIN", "60"))
    payment_reminder_time = os.environ.get("PAYMENT_REMINDER_TIME",    "09:00")
    recovery_time         = os.environ.get("RECOVERY_TIME",            "10:00")
    learning_day          = os.environ.get("LEARNING_DAY",             "sunday")
    learning_time         = os.environ.get("LEARNING_TIME",            "06:00")
    email_interval        = int(os.environ.get("EMAIL_POLL_INTERVAL_MIN", "15"))
    security_day          = os.environ.get("SECURITY_REMINDER_DAY",    "sunday")
    security_time         = os.environ.get("SECURITY_REMINDER_TIME",   "09:00")
    abandoned_interval    = int(os.environ.get("ABANDONED_INTERVAL_MIN", "45"))
    weekly_summary_day    = os.environ.get("WEEKLY_SUMMARY_DAY",       "sunday")
    weekly_summary_time   = os.environ.get("WEEKLY_SUMMARY_TIME",      "08:30")

    # Use automation guard wrapper for jobs that should be paused by EMERGENCY_STOP_AUTOMATION.
    # BUG-067 (BUG-DAILY-02): daily_digest/daily_collector previously ran on Shabbat/holidays —
    # daily_digest.py only shows a "Shabbat Mode" text banner, it never actually gates sending.
    # Wrapped in shabbat_safe(), same pattern already used for 6 other jobs below.
    schedule.every().day.at(digest_time).do(shabbat_safe(_automation_guard(_job_daily_digest, name="daily_digest")))
    schedule.every().day.at("03:30").do(_automation_guard(_job_schema_snapshot_archive, name="schema_snapshot_archive"))  # PR3A — flag: FEATURE_AIRTABLE_SCHEMA_SNAPSHOT
    schedule.every().day.at(collector_time).do(shabbat_safe(_automation_guard(_job_daily_collector, name="daily_collector")))
    schedule.every(cleanup_interval).minutes.do(_automation_guard(_job_cleanup_pending, name="cleanup_pending"))
    schedule.every(2).minutes.do(_automation_guard(_job_external_execution_poll, name="external_execution_poll"))
    schedule.every().day.at("00:05").do(_automation_guard(_job_overdue_payments, name="overdue_payments"))
    schedule.every(10).minutes.do(_automation_guard(job_flush_lead_memory, name="flush_lead_memory"))                                          # N01
    schedule.every(followup_interval).minutes.do(shabbat_safe(_automation_guard(_job_followup_scan, name="followup_scan")))               # N02
    schedule.every().day.at(payment_reminder_time).do(shabbat_safe(_automation_guard(_job_payment_reminders, name="payment_reminders")))      # N04
    schedule.every().day.at(recovery_time).do(shabbat_safe(_automation_guard(_job_lead_recovery, name="lead_recovery")))                  # F01
    getattr(schedule.every(), learning_day).at(learning_time).do(_automation_guard(_job_learning_cycle, name="learning_cycle"))            # F02
    schedule.every(email_interval).minutes.do(_automation_guard(_job_email_inbound, name="email_inbound"))
    schedule.every(abandoned_interval).minutes.do(shabbat_safe(_automation_guard(_job_abandoned_scan, name="abandoned_scan")))             # D02
    getattr(schedule.every(), "sunday").at("08:00").do(shabbat_safe(_automation_guard(_job_audience_report, name="audience_report")))       # D04
    getattr(schedule.every(), "sunday").at("08:30").do(_automation_guard(_job_attribution_report, name="attribution_report"))                  # D05
    schedule.every(15).minutes.do(shabbat_safe(_automation_guard(_job_interaction_scan, name="interaction_scan")))                           # D06
    getattr(schedule.every(), security_day).at(security_time).do(_automation_guard(_job_security_reminder, name="security_reminder"))
    getattr(schedule.every(), weekly_summary_day).at(weekly_summary_time).do(_automation_guard(_job_weekly_summary, name="weekly_summary"))  # C22
    schedule.every().day.at("07:00").do(_automation_guard(_job_daily_game_digest, name="daily_game_digest"))                            # Game digest (flag: GAME_SCHEDULER)
    getattr(schedule.every(), "sunday").at("08:00").do(_automation_guard(_job_weekly_quest_reset, name="weekly_quest_reset"))            # Game weekly reset
    getattr(schedule.every(), "friday").at("18:00").do(_automation_guard(_job_boss_battle_check, name="boss_battle_check"))             # Boss battle check
    schedule.every(60).minutes.do(_automation_guard(_job_cost_watchdog, name="cost_watchdog"))                                       # CORE_05 legacy: dollar-based emergency stop
    schedule.every().day.at("08:15").do(_automation_guard(_job_daily_usage_report, name="daily_usage_report"))                             # CORE_05 v2: count-based JSONL watchdog (08:15 — מניעת cluster עם D04+Game ב-Sunday 08:00)
    schedule.every().day.at("04:00").do(_automation_guard(_job_memory_shadow_scan, name="memory_shadow_scan"))                              # Episodic Memory Phase 2B follow-up: flag FEATURE_MEMORY_SHADOW_LOGGING (default off)

    logger.info(
        f"📅 Scheduler | digest={digest_time} | collector={collector_time} | "
        f"cleanup=every {cleanup_interval}min | followup=every {followup_interval}min | "
        f"payment={payment_reminder_time} | recovery={recovery_time} | "
        f"learning={learning_day} {learning_time} | "
        f"email=every {email_interval}min | "
        f"abandoned=every {abandoned_interval}min | "
        f"security={security_day} {security_time} | "
        f"weekly-summary=every {weekly_summary_day} {weekly_summary_time}"
    )

    t = threading.Thread(target=_run_scheduler, daemon=True, name="scheduler")
    t.start()
    return t
