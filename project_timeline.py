# project_timeline.py — Boss Bot Master Plan Timeline
# יוצר טבלת לוח זמנים ב-Airtable ומשתלב בדוח היומי
#
# שימוש:
#   python project_timeline.py --create-table   # יצירת טבלה + מילוי משימות
#   python project_timeline.py --status         # סטטוס נוכחי

import os
import logging
from datetime import date, timedelta

from tools.airtable_gateway import airtable_create
from tools.airtable_read_adapter import AirtableReadError, list_records
from tma_api import record_fields

logger = logging.getLogger(__name__)

TIMELINE_TABLE = os.environ.get("TIMELINE_TABLE", "ProjectTimeline")

TODAY = date.today()


def _d(offset: int) -> str:
    """תאריך יחסי מהיום"""
    return (TODAY + timedelta(days=offset)).isoformat()


TIMELINE_TASKS = [
    # ═══ שלב א — ניקוי ובדיקות (ימים 1-3) ═══
    {
        "Phase": "א — ניקוי ובדיקות", "Task": "Code Review מלא — כל הקבצים",
        "Description": "קריאת כל הקבצים, זיהוי bugs קיימים, מיפוי dependencies",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(0), "Due": _d(1), "Phase_Order": 1,
    },
    {
        "Phase": "א — ניקוי ובדיקות", "Task": "דיבאג — MAX_TOOL_TURNS + timeout",
        "Description": "בדיקת שרשרת כלים, תיקון תקיעות, וידוא AGENT_TIMEOUT=25 תקין",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(1), "Due": _d(2), "Phase_Order": 1,
    },
    {
        "Phase": "א — ניקוי ובדיקות", "Task": "בדיקת Airtable Tools — כל הטבלאות",
        "Description": "וידוא airtable_get / airtable_add / update עובדים על CRM + Cashflow + Tasks",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(1), "Due": _d(3), "Phase_Order": 1,
    },
    {
        "Phase": "א — ניקוי ובדיקות", "Task": "בדיקת Google Tools — Gmail + Calendar + Drive",
        "Description": "OAuth refresh, send_email, read_emails, create_event, search_drive — עם נתונים אמיתיים",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(2), "Due": _d(3), "Phase_Order": 1,
    },
    # ═══ שלב ב — Multi-Domain Router (ימים 4-7) ═══
    {
        "Phase": "ב — Multi-Domain", "Task": "בניית domain_router.py",
        "Description": "מיפוי מספר וואטסאפ/ערוץ → domain. real_estate / import / recruitment / investors",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(4), "Due": _d(5), "Phase_Order": 2,
    },
    {
        "Phase": "ב — Multi-Domain", "Task": "domain_prompts.py — פרומפט ייעודי לכל דומיין",
        "Description": "4 system prompts שונים + load_domain_prompt() לפי channel_id",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(5), "Due": _d(6), "Phase_Order": 2,
    },
    {
        "Phase": "ב — Multi-Domain", "Task": "בדיקת ניתוב — 4 דומיינים בפועל",
        "Description": "שליחת הודעות מ-4 מספרים שונים, וידוא שכל ערוץ מקבל context נכון",
        "Owner": "מפתח + אליהו", "Status": "open", "Priority": "medium",
        "Start": _d(6), "Due": _d(7), "Phase_Order": 2,
    },
    # ═══ שלב ג — Memory & Context (ימים 8-11) ═══
    {
        "Phase": "ג — Memory & Context", "Task": "shared_memory.py — ידע משותף לכל דומיינים",
        "Description": "ידע כללי על אליהו, עסקים, חוקי ברזל — זמין לכולם",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(8), "Due": _d(9), "Phase_Order": 3,
    },
    {
        "Phase": "ג — Memory & Context", "Task": "lead_memory.py — היסטוריית ליד לפי טלפון",
        "Description": "load_lead_history(phone) — שולף שיחות קודמות מ-Airtable/memory",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(9), "Due": _d(10), "Phase_Order": 3,
    },
    {
        "Phase": "ג — Memory & Context", "Task": "בדיקת memory pipeline מקצה לקצה",
        "Description": "shared → domain → lead — וידוא build_context() מחזיר context נכון",
        "Owner": "מפתח", "Status": "open", "Priority": "medium",
        "Start": _d(10), "Due": _d(11), "Phase_Order": 3,
    },
    # ═══ שלב ד — Lead Qualifier & CRM (ימים 12-15) ═══
    {
        "Phase": "ד — Lead Qualifier", "Task": "שדרוג lead_qualifier.py — scoring לפי דומיין",
        "Description": "כל דומיין שאלות שונות, scoring שונה, threshold שונה",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(12), "Due": _d(13), "Phase_Order": 4,
    },
    {
        "Phase": "ד — Lead Qualifier", "Task": "CRM auto-save — ליד חדש → Airtable אוטומטי",
        "Description": "כשמזוהה ליד חדש, נשמר אוטומטית ב-CRM עם score + domain + source",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(13), "Due": _d(14), "Phase_Order": 4,
    },
    {
        "Phase": "ד — Lead Qualifier", "Task": "Follow-up אוטומטי — תזכורות לפי CRM status",
        "Description": "contacted → 2 ימים, proposal → 5 ימים, negotiation → 1 יום",
        "Owner": "מפתח", "Status": "open", "Priority": "medium",
        "Start": _d(14), "Due": _d(15), "Phase_Order": 4,
    },
    # ═══ שלב ה — Scheduler & Daily Reports (ימים 16-18) ═══
    {
        "Phase": "ה — Scheduler & Reports", "Task": "שדרוג daily_digest — הוספת ProjectTimeline",
        "Description": "הדוח היומי יציג משימות פרויקט: פתוחות, הגיע דד-ליין, הושלמו היום",
        "Owner": "מפתח", "Status": "done", "Priority": "high",
        "Start": _d(16), "Due": _d(17), "Phase_Order": 5,
    },
    {
        "Phase": "ה — Scheduler & Reports", "Task": "daily_collector — שיפור זיהוי נתונים",
        "Description": "הוספת זיהוי: לידים חדשים, עסקאות, תשלומים, פגישות שלא נשמרו",
        "Owner": "מפתח", "Status": "open", "Priority": "medium",
        "Start": _d(17), "Due": _d(18), "Phase_Order": 5,
    },
    # ═══ שלב ו — דיבאגים ו-QA (ימים 19-23) ═══
    {
        "Phase": "ו — QA & Debug", "Task": "סימולציית שיחות אמיתיות — כל דומיין",
        "Description": "20 שיחות סימולציה לפחות: ליד חדש, פולואפ, הצעת מחיר, תשלום",
        "Owner": "מפתח + אליהו", "Status": "open", "Priority": "high",
        "Start": _d(19), "Due": _d(21), "Phase_Order": 6,
    },
    {
        "Phase": "ו — QA & Debug", "Task": "בדיקת approval flow — כל הפעולות הרגישות",
        "Description": "send_email, airtable_add, create_event — כולן עוברות אישור ידני",
        "Owner": "מפתח + אליהו", "Status": "open", "Priority": "high",
        "Start": _d(21), "Due": _d(22), "Phase_Order": 6,
    },
    {
        "Phase": "ו — QA & Debug", "Task": "עומס + rate limiting — בדיקת חוסן",
        "Description": "20+ הודעות מקבילות, RATE_LIMIT_PER_MIN, circuit breaker",
        "Owner": "מפתח", "Status": "open", "Priority": "medium",
        "Start": _d(22), "Due": _d(23), "Phase_Order": 6,
    },
    # ═══ שלב ז — הטמעה (ימים 24-28) ═══
    {
        "Phase": "ז — הטמעה", "Task": "Deploy ל-Render — גרסה מלאה",
        "Description": "העלאת כל הקבצים, env vars, הגדרת Webhooks לכל מספרי וואטסאפ",
        "Owner": "מפתח", "Status": "open", "Priority": "high",
        "Start": _d(24), "Due": _d(25), "Phase_Order": 7,
    },
    {
        "Phase": "ז — הטמעה", "Task": "חיבור 4 מספרי וואטסאפ + טלגרם",
        "Description": "Twilio webhook לכל מספר, בדיקת routing אמיתי, וידוא טלגרם פעיל",
        "Owner": "מפתח + אליהו", "Status": "open", "Priority": "high",
        "Start": _d(25), "Due": _d(26), "Phase_Order": 7,
    },
    {
        "Phase": "ז — הטמעה", "Task": "Monitoring — לוגים + התראות שגיאה",
        "Description": "Render logs, error alerts לטלגרם, בדיקת scheduler 07:30 + 23:00",
        "Owner": "מפתח", "Status": "open", "Priority": "medium",
        "Start": _d(26), "Due": _d(27), "Phase_Order": 7,
    },
    {
        "Phase": "ז — הטמעה", "Task": "Go Live — הפעלה מלאה",
        "Description": "הדוח הראשון, תשובה ראשונה מליד אמיתי, וידוא כל המערכת פעילה",
        "Owner": "מפתח + אליהו", "Status": "open", "Priority": "high",
        "Start": _d(27), "Due": _d(28), "Phase_Order": 7,
    },
]


# ══════════════════════════════════════════════════
# Airtable CRUD
# ══════════════════════════════════════════════════

def create_timeline_records() -> dict:
    """מוסיף את כל המשימות לטבלת ProjectTimeline"""
    results = {"created": 0, "errors": 0}

    for task in TIMELINE_TASKS:
        fields = {k: task[k] for k in
                  ("Phase", "Task", "Description", "Owner",
                   "Status", "Priority", "Start", "Due", "Phase_Order")}
        try:
            record = airtable_create(
                TIMELINE_TABLE,
                fields,
                source="project_timeline",
                timeout=10,
            )
            if not record:
                raise RuntimeError("Airtable timeline POST failed")
            results["created"] += 1
            print(f"✅ נוצר: {task['Task']}")
        except Exception as e:
            results["errors"] += 1
            print(f"❌ שגיאה: {task['Task']} — {e}")

    return results


def get_timeline_summary() -> dict:
    """שולף סטטוס מ-Airtable לדוח היומי"""
    api_key = os.environ.get("AIRTABLE_API_KEY", "")
    base_id = os.environ.get("AIRTABLE_BASE_ID", "")
    if not api_key or not base_id:
        return {}

    today_str = date.today().isoformat()
    try:
        formula = "OR(Status='open', Status='in_progress')"
        records = list_records(
            TIMELINE_TABLE,
            formula,
            max_records=None,
            sort=[{"field": "Due", "direction": "asc"}],
            paginate=False,
            timeout=10,
        )

        overdue = []
        due_today = []
        upcoming = []
        in_progress = []

        for r in records:
            f    = record_fields(r)
            due  = f.get("Due", "")
            entry = {
                "task":     f.get("Task", "?"),
                "phase":    f.get("Phase", ""),
                "due":      due,
                "priority": f.get("Priority", ""),
            }
            status = f.get("Status", "")
            if status == "in_progress":
                in_progress.append(entry)
            elif due < today_str:
                overdue.append(entry)
            elif due == today_str:
                due_today.append(entry)
            elif due <= (date.today() + timedelta(days=3)).isoformat():
                upcoming.append(entry)

        # הושלמו היום
        try:
            done_records = list_records(
                TIMELINE_TABLE,
                f"AND(Status='done', Due='{today_str}')",
                max_records=None,
                paginate=False,
                timeout=10,
            )
            done_today = len(done_records)
        except AirtableReadError as e:
            if e.status_code is None:
                raise
            done_today = 0

        return {
            "overdue":     overdue,
            "due_today":   due_today,
            "upcoming":    upcoming,
            "in_progress": in_progress,
            "done_today":  done_today,
            "total_open":  len(records),
            "phases_done": _count_phases_done(),
        }

    except AirtableReadError as e:
        logger.error(f"get_timeline_summary error: {e.cause or e}")
        return {}
    except Exception as e:
        logger.error(f"get_timeline_summary error: {e}")
        return {}


def _count_phases_done() -> list:
    """בודק אילו שלבים הושלמו לגמרי"""
    try:
        records = list_records(
            TIMELINE_TABLE,
            max_records=None,
            fields=["Phase", "Status"],
            paginate=False,
            timeout=10,
        )
        phases: dict = {}
        for r in records:
            f = record_fields(r)
            p = f.get("Phase", "")
            s = f.get("Status", "")
            if p not in phases:
                phases[p] = {"total": 0, "done": 0}
            phases[p]["total"] += 1
            if s == "done":
                phases[p]["done"] += 1
        return [p for p, v in phases.items() if v["total"] > 0 and v["done"] == v["total"]]
    except Exception:
        return []


# ══════════════════════════════════════════════════
# Daily Digest Block
# ══════════════════════════════════════════════════

def format_timeline_digest_block(summary: dict) -> str:
    """מחזיר בלוק טקסט מפורמט לדוח הבוקר."""
    if not summary:
        return ""

    lines = ["\n🗓️ *פרויקט בוט בוס — מצב יישום*"]

    if summary.get("phases_done"):
        lines.append(f"✅ *הושלמו:* {' | '.join(summary['phases_done'])}")

    if summary.get("in_progress"):
        lines.append(f"⚙️ *בביצוע ({len(summary['in_progress'])})* :")
        for t in summary["in_progress"][:2]:
            lines.append(f"   • {t['task']}")

    if summary.get("overdue"):
        lines.append(f"🔴 *באיחור ({len(summary['overdue'])})* :")
        for t in summary["overdue"][:2]:
            lines.append(f"   • {t['task']} [{t['due']}]")

    if summary.get("due_today"):
        lines.append(f"⚡ *להיום ({len(summary['due_today'])})* :")
        for t in summary["due_today"]:
            lines.append(f"   • {t['task']}")

    if summary.get("upcoming"):
        lines.append(f"📌 *ב-3 ימים ({len(summary['upcoming'])})* :")
        for t in summary["upcoming"][:2]:
            lines.append(f"   • {t['task']} [{t['due']}]")

    if summary.get("done_today"):
        lines.append(f"🎉 *הושלמו היום:* {summary['done_today']} משימות")

    total = summary.get("total_open", 0)
    if total:
        lines.append(f"📊 *סה\"כ פתוח:* {total} משימות")

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if "--create-table" in sys.argv:
        print(f"\n📋 יוצר {len(TIMELINE_TASKS)} משימות ב-Airtable...")
        print(f"   טבלה: {TIMELINE_TABLE}")
        results = create_timeline_records()
        print(f"\n✅ הושלמו: {results['created']} | ❌ שגיאות: {results['errors']}")
    elif "--status" in sys.argv:
        summary = get_timeline_summary()
        print(format_timeline_digest_block(summary))
    else:
        print("שימוש:")
        print("  python project_timeline.py --create-table   # יצירת משימות ב-Airtable")
        print("  python project_timeline.py --status         # סטטוס נוכחי")
