# core/learning_engine.py — F02 Learning Engine
# תלוי ב: C12 Lead Events (core/lead_events.py) + כמה חודשי דאטה
# flag: FEATURE_LEARNING_ENGINE (כבוי ברירת מחדל)
#
# Phase 1 — סטטיסטיקה בלבד (ללא LLM, ללא ML):
#   • conversion patterns: מה עבד (HOT→CLOSED)
#   • objection patterns:  מה לא עבד (keywords ב-COLD leads)
#   • time-to-close avg  per domain
#   • decay patterns: HOT→COLD
#
# READ-ONLY לחלוטין — לא כותב ל-Airtable.
# Phase 2 (עתידי): חיבור ל-domain_prompts → system prompt enrichment.

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Keywords לזיהוי התנגדויות ─────────────────────
_OBJECTION_KEYWORDS = [
    "יקר", "מחיר", "תקציב", "יקרה", "לא יכול",
    "לחשוב", "להתייעץ", "נחשוב", "נחזור", "בהמשך",
    "לא עכשיו", "אחר כך", "אין זמן", "לא בטוח",
    "price", "expensive", "budget",
]

# ── Keywords להצלחה ───────────────────────────────
_SUCCESS_KEYWORDS = [
    "מעוניין", "קדימה", "נסגור", "בסדר", "מצוין",
    "תשלח", "אשלח", "נקבע", "בוא נדבר", "מתי פנוי",
    "interested", "let's go", "deal",
]


# ══════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════

@dataclass
class InsightRecord:
    pattern:    str
    frequency:  int
    domain:     str
    example:    str
    confidence: float  # 0–1


@dataclass
class LearningReport:
    domain:               str
    total_events:         int = 0
    total_leads:          int = 0
    converted:            int = 0   # HOT → CLOSED
    decayed:              int = 0   # HOT → COLD
    avg_days_to_close:    float = 0.0
    top_objections:       list[tuple[str, int]] = field(default_factory=list)
    top_success_signals:  list[tuple[str, int]] = field(default_factory=list)
    conversion_rate:      float = 0.0


# ══════════════════════════════════════════════════
# 1. Load Events
# ══════════════════════════════════════════════════

def _load_events(domain: str = "") -> list[dict]:
    """
    טוען events מ-lead_events.py.
    מסנן לפי domain אם ניתן.
    """
    try:
        from core.lead_events import LeadEventStore  # type: ignore
        store  = LeadEventStore()
        events = store.get_all(domain=domain or None)
        logger.info(f"[Learning] loaded {len(events)} events (domain={domain or 'all'})")
        return events
    except ImportError:
        logger.warning("[Learning] lead_events not available — mock mode")
        return _mock_events(domain)
    except Exception as e:
        logger.error(f"[Learning] _load_events error: {e}")
        return _mock_events(domain)


def _mock_events(domain: str = "") -> list[dict]:
    """מוק לסביבת dev."""
    base = [
        {"type": "tier_change", "from": "WARM", "to": "HOT",    "domain": "real_estate", "memory_key": "w:1", "days_ago": 10},
        {"type": "tier_change", "from": "HOT",  "to": "CLOSED", "domain": "real_estate", "memory_key": "w:1", "days_ago": 5},
        {"type": "message",     "content": "אשמח לשמוע עוד פרטים",   "domain": "real_estate", "memory_key": "w:1"},
        {"type": "tier_change", "from": "WARM", "to": "HOT",    "domain": "real_estate", "memory_key": "w:2", "days_ago": 20},
        {"type": "tier_change", "from": "HOT",  "to": "COLD",   "domain": "real_estate", "memory_key": "w:2", "days_ago": 15},
        {"type": "message",     "content": "יקר לי מדי",             "domain": "real_estate", "memory_key": "w:2"},
        {"type": "message",     "content": "צריך לחשוב על זה",       "domain": "real_estate", "memory_key": "w:2"},
        {"type": "tier_change", "from": "WARM", "to": "HOT",    "domain": "import",      "memory_key": "t:1", "days_ago": 8},
        {"type": "tier_change", "from": "HOT",  "to": "CLOSED", "domain": "import",      "memory_key": "t:1", "days_ago": 3},
        {"type": "message",     "content": "בוא נסגור את העסקה",     "domain": "import",      "memory_key": "t:1"},
        {"type": "message",     "content": "מה המחיר הסופי?",        "domain": "import",      "memory_key": "w:3"},
        {"type": "tier_change", "from": "WARM", "to": "COLD",   "domain": "import",      "memory_key": "w:3", "days_ago": 12},
    ]
    if domain:
        return [e for e in base if e.get("domain") == domain]
    return base


# ══════════════════════════════════════════════════
# 2. Analyze Conversion Patterns
# ══════════════════════════════════════════════════

def analyze_conversion_patterns(domain: str = "") -> list[InsightRecord]:
    """מה עבד — מנתח HOT → CLOSED transitions."""
    events  = _load_events(domain)
    records = []

    # קבץ לפי memory_key
    by_lead: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        mk = e.get("memory_key", "unknown")
        by_lead[mk].append(e)

    converted_leads    = []
    success_kw_counter = Counter()

    for mk, lead_events in by_lead.items():
        tiers = [e for e in lead_events if e.get("type") == "tier_change"]
        # בדוק אם יש WARM→HOT ואחריו HOT→CLOSED
        reached_hot    = any(e.get("to") == "HOT" for e in tiers)
        reached_closed = any(e.get("to") == "CLOSED" for e in tiers)

        if reached_hot and reached_closed:
            converted_leads.append(mk)
            # ספור keywords של הצלחה בהודעות
            for e in lead_events:
                if e.get("type") == "message":
                    content = e.get("content", "").lower()
                    for kw in _SUCCESS_KEYWORDS:
                        if kw in content:
                            success_kw_counter[kw] += 1

    if converted_leads:
        total_leads = len(by_lead)
        conv_rate   = len(converted_leads) / total_leads if total_leads else 0
        top_signals = success_kw_counter.most_common(3)
        ex_signal   = top_signals[0][0] if top_signals else "—"

        records.append(InsightRecord(
            pattern    = "HOT_to_CLOSED",
            frequency  = len(converted_leads),
            domain     = domain or "all",
            example    = f"אות הצלחה: '{ex_signal}'",
            confidence = min(conv_rate + 0.3, 1.0),
        ))

        if top_signals:
            records.append(InsightRecord(
                pattern    = "success_signals",
                frequency  = sum(c for _, c in top_signals),
                domain     = domain or "all",
                example    = ", ".join(f"'{kw}'" for kw, _ in top_signals),
                confidence = 0.7,
            ))

    return records


# ══════════════════════════════════════════════════
# 3. Analyze Objection Patterns
# ══════════════════════════════════════════════════

def analyze_objection_patterns(domain: str = "") -> list[InsightRecord]:
    """מה לא עבד — keywords של COLD leads."""
    events = _load_events(domain)

    by_lead: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_lead[e.get("memory_key", "unknown")].append(e)

    objection_counter = Counter()
    cold_leads = []

    for mk, lead_events in by_lead.items():
        tiers      = [e for e in lead_events if e.get("type") == "tier_change"]
        ended_cold = any(e.get("to") == "COLD" for e in tiers)

        if ended_cold:
            cold_leads.append(mk)
            for e in lead_events:
                if e.get("type") == "message":
                    content = e.get("content", "").lower()
                    for kw in _OBJECTION_KEYWORDS:
                        if kw in content:
                            objection_counter[kw] += 1

    records = []
    top_objections = objection_counter.most_common(5)

    for kw, count in top_objections:
        records.append(InsightRecord(
            pattern    = f"objection_{kw}",
            frequency  = count,
            domain     = domain or "all",
            example    = f"לידים שאמרו '{kw}' — רובם הגיעו ל-COLD",
            confidence = min(count * 0.15, 0.9),
        ))

    return records


# ══════════════════════════════════════════════════
# 4. Time-to-Close Analysis
# ══════════════════════════════════════════════════

def _avg_days_to_close(events: list[dict]) -> float:
    """ממוצע ימים מ-HOT ל-CLOSED."""
    by_lead: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_lead[e.get("memory_key", "?")].append(e)

    durations = []
    for mk, lead_events in by_lead.items():
        tiers = [e for e in lead_events if e.get("type") == "tier_change"]
        hot_day    = next((e.get("days_ago", 0) for e in tiers if e.get("to") == "HOT"),    None)
        closed_day = next((e.get("days_ago", 0) for e in tiers if e.get("to") == "CLOSED"), None)
        if hot_day is not None and closed_day is not None and hot_day > closed_day:
            durations.append(hot_day - closed_day)

    return sum(durations) / len(durations) if durations else 0.0


# ══════════════════════════════════════════════════
# 5. Domain Insights (Display String)
# ══════════════════════════════════════════════════

def get_domain_insights(domain: str = "") -> str:
    """String מוכן להצגה — לowner דרך טלגרם."""
    label = f" [{domain}]" if domain else ""
    lines = [f"🧠 *Learning Engine Insights{label}*\n"]

    conv  = analyze_conversion_patterns(domain)
    obj   = analyze_objection_patterns(domain)
    events = _load_events(domain)

    # Conversion
    if conv:
        for ins in conv:
            if ins.pattern == "HOT_to_CLOSED":
                lines.append(f"✅ *המרות:* {ins.frequency} עסקאות נסגרו")
            elif ins.pattern == "success_signals":
                lines.append(f"🎯 *אותות הצלחה:* {ins.example}")
    else:
        lines.append("✅ *המרות:* אין מספיק דאטה עדיין")

    # Avg close time
    avg = _avg_days_to_close(events)
    if avg > 0:
        lines.append(f"⏱ *זמן סגירה ממוצע:* {avg:.1f} ימים מ-HOT")

    # Objections
    if obj:
        lines.append("\n⚠️ *התנגדויות נפוצות:*")
        for ins in obj[:3]:
            kw = ins.pattern.replace("objection_", "")
            lines.append(f"  • '{kw}' — {ins.frequency} פעמים (COLD leads)")
    else:
        lines.append("⚠️ *התנגדויות:* אין מספיק דאטה")

    lines.append(f"\n_מבוסס על {len(events)} events_")
    return "\n".join(lines)


# ══════════════════════════════════════════════════
# 6. Main Entry — run_learning_cycle()
# ══════════════════════════════════════════════════

def run_learning_cycle(domains: Optional[list[str]] = None) -> dict:
    """
    Entry point לscheduler (פעם בשבוע).
    מחזיר dict עם insights לכל domain.
    READ-ONLY — לא כותב לAirtable.
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("LEARNING_ENGINE"):
            logger.info("[Learning] LEARNING_ENGINE flag is OFF — skipping")
            return {}
    except ImportError:
        logger.warning("[Learning] feature_flags not available — dev mode")

    domains = domains or ["real_estate", "import", ""]
    report  = {}

    for domain in domains:
        try:
            label = domain or "all"
            conv  = analyze_conversion_patterns(domain)
            obj   = analyze_objection_patterns(domain)
            events = _load_events(domain)
            avg   = _avg_days_to_close(events)

            report[label] = {
                "total_events":        len(events),
                "conversions":         next((i.frequency for i in conv if i.pattern == "HOT_to_CLOSED"), 0),
                "top_objections":      [(i.pattern.replace("objection_",""), i.frequency) for i in obj[:3]],
                "avg_days_to_close":   round(avg, 1),
                "success_signals":     next((i.example for i in conv if i.pattern == "success_signals"), ""),
            }
            logger.info(f"[Learning] {label}: {report[label]}")

        except Exception as e:
            logger.error(f"[Learning] cycle error for domain={domain}: {e}")
            report[domain or "all"] = {"error": str(e)}

    return report


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    import sys, types
    passed = failed = 0

    def chk(desc: str, cond: bool):
        nonlocal passed, failed
        if cond:
            print(f"✅ {desc}")
            passed += 1
        else:
            print(f"❌ {desc}")
            failed += 1

    # ── mock events loaded ────────────────────────
    events = _mock_events()
    chk("mock events not empty",          len(events) > 0)
    chk("mock events has real_estate",     any(e.get("domain") == "real_estate" for e in events))
    chk("mock events has import",         any(e.get("domain") == "import" for e in events))

    # ── analyze_conversion_patterns ──────────────
    conv = analyze_conversion_patterns("real_estate")
    chk("conversion patterns list",       isinstance(conv, list))
    chk("found HOT_to_CLOSED pattern",    any(i.pattern == "HOT_to_CLOSED" for i in conv))
    hot_closed = next((i for i in conv if i.pattern == "HOT_to_CLOSED"), None)
    chk("conversion frequency >= 1",      hot_closed is not None and hot_closed.frequency >= 1)

    # ── analyze_objection_patterns ────────────────
    obj = analyze_objection_patterns("real_estate")
    chk("objection patterns list",        isinstance(obj, list))
    chk("found at least 1 objection",     len(obj) >= 1)
    keywords = [i.pattern.replace("objection_","") for i in obj]
    chk("'יקר' or 'חשוב' in objections", any(k in keywords for k in ["יקר","לחשוב","חשוב"]))

    # ── avg_days_to_close ─────────────────────────
    events_all = _mock_events()
    avg = _avg_days_to_close(events_all)
    chk("avg_days_to_close >= 0",         avg >= 0)
    chk("avg_days_to_close is float",     isinstance(avg, float))

    # ── get_domain_insights ───────────────────────
    ins = get_domain_insights("real_estate")
    chk("insights string not empty",      len(ins) > 20)
    chk("insights has 🧠",               "🧠" in ins)
    chk("insights has המרות section",     "המרות" in ins)
    chk("insights has התנגדויות section", "התנגדויות" in ins)

    ins2 = get_domain_insights("import")
    chk("import insights not empty",      len(ins2) > 20)

    # ── run_learning_cycle — flag OFF ─────────────
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff

    import importlib.util
    spec = importlib.util.spec_from_file_location("learning_engine", __file__)
    le   = importlib.util.module_from_spec(spec)
    sys.modules["learning_engine"] = le  # Python 3.11: dataclasses require module in sys.modules
    spec.loader.exec_module(le)

    result = le.run_learning_cycle()
    chk("flag=OFF → empty dict", result == {})

    # flag ON
    ff.is_enabled = lambda x: True
    result2 = le.run_learning_cycle(["real_estate", "import"])
    chk("flag=ON → dict with domains", isinstance(result2, dict) and len(result2) > 0)
    chk("result has 'real_estate' key",  "real_estate" in result2)
    chk("result has 'import' key",      "import" in result2)
    chk("real_estate has total_events",  "total_events" in result2.get("real_estate", {}))

    print(f"\n{'='*40}")
    print(f"F02 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
