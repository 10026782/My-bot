# lead_memory.py — N01 Airtable Save Debounce
# קובץ: lead_memory.py (flat, לא core/)
# flag: LEAD_MEMORY (env: FEATURE_LEAD_MEMORY=true)
#
# בעיה שפותרת:
#   scoring רץ על כל הודעה → כותב לAirtable על כל הודעה → rate-limit.
# פתרון:
#   debounce: שמירה כל SAVE_EVERY=3 הודעות, או כשtier השתנה.
#   flush() / flush_all() — שמירה מיידית לפי צורך.
#   scheduler safety-net כל 10 דקות.

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _write_success(result) -> bool:
    """Use the Airtable write contract; display text is never execution truth."""
    return isinstance(result, dict) and result.get("ok") is True


SAVE_EVERY = 3


@dataclass
class LeadState:
    memory_key:     str
    tier:           str = "COLD"
    score:          int = 0
    domain:         str = ""
    channel:        str = ""
    contact_name:   str = ""
    last_message:   str = ""
    summary:        str = ""
    msg_count:      int = 0
    followup_count: int = 0
    recovery_count: int = 0
    last_active:    str = ""
    dirty:          bool = False
    record_id:      str = ""


class LeadMemory:
    def __init__(self, save_every: int = SAVE_EVERY):
        self._store: dict[str, LeadState] = {}
        self._lock        = threading.Lock()
        self._save_every  = save_every

    # ── internal (call only when lock is held) ────
    def _get_unlocked(self, memory_key: str) -> LeadState:
        if memory_key not in self._store:
            self._store[memory_key] = LeadState(
                memory_key  = memory_key,
                last_active = _now_iso(),
            )
        return self._store[memory_key]

    # ── Public ────────────────────────────────────
    def get(self, memory_key: str) -> LeadState:
        with self._lock:
            return self._get_unlocked(memory_key)

    def update(self, memory_key: str, *, tier="", score=-1,
               domain="", channel="", contact_name="",
               last_message="", summary="",
               followup_count=-1, recovery_count=-1,
               record_id="") -> bool:
        with self._lock:
            state        = self._get_unlocked(memory_key)
            tier_changed = False

            if tier and tier != state.tier:
                state.tier   = tier
                tier_changed = True
                state.dirty  = True

            if score >= 0 and score != state.score:
                state.score = score
                state.dirty = True

            if domain:        state.domain        = domain
            if channel:       state.channel       = channel
            if contact_name:  state.contact_name  = contact_name
            if record_id:     state.record_id     = record_id
            if last_message:
                state.last_message = last_message[:200]
                state.dirty        = True

            if summary and summary != state.summary:
                state.summary = summary
                state.dirty   = True

            if followup_count >= 0: state.followup_count = followup_count
            if recovery_count >= 0: state.recovery_count = recovery_count

            state.last_active  = _now_iso()
            state.msg_count   += 1

            return tier_changed or (state.msg_count >= self._save_every)

    def save(self, memory_key: str) -> bool:
        with self._lock:
            state = self._store.get(memory_key)
            if not state or not state.dirty:
                return True
            ok = self._write(state)
            if ok:
                state.dirty     = False
                state.msg_count = 0
            return ok

    def flush(self, memory_key: str) -> bool:
        with self._lock:
            state = self._store.get(memory_key)
            if not state:
                return True
            state.dirty = True
            ok = self._write(state)
            if ok:
                state.dirty     = False
                state.msg_count = 0
            return ok

    def flush_all(self) -> int:
        with self._lock:
            saved = 0
            for state in self._store.values():
                if state.dirty:
                    if self._write(state):
                        state.dirty     = False
                        state.msg_count = 0
                        saved          += 1
            if saved:
                logger.info(f"[LeadMemory] flush_all: {saved} leads saved")
            return saved

    def all_active(self) -> list[LeadState]:
        with self._lock:
            return list(self._store.values())

    def _write(self, state: LeadState) -> bool:
        """כותב enrichment דרך ה-Gateway עם system principal מפורש.
        LeadMemory הוא post-write enrichment בלבד: אם אין record_id, מחפש
        Lead קיים לפי memory_key ומעדכן אותו; לעולם אינו יוצר Lead."""
        try:
            from tools.airtable_tools import airtable_get_records  # type: ignore
            from airtable_schema import Tables, LeadFields               # type: ignore
            from tools.airtable_gateway import escape_formula_value      # type: ignore
            from core.lead_service import update_lead_fields
            from identity import Identity, Role

            fields = {
                "memory_key": state.memory_key,
                LeadFields.SCORE: state.score,        # tier הוא formula field — לא כותבים אליו
                "domain":     state.domain,
                "channel":    state.channel,
                "Name":       state.contact_name,
            }
            if state.summary:
                fields[LeadFields.SUMMARY] = state.summary

            if not state.record_id:
                safe_memory_key = escape_formula_value(state.memory_key)
                records = airtable_get_records(
                    Tables.LEADS,
                    f"{{{LeadFields.MEMORY_KEY}}}='{safe_memory_key}'",
                    max_records=1,
                )
                if records:
                    state.record_id = records[0].get("id", "")

            if state.record_id:
                tenant_id = state.memory_key.split(":", 1)[0] or "boss_hq"
                system_identity = Identity(
                    user_id="lead_memory_scheduler",
                    role=Role.MANAGER,
                    tenant_id=tenant_id,
                    domain_id=state.domain or "general",
                    channel="scheduler",
                    external_id="lead_memory_scheduler",
                )
                result = update_lead_fields(
                    system_identity,
                    state.record_id,
                    fields,
                    source_module="lead_memory_scheduler",
                )
                return bool(result.ok)

            logger.warning(
                "[LeadMemory] no existing Lead for memory_key=%s; skipping enrichment write",
                state.memory_key,
            )
            return False
        except ImportError:
            logger.debug(f"[LeadMemory] dry-run: {state.memory_key}")
            return False
        except Exception as e:
            logger.error(f"[LeadMemory] write error: {e}")
            return False


# ── Singleton ─────────────────────────────────────
lead_memory = LeadMemory()

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

def job_flush_lead_memory():
    """Safety-net scheduler job — כל 10 דקות."""
    try:
        from feature_flags import is_enabled  # type: ignore
        if not is_enabled("LEAD_MEMORY"):
            return
    except ImportError:
        pass
    lead_memory.flush_all()


# ── Self-tests ────────────────────────────────────
def _run_tests() -> bool:
    passed = failed = 0

    def chk(desc, cond):
        nonlocal passed, failed
        if cond:
            print(f"✅ {desc}"); passed += 1
        else:
            print(f"❌ {desc}"); failed += 1

    lm = LeadMemory(save_every=3)
    mk = "whatsapp:972501"

    # get / init
    s = lm.get(mk)
    chk("get returns LeadState",     isinstance(s, LeadState))
    chk("initial tier=COLD",         s.tier == "COLD")
    chk("initial msg_count=0",       s.msg_count == 0)

    # debounce — 3 הודעות
    r1 = lm.update(mk, last_message="msg1", score=30)
    chk("msg1: save=False (1<3)",    r1 is False)
    r2 = lm.update(mk, last_message="msg2", score=40)
    chk("msg2: save=False (2<3)",    r2 is False)
    r3 = lm.update(mk, last_message="msg3", score=50)
    chk("msg3: save=True  (3>=3)",   r3 is True)

    # tier change → save מיידי
    lm2 = LeadMemory(save_every=10)
    mk2 = "telegram:999"
    lm2.update(mk2, tier="COLD")
    r = lm2.update(mk2, tier="HOT")
    chk("tier COLD→HOT → save now",  r is True)

    # dirty flag
    lm3 = LeadMemory(save_every=3)
    mk3 = "w:dirty"
    lm3.update(mk3, last_message="hi")
    chk("after update: dirty=True",  lm3.get(mk3).dirty is True)

    # flush (dry-run, no crash)
    try:
        lm3.flush(mk3)
        chk("flush() no crash",      True)
    except Exception:
        chk("flush() no crash",      False)

    # flush_all
    lm4 = LeadMemory(save_every=3)
    for i in range(4):
        lm4.update(f"w:{i}", last_message=f"m{i}", score=i*10)
    n = lm4.flush_all()
    chk("flush_all() returns int",   isinstance(n, int))

    # all_active
    active = lm4.all_active()
    chk("all_active returns list",   isinstance(active, list))
    chk("all_active has 4 leads",    len(active) == 4)

    # singleton
    chk("singleton exists",          lead_memory is not None)

    print(f"\n{'='*40}")
    print(f"N01 Tests: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    ok = _run_tests()
    exit(0 if ok else 1)
