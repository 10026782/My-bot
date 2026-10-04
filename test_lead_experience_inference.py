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

print("[5] כרטיס טיוטת ליד — הצעת השלמה גלויה וניתנת לעריכה")
from core.draft_flow import resolve_draft_reply

def _full_draft(**kw):
    d = ls.new_empty_draft("telegram")
    d.update({"name": "משה כהן", "phone": "0501234567", "domain": "recruitment", "note": "קבלן סלקום דרום"})
    d.update(kw)
    d["mode"], d["awaiting_field"] = "review", None
    return d

with patch("feature_flags.is_enabled", side_effect=_flags):
    d = ls.build_draft_from_text("משה כהן 0501234567 קבלן סלקום דרום", "telegram", "recruitment")
chk("טיוטה חדשה מקבלת הצעה כש-flag דלוק", d.get("experience_status") == X.WORKING_NOW and d.get("experience_hint") == "קבלן")
chk("ההצעה לא מוסיפה שדה חובה ולא משנה את מצב הטיוטה (אופציונלי, לא חוסם)",
    ls.first_missing_required_field(d) != "experience_status")

with patch("feature_flags.is_enabled", return_value=False):
    d_off = ls.build_draft_from_text("משה כהן 0501234567 קבלן סלקום דרום", "telegram", "recruitment")
chk("flag כבוי: אין הצעה בטיוטה", "experience_status" not in d_off and "experience_hint" not in d_off)

card = ls.render_lead_draft_card(_full_draft(experience_status=X.WORKING_NOW, experience_hint="קבלן"))
chk("הכרטיס מציג 'ניסיון בתחום (הצעה)' עם הערך והביטוי", "ניסיון בתחום (הצעה): " + X.WORKING_NOW in card and "הוסק מ'קבלן'" in card)
card2 = ls.render_lead_draft_card(_full_draft())
chk("בלי הצעה: אין שורת ניסיון בכרטיס", "ניסיון בתחום" not in card2)
card3 = ls.render_lead_draft_card(_full_draft(experience_status=X.NO_EXPERIENCE))
chk("ערך שעודכן ידנית (בלי ביטוי) מוצג בלי 'הצעה'", "ניסיון בתחום: " + X.NO_EXPERIENCE in card3 and "(הצעה)" not in card3)

print("[6] עריכה / ניקוי בכרטיס")
d = _full_draft(experience_status=X.WORKING_NOW, experience_hint="קבלן")
o = resolve_draft_reply("ערוך", d, ls.LEAD_DRAFT_SPEC)
o = resolve_draft_reply("ניסיון", d, ls.LEAD_DRAFT_SPEC)
chk("'ניסיון' מזוהה כשדה לעריכה ונשאל עם רשימה ממוספרת",
    d["awaiting_field"] == "experience_status" and "1. " + X.WORKING_NOW in o.message)
o = resolve_draft_reply("3", d, ls.LEAD_DRAFT_SPEC)
chk("בחירה במספר (3) -> ללא ניסיון, הביטוי המוסק נמחק, חוזרים לסקירה",
    d.get("experience_status") == X.NO_EXPERIENCE and "experience_hint" not in d and d["mode"] == "review")

for raw, want in (("עובד כיום בתחום", X.WORKING_NOW), ("לא ידוע", X.UNKNOWN), ("בעל ניסיון", X.EX_EXPERIENCED), ("1", X.WORKING_NOW)):
    dd = _full_draft()
    ok, err = ls.set_draft_field(dd, "experience_status", raw)
    chk(f"set_draft_field({raw!r}) -> {want}", ok and dd["experience_status"] == want)
dd = _full_draft(experience_status=X.WORKING_NOW, experience_hint="קבלן")
ok, err = ls.set_draft_field(dd, "experience_status", "נקה")
chk("'נקה' מנקה את הערך והביטוי", ok and dd["experience_status"] == "" and "experience_hint" not in dd)
dd = _full_draft(experience_status=X.WORKING_NOW)
ok, err = ls.set_draft_field(dd, "experience_status", "שטויות")
chk("ערך לא מוכר נדחה, הטיוטה לא משתנה", (not ok) and dd["experience_status"] == X.WORKING_NOW and "ניסיון לא מוכר" in err)
ok, err = ls.set_draft_field(_full_draft(), "experience_status", "5")
chk("מספר מחוץ לטווח נדחה", not ok)

print("[7] אישור: מה שבכרטיס הוא הערך הסופי — בלי הסקה שקטה נוספת")
pl = ls.draft_to_payload(_full_draft(experience_status=X.EX_EXPERIENCED, experience_hint="בעל ניסיון"))
chk("draft_to_payload מעביר את הערך כערך מפורש ומכבה הסקה", pl.experience_status == X.EX_EXPERIENCED and pl.infer_experience is False)
with patch("feature_flags.is_enabled", side_effect=_flags):
    f = ls.build_lead_fields(pl, None, "k")
    chk("נכתב בדיוק הערך שבכרטיס", f.get(LeadFields.EXPERIENCE_STATUS) == X.EX_EXPERIENCED)
    pl2 = ls.draft_to_payload(_full_draft(experience_status=""))   # הבעלים ניקה, הטקסט עדיין מכיל 'קבלן'
    f2 = ls.build_lead_fields(pl2, None, "k")
    chk("בעלים ניקה בכרטיס -> לא נכתב כלום, גם כש-flag דלוק והטקסט מכיל 'קבלן'",
        LeadFields.EXPERIENCE_STATUS not in f2)
chk("Score בטיוטה ללא שינוי (0)", pl.score == 0)

print(f"\nLead Experience inference: {_p}/{_p + _f} passed")
sys.exit(0 if _f == 0 else 1)
