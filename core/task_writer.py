"""Task Golden Writer — ליבת הכתיבה הקנונית היחידה למשימות (Tasks).

שלוש שכבות נפרדות במודול אחד (UX שייך לקוראים, לא לכאן):

1. Golden Writer validation (טהור, בלי I/O) — האינווריאנט היחיד:
   כותרת משימה חובה, ולא ריקה אחרי נרמול בטוח (NFKC, הסרת תווי רוחב-אפס,
   נרמול רווחים). אין כאן מדיניות עסקית חדשה: סטטוס, תאריך יעד, Owner ושדות
   לא מוכרים נשארים באחריות החוזים הקיימים (schema / airtable_gateway).
   UPDATE נבדק רק אם הוא נוגע בכותרת — אסור לרוקן כותרת קיימת.

2. Resolver / verification — מזהי רשומות שהמודל סיפק לא נכנסים ישירות:
   מזהה מאומת (קיים בטבלה המקושרת) או שם שנפתר לרשומה יחידה דרך resolver
   קנוני קיים → המזהה הקנוני; לא-ניתן-לאימות/עמום → מושמט (שדה אופציונלי).
   ה-I/O מוזרק ע"י הקורא (core/action_gateway.complete_task_proposal).

3. Diamond completion (טהור) — גזירת כותרת מהקשר מהימן קיים לפני ששואלים.
   ה-scope מוגבל בכוונה לשני מקורות בלבד: טקסט המשתמש המקורי דרך ה-parser
   הדטרמיניסטי הקיים של ה-router, או Next Action (שהוא פעולה) של ליד מאומת
   + שם הליד. שמות Contact/Deal משמשים רק ל-verification של קישורים, לעולם
   לא לגזירת כותרת. לעולם לא ממציאים עובדה חסרה. רץ רק לפני אישור (Gate 1);
   Gate 2 מאמת ומנרמל בלבד.

Root cause (audit 24/09/2026): 97 רשומות Tasks ריקות נוצרו כי אף שכבה לא
בדקה את *ערך* הכותרת — רק את נוכחות המפתח (sheets_append row_data=[""]).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from datetime import date

from airtable_schema import Tables, TaskFields

TASK_TABLE_NAMES = frozenset({Tables.TASKS, "Tasks"})

ASK_TITLE_MESSAGE = "מה כותרת המשימה? (מה בדיוק צריך לעשות)"

_ZERO_WIDTH_RE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")
_RECORD_ID_RE = re.compile(r"rec[A-Za-z0-9]{14}")
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class TaskWriteRejected(ValueError):
    """הכותרת חסרה/ריקה אחרי נרמול (או UPDATE שמרוקן אותה). fail-closed.

    ``missing`` = השדות שאי אפשר היה לגזור (Diamond: שואלים רק עליהם).
    """

    def __init__(self, code: str, reason: str, user_message: str = ASK_TITLE_MESSAGE,
                 missing: tuple[str, ...] = (TaskFields.NAME,)):
        super().__init__(reason)
        self.code = code
        self.user_message = user_message
        self.missing = missing


def is_task_table(table: object) -> bool:
    return str(table or "").strip() in TASK_TABLE_NAMES


# ══════════════════════════════════════════════════
# 1. Golden Writer validation
# ══════════════════════════════════════════════════

def normalize_title(value: object) -> str:
    """נרמול בטוח בלבד. ערך שאינו טקסט (שדה singleLineText) → "" (אין כותרת)."""
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value)
    text = _ZERO_WIDTH_RE.sub("", text)
    return " ".join(text.split())


def _require_title(value: object) -> str:
    title = normalize_title(value)
    if not title:
        raise TaskWriteRejected("title_blank", "task title is missing or empty after normalization")
    return title


def prepare_task_create(fields: Mapping[str, object] | None) -> dict:
    """מאמת יצירה ומחזיר את השדות עם כותרת מנורמלת. כל שדה אחר — כמות-שהוא."""
    fields = dict(fields) if isinstance(fields, Mapping) else {}
    fields[TaskFields.NAME] = _require_title(fields.get(TaskFields.NAME))
    return fields


def prepare_task_update(fields: Mapping[str, object] | None) -> dict:
    """UPDATE שלא נוגע בכותרת → כמות-שהוא. UPDATE שמרוקן כותרת → נדחה."""
    fields = dict(fields) if isinstance(fields, Mapping) else {}
    if TaskFields.NAME in fields:
        fields[TaskFields.NAME] = _require_title(fields[TaskFields.NAME])
    return fields


def validate_task_payload(tool_name: str, payload: Mapping[str, object] | None) -> None:
    """אימות בלבד (בלי לשנות payload). no-op לכל דבר שאינו כתיבת Task."""
    payload = payload or {}
    if tool_name not in ("airtable_add", "airtable_update") or not is_task_table(payload.get("table")):
        return
    if tool_name == "airtable_add":
        prepare_task_create(payload.get("fields"))
    else:
        prepare_task_update(payload.get("fields"))


def iso_date_or_none(value: object) -> str | None:
    """בדיקת סוג-schema קיימת לשדה התאריך (Airtable date, רמז FIELD_MAP
    "YYYY-MM-DD"; אותה בדיקה ש-_sheets_payload_to_airtable כבר מבצע). משמש
    רק להשמטת ערך אופציונלי שנגזר ממודל — לא לדחיית משימה."""
    raw = value.strip() if isinstance(value, str) else ""
    if not _ISO_DATE_RE.fullmatch(raw):
        return None
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return None


# ══════════════════════════════════════════════════
# 2. Resolver / verification of model-supplied references
# ══════════════════════════════════════════════════

# שדה קישור → (טבלה מקושרת, entity של resolver השם הקנוני אם קיים)
TASK_LINK_TARGETS: dict[str, tuple[str, str | None]] = {
    TaskFields.LEAD_LINK:     (Tables.LEADS, None),
    TaskFields.CONTACTS_LINK: (Tables.CONTACTS, "contact"),
    TaskFields.DEALS_LINK:    (Tables.DEALS, "deal"),
    TaskFields.OWNER:         (Tables.PROFILE, None),
}

RecordFetcher = Callable[[str, str], "dict | None"]      # (table, rec_id) -> fields | None
NameResolver = Callable[[str, str], "list[str]"]         # (entity, name) -> matching rec ids


def verify_task_links(
    fields: Mapping[str, object],
    *,
    fetch_record: RecordFetcher,
    resolve_name: NameResolver | None = None,
) -> tuple[dict, dict[str, dict], list[str]]:
    """מאמת הפניות שסופקו ע"י המודל. לעולם לא מעביר מזהה לא מאומת.

    מחזיר (fields, verified_records, omitted_fields):
      - מזהה rec… שקיים בטבלה המקושרת → נשמר (ו-fields של הרשומה נאספים
        ל-Diamond completion).
      - שם שה-resolver הקנוני מחזיר עבורו רשומה אחת בדיוק → המזהה הקנוני.
      - לא נמצא / עמום / אין resolver / כשל קריאה → הערך מושמט; שדה שלא נשאר
        בו ערך מאומת מוסר (השדות האלה אופציונליים).
    """
    result = dict(fields)
    verified: dict[str, dict] = {}
    omitted: list[str] = []
    for field, (table, entity) in TASK_LINK_TARGETS.items():
        if field not in result:
            continue
        raw = result[field]
        values = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
        kept: list[str] = []
        for value in values:
            ref = normalize_title(value) if isinstance(value, str) else ""
            if not ref:
                continue
            if _RECORD_ID_RE.fullmatch(ref):
                record_fields = fetch_record(table, ref)
                if record_fields is not None:
                    kept.append(ref)
                    verified[ref] = record_fields
            elif entity and resolve_name is not None:
                matches = resolve_name(entity, ref)
                if len(matches) == 1:
                    kept.append(matches[0])
        if kept:
            result[field] = list(dict.fromkeys(kept))
        else:
            del result[field]
        if len(kept) != len([v for v in values if isinstance(v, str) and normalize_title(v)]):
            omitted.append(field)
    return result, verified, omitted


# ══════════════════════════════════════════════════
# 3. Diamond completion — derive a Title from trusted context
# ══════════════════════════════════════════════════

# Leads."Next Action" (singleSelect) — רק האפשרויות שהן פעולה לביצוע.
# התוויות זהות לתוויות התצוגה הקנוניות ב-tma_api._LEAD_NEXT_ACTION_OPTIONS
# (test_task_golden_writer.py מוודא שאין סטייה). Waiting Response /
# Closed Won / Closed Lost / ליד חדש אינן פעולה → לא נגזרת מהן כותרת.
ACTIONABLE_LEAD_NEXT_ACTIONS: dict[str, str] = {
    "Call Back":        "להתקשר בחזרה",
    "Send Details":     "לשלוח פרטים",
    "Follow Up":        "פולואפ",
    "Schedule Meeting": "לתאם פגישה",
    "Create Deal":      "ליצור עסקה",
    "Convert Contact":  "להמיר לאיש קשר",
}


def compose_title(action: object, subject: object) -> str:
    """פעולה ידועה + נושא ידוע, בתבנית הקיימת של כותרות נגזרות במערכת
    ("📞 ליד נטוש — <sender>"). בלי פעולה אין כותרת — שם לבד אינו משימה."""
    action_text = normalize_title(action)
    subject_text = normalize_title(subject)
    if not action_text:
        return ""
    return f"{action_text} — {subject_text}" if subject_text else action_text


def title_from_user_text(user_text: str) -> tuple[str, str | None]:
    """הטקסט של המשתמש עצמו, דרך ה-parser הדטרמיניסטי הקיים של ה-router
    (אותו parser שמזין את create_task הדטרמיניסטי). רק תוצאה ודאית."""
    if not normalize_title(user_text):
        return "", None
    from core.router.router import parse_deterministic_create_task

    parsed = parse_deterministic_create_task(user_text)
    if not parsed.certain:
        return "", None
    return normalize_title(parsed.title), parsed.due_date


def title_from_lead(lead_fields: Mapping[str, object]) -> str:
    """ליד מאומת עם Next Action שהוא פעולה + שם הליד → כותרת."""
    from airtable_schema import LeadFields

    raw_action = lead_fields.get(LeadFields.NEXT_STEP)
    action = ACTIONABLE_LEAD_NEXT_ACTIONS.get(raw_action.strip()) if isinstance(raw_action, str) else None
    name = normalize_title(lead_fields.get(LeadFields.NAME))
    if not action or not name:
        return ""
    return compose_title(action, name)
