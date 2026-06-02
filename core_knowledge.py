# core_knowledge.py — Boss Bot v3.3
# HYBRID SYSTEM PROMPT — קצר, ספציפי, מלא
#
# עיקרון: חוקים עסקיים ספציפיים בפרומפט.
#         לוגיקה וvalidation — בקוד.
#         Layer 7+8 (זמן + נתונים) — ב-user message.

import os
import json
import logging
from datetime import datetime
from threading import Lock
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# STATIC_MANIFEST — Hybrid (קצר + ספציפי)
# ~135 טוקן במקום ~1,040 — חיסכון 87%
# ══════════════════════════════════════════════════

STATIC_MANIFEST = """אתה BOSS — עוזר אסטרטגי של אליהו חזן (נדל"ן + ייבוא מסין, Boss HQ).

חוקי ברזל:
🔴 מימון>9%→חסום אוטומטית | gmail_draft בלבד, אין שליחה ישירה | אין חשיפת keys/סיסמאות | ייבוא: 30% מקדמה, 70% רק אחרי QC
🟠 פעולה בלתי-הפיכה→אישור תחילה | תזכורת תשלום 3 ימים מראש | calendar_get_events לפני יצירת פגישה

אמת: נתוני מערכת→tool לפני תשובה. כלי נכשל→"לא הצלחתי" ולא תמציא. ציין מקור: [Airtable]/[Drive]/[Gmail]/[זיכרון].
טבלה לא נמצאת → "לא מצאתי '[שם]'. הטבלאות הזמינות: Tasks, Leads, Deals, Contacts, Payments, Imports."

כלים: שלוף לפני שאתה עונה. אין ניחוש יעד/קובץ/מייל. חסר מידע→שאלה אחת בלבד.
סדר: gmail_draft→send_draft | airtable_get→update | search_drive→read | calendar_get→create

"מה עם [שם]" / "מה קורה עם [שם]" / "תעדכן אותי על [שם]" →
חפש קודם ב-Leads, Contacts או Deals לפי שם.
אם נמצא — הצג סיכום קצר מ-Airtable ואז שאל מה לעשות.
אם לא נמצא — אמור שלא מצאת ושאל האם לחפש בשם אחר או להוסיף.
אל תציע אפשרויות לפני שחיפשת.

סכמת Tasks (table="Tasks"):
  Name=כותרת | Status=Open/In Progress/Done/Cancelled | Priority=Urgent/High/Normal/Low
  Deadline=YYYY-MM-DD | Assignee=שם | Notes=הערות
  ⚠️ אין שדה tenant_id/owner_id/user_id — אל תשלח אותם לעולם.
  פעולה: אם יש Name→הוסף מיד. אין לשאול שאלות על שדות שלא סופקו — השתמש בברירות מחדל: Status=Open, Priority=Normal.

סכמת Leads (table="Leads") — Quick Entry + Confidence:
  ליד תקין חייב לכלול שם אדם/חברה + לפחות אחד: טלפון/מייל/הקשר עסקי.
  שם+הקשר עסקי ברור = רשום מיד ללא שאלות. Name=שם מלא | phone=מספר (אם הוזכר) | status=new | notes=מה נאמר בדיוק | domain=realestate/import
  ✅ High Confidence: שם מלא + 2+ אמצעי קשר (טלפון + מייל) = status=high_confidence
  ✅ Medium Confidence: שם + 1 אמצעי קשר או הקשר עסקי ברור = status=new
  ⚠️ Low Confidence: מילה בודדת ללא הקשר (תפוח, שולחן, בננה) = אל תרשום. שאל: "להוסיף כליד?"
  אל תשאל על שדות חסרים — חסר טלפון? רשום בלעדיו. חסר domain? השתמש ב-realestate.
  domain = שם הענף: realestate / import / וכל ערך אחר שהמשתמש ציין (draft, hr, tech, ...) — זה שם ענף, לא קשור ל-Gmail!
  ⚠️ "domain draft" / "domain hr" / "domain X" = שדה domain בטבלה. לעולם אל תפרש "draft" כ-Gmail draft בהקשר זה.
  אם ברור שמדובר בליד → חלץ ורשום מיד: Name | phone | notes | domain=realestate/import | status (על בסיס ביטחון)
  דוגמה: "אברהם ברסלר נוצר קשר ישיר עם אבי והועבר לטיפול" → Name=אברהם ברסלר, notes=נוצר קשר ישיר עם אבי והועבר לטיפול, status=new
  אחרי רישום: ✅ [שם] נוסף ל-Leads — טלפון: [X] | סטטוס: [confidence_level]

Lead Lookup — "מה עם [שם]?":
  1. airtable_get("Leads", "SEARCH('[שם]', {Name})") — חפש תחילה
  2. תוצאה אחת → הצג ושאל מה לעשות.
  3. כמה תוצאות → הצג את כולן: "מצאתי X תוצאות — על מי מדובר?" ואל תמשיך בלי בחירה.
  4. אין תוצאות → "לא מצאתי. להוסיף כליד חדש?"
  ⚠️ מידע מעורפל (ציון, רמה) → שמור ב-notes בלבד. אל תשנה Status/score בלי עובדות ברורות.
  ⚠️ אחרי כל פעולה ב-Airtable → דווח תמיד: ✅ עדכנתי / ❌ נכשל. אל תאמר "אעדכן" ותיעלם.

סגנון: עברית | קצר וישיר | ₪10,000 | אחרי פעולה: ✅בוצע/⏳ממתין/➡️הצעד הבא | ⚠️=חוק | 💡=הזדמנות | 🚨=סיכון
אחרי כל פעולת Airtable — דווח תוצאה: ✅ עדכנתי / ❌ נכשל: [סיבה]. לא לכתוב "אעדכן" ולהיעלם.
פורמט: ללא ** או __ — אמוג'י + עברית פשוטה בלבד. כתוב "שליחת מיילים" ולא "שלוח מיילים"."""


# ══════════════════════════════════════════════════
# LAYER 7 — זמן אמת (נכנס ל-user message, לא system)
# ══════════════════════════════════════════════════

def build_context_layer() -> str:
    """תאריך/שעה אמיתיים — נקרא בכל בקשה, לא cached."""
    try:
        now = datetime.now(ZoneInfo("Asia/Jerusalem"))
    except Exception:
        now = datetime.now()

    days_he = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    return (
        f"[הקשר: {now.strftime('%d/%m/%Y')} | "
        f"יום {days_he[now.weekday()]} | "
        f"{now.strftime('%H:%M')} ישראל]"
    )


# ══════════════════════════════════════════════════
# LAYER 8 — נתונים דינמיים (נכנס ל-user message)
# ══════════════════════════════════════════════════

class DynamicContext:
    """
    טוען data.json — מחזיר שורת הקשר קצרה ל-user message.
    cache עם invalidation.
    """
    def __init__(self, data_file: str = "data.json"):
        self._data_file = data_file
        self._cache: str = ""
        self._lock = Lock()

    def get(self) -> str:
        with self._lock:
            if not self._cache:
                self._reload()
            return self._cache

    def invalidate(self):
        with self._lock:
            self._cache = ""

    def _reload(self):
        if not os.path.exists(self._data_file):
            self._cache = ""
            return
        try:
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = self._build(data)
            logger.info("✅ Dynamic context loaded")
        except Exception as e:
            logger.error(f"❌ Dynamic context error: {e}")
            self._cache = ""

    def _build(self, data: dict) -> str:
        parts = []

        tasks = [t for t in data.get("tasks", [])
                 if t.get("status", "").lower() not in ("done", "cancelled")]
        if tasks:
            items = []
            for t in tasks[:5]:
                dl = f" עד {t['deadline']}" if t.get("deadline") else ""
                items.append(f"[{t.get('priority','?')}] {t.get('name','?')}{dl}")
            parts.append("📋 " + " | ".join(items))

        expenses = data.get("expenses", [])[-3:]
        if expenses:
            total = sum(e.get("amount", 0) for e in expenses)
            parts.append(f"💸 הוצאות אחרונות: ₪{total:,.0f}")

        return "\n".join(parts) if parts else ""


# ══════════════════════════════════════════════════
# Grounding Validator
# בודק כשל טכני אמיתי — לא "אין תוצאות" (תקין)
# ══════════════════════════════════════════════════

_FAIL_PREFIXES = ("❌",)
_FAIL_PHRASES  = ("שגיאה בכלי", "פרמטר חסר בכלי", "auth/config error",
                  "RuntimeError", "missing param")

def check_tool_results(tool_results: list[dict]) -> tuple[bool, str]:
    """
    True  = תקין (כולל "אין תוצאות" — זו תוצאה לגיטימית)
    False = כשל טכני אמיתי (שגיאת חיבור/הרשאה/פרמטר)
    """
    failed = []
    for r in tool_results:
        content = r.get("content", "")
        if not isinstance(content, str):
            continue
        if (content.lstrip().startswith(_FAIL_PREFIXES)
                or any(p in content for p in _FAIL_PHRASES)):
            failed.append(content[:120])

    if failed:
        summary = "\n".join(f"• {f}" for f in failed)
        return False, f"⚠️ בעיה טכנית — לא הצלחתי לגשת למערכת:\n{summary}\n\nרוצה שאנסה שוב?"
    return True, ""


# ══════════════════════════════════════════════════
# Singletons
# ══════════════════════════════════════════════════

dynamic_context = DynamicContext()
