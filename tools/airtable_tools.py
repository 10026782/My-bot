# tools/airtable_tools.py
import os
import urllib.parse
import httpx
import logging
from airtable_schema import Tables
from guards.circuit_breaker import with_airtable_breaker

logger = logging.getLogger(__name__)


def _audit(tool_name: str, table: str, record_id: str = "", result: str = "") -> None:
    """לוג audit לכל פעולת Airtable — לא חוסם אם נכשל."""
    try:
        logger.info(
            "[AUDIT:airtable] tool=%s table=%s record=%s result=%s",
            tool_name, table, record_id or "-", (result or "")[:80],
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════
# סכמה — שדות חוקיים לכל טבלה
# Claude לא ישלח שדות שלא קיימים ב-Airtable
# ══════════════════════════════════════════════════

_TABLE_FIELDS: dict[str, set[str]] = {
    Tables.TASKS: {
        "כותרת המשימה", "תיאור", "תאריך יעד", "סטטוס",
        "מקושר לאנשי קשר", "מקושר לעסקאות",
        "Domain", "Owner", "Leads",
    },
    Tables.CONTACTS: {
        "שם", "חברה", "אימייל", "טלפון", "תאריך פולו אפ",
        "סטטוס", "עסקאות (Deals)", "משימות (Tasks)",
    },
    Tables.DEALS: {
        "שם העסקה", "סכום", "שלב", "תאריך סגירה",
        "מקושר לאנשי קשר", "משימות (Tasks)", "תשלומים (Payments)",
    },
    Tables.EXPENSES: {
        "שם ההוצאה", "סכום", "קטגוריה", "תאריך",
    },
    Tables.PAYMENTS: {
        "אסמכתא", "סכום", "תאריך", "סטטוס", "מקושר לעסקאות",
    },
    Tables.DEADLINES: {
        "שם המשימה", "סטטוס", "תאריך דדליין", "אחראי",
        "תיאור המשימה", "עדיפות", "קישור לרשומת מכירה/יחידה", "הערות",
    },
    # ── Leads — lowercase keys כפי שנוצרו ב-Airtable ──
    "Leads": {
        "Score",
        "Name", "phone", "status",
        "summary", "answers", "source", "channel",
        "created_at", "updated_at", "memory_key", "tenant_id", "domain",
        "notes", "next_step", "Next Action", "tier", "Temperature",
        "utm_source", "utm_medium", "utm_campaign", "platform",
        "deal_value", "converted_at", "campaign_source",
        "Business Outcome", "Next Followup", "Owner",
    },
    # ── Projects / Units ──────────────────────────
    "Projects": {
        "Project Name", "Location", "Status", "Total Units",
        "Project Type", "Start Date", "End Date",
        "Total Cost", "Total Revenue", "Project Manager",
        "Primary Lender", "Notes",
    },
    "Units": {
        "Unit Number", "Project", "Type", "Size (sqft)", "Price",
        "Status", "Floor", "Bedrooms", "Bathrooms", "Features",
        "Owner/Tenant", "Availability Date", "Notes", "Sale Price (NIS)",
    },
    "Loans": {
        "Loan Name/ID", "Project", "Lender", "Loan Amount",
        "Interest Rate (%)", "Term (months)", "Start Date", "End Date",
        "Payment Schedule", "Outstanding Balance",
        "Next Payment Due", "Payment Status", "Notes",
    },
    # ── Roadmap / Boss-Game ───────────────────────
    "Roadmap_Tasks": {
        "Task", "World", "Quest", "Owner", "Priority",
        "Status", "Due_Date", "Estimated_Hours", "Coins", "Blocker", "Notes",
    },
    "Weekly_Goals": {
        "Goal", "World", "Target_Date", "Status",
    },
    "Boss_Battles": {
        "Week", "Week_Start", "Question", "Answer", "Status", "Coins_Earned",
    },
    "Daily_Tasks": {
        "Date", "Task", "Quest", "Coins", "Status", "Who",
    },
    "Worlds": {
        "Name", "Number", "Status", "Boss", "Prize",
        "Total_Coins_Target", "Coins_Earned", "Start_Date", "End_Date", "Notes",
    },
    "Quests": {
        "Name", "World", "Status", "Coins", "Week_Start", "Impact", "Done_By", "Notes",
    },
    "Coins_Log": {
        "Action", "Coins", "Date", "Quest", "Note",
    },
}

# שדות שClaude ממציא ולא קיימים בשום טבלה
_ALWAYS_FORBIDDEN = {"tenant", "owner_id", "user_id", "chat_id"}

# _TABLE_ALIAS_MAP מיובא מ-airtable_schema — מקור אמת יחיד
from airtable_schema import TABLE_ALIASES as _TABLE_ALIAS_MAP


def _resolve_table(table: str) -> str:
    """מתרגם alias אנגלי לשם הטבלה האמיתי ב-Airtable."""
    return _TABLE_ALIAS_MAP.get(table, table)


# שדות linked-record לפי טבלה: field_name → linked_table_name
_LINKED_RECORD_FIELDS: dict[str, dict[str, str]] = {
    "Roadmap_Tasks": {
        "World": "Worlds",
        "Quest": "Quests",
    },
    "Weekly_Goals": {
        "World": "Worlds",
    },
    "Daily_Tasks": {
        "Quest": "Quests",
    },
    "Quests": {
        "World": "Worlds",
    },
    "Coins_Log": {
        "Quest": "Quests",
    },
}


def _lookup_record_id(linked_table: str, name: str) -> str | None:
    """
    מחפש רשומה לפי שם ב-linked_table.
    מחזיר record_id ("recXXX") אם נמצא, אחרת None.
    """
    try:
        safe = name.replace("'", "\\'")
        encoded = urllib.parse.quote(linked_table, safe="")
        r = httpx.get(
            f"https://api.airtable.com/v0/{_base()}/{encoded}",
            headers=_headers(),
            params={"filterByFormula": f"{{Name}}='{safe}'", "maxRecords": 1},
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning(f"airtable: lookup failed [{linked_table}] {r.status_code}")
            return None
        records = r.json().get("records", [])
        if records:
            return records[0]["id"]
        return None
    except Exception as e:
        logger.warning(f"airtable: lookup exception [{linked_table}/{name}]: {e}")
        return None


def _resolve_linked_fields(table: str, fields: dict) -> dict:
    """
    עבור טבלאות עם שדות linked-record:
    אם הערך הוא string (שם תצוגה) במקום ["recXXX"] — מבצע חיפוש ומחליף.
    שדות שלא נמצאו מוסרים כדי למנוע INVALID_RECORD_ID.
    """
    link_map = _LINKED_RECORD_FIELDS.get(table)
    if not link_map:
        return fields

    result = dict(fields)
    for field, linked_table in link_map.items():
        val = result.get(field)
        if val is None:
            continue
        # כבר בפורמט נכון — list של IDs
        if isinstance(val, list):
            continue
        # ערך string — צריך לחפש
        if isinstance(val, str):
            rec_id = _lookup_record_id(linked_table, val)
            if rec_id:
                result[field] = [rec_id]
                logger.info(f"airtable: resolved {field}='{val}' → {rec_id}")
            else:
                logger.warning(
                    f"airtable: '{val}' לא נמצא ב-{linked_table} — שדה {field} הוסר"
                )
                del result[field]
    return result


def _sanitize_fields(table: str, fields: dict) -> dict:
    """
    מסנן שדות:
    1. הסרת שדות אסורים תמיד (tenant_id וכו')
    2. אם הטבלה ידועה — מסנן רק לשדות בסכמה
    מחזיר dict נקי + מוגיש לוג על מה הוסר.
    """
    # שלב 1 — הסרת forbidden
    cleaned = {k: v for k, v in fields.items() if k not in _ALWAYS_FORBIDDEN}
    removed_forbidden = set(fields) - set(cleaned)
    if removed_forbidden:
        logger.warning(f"airtable: הוסרו שדות אסורים: {removed_forbidden}")

    # שלב 2 — סינון לפי סכמה אם קיימת
    allowed = _TABLE_FIELDS.get(_resolve_table(table))
    if allowed:
        valid   = {k: v for k, v in cleaned.items() if k in allowed}
        invalid = set(cleaned) - set(valid)
        if invalid:
            logger.warning(f"airtable[{table}]: שדות לא מוכרים הוסרו: {invalid}")
        return valid

    return cleaned


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('AIRTABLE_API_KEY', '')}",
        "Content-Type":  "application/json"
    }

def _base() -> str:
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    if not base:
        raise RuntimeError("AIRTABLE_BASE_ID לא מוגדר")
    return base


def airtable_get(table: str, filter_formula: str = "") -> str:
    real_table = _resolve_table(table)
    with with_airtable_breaker():
        params = {}
        if filter_formula:
            params["filterByFormula"] = filter_formula
        encoded = urllib.parse.quote(real_table, safe="")
        r = httpx.get(f"https://api.airtable.com/v0/{_base()}/{encoded}",
                      headers=_headers(), params=params, timeout=10)
        if r.status_code != 200:
            return f"❌ Airtable error {r.status_code}: {r.text[:150]}"
        records = r.json().get("records", [])
        if not records:
            _audit("airtable_get", table, result=f"0 records | filter={filter_formula[:40]}")
            return f"📭 אין רשומות בטבלה '{table}'."
        result = f"📊 {table} — {len(records)} רשומות:\n"
        for rec in records[:15]:
            fields = " | ".join(f"{k}: {v}" for k, v in rec.get("fields", {}).items())
            result += f"• [{rec['id']}] {fields}\n"
        _audit("airtable_get", table, result=f"{len(records)} records | filter={filter_formula[:40]}")
        return result


def airtable_add(table: str, fields: dict) -> str:
    fields = _resolve_linked_fields(_resolve_table(table), fields)
    from tools.airtable_gateway import airtable_create
    rec = airtable_create(_resolve_table(table), fields, source="agent")
    if rec:
        rec_id = rec.get("id", "?")
        _audit("airtable_add", table, record_id=rec_id, result="created")
        return f"✅ רשומה נוספה | ID: {rec_id}"
    _audit("airtable_add", table, result="error")
    return "❌ לא נשארו שדות תקינים לשמירה — בדוק שמות השדות."


def airtable_get_schema() -> str:
    """קורא את כל הטבלאות והשדות מ-Airtable Meta API בזמן אמת."""
    with with_airtable_breaker():
        base = _base()
        r = httpx.get(
            f"https://api.airtable.com/v0/meta/bases/{base}/tables",
            headers=_headers(),
            timeout=10
        )
        if r.status_code != 200:
            _audit("airtable_get_schema", "meta", result=f"error {r.status_code}")
            return f"❌ Meta API error {r.status_code}: {r.text[:150]}"
        tables = r.json().get("tables", [])
        if not tables:
            return "📭 לא נמצאו טבלאות בבסיס הנתונים."
        result = f"📊 נמצאו {len(tables)} טבלאות:\n\n"
        for t in tables:
            fields = [f["name"] for f in t.get("fields", [])]
            result += f"• {t['name']}\n"
            result += f"  שדות: {', '.join(fields)}\n\n"
        _audit("airtable_get_schema", "meta", result=f"{len(tables)} tables fetched")
        return result.strip()


def airtable_update(table: str, record_id: str, fields: dict) -> str:
    fields = _resolve_linked_fields(_resolve_table(table), fields)
    from tools.airtable_gateway import airtable_patch
    ok = airtable_patch(_resolve_table(table), record_id, fields, source="agent")
    if ok:
        _audit("airtable_update", table, record_id=record_id, result="updated")
        return f"✅ רשומה {record_id} עודכנה."
    _audit("airtable_update", table, record_id=record_id, result="error")
    return "❌ שגיאה בעדכון — בדוק שמות השדות."


def search_lead(name: str) -> str:
    """חיפוש ליד לפי שם חלקי — SEARCH formula של Airtable."""
    safe = name.replace("'", "\\'")
    return airtable_get("Leads", f"SEARCH('{safe}', {{Name}})")
