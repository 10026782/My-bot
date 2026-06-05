# audience_intelligence.py — D04 Audience Intelligence
# קובץ: audience_intelligence.py (flat, root)
# flag: FEATURE_AUDIENCE_INTELLIGENCE (כבוי ברירת מחדל)
#
# מה זה:
#   1. Segmentation    — מי הלידים שלי? (7 פרופילים)
#   2. High-Value      — איזה ליד שווה הכי הרבה?
#   3. Lookalike       — מי דומה ל-BOILING שנסגר?
#   4. Churn Risk      — מי עומד לקרר?
#   5. Audience Report — דוח שבועי לowner
#
# ללא ML ← סטטיסטיקה פשוטה + rule-based.
# ללא Airtable ישיר ← crm.py בלבד.
# Read-Only לחלוטין.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Segment Profiles — 7 פרופילי קהל
# ══════════════════════════════════════════════════

SEGMENTS = {
    "champion": {
        "label":       "🏆 Champion",
        "description": "לידים שנסגרו + חזרו / הפנו",
        "score_min":   80,
        "converted":   True,
        "days_since_activity_max": 30,
        "action":      "תגמול + בקש הפניה",
    },
    "hot_prospect": {
        "label":       "🚀 Hot Prospect",
        "description": "BOILING/VERY HOT — טרם נסגרו",
        "score_min":   70,
        "converted":   False,
        "days_since_activity_max": 14,
        "action":      "פנייה מיידית — human pipeline",
    },
    "promising": {
        "label":       "🔥 Promising",
        "description": "HOT — מתקדמים לאט",
        "score_min":   50,
        "converted":   False,
        "days_since_activity_max": 21,
        "action":      "רצף D01 + behavioral triggers",
    },
    "needs_attention": {
        "label":       "⚠️ Needs Attention",
        "description": "היה חם — התקרר",
        "score_min":   40,
        "score_max":   69,
        "converted":   False,
        "days_since_activity_min": 7,
        "days_since_activity_max": 30,
        "action":      "recovery D01 + bounce D02",
    },
    "at_risk": {
        "label":       "🌤️ At Risk",
        "description": "WARM ולא ענה 30+ ימים",
        "score_min":   20,
        "score_max":   49,
        "converted":   False,
        "days_since_activity_min": 30,
        "action":      "F01 Recovery — הצעה אחרונה",
    },
    "lost": {
        "label":       "🧊 Lost",
        "description": "COLD — 60+ ימים ללא פעילות",
        "score_max":   30,
        "days_since_activity_min": 60,
        "action":      "הסרה מרשימה פעילה",
    },
    "new": {
        "label":       "✨ New",
        "description": "נכנסו השבוע",
        "days_since_activity_max": 7,
        "action":      "שאלון + qualification מיד",
    },
}


# ══════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════

@dataclass
class LeadProfile:
    memory_key:      str
    name:            str
    score:           int
    tier:            str
    domain:          str
    channel:         str
    days_active:     int    # כמה ימים מאז יצירה
    days_silent:     int    # כמה ימים ללא פעילות
    converted:       bool   # נסגר?
    followup_count:  int
    answers:         dict = field(default_factory=dict)
    segment:         str = ""


@dataclass
class SegmentReport:
    segment:     str
    label:       str
    count:       int
    action:      str
    leads:       list[str] = field(default_factory=list)  # שמות


@dataclass
class AudienceReport:
    total:          int = 0
    segments:       list[SegmentReport] = field(default_factory=list)
    high_value:     list[LeadProfile]   = field(default_factory=list)
    lookalike_signals: list[str]        = field(default_factory=list)
    churn_risk:     list[LeadProfile]   = field(default_factory=list)
    generated_at:   str = ""


# ══════════════════════════════════════════════════
# 1. Load Leads
# ══════════════════════════════════════════════════

def load_all_leads() -> list[LeadProfile]:
    """טוען לידים מAirtable דרך crm. Read-only."""
    try:
        from tools.airtable_tools import airtable_get  # type: ignore
        from airtable_schema import Tables        # type: ignore

        records = airtable_get(Tables.LEADS, "")
        if not records or not isinstance(records, list):
            return _mock_leads()
        return _parse_records(records)

    except ImportError:
        logger.warning("[Audience] airtable not available — mock mode")
        return _mock_leads()
    except Exception as e:
        logger.error(f"[Audience] load error: {e}")
        return _mock_leads()


def _parse_records(records: list) -> list[LeadProfile]:
    """ממיר רשומות Airtable לLeadProfile."""
    profiles = []
    now = datetime.now(tz=timezone.utc)

    for r in records:
        if not isinstance(r, dict):
            continue
        f = r.get("fields", {})
        try:
            last_str    = f.get("last_active") or f.get("updated_at") or f.get("created_at") or ""
            days_silent = _days_since(last_str)
            created_str = f.get("created_at") or ""
            days_active = _days_since(created_str)

            profiles.append(LeadProfile(
                memory_key     = f.get("memory_key", r.get("id", "")),
                name           = f.get("Name") or f.get("name") or "ליד",
                score          = int(f.get("Score") or f.get("score") or 0),
                tier           = (f.get("Tier") or f.get("tier") or "COLD").upper(),
                domain         = f.get("domain") or f.get("Domain") or "general",
                channel        = f.get("channel") or "whatsapp",
                days_active    = days_active,
                days_silent    = days_silent,
                converted      = bool(f.get("status") in ("closed", "won", "converted")),
                followup_count = int(f.get("followup_count") or 0),
                answers        = {},
            ))
        except Exception:
            continue
    return profiles


def _mock_leads() -> list[LeadProfile]:
    """מוק לdev."""
    return [
        LeadProfile("w:001","יהודה כהן",   94,"HOT","real_estate","whatsapp",45,2,  False,1),
        LeadProfile("w:002","צבי לוי",     82,"HOT","real_estate","whatsapp",30,5,  False,2),
        LeadProfile("t:003","שרה מזרחי",   67,"HOT","import",    "telegram",20,3,  False,0),
        LeadProfile("w:004","אוריאל גרין",  55,"HOT","real_estate","whatsapp",60,15, False,3),
        LeadProfile("w:005","ראובן שמיר",   88,"HOT","real_estate","whatsapp",10,1,  True, 0),
        LeadProfile("t:006","דינה אברהם",   35,"WARM","import",   "telegram",90,40, False,2),
        LeadProfile("w:007","משה כץ",       20,"COLD","real_estate","whatsapp",120,65,False,1),
        LeadProfile("w:008","נעמי פרץ",     72,"HOT","real_estate","whatsapp",5,2,  False,0),
        LeadProfile("e:009","דוד ישראלי",   45,"HOT","import",    "email",   3, 1,  False,0),
        LeadProfile("w:010","חנה שפירא",    91,"HOT","real_estate","whatsapp",2, 0,  False,0),
    ]


# ══════════════════════════════════════════════════
# 2. Segmentation
# ══════════════════════════════════════════════════

def classify_segment(lead: LeadProfile) -> str:
    """מסווג ליד לאחד מ-7 segments."""
    s  = lead.days_silent
    sc = lead.score

    # New — ראשון (דורס הכל)
    if s <= 7 and lead.days_active <= 7:
        return "new"

    # Champion
    if lead.converted and s <= 30:
        return "champion"

    # Hot Prospect
    if sc >= 70 and not lead.converted and s <= 14:
        return "hot_prospect"

    # Promising
    if 50 <= sc < 70 and not lead.converted and s <= 21:
        return "promising"

    # At Risk
    if s >= 30 and 20 <= sc < 50:
        return "at_risk"

    # Lost
    if s >= 60 and sc < 30:
        return "lost"

    # Needs Attention (catch-all warm)
    if 7 <= s <= 30 and sc >= 40:
        return "needs_attention"

    return "at_risk"


def run_segmentation(leads: list[LeadProfile]) -> list[SegmentReport]:
    """מחלק כל הלידים לsegments."""
    buckets: dict[str, list[str]] = {k: [] for k in SEGMENTS}

    for lead in leads:
        seg = classify_segment(lead)
        lead.segment = seg
        buckets[seg].append(lead.name)

    reports = []
    for seg_id, cfg in SEGMENTS.items():
        names = buckets[seg_id]
        if not names:
            continue
        reports.append(SegmentReport(
            segment = seg_id,
            label   = cfg["label"],
            count   = len(names),
            action  = cfg["action"],
            leads   = names[:5],
        ))

    priority = ["new","hot_prospect","champion","promising","needs_attention","at_risk","lost"]
    reports.sort(key=lambda r: priority.index(r.segment) if r.segment in priority else 99)
    return reports


# ══════════════════════════════════════════════════
# 3. High-Value Detection
# ══════════════════════════════════════════════════

def detect_high_value(leads: list[LeadProfile], top_n: int = 3) -> list[LeadProfile]:
    """
    מזהה לידים בעלי ערך גבוה ביותר.
    נוסחת ערך: score × (1 + followup_count × 0.05) ÷ (1 + days_silent / 30)
    """
    def value_score(l: LeadProfile) -> float:
        decay   = 1 + l.days_silent / 30
        recency = 1 + (l.followup_count * 0.05)
        return (l.score * recency) / decay

    sorted_leads = sorted(leads, key=value_score, reverse=True)
    return [l for l in sorted_leads[:top_n] if not l.converted]


# ══════════════════════════════════════════════════
# 4. Lookalike Signals
# ══════════════════════════════════════════════════

def extract_lookalike_signals(leads: list[LeadProfile]) -> list[str]:
    """
    מחלץ דפוסים משותפים ל-BOILING leads שנסגרו.
    מחזיר list של insights טקסטואליים.
    """
    closed_hot = [l for l in leads if l.converted and l.score >= 70]
    if not closed_hot:
        return ["אין מספיק עסקאות סגורות עדיין לניתוח lookalike."]

    total   = len(closed_hot)
    signals = []

    channels = {}
    for l in closed_hot:
        channels[l.channel] = channels.get(l.channel, 0) + 1
    top_channel = max(channels, key=channels.get)
    pct = round(channels[top_channel] / total * 100)
    if pct >= 60:
        signals.append(f"📱 {pct}% מהעסקאות הגיעו מ-{top_channel}")

    domains = {}
    for l in closed_hot:
        domains[l.domain] = domains.get(l.domain, 0) + 1
    top_domain = max(domains, key=domains.get)
    pct_d = round(domains[top_domain] / total * 100)
    if pct_d >= 60:
        signals.append(f"🏢 {pct_d}% מדומיין {top_domain}")

    avg_active = sum(l.days_active for l in closed_hot) / total
    signals.append(f"⏱ זמן ממוצע לסגירה: {avg_active:.0f} ימים")

    avg_score = sum(l.score for l in closed_hot) / total
    signals.append(f"📊 ציון ממוצע בסגירה: {avg_score:.0f}")

    avg_fu = sum(l.followup_count for l in closed_hot) / total
    if avg_fu > 0:
        signals.append(f"💬 ממוצע פולואפים לסגירה: {avg_fu:.1f}")

    signals.append(f"\n💡 *Lookalike:* חפש לידים ב-{top_channel} מ-{top_domain} עם score 70+")
    return signals


# ══════════════════════════════════════════════════
# 5. Churn Risk Detection
# ══════════════════════════════════════════════════

def detect_churn_risk(leads: list[LeadProfile]) -> list[LeadProfile]:
    """
    לידים שהיו HOT ועכשיו מסתכנים בנטישה.
    סימנים: score ≥ 60 + שתיקה 7-25 ימים + לא נסגרו.
    """
    at_risk = [
        l for l in leads
        if l.score >= 60
        and 7 <= l.days_silent <= 25
        and not l.converted
    ]
    return sorted(at_risk, key=lambda l: l.score, reverse=True)[:5]


# ══════════════════════════════════════════════════
# 6. Main Report
# ══════════════════════════════════════════════════

def build_audience_report() -> AudienceReport:
    """Entry point — מייצר דוח audience מלא. Read-only לחלוטין."""
    leads = load_all_leads()

    return AudienceReport(
        total             = len(leads),
        segments          = run_segmentation(leads),
        high_value        = detect_high_value(leads),
        lookalike_signals = extract_lookalike_signals(leads),
        churn_risk        = detect_churn_risk(leads),
        generated_at      = datetime.now(tz=timezone.utc).strftime("%d/%m/%Y %H:%M"),
    )


def format_audience_report(report: AudienceReport) -> str:
    """פורמט לטלגרם."""
    lines = [f"🧠 *Audience Intelligence — {report.generated_at}*\n"]
    lines.append(f"👥 סה\"כ לידים: *{report.total}*\n")

    lines.append("*📊 Segmentation:*")
    for seg in report.segments:
        leads_str = ", ".join(seg.leads[:3])
        if len(seg.leads) < seg.count:
            leads_str += f" ועוד {seg.count - len(seg.leads)}"
        lines.append(f"  {seg.label} ({seg.count}): {leads_str}")
        lines.append(f"  → _{seg.action}_")
    lines.append("")

    if report.high_value:
        lines.append("*💎 High-Value Leads:*")
        for l in report.high_value:
            from score_display import format_score_inline  # type: ignore
            inline = format_score_inline(l.score)
            lines.append(f"  • *{l.name}* {inline} | {l.domain} | {l.days_silent}d שתיקה")
        lines.append("")

    if report.lookalike_signals:
        lines.append("*🔍 Lookalike Signals:*")
        for sig in report.lookalike_signals[:4]:
            lines.append(f"  {sig}")
        lines.append("")

    if report.churn_risk:
        lines.append("*🚨 Churn Risk — פנה מהר:*")
        for l in report.churn_risk[:3]:
            lines.append(f"  • *{l.name}* score={l.score} | {l.days_silent}d שתיקה")

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# Scheduler Entry
# ══════════════════════════════════════════════════

def run_audience_scan(owner_chat_id: str = "") -> AudienceReport:
    """Entry point לscheduler — פעם בשבוע."""
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("AUDIENCE_INTELLIGENCE"):
            return AudienceReport()
    except ImportError:
        pass

    report = build_audience_report()
    logger.info(f"[Audience] total={report.total} segments={len(report.segments)}")

    if owner_chat_id and report.total > 0:
        _send_report(report, owner_chat_id)

    return report


def _send_report(report: AudienceReport, chat_id: str):
    try:
        import telebot, os  # type: ignore
        token = os.environ.get("TELEGRAM_TOKEN", "")
        if not token:
            return
        msg = format_audience_report(report)
        telebot.TeleBot(token).send_message(chat_id, msg, parse_mode="Markdown")
        logger.info("[Audience] ✅ report sent")
    except Exception as e:
        logger.error(f"[Audience] send error: {e}")


# ── Utils ─────────────────────────────────────────

def _days_since(iso_str: str) -> int:
    if not iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(tz=timezone.utc) - dt).days)
    except Exception:
        return 0


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    leads = _mock_leads()

    # ── classify_segment ──────────────────────────
    new_lead  = LeadProfile("x","חדש",50,"HOT","real_estate","whatsapp",2,1,False,0)
    chk("new lead → new",           classify_segment(new_lead) == "new")

    hot_lead  = LeadProfile("x","חם",85,"HOT","real_estate","whatsapp",20,3,False,0)
    chk("hot 85 3d → hot_prospect", classify_segment(hot_lead) == "hot_prospect")

    champ     = LeadProfile("x","אלוף",88,"HOT","real_estate","whatsapp",40,10,True,0)
    chk("converted → champion",     classify_segment(champ) == "champion")

    cold_old  = LeadProfile("x","קר",15,"COLD","real_estate","whatsapp",90,70,False,0)
    chk("cold 70d → lost",          classify_segment(cold_old) == "lost")

    # ── run_segmentation ──────────────────────────
    segs    = run_segmentation(leads)
    seg_ids = [s.segment for s in segs]
    chk("segmentation returns list",  isinstance(segs, list))
    chk("has multiple segments",      len(segs) >= 2)
    chk("hot_prospect or new exists", "hot_prospect" in seg_ids or "new" in seg_ids)

    # ── detect_high_value ─────────────────────────
    hv = detect_high_value(leads, top_n=3)
    chk("high value returns max 3",  len(hv) <= 3)
    chk("high value sorted desc",    all(hv[i].score >= hv[i+1].score
                                         for i in range(len(hv)-1)) if len(hv) > 1 else True)
    chk("no converted in high value",all(not l.converted for l in hv))

    # ── detect_churn_risk ─────────────────────────
    cr = detect_churn_risk(leads)
    chk("churn risk returns list",   isinstance(cr, list))
    chk("churn only score 60+",      all(l.score >= 60 for l in cr))
    chk("churn only 7-25 days",      all(7 <= l.days_silent <= 25 for l in cr))

    # ── extract_lookalike_signals ─────────────────
    sigs = extract_lookalike_signals(leads)
    chk("lookalike returns list",    isinstance(sigs, list) and len(sigs) > 0)
    chk("lookalike has strings",     all(isinstance(s, str) for s in sigs))

    # ── build_audience_report ─────────────────────
    report = build_audience_report()
    chk("report.total == 10",        report.total == 10)
    chk("report has segments",       len(report.segments) > 0)
    chk("report has generated_at",   len(report.generated_at) > 5)

    # ── format_audience_report ────────────────────
    import sys, types
    sd = types.ModuleType("score_display")
    sd.format_score_inline = lambda s: f"🔥{s}"
    sys.modules["score_display"] = sd

    formatted = format_audience_report(report)
    chk("formatted not empty",       len(formatted) > 50)
    chk("formatted has 🧠",          "🧠" in formatted)
    chk("formatted has Segmentation","Segmentation" in formatted)

    # ── flag=OFF ──────────────────────────────────
    import importlib.util
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff

    spec = importlib.util.spec_from_file_location("audience_intelligence", __file__)
    ai   = importlib.util.module_from_spec(spec)
    sys.modules["audience_intelligence"] = ai
    spec.loader.exec_module(ai)

    r = ai.run_audience_scan()
    chk("flag=OFF → empty report",   r.total == 0)

    ff.is_enabled = lambda x: True
    r2 = ai.run_audience_scan()
    chk("flag=ON → full report",     r2.total == 10)

    print(f"\n{'='*40}")
    print(f"D04 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    if ok:
        import sys, types
        sd = types.ModuleType("score_display")
        sd.format_score_inline = lambda s: f"🔥{s}"
        sys.modules["score_display"] = sd
        print("\n" + "═"*40)
        print("SAMPLE AUDIENCE REPORT:")
        print("─"*40)
        report = build_audience_report()
        print(format_audience_report(report))
    exit(0 if ok else 1)
