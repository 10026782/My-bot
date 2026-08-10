from http.server import BaseHTTPRequestHandler, HTTPServer
import json

PROJECTS = {
    "global_kpis": {"overdue_tasks": 3, "hot_leads_count": 5},
    "exceptions": ["2 משימות עברו את הדדליין"],
    "projects": [
        {"id": "p1", "slug": "real-estate", "name": "נדל״ן", "emoji": "🏠", "mode": "business", "project_type": "Project", "domain": "real_estate", "status": "פעיל", "status_color": "green", "kpi": {"label": "לידים חמים", "value": 5}, "exception": None},
        {"id": "p2", "slug": "import", "name": "יבוא", "emoji": "📦", "mode": "business", "project_type": "Project", "domain": "import", "status": "דורש תשומת לב", "status_color": "yellow", "kpi": {"label": "משימות פתוחות", "value": 8}, "exception": "ספק ממתין למענה"},
        {"id": "p3", "slug": "partnerships", "name": "שותפויות", "emoji": "🤝", "mode": "business", "project_type": "Project", "domain": "partnerships", "status": "פעיל", "status_color": "green", "kpi": {"label": "עסקאות", "value": 2}, "exception": None},
        {"id": "p4", "slug": "personal", "name": "אישי", "emoji": "🌿", "mode": "personal", "project_type": "Personal", "domain": "personal", "status": "שקט", "status_color": "green", "kpi": {"label": "נכסים", "value": 4}, "exception": None},
    ],
}

LEADS = {"count": 3, "leads": [
    {"id": "l1", "name": "יוסי כהן", "phone": "050-1234567", "status": "Hot", "score": 88, "domain": "real_estate", "source": "WhatsApp"},
    {"id": "l2", "name": "דנה לוי", "phone": "052-7654321", "status": "Warm", "score": 64, "domain": "real_estate", "source": "Telegram"},
    {"id": "l3", "name": "אורי ישראלי", "phone": "054-2223333", "status": "New", "score": 42, "domain": "real_estate", "source": "Web"},
]}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,PUT,OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        payload = {
            "/api/projects": PROJECTS,
            "/api/leads": LEADS,
            "/api/approvals": {"count": 1, "approvals": [{"id": "a1", "action": "עדכון ליד", "requested_by": "owner", "requested_at": "היום 09:20", "risk_level": "medium", "context_type": "lead", "context_id": "l1", "status": "pending"}]},
            "/api/assets": {"count": 2, "total_value": 1800000, "total_debt": 650000, "total_equity": 1150000, "my_equity": 900000, "monthly_income": 8200, "assets": [{"id": "as1", "name": "דירה בתל אביב", "type": "נדל״ן", "current_value": 1500000, "mortgage_balance": 550000, "equity": 950000, "ownership_pct": 100, "my_equity": 950000, "monthly_income": 6200, "status": "פעיל"}]},
            "/api/finance/pulse": {"period": "החודש", "income": {"amount": 28000, "count": 4}, "pending": {"amount": 9000, "count": 2}, "overdue": {"amount": 3200, "count": 1}, "expenses": {"amount": 14000, "count": 8}, "net": 14000, "recent": []},
            "/api/activity": {"count": 3, "entries": [{"id": "e1", "title": "ליד חדש", "summary": "יוסי כהן נכנס למערכת", "channel": "WhatsApp", "domain": "real_estate", "timestamp": "לפני 20 דק׳", "sentiment": "positive"}]},
            "/api/health": {"status": "ok", "services": {"airtable": "ok", "telegram": "ok", "anthropic": "ok"}, "emergency_flags": {}, "active_emergency": [], "checked_at": "היום 09:30"},
            "/api/owner/control-center": {"ok": True, "system_health": {"health_percent": 92, "working_count": 11, "partial_count": 2, "broken_count": 0}, "critical_systems": [], "approvals": {"pending_count": 1, "pending": [], "recent_executed": [], "recent_receipts": []}, "permissions": [], "business_language": {"lead_status": [], "lead_outcome": [], "lead_tier": []}, "strategic_pipeline": {"stage_counts": {"Idea": 2, "Pending Decision": 1}, "total": 3, "active": 3}, "blockers": [], "next_actions": ["לטפל בליד החם ביותר"], "warnings": []},
            "/api/game/today": {"today": "2026-08-11", "tasks": [{"id": "t1", "task": "לחזור ליוסי כהן", "coins": 20, "status": "Todo", "who": "אני"}, {"id": "t2", "task": "לאשר הצעת ספק", "coins": 15, "status": "Done", "who": "אני"}], "world": {"id": "w1", "name": "שבוע הצמיחה", "number": 1, "boss": "הבוס הגדול", "prize": "יום חופש", "coins_earned": 35, "coins_target": 100, "progress_pct": 35}, "total_coins": 35},
            "/api/game/checkin": {"date": "2026-08-11", "tasks": [], "total_xp": 0, "updated_at": "היום", "updated_by": "owner", "world": None},
            "/api/ventures": {"count": 2, "ventures": [{"id": "v1", "name": "קו מוצרים חדש", "stage": "Research", "domain": "import", "conviction": "Medium", "estimated_potential": 250000, "target_decision_date": "2026-09-01", "decision_log": "", "next_action": "לבדוק ספקים", "notes": "", "linked_contacts": [], "owner": [], "converted_to_deal": [], "created_at": "2026-08-01"}]},
        }.get(path, {"ok": True})
        self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers(); self.wfile.write(json.dumps(payload, ensure_ascii=False).encode())

    def do_POST(self): self.do_GET()
    def do_PATCH(self): self.do_GET()
    def do_PUT(self): self.do_GET()

HTTPServer(("127.0.0.1", 5051), Handler).serve_forever()
