"""/decision from-insight (SPEC_Insight_to_Decision_to_Task §5, PR1).

שכבת הבדיקה: unit + integration מול Airtable-במקום (in-memory) — אין רשת, אין Flask
אמיתי, אין Anthropic. מה *לא* מוכח כאן: התנהגות Airtable אמיתית (עקביות קריאה אחרי כתיבה,
סדר createdTime), וריצה בפרודקשן. אידמפוטנטיות מוכחת רק לריצות סדרתיות, ריסטארט (state
בזיכרון נמחק) ותהליך יחיד מרובה threads; מרוץ בין תהליכים *מתכנס* אך אינו חסום (ראו מבחן
test_duplicate_inbox_created_by_rival_converges).
"""

import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cmd_decision
import decision_insight_source as src
from airtable_schema import Tables
from identity import Identity, Role
from tools.airtable_read_adapter import AirtableReadError

HOME = src.HOME_TENANT_ID
MARKER_LEN = 17


def rid(n: int) -> str:
    return f"rec{n:014d}"


# ── Airtable בזיכרון ─────────────────────────────────────────────

def _eval(query, rec) -> bool:
    fields = rec["fields"]
    op, args = query.operation, query.arguments
    if op == "empty":
        return True
    if op == "equals":
        return fields.get(args[0]) == args[1]
    if op == "contains":
        return args[1] in (fields.get(args[0]) or "")
    if op == "all_of":
        return all(_eval(c, rec) for c in args)
    if op == "any_of":
        return any(_eval(c, rec) for c in args)
    raise NotImplementedError(op)


class FakeAirtable:
    def __init__(self):
        self.tables: dict[str, list] = {}
        self._clock = 0
        self._ids = 1000
        self.fail_reads: set[str] = set()
        self.reads: list[str] = []
        self.stale_get: set[str] = set()      # table -> get_record מחזיר רשומה לא מעודכנת
        self._lock = threading.Lock()

    def add_record(self, table: str, fields: dict, rec_id: str | None = None) -> dict:
        with self._lock:
            self._clock += 1
            self._ids += 1
            record = {"id": rec_id or rid(self._ids), "createdTime": f"2026-10-13T00:00:{self._clock:06d}Z", "fields": dict(fields)}
            self.tables.setdefault(table, []).append(record)
            return record

    def list_records(self, table, formula="", **kwargs):
        self.reads.append(table)
        if table in self.fail_reads:
            raise AirtableReadError("boom", cause=RuntimeError("down"))
        rows = [r for r in self.tables.get(table, []) if formula == "" or _eval(formula, r)]
        limit = kwargs.get("limit")
        return [dict(r, fields=dict(r["fields"])) for r in (rows[:limit] if isinstance(limit, int) else rows)]

    def get_record(self, table, record_id, **kwargs):
        self.reads.append(table)
        if table in self.fail_reads:
            raise AirtableReadError("boom", cause=RuntimeError("down"))
        for r in self.tables.get(table, []):
            if r["id"] == record_id:
                snap = dict(r, fields=dict(r["fields"]))
                if table in self.stale_get:
                    snap["fields"].pop("Status", None)
                return snap
        raise AirtableReadError("404", status_code=404)

    def of(self, table):
        return self.tables.get(table, [])


class FakeStorage:
    def __init__(self, store: FakeAirtable):
        self.store = store
        self.writes: list[tuple] = []
        self.fail_add: set[str] = set()
        self.unknown_add: dict[str, str] = {}      # table -> "stored" | "lost" (תוצאה לא ידועה)
        self.unknown_once: set[str] = set()
        self.rival_on_add: dict[str, dict] = {}    # table -> fields של רשומה מתחרה שמקדימה את היצירה
        self.fail_update_with: list[set] = []      # רשימת סטים של שדות; update שמכיל אותם מחזיר False

    def add(self, table, fields, source):
        status, rec_id = self._add(table, fields, source)
        return rec_id if status == "created" else None

    def add_with_outcome(self, table, fields, source):
        status, rec_id = self._add(table, fields, source)
        record = {"id": rec_id} if rec_id else None
        return SimpleNamespace(status=status, record=record, error="")

    def _add(self, table, fields, source):
        if table in self.rival_on_add:
            self.store.add_record(table, self.rival_on_add.pop(table))
        if table in self.fail_add:
            return "failed", None
        mode = self.unknown_add.get(table)
        if mode:
            if table in self.unknown_once:
                self.unknown_add.pop(table)
                self.unknown_once.discard(table)
            if mode == "stored":
                rec = self.store.add_record(table, fields)
                self.writes.append(("add", table, rec["id"], dict(fields)))
            return "outcome_unknown", None
        rec = self.store.add_record(table, fields)
        self.writes.append(("add", table, rec["id"], dict(fields)))
        return "created", rec["id"]

    def update(self, table, record_id, fields, source):
        for trigger in self.fail_update_with:
            if trigger <= set(fields):
                return False
        for r in self.store.of(table):
            if r["id"] == record_id:
                r["fields"].update(fields)
                self.writes.append(("update", table, record_id, dict(fields)))
                return True
        return False

    def adds(self, table):
        return [w for w in self.writes if w[0] == "add" and w[1] == table]


# ── בוט מדומה ────────────────────────────────────────────────────

class Bot:
    def __init__(self):
        self.command = None
        self.callbacks = {}
        self.texts = []
        self.answers = []

    def message_handler(self, **kwargs):
        def register(fn):
            if kwargs.get("commands") == ["decision"]:
                self.command = fn
            return fn
        return register

    def callback_query_handler(self, **kwargs):
        def register(fn):
            self.callbacks[fn.__name__] = fn
            return fn
        return register

    def send_message(self, chat_id, text, **kwargs):
        self.texts.append(text)

    def edit_message_text(self, text, *args, **kwargs):
        self.texts.append(text)

    def answer_callback_query(self, call_id, text=None, **kwargs):
        self.answers.append(text)


def _msg(text, uid="u1"):
    return SimpleNamespace(text=text, from_user=SimpleNamespace(id=uid), chat=SimpleNamespace(id="c1"))


def _cb(data, uid="u1"):
    return SimpleNamespace(
        id="cb", data=data, from_user=SimpleNamespace(id=uid),
        message=SimpleNamespace(chat=SimpleNamespace(id="c1"), message_id=7),
    )


def owner(tenant=HOME, role=Role.OWNER, **kw):
    return Identity(user_id="u1", role=role, tenant_id=tenant, external_id="u1", **kw)


INSIGHT_ID = rid(1)


def insight_fields(**over):
    base = {"כותרת התובנה": "מימוש הפסדי הון", "תיאור": "בחינת קיזוז מס תוך שמירה על אסטרטגיה פסיבית",
            "domain": "General", "Next Action": "לברר עם רו\"ח"}
    base.update(over)
    return base


@contextmanager
def hub(identity=None, store=None, learnings=True):
    identity = identity or owner()
    store = store or FakeAirtable()
    if learnings and not store.of(Tables.LEARNINGS):
        store.add_record(Tables.LEARNINGS, insight_fields(), INSIGHT_ID)
    storage = FakeStorage(store)
    cmd_decision._pending.clear()
    with patch("feature_flags.is_enabled", return_value=True), \
            patch.object(cmd_decision, "list_records", store.list_records), \
            patch.object(cmd_decision, "get_record", store.get_record), \
            patch.object(src, "list_records", store.list_records), \
            patch.object(src, "get_record", store.get_record), \
            patch("tools.airtable_read_adapter.list_records", store.list_records), \
            patch("tools.airtable_read_adapter.get_record", store.get_record), \
            patch.object(cmd_decision, "_decision_storage", return_value=storage):
        bot = Bot()
        cmd_decision.register_decision_command(bot, lambda *_: identity)
        yield bot, store, storage
    cmd_decision._pending.clear()


def pending(uid="u1"):
    return cmd_decision._pending.get(uid)


def start(bot, arg="", uid="u1"):
    bot.command(_msg(f"/decision from-insight {arg}".strip(), uid))


def to_target(bot, uid="u1"):
    start(bot, uid=uid)
    bot.callbacks["cb_insight_pick"](_cb(f"dec_ins_pick:{pending(uid)['token']}:0", uid))
    return pending(uid)


def to_review(bot, target="new", uid="u1"):
    to_target(bot, uid)
    bot.callbacks["cb_insight_target"](_cb(f"dec_ins_target:{pending(uid)['token']}:{target}", uid))
    return pending(uid)


def confirm(bot, token, uid="u1"):
    bot.callbacks["cb_insight_confirm"](_cb(f"dec_ins_confirm:{token}", uid))


def seed_decision(store, title="החלטת קרן", status="Open", tenant=HOME, domain="כללי"):
    return store.add_record(Tables.DECISIONS, {"Title": title, "Status": status, "tenant_id": tenant, "Domain": domain})


# ── אין כתיבה לפני אישור / ביטול ─────────────────────────────────

def test_no_writes_before_confirm_and_cancel_leaves_nothing():
    with hub() as (bot, store, storage):
        st = to_review(bot)
        assert storage.writes == []
        bot.callbacks["cb_insight_cancel"](_cb(f"dec_ins_cancel:{st['token']}"))
        assert storage.writes == []
        assert pending() is None
        assert "לא נכתב דבר" in bot.texts[-1]


def test_confirm_after_cancel_is_stale_and_writes_nothing():
    with hub() as (bot, store, storage):
        st = to_review(bot)
        token = st["token"]
        bot.callbacks["cb_insight_cancel"](_cb(f"dec_ins_cancel:{token}"))
        confirm(bot, token)
        assert storage.writes == []
        assert "אינו זמין" in bot.answers[-1]


def test_retarget_invalidates_previous_confirm_token():
    with hub() as (bot, store, storage):
        old = to_review(bot)["token"]
        bot.callbacks["cb_insight_retarget"](_cb(f"dec_ins_retarget:{old}"))
        confirm(bot, old)
        assert storage.writes == []
        assert pending()["step"] == "insight_target" and pending()["token"] != old


def test_expired_state_confirm_writes_nothing():
    with hub() as (bot, store, storage):
        st = to_review(bot)
        st["created_at"] -= cmd_decision._STATE_TTL_SECONDS + 5
        confirm(bot, st["token"])
        assert storage.writes == []


def test_insight_changed_after_display_blocks_write():
    with hub() as (bot, store, storage):
        st = to_review(bot)
        store.of(Tables.LEARNINGS)[0]["fields"]["תיאור"] = "תוכן אחר לגמרי"
        confirm(bot, st["token"])
        assert storage.writes == []
        assert "שונתה" in bot.texts[-1]


def test_confirm_requires_current_review_step_not_pick_step():
    with hub() as (bot, store, storage):
        st = to_target(bot)
        confirm(bot, st["token"])          # עדיין בשלב בחירת יעד
        assert storage.writes == []


# ── מסלול מלא, כפילויות, retries, ריסטארט ────────────────────────

def test_happy_path_new_decision_writes_expected_records_with_marker():
    with hub() as (bot, store, storage):
        st = to_review(bot)
        confirm(bot, st["token"])
        marker = src.insight_marker(INSIGHT_ID)
        inbox = store.of(Tables.DECISION_INBOX)
        decisions = store.of(Tables.DECISIONS)
        events = store.of(Tables.DECISION_EVENTS)
        assert (len(inbox), len(decisions), len(events)) == (1, 1, 1)
        assert marker in inbox[0]["fields"]["Raw Input"] and marker in events[0]["fields"]["Raw Content"]
        assert inbox[0]["fields"]["Status"] == "Linked"
        assert inbox[0]["fields"]["Suggested Decision"] == [decisions[0]["id"]]
        assert inbox[0]["fields"]["Linked Event"] == [events[0]["id"]]
        assert decisions[0]["fields"]["tenant_id"] == HOME
        assert bot.texts[-1].startswith("✅ התובנה")


def test_insight_event_has_no_trust_level_and_carries_unverified_label():
    with hub() as (bot, store, storage):
        confirm(bot, to_review(bot)["token"])
        fields = store.of(Tables.DECISION_EVENTS)[0]["fields"]
        assert "Trust Level" not in fields and "Confidence" not in fields
        assert src.SOURCE_LABEL in fields["Raw Content"]


def test_existing_decision_target_does_not_create_decision():
    with hub() as (bot, store, storage):
        decision = seed_decision(store)
        st = to_review(bot, target="0")
        confirm(bot, st["token"])
        assert len(store.of(Tables.DECISIONS)) == 1
        assert store.of(Tables.DECISION_INBOX)[0]["fields"]["Suggested Decision"] == [decision["id"]]


def test_second_run_after_complete_link_writes_nothing():
    with hub() as (bot, store, storage):
        confirm(bot, to_review(bot)["token"])
        before = len(storage.writes)
        start(bot)
        bot.callbacks["cb_insight_pick"](_cb(f"dec_ins_pick:{pending()['token']}:0"))
        assert len(storage.writes) == before
        assert "כבר משויכת" in bot.texts[-1]


def test_failure_at_event_then_restart_then_resume_creates_each_record_once():
    with hub() as (bot, store, storage):
        storage.fail_add.add(Tables.DECISION_EVENTS)
        confirm(bot, to_review(bot)["token"])
        assert "לא הושלם" in bot.texts[-1] and "❌" in bot.texts[-1]
        assert (len(store.of(Tables.DECISION_INBOX)), len(store.of(Tables.DECISIONS)), len(store.of(Tables.DECISION_EVENTS))) == (1, 1, 0)
        assert store.of(Tables.DECISION_INBOX)[0]["fields"]["Status"] == "Pending"

        cmd_decision._pending.clear()                 # ריסטארט: state בזיכרון אובד
        storage.fail_add.clear()
        confirm(bot, to_review(bot, target="0")["token"])   # יעד: ההחלטה שנוצרה (שיוך חלקי)
        assert (len(store.of(Tables.DECISION_INBOX)), len(store.of(Tables.DECISIONS)), len(store.of(Tables.DECISION_EVENTS))) == (1, 1, 1)
        assert store.of(Tables.DECISION_INBOX)[0]["fields"]["Status"] == "Linked"
        assert bot.texts[-1].startswith("✅ התובנה")


def test_resume_as_new_decision_reuses_prior_partial_decision_not_a_second_one():
    with hub() as (bot, store, storage):
        storage.fail_add.add(Tables.DECISION_EVENTS)
        confirm(bot, to_review(bot)["token"])
        cmd_decision._pending.clear()
        storage.fail_add.clear()
        confirm(bot, to_review(bot, target="new")["token"])
        assert len(store.of(Tables.DECISIONS)) == 1


def test_lost_link_write_is_reported_and_retry_completes():
    with hub() as (bot, store, storage):
        storage.fail_update_with.append({"Linked Event"})
        confirm(bot, to_review(bot)["token"])
        assert "לא הושלם" in bot.texts[-1]
        assert store.of(Tables.DECISION_INBOX)[0]["fields"]["Status"] == "Pending"
        storage.fail_update_with.clear()
        cmd_decision._pending.clear()
        confirm(bot, to_review(bot, target="0")["token"])
        assert len(store.of(Tables.DECISION_EVENTS)) == 1 and len(store.of(Tables.DECISION_INBOX)) == 1
        assert store.of(Tables.DECISION_INBOX)[0]["fields"]["Status"] == "Linked"


def test_link_verification_mismatch_is_not_reported_as_success():
    with hub() as (bot, store, storage):
        store.stale_get.add(Tables.DECISION_INBOX)
        confirm(bot, to_review(bot)["token"])
        assert not bot.texts[-1].startswith("✅ התובנה")
        assert "לא אומת" in bot.texts[-1]


def test_outcome_unknown_but_stored_does_not_create_second_inbox():
    with hub() as (bot, store, storage):
        storage.unknown_add[Tables.DECISION_INBOX] = "stored"
        confirm(bot, to_review(bot)["token"])
        assert len(store.of(Tables.DECISION_INBOX)) == 1
        assert bot.texts[-1].startswith("✅ התובנה")


def test_outcome_unknown_and_lost_retries_exactly_once():
    with hub() as (bot, store, storage):
        storage.unknown_add[Tables.DECISION_INBOX] = "lost"
        storage.unknown_once.add(Tables.DECISION_INBOX)
        confirm(bot, to_review(bot)["token"])
        assert len(store.of(Tables.DECISION_INBOX)) == 1
        assert bot.texts[-1].startswith("✅ התובנה")


def test_outcome_unknown_twice_stops_with_explicit_message():
    with hub() as (bot, store, storage):
        storage.unknown_add[Tables.DECISION_INBOX] = "lost"
        confirm(bot, to_review(bot)["token"])
        assert len(store.of(Tables.DECISION_INBOX)) == 0
        assert "לא ידועה" in bot.texts[-1]
        assert store.of(Tables.DECISIONS) == [] and store.of(Tables.DECISION_EVENTS) == []


def test_dedup_lookup_failure_aborts_with_zero_writes():
    with hub() as (bot, store, storage):
        st = to_review(bot)
        store.fail_reads.add(Tables.DECISION_INBOX)
        confirm(bot, st["token"])
        assert storage.writes == []
        assert "לא ניתן לבדוק כפילות" in bot.texts[-1]


def test_lookup_failure_at_pick_blocks_flow_without_writes():
    with hub() as (bot, store, storage):
        start(bot)
        store.fail_reads.add(Tables.DECISION_INBOX)
        bot.callbacks["cb_insight_pick"](_cb(f"dec_ins_pick:{pending()['token']}:0"))
        assert storage.writes == []
        assert "לא נכתב דבר" in bot.texts[-1]


def test_rejected_inbox_blocks_without_writes():
    with hub() as (bot, store, storage):
        store.add_record(Tables.DECISION_INBOX, {"Raw Input": f"x\n{src.insight_marker(INSIGHT_ID)}", "Status": "Rejected", "tenant_id": HOME})
        start(bot)
        bot.callbacks["cb_insight_pick"](_cb(f"dec_ins_pick:{pending()['token']}:0"))
        assert storage.writes == [] and "נדחית" in bot.texts[-1]


def test_open_decision_with_same_title_blocks_new_creation():
    with hub() as (bot, store, storage):
        seed_decision(store, title="מימוש הפסדי הון")
        confirm(bot, to_review(bot, target="new")["token"])
        assert len(store.of(Tables.DECISIONS)) == 1
        assert "בשם זהה" in bot.texts[-1]


def test_partial_inbox_pointing_to_other_decision_blocks_conflicting_target():
    with hub() as (bot, store, storage):
        other = seed_decision(store, title="אחרת")
        mine = seed_decision(store, title="שלי")
        store.add_record(Tables.DECISION_INBOX, {
            "Raw Input": f"x\n{src.insight_marker(INSIGHT_ID)}", "Status": "Pending", "tenant_id": HOME,
            "Suggested Decision": [other["id"]],
        })
        st = to_target(bot)
        idx = [i for i, d in enumerate(st["options"]) if d["id"] == mine["id"]][0]
        bot.callbacks["cb_insight_target"](_cb(f"dec_ins_target:{st['token']}:{idx}"))
        confirm(bot, pending()["token"])
        assert storage.writes == []
        assert "שיוך חלקי קודם להחלטה אחרת" in bot.texts[-1]


def test_foreign_marker_inside_insight_text_does_not_confuse_dedup():
    """טקסט תובנה שמכיל סמן של תובנה אחרת (לא בשורה האחרונה) אינו נחשב התאמה."""
    with hub() as (bot, store, storage):
        other = rid(2)
        store.add_record(Tables.DECISION_INBOX, {
            "Raw Input": f"תובנה אחרת שמצטטת {src.insight_marker(INSIGHT_ID)} בתוך הטקסט\n{src.insight_marker(other)}",
            "Status": "Pending", "tenant_id": HOME,
        })
        confirm(bot, to_review(bot)["token"])
        assert len(store.of(Tables.DECISION_INBOX)) == 2           # נוצר Inbox נפרד לתובנה שלנו
        assert bot.texts[-1].startswith("✅ התובנה")


def test_unexpected_exception_during_write_is_reported_not_swallowed_as_success():
    with hub() as (bot, store, storage):
        st = to_review(bot)
        with patch.object(cmd_decision, "_execute_insight_link", side_effect=RuntimeError("boom")):
            confirm(bot, st["token"])
        assert "שגיאה בלתי צפויה" in bot.texts[-1] and not bot.texts[-1].startswith("✅")


def test_failed_edit_message_falls_back_to_new_message():
    with hub() as (bot, store, storage):
        st = to_review(bot)

        def broken_edit(*args, **kwargs):
            raise RuntimeError("message is not modified")
        bot.edit_message_text = broken_edit
        confirm(bot, st["token"])
        assert bot.texts[-1].startswith("✅ התובנה")


# ── מקביליות ─────────────────────────────────────────────────────

def test_parallel_double_click_performs_writes_once():
    with hub() as (bot, store, storage):
        token = to_review(bot)["token"]
        threads = [threading.Thread(target=confirm, args=(bot, token)) for _ in range(6)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert (len(store.of(Tables.DECISION_INBOX)), len(store.of(Tables.DECISIONS)), len(store.of(Tables.DECISION_EVENTS))) == (1, 1, 1)


def test_double_click_claims_state_atomically_so_link_executes_once():
    """הוכחה ל-claim עצמו (לא רק ל-dedup בסמן): _execute_insight_link נקרא פעם אחת בלבד."""
    calls = []
    original = cmd_decision._execute_insight_link

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    with hub() as (bot, store, storage), patch.object(cmd_decision, "_execute_insight_link", counting):
        token = to_review(bot)["token"]
        threads = [threading.Thread(target=confirm, args=(bot, token)) for _ in range(6)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert len(calls) == 1


def test_two_sessions_same_insight_in_one_process_end_with_single_records():
    with hub() as (bot, store, storage):
        t1 = to_review(bot, uid="u1")["token"]
        t2 = to_review(bot, uid="u2")["token"]
        threads = [threading.Thread(target=confirm, args=(bot, t1, "u1")), threading.Thread(target=confirm, args=(bot, t2, "u2"))]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert len(store.of(Tables.DECISION_INBOX)) == 1
        assert len(store.of(Tables.DECISION_EVENTS)) == 1
        assert len(store.of(Tables.DECISIONS)) == 1


def test_duplicate_inbox_created_by_rival_converges_but_is_not_prevented():
    """תהליך מתחרה מקדים את היצירה: נוצרת כפילות (לא נמנעת), אך הקישור מתכנס לוותיקה ביותר."""
    with hub() as (bot, store, storage):
        st = to_review(bot)
        storage.rival_on_add[Tables.DECISION_INBOX] = {
            "Raw Input": f"rival\n{src.insight_marker(INSIGHT_ID)}", "Status": "Pending", "tenant_id": HOME,
        }
        confirm(bot, st["token"])
        inboxes = store.of(Tables.DECISION_INBOX)
        assert len(inboxes) == 2                       # כפילות קיימת וגלויה
        rival = min(inboxes, key=lambda r: r["createdTime"])
        assert rival["fields"]["Status"] == "Linked"   # אך הקישור הושלם על הוותיקה
        assert bot.texts[-1].startswith("✅ התובנה")


# ── הרשאות, tenant, scope ────────────────────────────────────────

def test_other_tenant_identity_is_denied_before_any_airtable_access():
    with hub(identity=owner(tenant="tenant-b")) as (bot, store, storage):
        store.reads.clear()
        start(bot)
        assert store.reads == [] and storage.writes == []
        assert "אינן זמינות" in bot.texts[-1]


def test_unauthorized_role_is_denied():
    with hub(identity=owner(role=Role.READONLY)) as (bot, store, storage):
        start(bot)
        assert storage.writes == [] and bot.texts[-1] == "אין הרשאה לפקודה זו."


def test_scope_record_without_tenant_id_is_home_tenant_only():
    record = {"id": INSIGHT_ID, "fields": insight_fields()}
    assert src.insight_in_scope(record, owner(tenant=HOME)) is True
    assert src.insight_in_scope(record, owner(tenant="tenant-b")) is False


def test_scope_record_with_foreign_tenant_id_is_rejected_for_home_identity():
    record = {"id": INSIGHT_ID, "fields": insight_fields(tenant_id="tenant-b")}
    assert src.insight_in_scope(record, owner(tenant=HOME)) is False
    assert src.insight_in_scope(record, owner(tenant="tenant-b")) is True


def test_scope_blank_tenant_id_is_treated_as_missing_not_wildcard():
    record = {"id": INSIGHT_ID, "fields": insight_fields(tenant_id="  ")}
    assert src.insight_in_scope(record, owner(tenant="tenant-b")) is False


def test_partner_without_domain_access_cannot_see_insight():
    partner = owner(role=Role.PARTNER, allowed_domains=[])
    assert src.insight_in_scope({"id": INSIGHT_ID, "fields": insight_fields()}, partner) is False


def test_list_excludes_out_of_scope_and_unusable_records():
    store = FakeAirtable()
    store.add_record(Tables.LEARNINGS, insight_fields(), rid(1))
    store.add_record(Tables.LEARNINGS, insight_fields(tenant_id="tenant-b"), rid(2))
    store.add_record(Tables.LEARNINGS, {"domain": "General"}, rid(3))          # בלי תוכן
    with hub(store=store, learnings=False) as (bot, _, storage):
        assert [r["id"] for r in src.list_insights(owner())] == [rid(1)]


def test_confirm_rechecks_identity_tenant():
    with hub() as (bot, store, storage):
        st = to_review(bot)
    # אותו state, אבל ה-callback מגיע מ-identity של tenant אחר
    with hub(identity=owner(tenant="tenant-b")) as (bot2, store2, storage2):
        cmd_decision._pending["u1"] = st
        confirm(bot2, st["token"])
        assert storage2.writes == []


def test_domain_mapping_and_title_fallback():
    view = src.build_insight_view({"id": INSIGHT_ID, "fields": {"title": "כותרת חלופית", "summary": "תקציר", "domain": "Real Estate "}})
    assert view.title == "כותרת חלופית" and view.description == "תקציר"
    assert view.decision_domain == "נדל\"ן"
    assert src.map_domain("SaaS ") == "כללי"


# ── גבולות ארכיטקטורה (אכיפה קדימה) ──────────────────────────────

def test_no_gateway_bypass_or_task_write_in_new_code():
    root = Path(__file__).parent
    source = (root / "decision_insight_source.py").read_text(encoding="utf-8")
    for forbidden in ("airtable_gateway", "airtable_create(", "airtable_patch(", "httpx", "propose_action", "Tables.TASKS"):
        assert forbidden not in source, forbidden
    hub_src = (root / "cmd_decision.py").read_text(encoding="utf-8")
    for forbidden in ("airtable_create(", "airtable_patch(", "Tables.TASKS", "propose_action", "dispatch_tool"):
        assert forbidden not in hub_src, forbidden


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
