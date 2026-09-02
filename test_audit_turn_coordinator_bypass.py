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
