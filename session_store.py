# session_store.py — DB-backed Universal Session Store
# מחליף את _LRUSessionStore הקיים ב-lead_qualifier.py
# flag: תמיד פעיל — תשתית קריטית, לא אופציונלית
#
# מה זה פותר:
#   _LRUSessionStore שומר ב-RAM בלבד → Render restart = אובדן sessions
#   + אין נראות לנציג אנושי אם ליד נטש
#
# מה מוסיפים:
#   1. sync לAirtable Sessions בכל שלב (step-by-step) — C58, ראה SPEC_C58_Universal_Sessions.md
#   2. updated_at timestamp בכל עדכון
#   3. channel consistency — שמירת ערוץ המקור
#   4. drop-off tracking — באיזה שלב נטשו
#   5. restore מDB בrestart — אפס אובדן sessions
#
# C58 — Universal Sessions: כתיבה ל-Tables.SESSIONS (טבלה קיימת, tblHLfE24lTkVUhz0),
# לא ל-Tables.LEAD_SESSIONS (לא קיימה בפועל ב-Airtable — 403). State JSON מחזיק את כל
# ה-state הקיים בשדה יחיד; context_type="lead" כברירת מחדל לתאימות לאחור.

from __future__ import annotations

import json
import logging
import re
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from airtable_schema import SessionsFields as SF, Tables

logger = logging.getLogger(__name__)

_MAX_SESSIONS = 1000


# ══════════════════════════════════════════════════
# Session Schema
# ══════════════════════════════════════════════════

def _new_session(domain: str = "real_estate", channel: str = "whatsapp") -> dict:
    """session dict — מה ששמור ב-RAM וב-Airtable (Tables.SESSIONS, ראה C58)."""
    return {
        "context_type": "lead",    # C58: Sessions היא טבלה גנרית; "lead" = תאימות לאחור
        "domain":       domain,
        "channel":      channel,   # ← channel consistency
        "step":         0,
        "answers":      {},
        "done":         False,
        "created_at":   _now_iso(),
        "updated_at":   _now_iso(),
        "drop_off_step": None,     # ← באיזה שלב נטש (None = לא נטש)
        "record_id":    "",        # Airtable record ID (של רשומת ה-Session עצמה)
        "last_uploaded_file": None,  # ← FileUploadResult dict, ראה Stage 0.6
        "last_tool_result":   None,  # ← dict, ראה C60 (Tool Context Awareness)
        "current_lead_record_id": "",  # ← BUG-NEW-09: ה-record_id האמיתי של הליד
                                        # (לא של רשומת ה-Session) — מונע פברוק record_id בסבבים הבאים
    }


# ══════════════════════════════════════════════════
# FileUploadResult — Stage 0.6 (SPEC_File_Context_Reference.md)
# ══════════════════════════════════════════════════

@dataclass
class FileUploadResult:
    """תוצאת העלאת קובץ גנרית — מקור Drive או Decision Inbox.
    מ-C58 ואילך: נשמר בתוך State JSON (Tables.SESSIONS) — לא עוד RAM-only.
    type="drive_file" → file_id הוא record ID בטבלת Media Files, מקושר גם
    דרך SF.LINKED_MEDIA_FILE. type="inbox_file" → file_id הוא record ID
    ב-Decision Inbox (טבלה אחרת) — לא מקושר דרך LINKED_MEDIA_FILE כדי לא
    לכתוב record ID מטבלה לא נכונה לשדה linked-record (INVALID_RECORD_ID).
    """
    type: str               # "drive_file" | "inbox_file"
    url: str = ""
    file_id: str = ""
    original_filename: str = ""
    timestamp: str = ""
    conversation_id: str = ""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _extract_balanced_json(raw: str, field_label: str) -> Optional[dict]:
    """
    מחלץ אובייקט JSON מתוך airtable_get()'s formatted string output, לפי שם שדה.
    סופר עומק סוגריים (לא regex naive) כי State JSON מכיל אובייקטים מקוננים
    (answers) ואין הבטחה לסדר שדות עקבי בפלט של Airtable.
    """
    marker = f"{field_label}: {{"
    idx = raw.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker) - 1  # מיקום ה-{ הפותח
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


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

    def set_last_file(
        self,
        sender: str,
        result: FileUploadResult,
        domain: str = "real_estate",
        channel: str = "whatsapp",
    ) -> None:
        """
        שומר את הקובץ האחרון שהועלה — לשימוש ע"י "זה הנספח" וכד'.
        מ-C58 ואילך נכתב גם ל-Airtable (תוך State JSON, ראה FileUploadResult docstring).
        """
        session = self.get_or_create(sender, domain, channel)
        session["last_uploaded_file"] = asdict(result)
        session["updated_at"]         = _now_iso()
        self._sync_to_db(sender, session)

    def get_last_file(self, sender: str) -> Optional[dict]:
        """מחזיר את ה-FileUploadResult (כdict) האחרון, אם קיים."""
        session = self.get(sender)
        if not session:
            return None
        return session.get("last_uploaded_file")

    def set_last_tool_result(self, sender: str, result: dict) -> None:
        """שומר את תוצאת הכלי האחרונה — לתיקון 'עיוורון כלים' בין סבבי agent (C60).
        מבנה result: {tool, status, summary, record_id, url, input, timestamp}."""
        session = self.get_or_create(sender)
        session["last_tool_result"] = result
        session["updated_at"]       = _now_iso()
        self._sync_to_db(sender, session)

    def get_last_tool_result(self, sender: str) -> Optional[dict]:
        """מחזיר את תוצאת הכלי האחרונה, אם קיימת (C60)."""
        session = self.get(sender)
        if not session:
            return None
        return session.get("last_tool_result")

    def set_current_lead_record_id(self, sender: str, record_id: str) -> None:
        """שומר את ה-record_id האמיתי של הליד (Tables.LEADS) על ה-Session (BUG-NEW-09).
        חובה record_id אמיתי שמתחיל ב-'rec' — אסור לשמור id מפוברק."""
        if not record_id or not str(record_id).startswith("rec"):
            return
        session = self.get_or_create(sender)
        session["current_lead_record_id"] = record_id
        session["updated_at"]             = _now_iso()
        self._sync_to_db(sender, session)

    def get_current_lead_record_id(self, sender: str) -> Optional[str]:
        """מחזיר את ה-record_id האמיתי של הליד הנוכחי, אם קיים (BUG-NEW-09)."""
        session = self.get(sender)
        if not session:
            return None
        return session.get("current_lead_record_id") or None

    def delete(self, sender: str) -> None:
        """מוחק session (איפוס)."""
        session = self._store.pop(sender, None)
        if session and session.get("record_id"):
            self._delete_from_db(session["record_id"], session)

    # ── Airtable Sync (C58 — Tables.SESSIONS) ─────

    def _sync_to_db(self, sender: str, session: dict, is_new: bool = False) -> bool:
        """כותב/מעדכן session ב-Airtable Sessions (State JSON + linked fields, ראה C58)."""
        try:
            from tools.airtable_tools import airtable_add, airtable_update  # type: ignore

            state = {
                "domain":             session.get("domain", ""),
                "step":               session.get("step", 0),
                "answers":            session.get("answers", {}),
                "done":               session.get("done", False),
                "drop_off_step":      session.get("drop_off_step"),
                "score":              session.get("score", 0),
                "tier":               session.get("tier", ""),
                "last_uploaded_file": session.get("last_uploaded_file"),
                "last_tool_result":   session.get("last_tool_result"),
                "current_lead_record_id": session.get("current_lead_record_id", ""),
            }
            fields = {
                SF.SENDER_ID:    sender,
                SF.CONTEXT_TYPE: session.get("context_type", "lead"),
                SF.CHANNEL:      session.get("channel", ""),
                SF.STATE_JSON:   json.dumps(state, ensure_ascii=False),
                SF.UPDATED_AT:   session.get("updated_at", _now_iso()),
                SF.CREATED_AT:   session.get("created_at", _now_iso()),
            }

            # קישורים אופציונליים — רק אם קיימים ב-session:
            _linked_lead = session.get("lead_record_id") or session.get("current_lead_record_id")
            if _linked_lead:
                fields[SF.LINKED_LEAD] = [_linked_lead]
            if session.get("decision_record_id"):
                fields[SF.LINKED_DECISION] = [session["decision_record_id"]]
            last_file = session.get("last_uploaded_file") or {}
            # רק drive_file → Media Files record; inbox_file → Decision Inbox record
            # (טבלה אחרת — קישור דרך LINKED_MEDIA_FILE היה גורם ל-INVALID_RECORD_ID).
            if last_file.get("type") == "drive_file" and last_file.get("file_id"):
                fields[SF.LINKED_MEDIA_FILE] = [last_file["file_id"]]

            if session.get("record_id"):
                result = airtable_update(Tables.SESSIONS, session["record_id"], fields)
                return bool(result.get("ok"))

            # BUG-NEW-12: record_id ריק לא בהכרח אומר "session חדש" — ייתכן
            # parse miss ב-_load_from_db (ראה שם) על session שכבר קיים ב-Airtable.
            # לפני POST, בדיקה חיה אחרונה (mirror של inbound_handler._find_by_sender)
            # שמונעת רשומה כפולה.
            existing_id = self._find_record_id_in_db(sender)
            if existing_id:
                session["record_id"] = existing_id
                result = airtable_update(Tables.SESSIONS, existing_id, fields)
                return bool(result.get("ok"))

            result = airtable_add(Tables.SESSIONS, fields)
            if result.get("ok"):
                session["record_id"] = result.get("external_id", "")
                return True
            return False

        except ImportError:
            return False  # dev — אין Airtable
        except Exception as e:
            logger.error(f"[SessionStore] sync error for {sender}: {e}")
            return False

    def _find_record_id_in_db(self, sender: str) -> Optional[str]:
        """בדיקה חיה: האם כבר קיימת רשומת Sessions עבור sender זה ב-Airtable?
        regex סלחני (כמו inbound_handler._find_by_sender) — לא תלוי בסוגריים
        מרובעים מדויקים, כדי לא להחמיץ רשומה קיימת ולגרום ל-POST כפול (BUG-NEW-12)."""
        try:
            from tools.airtable_tools import airtable_get  # type: ignore
            raw = airtable_get(Tables.SESSIONS, f"{{{SF.SENDER_ID}}}='{sender}'")
            if not raw or "אין רשומות" in raw or "❌" in raw:
                return None
            m = re.search(r"rec\w+", raw)
            return m.group(0) if m else None
        except Exception as e:
            logger.warning(f"[SessionStore] live dedup check failed for {sender}: {e}")
            return None

    def _load_from_db(self, sender: str) -> Optional[dict]:
        """טוען session מ-Airtable Sessions לפי Sender ID."""
        try:
            from tools.airtable_tools import airtable_get  # type: ignore
            raw = airtable_get(Tables.SESSIONS, f"{{{SF.SENDER_ID}}}='{sender}'")
            if not raw or "אין רשומות" in raw or "❌" in raw:
                return None

            record_m  = re.search(r'rec\w+', raw)
            context_m = re.search(rf'{re.escape(SF.CONTEXT_TYPE)}:\s*([^|]+)', raw)
            channel_m = re.search(rf'{re.escape(SF.CHANNEL)}:\s*([^|]+)', raw)
            state     = _extract_balanced_json(raw, SF.STATE_JSON) or {}

            session = _new_session(
                domain  = state.get("domain") or "real_estate",
                channel = (channel_m.group(1).strip() if channel_m else "whatsapp"),
            )
            session["context_type"]     = context_m.group(1).strip() if context_m else "lead"
            session["step"]             = state.get("step", 0)
            session["answers"]          = state.get("answers", {})
            session["done"]             = state.get("done", False)
            session["drop_off_step"]    = state.get("drop_off_step")
            session["score"]            = state.get("score", 0)
            session["tier"]             = state.get("tier", "")
            session["last_uploaded_file"] = state.get("last_uploaded_file")
            session["last_tool_result"]   = state.get("last_tool_result")
            session["current_lead_record_id"] = state.get("current_lead_record_id", "")
            if record_m:
                session["record_id"] = record_m.group(0)
            return session

        except Exception as e:
            logger.warning(f"[SessionStore] load from DB failed for {sender}: {e}")
            return None

    def _delete_from_db(self, record_id: str, session: Optional[dict] = None) -> None:
        """מסמן session כ-done+deleted ב-State JSON (אין שדות done/deleted נפרדים ב-Sessions)."""
        try:
            from tools.airtable_tools import airtable_update  # type: ignore
            session = session or {}
            state = {
                "domain":             session.get("domain", ""),
                "step":               session.get("step", 0),
                "answers":            session.get("answers", {}),
                "done":               True,
                "deleted":            True,
                "drop_off_step":      session.get("drop_off_step"),
                "score":              session.get("score", 0),
                "tier":               session.get("tier", ""),
                "last_uploaded_file": session.get("last_uploaded_file"),
                "last_tool_result":   session.get("last_tool_result"),
            }
            airtable_update(Tables.SESSIONS, record_id, {SF.STATE_JSON: json.dumps(state, ensure_ascii=False)})
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

    # mock tools.airtable_tools — must match the real import path
    # (`from tools.airtable_tools import ...`), not the bare module name.
    tools_pkg = types.ModuleType("tools")
    at = types.ModuleType("tools.airtable_tools")
    saves = []
    at.airtable_add    = lambda t, f: (saves.append(f), {"ok": True, "external_id": "rec001"})[1]
    at.airtable_update = lambda t, r, f: (saves.append(f), {"ok": True, "external_id": r})[1]
    at.airtable_get    = lambda t, formula: "אין רשומות"
    tools_pkg.airtable_tools = at
    sys.modules["tools"] = tools_pkg
    sys.modules["tools.airtable_tools"] = at

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

    # ── C58: context_type default ─────────────────
    chk("context_type defaults to 'lead'", s1["context_type"] == "lead")

    # ── C58: _extract_balanced_json (nested objects) ──
    nested_raw = (
        'State JSON: {"domain": "real_estate", "answers": {"city": "תל אביב", '
        '"budget": {"min": 100, "max": 200}}, "step": 2} | Other Field: x'
    )
    parsed = _extract_balanced_json(nested_raw, SF.STATE_JSON)
    chk("balanced-json: parses nested object",      parsed is not None)
    chk("balanced-json: nested answers preserved",   parsed.get("answers", {}).get("budget") == {"min": 100, "max": 200})
    chk("balanced-json: missing field returns None", _extract_balanced_json(nested_raw, "No Such Field") is None)

    # ── C58: _sync_to_db State JSON structure (no info loss) ──
    saves.clear()
    store.mark_done("w:001", score=80, tier="HOT")
    last_fields = saves[-1]
    chk("sync: Context Type field present",  last_fields.get(SF.CONTEXT_TYPE) == "lead")
    synced_state = json.loads(last_fields[SF.STATE_JSON])
    chk("sync: State JSON carries score",            synced_state.get("score") == 80)
    chk("sync: State JSON carries last_uploaded_file key", "last_uploaded_file" in synced_state)

    # ── C58: drive_file vs inbox_file → LINKED_MEDIA_FILE gating ──
    saves.clear()
    store.set_last_file(
        "w:001",
        FileUploadResult(type="drive_file", url="https://x/y", file_id="recMEDIA1",
                          original_filename="a.pdf", timestamp=_now_iso()),
    )
    chk("drive_file: LINKED_MEDIA_FILE set", saves[-1].get(SF.LINKED_MEDIA_FILE) == ["recMEDIA1"])

    saves.clear()
    store.set_last_file(
        "w:001",
        FileUploadResult(type="inbox_file", url="", file_id="recINBOX1",
                          original_filename="b.pdf", timestamp=_now_iso()),
    )
    chk("inbox_file: LINKED_MEDIA_FILE NOT set", SF.LINKED_MEDIA_FILE not in saves[-1])

    # ── C58: _load_from_db round-trip (realistic airtable_get format) ──
    fabricated_state = {
        "domain": "real_estate", "step": 3,
        "answers": {"city": "ירושלים", "budget": {"min": 1, "max": 2}},
        "done": False, "drop_off_step": 3, "score": 55, "tier": "WARM",
        "last_uploaded_file": {"type": "drive_file", "file_id": "recMEDIA9"},
    }
    fabricated_raw = (
        f"📊 Sessions — 1 רשומות:\n"
        f"• [recRESTORE1] {SF.SENDER_ID}: w:restore | {SF.CONTEXT_TYPE}: lead | "
        f"{SF.CHANNEL}: telegram | {SF.STATE_JSON}: {json.dumps(fabricated_state, ensure_ascii=False)} | "
        f"{SF.UPDATED_AT}: 2026-01-01T00:00:00+00:00 | {SF.CREATED_AT}: 2026-01-01T00:00:00+00:00\n"
    )
    at.airtable_get = lambda t, formula: fabricated_raw
    restored = store.get("w:restore")
    chk("restore: session found",            restored is not None)
    chk("restore: record_id parsed",          restored.get("record_id") == "recRESTORE1")
    chk("restore: channel parsed",            restored.get("channel") == "telegram")
    chk("restore: context_type parsed",       restored.get("context_type") == "lead")
    chk("restore: nested answers preserved",  restored.get("answers", {}).get("budget") == {"min": 1, "max": 2})
    chk("restore: score/tier preserved",      restored.get("score") == 55 and restored.get("tier") == "WARM")
    chk("restore: last_uploaded_file preserved", restored.get("last_uploaded_file", {}).get("file_id") == "recMEDIA9")
    at.airtable_get = lambda t, formula: "אין רשומות"

    # ── C60: set_last_tool_result / get_last_tool_result ──
    saves.clear()
    store.set_last_tool_result("w:001", {
        "tool": "save_to_decision_inbox", "status": "success",
        "summary": "נשמר ב-Decision Inbox", "record_id": "rec123",
        "url": "", "input": "forward מעורך דין", "timestamp": _now_iso(),
    })
    chk("last_tool_result saved in RAM",
        store.get("w:001").get("last_tool_result", {}).get("tool") == "save_to_decision_inbox")
    chk("get_last_tool_result returns it",
        store.get_last_tool_result("w:001").get("record_id") == "rec123")
    chk("sync includes last_tool_result",
        json.loads(saves[-1][SF.STATE_JSON]).get("last_tool_result", {}).get("status") == "success")

    chk("get_last_tool_result: no session → None",
        store.get_last_tool_result("w:never-existed") is None)

    # ── BUG-NEW-09: current_lead_record_id persistence ──
    saves.clear()
    at.airtable_get = lambda t, formula: "אין רשומות"
    store.set_current_lead_record_id("w:001", "recLEAD123")
    chk("current_lead_record_id saved in RAM",
        store.get("w:001").get("current_lead_record_id") == "recLEAD123")
    chk("get_current_lead_record_id returns it",
        store.get_current_lead_record_id("w:001") == "recLEAD123")
    chk("sync includes current_lead_record_id",
        json.loads(saves[-1][SF.STATE_JSON]).get("current_lead_record_id") == "recLEAD123")
    store.set_current_lead_record_id("w:001", "NOT_A_REAL_ID")
    chk("non-rec id ignored — previous value kept",
        store.get_current_lead_record_id("w:001") == "recLEAD123")

    # ── BUG-NEW-12: session duplication — N existing Sessions rows for the
    # same sender must result in exactly one PATCH, zero POST. ──
    store3 = PersistentSessionStore(maxsize=5)
    add_calls = []
    update_calls = []
    at.airtable_add    = lambda t, f: (add_calls.append(f), {"ok": True, "external_id": "recNEW999"})[1]
    at.airtable_update = lambda t, r, f: (update_calls.append((r, f)), {"ok": True, "external_id": r})[1]
    # simulate: RAM is empty (fresh process), but Airtable already has an
    # existing Sessions record for this sender (e.g. from a prior call whose
    # _load_from_db parse silently missed it — record_id stayed "").
    at.airtable_get = lambda t, formula: "📊 Sessions — 4 רשומות:\n• [recDUP1] ...\n"
    session_dup = _new_session("real_estate", "whatsapp")  # record_id == "" deliberately
    store3._store["w:dup"] = session_dup
    store3._sync_to_db("w:dup", session_dup)
    chk("dedup: live check found existing record → PATCH used",
        len(update_calls) == 1 and update_calls[0][0] == "recDUP1")
    chk("dedup: no duplicate POST issued",
        len(add_calls) == 0)
    chk("dedup: session record_id healed after live check",
        session_dup.get("record_id") == "recDUP1")
    at.airtable_get = lambda t, formula: "אין רשומות"

    print(f"\n{'='*40}")
    print(f"SessionStore Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
