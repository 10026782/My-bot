"""חוזי נתונים למנוע מקומי; שיעורים כשברים, סכומים בשקלים."""

from dataclasses import dataclass, field
from datetime import date
import math
from typing import Callable


ENGINE_VERSION = "1.0.0"


def number(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def annual_values(value, name, minimum=None):
    values = tuple(value) if isinstance(value, (list, tuple)) else (value,)
    if not values:
        raise ValueError(f"{name} cannot be empty")
    for item in values:
        number(item, name, minimum)
    return values


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


@dataclass(frozen=True)
class Source:
    reference: str
    as_of: str
    description: str

    def __post_init__(self):
        for name in ("reference", "as_of", "description"):
            text(getattr(self, name), name)
        date.fromisoformat(self.as_of)


@dataclass(frozen=True)
class Asset:
    name: str = "global_accumulating"
    weight: float = 1.0
    annual_return: float | tuple[float, ...] = 0.08
    return_convention: str = "effective_annual"
    return_basis: str = "gross"
    annual_fee: float = 0.0015
    buy_fee: float = 0.0
    sell_fee: float = 0.0

    def __post_init__(self):
        text(self.name, "asset.name")
        number(self.weight, "weight", 0, 1)
        for name in ("annual_fee", "buy_fee", "sell_fee"):
            number(getattr(self, name), name, 0)
            if getattr(self, name) >= 1:
                raise ValueError(f"{name} must be < 1")
        returns = annual_values(self.annual_return, "annual_return")
        if self.return_convention not in {"effective_annual", "nominal_annual_monthly"}:
            raise ValueError("unknown return_convention")
        lower = -1 if self.return_convention == "effective_annual" else -12
        if any(r <= lower for r in returns):
            raise ValueError("monthly gross growth factor must be positive")
        if self.return_basis not in {"gross", "net_recurring"}:
            raise ValueError("unknown return_basis")
        if self.return_basis == "net_recurring" and self.annual_fee:
            raise ValueError("net_recurring returns require annual_fee=0 (no double counting)")
        object.__setattr__(self, "annual_return", returns)


@dataclass(frozen=True)
class Scenario:
    years: int = 60
    initial: float = 0.0
    monthly_contribution: float | tuple[float, ...] = 8000.0
    inflation: float | tuple[float, ...] = 0.02
    index_contributions: bool = False
    deposit_timing: str = "end"
    start_date: str = "2026-01-01"
    assets: tuple[Asset, ...] = field(default_factory=lambda: (Asset(),))
    result_type: str = "assumption_based_projection"
    sources: tuple[Source, ...] = ()

    def __post_init__(self):
        if type(self.years) is not int or not 10 <= self.years <= 100:
            raise ValueError("years must be an integer from 10 to 100")
        number(self.initial, "initial", 0)
        if type(self.index_contributions) is not bool:
            raise ValueError("index_contributions must be boolean")
        if self.deposit_timing not in {"begin", "end"}:
            raise ValueError("deposit_timing must be begin or end")
        start = date.fromisoformat(self.start_date)
        if start.day != 1 or start.year + self.years > 9999:
            raise ValueError("start_date must be the first day of a supported calendar month")
        if self.result_type not in {"mathematical", "historical", "assumption_based_projection"}:
            raise ValueError("unknown result_type")
        sources = tuple(self.sources)
        if any(not isinstance(s, Source) for s in sources):
            raise ValueError("sources must contain Source objects")
        if self.result_type == "historical" and not sources:
            raise ValueError("historical inputs require dated sources")
        assets = tuple(self.assets)
        if not assets or any(not isinstance(a, Asset) for a in assets):
            raise ValueError("assets must contain Asset objects")
        if len({a.name for a in assets}) != len(assets):
            raise ValueError("asset names must be unique")
        if not math.isclose(sum(a.weight for a in assets), 1, rel_tol=0, abs_tol=1e-12):
            raise ValueError("asset weights must sum to 1")
        contributions = annual_values(self.monthly_contribution, "monthly_contribution", 0)
        inflation = annual_values(self.inflation, "inflation")
        if any(i <= -1 for i in inflation):
            raise ValueError("inflation must be > -1")
        for name, values in [("monthly_contribution", contributions), ("inflation", inflation)]:
            if len(values) not in {1, self.years}:
                raise ValueError(f"{name} needs one value or exactly years values")
        for asset in assets:
            if len(asset.annual_return) not in {1, self.years}:
                raise ValueError("annual_return needs one value or exactly years values")
        object.__setattr__(self, "assets", assets)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "monthly_contribution", contributions)
        object.__setattr__(self, "inflation", inflation)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("scenario must be an object")
        values = dict(data)
        if "assets" in values:
            values["assets"] = tuple(Asset(**a) for a in values["assets"])
        if "sources" in values:
            values["sources"] = tuple(Source(**s) for s in values["sources"])
        return cls(**values)


@dataclass(frozen=True)
class PurchaseLot:
    asset: str
    purchased_on: str
    units: float
    unit_price: float
    cash_paid: float
    buy_fee: float
    cpi: float


@dataclass(frozen=True)
class SaleContext:
    sold_on: str
    lots: tuple[PurchaseLot, ...]
    closing_prices: tuple[tuple[str, float], ...]
    gross_proceeds: float
    sale_cost: float
    proceeds_before_tax: float
    cpi: float


@dataclass(frozen=True)
class TaxAssessment:
    amount: float
    rule_id: str
    rule_version: str
    parameters: dict
    source: Source
    externally_verified: bool = False


TaxModel = Callable[[SaleContext], TaxAssessment]
