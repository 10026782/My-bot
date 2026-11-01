"""FCC monthly cashflow — pure, read-only read model. No I/O, no writes, no estimates beyond what is labelled.

מה זה: לכל חודש — הכנסות לפי מקור (ברוטו / עלויות ישירות / נטו), הוצאות לפי קטגוריה, היתרה (הכנסות פחות הוצאות),
שינוי חודש-לחודש וחריגות. הקלט מגיע מהשירות (owner-scoped); המודול עצמו לא קורא ולא כותב דבר.

Iron rules (same family as ``loans`` / ``net_worth``):
* **Unknown != 0.** חודש בלי הכנסות רשומות או בלי הוצאות רשומות לא מקבל יתרה (``balance = None``, ``missing`` מפרט מה חסר);
  חודש לא-ידוע לעולם לא נכנס לממוצע, לשינוי או לחריגה.
* **הוצאה = מה שנרשם בפועל.** התחייבות קבועה (``Recurring Obligations``) היא התחייבות ולא חיוב: היא **לא** נוספת להוצאות כאן, כי
  החיוב בפועל (ידני או מייבוא בנק/אשראי) כבר נספר כהוצאה — הוספה הייתה סופרת אותו פעמיים. התחייבויות משמשות להמלצות בלבד.
* **הלוואות הן הוצאה** (קטגוריה ``loans``): חיוב שנרשם בפועל באותו חודש גובר; רק כשאין חיוב רשום וזה החודש הנוכחי נכנס ההחזר
  החודשי המתוכנן מטבלת ``Loans`` — מסומן ``basis="scheduled"`` (הערכה), ולעולם לא בנוסף לחיוב רשום.
* מקור הכנסה שאינו קבוע נקרא ``GENERAL_SOURCE`` ("כללי") — לא "אחר".
* סכום הוצאה חיובי = הוצאה, שלילי = זיכוי/החזר (מקטין את הקטגוריה).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from statistics import median

# ── Expense categories (owner list 31/10/2026 + the common ones the owner asked to be added) ─────────────────────
# (key, Hebrew label). Keys are stored in Airtable (``Financial Progress Events.Expense Category``, singleSelect: the option NAME is the key).
EXPENSE_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("living", "מחייה"),
    ("communication", "תקשורת"),
    ("loans", "הלוואות"),
    ("business", "עסק"),
    ("home", "הוצאות בית"),
    ("institutions", "מוסדות"),
    ("transport", "תחבורה"),
    ("donations", "תרומות"),
    ("clothing", "ביגוד והנעלה"),
    ("insurance", "ביטוחים"),
    # added (common household categories the owner did not list)
    ("health", "בריאות"),
    ("leisure", "פנאי ובילויים"),
    ("taxes", "מיסים ואגרות"),
    ("gifts", "מתנות ואירועים"),
    ("general", "כללי"),
)
CATEGORY_LABEL: dict[str, str] = dict(EXPENSE_CATEGORIES)
LOANS = "loans"
UNCATEGORIZED = "uncategorized"          # an expense whose category is missing/unknown: shown apart, never guessed into a category
UNCATEGORIZED_LABEL = "לא מסווג"
GENERAL_SOURCE = "כללי"                  # a non-fixed income source with no name of its own

FIXED, VARIABLE, GENERAL = "fixed", "variable", "general"
SOURCE_KINDS = (FIXED, VARIABLE, GENERAL)

# Insight thresholds (constants, exposed in the payload so the screen can state them)
MIN_CHANGE = 100.0            # a month-to-month category change smaller than this is not listed
SPIKE_PCT = 0.5               # a category above its baseline by more than 50% ...
SPIKE_MIN_EXCESS = 300.0      # ... AND by at least this many shekels is a spike
SPIKE_MIN_BASELINE_MONTHS = 2  # a baseline needs at least this many known preceding months (max BASELINE_MONTHS used)
BASELINE_MONTHS = 3
LARGE_ITEM_FLOOR = 1000.0     # a single expense item is "large" from here ...
LARGE_ITEM_MULT = 3.0         # ... and, when its category has >= 3 items, at least this many times the category median
LARGE_ITEM_LIMIT = 5

THRESHOLDS = {"min_change": MIN_CHANGE, "spike_pct": SPIKE_PCT, "spike_min_excess": SPIKE_MIN_EXCESS,
              "baseline_months": BASELINE_MONTHS, "large_item_floor": LARGE_ITEM_FLOOR, "large_item_mult": LARGE_ITEM_MULT}


@dataclass(frozen=True)
class Txn:
    """One dated amount. ``category`` is only meaningful for expenses."""
    amount: float
    occurred: date
    category: str | None = None
    ref: str | None = None
    label: str = ""


@dataclass(frozen=True)
class IncomeSource:
    """An income source with its entries. ``fixed_monthly`` (kind=fixed) is a standing monthly amount that applies to every month from
    ``fixed_since`` on (inclusive month); earlier months stay unknown. A variable/general source only counts what was recorded."""
    name: str
    kind: str = VARIABLE
    gross: tuple[Txn, ...] = ()
    direct_costs: tuple[Txn, ...] = ()
    fixed_monthly: float | None = None
    fixed_since: date | None = None


# ── months ───────────────────────────────────────────────────────────────────────────────────────────────────────
def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_windows(today: date, months: int) -> list[tuple[str, date, date]]:
    """The last ``months`` calendar months ending with the month of ``today`` (oldest first), as (key, first day, last day)."""
    months = max(1, min(int(months), 36))
    out: list[tuple[str, date, date]] = []
    y, m = today.year, today.month
    for _ in range(months):
        out.append((f"{y:04d}-{m:02d}", date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _in(d: date, start: date, end: date) -> bool:
    return start <= d <= end


def _r(v: float) -> float:
    return round(v, 2)


def category_key(value) -> str:
    """Known category key -> itself; a Hebrew label -> its key; anything else (None, unknown) -> UNCATEGORIZED. Never guessed."""
    if isinstance(value, dict):
        value = value.get("name")
    if not isinstance(value, str):
        return UNCATEGORIZED
    v = value.strip()
    if v in CATEGORY_LABEL:
        return v
    for key, label in EXPENSE_CATEGORIES:
        if v == label:
            return key
    return UNCATEGORIZED


def label_of(key: str) -> str:
    return CATEGORY_LABEL.get(key, UNCATEGORIZED_LABEL)


# ── one month ────────────────────────────────────────────────────────────────────────────────────────────────────
def _source_month(src: IncomeSource, start: date, end: date) -> dict | None:
    gross_entries = [t for t in src.gross if _in(t.occurred, start, end)]
    cost_entries = [t for t in src.direct_costs if _in(t.occurred, start, end)]
    standing = (src.kind == FIXED and src.fixed_monthly is not None
                and (src.fixed_since is None or end >= src.fixed_since.replace(day=1)))
    if not gross_entries and not cost_entries and not standing:
        return None                                                  # nothing known for this source this month (NOT zero)
    gross = sum(t.amount for t in gross_entries)
    basis = "recorded"
    if standing and not gross_entries:
        gross, basis = float(src.fixed_monthly), "standing"
    elif standing:
        basis = "recorded"                                           # an explicit entry replaces the standing amount, never adds to it
    costs = sum(t.amount for t in cost_entries)
    return {"name": src.name, "kind": src.kind, "gross": _r(gross), "direct_costs": _r(costs), "net": _r(gross - costs), "basis": basis}


def _expense_month(txns: list[Txn], start: date, end: date, today: date, loans_scheduled: float | None) -> dict:
    by_cat: dict[str, float] = {}
    count = 0
    for t in txns:
        if not _in(t.occurred, start, end):
            continue
        count += 1
        by_cat[category_key(t.category)] = by_cat.get(category_key(t.category), 0.0) + t.amount
    loans_basis = "recorded" if by_cat.get(LOANS) else None
    if not loans_basis and loans_scheduled is not None and start <= today <= end:
        by_cat[LOANS] = by_cat.get(LOANS, 0.0) + loans_scheduled   # current month only; never on top of a recorded loan charge
        loans_basis = "scheduled"
    known = bool(by_cat)
    order = [k for k, _ in EXPENSE_CATEGORIES] + [UNCATEGORIZED]
    cats = [{"key": k, "label": label_of(k), "amount": _r(by_cat[k]),
             **({"basis": loans_basis} if k == LOANS and loans_basis else {})} for k in order if k in by_cat]
    return {"known": known, "count": count, "categories": cats, "total": _r(sum(by_cat.values())) if known else None}


def build(income_sources: list[IncomeSource], expenses: list[Txn], today: date, months: int = 6,
          loans_scheduled_monthly: float | None = None) -> dict:
    """The cashflow view for the last ``months`` months (current, partial month included as the last entry).

    ``loans_scheduled_monthly`` is the sum of the active loans' monthly payments (None when unknown); it is used for the CURRENT month only,
    and only when no loan charge was recorded in it."""
    rows: list[dict] = []
    for key, start, end in month_windows(today, months):
        src_rows = [r for r in (_source_month(s, start, end) for s in income_sources) if r]
        income_known = bool(src_rows)
        income = {"known": income_known, "sources": src_rows,
                  "gross": _r(sum(r["gross"] for r in src_rows)) if income_known else None,
                  "direct_costs": _r(sum(r["direct_costs"] for r in src_rows)) if income_known else None,
                  "net": _r(sum(r["net"] for r in src_rows)) if income_known else None}
        exp = _expense_month(expenses, start, end, today, loans_scheduled_monthly)
        missing = [name for name, ok in (("income", income_known), ("expenses", exp["known"])) if not ok]
        balance = _r(income["net"] - exp["total"]) if not missing else None
        is_current = start <= today <= end
        rows.append({"month": key, "is_current": is_current,
                     "partial": is_current and today < end,
                     "day": today.day if is_current else None, "days_in_month": end.day,
                     "income": income, "expenses": exp, "balance": balance,
                     "shortfall": _r(max(-balance, 0.0)) if balance is not None else None,
                     "surplus": _r(max(balance, 0.0)) if balance is not None else None,
                     "missing": missing})
    return {"months": rows, "categories": [{"key": k, "label": v} for k, v in EXPENSE_CATEGORIES],
            "insights": insights(rows, expenses, today), "thresholds": THRESHOLDS, "as_of": today.isoformat()}


# ── insights (deterministic, numbers only — no recommendation wording here) ───────────────────────────────────────
def _cat_amounts(month_row: dict) -> dict[str, float]:
    return {c["key"]: c["amount"] for c in month_row["expenses"]["categories"]}


def category_changes(rows: list[dict]) -> dict | None:
    """The last two COMPLETE months with known expenses, category by category. None when there are not two such months."""
    done = [r for r in rows if not r["is_current"] and r["expenses"]["known"]]
    if len(done) < 2:
        return None
    prev, last = done[-2], done[-1]
    a, b = _cat_amounts(prev), _cat_amounts(last)
    items = []
    for key in sorted(set(a) | set(b)):
        before, after = a.get(key, 0.0), b.get(key, 0.0)
        delta = _r(after - before)
        if abs(delta) < MIN_CHANGE:
            continue
        items.append({"key": key, "label": label_of(key), "before": _r(before), "after": _r(after), "delta": delta,
                      "pct": _r((after - before) / before * 100.0) if before > 0 else None})
    items.sort(key=lambda i: abs(i["delta"]), reverse=True)
    return {"from": prev["month"], "to": last["month"], "total_before": prev["expenses"]["total"],
            "total_after": last["expenses"]["total"], "total_delta": _r(last["expenses"]["total"] - prev["expenses"]["total"]),
            "items": items}


def category_spikes(rows: list[dict]) -> list[dict]:
    """A category in the latest known months that is well above its own baseline (the average of up to 3 preceding KNOWN months)."""
    known = [r for r in rows if r["expenses"]["known"]]
    out: list[dict] = []
    for idx, row in enumerate(known):
        if idx < SPIKE_MIN_BASELINE_MONTHS or idx < len(known) - 2:   # judge the last two known months only
            continue
        prior = known[max(0, idx - BASELINE_MONTHS):idx]
        for c in row["expenses"]["categories"]:
            history = [_cat_amounts(p).get(c["key"], 0.0) for p in prior]
            baseline = sum(history) / len(history)
            excess = c["amount"] - baseline
            if baseline > 0 and excess >= SPIKE_MIN_EXCESS and excess / baseline > SPIKE_PCT:
                out.append({"month": row["month"], "key": c["key"], "label": c["label"], "amount": c["amount"],
                            "baseline": _r(baseline), "excess": _r(excess), "partial": bool(row["partial"])})
    out.sort(key=lambda s: s["excess"], reverse=True)
    return out


def large_items(expenses: list[Txn], rows: list[dict]) -> list[dict]:
    """Single expense items inside the window that stand out: >= the floor and, with >= 3 items in the category, >= 3x its median."""
    if not rows:
        return []
    start = date(int(rows[0]["month"][:4]), int(rows[0]["month"][5:]), 1)
    pool = [t for t in expenses if t.occurred >= start and t.amount > 0]
    by_cat: dict[str, list[float]] = {}
    for t in pool:
        by_cat.setdefault(category_key(t.category), []).append(t.amount)
    out = []
    for t in pool:
        key = category_key(t.category)
        amounts = by_cat[key]
        threshold = LARGE_ITEM_FLOOR
        if len(amounts) >= 3:
            threshold = max(threshold, LARGE_ITEM_MULT * median(amounts))
        if t.amount >= threshold:
            out.append({"ref": t.ref, "label": t.label, "amount": _r(t.amount), "date": t.occurred.isoformat(),
                        "key": key, "category": label_of(key)})
    out.sort(key=lambda i: i["amount"], reverse=True)
    return out[:LARGE_ITEM_LIMIT]


def insights(rows: list[dict], expenses: list[Txn], today: date) -> dict:
    return {"changes": category_changes(rows), "spikes": category_spikes(rows), "large_items": large_items(expenses, rows)}
