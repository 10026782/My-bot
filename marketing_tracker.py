# marketing_tracker.py
import logging
import os
from datetime import datetime

import httpx

from feature_flags import is_enabled

logger = logging.getLogger(__name__)


def log_lead_source(
    tenant_id: str,
    source: str,
    lead_type: str = "cold",
    campaign: str = "",
):
    """
    source: website | facebook | google | referral | cold | telegram
    lead_type: hot | cold
    """
    if is_enabled("SUPABASE"):
        try:
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_KEY", "")
            httpx.post(
                f"{url}/rest/v1/marketing_intelligence",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "tenant_id": tenant_id,
                    "source": source,
                    "lead_type": lead_type,
                    "campaign_name": campaign,
                    "leads_count": 1,
                    "created_at": datetime.now().isoformat(),
                },
                timeout=5,
            )
        except Exception as e:
            logger.error(f"log_lead_source: {e}")
    logger.info(f"Lead: {source} | {lead_type} | {campaign}")


def get_roi_report(tenant_id: str) -> str:
    if not is_enabled("SUPABASE"):
        return "💡 מעקב ROI יהיה זמין אחרי חיבור Supabase"
    try:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        r = httpx.get(
            f"{url}/rest/v1/marketing_intelligence",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"tenant_id": f"eq.{tenant_id}", "order": "roi.desc"},
            timeout=5,
        )
        data = r.json()
        if not data:
            return "📊 אין עדיין נתוני שיווק"
        lines = ["📊 *ROI לפי מקור:*\n"]
        for m in data:
            leads = m.get("leads_count", 0)
            closed = m.get("closed_count", 0)
            rate = round(closed / leads * 100) if leads > 0 else 0
            lines.append(
                f"• *{m.get('source','?')}*: {leads} לידים | "
                f"{closed} סגירות ({rate}%) | "
                f"CPL: ₪{m.get('cpl',0):,.0f}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_roi_report: {e}")
        return "❌ שגיאה בטעינת נתוני ROI"
