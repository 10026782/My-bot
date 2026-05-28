# contacts/aliases.py
import httpx
import logging
from tenant_config import get_airtable_base, get_airtable_key

logger = logging.getLogger(__name__)

BUILT_IN = {
    'עו"ד': {"Type":"Lawyer"}, "עורך דין": {"Type":"Lawyer"},
    'רו"ח': {"Type":"Accountant"}, "רואה חשבון": {"Type":"Accountant"},
    "ספק":  {"Type":"Supplier"},  "לקוח": {"Type":"Client"},
    "שותף": {"Type":"Partner"},
}

def resolve_alias(alias: str, tenant_id: str = "boss_hq") -> list[dict]:
    alias_l = alias.lower().strip()
    for key, filter_f in BUILT_IN.items():
        if key in alias_l:
            return _search(filter_f, tenant_id)
    return _search_nickname(alias, tenant_id)

def _search(filter_fields: dict, tenant_id: str) -> list[dict]:
    base_id = get_airtable_base(tenant_id)
    api_key = get_airtable_key(tenant_id)
    if not base_id or not api_key: return []
    conditions = " AND ".join([f"{{{k}}} = '{v}'" for k,v in filter_fields.items()])
    formula = f"AND({conditions}, {{Status}} = 'Active')"
    try:
        r = httpx.get(
            f"https://api.airtable.com/v0/{base_id}/Contacts",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"filterByFormula": formula}, timeout=10
        )
        r.raise_for_status()
        return [{"record_id":rec["id"],"name":rec["fields"].get("Name","?"),"score":8,"fields":rec["fields"]}
                for rec in r.json().get("records",[])]
    except Exception as e:
        logger.error(f"alias search: {e}")
        return []

def _search_nickname(alias: str, tenant_id: str) -> list[dict]:
    base_id = get_airtable_base(tenant_id)
    api_key = get_airtable_key(tenant_id)
    if not base_id or not api_key: return []
    formula = f"OR(FIND(LOWER('{alias}'),LOWER({{Nickname}})),FIND(LOWER('{alias}'),LOWER({{Tags}})))"
    try:
        r = httpx.get(
            f"https://api.airtable.com/v0/{base_id}/Contacts",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"filterByFormula": formula}, timeout=10
        )
        r.raise_for_status()
        return [{"record_id":rec["id"],"name":rec["fields"].get("Name","?"),"score":7,"fields":rec["fields"]}
                for rec in r.json().get("records",[])]
    except Exception as e:
        logger.error(f"nickname search: {e}")
        return []
