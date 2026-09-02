from __future__ import annotations

from tools import audit_turn_coordinator_bypass as audit


# ══════════════════════════════════════════════════════════════════
# Guard 1 — route regression detection
# ══════════════════════════════════════════════════════════════════

_LIVE_GATE_SNIPPET = """
    if (
        intent == Intent.CREATE_DEAL
        and _create_deal_parse.certain
        and identity.role not in ("lead", "guest", "readonly")
    ):
        risk, handler, needs_approval = Risk.NEEDS_APPROVAL, Handler.TOOL, True

    elif intent == Intent.CREATE_DEAL and _create_deal_parse.uncertain:
        handler = Handler.CLARIFY
"""


def test_find_deterministic_tool_gates_detects_live_gate():
    gates = audit.find_deterministic_tool_gates(_LIVE_GATE_SNIPPET)
    assert "CREATE_DEAL" in gates
    assert "certain" in gates["CREATE_DEAL"]


def test_find_clarify_gates_detects_live_fallback():
    gates = audit.find_clarify_gates(_LIVE_GATE_SNIPPET)
    assert "CREATE_DEAL" in gates


def test_current_repo_has_no_route_regressions():
    """Runs against the real, current source — proves today's protected
    intents (CREATE_TASK/UPDATE_TASK/COMPLETE_TASK/CREATE_DEAL) are wired."""
    assert audit.check_route_regressions() == []


def test_deleted_tool_gate_is_a_regression():
    broken = _LIVE_GATE_SNIPPET.replace("intent == Intent.CREATE_DEAL", "False")
    gates = audit.find_deterministic_tool_gates(broken)
    assert "CREATE_DEAL" not in gates


def test_deleted_clarify_fallback_is_a_regression():
    broken = _LIVE_GATE_SNIPPET.replace(
        "elif intent == Intent.CREATE_DEAL and _create_deal_parse.uncertain:",
        "elif False:",
    )
    gates = audit.find_clarify_gates(broken)
    assert "CREATE_DEAL" not in gates


def test_check_route_regressions_flags_a_missing_gate(monkeypatch, tmp_path):
    router = tmp_path / "router.py"
    router.write_text("# no gates at all\n", encoding="utf-8")
    route_decision = tmp_path / "route_decision.py"
    route_decision.write_text("CREATE_DEAL = \"create_deal\"\n", encoding="utf-8")
    monkeypatch.setattr(audit, "ROUTER_PY", router)
    monkeypatch.setattr(audit, "ROUTE_DECISION_PY", route_decision)
    monkeypatch.setattr(audit, "_TC_PROTECTED_INTENTS", ("CREATE_DEAL",))
    failures = audit.check_route_regressions()
    assert any("no longer has a live Handler.TOOL" in f for f in failures)


# ══════════════════════════════════════════════════════════════════
# Guard 2 — new unrouted canonical create-tool
# ══════════════════════════════════════════════════════════════════

def test_scan_tool_registry_extracts_name_and_flags():
    source = (
        "ToolMeta(\n"
        "    name=\"crm_create_expense\",\n"
        "    roles_allowed=_MANAGEMENT,\n"
        "    requires_approval=True,\n"
        "    high_risk=True,\n"
        "    description_he=\"x\",\n"
        "),\n"
    )
    entries = audit.scan_tool_registry(source)
    assert len(entries) == 1
    assert entries[0].name == "crm_create_expense"
    assert entries[0].requires_approval is True
    assert entries[0].high_risk is True


def test_low_risk_tool_is_never_flagged(monkeypatch):
    source = (
        "ToolMeta(\n"
        "    name=\"crm_create_note\",\n"
        "    roles_allowed=_MANAGEMENT,\n"
        "    requires_approval=False,\n"
        "    high_risk=False,\n"
        "),\n"
    )
    monkeypatch.setattr(audit, "_read", lambda p: source if p == audit.TOOL_REGISTRY_PY else "")
    monkeypatch.setattr(audit, "_added_line_ranges", lambda spec: (
        {"tool_registry.py": {1, 2, 3, 4, 5, 6}} if spec == "tool_registry.py" else {}
    ))
    monkeypatch.setattr(audit, "_baseline_tool_names", lambda: set())
    assert audit.check_new_unrouted_tools() == []


def test_new_high_risk_create_tool_without_registration_blocks(monkeypatch):
    source = (
        "ToolMeta(\n"
        "    name=\"crm_create_expense\",\n"
        "    roles_allowed=_MANAGEMENT,\n"
        "    requires_approval=True,\n"
        "    high_risk=True,\n"
        "),\n"
    )
    monkeypatch.setattr(audit, "_read", lambda p: (
        source if p == audit.TOOL_REGISTRY_PY else ""
    ))
    monkeypatch.setattr(audit, "_added_line_ranges", lambda spec: (
        {"tool_registry.py": {1, 2, 3, 4, 5, 6}} if spec == "tool_registry.py" else {}
    ))
    monkeypatch.setattr(audit, "_baseline_tool_names", lambda: set())
    failures = audit.check_new_unrouted_tools()
    assert len(failures) == 1
    assert "crm_create_expense" in failures[0]
    assert "no Turn Coordinator route registration" in failures[0]


def test_pre_existing_tool_touched_by_an_unrelated_diff_is_not_flagged(monkeypatch):
    """A harmless line move/edit on an already-registered tool must not
    look like a brand-new unrouted tool (mirrors audit_writer_authority_
    registration.py's baseline-comparison safeguard)."""
    source = (
        "ToolMeta(\n"
        "    name=\"crm_create_deal\",\n"
        "    roles_allowed=_MANAGEMENT,\n"
        "    requires_approval=True,\n"
        "    high_risk=True,\n"
        "),\n"
    )
    monkeypatch.setattr(audit, "_read", lambda p: (
        source if p == audit.TOOL_REGISTRY_PY else ""
    ))
    monkeypatch.setattr(audit, "_added_line_ranges", lambda spec: (
        {"tool_registry.py": {1, 2, 3, 4, 5, 6}} if spec == "tool_registry.py" else {}
    ))
    monkeypatch.setattr(audit, "_baseline_tool_names", lambda: {"crm_create_deal"})
    assert audit.check_new_unrouted_tools() == []


def test_stale_routed_registration_is_flagged(monkeypatch):
    """A tool registered as ROUTED to an intent whose gate no longer
    exists must fail — the registration itself can go stale."""
    source = (
        "ToolMeta(\n"
        "    name=\"crm_create_deal\",\n"
        "    roles_allowed=_MANAGEMENT,\n"
        "    requires_approval=True,\n"
        "    high_risk=True,\n"
        "),\n"
    )
    monkeypatch.setattr(audit, "_read", lambda p: (
        source if p == audit.TOOL_REGISTRY_PY else "# no gates"
    ))
    monkeypatch.setattr(audit, "_added_line_ranges", lambda spec: (
        {"tool_registry.py": {1, 2, 3, 4, 5, 6}} if spec == "tool_registry.py" else {}
    ))
    monkeypatch.setattr(audit, "_baseline_tool_names", lambda: set())
    failures = audit.check_new_unrouted_tools()
    assert any("registration is stale" in f for f in failures)


def test_current_repo_registry_is_consistent():
    """The real _TC_ROUTE_REGISTRY's ROUTED entries must match a real,
    live gate in the current router.py — catches this file's own
    registry going stale independent of any diff."""
    router_source = audit._read(audit.ROUTER_PY)
    routed_intents = set(audit.find_deterministic_tool_gates(router_source))
    for tool_name, (kind, detail) in audit._TC_ROUTE_REGISTRY.items():
        if kind == "ROUTED":
            assert detail in routed_intents, (
                f"{tool_name} claims ROUTED to Intent.{detail}, but no live "
                f"Handler.TOOL gate exists for it"
            )


# ══════════════════════════════════════════════════════════════════
# Guard 3 — schema tool-description nudge language
# ══════════════════════════════════════════════════════════════════

def test_nudge_phrase_without_router_change_blocks(monkeypatch):
    monkeypatch.setattr(audit, "_added_line_ranges", lambda spec: (
        {"tools/schemas.py": {1}} if spec == "tools/schemas.py" else {}
    ))
    monkeypatch.setattr(audit, "_read", lambda p: (
        "לא להשתמש בכלי הזה ליצירת עסקה\n" if p == audit.SCHEMAS_PY else ""
    ))
    failures = audit.check_schema_nudge_language()
    assert len(failures) == 1
    assert "PR #1171 pattern" in failures[0]


def test_nudge_phrase_alongside_a_real_router_change_is_allowed(monkeypatch):
    monkeypatch.setattr(audit, "_added_line_ranges", lambda spec: (
        {"tools/schemas.py": {1}} if spec == "tools/schemas.py"
        else ({"core/router/router.py": {10}} if spec == "core/router/router.py" else {})
    ))
    monkeypatch.setattr(audit, "_read", lambda p: (
        "לא להשתמש בכלי הזה ליצירת עסקה\n" if p == audit.SCHEMAS_PY else ""
    ))
    assert audit.check_schema_nudge_language() == []


def test_no_schema_diff_is_a_silent_no_op(monkeypatch):
    monkeypatch.setattr(audit, "_added_line_ranges", lambda spec: {})
    assert audit.check_schema_nudge_language() == []


# ══════════════════════════════════════════════════════════════════
# Guard 5 — protected business tables must never reach a raw airtable_update
# ══════════════════════════════════════════════════════════════════

_LIVE_UPDATE_CASE_SNIPPET = '''
            case "airtable_update":
                table     = inputs["table"]
                record_id = inputs["record_id"]
                fields    = dict(inputs["fields"])

                try:
                    enforce_leads_write_gate("airtable_update", {"table": table}, source=_write_source)
                except LeadsDirectWriteBlocked as e:
                    return str(e)

                if _ALIAS_MAP.get(table, table) == "אנשי קשר (Contacts)":
                    result = crm.update_contact(record_id, fields, source="agent")
                elif _resolved_table in _CRM_TABLE_ROUTING:
                    result = airtable_update(_resolved_table, record_id, fields)
                elif _ALIAS_MAP.get(table, table) == Tables.TASKS:
                    _unsupported = set(fields) - _TASK_ALLOWED_UPDATE_FIELDS
                    result = airtable_update(Tables.TASKS, record_id, fields)
                else:
                    result = airtable_update(table, record_id, fields)
                return result

            case "airtable_get_schema":
                return airtable_get_schema()
'''


def test_current_repo_has_no_protected_business_table_regressions():
    """Runs against the real, current source — proves today's protections
    (Leads/Contacts/Deals/Payment Terms/Payments/Tasks) are all still wired."""
    assert audit.check_protected_business_table_raw_update() == []


def test_find_airtable_update_case_body_extracts_only_that_case():
    body = audit.find_airtable_update_case_body(_LIVE_UPDATE_CASE_SNIPPET)
    assert body is not None
    assert "enforce_leads_write_gate" in body
    assert "_CRM_TABLE_ROUTING" in body
    assert "_TASK_ALLOWED_UPDATE_FIELDS" in body
    assert "airtable_get_schema" not in body  # next case must not leak in


def test_missing_case_entirely_is_flagged(monkeypatch, tmp_path):
    dispatcher = tmp_path / "dispatcher.py"
    dispatcher.write_text("# no airtable_update case at all\n", encoding="utf-8")
    monkeypatch.setattr(audit, "DISPATCHER_PY", dispatcher)
    failures = audit.check_protected_business_table_raw_update()
    assert any('no longer has a `case "airtable_update":`' in f for f in failures)


def test_removed_protection_signature_is_flagged(monkeypatch, tmp_path):
    dispatcher = tmp_path / "dispatcher.py"
    # Contacts' redirect signature is missing entirely from this snippet
    # (every other protection, including Tasks, is present).
    dispatcher.write_text('''
            case "airtable_update":
                enforce_leads_write_gate("airtable_update", {"table": table}, source=_write_source)
                if _resolved_table in _CRM_TABLE_ROUTING:
                    result = airtable_update(_resolved_table, record_id, fields)
                elif _ALIAS_MAP.get(table, table) == Tables.TASKS:
                    _unsupported = set(fields) - _TASK_ALLOWED_UPDATE_FIELDS
                    result = airtable_update(Tables.TASKS, record_id, fields)
                else:
                    result = airtable_update(table, record_id, fields)
''', encoding="utf-8")
    monkeypatch.setattr(audit, "DISPATCHER_PY", dispatcher)
    failures = audit.check_protected_business_table_raw_update()
    assert any("אנשי קשר (Contacts)" in f for f in failures)
    assert not any("enforce_leads_write_gate" in f and "no longer contains" in f for f in failures)
    assert not any("_TASK_ALLOWED_UPDATE_FIELDS" in f for f in failures)


def test_removed_task_allowlist_signature_is_flagged(monkeypatch, tmp_path):
    dispatcher = tmp_path / "dispatcher.py"
    # Tasks' field allowlist is missing entirely; every other protection
    # (including Contacts) is present.
    dispatcher.write_text('''
            case "airtable_update":
                enforce_leads_write_gate("airtable_update", {"table": table}, source=_write_source)
                if _ALIAS_MAP.get(table, table) == "אנשי קשר (Contacts)":
                    result = crm.update_contact(record_id, fields, source="agent")
                elif _resolved_table in _CRM_TABLE_ROUTING:
                    result = airtable_update(_resolved_table, record_id, fields)
                else:
                    result = airtable_update(table, record_id, fields)
''', encoding="utf-8")
    monkeypatch.setattr(audit, "DISPATCHER_PY", dispatcher)
    failures = audit.check_protected_business_table_raw_update()
    assert any("_TASK_ALLOWED_UPDATE_FIELDS" in f for f in failures)
    assert not any("אנשי קשר (Contacts)" in f for f in failures)


def test_all_protections_present_is_clean(monkeypatch, tmp_path):
    dispatcher = tmp_path / "dispatcher.py"
    dispatcher.write_text(_LIVE_UPDATE_CASE_SNIPPET, encoding="utf-8")
    monkeypatch.setattr(audit, "DISPATCHER_PY", dispatcher)
    assert audit.check_protected_business_table_raw_update() == []


# ══════════════════════════════════════════════════════════════════
# Guard 6 — every deterministic queue-then-approve turn must route through
# the shared duplicate-reply-suppression helper
# ══════════════════════════════════════════════════════════════════

_LIVE_DETERMINISTIC_QUEUE_SNIPPET = '''
def _finalize_deterministic_queue_outcome(
    outcome: dict, chat_id: str, out_meta: dict | None, log_prefix: str,
    fallback_message: str,
) -> str:
    """shared duplicate-reply-suppression guard."""
    return outcome.get("message") or fallback_message


def _queue_deterministic_create_task(
    title: str, chat_id: str, channel: str, user_text: str,
    identity, out_meta: dict | None = None, task_parse=None,
) -> str:
    outcome = queue_task_request(intent="create_task", queue=_queue_task)
    return _finalize_deterministic_queue_outcome(
        outcome, chat_id, out_meta, "DeterministicCreateTask", "fallback",
    )


def _queue_deterministic_create_deal(
    name: str, domain: str, chat_id: str, channel: str, user_text: str,
    identity, out_meta: dict | None = None,
) -> str:
    outcome = _queue_approval_detailed("crm_create_deal", {}, chat_id, channel, user_text)
    return _finalize_deterministic_queue_outcome(
        outcome, chat_id, out_meta, "DeterministicCreateDeal", "fallback",
    )


def _queue_deterministic_task_update(
    intent: str, user_text: str, chat_id: str, channel: str, identity,
    out_meta: dict | None = None,
) -> str:
    outcome = queue_task_request(intent=intent, queue=lambda t, p: _queue_approval_detailed(t, p, chat_id, channel, user_text))
    return _finalize_deterministic_queue_outcome(
        outcome, chat_id, out_meta, "DeterministicTaskUpdate", "fallback",
    )
'''


def test_current_repo_has_no_deterministic_queue_duplicate_reply_regressions():
    """Runs against the real, current source — proves every
    `_queue_deterministic_*()` function today (create_task, create_deal,
    task_update) routes through the shared helper."""
    assert audit.check_deterministic_queue_duplicate_reply_suppression() == []


def test_find_deterministic_queue_functions_extracts_all_three():
    functions = dict(audit.find_deterministic_queue_functions(_LIVE_DETERMINISTIC_QUEUE_SNIPPET))
    assert set(functions) == {
        "_queue_deterministic_create_task",
        "_queue_deterministic_create_deal",
        "_queue_deterministic_task_update",
    }
    for body in functions.values():
        assert "_finalize_deterministic_queue_outcome(" in body


def test_helper_removed_entirely_is_flagged(monkeypatch, tmp_path):
    app_py = tmp_path / "app.py"
    app_py.write_text("# no _finalize_deterministic_queue_outcome() at all\n", encoding="utf-8")
    monkeypatch.setattr(audit, "APP_PY", app_py)
    failures = audit.check_deterministic_queue_duplicate_reply_suppression()
    assert any("no longer defines" in f for f in failures)


def test_one_sibling_bypassing_the_helper_is_flagged(monkeypatch, tmp_path):
    app_py = tmp_path / "app.py"
    # create_deal composes its reply inline instead of calling the helper —
    # the exact BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY regression shape.
    broken = _LIVE_DETERMINISTIC_QUEUE_SNIPPET.replace(
        'outcome = _queue_approval_detailed("crm_create_deal", {}, chat_id, channel, user_text)\n'
        "    return _finalize_deterministic_queue_outcome(\n"
        '        outcome, chat_id, out_meta, "DeterministicCreateDeal", "fallback",\n'
        "    )",
        'outcome = _queue_approval_detailed("crm_create_deal", {}, chat_id, channel, user_text)\n'
        '    return outcome.get("message") or "fallback"',
    )
    assert "_finalize_deterministic_queue_outcome(\n        outcome, chat_id, out_meta, \"DeterministicCreateDeal\"" not in broken
    app_py.write_text(broken, encoding="utf-8")
    monkeypatch.setattr(audit, "APP_PY", app_py)
    failures = audit.check_deterministic_queue_duplicate_reply_suppression()
    assert any("_queue_deterministic_create_deal" in f for f in failures)
    assert not any("_queue_deterministic_create_task" in f for f in failures)
    assert not any("_queue_deterministic_task_update" in f for f in failures)


def test_all_three_using_the_helper_is_clean(monkeypatch, tmp_path):
    app_py = tmp_path / "app.py"
    app_py.write_text(_LIVE_DETERMINISTIC_QUEUE_SNIPPET, encoding="utf-8")
    monkeypatch.setattr(audit, "APP_PY", app_py)
    assert audit.check_deterministic_queue_duplicate_reply_suppression() == []


def test_no_deterministic_queue_functions_at_all_is_flagged(monkeypatch, tmp_path):
    app_py = tmp_path / "app.py"
    app_py.write_text(
        f"def {audit._DETERMINISTIC_QUEUE_OUTCOME_HELPER}():\n    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "APP_PY", app_py)
    failures = audit.check_deterministic_queue_duplicate_reply_suppression()
    assert any("has no `_queue_deterministic_*()` functions at all" in f for f in failures)


# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# Guard 7 — exactly one deterministic crm_create_deal payload builder
# ══════════════════════════════════════════════════════════════════

_LIVE_SINGLE_DEAL_BUILDER_SNIPPET = '''
def _queue_deterministic_create_deal(
    name: str, domain: str, chat_id: str, channel: str, user_text: str,
    identity, out_meta: dict | None = None, origin_lead_id: str = "",
) -> str:
    deal_inputs = {"name": name, "domain": domain, "owner_id": "x"}
    if origin_lead_id:
        deal_inputs["origin_lead_id"] = origin_lead_id
    outcome = _queue_approval_detailed(
        "crm_create_deal",
        deal_inputs,
        chat_id, channel, user_text,
        trusted_source="deterministic_create_deal",
    )
    return _finalize_deterministic_queue_outcome(
        outcome, chat_id, out_meta, "DeterministicCreateDeal", "fallback",
    )
'''


def test_current_repo_has_no_crm_create_deal_second_payload_builder():
    """Runs against the real, current source — proves the deterministic
    Lead→Deal route (origin_lead_id) still has exactly one proposer:
    _queue_deterministic_create_deal()."""
    assert audit.check_crm_create_deal_single_payload_builder() == []


def test_single_call_site_is_clean(monkeypatch, tmp_path):
    app_py = tmp_path / "app.py"
    app_py.write_text(_LIVE_SINGLE_DEAL_BUILDER_SNIPPET, encoding="utf-8")
    monkeypatch.setattr(audit, "APP_PY", app_py)
    assert audit.check_crm_create_deal_single_payload_builder() == []


def test_a_comment_or_docstring_mentioning_the_call_shape_is_not_a_false_positive(monkeypatch, tmp_path):
    """AST-based, not a text/count scan: a docstring or comment merely
    describing the call shape (exactly what happened once while writing
    this guard) must never be mistaken for a real second call site."""
    app_py = tmp_path / "app.py"
    snippet = _LIVE_SINGLE_DEAL_BUILDER_SNIPPET + '''

def some_other_function():
    """Never call _queue_approval_detailed("crm_create_deal", ...) directly
    from here — see _queue_deterministic_create_deal()."""
    # _queue_approval_detailed("crm_create_deal", ...) — also not a real call
    return None
'''
    app_py.write_text(snippet, encoding="utf-8")
    monkeypatch.setattr(audit, "APP_PY", app_py)
    assert audit.check_crm_create_deal_single_payload_builder() == []


def test_second_call_site_is_flagged(monkeypatch, tmp_path):
    """The exact LEAD-TO-DEAL-ORIGIN-LINK regression shape: a new trigger
    builds its own crm_create_deal payload and proposes it directly instead
    of reusing _queue_deterministic_create_deal(origin_lead_id=...)."""
    app_py = tmp_path / "app.py"
    second_site = '''

def cmd_deal_from_lead_BROKEN(msg):
    deal_inputs = {"name": "x", "domain": "import", "owner_id": "y"}
    outcome = _queue_approval_detailed(
        "crm_create_deal", deal_inputs, chat_id, channel, user_text,
    )
    return _finalize_deterministic_queue_outcome(
        outcome, chat_id, None, "DeterministicCreateDealFromLead", "fallback",
    )
'''
    app_py.write_text(_LIVE_SINGLE_DEAL_BUILDER_SNIPPET + second_site, encoding="utf-8")
    monkeypatch.setattr(audit, "APP_PY", app_py)
    failures = audit.check_crm_create_deal_single_payload_builder()
    assert any("cmd_deal_from_lead_BROKEN" in f for f in failures)


def test_no_call_site_at_all_is_flagged(monkeypatch, tmp_path):
    app_py = tmp_path / "app.py"
    app_py.write_text("# no crm_create_deal queueing here at all\n", encoding="utf-8")
    monkeypatch.setattr(audit, "APP_PY", app_py)
    failures = audit.check_crm_create_deal_single_payload_builder()
    assert any("no longer proposes" in f for f in failures)


def test_no_runtime_or_persistence_side_effects():
    """The module must be pure static analysis — same invariant every
    other tools/audit_*.py governance script upholds."""
    import ast
    import inspect

    source = inspect.getsource(audit)
    tree = ast.parse(source)
    forbidden = {"requests", "socket", "urllib"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & forbidden)
