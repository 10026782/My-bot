# session_store.py — DB-backed Lead Session Store
# מחליף את _LRUSessionStore הקיים ב-lead_qualifier.py
# flag: תמיד פעיל — תשתית קריטית, לא אופציונלית
#
# מה זה פותר:
#   _LRUSessionStore שומר ב-RAM בלבד → Render restart = אובדן sessions
#   + אין נראות לנציג אנושי אם ליד נטש
#
# מה מוסיפים:
#   1. sync לAirtable LeadSessions בכל שלב (step-by-step)
#   2. updated_at timestamp בכל עדכון
#   3. channel consistency — שמירת ערוץ המקור
#   4. drop-off tracking — באיזה שלב נטשו
#   5. restore מDB בrestart — אפס אובדן sessions

from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_SESSIONS = 1000


# ══════════════════════════════════════════════════
# Session Schema
# ══════════════════════════════════════════════════

def _new_session(domain: str = "real_estate", channel: str = "whatsapp") -> dict:
    """session dict — מה ששמור ב-RAM וב-Airtable."""
    return {
        "domain":       domain,
        "channel":      channel,   # ← channel consistency
        "step":         0,
        "answers":      {},
        "done":         False,
        "created_at":   _now_iso(),
        "updated_at":   _now_iso(),
        "drop_off_step": None,     # ← באיזה שלב נטש (None = לא נטש)
        "record_id":    "",        # Airtable record ID
    }


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ══════════════════════════════════════════════════
# PersistentSessionStore
# ══════════════════════════════════════════════════

class PersistentSessionStore:
    """
    Session store עם:
    - LRU ב-RAM (מהיר, 1000 sessions)
    - Airtable sync בכל שלב (עמיד לrestart)
    - Drop-off tracking
    - Channel consistency
    """

    def __init__(self, maxsize: int = _MAX_SESSIONS):
        self._store: OrderedDict[str, dict] = OrderedDict()
        self._maxsize = maxsize

    # ── Read ──────────────────────────────────────

    def get(self, sender: str) -> Optional[dict]:
        """מחזיר session מRAM. אם לא נמצא — מנסה מDB."""
        if sender in self._store:
            self._store.move_to_end(sender)
            return self._store[sender]

        # נסה לטעון מAirtable (אחרי restart)
        restored = self._load_from_db(sender)
        if restored:
            self._store[sender] = restored
            logger.info(f"[SessionStore] Restored session for {sender} from DB")
            return restored

        return None

    def get_or_create(
        self,
        sender: str,
        domain: str = "real_estate",
        channel: str = "whatsapp",
    ) -> dict:
        """מחזיר קיים או יוצר חדש."""
        existing = self.get(sender)
        if existing:
            return existing
        session = _new_session(domain, channel)
        self._store[sender] = session
        self._evict_if_needed()
        self._sync_to_db(sender, session, is_new=True)
        return session

    # ── Write ─────────────────────────────────────

    def update_step(
        self,
        sender: str,
        step: int,
        field_name: str,
        answer: str,
    ) -> None:
        """
        מעדכן תשובה לשלב + updated_at + מסנכרן לDB.
        נקרא אחרי כל תשובה של הליד.
        """
        session = self.get(sender)
        if not session:
            return

        session["step"]                    = step
        session["answers"][field_name]     = answer
        session["updated_at"]              = _now_iso()
        session["drop_off_step"]           = step  # יתעדכן ל-None כשיסיים

        self._sync_to_db(sender, session)

    def mark_done(self, sender: str, score: int = 0, tier: str = "COLD") -> None:
        """מסמן session כהושלם — לא נטש."""
        session = self.get(sender)
        if not session:
            return

        session["done"]          = True
        session["drop_off_step"] = None  # הושלם — לא drop-off
        session["updated_at"]    = _now_iso()
        session["score"]         = score
        session["tier"]          = tier

        self._sync_to_db(sender, session)
        logger.info(f"[SessionStore] Session done: {sender} | tier={tier} score={score}")

    def delete(self, sender: str) -> None:
        """מוחק session (איפוס)."""
        session = self._store.pop(sender, None)
        if session and session.get("record_id"):
            self._delete_from_db(session["record_id"])

    # ── Airtable Sync ─────────────────────────────

    def _sync_to_db(self, sender: str, session: dict, is_new: bool = False) -> bool:
        """כותב/מעדכן session ב-Airtable LeadSessions."""
        try:
            from tools.airtable_tools import airtable_add, airtable_update  # type: ignore

            fields = {
                "sender":        sender,
                "domain":        session.get("domain", ""),
                "channel":       session.get("channel", ""),
                "step":          session.get("step", 0),
                "answers":       json.dumps(session.get("answers", {}), ensure_ascii=False),
                "done":          session.get("done", False),
                "drop_off_step": session.get("drop_off_step"),
                "updated_at":    session.get("updated_at", _now_iso()),
                "created_at":    session.get("created_at", _now_iso()),
                "score":         session.get("score", 0),
                "tier":          session.get("tier", ""),
            }

            if session.get("record_id"):
                result = airtable_update("LeadSessions", session["record_id"], fields)
                return "✅" in result
            else:
                result = airtable_add("LeadSessions", fields)
                if "✅" in result:
                    import re
                    m = re.search(r'rec\w+', result)
                    if m:
                        session["record_id"] = m.group(0)
                    return True
                return False

        except ImportError:
            return False  # dev — אין Airtable
        except Exception as e:
            logger.error(f"[SessionStore] sync error for {sender}: {e}")
            return False

    def _load_from_db(self, sender: str) -> Optional[dict]:
        """טוען session מAirtable לפי sender."""
        try:
            from tools.airtable_tools import airtable_get  # type: ignore
            raw = airtable_get("LeadSessions", f"{{sender}}='{sender}'")
            if not raw or "אין רשומות" in raw or "❌" in raw:
                return None

            import re
            record_m  = re.search(r'rec\w+', raw)
            step_m    = re.search(r'step[:\s]+(\d+)', raw, re.IGNORECASE)
            done_m    = re.search(r'done[:\s]+(true|false)', raw, re.IGNORECASE)
            domain_m  = re.search(r'domain[:\s]+(\w+)', raw, re.IGNORECASE)
            channel_m = re.search(r'channel[:\s]+(\w+)', raw, re.IGNORECASE)

            session = _new_session(
                domain  = domain_m.group(1)  if domain_m  else "real_estate",
                channel = channel_m.group(1) if channel_m else "whatsapp",
            )
            if step_m:   session["step"]      = int(step_m.group(1))
            if done_m:   session["done"]       = done_m.group(1).lower() == "true"
            if record_m: session["record_id"]  = record_m.group(0)
            return session

        except Exception as e:
            logger.warning(f"[SessionStore] load from DB failed for {sender}: {e}")
            return None

    def _delete_from_db(self, record_id: str) -> None:
        try:
            from tools.airtable_tools import airtable_update  # type: ignore
            airtable_update("LeadSessions", record_id, {"done": True, "deleted": True})
        except Exception:
            pass

    # ── Utils ─────────────────────────────────────

    def _evict_if_needed(self) -> None:
        while len(self._store) > self._maxsize:
            evicted_key, evicted = self._store.popitem(last=False)
            # אם לא הסתיים — סמן כdrop-off לפני פינוי
            if not evicted.get("done"):
                evicted["drop_off_step"] = evicted.get("step", 0)
                self._sync_to_db(evicted_key, evicted)

    def get_all_active(self) -> list[tuple[str, dict]]:
        """כל הsessions הפעילים ב-RAM."""
        return [
            (k, v) for k, v in self._store.items()
            if not v.get("done")
        ]


# ── Singleton ─────────────────────────────────────
lead_sessions = PersistentSessionStore()


# ══════════════════════════════════════════════════
# Self-tests
# ══════════════════════════════════════════════════

def _run_tests() -> bool:
    import sys, types
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond: print(f"✅ {desc}"); passed += 1
        else:    print(f"❌ {desc}"); failed += 1

    # mock airtable
    at = types.ModuleType("airtable_tools")
    saves = []
    at.airtable_add    = lambda t, f: (saves.append(f), "✅ rec001")[1]
    at.airtable_update = lambda t, r, f: (saves.append(f), "✅")[1]
    at.airtable_get    = lambda t, formula: "אין רשומות"
    sys.modules["airtable_tools"] = at

    store = PersistentSessionStore(maxsize=5)

    # ── get_or_create ─────────────────────────────
    s1 = store.get_or_create("w:001", "real_estate", "whatsapp")
    chk("session created",           isinstance(s1, dict))
    chk("channel saved",             s1["channel"] == "whatsapp")
    chk("domain saved",              s1["domain"] == "real_estate")
    chk("step = 0",                  s1["step"] == 0)
    chk("airtable_add called",       len(saves) >= 1)

    # ── same session on 2nd call ──────────────────
    s1b = store.get_or_create("w:001", "real_estate", "whatsapp")
    chk("same session returned",     s1b is s1)

    # ── update_step ───────────────────────────────
    saves.clear()
    store.update_step("w:001", step=1, field_name="domain", answer="נדל\"ן")
    chk("answer saved",              s1["answers"].get("domain") == "נדל\"ן")
    chk("step updated to 1",         s1["step"] == 1)
    chk("updated_at refreshed",      s1["updated_at"] >= s1["created_at"])
    chk("drop_off_step = 1",         s1["drop_off_step"] == 1)
    chk("airtable sync called",      len(saves) >= 1)

    # ── mark_done ─────────────────────────────────
    store.mark_done("w:001", score=75, tier="HOT")
    chk("done = True",               s1["done"] is True)
    chk("drop_off_step = None",      s1["drop_off_step"] is None)
    chk("score saved",               s1.get("score") == 75)
    chk("tier saved",                s1.get("tier") == "HOT")

    # ── channel consistency ───────────────────────
    s2 = store.get_or_create("t:111", "import", "telegram")
    chk("telegram channel",          s2["channel"] == "telegram")
    s3 = store.get_or_create("e:abc@test.com", "general", "email")
    chk("email channel",             s3["channel"] == "email")

    # ── delete ────────────────────────────────────
    store.get_or_create("w:del", "real_estate", "whatsapp")
    store.delete("w:del")
    chk("deleted from store",        store.get("w:del") is None)

    # ── LRU eviction ─────────────────────────────
    store2 = PersistentSessionStore(maxsize=3)
    for i in range(4):
        store2.get_or_create(f"w:{i}", "real_estate", "whatsapp")
    chk("newest still there",        "w:3" in store2._store)

    # ── get_all_active ────────────────────────────
    active = store.get_all_active()
    chk("active list excludes done", all(not v.get("done") for _, v in active))

    print(f"\n{'='*40}")
    print(f"SessionStore Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
