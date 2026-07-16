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
  FEATURE_TOOL_AVAILABILITY_FILTER - "off" (default, no checks) / "shadow"
                                 (local readiness diagnostics only; schemas unchanged) /
                                 "enforce" (hide role-allowed tools whose local readiness
                                 check reports unavailable). Read through
                                 get_tool_availability_filter_state(), not is_enabled().

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
  FEATURE_ACTION_CONTRACT_PERSISTENCE - durable new proposals + proposal recovery lookups (Phase 4B-1A); default OFF
  FEATURE_ATOMIC_CLAIMS        - PostgreSQL atomic coordination for contract execution (Phase 4B0.1A); default OFF
  FEATURE_PA01_ENFORCEMENT_STATE - שלוש מצבים (לא boolean רגיל): "off" (ברירת מחדל,
                                 התנהגות קיימת ללא שינוי) / "shadow" (מטריצת PA-01 מחושבת
                                 ומלוגגת per-row, לעולם לא נוגעת ב-final_reply) / "enforce"
                                 (final_reply מוחלף בהתאם לשורת המטריצה — ראה
                                 docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md).
                                 State-only: אף שלב לא קורא את טקסט final_reply. קריאה דרך
                                 get_pa01_enforcement_state(), לא is_enabled(). עצמאי מ-
                                 FEATURE_ACTION_GATEWAY (ראה §1 במסמך).

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

PR3A — Airtable Schema Snapshot Archive:
  FEATURE_AIRTABLE_SCHEMA_SNAPSHOT         - scheduler job מייצר snapshot של ה-schema החי
                                 ומעלה JSON+XLSX ל-Tables.SCHEMA_SNAPSHOTS; default OFF.
                                 דורש manual pre-activation checklist (טבלה קיימת + שדות
                                 תואמים) לפני הפעלה — ראה tools/schema_snapshot.py.
  FEATURE_AIRTABLE_SCHEMA_SNAPSHOT_CLEANUP - מפעיל retention policy (מחיקת snapshots ישנים)
                                 בתוך run_snapshot_archive(); default OFF — ניקוי ראשוני
                                 ייעשה ידנית (tools/schema_snapshot.apply_retention_policy()).

PR3B (rev.2) — Airtable RuntimeSchemaProvider (independent of any snapshot-
archive work — see core/runtime_schema_provider.py):
  FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE - שלוש מצבים (לא boolean רגיל):
                                 "off" (ברירת מחדל, התנהגות קיימת ללא שינוי) / "shadow"
                                 (הפרובידר רץ, משווה מול schema_validator הקיים, מלוגג
                                 discrepancy — לא חוסם כתיבה) / "enforce" (תוצאת הפרובידר
                                 בפועל קובעת אילו שדות נחסמים). קריאה דרך
                                 get_runtime_schema_provider_state(), לא is_enabled().

PR2 (rev.2) — Gateway select-value validation (depends on PR3B's
RuntimeSchemaProvider; independent flag from it — see
tools/airtable_gateway.py:_provider_invalid_select_values()):
  FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE - שלוש מצבים (לא boolean רגיל):
                                 "off" (ברירת מחדל, אין בדיקת ערכים בכלל) / "shadow"
                                 (מלוגג ערך singleSelect/multipleSelects לא-תקין מול
                                 choices החיים, לא חוסם/מוריד כלום) / "enforce" (שדה
                                 עם ערך לא-תקין מוסר כולו מה-write — multipleSelects עם
                                 ערך לא-תקין אחד מוסר כולו, אין סינון חלקי). פועל רק
                                 כש-RuntimeSchemaProvider מחזיר mode="full" לטבלה —
                                 ב-mode="name_only" (seed) תמיד מדלג, ללא false positives.
                                 קריאה דרך get_select_value_validation_state(), לא is_enabled().

C94 (Unified Ingress Envelope + Evidence Trace):
  FEATURE_INGRESS_ENVELOPE    - קיל-סוויץ' לבניית IngressEnvelope ב-run_agent() (Telegram+WhatsApp/
                                 Twilio, C94 Stage ג/ד). default ON (ברירת מחדל הפוכה מרוב הדגלים
                                 כאן — ראה _DEFAULTS למטה) כי C94 כבר ב-main/כנראה בפרוד: אם ה-flag
                                 חסר לגמרי (עוד לא הוגדר ב-Render) הוא חייב להתנהג כאילו true, אחרת
                                 deploy של הקוד הזה היה מכבה שקט את מה שכבר רץ. false → run_agent()
                                 מדלג לגמרי על בניית ה-envelope (capture_ic=None כמו תמיד), classify_
                                 ingress()/הרואטר עצמם לא מושפעים כלל.

BUG-104 (Core Reasoning Activation Program — Phase 1: Leads Read-Only
Reasoning Projection — see core/leads_reasoning_projection.py):
  FEATURE_CORE_REASONING_LEADS_STATE - שלוש מצבים (לא boolean רגיל):
                                 "off" (ברירת מחדל — אין reasoning, אין קריאת Lead
                                 Events נוספת, אין שדה "reasoning" ב-GET /api/leads/<id>,
                                 response נשאר byte-compatible) / "shadow" (reasoning
                                 מחושב, נבדק ומלוגג — אך ה-response לא משתנה, אין
                                 persistence) / "on" (projection "reasoning" מוחזר ב-API,
                                 אין persistence). ערך לא-מוכר → "off" (fail closed).
                                 קריאה דרך get_core_reasoning_leads_state(), לא is_enabled().

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


# PR-0C (BUG-TMA-APPROVAL-TRUTHFULNESS follow-up): EMAIL_INBOUND/ABANDONED_LEADS
# request approval for "send_email_reply"/"send_bounce" via event_bus, but
# neither action has a working execution path — no .confirmed subscriber, and
# no dispatcher tool (unlike media_save_to_memory/send_followup/send_recovery,
# migrated in Phase 1). Approving either today always dead-ends with
# "⚠️ אין handler — הפעולה לא בוצעה." Owner decision (12/07/2026): do not touch
# these two writers in PR-0C; hard-block turning either flag on until the full
# adapter (schema + tool_registry + dispatcher + service + tests) exists for
# its action — checked here structurally (tool_registry entry), not by trust.
_ADAPTER_GATED_FLAGS: dict[str, str] = {
    "EMAIL_INBOUND":   "send_email_reply",
    "ABANDONED_LEADS": "send_bounce",
}


def is_enabled(name: str) -> bool:
    if name in _RUNTIME:
        value = _RUNTIME[name]
    else:
        raw = os.environ.get(name, _DEFAULTS.get(name, "")).strip().lower()
        value = raw in ("1", "true", "yes", "on", "enabled")

    if value and name in _ADAPTER_GATED_FLAGS:
        import tool_registry
        required_tool = _ADAPTER_GATED_FLAGS[name]
        if tool_registry.get(required_tool) is None:
            logging.getLogger(__name__).error(
                "[FeatureFlags] %s requested ON but blocked — '%s' has no "
                "ActionGateway adapter yet (tool_registry entry missing). "
                "Build the adapter (schema + registry + dispatcher + service + "
                "tests) before enabling this flag.", name, required_tool,
            )
            return False

    return value


_SCHEMA_PROVIDER_STATES = ("off", "shadow", "enforce")
_TOOL_AVAILABILITY_STATES = frozenset({"off", "shadow", "enforce"})


def get_tool_availability_filter_state() -> str:
    """Return the tool-availability rollout state; unknown values fail to off."""
    value = os.environ.get("FEATURE_TOOL_AVAILABILITY_FILTER", "off").strip().lower()
    return value if value in _TOOL_AVAILABILITY_STATES else "off"


def get_runtime_schema_provider_state() -> str:
    """
    Three-state accessor for FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE.
    Unlike every other flag in this registry, this one is not a boolean —
    it has an off/shadow/enforce lifecycle (see core/runtime_schema_provider.py).
    Returns "off" for any unset/unrecognized value — fail closed to old behavior.
    """
    value = os.environ.get("FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE", "off").strip().lower()
    return value if value in _SCHEMA_PROVIDER_STATES else "off"


def get_select_value_validation_state() -> str:
    """
    Three-state accessor for FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE
    (PR2 rev.2). Independent of get_runtime_schema_provider_state() — a
    deployment can run one in enforce and the other in shadow/off.
    Returns "off" for any unset/unrecognized value — fail closed to old behavior.
    """
    value = os.environ.get("FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE", "off").strip().lower()
    return value if value in _SCHEMA_PROVIDER_STATES else "off"


_PA01_STATES = frozenset({"off", "shadow", "enforce"})


def get_pa01_enforcement_state() -> str:
    """
    Three-state accessor for FEATURE_PA01_ENFORCEMENT_STATE (PA-01 —
    Phantom Approval Prompt structural enforcement). Independent of
    FEATURE_ACTION_GATEWAY by design — see
    docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md §1 for why.
    Returns "off" for any unset/unrecognized value — fail closed to old
    (log-only) behavior.
    """
    value = os.environ.get("FEATURE_PA01_ENFORCEMENT_STATE", "off").strip().lower()
    return value if value in _PA01_STATES else "off"


_CORE_REASONING_LEADS_STATES = frozenset({"off", "shadow", "on"})


def get_core_reasoning_leads_state() -> str:
    """
    Three-state accessor for FEATURE_CORE_REASONING_LEADS_STATE (BUG-104 —
    Core Reasoning Activation Program, Phase 1: Leads Read-Only Reasoning
    Projection). Independent of FEATURE_DECISION_HUB and every other flag.

      off    — no reasoning, no extra Lead Events read, no "reasoning" field
               on GET /api/leads/<id>; the response stays byte-compatible.
      shadow — reasoning is computed, verified and logged, but the API
               response is unchanged and nothing is persisted.
      on     — the "reasoning" projection is returned in the API response;
               nothing is persisted.

    Returns "off" for any unset/unrecognized value — fail closed to old
    behavior. Read via this accessor, NOT via is_enabled() (this flag is
    not a boolean). See core/leads_reasoning_projection.py.
    """
    value = os.environ.get("FEATURE_CORE_REASONING_LEADS_STATE", "off").strip().lower()
    return value if value in _CORE_REASONING_LEADS_STATES else "off"


def set_flag(name: str, value: bool) -> None:
    """Set a runtime feature flag. Persistent flags are written to disk."""
    _RUNTIME[name] = value
    if name in _PERSISTENT_FLAG_NAMES:
        _save_persistent()
        logger.warning(f"[FeatureFlags] persistent flag {name}={value} saved to disk")


# Restore on import so flags survive Render restarts.
_load_persistent()

ERROR_REPORTING = os.environ.get("ERROR_REPORTING", "true")
