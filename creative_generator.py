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
    """מייצר תוכן שיווקי לפי תבנית נבחרת והקשר עסקי."""
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
    """מייצר N גרסאות שונות לאותו תוכן לבדיקת A/B."""
    n = min(max(n, 2), 4)
    variants = []
    tones = ["professional", "casual", "urgent", "professional"]
    for i in range(n):
        variant = generate(template_name, context, tone=tones[i])
        variants.append(f"גרסה {i + 1}:\n{variant}")
    return variants


def list_templates() -> str:
    """מחזיר רשימה של כל התבניות הזמינות."""
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
    'נדל"ן':  "property_listing",
    "נדלן":   "property_listing",
    "נדל":    "property_listing",
    "ייבוא":  "import_offer",
    "יבוא":   "import_offer",
    "וואטסאפ": "whatsapp_followup",
    "ווטסאפ":  "whatsapp_followup",
    "מייל":   "email_proposal",
    "פוסט":   "social_post",
    "רשתות":  "social_post",
    "תשואה":  "property_listing",
    "ביטחון": "property_listing",
    "עיתוי":  "property_listing",
    "קהילה":  "property_listing",
    "דחיפות": "property_listing",
}

_ANGLE_CONTEXT = {
    "תשואה":  'זווית: תשואה — השקעה שמניבה תשואה יציבה בנדל"ן',
    "ביטחון": 'זווית: ביטחון — נכס בטוח כהגנה מפני אי-ודאות כלכלית',
    "עיתוי":  'זווית: עיתוי — הרגע הנכון להיכנס לשוק הנדל"ן',
    "קהילה":  'זווית: קהילה — סביבת מגורים איכותית ותחושת שייכות',
    "דחיפות": 'זווית: דחיפות — הזדמנות מוגבלת בזמן שאסור לפספס',
}


def handle_creative_command(text: str, chat_id: str) -> str:
    """מזהה תבנית מתוך הטקסט ומייצר תוכן שיווקי מותאם."""
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
                enriched_context = _ANGLE_CONTEXT[keyword]
            break

    result = generate(template, enriched_context)
    label = template.replace("_", " ").title()
    return f"*{label}*\n\n{result}"
