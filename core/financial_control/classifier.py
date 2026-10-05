"""FCC Classify step: raw Hebrew text -> structured intent (LLM, no phrase parsing).

The model sees the caller's OWN goal titles only (passed in by the writer
caller), never other people's. Output is validated by ``writer.validate_intent``.
"""

from __future__ import annotations

import json
import re
from datetime import date

_SYSTEM = (
    "אתה מסווג הודעות פיננסיות אישיות. החזר JSON בלבד, בלי טקסט נוסף, עם השדות: "
    "action (log_progress|set_target|create_goal|update_goal|rename_goal|follow_up|note), "
    "goal_hint (שם היעד כפי שנאמר, או ריק), amount (מספר או null), target (מספר או null), "
    "kind (one_time|monthly_recurring או null), title, new_title, task_title, note, category (אחד מ: income|savings|debt|emergency_fund, או טקסט חופשי אחר, או null), period_type (monthly|weekly|custom או null), calc_method (period_sum = סכום בתקופה, למשל הכנסה חודשית; cumulative = יתרה מצטברת מול יעד, למשל חיסכון/קרן חירום/סגירת חוב; recurring_level = שינוי קבוע בחודש, או null), start_date, end_date (YYYY-MM-DD או null; תאריך יחסי כמו ״סוף השנה״ חשב לפי היום שמסופק ב-today). update_goal = שינוי מאפייני יעד קיים (קטגוריה/תקופה/שיטה/תאריכים). "
    "אל תמציא סכומים או יעדים שלא נאמרו. הכנסה/חיסכון חד-פעמי = one_time; "
    "שינוי קבוע בחודש (הוצאה שבוטלה, החזר שירד) = monthly_recurring."
)


def classify(text: str, goal_titles: list[str]) -> dict | None:
    from llm_fallback import call_anthropic_text
    out = call_anthropic_text(
        source="fcc_classify", model="claude-haiku-4-5-20251001", max_tokens=400, temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(
            {"text": text, "goal_titles": goal_titles, "today": date.today().isoformat()}, ensure_ascii=False)}],
    )
    match = re.search(r"\{.*\}", out or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except ValueError:
        return None
