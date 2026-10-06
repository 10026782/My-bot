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
    "kind (one_time|monthly_recurring|direct_cost|household_expense או null), title, new_title, task_title, note, category (אחד מ: income|savings|debt|emergency_fund, או טקסט חופשי אחר, או null), period_type (monthly|weekly|custom או null), calc_method (period_sum = סכום בתקופה, למשל הכנסה חודשית; cumulative = יתרה מצטברת מול יעד, למשל חיסכון/קרן חירום/סגירת חוב; recurring_level = שינוי קבוע בחודש, או null), start_date, end_date (YYYY-MM-DD או null; תאריך יחסי כמו ״סוף השנה״ חשב לפי היום שמסופק ב-today). update_goal = שינוי מאפייני יעד קיים (קטגוריה/תקופה/שיטה/תאריכים). "
    "אל תמציא סכומים או יעדים שלא נאמרו. הכנסה/חיסכון חד-פעמי = one_time; "
    "שינוי קבוע בחודש (הוצאה שבוטלה, החזר שירד) = monthly_recurring. "
    "הוצאה שקשורה ישירות להפקת הכנסה (דלק, כביש, חניה, עמלה בנסיעות/עבודה) = log_progress עם kind=direct_cost, "
    "amount חיובי, ו-goal_hint של מקור ההכנסה (למשל נסיעות). "
    "הוצאה ביתית פרטית (סופר, חשבונות הבית, ילדים, בילויים) = log_progress עם kind=household_expense, "
    "amount חיובי, goal_hint=הוצאות בית. היא לא קשורה להכנסה ולא מורידה נטו."
)


def classify(text: str, goal_titles: list[str], *, today: date | None = None) -> dict | None:
    from llm_fallback import call_anthropic_text
    out = call_anthropic_text(
        source="fcc_classify", model="claude-haiku-4-5-20251001", max_tokens=400, temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(
            {"text": text, "goal_titles": goal_titles, "today": (today or date.today()).isoformat()}, ensure_ascii=False)}],
    )
    match = re.search(r"\{.*\}", out or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except ValueError:
        return None


_FILL_SYSTEM = (
    "אתה ממלא שדות חסרים בטיוטת עדכון כלכלי אישי. החזר JSON בלבד: אובייקט של שדות שנאמרו בהודעה, "
    "מתוך: title, target_amount (מספר), category (income|savings|emergency_fund|debt|other), "
    "period_type (monthly|weekly|custom), calc_method (period_sum|cumulative|recurring_level), "
    "end_date, start_date, occurred_at (YYYY-MM-DD; תאריך יחסי כמו ״סוף השנה״/״סוף יוני״ חשב לפי today), "
    "amount (מספר), kind (one_time|monthly_recurring|direct_cost|household_expense|target_change), note. "
    "כלול רק מה שנאמר במפורש; אל תמציא ואל תנחש. אם ההודעה היא תשובה לשדה ב-awaiting, מלא אותו. "
    "בעריכה (״ערוך סכום ל-80000״) החזר רק את השדה שהשתנה. "
    "אם ההודעה אינה קשורה לשאלה או לעריכה (למשל שאלה על לידים) — החזר fields ריק. "
    "פורמט: {\"fields\": {שדה: ערך}, \"evidence\": {שדה: ציטוט מדויק מההודעה שממנו נלקח הערך}}. "
    "אין ציטוט מהטקסט = אין שדה."
)


def fill_reply(text: str, awaiting: str | None, fields: dict, entity: str, *, today: date | None = None) -> dict:
    from llm_fallback import call_anthropic_text
    out = call_anthropic_text(
        source="fcc_fill", model="claude-haiku-4-5-20251001", max_tokens=300, temperature=0, system=_FILL_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(
            {"text": text, "awaiting": awaiting, "entity": entity, "draft": {k: str(v) for k, v in fields.items()},
             "today": (today or date.today()).isoformat()}, ensure_ascii=False)}],
    )
    match = re.search(r"\{.*\}", out or "", re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    fields, evidence = data.get("fields"), data.get("evidence")
    if not isinstance(fields, dict) or not isinstance(evidence, dict):
        return {}
    haystack = re.sub(r"\s+", " ", text or "").casefold()
    accepted = {}
    for name, value in fields.items():                       # anti-hallucination: the value must be quoted from the text
        quote = re.sub(r"\s+", " ", str(evidence.get(name) or "")).strip().casefold()
        if value not in (None, "") and quote and quote in haystack:
            accepted[name] = value
    return accepted
