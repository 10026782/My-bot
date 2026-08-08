"""פתרון שם/רפרנס משימה, מוגבל וללא תופעות לוואי (bounded, side-effect-free).

TC5 הכליל את המימוש המקורי של המודול הזה לתוך ה-framework המשותף ב-
``core/router/entity_resolvers.py``. ``TaskLookup`` ו-``resolve_task``
מיוצאים מחדש כאן ללא שינוי כדי שקוד/טסטים קיימים לא יצטרכו לשנות את נתיב
ה-import שלהם או להבחין בהבדל התנהגות כלשהו.
"""

from __future__ import annotations

from core.router.entity_resolvers import TaskLookup, resolve_task

__all__ = ["TaskLookup", "resolve_task"]
