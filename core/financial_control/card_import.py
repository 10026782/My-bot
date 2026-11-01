"""FCC credit-card statement import, stage 5c — pure parser + classifier + matching to the bank. No I/O, no writes, no network, no model.

Input: the TEXT FRAGMENTS of a card statement (``Fragment(page, x, y, text)``; y grows downward; text already in logical Hebrew order — the
extraction layer, ``scripts/fcc_card_statement_report.py``, reads the PDF and fixes the visual order). Written for the Max and the Isracard layouts:
a section of rows (date, [card at the business], merchant, type / sector, transaction amount, charge amount, remarks) closed by a
``סה"כ חיובים בתאריך`` (Max) / ``סה"כ חיוב לתאריך`` (Isracard) ``dd/mm/yy  total`` line; the card's own fee lines (no date) belong to the section they precede.

Iron rules:
* **A section is trusted only if it adds up.** The sum of its rows' charge amounts must equal the statement's own section total; a section that
  does not, a row left after the last total, or a row whose amounts cannot be read makes the statement ``ok = False`` (reported, never repaired).
* **The card statement is where the spending is; the bank line is only the payment.** A section's total is matched to the bank's card-settlement
  debit (same amount, the billing date or up to 3 days later, each bank line used once). A matched settlement stops being spending — its rows,
  with their merchants and categories, take its place — so bank + card can never count the same money twice. An unmatched settlement keeps
  counting as spending until its own card statement is imported.
* **Cash and loans are named for what they are:** an ATM withdrawal is ``cash_withdrawal`` (what was bought with the cash is unknown); a card
  loan instalment is an expense in the ``loans`` category at the INSTALMENT (the loan's full amount is never spending).
* **Importable only when decided:** an expense with a category (``importable``); cash and unknown merchants wait for the owner.
* **Unknown merchant = unknown** (the owner's rules are the only way a new merchant becomes known); only high-precision built-in rules exist.
* Only the last four digits of a card are read; the holder's name is never read into the result.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from core.financial_control import bank_import as bi

# kinds of a card line (after classification)
EXPENSE = "expense"
CASH = "cash_withdrawal"
ADJUSTMENT = "adjustment"            # a benefit / discount line (negative)
UNKNOWN = "unknown"
KINDS = (EXPENSE, CASH, ADJUSTMENT, UNKNOWN)

REGULAR, IMMEDIATE, LOAN, BENEFIT, FEE = "regular", "immediate", "loan_installment", "benefit", "fee"
ROW_TOLERANCE = 4.0                  # fragments whose y differs by less than this belong to one row (an icon / date sits a hair off the text)
SETTLEMENT_WINDOW_DAYS = 3
TOLERANCE = 0.005
DEFAULT_TYPE_X = 373.0               # the "סוג העסקה" column, when no header row was seen yet
MERCHANT_MARGIN = 9.0
NAME_MARGIN = 8.0                    # the merchant column ends here (right of it: the card-at-the-business column, never part of the name)
FEE_CATEGORY = "עמלות וריבית"
SECTOR_CATEGORIES = {"דלק": "transport", "תחבורה": "transport", "ביטוח": "insurance"}   # the issuer's own sector, only where it is unambiguous

_DATE = re.compile(r"^(\d{2}/\d{2}/\d{2})(?!\d)")
_AMOUNT = re.compile(r"^-?[\d,]+\.\d{2}$")
_LAST4 = re.compile(r"^\d{4}$")
_INSTALMENT = re.compile(r"(\d+)\s*מתוך\s*(\d+)")


@dataclass(frozen=True)
class Fragment:
    page: int
    x: float
    y: float
    text: str


@dataclass(frozen=True)
class CardCharge:
    date: date
    merchant: str
    charge: float                     # what is billed (negative = a benefit)
    amount: float | None              # the transaction's own amount (a loan's full amount, a foreign amount...)
    card: str                         # last four digits
    billing_date: date
    section: int
    kind: str                         # regular | immediate | loan_installment | benefit
    remark: str = ""
    sector: str = ""                  # the issuer's own type (Max) / sector (Isracard) text
    key: str = ""


@dataclass(frozen=True)
class Section:
    index: int
    card: str
    billing_date: date
    total: float
    computed: float
    ok: bool
    rows: int
    immediate: bool


@dataclass
class CardParse:
    charges: list[CardCharge]
    sections: list[Section]
    problems: list[str] = field(default_factory=list)
    ok: bool = True


def _d(token: str) -> date:
    return datetime.strptime(token, "%d/%m/%y").date()


def _num(token: str) -> float:
    return float(token.replace(",", ""))


def _rows(fragments: list[Fragment]) -> list[list[Fragment]]:
    """Reading order: page, then top to bottom; fragments less than ROW_TOLERANCE apart vertically are one row (left to right = x descending in RTL)."""
    out: list[list[Fragment]] = []
    last: Fragment | None = None
    for f in sorted(fragments, key=lambda f: (f.page, f.y, -f.x)):
        if last is not None and f.page == last.page and f.y - last.y < ROW_TOLERANCE:
            out[-1].append(f)
        else:
            out.append([f])
        last = f
    return [sorted(r, key=lambda f: -f.x) for r in out]


def _tokens(row: list[Fragment]) -> set[str]:
    return {t for f in row for t in bi.normalize(f.text).split()}


def parse_card_statement(fragments: list[Fragment], card_ref: str = "") -> CardParse:
    """Parse the fragments into charges and sections. ``card_ref`` is a label the CALLER chooses (it keeps two cards' keys apart)."""
    charges: list[CardCharge] = []
    sections: list[Section] = []
    problems: list[str] = []
    pending: list[dict] = []
    card, type_x, name_x = "", DEFAULT_TYPE_X, None
    for row in _rows(fragments):
        toks = _tokens(row)
        if "תאריך" in toks and toks & {"סוג", "ענף"} and toks & {"הערות", "סכום"}:          # a column header row (Max: סוג, Isracard: ענף)
            type_x = next(f.x for f in row if bi.normalize(f.text) in ("סוג", "ענף"))
            name_x = next((f.x for f in row if bi.normalize(f.text) == "שם"), name_x)
            continue
        if toks & {"שמסתיים", "שמסתיימים"}:
            digits = [f.text for f in row if _LAST4.match(f.text.strip())]
            if digits:
                card = digits[-1]
            continue
        dates = [(f, _DATE.match(f.text.strip())) for f in row]
        dates = [(f, m) for f, m in dates if m]
        amounts = [f for f in row if _AMOUNT.match(f.text.strip())]
        if "סהכ" in toks and (toks & {"חיובים", "חיוב"}) and (toks & {"בתאריך", "לתאריך"}) and dates and len(amounts) == 1:
            billing, total = _d(dates[0][1].group(1)), _num(amounts[0].text.strip())
            computed = round(sum(p["charge"] for p in pending), 2)
            ok = abs(computed - total) <= TOLERANCE
            if not ok:
                problems.append(f"section {len(sections) + 1} ({card}, {billing}): rows add up to {computed:.2f}, the statement says {total:.2f}")
            sections.append(Section(len(sections) + 1, card, billing, total, computed, ok, len(pending), any(p["kind"] == IMMEDIATE for p in pending)))
            for p in pending:
                charges.append(CardCharge(p["date"] or billing, p["merchant"], p["charge"], p["amount"], card, billing, len(sections), p["kind"], p["remark"], p["sector"]))
            pending = []
            continue
        if pending and not dates and len(amounts) == 1 and "סהכ" not in toks:                 # the card's own fee lines: no date, they precede the section total
            fee = "דמי" in toks or ("מעמ" in toks and any(f.text.strip().endswith("%") for f in row))
            if fee:
                words = " ".join(f.text.strip() for f in row if f.text.strip() not in ("₪", "") and not _AMOUNT.match(f.text.strip()) and not f.text.strip().endswith("%"))
                pending.append({"date": None, "merchant": re.sub(r"\s+", " ", words).strip(), "charge": _num(amounts[0].text.strip()), "amount": None,
                                "kind": FEE, "remark": "", "sector": ""})
            continue
        if not dates or not 1 <= len(amounts) <= 2:
            if dates and len(amounts) > 2:
                problems.append(f"unreadable row: {' '.join(f.text for f in row)[:80]}")
            continue
        amounts.sort(key=lambda f: -f.x)                                     # RTL: the transaction amount is right of the charge amount
        charge_f = amounts[-1]
        amount_f = amounts[0] if len(amounts) == 2 else None
        used = {id(f) for f, _ in dates} | {id(f) for f in amounts}
        rest = [f for f in row if id(f) not in used and f.text.strip() not in ("₪", "")]
        merchant = " ".join(f.text.strip() for f in rest if f.x > type_x + MERCHANT_MARGIN and (name_x is None or f.x <= name_x + NAME_MARGIN))
        lo, hi = (amount_f.x + 5.0 if amount_f else charge_f.x), type_x + MERCHANT_MARGIN
        kind_text = " ".join(f.text.strip() for f in rest if lo < f.x <= hi)
        remark = " ".join(f.text.strip() for f in rest if f.x < charge_f.x - 8.0)
        charge = _num(charge_f.text.strip())
        kind = IMMEDIATE if "מיידי" in kind_text else LOAN if "הלוואה" in kind_text else BENEFIT if (amount_f is None and charge < 0) else REGULAR
        if not merchant and kind == BENEFIT:
            merchant = remark or "הטבה"
        pending.append({"date": _d(dates[0][1].group(1)), "merchant": re.sub(r"\s+", " ", merchant).strip(), "charge": charge,
                        "amount": _num(amount_f.text.strip()) if amount_f else None, "kind": kind, "remark": re.sub(r"\s+", " ", remark).strip(),
                        "sector": re.sub(r"\s+", " ", kind_text).strip()})
    if pending:
        problems.append(f"{len(pending)} row(s) after the last section total")
    seen: dict[tuple, int] = {}
    keyed = []
    for c in charges:
        base = (card_ref, c.card, c.date.isoformat(), f"{c.charge:.2f}", bi.normalize(c.merchant), c.billing_date.isoformat())
        n = seen[base] = seen.get(base, 0) + 1                                # two identical same-day charges stay distinct
        keyed.append(CardCharge(**{**c.__dict__, "key": "card:" + hashlib.sha1(("|".join(base) + f"|{n}").encode("utf-8")).hexdigest()[:20]}))
    return CardParse(keyed, sections, problems, ok=not problems and bool(sections))


# ── classification ────────────────────────────────────────────────────────────────────────────────────────────────
def _r(match: str, category: str) -> bi.Rule:
    return bi.Rule(bi.normalize(match), bi.EXPENSE, category, None, f"builtin:{bi.normalize(match)}")


BUILTIN_RULES: tuple[bi.Rule, ...] = (            # high precision only; everything else is the owner's call
    _r("לתחבורה ציבורית", "transport"), _r("רב קו", "transport"), _r("פנגו", "transport"), _r("סונול", "transport"), _r("דלק", "transport"),
    _r("ביטוח", "insurance"), _r("הראל", "insurance"), _r("מגדל", "insurance"),
    _r("קופת חולים", "health"), _r("מכבי", "health"), _r("כללית", "health"),
)


@dataclass(frozen=True)
class ClassifiedCharge:
    charge: CardCharge
    kind: str
    category: str | None = None
    rule_id: str | None = None


def classify_charge(c: CardCharge, owner_rules: list[bi.Rule] | None = None) -> ClassifiedCharge:
    if c.kind == LOAN:
        return ClassifiedCharge(c, EXPENSE, "loans", "card:loan_installment")
    if c.kind == BENEFIT:
        return ClassifiedCharge(c, ADJUSTMENT, None, "card:benefit")
    if c.kind == FEE:
        return ClassifiedCharge(c, EXPENSE, FEE_CATEGORY, "card:fee")
    norm = bi.normalize(c.merchant)
    if "כספומט" in norm.split() or " משיכת מזומנים " in f" {norm} " or c.kind == IMMEDIATE and "כספומט" in norm:
        return ClassifiedCharge(c, CASH, None, "card:atm")
    for rule in [*(owner_rules or []), *BUILTIN_RULES]:
        if rule.key is None and f" {rule.match} " in f" {norm} ":
            kind = {bi.EXPENSE: EXPENSE, bi.IGNORE: ADJUSTMENT}.get(rule.kind, EXPENSE)
            return ClassifiedCharge(c, kind, rule.category, rule.rule_id)
    for word in bi.normalize(c.sector).split():                                  # the issuer's own sector: only the unambiguous ones
        if word in SECTOR_CATEGORIES:
            return ClassifiedCharge(c, EXPENSE, SECTOR_CATEGORIES[word], f"sector:{word}")
    return ClassifiedCharge(c, UNKNOWN, None, None)


def importable(c: ClassifiedCharge) -> bool:
    """Only a charge with a decided category is written. Unknown merchants, ATM withdrawals (cash: what it bought is unknown) and benefit lines
    wait for the owner."""
    return c.kind == EXPENSE and bool(c.category)


def classify_all(charges: list[CardCharge], owner_rules: list[bi.Rule] | None = None) -> list[ClassifiedCharge]:
    return [classify_charge(c, owner_rules) for c in charges]


# ── matching a card section to the bank's settlement ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Match:
    section: Section
    bank_key: str | None             # None = no bank line found (not paid from this account / outside the bank statement's period)


def match_settlements(sections: list[Section], bank_items: list[bi.Classified]) -> list[Match]:
    """Each section total against the bank's card-settlement debits: the same amount on the billing date or up to SETTLEMENT_WINDOW_DAYS later;
    the closest date wins and a bank line is used once. A section with no bank line is reported (``bank_key = None``), never forced."""
    free = {c.row.key: c for c in bank_items if c.kind == bi.CARD_SETTLEMENT and c.row.direction == bi.DEBIT}
    out: list[Match] = []
    for s in sorted(sections, key=lambda s: (s.billing_date, s.index)):
        best = None
        for key, c in free.items():
            gap = (c.row.date - s.billing_date).days
            if abs(c.row.amount - s.total) <= TOLERANCE and 0 <= gap <= SETTLEMENT_WINDOW_DAYS and (best is None or gap < best[0]):
                best = (gap, key)
        if best:
            del free[best[1]]
        out.append(Match(s, best[1] if best else None))
    return out


def reconcile(bank_items: list[bi.Classified], matches: list[Match]) -> dict:
    """What the card statement explains of the bank statement: the matched settlements (no longer spending), the card sections the bank does not
    show, and the bank's card settlements this statement does NOT cover (they keep counting until their own card statement is imported)."""
    matched = {m.bank_key for m in matches if m.bank_key}
    settlements = [c for c in bank_items if c.kind == bi.CARD_SETTLEMENT and c.row.direction == bi.DEBIT]
    rest = [c for c in settlements if c.row.key not in matched]
    return {
        "matched": [{"billing_date": m.section.billing_date.isoformat(), "card": m.section.card, "total": m.section.total, "bank_key": m.bank_key} for m in matches if m.bank_key],
        "sections_without_bank_line": [{"billing_date": m.section.billing_date.isoformat(), "card": m.section.card, "total": m.section.total} for m in matches if not m.bank_key],
        "uncovered_bank_settlements": {"count": len(rest), "total": round(sum(c.row.amount for c in rest), 2)},
        "matched_total": round(sum(m.section.total for m in matches if m.bank_key), 2),
    }


def summarize(items: list[ClassifiedCharge], top: int = 25) -> dict:
    by_kind: dict[str, dict] = {k: {"count": 0, "total": 0.0} for k in KINDS}
    by_cat: dict[str, float] = {}
    unmapped: dict[str, dict] = {}
    for c in items:
        by_kind[c.kind]["count"] += 1
        by_kind[c.kind]["total"] += c.charge.charge
        if c.kind == EXPENSE:
            by_cat[c.category or "uncategorized"] = by_cat.get(c.category or "uncategorized", 0.0) + c.charge.charge
        if c.kind == UNKNOWN:
            u = unmapped.setdefault(bi.normalize(c.charge.merchant), {"merchant": c.charge.merchant, "count": 0, "total": 0.0})
            u["count"] += 1
            u["total"] = round(u["total"] + c.charge.charge, 2)
    for v in by_kind.values():
        v["total"] = round(v["total"], 2)
    return {"by_kind": by_kind, "by_category": {k: round(v, 2) for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])},
            "unmapped": sorted(unmapped.values(), key=lambda u: -u["total"])[:top], "unmapped_total": len(unmapped)}
