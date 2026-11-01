#!/usr/bin/env python3
"""FCC credit-card statement report (stage 5c) — OFFLINE, read-only: parse a Max / Isracard card statement PDF, classify its lines and (optionally) match its
sections to a bank statement's card settlements.

    python3 scripts/fcc_card_statement_report.py (--xlsx card.xlsx | --pdf card.pdf) --card-ref max --outdir ~/fcc_review \
        [--bank-pdf bank.pdf | --bank-text bank.txt] [--rules my_rules.json]

Max and Isracard layouts. Needs ``pdfminer.six`` (``pip install pdfminer.six``): the card PDF stores Hebrew in visual order, which this script reverses word by word.
Writes to ``--outdir`` (which must be OUTSIDE this repository: statements are private data) charges.csv, summary.md and merchants_rules_template.json.
It touches no Airtable table and calls no model. Only the last four digits of a card are read; the holder's name is never read.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.financial_control import bank_import as bi  # noqa: E402
from core.financial_control import card_import as ci  # noqa: E402
from core.financial_control import statement_reader as sr  # noqa: E402

_HEBREW_RUN = re.compile(r'[֐-׿][֐-׿"\' ./\-]*[֐-׿]|[֐-׿]')


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def logical(text: str) -> str:
    return sr.logical(text)


def extract_fragments(pdf: Path) -> list[ci.Fragment]:
    try:
        return sr.pdf_fragments(pdf.read_bytes(), visual_hebrew=True)
    except sr.StatementError as exc:
        raise SystemExit(str(exc))


def table_rows(xlsx: Path) -> list[tuple]:
    try:
        return sr.xlsx_rows(xlsx.read_bytes())
    except sr.StatementError as exc:
        raise SystemExit(str(exc))


def bank_result(args, account_ref="bank"):
    """The bank statement for the matching: a text file (``pdftotext -layout``) or a PDF read with the same pure-Python reader the server uses."""
    if args.bank_text:
        return bi.parse_statement(args.bank_text.read_text(encoding="utf-8"), account_ref)
    if args.bank_pdf:
        try:
            return sr.read_bank(args.bank_pdf.read_bytes(), account_ref)
        except sr.StatementError as exc:
            raise SystemExit(str(exc))
    return None


def build(source, card_ref, owner_items=None, bank=None, account_ref="bank"):
    """``source``: PDF fragments (a list of ``Fragment``) or the rows of an Excel export (a list of tuples)."""
    parsed = ci.parse_card_table(source, card_ref) if source and not isinstance(source[0], ci.Fragment) else ci.parse_card_statement(source, card_ref)
    rules = bi.owner_rules_from(owner_items)
    items = ci.classify_all(parsed.charges, rules)
    summ = ci.summarize(items)
    recon = None
    if bank is not None:
        bank_parsed = bank if isinstance(bank, bi.ParseResult) else bi.parse_statement(bank, account_ref)
        bank_items = bi.classify(bank_parsed.rows, rules)
        recon = {"bank_ok": bank_parsed.ok, **ci.reconcile(bank_items, ci.match_settlements(parsed.sections, bank_items))}
    return parsed, items, summ, recon


def emit_report_pack(outdir: Path, parsed, items, summ, recon) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path, md_path, rules_path = outdir / "charges.csv", outdir / "summary.md", outdir / "merchants_rules_template.json"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "merchant", "charge", "transaction_amount", "card", "billing_date", "section", "line_type", "kind", "category", "rule", "remark", "key"])
        for c in items:
            x = c.charge
            w.writerow([x.date.isoformat(), x.merchant, f"{x.charge:.2f}", "" if x.amount is None else f"{x.amount:.2f}", x.card, x.billing_date.isoformat(),
                        x.section, x.kind, c.kind, c.category or "", c.rule_id or "", x.remark, x.key])
    lines = ["# דוח כרטיס אשראי", "", f"**{'הדוח שלם ומתיישב' if parsed.ok else 'הדוח אינו מתיישב — לא לייבא לפני בירור'}**", "",
             "## חלקי חיוב", "", "| # | כרטיס | תאריך חיוב | סה״כ בדוח | סכום השורות | שורות | מיידי | מתיישב |", "|---:|---|---|---:|---:|---:|---|---|"]
    for s in parsed.sections:
        lines.append(f"| {s.index} | {s.card} | {s.billing_date.isoformat()} | {s.total:,.2f} | {s.computed:,.2f} | {s.rows} | {'כן' if s.immediate else ''} | {'✓' if s.ok else '✗'} |")
    for p in parsed.problems:
        lines.append(f"\n- ⚠ {p}")
    lines += ["", "## לפי סוג", "", "| סוג | שורות | סכום |", "|---|---:|---:|"]
    for k, v in summ["by_kind"].items():
        if v["count"]:
            lines.append(f"| {k} | {v['count']} | {v['total']:,.2f} |")
    lines += ["", "## הוצאות לפי קטגוריה (מה שסווג)", "", "| קטגוריה | סכום |", "|---|---:|"]
    lines += [f"| {k} | {v:,.2f} |" for k, v in summ["by_category"].items()]
    if recon is not None:
        lines += ["", "## התאמה לדוח הבנק", "", f"- חיובי הבנק שנפתרו מול הדוח הזה: {len(recon['matched'])} (₪{recon['matched_total']:,.2f}) — הם כבר לא נספרים כהוצאה, השורות שלהם במקומם",
                  f"- חלקי חיוב שלא נמצאו בבנק: {len(recon['sections_without_bank_line'])}",
                  f"- חיובי כרטיס בבנק שהדוח הזה לא מכסה: {recon['uncovered_bank_settlements']['count']} (₪{recon['uncovered_bank_settlements']['total']:,.2f}) — אינם נספרים כהוצאה עד שייובא הדוח שמפרט אותם"]
    lines += ["", f"## בתי עסק שעדיין לא ממופים ({summ['unmapped_total']})", "", "| בית עסק | פעמים | סה״כ |", "|---|---:|---:|"]
    lines += [f"| {u['merchant']} | {u['count']} | {u['total']:,.2f} |" for u in summ["unmapped"]]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    seen = {}
    for c in items:
        if c.kind == ci.UNKNOWN:
            seen.setdefault(bi.normalize(c.charge.merchant), {"match": c.charge.merchant, "kind": "", "category": ""})
    rules_path.write_text(json.dumps(list(seen.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [csv_path, md_path, rules_path]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", type=Path, help="the card statement PDF (Max / Isracard)")
    src.add_argument("--xlsx", type=Path, help="the card statement's Excel export (preferred: exact and issuer-independent)")
    ap.add_argument("--card-ref", required=True, help="a label you choose for this card (NOT the card number)")
    ap.add_argument("--outdir", required=True, type=Path)
    bank = ap.add_mutually_exclusive_group()
    bank.add_argument("--bank-pdf", type=Path)
    bank.add_argument("--bank-text", type=Path)
    ap.add_argument("--rules", type=Path, help="your rules JSON: [{match, kind, category?}]")
    args = ap.parse_args(argv)
    if _inside(args.outdir, REPO):
        print("refusing: --outdir is inside the repository; a statement is private data and must not be committed", file=sys.stderr)
        return 2
    owner = json.loads(args.rules.read_text(encoding="utf-8")) if args.rules else None
    parsed, items, summ, recon = build((table_rows(args.xlsx) if args.xlsx else extract_fragments(args.pdf)), args.card_ref, owner, bank_result(args))
    for p in emit_report_pack(args.outdir, parsed, items, summ, recon):
        print(p)
    print(f"charges={len(parsed.charges)} sections={len(parsed.sections)} ok={parsed.ok} unmapped={summ['unmapped_total']}")
    return 0 if parsed.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
