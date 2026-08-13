from business_tool_registry import find_recommended_tools, get_playbook, list_tools, maybe_recommend


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


def test_recommendation_is_a_deterministic_playbook_with_clean_link():
    reply = maybe_recommend("אני צריך לאחד כמה מסמכי PDF")
    assert "[BentoPDF](https://bentopdf.com/)" in reply
    assert "איך להשתמש:" in reply
    assert "לפתיחה:" not in reply
    assert "![](https://" not in reply


def test_direct_tool_lookup_uses_the_same_playbook_without_agent():
    playbook_tool = get_playbook("איך משתמשים ב-BentoPDF?")
    assert playbook_tool and playbook_tool.playbook.agent_mode == "no_agent"
    assert "איך להשתמש:" in (maybe_recommend("איך משתמשים ב-BentoPDF?") or "")


def test_optional_assist_is_offered_but_not_invoked():
    reply = maybe_recommend("יש לי CSV ואני לא יודע איזה גרף לעשות")
    assert reply and "RAWGraphs" in reply
    assert "אפשר לבקש ממני עזרה" in reply


def test_all_business_tools_have_playbooks_and_operator_tools_stay_hidden():
    tools = list_tools()
    assert tools and all(tool.playbook for tool in tools)
    assert not any(tool.tool_class != "business" for tool in tools)


def test_unknown_need_is_not_invented():
    assert maybe_recommend("אני צריך מערכת לניהול משמרות") is None


if __name__ == "__main__":
    test_task_matching_returns_canonical_approved_tools()
    test_restricted_is_explicit_and_infrastructure_is_not_business_result()
    test_unknown_and_normal_conversation_do_not_get_invented_or_interrupted()
