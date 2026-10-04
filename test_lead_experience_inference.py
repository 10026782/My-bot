"""Experience Status — הסקה דטרמיניסטית ביצירת ליד (סיווג/סינון בלבד, לא Score)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("TELEGRAM_TOKEN", "123456:TESTTOKEN")

import feature_flags
from airtable_schema import ExperienceStatus as X, LeadFields
from core import lead_service as ls

_p = _f = 0
def chk(label, cond):
    global _p, _f
    if cond: _p += 1; print("  PASS:", label)
    else: _f += 1; print("  FAIL:", label)

inf = ls.infer_experience_status

print("[1] הסקה מטקסט")
chk("קבלן -> עובד כיום", inf("קבלן סלקום דרום") == X.WORKING_NOW)
chk("קבלנים (רבים)", inf("רשימת קבלנים") == X.WORKING_NOW)
chk("עובד בתחום -> עובד כיום", inf("עובד בתחום כבר שנים") == X.WORKING_NOW)
chk("בעל ניסיון -> בעל ניסיון לא עובד כיום", inf("בעל ניסיון בתקשורת") == X.EX_EXPERIENCED)
chk("הכתיב 'נסיון' נתמך", inf("בעל נסיון") == X.EX_EXPERIENCED and inf("אין נסיון") == X.NO_EXPERIENCE)
chk("ללא ניסיון -> ללא ניסיון", inf("ללא ניסיון קודם") == X.NO_EXPERIENCE)
chk("חדש בתחום -> ללא ניסיון", inf("חדש בתחום") == X.NO_EXPERIENCE)
chk("קבלן לשעבר -> לא עובד כיום (לשעבר גובר)", inf("קבלן לשעבר") == X.EX_EXPERIENCED)
chk("לא עובד כיום גובר על 'בתחום'", inf("לא עובד כיום בתחום") == X.EX_EXPERIENCED)
chk("קבלן בעל ניסיון -> עובד כיום (קבלן גובר על בעל ניסיון)", inf("קבלן בעל ניסיון") == X.WORKING_NOW)
chk("ללא ניסיון גובר על קבלן", inf("קבלן ללא ניסיון") == X.NO_EXPERIENCE)

print("[2] אין אות ברור = אין ערך")
chk("'ליד חדש' (תחילית פקודה) אינו אות", inf("ליד חדש | משה כהן | 0501234567") == "")
chk("'חדש' לבד אינו אות", inf("חדש") == "")
chk("'מתחיל לעבוד' אינו אות", inf("מתחיל לעבוד מחר") == "")
chk("טקסט ריק", inf("") == "" and inf(None, "") == "")
chk("הערך המוחזר תמיד אחד מהערכים החיים (או ריק)",
    all(inf(t) in (*X.ALL, "") for t in ("קבלן", "בעל ניסיון", "ללא ניסיון", "x", "לשעבר")))

print("[3] build_lead_fields — flag, ערך מפורש, יצירה בלבד")
def payload(**kw):
    base = dict(name="משה", phone="0501234567", summary="קבלן סלקום", source="owner_dictation", score=0)
    base.update(kw)
    return ls.LeadPayload(**base)

os.environ.pop("LEAD_EXPERIENCE_INFERENCE", None)
f = ls.build_lead_fields(payload(), None, "k")
chk("flag כבוי (ברירת מחדל): אין Experience Status", LeadFields.EXPERIENCE_STATUS not in f)
chk("flag כבוי: Score נשאר כמו שנשלח (0), לא מושפע", f[LeadFields.SCORE] == 0)

os.environ["LEAD_EXPERIENCE_INFERENCE"] = "true"
f = ls.build_lead_fields(payload(), None, "k")
chk("flag דלוק: 'קבלן' -> עובד כיום", f.get(LeadFields.EXPERIENCE_STATUS) == X.WORKING_NOW)
chk("flag דלוק: Score לא השתנה", f[LeadFields.SCORE] == 0)
f = ls.build_lead_fields(payload(summary="ליד חדש | משה"), None, "k")
chk("flag דלוק ואין אות: השדה לא נכתב בכלל", LeadFields.EXPERIENCE_STATUS not in f)
f = ls.build_lead_fields(payload(experience_status=X.NO_EXPERIENCE), None, "k")
chk("ערך מפורש תקף גובר על ההסקה", f.get(LeadFields.EXPERIENCE_STATUS) == X.NO_EXPERIENCE)
f = ls.build_lead_fields(payload(experience_status="עובד בסלקום"), None, "k")
chk("ערך מפורש לא תקף נדחה ולא נכתב (typecast כבוי)", LeadFields.EXPERIENCE_STATUS not in f)
os.environ["LEAD_EXPERIENCE_INFERENCE"] = "false"
f = ls.build_lead_fields(payload(experience_status=X.WORKING_NOW), None, "k")
chk("ערך מפורש תקף נכתב גם כשה-flag כבוי", f.get(LeadFields.EXPERIENCE_STATUS) == X.WORKING_NOW)

print("[4] ליד קיים לעולם לא נדרס; יצירה חדשה כן מקבלת")
from unittest.mock import patch
import tools.airtable_gateway as gw
captured = {}
class _Id:
    memory_key = "boss_hq:owner"; tenant_id = "boss_hq"; role = "owner"; user_id = "u"; display_name = "o"
    external_id = "1"; allowed_domains = []; domain_id = "recruitment"

def _flags(name):
    return name == "LEAD_EXPERIENCE_INFERENCE"   # רק הסקה דלוקה; EMERGENCY_STOP_* כבוי

with patch("feature_flags.is_enabled", side_effect=_flags), \
     patch.object(gw, "airtable_patch", lambda t, rid, fields, source="": captured.update(patch=dict(fields)) or True), \
     patch.object(gw, "airtable_create", lambda t, fields, source="": captured.update(create=dict(fields)) or {"id": "recNEW"}), \
     patch.object(ls, "resolve_owner", lambda identity, owner_user_id="": ("recOWNER", "u")), \
     patch.object(ls, "_run_post_write_enrichment", lambda *a, **k: None):
    r1 = ls.create_lead(_Id(), payload(), source_module="test", existing_id="recEXIST", manage_action_contract=False)
    chk("עדכון ליד קיים בוצע", r1.ok and r1.action == "updated" and "patch" in captured)
    chk("עדכון ליד קיים: Experience Status לא נשלח (לא דורס ערך ידני)",
        LeadFields.EXPERIENCE_STATUS not in captured.get("patch", {}))
    r2 = ls.create_lead(_Id(), payload(), source_module="test", existing_id=None, manage_action_contract=False)
    chk("יצירת ליד חדש בוצעה", r2.ok and r2.action == "created" and "create" in captured)
    chk("יצירה חדשה: Experience Status נשלח, Score=0 ללא שינוי",
        captured.get("create", {}).get(LeadFields.EXPERIENCE_STATUS) == X.WORKING_NOW
        and captured["create"][LeadFields.SCORE] == 0)

print(f"\nLead Experience inference: {_p}/{_p + _f} passed")
sys.exit(0 if _f == 0 else 1)
