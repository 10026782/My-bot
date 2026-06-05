# followup_engine.py — N02 Followup Activation
# קובץ: followup_engine.py (flat, לא core/)
# flag: FOLLOWUP_AUTOMATION (env: FEATURE_FOLLOWUP_AUTOMATION=true)
#
# API שה-scheduler מצפה לו:
#   from followup_engine import run_followup_scan
#   result = run_followup_scan(owner_chat_id="...")
#   result.candidates / result.scanned / result.approved / result.skipped / result.errors

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_FOLLOWUP_HOURS = {"HOT": 4, "WARM": 24, "COLD": 72}
_MAX_FOLLOWUPS  = {"HOT": 3, "WARM": 2,  "COLD": 1}

_TEMPLATES = {
    "HOT": {
        "real_estate": "שלום {name} 👋\nרציתי לוודא שקיבלת את כל המידע שצריך לגבי הנכס.\nמה אתה חושב?",
        "import":     "שלום {name} 👋\nיש לי עדכון לגבי ההזמנה מסין. מתי נוח לדבר?",
        "default":    "שלום {name} 👋\nרציתי להמשיך את השיחה שלנו — יש שאלות?",
    },
    "WARM": {
        "real_estate": "שלום {name},\nהייתי שמח לשמוע אם הגעת להחלטה 🙂",
        "import":     "שלום {name},\nרציתי לבדוק מה השתנה מאז שדיברנו.",
        "default":    "שלום {name},\nרק לוודא שהכל בסדר מצידך.",
    },
    "COLD": {
        "real_estate": "שלום {name},\nאנחנו עדיין זמינים לעזור בחיפוש הנכס שלך.",
        "import":     "שלום {name},\nאם יש עניין בייבוא בעתיד — נשמח לשמוע.",
        "default":    "שלום {name},\nנשמח לשמוע ממך אם יש עניין.",
    },
}


@dataclass
class FollowupCandidate:
    memory_key:      str
    tier:            str
    hours_silent:    float
    followup_count:  int
    last_message:    str
    contact_name:    str = ""
    contact_channel: str = ""
    domain:          str = "real_estate"
    draft:           str = ""


@dataclass
class FollowupResult:
    scanned:    int = 0
    candidates: list[FollowupCandidate] = field(default_factory=list)
    approved:   int = 0
    skipped:    int = 0
    errors:     list[str] = field(default_factory=list)


# ── helpers ───────────────────────────────────────

def _hours_since(iso_str: str) -> Optional[float]:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(tz=timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return None


# ── 1. Scan ───────────────────────────────────────

def scan_active_leads() -> list[dict]:
    """לידים פעילים מ-lead_memory singleton (או mock בdev)."""
    try:
        from lead_memory import lead_memory  # type: ignore
        leads = []
        for state in lead_memory.all_active():
            if state.tier in ("HOT", "WARM", "COLD"):
                leads.append({
                    "memory_key":     state.memory_key,
                    "tier":           state.tier,
                    "last_active":    state.last_active,
                    "channel":        state.channel,
                    "followup_count": state.followup_count,
                    "last_message":   state.last_message,
                    "name":           state.contact_name,
                    "domain":         state.domain or "real_estate",
                })
        return leads
    except ImportError:
        logger.warning("[Followup] lead_memory not available — mock mode")
        return _mock_leads()
    except Exception as e:
        logger.error(f"[Followup] scan error: {e}")
        return _mock_leads()


def _mock_leads() -> list[dict]:
    now = datetime.now(tz=timezone.utc)
    return [
        {"memory_key": "w:111", "tier": "HOT",  "name": "דני כהן",
         "last_active": (now - timedelta(hours=5)).isoformat(),
         "channel": "whatsapp", "followup_count": 0,
         "last_message": "אשמח לשמוע עוד", "domain": "real_estate"},
        {"memory_key": "t:222", "tier": "WARM", "name": "רחל לוי",
         "last_active": (now - timedelta(hours=30)).isoformat(),
         "channel": "telegram", "followup_count": 0,
         "last_message": "צריכה לחשוב", "domain": "import"},
        {"memory_key": "w:333", "tier": "COLD", "name": "משה גרין",
         "last_active": (now - timedelta(hours=10)).isoformat(),
         "channel": "whatsapp", "followup_count": 0,
         "last_message": "מה המחיר?", "domain": "real_estate"},
    ]


# ── 2. Decision ───────────────────────────────────

def determine_followup_needed(lead: dict) -> tuple[bool, str]:
    tier           = lead.get("tier", "COLD").upper()
    followup_count = int(lead.get("followup_count", 0))
    last_active    = lead.get("last_active", "")

    max_f = _MAX_FOLLOWUPS.get(tier, 1)
    if followup_count >= max_f:
        return False, f"מקסימום פולואפים ({followup_count}/{max_f})"

    hours = _hours_since(last_active)
    if hours is None:
        return False, "לא ניתן לחשב זמן"

    threshold = _FOLLOWUP_HOURS.get(tier, 72)
    if hours < threshold:
        return False, f"עוד מוקדם ({hours:.1f}h < {threshold}h)"

    return True, f"שתיקה {hours:.1f}h (threshold={threshold}h, tier={tier})"


# ── 3. Draft ──────────────────────────────────────

def build_followup_draft(candidate: FollowupCandidate) -> str:
    tier_tpl = _TEMPLATES.get(candidate.tier, _TEMPLATES["COLD"])
    template  = tier_tpl.get(candidate.domain, tier_tpl.get("default", "שלום {name},"))
    return template.format(name=candidate.contact_name or "לקוח")


# ── 4. Approval ───────────────────────────────────

def request_followup_approval(candidate: FollowupCandidate, owner_chat_id: str) -> tuple[str, str]:
    try:
        from event_bus import bus  # type: ignore
        payload = {
            "memory_key":   candidate.memory_key,
            "channel":      candidate.contact_channel,
            "draft":        candidate.draft,
            "tier":         candidate.tier,
            "contact_name": candidate.contact_name,
        }
        label = f"📤 פולואפ → {candidate.contact_name} ({candidate.tier})"
        action_id, btn_label = bus.request_approval(
            action="send_followup", payload=payload,
            chat_id=owner_chat_id, label=label,
        )
        return action_id, btn_label
    except ImportError:
        return "dry-run", f"[DRY-RUN] {candidate.draft[:60]}"
    except Exception as e:
        logger.error(f"[Followup] approval error: {e}")
        return "", str(e)


# ── 5. Main Entry ─────────────────────────────────

def run_followup_scan(owner_chat_id: str = "") -> FollowupResult:
    """Entry point לscheduler._job_followup_scan()."""
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("FOLLOWUP_AUTOMATION"):
            logger.info("[Followup] flag OFF — skipping")
            return FollowupResult()
    except ImportError:
        logger.warning("[Followup] feature_flags not available — dev mode")

    result = FollowupResult()
    leads  = scan_active_leads()
    result.scanned = len(leads)

    for lead in leads:
        try:
            needed, reason = determine_followup_needed(lead)
            if not needed:
                result.skipped += 1
                continue

            candidate = FollowupCandidate(
                memory_key      = lead.get("memory_key", ""),
                tier            = lead.get("tier", "COLD"),
                hours_silent    = _hours_since(lead.get("last_active", "")) or 0,
                followup_count  = int(lead.get("followup_count", 0)),
                last_message    = lead.get("last_message", ""),
                contact_name    = lead.get("name", "לקוח"),
                contact_channel = lead.get("channel", "whatsapp"),
                domain          = lead.get("domain", "real_estate"),
            )
            candidate.draft = build_followup_draft(candidate)
            result.candidates.append(candidate)

            action_id, label = request_followup_approval(candidate, owner_chat_id)
            if action_id:
                result.approved += 1

        except Exception as e:
            msg = f"error {lead.get('memory_key','?')}: {e}"
            logger.error(f"[Followup] {msg}")
            result.errors.append(msg)

    logger.info(f"[Followup] scanned={result.scanned} candidates={len(result.candidates)} "
                f"approved={result.approved} skipped={result.skipped}")
    return result


# ── Self-tests ────────────────────────────────────
def _run_tests() -> bool:
    from datetime import timedelta
    now = datetime.now(tz=timezone.utc)
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    def lead(tier, hours, count=0):
        return {"tier": tier, "followup_count": count,
                "last_active": (now - timedelta(hours=hours)).isoformat()}

    ok, r = determine_followup_needed(lead("HOT", 5))
    chk(f"HOT 5h → needed ({r})", ok is True)
    ok, r = determine_followup_needed(lead("HOT", 2))
    chk(f"HOT 2h → skip ({r})",   ok is False)
    ok, r = determine_followup_needed(lead("HOT", 10, 3))
    chk(f"HOT maxed → skip ({r})", ok is False)
    ok, r = determine_followup_needed(lead("COLD", 10))
    chk(f"COLD 10h → skip ({r})", ok is False)

    c = FollowupCandidate("w:1","HOT",5,0,"","דני","whatsapp","real_estate")
    d = build_followup_draft(c)
    chk("draft not empty",         len(d) > 10)
    chk("draft contains 'דני'",    "דני" in d)

    import sys, types, importlib.util
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff
    lm = types.ModuleType("lead_memory")
    sys.modules["lead_memory"] = lm

    spec = importlib.util.spec_from_file_location("followup_engine", __file__)
    fe   = importlib.util.module_from_spec(spec)
    sys.modules["followup_engine"] = fe  # Python 3.11: dataclasses require module in sys.modules
    spec.loader.exec_module(fe)

    r = fe.run_followup_scan()
    chk("flag=OFF → scanned=0", r.scanned == 0)

    ff.is_enabled = lambda x: True
    r2 = fe.run_followup_scan("chat_id")
    chk("flag=ON → scanned>0",      r2.scanned > 0)
    chk("flag=ON → has candidates", len(r2.candidates) >= 1)
    chk("result has .approved",     hasattr(r2, "approved"))
    chk("result has .errors",       isinstance(r2.errors, list))

    print(f"\n{'='*40}")
    print(f"N02 Tests: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
