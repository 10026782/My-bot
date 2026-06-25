# decision_pipeline.py — Decision Hub (Stage 0) Gate Pipeline
#
# BOSS never deletes signal. BOSS only down-ranks it.
# "לחץ בלבד / ללא שינוי" נשמר כ-Decision Event עם Status=Logged — לא נוגע
# ב-Canonical State, לא שולח התראה, אבל נשמר כי מחר הוא הופך לדפוס.
#
# חוק ברזל: שום פונקציה כאן לא מייבאת את שכבת הכתיבה ל-Airtable ישירות.
# הכל דרך DecisionPorts (decision_ports.py) — Decision Hub נולד תואם F08/F13.

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from decision_ports import DecisionPorts, build_default_ports
from airtable_schema import (
    DecisionSourceReliability as SRC,
    DecisionEventChannel as CH,
    DecisionTrustLevel as TL,
    DecisionEventTag as TAG,
    DecisionClaimTopicSource as TOPIC_SRC,
    DecisionExposureType as EXPOSURE,
    DecisionFields as DF,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# 3.1 — חוזה אחיד
# ══════════════════════════════════════════════════

@dataclass
class GateResult:
    passed: bool                       # עבר הלאה / נעצר
    reason: str                        # תמיד מוסבר, בעברית
    halt_status: str | None = None     # אם נעצר: "Logged"/"Review"/"Draft"/"NotReady"
    user_flag: str | None = None       # מה להציג למשתמש (None = שקט)
    next_gate: str | None = None       # שם השער הבא


# ══════════════════════════════════════════════════
# 3.2 — רישום שערים דקלרטיבי (מראה את _REGISTRY ב-tool_registry.py)
# ══════════════════════════════════════════════════

_GATE_REGISTRY: dict[str, tuple[int, Callable]] = {}


def register_gate(name: str, order: int):
    def wrap(fn):
        _GATE_REGISTRY[name] = (order, fn)
        return fn
    return wrap


def gate_order() -> list[str]:
    return [n for n, _ in sorted(_GATE_REGISTRY.items(), key=lambda kv: kv[1][0])]


# ══════════════════════════════════════════════════
# 3.6 — Delta classifier markers (Stage 0 = keyword-based; Stage 2 = AI)
# ══════════════════════════════════════════════════

PRESSURE_MARKERS = [
    "עכשיו או לעולם לא", "אחרון", "אולטימטום",
    "לא מחכה", "מחר בבוקר", "הגבלת זמן",
]
FACT_MARKERS = [
    "חתם", "נשלח", "אושר", "נדחה", "סעיף",
    "תאריך חדש", "טיוטה", "מסמך מצורף",
]


# ══════════════════════════════════════════════════
# 3.3 — השערים (חתימה אחידה: event, decision, ports)
# ══════════════════════════════════════════════════

@register_gate("delta", order=1)
def gate_delta(event: dict, decision: dict | None, ports: DecisionPorts) -> GateResult:
    """מסווג: לחץ/ללא_שינוי → passed=False, halt_status=Logged. מידע חדש → passed=True."""
    text = event.get("raw_content", "") or ""
    has_attachment = bool(event.get("attachment"))

    if has_attachment:
        event["Delta Type"] = "מסמך"
        return GateResult(True, "יש attachment מצורף — מסמך", next_gate="entity")

    has_fact = any(marker in text for marker in FACT_MARKERS)
    has_pressure = any(marker in text for marker in PRESSURE_MARKERS)

    if has_fact and not has_pressure:
        event["Delta Type"] = "עובדה"
        return GateResult(True, "נמצאה עובדה חדשה", next_gate="entity")

    if has_pressure and not has_fact:
        event["Delta Type"] = "לחץ"
        return GateResult(
            False, "לחץ טקטי בלבד — אין עובדה חדשה",
            halt_status="Logged",
        )

    event["Delta Type"] = "ללא_שינוי"
    return GateResult(
        False, "אותו מידע, ניסוח אחר",
        halt_status="Logged",
    )


@register_gate("entity", order=2)
def gate_entity(event: dict, decision: dict | None, ports: DecisionPorts) -> GateResult:
    """כפילות → passed=False, halt_status=Review. ודאי → passed=True. משתמש ב-ContactPort."""
    name = event.get("stakeholder_name")
    if not name:
        return GateResult(True, "אין stakeholder לזיהוי בעדכון הזה", next_gate="trust")

    result = ports.contacts.find_or_create(name)

    if result["status"] == "ambiguous":
        names = ", ".join(m.name for m in result.get("matches", []))
        return GateResult(
            False,
            f"כמה אנשי קשר תואמים ל-'{name}'",
            halt_status="Review",
            user_flag=f"שני אנשי קשר תואמים — מי? ({names})",
        )

    return GateResult(True, f"stakeholder '{name}' זוהה (status={result['status']})", next_gate="trust")


# ══════════════════════════════════════════════════
# 3.4 — Trust Model (Stage 1, Rev 2) — Authority × Medium × Verify
# ══════════════════════════════════════════════════

AUTHORITY_SCORE: dict[str, int] = {
    SRC.CONTRACT:   90,
    SRC.LAWYER:     88,
    SRC.ACCOUNTANT: 85,
    SRC.DOCUMENT:   80,
    SRC.PARTNER:    65,
    SRC.CLIENT:     60,
    SRC.MANUAL:     55,
    SRC.EMPLOYEE:   50,
    SRC.RUMOR:      15,
    SRC.UNKNOWN:    25,
}

MEDIUM_SCORE: dict[str, int] = {
    CH.DOCUMENT:  90,
    CH.EMAIL:     70,
    "טקסט":       65,   # spec value — no matching DecisionEventChannel option
    CH.WHATSAPP:  60,
    CH.TELEGRAM:  60,
    CH.VOICE:     45,
    "forward":    40,   # spec value — no matching DecisionEventChannel option
    CH.MANUAL:    55,
}

TOPIC_FROM_EVENT_TYPE = {
    "טיוטה":  "draft",
    "עמדה":   "position",
    "החלטה":  "decision",
    "לחץ":    "pressure",
    "מסמך":   "document",
    "פגישה":  "meeting",
}

TOPIC_KEYWORDS = {
    "מחיר":     "price",   "תמחור":     "price",
    "תאריך":    "date",    "לוח זמנים": "date",
    "תנאים":    "terms",   "סעיף":      "terms",
    "ערבות":    "guarantee", "אחריות":  "liability",
    "אספקה":    "delivery",
}


def compute_trust(authority: str, medium: str, verify_status: str) -> tuple[str, int]:
    """Authority מוביל (60%), Medium מגביל (40%). Medium ceiling: מקור חזק לא מציל ערוץ חלש."""
    a = AUTHORITY_SCORE.get(authority, 55)
    m = MEDIUM_SCORE.get(medium, 55)

    if verify_status in ("hallucination", "failed") and a >= 65:
        return TL.T0, 10   # אנומליה חמורה — מקור אמין שנכשל

    combined = int(a * 0.6 + m * 0.4)
    combined = min(combined, m + 15)   # medium ceiling

    if verify_status == "warn":
        combined = int(combined * 0.85)

    return score_to_level(combined), combined


def score_to_level(score: int) -> str:
    if score >= 80: return TL.T3
    if score >= 55: return TL.T2
    if score >= 30: return TL.T1
    return TL.T0


def extract_claim_topic(event: dict) -> tuple[str | None, str | None, int]:
    """גוזר Claim Topic אוטומטי לפי עדיפות: filename → Event Type → Delta Type → keywords → None.
    מחזיר (topic, source, confidence) — source/confidence ל-Claim Topic Source/Confidence."""
    attachment = event.get("Attachment") if event.get("Attachment") else event.get("attachment")
    filename = attachment.get("filename", "") if isinstance(attachment, dict) else ""
    if filename:
        for kw, topic in TOPIC_KEYWORDS.items():
            if kw in filename:
                return topic, TOPIC_SRC.FILENAME, 90

    event_type = event.get("Event Type", "")
    if event_type in TOPIC_FROM_EVENT_TYPE:
        return TOPIC_FROM_EVENT_TYPE[event_type], TOPIC_SRC.EVENT_TYPE, 80

    delta = event.get("Delta Type", "")
    if delta in ("מסמך", "טיוטה"):
        return "document", TOPIC_SRC.AUTO, 70

    raw = event.get("Raw Content") or event.get("raw_content", "") or ""
    for kw, topic in TOPIC_KEYWORDS.items():
        if kw in raw:
            return topic, TOPIC_SRC.KEYWORD, 60

    return None, None, 0


def _trust_rank(level: str) -> int:
    return {TL.T0: 0, TL.T1: 1, TL.T2: 2, TL.T3: 3}.get(level, 0)


def maybe_supersede(new_event: dict, decision: dict | None, ports: DecisionPorts) -> None:
    """Supersede רק אם: אותו Claim Topic + Trust החדש גבוה יותר. אסור לדרוס Events על נושאים שונים."""
    decision_id = new_event.get("_decision_id")
    if not decision or not decision_id or not new_event.get("Claim Topic"):
        return

    prior_events = ports.storage.get(
        "Decision Events",
        f"AND({{Decision}}='{decision_id}', "
        f"{{Claim Topic}}='{new_event['Claim Topic']}', "
        f"{{Status}}='Active')",
    )
    for prior in prior_events:
        prior_fields = prior.get("fields", prior)
        prior_level = prior_fields.get("Trust Level", TL.T0)
        if _trust_rank(new_event["Trust Level"]) > _trust_rank(prior_level):
            ports.storage.update("Decision Events", prior["id"], {"Status": "Superseded"}, source="gate_trust")
            new_event["Supersedes"] = [prior["id"]]


def _has_keyword_conflict(raw: str, decision: dict | None, ports: DecisionPorts) -> bool:
    """Spec Rev 2 §5 שלב ו' מפנה לפונקציה זו אך לא הגדיר את גוף הלוגיקה.
    מחזיר False (no-op) — 'potential_conflict' tag לא ייוצר בפועל עד שלוגיקת
    ה-keyword-conflict תוגדר במפרט (Stage 1.x / Stage 2)."""
    return False


def _compute_tags(event: dict, level: str, conf: int, verify_status: str) -> list[str]:
    tags = []
    if level == TL.T0:                            tags.append(TAG.LOW_CONFIDENCE)
    if level == TL.T1:                            tags.append(TAG.PARTIAL_TRANSCRIPT)
    if conf < 40:                                 tags.append(TAG.VAGUE)
    if "לחץ" in event.get("Delta Type", ""):      tags.append(TAG.PRESSURE_ONLY)
    if verify_status == "warn":                   tags.append(TAG.MISSING_CONTEXT)
    if event.get("Channel") == CH.VOICE:          tags.append(TAG.PARTIAL_TRANSCRIPT)
    return list(dict.fromkeys(tags))   # dedupe, preserve order


@register_gate("trust", order=3)
def gate_trust(event: dict, decision: dict | None, ports: DecisionPorts) -> GateResult:
    authority = event.get("Source Reliability") or event.get("source_reliability") or SRC.MANUAL
    medium    = event.get("Channel") or event.get("channel") or CH.MANUAL
    raw       = event.get("Raw Content") or event.get("raw_content", "") or ""

    verify = ports.verifier.verify(raw, authority)
    verify_status = verify.get("status", "ok")

    level, conf = compute_trust(authority, medium, verify_status)

    claim_topic, topic_source, topic_conf = extract_claim_topic(event)
    event["Claim Topic"] = claim_topic or ""
    if topic_source:
        event["Claim Topic Source"] = topic_source
        event["Claim Topic Confidence"] = topic_conf

    tags = _compute_tags(event, level, conf, verify_status)

    if _has_keyword_conflict(raw, decision, ports):
        tags.append(TAG.CONFLICT)
        # Stage 2 יחליט אם להוריד Trust

    if (TAG.PRESSURE_ONLY in tags and decision and
            decision.get(DF.EXPOSURE_TYPE) in (EXPOSURE.FINANCIAL, EXPOSURE.LEGAL)):
        level, conf = TL.T0, min(conf, 25)
        tags.append(TAG.PRESSURE_HIGH_RISK)

    event["Trust Level"] = level
    event["Confidence"]  = conf
    event["Tags"]        = list(dict.fromkeys(tags))

    maybe_supersede(event, decision, ports)

    if level == TL.T0:
        flag = "⚠️ מידע עם אמינות נמוכה — דורש בדיקה אנושית."
        if verify_status in ("hallucination", "failed") and AUTHORITY_SCORE.get(authority, 0) >= 65:
            flag = "⚠️ מקור אמין שנכשל באימות — חריג חמור. נדרשת בדיקה."
        return GateResult(False, f"T0: {verify_status}, conf={conf}",
                           halt_status="Review", user_flag=flag)

    if level == TL.T1:
        return GateResult(False, f"T1: conf={conf}",
                           halt_status="Draft", user_flag=None)

    topic_flag = None
    if not claim_topic:
        topic_flag = "📝 לא זיהיתי נושא — באיזה נושא מדובר? (אופציונלי)"

    return GateResult(True, f"{level}: conf={conf}",
                       halt_status=None, user_flag=topic_flag, next_gate="readiness")


@register_gate("readiness", order=4)
def gate_readiness(event: dict, decision: dict | None, ports: DecisionPorts) -> GateResult:
    """stub — Stage 3."""
    return GateResult(True, "readiness stub — stage 3", next_gate="risk")


@register_gate("risk", order=5)
def gate_risk(event: dict, decision: dict | None, ports: DecisionPorts) -> GateResult:
    """stub — Stage 5 יקרא ל-Approval Gate הקיים דרך ports.approver."""
    return GateResult(True, "risk stub — stage 5", next_gate=None)


# ══════════════════════════════════════════════════
# 3.5 — Runner (registry + ports injection)
# ══════════════════════════════════════════════════

def run_pipeline(
    event: dict,
    decision: dict | None,
    ports: DecisionPorts | None = None,
) -> dict:
    """מריץ event דרך השערים לפי order. עוצר בשער ראשון שלא passed.
    ports מוזרק — אין importים ישירים לליבה."""
    ports = ports or build_default_ports()

    collected_flag = None
    for name in gate_order():
        _, fn = _GATE_REGISTRY[name]
        result = fn(event, decision, ports)
        if result.user_flag:
            collected_flag = result.user_flag
        if not result.passed:
            # BOSS never deletes signal — only down-ranks.
            event["Status"] = result.halt_status or "Logged"
            return {"halted_at": name, "result": result, "event": event}

    event["Status"] = "Active"
    return {"halted_at": None, "result": GateResult(True, "passed all gates", user_flag=collected_flag), "event": event}
