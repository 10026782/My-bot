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

logger = logging.getLogger(__name__)


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

    def __init__(self, airtable_writer: Callable | None = None):
        self._store: dict[str, ActionContract] = {}    # contract_id → contract
        self._by_fingerprint: dict[str, str] = {}      # fingerprint → contract_id
        self._lock = threading.Lock()
        self._airtable_writer = airtable_writer        # callable(contract) → None

    def save(self, contract: ActionContract) -> None:
        with self._lock:
            self._store[contract.contract_id] = contract
            self._by_fingerprint[contract.business_action_fingerprint] = contract.contract_id
        if self._airtable_writer:
            try:
                self._airtable_writer(contract)
            except Exception as exc:
                logger.warning("[ActionGateway] Airtable write failed (RAM intact): %s", exc)

    def find_by_id(self, contract_id: str) -> ActionContract | None:
        return self._store.get(contract_id)

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
    ) -> GatewayResult:
        """
        מציע פעולה חדשה ל-Gateway.
        מחזיר GatewayResult(ok=True, contract_id=...) אם מותרת.
        מחזיר GatewayResult(ok=False, ...) אם נחסמת (כפילות/pending).

        identity: BUG-C89-APPROVAL-IDENTITY — אם מועבר, ה-Identity שנפתרה
        בפועל (role/external_id/...) נשמרת על ה-contract עצמו, כדי שביצוע
        לאחר אישור ישתמש בזהות המקורית ולא ינסה resolve_identity() מחדש על
        canonical_user_id/origin_chat_id (שיכולים להיות memory_key, לא
        external_id ערוץ אמיתי).
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

    # ── §4 — route_confirmation_word ────────────────────────────────

    def route_confirmation_word(self, canonical_user_id: str) -> str:
        """
        מיירט מילת אישור חופשית (כמו "מאשר") לפני שמגיעה ל-Agent.
        מחזיר תשובה ישירה למשתמש.
        """
        live = self.find_live_contracts(canonical_user_id)
        if len(live) == 0:
            return "אין פעולה שממתינה לאישור."
        if len(live) == 1:
            result = self.approve(live[0].contract_id, approver=canonical_user_id)
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

    @classmethod
    def _parse_ordinal(cls, text: str) -> int | None:
        """מחזיר אינדקס 1-based אם הטקסט הוא סדרתי; אחרת None."""
        t = text.strip().lower()
        # digit shorthand: "1", "2", ...
        if t.isdigit():
            return int(t)
        return cls._ORDINALS_HE.get(t)

    def route_disambiguation(self, canonical_user_id: str, text: str) -> str | None:
        """
        מיירט בחירת סדרתי ("הראשונה", "2", ...) אחרי שה-Gateway הציג רשימה.
        מחזיר None אם המשתמש אינו במצב disambiguation — ממשיך ל-Agent.
        מחזיר תשובה ישירה אם הבחירה חוקית.
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
        return self.approve(contract.contract_id, approver=canonical_user_id)

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

    def approve(self, contract_id: str, approver: str) -> str:
        """
        מאשר contract ומבצע אותו.
        Fail closed: אם _tool_executor חסר — לא מחזיר success, לא מסמן executed.
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

        if contract.canonical_user_id != approver and not approver.startswith("owner"):
            logger.warning(
                "[ActionGateway] approve: approver mismatch contract=%s approver=%s owner=%s",
                contract_id, approver, contract.canonical_user_id,
            )
        self._ledger.update_status(
            contract_id, "approved",
            approved_by=approver,
            approved_at=time.time(),
        )
        logger.info(
            "[ActionGateway] approved: contract=%s fingerprint=%.12s tool=%s "
            "payload_keys=%s by=%s",
            contract_id,
            contract.business_action_fingerprint,
            contract.tool_name,
            list(contract.normalized_payload.keys()),
            approver,
        )
        return self._execute_contract(contract)

    def _execute_contract(self, contract: ActionContract) -> str:
        """
        מבצע tool לאחר אישור — approved_payload == executed_payload (DoD §6).
        מריץ verify_execution על התוצאה — success claims require real tool evidence (DoD §3, §6).
        """
        self._ledger.update_status(contract.contract_id, "executing")
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
            rid = f" | מזהה: `{fact.record_id}`" if fact.record_id else ""
            text = f"✅ בוצע: {fact.tool_name}{rid}"
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
    כאשר Airtable לא מוגדר/לא מחובר, מחזיר None (RAM-only).
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
    except Exception:
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

        return dispatch_tool(tool_name, tool_inputs, identity=identity)

    return _executor


_ledger_singleton = ExecutionLedger(airtable_writer=None)  # RAM-only until Airtable table exists
action_gateway = ActionGateway(
    ledger=_ledger_singleton,
    tool_executor=_make_dispatch_executor(_ledger_singleton),
)
