from business_tool_registry import find_recommended_tools, list_tools, maybe_recommend


def test_task_matching_returns_canonical_approved_tools():
    assert find_recommended_tools("אני צריך לאחד כמה קבצי PDF")[0].tool_id == "bentopdf"
    assert find_recommended_tools("יש לי קובץ CSV שלא נפתח טוב")[0].tool_id == "csv-repair"
    assert maybe_recommend("יש לי CSV שבור") and "csv.repair" in maybe_recommend("יש לי CSV שבור")
    assert find_recommended_tools("אני צריך להקטין תמונה לפני שליחה")[0].tool_id == "squoosh"
    assert maybe_recommend("תקטין לי תמונה לוואטסאפ") and "Squoosh" in maybe_recommend("תקטין לי תמונה לוואטסאפ")
    assert maybe_recommend("הקובץ CSV לא נפתח באקסל") and "csv.repair" in maybe_recommend("הקובץ CSV לא נפתח באקסל")
    assert find_recommended_tools("צריך לכווץ לוגו SVG")[0].tool_id == "svgomg"
    assert find_recommended_tools("אני רוצה לשאול שאלה על CSV")[0].tool_id == "sql-for-files"
    assert find_recommended_tools("צריך לנקות לוג לפני שליחה")[0].tool_id == "shareclean"
    assert find_recommended_tools("אני רוצה ליצור גרף מהנתונים")[0].tool_id == "rawgraphs"
    assert find_recommended_tools("יש לי JSON מסובך שאני רוצה להבין")[0].tool_id == "json-crack"


def test_restricted_is_explicit_and_infrastructure_is_not_business_result():
    tools = find_recommended_tools("יש לי JSON מסובך")
    assert tools[0].verification_status == "approved_with_restrictions"
    assert all(tool.tool_class == "business" for tool in tools)
    assert any(tool.tool_class == "infrastructure_candidate" for tool in list_tools(tool_class="infrastructure_candidate"))
    assert find_recommended_tools("monitor endpoint") == []


def test_unknown_and_normal_conversation_do_not_get_invented_or_interrupted():
    assert find_recommended_tools("אני צריך מערכת לניהול עובדים") == []
    assert maybe_recommend("שלום, מה נשמע?") is None
    assert "BentoPDF" in maybe_recommend("איזה כלים עסקיים יש לי?")


if __name__ == "__main__":
    test_task_matching_returns_canonical_approved_tools()
    test_restricted_is_explicit_and_infrastructure_is_not_business_result()
    test_unknown_and_normal_conversation_do_not_get_invented_or_interrupted()
