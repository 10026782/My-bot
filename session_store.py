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
import threading
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
        "active_lead_candidate": None, # ← BUG-NEW-10/Section 4B: ליד שה-owner מכתיב, TTL 30 דקות
        "last_lead_candidate_batch": None,   # ← Section 4C: batch dictation state for follow-up routing
        "pending_lead_preview":     None,   # ← C89: preview candidates awaiting confirmation (FEATURE_AUTO_CAPTURE=OFF)
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


def _normalize_sender(sender: object) -> str:
    """Canonical representation used for cache keys and Airtable Sender ID."""
    return str(sender).strip()


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
        # BUG-NEW-12: get_or_create is GET-then-POST — without a lock, two
        # concurrent calls for the same sender can both miss RAM+DB and
        # both create+sync a session, producing duplicate Airtable rows.
        self._create_lock = threading.Lock()

    # ── Read ──────────────────────────────────────

    def get(self, sender: str) -> Optional[dict]:
        """מחזיר session מRAM. אם לא נמצא — מנסה מDB."""
        sender = _normalize_sender(sender)
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
        sender = _normalize_sender(sender)
        existing = self.get(sender)
        if existing:
            return existing
        with self._create_lock:
            # Re-check under the lock — another thread may have created
            # (and synced) the session while we were waiting for it.
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

    def set_active_lead_candidate(self, sender: str, name: str, record_id: str = "") -> None:
        """שומר candidate ליד פעיל עם TTL 30 דקות (BUG-NEW-10/Section 4B)."""
        import time as _time
        session = self.get(sender)
        if session is None:
            return
        session["active_lead_candidate"] = {
            "name":      name,
            "record_id": record_id,
            "set_at":    _time.time(),
        }
        session["updated_at"] = _now_iso()
        self._sync_to_db(sender, session)

    def get_active_lead_candidate(self, sender: str) -> Optional[dict]:
        """מחזיר candidate פעיל אם לא פג תוקפו (>1800 שניות), אחרת None."""
        import time as _time
        session = self.get(sender)
        if not session:
            return None
        cand = session.get("active_lead_candidate")
        if not cand:
            return None
        if _time.time() - cand.get("set_at", 0) > 1800:
            session["active_lead_candidate"] = None
            return None
        return cand

    def set_pending_lead_preview(
        self, sender: str, candidates: list[dict], raw_text: str,
        channel: str, domain: str,
    ) -> None:
        """שומר preview של batch (Tier 2) עם TTL 30 דקות — BUG-058 resolver.
        channel/domain נשמרים כאן כי ב-app.py section 2.55 (נקודת ה-resolve)
        ה-Router עוד לא רץ — אין resolved_route_domain זמין שם. נשמרים בזמן
        הכתיבה (_handle_clean_batch כבר מקבל את שניהם), לא מבוקשים מחדש."""
        import time as _time
        session = self.get_or_create(sender)
        session["pending_lead_preview"] = {
            "candidates": candidates,
            "raw_text":   raw_text,
            "channel":    channel,
            "domain":     domain,
            "set_at":     _time.time(),
        }
        session["updated_at"] = _now_iso()
        self._sync_to_db(sender, session)

    def get_pending_lead_preview(self, sender: str) -> Optional[dict]:
        """מחזיר pending_lead_preview אם לא פג תוקפו (>1800 שניות), אחרת None.
        בניגוד ל-get_active_lead_candidate(): קורא ל-_sync_to_db() גם אחרי ניקוי
        expired state — preview עם לידים לא-נכתבים לא אמור להישאר רפאים ב-DB."""
        import time as _time
        session = self.get(sender)
        if not session:
            return None
        preview = session.get("pending_lead_preview")
        if not preview:
            return None
        if _time.time() - preview.get("set_at", 0) > 1800:
            session["pending_lead_preview"] = None
            self._sync_to_db(sender, session)
            return None
        return preview

    def clear_pending_lead_preview(self, sender: str) -> None:
        """מנקה pending_lead_preview אחרי אישור/ביטול/מימוש."""
        session = self.get(sender)
        if not session:
            return
        session["pending_lead_preview"] = None
        session["updated_at"] = _now_iso()
        self._sync_to_db(sender, session)

    def delete(self, sender: str) -> None:
        """מוחק session (איפוס)."""
        sender = _normalize_sender(sender)
        session = self._store.pop(sender, None)
        if session and session.get("record_id"):
            self._delete_from_db(session["record_id"], session)

    # ── Airtable Sync (C58 — Tables.SESSIONS) ─────

    def _sync_to_db(self, sender: str, session: dict, is_new: bool = False) -> bool:
        """כותב/מעדכן session ב-Airtable Sessions (State JSON + linked fields, ראה C58)."""
        sender = _normalize_sender(sender)
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
                "active_lead_candidate":  session.get("active_lead_candidate"),
                "last_lead_candidate_batch": session.get("last_lead_candidate_batch"),
                "pending_lead_preview":     session.get("pending_lead_preview"),
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

            # BUG-NEW-12: record_id ריק ≠ "session חדש" — _load_from_db אולי פספס.
            # בדיקה חיה לפני כל POST. אם נמצאה רשומה → תמיד PATCH, אפס POST.
            existing_id, found_count, reason = self._find_best_session_in_db(sender)
            if existing_id:
                session["record_id"] = existing_id
                result = airtable_update(Tables.SESSIONS, existing_id, fields)
                logger.info(
                    "[SessionStore] lookup sender=%s found_count=%d selected=%s action=patch_existing",
                    sender, found_count, existing_id,
                )
                return bool(result.get("ok"))

            # A lookup failure is not proof that a record does not exist.
            # POST is allowed only after a successful zero-record lookup.
            if found_count != 0 or reason != "no_records":
                logger.error(
                    "[SessionStore] lookup sender=%s found_count=%d selected=None action=abort_create reason=%s",
                    sender, found_count, reason,
                )
                return False

            result = airtable_add(Tables.SESSIONS, fields)
            if result.get("ok"):
                session["record_id"] = result.get("external_id", "")
                logger.info(
                    "[SessionStore] sync sender=%s found_count=0 action=create_new new_id=%s",
                    sender, session["record_id"],
                )
                return True
            return False

        except ImportError:
            return False  # dev — אין Airtable
        except Exception as e:
            logger.error(f"[SessionStore] sync error for {sender}: {e}")
            return False

    @staticmethod
    def _validated_records(sender: str, raw_records: object) -> Optional[list[dict]]:
        """Validate a structured lookup without silently dropping rows."""
        if not isinstance(raw_records, list):
            logger.error(
                "SESSION_LOOKUP_CONTRACT_MISMATCH sender=%s raw_count=unknown parsed_count=0",
                sender,
            )
            return None

        parsed = [
            record for record in raw_records
            if isinstance(record, dict)
            and isinstance(record.get("id"), str)
            and record["id"].startswith("rec")
            and isinstance(record.get("fields", {}), dict)
        ]
        if len(parsed) != len(raw_records):
            logger.error(
                "SESSION_LOOKUP_CONTRACT_MISMATCH sender=%s raw_count=%d parsed_count=%d",
                sender, len(raw_records), len(parsed),
            )
            return None
        return parsed

    def _find_best_session_in_db(
        self, sender: str
    ) -> tuple[Optional[str], int, str]:
        """Select an existing Session from the structured Airtable response."""
        sender = _normalize_sender(sender)
        try:
            from tools.airtable_tools import airtable_get_records  # type: ignore

            raw_records = airtable_get_records(
                Tables.SESSIONS, f"{{{SF.SENDER_ID}}}='{sender}'"
            )
            records = self._validated_records(sender, raw_records)
            if records is None:
                raw_count = len(raw_records) if isinstance(raw_records, list) else -1
                return None, raw_count, "contract_mismatch"
            if not records:
                logger.info(
                    "[SessionStore] lookup sender=%s found_count=0 selected=None action=create_new reason=no_records",
                    sender,
                )
                return None, 0, "no_records"

            selected = records[0]["id"]
            return selected, len(records), "patch_existing"
        except Exception as exc:
            logger.warning("[SessionStore] live dedup check failed for %s: %s", sender, exc)
            return None, -1, f"error: {exc}"

    def _find_record_id_in_db(self, sender: str) -> Optional[str]:
        """Legacy wrapper — מחזיר record_id בלבד (ראה _find_best_session_in_db)."""
        record_id, _, _ = self._find_best_session_in_db(sender)
        return record_id

    def _load_from_db(self, sender: str) -> Optional[dict]:
        """Restore one Session from the structured Airtable response."""
        sender = _normalize_sender(sender)
        try:
            from tools.airtable_tools import airtable_get_records  # type: ignore

            raw_records = airtable_get_records(
                Tables.SESSIONS, f"{{{SF.SENDER_ID}}}='{sender}'"
            )
            records = self._validated_records(sender, raw_records)
            if records is None or not records:
                return None

            record = records[0]
            record_id = record["id"]
            if len(records) > 1:
                logger.warning(
                    "[SessionStore] load sender=%s found_count=%d -- using first: %s",
                    sender, len(records), record_id,
                )

            fields = record.get("fields", {})
            state_raw = fields.get(SF.STATE_JSON, {})
            if isinstance(state_raw, str):
                try:
                    state = json.loads(state_raw)
                except json.JSONDecodeError:
                    state = {}
            else:
                state = state_raw if isinstance(state_raw, dict) else {}

            session = _new_session(
                domain=state.get("domain") or "real_estate",
                channel=str(fields.get(SF.CHANNEL) or "whatsapp").strip(),
            )
            session["context_type"] = str(
                fields.get(SF.CONTEXT_TYPE) or "lead"
            ).strip()
            for key, default in (
                ("step", 0),
                ("answers", {}),
                ("done", False),
                ("drop_off_step", None),
                ("score", 0),
                ("tier", ""),
                ("last_uploaded_file", None),
                ("last_tool_result", None),
                ("current_lead_record_id", ""),
                ("active_lead_candidate", None),
                ("last_lead_candidate_batch", None),
                ("pending_lead_preview", None),
            ):
                session[key] = state.get(key, default)
            session["record_id"] = record_id
            return session
        except Exception as exc:
            logger.warning("[SessionStore] load from DB failed for %s: %s", sender, exc)
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
            result = airtable_update(Tables.SESSIONS, record_id, {SF.STATE_JSON: json.dumps(state, ensure_ascii=False)})
            if not result.get("ok"):
                logger.warning("[SessionStore] _delete_from_db not ok for record_id=%s: %s", record_id, result.get("user_message", result))
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
    at.airtable_get_records = lambda t, formula: []
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
    at.airtable_get_records = lambda t, formula: [{
        "id": "recRESTORE1",
        "fields": {
            SF.SENDER_ID: "w:restore",
            SF.CONTEXT_TYPE: "lead",
            SF.CHANNEL: "telegram",
            SF.STATE_JSON: json.dumps(fabricated_state, ensure_ascii=False),
        },
    }]
    restored = store.get("w:restore")
    chk("restore: session found",            restored is not None)
    chk("restore: record_id parsed",          restored.get("record_id") == "recRESTORE1")
    chk("restore: channel parsed",            restored.get("channel") == "telegram")
    chk("restore: context_type parsed",       restored.get("context_type") == "lead")
    chk("restore: nested answers preserved",  restored.get("answers", {}).get("budget") == {"min": 1, "max": 2})
    chk("restore: score/tier preserved",      restored.get("score") == 55 and restored.get("tier") == "WARM")
    chk("restore: last_uploaded_file preserved", restored.get("last_uploaded_file", {}).get("file_id") == "recMEDIA9")
    at.airtable_get = lambda t, formula: "אין רשומות"
    at.airtable_get_records = lambda t, formula: []

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

    # ── BUG-NEW-12: N existing Sessions rows for same sender → exactly one PATCH, zero POST ──
    store3 = PersistentSessionStore(maxsize=5)
    add_calls = []
    update_calls = []
    at.airtable_add    = lambda t, f: (add_calls.append(f), {"ok": True, "external_id": "recNEW999"})[1]
    at.airtable_update = lambda t, r, f: (update_calls.append((r, f)), {"ok": True, "external_id": r})[1]

    # 14 duplicate records for same sender — common production failure mode
    dup14_raw = (
        "📊 Sessions — 14 רשומות:\n"
        + "".join(f"• [recDUP{i}] Sender ID: w:dup | ...\n" for i in range(1, 15))
    )
    at.airtable_get = lambda t, formula: dup14_raw
    at.airtable_get_records = lambda t, formula: [
        {"id": f"recDUP{i}", "fields": {SF.SENDER_ID: "w:dup"}}
        for i in range(1, 15)
    ]

    session_dup = _new_session("real_estate", "whatsapp")  # record_id == "" (parse miss)
    store3._store["w:dup"] = session_dup
    store3._sync_to_db("w:dup", session_dup)
    chk("dedup: 14 records → PATCH on first (most recent), no POST",
        len(update_calls) == 1 and update_calls[0][0] == "recDUP1")
    chk("dedup: zero POST even with 14 existing records",
        len(add_calls) == 0)
    chk("dedup: session record_id healed to first found",
        session_dup.get("record_id") == "recDUP1")

    # _find_best_session_in_db must count all 14 and report correctly
    best_id, found_count, reason = store3._find_best_session_in_db("w:dup")
    chk("_find_best: found_count=14", found_count == 14)
    chk("_find_best: selected=recDUP1", best_id == "recDUP1")
    chk("_find_best: action=patch_existing", reason == "patch_existing")

    # no records → create_new
    at.airtable_get = lambda t, formula: "אין רשומות"
    at.airtable_get_records = lambda t, formula: []
    best_id2, found_count2, reason2 = store3._find_best_session_in_db("w:ghost")
    chk("_find_best: no records → found_count=0", found_count2 == 0)
    chk("_find_best: no records → action=create_new", reason2 == "no_records")

    at.airtable_get = lambda t, formula: "אין רשומות"

    print(f"\n{'='*40}")
    print(f"SessionStore Tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
