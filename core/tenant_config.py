# core/tenant_config.py
#
# F13 — TenantConfig
# שלב 1: hardcoded default + env override בלבד.
# שלב 3 (F08): loader יקרא מטבלת Tenants ב-Airtable.
#
# כלל: לא לייבא מודולים של providers כאן — circular import.
# כלל: get_tenant_config() חייב להיות synchronous.
# כלל: אפס Airtable calls בשלב זה.

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Literal

StorageProviderName  = Literal["airtable", "supabase", "hubspot", "postgres"]
LLMProviderName      = Literal["anthropic", "openai", "gemini"]
ChannelProviderName  = Literal["twilio", "meta_direct", "telegram"]


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: str
    storage_provider: StorageProviderName
    storage_base_id: str
    llm_provider: LLMProviderName
    llm_model_owner: str
    llm_model_default: str
    memory_max_messages: int        # -1 = ללא הגבלה
    memory_ttl_hours: int
    channel_provider: ChannelProviderName
    features: dict[str, bool] = field(default_factory=dict)
    allowed_tools: list[str] | None = None


def _default_tenant() -> TenantConfig:
    return TenantConfig(
        tenant_id="boss_hq",
        storage_provider="airtable",
        storage_base_id=os.environ.get("AIRTABLE_BASE_ID", ""),
        llm_provider="anthropic",
        llm_model_owner=os.environ.get("LLM_MODEL_OWNER", "claude-sonnet-4-6"),
        llm_model_default=os.environ.get("LLM_MODEL_DEFAULT", "claude-haiku-4-5-20251001"),
        memory_max_messages=int(os.environ.get("MEMORY_MAX_MESSAGES", "20")),
        memory_ttl_hours=int(os.environ.get("MEMORY_TTL_HOURS", "24")),
        channel_provider="twilio",
        features={},
        allowed_tools=None,
    )


_CACHE: dict[str, TenantConfig] = {}


def get_tenant_config(tenant_id: str = "boss_hq") -> TenantConfig:
    """
    שלב 1: תמיד boss_hq.
    שלב 3 (F08): lookup מטבלת Tenants + cache.
    """
    if tenant_id not in _CACHE:
        if tenant_id == "boss_hq":
            _CACHE[tenant_id] = _default_tenant()
        else:
            raise NotImplementedError(
                f"Tenant '{tenant_id}' not found. "
                "Multi-tenant loader not implemented yet (F08)."
            )
    return _CACHE[tenant_id]


def invalidate_tenant_cache(tenant_id: str | None = None) -> None:
    """שלב 3 — reload אחרי שינוי בטבלת Tenants."""
    if tenant_id:
        _CACHE.pop(tenant_id, None)
    else:
        _CACHE.clear()
