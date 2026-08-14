"""DB-backed SCOREBOS catalog importer and snapshot generator.

The catalog is editorial state. Runtime never calls this module; it reads the
validated local snapshot produced here.
"""

from __future__ import annotations

import copy
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.database import get_conn, release_conn
from tools.tool_runtime_snapshot import (
    DEFAULT_PATH,
    SCHEMA_VERSION,
    SnapshotLoadError,
    validate_snapshot,
)


class CatalogDatabaseUnavailable(RuntimeError):
    pass


def _json_value(value: Any, default):
    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _verification_status(seed_status: str) -> str:
    return {
        "verified": "VERIFIED",
        "approved_with_restrictions": "APPROVED_WITH_RESTRICTIONS",
    }.get(seed_status, "UNVERIFIED")


def _execution_mode(tool_class: str) -> str:
    if tool_class == "business":
        return "GUIDED_EXTERNAL"
    if tool_class == "operator":
        return "OPERATOR_ONLY"
    return "POC_ONLY"


def _decision(tool_class: str) -> str:
    return "KEEP_EXTERNAL" if tool_class in {"business", "operator", "research_crawler"} else "INTEGRATE_LATER"


def import_seed_to_db(conn=None, *, source_revision: str = "python-seed") -> dict[str, int]:
    """Idempotently copy the current seed into the canonical catalog tables."""
    owns_conn = conn is None
    if conn is None:
        conn = get_conn()
    if conn is None:
        raise CatalogDatabaseUnavailable("PostgreSQL connection is unavailable")

    from business_tool_registry import TOOL_REGISTRY
    from tools.tool_runtime_snapshot import normalize_capability_id

    counts = {"tools": 0, "capabilities": 0, "tool_capabilities": 0}
    now = _now()
    try:
        with conn.cursor() as cur:
            for tool in TOOL_REGISTRY:
                status = "APPROVED" if tool.verification_status in {"verified", "approved_with_restrictions"} else "DEFERRED"
                verification = _verification_status(tool.verification_status)
                execution = _execution_mode(tool.tool_class)
                playbook = None
                if tool.playbook:
                    playbook = {
                        "purpose": tool.playbook.purpose,
                        "steps": list(tool.playbook.steps),
                        "privacy_guidance": tool.playbook.privacy_guidance,
                        "agent_mode": "OPTIONAL_AGENT" if tool.playbook.agent_mode == "optional_agent" else "NO_AGENT",
                        "agent_assist_capabilities": list(tool.playbook.agent_assist_capabilities),
                    }
                tags = sorted(set(tool.categories + tool.domain_tags))
                cur.execute(
                    """INSERT INTO tools
                    (tool_id, name, canonical_url, tool_class, tags, tasks, playbook,
                     execution_mode, agent_mode, lifecycle_status, priority, decision,
                     privacy_class, enabled, source, verification_status, last_verified_at,
                     next_verification_at, verification_source, updated_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s)
                    ON CONFLICT (tool_id) DO UPDATE SET
                      name=EXCLUDED.name, canonical_url=EXCLUDED.canonical_url,
                      tool_class=EXCLUDED.tool_class, tags=EXCLUDED.tags, tasks=EXCLUDED.tasks,
                      playbook=EXCLUDED.playbook, execution_mode=EXCLUDED.execution_mode,
                      agent_mode=EXCLUDED.agent_mode, lifecycle_status=EXCLUDED.lifecycle_status,
                      decision=EXCLUDED.decision, privacy_class=EXCLUDED.privacy_class,
                      enabled=EXCLUDED.enabled, source=EXCLUDED.source,
                      verification_status=EXCLUDED.verification_status,
                      last_verified_at=EXCLUDED.last_verified_at, updated_at=EXCLUDED.updated_at""",
                    (tool.tool_id, tool.name, tool.url, tool.tool_class, json.dumps(tags, ensure_ascii=False),
                     json.dumps(list(tool.tasks), ensure_ascii=False), json.dumps(playbook, ensure_ascii=False),
                     execution, playbook["agent_mode"] if playbook else "NO_AGENT", status, 50,
                     _decision(tool.tool_class), getattr(tool.playbook, "privacy_class", "OTHER_BOUNDED_WARNING"),
                     bool(tool.enabled), source_revision, verification, tool.last_verified_at,
                     _SOURCE if False else tool.source, now),
                )
                counts["tools"] += 1

                for raw_capability in tool.capabilities:
                    capability_id = normalize_capability_id(raw_capability)
                    cur.execute(
                        """INSERT INTO capabilities
                        (capability_id, name, tags, lifecycle_status, source, updated_at)
                        VALUES (%s, %s, %s::jsonb, %s, %s, %s)
                        ON CONFLICT (capability_id) DO UPDATE SET
                          name=EXCLUDED.name, tags=EXCLUDED.tags,
                          lifecycle_status=EXCLUDED.lifecycle_status, source=EXCLUDED.source,
                          updated_at=EXCLUDED.updated_at""",
                        (capability_id, raw_capability, json.dumps([], ensure_ascii=False), "VERIFIED",
                         source_revision, now),
                    )
                    counts["capabilities"] += 1
                    relation_id = f"{tool.tool_id}:{capability_id}"
                    cur.execute(
                        """INSERT INTO tool_capabilities
                        (tool_capability_id, tool_id, capability_id, execution_mode, agent_mode,
                         lifecycle_status, verification_status, enabled, priority, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tool_capability_id) DO UPDATE SET
                          execution_mode=EXCLUDED.execution_mode, agent_mode=EXCLUDED.agent_mode,
                          lifecycle_status=EXCLUDED.lifecycle_status,
                          verification_status=EXCLUDED.verification_status,
                          enabled=EXCLUDED.enabled, priority=EXCLUDED.priority,
                          updated_at=EXCLUDED.updated_at""",
                        (relation_id, tool.tool_id, capability_id, execution,
                         playbook["agent_mode"] if playbook else "NO_AGENT", status,
                         verification, bool(tool.enabled), 50, now),
                    )
                    counts["tool_capabilities"] += 1
        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns_conn:
            release_conn(conn)


def _fetch_rows(conn, query: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        columns = [item[0] for item in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def read_catalog_from_db(conn) -> tuple[list[dict], list[dict], list[dict]]:
    tools = _fetch_rows(conn, """SELECT tool_id, name, canonical_url, tool_class, tags, tasks,
        playbook, execution_mode, agent_mode, lifecycle_status, priority, decision,
        privacy_class, enabled, source, verification_status, last_verified_at,
        next_verification_at FROM tools ORDER BY tool_id""")
    capabilities = _fetch_rows(conn, """SELECT capability_id, name, tags, lifecycle_status
        FROM capabilities ORDER BY capability_id""")
    relations = _fetch_rows(conn, """SELECT tool_capability_id, tool_id, capability_id,
        execution_mode, agent_mode, lifecycle_status, verification_status, enabled, priority
        FROM tool_capabilities ORDER BY tool_capability_id""")
    return tools, capabilities, relations


def snapshot_from_catalog_rows(
    tools: list[dict], capabilities: list[dict], relations: list[dict],
    *, source_revision: str = "catalog-db", generated_at: str | None = None,
) -> dict:
    generated_at = generated_at or _now()
    relation_ids_by_tool: dict[str, list[str]] = {}
    for relation in relations:
        relation_ids_by_tool.setdefault(relation["tool_id"], []).append(relation["capability_id"])

    snapshot_tools = []
    for row in tools:
        verification = row["verification_status"]
        runtime_visible = (
            row["tool_class"] == "business"
            and row["enabled"]
            and row["lifecycle_status"] == "APPROVED"
            and verification in {"VERIFIED", "APPROVED_WITH_RESTRICTIONS"}
            and row["execution_mode"] not in {"OPERATOR_ONLY", "POC_ONLY"}
        )
        snapshot_tools.append({
            "tool_id": row["tool_id"], "name": row["name"], "canonical_url": row["canonical_url"],
            "tool_class": row["tool_class"], "tags": sorted(_json_value(row["tags"], [])),
            "tasks": list(_json_value(row["tasks"], [])),
            "capability_ids": sorted(relation_ids_by_tool.get(row["tool_id"], [])),
            "execution_mode": row["execution_mode"], "agent_mode": row["agent_mode"],
            "lifecycle_status": row["lifecycle_status"], "decision": row["decision"],
            "privacy_class": row["privacy_class"], "enabled": bool(row["enabled"]),
            "verification_status": verification, "last_verified_at": row.get("last_verified_at"),
            "next_verification_at": row.get("next_verification_at"),
            "playbook": _json_value(row["playbook"], None),
            "runtime_visible": runtime_visible,
        })
    snapshot = {
        "schema_version": SCHEMA_VERSION, "generated_at": generated_at,
        "source_revision": source_revision,
        "tools": sorted(snapshot_tools, key=lambda item: item["tool_id"]),
        "capabilities": sorted(capabilities, key=lambda item: item["capability_id"]),
        "tool_capabilities": sorted(relations, key=lambda item: item["tool_capability_id"]),
    }
    validate_snapshot(snapshot)
    payload = copy.deepcopy(snapshot)
    payload["generated_at"] = ""
    snapshot["content_hash"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return snapshot


def generate_snapshot_from_db(
    conn=None, *, source_revision: str = "catalog-db", generated_at: str | None = None,
) -> dict:
    owns_conn = conn is None
    if conn is None:
        conn = get_conn()
    if conn is None:
        raise CatalogDatabaseUnavailable("PostgreSQL connection is unavailable")
    try:
        return snapshot_from_catalog_rows(
            *read_catalog_from_db(conn),
            source_revision=source_revision,
            generated_at=generated_at,
        )
    finally:
        if owns_conn:
            release_conn(conn)


def write_snapshot_from_db(
    path: str | Path = DEFAULT_PATH, conn=None, *, source_revision: str = "catalog-db",
) -> None:
    snapshot = generate_snapshot_from_db(conn, source_revision=source_revision)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
