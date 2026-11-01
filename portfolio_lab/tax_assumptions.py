"""שיעור המס הראשוני — קבוע ידוע **במקום אחד** (PATH_COMPARISON_TAX_EVENT_MODEL §2; PATH_ENGINE_ARCHITECTURE_SPEC §2.1).

הערכה לפי הנחיית הבעלים (20/10/2026): 25% מהתשואה הריאלית. **ראשוני, לא אומת מקצועית, ולעולם לא `externally_verified`** — חישוב מס "אמת" נשאר
כפוף ל-`TAX_MODEL_LEGAL_VERIFICATION_SPEC.md`. אף מודול אחר אינו מכיל את השיעור כמספר (נבדק מבנית); הוא מקבל אותו מכאן דרך `frame["tax"]`.
טהור: ללא I/O, Airtable או LLM."""

from __future__ import annotations

import math

TAX_RATE_VERSION = "tax-prelim-1"
TAX_RATE_AS_OF = "2026-10-20"
TAX_RATE_SOURCE = "owner_directive_2026-10-20"
TAX_BASIS = "real_return_after_inflation"
TAX_STATUS = "preliminary_estimate"

_DEFAULT_RATE = 0.25            # THE one place the number lives


def tax_record(override_rate=None) -> dict:
    """הרשומה היחידה. דריסה (`owner_override`) רק במפורש ומסומנת; היא אינה הופכת את הערך למאומת."""
    rate = _DEFAULT_RATE
    version, override = TAX_RATE_VERSION, False
    if override_rate is not None:
        if isinstance(override_rate, bool) or not isinstance(override_rate, (int, float)) or not math.isfinite(override_rate) or not 0 <= override_rate <= 1:
            raise ValueError("tax_rate_override must be a fraction between 0 and 1")
        rate, version, override = float(override_rate), f"{TAX_RATE_VERSION}+owner_override", True
    return {"rate": rate, "basis": TAX_BASIS, "status": TAX_STATUS, "externally_verified": False, "version": version,
            "as_of": TAX_RATE_AS_OF, "source": TAX_RATE_SOURCE, "owner_override": override}


def tax_on(real_gain, record: dict) -> float | None:
    """`tax = rate × max(real_gain, 0)`; הפסד = מס אפס, ללא קיזוז (לא נקבע כאן). `None` (בסיס עלות חסר) -> `None`, לא 0."""
    if real_gain is None:
        return None
    return record["rate"] * max(float(real_gain), 0.0)
