#!/usr/bin/env python3
# diagnose_airtable.py — בדיקת חיבור Airtable מלאה
# הרץ: python diagnose_airtable.py

import os
import sys
from dotenv import load_dotenv
from airtable_schema import Tables
from tools.airtable_gateway import AirtableLookupError, get_base_metadata, get_whoami
from tools.airtable_read_adapter import AirtableReadError, list_records


def main() -> int:
    load_dotenv()

    API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
    BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")

    print("=" * 60)
    print("AIRTABLE DIAGNOSTICS")
    print("=" * 60)

    # ── 1. בדיקת env vars ──────────────────────────────────────
    print("\n[1] Env vars:")
    print(f"  AIRTABLE_API_KEY : {'✅ מוגדר' if API_KEY else '❌ חסר'}")
    print(f"  AIRTABLE_BASE_ID : {'✅ ' + BASE_ID if BASE_ID else '❌ חסר'}")
    if not API_KEY or not BASE_ID:
        print("\n❌ חסרים env vars — עצור.")
        return 1

    # ── 2. בדיקת תקינות המפתח ──────────────────────────────────
    print("\n[2] בדיקת תקינות API key...")
    try:
        whoami = get_whoami(timeout=10)
    except AirtableLookupError as exc:
        if exc.status_code == 401:
            print("  ❌ 401 — המפתח לא תקין או פג תוקף")
            return 1
        if exc.status_code is None and exc.cause is not None:
            raise exc.cause from exc
        print(f"  ⚠️ {exc.status_code}: {exc.response_text[:100]}")
    else:
        user = whoami.get("email", whoami.get("id", "?"))
        print(f"  ✅ מפתח תקין — חשבון: {user}")

    # ── 3. רשימת טבלאות בbase ──────────────────────────────────
    print(f"\n[3] טבלאות ב-Base {BASE_ID}:")
    try:
        metadata = get_base_metadata(timeout=10)
    except AirtableLookupError as exc:
        if exc.status_code == 403:
            print("  ⚠️ 403 — אין הרשאת metadata (זה בסדר, ממשיכים)")
            tables = []
        elif exc.status_code is None and exc.cause is not None:
            raise exc.cause from exc
        else:
            print(f"  ⚠️ {exc.status_code}: {exc.response_text[:100]}")
            tables = []
    else:
        tables = metadata.get("tables", [])
        print(f"  נמצאו {len(tables)} טבלאות:")
        for t in tables:
            print(f"  • '{t['name']}' (id: {t['id']})")

    # ── 4. בדיקת כל טבלה ממפת השמות ─────────────────────────
    print("\n[4] בדיקת גישה לטבלאות CRM:")
    TABLE_NAMES = (
        Tables.CONTACTS,
        Tables.DEALS,
        Tables.PAYMENTS,
        Tables.TASKS,
    )

    for name in TABLE_NAMES:
        try:
            records = list_records(name, max_records=1, paginate=False, timeout=10)
        except AirtableReadError as exc:
            if exc.status_code == 404:
                print(f"  ❌ '{name}' — 404 לא נמצאה")
            elif exc.status_code == 403:
                print(f"  ⚠️ '{name}' — 403 אין הרשאה לטבלה זו")
            elif exc.status_code is None and exc.cause is not None:
                raise exc.cause from exc
            else:
                print(f"  ❌ '{name}' — {exc.status_code}: {exc.response_text[:80]}")
            continue
        else:
            count = len(records)
            print(f"  ✅ '{name}' — {count} רשומות")

    print("\n" + "=" * 60)
    print("סיום בדיקה — אם יש ❌ שלח את הפלט הזה לאיתור הבעיה")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
