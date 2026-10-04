"""FCC Classify step: raw Hebrew text -> structured intent (LLM, no phrase parsing).

The model sees the caller's OWN goal titles only (passed in by the writer
caller), never other people's. Output is validated by ``writer.validate_intent``.
"""

from __future__ import annotations

import json
import re

_SYSTEM = (
    "אתה מסווג הודעות פיננסיות אישיות. החזר JSON בלבד, בלי טקסט נוסף, עם השדות: "
    "action (log_progress|set_target|create_goal|rename_goal|follow_up|note), "
    "goal_hint (שם היעד כפי שנאמר, או ריק), amount (מספר או null), target (מספר או null), "
    "kind (one_time|monthly_recurring או null), title, new_title, task_title, note. "
    "אל תמציא סכומים או יעדים שלא נאמרו. הכנסה/חיסכון חד-פעמי = one_time; "
    "שינוי קבוע בחודש (הוצאה שבוטלה, החזר שירד) = monthly_recurring."
)


def classify(text: str, goal_titles: list[str]) -> dict | None:
    from llm_fallback import call_anthropic_text
    out = call_anthropic_text(
        source="fcc_classify", model="claude-haiku-4-5-20251001", max_tokens=400, temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(
            {"text": text, "goal_titles": goal_titles}, ensure_ascii=False)}],
    )
    match = re.search(r"\{.*\}", out or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except ValueError:
        return None
