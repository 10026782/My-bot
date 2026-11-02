"""FCC statement import, stage 5b — the PLAN: what a bank / card statement would write, what it skips and what the owner still has to classify.
Pure: no I/O, no writes, no network, no model. The plan is data; executing it is a separate, gated step (one review -> אשר, in batches).

Iron rules (every one is a test):
* **Decided rows are written with their category; an unclassified OUTFLOW is written WITHOUT one** (a bank debit no rule knows, an itemized card purchase) and
  the owner classifies it one by one on screen (owner decision 01/11/2026) — it shows as "לא מסווג", never guessed into a category. Income, refunds, and anything that
  might be a transfer are never written without the owner's explicit decision (``bank_import.importable``). Everything else is skipped and says why.
* **Never the same money twice.** A bank card-settlement is NEVER written (the card statement carries the merchants); cash withdrawals, rolling-credit lines,
  benefit lines, transfers, returned charges (both halves) and rows marked for review are never written either. A row whose idempotency key already exists is
  skipped (``already_imported``): importing the same statement twice writes nothing the second time.
* **The owner classifies, the system asks.** Every description no rule decides becomes ONE pending rule row (the same description is never asked twice, not
  even when it is already waiting as a pending row); a row marked for review becomes a pending ROW rule (by its key) — the owner fills Kind / Category in Airtable.
* **Dates:** a purchase counts on its own date; a loan instalment, an instalment purchase and the card's own fees count on the BILLING date (their transaction
  date can be years back). A refund is a NEGATIVE expense; income carries its source name as ``מקור: <name>`` and no goal (it must not inflate an income goal).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from core.financial_control import bank_import as bi
from core.financial_control import card_import as ci

SOURCE_BANK, SOURCE_CARD = "import:bank", "import:card"
HOUSEHOLD, ONE_TIME = "household_expense", "one_time"
VERIFICATION = "statement"
INSTALMENTS_NOTE = "תשלומים"       # the Note of an imported purchase paid in instalments (the consumption tab shows them apart)
SKIP_REASONS = ("already_imported", "card_settlement", "cash_withdrawal", "credit_service", "adjustment", "transfer", "reversal", "ignore", "needs_review",
                "needs_classification", "no_category", "no_source")


@dataclass(frozen=True)
class PlannedEvent:
    key: str                         # the idempotency key of the statement row
    date: date
    kind: str                        # household_expense (an expense, or a NEGATIVE one for a refund) | one_time (approved income)
    amount: float                    # signed
    category: str | None             # expense category / None for income
    source_name: str | None          # income source ("מקור: <name>")
    label: str                       # the statement's own description
    origin: str                      # import:bank | import:card
    month: str = ""
    billing: date | None = None      # a CARD row: the statement's billing date (the cashflow tab counts by it; ``date`` stays the consumption date)
    installments: bool = False       # a purchase paid in instalments (not a loan): the consumption tab labels it


@dataclass(frozen=True)
class PendingRule:
    match: str                       # the description (or "" for a row rule)
    row_key: str | None
    applies_to: str                  # bank | card
    direction: str                   # debit | credit
    times_seen: int
    last_seen: date
    example_amount: float
    note: str = ""


@dataclass
class ImportPlan:
    events: list[PlannedEvent] = field(default_factory=list)
    pending_rules: list[PendingRule] = field(default_factory=list)
    skipped: dict[str, dict] = field(default_factory=dict)

    def skip(self, reason: str, amount: float) -> None:
        s = self.skipped.setdefault(reason, {"count": 0, "total": 0.0})
        s["count"] += 1
        s["total"] = round(s["total"] + amount, 2)


_LONG_NUMBER = re.compile(r"(?<!\d)\d(?:[ \-]{0,3}\d){7,}(?!\d)")        # the same shape the personal-data guard refuses (8+ digits, even grouped)


def mask_numbers(text: str) -> str:
    """A description may carry a full account / card / reference number: it is never copied into the owner's tables."""
    return _LONG_NUMBER.sub("#", text or "")


def _month(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _pending(plan: ImportPlan, groups: dict, norm_known: set[str], match: str, row_key: str | None, applies_to: str, direction: str, amount: float, day: date, note: str = "") -> None:
    ident = ("row", row_key) if row_key else ("desc", bi.normalize(match), direction)
    if row_key:
        if row_key in norm_known:
            return
    elif bi.normalize(match) in norm_known or bi.normalize(mask_numbers(match)) in norm_known:        # the table keeps the MASKED text
        return
    g = groups.get(ident)
    if g is None:
        groups[ident] = {"match": "" if row_key else mask_numbers(match), "row_key": row_key, "applies_to": applies_to, "direction": direction, "n": 1, "last": day, "amount": amount, "note": mask_numbers(note or match)}
    else:
        g["n"] += 1
        g["last"] = max(g["last"], day)
        g["amount"] = max(g["amount"], amount)


def _finish(plan: ImportPlan, groups: dict) -> ImportPlan:
    plan.pending_rules = [PendingRule(g["match"], g["row_key"], g["applies_to"], g["direction"], g["n"], g["last"], round(g["amount"], 2), g["note"])
                          for g in sorted(groups.values(), key=lambda g: -g["amount"])]
    plan.events.sort(key=lambda e: (e.date, e.key))
    return plan


def plan_bank(items: list[bi.Classified], existing_keys: set[str] = frozenset(), known_rule_keys: set[str] = frozenset(), applies_to: str = "bank") -> ImportPlan:
    """``known_rule_keys``: the normalized descriptions AND the row keys that already have a rule row in the owner's table (decided or pending) — they are
    never added again."""
    plan, groups = ImportPlan(), {}
    for c in items:
        r = c.row
        if r.key in existing_keys:
            plan.skip("already_imported", r.amount)
            continue
        kind = c.kind
        if bi.importable(c):
            if kind == bi.INCOME_APPROVED:
                plan.events.append(PlannedEvent(r.key, r.date, ONE_TIME, r.amount, None, c.category, r.description, SOURCE_BANK, _month(r.date)))
            else:
                sign = -1.0 if kind == bi.REFUND else 1.0
                plan.events.append(PlannedEvent(r.key, r.date, HOUSEHOLD, sign * r.amount, c.category, None, r.description, SOURCE_BANK, _month(r.date)))
            continue
        reason = {bi.CARD_SETTLEMENT: "card_settlement", bi.TRANSFER: "transfer", bi.REVERSAL: "reversal", bi.IGNORE: "ignore"}.get(kind)
        if kind == bi.NEEDS_REVIEW:
            plan.skip("needs_review", r.amount)
            _pending(plan, groups, known_rule_keys, r.description, r.key, applies_to, r.direction, r.amount, r.date, f"לבדיקה: {r.description}")
        elif reason:
            plan.skip(reason, r.amount)
        elif kind in (bi.EXPENSE, bi.REFUND):
            plan.skip("no_category", r.amount)
        elif kind == bi.INCOME_APPROVED:
            plan.skip("no_source", r.amount)
        elif kind == bi.UNKNOWN:                                          # an unknown debit is a real outflow: written WITHOUT a category; the owner classifies it on screen
            plan.events.append(PlannedEvent(r.key, r.date, HOUSEHOLD, r.amount, None, None, r.description, SOURCE_BANK, _month(r.date)))
        else:                                                             # an income candidate (a credit): waiting for the owner's explicit approval
            plan.skip("needs_classification", r.amount)
            _pending(plan, groups, known_rule_keys, r.description, None, applies_to, r.direction, r.amount, r.date)
    return _finish(plan, groups)


def _card_date(c: ci.CardCharge) -> date:
    instalment = c.kind in (ci.LOAN, ci.FEE) or "תשלום" in c.remark
    return c.billing_date if instalment else c.date


def _is_instalments(c: ci.CardCharge) -> bool:
    """A purchase paid in instalments (NOT a loan or a card fee): the statement says "תשלום" in the remarks."""
    return c.kind not in (ci.LOAN, ci.FEE) and "תשלום" in c.remark


def plan_card(items: list[ci.ClassifiedCharge], existing_keys: set[str] = frozenset(), known_rule_keys: set[str] = frozenset()) -> ImportPlan:
    plan, groups = ImportPlan(), {}
    for c in items:
        x = c.charge
        if x.key in existing_keys:
            plan.skip("already_imported", abs(x.charge))
            continue
        if ci.importable(c):
            day = _card_date(x)
            plan.events.append(PlannedEvent(x.key, day, HOUSEHOLD, x.charge, c.category, None, x.merchant, SOURCE_CARD, _month(day), x.billing_date, _is_instalments(x)))
        elif c.kind == ci.CASH:
            plan.skip("cash_withdrawal", abs(x.charge))
        elif c.kind == ci.CREDIT_SERVICE:
            plan.skip("credit_service", abs(x.charge))
        elif c.kind == ci.ADJUSTMENT:
            plan.skip("adjustment", abs(x.charge))
        elif c.kind == ci.EXPENSE:
            plan.skip("no_category", abs(x.charge))
        elif x.charge > 0:                                                # an itemized purchase nobody classified: written WITHOUT a category, classified on screen
            day = _card_date(x)
            plan.events.append(PlannedEvent(x.key, day, HOUSEHOLD, x.charge, None, None, x.merchant, SOURCE_CARD, _month(day), x.billing_date, _is_instalments(x)))
        else:
            plan.skip("needs_classification", abs(x.charge))
            _pending(plan, groups, known_rule_keys, x.merchant, None, "card", "debit", abs(x.charge), x.date)
    return _finish(plan, groups)


def merge(*plans: ImportPlan) -> ImportPlan:
    out = ImportPlan()
    seen_events, seen_pending = set(), set()
    for p in plans:
        for e in p.events:
            if e.key not in seen_events:
                seen_events.add(e.key)
                out.events.append(e)
        for r in p.pending_rules:
            ident = (r.row_key, bi.normalize(r.match), r.applies_to, r.direction)
            if ident not in seen_pending:
                seen_pending.add(ident)
                out.pending_rules.append(r)
        for reason, s in p.skipped.items():
            t = out.skipped.setdefault(reason, {"count": 0, "total": 0.0})
            t["count"] += s["count"]
            t["total"] = round(t["total"] + s["total"], 2)
    out.events.sort(key=lambda e: (e.date, e.key))
    return out


def summarize(plan: ImportPlan) -> dict:
    """What the review shows: per month the expenses (net of refunds) and the income that WOULD be written, by category / source, and what is skipped."""
    months: dict[str, dict] = {}
    for e in plan.events:
        m = months.setdefault(e.month, {"expenses": 0.0, "income": 0.0, "events": 0, "by_category": {}, "by_source": {}})
        m["events"] += 1
        if e.kind == HOUSEHOLD:
            m["expenses"] += e.amount
            m["by_category"][e.category or "uncategorized"] = round(m["by_category"].get(e.category or "uncategorized", 0.0) + e.amount, 2)
        else:
            m["income"] += e.amount
            m["by_source"][e.source_name or "?"] = round(m["by_source"].get(e.source_name or "?", 0.0) + e.amount, 2)
    for m in months.values():
        m["expenses"], m["income"] = round(m["expenses"], 2), round(m["income"], 2)
    uncat = [e for e in plan.events if e.kind == HOUSEHOLD and not e.category]
    return {"events": len(plan.events), "months": dict(sorted(months.items())), "skipped": plan.skipped,
            "uncategorized": {"count": len(uncat), "total": round(sum(e.amount for e in uncat), 2)},
            "pending_rules": len(plan.pending_rules), "pending_row_rules": sum(1 for r in plan.pending_rules if r.row_key)}


# ── the writes (data only — executed elsewhere, after the owner's approval) ──────────────────────────────────────────────
def event_fields(e: PlannedEvent, user_id: str = "") -> dict:
    """The ``Financial Progress Events`` fields of one planned event. No goal link on purpose: an imported row must not move any goal's progress; the owner's
    ledger (``Financial Owner``) is stamped by the access policy at execution."""
    from airtable_schema import FinEventFields as EF  # noqa: PLC0415
    f = {EF.KIND: e.kind, EF.AMOUNT: e.amount, EF.OCCURRED_AT: e.date.isoformat(), EF.RECORDED_BY: user_id, EF.SOURCE: e.origin, EF.SOURCE_REF: e.key,
         EF.IDEMPOTENCY_KEY: e.key, EF.RAW_TEXT: mask_numbers(e.label)[:200], EF.VERIFICATION: VERIFICATION}
    if e.kind == HOUSEHOLD and e.category:
        f[EF.EXPENSE_CATEGORY] = e.category
    if e.origin == SOURCE_CARD and e.billing:
        f[EF.BILLING_DATE] = e.billing.isoformat()
    if e.kind == HOUSEHOLD and e.installments:
        f[EF.NOTE] = INSTALMENTS_NOTE
    if e.kind == ONE_TIME and e.source_name:
        f[EF.NOTE] = f"מקור: {e.source_name}"
    return f


def event_write(e: PlannedEvent, user_id: str = "") -> dict:
    from airtable_schema import Tables  # noqa: PLC0415
    return {"op": "post", "table": Tables.FIN_EVENTS, "fields": event_fields(e, user_id), "audit_action": "fcc_import_event", "audit_details": e.key}


def pending_rule_fields(r: PendingRule) -> dict:
    """A pending ``Cashflow Rules`` row: no Kind (undecided) — the owner fills Kind / Category in Airtable."""
    from airtable_schema import CashflowRuleFields as CR  # noqa: PLC0415
    f = {CR.MATCH: r.match, CR.APPLIES_TO: r.applies_to, CR.DIRECTION: r.direction, CR.STATUS: "pending", CR.TIMES_SEEN: r.times_seen,
         CR.LAST_SEEN: r.last_seen.isoformat(), CR.EXAMPLE_AMOUNT: r.example_amount, CR.NOTES: r.note[:300]}
    if r.row_key:
        f[CR.ROW_KEY] = r.row_key
    return f


def known_rule_keys(rule_rows: list[dict]) -> set[str]:
    """The normalized descriptions and the row keys already present in the owner's rules table (any status): never asked twice."""
    from airtable_schema import CashflowRuleFields as CR  # noqa: PLC0415
    out: set[str] = set()
    for rec in rule_rows:
        f = rec.get("fields") or {}
        if f.get(CR.MATCH):
            out.add(bi.normalize(str(f[CR.MATCH])))
        if f.get(CR.ROW_KEY):
            out.add(str(f[CR.ROW_KEY]).strip())
    return out
