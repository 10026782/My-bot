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
    "action (log_progress|set_target|create_goal|update_goal|rename_goal|follow_up|note|upsert_obligation|deactivate_obligation), "
    "goal_hint (שם היעד כפי שנאמר, או ריק), amount (מספר או null), target (מספר או null), "
    "kind (one_time|monthly_recurring|direct_cost|household_expense או null), title, new_title, task_title, note, category (אחד מ: income|savings|debt|emergency_fund, או טקסט חופשי אחר, או null), period_type (monthly|weekly|custom או null), calc_method (period_sum = סכום בתקופה, למשל הכנסה חודשית; cumulative = יתרה מצטברת מול יעד, למשל קרן חירום/סגירת חוב; recurring_level = שינוי קבוע בחודש, או null), start_date, end_date (YYYY-MM-DD או null; תאריך יחסי כמו ״סוף השנה״ חשב לפי היום שמסופק ב-today). savings = הוראת קבע חודשית לשוק ההון מול יעד (למשל 5,000 לחודש; calc_method=recurring_level, period_type=monthly) — לא סכום שמתאפס; כל הגדלה/הקטנה של ההפרשה נרשמת כ-log_progress עם kind=monthly_recurring ו-amount = השינוי (חיובי להגדלה, שלילי להקטנה). הפקדה בפועל לחודש הנוכחי (״הפקדתי החודש X לשוק ההון״) = log_progress עם kind=one_time ו-amount=X על יעד החיסכון (זו הפקדה בפועל, לא שינוי רמה). אם נאמר ״אני מפריש עכשיו X בחודש״ (הרמה הכוללת החדשה) החזר log_progress עם level=X (לא amount) והמערכת תחשב את ההפרש מהרמה הקיימת; אם נאמר ״הגדלתי/הקטנתי ב-X״ החזר amount. emergency_fund = סכום חד-פעמי שנצבר (cumulative). update_goal = שינוי מאפייני יעד קיים (קטגוריה/תקופה/שיטה/תאריכים). "
    "אל תמציא סכומים או יעדים שלא נאמרו. הכנסה/חיסכון חד-פעמי = one_time; "
    "שינוי קבוע בחודש (הוצאה שבוטלה, החזר שירד) = monthly_recurring. "
    "הוצאה שקשורה ישירות להפקת הכנסה (דלק, כביש, חניה, עמלה בנסיעות/עבודה) = log_progress עם kind=direct_cost, "
    "amount חיובי, ו-goal_hint של מקור ההכנסה (למשל נסיעות). "
    "הוצאה ביתית פרטית (סופר, חשבונות הבית, ילדים, בילויים) = log_progress עם kind=household_expense, "
    "amount חיובי, goal_hint=הוצאות בית. היא לא קשורה להכנסה ולא מורידה נטו. "
    "התחייבות חוזרת (מנוי, הוראת קבע, שירות קבוע: נטפליקס, חשמל, ביטוח, תוכנה) = upsert_obligation עם title=שם ההתחייבות, "
    "amount=סכום לחיוב, frequency (monthly|quarterly|yearly|custom, ברירת מחדל monthly), scope (household|business|personal רק אם נאמר), "
    "review_status (cancel=לבטל, reduce=להקטין, negotiate=לנהל משא ומתן, keep=להשאיר, review=לבדוק), saving (חיסכון חודשי רק אם נאמר), "
    "vendor, obligation_type (subscription|standing_order|service|loan_payment|other), essentiality (essential|useful|optional|review), next_charge_date. "
    "״ביטלתי את X״ (הביטול בוצע בפועל אצל הספק) = deactivate_obligation עם title=X; ״לבטל את X״ (החלטה/כוונה) = upsert_obligation עם review_status=cancel. "
    "התחייבות היא לא הוצאה בפועל ולא אירוע התקדמות: לעולם אל תחזיר log_progress בשבילה."
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
    "amount (מספר), kind (one_time|monthly_recurring|direct_cost|household_expense|target_change), note, name (שם התחייבות), scope (household|business|personal), frequency (monthly|quarterly|yearly|custom), review_status (keep|reduce|cancel|negotiate|review), saving (מספר), vendor, next_charge_date, balance (יתרה לסגירה מוקדמת, מספר), payment (החזר חודשי, מספר), rate (ריבית שנתית באחוזים, מספר), loan_type (private|business|mortgage), lender, original (סכום הלוואה מקורי, מספר), payments_left (מספר שלם), value (שווי נוכחי של נכס, מספר), mortgage (יתרת משכנתא בנכס, מספר), step (פעולה הבאה בנכס, טקסט חופשי כפי שנאמר), step_owner (אליהו|אהרן|אורי|משפטי). "
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
