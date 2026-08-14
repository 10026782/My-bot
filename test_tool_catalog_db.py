import json

from tools.tool_catalog_db import import_seed_to_db, snapshot_from_catalog_rows


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.description = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _tool():
    return {
        "tool_id": "bentopdf", "name": "BentoPDF from DB",
        "canonical_url": "https://bentopdf.example/", "tool_class": "business",
        "tags": json.dumps(["documents", "pdf"]), "tasks": json.dumps(["merge pdf"]),
        "playbook": json.dumps({
            "purpose": "DB purpose", "steps": ["DB step"],
            "privacy_guidance": "DB privacy guidance", "agent_mode": "NO_AGENT",
            "agent_assist_capabilities": [],
        }),
        "execution_mode": "GUIDED_EXTERNAL", "agent_mode": "NO_AGENT",
        "lifecycle_status": "APPROVED", "decision": "KEEP_EXTERNAL",
        "privacy_class": "COPY_ONLY", "enabled": True,
        "verification_status": "VERIFIED", "last_verified_at": "2026-08-14",
        "next_verification_at": None,
    }


def _capability(capability_id):
    return {"capability_id": capability_id, "name": capability_id,
            "tags": [], "lifecycle_status": "VERIFIED"}


def _relation(capability_id, verification="VERIFIED", lifecycle="APPROVED", enabled=True):
    return {
        "tool_capability_id": f"bentopdf:{capability_id}", "tool_id": "bentopdf",
        "capability_id": capability_id, "execution_mode": "GUIDED_EXTERNAL",
        "agent_mode": "NO_AGENT", "lifecycle_status": lifecycle,
        "verification_status": verification, "enabled": enabled, "priority": 50,
    }


def _snapshot(relations):
    return snapshot_from_catalog_rows(
        [_tool()], [_capability("pdf_merge"), _capability("csv_repair")],
        relations, source_revision="catalog-test", generated_at="2026-08-14T00:00:00Z",
    )


def test_seed_importer_is_insert_only_by_default():
    conn = FakeConnection()
    result = import_seed_to_db(conn, source_revision="test-seed")
    assert result["tools"] == 19
    assert result["tool_capabilities"] >= 19
    assert conn.committed is True
    assert conn.rolled_back is False
    assert "DO NOTHING" in conn.cursor_obj.calls[0][0]


def test_seed_importer_requires_explicit_update_override():
    conn = FakeConnection()
    import_seed_to_db(conn, source_revision="test-seed", allow_existing_update=True)
    assert "DO UPDATE" in conn.cursor_obj.calls[0][0]


def test_db_catalog_uses_db_authored_runtime_fields():
    snapshot = _snapshot([_relation("pdf_merge")])
    record = snapshot["tools"][0]
    assert record["runtime_visible"] is True
    assert record["name"] == "BentoPDF from DB"
    assert record["canonical_url"] == "https://bentopdf.example/"
    assert record["playbook"]["privacy_guidance"] == "DB privacy guidance"
    assert record["capability_ids"] == ["pdf_merge"]


def test_approved_tool_with_unverified_relation_hides_capability():
    snapshot = _snapshot([_relation("pdf_merge", verification="UNVERIFIED")])
    assert snapshot["tools"][0]["runtime_visible"] is False
    assert snapshot["tools"][0]["capability_ids"] == []
    assert snapshot["tool_capabilities"][0]["enabled"] is False


def test_only_verified_relation_is_runtime_visible():
    snapshot = _snapshot([
        _relation("pdf_merge", verification="VERIFIED"),
        _relation("csv_repair", verification="DEFERRED"),
    ])
    assert snapshot["tools"][0]["runtime_visible"] is True
    assert snapshot["tools"][0]["capability_ids"] == ["pdf_merge"]
    assert snapshot["tool_capabilities"][1]["enabled"] is False


def test_approved_tool_with_zero_eligible_relations_is_hidden():
    snapshot = _snapshot([
        _relation("pdf_merge", lifecycle="DEFERRED"),
        _relation("csv_repair", verification="UNVERIFIED"),
    ])
    assert snapshot["tools"][0]["runtime_visible"] is False
    assert snapshot["tools"][0]["capability_ids"] == []


def test_regeneration_after_relation_approval_exposes_capability():
    deferred = _snapshot([_relation("pdf_merge", verification="DEFERRED")])
    approved = _snapshot([_relation("pdf_merge", verification="VERIFIED")])
    assert deferred["tools"][0]["capability_ids"] == []
    assert approved["tools"][0]["capability_ids"] == ["pdf_merge"]


def test_non_business_records_stay_out_of_runtime():
    tool = _tool()
    tool.update({
        "tool_id": "sentry", "tool_class": "infrastructure_candidate",
        "execution_mode": "POC_ONLY", "lifecycle_status": "DEFERRED",
        "verification_status": "UNVERIFIED",
    })
    snapshot = snapshot_from_catalog_rows([tool], [], [])
    assert snapshot["tools"][0]["runtime_visible"] is False
