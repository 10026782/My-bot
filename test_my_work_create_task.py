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
raise SystemExit(1 if fails else 0)
