"""Generate and validate the read-only Business Tool runtime snapshot."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SCHEMA_VERSION = "1"
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data/tool_registry/runtime_snapshot.json"
_STATUS = {"DISCOVERED", "RESEARCHING", "VERIFIED", "APPROVED", "DEFERRED", "REJECTED", "DEPRECATED"}
_EXECUTION = {"GUIDED_EXTERNAL", "NATIVE", "INTEGRATED", "OPERATOR_ONLY", "POC_ONLY"}
_AGENT = {"NO_AGENT", "OPTIONAL_AGENT", "AGENT_REQUIRED"}
_DECISIONS = {"KEEP_EXTERNAL", "INTERNALIZE", "INTEGRATE_LATER", "REJECT"}
_CAPABILITY_OVERRIDES = {
    "merge": "pdf_merge", "split": "pdf_split", "compress": "pdf_compress",
    "convert": "file_convert", "format conversion": "file_convert",
    "compress image": "image_compress", "resize image": "image_resize", "optimize image": "image_compress",
    "device transfer": "file_transfer", "peer transfer": "file_transfer",
    "chart": "data_chart", "visualize csv": "data_chart", "visualize data": "data_chart",
    "repair csv": "csv_repair", "validate csv": "csv_validate", "inspect csv": "csv_validate",
    "query csv": "file_query", "query json": "file_query", "join files": "file_join", "profile data": "data_profile",
    "encode": "text_transform", "decode": "text_transform", "hash": "text_transform", "transform text": "text_transform",
    "optimize svg": "svg_optimize", "shrink svg": "svg_optimize",
    "convert csv": "file_convert", "convert tabular data": "file_convert",
    "visualize json": "json_visualize", "understand json": "json_visualize",
    "remove metadata": "metadata_remove", "strip exif": "metadata_remove",
    "redact text": "text_redact", "remove secrets": "text_redact", "sanitize logs": "log_sanitize",
    "api inspection": "api_inspection", "webhook inspection": "webhook_inspection",
    "inspect logs": "log_inspection", "search logs": "log_inspection",
    "uptime monitoring": "uptime_monitoring", "heartbeat": "uptime_monitoring",
    "synthetic api testing": "api_testing", "browser testing": "browser_testing",
    "error tracking": "error_tracking", "exception grouping": "error_tracking",
    "supply chain scan": "dependency_scan", "dependency scan": "dependency_scan",
}


class SnapshotValidationError(ValueError):
    pass


class SnapshotLoadError(RuntimeError):
    pass


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return value


def normalize_capability_id(value: str) -> str:
    """Return the stable public capability ID for an existing seed phrase."""
    return _CAPABILITY_OVERRIDES.get(value.lower(), _slug(value))


# Backward-compatible internal alias for the generator's existing callers.
_capability_id = normalize_capability_id


def _playbook(tool):
    book = tool.playbook
    if not book:
        return None
    return {
        "purpose": book.purpose,
        "steps": list(book.steps),
        "privacy_guidance": book.privacy_guidance,
        "agent_mode": "OPTIONAL_AGENT" if book.agent_mode == "optional_agent" else "NO_AGENT",
        "agent_assist_capabilities": list(book.agent_assist_capabilities),
    }


def generate_snapshot(*, source_revision: str | None = None, generated_at: str | None = None) -> dict:
    from business_tool_registry import TOOL_REGISTRY

    source_revision = source_revision or os.environ.get("TOOL_REGISTRY_SOURCE_REVISION", "working-tree")
    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    tools = []
    capabilities = {}
    relations = []
    for tool in TOOL_REGISTRY:
        status = "APPROVED" if tool.verification_status in {"verified", "approved_with_restrictions"} else "DEFERRED"
        execution = "GUIDED_EXTERNAL" if tool.tool_class == "business" else "OPERATOR_ONLY" if tool.tool_class == "operator" else "POC_ONLY"
        decision = "KEEP_EXTERNAL" if tool.tool_class in {"business", "operator", "research_crawler"} else "INTEGRATE_LATER"
        verified = tool.verification_status in {"verified", "approved_with_restrictions"}
        verification_status = "VERIFIED" if tool.verification_status == "verified" else "APPROVED_WITH_RESTRICTIONS" if tool.verification_status == "approved_with_restrictions" else "UNVERIFIED"
        runtime_visible = tool.tool_class == "business" and verified and tool.enabled
        tools.append({
            "tool_id": tool.tool_id, "name": tool.name, "canonical_url": tool.url,
            "tool_class": tool.tool_class, "tags": sorted(set(tool.categories + tool.domain_tags)),
            "tasks": list(tool.tasks),
            "capability_ids": sorted({normalize_capability_id(raw) for raw in tool.capabilities}),
            "execution_mode": execution, "agent_mode": "OPTIONAL_AGENT" if tool.playbook and tool.playbook.agent_mode == "optional_agent" else "NO_AGENT",
            "lifecycle_status": status, "decision": decision, "privacy_class": getattr(tool.playbook, "privacy_class", "OTHER_BOUNDED_WARNING") if tool.playbook else "OTHER_BOUNDED_WARNING",
            "enabled": bool(tool.enabled), "verification_status": verification_status,
            "last_verified_at": tool.last_verified_at, "next_verification_at": None,
            "playbook": _playbook(tool), "runtime_visible": runtime_visible,
        })
        for raw in tool.capabilities:
            capability_id = normalize_capability_id(raw)
            capabilities.setdefault(capability_id, {"capability_id": capability_id, "name": raw, "tags": [], "lifecycle_status": "VERIFIED"})
            relation_id = f"{tool.tool_id}:{capability_id}"
            if any(item["tool_capability_id"] == relation_id for item in relations):
                continue
            relations.append({
                "tool_capability_id": relation_id, "tool_id": tool.tool_id, "capability_id": capability_id,
                "execution_mode": execution, "agent_mode": tools[-1]["agent_mode"], "lifecycle_status": status,
                "verification_status": verification_status, "enabled": runtime_visible,
                "priority": 50 if runtime_visible else 0,
            })
    snapshot = {
        "schema_version": SCHEMA_VERSION, "generated_at": generated_at, "source_revision": source_revision,
        "tools": sorted(tools, key=lambda x: x["tool_id"]),
        "capabilities": sorted(capabilities.values(), key=lambda x: x["capability_id"]),
        "tool_capabilities": sorted(relations, key=lambda x: x["tool_capability_id"]),
    }
    validate_snapshot(snapshot)
    payload = copy.deepcopy(snapshot)
    payload["generated_at"] = ""
    snapshot["content_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return snapshot


def validate_snapshot(snapshot: dict) -> None:
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != SCHEMA_VERSION:
        raise SnapshotValidationError("unknown schema_version")
    for field in ("generated_at", "source_revision", "tools", "capabilities", "tool_capabilities"):
        if field not in snapshot:
            raise SnapshotValidationError(f"missing snapshot field: {field}")
    tools = snapshot["tools"]
    caps = snapshot["capabilities"]
    relations = snapshot["tool_capabilities"]
    if len({x.get("tool_id") for x in tools}) != len(tools): raise SnapshotValidationError("duplicate tool ID")
    if len({x.get("capability_id") for x in caps}) != len(caps): raise SnapshotValidationError("duplicate capability ID")
    if len({x.get("tool_capability_id") for x in relations}) != len(relations): raise SnapshotValidationError("duplicate relation ID")
    tool_ids, cap_ids = {x.get("tool_id") for x in tools}, {x.get("capability_id") for x in caps}
    for tool in tools:
        required = ("tool_id", "name", "canonical_url", "tool_class", "tags", "execution_mode", "agent_mode", "lifecycle_status", "decision", "privacy_class", "enabled", "verification_status", "last_verified_at", "runtime_visible")
        if any(not tool.get(field) and field not in {"enabled", "runtime_visible"} for field in required): raise SnapshotValidationError("missing tool field")
        parsed = urlparse(tool["canonical_url"])
        if parsed.scheme != "https" or not parsed.netloc: raise SnapshotValidationError("malformed URL")
        if tool["execution_mode"] not in _EXECUTION or tool["agent_mode"] not in _AGENT or tool["lifecycle_status"] not in _STATUS or tool["decision"] not in _DECISIONS: raise SnapshotValidationError("unknown enum value")
        if tool["runtime_visible"] and (not tool["enabled"] or tool["lifecycle_status"] != "APPROVED" or tool["verification_status"] not in {"VERIFIED", "APPROVED_WITH_RESTRICTIONS"} or tool["execution_mode"] in {"OPERATOR_ONLY", "POC_ONLY"} or tool["decision"] == "REJECT"): raise SnapshotValidationError("ineligible runtime-visible tool")
    for relation in relations:
        if relation.get("tool_id") not in tool_ids or relation.get("capability_id") not in cap_ids: raise SnapshotValidationError("broken relation")
        if relation.get("tool_capability_id") != f"{relation.get('tool_id')}:{relation.get('capability_id')}": raise SnapshotValidationError("unstable relation ID")
        if relation.get("execution_mode") not in _EXECUTION or relation.get("agent_mode") not in _AGENT or relation.get("lifecycle_status") not in _STATUS: raise SnapshotValidationError("unknown relation enum")
        parent = next(x for x in tools if x["tool_id"] == relation["tool_id"])
        if relation.get("enabled") and relation.get("lifecycle_status") == "APPROVED" and relation.get("verification_status") in {"VERIFIED", "APPROVED_WITH_RESTRICTIONS"} and not parent["runtime_visible"]: raise SnapshotValidationError("eligible relation has ineligible parent")


def load_tool_runtime_snapshot(path: str | Path | None = None) -> dict:
    snapshot_path = Path(path) if path else DEFAULT_PATH
    try:
        with snapshot_path.open(encoding="utf-8") as handle:
            snapshot = json.load(handle)
        validate_snapshot(snapshot)
        return snapshot
    except (OSError, json.JSONDecodeError, SnapshotValidationError) as exc:
        raise SnapshotLoadError(f"tool runtime snapshot unavailable: {exc}") from exc


def write_snapshot(path: str | Path = DEFAULT_PATH, *, source_revision: str | None = None) -> None:
    snapshot = generate_snapshot(source_revision=source_revision)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-revision")
    parser.add_argument("--output", default=str(DEFAULT_PATH))
    args = parser.parse_args()
    write_snapshot(args.output, source_revision=args.source_revision)
