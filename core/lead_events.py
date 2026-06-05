# core/lead_events.py — Lead Event Store
#
# מספק LeadEventStore ל-learning_engine.py.
# קורא events מטבלת "Business Memory" ב-Airtable.
# אם הטבלה לא מוגדרת — מחזיר רשימה ריקה בשקט.

from __future__ import annotations
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_AT_KEY  = os.environ.get("AIRTABLE_API_KEY", "")
_AT_BASE = os.environ.get("AIRTABLE_BASE_ID", "")
_TABLE   = "Business Memory"


class LeadEventStore:
    """
    מאגר events ממוסד של לידים — נקרא על-ידי learning_engine.
    Schema מינימלי: כל record עם שדה 'keywords' שמכיל JSON list.
    domain, type, memory_key נחלצים מה-keywords / שדות ישירים.
    """

    def get_all(self, domain: str | None = None) -> list[dict]:
        """
        מחזיר events (dicts) מ-Business Memory.
        domain=None → כל ה-events.
        domain='realestate' → מסנן לפי domain.
        """
        if not _AT_KEY or not _AT_BASE:
            logger.warning("[LeadEventStore] Airtable env vars not set — returning []")
            return []

        try:
            url    = f"https://api.airtable.com/v0/{_AT_BASE}/{_TABLE}"
            params: dict = {"maxRecords": 500}
            if domain:
                params["filterByFormula"] = f"FIND('{domain}', ARRAYJOIN({{keywords}}))"

            r = httpx.get(
                url,
                headers={"Authorization": f"Bearer {_AT_KEY}"},
                params=params,
                timeout=10,
            )
            if r.status_code != 200:
                logger.warning(f"[LeadEventStore] Airtable {r.status_code}: {r.text[:120]}")
                return []

            events = []
            for rec in r.json().get("records", []):
                f = rec.get("fields", {})
                # נסה לחלץ keywords מ-JSON
                try:
                    keywords = json.loads(f.get("keywords", "[]") or "[]")
                except (json.JSONDecodeError, TypeError):
                    keywords = []

                event: dict = {
                    "type":       f.get("type", "message"),
                    "domain":     f.get("domain", domain or ""),
                    "memory_key": f.get("memory_key", rec.get("id", "")),
                    "content":    f.get("summary", ""),
                    "keywords":   keywords,
                }
                events.append(event)

            logger.info(f"[LeadEventStore] loaded {len(events)} events (domain={domain or 'all'})")
            return events

        except Exception as e:
            logger.error(f"[LeadEventStore] get_all error: {e}")
            return []
