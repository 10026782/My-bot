# deterministic_denial.py
# Early, pre-Agent prediction of outcomes that a late-stage gate would
# provably deny regardless of what Claude does — skips the Claude round trip
# entirely in that case, same convention as the EMERGENCY_STOP_AI check in
# app.py's Agent Loop.
#
# כלל ברזל: מודול הזה אף פעם לא מחליט "מותר" — רק "אסור" או "לא יודע".
# הוא קורא לשערי האכיפה האמיתיים (enforce_leads_write_gate,
# tool_registry.check_allowed) כמו שהם — לא משכפל את הלוגיקה שלהם.
# hint שגוי/חסר יכול לכל היותר לדלג על אופטימיזציה מוקדמת — לעולם לא
# להעניק גישה ששערי האכיפה בהמשך (BUG-091 preflight, dispatch_tool's
# enforce()) לא היו תופסים בכל מקרה.

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .route_decision import Intent
import tool_registry
from tools.airtable_security import enforce_leads_write_gate, LeadsDirectWriteBlocked

if TYPE_CHECKING:
    from identity import Identity


@dataclass(frozen=True)
class ToolHint:
    """כלי אחד שה-Intent צפוי לקרוא לו, לצורך חיזוי חסימה מוקדם בלבד.
    לעולם לא משמש להעניק/לדלג על שער אמיתי — רק לקצר את הדרך כשהתוצאה
    כבר ודאית."""
    tool_name: str
    leads_table: str | None = None  # מוגדר רק כשהקריאה המשוערת מכוונת
                                      # לטבלת Leads (מוזן ל-enforce_leads_write_gate)


# היקף התחלתי שמרני: שני ה-Intent-ים ממופים לאותו שער מקור (source-gate)
# ודאי ומוכח — enforce_leads_write_gate חוסם airtable_add ו-airtable_update
# על Leads באותו אופן בדיוק עבור source="agent". Intent בלי רשומה כאן
# ממשיך ל-Agent כרגיל כמו היום — הטבלה הזו יכולה רק לדלג על אופטימיזציה,
# לעולם לא להעניק אחת.
INTENT_TOOL_HINTS: dict[str, tuple[ToolHint, ...]] = {
    Intent.UPDATE_LEAD: (ToolHint(tool_name="airtable_update", leads_table="Leads"),),
    Intent.CREATE_LEAD: (ToolHint(tool_name="airtable_add", leads_table="Leads"),),
}


@dataclass(frozen=True)
class DeterministicDenial:
    reason:    str   # "leads_write_gate" | "role_not_allowed"
    message:   str   # טקסט מוכן להחזרה למשתמש
    tool_name: str   # הכלי המשוער שהפעיל את החסימה (ללוג בלבד)


def check_deterministic_denial(intent: str, identity: "Identity") -> DeterministicDenial | None:
    """
    חיזוי טהור, read-only, של מה ששערי האכיפה המאוחרים היו עושים אילו
    ה-Agent רץ וקרא לכלי המשוער של ה-Intent. מחזיר חסימה רק כשהתוצאה כבר
    ודאית ב-100% מהעובדות הידועות כרגע — לעולם לא ניחוש. מחזיר None כש-hint
    חסר, לא רלוונטי, או ששערי האכיפה האמיתיים *עשויים* לאשר (לדוגמה כלים
    רגילים עם requires_approval=True שאדם עדיין יכול לאשר — לא מכוסים כאן
    בכוונה).
    """
    hints = INTENT_TOOL_HINTS.get(intent)
    if not hints:
        return None

    for hint in hints:
        # (b) role שמוחרג לגמרי מ-roles_allowed — שימוש חוזר ב-
        # tool_registry.check_allowed() כמו שהוא, בלי לוגיקת role חדשה.
        if not tool_registry.check_allowed(hint.tool_name, identity):
            return DeterministicDenial(
                reason="role_not_allowed",
                message=f"❌ הפעולה הזו אינה זמינה עבור התפקיד שלך ({identity.role}).",
                tool_name=hint.tool_name,
            )

        # (a) שער מקור בלתי מותנה — קורא לפונקציית השער האמיתית,
        # source="agent" קבוע (תואם בדיוק את נתיב ה-Agent השיחתי הגולמי,
        # כמו ה-preflight של BUG-091), משתמש בהודעה האמיתית שלה.
        if hint.leads_table:
            try:
                enforce_leads_write_gate(
                    hint.tool_name, {"table": hint.leads_table}, source="agent",
                )
            except LeadsDirectWriteBlocked as e:
                return DeterministicDenial(
                    reason="leads_write_gate", message=str(e), tool_name=hint.tool_name,
                )

    return None
