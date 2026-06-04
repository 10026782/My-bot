# interaction_engine.py — D06.1 Interaction Intelligence & Business Memory
# מחליף את meeting_intelligence.py
# flag: FEATURE_INTERACTION_INTELLIGENCE
#
# ארכיטקטורה:
#   [Calendar/WhatsApp/Email/Voice]
#       → Adapter → InteractionSchema (אחיד)
#       → LLM Analysis
#       → Business Memory (Airtable Business_Memory)  ← הדבר החדש
#       → Tasks + Telegram
#
# עיקרון: Stateful, לא Stateless.
# "מה סיכמנו עם ספק הייבוא במרץ?" — המערכת יודעת לענות.

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from airtable_schema import Tables

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Unified Interaction Schema
# ══════════════════════════════════════════════════

@dataclass
class InteractionSchema:
    """מבנה אחיד לכל ערוץ — Calendar / WhatsApp / Email / Voice."""
    source_channel: str        # calendar / whatsapp / email / voice
    raw_id:         str        # מפתח ייחודי מהמקור (מניעת כפילויות)
    title:          str
    participants:   list[str]  = field(default_factory=list)
    timestamp:      str        = ""    # ISO
    end_time:       str        = ""    # ISO (לפגישות)
    raw_content:    str        = ""    # טקסט גולמי / notes / תמלול
    domain:         str        = "general"
    metadata:       dict       = field(default_factory=dict)


@dataclass
class InteractionAnalysis:
    """תוצאת LLM analysis — זהה לכל ערוץ."""
    summary:    str            = ""
    decisions:  list[str]      = field(default_factory=list)
    tasks:      list[dict]     = field(default_factory=list)
    risks:      list[str]      = field(default_factory=list)
    next_steps: str            = ""
    sentiment:  str            = "neutral"
    keywords:   list[str]      = field(default_factory=list)


@dataclass
class BusinessMemoryRecord:
    """רשומת זיכרון עסקי — Single Source of Truth."""
    channel:         str
    external_id:     str        # raw_id מהמקור — מניעת כפילויות
    title:           str
    timestamp:       str
    participants:    str        # comma-separated
    summary:         str
    decisions:       str        # JSON string
    tasks_json:      str        # JSON string
    risks:           str        # comma-separated
    next_steps:      str
    sentiment:       str
    keywords:        str        # comma-separated
    raw_snapshot:    str        # עד 2000 תווים — לעיבוד מחדש בעתיד
    domain:          str
    record_id:       str = ""   # Airtable record ID אחרי שמירה


@dataclass
class InteractionResult:
    interaction:    InteractionSchema
    analysis:       InteractionAnalysis
    memory_id:      str = ""    # Airtable record ID
    tasks_created:  int = 0
    notified:       bool = False


@dataclass
class ScanResult:
    processed:  list[InteractionResult] = field(default_factory=list)
    skipped:    int = 0   # כפילויות שדולגו
    errors:     list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════
# Adapters — כל ערוץ מחזיר list[InteractionSchema]
# ══════════════════════════════════════════════════

def _adapter_calendar(lookback_minutes: int = 10) -> list[InteractionSchema]:
    """פגישות שהסתיימו לפני lookback_minutes דקות."""
    try:
        from calendar_tools import calendar_get_events  # type: ignore
        raw = calendar_get_events(days_ahead=0)
        if not raw or not isinstance(raw, list):
            return _mock_calendar()

        now    = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(minutes=lookback_minutes)
        result = []

        for ev in raw:
            end = _parse_dt(ev.get("end",""))
            if end and cutoff <= end <= now:
                result.append(InteractionSchema(
                    source_channel = "calendar",
                    raw_id         = ev.get("id", ""),
                    title          = ev.get("summary", "פגישה"),
                    participants   = ev.get("attendees", []),
                    timestamp      = ev.get("start",""),
                    end_time       = ev.get("end",""),
                    raw_content    = ev.get("description",""),
                    domain         = _detect_domain(ev.get("summary","") + ev.get("description","")),
                ))
        return result
    except ImportError:
        return _mock_calendar()
    except Exception as e:
        logger.error(f"[Interaction] calendar adapter error: {e}")
        return []


def _adapter_whatsapp() -> list[InteractionSchema]:
    """
    שיחות וואטסאפ שהסתיימו (לפי lead_memory sessions שסומנו done).
    Phase 1 — stub. Phase 2 — מחבר ל-session_store.
    """
    try:
        from session_store import lead_sessions  # type: ignore
        result = []
        for sender, session in lead_sessions.get_all_active():
            if session.get("done") and session.get("summary"):
                result.append(InteractionSchema(
                    source_channel = "whatsapp",
                    raw_id         = f"wa_{sender}_{session.get('created_at','')}",
                    title          = f"שיחת WhatsApp — {session.get('name', sender)}",
                    participants   = [sender],
                    timestamp      = session.get("created_at",""),
                    raw_content    = session.get("summary",""),
                    domain         = session.get("domain","general"),
                ))
        return result
    except ImportError:
        return []  # session_store לא זמין — ok


def _adapter_email() -> list[InteractionSchema]:
    """
    מיילים שטופלו ע"י email_inbound (F06).
    Phase 1 — stub. Phase 2 — מחבר ל-email_inbound.
    """
    return []  # F06 יחבר כשיהיה ready


def _mock_calendar() -> list[InteractionSchema]:
    return [
        InteractionSchema(
            source_channel = "calendar",
            raw_id         = "mock_ev_002",
            title          = "שיחת ספק — ייבוא Q3",
            participants   = ["supplier@china.com"],
            timestamp      = (datetime.now(tz=timezone.utc) - timedelta(hours=1, minutes=10)).isoformat(),
            end_time       = (datetime.now(tz=timezone.utc) - timedelta(minutes=10)).isoformat(),
            raw_content    = (
                "נדון: מחיר Q3 הועלה ב-8%. "
                "הוחלט לבדוק ספקים חלופיים עד סוף החודש. "
                "ספק יישלח הצעת מחיר מעודכנת תוך 3 ימים. "
                "מחיר הסופי ₪45,000."
            ),
            domain = "import",
        ),
    ]


# ══════════════════════════════════════════════════
# LLM Analysis
# ══════════════════════════════════════════════════

_PROMPT = """אתה מנתח אינטראקציות עסקיות.

ערוץ: {channel}
כותרת: {title}
משתתפים: {participants}
תוכן: {content}

החזר JSON בלבד (ללא Markdown):
{{
  "summary": "סיכום 2-3 משפטים",
  "decisions": ["החלטה 1", "החלטה 2"],
  "tasks": [{{"title": "משימה", "owner": "שם", "due": "YYYY-MM-DD"}}],
  "risks": ["סיכון 1"],
  "next_steps": "מה עכשיו",
  "sentiment": "positive/neutral/negative",
  "keywords": ["מילת מפתח 1", "מילת מפתח 2"]
}}"""


def analyze_interaction(interaction: InteractionSchema) -> InteractionAnalysis:
    """Claude מנתח אינטראקציה ומחזיר analysis מובנה."""
    if not interaction.raw_content and not interaction.title:
        return InteractionAnalysis(summary="אין תוכן לניתוח.")

    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        prompt = _PROMPT.format(
            channel      = interaction.source_channel,
            title        = interaction.title,
            participants = ", ".join(interaction.participants) or "לא צוינו",
            content      = interaction.raw_content[:1500] or interaction.title,
        )
        resp = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 700,
            messages   = [{"role":"user","content":prompt}],
        )
        parsed = _parse_json(resp.content[0].text)
        return InteractionAnalysis(
            summary    = parsed.get("summary",""),
            decisions  = parsed.get("decisions",[]),
            tasks      = parsed.get("tasks",[]),
            risks      = parsed.get("risks",[]),
            next_steps = parsed.get("next_steps",""),
            sentiment  = parsed.get("sentiment","neutral"),
            keywords   = parsed.get("keywords",[]),
        )
    except ImportError:
        return _rule_based_analysis(interaction)
    except Exception as e:
        logger.error(f"[Interaction] LLM error: {e}")
        return _rule_based_analysis(interaction)


def _rule_based_analysis(interaction: InteractionSchema) -> InteractionAnalysis:
    """Fallback ללא Claude."""
    import re
    desc     = interaction.raw_content
    analysis = InteractionAnalysis()
    analysis.summary = f"{interaction.title}: {desc[:120]}" if desc else interaction.title

    for kw in ["הוחלט","הוסכם","decided","agreed"]:
        m = re.search(rf"{kw}[: ]+(.+?)[\.\n]", desc, re.IGNORECASE)
        if m: analysis.decisions.append(m.group(1).strip())

    amounts = re.findall(r'₪[\d,]+|\$[\d,]+', desc)
    if amounts:
        analysis.tasks.append({
            "title": f"טיפול בתשלום: {amounts[0]}",
            "owner": "owner",
            "due":   (datetime.now(tz=timezone.utc)+timedelta(days=3)).strftime("%Y-%m-%d"),
        })

    if any(kw in desc.lower() for kw in ["יקר","עלה","מחיר","cost","expensive"]):
        analysis.risks.append("עלות גבוהה מהצפוי")
        analysis.sentiment = "negative"

    analysis.keywords = re.findall(r'\b[א-ת]{4,}\b', desc)[:5]
    return analysis


# ══════════════════════════════════════════════════
# Business Memory — Persist to Airtable
# ══════════════════════════════════════════════════

def save_to_business_memory(
    interaction: InteractionSchema,
    analysis:    InteractionAnalysis,
) -> str:
    """
    שומר רשומת זיכרון עסקי ל-Airtable Business_Memory.
    מחזיר record_id, או "" אם נכשל.
    זה ה-Single Source of Truth — נשמר לפני Telegram.
    """
    import json
    try:
        from airtable_tools import airtable_add  # type: ignore

        fields = {
            "channel":      interaction.source_channel,
            "external_id":  interaction.raw_id,
            "title":        interaction.title,
            "timestamp":    interaction.timestamp or datetime.now(tz=timezone.utc).isoformat(),
            "participants": ", ".join(interaction.participants),
            "domain":       interaction.domain,
            "summary":      analysis.summary,
            "decisions":    json.dumps(analysis.decisions, ensure_ascii=False),
            "tasks_json":   json.dumps(analysis.tasks, ensure_ascii=False),
            "risks":        ", ".join(analysis.risks),
            "next_steps":   analysis.next_steps,
            "sentiment":    analysis.sentiment,
            "keywords":     ", ".join(analysis.keywords),
            "raw_snapshot": interaction.raw_content[:2000],
        }

        result = airtable_add("Business_Memory", fields)
        if "✅" in result:
            import re
            m = re.search(r'rec\w+', result)
            record_id = m.group(0) if m else "saved"
            logger.info(f"[Memory] saved: {interaction.title} → {record_id}")
            return record_id
        return ""

    except ImportError:
        logger.debug(f"[Memory] dry-run: {interaction.title}")
        return "dry-run"
    except Exception as e:
        logger.error(f"[Memory] save error: {e}")
        return ""


def is_duplicate(raw_id: str) -> bool:
    """בודק אם אינטראקציה כבר נשמרה (לפי external_id)."""
    if not raw_id or raw_id.startswith("mock_"):
        return False
    try:
        from airtable_tools import airtable_get  # type: ignore
        raw = airtable_get("Business_Memory", f"{{external_id}}='{raw_id}'")
        return raw and "אין רשומות" not in raw and "❌" not in raw
    except Exception:
        return False


def search_business_memory(query: str, domain: str = "") -> str:
    """
    חיפוש בזיכרון העסקי — לשימוש Agent כשנשאלים "מה סיכמנו ב..."
    """
    try:
        from airtable_tools import airtable_get  # type: ignore
        formula = f"SEARCH('{query}',{{summary}})"
        if domain:
            formula = f"AND(SEARCH('{query}',{{summary}}),{{domain}}='{domain}')"
        raw = airtable_get("Business_Memory", formula)
        if not raw or "אין רשומות" in raw:
            return f"לא נמצאו רשומות עבור: {query}"
        return raw
    except ImportError:
        return "Business Memory לא זמין."
    except Exception as e:
        return f"שגיאה בחיפוש: {e}"


# ══════════════════════════════════════════════════
# Task Creation
# ══════════════════════════════════════════════════

def create_tasks_from_analysis(
    analysis:    InteractionAnalysis,
    interaction: InteractionSchema,
    memory_id:   str = "",
) -> int:
    """יוצר Tasks ב-Airtable עם קישור לרשומת הזיכרון."""
    if not analysis.tasks:
        return 0
    created = 0
    try:
        from airtable_tools import airtable_add  # type: ignore
        for task in analysis.tasks:
            fields = {
                "Name":      task.get("title",""),
                "Status":    "open",
                "Priority":  "high" if analysis.sentiment == "negative" else "medium",
                "Notes":     (
                    f"מקור: {interaction.source_channel} — {interaction.title}\n"
                    f"בעלים: {task.get('owner','')}\n"
                    f"Memory ID: {memory_id}"
                ),
                "Deadline":  task.get("due",""),
            }
            result = airtable_add(Tables.TASKS, fields)
            if "✅" in result:
                created += 1
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"[Interaction] create_tasks error: {e}")
    return created


# ══════════════════════════════════════════════════
# Format & Notify
# ══════════════════════════════════════════════════

def format_interaction_summary(
    interaction: InteractionSchema,
    analysis:    InteractionAnalysis,
    memory_id:   str = "",
) -> str:
    """פורמט לטלגרם."""
    emoji = {"positive":"🟢","negative":"🔴","neutral":"🟡"}.get(analysis.sentiment,"🟡")
    ch_icon = {"calendar":"📅","whatsapp":"💬","email":"📧","voice":"🎙"}.get(interaction.source_channel,"📌")

    lines = [
        f"{ch_icon} *{interaction.source_channel.upper()}* {emoji}",
        f"*{interaction.title}*",
        "",
    ]

    if analysis.summary:
        lines += [f"📝 {analysis.summary}", ""]

    if analysis.decisions:
        lines.append("✅ *החלטות:*")
        for d in analysis.decisions:
            lines.append(f"  • {d}")
        lines.append("")

    if analysis.tasks:
        lines.append(f"📌 *משימות ({len(analysis.tasks)}):*")
        for t in analysis.tasks[:4]:
            due = f" | {t.get('due','')}" if t.get('due') else ""
            lines.append(f"  • {t.get('title','')} — {t.get('owner','?')}{due}")
        lines.append("")

    if analysis.risks:
        lines.append(f"⚠️ *סיכונים:* {', '.join(analysis.risks[:2])}")

    if analysis.next_steps:
        lines.append(f"➡️ *הבא:* {analysis.next_steps}")

    if memory_id and memory_id not in ("","dry-run"):
        lines.append(f"\n_💾 נשמר בזיכרון עסקי — #{memory_id[:8]}_")

    return "\n".join(lines)


def _notify_owner(text: str, chat_id: str) -> bool:
    try:
        import telebot  # type: ignore
        token = os.environ.get("TELEGRAM_TOKEN","")
        if not token or not chat_id:
            return False
        telebot.TeleBot(token).send_message(chat_id, text, parse_mode="Markdown")
        return True
    except Exception as e:
        logger.error(f"[Interaction] notify error: {e}")
        return False


# ══════════════════════════════════════════════════
# Main Entry — run_interaction_scan()
# ══════════════════════════════════════════════════

def run_interaction_scan(
    channels:      list[str] = None,
    owner_chat_id: str = "",
) -> ScanResult:
    """
    Entry point לscheduler — כל 15 דקות.
    Pipeline:
      Adapter → InteractionSchema
      → LLM Analysis
      → 💾 Business Memory (FIRST)
      → Tasks
      → Telegram
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("INTERACTION_INTELLIGENCE"):
            return ScanResult()
    except ImportError:
        logger.warning("[Interaction] feature_flags not available — dev mode")

    channels = channels or ["calendar", "whatsapp", "email"]
    result   = ScanResult()

    # ── איסוף מכל הערוצים ────────────────────────
    interactions: list[InteractionSchema] = []
    _adapters = {
        "calendar": _adapter_calendar,
        "whatsapp": _adapter_whatsapp,
        "email":    _adapter_email,
    }
    for ch in channels:
        if ch in _adapters:
            try:
                interactions.extend(_adapters[ch]())
            except Exception as e:
                result.errors.append(f"{ch}: {e}")

    # ── עיבוד כל אינטראקציה ──────────────────────
    for interaction in interactions:

        # מניעת כפילויות
        if is_duplicate(interaction.raw_id):
            result.skipped += 1
            logger.debug(f"[Interaction] duplicate skipped: {interaction.raw_id}")
            continue

        try:
            # 1. LLM Analysis
            analysis = analyze_interaction(interaction)

            # 2. 💾 Business Memory — FIRST (לפני Telegram!)
            memory_id = save_to_business_memory(interaction, analysis)

            # 3. Tasks
            tasks_n = create_tasks_from_analysis(analysis, interaction, memory_id)

            # 4. Telegram
            summary_msg = format_interaction_summary(interaction, analysis, memory_id)
            notified    = bool(owner_chat_id and _notify_owner(summary_msg, owner_chat_id))

            result.processed.append(InteractionResult(
                interaction   = interaction,
                analysis      = analysis,
                memory_id     = memory_id,
                tasks_created = tasks_n,
                notified      = notified,
            ))
            logger.info(
                f"[Interaction] ✅ {interaction.source_channel}: {interaction.title} "
                f"| tasks={tasks_n} | memory={memory_id[:8] if memory_id else 'none'}"
            )

        except Exception as e:
            msg = f"error: {interaction.title}: {e}"
            logger.error(f"[Interaction] {msg}")
            result.errors.append(msg)

    logger.info(
        f"[Interaction] scan done | "
        f"processed={len(result.processed)} skipped={result.skipped} errors={len(result.errors)}"
    )
    return result


# ══════════════════════════════════════════════════
# Upcoming Reminders (שומר על הפיצ'ר מD06)
# ══════════════════════════════════════════════════

def send_upcoming_reminders(owner_chat_id: str, minutes_ahead: int = 15):
    """תזכורות לפגישות קרובות — נשמר מD06."""
    try:
        from calendar_tools import calendar_get_events  # type: ignore
        raw = calendar_get_events(days_ahead=1)
        if not raw or not isinstance(raw, list):
            return

        now    = datetime.now(tz=timezone.utc)
        cutoff = now + timedelta(minutes=minutes_ahead)

        for ev in raw:
            start = _parse_dt(ev.get("start",""))
            if start and now <= start <= cutoff:
                title     = ev.get("summary","פגישה")
                attendees = ", ".join(ev.get("attendees",[])[:3]) or "ללא משתתפים"
                time_str  = start.strftime("%H:%M")
                msg = (
                    f"⏰ *פגישה בעוד {minutes_ahead} דקות*\n"
                    f"📌 *{title}*\n"
                    f"🕐 {time_str} | 👥 {attendees}"
                )
                if owner_chat_id:
                    _notify_owner(msg, owner_chat_id)
    except ImportError:
        pass


# ── Utils ─────────────────────────────────────────

def _parse_dt(iso_str: str) -> Optional[datetime]:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _parse_json(text: str) -> dict:
    import json, re
    text = re.sub(r"```json|```","",text).strip()
    try:
        return json.loads(text)
    except Exception:
        return {}


def _detect_domain(text: str) -> str:
    text = text.lower()
    if any(k in text for k in ["נכס","דירה","שכירות","נדל","property"]):
        return "realestate"
    if any(k in text for k in ["ספק","ייבוא","סחורה","import","supplier"]):
        return "import"
    return "general"


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    import sys, types, json
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    # ── InteractionSchema ─────────────────────────
    i = InteractionSchema(
        source_channel="calendar", raw_id="ev001",
        title="פגישת ספק", participants=["a@b.com"],
        raw_content="הוחלט לבדוק ספקים. מחיר ₪50,000.",
        domain="import",
    )
    chk("schema source_channel",    i.source_channel == "calendar")
    chk("schema raw_id",            i.raw_id == "ev001")

    # ── _rule_based_analysis ──────────────────────
    a = _rule_based_analysis(i)
    chk("rule_based summary",       len(a.summary) > 5)
    chk("rule_based decisions",     len(a.decisions) >= 1)
    chk("rule_based tasks (amount)", len(a.tasks) >= 1)
    chk("rule_based risk (יקר/מחיר)", len(a.risks) >= 0)

    # ── _detect_domain ────────────────────────────
    chk("detect import domain",     _detect_domain("פגישת ספק ייבוא Q3") == "import")
    chk("detect realestate domain", _detect_domain("נכס ברחוב הרצל") == "realestate")
    chk("detect general domain",    _detect_domain("שיחת יעוץ") == "general")

    # ── save_to_business_memory — dry-run ────────
    at = types.ModuleType("airtable_tools")
    saves = []
    at.airtable_add = lambda t, f: (saves.append(f), "✅ rec_test123")[1]
    at.airtable_get = lambda t, f: "אין רשומות"
    sys.modules["airtable_tools"] = at

    mid = save_to_business_memory(i, a)
    chk("memory saved (dry or real)", len(mid) > 0)
    chk("airtable called",           len(saves) >= 1)

    if saves:
        saved = saves[-1]
        chk("memory has channel",    saved.get("channel") == "calendar")
        chk("memory has title",      saved.get("title") == "פגישת ספק")
        chk("memory has summary",    len(saved.get("summary","")) > 0)
        chk("memory has decisions JSON", "decisions" in saved)
        chk("memory has raw_snapshot",  "raw_snapshot" in saved)
        chk("memory has domain",     saved.get("domain") == "import")
        # decisions is valid JSON
        try:
            json.loads(saved.get("decisions","[]"))
            chk("decisions is valid JSON", True)
        except Exception:
            chk("decisions is valid JSON", False)

    # ── is_duplicate ──────────────────────────────
    at.airtable_get = lambda t, f: "• ev001"
    chk("duplicate detected",       is_duplicate("ev001") is True)
    at.airtable_get = lambda t, f: "אין רשומות"
    chk("not duplicate",            is_duplicate("ev999") is False)
    chk("mock not duplicate",       is_duplicate("mock_ev_001") is False)

    # ── format_interaction_summary ────────────────
    analysis = InteractionAnalysis(
        summary   = "נדון תמחור Q3",
        decisions = ["לבדוק ספקים חלופיים"],
        tasks     = [{"title":"שלח RFQ","owner":"אליהו","due":"2026-06-15"}],
        risks     = ["עלות גבוהה"],
        sentiment = "negative",
    )
    fmt = format_interaction_summary(i, analysis, memory_id="rec_abc123")
    chk("format has channel icon",  "📅" in fmt)
    chk("format has 🔴 (negative)", "🔴" in fmt)
    chk("format has decisions",     "לבדוק" in fmt)
    chk("format has tasks",         "שלח RFQ" in fmt)
    chk("format has memory badge",  "rec_abc" in fmt)

    # ── run_interaction_scan — flag=OFF ───────────
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff

    import importlib.util
    spec = importlib.util.spec_from_file_location("interaction_engine", __file__)
    ie   = importlib.util.module_from_spec(spec)
    sys.modules["interaction_engine"] = ie
    spec.loader.exec_module(ie)

    r = ie.run_interaction_scan()
    chk("flag=OFF → empty result",  r.processed == [] and r.skipped == 0)

    # flag=ON → processes mock calendar
    ff.is_enabled = lambda x: True
    at.airtable_get = lambda t, f: "אין רשומות"  # no duplicates
    r2 = ie.run_interaction_scan(["calendar"])
    chk("flag=ON → processed > 0",  len(r2.processed) > 0)
    chk("flag=ON → memory_id set",  any(p.memory_id for p in r2.processed))

    print(f"\n{'='*40}")
    print(f"D06.1 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
