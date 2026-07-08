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
  META_OUTBOUND_ENABLED       - Meta WhatsApp Cloud API (F05a): true מריץ run_agent על inbound; false (default) מדלג כל עוד outbound הוא stub

APPROVAL POLICY:
  EMERGENCY_WINDOW             - מאפשר הפעלת חריג זמני ל-High מהטלפון (core/emergency_window.py, כבוי כברירת מחדל)
  FEATURE_ACTION_GATEWAY       - ActionContract + Action Gateway (Stage B) — מרכז כל mutation תחת חוזה; default OFF

CAPTURE POLICY (C89):
  FEATURE_AUTO_CAPTURE         - Tiered auto-write via IngressClassification (Stage 3).
                                 OFF (default): everything shows preview before write.
                                 ON:  Tier 1 (single clear lead) and Tier 2 (clean batch) auto-write
                                      through Gateway without preview. Tier 3/4/5 always show preview.
                                 Branch: feature/capture-policy-stage-3
  FEATURE_RAW_CAPTURE          - C89 RAW-OBS: classify_ingress() persists the raw text to
                                 Tables.DECISION_INBOX (Decision Inbox) and stores the record id
                                 as IngressClassification.raw_ref. OFF (default): raw_ref still
                                 always populated (local fallback reference), no live Airtable
                                 write — classification behavior is unchanged either way.
  FEATURE_STRUCTURED_FILE_CAPTURE - C90: xlsx/csv uploaded to Telegram routes through
                                 classify_ingress(source_type="file") for a Tier-4-only preview
                                 reply, instead of the FEATURE_MEDIA_UPLOAD Drive/Media-Files
                                 path. No auto-write, no content parsing, no Airtable write.
                                 OFF (default): xlsx/csv uploads fall through to the existing
                                 FEATURE_MEDIA_UPLOAD behavior unchanged.

F52 STAGE 1 (safe refactors):
  FEATURE_LAST_TOOL_RESULT_SHADOW - passive Last-Tool-Result recorder (core/last_tool_result_shadow.py).
                                 RAM-only, TTL-bounded, side-effect-only observation —
                                 never affects return values or control flow. default OFF.

DECISION HUB (Stage 0):
  FEATURE_DECISION_HUB         - /decision new|update|status + forward→Inbox (decision_pipeline.py, cmd_decision.py); default OFF

  FEATURE_DECISION_AUTO_INGESTION - auto route WhatsApp/email/document/voice input to Decision Inbox only; default OFF

OUTPUT GATEWAY (C52):
  FINANCIAL_COMMITMENT_GATE   - core/financial_gate.py escalation על הודעות עם התחייבות פיננסית
                                 false (default) → shadow mode (log בלי לעצור)
                                 true            → production escalation (ESCALATE, לא BLOCK)

GAME / SCHEDULER:
  GAME_SCHEDULER              - scheduler jobs של מערכת הגיימיפיקציה
  PAYMENT_REMINDERS           - תזכורות תשלום אוטומטיות
  GIT_AUDIT_SCHEDULER         - הרצה יומית אוטומטית של daily_git_audit.py; default OFF (נשאר manual-only)

PR3A/PR3B/PR3C — Airtable Schema Snapshot / RuntimeSchemaProvider (SPEC v2):
  FEATURE_AIRTABLE_SCHEMA_SNAPSHOT         - scheduler job מייצר snapshot של ה-schema החי
                                 ומעלה JSON+XLSX ל-Tables.SCHEMA_SNAPSHOTS; default OFF.
                                 דורש manual pre-activation checklist (טבלה קיימת + שדות
                                 תואמים) לפני הפעלה — ראה tools/schema_snapshot.py.
  FEATURE_AIRTABLE_SCHEMA_SNAPSHOT_CLEANUP - מפעיל retention policy (מחיקת snapshots ישנים)
                                 בתוך run_snapshot_archive(); default OFF — ניקוי ראשוני
                                 ייעשה ידנית (tools/schema_snapshot.apply_retention_policy()).
  FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER - שלוש מצבים (לא boolean רגיל — ראה
                                 core/runtime_schema_provider.py): "off" (ברירת מחדל, התנהגות
                                 קיימת) / "shadow" (הפרובידר רץ ומשווה, לא חוסם כתיבה) /
                                 "enforce" (הפרובידר חוסם כתיבה). קריאה דרך get_schema_provider_mode(),
                                 לא is_enabled() — זה לא boolean.
  FEATURE_AIRTABLE_RUNTIME_SCHEMA_REFRESH  - מפעיל refresh() תקופתי של הפרובידר מה-scheduler;
                                 default OFF.

C94 (Unified Ingress Envelope + Evidence Trace):
  FEATURE_INGRESS_ENVELOPE    - קיל-סוויץ' לבניית IngressEnvelope ב-run_agent() (Telegram+WhatsApp/
                                 Twilio, C94 Stage ג/ד). default ON (ברירת מחדל הפוכה מרוב הדגלים
                                 כאן — ראה _DEFAULTS למטה) כי C94 כבר ב-main/כנראה בפרוד: אם ה-flag
                                 חסר לגמרי (עוד לא הוגדר ב-Render) הוא חייב להתנהג כאילו true, אחרת
                                 deploy של הקוד הזה היה מכבה שקט את מה שכבר רץ. false → run_agent()
                                 מדלג לגמרי על בניית ה-envelope (capture_ic=None כמו תמיד), classify_
                                 ingress()/הרואטר עצמם לא מושפעים כלל.

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
    "FEATURE_INGRESS_ENVELOPE": os.environ.get("FEATURE_INGRESS_ENVELOPE", "true"),
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


_SCHEMA_PROVIDER_MODES = ("off", "shadow", "enforce")


def get_schema_provider_mode() -> str:
    """
    Three-state accessor for FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER.
    Unlike every other flag in this registry, this one is not a boolean —
    it has an OFF/SHADOW/ENFORCE lifecycle (see core/runtime_schema_provider.py).
    Returns "off" for any unset/unrecognized value — fail closed to old behavior.
    """
    value = os.environ.get("FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER", "").strip().lower()
    return value if value in _SCHEMA_PROVIDER_MODES else "off"


def set_flag(name: str, value: bool) -> None:
    """Set a runtime feature flag. Persistent flags are written to disk."""
    _RUNTIME[name] = value
    if name in _PERSISTENT_FLAG_NAMES:
        _save_persistent()
        logger.warning(f"[FeatureFlags] persistent flag {name}={value} saved to disk")


# Restore on import so flags survive Render restarts.
_load_persistent()

ERROR_REPORTING = os.environ.get("ERROR_REPORTING", "true")
