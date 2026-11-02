"""POST /api/owner/my-work (יצירת משימה חוזרת) + שיקוף ב-Boss Daily."""
import os
for k, v in {"TELEGRAM_TOKEN": "1:a", "ANTHROPIC_API_KEY": "x", "ELIYAHU_CHAT_ID": "1",
             "AIRTABLE_API_KEY": "x", "AIRTABLE_BASE_ID": "appx"}.items():
    os.environ.setdefault(k, v)
from types import SimpleNamespace
from flask import Flask
import tma_api as t
from airtable_schema import TaskFields as F

app = Flask(__name__)
calls = []
t._resolve_profile_record_id = lambda uid: "recPROFILE0000000"
t._queue_or_owner_execute = lambda action, payload, ident, label: (calls.append((action, payload)) or ("a", {"ok": True}, 200))
owner = SimpleNamespace(is_owner=True, user_id="u1")
view = t.owner_my_work_create.__wrapped__
fails = 0

def post(body, ident=owner):
    with app.test_request_context(json=body):
        r = view(ident)
        resp, code = r if isinstance(r, tuple) else (r, 200)
        return code, resp.get_json()

def check(name, cond):
    global fails
    print(("PASS" if cond else "FAIL"), name)
    fails += not cond

code, _ = post({"title": "x"}, SimpleNamespace(is_owner=False, user_id="u"))
check("non-owner forbidden", code == 403)
code, _ = post({"title": "  "})
check("blank title rejected", code == 400)
code, _ = post({"title": "x", "topic": "bogus"})
check("bad topic rejected", code == 400)
code, _ = post({"title": "x", "cadence": "hourly"})
check("bad cadence rejected", code == 400)
code, _ = post({"title": "x", "cadence": "weekly"})
check("weekly without date rejected", code == 400)
code, _ = post({"title": "דוח שיווק", "topic": "שיווק", "cadence": "daily"})
f = calls[-1][1]["fields"]
check("daily created w/ today anchor", code == 200 and f[F.RECURRENCE] == "Daily" and f[F.DUE_DATE] and f[F.TOPIC] == "שיווק" and f[F.OWNER] == ["recPROFILE0000000"])
code, _ = post({"title": "חד פעמי"})
f = calls[-1][1]["fields"]
check("one-time has no cadence", code == 200 and F.RECURRENCE not in f)
# ── מועד אחרון ──
from core import task_writer
today = task_writer.local_today()
fut = (today.replace(day=1)).isoformat()
import datetime as _dt
tomorrow = (today + _dt.timedelta(days=1)).isoformat()
code, _ = post({"title": "x", "kind": "deadline"})
check("deadline without date rejected", code == 400)
code, _ = post({"title": "x", "kind": "deadline", "due_date": (today - _dt.timedelta(days=1)).isoformat()})
check("deadline in past rejected", code == 400)
code, _ = post({"title": "x", "kind": "deadline", "cadence": "daily", "due_date": tomorrow})
check("deadline can't be recurring", code == 400)
code, _ = post({"title": "הצעת מחיר", "kind": "deadline", "due_date": tomorrow})
f = calls[-1][1]["fields"]
check("deadline created w/ flag + date, no cadence", code == 200 and f[F.HARD_DEADLINE] is True and f[F.DUE_DATE] == tomorrow and F.RECURRENCE not in f)

t_ = today.isoformat()
y_ = (today - _dt.timedelta(days=1)).isoformat()
check("state last_day", t._deadline_state({F.HARD_DEADLINE: True, F.DUE_DATE: t_}, t_) == "last_day")
check("state active", t._deadline_state({F.HARD_DEADLINE: True, F.DUE_DATE: tomorrow}, t_) == "active")
check("state missed", t._deadline_state({F.HARD_DEADLINE: True, F.DUE_DATE: y_}, t_) == "missed")
check("regular task has no state", t._deadline_state({F.DUE_DATE: y_}, t_) is None)
recs = [
    {"id": "recA", "fields": {F.NAME: "m", F.HARD_DEADLINE: True, F.DUE_DATE: y_, F.OWNER: ["recP"]}},
    {"id": "recB", "fields": {F.NAME: "l", F.HARD_DEADLINE: True, F.DUE_DATE: t_, F.OWNER: ["recP"]}},
    {"id": "recC", "fields": {F.NAME: "d", F.HARD_DEADLINE: True, F.DUE_DATE: t_, F.OWNER: ["recP"], F.STATUS: "בוצע"}},
    {"id": "recD", "fields": {F.NAME: "plain", F.DUE_DATE: t_, F.OWNER: ["recP"]}},
]
res = t._deadlines_open(recs, "recP", t_, claim_ownerless=False)
check("deadlines_open: missed first, done/plain excluded", [r["id"] for r in res] == ["recA", "recB"])
raise SystemExit(1 if fails else 0)
