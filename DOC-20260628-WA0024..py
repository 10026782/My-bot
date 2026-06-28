# core/action_result.py — CXX: Action Integrity Contract
#
# כל פעולה במערכת מחזירה ActionResult במקום bool/str.
# מפריד בין: tool success / business success / audit / delivery.
#
# חוק ברזל: business_success לא נדרס על ידי audit_success או post_success.
# אם Airtable יצר רשומה וקיבלנו record_id — זו הצלחה עסקית, גם אם audit נפל.

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


# ══════════════════════════════════════════════════
# ClaimType — סוג הטענה שהבוט עומד לאמר
# ══════════════════════════════════════════════════

class ClaimType(str, Enum):
    """סוג הטענה שהבוט עומד לאמר ללקוח.
    נבדק ע"י ClaimGate לפני שמגיע לפלט.
    """
    CREATED   = "created"    # "נוצר", "הוספתי", "נפתח"
    UPDATED   = "updated"    # "עודכן", "שיניתי", "תיקנתי"
    SENT      = "sent"       # "נשלח", "שלחתי", "הועבר"
    FOUND     = "found"      # "מצאתי", "יש לך", "קיים"
    SCHEDULED = "scheduled"  # "קבעתי", "נקבע", "תזמנתי"
    DELETED   = "deleted"    # "נמחק", "הסרתי"


# ══════════════════════════════════════════════════
# ActionResult — תוצאת פעולה מפורקת
# ══════════════════════════════════════════════════

@dataclass
class ActionResult:
    """
    תוצאת פעולה מפורקת ל-8 שכבות עצמאיות.

    הסדר:
        tool_called → tool_http_ok → business_success → audit_success
        → post_success → output_approved → delivery_attempted → delivery_success

    כל שכבה עצמאית — כישלון שכבה אחת לא מחק את הקודמות.
    """

    # שלב 1 — כלי נקרא
    tool_called:           bool = False
    tool_http_ok:          bool = False

    # שלב 2 — תוצאה עסקית (הכי חשוב)
    business_success:      bool = False
    record_id:             str  = ""      # Airtable record ID אם נוצר/עודכן
    affected_records:      int  = 0       # כמה רשומות הושפעו

    # שלב 3 — audit
    audit_success:         bool = False
    audit_id:              str  = ""

    # שלב 4 — post-processing (scoring, memory, notifications)
    post_success:          bool = False

    # שלב 5 — פלט
    output_approved:       bool = False   # COG אישר
    delivery_attempted:    bool = False   # adapter נקרא
    delivery_success:      bool = False   # ידוע שנשלח בפועל
    adapter_mode:          str  = ""      # "live" | "stub" | "unknown"

    # claim שהפעולה מייצרת — נבדק ע"י ClaimGate
    claim_type:            ClaimType | None = None

    # מטא
    error:                 str  = ""      # שגיאה שלא עצרה business_success
    fatal_error:           str  = ""      # שגיאה שעצרה הכל
    source:                str  = ""      # "lead_capture" / "crm" / "run_agent"

    # ── helpers ────────────────────────────────────

    @property
    def ok(self) -> bool:
        """business_success — זה מה שחשוב לרוב הקוראים."""
        return self.business_success

    @property
    def failed(self) -> bool:
        return not self.business_success

    @classmethod
    def from_airtable_add(cls, result: dict, source: str = "") -> "ActionResult":
        """בנה ActionResult מתוצאת airtable_add (C53-A contract: dict)."""
        if not isinstance(result, dict):
            return cls(
                tool_called=True,
                fatal_error=f"airtable_add returned {type(result).__name__}, expected dict",
                source=source,
            )
        ok       = result.get("ok") is True
        rec_id   = result.get("external_id", "")
        return cls(
            tool_called      = True,
            tool_http_ok     = ok,
            business_success = ok and bool(rec_id),
            record_id        = rec_id,
            affected_records = 1 if ok else 0,
            source           = source,
        )

    @classmethod
    def from_airtable_update(cls, result: dict, source: str = "") -> "ActionResult":
        """בנה ActionResult מתוצאת airtable_update (C53-A contract: dict)."""
        if not isinstance(result, dict):
            return cls(
                tool_called=True,
                fatal_error=f"airtable_update returned {type(result).__name__}, expected dict",
                source=source,
            )
        ok     = result.get("ok") is True
        rec_id = result.get("external_id", "")
        return cls(
            tool_called      = True,
            tool_http_ok     = ok,
            business_success = ok,
            record_id        = rec_id,
            affected_records = 1 if ok else 0,
            source           = source,
        )

    @classmethod
    def failure(cls, error: str, source: str = "") -> "ActionResult":
        """ActionResult לכישלון ידוע לפני קריאת כלי."""
        return cls(fatal_error=error, source=source)

    def __repr__(self) -> str:
        status = "✅" if self.business_success else "❌"
        rec    = f" rec={self.record_id}" if self.record_id else ""
        err    = f" err={self.error or self.fatal_error}" if (self.error or self.fatal_error) else ""
        return f"ActionResult({status} src={self.source}{rec}{err})"
