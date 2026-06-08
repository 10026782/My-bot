import os
import json
import logging

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
