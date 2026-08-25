# data_engines.py — F02 + F03 + F04 Stubs
# ════════════════════════════════════════════════════════════════
# מצב: FALSE — ממתין לדאטה אמיתי
#
# מה חסר לכל אחד:
#   F02: 2-3 חודשי lead_events אמיתיים (HOT שנסגרו, התנגדויות)
#   F03: שדה campaign_source ב-Leads (utm/campaign_id)
#   F04: F02 + F03 פעילים
#
# איך מפעילים כשיש דאטה:
#   1. LEARNING_ENGINE=true
#   2. REVENUE_ATTRIBUTION=true
#   3. KPI_ENGINE=true
#   ← זהו. הקוד מוכן.
#
# מה צריך לעשות עכשיו (חד-פעמי, לפני שיש דאטה):
#   הוסף שדה "campaign_source" לטבלת Leads ב-Airtable
#   מלא אותו בכל ליד נכנס: "meta_rosh_hashana_2026", "google_apt_tlv" וכו'
# ════════════════════════════════════════════════════════════════

from __future__ import annotations
import logging
from typing import Optional

from airtable_schema import Tables
from core.query_contract import equals, negate

logger = logging.getLogger(__name__)

# ── מינימום דאטה נדרש לפני הפעלה ──────────────────
_MIN_EVENTS_FOR_LEARNING    = 50   # lead_events
_MIN_LEADS_FOR_ATTRIBUTION  = 20   # עם campaign_source מלא
_MIN_DAYS_DATA              = 30   # ימי דאטה


# ══════════════════════════════════════════════════
# F02 — Learning Engine Stub
# ══════════════════════════════════════════════════

def run_learning_cycle(domains: Optional[list] = None) -> dict:
    """
    F02: לומד מpatterns של lead_events.
    כרגע: מחזיר {} עד שיש מספיק דאטה.
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("LEARNING_ENGINE"):
            return {}
    except ImportError:
        pass

    readiness = _check_learning_readiness()
    if not readiness["ready"]:
        logger.info(f"[F02] Not ready: {readiness['reason']}")
        return {"status": "waiting", "reason": readiness["reason"]}

    # TODO: from learning_engine import run_learning_cycle as _real_cycle
    #       return _real_cycle(domains)
    return {"status": "stub — activate when data ready"}


def get_domain_insights(domain: str = "") -> str:
    """F02: insights לdomain ספציפי."""
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("LEARNING_ENGINE"):
            return ""
    except ImportError:
        pass

    readiness = _check_learning_readiness()
    if not readiness["ready"]:
        return f"🔜 Learning Engine: {readiness['reason']}"

    # TODO: from learning_engine import get_domain_insights as _real
    #       return _real(domain)
    return ""


def _check_learning_readiness() -> dict:
    """האם יש מספיק lead_events ללמידה?"""
    try:
        from tools.airtable_tools import airtable_get  # type: ignore
        raw = airtable_get("LeadEvents", "")
        count = raw.count("•") if raw else 0
        if count < _MIN_EVENTS_FOR_LEARNING:
            return {
                "ready": False,
                "reason": f"רק {count}/{_MIN_EVENTS_FOR_LEARNING} events נצברו",
                "count": count,
            }
        return {"ready": True, "count": count}
    except Exception:
        return {"ready": False, "reason": "LeadEvents לא זמין", "count": 0}


# ══════════════════════════════════════════════════
# F03 — Revenue Attribution Stub
# ══════════════════════════════════════════════════

def get_campaign_attribution(campaign_source: str = "") -> dict:
    """
    F03: קמפיין → ליד → עסקה → כסף.
    כרגע: מחזיר {} עד שיש campaign_source מלא.
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("REVENUE_ATTRIBUTION"):
            return {}
    except ImportError:
        pass

    readiness = _check_attribution_readiness()
    if not readiness["ready"]:
        logger.info(f"[F03] Not ready: {readiness['reason']}")
        return {"status": "waiting", "reason": readiness["reason"]}

    # TODO: לוגיקת attribution אמיתית
    # from tools.airtable_tools import airtable_get
    # leads = airtable_get("Leads", f"{{campaign_source}}='{campaign_source}'")
    # ... חשב ROI per campaign
    return {"status": "stub — activate when data ready"}


def get_attribution_report() -> str:
    """F03: דוח attribution — מאיזה פרסום הגיע הכסף."""
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("REVENUE_ATTRIBUTION"):
            return ""
    except ImportError:
        pass

    readiness = _check_attribution_readiness()
    if not readiness["ready"]:
        return f"🔜 Attribution: {readiness['reason']}"

    # TODO: from revenue_attribution import get_report
    return ""


def _check_attribution_readiness() -> dict:
    """האם יש לידים עם campaign_source?"""
    try:
        from tools.airtable_tools import airtable_get  # type: ignore
        raw = airtable_get("Leads", negate(equals("campaign_source", "")))
        count = raw.count("•") if raw else 0
        if count < _MIN_LEADS_FOR_ATTRIBUTION:
            return {
                "ready": False,
                "reason": (
                    f"רק {count}/{_MIN_LEADS_FOR_ATTRIBUTION} לידים "
                    f"עם campaign_source. "
                    f"הוסף שדה campaign_source לטבלת Leads."
                ),
                "count": count,
            }
        return {"ready": True, "count": count}
    except Exception:
        return {
            "ready": False,
            "reason": "הוסף שדה 'campaign_source' לטבלת Leads ב-Airtable",
            "count": 0,
        }


# ══════════════════════════════════════════════════
# F04 — KPI Engine Stub
# ══════════════════════════════════════════════════

def get_kpi_snapshot() -> dict:
    """
    F04: מצב עסק בזמן אמת.
    phase 1 (עכשיו): נתונים בסיסיים מAirtable ישירות — ללא F02/F03.
    phase 2 (אחרי F02/F03): enriched עם patterns + attribution.
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("KPI_ENGINE"):
            return {}
    except ImportError:
        pass

    snapshot = _basic_kpi()

    learning = run_learning_cycle()
    if learning and learning.get("status") != "waiting":
        snapshot["learning"] = learning

    attribution = get_attribution_report()
    if attribution:
        snapshot["attribution"] = attribution

    return snapshot


def _basic_kpi() -> dict:
    """
    KPI בסיסי מAirtable — עובד גם בלי F02/F03.
    לידים פעילים, עסקאות, תשלומים קרובים.
    """
    kpi: dict = {}
    try:
        from tools.airtable_tools import airtable_get  # type: ignore

        leads_hot  = airtable_get("Leads", equals("tier", "HOT"))
        leads_warm = airtable_get("Leads", equals("tier", "WARM"))
        kpi["leads_hot"]  = leads_hot.count("•")  if leads_hot  else 0
        kpi["leads_warm"] = leads_warm.count("•") if leads_warm else 0

        deals = airtable_get(Tables.DEALS, equals("Status", "Active"))
        kpi["deals_active"] = deals.count("•") if deals else 0

        overdue = airtable_get(Tables.PAYMENTS, equals("Status", "Overdue"))
        kpi["payments_overdue"] = overdue.count("•") if overdue else 0

        kpi["status"] = "basic"

    except Exception as e:
        kpi["error"] = str(e)

    return kpi


def get_kpi_report() -> str:
    """מחזיר KPI כstring לטלגרם."""
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("KPI_ENGINE"):
            return ""
    except ImportError:
        pass

    kpi = get_kpi_snapshot()
    if not kpi or "error" in kpi:
        return "❌ KPI לא זמין כרגע."

    lines = ["📊 *KPI — מצב עסק*\n"]
    if kpi.get("leads_hot",  0): lines.append(f"🔥 לידים HOT:  {kpi['leads_hot']}")
    if kpi.get("leads_warm", 0): lines.append(f"🟡 לידים WARM: {kpi['leads_warm']}")
    if kpi.get("deals_active",     0): lines.append(f"🤝 עסקאות פעילות: {kpi['deals_active']}")
    if kpi.get("payments_overdue", 0): lines.append(f"🚨 תשלומים באיחור: {kpi['payments_overdue']}")
    if kpi.get("attribution"): lines.append(f"\n{kpi['attribution']}")
    if kpi.get("learning"):    lines.append(f"\n🧠 Learning: פעיל")

    return "\n".join(lines) if len(lines) > 1 else "📊 KPI: אין נתונים זמינים."


# ══════════════════════════════════════════════════
# Readiness Check — לowner דרך טלגרם
# ══════════════════════════════════════════════════

def get_readiness_report() -> str:
    """
    "מה עוד חסר לפני שמפעילים F02/F03/F04?"
    קרא אחת לשבוע כדי לראות התקדמות.
    """
    lines = ["🔬 *Data Readiness Report*\n"]

    l2 = _check_learning_readiness()
    icon = "✅" if l2["ready"] else "⏳"
    lines.append(f"{icon} *F02 Learning:* {l2.get('reason', 'מוכן')}")

    l3 = _check_attribution_readiness()
    icon = "✅" if l3["ready"] else "⏳"
    lines.append(f"{icon} *F03 Attribution:* {l3.get('reason', 'מוכן')}")

    f04_ready = l2["ready"] and l3["ready"]
    icon = "✅" if f04_ready else "⏳"
    lines.append(f"{icon} *F04 KPI Full:* {'מוכן' if f04_ready else 'ממתין ל-F02+F03'}")

    lines.append("\n*לפעול עכשיו:*")
    if not l3["ready"]:
        lines.append("1️⃣ הוסף שדה `campaign_source` לטבלת Leads")
        lines.append("2️⃣ מלא אותו בכל ליד: `meta_rosh24`, `google_tlv` וכו'")
    if not l2["ready"]:
        lines.append(f"3️⃣ המשך לאסוף לידים — {l2.get('count',0)}/{_MIN_EVENTS_FOR_LEARNING} events")

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    import sys, types, importlib.util
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff

    at = types.ModuleType("airtable_tools")
    at.airtable_get = lambda t, f: "📭 אין רשומות"
    sys.modules["airtable_tools"] = at

    spec = importlib.util.spec_from_file_location("data_engines", __file__)
    de   = importlib.util.module_from_spec(spec)
    sys.modules["data_engines"] = de
    spec.loader.exec_module(de)

    # flag OFF → כולם מחזירים ריק
    chk("F02 flag=OFF → {}",   de.run_learning_cycle() == {})
    chk("F03 flag=OFF → {}",   de.get_campaign_attribution() == {})
    chk("F04 flag=OFF → {}",   de.get_kpi_snapshot() == {})
    chk("F02 insights OFF",    de.get_domain_insights() == "")
    chk("F03 report OFF",      de.get_attribution_report() == "")
    chk("F04 report OFF",      de.get_kpi_report() == "")

    # flag ON → waiting (אין דאטה)
    ff.is_enabled = lambda x: True

    r2 = de.run_learning_cycle()
    chk("F02 flag=ON → waiting", r2.get("status") == "waiting")
    chk("F02 has reason",        "reason" in r2)

    r3 = de.get_campaign_attribution()
    chk("F03 flag=ON → waiting", r3.get("status") == "waiting")
    chk("F03 reason mentions campaign_source", "campaign_source" in r3.get("reason",""))

    r4 = de.get_kpi_snapshot()
    chk("F04 returns dict",    isinstance(r4, dict))

    # readiness report
    report = de.get_readiness_report()
    chk("readiness report not empty", len(report) > 20)
    chk("readiness has F02",   "F02" in report)
    chk("readiness has F03",   "F03" in report)
    chk("readiness has action","campaign_source" in report)

    # basic KPI works without F02/F03
    kpi = de._basic_kpi()
    chk("basic_kpi returns dict", isinstance(kpi, dict))

    print(f"\n{'='*40}")
    print(f"F02/F03/F04 Stub Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
