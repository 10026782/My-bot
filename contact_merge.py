#!/usr/bin/env python3
"""
contact_merge.py
מיזוג אנשי קשר מכמה מקורות → CSV אחד מוכן לייבוא ל-Airtable Contacts.

שימוש:
    python contact_merge.py --files אליהו.csv אורי.vcf אהרן.csv אבי.vcf \
                             --names  "אליהו,אורי,אהרן,אבי"

פלט: contacts_merged.csv  (מוכן לייבוא ישיר ל-Airtable)

שדות פלט (תואמים Airtable Contacts):
    Name | Phone | Email | Company | Type | Notes | Owner | Status
"""

import argparse
import csv
import re
import sys
from pathlib import Path

# ──────────────────────────────────────────────
# 1. נרמול מספר טלפון ישראלי
# ──────────────────────────────────────────────

def normalize_phone(raw: str) -> str:
    """
    מחזיר מספר נורמלי בפורמט 05XXXXXXXX (10 ספרות, בלי מקפים).
    דוגמאות:
        +972-52-123-4567  → 0521234567
        972521234567      → 0521234567
        052-123-4567      → 0521234567
        52-123-4567       → 0521234567   (ללא קידומת ארץ ו-0)
    מחזיר "" אם לא ניתן לנרמל.
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)       # ספרות בלבד

    if digits.startswith("972"):
        digits = "0" + digits[3:]         # +972 → 0
    elif digits.startswith("00972"):
        digits = "0" + digits[5:]

    if len(digits) == 9 and not digits.startswith("0"):
        digits = "0" + digits             # 52... → 052...

    # קבל רק מספרים ישראלים תקינים (9–10 ספרות, מתחיל ב-0)
    if re.fullmatch(r"0\d{8,9}", digits):
        return digits
    return ""


# ──────────────────────────────────────────────
# 2. פרסור CSV של Google Contacts
# ──────────────────────────────────────────────

def _first(row: dict, *keys: str) -> str:
    for k in keys:
        if row.get(k, "").strip():
            return row[k].strip()
    return ""


def parse_google_csv(path: Path, source_name: str) -> list[dict]:
    """
    Google Contacts CSV — מחזיר רשימת dicts עם:
    name, phone, email, company, source
    """
    contacts = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = _first(row, "Name", "שם מלא")
            if not name:
                given  = _first(row, "Given Name", "שם פרטי")
                family = _first(row, "Family Name", "שם משפחה")
                name = f"{given} {family}".strip()

            # Google מייצא כמה טלפונים: "Phone 1 - Value", "Phone 2 - Value", ...
            phones = []
            for k, v in row.items():
                if ("phone" in k.lower() or "טלפון" in k.lower()) and "value" in k.lower():
                    n = normalize_phone(v)
                    if n:
                        phones.append(n)
            # קח את הראשון שמצאנו — העיקרי
            phone = phones[0] if phones else ""

            email = _first(row,
                           "E-mail 1 - Value", "Email 1 - Value",
                           "אימייל", "Email")
            company = _first(row, "Organization 1 - Name", "Company", "חברה")

            if name or phone:
                contacts.append({
                    "name": name,
                    "phone": phone,
                    "email": email.lower().strip() if email else "",
                    "company": company,
                    "source": source_name,
                })
    return contacts


# ──────────────────────────────────────────────
# 3. פרסור vCard (.vcf)
# ──────────────────────────────────────────────

def _vcard_decode(value: str, encoding: str = "") -> str:
    """מפענח QUOTED-PRINTABLE אם צריך, אחרת מחזיר as-is."""
    if encoding.upper() == "QUOTED-PRINTABLE":
        import quopri
        try:
            return quopri.decodestring(value.encode()).decode("utf-8", errors="ignore")
        except Exception:
            pass
    return value


def _unfold_vcard_lines(path: Path) -> list[str]:
    """
    vCard 2.1/3.0 line folding: שורה שמתחילה ברווח/טאב היא המשך של
    השורה הקודמת (RFC 2425) — יש לאחות אותה לפני הפרסור, אחרת תוכן
    שדות ארוכים (שם/הערות) נחתך בשקט.
    """
    logical_lines: list[str] = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.rstrip("\r\n")
            if line and line[0] in (" ", "\t") and logical_lines:
                logical_lines[-1] += line[1:]
            else:
                logical_lines.append(line)
    return logical_lines


def parse_vcf(path: Path, source_name: str) -> list[dict]:
    """
    vCard 2.1 / 3.0 — מחזיר רשימת dicts.
    תומך בקידוד QUOTED-PRINTABLE, בשמות בעברית, ובשורות מקופלות (folded).
    """
    contacts = []
    current: dict = {}

    for line in _unfold_vcard_lines(path):
        if line.upper() == "BEGIN:VCARD":
            current = {"name": "", "phone": "", "email": "", "company": "", "source": source_name}
            continue

        if line.upper() == "END:VCARD":
            if current.get("name") or current.get("phone"):
                contacts.append(current)
            current = {}
            continue

        if not current:
            continue

        # פירוק שורת vCard: KEY;PARAM=VAL:DATA
        colon_idx = line.find(":")
        if colon_idx < 0:
            continue
        key_part = line[:colon_idx]
        value    = line[colon_idx + 1:]

        # בדיקת encoding בפרמטרים
        params = key_part.upper().split(";")
        field  = params[0].split(".")[0]    # מסיר קידומת group (X.FN → FN)
        encoding = next((p.replace("ENCODING=", "") for p in params if "ENCODING=" in p), "")

        value = _vcard_decode(value, encoding)

        if field in ("FN", "N") and not current["name"]:
            if field == "N":
                # N:שם משפחה;שם פרטי;;; → שם פרטי שם משפחה
                parts = value.split(";")
                family = parts[0].strip() if parts else ""
                given  = parts[1].strip() if len(parts) > 1 else ""
                value  = f"{given} {family}".strip()
            current["name"] = value.strip()

        elif field == "TEL" and not current["phone"]:
            n = normalize_phone(value)
            if n:
                current["phone"] = n

        elif field == "EMAIL" and not current["email"]:
            current["email"] = value.lower().strip()

        elif field in ("ORG", "ORGANIZATION") and not current["company"]:
            current["company"] = value.split(";")[0].strip()

    return contacts


# ──────────────────────────────────────────────
# 4. מיזוג וניקוי כפילויות
# ──────────────────────────────────────────────

def merge_contacts(all_contacts: list[dict]) -> list[dict]:
    """
    מיזוג לפי מספר טלפון מנורמל.
    - אם לאותו מספר יש כמה שמות — לוקחים את הארוך ביותר.
    - Sources מצטברים: "אליהו, אורי"
    - ללא טלפון: מיזוג לפי שם מדויק.
    """
    by_phone:  dict[str, dict] = {}
    no_phone:  dict[str, dict] = {}

    for c in all_contacts:
        phone = c.get("phone", "")
        name  = c.get("name", "").strip()

        if phone:
            if phone in by_phone:
                existing = by_phone[phone]
                # מעדיף שם ארוך יותר
                if len(name) > len(existing.get("name", "")):
                    existing["name"] = name
                # מוסיף email / company אם חסר
                if not existing.get("email") and c.get("email"):
                    existing["email"] = c["email"]
                if not existing.get("company") and c.get("company"):
                    existing["company"] = c["company"]
                # מצבר sources
                sources = set(existing.get("source", "").split(", "))
                sources.add(c.get("source", ""))
                sources.discard("")
                existing["source"] = ", ".join(sorted(sources))
            else:
                by_phone[phone] = dict(c)
        elif name:
            key = name.strip().lower()
            if key in no_phone:
                existing = no_phone[key]
                if not existing.get("email") and c.get("email"):
                    existing["email"] = c["email"]
                if not existing.get("company") and c.get("company"):
                    existing["company"] = c["company"]
                sources = set(existing.get("source", "").split(", "))
                sources.add(c.get("source", ""))
                sources.discard("")
                existing["source"] = ", ".join(sorted(sources))
            else:
                no_phone[key] = dict(c)

    return list(by_phone.values()) + list(no_phone.values())


# ──────────────────────────────────────────────
# 5. כתיבת CSV מוכן ל-Airtable
# ──────────────────────────────────────────────

AIRTABLE_FIELDS = ["Name", "Phone", "Email", "Company", "Type", "Owner", "Status", "Notes"]

def write_airtable_csv(contacts: list[dict], output_path: Path) -> None:
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=AIRTABLE_FIELDS)
        writer.writeheader()
        for c in contacts:
            writer.writerow({
                "Name":    c.get("name", ""),
                "Phone":   c.get("phone", ""),
                "Email":   c.get("email", ""),
                "Company": c.get("company", ""),
                "Type":    "Client",       # ברירת מחדל — ניתן לסנן ב-Airtable
                "Owner":   c.get("source", ""),
                "Status":  "Active",
                "Notes":   "",
            })


# ──────────────────────────────────────────────
# 6. Main
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="מיזוג אנשי קשר לייבוא ל-Airtable")
    parser.add_argument("--files", nargs="+", required=True,
                        help="נתיבי קבצים (CSV / VCF)")
    parser.add_argument("--names", required=True,
                        help='שמות הבעלים, מופרדים בפסיק: "אליהו,אורי,אהרן,אבי"')
    parser.add_argument("--output", default="contacts_merged.csv",
                        help="שם קובץ הפלט (ברירת מחדל: contacts_merged.csv)")
    args = parser.parse_args()

    names = [n.strip() for n in args.names.split(",")]
    files = args.files

    if len(names) != len(files):
        print(f"❌ מספר שמות ({len(names)}) לא תואם מספר קבצים ({len(files)})")
        sys.exit(1)

    all_contacts: list[dict] = []

    for file_path, owner_name in zip(files, names):
        path = Path(file_path)
        if not path.exists():
            print(f"⚠️  קובץ לא נמצא: {file_path} — דלג")
            continue

        ext = path.suffix.lower()
        if ext == ".csv":
            parsed = parse_google_csv(path, owner_name)
        elif ext in (".vcf", ".vcard"):
            parsed = parse_vcf(path, owner_name)
        else:
            print(f"⚠️  סוג קובץ לא נתמך: {ext} — דלג")
            continue

        print(f"✅ {owner_name}: {len(parsed)} אנשי קשר נקראו מ-{path.name}")
        all_contacts.extend(parsed)

    merged = merge_contacts(all_contacts)

    # סטטיסטיקות
    with_phone    = sum(1 for c in merged if c.get("phone"))
    without_phone = sum(1 for c in merged if not c.get("phone"))

    print(f"\n📊 סיכום:")
    print(f"   סה\"כ לפני מיזוג: {len(all_contacts)}")
    print(f"   אחרי ניקוי כפילויות: {len(merged)}")
    print(f"   עם טלפון: {with_phone}")
    print(f"   ללא טלפון (לפי שם): {without_phone}")

    output = Path(args.output)
    write_airtable_csv(merged, output)
    print(f"\n✅ נשמר: {output.resolve()}")
    print("   → ייבוא ל-Airtable: Contacts → Import → CSV")


if __name__ == "__main__":
    main()
