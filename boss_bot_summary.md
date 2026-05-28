# Boss Bot — סיכום כל הקבצים שנוצרו/שונו
תאריך: 2026-05-28

---

## 1. `app.py` — קובץ הכניסה הראשי
> Flask app עם 5 routes: WhatsApp (Twilio XML), Telegram webhook, health check, worker trigger, home.
> כולל לולאת סוכן Claude עם tool calling, זיכרון שיחה per-user, וניהול תקציב קריאות API.

```python
"""
הבוס בוט v2.0 — Flask App
ארכיטקטורה: Native Tool Calling + Budget Protection + Proactive Worker
"""

import os
import logging
import requests as http_requests
from flask import Flask, request, jsonify, Response
from anthropic import Anthropic
from tools import TOOL_SCHEMAS, dispatch_tool
from memory import ConversationMemory
from worker import schedule_background_worker
from lead_qualifier import handle_lead_message, lead_sessions
from creative_generator import handle_creative_command

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ─── Env Vars ─────────────────────────────────────────────────────────────────
_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not _api_key:
    logger.critical("ANTHROPIC_API_KEY is not set — API calls will fail")
client = Anthropic(api_key=_api_key)

_telegram_token = os.environ.get("TELEGRAM_TOKEN", "")
if not _telegram_token:
    logger.critical("TELEGRAM_TOKEN is not set — Telegram webhook will not work")

# ─── Per-User Memory (max 500 users) ──────────────────────────────────────────
_user_memories: dict = {}
_MAX_MEMORY_USERS = 500


def _get_memory(user_id: str) -> ConversationMemory:
    if user_id not in _user_memories:
        if len(_user_memories) >= _MAX_MEMORY_USERS:
            oldest = next(iter(_user_memories))
            del _user_memories[oldest]
        _user_memories[user_id] = ConversationMemory(max_interactions=5)
    return _user_memories[user_id]


# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """אתה "הבוס בוט" – עוזר מנכ"ל, מנהל פרויקטים ומומחה אסטרטגי חריף וחד.
המנהל שלך (אלייהו) הוא בעל חזון ואופטימי מטבעו.
התפקיד שלך הוא להוות משקל נגד – לחפש את האותיות הקטנות, להציג את הסיכונים,
את נקודות התורפה בעסקאות, והיכן שותפים או מוכרים עלולים להטעות אותו.
היה קול ההיגיון הקר, הספקני והאנליטי.

כללים נוקשים:
1. תמיד תענה בעברית רהוטה, עסקית, חדה וללא גינונים מיותרים.
2. ברירת מחדל: תשובה של שורה עד שתיים בלבד. קצר, חד, לעניין.
3. רק אם ההודעה מתחילה ב-# — הפעל "מצב ניתוח עמוק" ותן ניתוח מורחב.
4. אל תחזור על שאלת המשתמש. אל תוסיף מילות מחמאה. ישר לגוף העניין."""

MAX_TOOL_TURNS = 2

# ─── Core Agent Loop ──────────────────────────────────────────────────────────
def run_agent(user_message: str, channel: str = "telegram", user_id: str = "default") -> str:
    mem = _get_memory(user_id)
    mem.add_user_message(user_message)
    messages = mem.get_messages()
    turn_count = 0
    response_text = "לא הצלחתי לעבד את הבקשה. נסה שוב."
    try:
        while turn_count < MAX_TOOL_TURNS:
            turn_count += 1
            logger.info(f"Agent turn {turn_count}/{MAX_TOOL_TURNS} | user={user_id}")
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000 if channel == "telegram" else 400,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            stop_reason = response.stop_reason
            if stop_reason == "end_turn":
                response_text = _extract_text(response)
                break
            elif stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info(f"Calling tool: {block.name} | input: {block.input}")
                        result = dispatch_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
                messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]
            else:
                logger.warning(f"Unexpected stop_reason: {stop_reason}")
                break
        else:
            logger.warning("MAX_TOOL_TURNS reached — cutting loop to prevent cost leak.")
            response_text = "הגעתי למגבלת הסיבובים. אנא פרט את הבקשה ונסה שוב."
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        response_text = f"שגיאה פנימית: {e}"
    mem.add_assistant_message(response_text)
    return response_text


def _extract_text(response) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""


# ─── Webhook Endpoints ────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "HEAD"])
def home():
    return "OK", 200


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook_twilio():
    from twilio.twiml.messaging_response import MessagingResponse
    user_message = request.values.get("Body", "").strip()
    sender = request.values.get("From", "unknown")
    if not user_message:
        return "OK", 200
    session = lead_sessions[sender]
    if session["state"].value != "done":
        reply = handle_lead_message(sender, user_message)
        if reply:
            resp = MessagingResponse()
            resp.message(reply)
            return Response(str(resp), mimetype="application/xml")
    reply = run_agent(user_message, channel="whatsapp", user_id=sender)
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp), 200, {"Content-Type": "text/xml"}


@app.route(f"/{_telegram_token}", methods=["POST"])
def telegram_webhook():
    logger.info("Telegram webhook hit")
    data = request.json or {}
    message_obj = data.get("message", {})
    user_message = message_obj.get("text", "")
    chat_id = message_obj.get("chat", {}).get("id")
    if not user_message:
        return "OK", 200
    telegram_url = f"https://api.telegram.org/bot{_telegram_token}/sendMessage"
    if "קריאייטיב" in user_message:
        reply = handle_creative_command(user_message, chat_id)
        try:
            http_requests.post(telegram_url, json={
                "chat_id": chat_id, "text": reply, "parse_mode": "Markdown"
            }, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send Telegram creative reply: {e}")
        return "OK", 200
    reply = run_agent(user_message, channel="telegram", user_id=str(chat_id))
    try:
        http_requests.post(telegram_url, json={"chat_id": chat_id, "text": reply}, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send Telegram reply: {e}")
    return "OK", 200


@app.route("/worker/trigger", methods=["POST"])
def worker_trigger():
    from worker import run_proactive_check
    result = run_proactive_check()
    return jsonify({"status": "ok", "result": result})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"})


# ─── Bootstrap — רץ גם תחת gunicorn ──────────────────────────────────────────
schedule_background_worker()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
```

---

## 2. `lead_qualifier.py` — כישור לידים + State Machine לוואטסאפ
> ניתוח לידים עם Claude (ציון 0-100, HOT/WARM/COLD), שאלות שלב-אחר-שלב לוואטסאפ,
> LRU store עם מגבלת 1000 משתמשים, ואפשרות איפוס session.

```python
import os
import logging
from enum import Enum
from collections import defaultdict, OrderedDict
from anthropic import Anthropic
from feature_flags import is_enabled

logger = logging.getLogger(__name__)

QUALIFICATION_SYSTEM = """
אתה מנתח לידים מקצועי עבור עסקי נדל"ן וייבוא סחורה מסין.
תפקידך לנתח כל ליד בקפדנות ולתת ציון מ-0 עד 100.

קריטריוני ניקוד:
- תקציב ורצינות פיננסית (25 נקודות)
- התאמה לתחומי הפעילות: נדל"ן / ייבוא רהיטים (25 נקודות)
- דחיפות ולוח זמנים ריאלי (20 נקודות)
- אמינות ונסיון קודם (20 נקודות)
- פוטנציאל לעסקאות חוזרות (10 נקודות)

החזר תמיד בפורמט:
ציון: [0-100]
סיווג: [HOT/WARM/COLD]
סיכום: [2-3 שורות]
סיכון עיקרי: [משפט אחד]
צעד הבא: [פעולה ספציפית אחת]
"""

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _client


def qualify_lead(lead_info: str, tenant_id: str = "default") -> dict:
    if not is_enabled("LEAD_QUALIFIER"):
        return _mock_qualify(lead_info)
    try:
        response = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=QUALIFICATION_SYSTEM,
            messages=[{"role": "user", "content": f"נתח את הליד הבא:\n{lead_info}"}],
        )
        return _parse_response(response.content[0].text)
    except Exception as e:
        logger.error(f"qualify_lead error: {e}")
        return {"score": 0, "tier": "COLD", "summary": "שגיאה בניתוח הליד.", "risk": str(e), "next_step": "נסה שנית"}


def batch_qualify(leads: list[str], tenant_id: str = "default") -> list[dict]:
    results = []
    for lead in leads:
        result = qualify_lead(lead, tenant_id)
        result["raw"] = lead
        results.append(result)
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def format_lead_report(qualification: dict) -> str:
    tier_emoji = {"HOT": "🔥", "WARM": "🟡", "COLD": "🧊"}.get(qualification.get("tier", ""), "❓")
    score = qualification.get("score", 0)
    return (
        f"{tier_emoji} *ציון ליד: {score}/100*\n"
        f"📋 {qualification.get('summary', '')}\n"
        f"⚠️ סיכון: {qualification.get('risk', '')}\n"
        f"➡️ צעד הבא: {qualification.get('next_step', '')}"
    )


def _parse_response(text: str) -> dict:
    result = {"score": 0, "tier": "COLD", "summary": "", "risk": "", "next_step": ""}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("ציון:"):
            try:
                result["score"] = int("".join(filter(str.isdigit, line.split(":", 1)[1])))
            except ValueError:
                pass
        elif line.startswith("סיווג:"):
            raw = line.split(":", 1)[1].strip().upper()
            result["tier"] = raw if raw in ("HOT", "WARM", "COLD") else "COLD"
        elif line.startswith("סיכום:"):
            result["summary"] = line.split(":", 1)[1].strip()
        elif line.startswith("סיכון עיקרי:"):
            result["risk"] = line.split(":", 1)[1].strip()
        elif line.startswith("צעד הבא:"):
            result["next_step"] = line.split(":", 1)[1].strip()
    return result


def _mock_qualify(lead_info: str) -> dict:
    return {
        "score": 50,
        "tier": "WARM",
        "summary": f"ניתוח מקדים (מצב ללא API): {lead_info[:80]}...",
        "risk": "LEAD_QUALIFIER לא מופעל בסביבה זו.",
        "next_step": "הפעל LEAD_QUALIFIER=true ב-env variables.",
    }


# ─── WhatsApp Lead Session State Machine ─────────────────────────────────────

class LeadState(Enum):
    INTRO = "intro"
    BUDGET = "budget"
    TIMELINE = "timeline"
    DONE = "done"


_FLOW = [
    (LeadState.INTRO,    'מה אתה מחפש? נדל"ן / ייבוא / אחר?'),
    (LeadState.BUDGET,   "מה התקציב שלך? (₪ / $)"),
    (LeadState.TIMELINE, "מה לוח הזמנים שלך? (מיידי / חודש / גמיש)"),
]


def _new_session() -> dict:
    return {"state": LeadState.INTRO, "answers": {}}


_RESET_KEYWORDS = {"איפוס", "reset", "restart", "התחל מחדש"}
_MAX_SESSIONS = 1000


class _LRUSessionStore:
    """מאגר sessions עם פינוי LRU — מגביל זיכרון ל-1000 משתמשים."""

    def __init__(self, maxsize: int = _MAX_SESSIONS):
        self._store: OrderedDict = OrderedDict()
        self._maxsize = maxsize

    def __getitem__(self, key: str) -> dict:
        if key not in self._store:
            self._store[key] = _new_session()
            if len(self._store) > self._maxsize:
                self._store.popitem(last=False)
        else:
            self._store.move_to_end(key)
        return self._store[key]

    def get(self, key: str, default=None):
        return self._store.get(key, default)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


lead_sessions = _LRUSessionStore()


def handle_lead_message(sender: str, message: str) -> str | None:
    if message.strip() in _RESET_KEYWORDS:
        lead_sessions.delete(sender)
        return 'בוצע איפוס! מה אתה מחפש? נדל"ן / ייבוא / אחר?'
    session = lead_sessions[sender]
    state = session["state"]
    if state == LeadState.DONE:
        return None
    step_index = next((i for i, (s, _) in enumerate(_FLOW) if s == state), 0)
    session["answers"][state.value] = message
    if step_index + 1 < len(_FLOW):
        next_state, next_question = _FLOW[step_index + 1]
        session["state"] = next_state
        return next_question
    session["state"] = LeadState.DONE
    lead_info = "\n".join(f"{k}: {v}" for k, v in session["answers"].items())
    result = qualify_lead(lead_info, sender)
    return format_lead_report(result)
```

---

## 3. `creative_generator.py` — יצירת תוכן שיווקי
> מייצר תוכן שיווקי בעברית לפי 5 תבניות. מזהה זוויות שיווקיות ומשלב אותן עם פרטי הנכס.

```python
import os
import logging
from anthropic import Anthropic
from feature_flags import is_enabled

logger = logging.getLogger(__name__)

_PERSONA = (
    "אתה קופירייטר עסקי דובר עברית ברמה גבוהה, המתמחה בנדל\"ן ובייבוא סחורות מסין. "
    "הסגנון: ישיר, שכנועי, ללא מילים מיותרות. ממוקד בתועלת ללקוח."
)

TEMPLATES: dict[str, str] = {
    "property_listing": (
        "כתוב מודעת נדל\"ן מוכרת לנכס הבא. "
        "כלול: כותרת חזקה, 3 יתרונות מפתח, קריאה לפעולה. עד 120 מילה."
    ),
    "import_offer": (
        "כתוב הצעת מחיר שיווקית לסחורה המיובאת. "
        "הדגש: איכות, מחיר תחרותי, אמינות הספק. עד 100 מילה."
    ),
    "whatsapp_followup": (
        "כתוב הודעת WhatsApp קצרה ואנושית למעקב אחרי ליד שלא ענה. "
        "טון: ידידותי אך עסקי. עד 50 מילה."
    ),
    "email_proposal": (
        "כתוב אימייל מקצועי עם הצעה עסקית. "
        "מבנה: פתיחה חמה, בעיה+פתרון, קריאה לפעולה ברורה. עד 200 מילה."
    ),
    "social_post": (
        "כתוב פוסט לרשתות חברתיות (פייסבוק / לינקדאין). "
        "כלול האשטאג רלוונטי. עד 80 מילה."
    ),
}

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _client


def generate(template_name: str, context: str, tone: str = "professional") -> str:
    if template_name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        return f"❌ תבנית לא קיימת. אפשרויות: {available}"
    if not is_enabled("CREATIVE_GENERATOR"):
        return _mock_generate(template_name, context)
    instruction = TEMPLATES[template_name]
    tone_note = {"casual": "סגנון: קליל ולא פורמלי.", "urgent": "סגנון: דחוף, צור מסגרת זמן."}.get(tone, "")
    prompt = f"{instruction}\n{tone_note}\n\nפרטי ההקשר:\n{context}"
    try:
        response = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_PERSONA,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"generate error: {e}")
        return f"❌ שגיאה בייצור תוכן: {e}"


def generate_ab_variants(template_name: str, context: str, n: int = 2) -> list[str]:
    n = min(max(n, 2), 4)
    variants = []
    tones = ["professional", "casual", "urgent", "professional"]
    for i in range(n):
        variant = generate(template_name, context, tone=tones[i])
        variants.append(f"גרסה {i + 1}:\n{variant}")
    return variants


def list_templates() -> str:
    lines = ["📝 תבניות יצירת תוכן זמינות:\n"]
    descriptions = {
        "property_listing": "מודעת נדל\"ן",
        "import_offer": "הצעת מחיר לייבוא",
        "whatsapp_followup": "מעקב WhatsApp",
        "email_proposal": "אימייל הצעה עסקית",
        "social_post": "פוסט לרשתות חברתיות",
    }
    for key, desc in descriptions.items():
        lines.append(f"• `{key}` — {desc}")
    return "\n".join(lines)


def _mock_generate(template_name: str, context: str) -> str:
    return (
        f"[מצב הדגמה — CREATIVE_GENERATOR לא מופעל]\n"
        f"תבנית: {template_name}\n"
        f"הקשר: {context[:100]}...\n"
        f"הפעל CREATIVE_GENERATOR=true ב-env variables לתוצאות אמיתיות."
    )


# ─── Telegram Command Handler ─────────────────────────────────────────────────

_KEYWORD_TO_TEMPLATE = {
    'נדל"ן':   "property_listing",
    "נדלן":    "property_listing",
    "נדל":     "property_listing",
    "ייבוא":   "import_offer",
    "יבוא":    "import_offer",
    "וואטסאפ": "whatsapp_followup",
    "ווטסאפ":  "whatsapp_followup",
    "מייל":    "email_proposal",
    "פוסט":    "social_post",
    "רשתות":   "social_post",
    "תשואה":   "property_listing",
    "ביטחון":  "property_listing",
    "עיתוי":   "property_listing",
    "קהילה":   "property_listing",
    "דחיפות":  "property_listing",
}

_ANGLE_CONTEXT = {
    "תשואה":  'זווית: תשואה — השקעה שמניבה תשואה יציבה בנדל"ן',
    "ביטחון": 'זווית: ביטחון — נכס בטוח כהגנה מפני אי-ודאות כלכלית',
    "עיתוי":  'זווית: עיתוי — הרגע הנכון להיכנס לשוק הנדל"ן',
    "קהילה":  'זווית: קהילה — סביבת מגורים איכותית ותחושת שייכות',
    "דחיפות": 'זווית: דחיפות — הזדמנות מוגבלת בזמן שאסור לפספס',
}


def handle_creative_command(text: str, chat_id: str) -> str:
    parts = text.split("קריאייטיב", 1)
    context = parts[1].strip() if len(parts) > 1 else ""
    if not context:
        return list_templates()
    template = "property_listing"
    enriched_context = context
    for keyword, tmpl in _KEYWORD_TO_TEMPLATE.items():
        if keyword in context:
            template = tmpl
            if keyword in _ANGLE_CONTEXT:
                enriched_context = f"{_ANGLE_CONTEXT[keyword]}\nפרטים: {context}"
            break
    result = generate(template, enriched_context)
    label = template.replace("_", " ").title()
    return f"*{label}*\n\n{result}"
```

---

## 4. `requirements.txt` — תלויות הפרויקט
> נוסף `requests` שהיה חסר.

```
python-telegram-bot
anthropic
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
httpx
schedule
flask
twilio
requests
gunicorn
pyTelegramBotAPI
```

---

## 5. `tools/__init__.py` — חשיפת ה-tools module
> היה ריק — נוספו exports כדי ש-`app.py` יוכל לייבא.

```python
from tools.schemas import TOOL_SCHEMAS
from tools.dispatcher import dispatch_tool
```

---

## 6. `memory.py` — זיכרון שיחה per-user
> `ConversationMemory` thread-safe עם `deque` — שומר עד 5 אינטראקציות אחרונות לכל משתמש.

```python
"""
memory.py — ניהול זיכרון שיחה קשיח
Memory Length = 5 אינטראקציות (user+assistant = זוג אחד).
"""

from collections import deque
from threading import Lock


class ConversationMemory:
    def __init__(self, max_interactions: int = 5):
        self.max_interactions = max_interactions
        self._messages: deque = deque(maxlen=max_interactions * 2)
        self._lock = Lock()

    def add_user_message(self, text: str):
        with self._lock:
            self._messages.append({"role": "user", "content": text})

    def add_assistant_message(self, text: str):
        with self._lock:
            self._messages.append({"role": "assistant", "content": text})

    def get_messages(self) -> list:
        with self._lock:
            return list(self._messages)

    def clear(self):
        with self._lock:
            self._messages.clear()
```

---

## 7. `worker.py` — Background Worker פרואקטיבי
> סורק Airtable לדדליינים מתקרבים ושולח התראות לטלגרם.
> רץ ב-daemon thread ומופעל גם דרך `POST /worker/trigger`.

```python
"""
worker.py — Background Worker פרואקטיבי ("הנודניק")
מופעל על ידי Cron Job ב-Render (08:00 ו-18:00) דרך POST /worker/trigger
"""

import os
import logging
import requests
from datetime import datetime, timedelta, timezone
from threading import Thread
from time import sleep

logger = logging.getLogger(__name__)

AIRTABLE_TOKEN    = os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_ID  = os.environ.get("AIRTABLE_BASE_ID", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "")

DEADLINE_FIELD = "Deadline"
STATUS_FIELD   = "Status"
NAME_FIELD     = "Name"
TASKS_TABLE    = os.environ.get("AIRTABLE_TASKS_TABLE", "Tasks")
NUDGE_AFTER_HOURS = 3


def run_proactive_check() -> str:
    logger.info("Proactive worker triggered.")
    try:
        urgent_tasks = _scan_airtable_deadlines(days_ahead=3)
        if not urgent_tasks:
            logger.info("No urgent tasks found.")
            return "אין משימות דחופות."
        for task in urgent_tasks:
            message = _build_urgency_message(task)
            _send_telegram(message)
        return f"נשלחו {len(urgent_tasks)} התראות."
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        return f"שגיאה ב-Worker: {e}"


def _scan_airtable_deadlines(days_ahead: int = 3) -> list:
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    today = datetime.now(tz=timezone.utc)
    cutoff = today + timedelta(days=days_ahead)
    params = {
        "filterByFormula": f"AND({{Status}} != 'Done', IS_BEFORE({{{DEADLINE_FIELD}}}, '{cutoff.strftime('%Y-%m-%d')}'))",
        "fields[]": [NAME_FIELD, DEADLINE_FIELD, STATUS_FIELD],
        "maxRecords": 20,
    }
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{TASKS_TABLE}"
    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    records = r.json().get("records", [])
    urgent = []
    for rec in records:
        fields = rec.get("fields", {})
        deadline_str = fields.get(DEADLINE_FIELD, "")
        if not deadline_str:
            continue
        try:
            deadline = datetime.fromisoformat(deadline_str).replace(tzinfo=timezone.utc)
            days_left = (deadline - today).days
            urgent.append({
                "name": fields.get(NAME_FIELD, "ללא שם"),
                "deadline": deadline_str,
                "days_left": days_left,
                "status": fields.get(STATUS_FIELD, ""),
            })
        except ValueError:
            continue
    return urgent


def _build_urgency_message(task: dict) -> str:
    days = task["days_left"]
    name = task["name"]
    deadline = task["deadline"]
    status = task["status"]
    if days < 0:
        urgency = f"⚠️ *עבר הדד-ליין!* לפני {abs(days)} ימים"
    elif days == 0:
        urgency = "🔴 *היום הוא הדד-ליין!*"
    elif days == 1:
        urgency = "🟠 *מחר הוא הדד-ליין*"
    else:
        urgency = f"🟡 *{days} ימים לדד-ליין*"
    return (
        f"{urgency}\n"
        f"📋 משימה: *{name}*\n"
        f"📅 תאריך: {deadline}\n"
        f"סטטוס נוכחי: {status or 'לא הוגדר'}\n\n"
        f"אלייהו — טפל בזה. פספוס יגרור עלויות/נזק. האם לעדכן סטטוס?"
    )


def _send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials missing — skipping notification.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload, timeout=10)
    if not r.ok:
        logger.error(f"Telegram send failed: {r.text}")
    else:
        logger.info("Telegram notification sent.")


def _nudge_loop():
    while True:
        sleep(NUDGE_AFTER_HOURS * 3600)
        logger.info("Nudge loop waking up — re-checking deadlines.")
        run_proactive_check()


def schedule_background_worker():
    thread = Thread(target=_nudge_loop, daemon=True, name="NudgeWorker")
    thread.start()
    logger.info("Background nudge worker started.")
```

---

## 8. `profile.py` — פרופיל משתמש עם Airtable Backend
> זיכרון ארוך-טווח ב-Airtable: פרויקטים, מטרות, אנשי קשר, העדפות, התראות. Cache 60 שניות.

```python
"""
profile.py — User Profile Layer (Airtable Backend)
טבלה: Profile | שורה אחת | שדה ProfileData = JSON כ-Long Text.
"""

import json
import os
import time
import requests
from threading import Lock
from datetime import datetime

_lock = Lock()

_AT_TOKEN   = os.environ.get("AIRTABLE_TOKEN", "")
_AT_BASE    = os.environ.get("AIRTABLE_BASE_ID", "")
_AT_TABLE   = os.environ.get("AIRTABLE_PROFILE_TABLE", "Profile")
_AT_HEADERS = {"Authorization": f"Bearer {_AT_TOKEN}", "Content-Type": "application/json"}
_AT_URL     = f"https://api.airtable.com/v0/{_AT_BASE}/{_AT_TABLE}"

_cache: dict = {"profile": None, "record_id": None, "ts": 0}
_CACHE_TTL = 60

DEFAULT_PROFILE = {
    "name": "אלייהו",
    "tone": "direct",
    "active_projects": [],
    "goals": [],
    "focus_areas": [],
    "known_contacts": {},
    "preferences": {
        "response_length": "short",
        "risk_sensitivity": "high",
        "language": "he",
    },
    "events": [],
    "reminders_pending": [],
    "last_updated": None,
}


def load_profile() -> dict:
    with _lock:
        if _cache["profile"] and (time.time() - _cache["ts"]) < _CACHE_TTL:
            return dict(_cache["profile"])
        try:
            r = requests.get(
                _AT_URL,
                headers=_AT_HEADERS,
                params={"filterByFormula": "{Name}='main'", "maxRecords": 1},
                timeout=10,
            )
            r.raise_for_status()
            records = r.json().get("records", [])
            if records:
                rec = records[0]
                raw = rec["fields"].get("ProfileData", "{}")
                profile = json.loads(raw)
                merged = {**DEFAULT_PROFILE, **profile}
                _cache["profile"] = merged
                _cache["record_id"] = rec["id"]
                _cache["ts"] = time.time()
                return dict(merged)
            else:
                _create_profile_record()
                return dict(DEFAULT_PROFILE)
        except Exception as e:
            print(f"[profile] load error: {e}", flush=True)
            return dict(DEFAULT_PROFILE)


def save_profile(profile: dict):
    with _lock:
        profile["last_updated"] = datetime.now().isoformat()
        payload = json.dumps(profile, ensure_ascii=False)
        try:
            record_id = _cache.get("record_id")
            if record_id:
                r = requests.patch(
                    f"{_AT_URL}/{record_id}",
                    headers=_AT_HEADERS,
                    json={"fields": {"ProfileData": payload}},
                    timeout=10,
                )
            else:
                r = requests.post(
                    _AT_URL,
                    headers=_AT_HEADERS,
                    json={"fields": {"Name": "main", "ProfileData": payload}},
                    timeout=10,
                )
                _cache["record_id"] = r.json().get("id")
            r.raise_for_status()
            _cache["profile"] = profile
            _cache["ts"] = time.time()
        except Exception as e:
            print(f"[profile] save error: {e}", flush=True)


def _create_profile_record():
    try:
        payload = json.dumps(DEFAULT_PROFILE, ensure_ascii=False)
        r = requests.post(
            _AT_URL,
            headers=_AT_HEADERS,
            json={"fields": {"Name": "main", "ProfileData": payload}},
            timeout=10,
        )
        r.raise_for_status()
        _cache["record_id"] = r.json().get("id")
        _cache["profile"] = dict(DEFAULT_PROFILE)
    except Exception as e:
        print(f"[profile] create error: {e}", flush=True)


def process_events(events: list) -> list:
    alerts = []
    today = datetime.now().date()
    for e in events:
        try:
            etype = e.get("type")
            if etype == "birthday":
                d = datetime.fromisoformat(e["date"]).date().replace(year=today.year)
                days_left = (d - today).days
                remind_before = e.get("remind_days_before", 3)
                if 0 <= days_left <= remind_before:
                    suffix = "היום! 🎂" if days_left == 0 else f"בעוד {days_left} ימים"
                    alerts.append(f"🎂 {e['title']} — {suffix}")
            elif etype == "shabbat":
                if today.weekday() in (4, 5):
                    alerts.append("🕯️ ערב שבת / שבת — בדוק לוחות זמנים")
            elif etype == "deadline":
                d = datetime.fromisoformat(e["date"]).date()
                days_left = (d - today).days
                if 0 <= days_left <= e.get("remind_days_before", 2):
                    suffix = "היום!" if days_left == 0 else f"בעוד {days_left} ימים"
                    alerts.append(f"⏰ דד-ליין: {e['title']} — {suffix}")
        except Exception:
            continue
    return alerts


def build_profile_context(profile: dict) -> str:
    lines = ["\n--- הקשר אישי (זיכרון ארוך טווח) ---"]
    if profile.get("active_projects"):
        lines.append(f"פרויקטים פעילים: {', '.join(profile['active_projects'])}")
    if profile.get("goals"):
        lines.append(f"מטרות עכשוויות: {' | '.join(profile['goals'][:3])}")
    if profile.get("focus_areas"):
        lines.append(f"תחומי עיסוק: {', '.join(profile['focus_areas'])}")
    if profile.get("known_contacts"):
        contacts = ", ".join(f"{n} ({r})" for n, r in list(profile["known_contacts"].items())[:5])
        lines.append(f"אנשי קשר: {contacts}")
    risk = profile.get("preferences", {}).get("risk_sensitivity", "high")
    lines.append(f"רמת ספקנות: {risk}")
    alerts = process_events(profile.get("events", []))
    if alerts:
        lines.append("התראות להיום: " + " | ".join(alerts))
    lines.append("--- סוף הקשר אישי ---")
    return "\n".join(lines)


def add_project(name: str):
    p = load_profile()
    if name not in p["active_projects"]:
        p["active_projects"].append(name)
        save_profile(p)

def remove_project(name: str):
    p = load_profile()
    p["active_projects"] = [x for x in p["active_projects"] if x != name]
    save_profile(p)

def add_goal(goal: str):
    p = load_profile()
    if goal not in p["goals"]:
        p["goals"].insert(0, goal)
        p["goals"] = p["goals"][:10]
        save_profile(p)

def add_contact(name: str, role: str):
    p = load_profile()
    p["known_contacts"][name] = role
    save_profile(p)

def update_preference(key: str, value):
    p = load_profile()
    p["preferences"][key] = value
    save_profile(p)
```

---

## סיכום שינויים עיקריים שבוצעו

| קובץ | מה השתנה |
|------|----------|
| `app.py` | נוצר/שוכתב — per-user memory, LRU, safe env vars, gunicorn bootstrap, exception handling |
| `lead_qualifier.py` | נוצר + שודרג — LeadState machine, LRU session store, reset support |
| `creative_generator.py` | נוצר + שודרג — 5 תבניות, זוויות שיווקיות, enriched context |
| `requirements.txt` | נוסף `requests` |
| `tools/__init__.py` | היה ריק — נוספו exports |
| `memory.py` | הובא מ-bot.boss |
| `worker.py` | הובא מ-bot.boss |
| `profile.py` | הובא מ-bot.boss |
