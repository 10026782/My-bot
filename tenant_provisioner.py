# tenant_provisioner.py — F08 SaaS Multi-Tenant
# קובץ: tenant_provisioner.py (flat, root)
# flag: MULTITENANT (env: MULTITENANT=true)
#
# מה זה עושה:
#   provision_tenant()  — מוסיף לקוח עסקי חדש (tenant) למערכת
#   list_tenants()      — רשימת כל הtenants הפעילים
#   suspend_tenant()    — השעיית tenant
#   get_tenant_config() — קריאת config של tenant ספציפי
#
# מה כבר קיים ולא צריך לבנות:
#   identity.py     — tenant_id, roles, permissions ✅
#   airtable_security.py — tenant isolation ✅
#   dispatcher.py   — tenant_id injection לכל רשומה ✅
#
# מה F08 מוסיף:
#   1. Tenant Registry (Airtable Tenants table)
#   2. IDENTITY_MAP generator — מייצר JSON לenv var
#   3. Template selection — איזה domain_prompts לtenant
#   4. Usage tracking — כמה API calls לפי tenant
#
# מודל עסקי: White-Label BOSS לעסקים אחרים.
# כל tenant = Airtable base נפרד + IDENTITY_MAP entry.

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Templates — מה הבוט יודע לעשות לפי סוג עסק
# ══════════════════════════════════════════════════

TENANT_TEMPLATES = {
    "real_estate": {
        "label":       "נדל\"ן",
        "domains":     ["real_estate", "finance"],
        "description": "ניהול לידים, עסקאות, תשלומים ונכסים",
        "features":    ["lead_qualifier", "payment_reminders", "daily_digest"],
    },
    "import": {
        "label":       "ייבוא וסחר",
        "domains":     ["import", "finance"],
        "description": "ניהול ספקים, הזמנות, משלוחים ותשלומים",
        "features":    ["lead_qualifier", "payment_reminders", "daily_digest"],
    },
    "services": {
        "label":       "שירותים מקצועיים",
        "domains":     ["general", "finance"],
        "description": "ניהול לקוחות, פגישות ומשימות",
        "features":    ["lead_qualifier", "daily_digest", "followup_automation"],
    },
    "recruitment": {
        "label":       "גיוס עובדים",
        "domains":     ["general"],
        "description": "ניהול מועמדים, ראיונות ותהליכי גיוס",
        "features":    ["lead_qualifier", "followup_automation"],
    },
}


# ══════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════

@dataclass
class TenantConfig:
    tenant_id:     str
    business_name: str
    template:      str          # real_estate / import / services / recruitment
    owner_name:    str
    owner_phone:   str          # מספר טלגרם chat_id של owner
    owner_channel: str = "telegram"
    airtable_base: str = ""     # Base ID נפרד לtenant
    plan:          str = "basic"  # basic / pro / enterprise
    status:        str = "active" # active / suspended / trial
    created_at:    str = ""
    domains:       list = field(default_factory=list)
    features:      list = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = date.today().isoformat()
        if not self.domains and self.template in TENANT_TEMPLATES:
            self.domains  = TENANT_TEMPLATES[self.template]["domains"]
            self.features = TENANT_TEMPLATES[self.template]["features"]


@dataclass
class ProvisionResult:
    ok:           bool
    tenant_id:    str
    identity_entry: dict = field(default_factory=dict)
    env_snippet:  str = ""
    error:        str = ""


# ══════════════════════════════════════════════════
# 1. Provision Tenant
# ══════════════════════════════════════════════════

def provision_tenant(config: TenantConfig) -> ProvisionResult:
    """
    מוסיף tenant חדש:
    1. שומר ב-Airtable Tenants table
    2. מייצר IDENTITY_MAP entry
    3. מחזיר env snippet להדבקה ב-Render
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("MULTITENANT"):
            return ProvisionResult(
                ok=False, tenant_id=config.tenant_id,
                error="MULTITENANT flag is OFF",
            )
    except ImportError:
        pass  # dev mode

    # ── שמירה ב-Airtable ──────────────────────────
    saved = _save_tenant_to_airtable(config)
    if not saved:
        logger.warning(f"[Tenant] Airtable save failed for {config.tenant_id} — continuing")

    # ── בניית IDENTITY_MAP entry ──────────────────
    identity_key   = f"{config.owner_channel}:{config.owner_phone}"
    identity_entry = {
        "tenant":  config.tenant_id,
        "user":    "owner",
        "role":    "owner",
        "name":    config.owner_name,
        "domains": config.domains,
    }

    # ── env snippet ───────────────────────────────
    env_snippet = _build_env_snippet(config, identity_key, identity_entry)

    logger.info(
        f"[Tenant] ✅ Provisioned: {config.tenant_id} | "
        f"template={config.template} | owner={config.owner_name}"
    )

    return ProvisionResult(
        ok             = True,
        tenant_id      = config.tenant_id,
        identity_entry = {identity_key: identity_entry},
        env_snippet    = env_snippet,
    )


def _save_tenant_to_airtable(config: TenantConfig) -> bool:
    """שומר tenant ל-Airtable Tenants table."""
    try:
        from tools.airtable_tools import airtable_add  # type: ignore

        fields = {
            "tenant_id":     config.tenant_id,
            "Name":          config.business_name,
            "template":      config.template,
            "owner_name":    config.owner_name,
            "owner_phone":   config.owner_phone,
            "plan":          config.plan,
            "status":        config.status,
            "created_at":    config.created_at,
            "airtable_base": config.airtable_base,
            "domains":       ",".join(config.domains),
            "features":      ",".join(config.features),
        }
        result = airtable_add("Tenants", fields)
        return bool(result.get("ok"))

    except ImportError:
        logger.debug("[Tenant] airtable_tools not available — dry-run")
        return False
    except Exception as e:
        logger.error(f"[Tenant] _save_tenant_to_airtable: {e}")
        return False


def _build_env_snippet(
    config: TenantConfig,
    identity_key: str,
    identity_entry: dict,
) -> str:
    """מייצר env snippet מוכן להדבקה ב-Render."""
    current_map_str = os.environ.get("IDENTITY_MAP", "{}")
    try:
        current_map = json.loads(current_map_str)
    except Exception:
        current_map = {}

    current_map[identity_key] = identity_entry
    new_map_json = json.dumps(current_map, ensure_ascii=False)

    lines = [
        f"# ── Tenant: {config.business_name} ({config.tenant_id}) ──",
        f"# הוסף/עדכן ב-Render → Environment Variables:",
        f"IDENTITY_MAP={new_map_json}",
    ]

    if config.airtable_base:
        lines.append(f"# Airtable Base: {config.airtable_base}")

    template_info = TENANT_TEMPLATES.get(config.template, {})
    if template_info.get("features"):
        for feat in template_info["features"]:
            lines.append(f"FEATURE_{feat.upper()}=true")

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# 2. List Tenants
# ══════════════════════════════════════════════════

def list_tenants() -> str:
    """מחזיר string מפורמט של כל הtenants."""
    try:
        from tools.airtable_tools import airtable_get  # type: ignore
        raw = airtable_get("Tenants", "")
        if "אין רשומות" in raw or "error" in raw.lower():
            return "📭 אין tenants רשומים."
        return f"🏢 *Tenants פעילים:*\n{raw}"

    except ImportError:
        return _mock_list_tenants()
    except Exception as e:
        return f"❌ שגיאה: {e}"


def _mock_list_tenants() -> str:
    return (
        "🏢 *Tenants (mock):*\n"
        "• boss_hq | אליהו חזן | נדל\"ן + ייבוא | active\n"
        "• client_001 | דני כהן נדל\"ן | נדל\"ן | trial"
    )


# ══════════════════════════════════════════════════
# 3. Suspend / Reactivate
# ══════════════════════════════════════════════════

def suspend_tenant(tenant_id: str) -> str:
    """משעה tenant — מונע גישה."""
    try:
        from tools.airtable_tools import airtable_get, airtable_update  # type: ignore

        records = airtable_get("Tenants", f"{{tenant_id}}='{tenant_id}'")
        if "אין רשומות" in records:
            return f"❌ tenant '{tenant_id}' לא נמצא."

        import re
        m = re.search(r'\[(rec\w+)\]', records)
        if not m:
            return "❌ לא נמצא record_id."

        result = airtable_update("Tenants", m.group(1), {"status": "suspended"})
        if not result.get("ok"):
            logger.warning(f"[Tenant] Suspend failed: {tenant_id} — {result.get('user_message', result)}")
            return f"❌ השעיית tenant '{tenant_id}' נכשלה."
        logger.warning(f"[Tenant] Suspended: {tenant_id}")
        return f"⏸ Tenant '{tenant_id}' הושעה."

    except ImportError:
        return f"[DRY-RUN] suspend tenant: {tenant_id}"
    except Exception as e:
        return f"❌ שגיאה: {e}"


# ══════════════════════════════════════════════════
# 4. Get Tenant Config
# ══════════════════════════════════════════════════

def get_tenant_config(tenant_id: str) -> Optional[dict]:
    """קורא config של tenant ספציפי מAirtable."""
    try:
        from tools.airtable_tools import airtable_get  # type: ignore
        records = airtable_get("Tenants", f"{{tenant_id}}='{tenant_id}'")
        if "אין רשומות" in records or "❌" in records:
            return None
        return {"tenant_id": tenant_id, "raw": records}
    except Exception:
        return None


# ══════════════════════════════════════════════════
# 5. Usage Tracking (lightweight)
# ══════════════════════════════════════════════════

_usage: dict[str, dict] = {}   # tenant_id → {calls, tokens}


def track_usage(tenant_id: str, tokens: int = 0):
    """מעקב usage per tenant (RAM — עתידי: Airtable/DB)."""
    if tenant_id not in _usage:
        _usage[tenant_id] = {"calls": 0, "tokens": 0, "date": date.today().isoformat()}
    _usage[tenant_id]["calls"]  += 1
    _usage[tenant_id]["tokens"] += tokens


def get_usage_report() -> str:
    """דוח usage לכל הtenants."""
    if not _usage:
        return "📊 אין נתוני usage."
    lines = ["📊 *Usage Report:*\n"]
    for tid, data in _usage.items():
        lines.append(
            f"• *{tid}* | calls={data['calls']} | "
            f"tokens={data['tokens']:,} | {data['date']}"
        )
    return "\n".join(lines)


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc: str, cond: bool):
        nonlocal passed, failed
        if cond:
            print(f"✅ {desc}"); passed += 1
        else:
            print(f"❌ {desc}"); failed += 1

    # ── TenantConfig defaults ─────────────────────
    tc = TenantConfig(
        tenant_id     = "client_test",
        business_name = "דני כהן נדל\"ן",
        template      = "real_estate",
        owner_name    = "דני כהן",
        owner_phone   = "123456789",
    )
    chk("TenantConfig created",         isinstance(tc, TenantConfig))
    chk("domains auto-filled",          "real_estate" in tc.domains)
    chk("features auto-filled",         len(tc.features) > 0)
    chk("created_at auto-filled",       len(tc.created_at) == 10)
    chk("default status=active",        tc.status == "active")

    # ── TENANT_TEMPLATES ──────────────────────────
    chk("4 templates defined",          len(TENANT_TEMPLATES) == 4)
    chk("real_estate template exists",   "real_estate" in TENANT_TEMPLATES)
    chk("import template has domains",  "import" in TENANT_TEMPLATES["import"]["domains"])

    # ── _build_env_snippet ───────────────────────
    snippet = _build_env_snippet(
        tc,
        "telegram:123456789",
        {"tenant": "client_test", "user": "owner", "role": "owner",
         "name": "דני כהן", "domains": tc.domains},
    )
    chk("env_snippet not empty",        len(snippet) > 10)
    chk("env_snippet has IDENTITY_MAP", "IDENTITY_MAP=" in snippet)
    chk("env_snippet has tenant_id",    "client_test" in snippet)
    chk("env_snippet has feature flags", "FEATURE_" in snippet)

    # ── provision_tenant — flag OFF ───────────────
    import sys, types, importlib.util
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff
    at = types.ModuleType("airtable_tools")
    sys.modules["airtable_tools"] = at

    spec = importlib.util.spec_from_file_location("tenant_provisioner", __file__)
    tp   = importlib.util.module_from_spec(spec)
    sys.modules["tenant_provisioner"] = tp
    spec.loader.exec_module(tp)

    r = tp.provision_tenant(tp.TenantConfig(
        tenant_id="test", business_name="Test", template="services",
        owner_name="Test", owner_phone="000",
    ))
    chk("flag=OFF → ok=False",          r.ok is False)
    chk("flag=OFF → error message",     "flag" in r.error.lower() or "off" in r.error.lower())

    # flag ON
    ff.is_enabled = lambda x: True
    r2 = tp.provision_tenant(tp.TenantConfig(
        tenant_id="client_001", business_name="דני כהן נדל\"ן",
        template="real_estate", owner_name="דני", owner_phone="987654321",
    ))
    chk("flag=ON → ok=True",            r2.ok is True)
    chk("flag=ON → tenant_id",          r2.tenant_id == "client_001")
    chk("flag=ON → has identity_entry", len(r2.identity_entry) > 0)
    chk("flag=ON → has env_snippet",    "IDENTITY_MAP" in r2.env_snippet)

    # ── usage tracking ────────────────────────────
    tp.track_usage("client_001", tokens=500)
    tp.track_usage("client_001", tokens=300)
    report = tp.get_usage_report()
    chk("usage tracked",                "client_001" in report)
    chk("usage calls=2",                "calls=2" in report)
    chk("usage tokens=800",             "800" in report)

    # ── list_tenants mock ─────────────────────────
    listing = tp.list_tenants()
    chk("list_tenants returns string",  isinstance(listing, str) and len(listing) > 0)

    print(f"\n{'='*40}")
    print(f"F08 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
