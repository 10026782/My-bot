"""
domain_prompts.py — MADS CORE Domain Layer
פרומפטים והגדרות ייעודיות לכל דומיין.
כל דומיין עצמאי — ניתן להרחיב בלי לגעת בשאר.
"""

DOMAIN_CONFIG: dict[str, dict] = {

    # ─── נדל"ן ────────────────────────────────────────────────────────────────
    "real_estate": {
        "name": 'נדל"ן',
        "tone": "professional",
        "priority": "high",

        # שאלות ה-State Machine לוואטסאפ (בסדר הזה)
        "flow": [
            ("intro",    "שלום! אני מכאן לעזור 🏠\nמה אתה מחפש — נכס למגורים או להשקעה?"),
            ("budget",   "מה התקציב שלך? (ניתן לציין טווח)"),
            ("area",     "באיזה אזור אתה מתעניין?"),
            ("timeline", "מה לוח הזמנים שלך? (מיידי / חודשים / גמיש)"),
        ],

        # פרומפט לניתוח הליד אחרי איסוף המידע
        "qualification_prompt": """
אתה מנתח לידים מקצועי בתחום הנדל"ן.
נתח את הליד ותן ציון מ-0 עד 100.

קריטריוני ניקוד:
- תקציב ורצינות פיננסית (30 נקודות)
- בהירות הצורך: מגורים / השקעה (20 נקודות)
- אזור וספציפיות הדרישה (20 נקודות)
- דחיפות ולוח זמנים (20 נקודות)
- פוטנציאל עסקה חוזרת (10 נקודות)

החזר תמיד בפורמט:
ציון: [0-100]
סיווג: [HOT/WARM/COLD]
סיכום: [2-3 שורות]
סיכון עיקרי: [משפט אחד]
צעד הבא: [פעולה ספציפית אחת]
""",

        # שדות שנאסף מהשיחה — לשימוש עתידי ב-CRM
        "required_fields": ["intro", "budget", "area", "timeline"],

        # תגיות לסינון/דיווח
        "tags": ["property", "investment", "residential"],
    },

    # ─── גיוס עובדים ──────────────────────────────────────────────────────────
    "recruitment": {
        "name": "גיוס עובדים",
        "tone": "friendly",
        "priority": "high",

        "flow": [
            ("intro",       "שלום! 👋 אני כאן לעזור במציאת עבודה.\nאיזה תפקיד אתה מחפש?"),
            ("experience",  "מה הניסיון הרלוונטי שלך בתחום?"),
            ("availability", "מתי אתה יכול להתחיל? (מיידי / הודעה מוקדמת / גמיש)"),
            ("location",    "איפה אתה מעוניין לעבוד? (עיר / אזור / עבודה מרחוק)"),
        ],

        "qualification_prompt": """
אתה מנתח מועמדים לגיוס עובדים.
נתח את המועמד ותן ציון מ-0 עד 100.

קריטריוני ניקוד:
- התאמה לתפקיד המבוקש (30 נקודות)
- ניסיון ורקע רלוונטי (25 נקודות)
- זמינות ולוח זמנים (20 נקודות)
- גמישות ומוטיבציה (15 נקודות)
- פוטנציאל התאמה ארגונית (10 נקודות)

החזר תמיד בפורמט:
ציון: [0-100]
סיווג: [HOT/WARM/COLD]
סיכום: [2-3 שורות]
סיכון עיקרי: [משפט אחד]
צעד הבא: [פעולה ספציפית אחת]
""",

        "required_fields": ["intro", "experience", "availability", "location"],

        "tags": ["candidate", "job", "hiring"],
    },
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_domain_config(domain: str) -> dict:
    """מחזיר את הקונפיג לדומיין, עם fallback ל-real_estate."""
    return DOMAIN_CONFIG.get(domain, DOMAIN_CONFIG["real_estate"])


def get_qualification_prompt(domain: str) -> str:
    return get_domain_config(domain)["qualification_prompt"].strip()


def get_flow(domain: str) -> list[tuple[str, str]]:
    return get_domain_config(domain)["flow"]


def list_domains() -> list[str]:
    return list(DOMAIN_CONFIG.keys())
