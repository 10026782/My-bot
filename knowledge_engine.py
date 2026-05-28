# knowledge_engine.py
import os, httpx, logging
from feature_flags import is_enabled
from router import detect_topic

logger = logging.getLogger(__name__)
MAX_TOKENS = 12000

STATIC = """
אתה "הבוס בוט" — עוזר אסטרטגי עסקי.
גישה מלאה: Gmail, Drive, Calendar, Airtable, CRM.

חוקי ברזל:
1. מימון >9% — חסום | 2. מיילים — טיוטה בלבד
3. ייבוא: 30% מקדמה, 70% אחרי QC
4. פעולה בלתי הפיכה — בקש אישור
5. תזכורת תשלום — 3 ימים לפני
6. אל תמציא נתונים | 7. סכם ב"הצעד הבא"

כללים: עברית, קצר, כלים לפני ניחוש, ⚠️💡🚨
"""


class KnowledgeEngine:
    def build_context(self, tenant_id: str, user_message: str) -> str:
        if not is_enabled("KNOWLEDGE_ENGINE"):
            return STATIC
        parts, budget = [STATIC], MAX_TOKENS - self._tok(STATIC)

        rules = self._get(tenant_id, "adaptive_rules", {"active": "eq.true"}, limit=5)
        if rules and budget > 500:
            text = "\n⚡ כללים:\n" + "\n".join(f"• {r['rule']}" for r in rules)
            parts.append(text); budget -= self._tok(text)

        facts = self._get(tenant_id, "business_memory", {"active": "eq.true"}, limit=5)
        if facts and budget > 500:
            text = "\n📚 ידע:\n" + "\n".join(f"• {f['fact']}" for f in facts)
            parts.append(text); budget -= self._tok(text)

        topic = detect_topic(user_message)
        if topic in ("crm","finance") and budget > 500:
            deals = self._get(tenant_id, "deal_intelligence", {}, limit=5)
            if deals:
                won  = [d for d in deals if d.get("outcome")=="won"]
                lost = [d for d in deals if d.get("outcome")=="lost"]
                lines = ["\n💡 עסקאות:"]
                for d in won[:2]:  lines.append(f"  ✅ turning: {d.get('turning_point','?')}")
                for d in lost[:2]: lines.append(f"  ❌ סיבה: {d.get('reason','?')}")
                parts.append("\n".join(lines))

        return "\n".join(parts)

    def add_fact(self, tenant_id: str, fact: str, source: str = "manual") -> bool:
        if not is_enabled("SUPABASE"):
            logger.info(f"FACT: {fact}"); return True
        try:
            self._post("business_memory", {"tenant_id": tenant_id, "fact": fact, "source": source})
            return True
        except Exception as e:
            logger.error(f"add_fact: {e}"); return False

    def _get(self, tenant_id, table, params, limit=5) -> list:
        if not is_enabled("SUPABASE"): return []
        try:
            url = os.environ.get("SUPABASE_URL","")
            key = os.environ.get("SUPABASE_KEY","")
            r = httpx.get(f"{url}/rest/v1/{table}",
                headers={"apikey":key,"Authorization":f"Bearer {key}"},
                params={"tenant_id":f"eq.{tenant_id}","limit":str(limit),**params},
                timeout=5)
            return r.json() if r.status_code == 200 else []
        except: return []

    def _post(self, table, data):
        url = os.environ.get("SUPABASE_URL","")
        key = os.environ.get("SUPABASE_KEY","")
        httpx.post(f"{url}/rest/v1/{table}",
            headers={"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json=data, timeout=5)

    def _tok(self, text: str) -> int:
        return len(text) // 4


knowledge_engine = KnowledgeEngine()
