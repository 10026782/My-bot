# core/lead_events.py — Lead Event Store
#
# מספק LeadEventStore ל-learning_engine.py.
# קורא events מטבלת "Business Memory" ב-Airtable.
# אם הטבלה לא מוגדרת — מחזיר רשימה ריקה בשקט.

from __future__ import annotations
import json
import logging
import os

from core.query_contract import array_contains
from tools.airtable_read_adapter import AirtableReadError, list_records

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
        domain='real_estate' → מסנן לפי domain.
        """
        if not _AT_KEY or not _AT_BASE:
            logger.warning("[LeadEventStore] Airtable env vars not set — returning []")
            return []

        try:
            formula = ""
            if domain:
                formula = array_contains("keywords", domain)

            records = list_records(
                _TABLE,
                formula,
                limit=500,
                paginate=False,
                timeout=10,
            )

            events = []
            for rec in records:
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

        except AirtableReadError as e:
            if e.status_code is not None:
                logger.warning(
                    f"[LeadEventStore] Airtable {e.status_code}: {e.response_text[:120]}"
                )
            else:
                logger.error(f"[LeadEventStore] get_all error: {e.cause or e}")
            return []
        except Exception as e:
            logger.error(f"[LeadEventStore] get_all error: {e}")
            return []
