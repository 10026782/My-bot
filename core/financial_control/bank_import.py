"""FCC bank-statement import, stage 5a — pure parser + classifier. No I/O, no writes, no network, no model.

Input: the TEXT of a bank "תנועות בחשבון" statement (``pdftotext -layout`` of the bank's PDF; the Bank Hapoalim layout: date, description,
debit, credit, running balance). Output: the movements, each with an arithmetic check, and a deterministic classification.

Iron rules:
* **A row is trusted only if it adds up.** The running balance gives an exact check: |balance(row) - balance(older neighbour)| must equal the
  row's amount, and its sign says debit / credit. The amount's COLUMN gives a second, independent direction. Both agree -> ``verified``;
  a disagreement or a broken chain is reported (``conflict`` / ``chain_break``), never silently resolved by guessing. A statement with a
  broken chain is incomplete (a missing page / row) and ``ok`` is False.
* **A statement is a ledger of money movements, not of expenses.** A credit-card settlement, a transfer between own accounts and a returned
  charge (a debit reversed by a credit) are NOT spending; only the card's own statement carries the real merchants and categories. They are
  classified apart (``card_settlement`` / ``transfer`` / ``reversal``) so that importing both a bank and a card statement never counts the
  same money twice.
* **Unknown is unknown.** A description no rule knows is ``unknown`` (never guessed into a category); the owner's own rules (``owner_rules``)
  win over the built-in ones and are the only way a new description becomes known. Every credit is an ``income_candidate`` until a source is
  assigned — a credit is not necessarily income.
* The account number / holder name in the statement header are never read into the result.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime

# ── kinds ────────────────────────────────────────────────────────────────────────────────────────────────────────
EXPENSE = "expense"                    # a known spending category (built-in or owner rule)
CARD_SETTLEMENT = "card_settlement"    # the bank paying a credit-card bill: NOT spending (the card statement has the merchants)
INCOME = "income_candidate"            # a credit; the source is assigned by the owner (an owner rule may give it)
TRANSFER = "transfer"                  # between the owner's own accounts / people: neither income nor spending
REVERSAL = "reversal"                  # a debit and the credit that returned it: both cancel out
IGNORE = "ignore"                      # the owner told us to skip it
UNKNOWN = "unknown"                    # a debit no rule knows
KINDS = (EXPENSE, CARD_SETTLEMENT, INCOME, TRANSFER, REVERSAL, IGNORE, UNKNOWN)
COUNTED_AS_SPENDING = (EXPENSE, UNKNOWN)       # the only kinds that are spending today (card settlements count only until a card statement covers them)

CREDIT, DEBIT = "credit", "debit"
TOLERANCE = 0.005
REVERSAL_WINDOW_DAYS = 14

_BIDI = re.compile("[‎‏‪-‮⁦-⁩]")
_DATE = re.compile(r"(\d{2}/\d{2}/\d{4})\s*$")
_BAL = re.compile(r"(-?)₪\s*(-?)([\d,]+\.\d{2})|₪\s*(-?[\d,]+\.\d{2})")
_AMT = re.compile(r"(?<![\d,.])[\d,]+\.\d{2}(?![\d])")


@dataclass(frozen=True)
class BankRow:
    date: date
    description: str
    amount: float                    # always positive
    direction: str                   # credit | debit
    balance: float
    verified: bool                   # the balance chain AND the column agree (or the chain alone, when the column is unknown)
    flags: tuple[str, ...] = ()      # conflict | chain_break | no_neighbour | column_only
    key: str = ""                    # idempotency key (account_ref + date + direction + amount + balance + description)


@dataclass
class ParseResult:
    rows: list[BankRow]              # oldest first
    unparsed: list[str] = field(default_factory=list)
    period: tuple[date, date] | None = None
    ok: bool = True                  # every transition between neighbours adds up and nothing was left unparsed
    summary: dict = field(default_factory=dict)


def _num(token: str) -> float:
    return float(token.replace(",", ""))


def _d(token: str) -> date:
    return datetime.strptime(token, "%d/%m/%Y").date()


def normalize(text: str) -> str:
    """For rule matching: no bidi marks, quotes / geresh removed (מע"מ == מעמ), punctuation to spaces, one space between tokens."""
    t = _BIDI.sub("", text or "")
    t = re.sub(r"[\"'״׳`]", "", t)
    t = re.sub(r"[^\w֐-׿]+", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip().casefold()


def _balance(line: str):
    m = _BAL.search(line)
    if not m:
        return None, None
    if m.group(3) is not None:
        value = _num(m.group(3)) * (-1 if (m.group(1) or m.group(2)) else 1)
    else:
        value = _num(m.group(4))
    return value, m.span()


def _split_pages(text: str) -> list[str]:
    return _BIDI.sub("", text).split("\f")


def _columns(page: str, previous: tuple[int, int] | None) -> tuple[int, int] | None:
    for line in page.splitlines():
        if "זכות" in line and "חובה" in line:
            return line.index("זכות") + len("זכות"), line.index("חובה") + len("חובה")
    return previous


def parse_statement(text: str, account_ref: str = "") -> ParseResult:
    """Parse the statement text. ``account_ref`` is a label the CALLER chooses (never the bank account number) that keeps two accounts' keys apart."""
    parsed: list[dict] = []
    unparsed: list[str] = []
    cols: tuple[int, int] | None = None
    for page in _split_pages(text):
        cols = _columns(page, cols)
        for line in page.splitlines():
            dm = _DATE.search(line)
            bal, span = _balance(line)
            if not dm or bal is None:
                continue
            body = line[:dm.start()]
            amounts = [m for m in _AMT.finditer(body) if not (span[0] <= m.start() < span[1])]
            if len(amounts) != 1:
                unparsed.append(line.strip())
                continue
            a = amounts[0]
            column = None
            if cols:
                column = CREDIT if a.end() <= (cols[0] + cols[1]) / 2 else DEBIT
            desc = body
            for s, e in sorted([span, (a.start(), a.end())], reverse=True):
                desc = desc[:s] + " " + desc[e:]
            desc = re.sub(r"##", " ", desc)
            desc = re.sub(r"\s+", " ", desc).strip()
            parsed.append({"date": _d(dm.group(1)), "desc": desc, "amount": _num(a.group()), "balance": bal, "column": column})
    if not parsed:
        return ParseResult([], unparsed, None, ok=False, summary={"rows": 0, "unparsed": len(unparsed)})

    descending = parsed[0]["date"] >= parsed[-1]["date"]
    n = len(parsed)
    rows: list[BankRow] = []
    breaks = conflicts = verified = 0
    for i, p in enumerate(parsed):
        older = (i + 1 if descending else i - 1)
        flags: list[str] = []
        chain_dir = None
        if 0 <= older < n:
            delta = round(p["balance"] - parsed[older]["balance"], 2)
            if abs(abs(delta) - p["amount"]) <= TOLERANCE:
                chain_dir = CREDIT if delta > 0 else DEBIT
            else:
                flags.append("chain_break")
        else:
            flags.append("no_neighbour")
        direction, ok = chain_dir or p["column"], False
        if chain_dir and p["column"] and chain_dir != p["column"]:
            flags.append("conflict")
        elif chain_dir:
            ok = True
        elif p["column"] and "chain_break" not in flags:
            flags.append("column_only")
        if direction is None:
            unparsed.append(f"{p['date']} {p['desc']} {p['amount']}")
            continue
        breaks += "chain_break" in flags
        conflicts += "conflict" in flags
        verified += ok
        key = hashlib.sha1("|".join((account_ref, p["date"].isoformat(), direction, f"{p['amount']:.2f}", f"{p['balance']:.2f}", normalize(p["desc"]))).encode("utf-8")).hexdigest()[:20]
        rows.append(BankRow(p["date"], p["desc"], p["amount"], direction, p["balance"], ok, tuple(flags), "bank:" + key))
    if descending:
        rows.reverse()
    period = (min(r.date for r in rows), max(r.date for r in rows)) if rows else None
    return ParseResult(rows, unparsed, period, ok=(breaks == 0 and conflicts == 0 and not unparsed),
                       summary={"rows": len(rows), "verified": verified, "chain_breaks": breaks, "conflicts": conflicts, "unparsed": len(unparsed),
                                "unchecked": len(rows) - verified - breaks - conflicts})


# ── classification ────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Rule:
    match: str                       # a whole-token sequence of the NORMALIZED description
    kind: str
    category: str | None = None      # expense category key / custom name, or an income source name (INCOME)
    direction: str | None = None     # None = any
    rule_id: str = ""


def _r(match: str, kind: str, category: str | None = None, direction: str | None = None) -> Rule:
    return Rule(normalize(match), kind, category, direction, f"builtin:{normalize(match)}")


# High precision only: a name that could mean two things is left to the owner's rules.
BUILTIN_RULES: tuple[Rule, ...] = (
    # credit-card bills paid by the bank: not spending (the card statement has the merchants)
    _r("ישראכרט", CARD_SETTLEMENT, direction=DEBIT), _r("מקס איט", CARD_SETTLEMENT, direction=DEBIT), _r("כרטיסי אשראי", CARD_SETTLEMENT, direction=DEBIT),
    _r("מסטרקרד", CARD_SETTLEMENT, direction=DEBIT), _r("ויזה כאל", CARD_SETTLEMENT, direction=DEBIT), _r("לאומי קארד", CARD_SETTLEMENT, direction=DEBIT),
    _r("דיינרס", CARD_SETTLEMENT, direction=DEBIT), _r("אמריקן אקספרס", CARD_SETTLEMENT, direction=DEBIT),
    # between the owner's own accounts / people
    _r("העברה נייד", TRANSFER), _r("העב לאחר נייד", TRANSFER),
    # a charge the bank returned
    _r("החזר חיוב", REVERSAL, direction=CREDIT),
    # loans
    _r("משכנתא", EXPENSE, "loans", DEBIT), _r("הלואה", EXPENSE, "loans", DEBIT), _r("הלו רבית", EXPENSE, "loans", DEBIT),
    # taxes and levies
    _r("מעמ", EXPENSE, "taxes", DEBIT), _r("ביטוח לאומי", EXPENSE, "taxes", DEBIT), _r("עיריית", EXPENSE, "taxes", DEBIT), _r("מס הכנסה", EXPENSE, "taxes", DEBIT),
    _r("רשות המסים", EXPENSE, "taxes", DEBIT), _r("ארנונה", EXPENSE, "taxes", DEBIT),
    # health / insurance
    _r("שירותי בריאות", EXPENSE, "health", DEBIT), _r("מכבי", EXPENSE, "health", DEBIT), _r("כללית", EXPENSE, "health", DEBIT),
    _r("הראל", EXPENSE, "insurance", DEBIT), _r("הפניקס", EXPENSE, "insurance", DEBIT), _r("מגדל", EXPENSE, "insurance", DEBIT), _r("ביטוח", EXPENSE, "insurance", DEBIT),
    # bank charges (a custom category: it needs no schema change)
    _r("עמלה", EXPENSE, "עמלות וריבית", DEBIT), _r("רבית", EXPENSE, "עמלות וריבית", DEBIT), _r("ריבית", EXPENSE, "עמלות וריבית", DEBIT),
    # credits that are known to be a kind of income source
    _r("קצבת ילדים", INCOME, "קצבאות", CREDIT), _r("בטוח לאומי", INCOME, "קצבאות", CREDIT), _r("ביטוח לאומי", INCOME, "קצבאות", CREDIT),
    _r("הפק מזומן", INCOME, None, CREDIT), _r("העברה הפקדה", INCOME, None, CREDIT),
)


def owner_rules_from(items) -> list[Rule]:
    """The owner's rules (list of {match, kind, category?, direction?}); an invalid item is skipped (reported by the caller via len())."""
    out = []
    for i, it in enumerate(items or []):
        match = normalize(str((it or {}).get("match") or ""))
        kind = (it or {}).get("kind")
        direction = (it or {}).get("direction") or None
        if not match or kind not in KINDS or kind == UNKNOWN or direction not in (None, CREDIT, DEBIT):
            continue
        out.append(Rule(match, kind, (it.get("category") or None), direction, f"owner:{i}"))
    return out


def _matches(rule: Rule, norm: str, direction: str) -> bool:
    return (rule.direction in (None, direction)) and f" {rule.match} " in f" {norm} "


@dataclass(frozen=True)
class Classified:
    row: BankRow
    kind: str
    category: str | None = None
    rule_id: str | None = None
    paired_key: str | None = None            # REVERSAL: the key of the other half


def classify_row(row: BankRow, owner_rules: list[Rule] | None = None) -> Classified:
    norm = normalize(row.description)
    for rule in [*(owner_rules or []), *BUILTIN_RULES]:                 # the owner's rules win; first match wins
        if _matches(rule, norm, row.direction):
            return Classified(row, rule.kind, rule.category, rule.rule_id)
    return Classified(row, UNKNOWN if row.direction == DEBIT else INCOME, None, None)


def classify(rows: list[BankRow], owner_rules: list[Rule] | None = None) -> list[Classified]:
    """Classify, then cancel returned charges: a ``reversal`` credit is paired with the closest earlier-or-same-day unpaired debit of the same
    amount within REVERSAL_WINDOW_DAYS (both become ``reversal``). An unpaired returned-charge credit stays an income candidate (flagged by
    having no ``paired_key``)."""
    out = [classify_row(r, owner_rules) for r in rows]
    used: set[int] = set()
    for i, c in enumerate(out):
        if c.kind != REVERSAL or c.row.direction != CREDIT:
            continue
        best = None
        for j, d in enumerate(out):
            if j in used or d.row.direction != DEBIT or d.kind in (REVERSAL, IGNORE) or abs(d.row.amount - c.row.amount) > TOLERANCE:
                continue
            gap = (c.row.date - d.row.date).days
            if 0 <= gap <= REVERSAL_WINDOW_DAYS and (best is None or gap < best[0]):
                best = (gap, j)
        if best is None:
            out[i] = Classified(c.row, INCOME, None, c.rule_id)
            continue
        j = best[1]
        used.add(j)
        out[i] = Classified(c.row, REVERSAL, None, c.rule_id, out[j].row.key)
        out[j] = Classified(out[j].row, REVERSAL, None, out[j].rule_id, c.row.key)
    return out


# ── report ───────────────────────────────────────────────────────────────────────────────────────────────────────
def summarize(items: list[Classified], top_unknown: int = 15) -> dict:
    """Counts and sums by kind and by month, and the unknown descriptions that matter most (what the owner has to map once)."""
    by_kind: dict[str, dict] = {k: {"count": 0, "debit": 0.0, "credit": 0.0} for k in KINDS}
    months: dict[str, dict] = {}
    unknown: dict[str, dict] = {}
    for c in items:
        r = c.row
        side = "debit" if r.direction == DEBIT else "credit"
        by_kind[c.kind]["count"] += 1
        by_kind[c.kind][side] += r.amount
        m = months.setdefault(f"{r.date.year:04d}-{r.date.month:02d}", {"spending_candidates": 0.0, "card_settlements": 0.0, "income_candidates": 0.0, "other": 0.0})
        if c.kind in COUNTED_AS_SPENDING:
            m["spending_candidates"] += r.amount
        elif c.kind == CARD_SETTLEMENT:
            m["card_settlements"] += r.amount
        elif c.kind == INCOME:
            m["income_candidates"] += r.amount
        else:
            m["other"] += r.amount
        if c.kind in (UNKNOWN, INCOME) and c.rule_id is None:
            u = unknown.setdefault(normalize(r.description), {"description": r.description, "direction": r.direction, "count": 0, "total": 0.0})
            u["count"] += 1
            u["total"] = round(u["total"] + r.amount, 2)
    for v in by_kind.values():
        v["debit"], v["credit"] = round(v["debit"], 2), round(v["credit"], 2)
    for v in months.values():
        for k in v:
            v[k] = round(v[k], 2)
    top = sorted(unknown.values(), key=lambda u: -u["total"])[:top_unknown]
    return {"by_kind": by_kind, "months": dict(sorted(months.items())), "unmapped": top, "unmapped_total": len(unknown)}
