# contacts/ranking.py
from datetime import date, datetime
import logging
logger = logging.getLogger(__name__)

STAGE_SCORES = {"negotiation":3,"proposal":2,"contacted":1,"lead":0,"won":-1,"lost":-2}

def rank_candidates(candidates: list[dict]) -> list[dict]:
    for c in candidates:
        c["rank_score"] = c.get("score", 0) + _ctx_score(c["fields"])
    candidates.sort(key=lambda x: x["rank_score"], reverse=True)
    return candidates

def _ctx_score(fields: dict) -> float:
    score = 0.0
    last = fields.get("Last Contact","")
    if last:
        try:
            days = (date.today() - datetime.fromisoformat(last).date()).days
            if days <= 7:    score += 3
            elif days <= 30: score += 1
        except: pass
    score += STAGE_SCORES.get(fields.get("Stage","").lower(), 0)
    return score
