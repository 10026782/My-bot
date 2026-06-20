#!/usr/bin/env python3
"""Classify a CSV/VCF contacts export into review-safe Airtable import files.

This script is deliberately offline: it reads one local export and writes local
CSV/XLSX/Markdown artifacts. It never connects to Airtable or any external API.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import quopri
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence
from xml.sax.saxutils import escape, quoteattr


REQUIRED_COLUMNS = [
    "Name",
    "Phone",
    "Normalized Phone",
    "Role Category",
    "Specialty",
    "Source",
    "Status",
    "Import Batch",
    "Classification Confidence",
    "Classification Reason",
    "Review Required",
    "Original Name",
    "Original Phone",
]

ALLOWED_ROLES = {
    "lead",
    "broker",
    "expert",
    "supplier",
    "operator",
    "partner",
    "investor",
    "client",
    "other",
}
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
ROLE_PRIORITY = {
    "expert": 0,
    "broker": 1,
    "investor": 2,
    "client": 3,
    "supplier": 4,
    "partner": 5,
    "operator": 6,
    "lead": 7,
    "other": 8,
}


@dataclass(frozen=True)
class Rule:
    term: str
    role: str
    specialty: str
    confidence: str = "high"
    supplier_like: bool = False
    prefix: bool = False


@dataclass
class InputRecord:
    name: str
    phone: str
    source: str
    status: str = "חדש"
    existing_role: str = ""
    existing_specialty: str = ""
    existing_confidence: str = ""
    source_index: int = 0


@dataclass
class Match:
    role: str
    specialty: str
    confidence: str
    term: str
    name: str
    supplier_like: bool


@dataclass
class ClassifiedRecord:
    values: dict[str, str]
    suspicious: bool = False
    supplier_like: bool = False
    matches: list[Match] = field(default_factory=list)


RULES = [
    # Brokers
    Rule("מתווך", "broker", "Real Estate Broker"),
    Rule("תיווך", "broker", "Real Estate Broker"),
    Rule('נדל"ן', "broker", "Real Estate Broker"),
    Rule("יועץ נדלן", "broker", "Real Estate Broker"),
    Rule("מתווכ", "broker", "Real Estate Broker", "medium"),
    Rule("מתווכ", "broker", "Real Estate Broker", "medium", prefix=True),
    Rule("נדלן", "broker", "Real Estate Broker", "medium"),
    Rule("נכסים", "broker", "Real Estate Broker", "medium"),
    # Lawyers / experts
    Rule('עו"ד', "expert", "Lawyer"),
    Rule("עורך דין", "expert", "Lawyer"),
    Rule("עורכת דין", "expert", "Lawyer"),
    Rule("משרד עורכי דין", "expert", "Lawyer"),
    Rule("עוד", "expert", "Lawyer", "medium"),
    # Buyers / clients
    Rule("רוכש", "client", "Buyer / Client"),
    Rule("קונה", "client", "Buyer / Client"),
    Rule("לקוח", "client", "Buyer / Client"),
    Rule("buyer", "client", "Buyer / Client"),
    # Investors
    Rule("משקיע", "investor", "Investor"),
    Rule("investor", "investor", "Investor"),
    Rule("השקעות", "investor", "Investor", "medium"),
    # Supplier-like experts
    Rule("שמאי", "expert", "Real Estate Appraiser", supplier_like=True),
    Rule("שמאות", "expert", "Real Estate Appraiser", supplier_like=True),
    Rule("אדריכל", "expert", "Architect", supplier_like=True),
    Rule("מהנדס", "expert", "Engineer", supplier_like=True),
    Rule("מודד", "expert", "Surveyor", supplier_like=True),
    Rule("יועץ משכנתא", "expert", "Mortgage Advisor", supplier_like=True),
    Rule("רואה חשבון", "expert", "Accountant", supplier_like=True),
    Rule('רו"ח', "expert", "Accountant", supplier_like=True),
    # Suppliers
    Rule("ספק", "supplier", "Supplier", supplier_like=True),
    Rule("קבלן", "supplier", "Contractor", supplier_like=True),
    Rule("חשמלאי", "supplier", "Electrician", supplier_like=True),
    Rule("אינסטלטור", "supplier", "Plumber", supplier_like=True),
    Rule("נגר", "supplier", "Carpenter", supplier_like=True),
    Rule("מסגר", "supplier", "Metalworker", supplier_like=True),
    Rule("אלומיניום", "supplier", "Aluminum", supplier_like=True),
    Rule("גבס", "supplier", "Drywall", supplier_like=True),
    Rule("צבעי", "supplier", "Painter", supplier_like=True),
    Rule("ריצוף", "supplier", "Flooring", supplier_like=True),
    Rule("שיש", "supplier", "Stone / Marble", supplier_like=True),
    Rule("מטבחים", "supplier", "Kitchens", supplier_like=True),
    Rule("הובלות", "supplier", "Moving", supplier_like=True),
    Rule("משלוחים", "supplier", "Delivery", supplier_like=True),
    Rule("מדידות", "supplier", "Measurements", supplier_like=True),
    Rule("ביטוח", "supplier", "Insurance", supplier_like=True),
    # Partners
    Rule("שותף", "partner", "Business Partner"),
    Rule("שותפות", "partner", "Business Partner"),
    Rule("partner", "partner", "Business Partner"),
    # Operators. Broad organization words are medium confidence by design.
    Rule("תפעול", "operator", "Operations"),
    Rule("מתקין", "operator", "Installer"),
    Rule("טכנאי", "operator", "Technician"),
    Rule("מנהל", "operator", "Manager", "medium"),
    Rule("עובד", "operator", "Employee", "medium"),
    Rule("צוות", "operator", "Team", "medium"),
]

UNCERTAIN_BUSINESS_TERMS = [
    "בעמ",
    "חברה",
    "משרד",
    "שירות",
    "שירותים",
    "עסק",
    "חנות",
    "מפעל",
    "מוסך",
    "קליניקה",
    "רופא",
    "דוקטור",
    "יועץ",
    "סוכנות",
    "תחזוקה",
]

CSV_ALIASES = {
    "name": ["Name", "Original Name", "Full Name", "שם", "שם מלא", "FN"],
    "phone": ["Phone", "Original Phone", "Normalized Phone", "טלפון", "טלפון ראשי", "TEL"],
    "role": ["Role Category", "role_category", "Role"],
    "specialty": ["Specialty", "specialty"],
    "source": ["Source", "source"],
    "status": ["Status", "סטטוס", "status"],
    "confidence": ["Classification Confidence", "confidence"],
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create review-safe Airtable contact import files from CSV or VCF.",
        epilog=(
            "Example: python scripts/classify_contacts_for_airtable.py "
            "--input contacts_airtable_import.csv --outdir output_contacts"
        ),
    )
    parser.add_argument("--input", required=True, type=Path, help="Input .csv or .vcf export")
    parser.add_argument("--outdir", required=True, type=Path, help="Output directory")
    parser.add_argument(
        "--batch",
        help="Optional Import Batch value. Default is deterministic from the input SHA-256.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse, classify, and print the summary without writing files.",
    )
    return parser.parse_args(argv)


def normalize_match_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = value.translate(
        str.maketrans({"״": '"', "“": '"', "”": '"', "׳": "'", "‘": "'", "’": "'"})
    )
    value = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", value)
    value = re.sub(r"[^\w\u0590-\u05ff\"']+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def term_matches(text: str, rule: Rule) -> bool:
    term = normalize_match_text(rule.term)
    if not term:
        return False
    if rule.prefix:
        return re.search(rf"(?<!\w){re.escape(term)}\w+", text, flags=re.UNICODE) is not None
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.UNICODE) is not None


def find_matches(name: str) -> list[Match]:
    text = normalize_match_text(name)
    found: list[Match] = []
    seen: set[tuple[str, str, str]] = set()
    for rule in RULES:
        if not term_matches(text, rule):
            continue
        key = (rule.role, rule.specialty, normalize_match_text(rule.term))
        if key in seen:
            continue
        seen.add(key)
        found.append(
            Match(
                role=rule.role,
                specialty=rule.specialty,
                confidence=rule.confidence,
                term=rule.term,
                name=name,
                supplier_like=rule.supplier_like,
            )
        )
    return found


def uncertain_business_terms(name: str) -> list[str]:
    text = normalize_match_text(name)
    return [term for term in UNCERTAIN_BUSINESS_TERMS if term_matches(text, Rule(term, "other", ""))]


def normalize_phone(phone: str) -> tuple[str, str]:
    """Return (normalized phone, issue). Preserve non-normalizable input separately."""
    raw = (phone or "").strip()
    if not raw:
        return "", "missing phone"

    extension_match = re.search(r"(?:ext\.?|extension|שלוחה|x)\s*\d+\s*$", raw, re.IGNORECASE)
    base = raw[: extension_match.start()] if extension_match else raw
    has_plus = base.lstrip().startswith("+")
    digits = re.sub(r"\D", "", base)
    if not digits:
        return "", "phone has no digits"

    if digits.startswith("00972"):
        digits = digits[2:]
        has_plus = True
    if digits.startswith("972"):
        national = digits[3:]
        if national.startswith("0"):
            national = national[1:]
        if len(national) in (8, 9):
            return f"+972{national}", ""
        return "", "invalid Israeli country-code length"

    if digits.startswith("0") and len(digits) in (9, 10):
        return f"+972{digits[1:]}", ""
    if len(digits) == 9 and digits.startswith("5"):
        return f"+972{digits}", ""
    if has_plus and 8 <= len(digits) <= 15:
        return f"+{digits}", ""
    return "", "phone could not be normalized confidently"


def read_text_with_fallback(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1255", "windows-1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode input file: {path}")


def unfold_vcard_lines(text: str) -> list[str]:
    physical = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    logical: list[str] = []
    for line in physical:
        if not logical:
            logical.append(line)
        elif logical[-1].endswith("="):
            logical[-1] = logical[-1][:-1] + line
        elif line.startswith((" ", "\t")):
            logical[-1] += line[1:]
        else:
            logical.append(line)
    return logical


def decode_vcard_value(value: str, params: dict[str, str]) -> str:
    if params.get("ENCODING", "").upper() == "QUOTED-PRINTABLE":
        charset = params.get("CHARSET", "utf-8")
        decoded = quopri.decodestring(value.encode("latin-1", errors="replace"))
        try:
            value = decoded.decode(charset)
        except (LookupError, UnicodeDecodeError):
            value = decoded.decode("utf-8", errors="replace")
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def parse_vcard_property(line: str) -> tuple[str, dict[str, str], list[str], str] | None:
    if ":" not in line:
        return None
    left, value = line.split(":", 1)
    segments = left.split(";")
    name = segments.pop(0).split(".")[-1].upper()
    params: dict[str, str] = {}
    types: list[str] = []
    for segment in segments:
        if "=" in segment:
            key, param_value = segment.split("=", 1)
            params[key.upper()] = param_value
            if key.upper() == "TYPE":
                types.extend(part.upper() for part in param_value.split(","))
        else:
            types.append(segment.upper())
    return name, params, types, decode_vcard_value(value, params)


def split_vcard_structured(value: str) -> list[str]:
    parts = re.split(r"(?<!\\);", value)
    return [part.replace("\\;", ";").strip() for part in parts]


def read_vcf(path: Path) -> tuple[list[InputRecord], int]:
    records: list[InputRecord] = []
    cards: list[list[tuple[str, dict[str, str], list[str], str]]] = []
    current: list[tuple[str, dict[str, str], list[str], str]] | None = None
    for line in unfold_vcard_lines(read_text_with_fallback(path)):
        marker = line.strip().upper()
        if marker == "BEGIN:VCARD":
            current = []
        elif marker == "END:VCARD":
            if current is not None:
                cards.append(current)
            current = None
        elif current is not None:
            prop = parse_vcard_property(line)
            if prop is not None and prop[0] not in {"PHOTO", "LOGO", "SOUND", "KEY"}:
                current.append(prop)

    for card_index, card in enumerate(cards, start=1):
        by_name: dict[str, list[tuple[dict[str, str], list[str], str]]] = defaultdict(list)
        for prop_name, params, types, value in card:
            by_name[prop_name].append((params, types, value))

        full_name = by_name.get("FN", [({}, [], "")])[0][2]
        if not full_name and by_name.get("N"):
            n_parts = split_vcard_structured(by_name["N"][0][2])
            family = n_parts[0] if len(n_parts) > 0 else ""
            given = n_parts[1] if len(n_parts) > 1 else ""
            additional = n_parts[2] if len(n_parts) > 2 else ""
            full_name = " ".join(part for part in (given, additional, family) if part)

        phones = by_name.get("TEL", [])
        preferred = [item for item in phones if "PREF" in item[1]]
        ordered = preferred + [item for item in phones if item not in preferred]
        unique_phones: list[str] = []
        seen_raw: set[str] = set()
        for _, _, phone in ordered:
            if phone not in seen_raw:
                unique_phones.append(phone)
                seen_raw.add(phone)
        if not unique_phones:
            unique_phones = [""]

        for phone in unique_phones:
            records.append(
                InputRecord(
                    name=full_name,
                    phone=phone,
                    source="VCF Export",
                    source_index=card_index,
                )
            )
    return records, len(cards)


def find_csv_value(row: dict[str, str], aliases: Iterable[str]) -> str:
    normalized = {str(key).strip().casefold(): value for key, value in row.items() if key is not None}
    for alias in aliases:
        value = normalized.get(alias.strip().casefold())
        if value is not None and str(value).strip():
            return str(value)
    return ""


def read_csv(path: Path) -> tuple[list[InputRecord], int]:
    text = read_text_with_fallback(path)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV input has no header row")

    records: list[InputRecord] = []
    for index, row in enumerate(reader, start=1):
        name = find_csv_value(row, CSV_ALIASES["name"])
        phone = find_csv_value(row, CSV_ALIASES["phone"])
        if not name and not phone:
            continue
        records.append(
            InputRecord(
                name=name,
                phone=phone,
                source=find_csv_value(row, CSV_ALIASES["source"]) or "CSV Export",
                status=find_csv_value(row, CSV_ALIASES["status"]) or "חדש",
                existing_role=find_csv_value(row, CSV_ALIASES["role"]).strip().lower(),
                existing_specialty=find_csv_value(row, CSV_ALIASES["specialty"]),
                existing_confidence=find_csv_value(row, CSV_ALIASES["confidence"]).strip().lower(),
                source_index=index,
            )
        )
    return records, len(records)


def read_input(path: Path) -> tuple[list[InputRecord], int, str]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        records, source_records = read_csv(path)
        return records, source_records, "CSV"
    if suffix in {".vcf", ".vcard"}:
        records, source_records = read_vcf(path)
        return records, source_records, "VCF"
    raise ValueError("Input must be a .csv, .vcf, or .vcard file")


def pick_match(matches: list[Match]) -> Match | None:
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda item: (
            -CONFIDENCE_RANK[item.confidence],
            ROLE_PRIORITY[item.role],
            normalize_match_text(item.term),
            normalize_match_text(item.name),
        ),
    )[0]


def classify_group(records: list[InputRecord], batch: str) -> ClassifiedRecord:
    first = records[0]
    normalized_phone, phone_issue = normalize_phone(first.phone)
    matches = [match for record in records for match in find_matches(record.name)]
    business_terms = sorted({term for record in records for term in uncertain_business_terms(record.name)})
    detected_roles = sorted({match.role for match in matches}, key=lambda role: ROLE_PRIORITY[role])
    chosen = pick_match(matches)

    existing_roles = [record.existing_role for record in records if record.existing_role in ALLOWED_ROLES]
    existing_role = existing_roles[0] if existing_roles else ""
    invalid_existing_roles = sorted(
        {record.existing_role for record in records if record.existing_role and record.existing_role not in ALLOWED_ROLES}
    )
    existing_specialty = next((record.existing_specialty for record in records if record.existing_specialty), "")
    existing_confidence = next(
        (record.existing_confidence for record in records if record.existing_confidence in CONFIDENCE_RANK), ""
    )

    role = "other"
    specialty = ""
    confidence = "low"
    reasons: list[str] = []
    review = False

    if existing_role:
        role = existing_role
        specialty = existing_specialty
        confidence = existing_confidence or "high"
        reasons.append(f"Preserved existing classification '{existing_role}'.")
        if chosen and chosen.role != existing_role:
            if chosen.confidence == "high" and len(detected_roles) == 1:
                role = chosen.role
                specialty = chosen.specialty
                confidence = "high"
                review = True
                reasons.append(
                    f"High-confidence keyword '{chosen.term}' in '{chosen.name}' changed "
                    f"existing role '{existing_role}' to '{chosen.role}'; manual confirmation required."
                )
            else:
                review = True
                reasons.append(
                    f"Detected '{chosen.term}' -> {chosen.role} ({chosen.confidence}) but retained "
                    f"existing role '{existing_role}'."
                )
        elif chosen:
            confidence = max(confidence, chosen.confidence, key=lambda item: CONFIDENCE_RANK[item])
            specialty = specialty or chosen.specialty
            reasons.append(f"Keyword '{chosen.term}' supports existing role '{existing_role}'.")
    elif chosen:
        role = chosen.role
        specialty = chosen.specialty
        confidence = chosen.confidence
        reasons.append(
            f"Matched {'exact' if chosen.confidence == 'high' else 'partial/ambiguous'} "
            f"keyword '{chosen.term}' in '{chosen.name}' -> {chosen.role}."
        )
    else:
        reasons.append("No reliable role keyword found; defaulted to other.")

    if len(detected_roles) > 1:
        review = True
        details = ", ".join(
            f"{match.role}:'{match.term}'" for match in sorted(matches, key=lambda item: (item.role, item.term))
        )
        reasons.append(f"Multiple roles detected ({details}).")

    if len(set(existing_roles)) > 1:
        review = True
        reasons.append(
            f"Conflicting existing classifications across duplicates: {', '.join(sorted(set(existing_roles)))}."
        )
    if invalid_existing_roles:
        review = True
        reasons.append(
            "Unsupported existing classification value(s) require manual mapping: "
            f"{', '.join(invalid_existing_roles)}."
        )

    supplier_like = any(match.supplier_like for match in matches)
    if supplier_like:
        review = True
        reasons.append("Supplier-like/professional contact requires manual supplier confirmation.")
    if confidence == "medium" and role != "other":
        review = True
        reasons.append("Medium-confidence non-other classification requires review.")
    if business_terms and not matches:
        review = True
        reasons.append(f"Uncertain business/profession terms detected: {', '.join(business_terms)}.")
    if phone_issue:
        review = True
        reasons.append(f"Phone review required: {phone_issue}.")

    unique_names = list(dict.fromkeys(record.name for record in records if record.name))
    if len(records) > 1:
        extra_names = [name for name in unique_names if name != first.name]
        detail = f" Extra names: {' | '.join(extra_names)}." if extra_names else ""
        role_evidence = sorted(
            {
                f"{match.name}: {match.term}->{match.role}"
                for match in matches
                if match.name != first.name
            }
        )
        if role_evidence:
            detail += f" Duplicate role evidence: {' | '.join(role_evidence)}."
        reasons.append(f"Merged {len(records) - 1} duplicate row(s) by Normalized Phone.{detail}")

    values = {
        "Name": first.name,
        "Phone": first.phone,
        "Normalized Phone": normalized_phone,
        "Role Category": role,
        "Specialty": specialty,
        "Source": first.source,
        "Status": first.status,
        "Import Batch": batch,
        "Classification Confidence": confidence,
        "Classification Reason": " ".join(reasons),
        "Review Required": "true" if review else "false",
        "Original Name": first.name,
        "Original Phone": first.phone,
    }
    return ClassifiedRecord(
        values=values,
        suspicious=bool(business_terms or len(detected_roles) > 1 or phone_issue),
        supplier_like=supplier_like,
        matches=matches,
    )


def deduplicate_and_classify(
    records: list[InputRecord], batch: str
) -> tuple[list[ClassifiedRecord], list[dict[str, str]]]:
    groups: list[list[InputRecord]] = []
    by_phone: dict[str, list[InputRecord]] = {}
    for record in records:
        normalized, _ = normalize_phone(record.phone)
        if normalized:
            if normalized not in by_phone:
                by_phone[normalized] = []
                groups.append(by_phone[normalized])
            by_phone[normalized].append(record)
        else:
            groups.append([record])

    classified = [classify_group(group, batch) for group in groups]
    duplicates: list[dict[str, str]] = []
    for group in groups:
        if len(group) <= 1:
            continue
        normalized, _ = normalize_phone(group[0].phone)
        kept = group[0]
        for duplicate in group[1:]:
            duplicate_classified = classify_group([duplicate], batch).values
            duplicates.append(
                {
                    **duplicate_classified,
                    "Duplicate Group Phone": normalized,
                    "Duplicate Of Name": kept.name,
                    "Duplicate Source Row": str(duplicate.source_index),
                }
            )
    return classified, duplicates


def suspicious_names(classified: list[ClassifiedRecord]) -> list[dict[str, str]]:
    candidates = [
        item.values
        for item in classified
        if item.values["Review Required"] == "true" or item.suspicious
    ]
    return sorted(
        candidates,
        key=lambda row: (
            -sum(
                marker in row["Classification Reason"]
                for marker in (
                    "Multiple roles detected",
                    "Phone review required",
                    "Medium-confidence",
                    "Uncertain business/profession",
                    "Conflicting existing classifications",
                    "Unsupported existing classification",
                )
            ),
            -len(row["Classification Reason"]),
            normalize_match_text(row["Original Name"]),
            row["Original Phone"],
        ),
    )[:30]


def build_summary(
    *,
    input_path: Path,
    source_type: str,
    source_records: int,
    input_rows: int,
    classified: list[ClassifiedRecord],
    duplicates: list[dict[str, str]],
    batch: str,
) -> dict[str, object]:
    rows = [item.values for item in classified]
    role_counts = Counter(row["Role Category"] for row in rows)
    confidence_counts = Counter(row["Classification Confidence"] for row in rows)
    review_count = sum(row["Review Required"] == "true" for row in rows)
    supplier_count = sum(item.supplier_like for item in classified)
    ready_count = len(rows) - review_count
    return {
        "input_path": str(input_path.resolve()),
        "source_type": source_type,
        "source_records": source_records,
        "total_input_rows": input_rows,
        "total_unique_contacts": len(rows),
        "duplicates_skipped": len(duplicates),
        "import_ready_count": ready_count,
        "review_required_count": review_count,
        "supplier_review_count": supplier_count,
        "role_counts": {role: role_counts.get(role, 0) for role in sorted(ALLOWED_ROLES)},
        "confidence_counts": {
            confidence: confidence_counts.get(confidence, 0) for confidence in ("high", "medium", "low")
        },
        "import_batch": batch,
        "suspicious_names": suspicious_names(classified),
    }


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def excel_column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def sheet_xml(rows: list[dict[str, object]], columns: list[str], rtl: bool = True) -> str:
    all_rows = [{column: column for column in columns}, *rows]
    widths = []
    for column in columns:
        values = [str(row.get(column, "")) for row in all_rows]
        longest = max((max((len(part) for part in value.splitlines()), default=0) for value in values), default=0)
        widths.append(min(max(longest + 2, 10), 55))
    col_xml = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    row_parts = []
    for row_index, row in enumerate(all_rows, start=1):
        cell_parts = []
        for column_index, column in enumerate(columns, start=1):
            ref = f"{excel_column_name(column_index)}{row_index}"
            value = str(row.get(column, ""))[:32767]
            style = 1 if row_index == 1 else 2
            cell_parts.append(
                f'<c r="{ref}" t="inlineStr" s="{style}"><is><t xml:space="preserve">'
                f"{escape(value)}"
                "</t></is></c>"
            )
        height = ' ht="24" customHeight="1"' if row_index == 1 else ""
        row_parts.append(f'<row r="{row_index}"{height}>{"".join(cell_parts)}</row>')
    last_cell = f"{excel_column_name(len(columns))}{max(len(all_rows), 1)}"
    right_to_left = ' rightToLeft="1"' if rtl else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetViews><sheetView workbookViewId="0"{right_to_left}>'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        "</sheetView></sheetViews>"
        '<sheetFormatPr defaultRowHeight="18"/>'
        f"<cols>{col_xml}</cols>"
        f'<sheetData>{"".join(row_parts)}</sheetData>'
        f'<autoFilter ref="A1:{last_cell}"/>'
        "</worksheet>"
    )


def zip_write_deterministic(archive: zipfile.ZipFile, name: str, content: str) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, content.encode("utf-8"))


def write_xlsx(path: Path, sheets: list[tuple[str, list[dict[str, object]], list[str]]]) -> None:
    content_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    workbook_sheets = "".join(
        f'<sheet name={quoteattr(title)} sheetId="{index}" r:id="rId{index}"/>'
        for index, (title, _, _) in enumerate(sheets, start=1)
    )
    workbook_rels = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    styles_rid = len(sheets) + 1
    workbook_rels += (
        f'<Relationship Id="rId{styles_rid}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )

    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            f"{content_overrides}"
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{workbook_sheets}</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{workbook_rels}</Relationships>"
        ),
        "xl/styles.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Arial"/></font>'
            '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Arial"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/>'
            '<bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
            '<border><left style="thin"><color rgb="FFD9E2F3"/></left>'
            '<right style="thin"><color rgb="FFD9E2F3"/></right>'
            '<top style="thin"><color rgb="FFD9E2F3"/></top>'
            '<bottom style="thin"><color rgb="FFD9E2F3"/></bottom><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="49" fontId="1" fillId="2" borderId="1" xfId="0" applyAlignment="1">'
            '<alignment horizontal="right" vertical="center"/></xf>'
            '<xf numFmtId="49" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1">'
            '<alignment horizontal="right" vertical="top" wrapText="1"/></xf></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            "</styleSheet>"
        ),
    }
    for index, (_, rows, columns) in enumerate(sheets, start=1):
        files[f"xl/worksheets/sheet{index}.xml"] = sheet_xml(rows, columns)

    with zipfile.ZipFile(path, "w") as archive:
        for name in sorted(files):
            zip_write_deterministic(archive, name, files[name])


def summary_sheet_rows(summary: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {"Metric": "Input path", "Value": summary["input_path"]},
        {"Metric": "Source type", "Value": summary["source_type"]},
        {"Metric": "Source records", "Value": summary["source_records"]},
        {"Metric": "Total input rows", "Value": summary["total_input_rows"]},
        {"Metric": "Total unique contacts", "Value": summary["total_unique_contacts"]},
        {"Metric": "Duplicates skipped", "Value": summary["duplicates_skipped"]},
        {"Metric": "Import ready", "Value": summary["import_ready_count"]},
        {"Metric": "Review required", "Value": summary["review_required_count"]},
        {"Metric": "Supplier review", "Value": summary["supplier_review_count"]},
        {"Metric": "Import batch", "Value": summary["import_batch"]},
    ]
    rows.extend(
        {"Metric": f"Role: {role}", "Value": count}
        for role, count in summary["role_counts"].items()
    )
    rows.extend(
        {"Metric": f"Confidence: {confidence}", "Value": count}
        for confidence, count in summary["confidence_counts"].items()
    )
    rows.append({"Metric": "Top suspicious/ambiguous names", "Value": ""})
    rows.extend(
        {
            "Metric": row["Original Name"],
            "Value": row["Classification Reason"],
        }
        for row in summary["suspicious_names"]
    )
    return rows


def markdown_summary(summary: dict[str, object]) -> str:
    role_lines = "\n".join(f"| `{role}` | {count} |" for role, count in summary["role_counts"].items())
    confidence_lines = "\n".join(
        f"| `{confidence}` | {count} |" for confidence, count in summary["confidence_counts"].items()
    )
    suspicious = summary["suspicious_names"]
    suspicious_lines = "\n".join(
        f"{index}. **{row['Original Name'] or '(blank name)'}** "
        f"(`{row['Original Phone'] or 'no phone'}`): {row['Classification Reason']}"
        for index, row in enumerate(suspicious, start=1)
    ) or "No suspicious or ambiguous names were found."
    return f"""# Contacts Classification Summary

## Run Summary

- Input: `{summary['input_path']}`
- Source format: {summary['source_type']}
- Source records: {summary['source_records']}
- Total input rows: {summary['total_input_rows']}
- Total unique contacts: {summary['total_unique_contacts']}
- Duplicates skipped: {summary['duplicates_skipped']}
- Import-ready contacts: {summary['import_ready_count']}
- Contacts requiring review: {summary['review_required_count']}
- Supplier review count: {summary['supplier_review_count']}
- Import batch: `{summary['import_batch']}`

## Count By Role Category

| Role Category | Count |
|---|---:|
{role_lines}

## Count By Confidence

| Confidence | Count |
|---|---:|
{confidence_lines}

## Top 30 Suspicious Or Ambiguous Names

{suspicious_lines}

## Safe Airtable Import Note

1. Do not import `contacts_review_required.csv` or `contacts_supplier_review.csv` before manual review.
2. Review every supplier-like contact and every row whose phone could not be normalized.
3. In Airtable, verify that `Role Category` contains exactly the allowed single-select values before importing.
4. Import `contacts_airtable_import_classified.csv` into a temporary/staging view first, matching columns by name.
5. Use `Normalized Phone` as the duplicate check key. Spot-check names, original phones, and classification reasons before moving records into the production Contacts workflow.

No Airtable write or external API call was performed by this script.
"""


def write_outputs(
    outdir: Path,
    classified: list[ClassifiedRecord],
    duplicates: list[dict[str, str]],
    summary: dict[str, object],
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    ready = [item.values for item in classified if item.values["Review Required"] == "false"]
    review = [item.values for item in classified if item.values["Review Required"] == "true"]
    supplier = [item.values for item in classified if item.supplier_like]

    write_csv(outdir / "contacts_airtable_import_classified.csv", ready, REQUIRED_COLUMNS)
    write_csv(outdir / "contacts_review_required.csv", review, REQUIRED_COLUMNS)
    write_csv(outdir / "contacts_supplier_review.csv", supplier, REQUIRED_COLUMNS)

    duplicate_columns = REQUIRED_COLUMNS + [
        "Duplicate Group Phone",
        "Duplicate Of Name",
        "Duplicate Source Row",
    ]
    sheets = [
        ("Import Ready", ready, REQUIRED_COLUMNS),
        ("Review Required", review, REQUIRED_COLUMNS),
        ("Supplier Review", supplier, REQUIRED_COLUMNS),
        ("Duplicates", duplicates, duplicate_columns),
        ("Summary", summary_sheet_rows(summary), ["Metric", "Value"]),
    ]
    write_xlsx(outdir / "contacts_airtable_import_classified.xlsx", sheets)
    (outdir / "contacts_classification_summary.md").write_text(
        markdown_summary(summary), encoding="utf-8", newline="\n"
    )


def deterministic_batch(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"contacts-{digest}"


def run(args: argparse.Namespace) -> dict[str, object]:
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    records, source_records, source_type = read_input(input_path)
    if not records:
        raise ValueError("Input contains no usable contact rows")
    batch = args.batch or deterministic_batch(input_path)
    classified, duplicates = deduplicate_and_classify(records, batch)
    summary = build_summary(
        input_path=input_path,
        source_type=source_type,
        source_records=source_records,
        input_rows=len(records),
        classified=classified,
        duplicates=duplicates,
        batch=batch,
    )
    if not args.dry_run:
        write_outputs(args.outdir.expanduser().resolve(), classified, duplicates, summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    try:
        summary = run(args)
    except (OSError, ValueError, csv.Error, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("Dry run complete; no files were written.")
    else:
        print(f"Output files written to: {args.outdir.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
