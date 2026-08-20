# domain_router.py — CORE_02_ROUTER
# זיהוי הדומיין העסקי של הבקשה.
#
# שלוש שכבות לפי עדיפות:
# 1. מיפוי מספר טלפון (ודאי 100%) ← מה שהיה ב-config.get_domain()
# 2. identity.domain_id (הוגדר ב-registry)
# 3. זיהוי מטקסט — rule-based

from __future__ import annotations
import re
import logging
from .route_decision import RouterDomain

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Layer 3 — Text-based Rules
# ══════════════════════════════════════════════════

_DOMAIN_RULES: list[tuple[str, str, float]] = [

    # ── Real Estate ──────────────────────────────
    (r"(נדל.ן|דירה|דירות|קרקע|נכס|נכסים|שכירות|שוכר|משכנתא|פינוי|בינוי|עסקת נדל)", RouterDomain.REAL_ESTATE, 0.95),
    (r"(apartment|property|real.estate|rental|tenant|mortgage)", RouterDomain.REAL_ESTATE, 0.95),

    # ── Import ───────────────────────────────────
    (r"(יבוא|ייבוא|סין|ספק|ספקים|מכולה|שילוח|מטען|קנייה בחו.ל|רהיט)", RouterDomain.IMPORT, 0.95),
    (r"(import|supplier|china|shipping|container|cargo|procurement)", RouterDomain.IMPORT, 0.95),

    # ── Finance ──────────────────────────────────
    # BUG-Phase1-Domain: "מס" (tax) MUST be word-bounded — unbounded, it
    # matched as a substring inside "מספר" (number/phone), "מסמך" (document),
    # "מסלול" (path/track), etc., causing "...בעל מספר צוותים..." to
    # misroute to FINANCE before the RECRUITMENT rule below ever got a
    # chance to match "recruitment"/"גיוס" in the same message (see the
    # Lead System E2E Audit's golden failure case). \b is Unicode-aware in
    # Python's re module (treats Hebrew letters as \w), so it correctly
    # excludes "מס" as a substring of a longer word while still matching it
    # standalone (e.g. "לשלם מס").
    (r"(כסף|תזרים|מזומן|הכנסה|הוצאה|רווח|הפסד|חשבון|תשלום|חשבונית|מע.מ|\bמס\b)", RouterDomain.FINANCE, 0.95),
    (r"(finance|cash.flow|revenue|expense|profit|invoice|payment|tax|vat)", RouterDomain.FINANCE, 0.95),

    # ── Recruitment ────────────────────────────────────────────────────────
    (r"(גיוס|גיוסים|מגייס|מגייסת|recruiting|recruitment)", RouterDomain.RECRUITMENT, 0.95),

    # ── Media ────────────────────────────────────
    (r"(שיווק|מדיה|קמפיין|פרסום|תוכן|סושיאל|אינסטגרם|פייסבוק|יוטיוב|טיקטוק)", RouterDomain.MEDIA, 0.90),
    (r"(marketing|media|campaign|content|social|instagram|facebook|youtube|tiktok)", RouterDomain.MEDIA, 0.90),

    # ── SaaS ─────────────────────────────────────
    (r"(saas|מנוי|subscription|לקוח saas|פיצ.ר|feature|product|api|integrat)", RouterDomain.SAAS, 0.90),

    # ── CRM — כללי (אחרי הספציפיים) ─────────────
    (r"(ליד|lead|לקוח|לקוחות|קשר עסקי|עסקה|pipeline|crm)", RouterDomain.CRM, 0.85),
]

_COMPILED_DOMAIN: list[tuple[re.Pattern, str, float]] = [
    (re.compile(p, re.IGNORECASE | re.UNICODE), d, c)
    for p, d, c in _DOMAIN_RULES
]


def detect_domain(
    text: str,
    domain_from_channel: str = "",
    domain_from_identity: str = "",
    confidence_threshold: float = 0.80,
) -> tuple[str, float]:
    """
    מחזיר (domain, confidence).

    עדיפות:
    1. domain_from_channel  — מיפוי מספר טלפון (ודאי)
    2. domain_from_identity — הוגדר ב-registry
    3. זיהוי מטקסט         — rule-based
    4. GENERAL              — fallback
    """
    # Layer 1: מיפוי ערוץ — ודאי 100%
    if domain_from_channel and domain_from_channel != RouterDomain.GENERAL:
        logger.debug(f"[Domain] From channel mapping: {domain_from_channel}")
        return domain_from_channel, 1.0

    # Layer 2: מ-identity registry
    if domain_from_identity and domain_from_identity != RouterDomain.GENERAL:
        logger.debug(f"[Domain] From identity: {domain_from_identity}")
        return domain_from_identity, 0.90

    # Layer 3: זיהוי מטקסט
    for pattern, domain, confidence in _COMPILED_DOMAIN:
        if pattern.search(text):
            if confidence >= confidence_threshold:
                logger.debug(f"[Domain] Text match: {domain} ({confidence:.2f})")
                return domain, confidence

    # Fallback
    logger.debug(f"[Domain] No match — GENERAL fallback")
    return RouterDomain.GENERAL, 0.5
