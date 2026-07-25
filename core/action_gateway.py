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

from core.action_contract_repository import (
    ActionContractLookupError,
    ActionContractTransitionConflictError,
    ActionContractTransitionError,
    ActionContractTransitionPersistenceError,
    CONTRACT_PENDING_TTL_SECONDS,
    _is_expired as _is_contract_expired,
)
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
    status:                     str    # draft|pending|approved|rejected|completed|failed|outcome_unknown (executed legacy)
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
    # Frozen proposal identity for durable recovery/audit. PostgreSQL claim
    # ownership remains separate from this provider idempotency metadata.
    idempotency_key:             str = ""
    # Persisted lifecycle version. Repository transitions reject a stale
    # pre-write version and verify the increment after their partial PATCH;
    # Airtable still provides no atomic compare-and-swap primitive. PostgreSQL
    # owns the genuinely atomic execution claim.
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
    failure_code: str | None = None   # machine-readable, e.g. persistence_failed


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


class CanonicalizationError(ValueError):
    """A tool override could not produce a safe payload for its new tool."""


def _sheets_payload_to_airtable(tool_inputs: dict) -> dict:
    """Convert a Sheets-shaped append payload into an Airtable add payload."""
    from airtable_schema import FIELD_MAP, TABLE_ALIASES, Tables, TaskFields

    payload = dict(tool_inputs or {})
    table = (
        payload.get("table")
        or payload.get("sheet_name")
        or payload.get("spreadsheet_name")
    )
    row_data = payload.get("row_data")
    if not table:
        raise CanonicalizationError(
            "cannot canonicalize sheets_append without a target table"
        )

    canonical_table = TABLE_ALIASES.get(str(table), str(table))
    approved_fields = FIELD_MAP.get(canonical_table)
    if not approved_fields:
        raise CanonicalizationError(
            f"cannot canonicalize sheets_append to unknown Airtable table {table!r}"
        )

    existing_fields = payload.get("fields")
    if isinstance(existing_fields, dict):
        fields = dict(existing_fields)
    elif isinstance(row_data, dict):
        fields = dict(row_data)
    elif isinstance(row_data, list):
        if canonical_table != Tables.TASKS or len(row_data) != 1:
            raise CanonicalizationError(
                f"no explicit positional converter for Airtable table {table!r}"
            )
        fields = {TaskFields.NAME: row_data[0]}
    else:
        raise CanonicalizationError(
            "cannot canonicalize sheets_append without fields or row_data"
        )

    if not fields:
        raise CanonicalizationError(
            "cannot canonicalize sheets_append with empty Airtable fields"
        )
    if canonical_table == Tables.TASKS and "Task" in fields and TaskFields.NAME not in fields:
        fields = {TaskFields.NAME if k == "Task" else k: v for k, v in fields.items()}

    unknown_fields = sorted(set(fields) - set(approved_fields))
    if unknown_fields:
        raise CanonicalizationError(
            f"cannot canonicalize unapproved Airtable fields for {table!r}: "
            + ", ".join(unknown_fields)
        )

    return {"table": canonical_table, "fields": fields}


def resolve_canonical_call(
    tool_hint: str,
    tool_inputs: dict,
    user_text: str = "",
) -> tuple[str, dict]:
    """Resolve the canonical tool and its matching payload atomically."""
    payload = dict(tool_inputs or {})
    resolved_tool = resolve_canonical_tool(tool_hint, payload, user_text)
    if tool_hint == "sheets_append" and resolved_tool == _CANONICAL_TOOL_DEFAULT:
        payload = _sheets_payload_to_airtable(payload)
    elif (
        tool_hint in ("drive_upload", "drive_create")
        and resolved_tool == _CANONICAL_TOOL_DEFAULT
    ):
        raise CanonicalizationError(
            f"cannot canonicalize {tool_hint} payload to airtable_add"
        )
    return resolved_tool, payload


def _hash_challenge(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _gen_challenge_code() -> str:
    return str(random.randint(100000, 999999))


# ══════════════════════════════════════════════════
# Execution Ledger — ממשק עמיד (§7, §8)
# ממשק מופרד מ-ActionGateway; backing ראשוני = RAM + Airtable stub.
# ══════════════════════════════════════════════════

class ActionContractPersistenceError(RuntimeError):
    """A durable proposal could not be committed to its repository."""


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
        # ActionContractRepository | None. When set, reads recover through it
        # and lifecycle updates persist there before the RAM cache changes.
        # PostgreSQL remains the separate atomic execution-claim owner.
        self._repository = repository

    def _cache_contract(self, contract: ActionContract) -> None:
        with self._lock:
            self._store[contract.contract_id] = contract
            self._by_fingerprint[contract.business_action_fingerprint] = contract.contract_id

    def _refresh_stale_contract_cache(self, contract_id: str) -> "ActionContract | None":
        """BUG-127A: the RAM ledger's cached version/status can drift behind
        the durable repository (transition()'s own internal read-back always
        sees fresh truth, but a rejected transition never reports it back to
        the caller, and update_status() only re-caches on SUCCESS — so a
        version conflict caused by pure RAM staleness, once it happens,
        never self-heals on its own). Called only to recover from that
        specific staleness before a single retry, never as a substitute for
        the CAS check itself. Returns the refreshed contract, or None if it
        can't be refreshed (repository unreachable, or the contract is
        genuinely gone/expired) — callers must treat None as "give up,
        propagate the original error," never invent a fallback state."""
        if not self._repository:
            return None
        try:
            fresh = self._repository.get(contract_id)
        except Exception as exc:
            logger.warning(
                "[ActionGateway] BUG-127A stale-cache refresh failed for %s: %s",
                contract_id, exc,
            )
            return None
        if fresh is None:
            return None
        with self._lock:
            cached = self._store.get(contract_id)
            if cached is not None:
                cached.status = fresh.status
                cached.version = fresh.version
        return fresh

    def save(self, contract: ActionContract) -> bool:
        # Phase 4B-1A: when a repository is configured it is authoritative for
        # NEW proposals. Persist before publishing the contract into RAM so a
        # failed durable write can never leave an actionable RAM-only contract.
        # This does not make later status/context mutations durable; those stay
        # explicitly deferred to Phase 4B-1B.
        if self._repository:
            try:
                persisted = self._repository.save(contract)
            except Exception as exc:
                raise ActionContractPersistenceError(
                    f"repository save raised: {type(exc).__name__}"
                ) from exc
            if persisted is not True:
                raise ActionContractPersistenceError("repository save returned non-True")

        self._cache_contract(contract)
        if self._airtable_writer:
            try:
                self._airtable_writer(contract)
            except Exception as exc:
                logger.warning("[ActionGateway] Airtable write failed (RAM intact): %s", exc)
        return True

    def find_by_id(self, contract_id: str) -> ActionContract | None:
        cached = self._store.get(contract_id)
        if cached is not None:
            return cached
        if not self._repository:
            return None
        # Cache miss — fall back to the durable repository (restart / second
        # instance recovery). Repository lookup failures intentionally
        # propagate; only clean not-found/expiry returns None.
        hydrated = self._repository.get(contract_id)
        if hydrated is None:
            return None
        self._cache_contract(hydrated)
        return hydrated

    def find_by_fingerprint(self, fingerprint: str) -> ActionContract | None:
        cid = self._by_fingerprint.get(fingerprint)
        cached = self._store.get(cid) if cid else None
        if cached is not None:
            return cached
        if not self._repository:
            return None
        recovered = self._repository.find_by_business_fingerprint(fingerprint)
        if recovered is None:
            return None
        self._cache_contract(recovered)
        return recovered

    def find_live_by_user(self, canonical_user_id: str) -> list[ActionContract]:
        """מחזיר contracts חיים (pending, לא פג-תוקף) לזהות קנונית.

        Staging finding #1 (23/07/2026): the cold-cache/recovery path already
        filters expired contracts via the repository's own find_pending_by_
        canonical_user_id() (which applies _is_expired()/CONTRACT_PENDING_TTL_
        SECONDS, same as ActionContractRepository.get()) — but once this
        user's RAM cache is warm (has_cached_user_contract=True), the recovery
        branch below is skipped entirely and the old code returned straight
        from self._store without ever re-checking expiry. A "pending" contract
        that outlives CONTRACT_PENDING_TTL_SECONDS (24h) never gets a status
        transition on its own (nothing proactively re-visits it), so it sat in
        _store as "pending" forever and kept showing up as a live candidate —
        inconsistent with the exact same query answered fresh after a restart
        (cache empty -> repository path -> expired one filtered out). Filtering
        here makes both paths agree. This does not by itself guarantee no
        stale-looking contract is ever shown (CONTRACT_PENDING_TTL_SECONDS is
        24h, deliberately long for TMA approvals that can sit unopened for
        hours — see docs/architecture/action-gateway/
        BUG-STAGING-23JUL_TTL_AND_DISAMBIGUATION_AUDIT.md) — the per-item age
        indicator added to the disambiguation listing is the complementary,
        immediate mitigation for that gap.
        """
        # Repository recovery is cache-miss only. Lifecycle transitions write
        # through before RAM changes, so the durable query is authoritative on
        # restart; avoiding a second query once this user's cache is populated
        # also keeps one request path internally consistent.
        has_cached_user_contract = any(
            c.canonical_user_id == canonical_user_id for c in self._store.values()
        )
        if self._repository and not has_cached_user_contract:
            for recovered in self._repository.find_pending_by_canonical_user(canonical_user_id):
                self._cache_contract(recovered)
        return [
            c for c in self._store.values()
            if c.canonical_user_id == canonical_user_id
            and c.status == "pending"
            and not _is_contract_expired(c)
        ]

    def find_most_recent_by_user(self, canonical_user_id: str) -> "ActionContract | None":
        """Most recent contract (any status) for this identity — used to give
        a specific "your previous action was superseded" message instead of a
        generic "nothing pending" when the most recent contract was closed by
        a second interruption rather than executed/cancelled by the user."""
        candidates = [c for c in self._store.values() if c.canonical_user_id == canonical_user_id]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.created_at)

    def update_status(self, contract_id: str, status: str, *,
                      require_status: str | None = None, **kwargs) -> bool:
        """Persist an expected lifecycle transition before updating RAM.

        With no repository configured, preserves the legacy RAM-only behavior.
        Transition failures propagate so callers cannot report approval,
        rejection, or execution success when the durable audit row disagrees.

        require_status (Codex re-audit of 818c8a6 — TOCTOU race fix): when
        provided, the transition is CONDITIONAL and ATOMIC — applied only if
        the contract is still in exactly `require_status` at the moment of
        the write, and returning False (without mutating) if it has moved on.
        RAM path: the guard and the set share a SINGLE lock acquisition, so
        no concurrent writer can slip a status change in between them.
        Durable path: enforced by the repository's own CAS on
        expected_status. This closes the window a plain check-then-update
        leaves open — a concurrent lifecycle event moving a "pending"
        contract to "approved" between a caller's status check and the write
        must never be silently clobbered. When require_status is None the
        behavior is byte-for-byte the legacy unconditional overwrite, so no
        existing caller is affected.
        """
        with self._lock:
            c = self._store.get(contract_id)
            if not c:
                return False
            expected_status = c.status
            expected_version = c.version

        if self._repository:
            # Codex re-audit of ce990a0, fix 1 — durable conditional cleanup
            # must fail closed. A require_status transition is CONDITIONAL and
            # DESTRUCTIVE (PA-01's pending->rejected orphan cleanup). The
            # durable store can only perform it safely if it offers a real
            # atomic conditional primitive. Airtable's transition() is
            # read-check-PATCH (TOCTOU-prone), so its repository declares
            # supports_atomic_conditional_transition = False — and when it is
            # not exactly True, we must NOT call transition() at all: an
            # unconditional PATCH could clobber a concurrent lifecycle change
            # (e.g. a live approval). Return False without any durable
            # mutation; the caller (reject_if_pending -> _revoke_and_verify_
            # contract) maps False to APPROVAL_QUEUE_ORPHANED. The decision
            # lives here, at the ledger/repository boundary, not behind a
            # feature-flag check in app.py. `is not True` (not just truthiness)
            # so a test double / mock whose attribute auto-creates to a truthy
            # object is still treated as "no CAS" — fail closed by default.
            if (require_status is not None
                    and getattr(self._repository, "supports_atomic_conditional_transition", False)
                        is not True):
                logger.warning(
                    "[ActionGateway] conditional transition require_status=%s requested but the "
                    "durable repository has no atomic conditional primitive — failing closed "
                    "(no PATCH). contract=%s", require_status, contract_id,
                )
                return False
            # When require_status is given (and the repository DID declare CAS
            # support above), the durable CAS must enforce THAT status
            # specifically (not merely the RAM-captured current one), and a
            # CAS mismatch is a conditional-transition "no-op", not an error
            # to propagate.
            _cas_expected = require_status if require_status is not None else expected_status
            try:
                persisted = self._repository.transition(
                    contract_id,
                    expected_status=_cas_expected,
                    expected_version=expected_version,
                    new_status=status,
                    updates=kwargs,
                )
            except ActionContractTransitionConflictError as exc:
                # BUG-127A: this conflict can mean the RAM ledger's cached
                # version merely drifted behind durable truth, not necessarily
                # a real concurrent lifecycle change. Refresh from durable
                # truth and retry ONCE with the corrected version before
                # treating this as a genuine conflict. _cas_expected (the
                # caller's real status requirement — require_status when
                # given, or the RAM-captured status otherwise) is deliberately
                # NOT refreshed — only the version is corrected, so a real
                # status divergence (contract genuinely moved on) still fails
                # the retry exactly like before; this only recovers from pure
                # version staleness, never loosens the CAS check itself.
                refreshed = self._refresh_stale_contract_cache(contract_id)
                if refreshed is None:
                    if require_status is not None:
                        return False
                    raise
                try:
                    persisted = self._repository.transition(
                        contract_id,
                        expected_status=_cas_expected,
                        expected_version=refreshed.version,
                        new_status=status,
                        updates=kwargs,
                    )
                except ActionContractTransitionError:
                    if require_status is not None:
                        return False
                    raise exc from None  # surface the ORIGINAL conflict, not the retry's
                except Exception as retry_exc:
                    raise ActionContractTransitionPersistenceError(
                        f"repository lifecycle transition raised on retry: {type(retry_exc).__name__}"
                    ) from retry_exc
            except ActionContractTransitionError:
                if require_status is not None:
                    return False
                raise
            except Exception as exc:
                raise ActionContractTransitionPersistenceError(
                    f"repository lifecycle transition raised: {type(exc).__name__}"
                ) from exc
            self._cache_contract(persisted)
            return True

        with self._lock:
            c = self._store.get(contract_id)
            if not c:
                return False
            # Atomic guard: check-and-set inside the SAME lock section (the
            # TOCTOU fix). A concurrent update_status() for this contract
            # also takes self._lock, so the two are serialized and this can
            # never overwrite a status a concurrent writer already changed.
            if require_status is not None and c.status != require_status:
                return False
            c.status = status
            for k, v in kwargs.items():
                if hasattr(c, k):
                    setattr(c, k, v)
        if self._airtable_writer:
            try:
                self._airtable_writer(self._store[contract_id])
            except Exception as exc:
                logger.warning("[ActionGateway] Airtable status update failed: %s", exc)
        return True

    # ── PR-0 / BUG-PENDING-APPROVAL-B ────────────────────────────────

    def mark_context_interrupted(self, canonical_user_id: str) -> None:
        """כל pending contract חי לזהות זו מטופל לפי bounded one-shot FSM:
        contract שטרם הציג reconfirmation (reconfirmation_required=False)
        מסומן context_interrupted=True (עדיין ניתן להצלה בסיבוב אחד). contract
        שכבר הציג reconfirmation פעם אחת (reconfirmation_required=True) —
        הפרעה נוספת מבטלת אותו סופית (status="superseded"), לא פותחת סיבוב
        שני. אין מעגלי reconfirmation חוזרים — ראה route_confirmation_word().

        BUG-114: contract שכבר context_interrupted=True (ועדיין לא הגיע
        ל-reconfirmation) מדולג — סימון חוזר הוא no-op ערכית, אבל update_status()
        לא יודע את זה: ה-updates dict שנשלח ({"context_interrupted": True}) אינו
        ריק גם כשהערך כבר זהה, אז ה-shortcut האידמפוטנטי ב-
        ActionContractRepository.transition() לא יורה, וכל הודעה נכנסת
        בלתי-קשורה עתידית הייתה מפיקה GET+PATCH+GET מלא לכל contract כזה, ללא
        הגבלת זמן. הבדיקה כאן היא RAM טהורה (context_interrupted כבר שדה
        cached על ActionContract) — אפס I/O נוסף. contracts עם
        reconfirmation_required=True **לא** מדולגים למרות ה-`or` — הם עדיין
        זקוקים ל-supersede אמיתי (שינוי status אמיתי, לא re-write של ערך זהה),
        ללא קשר לערך context_interrupted הנוכחי שלהם."""
        with self._lock:
            changes = [
                (c.contract_id, "superseded", {})
                if c.reconfirmation_required
                else (c.contract_id, "pending", {"context_interrupted": True})
                for c in self._store.values()
                if c.canonical_user_id == canonical_user_id
                and c.status == "pending"
                and (c.reconfirmation_required or not c.context_interrupted)
            ]
        for contract_id, status, updates in changes:
            self.update_status(contract_id, status, **updates)

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
            changes = [
                (c.contract_id, "superseded", {})
                if c.reconfirmation_required
                else (c.contract_id, "pending", {"context_integrity_unknown": True})
                for c in self._store.values()
                if c.canonical_user_id == canonical_user_id and c.status == "pending"
            ]
        for contract_id, status, updates in changes:
            self.update_status(contract_id, status, **updates)


# ══════════════════════════════════════════════════
# PR-0 / BUG-PENDING-APPROVAL-B — business description for reconfirmation
# תיאור עסקי קריא בלבד — לעולם לא internal contract_id בלבד (DoD #3/#9).
# ══════════════════════════════════════════════════

def _describe_contract_for_reconfirmation(contract: ActionContract) -> str:
    """Unchanged by BUG-115 — this helper's fallback (raw "tool_name / table")
    is relied on by other, pre-existing call sites outside the disambiguation
    list (e.g. _compose_status_reply_legacy()'s "✅ בוצע: {label}" executed-
    status text, asserted by test_stage_b_full_suite.py's DoD20 to contain
    the tool name). Generalizing this shared function's fallback instead of
    adding a separate one was tried first and reverted — it silently changed
    that unrelated, already-tested behavior too. See
    _describe_contract_for_disambiguation() below for the BUG-115-specific
    version, used only by the multi-contract list."""
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


def _describe_contract_for_disambiguation(contract: ActionContract) -> str:
    """BUG-115: human-readable label for ActionGateway's multi-contract
    disambiguation list ONLY — deliberately a separate function from
    _describe_contract_for_reconfirmation() above, not a generalization of
    it, so this fix cannot change that other function's behavior at its
    other call sites (tried, reverted — see its docstring). Reuses the same
    Leads-specific branch (identical business description either way), but
    generalizes the *fallback* to any table for airtable_add/airtable_update
    — production evidence showed every disambiguation-list item was exactly
    this shape (airtable_add/airtable_update against non-Leads tables like
    Tasks), which the shared helper's raw "tool_name / table" fallback would
    still leak the tool name for. Other tool types (gmail_send_draft/
    calendar_create_event/etc.) fall back to the shared helper's own
    behavior unchanged — production reports never exercise them here, and
    app.py's _describe_tool_call() already owns richer per-tool copy for
    the initial approval prompt itself."""
    payload = contract.normalized_payload or {}
    if contract.tool_name in ("airtable_add", "airtable_update") and payload.get("table") == _LEAD_CAPTURE_TABLE:
        return _describe_contract_for_reconfirmation(contract)
    table = payload.get("table") or payload.get("spreadsheet_name") or ""
    if table and contract.tool_name in ("airtable_add", "airtable_update"):
        verb = "הוספה" if contract.tool_name == "airtable_add" else "עדכון"
        preview = _first_field_preview(payload.get("fields") or {})
        return f"{verb} ב-{table}" + (f": {preview}" if preview else "")
    return _describe_contract_for_reconfirmation(contract)


# Staging finding #1 (23/07/2026): CONTRACT_PENDING_TTL_SECONDS is 24h,
# deliberately long (TMA approvals can sit unopened for hours) — a contract
# well under that TTL can still be old enough that a user picking blindly
# from a numbered list has no way to know it isn't from the current
# conversation. This does not change what counts as "live" (find_live_by_user
# already filters true TTL expiry) — it only makes age visible on every
# multi-item listing so a stale-but-not-yet-expired item can't be mistaken
# for a fresh one. Threshold is display-only, independent of the TTL itself.
_STALE_DISPLAY_THRESHOLD_SECONDS = 3600  # 1h


def _format_pending_age_suffix(contract: ActionContract) -> str:
    """Returns an inline age warning (" ⚠️ ממתין מ-X שעות/דקות") for a pending
    contract older than _STALE_DISPLAY_THRESHOLD_SECONDS, else "" — appended
    to each line of a multi-contract listing, never changes the underlying
    approve/reject decision."""
    age_seconds = time.time() - contract.created_at
    if age_seconds < _STALE_DISPLAY_THRESHOLD_SECONDS:
        return ""
    hours = int(age_seconds // 3600)
    if hours >= 1:
        return f" ⚠️ (ממתין מ-{hours} שעות)" if hours > 1 else " ⚠️ (ממתין משעה)"
    minutes = int(age_seconds // 60)
    return f" ⚠️ (ממתין מ-{minutes} דקות)"


def _first_field_preview(fields: dict, *, max_len: int = 40) -> str:
    """BUG-115: a short, human-readable preview of the first non-empty
    string-ish field value — used only for a compact disambiguation-list
    label, never for anything security-relevant. Skips record-id-shaped
    keys/values (technical identifiers, not business content) and
    truncates defensively."""
    for key, value in (fields or {}).items():
        if not isinstance(value, (str, int, float)):
            continue
        text = str(value).strip()
        if not text or re.fullmatch(r"rec[A-Za-z0-9]{14}", text):
            continue
        return text[:max_len] + ("…" if len(text) > max_len else "")
    return ""


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
        user_text: str = "",
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

        BUG-CANONICAL-TOOL-WIRING: resolve_canonical_tool() existed and was
        unit-tested (DoD19) but was never actually called from this method —
        the durable contract stored whatever tool_name the caller (including
        the raw, untrusted Agent tool_use loop) passed in verbatim. A "create
        task" request with no Sheets/Drive wording could therefore create a
        sheets_append/drive_* ActionContract that later failed on missing
        Google OAuth. Applied here, at the single contract-creation entry
        point, so every caller is protected uniformly; a no-op for every
        current caller that never passes a sheets/drive tool_hint.
        """
        tool_name, tool_inputs = resolve_canonical_call(
            tool_name, tool_inputs, user_text
        )

        if trusted_source == "agent":
            try:
                live = self.find_live_contracts(canonical_user_id)
            except ActionContractLookupError as exc:
                logger.error(
                    "[ActionGateway] live-contract lookup failed before Agent "
                    "proposal: user=%s error=%s", canonical_user_id, exc,
                )
                return GatewayResult(
                    ok=False,
                    reason="לא ניתן לבדוק כרגע אם קיימת פעולה ממתינה.",
                    user_message=(
                        "❌ לא ניתן לבדוק כרגע את בקשות האישור. "
                        "הפעולה החדשה לא נשמרה ולא תבוצע."
                    ),
                    failure_code="persistence_lookup_failed",
                )
            if live:
                logger.info(
                    "[BUG-122] proposal_boundary_blocked user=%s "
                    "existing_contract=%s proposed_tool=%s",
                    canonical_user_id, live[0].contract_id, tool_name,
                )
                return GatewayResult(
                    ok=False,
                    reason="קיימת פעולה לא פתורה; הצעת Agent חדשה נחסמה.",
                    contract_id=live[0].contract_id,
                    user_message=(
                        "יש לך פעולה שממתינה לאישור. יש לאשר או לבטל אותה, "
                        "ואז לשלוח מחדש את הבקשה החדשה. הפעולה החדשה לא נשמרה."
                    ),
                    failure_code="existing_pending_blocks_agent",
                )
        normalized = self.normalize_payload(tool_inputs)
        fingerprint = self.compute_business_fingerprint(
            tenant_id, canonical_user_id, tool_name, normalized
        )

        # The durable lookup happens before generating any contract identity.
        # An unavailable store is not evidence that the action is absent.
        try:
            existing = self._ledger.find_by_fingerprint(fingerprint)
        except ActionContractLookupError as exc:
            logger.error(
                "[ActionGateway] durable fingerprint lookup failed: tool=%s "
                "fingerprint=%.12s user=%s error=%s",
                tool_name, fingerprint, canonical_user_id, exc,
            )
            return GatewayResult(
                ok=False,
                reason="לא ניתן לבדוק אם בקשת הפעולה כבר קיימת.",
                user_message=(
                    "❌ לא ניתן לבדוק כרגע את מאגר בקשות האישור. "
                    "הפעולה לא הועברה לאישור ולא תבוצע."
                ),
                failure_code="persistence_lookup_failed",
            )
        if existing:
            if existing.status == "pending":
                return GatewayResult(
                    ok=False,
                    reason="כבר קיימת בקשת אישור פתוחה לפעולה הזו.",
                    contract_id=existing.contract_id,
                    user_message="⏳ כבר יש בקשת אישור פתוחה לפעולה זו. שלח *מאשר* כדי לאשר.",
                )
            if existing.status in ("completed", "executed"):
                return self._handle_duplicate_executed(existing, canonical_user_id)
            if existing.status in ("approved", "executing", "outcome_unknown"):
                return GatewayResult(
                    ok=False,
                    reason=f"הפעולה כבר קיימת במצב {existing.status}.",
                    contract_id=existing.contract_id,
                    user_message=(
                        "⚠️ הפעולה כבר אושרה או שתוצאתה אינה סופית. "
                        "אין ליצור אותה מחדש אוטומטית."
                    ),
                )

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

        contract_id = str(uuid.uuid4())
        contract = ActionContract(
            contract_id=contract_id,
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
            idempotency_key=hashlib.sha256(
                f"{contract_id}:{fingerprint}".encode()
            ).hexdigest()[:32],
        )

        if requires_approval:
            contract.status = "pending"
        else:
            contract.status = "approved"

        try:
            self._ledger.save(contract)
        except ActionContractPersistenceError as exc:
            logger.error(
                "[ActionGateway] durable proposal persistence failed: tool=%s "
                "fingerprint=%.12s user=%s error=%s",
                tool_name, fingerprint, canonical_user_id, exc,
            )
            return GatewayResult(
                ok=False,
                reason="לא ניתן לשמור את בקשת הפעולה באופן עמיד.",
                user_message=(
                    "❌ לא ניתן לשמור כרגע את בקשת האישור. "
                    "הפעולה לא הועברה לאישור ולא תבוצע."
                ),
                failure_code="persistence_failed",
            )
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
        user_text: str = "",
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
                user_text=user_text,
            )
            if not result.ok:
                logger.info(
                    "[ActionGateway] propose_gated blocked: %s | contract=%s",
                    result.reason, result.contract_id,
                )
                return result.user_message or f"⏳ {result.reason}"
            return None

        try:
            result = self.propose_action(
                tenant_id=tenant_id, canonical_user_id=canonical_user_id,
                tool_name=tool_name, tool_inputs=tool_inputs,
                origin_channel=origin_channel, origin_chat_id=origin_chat_id,
                requires_approval=True, identity=identity, trusted_source=trusted_source,
                user_text=user_text,
            )
            if result.failure_code in {"persistence_failed", "persistence_lookup_failed"}:
                return result.user_message or f"❌ {result.reason}"
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

    def is_own_resolution_event(
        self, canonical_user_id: str, text: str, live: list | None = None,
    ) -> bool:
        """
        live: an already-fetched find_live_contracts() result, reused instead
        of querying again. None (default) preserves the original behavior —
        fetch internally — so every existing caller (including direct tests
        that call this with 2 positional args) is unaffected. Passing `live`
        must be the SAME canonical_user_id's live contracts, fetched no
        earlier than this identity's current turn began — this method does
        not verify that; the caller owns that invariant. See app.py's
        _apply_ingress_context_gate() for the one caller that passes it, and
        docs/architecture/f52-unified-approval-runtime/audits/phase-4c/
        TURN_OWNERSHIP_EXTENSION.md's Case C read-amplification fix.
        """
        if live is None:
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

    def _resolve_single_contract(
        self, contract: "ActionContract", approver_role: str, canonical_user_id: str,
    ) -> tuple[str, bool]:
        """Single-contract resolution logic shared by both the "only one live
        contract" case and the BUG-115 bookmark-hit case below — same
        reconfirmation/context-poisoning safety either way (BUG-PENDING-
        APPROVAL-B), never bypassed by a bookmark.

        Returns (message, terminal): terminal=True means this contract's fate
        was fully decided this call (approved, or a durable-write failure) —
        the caller should clear any BUG-115 bookmark pointing at it.
        terminal=False means a reconfirmation was requested instead (context
        was interrupted since this contract was last shown) — the contract
        is still pending and needs one more confirm word, so a bookmark
        pointing at it must be KEPT, not cleared, or the next confirm would
        itself fall into the same disambiguation problem this fix exists to
        solve."""
        # PR-0 / BUG-PENDING-APPROVAL-B: a message unrelated to this
        # contract arrived since the preview was shown (mark_context_interrupted).
        # The first "כן" after that must re-show the business description
        # and require an explicit second "כן" — never silently execute a
        # stale action (context poisoning). context_integrity_unknown is
        # gated identically — a marking failure must never be treated as
        # "context intact" (see _apply_ingress_context_gate in app.py).
        if (contract.context_interrupted or contract.context_integrity_unknown) \
                and not contract.reconfirmation_required:
            try:
                self._ledger.update_status(
                    contract.contract_id, contract.status,
                    reconfirmation_required=True,
                )
            except ActionContractTransitionError as exc:
                logger.error(
                    "[ActionGateway] durable reconfirmation update failed: "
                    "contract=%s error=%s",
                    contract.contract_id, exc,
                )
                return (
                    "❌ לא ניתן לשמור את מצב האישור באופן עמיד. "
                    "הפעולה לא בוצעה; אין לנסות שוב עד לבדיקת המערכת."
                ), True
            desc = _describe_contract_for_reconfirmation(contract)
            return (
                f"יש פעולה קודמת שממתינה לאישור: {desc}.\n"
                f"לאשר אותה? (כן/לא)"
            ), False
        result = self.approve(contract.contract_id, approver=canonical_user_id, approver_role=approver_role)
        return result, True

    def route_confirmation_word(self, canonical_user_id: str, approver_role: str = "") -> str:
        """
        מיירט מילת אישור חופשית (כמו "מאשר") לפני שמגיעה ל-Agent.
        מחזיר תשובה ישירה למשתמש.

        approver_role: BUG-074 — התפקיד המאומת של המשתמש שמאשר עכשיו (לא
        נגזר מ-canonical_user_id). approve() הוא שער האכיפה — ראה שם.

        BUG-115: בודק קודם bookmark "contract שהוצג לאחרונה" (session_store,
        נרשם ב-_propose_lead_write()'s caller ו-app.py's
        _queue_approval_detailed_impl() ברגע ששולחת הודעת-אישור visible
        למשתמש) — אם קיים, מצביע על contract חי ("pending") ששייך לאותו
        canonical_user_id, ולא פג תוקף (600 שניות), נפתר ישירות מולו,
        ללא קשר לכמה contracts ישנים ולא-קשורים אחרים גם חיים. רק כשה-
        bookmark חסר/פג-תוקף/לא-חי/משתמש-אחר נופל להתנהגות הקיימת (ספירה
        לפי כמות). ראה docs/architecture/action-gateway/
        BUG-115_CONFIRMATION_ROUTING_HIJACK_AUDIT.md.
        """
        try:
            from session_store import lead_sessions as _ls
            _bookmark = _ls.get_last_prompted_contract(canonical_user_id)
        except Exception:
            _bookmark = None
        if _bookmark:
            _bookmarked = self._ledger.find_by_id(_bookmark.get("contract_id", ""))
            if (
                _bookmarked is not None
                and _bookmarked.status == "pending"
                and _bookmarked.canonical_user_id == canonical_user_id
            ):
                message, terminal = self._resolve_single_contract(
                    _bookmarked, approver_role, canonical_user_id,
                )
                if terminal:
                    try:
                        from session_store import lead_sessions as _ls2
                        _ls2.clear_last_prompted_contract(canonical_user_id)
                    except Exception:
                        pass
                return message
            # Bookmark present but stale/no-longer-live/wrong-user — clear it
            # (nothing useful left to point at) and fall through below.
            try:
                from session_store import lead_sessions as _ls3
                _ls3.clear_last_prompted_contract(canonical_user_id)
            except Exception:
                pass

        live = self.find_live_contracts(canonical_user_id)
        if len(live) == 0:
            return self.describe_no_pending_reason(canonical_user_id)
        if len(live) == 1:
            message, _terminal = self._resolve_single_contract(live[0], approver_role, canonical_user_id)
            return message
        # יותר מאחת — מציג רשימה ממוספרת + שומר disambiguation state
        with self._disambiguation_lock:
            self._disambiguation[canonical_user_id] = list(live)
        lines = ["יש כמה פעולות הממתינות לאישור — איזו?"]
        for i, c in enumerate(live, 1):
            # BUG-115: human-readable business description, never the raw
            # tool_name/internal contract_id. Uses the disambiguation-
            # specific helper (not _describe_contract_for_reconfirmation()
            # directly) so this fix cannot change that other function's
            # behavior at its other, unrelated call sites — see both
            # functions' docstrings.
            lines.append(f"• {i}. {_describe_contract_for_disambiguation(c)}{_format_pending_age_suffix(c)}")
        lines.append("\nשלח את המספר (1, 2, ...) כדי לאשר פעולה ספציפית.")
        return "\n".join(lines)

    # ── BUG-056 — route_cancellation_word ───────────────────────────

    def reject(self, contract_id: str, rejected_by: str = "") -> str:
        """Durably reject one pending contract without executing it."""
        contract = self._ledger.find_by_id(contract_id)
        if not contract:
            return "⚠️ פעולה לא נמצאה."
        if contract.status != "pending":
            return f"⚠️ הפעולה אינה במצב המתנה (מצב נוכחי: {contract.status})."
        try:
            self._ledger.update_status(contract_id, "rejected")
        except ActionContractTransitionError as exc:
            logger.error(
                "[ActionGateway] durable rejection failed: contract=%s by=%s error=%s",
                contract_id, rejected_by, exc,
            )
            return (
                "❌ לא ניתן לשמור את ביטול הפעולה באופן עמיד. "
                "הפעולה לא סומנה כמבוטלת; אין לנסות לאשר אותה עד לבדיקת המערכת."
            )
        logger.info(
            "[ActionGateway] rejected: contract=%s tool=%s by=%s",
            contract_id, contract.tool_name, rejected_by,
        )
        return "🚫 הפעולה בוטלה."

    # ── F52 PR5 — rejection/cancellation shadow verification ────────
    # Production finding: reject()/route_cancellation_word()/route_combined_word()
    # never called compose_status_reply() at all — every rejection/cancellation
    # reply was a hardcoded legacy string with zero FEATURE_UNIFIED_STATUS_FORMATTER
    # involvement, so no [UnifiedStatusFormatterShadow] line was ever emitted for
    # this surface (PR4 only wired the EXECUTED/status-query path). This closes
    # that gap the same way PR4 did for compose_status_reply(): off (default)
    # returns the caller's own legacy text byte-identical; shadow computes the
    # unified text via the SAME formatter/state-mapping already used for the
    # executed path ("rejected" -> "failure" family, locked in PR1-3 — no new
    # canonical state invented here) and logs the SAME safe comparison record
    # PR4 already built (_log_shadow_comparison/_shadow_leak_flags, reused
    # as-is, not duplicated); on returns the unified text.
    #
    # Deliberately NOT folded into reject() itself: reject()'s return value is
    # an internal control-flow signal multiple callers branch on via
    # `result.startswith("🚫")` (route_cancellation_word's loop, route_
    # disambiguation's/route_combined_word's sibling-closing) to distinguish
    # "successfully rejected" from "a real error occurred". If reject() itself
    # returned the unified text under 'on', that prefix check would silently
    # break (unified wording does not start with "🚫") — a latent multi-
    # contract correctness bug that would only surface once an operator later
    # sets the flag to 'on'. Rendering happens instead at the OUTERMOST,
    # actually-user-visible return points, exactly mirroring where
    # compose_status_reply() itself is called (at the final reply boundary,
    # never woven into internal helpers) — see route_cancellation_word() and
    # route_combined_word() below. Sibling rejections closed while resolving a
    # disambiguation/combined-word CONFIRM are never independently shown to
    # the user (only the chosen contract's approve() reply is) — nothing to
    # render there.

    def _render_rejection_reply(self, contract: "ActionContract", legacy_text: str) -> str:
        """Renders a rejection/cancellation reply through the same off/
        shadow/on FEATURE_UNIFIED_STATUS_FORMATTER path compose_status_reply()
        uses, without changing reject()'s own return contract. legacy_text is
        the caller's own pre-existing hardcoded reply — returned unchanged
        unless the flag is 'on'."""
        try:
            from feature_flags import get_unified_status_formatter_state
            state = get_unified_status_formatter_state()
        except Exception:
            state = "off"

        if state == "off":
            return legacy_text

        fact = ActionFact(
            tool_name=contract.tool_name,
            contract_id=contract.contract_id,
            outcome="rejected",
            record_id=None,
            error_code=None,
            raw_tool_response={},
        )
        try:
            unified_text, meta = self._compose_status_reply_unified(fact)
        except Exception as exc:
            # A rejection reply must never break because of the formatter.
            logger.warning("[ActionGateway] unified rejection formatter failed: %s", exc)
            return legacy_text

        if state == "shadow":
            self._log_shadow_comparison(fact, legacy_text, unified_text, meta)
            return legacy_text

        # state == "on"
        return unified_text

    # ── F52 PR6 — approval_pending prompt shadow rendering ───────────────
    # Same architectural gap PR5 closed for rejections, now for the
    # approval-pending notification surface: app.py's
    # _queue_approval_detailed_impl() sends its own hardcoded "⏳ בקשת
    # אישור..." text directly via bot.send_message(), never through
    # compose_status_reply()/ActionFact — so FEATURE_UNIFIED_STATUS_
    # FORMATTER=shadow had no visibility into this surface, and outcome=
    # "pending" (already a valid ActionFact.outcome, already mapped to the
    # "approval_pending" canonical state by _action_fact_to_message() —
    # see that method, unmodified) was never actually exercised end-to-end
    # from a real call site.
    #
    # off (default): returns the caller's own legacy_text byte-identical.
    # shadow: computes the unified text via the SAME formatter/state-mapping
    # already used for the executed/rejected paths, logs the SAME safe
    # comparison record (_log_shadow_comparison/_shadow_leak_flags, reused
    # as-is), and still returns legacy_text. on: returns the unified text.
    #
    # Deliberately a free-standing render call at the actual send site
    # (app.py), not folded into propose_action()/request_approval() —
    # mirrors exactly where _render_rejection_reply() is called from
    # route_cancellation_word()/route_combined_word(), never woven into an
    # internal helper that other callers depend on for a different contract.
    def _render_pending_prompt(
        self, tool_name: str, contract_id: str | None, legacy_text: str,
    ) -> str:
        """Renders the approval-pending owner notification through the same
        off/shadow/on FEATURE_UNIFIED_STATUS_FORMATTER path compose_status_
        reply() uses, without changing the legacy EventBus/Telegram
        notification flow itself. legacy_text is the caller's own
        pre-existing hardcoded prompt — returned unchanged unless the flag
        is 'on'. contract_id may be None (e.g. shadow-mode propose_action()
        raised before returning one) — _action_fact_to_message() already
        handles a missing/unfound contract by falling back to an empty
        human_summary, same as every other outcome."""
        try:
            from feature_flags import get_unified_status_formatter_state
            state = get_unified_status_formatter_state()
        except Exception:
            state = "off"

        if state == "off":
            return legacy_text

        fact = ActionFact(
            tool_name=tool_name,
            contract_id=contract_id or "",
            outcome="pending",
            record_id=None,
            error_code=None,
            raw_tool_response={},
        )
        try:
            unified_text, meta = self._compose_status_reply_unified(fact)
        except Exception as exc:
            # An approval prompt must never break because of the formatter.
            logger.warning("[ActionGateway] unified pending formatter failed: %s", exc)
            return legacy_text

        if state == "shadow":
            self._log_shadow_comparison(fact, legacy_text, unified_text, meta)
            return legacy_text

        # state == "on"
        return unified_text

    def reject_if_pending(self, contract_id: str, rejected_by: str = "") -> bool:
        """
        Atomic conditional cancel (Codex re-audit of 818c8a6 — TOCTOU race
        fix): transition pending -> rejected ONLY if the contract is still
        pending at the moment of the guarded ledger write, and return True
        iff THIS call performed that transition.

        Unlike reject() — which reads the status, checks it is "pending", and
        only THEN (in a separate step) calls update_status() — this pushes
        the "must still be pending" check INTO the same atomic write
        (update_status(require_status="pending")). reject()'s two-step form
        leaves a window: a concurrent turn moving the contract pending ->
        approved between the check and the write is silently overwritten to
        "rejected" by the RAM ledger's unconditional set. A caller that then
        reads back "rejected" would wrongly conclude its own cancellation
        succeeded, when it in fact clobbered a live approval. This method
        makes that impossible: if the contract is not pending at the write,
        no mutation happens and False is returned.

        Any failure to cleanly transition (durable CAS mismatch, a transition
        error, or a missing contract) returns False without raising — the
        caller treats False as "not cancelled by us", never as success.
        reject() itself is intentionally left unchanged so its existing
        callers (route_cancellation_word, the Telegram approval callback)
        keep their current user-facing-string contract; this is an additive,
        purpose-built API for the PA-01 orphan-cleanup path, which needs a
        verified boolean, not a message.

        Codex re-audit of ce990a0: True is returned ONLY when a real atomic
        primitive actually performed pending -> rejected. On the RAM-only
        ledger that is the single-lock guarded set in update_status(). When a
        DURABLE repository is active that has no atomic conditional primitive
        (Airtable — see ActionContractRepository.supports_atomic_conditional_
        transition), update_status(require_status="pending") fails closed and
        returns False WITHOUT any PATCH, so this returns False too — a
        destructive conditional cleanup is never performed non-atomically
        against the durable store. A read-back showing "rejected" is never on
        its own sufficient to return True.
        """
        try:
            return bool(self._ledger.update_status(
                contract_id, "rejected", require_status="pending",
            ))
        except Exception as exc:
            logger.warning(
                "[ActionGateway] reject_if_pending: transition failed contract=%s error=%s",
                contract_id, exc,
            )
            return False

    def route_cancellation_word(self, canonical_user_id: str) -> str | None:
        """
        מיירט מילת ביטול חופשית ("לא") לפני שמגיעה ל-Agent.
        מחזיר None אם אין contracts חיים (ממשיך לזרימה הקיימת/ל-Agent),
        אחרת מבטל את כל ה-contracts החיים ומחזיר תשובת ביטול.
        """
        live = self.find_live_contracts(canonical_user_id)
        if not live:
            return None
        rendered = "🚫 הפעולה בוטלה."
        for c in live:
            result = self.reject(c.contract_id, rejected_by=canonical_user_id)
            if not result.startswith("🚫"):
                return result
            # F52 PR5: render (off: unchanged, shadow: logged+unchanged, on:
            # unified) only on confirmed success — reject()'s own return
            # contract above is untouched, so the "🚫" check stays valid
            # regardless of formatter state.
            rendered = self._render_rejection_reply(c, result)
        return rendered

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
        rejected_siblings = 0
        for sibling in pending_list:
            if sibling.contract_id != contract.contract_id and sibling.status == "pending":
                rejection = self.reject(sibling.contract_id, rejected_by=canonical_user_id)
                if not rejection.startswith("🚫"):
                    return rejection
                rejected_siblings += 1
                logger.info(
                    "[ActionGateway] disambiguation: closing sibling contract=%s tool=%s",
                    sibling.contract_id, sibling.tool_name,
                )
        logger.info(
            "[ActionGateway] disambiguation: user=%s selected idx=%d contract=%s tool=%s rejected_siblings=%d",
            canonical_user_id, idx, contract.contract_id, contract.tool_name, rejected_siblings,
        )
        result = self.approve(contract.contract_id, approver=canonical_user_id, approver_role=approver_role)
        # Staging finding #3 (23/07/2026): the user was never told that
        # picking one item from the list silently rejected the others — see
        # §21 comment above. Disclosure only, does not change what got
        # rejected (already decided above, unconditionally, before this fix).
        if rejected_siblings:
            result += (
                f"\n\nℹ️ שים לב: {rejected_siblings} פעולות נוספות שהיו ברשימה נדחו אוטומטית "
                f"(בחירה לפי מספר מבטלת את שאר האפשרויות שהוצגו יחד)."
            )
        return result

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
            rejected_siblings = 0
            for sibling in live:
                if sibling.contract_id != contract.contract_id and sibling.status == "pending":
                    rejection = self.reject(sibling.contract_id, rejected_by=canonical_user_id)
                    if not rejection.startswith("🚫"):
                        return rejection
                    rejected_siblings += 1
                    logger.info(
                        "[ActionGateway] combined_word confirm: closing sibling contract=%s tool=%s",
                        sibling.contract_id, sibling.tool_name,
                    )
            logger.info(
                "[ActionGateway] combined_word: user=%s confirm idx=%d contract=%s tool=%s rejected_siblings=%d",
                canonical_user_id, idx, contract.contract_id, contract.tool_name, rejected_siblings,
            )
            result = self.approve(contract.contract_id, approver=canonical_user_id, approver_role=approver_role)
            # Staging finding #3 (23/07/2026) — see route_disambiguation()'s
            # identical disclosure for the full rationale.
            if rejected_siblings:
                result += (
                    f"\n\nℹ️ שים לב: {rejected_siblings} פעולות נוספות שהיו ברשימה נדחו אוטומטית "
                    f"(בחירה לפי מספר מבטלת את שאר האפשרויות שהוצגו יחד)."
                )
            return result

        # action == "cancel" — דוחה רק את הפריט שנבחר, לא נוגע בשאר הממתינים
        rejection = self.reject(contract.contract_id, rejected_by=canonical_user_id)
        if not rejection.startswith("🚫"):
            return rejection
        logger.info(
            "[ActionGateway] combined_word: user=%s cancel idx=%d contract=%s tool=%s",
            canonical_user_id, idx, contract.contract_id, contract.tool_name,
        )
        remaining = len(live) - 1
        if remaining > 0:
            legacy_text = f"🚫 פעולה מספר {idx} ({contract.tool_name}) בוטלה. נשארו {remaining} פעולות ממתינות."
        else:
            legacy_text = f"🚫 פעולה מספר {idx} בוטלה."
        # F52 PR5: same off/shadow/on rendering as route_cancellation_word()
        # above. Note (pre-existing, not introduced or fixed here): the
        # legacy_text branch above already embeds contract.tool_name — a
        # leak that predates this PR and is intentionally left as-is (legacy
        # output must stay byte-identical); only the unified/shadow text this
        # renders is guaranteed tool-name-free.
        return self._render_rejection_reply(contract, legacy_text)

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

        # Approval is durably recorded before execution. This is not the
        # execution claim: PostgreSQL claim acquisition inside
        # _execute_contract remains the sole dispatcher-ownership boundary.
        try:
            self._ledger.update_status(
                contract_id, "approved", approved_by=approver, approved_at=time.time(),
            )
        except ActionContractTransitionError as exc:
            logger.error(
                "[ActionGateway] durable approval failed before execution: "
                "contract=%s approver=%s error=%s",
                contract_id, approver, exc,
            )
            return (
                "❌ האישור לא נשמר באופן עמיד ולכן הפעולה לא בוצעה. "
                "אין לנסות שוב עד לבדיקת המערכת."
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

        def _persist_execution_status(status: str) -> bool:
            try:
                persisted = self._ledger.update_status(contract.contract_id, status)
            except ActionContractTransitionError as exc:
                logger.critical(
                    "[ActionGateway] durable execution lifecycle write failed: "
                    "contract=%s status=%s error=%s",
                    contract.contract_id, status, exc,
                )
                return False
            if not persisted:
                logger.critical(
                    "[ActionGateway] execution lifecycle contract missing: "
                    "contract=%s status=%s",
                    contract.contract_id, status,
                )
                return False
            return True

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
                if not _persist_execution_status("failed"):
                    return (
                        "❌ לא ניתן לאמת את זהות המבקש, וגם סטטוס הכשל לא נשמר "
                        "באופן עמיד. אין לנסות שוב עד לבדיקת המערכת."
                    )
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
                    # A structured dispatcher outcome means claim ownership was
                    # acquired and the provider result is known. A None result
                    # means dispatch never started (DB unavailable/conflict);
                    # leave the durable contract approved rather than letting a
                    # losing caller overwrite the claim owner's terminal state.
                    from core.dispatcher_outcome import DispatcherOutcome
                    if isinstance(result, DispatcherOutcome):
                        terminal_status = result.result
                        if not _persist_execution_status(terminal_status):
                            return (
                                "⚠️ תוצאת הביצוע סווגה כ־"
                                f"{terminal_status}, אך לא נשמרה באופן עמיד. "
                                "אין לנסות שוב עד לבדיקת המערכת."
                            )
                        if result.is_outcome_unknown():
                            return (
                                result.user_message
                                or "⚠️ תוצאת הפעולה אינה ידועה. אין לנסות שוב אוטומטית."
                            )
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
                if not _persist_execution_status("failed"):
                    return (
                        "❌ המבצע האטומי נכשל, וגם סטטוס הכשל לא נשמר באופן עמיד. "
                        "אין לנסות שוב עד לבדיקת המערכת."
                    )
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
                if not _persist_execution_status("failed"):
                    return (
                        "❌ הביצוע נכשל, וגם סטטוס הכשל לא נשמר באופן עמיד. "
                        "אין לנסות שוב עד לבדיקת המערכת."
                    )
                logger.error(
                    "[ActionGateway] execution failed: contract=%s error=%s",
                    contract.contract_id, exc,
                )
                return f"❌ ביצוע נכשל: {exc}"

        # A legacy/direct executor may already expose the same structured
        # outcome contract used by the atomic path. Preserve ambiguity rather
        # than forcing it through evidence parsing as a generic failure.
        from core.dispatcher_outcome import DispatcherOutcome
        if isinstance(raw, DispatcherOutcome):
            if raw.is_failed() or raw.is_outcome_unknown():
                if not _persist_execution_status(raw.result):
                    return (
                        "⚠️ תוצאת הביצוע סווגה כ־"
                        f"{raw.result}, אך לא נשמרה באופן עמיד. "
                        "אין לנסות שוב עד לבדיקת המערכת."
                    )
                if raw.is_outcome_unknown():
                    return raw.user_message or "⚠️ תוצאת הפעולה אינה ידועה. אין לנסות שוב אוטומטית."
                return f"❌ ביצוע נכשל: {raw.error or raw.user_message}"
            raw = raw.raw_response or {
                "ok": True,
                "external_id": raw.external_id,
                "user_message": raw.user_message,
            }

        # §3 / §6: verify before reporting success — no real evidence → failure
        try:
            from core.anti_hallucination import verify_execution
            check = verify_execution(contract.tool_name, raw)
            if check.status == "failed":
                if not _persist_execution_status("failed"):
                    return (
                        "❌ לא נמצאה הוכחת ביצוע, וגם סטטוס הכשל לא נשמר באופן עמיד. "
                        "אין לנסות שוב עד לבדיקת המערכת."
                    )
                logger.error(
                    "[ActionGateway] evidence missing: contract=%s tool=%s reason=%s",
                    contract.contract_id, contract.tool_name, check.reason,
                )
                return f"❌ הפעולה לא הושלמה: {check.reason}"
        except Exception as verify_exc:
            logger.warning("[ActionGateway] verify_execution import failed: %s", verify_exc)

        ext_id = raw.get("external_id", "") if isinstance(raw, dict) else ""
        # Preserve Phase 4B-1A flag-OFF behavior exactly: RAM-only ledgers keep
        # the legacy success value. Durable ledgers emit canonical completed.
        success_status = (
            "completed" if getattr(self._ledger, "_repository", None) else "executed"
        )
        if not _persist_execution_status(success_status):
            return (
                f"⚠️ הספק החזיר הצלחה מפורשת, אך סטטוס {success_status} לא נשמר "
                "באופן עמיד. אין לנסות שוב עד לבדיקת המערכת."
            )
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
        # BUG-SS-DOUBLE-SUCCESS: compose_status_reply() is documented above
        # (§15.2) as "the only function allowed to produce action-status
        # text" — this used to also append the executor's own C53-A
        # user_message as a second line, producing two success statements
        # in one reply (e.g. "✅ בוצע: ..." followed by "✅ רשומה נוספה...").
        # The executor's raw response (including user_message) is still
        # preserved internally on `fact.raw_tool_response` (and already
        # logged above) for verification/audit — it is simply never
        # surfaced a second time in the user-facing text.
        gateway_reply = self.compose_status_reply(fact)
        return gateway_reply.text

    # ── §15.2 — compose_status_reply ────────────────────────────────
    # הפונקציה היחידה בכל הקוד שמותר לה לייצר טקסט סטטוס-פעולה.
    # F52 PR4 scope guard: represents exactly ONE ActionFact. Batch/multi-status
    # rendering (approval_pending_batch, mixed, mixed_with_unknown) is out of
    # scope here — this path has no multi-fact input to format. See
    # docs/architecture/f52-unified-approval-runtime/PR4_ACTION_STATUS_SHADOW_VERIFICATION.md §5.
    #
    # F52 reconciliation: this remains the single entry point for action-status
    # text, but it is no longer a second competing formatter. Under
    # FEATURE_UNIFIED_STATUS_FORMATTER it delegates the WORDING to the one
    # canonical formatter (core/agent_message_formatter.format_agent_message).
    #   off    → the legacy text below, byte-identical to before F52.
    #   shadow → unified text computed + logged next to legacy; legacy is sent.
    #   on     → unified text is sent.
    # The legacy renderer (_compose_status_reply_legacy) is retained only as the
    # flag-off fallback and is slated for removal after the cutover.

    def compose_status_reply(self, fact: ActionFact) -> GatewayReply:
        legacy = self._compose_status_reply_legacy(fact)

        try:
            from feature_flags import get_unified_status_formatter_state
            state = get_unified_status_formatter_state()
        except Exception:
            state = "off"

        if state == "off":
            return legacy

        try:
            unified_text, meta = self._compose_status_reply_unified(fact)
        except Exception as exc:
            # The live status path must never break because of the formatter.
            logger.warning("[ActionGateway] unified status formatter failed: %s", exc)
            return legacy

        if state == "shadow":
            self._log_shadow_comparison(fact, legacy.text, unified_text, meta)
            return legacy

        # state == "on"
        return GatewayReply(text=unified_text, fact=fact)

    # ── F52 PR4 — safe shadow comparison logging ────────────────────
    # Logs only booleans/counts/state-names, never the rendered text itself
    # (legacy or unified text may embed business data — names, phones, business
    # summaries — that must not ride into logs), and never raw record_id/
    # tool_name/contract_id values. Independently re-checks (defense in depth,
    # on top of the formatter's own redaction) that none of those identifiers
    # slipped into the text that would be sent if the flag were 'on'.

    @staticmethod
    def _shadow_leak_flags(fact: ActionFact, unified_text: str) -> dict:
        return {
            "record_id_leak":    bool(fact.record_id) and fact.record_id in unified_text,
            "tool_name_leak":    bool(fact.tool_name) and fact.tool_name in unified_text,
            "contract_id_leak":  bool(fact.contract_id) and fact.contract_id in unified_text,
        }

    def _log_shadow_comparison(
        self, fact: ActionFact, legacy_text: str, unified_text: str, meta: dict,
    ) -> None:
        leaks = self._shadow_leak_flags(fact, unified_text)
        logger.info(
            "[UnifiedStatusFormatterShadow] outcome=%s mapped_state=%s text_differs=%s "
            "record_id_leak=%s tool_name_leak=%s contract_id_leak=%s "
            "redaction_count=%d fallback_used=%s formatter_version=%s "
            "legacy_len=%d unified_len=%d",
            fact.outcome, meta.get("message_state"), legacy_text != unified_text,
            leaks["record_id_leak"], leaks["tool_name_leak"], leaks["contract_id_leak"],
            meta.get("redaction_count", 0), meta.get("fallback_used", False),
            meta.get("formatter_version"), len(legacy_text), len(unified_text),
        )
        if any(leaks.values()):
            logger.warning(
                "[UnifiedStatusFormatterShadow] potential identifier leak detected: "
                "record_id_leak=%s tool_name_leak=%s contract_id_leak=%s outcome=%s",
                leaks["record_id_leak"], leaks["tool_name_leak"], leaks["contract_id_leak"],
                fact.outcome,
            )

    def _compose_status_reply_legacy(self, fact: ActionFact) -> GatewayReply:
        """Pre-F52 status wording. Retained only as the FEATURE_UNIFIED_STATUS_
        FORMATTER=off fallback; do not add new call sites."""
        if fact.outcome in ("completed", "executed"):
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

    def _action_fact_to_message(self, fact: ActionFact) -> tuple[str, dict]:
        """Map a structured ActionFact to the canonical formatter's
        (state, payload). The business label comes from the frozen contract,
        never the raw tool_name; technical ids are dropped (the formatter
        redacts anything that slips through). Rejection/expiry are failure-family
        variants (spec); an unrecognized outcome is outcome_unknown, never
        success."""
        contract = self._ledger.find_by_id(fact.contract_id) if fact.contract_id else None
        label = _describe_contract_for_reconfirmation(contract) if contract else ""

        if fact.outcome in ("completed", "executed"):
            return "success", {"human_summary": label}
        if fact.outcome == "pending":
            return "approval_pending", {"human_summary": label}
        if fact.outcome == "failed":
            # Only the stable reason_code is passed; an unrecognized code maps to
            # a generic human message rather than echoing the raw code.
            return "failure", {"reason_code": fact.error_code}
        if fact.outcome == "rejected":
            return "failure", {"reason_code": "ACTION_REJECTED",
                               "reason": "הפעולה נדחתה."}
        return "outcome_unknown", {}

    def _compose_status_reply_unified(self, fact: ActionFact) -> tuple[str, dict]:
        """Returns (text, meta). meta is the formatter's own observability
        record (message_state, formatter_version, fallback_used,
        redaction_count) — safe to log as-is, never contains raw text/ids."""
        from core.agent_message_formatter import format_agent_message_with_meta
        state, payload = self._action_fact_to_message(fact)
        return format_agent_message_with_meta(state, payload)

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
            and c.status in ("completed", "executed", "failed", "outcome_unknown")
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

    # Staging finding #4 (23/07/2026): a natural-language "what's pending
    # approval?" question (e.g. "לאשר את הפעולות שממתינות לאישור") doesn't
    # match the exact-word grammar of _CONFIRM_WORDS/route_confirmation_word,
    # so it used to fall straight through to the general agent — which has no
    # dedicated tool for ActionContracts and guessed at an ordinary Airtable
    # table (observed: "Tasks") instead. Read-only: never approves/rejects
    # anything, unlike route_confirmation_word()'s single-live-contract branch.
    # Sets the same disambiguation state route_confirmation_word() sets, so a
    # follow-up bare number still resolves via route_disambiguation().
    #
    # Review follow-up (23/07/2026, finding #3 of the review pass): this
    # queries ActionContracts only. Two other pending-action stores exist in
    # this codebase and are NOT covered here — app.py's own _pending_approvals
    # dict and event_bus.py's PendingActionsStore/bus.pending (the "Stage A"
    # legacy approval queue documented in CLAUDE.md's approval-flow section,
    # still live for approval paths not migrated onto ActionGateway). A
    # aggregate-all-sources answer would require a new read-only aggregator
    # spanning all three stores — a real design decision (how to de-duplicate/
    # order them, whether that belongs on ActionGateway at all), not something
    # to improvise here. Until that exists, the reply must not imply it
    # checked everything — see the fixed final line below.
    def describe_pending_queue(self, canonical_user_id: str) -> str:
        live = self.find_live_contracts(canonical_user_id)
        if not live:
            no_pending = self.describe_no_pending_reason(canonical_user_id)
            base = no_pending or "לא מצאתי בקשות ממתינות במערכת ActionContracts."
            return base + "\n\n(הבדיקה מכסה את מערכת ActionContracts בלבד — לא תורי אישור legacy נוספים.)"
        with self._disambiguation_lock:
            self._disambiguation[canonical_user_id] = list(live)
        lines = [f"במערכת ActionContracts מצאתי {len(live)} בקשות ממתינות:"]
        for i, c in enumerate(live, 1):
            lines.append(f"• {i}. {_describe_contract_for_disambiguation(c)}{_format_pending_age_suffix(c)}")
        lines.append("\nשלח את המספר (1, 2, ...) כדי לאשר פעולה ספציפית, או \"בטל <מספר>\" כדי לדחות אחת.")
        lines.append("\n(הבדיקה אינה כוללת כרגע תורי אישור legacy נוספים.)")
        return "\n".join(lines)

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
                fail_closed_on_lookup_error=True,
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

    P0 (unhashable Identity): the atomic-claims wrapper (execute_with_atomic_claim)
    already reconstructs and fail-closed-validates an Identity from the frozen
    contract before calling this executor — it must be threaded straight through
    to dispatch_tool's identity= keyword, not re-derived here a second time.
    `identity` is therefore an explicit keyword param: when the caller supplies
    one (atomic path), it is used as-is; when omitted (legacy flag-OFF path,
    which never had an identity to give), behavior is unchanged from before —
    identity is derived from contract_id via the ledger lookup below.
    """
    def _executor(tool_name: str, tool_inputs: dict, contract_id: str, identity=None, claim_execution_id=None):
        from tools.dispatcher import dispatch_tool
        from identity import Identity, resolve_identity

        contract = ledger.find_by_id(contract_id)

        if identity is None:
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
        else:
            logger.info(
                "[ActionGateway] using pre-resolved identity from atomic wrapper: "
                "contract=%s tenant=%s user=%s role=%s external_id=%s",
                contract_id, identity.tenant_id, identity.user_id, identity.role, identity.external_id,
            )

        # BUG-091: trusted_source comes from the contract itself (set once,
        # server-side, at propose_action() time) — never re-derived from
        # tool_inputs, which is Claude-controlled data that survives
        # normalize_payload() unchanged (including any "_source" key).
        _trusted_source = getattr(contract, "trusted_source", "agent") if contract else "agent"

        # Phase 4B-2 follow-up: execution_context is the ONLY legitimate
        # source of contract_id/approved_by for tools (like tma_write) that
        # refuse to run outside the propose/approve ceremony. Populated only
        # here, from the durable contract itself — never from tool_inputs
        # (frozen, attacker-influenceable payload) and never re-derived from
        # `identity` (the frozen REQUESTER, not the approver — see
        # tools/approval_actions.py::tma_write()'s docstring). approved_by
        # is only meaningful once approve() has durably transitioned the
        # contract, which is always true by the time _execute_contract()
        # (and therefore this executor) runs.
        #
        # claim_execution_id (Phase 4B-2 authority-boundary follow-up): a
        # plain execution_context dict is caller-constructible and therefore
        # forgeable proof by itself — contract_id/approved_by alone are NOT
        # sufficient. claim_execution_id is the execution_id of the real
        # PostgreSQL row that execute_with_atomic_claim() acquired for THIS
        # specific execution attempt (passed in only when the atomic-claims
        # path ran and won the claim; None on the legacy flag-OFF path, where
        # no PostgreSQL claim was ever created). Gated tools must independently
        # verify this id against a live claim via
        # core.atomic_claim_repository.get_claim(contract_id) — never trust
        # the dict's presence alone.
        execution_context = (
            {
                "contract_id": contract_id,
                "approved_by": getattr(contract, "approved_by", "") or "",
                "claim_execution_id": claim_execution_id,
            }
            if contract else None
        )
        return dispatch_tool(
            tool_name, tool_inputs, identity=identity, trusted_source=_trusted_source,
            execution_context=execution_context,
        )

    return _executor


# Phase 4B-1A: durable NEW proposals and proposal-recovery lookups are enabled
# independently from ActionGateway enforcement. Default OFF means the exact
# existing RAM-only ledger and zero ActionContractRepository calls. The legacy
# _build_airtable_writer() is intentionally never activated: it is a partial
# mirror that omits frozen identity/policy/context fields. Status/context
# write-through remains out of scope until Phase 4B-1B.
def _build_action_contract_repository():
    from feature_flags import is_enabled
    if not is_enabled("FEATURE_ACTION_CONTRACT_PERSISTENCE"):
        return None
    from core.action_contract_repository import ActionContractRepository
    return ActionContractRepository()


_action_contract_repository_singleton = _build_action_contract_repository()
_ledger_singleton = ExecutionLedger(
    airtable_writer=None,
    repository=_action_contract_repository_singleton,
)
action_gateway = ActionGateway(
    ledger=_ledger_singleton,
    tool_executor=_make_dispatch_executor(_ledger_singleton),
)
