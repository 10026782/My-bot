# score_display.py — Lead Temperature Display System
# סולם 5 דרגות: COLD → WARM → HOT → VERY HOT → BOILING
# ציון 0-100 פנימי, תצוגה ויזואלית לחלוטין.

from __future__ import annotations


# ══════════════════════════════════════════════════
# Temperature Scale
# ══════════════════════════════════════════════════

_SCALE = [
    (81, "🚀", "BOILING",  "ליד רותח — פנה עכשיו!"),
    (61, "🔥🔥", "VERY HOT","ליד חם מאוד — היום"),
    (41, "🔥",  "HOT",      "ליד חם — פולואפ מהיר"),
    (21, "🌤️", "WARM",     "מתעניין — שמור קשר"),
    (0,  "🧊",  "COLD",     "מתחמם — רצף אוטומטי"),
]


def get_temperature(score: int) -> tuple[str, str, str]:
    """מחזיר (emoji, label, advice) לפי score."""
    for threshold, emoji, label, advice in _SCALE:
        if score >= threshold:
            return emoji, label, advice
    return "🧊", "COLD", "רצף אוטומטי"


def score_bar(score: int, length: int = 10) -> str:
    filled = round(max(0, min(score, 100)) / 100 * length)
    return "█" * filled + "░" * (length - filled)


# ══════════════════════════════════════════════════
# format_lead_report() — החלפה ל-lead_qualifier.py
# ══════════════════════════════════════════════════

def format_lead_report(qualification: dict) -> str:
    """
    פורמט ויזואלי מלא.
    קלט: dict עם score, tier, summary, risk, next_step, signals, name
    """
    score     = int(qualification.get("score", 0))
    name      = qualification.get("name", "")
    summary   = qualification.get("summary", "")
    risk      = qualification.get("risk", "")
    next_step = qualification.get("next_step", "")
    signals   = qualification.get("signals", [])  # list[str] — מה הצביע על ה-score

    emoji, label, advice = get_temperature(score)
    bar = score_bar(score)

    lines = []

    if name:
        lines.append(f"👤 *{name}*")

    lines.append(f"{emoji} *{label} — {score}/100*")
    lines.append(f"`{bar}` {score}%")
    lines.append("")

    # Signals — מה תרם לציון
    if signals:
        for s in signals[:5]:
            lines.append(f"✓ {s}")
        lines.append("")

    if summary:
        lines.append(f"📋 {summary}")
    if risk:
        lines.append(f"⚠️ {risk}")

    lines.append("")
    lines.append("*Next Action:*")
    if next_step:
        lines.append(f"📞 {next_step}")
    else:
        lines.append(f"💡 {advice}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# format_score_inline() — לדוח בוקר / notifications
# ══════════════════════════════════════════════════

def format_score_inline(score: int) -> str:
    """קומפקטי: 🚀 BOILING 94 ████████░░"""
    emoji, label, _ = get_temperature(score)
    bar = score_bar(score, 8)
    return f"{emoji} {label} {score} `{bar}`"


# ══════════════════════════════════════════════════
# format_leads_summary() — לדוח בוקר daily_digest
# ══════════════════════════════════════════════════

def format_leads_summary(leads: list[dict]) -> str:
    """
    טבלת לידים לדוח הבוקר.
    קלט: list[dict] עם name, score, next_step
    """
    if not leads:
        return "📭 אין לידים פעילים."

    # מיון לפי score יורד
    leads = sorted(leads, key=lambda l: l.get("score", 0), reverse=True)

    # קיבוץ לפי temperature
    boiling  = [l for l in leads if l.get("score", 0) >= 81]
    very_hot = [l for l in leads if 61 <= l.get("score", 0) <= 80]
    hot      = [l for l in leads if 41 <= l.get("score", 0) <= 60]
    warm     = [l for l in leads if 21 <= l.get("score", 0) <= 40]
    cold     = [l for l in leads if l.get("score", 0) <= 20]

    lines = [f"👥 *לידים — {len(leads)} פעילים*\n"]

    def _section(group, emoji, label, show_detail=True):
        if not group:
            return
        lines.append(f"{emoji} *{label} ({len(group)}):*")
        if show_detail:
            for l in group[:5]:
                s    = l.get("score", 0)
                bar  = score_bar(s, 8)
                name = l.get("name", "ליד")
                step = l.get("next_step", "")
                step_str = f" | {step[:28]}" if step else ""
                lines.append(f"  • *{name}* `{bar}` {s}{step_str}")
            if len(group) > 5:
                lines.append(f"  _(ועוד {len(group)-5})_")
        else:
            names = ", ".join(l.get("name","?") for l in group[:5])
            if len(group) > 5:
                names += f" ועוד {len(group)-5}"
            lines.append(f"  {names}")
        lines.append("")

    _section(boiling,  "🚀", "BOILING",  show_detail=True)
    _section(very_hot, "🔥🔥", "VERY HOT", show_detail=True)
    _section(hot,      "🔥",  "HOT",      show_detail=False)
    _section(warm,     "🌤️", "WARM",     show_detail=False)
    if cold:
        lines.append(f"🧊 *COLD ({len(cold)}):* רצף אוטומטי פעיל")
        lines.append("")

    avg = sum(l.get("score",0) for l in leads) // len(leads) if leads else 0
    lines.append(f"📊 ממוצע: {format_score_inline(avg)}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# format_airtable_row() — לתצוגה ב-Airtable
# ══════════════════════════════════════════════════

def format_airtable_temperature(score: int) -> str:
    """
    שדה Temperature לAirtable.
    דוגמה: 🚀 BOILING
    """
    emoji, label, _ = get_temperature(score)
    return f"{emoji} {label}"


# ══════════════════════════════════════════════════
# Self-tests + Samples
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    # get_temperature
    chk("98 → BOILING 🚀",    get_temperature(98)[1] == "BOILING")
    chk("81 → BOILING",       get_temperature(81)[1] == "BOILING")
    chk("80 → VERY HOT",      get_temperature(80)[1] == "VERY HOT")
    chk("61 → VERY HOT",      get_temperature(61)[1] == "VERY HOT")
    chk("60 → HOT",           get_temperature(60)[1] == "HOT")
    chk("41 → HOT",           get_temperature(41)[1] == "HOT")
    chk("40 → WARM",          get_temperature(40)[1] == "WARM")
    chk("21 → WARM",          get_temperature(21)[1] == "WARM")
    chk("20 → COLD 🧊",       get_temperature(20)[1] == "COLD")
    chk("0 → COLD",           get_temperature(0)[1]  == "COLD")

    # score_bar
    chk("bar 100 = full",     score_bar(100) == "██████████")
    chk("bar 0   = empty",    score_bar(0)   == "░░░░░░░░░░")
    chk("bar 50  = half",     score_bar(50)  == "█████░░░░░")

    # format_lead_report
    q = {
        "score": 94, "name": "יהודה כהן",
        "summary": "ליד ממוקד עם תקציב גבוה",
        "risk": "מחיר גבוה מהמצופה",
        "next_step": "לחזור תוך שעה עם הצעה",
        "signals": ["ביקש להתקדם", "השאיר טלפון", "עסק פעיל", "הגיב מהר"],
    }
    r = format_lead_report(q)
    chk("BOILING in report",      "BOILING" in r)
    chk("94/100 in report",       "94/100" in r)
    chk("bar in report",          "█" in r)
    chk("signals ✓ in report",    "✓" in r)
    chk("name in report",         "יהודה" in r)
    chk("Next Action in report",  "Next Action" in r)

    # format_score_inline
    inline = format_score_inline(82)
    chk("inline BOILING at 82",       "BOILING" in inline)
    chk("inline 82",              "82" in inline)

    # format_airtable_temperature
    chk("airtable BOILING",       "🚀" in format_airtable_temperature(95))
    chk("airtable COLD",          "🧊" in format_airtable_temperature(10))

    # format_leads_summary
    leads = [
        {"name": "יהודה",  "score": 94, "next_step": "לחזור תוך שעה"},
        {"name": "צבי",    "score": 82, "next_step": ""},
        {"name": "אוריאל", "score": 67, "next_step": "שלח הצעה"},
        {"name": "שמעון",  "score": 35, "next_step": ""},
        {"name": "ראובן",  "score": 12, "next_step": ""},
    ]
    s = format_leads_summary(leads)
    chk("summary has BOILING",    "BOILING" in s)
    chk("summary has VERY HOT",   "VERY HOT" in s)
    chk("summary has יהודה",      "יהודה" in s)
    chk("summary has average",    "📊" in s)

    print(f"\n{'='*40}")
    print(f"Tests: {passed} passed, {failed} failed")

    print("\n" + "═"*40)
    print("BOILING — 94/100:")
    print("─"*40)
    print(format_lead_report(q))
    print("\n" + "═"*40)
    print("COLD — 15/100:")
    print("─"*40)
    print(format_lead_report({"score": 15, "name": "לקוח פוטנציאלי",
        "summary": "שאל שאלה כללית", "next_step": ""}))
    print("\n" + "═"*40)
    print("DIGEST SUMMARY:")
    print("─"*40)
    print(format_leads_summary(leads))
    print("\n" + "═"*40)
    print("AIRTABLE COLUMN:")
    print("─"*40)
    for l in leads:
        temp = format_airtable_temperature(l["score"])
        print(f"  {l['name']:10} | {l['score']:3} | {temp}")

    return failed == 0


if __name__ == "__main__":
    ok = _run_tests()
    exit(0 if ok else 1)
