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


def test_shared_formatter_is_compact_and_telegram_ready():
    reply = maybe_recommend("אני צריך לאחד כמה מסמכי PDF")
    assert reply.splitlines()[:2] == ["יש לי כלי מתאים לזה:", ""]
    assert "[BentoPDF](https://bentopdf.com/)" in reply
    assert "מה הוא עושה" in reply and "איך משתמשים" in reply
    assert "מה זה עוזר" not in reply
    assert "ללא אישור" not in reply
    assert "איך להשתמש:" not in reply
    assert "1. " not in reply
    assert reply.count("https://bentopdf.com/") == 1


def test_no_agent_has_no_assistance_heading():
    reply = maybe_recommend("אני צריך להקטין תמונה")
    assert "עזרה נוספת" not in reply
    assert "Agent" not in reply and "AI" not in reply


def test_optional_agent_has_one_bounded_assistance_line():
    reply = maybe_recommend("אני רוצה ליצור גרף מהנתונים")
    assert reply.count("עזרה נוספת") == 1
    assert reply.count("אם תרצה") == 1


def test_direct_and_need_lookup_share_the_same_render_contract():
    need = maybe_recommend("אני צריך לאחד PDF")
    direct = maybe_recommend("איך משתמשים ב-BentoPDF?")
    assert need == direct


def test_every_approved_business_tool_renders_without_internal_wording():
    for tool in list_tools():
        reply = maybe_recommend(f"אני צריך {tool.name}")
        assert reply is not None, tool.tool_id
        assert f"[{tool.name}]({tool.url})" in reply
        assert "מה זה עוזר" not in reply
        assert "מקור אמת" not in reply
        assert "ללא אישור" not in reply


# ══════════════════════════════════════════════════
# BUG-051-FU (14/08/2026 manual QA): deterministic matching gap.
#
#   "אני צריך לדחוס תמונה"        -> Squoosh (already worked)
#   "יש כלי לדחיסת תמונה?"        -> Squoosh (FAILED before fix: construct-
#                                     noun form "לדחיסת" vs the catalog's
#                                     verb form "לדחוס" never matched)
#   "אני צריך ליצור תרשים מנתונים" -> RAWGraphs (FAILED before fix:
#                                     catalog phrase "תרשים מהנתונים" has
#                                     the definite article "ה", user text
#                                     doesn't)
#
# Fixed by (1) a generic, closed _DEF_ARTICLE_PREFIX_RE normalization that
# collapses "מה/לה/בה/וה/כה" + word to the bare preposition form (applied
# identically to catalog phrases and input), and (2) one added catalog
# phrase variant on squoosh ("לדחיסת תמונה"/"לדחיסת תמונות") for the
# genuinely different construct-noun inflection that (1) cannot bridge.
# ══════════════════════════════════════════════════

def test_bug051fu_squoosh_matches_construct_noun_phrasing():
    assert find_recommended_tools("יש כלי לדחיסת תמונה?")[0].tool_id == "squoosh"
    reply = maybe_recommend("יש כלי לדחיסת תמונה?")
    assert reply and "Squoosh" in reply


def test_bug051fu_squoosh_still_matches_verb_phrasing():
    # Pre-existing case — must not regress.
    assert find_recommended_tools("אני צריך לדחוס תמונה")[0].tool_id == "squoosh"


def test_bug051fu_rawgraphs_matches_definite_article_variant():
    assert find_recommended_tools("אני צריך ליצור תרשים מנתונים")[0].tool_id == "rawgraphs"
    reply = maybe_recommend("אני צריך ליצור תרשים מנתונים")
    assert reply and "RAWGraphs" in reply


def test_bug051fu_rawgraphs_still_matches_definite_article_form():
    # Pre-existing case ("גרף מהנתונים", WITH the definite article) — must
    # not regress after adding the ה-collapsing normalizer.
    assert find_recommended_tools("אני רוצה ליצור גרף מהנתונים")[0].tool_id == "rawgraphs"


def test_bug051fu_definite_article_normalization_does_not_widen_false_positives():
    # The ה-collapse must not turn unrelated sentences into matches, and
    # must not make the tool-seeking gate (maybe_recommend's intent_markers)
    # any broader than before.
    assert maybe_recommend("יש לי כלי עבודה חדש בעבודה") is None
    assert maybe_recommend("קניתי כלי נגינה") is None
    assert maybe_recommend("תרשים ארגוני של החברה") is None
    assert find_recommended_tools("מה שלומך היום") == []
