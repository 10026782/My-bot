# core/action_gateway.py — Action Gateway (Stage B)
#
# ActionContract הוא מקור האמת לכל mutation עסקי.
# ExecutionReceipt הוא ההוכחה היחידה לביצוע.
# Agent הוא מקור סיגנלים בלבד — לא מקור סמכות.
#
# FEATURE_ACTION_GATEWAY=false כברירת מחדל.
# כשהדגל כבוי — כל המסלולים הקיימים ממשיכים לפעול ללא שינוי.
# כשהדגל פעיל — כל mutating tool חייב לעבור דרך Gateway (§6 SPEC).

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from tool_registry import needs_approval

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# BUG-074 — approval authority check
#
# approve() is the sole enforcement boundary for every approval path
# (Telegram callback + all free-text confirm routes). A confirming identity
# must independently hold approval authority (owner, or the "actions.approve"
# permission) — being the same person who requested the action is not
# sufficient, even though every free-text route below only ever matches
# contracts belonging to the confirming user's own canonical_user_id.
# ══════════════════════════════════════════════════

def _has_approval_authority(role: str) -> bool:
    from identity import Role, ROLE_PERMISSIONS
    return role == Role.OWNER or "actions.approve" in ROLE_PERMISSIONS.get(role, set())


def _is_internal_role(role: str) -> bool:
    from identity import Role
    return role in (Role.OWNER, Role.PARTNER, Role.MANAGER, Role.EMPLOYEE)


# ══════════════════════════════════════════════════
# BUG-076 — "confirmation" vs "approval" policy
#
# Two distinct concepts (product decision, 2026-07-06):
#   - APPROVAL_POLICY_APPROVAL (default, strict): a privileged identity
#     (owner / "actions.approve") must authorize a sensitive action. This is
#     the BUG-074 rule above, unchanged for everything except the narrow
#     carve-out below.
#   - APPROVAL_POLICY_SELF_CONFIRM: the requester merely confirms the system
#     understood a low-risk draft/preview correctly — no privileged approver
#     needed. Reserved for a tight, explicitly allowlisted class of lead
#     writes (see classify_approval_policy()) — never for deletion, protected
#     fields (status/score/owner-assignment/tier), financial/legal/deal
#     mutation, outbound messaging, or bulk actions. Anything outside the
#     allowlist falls back to APPROVAL_POLICY_APPROVAL automatically — the
#     classification is computed here, centrally, from the actual tool_name/
#     tool_inputs being proposed, never trusted from the caller.
# ══════════════════════════════════════════════════

APPROVAL_POLICY_APPROVAL     = "approval"
APPROVAL_POLICY_SELF_CONFIRM = "self_confirm"

_LEAD_CAPTURE_TABLE = "Leads"


def _lead_safe_fields() -> tuple[frozenset, frozenset]:
    """
    Lazy import to avoid module-load-order coupling to airtable_schema.

    create_fields: matches exactly what _write_one_lead()/_propose_lead_write()
    (core/lead_candidate_handler.py) already write for a brand-new lead —
    establishing a record's initial state is not a "status escalation" (there
    is no prior state to escalate from).

    update_fields: deliberately narrower — matches exactly what
    _propose_lead_write() writes for an EXISTING lead today. No status/score/
    tier/owner/next-step field may ever appear here: those are assignment/
    escalation, not safe self-confirm.
    """
    from airtable_schema import LeadFields
    create_fields = frozenset({
        LeadFields.NAME, LeadFields.PHONE, LeadFields.CHANNEL, LeadFields.MEMORY_KEY,
        LeadFields.DOMAIN, LeadFields.SOURCE, LeadFields.STATUS, LeadFields.SUMMARY,
        LeadFields.SCORE, LeadFields.SENDER_ID,
    })
    update_fields = frozenset({
        LeadFields.PHONE, LeadFields.SUMMARY, LeadFields.DOMAIN,
    })
    return create_fields, update_fields


def classify_approval_policy(tool_name: str, tool_inputs: dict) -> str:
    """
    Returns APPROVAL_POLICY_SELF_CONFIRM ONLY for a narrow, allowlisted class
    of safe lead-capture writes on the Leads table (create, or update
    restricted to {phone, summary, domain}). Everything else — any other
    tool, any other table, or any Leads write that touches a field outside
    the allowlist (status, score, tier, owner, next-step, or anything not
    explicitly listed) — is APPROVAL_POLICY_APPROVAL, the strict default.
    """
    if tool_name not in ("airtable_add", "airtable_update"):
        return APPROVAL_POLICY_APPROVAL
    if not isinstance(tool_inputs, dict) or tool_inputs.get("table") != _LEAD_CAPTURE_TABLE:
        return APPROVAL_POLICY_APPROVAL

    fields = tool_inputs.get("fields")
    if not isinstance(fields, dict) or not fields:
        return APPROVAL_POLICY_APPROVAL

    create_fields, update_fields = _lead_safe_fields()
    safe_fields = create_fields if tool_name == "airtable_add" else update_fields
    if not set(fields.keys()) <= safe_fields:
        return APPROVAL_POLICY_APPROVAL

    return APPROVAL_POLICY_SELF_CONFIRM


# ══════════════════════════════════════════════════
# 3.1 — ActionContract
# ══════════════════════════════════════════════════

@dataclass
class ActionContract:
    contract_id:                str
    tenant_id:                  str
    canonical_user_id:          str    # = identity.memory_key
    tool_name:                  str
    normalized_payload:         dict   # אחרי normalize — לא raw input
    business_action_fingerprint: str   # hash(tenant+user+tool+payload)
    origin_channel:             str
    origin_chat_id:             str
    requires_approval:          bool
    status:                     str    # draft|pending|approved|rejected|executing|executed|failed
    created_at:                 float
    approved_by:                str | None = None
    approved_at:                float | None = None
    agent_observations:         list[dict] = field(default_factory=list)  # §5 — לעולם לא סמכות
    # BUG-C89-APPROVAL-IDENTITY: the resolved actor identity at propose time —
    # canonical_user_id/origin_chat_id may be a memory_key (e.g. "boss_hq:eliyahu"),
    # not a channel external_id, so they must never be fed back into
    # resolve_identity() at execution time. These fields are the source of
    # truth for who the dispatcher runs as when the contract is approved.
    actor_role:                 str = ""
    actor_user_id:               str = ""
    actor_display_name:         str = ""
    actor_domain_id:             str = ""
    actor_external_id:           str = ""
    actor_allowed_domains:       list = field(default_factory=list)
    # BUG-076: "approval" (default, strict — owner/actions.approve required)
    # or "self_confirm" (requester may confirm their own low-risk draft —
    # see classify_approval_policy()). Computed once at propose time from the
    # actual tool_name/tool_inputs, never trusted from the caller.
    approval_policy:             str = APPROVAL_POLICY_APPROVAL
    # BUG-091: which Python call site proposed this contract — "agent" (raw
    # LLM tool_use, the default/least-trusted) or a specific trusted internal
    # source (e.g. "lead_capture"). Set once at propose_action() time from an
    # explicit keyword argument, never from tool_inputs — a "_source" key
    # inside tool_inputs is Claude-controlled data and must never be trusted
    # as a security boundary. Read by _make_dispatch_executor() at execution
    # time and passed to dispatch_tool(trusted_source=...).
    trusted_source:              str = "agent"
    # PR-0 / BUG-PENDING-APPROVAL-B: context-poisoning guard. context_interrupted
    # is set by mark_context_interrupted() when a message arrives that is not
    # itself a confirm/cancel/disambiguation resolution for this contract —
    # i.e. the user has moved on since the preview was shown. reconfirmation_required
    # is set once route_confirmation_word() has re-shown the business description
    # in response to a "כן" that arrived after an interruption; only a second
    # "כן" (with reconfirmation_required=True) actually executes. See
    # route_confirmation_word() for the state machine.
    context_interrupted:         bool = False
    reconfirmation_required:     bool = False
    # Global ingress gate follow-up: distinct from context_interrupted — set
    # when the gate could not positively record whether this contract's
    # context was interrupted (the primary mark raised and even the
    # independent fallback path failed). Never silently treated as "context
    # intact": route_confirmation_word() gates on this exactly like a real
    # interruption, but it stays a separate, observable field so a genuine
    # interruption is never confused in logs/audits with "we don't actually
    # know." Does not block the incoming message itself from being routed —
    # only affects whether a later bare confirm executes directly.
    context_integrity_unknown:   bool = False
    # PR-0C Phase 4B0 — persisted version metadata, bumped on save. NOT a
    # concurrency-control mechanism today: no transition path in this codebase
    # checks or CAS's on this value. A real claim mechanism using this (or a
    # replacement) is tracked separately as Phase 4B0.1.
    version:                     int = 1


# ══════════════════════════════════════════════════
# GatewayResult — חוזה אחיד (מקביל ל-GateResult ב-decision_pipeline.py)
# ══════════════════════════════════════════════════

@dataclass
class GatewayResult:
    ok:           bool
    reason:       str
    contract_id:  str | None = None
    user_message: str | None = None   # מה להציג למשתמש (None = שקט)


# ══════════════════════════════════════════════════
# §5 — AgentObservation
# לא user-facing, לא executable, signal בלבד.
# ══════════════════════════════════════════════════

@dataclass
class AgentObservation:
    contract_id:  str | None
    kind:         str    # "uncertainty" | "contradiction" | "concern"
    text:         str
    created_at:   float


# ══════════════════════════════════════════════════
# §15.1-15.3 — Single Speaker Enforcement
# ActionFact: structural only, no NL text.
# GatewayReply: the ONLY type allowed to carry action-status text.
# AgentReply: free-text/personality, never action-status.
# ══════════════════════════════════════════════════

@dataclass(frozen=True)
class ActionFact:
    """מבני בלבד. אין בו משפט בשפה טבעית. אסור להעביר אותו ישירות לשליחה."""
    tool_name:         str
    contract_id:       str
    outcome:           str    # "executed" | "failed" | "pending" | "rejected"
    record_id:         str | None
    error_code:        str | None
    raw_tool_response: dict


@dataclass(frozen=True)
class GatewayReply:
    """הטיפוס היחיד שמותר לו להכיל ניסוח סטטוס פעולה.
    מיוצר אך ורק מתוך ActionFact ע"י compose_status_reply()."""
    text: str
    fact: ActionFact


@dataclass(frozen=True)
class AgentReply:
    """טקסט חופשי, טון, אישיות, שיחה.
    לעולם לא כולל ניסוח מצב פעולה בהקשר ActionContract."""
    text: str
    contract_id: str | None = None


# regex לזיהוי טענות סטטוס-פעולה בטקסט Agent — safety belt בלבד (§15.3).
# דורש שמילת-הסטטוס לא תיסיים ב-? ישירות (שאלה), ולא תופיע אחרי "לא ".
_ACTION_STATUS_PATTERN = re.compile(
    r"(?<!\bלא )\b(נוסף|נוספה|נוספו|עודכן|עודכנה|עודכנו|"
    r"בוצע|בוצעה|נשלח|נשלחה|נשמר|נשמרה|נוצר|נוצרה|הוסף|הוספה|"
    r"הוספתי|עדכנתי|שלחתי|יצרתי|שמרתי)\b(?!\?)",
    re.UNICODE,
)


# ══════════════════════════════════════════════════
# §10 §4 — DuplicateOverrideApproval
# override חד-פעמי לפעולה שכבר executed.
# ══════════════════════════════════════════════════

@dataclass
class DuplicateOverrideApproval:
    contract_id:          str
    business_fingerprint: str
    challenge_hash:       str    # hash בלבד — לא נשמר קוד גולמי
    issued_to:            str    # canonical_user_id של הבעלים המאומת בלבד
    issued_at:            float
    ttl_seconds:          int    # קצר — 300 שניות
    consumed:             bool   # False עד שימוש; True אחרי — חד-פעמי


# ══════════════════════════════════════════════════
# §19 / §15.7-ב — canonical tool selection
# נקרא *לפני* יצירת ActionContract — מחזיר tool_name יחיד ומוכרע.
# מונע מצב שבו שני contracts מקבילים נוצרים לאותה business action.
# ══════════════════════════════════════════════════

# מילים שמצביעות על בקשה מפורשת ל-Sheets/Drive
_SHEETS_KEYWORDS = frozenset({
    "שיטס", "sheets", "google sheets", "גוגל שיטס",
    "גיליון", "גליון", "spreadsheet", "טבלה ב-google",
})
_DRIVE_KEYWORDS = frozenset({
    "דרייב", "drive", "google drive", "גוגל דרייב", "קובץ ב-drive",
})

# ברירת מחדל per tool-category — אפשר להרחיב
_CANONICAL_TOOL_DEFAULT = "airtable_add"


def resolve_canonical_tool(
    tool_hint: str,
    tool_inputs: dict,
    user_text: str = "",
) -> str:
    """
    מחזיר tool_name יחיד ומוכרע לפני יצירת ActionContract.
    ברירת מחדל: airtable_add.
    sheets_append/drive_upload מוחזרים רק אם המשתמש ביקש Sheets/Drive במפורש.
    """
    if tool_hint in ("sheets_append", "drive_upload", "drive_create"):
        lower = user_text.lower()
        if tool_hint == "sheets_append" and any(k in lower for k in _SHEETS_KEYWORDS):
            return "sheets_append"
        if tool_hint in ("drive_upload", "drive_create") and any(k in lower for k in _DRIVE_KEYWORDS):
            return tool_hint
        # hint was sheets/drive but user didn't explicitly ask — fall back to Airtable
        logger.info(
            "[ActionGateway] resolve_canonical_tool: overriding %s → %s "
            "(no explicit Sheets/Drive request in user_text)",
            tool_hint, _CANONICAL_TOOL_DEFAULT,
        )
        return _CANONICAL_TOOL_DEFAULT
    # all other tools: trust the caller
    return tool_hint


def _hash_challenge(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _gen_challenge_code() -> str:
    return str(random.randint(100000, 999999))


# ══════════════════════════════════════════════════
# Execution Ledger — ממשק עמיד (§7, §8)
# ממשק מופרד מ-ActionGateway; backing ראשוני = RAM + Airtable stub.
# ══════════════════════════════════════════════════

class ExecutionLedger:
    """
    שכבת אחסון עמידה ל-ActionContracts.
    RAM + כתיבה ל-Airtable ייעודי (ActionContracts) כאשר הוא מוגדר.
    """

    def __init__(self, airtable_writer: Callable | None = None, repository=None):
        self._store: dict[str, ActionContract] = {}    # contract_id → contract (CACHE, not source of truth)
        self._by_fingerprint: dict[str, str] = {}      # fingerprint → contract_id
        self._lock = threading.Lock()
        self._airtable_writer = airtable_writer        # callable(contract) → None — legacy best-effort mirror (Phase 4A)
        # PR-0C Phase 4B0: ActionContractRepository | None. When set, find_by_id()
        # falls back to it on a cache miss (restart/second-instance recovery) and
        # hydrates the cache. There is no status-transition use of this
        # repository — update_status() below remains a bare in-memory update
        # regardless of whether a repository is set. Deliberately None on the
        # live singleton for now (see _ledger_singleton comment) — this is
        # tested, inert infrastructure, not yet an activated live
        # persistence/recovery path.
        self._repository = repository

    def save(self, contract: ActionContract) -> None:
        with self._lock:
            self._store[contract.contract_id] = contract
            self._by_fingerprint[contract.business_action_fingerprint] = contract.contract_id
        if self._airtable_writer:
            try:
                self._airtable_writer(contract)
            except Exception as exc:
                logger.warning("[ActionGateway] Airtable write failed (RAM intact): %s", exc)
        if self._repository:
            try:
                self._repository.save(contract)
            except Exception as exc:
                logger.warning("[ActionGateway] repository save failed (RAM intact): %s", exc)

    def find_by_id(self, contract_id: str) -> ActionContract | None:
        cached = self._store.get(contract_id)
        if cached is not None:
            return cached
        if not self._repository:
            return None
        # Cache miss — fall back to the durable repository (restart / second
        # instance recovery). get() already fails closed (returns None) on
        # not-found, store-unreachable, or expiry; never fabricate a contract
        # here if it returns None.
        hydrated = self._repository.get(contract_id)
        if hydrated is None:
            return None
        with self._lock:
            self._store[contract_id] = hydrated
            self._by_fingerprint[hydrated.business_action_fingerprint] = contract_id
        return hydrated

    def find_by_fingerprint(self, fingerprint: str) -> ActionContract | None:
        cid = self._by_fingerprint.get(fingerprint)
        return self._store.get(cid) if cid else None

    def find_live_by_user(self, canonical_user_id: str) -> list[ActionContract]:
        """מחזיר contracts חיים (pending) לזהות קנונית."""
        now = time.time()
        result = []
        for c in self._store.values():
            if c.canonical_user_id != canonical_user_id:
                continue
            if c.status == "pending":
                result.append(c)
        return result

    def find_most_recent_by_user(self, canonical_user_id: str) -> "ActionContract | None":
        """Most recent contract (any status) for this identity — used to give
        a specific "your previous action was superseded" message instead of a
        generic "nothing pending" when the most recent contract was closed by
        a second interruption rather than executed/cancelled by the user."""
        candidates = [c for c in self._store.values() if c.canonical_user_id == canonical_user_id]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.created_at)

    def update_status(self, contract_id: str, status: str, **kwargs) -> None:
        with self._lock:
            c = self._store.get(contract_id)
            if not c:
                return
            c.status = status
            for k, v in kwargs.items():
                if hasattr(c, k):
                    setattr(c, k, v)
        if self._airtable_writer:
            try:
                self._airtable_writer(self._store[contract_id])
            except Exception as exc:
                logger.warning("[ActionGateway] Airtable status update failed: %s", exc)

    # ── PR-0 / BUG-PENDING-APPROVAL-B ────────────────────────────────

    def mark_context_interrupted(self, canonical_user_id: str) -> None:
        """כל pending contract חי לזהות זו מטופל לפי bounded one-shot FSM:
        contract שטרם הציג reconfirmation (reconfirmation_required=False)
        מסומן context_interrupted=True (עדיין ניתן להצלה בסיבוב אחד). contract
        שכבר הציג reconfirmation פעם אחת (reconfirmation_required=True) —
        הפרעה נוספת מבטלת אותו סופית (status="superseded"), לא פותחת סיבוב
        שני. אין מעגלי reconfirmation חוזרים — ראה route_confirmation_word()."""
        with self._lock:
            for c in self._store.values():
                if c.canonical_user_id == canonical_user_id and c.status == "pending":
                    if c.reconfirmation_required:
                        c.status = "superseded"
                    else:
                        c.context_interrupted = True

    def mark_context_integrity_unknown(self, canonical_user_id: str) -> None:
        """Independent fallback primitive — a separately-written method
        touching a different field, so a bug specific to
        mark_context_interrupted()'s own logic doesn't also break this one.
        Used by app.py's ingress gate when the primary mark_context_interrupted()
        call itself raised — a marking failure must never be indistinguishable
        from "context intact"; route_confirmation_word() gates on this flag
        exactly like a real interruption, but keeps it a separate, observable
        field rather than conflating "known interrupted" with "unknown".
        Same bounded one-shot rule as mark_context_interrupted(): a contract
        that already required reconfirmation once is superseded, not re-armed."""
        with self._lock:
            for c in self._store.values():
                if c.canonical_user_id == canonical_user_id and c.status == "pending":
                    if c.reconfirmation_required:
                        c.status = "superseded"
                    else:
                        c.context_integrity_unknown = True


# ══════════════════════════════════════════════════
# PR-0 / BUG-PENDING-APPROVAL-B — business description for reconfirmation
# תיאור עסקי קריא בלבד — לעולם לא internal contract_id בלבד (DoD #3/#9).
# ══════════════════════════════════════════════════

def _describe_contract_for_reconfirmation(contract: ActionContract) -> str:
    payload = contract.normalized_payload or {}
    if contract.tool_name in ("airtable_add", "airtable_update") and payload.get("table") == _LEAD_CAPTURE_TABLE:
        fields = payload.get("fields") or {}
        try:
            from airtable_schema import LeadFields
            parts = [
                fields.get(LeadFields.NAME, ""),
                fields.get(LeadFields.PHONE, ""),
                fields.get(LeadFields.DOMAIN, ""),
            ]
        except Exception:
            parts = []
        parts = [p for p in parts if p]
        verb = "יצירת ליד" if contract.tool_name == "airtable_add" else "עדכון ליד"
        return f"{verb}: {', '.join(parts)}" if parts else verb
    table = payload.get("table") or payload.get("spreadsheet_name") or ""
    return f"{contract.tool_name} / {table}" if table else contract.tool_name


# ══════════════════════════════════════════════════
# ActionGateway — Gateway מרכזי
# ══════════════════════════════════════════════════

class ActionGateway:
    """
    Gateway מרכזי לכל פעולה עסקית מוטטת (mutating).

    כשהדגל FEATURE_ACTION_GATEWAY=false, Gateway פועל ב-shadow mode:
    propose_action() רושם contracts ב-ledger לצרכי מעקב, אבל לא חוסם
    את המסלולים הקיימים. הקוד הקורא אחראי לבדוק את הדגל.
    """

    def __init__(
        self,
        ledger: ExecutionLedger | None = None,
        tool_executor: Callable | None = None,
    ):
        self._ledger = ledger or ExecutionLedger()
        self._tool_executor = tool_executor
        self._overrides: dict[str, DuplicateOverrideApproval] = {}
        self._override_lock = threading.Lock()
        # disambiguation state: user_id → ordered list of pending contracts
        # set when route_confirmation_word finds >1 pending contracts.
        # cleared on next route_disambiguation() call regardless of outcome.
        self._disambiguation: dict[str, list[ActionContract]] = {}
        self._disambiguation_lock = threading.Lock()

    # ── §3.2 — fingerprint ──────────────────────────────────────────

    @staticmethod
    def compute_business_fingerprint(
        tenant_id: str,
        canonical_user_id: str,
        tool_name: str,
        normalized_payload: dict,
    ) -> str:
        raw = json.dumps(
            {
                "tenant_id":          tenant_id,
                "canonical_user_id":  canonical_user_id,
                "tool_name":          tool_name,
                "normalized_payload": normalized_payload,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha1(raw.encode()).hexdigest()[:24]

    @staticmethod
    def normalize_payload(tool_inputs: dict) -> dict:
        """אחיד לפי sort_keys — payload קנוני, לא raw input."""
        return dict(sorted((str(k), v) for k, v in (tool_inputs or {}).items()))

    # ── §3.3 — propose_action ───────────────────────────────────────

    def propose_action(
        self,
        *,
        tenant_id: str,
        canonical_user_id: str,
        tool_name: str,
        tool_inputs: dict,
        origin_channel: str,
        origin_chat_id: str,
        requires_approval: bool,
        identity=None,
        trusted_source: str = "agent",
    ) -> GatewayResult:
        """
        מציע פעולה חדשה ל-Gateway.

        trusted_source (BUG-091): מי שקורא ל-propose_action() בפועל —
        "agent" (ברירת מחדל, הכי לא-מהימן) לקריאות שמקורן ב-Agent tool_use
        loop, או source פנימי מהימן (למשל "lead_capture") רק כשקוד Python
        מהימן קורא ישירות. חייב להיות ארגומנט Python מפורש מהקורא — לעולם
        אסור לגזור אותו מתוך tool_inputs (זה תוכן ש-Claude שולט בו).
        מחזיר GatewayResult(ok=True, contract_id=...) אם מותרת.
        מחזיר GatewayResult(ok=False, ...) אם נחסמת (כפילות/pending).

        identity: BUG-C89-APPROVAL-IDENTITY — אם מועבר, ה-Identity שנפתרה
        בפועל (role/external_id/...) נשמרת על ה-contract עצמו, כדי שביצוע
        לאחר אישור ישתמש בזהות המקורית ולא ינסה resolve_identity() מחדש על
        canonical_user_id/origin_chat_id (שיכולים להיות memory_key, לא
        external_id ערוץ אמיתי).

        BUG-077: requires_approval לא נסמך עיוורת על הקורא — cross-check
        fail-closed מול tool_registry.needs_approval(tool_name). אם הרישום
        דורש אישור אבל הקורא העביר False, הרישום מנצח (True גובר תמיד) —
        חוץ מ-approval_policy == self_confirm (BUG-076 carve-out: lead
        capture בטוח לא צריך אישור owner; classify_approval_policy() כבר
        מחשב את זה מהתוכן בפועל, לא מהקורא, אז אין כאן בריחה מהבדיקה).
        """
        normalized = self.normalize_payload(tool_inputs)
        fingerprint = self.compute_business_fingerprint(
            tenant_id, canonical_user_id, tool_name, normalized
        )

        existing = self._ledger.find_by_fingerprint(fingerprint)
        if existing:
            if existing.status == "pending":
                return GatewayResult(
                    ok=False,
                    reason="כבר קיימת בקשת אישור פתוחה לפעולה הזו.",
                    contract_id=existing.contract_id,
                    user_message="⏳ כבר יש בקשת אישור פתוחה לפעולה זו. שלח *מאשר* כדי לאשר.",
                )
            if existing.status == "executed":
                return self._handle_duplicate_executed(existing, canonical_user_id)

        # BUG-076: classified from the actual normalized payload that will
        # be dispatched — never trusted from the caller.
        approval_policy = classify_approval_policy(tool_name, normalized)

        if (approval_policy != APPROVAL_POLICY_SELF_CONFIRM
                and needs_approval(tool_name)
                and not requires_approval):
            logger.warning(
                "[ActionGateway] propose_action: caller passed "
                "requires_approval=False for '%s' but tool_registry requires "
                "True — overriding to True (fail-closed, BUG-077).",
                tool_name,
            )
            requires_approval = True

        contract = ActionContract(
            contract_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            canonical_user_id=canonical_user_id,
            tool_name=tool_name,
            normalized_payload=normalized,
            business_action_fingerprint=fingerprint,
            origin_channel=origin_channel,
            origin_chat_id=origin_chat_id,
            requires_approval=requires_approval,
            status="draft",
            created_at=time.time(),
            actor_role=getattr(identity, "role", "") or "",
            actor_user_id=getattr(identity, "user_id", "") or "",
            actor_display_name=getattr(identity, "display_name", "") or "",
            actor_domain_id=getattr(identity, "domain_id", "") or "",
            actor_external_id=getattr(identity, "external_id", "") or "",
            actor_allowed_domains=list(getattr(identity, "allowed_domains", None) or []),
            approval_policy=approval_policy,
            trusted_source=trusted_source,
        )

        if requires_approval:
            contract.status = "pending"
        else:
            contract.status = "approved"

        self._ledger.save(contract)
        logger.info(
            "[ActionGateway] propose_action: contract=%s fingerprint=%.12s "
            "tool=%s table=%s provider=%s channel=%s status=%s user=%s",
            contract.contract_id,
            fingerprint,
            tool_name,
            normalized.get("table", normalized.get("spreadsheet_name", "")),
            "airtable" if "airtable" in tool_name else tool_name.split("_")[0],
            origin_channel,
            contract.status,
            canonical_user_id,
        )
        return GatewayResult(ok=True, reason="contract נרשם", contract_id=contract.contract_id)

    # PR-0C Phase 3 — shared shadow/enforced propose wrapper. Every approval
    # writer (app.py::_queue_approval, media_handler.py, followup_engine.py,
    # core/lead_recovery.py) needs the identical FEATURE_ACTION_GATEWAY policy:
    # flag ON -> propose_action() gates the caller for real (duplicate/pending
    # blocks propagate as a user-facing message); flag OFF -> best-effort
    # shadow propose for ledger/audit visibility only, never blocks, any
    # exception is swallowed (log only). Extracted here so new writers don't
    # each re-implement this dance by hand.
    def propose_gated(
        self,
        *,
        tenant_id: str,
        canonical_user_id: str,
        tool_name: str,
        tool_inputs: dict,
        origin_channel: str,
        origin_chat_id: str,
        identity=None,
        trusted_source: str = "agent",
    ) -> str | None:
        """Returns None to proceed normally, or a user-facing block message the
        caller must return immediately instead of queuing the approval."""
        from feature_flags import is_enabled as _flag

        if _flag("FEATURE_ACTION_GATEWAY"):
            result = self.propose_action(
                tenant_id=tenant_id, canonical_user_id=canonical_user_id,
                tool_name=tool_name, tool_inputs=tool_inputs,
                origin_channel=origin_channel, origin_chat_id=origin_chat_id,
                requires_approval=True, identity=identity, trusted_source=trusted_source,
            )
            if not result.ok:
                logger.info(
                    "[ActionGateway] propose_gated blocked: %s | contract=%s",
                    result.reason, result.contract_id,
                )
                return result.user_message or f"⏳ {result.reason}"
            return None

        try:
            self.propose_action(
                tenant_id=tenant_id, canonical_user_id=canonical_user_id,
                tool_name=tool_name, tool_inputs=tool_inputs,
                origin_channel=origin_channel, origin_chat_id=origin_chat_id,
                requires_approval=True, identity=identity, trusted_source=trusted_source,
            )
        except Exception as exc:
            logger.debug("[ActionGateway] shadow propose_gated failed (non-blocking): %s", exc)
        return None

    def _handle_duplicate_executed(
        self, existing: ActionContract, canonical_user_id: str
    ) -> GatewayResult:
        """מטפל בכפילות של פעולה executed — מייצר DuplicateOverrideApproval."""
        code = _gen_challenge_code()
        override = DuplicateOverrideApproval(
            contract_id=existing.contract_id,
            business_fingerprint=existing.business_action_fingerprint,
            challenge_hash=_hash_challenge(code),
            issued_to=canonical_user_id,
            issued_at=time.time(),
            ttl_seconds=300,
            consumed=False,
        )
        with self._override_lock:
            self._overrides[existing.business_action_fingerprint] = override
        logger.info(
            "[ActionGateway] duplicate_executed: fingerprint=%s, override issued to %s",
            existing.business_action_fingerprint[:12], canonical_user_id,
        )
        return GatewayResult(
            ok=False,
            reason="כפילות נחסמה — פעולה זו כבר בוצעה לאחרונה.",
            contract_id=existing.contract_id,
            user_message=(
                f"⚠️ פעולה זו כבר בוצעה לאחרונה.\n"
                f"אם אתה בטוח שזו חזרה מכוונת — שלח: *בצע שוב {code}*"
            ),
        )

    # ── ingress context gate — is_own_resolution_event ───────────────
    # BUG-PENDING-APPROVAL-B follow-up: used by app.py's webhook-level
    # ingress gate to decide whether an incoming *text* event is a genuine
    # attempt to resolve one of this identity's own live contracts (exempt
    # from being marked context_interrupted) versus any other event, which
    # is not exempt. Mirrors route_confirmation_word/route_cancellation_word/
    # route_disambiguation/route_combined_word's own matching exactly — same
    # keyword sets, same bare-digit-only-with-2+-live precedent (BUG-070) —
    # so this check can never drift from what those routes actually consume.

    def is_own_resolution_event(self, canonical_user_id: str, text: str) -> bool:
        live = self.find_live_contracts(canonical_user_id)
        if not live:
            return False
        stripped = text.strip()
        lower = stripped.lower()
        if lower in self._CONFIRM_KEYWORDS or lower in self._CANCEL_KEYWORDS:
            return True
        if self._parse_combined(stripped) is not None:
            return True
        if len(live) > 1 and self._parse_ordinal(stripped) is not None:
            return True
        return False

    # ── bounded one-shot reconfirmation — "no pending" reason ────────
    # BUG-PENDING-APPROVAL-B follow-up: when nothing is live, distinguish
    # "there genuinely was never anything pending" (unchanged wording, relied
    # on by existing tests) from "the last contract was superseded by a
    # second interruption" — the latter gets a specific, actionable message
    # instead of a silent dead end (the exact production bug reported: a
    # bare כן after a supersede must never look identical to "nothing ever
    # happened").

    def describe_no_pending_reason(self, canonical_user_id: str) -> str:
        recent = self._ledger.find_most_recent_by_user(canonical_user_id)
        if recent and recent.status == "superseded":
            desc = _describe_contract_for_reconfirmation(recent)
            return (
                f"הפעולה הקודמת בוטלה כי התחלת פעולה אחרת: {desc}.\n"
                f"כדי לבצע אותה, שלח את הבקשה מחדש."
            )
        return "אין פעולה שממתינה לאישור."

    # ── §4 — route_confirmation_word ────────────────────────────────

    def route_confirmation_word(self, canonical_user_id: str, approver_role: str = "") -> str:
        """
        מיירט מילת אישור חופשית (כמו "מאשר") לפני שמגיעה ל-Agent.
        מחזיר תשובה ישירה למשתמש.

        approver_role: BUG-074 — התפקיד המאומת של המשתמש שמאשר עכשיו (לא
        נגזר מ-canonical_user_id). approve() הוא שער האכיפה — ראה שם.
        """
        live = self.find_live_contracts(canonical_user_id)
        if len(live) == 0:
            return self.describe_no_pending_reason(canonical_user_id)
        if len(live) == 1:
            contract = live[0]
            # PR-0 / BUG-PENDING-APPROVAL-B: a message unrelated to this
            # contract arrived since the preview was shown (mark_context_interrupted).
            # The first "כן" after that must re-show the business description
            # and require an explicit second "כן" — never silently execute a
            # stale action (context poisoning). context_integrity_unknown is
            # gated identically — a marking failure must never be treated as
            # "context intact" (see _apply_ingress_context_gate in app.py).
            if (contract.context_interrupted or contract.context_integrity_unknown) \
                    and not contract.reconfirmation_required:
                self._ledger.update_status(
                    contract.contract_id, contract.status,
                    reconfirmation_required=True,
                )
                desc = _describe_contract_for_reconfirmation(contract)
                return (
                    f"יש פעולה קודמת שממתינה לאישור: {desc}.\n"
                    f"לאשר אותה? (כן/לא)"
                )
            result = self.approve(contract.contract_id, approver=canonical_user_id, approver_role=approver_role)
            return result
        # יותר מאחת — מציג רשימה ממוספרת + שומר disambiguation state
        with self._disambiguation_lock:
            self._disambiguation[canonical_user_id] = list(live)
        lines = ["יש כמה פעולות הממתינות לאישור — איזו?"]
        for i, c in enumerate(live, 1):
            lines.append(f"• {i}. {c.tool_name} (id: {c.contract_id[:8]})")
        lines.append("\nשלח את המספר (1, 2, ...) כדי לאשר פעולה ספציפית.")
        return "\n".join(lines)

    # ── BUG-056 — route_cancellation_word ───────────────────────────

    def route_cancellation_word(self, canonical_user_id: str) -> str | None:
        """
        מיירט מילת ביטול חופשית ("לא") לפני שמגיעה ל-Agent.
        מחזיר None אם אין contracts חיים (ממשיך לזרימה הקיימת/ל-Agent),
        אחרת מבטל את כל ה-contracts החיים ומחזיר תשובת ביטול.
        """
        live = self.find_live_contracts(canonical_user_id)
        if not live:
            return None
        for c in live:
            self._ledger.update_status(c.contract_id, "rejected")
            logger.info(
                "[ActionGateway] rejected via cancel word: contract=%s tool=%s user=%s",
                c.contract_id, c.tool_name, canonical_user_id,
            )
        return "🚫 הפעולה בוטלה."

    # ── disambiguation ordinal resolver ─────────────────────────────

    _ORDINALS_HE: dict[str, int] = {
        "ראשונה": 1, "ראשון": 1, "הראשונה": 1, "הראשון": 1, "first": 1,
        "שנייה": 2,  "שני":    2, "השנייה":  2, "השני":    2, "second": 2,
        "שלישית": 3, "שלישי": 3, "השלישית": 3, "השלישי":  3, "third": 3,
        "רביעית": 4, "רביעי": 4, "הרביעית": 4, "הרביעי":  4, "fourth": 4,
    }

    # BUG-070 gap #1: combined wording ("כן 1"/"אשר 3"/"לא 2") — a leading
    # confirm/cancel keyword followed by an ordinal, targeting one specific
    # contract in a single message instead of requiring two round-trips.
    _CONFIRM_KEYWORDS = frozenset({
        "כן", "אשר", "מאשר", "מאשרת", "אוקי", "בצע", "קדימה", "yes", "y", "ok",
    })
    _CANCEL_KEYWORDS = frozenset({
        "לא", "בטל", "ביטול", "עצור", "cancel", "no", "n",
    })

    @classmethod
    def _parse_ordinal(cls, text: str) -> int | None:
        """מחזיר אינדקס 1-based אם הטקסט הוא סדרתי; אחרת None."""
        t = text.strip().lower()
        # digit shorthand: "1", "2", ...
        if t.isdigit():
            return int(t)
        return cls._ORDINALS_HE.get(t)

    @classmethod
    def _parse_combined(cls, text: str) -> tuple[str, int] | None:
        """
        מפרש "<מילת אישור/ביטול> <סדרתי>" (למשל "כן 1", "אשר 3", "לא 2").
        מחזיר ("confirm"|"cancel", idx) או None אם הטקסט לא תואם את התבנית.
        """
        parts = text.strip().split()
        if len(parts) != 2:
            return None
        word, ord_token = parts[0].lower(), parts[1]
        idx = int(ord_token) if ord_token.isdigit() else cls._ORDINALS_HE.get(ord_token.lower())
        if idx is None:
            return None
        if word in cls._CONFIRM_KEYWORDS:
            return ("confirm", idx)
        if word in cls._CANCEL_KEYWORDS:
            return ("cancel", idx)
        return None

    def route_disambiguation(self, canonical_user_id: str, text: str, approver_role: str = "") -> str | None:
        """
        מיירט בחירת סדרתי ("הראשונה", "2", ...) אחרי שה-Gateway הציג רשימה.
        מחזיר None אם המשתמש אינו במצב disambiguation — ממשיך ל-Agent.
        מחזיר תשובה ישירה אם הבחירה חוקית.

        approver_role: BUG-074 — ראה route_confirmation_word / approve().
        """
        with self._disambiguation_lock:
            pending_list = self._disambiguation.get(canonical_user_id)
        if not pending_list:
            return None

        idx = self._parse_ordinal(text)
        if idx is None:
            # לא מספר/סדרתי — לא disambiguation; נקה state, המשך ל-Agent
            with self._disambiguation_lock:
                self._disambiguation.pop(canonical_user_id, None)
            return None

        # נקה state בכל מקרה — בחירה נצרכת פעם אחת בלבד
        with self._disambiguation_lock:
            self._disambiguation.pop(canonical_user_id, None)

        if not (1 <= idx <= len(pending_list)):
            return f"⚠️ אין פעולה מספר {idx}. יש {len(pending_list)} פעולות ממתינות."

        contract = pending_list[idx - 1]
        # §21: close all other pending contracts from the disambiguation list
        # so no sibling contracts linger after the user makes a selection.
        for sibling in pending_list:
            if sibling.contract_id != contract.contract_id and sibling.status == "pending":
                self._ledger.update_status(sibling.contract_id, "rejected")
                logger.info(
                    "[ActionGateway] disambiguation: closing sibling contract=%s tool=%s",
                    sibling.contract_id, sibling.tool_name,
                )
        logger.info(
            "[ActionGateway] disambiguation: user=%s selected idx=%d contract=%s tool=%s",
            canonical_user_id, idx, contract.contract_id, contract.tool_name,
        )
        return self.approve(contract.contract_id, approver=canonical_user_id, approver_role=approver_role)

    # ── BUG-070 gap #1 — route_combined_word ────────────────────────
    # "כן 1"/"אשר 3" (אישור ממוקד) ו-"לא 2" (דחייה ממוקדת) בהודעה אחת,
    # בלי לדרוש קודם שהמשתמש יראה את הרשימה הממוספרת (route_confirmation_word)
    # ובלי להמתין למצב disambiguation קיים — פועל ישירות מול contracts חיים.

    def route_combined_word(self, canonical_user_id: str, text: str, approver_role: str = "") -> str | None:
        """
        מיירט "<מילת אישור/ביטול> <סדרתי>" (כמו "כן 1"/"אשר 3"/"לא 2").
        מחזיר None אם הטקסט לא תואם את התבנית, או שאין contracts חיים —
        ממשיך לזרימה הקיימת/ל-Agent. אחרת מחזיר תשובה ישירה.

        approver_role: BUG-074 — ראה route_confirmation_word / approve().
        """
        parsed = self._parse_combined(text)
        if parsed is None:
            return None
        action, idx = parsed

        live = self.find_live_contracts(canonical_user_id)
        if not live:
            return None

        # בחירה תקפה — מנקה גם disambiguation state ישן כדי לא להשאיר אותו תלוי
        with self._disambiguation_lock:
            self._disambiguation.pop(canonical_user_id, None)

        if not (1 <= idx <= len(live)):
            return f"⚠️ אין פעולה מספר {idx}. יש {len(live)} פעולות ממתינות."

        contract = live[idx - 1]

        if action == "confirm":
            # §21 — כמו route_disambiguation: בחירה ממוקדת סוגרת siblings אחרים
            for sibling in live:
                if sibling.contract_id != contract.contract_id and sibling.status == "pending":
                    self._ledger.update_status(sibling.contract_id, "rejected")
                    logger.info(
                        "[ActionGateway] combined_word confirm: closing sibling contract=%s tool=%s",
                        sibling.contract_id, sibling.tool_name,
                    )
            logger.info(
                "[ActionGateway] combined_word: user=%s confirm idx=%d contract=%s tool=%s",
                canonical_user_id, idx, contract.contract_id, contract.tool_name,
            )
            return self.approve(contract.contract_id, approver=canonical_user_id, approver_role=approver_role)

        # action == "cancel" — דוחה רק את הפריט שנבחר, לא נוגע בשאר הממתינים
        self._ledger.update_status(contract.contract_id, "rejected")
        logger.info(
            "[ActionGateway] combined_word: user=%s cancel idx=%d contract=%s tool=%s",
            canonical_user_id, idx, contract.contract_id, contract.tool_name,
        )
        remaining = len(live) - 1
        if remaining > 0:
            return f"🚫 פעולה מספר {idx} ({contract.tool_name}) בוטלה. נשארו {remaining} פעולות ממתינות."
        return f"🚫 פעולה מספר {idx} בוטלה."

    # ── §10 — route_override_word ────────────────────────────────────

    def route_override_word(
        self, canonical_user_id: str, submitted_code: str
    ) -> str:
        """
        מיירט "בצע שוב <קוד>" לפני שמגיע ל-Agent.
        אינו מקבל מילות אישור כלליות — חייב את הקוד המפורש.
        consumed=True מוגדר לפני dispatch למניעת race condition.
        """
        with self._override_lock:
            # מחפש override לכל fingerprint ב-ledger של המשתמש
            override = next(
                (
                    o for o in self._overrides.values()
                    if o.issued_to == canonical_user_id
                    and not o.consumed
                ),
                None,
            )
            if not override:
                return "אין override פתוח עבורך. שלח את הבקשה המקורית מחדש."
            if time.time() - override.issued_at > override.ttl_seconds:
                return "קוד האתגר פג. שלח את הבקשה המקורית מחדש."
            if _hash_challenge(submitted_code) != override.challenge_hash:
                return "קוד שגוי. נסה שוב או שלח את הבקשה המקורית מחדש."
            # consumed=True לפני dispatch — מונע race
            override.consumed = True

        logger.info(
            "[ActionGateway] override approved: fingerprint=%s user=%s",
            override.business_fingerprint[:12], canonical_user_id,
        )
        if self._tool_executor:
            existing = self._ledger.find_by_fingerprint(override.business_fingerprint)
            if existing:
                return self._execute_contract(existing)
        return "✅ override אושר — הפעולה תבוצע."

    # ── §3.3 — approve ──────────────────────────────────────────────

    def approve(self, contract_id: str, approver: str, approver_role: str = "") -> str:
        """
        מאשר contract ומבצע אותו.
        Fail closed: אם _tool_executor חסר — לא מחזיר success, לא מסמן executed.

        BUG-074: approve() הוא שער האכיפה היחיד לכל מסלולי האישור (כפתור
        טלגרם + כל מילות האישור החופשיות). approver_role חייב לשקף את
        התפקיד המאומת בפועל של מי שמאשר עכשיו — לא נגזר מ-canonical_user_id
        ולא מ-contract.actor_role (זהות המבקש המקורי). היות שכל מסלולי
        הטקסט החופשי (route_confirmation_word/route_disambiguation/
        route_combined_word) מוצאים רק contracts ששייכים ל-canonical_user_id
        של המאשר עצמו, זהו למעשה תמיד "אישור עצמי".

        BUG-076: "אישור עצמי" אינו אומר "לא צריך סמכות" באופן גורף —
        זה תלוי במדיניות (`contract.approval_policy`, ראה
        classify_approval_policy()):
          - APPROVAL_POLICY_APPROVAL (ברירת מחדל): המאשר חייב סמכות אישור
            אמיתית (owner / "actions.approve") — בדיוק כמו ב-BUG-074,
            ללא תלות בזהות/תפקיד המבקש המקורי.
          - APPROVAL_POLICY_SELF_CONFIRM: זהו "confirmation" לא "approval" —
            המבקש המקורי בעצמו יכול לאשר את הטיוטה שלו, בתנאי שהמאשר הוא
            *אותה* זהות בדיוק (לא זהות אחרת) וגם מחזיק role פנימי
            (owner/partner/manager/employee). שמור אך ורק ל-lead capture
            בטוח שסווג ככזה — ראה classify_approval_policy().
        """
        contract = self._ledger.find_by_id(contract_id)
        if not contract:
            logger.warning("[ActionGateway] approve: contract not found id=%s", contract_id)
            return "⚠️ פעולה לא נמצאה."
        if contract.status != "pending":
            logger.info(
                "[ActionGateway] approve: not-pending contract=%s status=%s",
                contract_id, contract.status,
            )
            return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {contract.status})."

        # BUG-074/076 — hard authorization boundary. Fail-closed: unknown/
        # insufficient role never dispatches. The contract stays "pending"
        # (not consumed), so a genuinely authorized approver can still act
        # on it afterward.
        policy = getattr(contract, "approval_policy", APPROVAL_POLICY_APPROVAL)
        if policy == APPROVAL_POLICY_SELF_CONFIRM:
            authorized = approver == contract.canonical_user_id and _is_internal_role(approver_role)
        else:
            authorized = _has_approval_authority(approver_role)
        if not authorized:
            logger.warning(
                "[ActionGateway] approve: DENIED — approver lacks authority for policy=%s "
                "contract=%s tool=%s approver=%s role=%r requester=%s",
                policy, contract_id, contract.tool_name, approver, approver_role, contract.canonical_user_id,
            )
            return "⛔ הפעולה דורשת אישור בעלים."

        # §§3/#6 fail-closed: without executor no execution can be verified
        if not self._tool_executor:
            logger.error(
                "[ActionGateway] approve: _tool_executor is None — failing closed. "
                "contract=%s tool=%s user=%s",
                contract_id, contract.tool_name, approver,
            )
            return (
                "❌ Gateway executor לא מחובר — הפעולה לא בוצעה. "
                "פנה לתמיכה טכנית."
            )

        # NOTE: this is a plain in-memory status update, not an atomic claim.
        # There is no protection here against two callers (two Render
        # instances, a duplicate webhook, a double-tap) both reaching this
        # point for the same contract — a genuinely atomic coordination
        # primitive outside Airtable is tracked separately as Phase 4B0.1 and
        # does not exist yet. TMA routing by contract_id stays blocked until
        # it does (see core/action_contract_repository.py's module docstring).
        self._ledger.update_status(
            contract_id, "approved", approved_by=approver, approved_at=time.time(),
        )
        updated = self._ledger.find_by_id(contract_id)
        if not updated:
            logger.warning(
                "[ActionGateway] approve: contract vanished immediately after update_status contract=%s",
                contract_id,
            )
            return "⚠️ הפעולה לא נמצאה."

        logger.info(
            "[ActionGateway] approved: contract=%s fingerprint=%.12s tool=%s "
            "payload_keys=%s by=%s",
            contract_id,
            updated.business_action_fingerprint,
            updated.tool_name,
            list(updated.normalized_payload.keys()),
            approver,
        )
        return self._execute_contract(updated)

    def _execute_contract(self, contract: ActionContract) -> str:
        """
        מבצע tool לאחר אישור — approved_payload == executed_payload (DoD §6).
        מריץ verify_execution על התוצאה — success claims require real tool evidence (DoD §3, §6).

        Phase 4B0: When FEATURE_ATOMIC_CLAIMS=true, acquisition of atomic claim is REQUIRED
        before any dispatcher call. No exception falls back to direct dispatch.
        Identity from frozen contract must be preserved through atomic wrapper.
        Dispatcher result must be classified explicitly (not just exception-based).
        """
        from feature_flags import is_enabled

        self._ledger.update_status(contract.contract_id, "executing")

        # Phase 4B0 atomic claim gate (if flag enabled)
        if is_enabled("FEATURE_ATOMIC_CLAIMS"):
            from core.action_gateway_atomic_executor import execute_with_atomic_claim
            from identity import Identity
            import hashlib

            # Reconstruct identity from frozen contract (actor who proposed this contract)
            # This identity is bound at proposal time and must not be re-derived at execution.
            # FAIL-CLOSED: If required immutable fields are missing, fail immediately (don't fall back).
            # BUG-C89-APPROVAL-IDENTITY: actor_role, actor_external_id, tenant_id, actor_user_id
            # are integrity-bound at proposal time and must never be missing for a valid contract.
            # Scoped to the atomic-claims path only — the legacy (flag-off) dispatch below never
            # consumed a reconstructed identity and must not change behavior while flag is off.
            identity = None
            if contract.actor_role and contract.actor_external_id and contract.tenant_id and contract.actor_user_id:
                identity = Identity(
                    user_id=contract.actor_user_id,
                    role=contract.actor_role,
                    display_name=contract.actor_display_name or "",
                    tenant_id=contract.tenant_id,
                    domain_id=contract.actor_domain_id or "general",
                    allowed_domains=list(contract.actor_allowed_domains or []),
                    channel=contract.origin_channel,
                    external_id=contract.actor_external_id,
                )
            else:
                # Missing tenant, user, role, or external identity — fail closed.
                logger.error(
                    "[ActionGateway] identity integrity violation: contract=%s "
                    "actor_role=%s actor_external_id=%s tenant_id=%s actor_user_id=%s "
                    "(all required for valid frozen identity under FEATURE_ATOMIC_CLAIMS)",
                    contract.contract_id,
                    contract.actor_role,
                    contract.actor_external_id,
                    contract.tenant_id,
                    contract.actor_user_id,
                )
                self._ledger.update_status(contract.contract_id, "failed")
                return "❌ שגיאת זהות: לא ניתן לאמת את הזהות של המבקש. פנה לתמיכה טכנית."

            # Deterministic idempotency key: hash(contract_id + approved_by)
            # Same contract + same approver → same key → ALREADY_CLAIMED on retry
            idem_seed = f"{contract.contract_id}:{contract.approved_by or contract.actor_user_id}"
            idempotency_key = hashlib.sha256(idem_seed.encode()).hexdigest()[:16]

            # Gate dispatcher behind atomic claim acquisition
            try:
                success, result, error = execute_with_atomic_claim(
                    contract_id=contract.contract_id,
                    canonical_user_id=contract.approved_by or contract.actor_user_id,
                    tool_name=contract.tool_name,
                    tool_inputs=contract.normalized_payload,
                    identity=identity,  # Frozen contract identity
                    executor_fn=self._tool_executor,
                    idempotency_key=idempotency_key,
                )

                if not success:
                    # Fail-closed: claim unavailable, DB down, conflict, or disabled
                    self._ledger.update_status(contract.contract_id, "failed")
                    logger.error(
                        "[ActionGateway] atomic claim failed: contract=%s error=%s",
                        contract.contract_id, error,
                    )
                    return f"❌ ביצוע נכשל: {error}"

                # Phase 4B0: result is DispatcherOutcome when flag enabled
                # Extract structured fields and convert to dict for downstream processing
                from core.dispatcher_outcome import DispatcherOutcome
                if isinstance(result, DispatcherOutcome):
                    # Convert DispatcherOutcome to dict for verify_execution and status reply
                    raw = result.raw_response or {
                        "ok": True,
                        "external_id": result.external_id,
                    }
                    # Ensure user_message is available for status reply
                    if "user_message" not in raw:
                        raw["user_message"] = result.user_message
                else:
                    raw = result
            except Exception as exc:
                # No exception fallback to direct dispatch when flag is ON — fail closed
                self._ledger.update_status(contract.contract_id, "failed")
                logger.error(
                    "[ActionGateway] atomic executor raised: contract=%s error=%s",
                    contract.contract_id, exc,
                )
                return f"❌ ביצוע נכשל: {exc}"
        else:
            # Flag OFF: legacy direct dispatch (no claim creation, no atomic coordination)
            # _tool_executor reconstructs identity from contract using contract_id
            try:
                raw = self._tool_executor(
                    tool_name=contract.tool_name,
                    tool_inputs=contract.normalized_payload,
                    contract_id=contract.contract_id,
                )
            except Exception as exc:
                self._ledger.update_status(contract.contract_id, "failed")
                logger.error(
                    "[ActionGateway] execution failed: contract=%s error=%s",
                    contract.contract_id, exc,
                )
                return f"❌ ביצוע נכשל: {exc}"

        # §3 / §6: verify before reporting success — no real evidence → failure
        try:
            from core.anti_hallucination import verify_execution
            check = verify_execution(contract.tool_name, raw)
            if check.status == "failed":
                self._ledger.update_status(contract.contract_id, "failed")
                logger.error(
                    "[ActionGateway] evidence missing: contract=%s tool=%s reason=%s",
                    contract.contract_id, contract.tool_name, check.reason,
                )
                return f"❌ הפעולה לא הושלמה: {check.reason}"
        except Exception as verify_exc:
            logger.warning("[ActionGateway] verify_execution import failed: %s", verify_exc)

        ext_id = raw.get("external_id", "") if isinstance(raw, dict) else ""
        self._ledger.update_status(contract.contract_id, "executed")
        # persist record_id as observation so query_execution_status can retrieve it
        if ext_id:
            contract.agent_observations.append({
                "kind": "execution_fact",
                "record_id": ext_id,
                "created_at": time.time(),
            })
        logger.info(
            "[ActionGateway] executed: contract=%s fingerprint=%.12s tool=%s "
            "external_id=%s payload_keys=%s",
            contract.contract_id,
            contract.business_action_fingerprint,
            contract.tool_name,
            ext_id,
            list(contract.normalized_payload.keys()),
        )
        # §15.2 — compose_status_reply is the single source of status text
        fact = ActionFact(
            tool_name=contract.tool_name,
            contract_id=contract.contract_id,
            outcome="executed",
            record_id=ext_id or None,
            error_code=None,
            raw_tool_response=raw if isinstance(raw, dict) else {"raw": str(raw)},
        )
        gateway_reply = self.compose_status_reply(fact)
        # Append C53-A user_message as conversational context after the fact
        c53_message = raw.get("user_message") if isinstance(raw, dict) else None
        if c53_message and c53_message != gateway_reply.text:
            return f"{gateway_reply.text}\n{c53_message}"
        return gateway_reply.text

    # ── §15.2 — compose_status_reply ────────────────────────────────
    # הפונקציה היחידה בכל הקוד שמותר לה לייצר טקסט סטטוס-פעולה.

    def compose_status_reply(self, fact: ActionFact) -> GatewayReply:
        if fact.outcome == "executed":
            # BUG-PENDING-APPROVAL-B follow-up: reuse the frozen contract's
            # business description (e.g. "יצירת ליד: יוסי כהן, ...") instead
            # of the bare tool_name — the payload never changes between
            # proposal and execution (approved_payload == executed_payload),
            # so the description computed at reconfirmation time is exactly
            # what was actually written.
            contract = self._ledger.find_by_id(fact.contract_id)
            label = _describe_contract_for_reconfirmation(contract) if contract else fact.tool_name
            rid = f" | מזהה: `{fact.record_id}`" if fact.record_id else ""
            text = f"✅ בוצע: {label}{rid}"
        elif fact.outcome == "failed":
            ec = f" ({fact.error_code})" if fact.error_code else ""
            text = f"❌ נכשל: {fact.tool_name}{ec}"
        elif fact.outcome == "pending":
            text = f"⏳ ממתין לאישור: {fact.tool_name}"
        elif fact.outcome == "rejected":
            text = f"⚠️ נדחה: {fact.tool_name}"
        else:
            text = f"ℹ️ {fact.tool_name}: {fact.outcome}"
        return GatewayReply(text=text, fact=fact)

    # ── §7 §20 — query_execution_status ─────────────────────────────
    # עונה לשאלות סטטוס ("נוספה?") אך ורק מה-ExecutionLedger.
    # לעולם לא מסתמך על טקסט שיחה או קלט Agent.

    def query_execution_status(
        self, canonical_user_id: str, window_seconds: int = 600
    ) -> str | None:
        """
        מחזיר תשובת סטטוס לשאלה "נוספה?"/"הצליח?" — מה-Ledger בלבד.
        None = אין ביצוע אחרון רלוונטי בחלון הזמן.
        BUG-SB-03: אם אין executed/failed, מחפש pending contracts ומדווח עליהם.
        """
        candidates = [
            c for c in self._ledger._store.values()
            if c.canonical_user_id == canonical_user_id
            and c.status in ("executed", "failed")
        ]
        if not candidates:
            # BUG-SB-03: check for pending contracts before returning None
            live = self.find_live_contracts(canonical_user_id)
            if live:
                label = live[0].tool_name
                return f"⏳ יש בקשת אישור פתוחה: {label}"
            return None
        latest = max(candidates, key=lambda c: c.created_at)
        if time.time() - latest.created_at > window_seconds:
            # still check pending before giving up
            live = self.find_live_contracts(canonical_user_id)
            if live:
                label = live[0].tool_name
                return f"⏳ יש בקשת אישור פתוחה: {label}"
            return None
        ext_id = None
        if isinstance(latest.agent_observations, list):
            for obs in reversed(latest.agent_observations):
                if obs.get("kind") == "execution_fact" and obs.get("record_id"):
                    ext_id = obs["record_id"]
                    break
        fact = ActionFact(
            tool_name=latest.tool_name,
            contract_id=latest.contract_id,
            outcome=latest.status,
            record_id=ext_id,
            error_code=None,
            raw_tool_response={},
        )
        return self.compose_status_reply(fact).text

    # ── query helpers ────────────────────────────────────────────────

    def find_live_contracts(self, canonical_user_id: str) -> list[ActionContract]:
        return self._ledger.find_live_by_user(canonical_user_id)

    def find_contract(self, contract_id: str) -> ActionContract | None:
        return self._ledger.find_by_id(contract_id)

    # ── PR-0 / BUG-PENDING-APPROVAL-B ────────────────────────────────

    def mark_context_interrupted(self, canonical_user_id: str) -> None:
        """נקרא מ-app.py לכל הודעה שאינה עצמה resolution (כן/לא/disambiguation/
        combined) עבור contract חי של הזהות הזו — ראה route_confirmation_word()."""
        self._ledger.mark_context_interrupted(canonical_user_id)

    def mark_context_integrity_unknown(self, canonical_user_id: str) -> None:
        """Fallback delegate — see ExecutionLedger.mark_context_integrity_unknown()."""
        self._ledger.mark_context_integrity_unknown(canonical_user_id)

    # ── §5 — AgentObservation ────────────────────────────────────────

    def record_agent_observation(
        self,
        contract_id: str | None,
        kind: str,
        text: str,
    ) -> AgentObservation:
        """שומר signal של Agent — לעולם לא user-facing, לעולם לא executable."""
        obs = AgentObservation(
            contract_id=contract_id,
            kind=kind,
            text=text,
            created_at=time.time(),
        )
        if contract_id:
            contract = self._ledger.find_by_id(contract_id)
            if contract:
                contract.agent_observations.append(
                    {"kind": kind, "text": text, "created_at": obs.created_at}
                )
        logger.debug(
            "[ActionGateway] AgentObservation: kind=%s contract=%s text=%.80s",
            kind, contract_id, text,
        )
        return obs


# ══════════════════════════════════════════════════
# Singleton — ייצור עם lazy Airtable writer
# ══════════════════════════════════════════════════

def _build_airtable_writer():
    """
    מחזיר callable שכותב ActionContract ל-Airtable ActionContracts table.
    נקרא lazy בעת יצוא singleton — לא בזמן import.
    כאשר Airtable לא מוגדר/לא מחובר, מחזיר None (RAM-only) — מצב צפוי, לא שגיאה.
    כל כשל אחר (import שבור, bug) מתועד ב-warning — אסור להיבלע בשקט לגמרי,
    אחרת "אין writer" ו"יש באג ב-writer" נראים זהים בלוגים.
    """
    try:
        from airtable_schema import Tables
        if not hasattr(Tables, "ACTION_CONTRACTS"):
            return None
        from tools.airtable_gateway import at_upsert

        def _writer(c: ActionContract) -> None:
            at_upsert(
                Tables.ACTION_CONTRACTS,
                {
                    "contract_id":                c.contract_id,
                    "tenant_id":                  c.tenant_id,
                    "canonical_user_id":          c.canonical_user_id,
                    "tool_name":                  c.tool_name,
                    "normalized_payload":         json.dumps(c.normalized_payload, ensure_ascii=False),
                    "business_action_fingerprint": c.business_action_fingerprint,
                    "origin_channel":             c.origin_channel,
                    "origin_chat_id":             c.origin_chat_id,
                    "requires_approval":          c.requires_approval,
                    "status":                     c.status,
                    "created_at":                 c.created_at,
                    "approved_by":                c.approved_by or "",
                    "approved_at":                c.approved_at or 0.0,
                },
                match_field="contract_id",
            )

        return _writer
    except Exception as exc:
        logger.warning(
            "[ActionGateway] _build_airtable_writer failed — falling back to RAM-only: %s",
            exc,
        )
        return None


def _make_dispatch_executor(ledger: ExecutionLedger):
    """
    מחזיר tool executor שמחובר ל-dispatcher.
    Closure על ה-ledger — מוצא identity מהחוזה לפי contract_id.
    לא מייבא dispatcher/identity בזמן module-load (נמנעים מ-circular import).

    BUG-C89-APPROVAL-IDENTITY: כשה-contract נשא actor identity (propose_action
    קיבל identity=...), הביצוע חייב להשתמש בזהות המקורית שנפתרה בזמן היצירה —
    לא ב-resolve_identity(origin_channel, origin_chat_id) מחדש, כי origin_chat_id
    יכול להיות identity.memory_key ("boss_hq:eliyahu") ולא external_id ערוץ
    אמיתי, מה שגורם ל-role ליפול חזרה ל-readonly. fallback ל-resolve_identity
    נשאר רק לחוזים ישנים/callers שלא העבירו identity ל-propose_action.
    """
    def _executor(tool_name: str, tool_inputs: dict, contract_id: str):
        from tools.dispatcher import dispatch_tool
        from identity import Identity, resolve_identity

        identity = None
        contract = ledger.find_by_id(contract_id)
        if contract:
            if contract.actor_role and contract.actor_external_id:
                identity = Identity(
                    user_id         = contract.actor_user_id or contract.canonical_user_id,
                    role            = contract.actor_role,
                    display_name    = contract.actor_display_name,
                    tenant_id       = contract.tenant_id,
                    domain_id       = contract.actor_domain_id or "general",
                    allowed_domains = list(contract.actor_allowed_domains or []),
                    channel         = contract.origin_channel,
                    external_id     = contract.actor_external_id,
                )
                logger.info(
                    "[ActionGateway] approved by=%s/%s@%s external_id=%s | dispatch role=%s",
                    contract.tenant_id, identity.user_id, contract.actor_role,
                    contract.actor_external_id, identity.role,
                )
            else:
                try:
                    identity = resolve_identity(contract.origin_channel, contract.origin_chat_id)
                except Exception as exc:
                    logger.warning("[ActionGateway] identity resolve failed: %s", exc)

        # BUG-091: trusted_source comes from the contract itself (set once,
        # server-side, at propose_action() time) — never re-derived from
        # tool_inputs, which is Claude-controlled data that survives
        # normalize_payload() unchanged (including any "_source" key).
        _trusted_source = getattr(contract, "trusted_source", "agent") if contract else "agent"
        return dispatch_tool(tool_name, tool_inputs, identity=identity, trusted_source=_trusted_source)

    return _executor


# PR-0C Phase 4A: _build_airtable_writer()/at_upsert()/Tables.ACTION_CONTRACTS
# are built and tested, but deliberately NOT wired into the live singleton
# yet. propose_action()/propose_gated() are already called unconditionally
# in production today (shadow mode when FEATURE_ACTION_GATEWAY is off) by
# app.py::_queue_approval, media_handler.py, followup_engine.py, and
# core/lead_recovery.py — wiring this writer in would mean every one of
# those calls starts writing real Airtable records immediately, which is a
# live behavior change, not inert infrastructure. It also requires a durable
# read/recovery path first (load-by-contract_id on restart, pending-contract
# recovery) — ExecutionLedger is 100% in-memory today, so "ActionContracts"
# cannot honestly be called canonical durable truth until contracts can be
# read back, not just written. Wire this only after that read path exists,
# at_upsert()'s concurrent-write behavior has been reviewed, and the rollout
# has been verified in a non-production environment first.
_ledger_singleton = ExecutionLedger(airtable_writer=None)
action_gateway = ActionGateway(
    ledger=_ledger_singleton,
    tool_executor=_make_dispatch_executor(_ledger_singleton),
)
