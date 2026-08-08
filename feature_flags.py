import os
import logging
import threading
from dataclasses import dataclass
from typing import Optional

from core.emergency_stop import (
    EmergencyStopManager,
    FlagEvaluation,
    KNOWN_EMERGENCY_STOP_FLAG_NAMES,
    ManagerStatus,
    WriteResult,
)

"""
══════════════════════════════════════════════════════════════════════
FEATURE FLAGS REGISTRY — מקור אמת יחיד
כל flag שנבדק בקוד חייב להופיע כאן. ברירת מחדל = כבוי אלא אם צוין אחרת.
══════════════════════════════════════════════════════════════════════

EMERGENCY (PATCH 3B Step 6 — durably backed by Airtable via
EmergencyStopManager, NOT the legacy in-memory/_tmp mechanism; survives a
restart because the durable store does, not because of anything in this
file. is_enabled()/set_flag() are intercepted for exactly these 5 names —
see is_enabled()/set_flag()'s own docstrings and the
"PATCH 3B Step 6 — atomic cutover" section below):
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
  FEATURE_EVIDENCE_FINALIZER    - "off" (default, no comparison) / "shadow"
                                 (evidence-derived status compared and safely logged; user
                                 text unchanged) / "enforce" (accepted but still shadow-only
                                 in PR-RP4). Read through get_evidence_finalizer_state().
  FEATURE_UNIFIED_STATUS_FORMATTER - F52: routes ActionGateway.compose_status_reply()
                                 through the single canonical formatter
                                 (core/agent_message_formatter.format_agent_message).
                                 "off" (default, legacy status text byte-identical to
                                 before) / "shadow" (unified output computed + logged next
                                 to legacy, legacy still sent) / "on" (unified output sent).
                                 Read through get_unified_status_formatter_state(). Fails
                                 closed to "off". Independent of FEATURE_ACTION_GATEWAY.

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
  FEATURE_SINGLE_SPEAKER_APPROVAL_UX - PR1 response-routing cutover for approval
                                 turns. false (default): legacy delivery routing;
                                 true: Gateway owns the one final response. Identifier
                                 redaction is unconditional and is not rolled back.
  FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS - PR2, resolver דטרמיניסטי מוקדם
                                 לאישורים. כבוי כברירת מחדל, ופעיל רק כש-
                                 FEATURE_SINGLE_SPEAKER_APPROVAL_UX מופעל.
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

# PATCH 3B Step 6: the /tmp/emergency_flags.json persistence mechanism
# (_PERSISTENT_FLAG_NAMES / _PERSIST_PATH / _load_persistent() /
# _save_persistent(), restored on import, written on every set_flag() call
# for the 5 EMERGENCY_STOP_* names) has been removed entirely. It existed
# ONLY for those 5 names, and set_flag() now hard-blocks them (see
# EmergencyStopLegacyWriteBlocked below) — durable persistence for these
# flags is EmergencyStopManager's job (Airtable-backed, survives a restart
# for real, unlike a container-local /tmp file). Nothing else in this file
# ever used this mechanism.

# Runtime overrides — in-memory, checked first.
_RUNTIME: dict[str, bool] = {}

# Flags that default to ON when the env var is unset (unlike the standard
# default-OFF behavior). Each entry mirrors os.environ.get(NAME, default).
_DEFAULTS: dict[str, str] = {
    "IMPORT_DOMAIN": os.environ.get("IMPORT_DOMAIN", "true"),
    "FEATURE_INGRESS_ENVELOPE": os.environ.get("FEATURE_INGRESS_ENVELOPE", "true"),
    "FEATURE_SINGLE_SPEAKER_APPROVAL_UX": os.environ.get(
        "FEATURE_SINGLE_SPEAKER_APPROVAL_UX", "false",
    ),
    "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS": os.environ.get(
        "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS", "false",
    ),
}


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
    """
    PATCH 3B Step 6 cutover: for exactly the 5 canonical EMERGENCY_STOP_*
    names (KNOWN_EMERGENCY_STOP_FLAG_NAMES), this delegates to
    evaluate_emergency_stop() — the durable, Airtable-backed manager — and
    NEVER consults _RUNTIME/env for those names anymore. If the manager
    isn't configured yet (EmergencyStopNotConfigured — shouldn't happen in
    production after app.run_startup_sequence(), but is reachable in a test
    or a not-yet-bootstrapped context), this fails closed to True, matching
    the manager's own "unknown -> blocked=True" convention, rather than
    silently falling back to the legacy env/_RUNTIME path (which would
    reintroduce exactly the dual-source-of-truth bug this cutover exists to
    remove).

    Every other flag name is completely unaffected by this branch — same
    _RUNTIME/env lookup as always.
    """
    if name in KNOWN_EMERGENCY_STOP_FLAG_NAMES:
        try:
            return evaluate_emergency_stop(name).blocked
        except EmergencyStopNotConfigured:
            return True

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

    # PR2 אסור שישנה בעלות-תשובה באופן עצמאי — לכן ה-resolver המוקדם שלו
    # כבוי מבחינה אפקטיבית אלא אם גם מעבר-הבעלות של PR1 מופעל.
    if name == "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS" and value:
        return is_enabled("FEATURE_SINGLE_SPEAKER_APPROVAL_UX")

    return value


_SCHEMA_PROVIDER_STATES = ("off", "shadow", "enforce")
_TOOL_AVAILABILITY_STATES = frozenset({"off", "shadow", "enforce"})
_EVIDENCE_FINALIZER_STATES = frozenset({"off", "shadow", "enforce"})
_UNIFIED_STATUS_FORMATTER_STATES = frozenset({"off", "shadow", "on"})


def get_tool_availability_filter_state() -> str:
    """Return the tool-availability rollout state; unknown values fail to off."""
    value = os.environ.get("FEATURE_TOOL_AVAILABILITY_FILTER", "off").strip().lower()
    return value if value in _TOOL_AVAILABILITY_STATES else "off"


def get_evidence_finalizer_state() -> str:
    """Return RP4's rollout state; enforce remains comparison-only until RP5."""
    value = os.environ.get("FEATURE_EVIDENCE_FINALIZER", "off").strip().lower()
    return value if value in _EVIDENCE_FINALIZER_STATES else "off"


def get_unified_status_formatter_state() -> str:
    """
    Three-state accessor for FEATURE_UNIFIED_STATUS_FORMATTER (F52 — routes
    ActionGateway.compose_status_reply() through the single canonical formatter
    core/agent_message_formatter.format_agent_message):

      off    — legacy compose_status_reply text, byte-identical to before F52.
      shadow — the unified formatter output is computed and logged next to the
               legacy text for comparison, but the LEGACY text is still sent.
      on     — the unified formatter output is sent to the user.

    Returns "off" for any unset/unrecognized value — fail closed to legacy
    behavior. Read via this accessor, NOT via is_enabled() (three-state, not a
    boolean). Independent of FEATURE_ACTION_GATEWAY.
    """
    value = os.environ.get("FEATURE_UNIFIED_STATUS_FORMATTER", "off").strip().lower()
    return value if value in _UNIFIED_STATUS_FORMATTER_STATES else "off"


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
    """
    Set a runtime feature flag.

    PATCH 3B Step 6 cutover: for exactly the 5 canonical EMERGENCY_STOP_*
    names, this raises EmergencyStopLegacyWriteBlocked instead of writing
    to _RUNTIME — that in-memory (previously /tmp-persisted) path no longer
    exists for these names. Use set_emergency_stop()/clear_emergency_stop()
    instead, which write durably through the configured EmergencyStopManager.
    Every other flag name is unaffected.
    """
    if name in KNOWN_EMERGENCY_STOP_FLAG_NAMES:
        raise EmergencyStopLegacyWriteBlocked(
            f"set_flag({name!r}, {value!r}) is blocked (PATCH 3B Step 6) — "
            f"{name} is one of the 5 canonical Emergency Stop flags, durably "
            "backed by Airtable via EmergencyStopManager. Use "
            "set_emergency_stop()/clear_emergency_stop() instead."
        )
    _RUNTIME[name] = value


# ══════════════════════════════════════════════════════════════════
# PATCH 3B — EmergencyStopManager integration and completed cutover.
# is_enabled() delegates the canonical emergency names to the manager;
# set_flag() rejects legacy writes. TMA and cost-monitor writes use the
# durable APIs below.
#
# This module may import core.emergency_stop (pure, I/O-free — see that
# module's own header). It does NOT import adapters.airtable_emergency_stop_store
# or tools/airtable_gateway — building the concrete adapter and injecting it
# via configure_emergency_stop_manager() remains app.py's startup job, not
# this module's.
# ══════════════════════════════════════════════════════════════════

class EmergencyStopNotConfigured(RuntimeError):
    """Raised by evaluate_emergency_stop()/set_emergency_stop()/
    clear_emergency_stop() when configure_emergency_stop_manager() has not
    been called yet. is_enabled() (Step 6) calls evaluate_emergency_stop()
    internally for the 5 canonical EMERGENCY_STOP_* names but always
    CATCHES this — it never propagates out of is_enabled() itself; an
    unconfigured manager there just means is_enabled() fails closed to
    True instead of raising."""


class EmergencyStopManagerConflict(RuntimeError):
    """Raised by configure_emergency_stop_manager() when a DIFFERENT manager
    instance is already configured. Re-configuring with the SAME instance
    (by identity) is a no-op, not an error."""


class EmergencyStopLegacyWriteBlocked(RuntimeError):
    """Raised by set_flag() (Step 6 cutover) when called with one of the 5
    canonical EMERGENCY_STOP_* names. Those names no longer have any legacy
    in-memory/_tmp write path — use set_emergency_stop()/
    clear_emergency_stop() instead, which write durably through the
    configured EmergencyStopManager."""


@dataclass(frozen=True)
class EmergencyStopStatusView:
    """get_emergency_stop_status()'s return shape. Unlike ManagerStatus
    (core.emergency_stop), this is safe to request at any time, configured
    or not — configured=False + manager_status=None pre-configure, never a
    flags dict that could be misread as "unknown = stop active"."""
    configured: bool
    manager_status: Optional[ManagerStatus] = None


@dataclass(frozen=True)
class EmergencyStopClearResult:
    """clear_emergency_stop()'s return shape. write is the durable write
    outcome; still_blocked_by_env is True when, even after a successful
    durable clear, an env force-stop (see EmergencyStopManager's
    force_stop_provider precedence) still makes the flag effectively
    blocked — a caller must never report "cleared" from write.ok alone
    without also checking this."""
    write: WriteResult
    still_blocked_by_env: bool


_emergency_stop_manager: Optional[EmergencyStopManager] = None
_emergency_stop_manager_lock = threading.Lock()


def _env_force_stop_provider(flag_name: str) -> bool:
    """
    PATCH 3B Step 6: the concrete force_stop_provider wired into the
    EmergencyStopManager constructed in core/emergency_stop_bootstrap.py —
    a manual break-glass override read directly from os.environ (a Render
    dashboard env var, set by hand), independent of the durable Airtable
    state entirely.

    Deliberately does NOT call is_enabled() — after this step's cutover,
    is_enabled() for these same 5 names delegates to
    evaluate_emergency_stop(), which calls INTO this very manager/provider;
    routing through is_enabled() here would be circular. This reads
    os.environ directly, exactly like is_enabled() used to for these names
    pre-cutover, just narrower (see below).

    Precedence contract (matches EmergencyStopManager.evaluate()'s own
    docstring — force_stop_provider returning True always wins over
    durable/cache state): returning True forces a stop unconditionally.
    Returning False does NOT clear or override anything — it just means
    this override isn't forcing a block right now; a durable True still
    blocks normally through the ordinary cache/durable path. An unset env
    var and an explicit "false" are treated identically (both -> False) —
    neither one can ever cancel a durable stop; only a real
    clear_emergency_stop() durable write can do that.

    Only the literal string "true" (case-insensitive) forces a stop —
    narrower than is_enabled()'s generic truthy parsing ("1"/"yes"/"on"/
    "enabled" also count there). This is a deliberately unambiguous
    convention for a manual emergency override, not a normal feature flag.
    """
    raw = os.environ.get(flag_name, "").strip().lower()
    return raw == "true"


def configure_emergency_stop_manager(manager: EmergencyStopManager) -> None:
    """
    Inject the (already-constructed, already-wired) EmergencyStopManager
    that evaluate_emergency_stop()/get_emergency_stop_status()/
    set_emergency_stop()/clear_emergency_stop() delegate to.

    Deliberately does NOT construct a manager or a store here — no
    adapters.airtable_emergency_stop_store import, no Airtable gateway
    import, no network/file I/O. The caller (a later step's app.py wiring)
    builds the manager (and its adapter) and passes the finished object in.

    Thread-safe. Calling this again with the SAME instance (by identity) is
    a no-op. Calling it with a DIFFERENT instance while one is already
    configured raises EmergencyStopManagerConflict — there is exactly one
    manager for the life of the process; swapping managers at runtime is
    not a supported operation (restart the process instead).
    """
    if manager is None:
        raise TypeError("manager must not be None")
    global _emergency_stop_manager
    with _emergency_stop_manager_lock:
        if _emergency_stop_manager is None:
            _emergency_stop_manager = manager
        elif _emergency_stop_manager is not manager:
            raise EmergencyStopManagerConflict(
                "an EmergencyStopManager is already configured — "
                "configure_emergency_stop_manager() does not support "
                "swapping managers at runtime."
            )
        # else: same instance already configured — idempotent no-op.


def _reset_emergency_stop_manager_for_tests() -> None:
    """Test-only. NOT a production API — clears the configured manager so
    each test can start from an unconfigured state. Never call this from
    application code (no caller outside test_*.py files should ever import
    a name prefixed with _)."""
    global _emergency_stop_manager
    with _emergency_stop_manager_lock:
        _emergency_stop_manager = None


def _get_configured_emergency_stop_manager() -> EmergencyStopManager:
    with _emergency_stop_manager_lock:
        manager = _emergency_stop_manager
    if manager is None:
        raise EmergencyStopNotConfigured(
            "configure_emergency_stop_manager() has not been called yet — "
            "this API has no manager to delegate to."
        )
    return manager


def evaluate_emergency_stop(flag_name: str) -> FlagEvaluation:
    """
    Manager-backed read API used by is_enabled() for the canonical
    EMERGENCY_STOP_* names. Raises EmergencyStopNotConfigured if
    configure_emergency_stop_manager() hasn't been called.
    """
    return _get_configured_emergency_stop_manager().evaluate(flag_name)


def get_emergency_stop_status() -> EmergencyStopStatusView:
    """
    Manager-backed status API used by startup/health code. Unlike the other
    three functions here, this one does NOT raise when
    unconfigured — a health/status view must be safe to call at any time.
    Pre-configure it returns configured=False with manager_status=None
    (never a flags dict whose "unknown" entries could be misread as an
    active stop).
    """
    with _emergency_stop_manager_lock:
        manager = _emergency_stop_manager
    if manager is None:
        return EmergencyStopStatusView(configured=False, manager_status=None)
    return EmergencyStopStatusView(configured=True, manager_status=manager.status())


def set_emergency_stop(
    flag_name: str,
    enabled: bool,
    *,
    operation_id: str,
    updated_by: str,
    source: str,
    reason: str,
    expected_operation_id: Optional[str] = None,
) -> WriteResult:
    """
    Parallel write API (Step 3, wired to live callers as of Step 6). Raises
    EmergencyStopNotConfigured if unconfigured. See EmergencyStopManager.write()
    (core/emergency_stop.py) for the underlying durable-write + cache-
    invalidation contract.

    source (Step 6): the caller identifies itself explicitly — no longer
    hardcoded to "feature_flags.set_emergency_stop". Every production caller
    uses its own canonical value (e.g. cost_monitor.py -> "cost_watchdog",
    tma_api.py's stop endpoint -> "tma_owner_stop") so the durable record's
    Source field and the owner-facing notification both name who actually
    triggered the stop, not this pass-through function.
    """
    manager = _get_configured_emergency_stop_manager()
    return manager.write(
        flag_name, enabled,
        operation_id=operation_id, updated_by=updated_by,
        source=source, reason=reason,
        expected_operation_id=expected_operation_id,
    )


def clear_emergency_stop(
    flag_name: str,
    *,
    operation_id: str,
    updated_by: str,
    source: str,
    reason: str,
    expected_operation_id: Optional[str] = None,
) -> EmergencyStopClearResult:
    """
    Parallel write API (Step 3, wired to live callers as of Step 6). Raises
    EmergencyStopNotConfigured if unconfigured.

    Durable-clears (Enabled=False) the given flag, then re-evaluates it: if
    an env force-stop is still configured for this flag (see
    EmergencyStopManager's force_stop_provider precedence), the flag is
    still EFFECTIVELY blocked even though the durable write succeeded.
    still_blocked_by_env communicates that explicitly so a caller never
    reports "cleared" when nothing observable actually changed.

    source (Step 6): see set_emergency_stop()'s docstring — every caller
    identifies itself explicitly (e.g. tma_api.py's clear endpoint ->
    "tma_owner_clear").
    """
    manager = _get_configured_emergency_stop_manager()
    write_result = manager.write(
        flag_name, False,
        operation_id=operation_id, updated_by=updated_by,
        source=source, reason=reason,
        expected_operation_id=expected_operation_id,
    )
    still_blocked_by_env = manager.evaluate(flag_name).source == "env"
    return EmergencyStopClearResult(write=write_result, still_blocked_by_env=still_blocked_by_env)


ERROR_REPORTING = os.environ.get("ERROR_REPORTING", "true")
