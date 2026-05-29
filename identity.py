# identity.py
# שכבת הזהות המרכזית — הבסיס של כל Multi-Tenant
#
# כל אינטראקציה במערכת עוברת דרך Identity.
# chat_id לבדו הוא לא זהות — tenant + user + role + channel = זהות.
#
# שימוש:
#   identity = resolve_identity("telegram", "123456789")
#   → Identity(tenant_id="boss_hq", user_id="eliyahu", role="owner", channel="telegram")

from __future__ import annotations
import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# Roles
# ══════════════════════════════════════════════════

class Role:
    OWNER    = "owner"    # אליהו — כל ההרשאות
    STAFF    = "staff"    # צוות פנימי — תפעול, לא פיננסי
    CLIENT   = "client"   # לקוח חיצוני — רק נתונים שלו
    SUPPLIER = "supplier" # ספק — PO רלוונטי בלבד
    READONLY = "readonly" # קריאה בלבד


# ══════════════════════════════════════════════════
# Identity Dataclass
# ══════════════════════════════════════════════════

@dataclass
class Identity:
    tenant_id:    str
    user_id:      str
    role:         str
    channel:      str
    chat_id:      str              # המזהה המקורי מהערוץ
    display_name: str = ""
    metadata:     dict = field(default_factory=dict)

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"

    @property
    def is_owner(self) -> bool:
        return self.role == Role.OWNER

    @property
    def is_internal(self) -> bool:
        return self.role in (Role.OWNER, Role.STAFF)

    @property
    def is_external(self) -> bool:
        return self.role in (Role.CLIENT, Role.SUPPLIER)

    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())


# ══════════════════════════════════════════════════
# Permission Map
# ══════════════════════════════════════════════════

ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.OWNER: {
        "tools.all",
        "tools.financial", "tools.gmail", "tools.drive",
        "tools.calendar", "tools.airtable", "tools.sheets",
        "data.all", "data.financial", "data.clients",
        "actions.send_email", "actions.create_invoice",
        "actions.approve", "actions.delete",
    },
    Role.STAFF: {
        "tools.drive", "tools.calendar", "tools.airtable",
        "tools.sheets", "tools.gmail",
        "data.projects", "data.tasks", "data.suppliers",
        "actions.send_email",
    },
    Role.CLIENT: {
        "data.own_projects", "data.own_invoices", "data.own_status",
    },
    Role.SUPPLIER: {
        "data.own_orders", "data.own_qc",
    },
    Role.READONLY: {
        "data.own_projects",
    },
}


# ══════════════════════════════════════════════════
# Identity Registry — מיפוי chat_id → Identity
# ══════════════════════════════════════════════════

def _load_registry() -> dict:
    """טוען מפת זהויות: env var > קובץ > default (ELIYAHU_CHAT_ID)."""

    # Option 1: env var (מומלץ ל-Render)
    env_map = os.environ.get("IDENTITY_MAP", "")
    if env_map:
        try:
            return json.loads(env_map)
        except json.JSONDecodeError as e:
            logger.error(f"IDENTITY_MAP env parse error: {e}")

    # Option 2: קובץ מקומי (פיתוח)
    try:
        with open("identity_map.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"identity_map.json load error: {e}")

    # Option 3: backward compat — אליהו בלבד
    owner_chat = os.environ.get("ELIYAHU_CHAT_ID", "")
    default: dict = {}
    if owner_chat:
        default[f"telegram:{owner_chat}"] = {
            "tenant": "boss_hq",
            "user":   "eliyahu",
            "role":   Role.OWNER,
            "name":   "אליהו חזן",
        }
    return default


_REGISTRY: dict = _load_registry()


def resolve_identity(channel: str, chat_id: str) -> Identity:
    """
    מחזיר Identity לפי channel + chat_id.
    אם לא מוכר — מחזיר READONLY (לא קורס).
    """
    key = f"{channel}:{chat_id}"
    entry = _REGISTRY.get(key)

    if entry:
        return Identity(
            tenant_id    = entry.get("tenant", "unknown"),
            user_id      = entry.get("user",   chat_id),
            role         = entry.get("role",   Role.READONLY),
            channel      = channel,
            chat_id      = chat_id,
            display_name = entry.get("name",   ""),
            metadata     = entry.get("meta",   {}),
        )

    logger.warning(f"Unknown identity: {key} — defaulting to readonly")
    return Identity(
        tenant_id    = "unknown",
        user_id      = chat_id,
        role         = Role.READONLY,
        channel      = channel,
        chat_id      = chat_id,
        display_name = "Unknown",
    )
