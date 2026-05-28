import os


def get_airtable_base(tenant_id: str = "boss_hq"):
    return os.environ.get("AIRTABLE_BASE_ID", "")


def get_airtable_key(tenant_id: str = "boss_hq"):
    return os.environ.get("AIRTABLE_API_KEY", "")
