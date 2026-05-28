# identity.py
# זהות משתמש + RBAC

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


class Role:
    OWNER    = "owner"
    STAFF    = "staff"
    CLIENT   = "client"
    SUPPLIER = "supplier"
    READONLY = "readonly"


@dataclass
class Identity:
    tenant_id:    str
    user_id:      str
    role:         str
    channel:      str
    chat_id:      str
    display_name: str = ""
    metadata:     dict = field(default_factory=dict)

    @property
    def memory_key(self) -> str:
        """מפתח זיכרון: tenant:user"""
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


ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.OWNER: {
        "tools.all",
        "data.all",
        "actions.all",
    },
    Role.STAFF: {
        "tools.drive", "tools.calendar", "tools.airtable",
        "data.projects", "data.tasks",
        "actions.send_email",
    },
    Role.CLIENT: {
        "data.own_projects", "data.own_invoices",
    },
    Role.SUPPLIER: {
        "data.own_orders",
    },
    Role.READONLY: set(),
}


def _load_registry() -> dict:
    """טוען מפת זהויות."""
    env_map = os.environ.get("IDENTITY_MAP", "")
    if env_map:
        try:
            return json.loads(env_map)
        except json.JSONDecodeError as e:
            logger.error(f"IDENTITY_MAP parse error: {e}")

    try:
        with open("identity_map.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"identity_map.json error: {e}")

    owner_chat = os.environ.get("ELIYAHU_CHAT_ID", "")
    default: dict = {}
    if owner_chat:
        default[f"telegram:{owner_chat}"] = {
            "tenant": "boss_hq",
            "user":   "eliyahu",
            "role":   Role.OWNER,
            "name":   "אליהו חזן"
        }
    return default


_REGISTRY: dict = _load_registry()


def resolve_identity(channel: str, chat_id: str) -> Identity:
    """מחזיר Identity לפי channel + chat_id."""
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

    logger.warning(f"Unknown identity: {key}")
    return Identity(
        tenant_id    = "unknown",
        user_id      = chat_id,
        role         = Role.READONLY,
        channel      = channel,
        chat_id      = chat_id,
        display_name = "Unknown",
    )
