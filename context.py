from dataclasses import dataclass
from knowledge_engine import knowledge_engine


@dataclass
class Identity:
    tenant_id: str = "boss_hq"


def build_context(identity: Identity, user_text: str) -> str:
    system = knowledge_engine.build_context(identity.tenant_id, user_text)
    return system
