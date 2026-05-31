# core/lead_recovery.py — F01 Lead Recovery Engine
# תלוי ב: N02 (core/followup_engine.py קיים ✅)
# flag: FEATURE_LEAD_RECOVERY (כבוי ברירת מחדל)
#
# ההבדל מ-N02 Followup:
#   Followup = ליד פעיל שלא ענה 4-24h → "נמשיך את השיחה"
#   Recovery = ליד שדעך 7-14 יום      → "חזרנו לבדוק אם עדיין רלוונטי"
#
# כלל ברזל: recovery_count מקסימום 1 — פעם אחת, לא spam.
# לא שולח ללקוח בלי אישור owner.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Thresholds ───────────────────────────────────
_RECOVERY_THRESHOLD_DAYS: dict[str, int] = {
    "WARM": 7,    # warm שלא ענה שבוע
    "COLD": 14,   # cold שלא ענה שבועיים
}
_MAX_RECOVERY_ATTEMPTS = 1  # פעם אחת בלבד

# ── Templates ────────────────────────────────────
_TEMPLATES: dict[str, dict[str, str]] = {
    "WARM": {
        "realestate": "שלום {name} 😊\nהיינו בקשר לפני כמה זמן בנוגע לנכס.\nעדיין רלוונטי? נשמח לעדכן אותך בהזדמנויות חדשות.",
        "import":     "שלום {name} 😊\nדיברנו בעבר על ייבוא סחורה מסין.\nאם יש עניין מחודש — אשמח לשלוח עדכון מחירים עדכני.",
        "default":    "שלום {name} 😊\nרציתי לבדוק אם יש עניין לחדש את השיחה שלנו.",
    },
    "COLD": {
        "realestate": "שלום {name},\nאנחנו כאן אם תחליט להתקדם בחיפוש הנכס. אין לחץ 🙂",
        "import":     "שלום {name},\nאם ייבוא הפך לרלוונטי שוב — נשמח לשמוע ממך.",
        "default":    "שלום {name},\nאנחנו כאן אם תרצה לחזור לשיחה.",
    },
}


# ══════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════

@dataclass
class RecoveryCandidate:
    memory_key:     str
    name:           str
    tier:           str   # WARM / COLD (HOT לא עובר recovery)
    days_silent:    int
    last_message:   str
    domain:         str
    channel:        str
    recovery_count: int = 0
    draft:          str = ""


@dataclass
class RecoveryResult:
    scanned:    int = 0
    candidates: list[RecoveryCandidate] = field(default_factory=list)
    queued:     int = 0
    skipped:    int = 0
    errors:     list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════
# 1. Scan Dormant Leads
# ══════════════════════════════════════════════════

def scan_dormant_leads() -> list[dict]:
    """WARM/COLD שלא ענו מעל threshold. crm בלבד, לא Airtable ישיר."""
    try:
        from crm import crm_list_deals  # type: ignore
        raw = crm_list_deals()
        return _parse_leads(raw)
    except ImportError:
        logger.warning("[Recovery] crm not available — mock mode")
        return _mock_leads()
    except Exception as e:
        logger.error(f"[Recovery] scan_dormant_leads error: {e}")
        return []


def _parse_leads(raw: str) -> list[dict]:
    """Parser פשוט ל-crm_list_deals output."""
    leads = []
    if not raw or not raw.strip():
        return leads
    import re
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("─") or line.startswith("📋"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        try:
            leads.append({
                "name":           parts[0] if len(parts) > 0 else "לא ידוע",
                "tier":           parts[1].upper() if len(parts) > 1 else "COLD",
                "last_active":    parts[2] if len(parts) > 2 else "",
                "channel":        parts[3] if len(parts) > 3 else "whatsapp",
                "memory_key":     parts[4] if len(parts) > 4 else "",
                "recovery_count": int(parts[5]) if len(parts) > 5 else 0,
                "last_message":   parts[6] if len(parts) > 6 else "",
                "domain":         parts[7] if len(parts) > 7 else "realestate",
            })
        except Exception:
            continue
    return leads


def _mock_leads() -> list[dict]:
    now = datetime.now(tz=timezone.utc)
    return [
        {   # WARM 8 ימים — ראוי ל-recovery
            "name": "דני כהן", "tier": "WARM",
            "last_active": (now - timedelta(days=8)).isoformat(),
            "channel": "whatsapp", "memory_key": "whatsapp:972501111111",
            "recovery_count": 0, "last_message": "צריך לחשוב על זה",
            "domain": "realestate",
        },
        {   # COLD 15 ימים — ראוי ל-recovery
            "name": "רחל לוי", "tier": "COLD",
            "last_active": (now - timedelta(days=15)).isoformat(),
            "channel": "telegram", "memory_key": "telegram:123456789",
            "recovery_count": 0, "last_message": "אשמח לשמוע עוד",
            "domain": "import",
        },
        {   # HOT — לא recovery
            "name": "משה גרין", "tier": "HOT",
            "last_active": (now - timedelta(hours=6)).isoformat(),
            "channel": "whatsapp", "memory_key": "whatsapp:972502222222",
            "recovery_count": 0, "last_message": "מה המחיר?",
            "domain": "realestate",
        },
        {   # WARM 8 ימים אבל כבר נשלח — maxed
            "name": "יוסי אברהם", "tier": "WARM",
            "last_active": (now - timedelta(days=10)).isoformat(),
            "channel": "whatsapp", "memory_key": "whatsapp:972503333333",
            "recovery_count": 1, "last_message": "נחזור אליך",
            "domain": "realestate",
        },
    ]


# ══════════════════════════════════════════════════
# 2. Is Recoverable
# ══════════════════════════════════════════════════

def is_recoverable(lead: dict) -> tuple[bool, str]:
    """
    כלל-based: האם הליד ראוי ל-recovery?
    מחזיר (bool, reason).
    """
    tier           = lead.get("tier", "COLD").upper()
    recovery_count = int(lead.get("recovery_count", 0))
    last_active    = lead.get("last_active", "")

    # HOT לא צריך recovery
    if tier == "HOT":
        return False, "HOT lead — לא צריך recovery"

    # מקסימום ניסיונות
    if recovery_count >= _MAX_RECOVERY_ATTEMPTS:
        return False, f"כבר נשלח recovery (count={recovery_count})"

    # חישוב ימי שתיקה
    days = _days_since(last_active)
    if days is None:
        return False, "לא ניתן לחשב זמן אחרון"

    threshold = _RECOVERY_THRESHOLD_DAYS.get(tier, 999)
    if days < threshold:
        return False, f"עוד מוקדם ({days}d < {threshold}d לtier={tier})"

    return True, f"שתיקה של {days} ימים (threshold={threshold}, tier={tier})"


def _days_since(iso_str: str) -> Optional[int]:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(tz=timezone.utc) - dt).days
    except Exception:
        return None


# ══════════════════════════════════════════════════
# 3. Build Recovery Draft
# ══════════════════════════════════════════════════

def build_recovery_draft(candidate: RecoveryCandidate) -> str:
    """
    טיוטת הודעת חזרה — שונה מ-followup.
    טון: ידידותי, אין לחץ, בדיקת עניין בלבד.
    """
    tier   = candidate.tier
    domain = candidate.domain
    name   = candidate.name or "לקוח"

    tier_tpl = _TEMPLATES.get(tier, _TEMPLATES["COLD"])
    template  = tier_tpl.get(domain, tier_tpl.get("default", "שלום {name},\nרציתי לבדוק אם יש עניין לחדש קשר."))
    return template.format(name=name)


# ══════════════════════════════════════════════════
# 4. Request Approval
# ══════════════════════════════════════════════════

def request_recovery_approval(
    candidate: RecoveryCandidate,
    owner_chat_id: str,
) -> tuple[str, str]:
    """
    שולח לאישור owner דרך event_bus.
    לא שולח ללקוח!
    """
    try:
        from event_bus import bus  # type: ignore
        payload = {
            "memory_key":   candidate.memory_key,
            "channel":      candidate.channel,
            "draft":        candidate.draft,
            "tier":         candidate.tier,
            "contact_name": candidate.name,
            "action_type":  "recovery",
        }
        label = f"♻️ Recovery → {candidate.name} ({candidate.tier}, {candidate.days_silent}d)"
        action_id, btn_label = bus.request_approval(
            action  = "send_recovery",
            payload = payload,
            chat_id = owner_chat_id,
            label   = label,
        )
        logger.info(f"[Recovery] Approval requested: {action_id} for {candidate.memory_key}")
        return action_id, btn_label
    except ImportError:
        logger.warning("[Recovery] event_bus not available — dry-run")
        return "dry-run", f"[DRY-RUN] {candidate.draft[:60]}"
    except Exception as e:
        logger.error(f"[Recovery] request_approval error: {e}")
        return "", str(e)


# ══════════════════════════════════════════════════
# 5. Main Entry
# ══════════════════════════════════════════════════

def run_recovery_scan(owner_chat_id: str = "") -> RecoveryResult:
    """
    Entry point לscheduler.
    סורק → מחליט → בונה draft → שולח לאישור owner.
    """
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("LEAD_RECOVERY"):
            logger.info("[Recovery] LEAD_RECOVERY flag is OFF — skipping")
            return RecoveryResult()
    except ImportError:
        logger.warning("[Recovery] feature_flags not available — dev mode")

    result = RecoveryResult()
    leads  = scan_dormant_leads()
    result.scanned = len(leads)

    for lead in leads:
        try:
            recoverable, reason = is_recoverable(lead)
            if not recoverable:
                logger.debug(f"[Recovery] Skip {lead.get('memory_key')}: {reason}")
                result.skipped += 1
                continue

            candidate = RecoveryCandidate(
                memory_key     = lead.get("memory_key", ""),
                name           = lead.get("name", "לקוח"),
                tier           = lead.get("tier", "COLD"),
                days_silent    = _days_since(lead.get("last_active", "")) or 0,
                last_message   = lead.get("last_message", ""),
                domain         = lead.get("domain", "realestate"),
                channel        = lead.get("channel", "whatsapp"),
                recovery_count = int(lead.get("recovery_count", 0)),
            )
            candidate.draft = build_recovery_draft(candidate)
            result.candidates.append(candidate)

            action_id, label = request_recovery_approval(candidate, owner_chat_id)
            if action_id:
                result.queued += 1
                logger.info(f"[Recovery] ✅ Queued: {candidate.name} | {label}")

        except Exception as e:
            msg = f"error for {lead.get('memory_key', '?')}: {e}"
            logger.error(f"[Recovery] {msg}")
            result.errors.append(msg)

    logger.info(
        f"[Recovery] Done | scanned={result.scanned} candidates={len(result.candidates)} "
        f"queued={result.queued} skipped={result.skipped} errors={len(result.errors)}"
    )
    return result


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    from datetime import timedelta
    now = datetime.now(tz=timezone.utc)
    passed = failed = 0

    def chk(desc: str, cond: bool):
        nonlocal passed, failed
        if cond:
            print(f"✅ {desc}")
            passed += 1
        else:
            print(f"❌ {desc}")
            failed += 1

    def lead(tier, days, count=0):
        return {
            "tier": tier, "recovery_count": count,
            "last_active": (now - timedelta(days=days)).isoformat(),
            "memory_key": f"test:{tier}:{days}",
        }

    # ── is_recoverable ────────────────────────────
    ok, r = is_recoverable(lead("HOT",  5))
    chk(f"HOT → not recoverable ({r})", ok is False)

    ok, r = is_recoverable(lead("WARM", 6))
    chk(f"WARM 6d → not recoverable ({r})", ok is False)

    ok, r = is_recoverable(lead("WARM", 8))
    chk(f"WARM 8d → recoverable ({r})", ok is True)

    ok, r = is_recoverable(lead("WARM", 8, count=1))
    chk(f"WARM 8d maxed → not recoverable ({r})", ok is False)

    ok, r = is_recoverable(lead("COLD", 13))
    chk(f"COLD 13d → not recoverable ({r})", ok is False)

    ok, r = is_recoverable(lead("COLD", 15))
    chk(f"COLD 15d → recoverable ({r})", ok is True)

    # ── build_recovery_draft ──────────────────────
    c = RecoveryCandidate(
        memory_key="w:1", name="דני", tier="WARM", days_silent=8,
        last_message="", domain="realestate", channel="whatsapp",
    )
    draft = build_recovery_draft(c)
    chk("WARM/realestate draft not empty", len(draft) > 10)
    chk("WARM draft contains 'עדיין רלוונטי'", "עדיין רלוונטי" in draft)
    chk("WARM draft contains name 'דני'", "דני" in draft)

    c2 = RecoveryCandidate(
        memory_key="t:2", name="רחל", tier="COLD", days_silent=15,
        last_message="", domain="import", channel="telegram",
    )
    draft2 = build_recovery_draft(c2)
    chk("COLD/import draft not empty", len(draft2) > 10)

    # ── run_recovery_scan — flag OFF ──────────────
    import sys, types
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda x: False
    sys.modules["feature_flags"] = ff
    crm = types.ModuleType("crm")
    sys.modules["crm"] = crm

    import importlib.util
    spec = importlib.util.spec_from_file_location("lead_recovery", __file__)
    lr   = importlib.util.module_from_spec(spec)
    sys.modules["lead_recovery"] = lr   # Python 3.11: dataclasses require module in sys.modules
    spec.loader.exec_module(lr)

    result = lr.run_recovery_scan()
    chk("flag=OFF → scanned=0", result.scanned == 0)
    chk("flag=OFF → no candidates", result.candidates == [])

    # flag ON → mock leads
    ff.is_enabled = lambda x: True
    result2 = lr.run_recovery_scan(owner_chat_id="test_chat")
    chk("flag=ON → scanned > 0", result2.scanned > 0)
    chk("flag=ON → has candidates (WARM+COLD, not HOT)", len(result2.candidates) >= 1)
    chk("flag=ON → HOT skipped", result2.skipped >= 1)

    print(f"\n{'='*40}")
    print(f"F01 Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
