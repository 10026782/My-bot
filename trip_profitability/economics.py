"""חישובי כלכלה טהורים לנסיעה אחת: תרחיש, תוחלת, החלטת המתנה, רגישות והיפוך דירוג.

נוסחאות לפי SMART_TRIPS_P0_CALCULATION_CONTRACT.md §4–5. כל החישוב ב-Decimal, בלי עיגול ובלי IO.
הפונקציות לא יודעות מי ספק הרגליים: הן מקבלות רגליים (ק"מ, דקות, טעונה/ריקה) ומחזירות מספרים.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .models import HUNDRED, ONE, ZERO, Vehicle


@dataclass(frozen=True)
class LegCalc:
    key: str
    origin: str
    dest: str
    loaded: bool
    km: Decimal
    minutes: Decimal
    depart_at: datetime | None
    provenance: dict


@dataclass(frozen=True)
class ScenarioCalc:
    name: str                    # empty | return | leave
    legs: tuple[LegCalc, ...]
    wait: Decimal
    service: Decimal
    revenue: Decimal
    fees: Decimal
    fuel: Decimal
    wear: Decimal
    fixed: Decimal
    extra: Decimal
    contribution: Decimal        # כלכלית: כולל שחיקה
    cash_contribution: Decimal   # במזומן: אחרי דלק בלבד
    total_minutes: Decimal
    km: Decimal
    deadhead_km: Decimal

    @property
    def costs(self) -> Decimal:
        return self.fuel + self.wear + self.fixed + self.extra

    @property
    def valid(self) -> bool:
        return self.total_minutes > 0

    @property
    def per_hour(self) -> Decimal | None:
        return self.contribution / (self.total_minutes / 60) if self.valid else None


def compute_scenario(name: str, legs: list[LegCalc], wait: Decimal, service: Decimal, revenue: Decimal,
                     vehicle: Vehicle, extra_costs: Decimal) -> ScenarioCalc:
    """Contribution = Revenue − Fees − (דלק + שחיקה על כל הרגליים + עלות קבועה + עלויות נוספות)."""
    fuel = sum((vehicle.fuel(leg.km) for leg in legs), ZERO)
    wear = sum((vehicle.wear(leg.km) for leg in legs), ZERO)
    fees = revenue * vehicle.fee_pct / HUNDRED
    contribution = revenue - fees - fuel - wear - vehicle.fixed_cost - extra_costs
    return ScenarioCalc(
        name=name,
        legs=tuple(legs),
        wait=wait,
        service=service,
        revenue=revenue,
        fees=fees,
        fuel=fuel,
        wear=wear,
        fixed=vehicle.fixed_cost,
        extra=extra_costs,
        contribution=contribution,
        cash_contribution=contribution + wear,
        total_minutes=sum((leg.minutes for leg in legs), ZERO) + service + wait,
        km=sum((leg.km for leg in legs), ZERO),
        deadhead_km=sum((leg.km for leg in legs if not leg.loaded), ZERO),
    )


@dataclass(frozen=True)
class Expected:
    contribution: Decimal
    minutes: Decimal
    throughput: Decimal | None       # E[C] / (E[T]/60): מדד הדירוג
    per_hour_avg: Decimal | None     # Σ p·(C/h): מדד נפרד ומתויג
    deadhead_km: Decimal


def expected(weighted: list[tuple[Decimal, ScenarioCalc]]) -> Expected:
    contribution = sum((p * s.contribution for p, s in weighted), ZERO)
    minutes = sum((p * s.total_minutes for p, s in weighted), ZERO)
    return Expected(
        contribution=contribution,
        minutes=minutes,
        throughput=contribution / (minutes / 60) if minutes > 0 else None,
        per_hour_avg=sum((p * s.per_hour for p, s in weighted), ZERO) if all(s.valid for _, s in weighted) else None,
        deadhead_km=sum((p * s.deadhead_km for p, s in weighted), ZERO),
    )


def downside(weighted: list[tuple[Decimal, ScenarioCalc]]) -> ScenarioCalc:
    """התרחיש עם התרומה הנמוכה ביותר מבין אלה בעלי הסתברות חיובית."""
    return min((s for p, s in weighted if p > 0), key=lambda s: s.contribution)


@dataclass(frozen=True)
class Line:
    """C(p) ו-T(p) לינאריים ב-p (הסתברות להצלחה) בין תרחיש כישלון להצלחה."""
    c0: Decimal
    dc: Decimal
    t0: Decimal
    dt: Decimal

    @classmethod
    def of(cls, fail: ScenarioCalc, succ: ScenarioCalc) -> "Line":
        return cls(fail.contribution, succ.contribution - fail.contribution,
                   fail.total_minutes, succ.total_minutes - fail.total_minutes)

    def contribution(self, p: Decimal) -> Decimal:
        return self.c0 + p * self.dc

    def minutes(self, p: Decimal) -> Decimal:
        return self.t0 + p * self.dt

    def throughput(self, p: Decimal) -> Decimal | None:
        minutes = self.minutes(p)
        return self.contribution(p) / (minutes / 60) if minutes > 0 else None


def crossover(line: Line, target_throughput: Decimal) -> Decimal | None:
    """ה-p∈[0,1] שבו תפוקת ההצעה שווה ל-target (פתרון מדויק של c(p)·60/t(p)=target), או None."""
    denominator = 60 * line.dc - target_throughput * line.dt
    if denominator == 0:
        return None
    p = (target_throughput * line.t0 - 60 * line.c0) / denominator
    return p if ZERO <= p <= ONE else None


def value(s: ScenarioCalc, opportunity_cost: Decimal) -> Decimal:
    """V = Contribution − o · Time/60 (o = עלות הזדמנות לשעה, קלט משתמש)."""
    return s.contribution - opportunity_cost * s.total_minutes / 60


def wait_decision(fail: ScenarioCalc, succ: ScenarioCalc, leave: ScenarioCalc, p: Decimal,
                  opportunity_cost: Decimal, fee_pct: Decimal) -> dict:
    """p* (נקודת איזון) ותשלום חזרה מינימלי R*. אין "המלצה אטומה": הערכים והנימוק מוחזרים."""
    v_leave, v_fail, v_succ = (value(s, opportunity_cost) for s in (leave, fail, succ))
    result: dict = {"v_leave": v_leave, "v_fail": v_fail, "v_succ": v_succ, "p_break_even": None,
                    "min_return_fare": None, "verdict": "WAIT_NEVER", "wait_beats_leave_at_p": None}
    gain = v_succ - v_fail
    if gain > 0:
        p_star = (v_leave - v_fail) / gain
        result["p_break_even"] = p_star
        if p_star <= 0:
            result["verdict"] = "WAIT_ALWAYS"
        elif p_star < 1:
            result["verdict"] = "WAIT_IF_P_ABOVE"
        result["wait_beats_leave_at_p"] = p > p_star
    else:
        result["wait_beats_leave_at_p"] = False
    if p > 0 and fee_pct < HUNDRED:
        # V_succ0 = V_succ כשתשלום החזרה הוא 0: ההכנסה מההחזרה נכנסת נטו מעמלה
        succ_fare = succ.revenue - leave.revenue
        v_succ0 = v_succ - succ_fare * (ONE - fee_pct / HUNDRED)
        fare = ((v_leave - (ONE - p) * v_fail) / p - v_succ0) / (ONE - fee_pct / HUNDRED)
        result["min_return_fare"] = max(ZERO, fare)
    return result
