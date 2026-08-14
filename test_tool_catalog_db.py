import json

from tools.tool_catalog_db import (
    import_seed_to_db,
    snapshot_from_catalog_rows,
)


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


def test_seed_importer_is_idempotent_db_writer():
    conn = FakeConnection()
    result = import_seed_to_db(conn, source_revision="test-seed")
    assert result["tools"] == 19
    assert result["tool_capabilities"] >= 19
    assert conn.committed is True
    assert conn.rolled_back is False
    assert any("INSERT INTO tools" in query for query, _ in conn.cursor_obj.calls)


def test_db_catalog_builds_runtime_snapshot_records():
    tools = [{
        "tool_id": "bentopdf",
        "name": "BentoPDF from DB",
        "canonical_url": "https://bentopdf.example/",
        "tool_class": "business",
        "tags": json.dumps(["documents", "pdf"]),
        "tasks": json.dumps(["merge pdf"]),
        "playbook": json.dumps({
            "purpose": "DB purpose",
            "steps": ["DB step"],
            "privacy_guidance": "DB privacy guidance",
            "agent_mode": "NO_AGENT",
            "agent_assist_capabilities": [],
        }),
        "execution_mode": "GUIDED_EXTERNAL",
        "agent_mode": "NO_AGENT",
        "lifecycle_status": "APPROVED",
        "decision": "KEEP_EXTERNAL",
        "privacy_class": "COPY_ONLY",
        "enabled": True,
        "verification_status": "VERIFIED",
        "last_verified_at": "2026-08-14",
        "next_verification_at": None,
    }]
    capabilities = [{
        "capability_id": "pdf_merge",
        "name": "PDF merge",
        "tags": [],
        "lifecycle_status": "VERIFIED",
    }]
    relations = [{
        "tool_capability_id": "bentopdf:pdf_merge",
        "tool_id": "bentopdf",
        "capability_id": "pdf_merge",
        "execution_mode": "GUIDED_EXTERNAL",
        "agent_mode": "NO_AGENT",
        "lifecycle_status": "APPROVED",
        "verification_status": "VERIFIED",
        "enabled": True,
        "priority": 50,
    }]
    snapshot = snapshot_from_catalog_rows(
        tools, capabilities, relations,
        source_revision="catalog-test", generated_at="2026-08-14T00:00:00Z",
    )
    record = snapshot["tools"][0]
    assert record["runtime_visible"] is True
    assert record["name"] == "BentoPDF from DB"
    assert record["canonical_url"] == "https://bentopdf.example/"
    assert record["playbook"]["privacy_guidance"] == "DB privacy guidance"
    assert record["capability_ids"] == ["pdf_merge"]


def test_db_catalog_keeps_non_business_records_out_of_runtime():
    tools = [{
        "tool_id": "sentry",
        "name": "Sentry",
        "canonical_url": "https://sentry.io/",
        "tool_class": "infrastructure_candidate",
        "tags": [],
        "tasks": ["track error"],
        "playbook": None,
        "execution_mode": "POC_ONLY",
        "agent_mode": "NO_AGENT",
        "lifecycle_status": "DEFERRED",
        "decision": "INTEGRATE_LATER",
        "privacy_class": "NO_SENSITIVE_DATA",
        "enabled": True,
        "verification_status": "UNVERIFIED",
        "last_verified_at": "2026-08-14",
        "next_verification_at": None,
    }]
    snapshot = snapshot_from_catalog_rows(tools, [], [])
    assert snapshot["tools"][0]["runtime_visible"] is False
