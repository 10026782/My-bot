#!/usr/bin/env python3
"""FCC bank-statement report (stage 5a) — OFFLINE, read-only: parse a bank "תנועות בחשבון" PDF/text, classify it, write a review pack.

    python3 scripts/fcc_bank_statement_report.py --pdf statement.pdf --account-ref poalim-main --outdir ~/fcc_review [--rules my_rules.json]

Writes to ``--outdir`` (which must be OUTSIDE this repository: a statement is private financial data and must never be committed):
  * classified.csv       every movement with its kind / category / the rule that decided it / the arithmetic check
  * summary.md           what the statement adds up to, month by month, and the descriptions you still have to map
  * rules_template.json  one entry per unmapped description for you to fill (kind: expense | income_candidate | transfer | ignore)

It touches no Airtable table and calls no model. The account number / holder name in the header are never read.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.financial_control import bank_import as bi  # noqa: E402
from core.financial_control import statement_reader as sr  # noqa: E402


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def read_parsed(pdf: Path, account_ref: str) -> bi.ParseResult:
    """The statement PDF read with the same pure-Python reader the server uses (no pdftotext binary needed)."""
    try:
        return sr.read_bank(pdf.read_bytes(), account_ref)
    except sr.StatementError as exc:
        raise SystemExit(str(exc))


def report(source, account_ref: str, owner_items=None) -> tuple[bi.ParseResult, list[bi.Classified], dict]:
    """``source``: the statement text (``pdftotext -layout``) or an already parsed ``ParseResult``."""
    parsed = source if isinstance(source, bi.ParseResult) else bi.parse_statement(source, account_ref)
    items = bi.classify(parsed.rows, bi.owner_rules_from(owner_items))
    return parsed, items, bi.summarize(items)


def write_pack(outdir: Path, parsed: bi.ParseResult, items: list[bi.Classified], summ: dict) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path, md_path, rules_path = outdir / "classified.csv", outdir / "summary.md", outdir / "rules_template.json"
    review_path = outdir / "review_one_by_one.csv"
    with review_path.open("w", newline="", encoding="utf-8-sig") as fh:             # every transfer / bit, in or out: the owner decides each row
        w = csv.writer(fh)
        w.writerow(["date", "direction", "amount", "description", "key", "decision (own_account | income | loan | other)", "source / note"])
        for c in items:
            if c.kind == bi.NEEDS_REVIEW:
                w.writerow([c.row.date.isoformat(), c.row.direction, f"{c.row.amount:.2f}", c.row.description, c.row.key, "", ""])
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "description", "direction", "amount", "balance", "kind", "category", "rule", "paired_with", "verified", "flags", "key"])
        for c in items:
            r = c.row
            w.writerow([r.date.isoformat(), r.description, r.direction, f"{r.amount:.2f}", f"{r.balance:.2f}", c.kind, c.category or "", c.rule_id or "",
                        c.paired_key or "", "yes" if r.verified else "no", " ".join(r.flags), r.key])
    s = parsed.summary
    lines = [f"# דוח תנועות בנק", "",
             f"תקופה: {parsed.period[0].isoformat()} – {parsed.period[1].isoformat()}" if parsed.period else "תקופה: לא זוהתה", "",
             f"- שורות: {s.get('rows', 0)} · אומתו בשרשרת היתרות: {s.get('verified', 0)} · שבירות שרשרת: {s.get('chain_breaks', 0)} · "
             f"סתירות כיוון: {s.get('conflicts', 0)} · שורות שלא פוענחו: {s.get('unparsed', 0)}",
             f"- **{'הדוח שלם ומתיישב' if parsed.ok else 'הדוח אינו שלם / אינו מתיישב — לא לייבא לפני בירור'}**", "", "## לפי סוג", "",
             "| סוג | שורות | חובה | זכות |", "|---|---:|---:|---:|"]
    for kind, v in summ["by_kind"].items():
        if v["count"]:
            lines.append(f"| {kind} | {v['count']} | {v['debit']:,.0f} | {v['credit']:,.0f} |")
    lines += ["", "## לפי חודש", "", "| חודש | הוצאות (מסווגות + לא ידועות) | חיובי כרטיס (ממתינים לפירוט) | זכויות (מועמדות — לא הכנסה) | הכנסה שאושרה | אחר |", "|---|---:|---:|---:|---:|---:|"]
    for month, v in summ["months"].items():
        lines.append(f"| {month} | {v['spending_candidates']:,.0f} | {v['card_settlements']:,.0f} | {v['income_candidates']:,.0f} | {v['income_approved']:,.0f} | {v['other']:,.0f} |")
    rv = summ["review"]
    lines += ["", f"## לבדיקה אחת-אחת: העברות וביט ({rv['count']})", "",
              f"- זכות ₪{rv['credit']:,.0f} · חובה ₪{rv['debit']:,.0f} — כל העברה (בזכות או בחובה) ו-bit מסומנות לבדיקה: מחשבון אחר שלך? הכנסה? הלוואה? סיבה אחרת? שום דבר מהן לא סווג ולא נספר.",
              "- הרשימה המלאה, שורה לשורה, ב-review_one_by_one.csv."]
    lines += ["", f"## תיאורים שעדיין לא ממופים ({summ['unmapped_total']})", "", "| תיאור | כיוון | פעמים | סה״כ |", "|---|---|---:|---:|"]
    for u in summ["unmapped"]:
        lines.append(f"| {u['description']} | {u['direction']} | {u['count']} | {u['total']:,.0f} |")
    lines += ["", f"- ניתנות לייבוא כרגע (הוחלט במלואן): {summ['importable']} · חיובי כרטיס שממתינים לפירוט: ₪{summ['pending_card_total']:,.0f}",
              "", "> חיובי כרטיס אשראי (מקס / ישראכרט וכו׳) הם לפעמים חיוב חודשי ולפעמים משיכת מזומן שנפרעת אחרי יום–יומיים. הם **אינם נספרים כהוצאה** עד שיובא דוח הכרטיס שמפרט אותם.",
              "> זכות אינה הכנסה: גם הפקדת מזומן והעברה. הכנסה נספרת רק אחרי אישור מפורש שלך (כלל מסוג income עם שם מקור)."]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    seen = {}
    for c in items:
        if c.kind in (bi.UNKNOWN, bi.INCOME) and c.rule_id is None:
            seen.setdefault(bi.normalize(c.row.description), {"match": c.row.description, "direction": c.row.direction, "kind": "", "category": ""})
    rules_path.write_text(json.dumps(list(seen.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [csv_path, md_path, rules_path, review_path]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", type=Path, help="the bank's statement PDF")
    src.add_argument("--text", type=Path, help="text already extracted with `pdftotext -layout`")
    ap.add_argument("--account-ref", required=True, help="a label you choose for this account (NOT the account number)")
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--rules", type=Path, help="your rules JSON: [{match, kind, category?, direction?}]")
    args = ap.parse_args(argv)
    if _inside(args.outdir, REPO):
        print("refusing: --outdir is inside the repository; a statement is private data and must not be committed", file=sys.stderr)
        return 2
    source = read_parsed(args.pdf, args.account_ref) if args.pdf else args.text.read_text(encoding="utf-8")
    owner = json.loads(args.rules.read_text(encoding="utf-8")) if args.rules else None
    parsed, items, summ = report(source, args.account_ref, owner)
    for p in write_pack(args.outdir, parsed, items, summ):
        print(p)
    print(f"rows={parsed.summary.get('rows', 0)} ok={parsed.ok} unmapped={summ['unmapped_total']}")
    return 0 if parsed.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
