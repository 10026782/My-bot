# ad_attribution.py — D05 v2 (Bulletproof)
# שיפורים על v1:
# 1. UTM מופרד ל-3 שדות (source/medium/campaign)
# 2. נרמול אגרסיבי
# 3. Timeframe parameter לשאילתות
# 4. Organic/Direct ברירת מחדל — Warning רק לקמפיין שבור

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.query_contract import after

logger = logging.getLogger(__name__)

_KNOWN_PLATFORMS = {
    "meta","facebook","google","tiktok",
    "organic","referral","ivr","email","sms","direct",
}


# ══════════════════════════════════════════════════
# Normalization — פעם אחת, לכולם
# ══════════════════════════════════════════════════

def _norm(s: str) -> str:
    """
    נרמול אגרסיבי:
      Meta Rosh24 → meta_rosh24
      meta → meta
      (blank) → ""
    """
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9\u05d0-\u05ea]+", "_", s)  # עברית + לטינית
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:40]


def extract_platform(utm_source: str) -> str:
    src = _norm(utm_source).split("_")[0]
    if src in _KNOWN_PLATFORMS:
        return src
    if "fb" in src or "face" in src:
        return "meta"
    if "goog" in src:
        return "google"
    return "other"


# ══════════════════════════════════════════════════
# UTM Parsing — 3 שדות נפרדים
# ══════════════════════════════════════════════════

@dataclass
class UTMParams:
    """3 שדות UTM מופרדים — מה שיורד לAirtable."""
    source:   str = ""   # utm_source  : meta / google / dani_cohen
    medium:   str = ""   # utm_medium  : cpc / referral / story
    campaign: str = ""   # utm_campaign: apt_tlv / rosh24_men35

    @property
    def platform(self) -> str:
        return extract_platform(self.source)

    @property
    def campaign_source(self) -> str:
        """String מאוחד לDisplay בלבד — לא לstorage."""
        parts = [p for p in [self.source, self.campaign] if p]
        return "_".join(parts) if parts else "direct"

    @property
    def is_paid(self) -> bool:
        """האם הגיע מפרסום ממומן?"""
        return self.platform in {"meta","google","tiktok"} or self.medium in {"cpc","cpm","paid"}

    @property
    def is_organic(self) -> bool:
        return not self.is_paid and self.source in {"organic","direct","",}

    def to_airtable_fields(self) -> dict:
        """שדות Airtable — 3 שדות נפרדים."""
        return {
            "utm_source":   self.source   or "direct",
            "utm_medium":   self.medium   or "organic",
            "utm_campaign": self.campaign or "",
            "platform":     self.platform,
        }


def parse_utm(url_or_text: str = "", manual: dict = None) -> UTMParams:
    """
    מחלץ UTM params מURL או מdict ידני.
    מחזיר UTMParams עם 3 שדות מנורמלים.
    """
    if manual:
        return UTMParams(
            source   = _norm(manual.get("utm_source",   manual.get("source",   ""))),
            medium   = _norm(manual.get("utm_medium",   manual.get("medium",   ""))),
            campaign = _norm(manual.get("utm_campaign", manual.get("campaign", ""))),
        )

    if not url_or_text:
        return UTMParams()

    def _extract(key: str) -> str:
        m = re.search(rf"[?&]{key}=([^&\s#]+)", url_or_text, re.IGNORECASE)
        return _norm(m.group(1)) if m else ""

    return UTMParams(
        source   = _extract("utm_source"),
        medium   = _extract("utm_medium"),
        campaign = _extract("utm_campaign"),
    )


def parse_campaign_source(
    url_or_text: str = "",
    request_args: dict = None,
    channel: str = "whatsapp",
) -> UTMParams:
    """
    Entry point — מחלץ UTM מrequest.
    ברירות מחדל ברורות:
      יש UTM paid → paid lead
      אין UTM + channel ידוע → organic_{channel}
      אין כלום → direct
    """
    # explicit UTM מparams
    if request_args:
        has_utm = any(k.startswith("utm_") or k == "campaign_source" for k in request_args)
        if has_utm:
            if "campaign_source" in request_args:
                # legacy single-field — פרוק ל-3
                cs = _norm(request_args["campaign_source"])
                parts = cs.split("_", 2)
                return UTMParams(
                    source   = parts[0] if len(parts) > 0 else "",
                    medium   = parts[1] if len(parts) > 1 else "",
                    campaign = parts[2] if len(parts) > 2 else "",
                )
            return parse_utm(manual=request_args)

    # UTM מURL
    if url_or_text and "utm_" in url_or_text.lower():
        utm = parse_utm(url_or_text)
        if utm.source:
            return utm

    # ברירת מחדל חכמה — לא Warning
    return UTMParams(
        source   = "organic",
        medium   = channel,   # whatsapp / telegram / email / voice
        campaign = "",
    )


# ══════════════════════════════════════════════════
# Airtable Integration
# ══════════════════════════════════════════════════

def record_lead_source(memory_key: str, utm: UTMParams, *, identity=None) -> bool:
    """רושם 3 שדות UTM דרך ה־Lead service הקנוני."""
    try:
        from core.lead_service import update_lead_fields
        from tools.airtable_tools import airtable_get  # type: ignore
        if identity is None:
            return False
        raw = airtable_get("Leads", f"{{memory_key}}='{memory_key}'")
        if "אין רשומות" in (raw or "") or not raw:
            return False
        rec_m = re.search(r'rec\w+', raw)
        if not rec_m:
            return False
        result = update_lead_fields(
            identity,
            rec_m.group(0),
            utm.to_airtable_fields(),
            source_module="ad_attribution",
        )
        return bool(result.ok)
    except ImportError:
        logger.debug(f"[Attribution] dry-run: {memory_key} → {utm.campaign_source}")
        return False
    except Exception as e:
        logger.error(f"[Attribution] record: {e}")
        return False


def mark_converted(memory_key: str, deal_value: float = 0) -> bool:
    """מסמן ליד כסגור (status=done, Business Outcome=converted) + שווי עסקה."""
    try:
        from tools.airtable_tools import airtable_get, airtable_update  # type: ignore
        from airtable_schema import LeadFields, LeadStatus, LeadOutcome  # type: ignore
        raw = airtable_get("Leads", f"{{memory_key}}='{memory_key}'")
        if "אין רשומות" in (raw or ""):
            return False
        rec_m = re.search(r'rec\w+', raw)
        if not rec_m:
            return False
        fields: dict = {LeadFields.STATUS:       LeadStatus.DONE,
                        LeadFields.OUTCOME:      LeadOutcome.CONVERTED,
                        LeadFields.CONVERTED_AT: datetime.now(tz=timezone.utc).isoformat()}
        if deal_value:
            fields["deal_value"] = deal_value
        # airtable_update() routes through tools.airtable_gateway.airtable_patch
        # internally, unlike what the 17/07 audit assumed.
        result = airtable_update("Leads", rec_m.group(0), fields)
        logger.info(f"[Attribution] converted: {memory_key} ₪{deal_value:,.0f}")
        return bool(result.get("ok"))
    except ImportError:
        return False
    except Exception as e:
        logger.error(f"[Attribution] convert: {e}")
        return False


# ══════════════════════════════════════════════════
# app.py helper
# ══════════════════════════════════════════════════

def inject_source_to_incoming_lead(
    memory_key:   str,
    request_args: dict,
    channel:      str = "whatsapp",
    identity=None,
) -> UTMParams:
    """
    Entry point מapp.py.
    מחלץ → מנרמל → רושם → מחזיר UTMParams.

    Warning ⚠️ רק אם הגיע מדף ממומן אבל חסר UTM.
    Organic/Direct = שקט, ללא Warning.
    """
    utm = parse_campaign_source(request_args=request_args, channel=channel)

    # Warning רק למקרה שיש referer של קמפיין אבל UTM חסר
    referer = request_args.get("referer", "")
    if not utm.is_organic and not utm.source and referer:
        logger.warning(
            f"[Attribution] ⚠️ Missing UTM on paid referrer: {referer[:60]} | lead: {memory_key}"
        )

    record_lead_source(memory_key, utm, identity=identity)
    return utm


# ══════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════

@dataclass
class CampaignStats:
    utm_source:    str
    utm_medium:    str
    utm_campaign:  str
    platform:      str
    total_leads:   int   = 0
    hot_leads:     int   = 0
    conversions:   int   = 0
    avg_score:     float = 0.0
    spend:         float = 0.0   # Phase 2: Meta Ads API
    revenue:       float = 0.0

    @property
    def label(self) -> str:
        parts = [p for p in [self.utm_source, self.utm_campaign] if p]
        return "_".join(parts) or "direct"

    @property
    def conversion_rate(self) -> float:
        return (self.conversions / self.total_leads * 100) if self.total_leads else 0

    @property
    def cpl(self) -> float:
        return (self.spend / self.total_leads) if self.total_leads and self.spend else 0

    @property
    def roi_pct(self) -> float:
        return ((self.revenue - self.spend) / self.spend * 100) if self.spend else 0

    @property
    def quality_score(self) -> float:
        return round(self.avg_score * self.conversion_rate / 10, 1)


@dataclass
class AttributionReport:
    campaigns:      list[CampaignStats] = field(default_factory=list)
    total_leads:    int = 0
    top_campaign:   str = ""
    worst_campaign: str = ""
    days_back:      int = 30
    generated_at:   str = ""
    missing_utm:    int = 0   # ⚠️ רק paid ללא UTM — לא organic


# ══════════════════════════════════════════════════
# Report Builder — עם Timeframe
# ══════════════════════════════════════════════════

def build_attribution_report(days_back: int = 30) -> AttributionReport:
    """
    בונה דוח attribution עם timeframe.
    Airtable pagination aware — לא שולף כל הטבלה.
    """
    try:
        from airtable_schema import LeadOutcome  # type: ignore
        converted_outcome = LeadOutcome.CONVERTED
    except ImportError:
        converted_outcome = None

    leads  = _load_leads_with_timeframe(days_back)
    report = AttributionReport(
        total_leads  = len(leads),
        days_back    = days_back,
        generated_at = datetime.now(tz=timezone.utc).strftime("%d/%m/%Y"),
    )

    # ספור missing UTM רק מpaid (לא organic)
    # Warning: has referer (came from paid link) but no proper UTM
    report.missing_utm = sum(
        1 for l in leads
        if l.get("referer")      # הגיע ממקום ספציפי
        and not l.get("utm_source")  # אבל ללא UTM
    )

    # קבץ לפי source+campaign
    buckets: dict[tuple, list[dict]] = {}
    for lead in leads:
        key = (
            _norm(lead.get("utm_source",   "")),
            _norm(lead.get("utm_medium",   "")),
            _norm(lead.get("utm_campaign", "")),
        )
        buckets.setdefault(key, []).append(lead)

    for (src, med, cmp), group in buckets.items():
        scores    = [l.get("score", 0) for l in group]
        converted = [
            l for l in group
            if l.get("status") == "converted"  # BUG-110: legacy pre-fix marker, no backfill
            or (converted_outcome is not None and l.get("outcome") == converted_outcome)
        ]
        revenues  = [l.get("deal_value", 0) for l in converted if l.get("deal_value")]

        stats = CampaignStats(
            utm_source   = src or "organic",
            utm_medium   = med or "direct",
            utm_campaign = cmp,
            platform     = extract_platform(src),
            total_leads  = len(group),
            hot_leads    = sum(1 for l in group if l.get("score",0) >= 70),
            conversions  = len(converted),
            avg_score    = sum(scores) / len(scores) if scores else 0,
            revenue      = sum(revenues),
        )
        report.campaigns.append(stats)

    report.campaigns.sort(key=lambda c: c.quality_score, reverse=True)

    if report.campaigns:
        report.top_campaign   = report.campaigns[0].label
        report.worst_campaign = report.campaigns[-1].label

    return report


def _load_leads_with_timeframe(days_back: int) -> list[dict]:
    """
    שולף לידים מAirtable עם filter לפי תאריך.
    Pagination aware: מושך עמודים עד שנגמרים.
    """
    try:
        from tools.airtable_tools import airtable_get  # type: ignore
        from airtable_schema import Tables, LeadFields  # type: ignore

        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        raw = airtable_get(Tables.LEADS, after("created_at", cutoff))

        if not raw or "אין רשומות" in str(raw) or not isinstance(raw, list):
            logger.warning("[Attribution] airtable returned no leads — returning empty")
            return []

        return [{
            "utm_source":   _norm(r.get("fields",{}).get("utm_source",  "")),
            "utm_medium":   _norm(r.get("fields",{}).get("utm_medium",  "")),
            "utm_campaign": _norm(r.get("fields",{}).get("utm_campaign","")),
            "score":        int(r.get("fields",{}).get("Score", 0) or 0),
            "status":       r.get("fields",{}).get("status",""),
            "outcome":      r.get("fields",{}).get(LeadFields.OUTCOME,""),  # BUG-110: canonical post-fix conversion marker
            "deal_value":   float(r.get("fields",{}).get("deal_value",0) or 0),
            "referer":      r.get("fields",{}).get("referer",""),
        } for r in raw if isinstance(r, dict)]

    except (ImportError, TypeError):
        logger.warning("[Attribution] airtable tools not available — returning empty, no mock data")
        return []
    except Exception as e:
        logger.error(f"[Attribution] load: {e}")
        return []


def _mock_leads() -> list[dict]:
    return [
        {"utm_source":"meta",    "utm_medium":"cpc",     "utm_campaign":"rosh24_men35","score":92,"status":"converted","deal_value":1200000},
        {"utm_source":"meta",    "utm_medium":"cpc",     "utm_campaign":"rosh24_men35","score":78,"status":"active",   "deal_value":0},
        {"utm_source":"meta",    "utm_medium":"story",   "utm_campaign":"rosh24_men35","score":55,"status":"active",   "deal_value":0},
        {"utm_source":"google",  "utm_medium":"cpc",     "utm_campaign":"apt_tlv",     "score":84,"status":"converted","deal_value":950000},
        {"utm_source":"google",  "utm_medium":"cpc",     "utm_campaign":"apt_tlv",     "score":41,"status":"active",   "deal_value":0},
        {"utm_source":"referral","utm_medium":"referral","utm_campaign":"dani_cohen",  "score":95,"status":"converted","deal_value":1500000},
        {"utm_source":"organic", "utm_medium":"whatsapp","utm_campaign":"",            "score":30,"status":"active",   "deal_value":0},
        {"utm_source":"organic", "utm_medium":"whatsapp","utm_campaign":"",            "score":25,"status":"active",   "deal_value":0},
        {"utm_source":"ivr",     "utm_medium":"voice",   "utm_campaign":"haredi_bneiB","score":60,"status":"active",   "deal_value":0},
        {"utm_source":"",        "utm_medium":"",        "utm_campaign":"",            "score":45,"status":"active",   "deal_value":0,"referer":"https://meta.com/ad/123"},
    ]


# ══════════════════════════════════════════════════
# Format
# ══════════════════════════════════════════════════

def format_attribution_report(report: AttributionReport) -> str:
    lines = [
        f"📊 *Attribution — {report.generated_at}* | {report.days_back} ימים",
        f"סה\"כ {report.total_leads} לידים\n",
    ]

    # ⚠️ רק אם יש paid ללא UTM
    if report.missing_utm:
        lines.append(f"⚠️ *{report.missing_utm} לידים ממומנים ללא UTM* — בדוק לינקי הקמפיין!\n")

    for c in report.campaigns[:7]:
        bar  = "█" * min(int(c.conversion_rate / 10), 10) or "░"
        hot  = f" 🔥{c.hot_leads}" if c.hot_leads else ""
        conv = f" ✅{c.conversions}" if c.conversions else ""
        rev  = f"\n  💰 ₪{c.revenue:,.0f}" if c.revenue else ""

        lines.append(
            f"*{c.label}* | {c.platform}\n"
            f"  {c.total_leads} לידים{hot}{conv} | "
            f"המרה: {c.conversion_rate:.0f}% `{bar}` | ציון: {c.avg_score:.0f}{rev}"
        )

        # Phase 2 — ROI
        if c.spend:
            lines.append(f"  📉 CPL: ₪{c.cpl:,.0f} | ROI: {c.roi_pct:.0f}%")
        lines.append("")

    if report.top_campaign:
        lines.append(f"🏆 *הטוב ביותר:* `{report.top_campaign}`")

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# Scheduler Entry
# ══════════════════════════════════════════════════

def run_attribution_report(
    owner_chat_id: str = "",
    days_back: int = 30,
) -> AttributionReport:
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("AD_ATTRIBUTION"):
            return AttributionReport()
    except ImportError:
        pass

    report = build_attribution_report(days_back=days_back)
    if owner_chat_id and report.campaigns:
        _send(report, owner_chat_id)
    return report


def _send(report: AttributionReport, chat_id: str):
    try:
        import telebot, os  # type: ignore
        token = os.environ.get("TELEGRAM_TOKEN","")
        if not token: return
        telebot.TeleBot(token).send_message(
            chat_id, format_attribution_report(report), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"[Attribution] send: {e}")


# ══════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    # ── _norm ─────────────────────────────────────
    chk("norm Meta Rosh24",    _norm("Meta Rosh24")   == "meta_rosh24")
    chk("norm double spaces",  _norm("meta  rosh")    == "meta_rosh")
    chk("norm META",           _norm("META")           == "meta")
    chk("norm max 40",         len(_norm("a"*100))    <= 40)
    chk("norm empty → ''",     _norm("")              == "")

    # ── parse_utm ─────────────────────────────────
    url = "https://wa.me/972?utm_source=meta&utm_medium=cpc&utm_campaign=rosh24"
    utm = parse_utm(url)
    chk("UTM source=meta",     utm.source   == "meta")
    chk("UTM medium=cpc",      utm.medium   == "cpc")
    chk("UTM campaign=rosh24", utm.campaign == "rosh24")
    chk("UTM platform=meta",   utm.platform == "meta")
    chk("UTM is_paid",         utm.is_paid  is True)

    utm2 = parse_utm(manual={"utm_source":"Google","utm_campaign":"Apt TLV"})
    chk("manual source=google",   utm2.source   == "google")
    chk("manual campaign norm",   utm2.campaign == "apt_tlv")

    utm3 = parse_utm("")
    chk("empty → organic",        utm3.source   == "")
    chk("empty is_organic",       utm3.is_organic)

    # ── parse_campaign_source ─────────────────────
    args = {"utm_source":"meta","utm_medium":"story","utm_campaign":"summer26"}
    utm4 = parse_campaign_source(request_args=args)
    chk("request args parsed",    utm4.source   == "meta")
    chk("request medium=story",   utm4.medium   == "story")

    # organic fallback
    utm5 = parse_campaign_source(request_args={}, channel="whatsapp")
    chk("no UTM → organic",       utm5.source   == "organic")
    chk("no UTM medium=channel",  utm5.medium   == "whatsapp")
    chk("no UTM is_organic",      utm5.is_organic)

    # legacy campaign_source param
    utm6 = parse_campaign_source(request_args={"campaign_source":"meta_cpc_rosh24"})
    chk("legacy source=meta",     utm6.source   == "meta")
    chk("legacy medium=cpc",      utm6.medium   == "cpc")

    # ── UTMParams.to_airtable_fields ──────────────
    utm7 = UTMParams("meta","cpc","rosh24")
    fields = utm7.to_airtable_fields()
    chk("airtable has utm_source",   "utm_source"   in fields)
    chk("airtable has utm_medium",   "utm_medium"   in fields)
    chk("airtable has utm_campaign", "utm_campaign" in fields)
    chk("airtable has platform",     "platform"     in fields)
    chk("airtable 4 fields only",    len(fields)    == 4)

    # ── CampaignStats ─────────────────────────────
    c = CampaignStats("meta","cpc","rosh24","meta",
                      total_leads=10, conversions=3, avg_score=72, hot_leads=5)
    chk("conversion_rate 30%",    c.conversion_rate == 30.0)
    chk("quality_score > 0",      c.quality_score   >  0)
    chk("label = meta_rosh24",    c.label           == "meta_rosh24")
    chk("cpl=0 no spend",         c.cpl             == 0)

    c2 = CampaignStats("google","cpc","tlv","google",
                       total_leads=5, conversions=2, avg_score=80,
                       spend=2000, revenue=10000)
    chk("ROI 400%",   c2.roi_pct == 400.0)
    chk("CPL 400",    c2.cpl     == 400.0)

    # ── build_attribution_report ──────────────────
    report = build_attribution_report(days_back=30)
    chk("report.total_leads == 10",   report.total_leads == 10)
    chk("report has campaigns",        len(report.campaigns) > 0)
    chk("sorted quality desc",
        report.campaigns[0].quality_score >= report.campaigns[-1].quality_score)
    chk("top_campaign set",            len(report.top_campaign) > 0)
    chk("missing_utm=1 (paid no utm)", report.missing_utm == 1)

    # ── format ────────────────────────────────────
    fmt = format_attribution_report(report)
    chk("format has 📊",    "📊" in fmt)
    chk("format has meta",  "meta" in fmt)
    chk("warning shown",    "⚠️" in fmt)  # 1 paid without UTM

    print(f"\n{'='*40}")
    print(f"D05 v2 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    if ok:
        print("\n" + "═"*40)
        print("SAMPLE REPORT:")
        print("─"*40)
        report = build_attribution_report()
        print(format_attribution_report(report))
    exit(0 if ok else 1)
