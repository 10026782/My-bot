# startup_validator.py — Startup Env Validation
# קובץ: startup_validator.py (flat, root)
# נקרא: app.py → לפני כל דבר אחר
#
# עקרון: Fail Fast.
# מוטב שהבוט לא יעלה בכלל מאשר יעלה ויפול בשיחה הראשונה.
#
# שכבות:
#   CRITICAL  — חסר = הבוט לא עולה בכלל (SystemExit)
#   WARNING   — חסר = פיצ'ר מסוים לא יעבוד (log בלבד)
#   INFO      — מוצג ב-startup log לנוחות

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Validation Rules
# ══════════════════════════════════════════════════

@dataclass
class EnvVar:
    name:        str
    level:       str          # "critical" / "warning" / "info"
    description: str
    validator:   str = "non_empty"   # "non_empty" / "url" / "starts_with"
    starts_with: str = ""            # לvalidator "starts_with"
    feature:     str = ""            # איזה פיצ'ר תלוי בזה


_RULES: list[EnvVar] = [

    # ── CRITICAL — הבוט לא עולה בלעדיהם ──────────
    # הערה: בדיקת פורמט (starts_with) היא WARNING בלבד — CRITICAL = קיים בלבד
    EnvVar("ANTHROPIC_API_KEY",   "critical", "Claude AI API key"),
    EnvVar("TELEGRAM_TOKEN",      "critical", "Telegram Bot token"),
    EnvVar("AIRTABLE_API_KEY",    "critical", "Airtable Personal Access Token"),
    EnvVar("AIRTABLE_BASE_ID",    "critical", "Airtable Base ID"),

    # ── WARNING — פיצ'ר ספציפי לא יעבוד ──────────
    EnvVar("DIGEST_CHAT_ID",      "warning",  "Daily Digest Telegram chat ID",
           feature="daily_digest"),
    EnvVar("OWNER_TELEGRAM_ID",   "warning",  "Owner Telegram user ID for approval callbacks",
           feature="approval_callbacks"),
    EnvVar("IDENTITY_MAP",          "warning",  "JSON map of authorized users",
           feature="identity"),
    EnvVar("ELIYAHU_CHAT_ID",      "warning",  "Telegram chat ID of owner — required for identity resolution",
           feature="identity"),
    EnvVar("OWNER_PHONES",         "warning",  "Owner WhatsApp phone number(s) — required for WhatsApp identity",
           feature="identity"),
    EnvVar("GOOGLE_CLIENT_ID",     "warning",  "Google OAuth client ID — required for Drive/Calendar/Gmail",
           feature="google_tools"),
    EnvVar("GOOGLE_CLIENT_SECRET", "warning",  "Google OAuth client secret",
           feature="google_tools"),
    EnvVar("GOOGLE_REFRESH_TOKEN", "warning",  "Google OAuth refresh token",
           feature="google_tools"),
    EnvVar("RENDER_APP_URL",       "warning",  "Public URL for Telegram/Twilio webhooks",
           validator="url", feature="webhooks"),
    EnvVar("WORKER_SECRET",        "warning",  "Secret for /worker endpoint — missing means scheduler jobs run unauthenticated",
           feature="scheduler"),
    EnvVar("OWNER_USER_ID_MAPPINGS", "warning", "JSON map of WhatsApp/email/voice destination → owner user_id — missing means non-interactive canonical Lead writers (N18) stay fail-closed",
           feature="canonical_lead_writers"),

    # ── INFO — אופציונלי, מוצג בlog ───────────────
    EnvVar("TWILIO_ACCOUNT_SID",  "info", "Twilio for WhatsApp/Voice",
           feature="voice_ivr"),
    EnvVar("TWILIO_AUTH_TOKEN",   "info", "Twilio auth",
           feature="voice_ivr"),
    EnvVar("DIGEST_TIME",         "info", "Daily digest send time (default 07:30)",
           feature="daily_digest"),
    EnvVar("SHABBAT_CITY",        "info", "City for Shabbat times (default tel_aviv)",
           feature="shabbat_guard"),
]


# ══════════════════════════════════════════════════
# Validators
# ══════════════════════════════════════════════════

@dataclass
class ValidationResult:
    ok:       bool
    level:    str
    name:     str
    message:  str
    feature:  str = ""


def _validate_var(rule: EnvVar) -> ValidationResult:
    value = os.environ.get(rule.name, "")

    # חסר לחלוטין
    if not value:
        return ValidationResult(
            ok      = False,
            level   = rule.level,
            name    = rule.name,
            message = f"חסר לחלוטין — {rule.description}",
            feature = rule.feature,
        )

    # בדיקת prefix
    if rule.validator == "starts_with" and rule.starts_with:
        if not value.startswith(rule.starts_with):
            return ValidationResult(
                ok      = False,
                level   = rule.level,
                name    = rule.name,
                message = f"פורמט שגוי — חייב להתחיל ב-'{rule.starts_with}' (קיבלנו: {value[:8]}...)",
                feature = rule.feature,
            )

    # בדיקת URL
    if rule.validator == "url":
        if not (value.startswith("http://") or value.startswith("https://")):
            return ValidationResult(
                ok      = False,
                level   = rule.level,
                name    = rule.name,
                message = f"לא URL תקין — {value[:30]}",
                feature = rule.feature,
            )

    return ValidationResult(
        ok      = True,
        level   = rule.level,
        name    = rule.name,
        message = f"✅ {value[:6]}{'*' * min(len(value)-6, 10) if len(value) > 6 else ''}",
        feature = rule.feature,
    )


# ══════════════════════════════════════════════════
# Main Validator
# ══════════════════════════════════════════════════

def validate_startup(raise_on_critical: bool = True) -> list[ValidationResult]:
    """
    Entry point — נקרא מapp.py בעלייה.
    אם raise_on_critical=True (ברירת מחדל): SystemExit על CRITICAL חסר.
    מחזיר list[ValidationResult] לכל הבדיקות.
    """
    results   = [_validate_var(r) for r in _RULES]
    criticals = [r for r in results if not r.ok and r.level == "critical"]
    warnings  = [r for r in results if not r.ok and r.level == "warning"]
    oks       = [r for r in results if r.ok]

    # ── Log ──────────────────────────────────────
    logger.info("=" * 50)
    logger.info("🚀 BOSS Bot — Startup Validation")
    logger.info("=" * 50)

    for r in results:
        if r.ok:
            logger.info(f"  ✅ {r.name:<30} {r.message}")
        elif r.level == "critical":
            logger.critical(f"  ❌ CRITICAL: {r.name:<25} {r.message}")
        elif r.level == "warning":
            logger.warning(f"  ⚠️  WARNING:  {r.name:<25} {r.message}"
                           + (f" [{r.feature}]" if r.feature else ""))
        else:
            logger.info(f"  ℹ️  INFO:     {r.name:<25} {r.message}")

    logger.info("-" * 50)
    logger.info(
        f"  ✅ {len(oks)} OK | "
        f"⚠️  {len(warnings)} WARNING | "
        f"❌ {len(criticals)} CRITICAL"
    )
    logger.info("=" * 50)

    # ── Fail Fast on Critical ─────────────────────
    if criticals and raise_on_critical:
        msg = "\n".join(
            f"  ❌ {r.name}: {r.message}" for r in criticals
        )
        logger.critical(
            f"\n{'='*50}\n"
            f"BOSS Bot לא יכול לעלות — חסרים env vars קריטיים:\n"
            f"{msg}\n"
            f"הוסף אותם ב-Render → Environment Variables\n"
            f"{'='*50}"
        )
        sys.exit(1)

    return results


def get_summary() -> dict:
    """
    מחזיר dict מסוכם — לbrandpoint בtelegram אחרי startup.
    """
    results   = [_validate_var(r) for r in _RULES]
    criticals = [r for r in results if not r.ok and r.level == "critical"]
    warnings  = [r for r in results if not r.ok and r.level == "warning"]

    return {
        "ok":        not criticals,
        "criticals": [r.name for r in criticals],
        "warnings":  [r.name for r in warnings],
        "total":     len(results),
        "passed":    len([r for r in results if r.ok]),
    }


def format_startup_message() -> str:
    """
    הודעת Telegram לowner אחרי startup.
    מראה מה עובד ומה לא.
    """
    summary = get_summary()

    if not summary["ok"]:
        return (
            "❌ *BOSS Bot — startup נכשל!*\n"
            f"חסרים: {', '.join(summary['criticals'])}\n"
            "הוסף ב-Render → Environment Variables."
        )

    lines = ["✅ *BOSS Bot עלה בהצלחה!*\n"]

    if summary["warnings"]:
        lines.append("⚠️ *פיצ'רים לא פעילים (חסרים vars):*")
        # קבץ לפי feature
        results = [_validate_var(r) for r in _RULES if not _validate_var(r).ok and _validate_var(r).level == "warning"]
        by_feature: dict[str, list[str]] = {}
        for r in results:
            feat = r.feature or "other"
            by_feature.setdefault(feat, []).append(r.name)
        for feat, names in by_feature.items():
            lines.append(f"  • {feat}: {', '.join(names)}")
        lines.append("")

    lines.append(f"🟢 {summary['passed']}/{summary['total']} env vars תקינים")
    return "\n".join(lines)


# ══════════════════════════════════════════════════
# app.py integration patch
# ══════════════════════════════════════════════════

APP_PATCH = '''
# app.py — הוסף בראש הקובץ, לפני כל import אחר:

import logging
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)

from startup_validator import validate_startup, format_startup_message
validate_startup()   # ← Fail Fast — SystemExit אם חסר CRITICAL

# ...שאר ה-imports...

# אחרי יצירת bot:
# @bot.message_handler(commands=["status"])
# def cmd_status(msg):
#     bot.send_message(msg.chat.id, format_startup_message(), parse_mode="Markdown")
'''


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    # save env
    saved = {r.name: os.environ.get(r.name) for r in _RULES}

    def clear(*names):
        for n in names:
            os.environ.pop(n, None)

    def setv(name, val):
        os.environ[name] = val

    try:
        # ── non_empty OK ──────────────────────────
        setv("DIGEST_CHAT_ID", "123456789")
        r = _validate_var(next(r for r in _RULES if r.name == "DIGEST_CHAT_ID"))
        chk("DIGEST_CHAT_ID set → ok",        r.ok is True)

        clear("DIGEST_CHAT_ID")
        r2 = _validate_var(next(r for r in _RULES if r.name == "DIGEST_CHAT_ID"))
        chk("DIGEST_CHAT_ID missing → not ok", r2.ok is False)
        chk("DIGEST_CHAT_ID level=warning",     r2.level == "warning")

        # ── starts_with validator ─────────────────
        setv("ANTHROPIC_API_KEY", "sk-ant-api03-abc123")
        r3 = _validate_var(next(r for r in _RULES if r.name == "ANTHROPIC_API_KEY"))
        chk("valid ANTHROPIC_API_KEY → ok",     r3.ok is True)

        setv("ANTHROPIC_API_KEY", "wrong-key")
        r4 = _validate_var(next(r for r in _RULES if r.name == "ANTHROPIC_API_KEY"))
        chk("wrong prefix → not ok",            r4.ok is False)
        chk("wrong prefix → critical",          r4.level == "critical")

        clear("ANTHROPIC_API_KEY")
        r5 = _validate_var(next(r for r in _RULES if r.name == "ANTHROPIC_API_KEY"))
        chk("missing ANTHROPIC → critical",     r5.level == "critical")

        # ── URL validator ─────────────────────────
        setv("RENDER_APP_URL", "https://boss.onrender.com")
        r6 = _validate_var(next(r for r in _RULES if r.name == "RENDER_APP_URL"))
        chk("valid URL → ok",                   r6.ok is True)

        setv("RENDER_APP_URL", "not-a-url")
        r7 = _validate_var(next(r for r in _RULES if r.name == "RENDER_APP_URL"))
        chk("invalid URL → not ok",             r7.ok is False)

        # ── Airtable prefix ───────────────────────
        setv("AIRTABLE_API_KEY", "patXXXXXXXXXXXXXX")
        r8 = _validate_var(next(r for r in _RULES if r.name == "AIRTABLE_API_KEY"))
        chk("Airtable key pat... → ok",         r8.ok is True)

        setv("AIRTABLE_BASE_ID", "appABC123")
        r9 = _validate_var(next(r for r in _RULES if r.name == "AIRTABLE_BASE_ID"))
        chk("Airtable base app... → ok",        r9.ok is True)

        # ── validate_startup — no raise ───────────
        # Set minimal env
        setv("ANTHROPIC_API_KEY", "sk-ant-test")
        setv("TELEGRAM_TOKEN",    "1234567890:ABC-test")
        setv("AIRTABLE_API_KEY",  "patTestKey")
        setv("AIRTABLE_BASE_ID",  "appTestBase")

        results = validate_startup(raise_on_critical=False)
        chk("validate_startup returns list",    isinstance(results, list))
        chk("has all rules",                    len(results) == len(_RULES))

        # ── get_summary ───────────────────────────
        summary = get_summary()
        chk("summary has ok",                   "ok" in summary)
        chk("summary has warnings",             "warnings" in summary)
        chk("summary ok=True (criticals set)",  summary["ok"] is True)

        # ── format_startup_message ────────────────
        msg = format_startup_message()
        chk("startup message not empty",        len(msg) > 10)
        chk("startup message has ✅",           "✅" in msg)

        # ── fail fast test ────────────────────────
        clear("ANTHROPIC_API_KEY")
        try:
            validate_startup(raise_on_critical=True)
            chk("SystemExit on missing critical", False)   # should not reach
        except SystemExit:
            chk("SystemExit raised correctly",   True)

    finally:
        # restore env
        for name, val in saved.items():
            if val is not None:
                os.environ[name] = val
            else:
                os.environ.pop(name, None)

    print(f"\n{'='*40}")
    print(f"StartupValidator Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ok = _run_tests()
    exit(0 if ok else 1)
