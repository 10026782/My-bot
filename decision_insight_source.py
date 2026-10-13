# decision_insight_source.py — Decision Hub: תובנה (Learnings & Insights) כמקור להחלטה
#
# PR1 של SPEC_Insight_to_Decision_to_Task. מודול קריאה/עזר בלבד:
#   - לא כותב ל-Airtable ולא מייבא שכבת כתיבה (שער 1 ב-PLANNING_GATE).
#   - קריאה רק דרך tools.airtable_read_adapter (גבול הקריאה הציבורי).
#   - הכתיבות (Inbox/Decision/Event) נשארות ב-cmd_decision.py דרך DecisionPorts.
#
# Tenant: לטבלת Learnings אין tenant_id (אומת חי 13/10/2026) והמערכת חד-tenant.
# לכן הכלל fail-closed: תובנה נגישה רק ל-identity ששייך ל-tenant הבית; רשומה
# שנושאת tenant_id משלה (בעתיד) חייבת להתאים ל-identity; ערך ריק/חסר = tenant הבית בלבד.

from __future__ import annotations

import dataclasses
import hashlib
import re
from dataclasses import dataclass

from airtable_schema import DecisionDomain, LearningFields, Tables
from core.query_contract import Query
from identity import Identity
from tools.airtable_read_adapter import AirtableReadError, get_record, list_records

# קבוע ה-tenant הקנוני נגזר מברירת המחדל של Identity — אין literal שני.
HOME_TENANT_ID: str = next(f.default for f in dataclasses.fields(Identity) if f.name == "tenant_id")

# שדה tenant_id אינו חי ב-Learnings. נקרא באופן הגנתי בלבד; לעולם לא נכתב.
_DEFENSIVE_TENANT_KEY = "tenant_id"

_MARKER_RE = re.compile(r"\[insight:(rec[A-Za-z0-9]{14})\]")
_REC_ID_RE = re.compile(r"^rec[A-Za-z0-9]{14}$")

SOURCE_LABEL = "מקור: תובנה פנימית (Learnings & Insights) — לא אומת מול מקור חיצוני"

_MAX_DESCRIPTION_CHARS = 600
_LIST_FETCH_LIMIT = 50

# Learnings.domain החי -> DecisionDomain (ערכים חיים עם רווח סופי: מנרמלים בהשוואה בלבד)
_DOMAIN_MAP = {
    "general": DecisionDomain.GENERAL,
    "real estate": DecisionDomain.REAL_ESTATE,
    "import": DecisionDomain.IMPORT,
    "recruitment": DecisionDomain.RECRUITMENT,
}


@dataclass(frozen=True)
class InsightView:
    record_id: str
    title: str
    description: str
    next_action: str
    outcome: str
    decision_domain: str
    fingerprint: str

    @property
    def match_text(self) -> str:
        return f"{self.title} {self.description}".strip()


def insight_marker(record_id: str) -> str:
    if not _REC_ID_RE.match(record_id or ""):
        raise ValueError(f"invalid insight record id: {record_id!r}")
    return f"[insight:{record_id}]"


def marker_ids(text: str) -> list[str]:
    return _MARKER_RE.findall(text or "")


def _fields(record: dict | None) -> dict:
    return (record or {}).get("fields") or {}


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def map_domain(raw_domain: str) -> str:
    return _DOMAIN_MAP.get(_text(raw_domain).lower(), DecisionDomain.GENERAL)


def build_insight_view(record: dict | None) -> InsightView | None:
    """תצוגה ממוינת של תובנה. None אם אין מזהה תקין או אין תוכן להצגה."""
    if not record:
        return None
    record_id = record.get("id", "")
    if not _REC_ID_RE.match(record_id or ""):
        return None
    fields = _fields(record)
    title = _text(fields.get(LearningFields.TITLE)) or _text(fields.get(LearningFields.ALT_TITLE))
    description = _text(fields.get(LearningFields.DESCRIPTION)) or _text(fields.get(LearningFields.ALT_SUMMARY))
    if not title and not description:
        return None
    if not title:
        title = description[:80]
    next_action = _text(fields.get(LearningFields.NEXT_ACTION))
    outcome = _text(fields.get(LearningFields.OUTCOME))
    domain = map_domain(fields.get(LearningFields.DOMAIN, ""))
    digest = hashlib.sha256(
        "\x1f".join((record_id, title, description, next_action)).encode("utf-8")
    ).hexdigest()[:16]
    return InsightView(record_id, title, description, next_action, outcome, domain, digest)


def insight_in_scope(record: dict | None, identity) -> bool:
    """Fail-closed: capability + tenant + domain. ללא tenant_id ברשומה = tenant הבית בלבד."""
    from decision_matching import has_decision_capability

    if not record or not has_decision_capability(identity):
        return False
    identity_tenant = getattr(identity, "tenant_id", None)
    record_tenant = _text(_fields(record).get(_DEFENSIVE_TENANT_KEY))
    if record_tenant:
        if record_tenant != identity_tenant:
            return False
    elif identity_tenant != HOME_TENANT_ID:
        return False
    view = build_insight_view(record)
    if view is None:
        return False
    return bool(identity.can_access_domain(view.decision_domain))


def list_insights(identity, hint: str = "", limit: int = 5) -> list[dict]:
    """תובנות בתחום ה-identity. מעלה AirtableReadError — קריאה שנכשלה אינה 'אין תוצאות'."""
    records = list_records(
        Tables.LEARNINGS,
        "",
        limit=_LIST_FETCH_LIMIT,
        paginate=False,
        sort=[{"field": LearningFields.DATE, "direction": "desc"}],
        timeout=10,
    )
    needle = _text(hint).lower()
    selected: list[dict] = []
    for record in records:
        if not insight_in_scope(record, identity):
            continue
        view = build_insight_view(record)
        if needle and needle not in view.match_text.lower():
            continue
        selected.append(record)
        if len(selected) >= limit:
            break
    return selected


def read_insight(record_id: str, identity) -> tuple[dict | None, InsightView | None]:
    """קריאה טרייה + בדיקת scope. (None, None) אם לא נגיש. מעלה AirtableReadError בכשל קריאה."""
    if not _REC_ID_RE.match(record_id or ""):
        return None, None
    record = get_record(Tables.LEARNINGS, record_id, timeout=10)
    if not insight_in_scope(record, identity):
        return None, None
    return record, build_insight_view(record)


def compose_event_content(view: InsightView) -> str:
    """Raw Content לאירוע / Raw Input ל-Inbox: תוכן + תווית מקור + סמן (שורה אחרונה)."""
    parts = [f"תובנה: {view.title}"]
    if view.description:
        parts.append(view.description)
    if view.next_action:
        parts.append(f"פעולה הבאה (מהתובנה): {view.next_action}")
    parts.append(SOURCE_LABEL)
    parts.append(insight_marker(view.record_id))
    return "\n".join(parts)


def excerpt(view: InsightView) -> str:
    text = view.description
    return text if len(text) <= _MAX_DESCRIPTION_CHARS else text[:_MAX_DESCRIPTION_CHARS].rstrip() + "…"


def canonical_record(records: list[dict]) -> dict | None:
    """בחירה דטרמיניסטית בין כפילויות: הוותיקה ביותר (createdTime, אח"כ id).
    כל מי שרץ במקביל מתכנס לאותה רשומה; הכפילויות נשארות גלויות (אין מחיקה)."""
    if not records:
        return None
    return sorted(records, key=lambda r: (str(r.get("createdTime", "")), str(r.get("id", ""))))[0]


def search_query_for_marker(field: str, marker: str, tenant_id: str) -> Query:
    from core.query_contract import all_of, contains, equals

    return all_of(
        contains(field, marker, case_sensitive=True),
        equals("tenant_id", tenant_id),
    )


__all__ = [
    "AirtableReadError", "HOME_TENANT_ID", "InsightView", "SOURCE_LABEL",
    "build_insight_view", "canonical_record", "compose_event_content", "excerpt",
    "insight_in_scope", "insight_marker", "list_insights", "map_domain",
    "marker_ids", "read_insight", "search_query_for_marker",
]
