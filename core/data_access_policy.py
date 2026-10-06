"""Central personal-data access policy (Privacy Foundation, PRIV-FCC-01).

ONE place that decides which Airtable records an actor may see or change when
the table holds personal/sensitive data. It extends the existing access layer
(``tools/airtable_security.enforce_tenant_scope`` is the generic-tool hook; the
TMA routes and ``tools/approval_actions.tma_write`` call the same functions) —
there is deliberately no per-table ``if table == ...`` anywhere else.

Principle: **business role != personal authorization.** ``owner`` / ``partner``
/ ``manager`` / ``employee`` get no automatic right to another person's
personal records. Everyone — including the business owner — sees a record of a
policy table only when their own Profile record is in its ``Owner`` link
("owner-of-record").

Fail closed:
  * identity missing / external / not resolvable to EXACTLY ONE Profile row
    (see ``core.owner_resolution``) -> no access to owner-scoped tables;
  * owner-scoped record with no Owner link -> nobody sees it (``ownerless``
    policy ``deny``) until an owner is assigned;
  * raw Airtable table ids (``tbl...``) on a generic path -> denied, because a
    table id would bypass every name-based rule here.

Adding a table (e.g. the future Financial Control Center tables) = one entry
in ``_POLICIES``; no access-layer rewrite.

Pure policy: no Airtable writes. The only I/O is the injected-free Profile
resolution and, for record-level update checks, one record read.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from airtable_schema import TABLE_ALIASES, FinGoalFields, Tables, TaskFields
from core import owner_resolution

logger = logging.getLogger(__name__)

OWNER_SCOPED = "owner_scoped"      # visible ONLY to the owner-of-record
RECORD_MARKER = "record_marker"    # visible per existing rules unless marked private
SYSTEM_INTERNAL = "system_internal"  # internal system state (e.g. Sessions): no generic-tool access for ANY role

OWNERLESS_DENY = "deny"


class PersonalDataAccessDenied(PermissionError):
    """Actor may not read/change this personal record. Always fail-closed."""


DENIED_MESSAGE = "❌ גישה נחסמה: נתונים אישיים זמינים רק לבעל הרשומה."
UNRESOLVED_MESSAGE = "❌ גישה נחסמה: לא ניתן לאמת את זהותך מול רשומה אישית."
SYSTEM_STATE_MESSAGE = "❌ גישה נחסמה: זה מצב פנימי של המערכת ואינו זמין דרך כלי הנתונים."
RAW_TABLE_ID_MESSAGE = "❌ גישה נחסמה: יש לפנות לטבלה לפי שם, לא לפי מזהה."


@dataclass(frozen=True)
class TablePolicy:
    table: str                              # canonical Airtable table name
    mode: str                               # OWNER_SCOPED | RECORD_MARKER
    owner_field: str = "Owner"              # multipleRecordLinks -> Profile
    ownerless: str = OWNERLESS_DENY         # OWNER_SCOPED only
    private_marker: tuple[str, str] | None = None   # RECORD_MARKER only: (field, value)
    # (link field, target table): a record may only link to rows the actor owns
    # (cross-owner link guard, checked on create and on update).
    linked_owner_checks: tuple[tuple[str, str], ...] = ()


# Proposed (NOT yet in the live schema): Tasks."Visibility" = "Private". The
# marker is read-only code support — reading a field that does not exist yields
# None, so nothing is hidden until the field is added live (owner decision).
TASK_PRIVATE_MARKER = ("Visibility", "Private")

_POLICIES: dict[str, TablePolicy] = {
    "Assets":     TablePolicy("Assets", OWNER_SCOPED),
    Tables.LOANS: TablePolicy(Tables.LOANS, OWNER_SCOPED),
    # FCC tables: owner-of-record only; role (even business owner) grants nothing.
    Tables.FIN_GOALS:  TablePolicy(Tables.FIN_GOALS, OWNER_SCOPED, owner_field=FinGoalFields.FINANCIAL_OWNER),
    Tables.FIN_EVENTS: TablePolicy(
        Tables.FIN_EVENTS, OWNER_SCOPED, owner_field=FinGoalFields.FINANCIAL_OWNER,
        linked_owner_checks=(("Goal", Tables.FIN_GOALS),),
    ),
    # Sessions hold per-person working state (lead-qualifier answers, BusinessDraft incl. FCC financial
    # drafts). Only session_store (its own sanctioned internal I/O) may touch them — never a generic
    # agent/TMA tool, whatever the caller's role. The Sender-ID key is NOT an access policy.
    Tables.SESSIONS: TablePolicy(Tables.SESSIONS, SYSTEM_INTERNAL),
    Tables.LEAD_SESSIONS: TablePolicy(Tables.LEAD_SESSIONS, SYSTEM_INTERNAL),
    Tables.TASKS: TablePolicy(
        Tables.TASKS, RECORD_MARKER, owner_field=TaskFields.OWNER,
        private_marker=TASK_PRIVATE_MARKER,
    ),
}

_RAW_TABLE_ID_RE = re.compile(r"^tbl[A-Za-z0-9]{14}$")
_BY_FOLD = {name.casefold(): policy for name, policy in _POLICIES.items()}


# ══════════════════════════════════════════════════
# Table lookup
# ══════════════════════════════════════════════════

def is_raw_table_id(table: object) -> bool:
    return isinstance(table, str) and bool(_RAW_TABLE_ID_RE.match(table.strip()))


def policy_for(table: object) -> TablePolicy | None:
    """Policy for a table name or alias (case/whitespace-insensitive), else None."""
    if not isinstance(table, str) or not table.strip():
        return None
    name = table.strip()
    name = TABLE_ALIASES.get(name, name)
    return _BY_FOLD.get(name.casefold())


def is_owner_scoped(table: object) -> bool:
    policy = policy_for(table)
    return policy is not None and policy.mode == OWNER_SCOPED


def is_system_internal(table: object) -> bool:
    policy = policy_for(table)
    return policy is not None and policy.mode == SYSTEM_INTERNAL


def needs_record_filter(table: object) -> bool:
    """True when read results for this table must pass ``filter_records``."""
    return policy_for(table) is not None


# ══════════════════════════════════════════════════
# Actor resolution
# ══════════════════════════════════════════════════

@dataclass(frozen=True)
class ActorScope:
    profile_id: str | None
    reason: str

    @property
    def resolved(self) -> bool:
        return bool(self.profile_id)


def resolve_actor(identity) -> ActorScope:
    """Identity -> unique Profile record, or an unresolved scope (never a guess)."""
    if identity is None:
        return ActorScope(None, "no_identity")
    if getattr(identity, "is_external", False):
        return ActorScope(None, "external_identity")
    user_id = getattr(identity, "user_id", "")
    profile_id, reason = owner_resolution.resolve_profile_record_strict(user_id)
    return ActorScope(profile_id, reason)


def owner_refs(fields: dict | None, owner_field: str) -> tuple[str, ...]:
    value = (fields or {}).get(owner_field)
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(v for v in value if isinstance(v, str) and v)


def _is_private(policy: TablePolicy, fields: dict | None) -> bool:
    if not policy.private_marker:
        return False
    field, value = policy.private_marker
    raw = (fields or {}).get(field)
    if isinstance(raw, dict):           # singleSelect object form
        raw = raw.get("name")
    return isinstance(raw, str) and raw.strip().casefold() == value.casefold()


# ══════════════════════════════════════════════════
# Record visibility
# ══════════════════════════════════════════════════

def record_visible(table: object, fields: dict | None, actor: ActorScope) -> bool:
    policy = policy_for(table)
    if policy is None:
        return True
    if policy.mode == SYSTEM_INTERNAL:
        return False                    # never visible through a data tool, for any actor
    refs = owner_refs(fields, policy.owner_field)
    owner_of_record = actor.resolved and actor.profile_id in refs
    if policy.mode == OWNER_SCOPED:
        return owner_of_record          # ownerless -> False (fail closed)
    # RECORD_MARKER
    if _is_private(policy, fields):
        return owner_of_record          # private + ownerless -> nobody
    return True


def filter_records(table: object, records: list[dict], identity) -> list[dict]:
    """Keep only records the identity may see. Aggregate ONLY over the result."""
    policy = policy_for(table)
    if policy is None:
        return list(records)
    if policy.mode == SYSTEM_INTERNAL:
        return []
    if policy.mode == RECORD_MARKER and not any(
        _is_private(policy, (r or {}).get("fields")) for r in records
    ):
        return list(records)             # nothing private: no identity lookup needed
    actor = resolve_actor(identity)
    if policy.mode == OWNER_SCOPED and not actor.resolved:
        logger.warning("[data_access_policy] read denied table=%s reason=%s", policy.table, actor.reason)
        raise PersonalDataAccessDenied(UNRESOLVED_MESSAGE)
    return [r for r in records if record_visible(table, (r or {}).get("fields"), actor)]


def authorize_record(table: object, fields: dict | None, identity) -> None:
    """Raise unless the identity may access this single record."""
    policy = policy_for(table)
    if policy is None:
        return
    if policy.mode == SYSTEM_INTERNAL:
        raise PersonalDataAccessDenied(SYSTEM_STATE_MESSAGE)
    actor = resolve_actor(identity)
    if policy.mode == OWNER_SCOPED and not actor.resolved:
        raise PersonalDataAccessDenied(UNRESOLVED_MESSAGE)
    if not record_visible(table, fields, actor):
        raise PersonalDataAccessDenied(DENIED_MESSAGE)


def scope_new_record_fields(table: object, fields: dict, identity) -> dict:
    """Owner-stamp a new record for a policy table; refuse another person's Owner."""
    policy = policy_for(table)
    if policy is None:
        return fields
    if policy.mode == SYSTEM_INTERNAL:
        raise PersonalDataAccessDenied(SYSTEM_STATE_MESSAGE)
    actor = resolve_actor(identity)
    wants_scope = policy.mode == OWNER_SCOPED or _is_private(policy, fields)
    if not wants_scope:
        return fields
    if not actor.resolved:
        raise PersonalDataAccessDenied(UNRESOLVED_MESSAGE)
    refs = owner_refs(fields, policy.owner_field)
    if refs and set(refs) != {actor.profile_id}:
        raise PersonalDataAccessDenied(DENIED_MESSAGE)
    _check_linked_owners(policy, fields, actor)
    scoped = dict(fields)
    scoped[policy.owner_field] = [actor.profile_id]
    return scoped


def _check_linked_owners(policy: TablePolicy, fields: dict | None, actor: ActorScope) -> None:
    for link_field, target in policy.linked_owner_checks:
        ids = (fields or {}).get(link_field)
        if isinstance(ids, str):
            ids = [ids]
        for rid in ids or []:
            if not isinstance(rid, str) or not rid.startswith("rec"):
                raise PersonalDataAccessDenied(DENIED_MESSAGE)
            from tools.airtable_read_adapter import get_record_fields
            try:
                linked = get_record_fields(target, rid)
            except Exception as exc:
                raise PersonalDataAccessDenied(UNRESOLVED_MESSAGE) from exc
            if not record_visible(target, linked, actor):
                raise PersonalDataAccessDenied(DENIED_MESSAGE)


# ══════════════════════════════════════════════════
# Generic-tool hook (called from airtable_security.enforce_tenant_scope)
# ══════════════════════════════════════════════════

def enforce_table_access(tool_name: str, identity, params: dict) -> None:
    """Pre-flight for generic agent tools (airtable_get/add/update).

    * raw ``tbl...`` ids -> denied (would bypass name-based policy);
    * owner-scoped table -> actor must resolve to exactly one Profile;
    * update with record_id on a policy table -> the existing record must be
      visible to the actor (read once; read failure -> deny).
    Read results are additionally narrowed by ``filter_records`` in the caller.
    """
    table = params.get("table")
    if is_raw_table_id(table):
        raise PersonalDataAccessDenied(RAW_TABLE_ID_MESSAGE)
    policy = policy_for(table)
    if policy is None:
        return
    if policy.mode == SYSTEM_INTERNAL:
        logger.warning("[data_access_policy] %s denied on system table=%s", tool_name, policy.table)
        raise PersonalDataAccessDenied(SYSTEM_STATE_MESSAGE)
    record_id = params.get("record_id")
    needs_record_check = tool_name == "airtable_update" and bool(record_id)
    if policy.mode == RECORD_MARKER and not needs_record_check:
        return                           # reads are narrowed by filter_records; creates by scope_new_record_fields
    actor = None
    if policy.mode == OWNER_SCOPED:
        actor = resolve_actor(identity)
        if not actor.resolved:
            logger.warning(
                "[data_access_policy] %s denied table=%s reason=%s", tool_name, policy.table, actor.reason,
            )
            raise PersonalDataAccessDenied(UNRESOLVED_MESSAGE)
    if policy.linked_owner_checks and tool_name in ("airtable_add", "airtable_update"):
        _check_linked_owners(policy, params.get("fields"), actor or resolve_actor(identity))
    if needs_record_check:
        from tools.airtable_read_adapter import get_record_fields
        try:
            existing = get_record_fields(policy.table, record_id)
        except Exception as exc:
            logger.warning("[data_access_policy] record read failed table=%s: %s", policy.table, exc)
            raise PersonalDataAccessDenied(UNRESOLVED_MESSAGE) from exc
        if policy.mode == RECORD_MARKER and not _is_private(policy, existing):
            return                       # business task: existing rules apply, no identity lookup
        actor = actor or resolve_actor(identity)
        if not record_visible(policy.table, existing, actor):
            raise PersonalDataAccessDenied(DENIED_MESSAGE)


# ══════════════════════════════════════════════════
# Ownerless business Tasks (existing behavior, now explicit + fail-closed)
# ══════════════════════════════════════════════════

def ownerless_task_claimable(identity) -> bool:
    """Ownerless business Tasks go to the requester only while they are the
    SOLE business owner in the identity registry (today's single-owner
    reality, preserved). A second owner-role user flips this to False — no
    silent fan-out of unassigned tasks to every owner."""
    from identity import business_owner_user_ids
    if identity is None or not getattr(identity, "is_owner", False):
        return False
    owners = {u.casefold() for u in business_owner_user_ids()}
    return owners == {str(getattr(identity, "user_id", "")).casefold()}


def task_in_actor_queue(fields: dict | None, actor: ActorScope, *, claim_ownerless: bool) -> bool:
    """My-Work/PATCH rule: explicit Owner link must include the actor; an
    ownerless task is served only if business (not private) and claimable."""
    policy = _POLICIES[Tables.TASKS]
    refs = owner_refs(fields, policy.owner_field)
    if refs:
        return actor.resolved and actor.profile_id in refs
    if _is_private(policy, fields):
        return False
    return bool(claim_ownerless)
