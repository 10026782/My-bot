import os

# Runtime overrides — set by TMA emergency stop, checked by bot before executing actions.
# These persist for the lifetime of the process only (cleared on restart).
_RUNTIME: dict[str, bool] = {}


def is_enabled(name: str) -> bool:
    if name in _RUNTIME:
        return _RUNTIME[name]
    value = os.environ.get(name, "").strip().lower()
    return value in ("1", "true", "yes", "on", "enabled")


def set_flag(name: str, value: bool) -> None:
    """Set a runtime feature flag (in-process only, not persisted across restarts)."""
    _RUNTIME[name] = value
