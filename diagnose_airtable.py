#!/usr/bin/env python3
# diagnose_airtable.py — בדיקת חיבור Airtable מלאה
# הרץ: python diagnose_airtable.py

import os, sys, urllib.parse, requests
from dotenv import load_dotenv
from airtable_schema import Tables


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

    HEADERS = {"Authorization": f"Bearer {API_KEY}"}

    # ── 2. בדיקת תקינות המפתח ──────────────────────────────────
    print("\n[2] בדיקת תקינות API key...")
    r = requests.get("https://api.airtable.com/v0/meta/whoami", headers=HEADERS, timeout=10)
    if r.status_code == 200:
        user = r.json().get("email", r.json().get("id", "?"))
        print(f"  ✅ מפתח תקין — חשבון: {user}")
    elif r.status_code == 401:
        print(f"  ❌ 401 — המפתח לא תקין או פג תוקף")
        return 1
    else:
        print(f"  ⚠️ {r.status_code}: {r.text[:100]}")

    # ── 3. רשימת טבלאות בbase ──────────────────────────────────
    print(f"\n[3] טבלאות ב-Base {BASE_ID}:")
    r = requests.get(
        f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables",
        headers=HEADERS, timeout=10
    )
    if r.status_code == 200:
        tables = r.json().get("tables", [])
        print(f"  נמצאו {len(tables)} טבלאות:")
        for t in tables:
            print(f"  • '{t['name']}' (id: {t['id']})")
    elif r.status_code == 403:
        print(f"  ⚠️ 403 — אין הרשאת metadata (זה בסדר, ממשיכים)")
        tables = []
    else:
        print(f"  ⚠️ {r.status_code}: {r.text[:100]}")
        tables = []

    # ── 4. בדיקת כל טבלה ממפת השמות ─────────────────────────
    print("\n[4] בדיקת גישה לטבלאות CRM:")
    TABLE_NAMES = (
        Tables.CONTACTS,
        Tables.DEALS,
        Tables.PAYMENTS,
        Tables.TASKS,
    )

    for name in TABLE_NAMES:
        encoded = urllib.parse.quote(name, safe="")
        url = f"https://api.airtable.com/v0/{BASE_ID}/{encoded}"
        r = requests.get(url, headers=HEADERS, params={"maxRecords": 1}, timeout=10)
        if r.status_code == 200:
            count = len(r.json().get("records", []))
            print(f"  ✅ '{name}' — {count} רשומות")
        elif r.status_code == 404:
            print(f"  ❌ '{name}' — 404 לא נמצאה")
        elif r.status_code == 403:
            print(f"  ⚠️ '{name}' — 403 אין הרשאה לטבלה זו")
        else:
            print(f"  ❌ '{name}' — {r.status_code}: {r.text[:80]}")

    print("\n" + "=" * 60)
    print("סיום בדיקה — אם יש ❌ שלח את הפלט הזה לאיתור הבעיה")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
