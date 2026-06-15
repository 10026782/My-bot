# BOSS Bot — Claude Skills Architecture
**גרסה:** 1.0 | **עודכן:** 11/06/2026  
**מיקום בריפו:** `.claude/skills/CLAUDE_SKILLS.md`

> מסמך זה הוא מקור האמת לכל הסקילס של Claude בפרויקט BOSS Bot.  
> שני סוכנים — Developer Agent (בנייה) ו-Operator Agent (בוט חי).  
> Claude טוען סקיל לפי טריגר — לא הכל בכל שיחה.

---

## מבנה תיקיות

```
.claude/
└── skills/
    ├── CLAUDE_SKILLS.md          ← המסמך הזה (אינדקס + כל הסקילס)
    ├── dev/
    │   ├── SKILL_01_arch.md
    │   ├── SKILL_02_schema.md
    │   ├── SKILL_03_security.md
    │   ├── SKILL_04_airtable.md
    │   └── SKILL_05_qa.md
    └── operator/
        ├── SKILL_06_router.md
        ├── SKILL_07_lead_crm.md
        ├── SKILL_08_real_estate.md
        ├── SKILL_09_whatsapp.md
        └── SKILL_10_digest.md
```

---

## חוקי בסיס (חלים על כל סקיל)

1. **Anti-hallucination:** אל תדווח על הצלחה ללא הוכחת tool call — `_at_patch 200 OK` חייב להופיע בלוג לפני כל "נשמר".
2. **Feature Flags:** כל פיצ'ר חדש — `flags.is_enabled("X")` לפני ביצוע. ברירת מחדל = כבוי.
3. **Airtable Security:** כל כתיבה עוברת `_sanitize_fields()` + `tenant_id` + `owner_user_id`.
4. **Router is Dumb:** `dispatcher.py` מסווג בלבד — אף פעם לא מבצע.
5. **One File Per Task:** Claude Code נוגע בקובץ אחד לכל משימה. לא מיזוג עיוור.
6. **No Fake Control:** אין כפתור "נשמר" ללא אישור Airtable 200.

---

## DEVELOPER SKILLS (בנייה ופיתוח)

---

### SKILL_01 — Architecture Standard

```yaml
name: boss-arch-standard
trigger: "בנה פיצ'ר חדש | קובץ חדש | refactor | blueprint | module"
stack: Python 3.11 / Flask / Anthropic Claude Sonnet 4.6 / Render / Airtable
```

**חוקים קשיחים:**
- כל קובץ חדש → נרשם ב-`FILE_OWNERSHIP.md` לפני כתיבה
- כל פיצ'ר → נרשם ב-`ROADMAP.md` (N/F) לפני כתיבה
- `app.py` — לא נוגעים בלוגיקה עסקית. רק: `webhook → router → agent → reply`
- כיוון תלויות: `crm/lead_* → airtable_tools` (לא הפוך)
- כלים (`airtable_tools`, `gmail_tools`) — stateless בלבד

**מבנה קובץ חדש:**
```python
# module_name.py
# תפקיד: תיאור חד-משפטי
# קורא מ: X
# כותב ל: Y
# feature flag: FEATURE_X

import logging
logger = logging.getLogger(__name__)

def main_function(param: str) -> dict:
    """תיאור. קלט: X. פלט: Y."""
    pass
```

**אסור:**
- ייבוא circular (`crm` ← `airtable_tools` ← `crm`)
- State גלובלי מחוץ ל-`memory/` או `crm/`
- LLM call בתוך `memory_store`, `lead_memory`, `shared_memory`

---

### SKILL_02 — Airtable Schema Enforcer

```yaml
name: boss-airtable-schema
trigger: "שדה חדש | טבלה חדשה | schema | Airtable write | _at_patch | _at_post"
base_id: app4bcgoX7t0HUVnm   # PRODUCTION BASE — אומת 2026-06-15 (appefldVZAKnrge36 = base ישן/snapshot, לא בשימוש)
```

**כללי כתיבה:**
```python
# תמיד לפני כתיבה:
fields = _sanitize_fields(raw_fields)  # מסיר None, מנקה ערכים
fields["tenant_id"] = TENANT_ID
fields["owner_user_id"] = OWNER_ID

# 422 = שדה לא קיים או ערך select לא חוקי
# 403 = גם base_id שגוי וגם הרשאה חסרה
```

**שדות formula — read-only (אסור לכתוב):**
- `טמפרטורה` / `tier` — מחושב מ-`Score` אוטומטית
- `אימוגי טמפרטורה` — formula
- `תוצאת ליד` (הצגה) — formula

**ערכי Select חוקיים — Leads:**

| שדה | ערכים חוקיים |
|-----|-------------|
| `status` | `new`, `waiting_call`, `active`, `high_confidence`, `waiting_response`, `archived`, `not_relevant`, `done`, `awaiting_call` |
| `Business Outcome` | `open`, `needs_followup`, `meeting_scheduled`, `converted`, `not_relevant`, `lost`, `duplicate`, `archived` |
| `Score` | מספר 0–100 (integer) |

**טיירים (קריאה בלבד מ-formula):**
- קר / Cold: 0–39
- חם / Warm: 40–59  
- לוהט / Hot: 60–79
- רותח / Ultra Hot: 80–100

**Airtable quirks:**
```python
# טבלאות עם עברית — שם מלא כולל סוגריים:
TABLE = "תשלומים (Payments)"
TABLE = "משימות (Tasks)"
TABLE = "Leads"  # ← ללא עברית

# 403 לא אומר רק הרשאה — יכול להיות שם טבלה שגוי
# אין 404 על טבלה לא קיימת — תמיד 403
```

---

### SKILL_03 — Security & Auth

```yaml
name: boss-security
trigger: "auth | tenant | permission | Twilio webhook | signature | owner check"
```

**שכבות אבטחה:**
```python
# 1. Twilio — חתימת webhook חובה
from twilio.request_validator import RequestValidator
validator = RequestValidator(TWILIO_AUTH_TOKEN)
if not validator.validate(url, params, signature):
    return "Forbidden", 403

# 2. TMA — initData validation
from identity import resolve_identity
identity = resolve_identity(init_data)
if not identity or identity["role"] != "owner":
    return jsonify({"error": "unauthorized"}), 403

# 3. Airtable — tenant isolation
fields["tenant_id"] = TENANT_ID  # חובה בכל כתיבה
```

**Worker endpoint — authentication חובה:**
```python
@app.route("/worker/trigger", methods=["POST"])
def worker_trigger():
    token = request.headers.get("X-Worker-Token")
    if token != WORKER_SECRET:
        return "Unauthorized", 401
```

**אסור:**
- `/worker/trigger` ללא auth
- Airtable read ללא `tenant_id` filter
- Approval ללא receipt persistence

---

### SKILL_04 — CRM & Lead Logic

```yaml
name: boss-crm-lead
trigger: "ליד | lead | CRM | outcome | scoring | qualifier | lead_capture"
```

**זרימת ליד:**
```
WhatsApp/Telegram → lead_capture.py → Airtable Leads
                         ↓
                  lead_qualifier.py (score 0–100)
                         ↓
                  lead_memory.py (זיכרון קצר)
                         ↓
                  TMA Lead Card (PATCH/outcome/task)
```

**Scoring logic:**
```python
# score קובע tier (formula ב-Airtable):
# 0-39  → קר/Cold
# 40-59 → חם/Warm  
# 60-79 → לוהט/Hot
# 80+   → רותח/Ultra Hot

# HOT leads filter:
filter = "score >= 70"  # לא לפלטר לפי tier (formula field)
```

**כתיבה ל-Lead — field mapping נכון:**
```python
fields = {
    LeadFields.SCORE: score,        # "Score" — כתיב
    LeadFields.STATUS: status,      # "status" — select חוקי
    LeadFields.OUTCOME: outcome,    # "Business Outcome" — select חוקי
    LeadFields.NEXT_STEP: action,   # "Next Action" — text
    LeadFields.OWNER: owner_name,   # "Owner" — text
    # ❌ אסור: LeadFields.TIER — formula, read-only
}
```

**_execute_tma_write — ניקוי לפני כתיבה:**
```python
def _clean_fields_select_values(fields: dict) -> dict:
    """מנקה double-quotes מערכי select לפני שליחה ל-Airtable."""
    select_fields = [LeadFields.STATUS, LeadFields.OUTCOME, LeadFields.NEXT_STEP]
    for field in select_fields:
        if field in fields and fields[field]:
            val = str(fields[field])
            while val.startswith(('"', "'")) and val.endswith(('"', "'")):
                val = val[1:-1]
            fields[field] = val.strip().lower()
    return fields
```

---

### SKILL_05 — QA & Testing

```yaml
name: boss-qa
trigger: "בדיקה | test | smoke | verify | validation | לפני deploy"
```

**Smoke test — לפני כל PR:**
```bash
# 1. syntax check
python -m py_compile app.py dispatcher.py crm.py tma_api.py

# 2. imports check  
python -c "from app import app; print('✅ imports OK')"

# 3. Airtable connectivity
python -c "from airtable_tools import at_list; print(at_list('Leads', max_records=1))"

# 4. Lead Card endpoints
curl -X GET https://my-bot-XXX.render.com/api/leads \
  -H "X-TMA-Init: <init_data>"
```

**Known false positives (לא לתקן — לתעד):**
- `ZoneInfoNotFoundError: Asia/Jerusalem` — local only, Render OK
- `core_knowledge.py` fake approval — known issue, tracked

**Render deploy verification:**
```bash
# ודא שה-commit הנכון עלה:
curl https://my-bot-XXX.render.com/health
# חפש commit hash בלוג הראשון של Render
```

---

## OPERATOR SKILLS (בוט חי)

---

### SKILL_06 — Tenant Router

```yaml
name: boss-tenant-router
trigger: "הודעה נכנסת | webhook | classify | route | domain detect"
```

**עיקרון: Router is Dumb by Design**
```python
# dispatcher.py — מסווג בלבד, לא מבצע
def classify(message: str, identity: dict) -> dict:
    return {
        "intent": detect_intent(message),
        "domain": detect_domain(identity["phone"]),
        "risk": assess_risk(message),
        "channel": identity["channel"]
    }
    # ❌ אסור: לשלוח הודעה, לכתוב ל-Airtable, לקרוא LLM
```

**דומיינים פעילים:**
| דומיין | זיהוי | פרומפט |
|--------|-------|--------|
| `real_estate` | מספרי BlueView / Tiberias | domain_prompts.REAL_ESTATE |
| `recruitment` | ברנץ' האח | domain_prompts.RECRUITMENT |
| `furniture` | עץ מלא / ייבוא | domain_prompts.FURNITURE |
| `general` | ברירת מחדל | domain_prompts.GENERAL |

---

### SKILL_07 — Lead CRM Operations

```yaml
name: boss-lead-ops
trigger: "ליד נכנס | outcome | תוצאה עסקית | next action | task | archived | converted"
```

**Lead lifecycle:**
```
new → waiting_call → active → [converted/archived/lost/not_relevant]
```

**TMA Lead Card endpoints:**
```
GET  /api/leads              ← רשימה
GET  /api/leads/<id>         ← כרטיס
PATCH /api/leads/<id>        ← עדכון שדות (score, status, next_step, owner)
POST /api/leads/<id>/outcome ← תוצאה עסקית (מפעיל approval flow)
POST /api/leads/<id>/task    ← יצירת משימה מקושרת
```

**Approval flow:**
```python
# owner בלבד — ישיר ל-Airtable
# non-owner — נשמר ב-Approvals table, owner מאשר
if identity["role"] == "owner":
    _at_patch("Leads", lead_id, clean_fields)
else:
    _create_approval_record(action, fields)
    # ❌ אסור להחזיר "pending_approval" אם יצירת approval נכשלה
```

---

### SKILL_08 — Real Estate Logic

```yaml
name: boss-real-estate
trigger: "BlueView | טבריה | נכס | תשלום | שוכר | קונה | ROI | Tiberias"
```

**פרויקט BlueView — טבריה:**
- שותפים: אליהו, אורי, אהרון
- טבלה: `BLUE VIEW BUYERS`
- סטטוס עסקאות: `Active`, `Done`, `Cancelled`

**חישוב ROI:**
```python
roi = (monthly_rent * 12 / total_property_cost) * 100
```

**ביטול עסקה — פרוטוקול:**
```python
# אי-תשלום > 30 יום:
update_lead_status(lead_id, "archived")
update_deal_status(deal_id, "CANCELED_FAILED")
create_urgent_task(owner="eliyahu", title="בדיקה משפטית — ביטול עסקה")
```

**Daily Digest — תשלומים:**
```python
upcoming = crm_upcoming_payments(days_ahead=7)
overdue = crm_overdue_payments()
# ← נשלח ב-08:00 כל יום ל-Telegram
```

---

### SKILL_09 — WhatsApp & Channels

```yaml
name: boss-whatsapp
trigger: "WhatsApp | Twilio | Meta Cloud | inbound | outbound | lead נכנס"
```

**ערוץ פעיל: Twilio (לא Meta Cloud API)**

**inbound flow:**
```
Twilio webhook → signature validation → junk guard → duplicate guard
              → lead_capture.py → Airtable Leads → score → memory
```

**guards חובה לפני כל עיבוד:**
```python
# 1. Twilio signature
if not validate_twilio_signature(request):
    return "Forbidden", 403

# 2. Junk guard
if is_junk_message(body):
    return "OK", 200  # בשקט

# 3. Duplicate guard  
if is_duplicate(phone, body, window_seconds=60):
    return "OK", 200
```

**Outbound — approval only:**
```python
# ❌ אסור: שליחת הודעה יוצאת ללא אישור owner
# ✅ מותר: יצירת approval record + המתנה לאישור
```

**Emergency stop:**
```python
if flags.WHATSAPP_EMERGENCY_STOP:
    return "Service temporarily unavailable", 503
```

---

### SKILL_10 — Daily Digest & Scheduler

```yaml
name: boss-digest
trigger: "דוח בוקר | digest | scheduler | 08:00 | BossDigest | סיכום יומי"
```

**מה הדוח כולל (לפי סדר):**
1. ☀️ כותרת + תאריך
2. 📅 תשלומים קרובים (7 ימים)
3. 🚨 תשלומים באיחור
4. 🔥 לידים לפי טמפרטורה (Hot/Warm/Cold/Ultra Hot)
5. 🤝 עסקאות פתוחות
6. 📋 ProjectTimeline
7. 💪 סיום

**Lead summary block (N05):**
```python
def _build_lead_summary() -> str:
    leads = _at_list("Leads", filter="status != 'archived'")
    hot = [l for l in leads if l.get("Score", 0) >= 70]
    warm = [l for l in leads if 40 <= l.get("Score", 0) < 70]
    cold = [l for l in leads if l.get("Score", 0) < 40]
    return f"🔥 לוהט/רותח: {len(hot)}\n🟡 חם: {len(warm)}\n🧊 קר: {len(cold)}"
```

**Scheduler — jobs פעילים:**
```python
# 08:00 כל יום — Daily Digest
scheduler.add_job(send_daily_digest, 'cron', hour=8, minute=0)

# ❌ כבוי: INTERACTION_ENGINE (עלות API)
# ❌ כבוי: AUTO_FOLLOWUP (לא מוכן לפרודקשן)
```

---

## סיכום — מה בנוי vs מה בפיתוח

| סקיל | סטטוס | Feature Flag |
|------|--------|-------------|
| Arch Standard | ✅ פעיל | — |
| Airtable Schema | ✅ פעיל | — |
| Security & Auth | ✅ פעיל | — |
| CRM & Lead Logic | ✅ פעיל | `LEAD_CAPTURE`, `LEAD_SCORING` |
| QA & Testing | 🟡 חלקי | — |
| Tenant Router | ✅ פעיל | `DOMAIN_ROUTING` |
| Lead CRM Ops | ✅ פעיל | `LEAD_CAPTURE` |
| Real Estate | ✅ פעיל | `DOMAIN_PROMPTS` |
| WhatsApp | 🟡 Twilio בלבד | `WHATSAPP_INBOUND` |
| Daily Digest | 🟡 חלקי (N05 פתוח) | `DAILY_DIGEST` |

---

## הוראות שימוש ל-Claude Code

בתחילת כל session:
```
סרוק את .claude/skills/CLAUDE_SKILLS.md וטען את הסקילס הרלוונטיים.
פרויקט: BOSS Bot. Stack: Python/Flask/Airtable/Render.
חוק עליון: Anti-hallucination — אל תדווח הצלחה ללא tool evidence.
```

טריגרים לדוגמה:
- "תוסיף שדה חדש ל-Leads" → SKILL_02 (Airtable Schema)
- "ליד נכנס מ-WhatsApp" → SKILL_09 + SKILL_07
- "בנה endpoint חדש" → SKILL_01 + SKILL_03
- "מה הסטטוס של הדוח הבוקר" → SKILL_10
