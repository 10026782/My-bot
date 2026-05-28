# tool_registry.py — Tool Permission Enforcement

import logging

logger = logging.getLogger(__name__)


class ToolDenied(Exception):
    pass


def enforce(tool_name: str, identity) -> None:
    """
    מעלה ToolDenied אם לתפקיד של identity אין הרשאה לכלי tool_name.
    מייבא _ROLE_TOOLS מ-context בזמן ריצה כדי למנוע circular import.
    """
    from context import _ROLE_TOOLS
    allowed = _ROLE_TOOLS.get(identity.role, set())
    if tool_name not in allowed:
        logger.warning(f"Tool denied: {tool_name} for role {identity.role}")
        raise ToolDenied(f"❌ כלי '{tool_name}' אינו מורשה לתפקיד {identity.role.value}")
