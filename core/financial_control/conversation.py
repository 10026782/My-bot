"""FCC conversation: ONE draft/completion primitive for TMA and chat.

free text -> extract known fields -> FCC draft (BusinessDraft, persisted by session_store)
-> filling (ask only what is missing) -> review -> confirm -> immutable ConfirmedSnapshot
-> (caller) ActionGateway -> canonical writes -> receipt.

State lives on the server, keyed by the canonical person (``identity.user_id``) in the shared
``fcc`` slot, so a question asked in the TMA can be answered in chat and vice-versa. React/chat
adapters only render ``TurnResult`` and send the user's next text. Nothing here writes to
Airtable; after ``confirm`` no extractor/classifier is called again and no field is defaulted.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from commercial_completion import CompletionError
from core import data_access_policy as policy
from core.business_draft import (
    BusinessDraft, BusinessDraftError, DraftConflictError, DraftIdentityMismatchError,
    DraftOperation, DraftState, create_draft,
)
from core.draft_flow import CANCEL_WORDS, CONFIRM_WORDS, EDIT_WORDS, SKIP_WORDS
from core.financial_control import calc, draft as fd, loans as fcc_loans, service, writer
from airtable_schema import AssetFields as AF, FinEventFields as EF, FinGoalFields as GF, LoanFields as LF, RecObFields as RF, TaskFields, Tables

logger = logging.getLogger(__name__)

_TERMINAL = (DraftState.CANCELLED, DraftState.EXPIRED, DraftState.FAILED)
_VALIDATION_ERRORS = (BusinessDraftError, CompletionError, ValueError)


@dataclass
class TurnResult:
    state: str          # ask | review | confirmed | cancelled | needs_goal | duplicate | clarify | denied | info | unrelated
    message: str = ""
    entity: str | None = None
    awaiting: str | None = None
    fields: dict = field(default_factory=dict)       # display view of the draft so far
    candidates: list = field(default_factory=list)   # [{goal_id, title}] when the goal must be chosen
    snapshot: dict | None = None                     # frozen writes, only when state == "confirmed"

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("state", "message", "entity", "awaiting", "fields", "candidates", "snapshot")}


# ── Extractor (LLM) — injectable; default wraps core.financial_control.classifier ────────────────
class LlmExtractor:
    def classify(self, text: str, goal_titles: list[str], today: date) -> dict | None:
        from core.financial_control import classifier
        return classifier.classify(text, goal_titles, today=today)

    def fill(self, text: str, awaiting: str | None, fields: dict, entity: str, today: date) -> dict:
        from core.financial_control import classifier
        return classifier.fill_reply(text, awaiting, fields, entity, today=today)


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────
def _store():
    from session_store import lead_sessions
    return lead_sessions


def _ids(identity, actor) -> dict | None:
    """Canonical slot key = tenant + stable user_id (never a display name); no fallback to anyone else."""
    tenant = str(getattr(identity, "tenant_id", "") or "").strip()
    user = str(getattr(identity, "user_id", "") or "").strip()
    if not tenant or tenant == "unknown" or not user:
        return None
    return {"tenant_id": tenant, "actor_user_id": user, "sender": f"{tenant}:{user}", "profile_id": actor.profile_id}


def _load_all(store, ids) -> list[BusinessDraft]:
    out = []
    for entity in fd.FCC_ENTITIES:
        try:
            d = store.load_business_draft(ids["sender"], entity, tenant_id=ids["tenant_id"],
                                          actor_user_id=ids["actor_user_id"], source_channel=fd.FCC_CHANNEL,
                                          channel=fd.FCC_CHANNEL, contracts=fd.FCC_CONTRACTS)
        except DraftIdentityMismatchError:
            logger.warning("[fcc] draft binding mismatch entity=%s", entity)
            continue
        if d is not None:
            out.append(d)
    return out


def _delete(store, ids, entity) -> None:
    store.delete_business_draft(ids["sender"], entity, channel=fd.FCC_CHANNEL)


def _save(store, ids, d: BusinessDraft, *, expected: int) -> BusinessDraft:
    return store.save_business_draft(ids["sender"], d, expected_version=expected, channel=fd.FCC_CHANNEL,
                                     contracts=fd.FCC_CONTRACTS)


def _view(d: BusinessDraft) -> dict:
    return {fd.label(d.entity_type, k): fd.display_value(k, v) for k, v in d.fields.items() if v not in (None, "")}


def _missing(d: BusinessDraft) -> list[str]:
    return [m.field_name for m in d.missing_fields()] if d.operation is DraftOperation.CREATE else []


def _render(d: BusinessDraft) -> TurnResult:
    goal_title = str(d.source_context.get("goal_title") or "")
    inferred = tuple(d.source_context.get("inferred") or ())
    if d.lifecycle_state is DraftState.EDITING:
        return TurnResult("ask", "מה לערוך? (למשל: סכום 80000)", d.entity_type, None, _view(d))
    if d.lifecycle_state is DraftState.READY_FOR_REVIEW:
        original = d.original_fields or {}
        changed = {k: v for k, v in d.fields.items() if d.operation is DraftOperation.UPDATE and v != original.get(k)}
        return TurnResult("review", fd.render_review(
            d.entity_type, d.fields, goal_title=goal_title, operation=d.operation.value, changed=changed,
            inferred=inferred, note=(_sale_note(d) if d.entity_type == fd.FCC_ASSET_SOLD else str(d.source_context.get("review_note") or ""))),
            d.entity_type, None, _view(d))
    if d.source_context.get("ask_source"):                    # "מקור אחר": the source's name comes before the amount
        return TurnResult("ask", "מה שם המקור? (למשל: אבי, תיווך)", d.entity_type, "source", _view(d))
    missing = _missing(d)
    awaiting = missing[0] if missing else None
    msg = fd.prompt_for(d.entity_type, awaiting, d.fields, goal_title) if awaiting else "מה לעדכן?"
    if awaiting and d.entity_type in (fd.FCC_LOAN_BALANCE, fd.FCC_LOAN_PAYMENT, fd.FCC_ASSET_VALUE, fd.FCC_ASSET_MORTGAGE,
                                      fd.FCC_ASSET_STEP) and d.source_context.get("review_note"):
        msg += f"\n({d.source_context['review_note']})"
    return TurnResult("ask", msg, d.entity_type, awaiting, _view(d))


def _set_fields(d: BusinessDraft, updates: dict, *, strict: bool) -> tuple[BusinessDraft, list[str]]:
    """Apply validated updates; track inferred values. Returns (draft, rejected_field_names)."""
    contract = fd.FCC_CONTRACTS[d.entity_type]
    names = {f.field_name for f in contract.fields}
    inferred = list(d.source_context.get("inferred") or [])
    rejected: list[str] = []
    ordered = sorted((k for k in updates if k in names), key=lambda k: k != "category")   # category first
    for name in ordered:
        value = updates[name]
        if value in (None, ""):
            continue
        try:
            d = d.set_field(name, value, adapter=fd.ADAPTER)
        except _VALIDATION_ERRORS:
            if strict:
                raise
            rejected.append(name)
            continue
        if name in inferred:
            inferred.remove(name)
        if name == "category" and d.entity_type == fd.FCC_GOAL:
            for old in list(inferred):                       # category changed -> drop stale inference
                try:
                    d = d.clear_field(old, adapter=fd.ADAPTER)
                except _VALIDATION_ERRORS:
                    pass
            inferred = []
            for k, v in fd.INFERENCE.get(str(value), {}).items():
                if d.fields.get(k) in (None, ""):
                    d = d.set_field(k, v, adapter=fd.ADAPTER)
                    inferred.append(k)
    d = replace(d, source_context={**d.source_context, "inferred": inferred})
    if {"review_status", "amount", "frequency", "saving"} & set(updates):   # never touch unmentioned fields
        d = _derive_obligation_saving(d)
    return d, rejected


def _derive_obligation_saving(d: BusinessDraft) -> BusinessDraft:
    """Cancelling a commitment saves its monthly cost: when no saving was stated, fill it with the monthly
    equivalent and mark it (הוסק) so the review shows it. A saving the owner stated is never overwritten."""
    if d.entity_type != fd.FCC_OBLIGATION or d.fields.get("review_status") != "cancel":
        return d
    inferred = list(d.source_context.get("inferred") or [])
    if d.fields.get("saving") not in (None, "") and "saving" not in inferred:
        return d
    monthly = calc.monthly_equivalent(d.fields.get("amount"), d.fields.get("frequency"))
    if monthly is None:
        return d
    d = d.set_field("saving", monthly, adapter=fd.ADAPTER)
    if "saving" not in inferred:
        inferred.append("saving")
    return replace(d, source_context={**d.source_context, "inferred": inferred})


def _deterministic_answer(field_name: str, text: str):
    """Value-shaped answers only (a number, a date with digits, one of the presented choices). Free text
    (titles, notes) is never accepted deterministically — it must be evidenced by the extractor."""
    t = text.strip()
    vocab = fd.ANSWER_VOCAB.get(field_name)
    if vocab and t in vocab:
        return vocab[t]
    if field_name in ("target_amount", "amount", "saving"):
        cleaned = t.replace(",", "").replace("₪", "").replace("ש\"ח", "").replace("שח", "").strip()
        try:
            float(cleaned)
            return cleaned
        except ValueError:
            return None
    if field_name in ("end_date", "start_date", "occurred_at", "due_date", "next_charge_date") and any(ch.isdigit() for ch in t):
        return t
    return None


def _goal_by_text(goals: list[dict], text: str):
    state, matches = writer.resolve_goal(text, goals)
    return matches[0] if state == "one" else None


# ── public API ──────────────────────────────────────────────────────────────────────────────────
def pending_view(identity, *, store=None) -> dict | None:
    """The open draft as a render-ready dict (so a refreshed TMA / the next chat message resumes it)."""
    actor = policy.resolve_actor(identity)
    if not actor.resolved:
        return None
    store = store or _store()
    ids = _ids(identity, actor)
    if ids is None:
        return None
    for d in _load_all(store, ids):
        if d.lifecycle_state not in _TERMINAL:
            return _render(d).to_dict()
    return None


def has_pending(identity, *, store=None) -> bool:
    return pending_view(identity, store=store) is not None


FREE_TEXT_TABS = (None, "monthly")      # free text opens a NEW draft only from the monthly area; other tabs start via intents


def handle_turn(identity, text: str, *, goal_id: str | None = None, extractor=None, store=None,
                today: date | None = None, scope: str | None = None) -> TurnResult:
    today = today or date.today()
    actor = policy.resolve_actor(identity)
    if not actor.resolved:
        return TurnResult("denied", policy.UNRESOLVED_MESSAGE)
    text = (text or "").strip()
    if not text:
        return TurnResult("clarify", "מה לעדכן?")
    store, extractor = store or _store(), extractor or LlmExtractor()
    ids = _ids(identity, actor)
    if ids is None:                                          # no tenant / user_id -> fail closed
        return TurnResult("denied", policy.UNRESOLVED_MESSAGE)
    lower = text.lower()

    drafts = _load_all(store, ids)
    for d in list(drafts):                                   # clear closed/expired slots
        if d.lifecycle_state in _TERMINAL:
            _delete(store, ids, d.entity_type)
            drafts.remove(d)
            if d.lifecycle_state is DraftState.EXPIRED and (lower in CONFIRM_WORDS or lower in CANCEL_WORDS):
                return TurnResult("info", "הטיוטה פגה (30 דקות). אפשר להתחיל מחדש.")
    if drafts:
        return _continue(identity, ids, drafts[0], text, goal_id, extractor, store, today)
    if lower in CONFIRM_WORDS or lower in CANCEL_WORDS or lower in EDIT_WORDS:
        return TurnResult("info", "אין עדכון פתוח כרגע.")
    if scope not in FREE_TEXT_TABS:
        return TurnResult("info", "בלשונית הזו הפעולות נבחרות בכפתורים. לכתיבה חופשית עברו ל״התנהלות חודשית״.")
    return _start(identity, actor, ids, text, goal_id, extractor, store, today)


def _debt_goal(identity) -> dict | None:
    """The one active debt goal progress events go to. Zero or several -> None (never guess which one)."""
    active = [g for g in service.my_goals(identity)
              if str((g.get("fields") or {}).get(GF.STATUS) or "active").lower() in ("active", "פעיל")
              and service._category_key((g.get("fields") or {}).get(GF.CATEGORY)) == "debt"]
    return active[0] if len(active) == 1 else None


def _open_slot(identity, store, why: str):
    """Shared preamble of every structured entry: resolved actor, canonical slot key, no other draft open
    (closed/expired slots are cleared). Returns (store, ids, None) or (None, None, a ready TurnResult)."""
    actor = policy.resolve_actor(identity)
    if not actor.resolved:
        return None, None, TurnResult("denied", policy.UNRESOLVED_MESSAGE)
    store = store or _store()
    ids = _ids(identity, actor)
    if ids is None:
        return None, None, TurnResult("denied", policy.UNRESOLVED_MESSAGE)
    for d in _load_all(store, ids):
        if d.lifecycle_state in _TERMINAL:
            _delete(store, ids, d.entity_type)
        else:
            return None, None, TurnResult("info", f"יש עדכון פתוח — לסיים או לבטל אותו לפני {why}.", d.entity_type)
    return store, ids, None


def start_loan_close(identity, loan_id: str, *, store=None, today: date | None = None) -> TurnResult:
    """Structured entry for "I closed this loan" (intent ``loan.close`` — no classifier involved). Opens a
    draft on the shared FCC slot: amount paid defaults to the stored early-closure balance (shown as inferred,
    editable), then the usual review -> אשר / ערוך / בטל. Nothing is written here."""
    today = today or date.today()
    store, ids, stop = _open_slot(identity, store, "סגירת הלוואה")
    if stop is not None:
        return stop
    loan = next((r for r in service.my_loans(identity) if r["id"] == str(loan_id or "")), None)
    if loan is None:                                          # not found == not yours: same answer, no probing
        return TurnResult("denied", policy.DENIED_MESSAGE)
    item = fcc_loans.loan_item(loan, today)
    if not item["active"]:
        return TurnResult("info", "ההלוואה כבר מסומנת כנסגרה.")
    goal = _debt_goal(identity)
    name = item["name"] or "ההלוואה"
    ctx = {"record_id": loan["id"], "loan_name": name, "goal_title": name}
    review_note = ""
    if goal is not None:
        ctx["debt_goal_id"] = goal["id"]
        review_note = f"יירשם גם אירוע התקדמות ביעד: {goal['fields'].get(GF.TITLE, '')}"
    else:
        review_note = "לא נמצא יעד חוב פעיל אחד — יתעדכן רק סטטוס ההלוואה, בלי אירוע התקדמות."
    ctx["review_note"] = review_note
    d = _new_draft(identity, ids, fd.FCC_LOAN_CLOSE, DraftOperation.CREATE, fields={}, raw_text=f"close_loan:{loan['id']}",
                   today=today, extra_ctx=ctx)
    fields = {"occurred_at": today.isoformat()}
    inferred = ["occurred_at"]
    if item["early_closure_balance"] is not None and item["early_closure_balance"] > 0:
        fields["amount"] = item["early_closure_balance"]
        inferred.append("amount")
    d, _rej = _set_fields(d, fields, strict=False)
    d = replace(d, source_context={**d.source_context, "inferred": inferred})
    return _persist_new(store, ids, d)


_LOAN_CURRENT = {fd.FCC_LOAN_BALANCE: LF.EARLY_CLOSURE, fd.FCC_LOAN_PAYMENT: LF.MONTHLY_PAYMENT}


def _start_loan_intent(identity, ids, entity, entity_id, store, today) -> TurnResult:
    """update balance / update monthly payment (the chosen ACTIVE loan, one field) or a new loan. The loan must be the
    caller's own (not found == not yours); the draft shows today's stored value so the owner reviews old -> new."""
    raw = f"intent:{entity}#{uuid.uuid4().hex[:8]}"
    if entity == fd.FCC_LOAN_NEW:
        return _persist_new(store, ids, _new_draft(identity, ids, entity, DraftOperation.CREATE, fields={}, raw_text=raw, today=today))
    if not entity_id:
        return TurnResult("clarify", "בחרו קודם את ההלוואה לעדכון.")
    loan = next((r for r in service.my_loans(identity) if r["id"] == str(entity_id)), None)
    if loan is None:
        return TurnResult("denied", policy.DENIED_MESSAGE)
    item = fcc_loans.loan_item(loan, today)
    if not item["active"]:
        return TurnResult("info", "ההלוואה מסומנת כנסגרה — אין מה לעדכן.")
    name = item["name"] or "ההלוואה"
    current = calc._num((loan.get("fields") or {}).get(_LOAN_CURRENT[entity]))
    note = f"היום: {fd.display_value('balance', current)}" if current is not None else "היום: לא הוגדר"
    d = _new_draft(identity, ids, entity, DraftOperation.CREATE, fields={}, raw_text=raw, today=today,
                   extra_ctx={"record_id": loan["id"], "loan_name": name, "goal_title": name, "review_note": note})
    return _persist_new(store, ids, d)


_ASSET_CURRENT = {fd.FCC_ASSET_VALUE: AF.VALUE, fd.FCC_ASSET_MORTGAGE: AF.MORTGAGE, fd.FCC_ASSET_STEP: AF.NEXT_STEP,
                  fd.FCC_ASSET_SOLD: AF.STATUS}
_ASSET_GONE = ("נמכר", "לא פעיל")      # live Assets.Status choices that mean the asset is no longer held


def _start_asset_intent(identity, ids, entity, entity_id, store, today) -> TurnResult:
    """update value / mortgage / next step of ONE of the caller's own assets. The asset is chosen by id (never typed),
    not found == not yours, and a sold asset has nothing to update. The review shows today's stored value."""
    if not entity_id:
        return TurnResult("clarify", "בחרו קודם את הנכס לעדכון.")
    asset = next((r for r in service.my_assets(identity) if r["id"] == str(entity_id)), None)
    if asset is None:
        return TurnResult("denied", policy.DENIED_MESSAGE)
    f = asset.get("fields") or {}
    status = service._sel(f.get(AF.STATUS))
    if status in _ASSET_GONE:
        return TurnResult("info", f"הנכס מסומן כ״{status}״ — אין מה לעדכן.")
    name = f.get(AF.NAME) or "הנכס"
    if entity == fd.FCC_ASSET_SOLD:
        return _start_asset_sale(identity, ids, asset, name, store, today)
    current = f.get(_ASSET_CURRENT[entity])
    if entity == fd.FCC_ASSET_STEP:
        owner = service._sel(f.get(AF.NEXT_STEP_OWNER))
        text = str(current or "").strip()
        note = ("היום: " + (text[:120] + ("…" if len(text) > 120 else "") if text else "לא הוגדר")) + (f" · אחראי: {owner}" if owner else "")
    else:
        num = calc._num(current)
        note = f"היום: {fd.display_value('value', num)}" if num is not None else "היום: לא הוגדר"
    d = _new_draft(identity, ids, entity, DraftOperation.CREATE, fields={}, raw_text=f"intent:{entity}#{uuid.uuid4().hex[:8]}", today=today,
                   extra_ctx={"record_id": asset["id"], "asset_name": name, "goal_title": name, "review_note": note})
    return _persist_new(store, ids, d)


def _sale_warnings(identity, asset: dict, today) -> str:
    """What stays UNTOUCHED by a sale, shown before approval: linked loans remain open, the mortgage field is not reset."""
    f = asset.get("fields") or {}
    lines = []
    linked = [fcc_loans.loan_item(r, today) for r in service.my_loans(identity)
              if asset["id"] in (r.get("fields") or {}).get(LF.RELATED_ASSET, []) and fcc_loans.is_active(r.get("fields") or {})]
    if linked:
        lines.append("⚠️ הלוואות מקושרות שיישארו פתוחות (לא נסגרות אוטומטית): " + ", ".join(
            f"{i['name'] or 'ללא שם'} ({fd.display_value('balance', i['early_closure_balance']) if i['early_closure_balance'] is not None else 'יתרה לא הוגדרה'})"
            for i in linked))
    mortgage = calc._num(f.get(AF.MORTGAGE))
    if mortgage:
        lines.append(f"⚠️ יתרת המשכנתא הרשומה בנכס ({fd.display_value('mortgage', mortgage)}) לא מתאפסת.")
    return "\n".join(lines)


def _start_asset_sale(identity, ids, asset: dict, name: str, store, today) -> TurnResult:
    """TRANSITION: opens the sale draft (date defaults to today as an inferred, editable value). Nothing is written; the
    owner reviews date / full price / own share / what stays open, then approves in a separate turn."""
    f = asset.get("fields") or {}
    ctx = {"record_id": asset["id"], "asset_name": name, "goal_title": name,
           "ownership_pct": calc._num(f.get(AF.OWNERSHIP_PCT)), "sale_warnings": _sale_warnings(identity, asset, today)}
    d = _new_draft(identity, ids, fd.FCC_ASSET_SOLD, DraftOperation.CREATE, fields={}, raw_text=f"intent:{fd.FCC_ASSET_SOLD}#{uuid.uuid4().hex[:8]}",
                   today=today, extra_ctx=ctx)
    d, _rej = _set_fields(d, {"sale_date": today.isoformat()}, strict=False)
    d = replace(d, source_context={**d.source_context, "inferred": ["sale_date"]})
    return _persist_new(store, ids, d)


def _sale_note(d: BusinessDraft) -> str:
    """Review note of a sale: my share (price × Ownership %, unknown stays unknown) + the untouched-items warnings."""
    lines = []
    amount, pct = d.fields.get("sale_amount"), d.source_context.get("ownership_pct")
    if amount:
        lines.append(f"• החלק שלך ({pct:g}%): {fd.display_value('sale_amount', round(amount * pct / 100.0, 2))}" if pct is not None
                     else "• החלק שלך: לא ניתן לחשב — אחוז הבעלות בנכס לא הוגדר")
    if d.source_context.get("sale_warnings"):
        lines.append(d.source_context["sale_warnings"])
    return "\n".join(lines)


def _is_income_goal(g: dict) -> bool:
    return service._category_key((g.get("fields") or {}).get(GF.CATEGORY)) == "income"


OTHER_SOURCE_ID = "other"           # synthetic choice id: "מקור אחר" -> booked on the total income goal + the named source in the note
OTHER_SOURCE_TITLE = "מקור אחר"


def _total_income_goal(goals: list[dict]) -> dict | None:
    """The one top-level income goal (no "Contributes To" parent). Without exactly one, "other source" is not offered."""
    roots = [g for g in goals if _is_income_goal(g) and calc.parent_goal_id(g.get("fields") or {}, GF) is None]
    return roots[0] if len(roots) == 1 else None


def _choices_for(d: BusinessDraft, goals: list[dict]) -> list[dict]:
    cands = writer._cand(goals)
    if d.source_context.get("offer_other"):
        cands.append({"goal_id": OTHER_SOURCE_ID, "title": OTHER_SOURCE_TITLE})
    return cands


def start_intent(identity, intent_id: str, entity_id: str | None = None, *, store=None,
                 today: date | None = None) -> TurnResult:
    """THE structured entry (POST /api/fcc/intent/start). A chip / card action names an intent and, when it is about
    one record, that record's id. It opens a draft on the shared FCC slot with only the intent's fixed fields
    pre-filled; the usual completion flow then asks what is missing -> review -> אשר. Nothing is written here,
    the classifier is not called, and a record that is not the caller's own is answered exactly like a missing one."""
    today = today or date.today()
    spec = fd.INTENTS.get(str(intent_id or ""))
    if spec is None:
        return TurnResult("clarify", "הפעולה לא מוכרת.")
    entity_id = str(entity_id or "").strip() or None
    if intent_id == "loan.close":
        return start_loan_close(identity, entity_id or "", store=store, today=today)
    store, ids, stop = _open_slot(identity, store, "פעולה חדשה")
    if stop is not None:
        return stop
    if spec["entity"] in (fd.FCC_LOAN_BALANCE, fd.FCC_LOAN_PAYMENT, fd.FCC_LOAN_NEW):
        return _start_loan_intent(identity, ids, spec["entity"], entity_id, store, today)
    if spec["entity"] in _ASSET_CURRENT:
        return _start_asset_intent(identity, ids, spec["entity"], entity_id, store, today)
    goals = service.my_goals(identity) if spec.get("target") == "goal" else []
    chosen = None
    if entity_id:
        chosen = next((g for g in goals if g["id"] == entity_id), None)
        if chosen is None:                                    # not found == not yours
            return TurnResult("denied", policy.DENIED_MESSAGE)
    elif spec.get("target_required"):
        return TurnResult("clarify", "בחרו קודם את הרשומה לעדכון.")
    entity = spec["entity"]
    raw = f"intent:{intent_id}#{uuid.uuid4().hex[:8]}"      # unique per draft: a retry of THIS draft is idempotent, a second legitimate entry is not

    if entity == fd.FCC_OBLIGATION:
        d = _new_draft(identity, ids, entity, DraftOperation.CREATE, fields={}, raw_text=raw, today=today)
        return _persist_new(store, ids, d)

    if entity == fd.FCC_GOAL:                                 # update of an existing goal: ask what to change
        original = _goal_original(identity, chosen)
        d = _new_draft(identity, ids, entity, DraftOperation.UPDATE, fields=dict(original), raw_text=raw, today=today,
                       extra_ctx={"record_id": chosen["id"], "goal_title": chosen["fields"].get(GF.TITLE, "")},
                       original=original)
        if d.lifecycle_state is DraftState.READY_FOR_REVIEW:
            d = d.begin_edit()
        return _persist_new(store, ids, d)

    # progress event: kind is fixed by the intent; the goal comes from the card, a unique match, or a choice among OWN goals
    candidates = goals
    if spec.get("goal_filter") == "income":
        candidates = [g for g in goals if _is_income_goal(g)] or goals
    if chosen is None and spec.get("goal_hint"):
        state, matches = writer.resolve_goal(spec["goal_hint"], goals)
        if state == "one":
            chosen = matches[0]
        elif matches:
            candidates = matches
    if chosen is None and not goals:
        return TurnResult("clarify", "אין עדיין יעדים — צרו יעד קודם.")
    fields = {"kind": spec["kind"], "occurred_at": today.isoformat()}
    extra = {}
    offer_other = chosen is None and spec.get("goal_filter") == "income" and _total_income_goal(goals) is not None
    if offer_other:
        extra["offer_other"] = True
    if chosen is not None:
        fields["goal"] = chosen["id"]
        extra["goal_title"] = chosen["fields"].get(GF.TITLE, "")
    d = _new_draft(identity, ids, fd.FCC_EVENT, DraftOperation.CREATE, fields={}, raw_text=raw, today=today, extra_ctx=extra)
    d, _rej = _set_fields(d, fields, strict=False)
    d = replace(d, source_context={**d.source_context, "inferred": ["occurred_at"]})
    return _with_goal_choices(_persist_new(store, ids, d), candidates, other=offer_other)


def complete_execution(identity, entity: str | None = None, *, store=None) -> None:
    """Call ONLY after the confirmed writes were successfully handed to the ActionGateway."""
    actor = policy.resolve_actor(identity)
    if not actor.resolved:
        return
    store = store or _store()
    ids = _ids(identity, actor)
    if ids is None:
        return
    for d in _load_all(store, ids):
        if d.lifecycle_state is DraftState.CONFIRMED and (entity is None or d.entity_type == entity):
            _delete(store, ids, d.entity_type)


# ── continuing an open draft ────────────────────────────────────────────────────────────────────
def _continue(identity, ids, d: BusinessDraft, text, goal_id, extractor, store, today) -> TurnResult:
    lower = text.lower()
    if lower in CANCEL_WORDS:
        _delete(store, ids, d.entity_type)
        return TurnResult("cancelled", "בוטל. לא נרשם דבר.")

    if d.lifecycle_state is DraftState.CONFIRMED:             # approved earlier, execution did not finish
        if lower in CONFIRM_WORDS:
            return _confirmed_result(identity, d)
        return TurnResult("info", "יש פעולה שאושרה וממתינה לביצוע — אשר כדי לנסות שוב, או בטל.", d.entity_type)

    if d.lifecycle_state is DraftState.READY_FOR_REVIEW and lower in CONFIRM_WORDS:
        return _confirm(identity, ids, d, store)
    if d.lifecycle_state is DraftState.READY_FOR_REVIEW and lower in EDIT_WORDS:
        edited = d.begin_edit()
        _save(store, ids, edited, expected=d.idempotency_key)
        return _render(edited)

    expected = d.idempotency_key
    if d.source_context.get("ask_source") and d.lifecycle_state not in (DraftState.READY_FOR_REVIEW, DraftState.EDITING):
        name = text.strip()
        if not name or lower in SKIP_WORDS or lower in CONFIRM_WORDS or lower in EDIT_WORDS:
            return replace_result(_render(d), message=f"שדה חובה — צריך שם למקור.\n{_render(d).message}")
        d2, _rej = _set_fields(d, {"note": f"מקור: {name[:80]}"}, strict=False)
        d2 = replace(d2, source_context={k: v for k, v in d2.source_context.items() if k != "ask_source"})
        return _render(_save(store, ids, d2, expected=expected))
    editing = d.lifecycle_state in (DraftState.READY_FOR_REVIEW, DraftState.EDITING)
    awaiting = None if editing else (_missing(d) or [None])[0]
    if awaiting and lower in SKIP_WORDS:
        return replace_result(_render(d), message=f"שדה חובה — אי אפשר לדלג.\n{_render(d).message}")

    updates: dict[str, Any] = {}
    det_failed = fill_failed = False
    goals = service.my_goals(identity) if d.entity_type in (fd.FCC_EVENT, fd.FCC_FOLLOWUP) else []
    if awaiting == "goal":                                    # choose among the caller's OWN goals only
        chosen = None
        other = bool(d.source_context.get("offer_other")) and (goal_id == OTHER_SOURCE_ID or (not goal_id and text.strip() == OTHER_SOURCE_TITLE))
        if other:
            chosen = _total_income_goal(goals)                # the caller's OWN total income goal; none -> "not recognised" below
        elif goal_id:
            chosen = next((g for g in goals if g["id"] == goal_id), None)
            if chosen is None:
                return TurnResult("denied", policy.DENIED_MESSAGE)
        else:
            chosen = _goal_by_text(goals, text)
        if chosen is None:                                    # no mutation; draft stays open
            noun = fd.record_noun(d.entity_type, d.fields)
            return TurnResult("needs_goal", f"לא זיהיתי את ה{noun} — בחר מהרשימה.", d.entity_type, "goal",
                              _view(d), candidates=_choices_for(d, goals))
        updates["goal"] = chosen["id"]
        d = replace(d, source_context={**d.source_context, "goal_title": chosen["fields"].get(GF.TITLE, ""),
                                       **({"ask_source": True} if other else {})})
        pending_level = d.source_context.get("level")
        if pending_level is not None and d.fields.get("amount") in (None, ""):
            delta = _level_delta(identity, chosen, float(pending_level), today)
            if delta == 0:
                return TurnResult("clarify", f"ההפרשה כבר עומדת על ₪{float(pending_level):,.0f} לחודש — אין מה לעדכן.")
            updates["amount"] = delta
            updates["note"] = f"קביעת רמה: ₪{float(pending_level):,.0f} לחודש"
    else:
        if awaiting:
            value = _deterministic_answer(awaiting, text)
            if value is not None:
                try:
                    _set_fields(d, {awaiting: value}, strict=True)   # valid number / ISO date / presented choice
                    updates[awaiting] = value
                except _VALIDATION_ERRORS:
                    det_failed = True                                # looked like a value but is not a valid one
        if awaiting is None or awaiting not in updates:
            filled = extractor.fill(text, awaiting, dict(d.fields), d.entity_type, today) or {}
            if awaiting is None:                                     # review/edit: any evidenced field change
                updates.update(filled)
            elif awaiting in filled:                                 # extras only ALONGSIDE a valid awaited answer
                try:
                    _set_fields(d, {awaiting: filled[awaiting]}, strict=True)
                    updates.update(filled)
                except _VALIDATION_ERRORS:
                    fill_failed = True

    d2, rejected = _set_fields(d, updates, strict=False) if updates else (d, [])
    answered = bool(updates) and (awaiting is None or awaiting in updates) and awaiting not in rejected
    if not answered or (d2.fields == d.fields and d2.lifecycle_state is d.lifecycle_state and awaiting != "goal"):
        return _not_an_answer(d, awaiting, invalid=det_failed or fill_failed or (awaiting in rejected))
    saved = _save(store, ids, d2, expected=expected)
    return _render(saved)


def _not_an_answer(d: BusinessDraft, awaiting: str | None, *, invalid: bool) -> TurnResult:
    """No mutation: the draft stays exactly as stored. An invalid value re-asks the same field; text that is
    not an answer at all is reported as ``unrelated`` (chat lets it fall through to the agent)."""
    base = _render(d)
    label = fd.LABELS.get(awaiting or "", "")
    if invalid and awaiting:
        return replace(base, state="ask", message=f"❌ ערך לא תקין ל{label}.\n{base.message}")
    if awaiting is None:
        return replace(base, state="unrelated", message=f"לא הבנתי את העריכה.\n{base.message}")
    return replace(base, state="unrelated", message=f"לא הבנתי — {base.message}\n(אפשר לכתוב ״בטל״ לביטול)")


def replace_result(r: TurnResult, **kw) -> TurnResult:
    return replace(r, **kw)


# ── confirm: freeze, final duplicate guard, immutable snapshot ──────────────────────────────────
def _already_applied(identity, write: dict) -> bool:
    fields = write.get("fields") or {}
    if write["op"] == "post" and write["table"] == "Financial Progress Events":
        key = fields.get(EF.IDEMPOTENCY_KEY)
        return any((e.get("fields") or {}).get(EF.IDEMPOTENCY_KEY) == key for e in service.my_events(identity))
    if write["op"] == "post" and write["table"] == "Recurring Obligations":
        name = writer._norm(fields.get(RF.NAME, ""))
        return any(writer._norm((o.get("fields") or {}).get(RF.NAME, "")) == name and (o.get("fields") or {}).get(RF.ACTIVE)
                   for o in service.my_obligations(identity))          # a cancelled (inactive) one may be re-added
    if write["op"] == "patch" and write["table"] == Tables.LOANS and fields.get(LF.STATUS) == fd.LOAN_PAID_OFF:
        rec = next((r for r in service.my_loans(identity) if r["id"] == write.get("record_id")), None)
        return rec is not None and not fcc_loans.is_active(rec.get("fields") or {})      # already closed -> nothing to do
    if write["op"] == "patch" and write["table"] == "Assets" and fields.get(AF.STATUS) == fd.ASSET_SOLD_STATUS:
        rec = next((r for r in service.my_assets(identity) if r["id"] == write.get("record_id")), None)
        return rec is not None and service._sel((rec.get("fields") or {}).get(AF.STATUS)) == fd.ASSET_SOLD_STATUS
    if write["op"] == "patch" and write["table"] in (Tables.LOANS, "Assets") and LF.STATUS not in fields:
        rows = service.my_loans(identity) if write["table"] == Tables.LOANS else service.my_assets(identity)
        rec = next((r for r in rows if r["id"] == write.get("record_id")), None)
        cur = (rec or {}).get("fields") or {}
        same = lambda have, want: (writer._norm(str(have or "")) == writer._norm(want)) if isinstance(want, str) else calc._num(have) == want
        return rec is not None and all(same(cur.get(k), v) for k, v in fields.items())    # the record already holds exactly this
    if write["op"] == "post" and write["table"] == Tables.LOANS:
        name = writer._norm(fields.get(LF.NAME, ""))
        return any(writer._norm((r.get("fields") or {}).get(LF.NAME, "")) == name and fcc_loans.is_active(r.get("fields") or {})
                   for r in service.my_loans(identity))                                           # same-named ACTIVE loan exists
    if write["op"] == "post" and write["table"] == "Financial Goals":
        title = writer._norm(fields.get(GF.TITLE, ""))
        return any(writer._norm((g.get("fields") or {}).get(GF.TITLE, "")) == title for g in service.my_goals(identity))
    return False


def _confirm(identity, ids, d: BusinessDraft, store) -> TurnResult:
    try:
        confirmed, snapshot = d.confirm(adapter=fd.ADAPTER)
    except _VALIDATION_ERRORS as exc:
        return TurnResult("clarify", f"❌ {exc}", d.entity_type)
    writes = [w for w in snapshot.tool_inputs["writes"] if not _already_applied(identity, w)]
    if not writes:
        _delete(store, ids, d.entity_type)
        return TurnResult("duplicate", "כבר נרשם — לא נוצרה כפילות.", d.entity_type)
    stored = _save(store, ids, confirmed, expected=d.idempotency_key)
    return _confirmed_result(identity, stored, writes)


def _confirmed_result(identity, d: BusinessDraft, writes: list | None = None) -> TurnResult:
    snap = d.snapshot
    if writes is None:
        writes = [w for w in snap.tool_inputs["writes"] if not _already_applied(identity, w)]
        if not writes:
            return TurnResult("duplicate", "כבר נרשם — לא נוצרה כפילות.", d.entity_type)
    return TurnResult("confirmed", "מאושר — נרשם.", d.entity_type, None, _view(d), snapshot={
        "draft_id": snap.draft_id, "entity": snap.entity_type, "tool_name": snap.tool_name,
        "confirmed_at": snap.confirmed_at, "writes": writes})


# ── starting a new draft ────────────────────────────────────────────────────────────────────────
def _new_draft(identity, ids, entity, operation, *, fields, raw_text, today, extra_ctx=None, original=None):
    ctx = {"raw_text": raw_text[:2000], "today": today.isoformat(), **(extra_ctx or {})}
    return create_draft(
        entity_type=entity, operation=operation, tenant_id=ids["tenant_id"], actor_role=str(identity.role),
        actor_user_id=ids["actor_user_id"], source_channel=fd.FCC_CHANNEL, sender=ids["sender"],
        fields=fields, source_context=ctx, identity={"profile_id": ids["profile_id"], "user_id": ids["actor_user_id"]},
        original_fields=original, actor_display_name=getattr(identity, "display_name", "") or "",
        contracts=fd.FCC_CONTRACTS,
    )


def _persist_new(store, ids, d: BusinessDraft) -> TurnResult:
    try:
        stored = store.create_business_draft(ids["sender"], d, channel=fd.FCC_CHANNEL, contracts=fd.FCC_CONTRACTS)
    except DraftConflictError:
        return TurnResult("info", "יש פעולה שאושרה וממתינה לביצוע — יש לסיים או לבטל אותה קודם.")
    return _render(stored)


def _with_goal_choices(res: TurnResult, goals: list[dict], other: bool = False) -> TurnResult:
    """A draft that still lacks its goal asks for it, offering only the caller's own goals (+ "מקור אחר" for income)."""
    if res.awaiting == "goal":
        cands = writer._cand(goals) + ([{"goal_id": OTHER_SOURCE_ID, "title": OTHER_SOURCE_TITLE}] if other else [])
        return replace(res, state="needs_goal", candidates=cands)
    return res


def _goal_original(identity, goal: dict) -> dict:
    f = goal.get("fields") or {}

    def sel(key):
        v = f.get(key)
        return v.get("name") if isinstance(v, dict) else v

    events = calc.parse_events([e for e in service.my_events(identity)
                                if goal["id"] in service._goal_ids_of(e)], EF)
    base = calc._num(f.get(GF.TARGET_AMOUNT))
    target = calc.effective_target(base, [e for e in events if not e.superseded], date.today())
    original = {"title": f.get(GF.TITLE), "target_amount": target, "category": sel(GF.CATEGORY),
                "period_type": sel(GF.PERIOD_TYPE), "calc_method": sel(GF.CALC_METHOD),
                "end_date": f.get(GF.END_DATE), "start_date": f.get(GF.START_DATE)}
    return {k: v for k, v in original.items() if v not in (None, "")}


_OB_KEYS = ("frequency", "scope", "review_status", "obligation_type", "essentiality", "vendor", "next_charge_date")


def _obligation_original(rec: dict) -> dict:
    f = rec.get("fields") or {}
    sel = service._sel
    original = {"name": f.get(RF.NAME), "amount": calc._num(f.get(RF.AMOUNT)), "scope": sel(f.get(RF.SCOPE)),
                "frequency": sel(f.get(RF.FREQUENCY)), "review_status": sel(f.get(RF.REVIEW_STATUS)),
                "saving": calc._num(f.get(RF.POTENTIAL_SAVING)), "obligation_type": sel(f.get(RF.TYPE)),
                "essentiality": sel(f.get(RF.ESSENTIALITY)), "vendor": f.get(RF.VENDOR),
                "next_charge_date": f.get(RF.NEXT_CHARGE)}
    original["status"] = "active" if f.get(RF.ACTIVE) else "inactive"
    return {k: v for k, v in original.items() if v not in (None, "")}


def _find_active_obligation(identity, name):
    if not name:
        return None
    for rec in service.my_obligations(identity):
        f = rec.get("fields") or {}
        if writer._norm(f.get(RF.NAME, "")) == writer._norm(name) and f.get(RF.ACTIVE):
            return rec
    return None


def _start_obligation(identity, ids, intent, text, extractor, store, today) -> TurnResult:
    """A commitment is created/updated in Recurring Obligations — never logged as a progress event, and never
    rewritten monthly (an existing one with the same name is UPDATED, a new name is CREATED)."""
    name = intent.get("title") or intent.get("goal_hint")
    existing = _find_active_obligation(identity, name)
    if intent["action"] == "deactivate_obligation":
        if existing is None:
            return TurnResult("clarify", f"לא מצאתי התחייבות פעילה בשם {name or ''}. אין מה לסמן כמבוטלת.".replace("  ", " "))
        original = _obligation_original(existing)
        d = _new_draft(identity, ids, fd.FCC_OBLIGATION, DraftOperation.UPDATE, fields=dict(original), raw_text=text,
                       today=today, extra_ctx={"record_id": existing["id"]}, original=original)
        d, _rej = _set_fields(d, {"status": "inactive"}, strict=False)
        return _persist_new(store, ids, d)
    updates = {k: intent[k] for k in _OB_KEYS if k in intent}
    if "amount" in intent:
        updates["amount"] = intent["amount"]
    if "saving" in intent:
        updates["saving"] = intent["saving"]
    if existing is not None:
        original = _obligation_original(existing)
        d = _new_draft(identity, ids, fd.FCC_OBLIGATION, DraftOperation.UPDATE, fields=dict(original), raw_text=text,
                       today=today, extra_ctx={"record_id": existing["id"]}, original=original)
        d, _rej = _set_fields(d, updates, strict=False)
        if d.fields == original:
            return TurnResult("clarify", "מה לעדכן בהתחייבות (סכום, תדירות, החלטה, חיסכון)?")
        return _persist_new(store, ids, d)
    ctx = None
    if updates.get("review_status") and name:      # acting on a commitment that is not tracked yet -> say so in the review
        label = fd.VALUE_LABELS["review_status"].get(updates["review_status"], updates["review_status"])
        ctx = {"review_note": f"לא מצאתי התחייבות בשם {name}. לרשום אותה חדשה ולסמן: {label}?"}
    d = _new_draft(identity, ids, fd.FCC_OBLIGATION, DraftOperation.CREATE, fields={}, raw_text=text, today=today,
                   extra_ctx=ctx)
    d, _rej = _set_fields(d, {k: v for k, v in {"name": name, **updates}.items() if v is not None}, strict=False)
    return _persist_new(store, ids, d)


def _level_delta(identity, goal: dict, level: float, today: date) -> float:
    """Change needed to bring the goal's standing monthly level to ``level`` (never guessed from the text)."""
    events = calc.parse_events([e for e in service.my_events(identity) if goal["id"] in service._goal_ids_of(e)], EF)
    return round(level - calc.monthly_level_now(events, today), 2)


def _start(identity, actor, ids, text, goal_id, extractor, store, today) -> TurnResult:
    goals = service.my_goals(identity)
    intent = writer.validate_intent(extractor.classify(text, [g["fields"].get(GF.TITLE, "") for g in goals], today))
    if intent is None:
        return TurnResult("clarify", "לא הבנתי את הבקשה — אפשר לנסח שוב?")
    action = intent["action"]

    if action in ("upsert_obligation", "deactivate_obligation"):
        return _start_obligation(identity, ids, intent, text, extractor, store, today)

    if action == "create_goal":
        title = intent.get("title") or intent.get("goal_hint")
        if title and any(writer._norm(g["fields"].get(GF.TITLE, "")) == writer._norm(title) for g in goals):
            return TurnResult("duplicate", "כבר קיים יעד בשם הזה.")
        d = _new_draft(identity, ids, fd.FCC_GOAL, DraftOperation.CREATE, fields={}, raw_text=text, today=today)
        updates = {"title": title, "target_amount": intent.get("target", intent.get("amount")),
                   **{k: intent[k] for k in ("category", "period_type", "calc_method", "end_date", "start_date")
                      if k in intent}}
        d, _rej = _set_fields(d, {k: v for k, v in updates.items() if v is not None}, strict=False)
        return _persist_new(store, ids, d)

    state, matches = writer.resolve_goal(intent["goal_hint"], goals)
    if goal_id:
        chosen = [g for g in goals if g["id"] == goal_id]
        if not chosen:
            return TurnResult("denied", policy.DENIED_MESSAGE)
        state, matches = "one", chosen
    goal = matches[0] if state == "one" else None

    if action in ("update_goal", "rename_goal"):
        if goal is None:
            return TurnResult("needs_goal", "איזה יעד לעדכן?", candidates=writer._cand(matches or goals))
        original = _goal_original(identity, goal)
        d = _new_draft(identity, ids, fd.FCC_GOAL, DraftOperation.UPDATE, fields=dict(original), raw_text=text,
                       today=today, extra_ctx={"record_id": goal["id"], "goal_title": goal["fields"].get(GF.TITLE, "")},
                       original=original)
        updates = {k: intent[k] for k in ("category", "period_type", "calc_method", "end_date", "start_date") if k in intent}
        if "target" in intent or "amount" in intent:
            updates["target_amount"] = intent.get("target", intent.get("amount"))
        if action == "rename_goal" and intent.get("new_title"):
            updates["title"] = intent["new_title"]
        d, _rej = _set_fields(d, updates, strict=False)
        if d.fields == original:
            return TurnResult("clarify", "מה לעדכן ביעד (סכום, קטגוריה, תקופה, שיטה, תאריכים, שם)?")
        return _persist_new(store, ids, d)

    if action in ("log_progress", "set_target", "note"):
        kind = {"set_target": "target_change", "note": "note"}.get(action, intent.get("kind", "one_time"))
        amount = intent.get("target") if action == "set_target" else intent.get("amount")
        fields = {"kind": kind, "occurred_at": today.isoformat()}
        level = intent.get("level") if action == "log_progress" else None
        if level is not None:
            kind = fields["kind"] = calc.MONTHLY_RECURRING
            if goal is not None:
                amount = _level_delta(identity, goal, level, today)
                if amount == 0:
                    return TurnResult("clarify", f"ההפרשה כבר עומדת על ₪{level:,.0f} לחודש — אין מה לעדכן.")
                fields["note"] = f"קביעת רמה: ₪{level:,.0f} לחודש"
        if action == "note":
            amount = 0
            fields["note"] = intent.get("note") or text
        elif intent.get("note"):
            fields["note"] = intent["note"]
        if amount is not None:
            fields["amount"] = amount
        extra = {}
        if goal is not None:
            fields["goal"] = goal["id"]
            extra["goal_title"] = goal["fields"].get(GF.TITLE, "")
        elif level is not None:
            extra["level"] = level                     # converted to a delta once the goal is chosen
        d = _new_draft(identity, ids, fd.FCC_EVENT, DraftOperation.CREATE, fields={}, raw_text=text, today=today,
                       extra_ctx=extra)
        d, _rej = _set_fields(d, fields, strict=False)
        if goal is not None and "amount" in d.fields:
            key = fd.event_idempotency_key(ids["profile_id"], goal["id"], d.fields["kind"], d.fields["amount"],
                                           d.fields["occurred_at"], text)
            if any((e.get("fields") or {}).get(EF.IDEMPOTENCY_KEY) == key for e in service.my_events(identity)):
                return TurnResult("duplicate", "האירוע כבר נרשם.", fd.FCC_EVENT)
        return _with_goal_choices(_persist_new(store, ids, d), matches or goals)

    if action == "follow_up":
        title = intent.get("task_title") or (goal["fields"].get(GF.TITLE) if goal else None)
        d = _new_draft(identity, ids, fd.FCC_FOLLOWUP, DraftOperation.CREATE, fields={}, raw_text=text, today=today,
                       extra_ctx={"goal_title": goal["fields"].get(GF.TITLE, "")} if goal else None)
        d, _rej = _set_fields(d, {"title": title, **({"goal": goal["id"]} if goal else {})}, strict=False)
        if goal is not None and title:
            for rec in service.open_followups(identity, goal["id"]):
                if writer._norm(rec["fields"].get(TaskFields.NAME, "")) == writer._norm(title):
                    return TurnResult("duplicate", "משימה פתוחה זהה כבר קיימת.", fd.FCC_FOLLOWUP)
        return _with_goal_choices(_persist_new(store, ids, d), matches or goals)

    return TurnResult("clarify", "לא הבנתי את הבקשה — אפשר לנסח שוב?")
