"""
core/financial_gate.py — Financial Commitment Escalation Gate

עיקרון: ESCALATE, לא BLOCK.
כשמזוהה התחייבות פיננסית ממקור לא מאושר —
1. הלקוח מקבל fallback
2. בעל הבית מקבל alert
3. אין DROP שקט
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ─── Feature Flag ──────────────────────────────────────────────────────────────
# false = shadow mode (בדוק בלי לעצור)
# true  = production escalation
FLAG_NAME = "FINANCIAL_COMMITMENT_GATE"

RULE_VERSION = "1.0"

# ─── Approved Sources ──────────────────────────────────────────────────────────
# הודעה שמקורה אחד מהבאים — עוברת ללא escalation
APPROVED_SOURCES = frozenset({
    "airtable_record",   # שורת Airtable שאושרה ידנית
    "pricing_script",    # מסמך תמחור מאושר (עתידי)
    "owner_approved",    # override ידני של בעל הבית
    "manual_override",   # override מאומת עם audit trail
})

# ─── Financial Triggers ────────────────────────────────────────────────────────
# כל pattern שמתאים → escalation (אם מקור לא מאושר)
_TRIGGER_PATTERNS: list[tuple[str, str]] = [
    # עברית
    (r"קיבלנו את התשלום|תשלום אושר|אושר התשלום",          "payment_confirmed"),
    (r"נחזיר לך|כסף יוחזר|החזר כספי|refund",               "refund_promise"),
    (r"נזכה את חשבונך|credit|זיכוי",                        "credit_issued"),
    (r"הנחה של \d|מחיר מיוחד|הנחה עבורך",                  "discount_offer"),
    (r"היתרה שלך|you owe nothing|אין חוב|חוב אפס",          "balance_confirmation"),
    (r"מחקנו את החוב|ביטול החוב|debt cancel",               "debt_cancellation"),
    (r"הסכם בוטל|ביטול ההזמנה אושר|cancellation approved",  "cancellation_financial"),
    (r"תשלום ב-\d+ תשלומים|ריבית 0%|payment plan",         "payment_terms"),
    (r"תשלום ראשון ב-|payment schedule",                    "payment_schedule"),
    (r"ללא עמלה|fee waived|עמלה אפס",                       "fee_waiver"),
    (r"המחיר עודכן|price changed|מחיר חדש",                 "price_change"),
    # כסף + מחויבות (סכום + פועל מחייב)
    (r"[₪$€£]\s*\d[\d,\.]+\s*(ישולם|מגיע לך|תקבל|יוחזר|נחזיר)", "amount_commitment"),
    (r"\d[\d,\.]+\s*₪\s*(ישולם|מגיע לך|תקבל|יוחזר|נחזיר)",           "amount_commitment_ils"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE | re.UNICODE), label) for p, label in _TRIGGER_PATTERNS]


@dataclass
class FinancialGateResult:
    escalated:   bool
    shadow_only: bool = False    # True = shadow mode, לא נחסם
    reason:      str  = ""
    triggers:    list[str] = None

    def __post_init__(self):
        if self.triggers is None:
            self.triggers = []


def check(envelope) -> FinancialGateResult:
    """
    בודק אם ההודעה מכילה התחייבות פיננסית ממקור לא מאושר.
    מחזיר FinancialGateResult.
    """
    from feature_flags import is_enabled

    shadow_mode = not is_enabled(FLAG_NAME)

    # בדוק triggers
    matched = _detect_triggers(envelope.body)
    if not matched:
        return FinancialGateResult(escalated=False)

    # בדוק source
    source_type = (envelope.meta or {}).get("source_type", "")
    if source_type in APPROVED_SOURCES:
        logger.info(
            "[FinGate] approved source override | source=%s | triggers=%s",
            source_type, matched
        )
        return FinancialGateResult(escalated=False)

    # מקור לא מאושר + יש triggers
    reason = f"financial_trigger:{','.join(matched)} | rule_v{RULE_VERSION}"

    if shadow_mode:
        logger.warning(
            "[FinGate] SHADOW | would_escalate | triggers=%s | source=%s | ref=%s",
            matched, envelope.source_module, envelope.source_ref
        )
        return FinancialGateResult(escalated=False, shadow_only=True, reason=reason, triggers=matched)

    logger.warning(
        "[FinGate] ESCALATE | triggers=%s | source=%s | ref=%s",
        matched, envelope.source_module, envelope.source_ref
    )
    return FinancialGateResult(escalated=True, reason=reason, triggers=matched)


def _detect_triggers(body: str) -> list[str]:
    matched = []
    for pattern, label in _COMPILED:
        if pattern.search(body):
            matched.append(label)
    return matched
