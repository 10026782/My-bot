# tool_registry.py — Tool Registry Layer v2
# מטא-דאטה ומדיניות לכל כלי: הרשאות, אישור, סיכון.
#
# כלל ברזל: אין Tool בלי בדיקת הרשאה.
# dispatcher מבצע. registry מחליט אם מותר.

from __future__ import annotations
import logging
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from identity import Identity


logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Tool Metadata
# ══════════════════════════════════════════════════

@dataclass(frozen=True)
class ToolAvailability:
    """Side-effect-free, redacted readiness result for one tool."""

    available: bool
    code: str
    detail: str


AvailabilityCheck = Callable[[], ToolAvailability]


@dataclass
class ToolMeta:
    name:              str
    roles_allowed:     set[str]       # roles שמורשים
    tenant_scoped:     bool = False   # מסנן לפי tenant אוטומטית
    requires_approval: bool = False   # דורש אישור אנושי לפני ביצוע
    blocked_by_emergency: bool = False  # נחסם על ידי EMERGENCY_STOP_ALL
    high_risk:         bool = False   # פעולה בלתי הפיכה
    read_only:         bool = False   # לא משנה נתונים
    model_exposed:     bool = True    # False = internal Python callers only
    availability_check: AvailabilityCheck | None = None
    description_he:    str  = ""


_STABLE_AVAILABILITY_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SECRET_ENV_MARKERS = (
    "API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "DATABASE_URL", "DSN",
)


def _redact_operator_detail(detail: object) -> str:
    """Return bounded operator text with configured secret values removed."""
    text = str(detail or "").replace("\r", " ").replace("\n", " ")
    for name, value in os.environ.items():
        if value and any(marker in name.upper() for marker in _SECRET_ENV_MARKERS):
            text = text.replace(value, "[REDACTED]")
    text = re.sub(
        r"(?i)(bearer\s+|(?:api[_-]?key|token|secret|password)\s*[:=]\s*)\S+",
        r"\1[REDACTED]",
        text,
    )
    return text[:500] or "No operator detail provided."


def _required_env_availability(
    *,
    missing_code: str,
    operator_label: str,
    names: tuple[str, ...],
) -> AvailabilityCheck:
    """Build a local env-only readiness check; it never probes a provider."""
    def check() -> ToolAvailability:
        missing = [name for name in names if not os.environ.get(name, "").strip()]
        if missing:
            return ToolAvailability(
                available=False,
                code=missing_code,
                detail=f"{operator_label} configuration is incomplete ({', '.join(missing)}).",
            )
        return ToolAvailability(
            available=True,
            code="available",
            detail=f"{operator_label} configuration is present; provider was not contacted.",
        )

    return check


_GOOGLE_OAUTH_AVAILABILITY = _required_env_availability(
    missing_code="google_oauth_missing",
    operator_label="Google OAuth",
    names=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"),
)
_AIRTABLE_AVAILABILITY = _required_env_availability(
    missing_code="airtable_config_missing",
    operator_label="Airtable",
    names=("AIRTABLE_API_KEY", "AIRTABLE_BASE_ID"),
)


class ToolRegistryInvariantError(ValueError):
    """Raised when registry/schema declarations are ambiguous or drifted."""


def _build_registry(entries: Iterable[ToolMeta]) -> dict[str, ToolMeta]:
    """Build the registry without permitting duplicate-name overwrite."""
    registry: dict[str, ToolMeta] = {}
    first_positions: dict[str, int] = {}

    for position, meta in enumerate(entries, start=1):
        if not isinstance(meta, ToolMeta):
            raise ToolRegistryInvariantError(
                f"registry declaration #{position} is not ToolMeta"
            )
        name = meta.name.strip() if isinstance(meta.name, str) else ""
        if not name:
            raise ToolRegistryInvariantError(
                f"registry declaration #{position} has an empty tool name"
            )
        if name in registry:
            raise ToolRegistryInvariantError(
                f"duplicate registry tool name {name!r}: declarations "
                f"#{first_positions[name]} and #{position}"
            )
        registry[name] = meta
        first_positions[name] = position

    return registry


def validate_tool_invariants(
    model_schemas: Sequence[Mapping[str, Any]],
    *,
    registry: Mapping[str, ToolMeta] | None = None,
) -> None:
    """Validate model schema uniqueness and registry/schema coverage."""
    active_registry = _REGISTRY if registry is None else registry
    schema_positions: dict[str, int] = {}

    for position, schema in enumerate(model_schemas, start=1):
        raw_name = schema.get("name") if isinstance(schema, Mapping) else None
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        if not name:
            raise ToolRegistryInvariantError(
                f"model schema declaration #{position} has an empty tool name"
            )
        if name in schema_positions:
            raise ToolRegistryInvariantError(
                f"duplicate model schema tool name {name!r}: declarations "
                f"#{schema_positions[name]} and #{position}"
            )
        schema_positions[name] = position

        meta = active_registry.get(name)
        if meta is None:
            raise ToolRegistryInvariantError(
                f"model-exposed schema {name!r} has no tool_registry policy"
            )
        if not meta.model_exposed:
            raise ToolRegistryInvariantError(
                f"internal-only registry tool {name!r} must not be model-exposed"
            )

    schema_names = frozenset(schema_positions)
    missing_schemas = sorted(
        name
        for name, meta in active_registry.items()
        if meta.model_exposed and name not in schema_names
    )
    if missing_schemas:
        raise ToolRegistryInvariantError(
            "model-exposed registry tools missing schemas: "
            + ", ".join(missing_schemas)
        )


# ── Shortcuts לקבוצות roles ──────────────────────
_INTERNAL      = {"owner", "partner", "manager", "employee"}
_MANAGEMENT    = {"owner", "partner", "manager"}
_SENIOR        = {"owner", "partner"}
_OWNER_ONLY    = {"owner"}
_ALL_EXTERNAL  = {"owner", "partner", "manager", "employee", "lead"}


# ══════════════════════════════════════════════════
# C83: approval and emergency blocking are separate policy dimensions.
# Derived policy sets are defined after _REGISTRY below.
# ══════════════════════════════════════════════════


# ══════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════

_REGISTRY_ENTRIES: tuple[ToolMeta, ...] = (

    # ── Google Drive ─────────────────────────────
    ToolMeta(
        name="search_drive",
        roles_allowed=_MANAGEMENT,
        read_only=True,
        availability_check=_GOOGLE_OAUTH_AVAILABILITY,
        description_he="חיפוש קבצים ב-Drive"
    ),
    ToolMeta(
        name="read_drive_file",
        roles_allowed=_MANAGEMENT,
        read_only=True,
        availability_check=_GOOGLE_OAUTH_AVAILABILITY,
        description_he="קריאת תוכן קובץ מ-Drive"
    ),

    # ── Calendar ─────────────────────────────────
    ToolMeta(
        name="calendar_get_events",
        roles_allowed=_INTERNAL,
        read_only=True,
        availability_check=_GOOGLE_OAUTH_AVAILABILITY,
        description_he="קריאת אירועים מהיומן"
    ),
    ToolMeta(
        name="calendar_create_event",
        roles_allowed=_MANAGEMENT,
        requires_approval=True,
        blocked_by_emergency=True,
        availability_check=_GOOGLE_OAUTH_AVAILABILITY,
        description_he="יצירת אירוע ביומן — דורש אישור, בודק חפיפות, force=true לקבוע בכל זאת"
    ),

    # ── Gmail ────────────────────────────────────
    ToolMeta(
        name="gmail_draft",
        roles_allowed=_MANAGEMENT,
        requires_approval=True,
        blocked_by_emergency=True,
        availability_check=_GOOGLE_OAUTH_AVAILABILITY,
        description_he="יצירת טיוטת מייל — דורש אישור (לא שולח)"
    ),
    ToolMeta(
        name="gmail_send_draft",
        roles_allowed=_SENIOR,
        requires_approval=True,
        blocked_by_emergency=True,
        high_risk=True,
        availability_check=_GOOGLE_OAUTH_AVAILABILITY,
        description_he="שליחת טיוטה — דורש אישור owner/partner"
    ),
    ToolMeta(
        name="gmail_read",
        roles_allowed=_OWNER_ONLY,
        read_only=True,
        availability_check=_GOOGLE_OAUTH_AVAILABILITY,
        description_he="קריאת מיילים אחרונים"
    ),

    # ── Sheets ───────────────────────────────────
    ToolMeta(
        name="sheets_append",
        roles_allowed=_MANAGEMENT,
        requires_approval=True,
        blocked_by_emergency=True,
        availability_check=_GOOGLE_OAUTH_AVAILABILITY,
        description_he="הוספת שורה לגיליון — דורש אישור"
    ),

    # ── Airtable ─────────────────────────────────
    ToolMeta(
        name="airtable_get",
        roles_allowed=_ALL_EXTERNAL,   # lead רואה רק נתוני עצמו (filter ב-tool)
        tenant_scoped=True,
        read_only=True,
        availability_check=_AIRTABLE_AVAILABILITY,
        description_he="שליפת רשומות מ-Airtable"
    ),
    ToolMeta(
        name="airtable_add",
        roles_allowed=_INTERNAL,
        tenant_scoped=True,
        requires_approval=True,
        blocked_by_emergency=True,
        high_risk=True,
        availability_check=_AIRTABLE_AVAILABILITY,
        description_he="הוספת רשומה ל-Airtable — דורש אישור"
    ),
    ToolMeta(
        name="airtable_update",
        roles_allowed=_MANAGEMENT,
        tenant_scoped=True,
        requires_approval=True,
        blocked_by_emergency=True,
        high_risk=True,
        availability_check=_AIRTABLE_AVAILABILITY,
        description_he="עדכון רשומה ב-Airtable — דורש אישור"
    ),
    ToolMeta(
        name="airtable_get_schema",
        roles_allowed=_SENIOR,
        read_only=True,
        availability_check=_AIRTABLE_AVAILABILITY,
        description_he="קריאת כל הטבלאות והשדות מ-Airtable בזמן אמת"
    ),

    # ── Lead Search ───────────────────────────────
    ToolMeta(
        name             = "search_lead",
        roles_allowed    = _MANAGEMENT,
        read_only        = True,
        availability_check = _AIRTABLE_AVAILABILITY,
        description_he   = "חיפוש ליד לפי שם חלקי בטבלת Leads",
    ),

    # ── Contact Resolver (N03) ────────────────────
    ToolMeta(
        name             = "resolve_contact",
        roles_allowed    = _MANAGEMENT,
        read_only        = True,
        availability_check = _AIRTABLE_AVAILABILITY,
        description_he   = "חיפוש fuzzy של איש קשר לפי שם — מחזיר פרטים או רשימה לבחירה",
    ),

    # ── Daily Digest on-demand ────────────────────
    ToolMeta(
        name           = "get_daily_report",
        roles_allowed  = _MANAGEMENT,
        read_only      = True,
        availability_check = _AIRTABLE_AVAILABILITY,
        description_he = "דוח יומי מלא — לידים חמים, פולו-אפ, משימות, עסקאות, תשלומים",
    ),

    # ── D06 — Business Memory ─────────────────────
    ToolMeta(
        name             = "search_business_memory",
        roles_allowed    = _MANAGEMENT,
        read_only        = True,
        availability_check = _AIRTABLE_AVAILABILITY,
        description_he   = "חיפוש בזיכרון עסקי — 'מה סיכמנו עם ספק X?' / 'החלטות מהפגישה עם Y'",
    ),

    # ── CRM — Payments ─────────────────────────────
    ToolMeta(
        name             = "crm_mark_payment_paid",
        roles_allowed    = _SENIOR,
        tenant_scoped    = True,
        requires_approval= True,
        blocked_by_emergency=True,
        high_risk        = True,
        availability_check = _AIRTABLE_AVAILABILITY,
        description_he   = "סימון תשלום כ-שולם — דורש אישור owner/partner",
    ),

    # ── commercial_crm.py — canonical Deal/PaymentTerm/Payment writers ──
    ToolMeta(
        name             = "crm_create_deal",
        roles_allowed    = _MANAGEMENT,
        tenant_scoped    = True,
        requires_approval= True,
        blocked_by_emergency=True,
        high_risk        = True,
        availability_check = _AIRTABLE_AVAILABILITY,
        description_he   = "יצירת עסקה (Deal) חדשה — דורש אישור",
    ),
    ToolMeta(
        name             = "crm_create_payment_term",
        roles_allowed    = _MANAGEMENT,
        tenant_scoped    = True,
        requires_approval= True,
        blocked_by_emergency=True,
        high_risk        = True,
        availability_check = _AIRTABLE_AVAILABILITY,
        description_he   = "יצירת תנאי תשלום (Payment Term) לעסקה קיימת — דורש אישור",
    ),
    ToolMeta(
        name             = "crm_create_payment",
        roles_allowed    = _MANAGEMENT,
        tenant_scoped    = True,
        requires_approval= True,
        blocked_by_emergency=True,
        high_risk        = True,
        availability_check = _AIRTABLE_AVAILABILITY,
        description_he   = "יצירת תשלום (Payment) חדש — דורש אישור",
    ),

    # ── PR-0C — ActionGateway adapters for former event_bus custom actions ──
    # Internal-execution-only: not in tools/schemas.py's TOOL_SCHEMAS, so the
    # Agent tool_use loop can never propose these directly — only trusted
    # Python callers (media_handler.py, followup_engine.py, core/lead_recovery.py)
    # via ActionGateway.propose_action(trusted_source=...).
    ToolMeta(
        name             = "media_save_to_memory",
        roles_allowed    = _INTERNAL,
        requires_approval= True,
        blocked_by_emergency=True,
        model_exposed    = False,
        description_he   = "שמירת תמלול הודעה קולית ל-Business Memory — לאחר אישור בעלים",
    ),
    ToolMeta(
        name             = "send_followup",
        roles_allowed    = _INTERNAL,
        requires_approval= True,
        blocked_by_emergency=True,
        model_exposed    = False,
        description_he   = "הצגת טיוטת פולואפ מאושרת לבעלים להעברה ידנית",
    ),
    ToolMeta(
        name             = "send_recovery",
        roles_allowed    = _INTERNAL,
        requires_approval= True,
        blocked_by_emergency=True,
        model_exposed    = False,
        description_he   = "הצגת טיוטת recovery מאושרת לבעלים להעברה ידנית",
    ),

    # ── Phase 4B-2 wiring — TMA write-through-approval adapter ──
    # Internal-execution-only, like the three adapters above: not in
    # tools/schemas.py's TOOL_SCHEMAS, so the Agent tool_use loop can never
    # propose this directly — only tma_api.py, via
    # ActionGateway.propose_action(trusted_source="tma_api"). roles_allowed
    # is the union of roles that actually reach tma_api.py's
    # _queue_tma_write_approval() call sites (owner for project creation,
    # owner+manager for lead/task writes) — narrower than _INTERNAL since
    # partner/employee never call it. This is a defense-in-depth layer only:
    # the stricter per-endpoint role check in tma_api.py's route handlers is
    # unchanged and still runs first.
    ToolMeta(
        name             = "tma_write",
        roles_allowed    = {"owner", "manager"},
        requires_approval= True,
        blocked_by_emergency=True,
        model_exposed    = False,
        description_he   = "כתיבת Airtable שמקורה ב-TMA — לאחר אישור ActionGateway",
    ),
    ToolMeta(
        name             = "external_execution.submit",
        roles_allowed    = _INTERNAL,
        requires_approval= True,
        blocked_by_emergency=True,
        model_exposed    = False,
        description_he   = "שליחת עבודה ל-adapter חיצוני לאחר אישור ActionGateway",
    ),
)

_REGISTRY: dict[str, ToolMeta] = _build_registry(_REGISTRY_ENTRIES)


# C83: single policy source. Consumers import these derived views instead of
# maintaining independent tool-name lists.
TOOLS_REQUIRING_APPROVAL: frozenset[str] = frozenset(
    name for name, meta in _REGISTRY.items() if meta.requires_approval
)
TOOLS_BLOCKED_BY_EMERGENCY: frozenset[str] = frozenset(
    name for name, meta in _REGISTRY.items() if meta.blocked_by_emergency
)


# ══════════════════════════════════════════════════
# Policy Checks
# ══════════════════════════════════════════════════

class ToolDenied(Exception):
    """כלי לא מורשה לזהות זו."""


def get(tool_name: str) -> ToolMeta | None:
    return _REGISTRY.get(tool_name)


def check_allowed(tool_name: str, identity: "Identity") -> bool:
    meta = _REGISTRY.get(tool_name)
    if not meta:
        return False
    return identity.role in meta.roles_allowed


def get_availability(
    tool_name: str,
    *,
    role: str | None = None,
    tenant_id: str | None = None,
) -> ToolAvailability:
    """Evaluate local diagnostic readiness without changing authorization or execution.

    Order: registered -> role authorized -> tenant readiness -> provider config.
    tenant_id readiness mirrors airtable_security.enforce_tenant_scope()'s own
    guard exactly (missing or "unknown" tenant_id blocks external identities;
    internal roles bypass tenant scoping there too) - it is not a new tenant
    model, only a read-only preview of that existing enforcement gate. It only
    applies to tenant_scoped=True tools, and only when a role is known (no
    role => internal/external cannot be determined, so the check is skipped,
    same as the role check above it).
    """
    meta = _REGISTRY.get(tool_name)
    if meta is None:
        return ToolAvailability(False, "unknown_tool", "Tool is not registered.")
    if role is not None and role not in meta.roles_allowed:
        return ToolAvailability(False, "role_denied", "Tool is not permitted for this role.")

    if meta.tenant_scoped and role is not None and role not in _INTERNAL:
        try:
            tenant_ready = bool(tenant_id) and tenant_id != "unknown"
        except Exception:
            logger.warning(
                "[ToolAvailability] tool=%s available=false code=tenant_check_error",
                tool_name,
            )
            return ToolAvailability(
                False,
                "tenant_check_error",
                "Tenant readiness check raised an exception; details were redacted.",
            )
        if not tenant_ready:
            return ToolAvailability(
                False,
                "tenant_not_ready",
                "Tenant context is missing or unresolved for this tenant-scoped tool.",
            )

    if meta.availability_check is None:
        return ToolAvailability(
            True,
            "available_by_default",
            "No availability check is declared; legacy availability is preserved.",
        )

    try:
        result = meta.availability_check()
    except Exception:
        logger.warning(
            "[ToolAvailability] tool=%s available=false code=availability_check_error",
            tool_name,
        )
        return ToolAvailability(
            False,
            "availability_check_error",
            "Availability check raised an exception; details were redacted.",
        )

    if not isinstance(result, ToolAvailability) or not _STABLE_AVAILABILITY_CODE.fullmatch(result.code):
        return ToolAvailability(
            False,
            "availability_check_invalid",
            "Availability check returned an invalid diagnostic contract.",
        )
    return ToolAvailability(
        bool(result.available),
        result.code,
        _redact_operator_detail(result.detail),
    )


def enforce(tool_name: str, identity: "Identity") -> ToolMeta:
    """
    זורק ToolDenied אם לא מורשה.
    כלל ברזל: נקרא לפני כל dispatch.
    """
    meta = _REGISTRY.get(tool_name)
    if not meta:
        raise ToolDenied(f"כלי לא קיים ב-Registry: {tool_name}")
    if identity.role not in meta.roles_allowed:
        raise ToolDenied(
            f"❌ {identity.role} אינו מורשה להפעיל '{tool_name}'"
        )
    return meta


def needs_approval(tool_name: str) -> bool:
    meta = _REGISTRY.get(tool_name)
    return meta.requires_approval if meta else False


def is_blocked_by_emergency(tool_name: str) -> bool:
    meta = _REGISTRY.get(tool_name)
    return meta.blocked_by_emergency if meta else False


def is_high_risk(tool_name: str) -> bool:
    meta = _REGISTRY.get(tool_name)
    return meta.high_risk if meta else False


def all_tools_for_role(role: str) -> list[str]:
    return [name for name, meta in _REGISTRY.items() if role in meta.roles_allowed]
