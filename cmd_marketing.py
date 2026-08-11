# cmd_marketing.py — F23 BOSS Marketing Bridge (M1)
# /marketing_brief <Demand Record ID>   — compose brief, call AI once for 3 ideas, save
# /marketing_handoff <Creative Record ID> — compose Production Handoff for the selected idea
# Feature flag: FEATURE_MARKETING_BRIDGE (default OFF)
#
# M1 scope only. Per the M1 spec's Canonical Reuse Gate: this is a direct,
# human-command-triggered handler (same shape as cmd_update.py/cmd_decision.py)
# — not an agent-invoked dispatcher tool, no tool_registry/ActionGateway
# involvement, because the human typing the command IS the authorization,
# same as /update. Demand creation, creative review/selection, and
# publication recording all happen via direct Airtable data entry for M1 —
# a full conversational wizard and query commands (list demands, next
# action, etc.) are explicitly M2 scope and not built here.

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_ALLOWED_ROLES = ("owner", "manager", "partner")


# ── Registration ─────────────────────────────────────────────────

def register_marketing_command(bot, get_identity):
    """נקרא מ-app.py פעם אחת ב-startup."""
    try:
        from feature_flags import is_enabled
        if not is_enabled("FEATURE_MARKETING_BRIDGE"):
            logger.info("[F23] FEATURE_MARKETING_BRIDGE=off — /marketing_brief not registered")
            return
    except ImportError:
        pass  # dev mode

    @bot.message_handler(commands=["marketing_brief"])
    def cmd_marketing_brief(msg):
        identity = _authorized(bot, msg, get_identity)
        if not identity:
            return
        demand_id = _parse_arg(msg)
        if not demand_id:
            bot.send_message(msg.chat.id, "שימוש: /marketing_brief <Demand Record ID>")
            return
        result = generate_ideas_for_demand(demand_id, triggered_by=f"telegram:{identity.user_id}")
        bot.send_message(msg.chat.id, _format_ideas_result(result), parse_mode="Markdown")

    @bot.message_handler(commands=["marketing_handoff"])
    def cmd_marketing_handoff(msg):
        identity = _authorized(bot, msg, get_identity)
        if not identity:
            return
        creative_id = _parse_arg(msg)
        if not creative_id:
            bot.send_message(msg.chat.id, "שימוש: /marketing_handoff <Creative Record ID>")
            return
        result = generate_handoff_for_creative(creative_id)
        bot.send_message(msg.chat.id, _format_handoff_result(result), parse_mode="Markdown")

    logger.info("[F23] /marketing_brief, /marketing_handoff registered successfully")


def _authorized(bot, msg, get_identity):
    try:
        identity = get_identity("telegram", str(msg.from_user.id))
    except Exception as e:
        logger.error(f"[F23] identity error: {e}", exc_info=True)
        bot.send_message(msg.chat.id, "❌ שגיאה בזיהוי משתמש.")
        return None
    if not identity or not (identity.is_owner or identity.role in _ALLOWED_ROLES):
        bot.send_message(msg.chat.id, "אין הרשאה לפקודה זו.")
        return None
    return identity


def _parse_arg(msg) -> str:
    parts = (getattr(msg, "text", "") or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _format_ideas_result(result: dict) -> str:
    if not result["ok"]:
        return f"❌ {result['error']}"
    lines = [f"✅ נשמרו 3 רעיונות — creative_id: `{result['creative_id']}`", ""]
    for i, idea in enumerate(result["ideas"], start=1):
        lines.append(f"*רעיון {i}:*\n{idea}\n")
    lines.append("בחר רעיון ישירות ב-Airtable (שדה Selected Idea), ואז /marketing_handoff <creative_id>.")
    return "\n".join(lines)


def _format_handoff_result(result: dict) -> str:
    if not result["ok"]:
        return f"❌ {result['error']}"
    return f"✅ *Production Handoff נשמר:*\n\n{result['handoff']}"


# ── Core logic — importable/testable without a bot instance ─────────

def _parse_three_ideas(raw: str) -> list[str]:
    parts = re.split(r"רעיון\s*\d\s*:", raw)
    return [p.strip() for p in parts if p.strip()][:3]


def generate_ideas_for_demand(demand_id: str, triggered_by: str = "unknown") -> dict:
    """
    Returns {"ok": True, "creative_id": ..., "ideas": [str, str, str]} or
    {"ok": False, "error": str}. One AI call for all 3 ideas (not the Agent
    tool-use loop — see the M1 spec's point on minimizing LLM calls).
    """
    import marketing_gateway
    from airtable_schema import MarketingDemandFields as MDF
    from llm_fallback import call_anthropic_text
    from marketing_brief_composer import compose_brief

    demand = marketing_gateway.get_demand(demand_id)
    if not demand:
        return {"ok": False, "error": f"Demand {demand_id} not found"}

    domain_rules = marketing_gateway.get_marketing_rules(demand.get(MDF.DOMAIN, "general"))

    try:
        brief = compose_brief(demand=demand, task_type="creative_ideas", domain_rules=domain_rules)
    except Exception as e:
        return {"ok": False, "error": f"brief composition failed: {e}"}

    instruction = (
        brief
        + "\n\nהחזר בדיוק בפורמט הבא, ללא טקסט נוסף:\n"
          "רעיון 1:\n<טקסט>\n\nרעיון 2:\n<טקסט>\n\nרעיון 3:\n<טקסט>"
    )

    try:
        raw = call_anthropic_text(
            source="cmd_marketing.generate_ideas_for_demand",
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system="אתה עוזר קריאייטיב שיווקי. החזר תשובה בפורמט המדויק המבוקש בלבד.",
            messages=[{"role": "user", "content": instruction}],
        )
    except Exception as e:
        return {"ok": False, "error": f"AI call failed: {e}"}

    ideas = _parse_three_ideas(raw)
    if len(ideas) != 3:
        return {"ok": False, "error": f"could not parse 3 ideas from AI response (got {len(ideas)})"}

    creative_id = marketing_gateway.save_creative_ideas(
        demand_id=demand_id,
        title=f"{demand.get(MDF.NAME, demand_id)} — creatives",
        idea1=ideas[0], idea2=ideas[1], idea3=ideas[2],
        brief_used=brief,
    )
    if not creative_id:
        return {"ok": False, "error": "save_creative_ideas failed"}

    logger.info("[F23] ideas saved creative_id=%s demand_id=%s by=%s", creative_id, demand_id, triggered_by)
    return {"ok": True, "creative_id": creative_id, "ideas": ideas}


def generate_handoff_for_creative(creative_id: str) -> dict:
    """Returns {"ok": True, "handoff": str} or {"ok": False, "error": str}."""
    import marketing_gateway
    from airtable_schema import MarketingCreativesFields as MCF, MarketingDemandFields as MDF, MarketingDemandStage
    from marketing_brief_composer import compose_production_handoff

    creative = marketing_gateway.get_creative(creative_id)
    if not creative:
        return {"ok": False, "error": f"Creative {creative_id} not found"}

    selected = creative.get(MCF.SELECTED_IDEA)
    if not selected or selected == "None":
        return {"ok": False, "error": "no idea selected yet — set Selected Idea in Airtable first"}

    idea_field = {"Idea 1": MCF.IDEA_1, "Idea 2": MCF.IDEA_2, "Idea 3": MCF.IDEA_3}.get(selected)
    selected_text = creative.get(idea_field, "") if idea_field else ""
    if not selected_text:
        return {"ok": False, "error": f"selected idea field '{selected}' is empty"}

    demand_ids = creative.get(MCF.LINKED_DEMAND) or []
    if not demand_ids:
        return {"ok": False, "error": "creative has no Linked Demand"}

    demand = marketing_gateway.get_demand(demand_ids[0])
    if not demand:
        return {"ok": False, "error": f"linked Demand {demand_ids[0]} not found"}

    domain_rules = marketing_gateway.get_marketing_rules(demand.get(MDF.DOMAIN, "general"))

    try:
        handoff = compose_production_handoff(
            demand=demand, selected_creative=selected_text, domain_rules=domain_rules,
        )
    except Exception as e:
        return {"ok": False, "error": f"handoff composition failed: {e}"}

    if not marketing_gateway.save_production_handoff(creative_id, handoff):
        return {"ok": False, "error": "save_production_handoff failed"}

    marketing_gateway.update_demand_stage(demand_ids[0], MarketingDemandStage.HANDOFF_SENT)

    logger.info("[F23] handoff saved creative_id=%s demand_id=%s", creative_id, demand_ids[0])
    return {"ok": True, "handoff": handoff}


if __name__ == "__main__":
    sample = (
        "רעיון 1:\nמודעה קצרה וישירה.\n\n"
        "רעיון 2:\nמודעה עם דגש על תנאים.\n\n"
        "רעיון 3:\nמודעה עם קריאה לפעולה דחופה."
    )
    ideas = _parse_three_ideas(sample)
    assert len(ideas) == 3, f"expected 3 ideas, got {len(ideas)}"
    assert ideas[0] == "מודעה קצרה וישירה."
    assert ideas[2] == "מודעה עם קריאה לפעולה דחופה."

    malformed = _parse_three_ideas("אין כאן שום דבר בפורמט הנכון")
    assert len(malformed) != 3

    print("cmd_marketing.py self-test OK")
