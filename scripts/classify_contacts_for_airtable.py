#!/usr/bin/env python3
"""
scripts/classify_contacts_for_airtable.py
מסווג קובץ אנשי קשר בודד (vCard/CSV) לפי תפקיד עסקי (Type / Role Category),
ומכין CSV מוכן לייבוא ל-Airtable Contacts + דו"ח סיכום.

שימוש:
    python scripts/classify_contacts_for_airtable.py \
        --input contacts.vcf --outdir output/contacts/ \
        --owner "אליהו" --referred-by "אליהו"

הערה: 'Owner' ו-'Referred By' אינם שדות קיימים כיום בטבלת Contacts
(ראה ContactFields ב-airtable_schema.py) — הם נכתבים כעמודות נוספות
בפלט; יש להוסיף אותם בטבלה לפני ייבוא, או למפות/לדלג עליהם ב-import.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from contact_merge import parse_google_csv, parse_vcf, merge_contacts  # noqa: E402

# ──────────────────────────────────────────────
# סיווג לפי מילות מפתח בשם — Type + Role Category
# (ערכים תואמים ContactFields.TYPE / ContactRoleCategory ב-airtable_schema.py)
# ──────────────────────────────────────────────

_KEYWORD_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("עו\"ד", "עוה\"ד"), "Lawyer", "expert"),
    (("רו\"ח",), "Accountant", "expert"),
    (("ספק", "יבואן", "יבוא "), "Supplier", "supplier"),
    (("שותף",), "Partner", "partner"),
    (("משקיע",), "Client", "investor"),
]
_DEFAULT_TYPE = "Client"
_DEFAULT_ROLE = "lead"


def classify(name: str) -> tuple[str, str]:
    for keywords, type_, role in _KEYWORD_RULES:
        if any(kw in name for kw in keywords):
            return type_, role
    return _DEFAULT_TYPE, _DEFAULT_ROLE


AIRTABLE_FIELDS = ["שם", "טלפון", "אימייל", "חברה", "Type", "Role Category", "Owner", "Referred By"]


def write_csv(contacts: list[dict], output_path: Path, owner: str, referred_by: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=AIRTABLE_FIELDS)
        writer.writeheader()
        for c in contacts:
            type_, role = classify(c.get("name", ""))
            counts[type_] = counts.get(type_, 0) + 1
            writer.writerow({
                "שם":            c.get("name", ""),
                "טלפון":         c.get("phone", ""),
                "אימייל":        c.get("email", ""),
                "חברה":          c.get("company", ""),
                "Type":          type_,
                "Role Category": role,
                "Owner":         owner,
                "Referred By":   referred_by,
            })
    return counts


def write_report(report_path: Path, input_name: str, raw_count: int,
                  merged: list[dict], counts: dict[str, int]) -> None:
    with_phone = sum(1 for c in merged if c.get("phone"))
    lines = [
        f"קלט: {input_name}",
        f'סה"כ אנשי קשר (לפני dedup): {raw_count}',
        f"אחרי dedup לפי טלפון/שם: {len(merged)}",
        f"עם טלפון: {with_phone}",
        f"ללא טלפון: {len(merged) - with_phone}",
        "",
        "פירוט לפי Type:",
    ] + [f"  {t}: {n}" for t, n in sorted(counts.items(), key=lambda kv: -kv[1])]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="סיווג אנשי קשר לייבוא ל-Airtable Contacts")
    parser.add_argument("--input", required=True, help="קובץ CSV (Google Contacts) או VCF")
    parser.add_argument("--outdir", required=True, help="תיקיית פלט")
    parser.add_argument("--owner", required=True, help='בעל הקובץ — נכתב לעמודת "Owner" בפלט')
    parser.add_argument("--referred-by", required=True, help='נכתב לעמודת "Referred By" בפלט')
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"❌ קובץ לא נמצא: {args.input}")
        sys.exit(1)

    ext = path.suffix.lower()
    if ext == ".csv":
        parsed = parse_google_csv(path, args.owner)
    elif ext in (".vcf", ".vcard"):
        parsed = parse_vcf(path, args.owner)
    else:
        print(f"❌ סוג קובץ לא נתמך: {ext}")
        sys.exit(1)

    merged = merge_contacts(parsed)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out_csv = outdir / "contacts_classified.csv"
    counts = write_csv(merged, out_csv, args.owner, args.referred_by)

    report_path = outdir / "report.txt"
    write_report(report_path, path.name, len(parsed), merged, counts)

    print(f"✅ {len(merged)} אנשי קשר (מתוך {len(parsed)} לפני dedup) → {out_csv}")
    print(f"📄 דו\"ח: {report_path}")
    print("\n⚠️  'Owner' ו-'Referred By' אינם שדות קיימים כיום בטבלת Contacts ב-Airtable")
    print("   (ContactFields ב-airtable_schema.py) — הוסף אותם בטבלה לפני ייבוא, או דלג עליהם ב-import.")


if __name__ == "__main__":
    main()
