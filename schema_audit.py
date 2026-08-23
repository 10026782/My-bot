#!/usr/bin/env python3
# schema_audit.py
# סקריפט עצמאי — מריץ פעם אחת:
# 1. מרענן schema_cache.json מ-Airtable Metadata API
# 2. משווה את כל הקבועים ב-airtable_schema.py לשמות השדות האמיתיים
# 3. מדפיס דוח mismatches

import os, sys, json
from pathlib import Path

# הוסף את תיקיית הפרויקט ל-path
sys.path.insert(0, str(Path(__file__).parent))

import schema_validator as sv
import airtable_schema as schema

# ══════════════════════════════════════
# טבלת מיפוי: שם טבלה → *Fields class
# ══════════════════════════════════════
TABLE_CLASS_MAP = {
    schema.Tables.LEADS:           schema.LeadFields,
    schema.Tables.TASKS:           schema.TaskFields,
    "Assets":                      schema.AssetsFields,
    schema.Tables.DEALS:           schema.DealFields,
    "Approvals":                   schema.ApprovalsFields,
    schema.Tables.INTERACTION_LOG: schema.InteractionLogFields,
    schema.Tables.PAYMENTS:        schema.PaymentFields,
    schema.Tables.CONTACTS:        schema.ContactFields,
    schema.Tables.PROJECTS:        schema.ProjectFields,
    schema.Tables.WORLDS:          schema.WorldsFields,
    schema.Tables.QUESTS:          schema.QuestsFields,
    schema.Tables.COINS_LOG:       schema.CoinsLogFields,
    schema.Tables.EMERGENCY_WINDOW: schema.EmergencyWindowFields,
    schema.Tables.MEDIA_FILES:     schema.MediaFileFields,
    schema.Tables.ACTION_CONTRACTS: schema.ActionContractsFields,
    schema.Tables.DAILY_CHECKIN:    schema.DailyCheckinFields,
    schema.Tables.EMERGENCY_STOP_FLAGS: schema.EmergencyStopFlagFields,
    schema.Tables.EXTERNAL_EXECUTION_JOBS: schema.ExternalExecutionJobFields,
    schema.Tables.LEAD_EVENTS:      schema.LeadEventFields,
    schema.Tables.MARKETING_DEMAND: schema.MarketingDemandFields,
    schema.Tables.MARKETING_PUBLICATIONS: schema.MarketingPublicationFields,
    schema.Tables.SESSIONS:          schema.SessionsFields,
    schema.Tables.BUSINESS_MEMORY:   schema.BusinessMemoryFields,
    schema.Tables.DECISION_EVENTS:   schema.DecisionEventFields,
    schema.Tables.DECISIONS:         schema.DecisionFields,
    schema.Tables.DECISION_INBOX:    schema.DecisionInboxFields,
    schema.Tables.DECISION_STAKEHOLDERS: schema.DecisionStakeholderFields,
    schema.Tables.EXPENSES:          schema.ExpenseFields,
    schema.Tables.PROFILE:           schema.ProfileFields,
    schema.Tables.ROADMAP_TASKS:     schema.RoadmapTaskFields,
    schema.Tables.VENTURES:          schema.VentureFields,
}


def _class_values(cls) -> set[str]:
    return {v for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str)}


def run_audit(live: bool = True) -> bool:
    print("=" * 60)
    print("BOSS Bot — Airtable Schema Audit")
    print("=" * 60)

    if live:
        print("\n⏳ שולף schema חי מ-Airtable...")
        try:
            tables = sv.refresh_cache()
            print(f"✅ Cache רוענן — {len(tables)} טבלאות\n")
        except Exception as e:
            print(f"⚠️  לא ניתן לשלוף schema: {e}")
            print("   ממשיך עם cache קיים (אם יש)\n")
            cache_path = Path(__file__).parent / "schema_cache.json"
            try:
                tables = json.loads(cache_path.read_text(encoding="utf-8")).get("tables", {})
            except FileNotFoundError:
                print("❌ אין cache קיים — לא ניתן להריץ audit")
                return False
    else:
        tables = json.loads((Path(__file__).parent / "schema_cache.json")
                            .read_text(encoding="utf-8")).get("tables", {})
        print(f"ℹ️  משתמש ב-cache קיים — {len(tables)} טבלאות\n")

    all_ok = True

    for table_name, fields_cls in TABLE_CLASS_MAP.items():
        schema_values = _class_values(fields_cls)
        live_fields   = set(tables.get(table_name, []))

        if not live_fields:
            print(f"❌  {table_name}: הטבלה לא קיימת ב-Airtable (live) — קוד מגדיר טבלה שלא נוצרה")
            all_ok = False
            continue

        unknown_in_schema = schema_values - live_fields    # בקוד אך לא ב-Airtable
        missing_from_code  = live_fields - schema_values   # ב-Airtable אך לא בקוד

        if not unknown_in_schema and not missing_from_code:
            print(f"✅  {table_name}: הכל תואם ({len(live_fields)} שדות)")
            continue

        all_ok = False
        print(f"❌  {table_name}:")
        if unknown_in_schema:
            print(f"    בקוד אך לא ב-Airtable (יגרמו 422):")
            for f in sorted(unknown_in_schema):
                print(f"      - '{f}'")
        if missing_from_code:
            print(f"    ב-Airtable אך לא ב-airtable_schema.py:")
            for f in sorted(missing_from_code):
                print(f"      + '{f}'")

    print("\n" + "=" * 60)
    if all_ok:
        print("✅  אין mismatches — schema מסונכרן")
    else:
        print("⚠️  נמצאו mismatches — עדכן airtable_schema.py בהתאם")
    print("=" * 60)

    return all_ok


if __name__ == "__main__":
    # --offline = השתמש ב-cache קיים ללא fetch
    live = "--offline" not in sys.argv
    sys.exit(0 if run_audit(live=live) else 1)
