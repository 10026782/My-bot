# tools/airtable_tools.py
import os
import urllib.parse
import httpx
import logging
from guards.circuit_breaker import with_airtable_breaker

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# סכמה — שדות חוקיים לכל טבלה
# Claude לא ישלח שדות שלא קיימים ב-Airtable
# ══════════════════════════════════════════════════

_TABLE_FIELDS: dict[str, set[str]] = {
    # ── alias keys (what Claude sends) ────────────
    "Tasks": {
        "כותרת המשימה", "תיאור", "תאריך יעד", "סטטוס",
        "מקושר לאנשי קשר", "מקושר לעסקאות",
    },
    "Contacts": {
        "שם", "חברה", "אימייל", "טלפון", "תאריך פולו אפ",
        "סטטוס", "עסקאות (Deals)", "משימות (Tasks)",
    },
    "Deals": {
        "שם העסקה", "סכום", "שלב", "תאריך סגירה",
        "מקושר לאנשי קשר", "משימות (Tasks)", "תשלומים (Payments)",
    },
    "Expenses": {
        "שם ההוצאה", "סכום", "קטגוריה", "תאריך",
    },
    "Payments": {
        "אסמכתא", "סכום", "תאריך", "סטטוס", "מקושר לעסקאות",
    },
    "Deadlines": {
        "שם המשימה", "סטטוס", "תאריך דדליין", "אחראי",
        "תיאור המשימה", "עדיפות", "קישור לרשומת מכירה/יחידה", "הערות",
    },
    # ── Leads — lowercase keys כפי שנוצרו ב-Airtable ──
    "Leads": {
        "Name", "phone", "status", "score ציון",
        "summary", "answers", "source", "channel",
        "created_at", "memory_key", "tenant_id", "domain",
        "notes", "next_step", "tier", "Temperature",
        "utm_source", "utm_medium", "utm_campaign", "platform",
        "deal_value", "converted_at", "campaign_source",
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
}

# שדות שClaude ממציא ולא קיימים בשום טבלה
_ALWAYS_FORBIDDEN = {"tenant", "owner_id", "user_id", "chat_id"}

# מיפוי שמות ידידותיים → שמות אמיתיים ב-Airtable
# מאפשר ל-Claude להשתמש בשמות אנגליים קצרים
_TABLE_ALIAS_MAP: dict[str, str] = {
    "Tasks":    "משימות (Tasks)",
    "Contacts": "אנשי קשר (Contacts)",
    "Deals":    "עסקאות (Deals)",
    "Expenses": "הוצאות (Expenses)",
    "Payments": "תשלומים (Payments)",
}


def _resolve_table(table: str) -> str:
    """מתרגם alias אנגלי לשם הטבלה האמיתי ב-Airtable."""
    return _TABLE_ALIAS_MAP.get(table, table)


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
    allowed = _TABLE_FIELDS.get(table)
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
            return f"📭 אין רשומות בטבלה '{table}'."
        result = f"📊 {table} — {len(records)} רשומות:\n"
        for rec in records[:15]:
            fields = " | ".join(f"{k}: {v}" for k, v in rec.get("fields", {}).items())
            result += f"• [{rec['id']}] {fields}\n"
        return result


def airtable_add(table: str, fields: dict) -> str:
    fields = _sanitize_fields(table, fields)
    if not fields:
        return "❌ לא נשארו שדות תקינים לשמירה — בדוק שמות השדות."
    real_table = _resolve_table(table)
    encoded = urllib.parse.quote(real_table, safe="")
    with with_airtable_breaker():
        r = httpx.post(f"https://api.airtable.com/v0/{_base()}/{encoded}",
                       headers=_headers(), json={"fields": fields}, timeout=10)
        if r.status_code in [200, 201]:
            return f"✅ רשומה נוספה | ID: {r.json().get('id','?')}"
        return f"❌ Airtable error {r.status_code}: {r.text[:150]}"


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
            return f"❌ Meta API error {r.status_code}: {r.text[:150]}"
        tables = r.json().get("tables", [])
        if not tables:
            return "📭 לא נמצאו טבלאות בבסיס הנתונים."
        result = f"📊 נמצאו {len(tables)} טבלאות:\n\n"
        for t in tables:
            fields = [f["name"] for f in t.get("fields", [])]
            result += f"• {t['name']}\n"
            result += f"  שדות: {', '.join(fields)}\n\n"
        return result.strip()


def airtable_update(table: str, record_id: str, fields: dict) -> str:
    fields = _sanitize_fields(table, fields)
    if not fields:
        return "❌ לא נשארו שדות תקינים לעדכון — בדוק שמות השדות."
    real_table = _resolve_table(table)
    encoded = urllib.parse.quote(real_table, safe="")
    with with_airtable_breaker():
        r = httpx.patch(f"https://api.airtable.com/v0/{_base()}/{encoded}/{record_id}",
                        headers=_headers(), json={"fields": fields}, timeout=10)
        if r.status_code == 200:
            return f"✅ רשומה {record_id} עודכנה."
        return f"❌ Airtable error {r.status_code}: {r.text[:150]}"


def search_lead(name: str) -> str:
    """חיפוש ליד לפי שם חלקי — SEARCH formula של Airtable."""
    safe = name.replace("'", "\\'")
    return airtable_get("Leads", f"SEARCH('{safe}', {{Name}})")
