# identity.py — CORE_01_IDENTITY v2
#
# זרימה: resolve_identity(channel, external_id) → Identity
# Identity היא הבסיס של כל פעולה במערכת.
# אין פעולה בלי זהות. אין כלי בלי role. אין זיכרון בלי memory_key.

from __future__ import annotations
import os
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Roles — היררכיה מלאה
# ══════════════════════════════════════════════════

class Role:
    OWNER    = "owner"     # בעלים מלא — הכל פתוח
    PARTNER  = "partner"   # שותף — מוגבל לדומיין שהוגדר לו
    MANAGER  = "manager"   # מנהל תפעולי — CRM, Tasks, Calendar
    EMPLOYEE = "employee"  # עובד ביצוע — Tasks, סטטוס בלבד
    LEAD     = "lead"      # ליד חיצוני — מידע על עצמו בלבד
    GUEST    = "guest"     # אורח — תשובות כלליות בלבד
    READONLY = "readonly"  # קריאה בלבד — fallback

    # סדר עוצמה — לשימוש בהשוואות
    _RANK = {
        "owner": 6, "partner": 5, "manager": 4,
        "employee": 3, "lead": 2, "guest": 1, "readonly": 0
    }

    @classmethod
    def rank(cls, role: str) -> int:
        return cls._RANK.get(role, 0)


# ══════════════════════════════════════════════════
# Domains
# ══════════════════════════════════════════════════

class Domain:
    REAL_ESTATE = "real_estate"
    IMPORT      = "import"
    MEDIA       = "media"
    SAAS        = "saas"
    FINANCE     = "finance"
    GENERAL     = "general"

    ALL = {REAL_ESTATE, IMPORT, MEDIA, SAAS, FINANCE, GENERAL}


# ══════════════════════════════════════════════════
# Permission Map — מה כל role מורשה לעשות
# ══════════════════════════════════════════════════

ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.OWNER: {
        "tools.all",
        "tools.financial", "tools.gmail", "tools.drive",
        "tools.calendar", "tools.airtable", "tools.sheets",
        "data.all", "data.financial", "data.clients",
        "actions.send_email", "actions.create_invoice",
        "actions.approve", "actions.delete",
        "settings.read", "settings.write",
        "memory.all",
    },
    Role.PARTNER: {
        "tools.drive", "tools.calendar", "tools.airtable", "tools.sheets",
        "data.projects", "data.tasks", "data.clients",
        "actions.send_email",
        "memory.domain",
    },
    Role.MANAGER: {
        "tools.drive", "tools.calendar", "tools.airtable",
        "tools.sheets", "tools.gmail",
        "data.projects", "data.tasks", "data.suppliers", "data.clients",
        "actions.send_email",
        "memory.domain",
    },
    Role.EMPLOYEE: {
        "tools.airtable",
        "tools.calendar",
        "data.tasks",
        "memory.self",
    },
    Role.LEAD: {
        "data.self",
        "memory.self",
    },
    Role.GUEST: set(),
    Role.READONLY: {
        "data.self",
    },
}


# ══════════════════════════════════════════════════
# Identity Dataclass
# ══════════════════════════════════════════════════

@dataclass
class Identity:
    # מי
    user_id:      str              # מזהה ייחודי של האדם
    role:         str              # owner / partner / manager / employee / lead / guest / readonly
    display_name: str = ""

    # איפה
    tenant_id:    str = "boss_hq"  # העסק / הארגון
    domain_id:    str = Domain.GENERAL  # הדומיין הפעיל

    # דומיינים מורשים — רלוונטי לpartner
    allowed_domains: list = field(default_factory=list)

    # ערוץ
    channel:      str = "telegram"
    external_id:  str = ""         # chat_id / phone / email — המזהה המקורי

    # מטה
    metadata:     dict = field(default_factory=dict)

    # ── Properties ──────────────────────────────

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"

    @property
    def memory_scope(self) -> str:
        perms = ROLE_PERMISSIONS.get(self.role, set())
        if "memory.all"    in perms: return "all"
        if "memory.domain" in perms: return "domain"
        if "memory.self"   in perms: return "self"
        return "none"

    @property
    def permissions(self) -> set[str]:
        return ROLE_PERMISSIONS.get(self.role, set())

    @property
    def is_owner(self) -> bool:
        return self.role == Role.OWNER

    @property
    def is_internal(self) -> bool:
        return self.role in (Role.OWNER, Role.PARTNER, Role.MANAGER, Role.EMPLOYEE)

    @property
    def is_external(self) -> bool:
        return self.role in (Role.LEAD, Role.GUEST, Role.READONLY)

    def can(self, permission: str) -> bool:
        perms = ROLE_PERMISSIONS.get(self.role, set())
        return "tools.all" in perms or permission in perms

    def can_access_domain(self, domain: str) -> bool:
        if self.role == Role.OWNER:
            return True
        if self.role == Role.PARTNER:
            return domain in self.allowed_domains
        return True

    def __str__(self) -> str:
        return f"{self.tenant_id}/{self.user_id}@{self.role} [{self.channel}:{self.domain_id}]"


# ══════════════════════════════════════════════════
# Identity Registry
# ══════════════════════════════════════════════════

def _load_registry() -> dict:
    # Option 1: env var (Render)
    env_map = os.environ.get("IDENTITY_MAP", "")
    registry: dict = {}
    if env_map:
        try:
            registry = json.loads(env_map)
        except json.JSONDecodeError as e:
            logger.error(f"IDENTITY_MAP parse error: {e}")

    # Option 2: קובץ מקומי (פיתוח)
    if not registry:
        try:
            with open("identity_map.json", encoding="utf-8") as f:
                registry = json.load(f)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"identity_map.json error: {e}")

    # Option 3: default telegram fallback
    if not registry:
        owner_chat = os.environ.get("ELIYAHU_CHAT_ID", "")
        if owner_chat:
            registry[f"telegram:{owner_chat}"] = {
                "tenant":  "boss_hq",
                "user":    "eliyahu",
                "role":    Role.OWNER,
                "name":    "אליהו חזן",
                "domains": list(Domain.ALL),
            }

    # תמיד: הוסף WhatsApp owner אם יש OWNER_PHONES / ELIYAHU_WHATSAPP
    # ומפתח whatsapp:... עדיין לא קיים ב-registry
    wa_phone = (
        os.environ.get("OWNER_PHONES", "") or
        os.environ.get("ELIYAHU_WHATSAPP", "")
    ).strip().removeprefix("whatsapp:")

    if wa_phone and not any(k.startswith(f"whatsapp:{wa_phone}") for k in registry):
        # מצא את ה-owner entry הקיים מ-telegram כדי לשכפל אותו
        owner_entry = next(
            (v for k, v in registry.items() if v.get("role") == Role.OWNER),
            {
                "tenant":  "boss_hq",
                "user":    "eliyahu",
                "role":    Role.OWNER,
                "name":    "אליהו חזן",
                "domains": list(Domain.ALL),
            },
        )
        registry[f"whatsapp:{wa_phone}"] = owner_entry
        logger.info(f"[Identity] Auto-added WhatsApp owner entry for {wa_phone}")

    return registry


_REGISTRY: dict = _load_registry()


def resolve_identity(channel: str, external_id: str) -> Identity:
    """
    מחזיר Identity לפי channel + external_id.
    כלל ברזל: אם אין זהות ברורה — READONLY, לא קריסה.
    """
    key = f"{channel}:{external_id}"
    entry = _REGISTRY.get(key)

    if entry:
        identity = Identity(
            tenant_id       = entry.get("tenant",  "boss_hq"),
            user_id         = entry.get("user",    external_id),
            role            = entry.get("role",    Role.READONLY),
            display_name    = entry.get("name",    ""),
            domain_id       = entry.get("domain",  Domain.GENERAL),
            allowed_domains = entry.get("domains", []),
            channel         = channel,
            external_id     = external_id,
            metadata        = entry.get("meta",    {}),
        )
        logger.info(f"[Identity] Resolved: {identity}")
        return identity

    # Unknown ID — log at WARNING so it's easy to spot in Render logs
    logger.warning(
        f"[Identity] UNKNOWN — key='{key}' not in registry "
        f"(channel={channel}, external_id={external_id}). "
        f"Registry has {len(_REGISTRY)} entries: {list(_REGISTRY.keys())[:5]}"
    )

    # מספר לא מוכר = ליד פוטנציאלי
    # memory_key יהיה boss_hq:{external_id} — canonical key לכל הטבלאות
    #
    # BUG-NEW-01 ROOT CAUSE FIX:
    # display_name חייב להיות ריק — לא "ליד חדש".
    # lead_capture.py כותב: LeadFields.NAME = identity.display_name or identity.external_id
    # כאשר display_name = "ליד חדש", הערך "ליד חדש" נכתב לשדה Name של כל ליד.
    # שדה Name הוא ה-Primary Field של Airtable — הוא מופיע בכל Linked Record בכל טבלה.
    # לכן "ליד חדש" התפשט ונראה כאילו כל השדות מכילים אותו.
    # הפתרון: display_name="" → lead_capture כותב את הטלפון (external_id) כ-Name.
    is_whatsapp = channel == "whatsapp"
    return Identity(
        tenant_id    = "boss_hq",
        user_id      = external_id,
        role         = Role.LEAD if is_whatsapp else Role.READONLY,
        display_name = "",          # ← ריק בכוונה — ראה הסבר מעל
        channel      = channel,
        external_id  = external_id,
        domain_id    = Domain.GENERAL,
    )
