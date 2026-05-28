# contacts/resolver.py
import httpx
import logging
from tenant_config import get_airtable_base, get_airtable_key

logger = logging.getLogger(__name__)


def resolve_contact(name_query: str, tenant_id: str = "boss_hq") -> list[dict]:
    """
    מחפש איש קשר לפי שם חלקי.
    מחזיר: [{"record_id","name","score","fields"}, ...]
    """
    base_id = get_airtable_base(tenant_id)
    api_key = get_airtable_key(tenant_id)
    if not base_id or not api_key:
        return []
    try:
        r = httpx.get(
            f"https://api.airtable.com/v0/{base_id}/Contacts",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"filterByFormula": "{Status} = 'Active'"},
            timeout=10
        )
        r.raise_for_status()
        results = []
        query = name_query.lower().strip()
        for rec in r.json().get("records", []):
            f = rec.get("fields", {})
            score = _score(query, f)
            if score > 0:
                results.append({"record_id": rec["id"], "name": f.get("Name","?"), "score": score, "fields": f})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:5]
    except Exception as e:
        logger.error(f"resolve_contact: {e}")
        return []


def _score(query: str, f: dict) -> float:
    score = 0.0
    name    = f.get("Name","").lower()
    nick    = f.get("Nickname","").lower()
    tags    = f.get("Tags","").lower()
    company = f.get("Company","").lower()
    if name == query:             score += 10
    elif query in name:           score += 7
    elif name in query:           score += 5
    if nick and nick == query:    score += 9
    elif nick and query in nick:  score += 6
    if query in tags:             score += 4
    if query in company:          score += 3
    return score


def format_contact_choice(candidates: list[dict]) -> str:
    if not candidates:
        return "❌ לא נמצא איש קשר"
    if len(candidates) == 1:
        c = candidates[0]
        f = c["fields"]
        return (
            f"📋 *{c['name']}*\n"
            f"{'📞 ' + f.get('Phone','') if f.get('Phone') else ''}"
            f"{'  ✉️ ' + f.get('Email','') if f.get('Email') else ''}\n"
            f"ID: `{c['record_id']}`\n"
            f"מתכוון לאיש קשר הזה? ✅ / ❌"
        )
    lines = ["📋 *מצאתי כמה אפשרויות:*\n"]
    for i, c in enumerate(candidates, 1):
        company = c["fields"].get("Company","")
        lines.append(f"{i}. *{c['name']}*{' — ' + company if company else ''}")
    lines.append("\nאיזה מהם? (ענה 1/2/3...)")
    return "\n".join(lines)
