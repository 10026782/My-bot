"""Smart Trips — מנוע כדאיות נסיעות ומיון תחנות. חישוב טהור, לא מחובר ל-app.py, ל-API, ל-Airtable או לספק בתשלום."""

from .compare import compare
from .models import ENGINE_VERSION
from .stops import order_stops

__all__ = ["ENGINE_VERSION", "compare", "order_stops"]
