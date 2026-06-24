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


@register_gate("trust", order=3)
def gate_trust(event: dict, decision: dict | None, ports: DecisionPorts) -> GateResult:
    """stub — Stage 1 יעטוף anti_hallucination.VerifyResult דרך ports.verifier."""
    return GateResult(True, "trust stub — stage 1", next_gate="readiness")


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

    for name in gate_order():
        _, fn = _GATE_REGISTRY[name]
        result = fn(event, decision, ports)
        if not result.passed:
            # BOSS never deletes signal — only down-ranks.
            event["Status"] = result.halt_status or "Logged"
            return {"halted_at": name, "result": result, "event": event}

    event["Status"] = "Active"
    return {"halted_at": None, "result": GateResult(True, "passed all gates"), "event": event}
