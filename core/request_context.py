# core/request_context.py — CXX: Per-Request Context Cache
#
# פותר: Sessions נקרא 4 פעמים לbodאמה אחת, domain drift, double identity lookup.
#
# עיקרון: Identity / Lead / Session / Domain נפתרים פעם אחת ב-run_agent.
# כל שכבה פנימית מקבלת את RequestContext ולא קוראת resolve_identity / airtable_get מחדש.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from identity import Identity


@dataclass
class RequestContext:
    """
    Context אחיד לrequest יחיד.

    נוצר ב-run_agent, מועבר ל:
      - _build_tool_context
      - resolve_context_pronouns
      - _capture_last_tool_result
      - capture_inbound_lead (לא קורא resolve_identity שוב)
      - _gateway_whatsapp_reply (מקבל final_domain)

    חוק ברזל: כל module שמקבל RequestContext לא קורא:
      - resolve_identity()
      - airtable_get(Sessions, ...)
      בנפרד — הנתונים כבר כאן.
    """

    # Identity — נפתר פעם אחת
    identity:           "Identity"
    memory_key:         str           # canonical: boss_hq:+972... (לעולם לא whatsapp:+972...)
    role:               str
    channel:            str

    # Domain — נפתר ע"י Router, לא נחשב מחדש
    # מתחיל מ-domain_from_channel, מתעדכן אחרי Router רץ
    domain:             str = "general"

    # Lead — נטען פעם אחת (ריק אם לא ליד)
    lead_record_id:     str = ""

    # Session — נטען פעם אחת
    session:            dict = field(default_factory=dict)
    session_record_id:  str = ""
    session_loaded:     bool = False   # True = כבר נטען מ-Airtable (לא לטעון שוב)

    # Delivery
    adapter_mode:       str = "unknown"   # "live" | "stub"

    # ── helpers ────────────────────────────────────

    @property
    def is_lead(self) -> bool:
        from identity import Role
        return self.role == Role.LEAD

    @property
    def is_owner(self) -> bool:
        from identity import Role
        return self.role == Role.OWNER

    @classmethod
    def from_identity(cls, identity: "Identity", domain: str = "general") -> "RequestContext":
        """בנה RequestContext מ-Identity לאחר resolve."""
        return cls(
            identity   = identity,
            memory_key = identity.memory_key,   # canonical — boss_hq:+972...
            role       = identity.role,
            channel    = identity.channel,
            domain     = domain,
        )

    def update_domain(self, domain: str) -> None:
        """מעדכן domain לאחר Router רץ — קורא פעם אחת בלבד מ-run_agent."""
        if domain and domain != self.domain:
            self.domain = domain
            # עדכן גם ב-identity כדי ש-build_context יראה את הdomain הנכון
            self.identity.domain_id = domain

    def mark_session_loaded(self, session: dict, record_id: str = "") -> None:
        """סמן session כנטעון — מונע קריאה חוזרת."""
        self.session         = session
        self.session_record_id = record_id
        self.session_loaded  = True

    def __repr__(self) -> str:
        return (
            f"RequestContext(role={self.role} domain={self.domain} "
            f"channel={self.channel} key={self.memory_key})"
        )
