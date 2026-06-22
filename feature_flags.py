import os
import json
import logging

"""
══════════════════════════════════════════════════════════════════════
FEATURE FLAGS REGISTRY — מקור אמת יחיד
כל flag שנבדק בקוד חייב להופיע כאן. ברירת מחדל = כבוי אלא אם צוין אחרת.
══════════════════════════════════════════════════════════════════════

EMERGENCY (persistent — שורדים restart, נשמרים ב-/tmp/emergency_flags.json):
  EMERGENCY_STOP_ALL          - חוסם כל ביצוע tool מסוכן
  EMERGENCY_STOP_WHATSAPP     - חוסם שליחה יוצאת WhatsApp
  EMERGENCY_STOP_EMAIL        - חוסם שליחה יוצאת email
  EMERGENCY_STOP_AUTOMATION   - חוסם jobs אוטומטיים של scheduler
  EMERGENCY_STOP_AI           - חוסם קריאות Claude API (Cost Watchdog)

LEAD PIPELINE:
  LEAD_CAPTURE                - WhatsApp מספר לא מוכר → רשומת Leads
  LEAD_SCORING                - score+tier נכתב בעת יצירת lead
  LEAD_MEMORY                 - lead_memory.update() מחובר ל-lead_capture
  FOLLOWUP_AUTOMATION         - scheduler סורק לידים HOT, מעלה לאישור
  LEAD_QUALIFIER              - מנוע שאלון lead_qualifier (F09, לא פעיל)
  LEAD_RECOVERY               - זיהוי לידים דועכים + שליחה מחדש
  ABANDONED_LEADS             - מעקב לידים שנטשו

INFRA / DATA:
  KNOWLEDGE_ENGINE            - בניית context דינמי (Supabase-backed)
  SUPABASE                    - מאפשר קריאה/כתיבה ל-Supabase
  COST_WATCHDOG_LIVE          - לוג שימוש + daily Sonnet limit (CORE_05)
  IMPORT_DOMAIN               - ברירת מחדל ON; פיצ'רים יבוא/עץ
  MULTITENANT                 - מצב multi-tenant (כבוי, F08)

INTEGRATIONS:
  VOICE_IVR                   - קו טלפוני Twilio IVR (F07)
  EMAIL_INBOUND               - ערוץ email נכנס (F06)
  CREATIVE_GENERATOR          - יצירת תוכן שיווקי אוטומטי
  AD_ATTRIBUTION              - ייחוס UTM מפרסום → ליד
  CONTACT_RESOLVER            - פתרון אנשי קשר אוטומטי
  LLM_FALLBACK                - fallback ל-OpenAI כש-Anthropic מחזיר שגיאה/timeout (ברירת מחדל: כבוי)
  FEATURE_BUSINESS_UPDATE     - /update command (Business Memory log); default OFF
  FEATURE_WEEKLY_SUMMARY      - Weekly Business Memory digest (C22, scheduler.py); default OFF
  FEATURE_VOICE_NOTES         - Telegram voice note -> STT -> Drive + Media Files (F16); default OFF
  FEATURE_MEDIA_UPLOAD        - Telegram/TMA photo/document -> Drive + Media Files (F16); default OFF

APPROVAL POLICY:
  EMERGENCY_WINDOW             - מאפשר הפעלת חריג זמני ל-High מהטלפון (core/emergency_window.py, כבוי כברירת מחדל)

OUTPUT GATEWAY (C52):
  FINANCIAL_COMMITMENT_GATE   - core/financial_gate.py escalation על הודעות עם התחייבות פיננסית
                                 false (default) → shadow mode (log בלי לעצור)
                                 true            → production escalation (ESCALATE, לא BLOCK)

GAME / SCHEDULER:
  GAME_SCHEDULER              - scheduler jobs של מערכת הגיימיפיקציה
  PAYMENT_REMINDERS           - תזכורות תשלום אוטומטיות
  GIT_AUDIT_SCHEDULER         - הרצה יומית אוטומטית של daily_git_audit.py; default OFF (נשאר manual-only)

FUTURE (לא פעיל):
  AUDIENCE_INTELLIGENCE       - ניתוח קהל יעד (Future)
  INTERACTION_INTELLIGENCE    - ניתוח דפוסי שיחה (Future)
  KPI_ENGINE                  - מנוע KPI (F04)
  LEARNING_ENGINE             - מנוע למידה מדפוסים (F02)
  REVENUE_ATTRIBUTION         - ייחוס הכנסות (F03)
══════════════════════════════════════════════════════════════════════
"""

logger = logging.getLogger(__name__)

# Flags that must survive a restart (e.g. EMERGENCY_STOP_ALL).
# Written to /tmp/emergency_flags.json on set, restored on import.
_PERSISTENT_FLAG_NAMES = frozenset({
    "EMERGENCY_STOP_ALL",
    "EMERGENCY_STOP_WHATSAPP",
    "EMERGENCY_STOP_EMAIL",
    "EMERGENCY_STOP_AUTOMATION",
    "EMERGENCY_STOP_AI",          # CORE_05: Cost Watchdog — חוסם קריאות Claude API
})
_PERSIST_PATH = "/tmp/emergency_flags.json"

# Runtime overrides — in-memory, checked first.
_RUNTIME: dict[str, bool] = {}

# Flags that default to ON when the env var is unset (unlike the standard
# default-OFF behavior). Each entry mirrors os.environ.get(NAME, default).
_DEFAULTS: dict[str, str] = {
    "IMPORT_DOMAIN": os.environ.get("IMPORT_DOMAIN", "true"),
}


def _load_persistent() -> None:
    """Restore persistent flags from disk on startup."""
    try:
        with open(_PERSIST_PATH) as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, bool):
                    _RUNTIME[k] = v
            if data:
                logger.warning(f"[FeatureFlags] restored {len(data)} persistent flags: {list(data)}")
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"[FeatureFlags] failed to load {_PERSIST_PATH}: {e}")


def _save_persistent() -> None:
    """Write all active persistent flags to disk."""
    try:
        data = {k: v for k, v in _RUNTIME.items() if k in _PERSISTENT_FLAG_NAMES}
        with open(_PERSIST_PATH, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"[FeatureFlags] failed to save {_PERSIST_PATH}: {e}")


def is_enabled(name: str) -> bool:
    if name in _RUNTIME:
        return _RUNTIME[name]
    value = os.environ.get(name, _DEFAULTS.get(name, "")).strip().lower()
    return value in ("1", "true", "yes", "on", "enabled")


def set_flag(name: str, value: bool) -> None:
    """Set a runtime feature flag. Persistent flags are written to disk."""
    _RUNTIME[name] = value
    if name in _PERSISTENT_FLAG_NAMES:
        _save_persistent()
        logger.warning(f"[FeatureFlags] persistent flag {name}={value} saved to disk")


# Restore on import so flags survive Render restarts.
_load_persistent()

ERROR_REPORTING = os.environ.get("ERROR_REPORTING", "true")
