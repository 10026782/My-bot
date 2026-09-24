"""Task Golden Writer — ליבת הכתיבה הקנונית היחידה למשימות (Tasks).

כל כתיבה עסקית של משימה מחוץ ל-Mini App (router דטרמיניסטי, Agent
airtable_add, המרת sheets_append, workers אוטומטיים) עוברת כאן פעמיים:

1. בגבול ההצעה — core/action_gateway.resolve_canonical_call() מאמת בלבד
   (לא משנה את ה-payload, כדי לא לשבור את זהות ה-fingerprint של BUG-TASK-01)
   ונכשל לפני שנוצרת בקשת אישור.
2. בגבול הביצוע — tools/dispatcher.py (airtable_add / airtable_update מול
   Tasks) מאמת שוב וכותב את השדות המנורמלים.

הפונקציות כאן טהורות (אין I/O): אין "השלמה" של ערך שלא נגזר באופן
דטרמיניסטי. כותרת היא השדה העסקי החובה היחיד; סטטוס מקבל ברירת מחדל
"ממתין"; כל השאר אופציונלי. מזהי רשומות (Owner / קישורים) שמקורם ב-Agent
נדחים — לעולם לא סומכים על מזהה שהמודל יצר.

Root cause (audit 24/09/2026): 97 רשומות Tasks ריקות נוצרו כי אף שכבה לא
בדקה את *ערך* הכותרת — רק את נוכחות המפתח.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from datetime import date

from airtable_schema import Tables, TaskFields, TaskStatus

TASK_TABLE_NAMES = frozenset({Tables.TASKS, "Tasks"})

TITLE_MAX_LENGTH = 250

# מקורות לא-מהימנים: תוכן שהמודל שולט בו. ברירת מחדל fail-closed —
# dispatcher מעביר "agent" כשאין trusted_source מפורש.
UNTRUSTED_SOURCES = frozenset({"agent", ""})

ASK_TITLE_MESSAGE = "מה כותרת המשימה? (מה בדיוק צריך לעשות)"

_WRITE_FIELDS = frozenset({
    TaskFields.NAME,
    TaskFields.DESCRIPTION,
    TaskFields.DUE_DATE,
    TaskFields.STATUS,
    TaskFields.DOMAIN,
    TaskFields.OWNER,
    TaskFields.CONTACTS_LINK,
    TaskFields.DEALS_LINK,
    TaskFields.LEAD_LINK,
})
_RECORD_ID_FIELDS = frozenset({
    TaskFields.OWNER,
    TaskFields.CONTACTS_LINK,
    TaskFields.DEALS_LINK,
    TaskFields.LEAD_LINK,
})
# מפתחות שהקוד מזריק/מתעלם מהם בכל כתיבה גנרית (ראה GENERIC_WRITE_IGNORED_KEYS).
_IGNORED_KEYS = frozenset({"tenant_id"})

# מיפוי דטרמיניסטי של שמות שדה אנגליים שהמודל שולח (core_knowledge מתעד
# שדות עבריים, אבל _canonical_task_payload כבר מכיר "title"/"due_date").
_FIELD_ALIASES = {
    "title": TaskFields.NAME,
    "description": TaskFields.DESCRIPTION,
    "due_date": TaskFields.DUE_DATE,
    "status": TaskFields.STATUS,
}

_STATUS_VALUES = {
    TaskStatus.PENDING: TaskStatus.PENDING,
    TaskStatus.IN_PROGRESS: TaskStatus.IN_PROGRESS,
    TaskStatus.DONE: TaskStatus.DONE,
    "pending": TaskStatus.PENDING,
    "todo": TaskStatus.PENDING,
    "in progress": TaskStatus.IN_PROGRESS,
    "in_progress": TaskStatus.IN_PROGRESS,
    "done": TaskStatus.DONE,
    "completed": TaskStatus.DONE,
}

# כותרות שהן placeholder ולא פעולה — כולל הדוגמה מתוך prompt של
# interaction_engine ("משימה"), שמודל עלול להחזיר כמות-שהיא.
_PLACEHOLDER_TITLES = frozenset({
    "משימה", "משימה חדשה", "ללא כותרת", "כותרת", "כותרת המשימה", "אין",
    "task", "new task", "untitled", "title", "todo", "to do", "tbd",
    "none", "null", "undefined", "nan", "n a", "na",
})

_ZERO_WIDTH_RE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")
_RECORD_ID_RE = re.compile(r"rec[A-Za-z0-9]{14}")
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class TaskWriteRejected(ValueError):
    """כתיבת משימה לא תקינה/עמומה — נכשלת סגור, לפני כל כתיבה.

    ``missing`` מפרט את השדות שאי אפשר לגזור ושצריך לשאול עליהם בלבד
    (Diamond: לשאול רק מה שלא ניתן לגזור). ``user_message`` בטוח למשתמש.
    """

    def __init__(self, code: str, reason: str, user_message: str, missing: tuple[str, ...] = ()):
        super().__init__(reason)
        self.code = code
        self.user_message = user_message
        self.missing = missing


def is_task_table(table: object) -> bool:
    return str(table or "").strip() in TASK_TABLE_NAMES


def _clean_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = _ZERO_WIDTH_RE.sub("", text).replace(" ", " ")
    return " ".join(text.split())


def _placeholder_key(title: str) -> str:
    """מפתח השוואה ל-placeholder: רק אותיות/ספרות. עטיפות כמו "[משימה]" או
    ‎"> משימה."‎ (ש-_canonical_business_text של ה-gateway מקלף לפני האחסון)
    נתפסות כבר בגבול ההצעה, לא רק אחרי אישור."""
    return " ".join("".join(ch if ch.isalnum() else " " for ch in title).split()).casefold()


def normalize_task_title(value: object) -> str:
    """מחזיר כותרת מנורמלת תקינה או זורק TaskWriteRejected.

    לעולם לא ממציא כותרת: ריק/רווחים/placeholder/ללא אות או ספרה → דחייה.
    """
    if value is None:
        raise TaskWriteRejected("title_missing", "task title is required",
                                ASK_TITLE_MESSAGE, missing=(TaskFields.NAME,))
    if not isinstance(value, str):
        raise TaskWriteRejected("title_invalid_type",
                                f"task title must be text, got {type(value).__name__}",
                                ASK_TITLE_MESSAGE, missing=(TaskFields.NAME,))
    title = _clean_text(value)
    if not title:
        raise TaskWriteRejected("title_blank", "task title is empty or whitespace",
                                ASK_TITLE_MESSAGE, missing=(TaskFields.NAME,))
    if not any(ch.isalnum() for ch in title):
        raise TaskWriteRejected("title_not_meaningful",
                                f"task title has no letters or digits: {title!r}",
                                ASK_TITLE_MESSAGE, missing=(TaskFields.NAME,))
    if _placeholder_key(title) in _PLACEHOLDER_TITLES:
        raise TaskWriteRejected("title_placeholder",
                                f"task title is a placeholder: {title!r}",
                                ASK_TITLE_MESSAGE, missing=(TaskFields.NAME,))
    if len(title) > TITLE_MAX_LENGTH:
        raise TaskWriteRejected("title_too_long",
                                f"task title exceeds {TITLE_MAX_LENGTH} characters",
                                f"❌ כותרת המשימה ארוכה מדי (מעל {TITLE_MAX_LENGTH} תווים). "
                                "נסח כותרת קצרה ושים את הפרטים בתיאור.")
    return title


def normalize_due_date(value: object) -> str:
    raw = value.strip() if isinstance(value, str) else ""
    if not _ISO_DATE_RE.fullmatch(raw):
        raise TaskWriteRejected("due_date_invalid", f"invalid task due date {value!r}",
                                "❌ תאריך היעד לא תקין — נדרש תאריך בפורמט YYYY-MM-DD.")
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        raise TaskWriteRejected("due_date_invalid", f"invalid task due date {value!r}",
                                "❌ תאריך היעד לא תקין — נדרש תאריך קיים בלוח השנה.") from None


def _normalize_status(value: object) -> str:
    status = _STATUS_VALUES.get(_clean_text(value).casefold()) if isinstance(value, str) else None
    if not status:
        raise TaskWriteRejected("status_invalid", f"unknown task status {value!r}",
                                "❌ סטטוס משימה לא מוכר — אפשרי: ממתין / בביצוע / בוצע.")
    return status


def _normalize_record_ids(field: str, value: object) -> list[str]:
    ids = [value] if isinstance(value, str) else value
    if not isinstance(ids, list) or not ids:
        raise TaskWriteRejected("link_invalid", f"{field} must be a list of record ids",
                                f"❌ שדה {field} חייב להכיל מזהה רשומה מאומת.")
    cleaned = []
    for item in ids:
        item = str(item or "").strip() if isinstance(item, str) else ""
        if not _RECORD_ID_RE.fullmatch(item):
            raise TaskWriteRejected("link_invalid", f"{field} has a malformed record id {item!r}",
                                    f"❌ שדה {field} חייב להכיל מזהה רשומה מאומת.")
        cleaned.append(item)
    return cleaned


def _canonical_keys(fields: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in fields.items():
        if key in _IGNORED_KEYS:
            continue
        canonical = _FIELD_ALIASES.get(key, key)
        if canonical in result:
            raise TaskWriteRejected("field_ambiguous", f"task field {canonical!r} supplied twice",
                                    "❌ אותו שדה משימה נשלח פעמיים בשמות שונים.")
        result[canonical] = value
    unknown = sorted(set(result) - _WRITE_FIELDS)
    if unknown:
        raise TaskWriteRejected("field_unknown", f"unsupported task fields: {unknown}",
                                f"❌ שדות לא נתמכים בטבלת המשימות: {', '.join(unknown)}.")
    return result


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not _clean_text(value)
    return isinstance(value, (list, dict)) and not value


def prepare_task_create(fields: Mapping[str, object] | None, *, source: str = "agent") -> dict:
    """Golden Writer: מאמת ומנרמל שדות ליצירת משימה. טהור, אידמפוטנטי.

    מחזיר dict של שדות Airtable קנוניים (תמיד כולל כותרת תקינה וסטטוס).
    זורק TaskWriteRejected על כל ערך לא תקין — לעולם לא משלים ערך חסר
    פרט לסטטוס ברירת מחדל.
    """
    if not isinstance(fields, Mapping):
        raise TaskWriteRejected("fields_invalid", "task fields must be an object",
                                ASK_TITLE_MESSAGE, missing=(TaskFields.NAME,))
    raw = _canonical_keys(fields)
    title = normalize_task_title(raw.get(TaskFields.NAME))
    result: dict[str, object] = {TaskFields.NAME: title}

    untrusted = str(source or "").strip() in UNTRUSTED_SOURCES
    for key, value in raw.items():
        if key == TaskFields.NAME or _is_empty(value):
            continue
        if key == TaskFields.DESCRIPTION:
            if not isinstance(value, str):
                raise TaskWriteRejected("description_invalid", "task description must be text",
                                        "❌ תיאור המשימה חייב להיות טקסט.")
            result[key] = value.strip()
        elif key == TaskFields.DUE_DATE:
            result[key] = normalize_due_date(value)
        elif key == TaskFields.STATUS:
            result[key] = _normalize_status(value)
        elif key == TaskFields.DOMAIN:
            if not isinstance(value, str):
                raise TaskWriteRejected("domain_invalid", "task domain must be text",
                                        "❌ תחום המשימה לא תקין.")
            result[key] = _clean_text(value)
        elif key in _RECORD_ID_FIELDS:
            if untrusted:
                raise TaskWriteRejected(
                    "link_untrusted",
                    f"{key} supplied by an untrusted source; record ids must come from a resolver",
                    "❌ לא ניתן לשייך משימה לרשומה לפי מזהה שלא אומת. "
                    "צור את המשימה בלי השיוך, או שייך אותה מתוך הרשומה עצמה.",
                )
            result[key] = _normalize_record_ids(key, value)

    result.setdefault(TaskFields.STATUS, TaskStatus.PENDING)
    return result


def prepare_task_update(fields: Mapping[str, object] | None, *, source: str = "agent") -> dict:
    """מאמת עדכון משימה: אם הכותרת מעודכנת — היא חייבת להישאר תקינה.

    שאר השדות נשארים באחריות מסלול העדכון הקיים (allowlist + Domain) —
    כאן רק מונעים מחיקת כותרת/כותרת placeholder ותאריך/סטטוס פגומים.
    """
    if not isinstance(fields, Mapping):
        raise TaskWriteRejected("fields_invalid", "task fields must be an object",
                                "❌ שדות העדכון לא תקינים.")
    result = dict(fields)
    if TaskFields.NAME in result:
        result[TaskFields.NAME] = normalize_task_title(result[TaskFields.NAME])
    if TaskFields.DUE_DATE in result and not _is_empty(result[TaskFields.DUE_DATE]):
        result[TaskFields.DUE_DATE] = normalize_due_date(result[TaskFields.DUE_DATE])
    if TaskFields.STATUS in result:
        result[TaskFields.STATUS] = _normalize_status(result[TaskFields.STATUS])
    return result


def validate_task_payload(tool_name: str, payload: Mapping[str, object] | None, *, source: str = "agent") -> None:
    """גבול ההצעה: אימות בלבד, בלי לשנות את ה-payload. no-op לכל דבר שאינו Task."""
    payload = payload or {}
    if tool_name not in ("airtable_add", "airtable_update") or not is_task_table(payload.get("table")):
        return
    if tool_name == "airtable_add":
        prepare_task_create(payload.get("fields"), source=source)
    else:
        prepare_task_update(payload.get("fields"), source=source)
