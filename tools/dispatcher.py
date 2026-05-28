def dispatch_tool(name: str, inputs: dict, tenant_id: str = "boss_hq"):
    match name:
        case "add_knowledge":
            from knowledge_engine import knowledge_engine
            ok = knowledge_engine.add_fact(tenant_id, inputs["fact"])
            return "✅ עובדה נוספה" if ok else "❌ שגיאה"
        case _:
            return "❌ כלי לא מוכר"
