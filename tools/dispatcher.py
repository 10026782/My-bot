def dispatch_tool(name: str, inputs: dict, tenant_id: str = "boss_hq"):
    match name:
        case "add_knowledge":
            from knowledge_engine import knowledge_engine
            ok = knowledge_engine.add_fact(tenant_id, inputs["fact"])
            return "✅ עובדה נוספה" if ok else "❌ שגיאה"
        case "get_roi_report":
            from marketing_tracker import get_roi_report
            return get_roi_report(tenant_id)
        case _:
            return "❌ כלי לא מוכר"
