"""Deterministic metadata loader and context-bundle builder.

This module is developer tooling only. It has no production imports and uses
only the Python standard library. הקטלוג הוא `.json` פשוט (N17 סעיף 2 —
בעבר נקרא `.yaml` אך תמיד נטען עם `json.loads()`; שונה לפורמט האמיתי שלו
כך שתכונת YAML אמיתית — הערות, multi-line strings, anchors — לא תוכל
יותר לשבור את הטעינה בשקט).
"""

from __future__ import annotations

import fnmatch
import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_SCHEMA_MAJOR = 1
CATALOG_RELATIVE_ROOT = Path("docs/context_librarian")
# היוריסטיקה לא-מאומתת של ספירת-תווים, לא token count אמיתי של Anthropic.
# מקור אמת יחיד עבור המקדם כך ששינוי עתידי (אחרי ש-
# TOKEN_ESTIMATION_BENCHMARK.md יכיל נתונים אמיתיים) יגע רק בקבוע אחד.
# ראו את ה-docstring של _approximate_char_estimate() להסתייגות המלאה.
_CHARS_PER_APPROXIMATE_TOKEN = 4
DEFAULT_EXCLUDED_STATUSES = frozenset({"historical", "superseded"})
QUALIFYING_PRODUCTION_EVIDENCE_STATUSES = frozenset(
    {"live", "production_verified"}
)
NODE_FIELDS = frozenset(
    {
        "id",
        "name",
        "type",
        "status",
        "authority_level",
        "source_of_truth",
        "owner",
        "code_paths",
        "test_paths",
        "canonical_docs",
        "production_evidence",
        "feature_flags",
        "valid_from",
        "last_verified_commit",
        "confidence",
        "notes",
        "extensions",
    }
)
EDGE_FIELDS = frozenset({"from", "to", "type", "notes", "extensions"})
PROFILE_FIELDS = frozenset(
    {
        "id",
        "description",
        "primary_layers",
        "required_dependency_layers",
        "optional_evidence",
        "conditional_optional_evidence",
        "excluded_areas",
        "maximum_documents",
        "maximum_approximate_token_budget",
        "mandatory_canonical_decisions",
        "allowed_edge_types",
        "maximum_traversal_depth",
        "allowed_statuses",
        "selection_terms",
        "extensions",
    }
)
PROFILE_REQUIRED_FIELDS = PROFILE_FIELDS - {"extensions"}
SAFETY_RULES = (
    "main overrides planning documents and generated bundles.",
    "ActionContracts is canonical for approval lifecycle.",
    "No new source of truth may be created.",
    "shadow, flag_off, and planning_only are not production-active.",
    "Production verification is required before claiming completion.",
    "Historical failures must not override later verified evidence.",
    "UX work must not expose user-facing/internal IDs or internal tool names.",
)


class ContextLibrarianError(RuntimeError):
    """Raised for fail-closed catalog, selection, or budget errors."""


@dataclass(frozen=True)
class Catalog:
    repo_root: Path
    catalog_root: Path
    node_schema: dict[str, Any]
    edge_schema: dict[str, Any]
    nodes: dict[str, dict[str, Any]]
    edges: tuple[dict[str, Any], ...]
    profiles: dict[str, dict[str, Any]]
    layer_nodes: dict[str, str]


def _load_catalog_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextLibrarianError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContextLibrarianError(f"{path} must contain an object")
    return value


def _validate_version(value: Any, path: Path) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+", value):
        raise ContextLibrarianError(f"{path}: invalid schema_version {value!r}")
    if int(value.split(".", 1)[0]) != SUPPORTED_SCHEMA_MAJOR:
        raise ContextLibrarianError(f"{path}: unsupported schema major {value}")


def _require_fields(
    value: dict[str, Any], required: Iterable[str], allowed: Iterable[str], label: str
) -> None:
    required_set = set(required)
    allowed_set = set(allowed)
    missing = sorted(required_set - set(value))
    unknown = sorted(set(value) - allowed_set)
    if missing:
        raise ContextLibrarianError(f"{label}: missing fields: {', '.join(missing)}")
    if unknown:
        raise ContextLibrarianError(f"{label}: unknown fields: {', '.join(unknown)}")


def _validate_reference(ref: Any, required: list[str], label: str) -> None:
    if not isinstance(ref, dict):
        raise ContextLibrarianError(f"{label}: reference must be an object")
    missing = sorted(set(required) - set(ref))
    if missing:
        raise ContextLibrarianError(f"{label}: reference missing {', '.join(missing)}")


def _validate_node(
    node: dict[str, Any], schema: dict[str, Any], repo_root: Path, label: str
) -> None:
    _require_fields(node, schema["required"], NODE_FIELDS, label)
    if node["type"] not in schema["types"]:
        raise ContextLibrarianError(f"{label}: unknown node type {node['type']!r}")
    if node["status"] not in schema["statuses"]:
        raise ContextLibrarianError(f"{label}: unknown status {node['status']!r}")
    if node["authority_level"] not in schema["authority_levels"]:
        raise ContextLibrarianError(
            f"{label}: unknown authority_level {node['authority_level']!r}"
        )
    if not isinstance(node["source_of_truth"], dict):
        raise ContextLibrarianError(f"{label}: source_of_truth must be an object")
    missing_source = set(schema["source_of_truth_required"]) - set(
        node["source_of_truth"]
    )
    if missing_source:
        raise ContextLibrarianError(
            f"{label}: source_of_truth missing {', '.join(sorted(missing_source))}"
        )
    if not re.fullmatch(schema["commit_pattern"], str(node["last_verified_commit"])):
        raise ContextLibrarianError(f"{label}: invalid last_verified_commit")
    low, high = schema["confidence_range"]
    if not isinstance(node["confidence"], (int, float)) or not low <= node["confidence"] <= high:
        raise ContextLibrarianError(f"{label}: confidence outside {low}..{high}")

    list_fields = (
        "code_paths",
        "test_paths",
        "canonical_docs",
        "production_evidence",
        "feature_flags",
        "notes",
    )
    for field in list_fields:
        if not isinstance(node[field], list):
            raise ContextLibrarianError(f"{label}: {field} must be a list")
    for ref in node["canonical_docs"]:
        _validate_reference(ref, schema["reference_required"], label)
        if ref["status"] not in schema["statuses"]:
            raise ContextLibrarianError(
                f"{label}: canonical document has unknown status {ref['status']!r}"
            )
    for ref in node["production_evidence"]:
        _validate_reference(ref, schema["production_evidence_required"], label)
    for ref in node["feature_flags"]:
        _validate_reference(ref, schema["feature_flag_required"], label)

    referenced_paths = list(node["code_paths"]) + list(node["test_paths"])
    referenced_paths += [ref["path"] for ref in node["canonical_docs"]]
    referenced_paths += [ref["path"] for ref in node["production_evidence"]]
    for relative in referenced_paths:
        path = repo_root / relative
        if not path.exists():
            raise ContextLibrarianError(f"{label}: referenced path does not exist: {relative}")


def _validate_profile(
    profile: dict[str, Any], edge_types: set[str], layer_ids: set[str], label: str
) -> None:
    _require_fields(profile, PROFILE_REQUIRED_FIELDS, PROFILE_FIELDS, label)
    layer_fields = (
        "primary_layers",
        "required_dependency_layers",
        "optional_evidence",
        "excluded_areas",
    )
    for field in layer_fields:
        if not isinstance(profile[field], list):
            raise ContextLibrarianError(f"{label}: {field} must be a list")
        unknown = sorted(set(profile[field]) - layer_ids)
        if unknown:
            raise ContextLibrarianError(
                f"{label}: unknown layers in {field}: {', '.join(unknown)}"
            )
    for condition in profile["conditional_optional_evidence"]:
        if set(condition) != {"layer", "query_terms"}:
            raise ContextLibrarianError(f"{label}: invalid conditional evidence shape")
        if condition["layer"] not in layer_ids:
            raise ContextLibrarianError(
                f"{label}: unknown conditional layer {condition['layer']}"
            )
    unknown_edges = sorted(set(profile["allowed_edge_types"]) - edge_types)
    if unknown_edges:
        raise ContextLibrarianError(
            f"{label}: unknown allowed edge types: {', '.join(unknown_edges)}"
        )
    if profile["maximum_documents"] <= 0:
        raise ContextLibrarianError(f"{label}: maximum_documents must be positive")
    if profile["maximum_approximate_token_budget"] <= 0:
        raise ContextLibrarianError(
            f"{label}: maximum_approximate_token_budget must be positive"
        )


def load_catalog(repo_root: Path | str) -> Catalog:
    repo_root = Path(repo_root).resolve()
    catalog_root = repo_root / CATALOG_RELATIVE_ROOT
    node_schema = _load_catalog_json(catalog_root / "schema/node_schema.json")
    edge_schema = _load_catalog_json(catalog_root / "schema/edge_schema.json")
    _validate_version(node_schema.get("schema_version"), catalog_root / "schema/node_schema.json")
    _validate_version(edge_schema.get("schema_version"), catalog_root / "schema/edge_schema.json")
    edge_types = set(edge_schema["edge_types"])

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    layer_nodes: dict[str, str] = {}
    catalog_files = sorted((catalog_root / "layers").glob("*.json"))
    catalog_files.append(catalog_root / "decisions/canonical_boundaries.json")
    for path in catalog_files:
        data = _load_catalog_json(path)
        _validate_version(data.get("schema_version"), path)
        if "layer_id" in data:
            layer_id = data["layer_id"]
            if layer_id in layer_nodes:
                raise ContextLibrarianError(f"duplicate layer_id {layer_id}")
        for raw_node in data.get("nodes", []):
            if not isinstance(raw_node, dict):
                raise ContextLibrarianError(f"{path}: node must be an object")
            node_id = raw_node.get("id", "<missing>")
            _validate_node(raw_node, node_schema, repo_root, f"{path}:{node_id}")
            if node_id in nodes:
                raise ContextLibrarianError(f"duplicate node id {node_id}")
            nodes[node_id] = raw_node
        if "layer_id" in data:
            expected_node_id = f"layer.{data['layer_id']}"
            if expected_node_id not in nodes:
                raise ContextLibrarianError(
                    f"{path}: layer catalog must define {expected_node_id}"
                )
            layer_nodes[data["layer_id"]] = expected_node_id
        for edge in data.get("edges", []):
            if not isinstance(edge, dict):
                raise ContextLibrarianError(f"{path}: edge must be an object")
            _require_fields(edge, edge_schema["required"], EDGE_FIELDS, f"{path}:edge")
            if edge["type"] not in edge_types:
                raise ContextLibrarianError(f"{path}: unknown edge type {edge['type']!r}")
            edges.append(edge)

    for edge in edges:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            raise ContextLibrarianError(
                f"edge target missing: {edge['from']} -> {edge['to']}"
            )

    profiles_data = _load_catalog_json(catalog_root / "task_profiles/profiles.json")
    _validate_version(
        profiles_data.get("schema_version"), catalog_root / "task_profiles/profiles.json"
    )
    profiles: dict[str, dict[str, Any]] = {}
    for profile in profiles_data.get("profiles", []):
        if not isinstance(profile, dict):
            raise ContextLibrarianError("profile must be an object")
        profile_id = profile.get("id", "<missing>")
        _validate_profile(
            profile, edge_types, set(layer_nodes), f"profile:{profile_id}"
        )
        if profile_id in profiles:
            raise ContextLibrarianError(f"duplicate profile id {profile_id}")
        for decision in profile["mandatory_canonical_decisions"]:
            if f"decision.{decision}" not in nodes:
                raise ContextLibrarianError(
                    f"profile:{profile_id}: unknown mandatory decision {decision}"
                )
        profiles[profile_id] = profile

    return Catalog(
        repo_root=repo_root,
        catalog_root=catalog_root,
        node_schema=node_schema,
        edge_schema=edge_schema,
        nodes=nodes,
        edges=tuple(edges),
        profiles=profiles,
        layer_nodes=layer_nodes,
    )


def _normalise_query(query: str) -> str:
    return " ".join(query.casefold().split())


def suggest_profiles(catalog: Catalog, query: str) -> list[dict[str, Any]]:
    """Return explainable lexical suggestions without selecting for build."""
    normalised = _normalise_query(query)
    ranked: list[dict[str, Any]] = []
    for profile in catalog.profiles.values():
        matched = sorted(
            {
                term
                for term in profile["selection_terms"]
                if term.casefold() in normalised
            }
        )
        ranked.append(
            {
                "profile_id": profile["id"],
                "score": len(matched),
                "matched_terms": matched,
            }
        )
    return sorted(ranked, key=lambda item: (-item["score"], item["profile_id"]))


def assess_profile_suggestions(
    ranked: list[dict[str, Any]],
) -> dict[str, Any]:
    """Describe suggestion confidence without selecting a build profile."""
    if not ranked or ranked[0]["score"] == 0:
        return {
            "status": "no_match",
            "top_score": 0,
            "candidates": [],
            "suggested_profile": None,
            "automatic_selection": False,
        }

    top_score = ranked[0]["score"]
    candidates = [
        item["profile_id"] for item in ranked if item["score"] == top_score
    ]
    if len(candidates) > 1:
        return {
            "status": "tie",
            "top_score": top_score,
            "candidates": candidates,
            "suggested_profile": None,
            "automatic_selection": False,
        }
    return {
        "status": "unique_suggestion",
        "top_score": top_score,
        "candidates": candidates,
        "suggested_profile": candidates[0],
        "automatic_selection": False,
    }


def evaluate_workflow_gate(
    *,
    stale_node_ids: Iterable[str] = (),
    mandatory_authority_coverage: float = 1.0,
    production_claim: bool = False,
    qualifying_production_evidence: int = 0,
    unresolved_conflicts: Iterable[str] = (),
    excluded_layer_leakage: Iterable[str] = (),
) -> dict[str, Any]:
    """Return the manual agent-bootstrap stop decision and its reasons.

    This gate is reported inside a bundle. It deliberately does not prevent a
    stale bundle from being rendered, because agents need the bundle to learn
    what changed and which sources require direct verification.
    """
    stale = sorted(set(stale_node_ids))
    conflicts = sorted(set(unresolved_conflicts))
    leakage = sorted(set(excluded_layer_leakage))
    reasons: list[str] = []
    if stale:
        reasons.append("stale_nodes")
    if mandatory_authority_coverage < 1.0:
        reasons.append("mandatory_authority_incomplete")
    if production_claim and qualifying_production_evidence == 0:
        reasons.append("production_evidence_missing")
    if conflicts:
        reasons.append("unresolved_source_conflict")
    if leakage:
        reasons.append("excluded_layer_leakage")
    return {
        "status": "STOP" if reasons else "PROCEED",
        "reasons": reasons,
        "stale_nodes": stale,
        "mandatory_authority_coverage": mandatory_authority_coverage,
        "production_claim": production_claim,
        "qualifying_production_evidence": qualifying_production_evidence,
        "unresolved_conflicts": conflicts,
        "excluded_layer_leakage": leakage,
    }


def _conditional_layers(profile: dict[str, Any], query: str) -> set[str]:
    normalised = _normalise_query(query)
    result: set[str] = set()
    for condition in profile["conditional_optional_evidence"]:
        if any(term.casefold() in normalised for term in condition["query_terms"]):
            result.add(condition["layer"])
    return result


def _selection_roles(profile: dict[str, Any], query: str) -> dict[str, str]:
    roles: dict[str, str] = {}
    for layer in profile["primary_layers"]:
        roles[layer] = "primary"
    for layer in profile["required_dependency_layers"]:
        roles.setdefault(layer, "required_dependency")
    for layer in sorted(_conditional_layers(profile, query)):
        roles.setdefault(layer, "conditional_evidence")
    return roles


def _select_nodes(
    catalog: Catalog, profile: dict[str, Any], query: str
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    roles = _selection_roles(profile, query)
    excluded = set(profile["excluded_areas"])
    allowed_statuses = set(profile["allowed_statuses"]) - DEFAULT_EXCLUDED_STATUSES
    for layer in roles:
        if layer in excluded:
            raise ContextLibrarianError(
                f"profile {profile['id']} both selects and excludes {layer}"
            )

    selected_ids: set[str] = {
        catalog.layer_nodes[layer]
        for layer in roles
        if catalog.nodes[catalog.layer_nodes[layer]]["status"] in allowed_statuses
    }
    mandatory_ids = [
        f"decision.{decision}" for decision in profile["mandatory_canonical_decisions"]
    ]
    selected_ids.update(mandatory_ids)

    allowed_edges = set(profile["allowed_edge_types"])
    permitted_layer_nodes = {catalog.layer_nodes[layer] for layer in roles}
    frontier = set(selected_ids)
    traversed: list[dict[str, Any]] = []
    for _ in range(profile["maximum_traversal_depth"]):
        next_frontier: set[str] = set()
        for edge in catalog.edges:
            if edge["from"] not in frontier or edge["type"] not in allowed_edges:
                continue
            target = edge["to"]
            target_node = catalog.nodes[target]
            if target_node["type"] == "layer" and target not in permitted_layer_nodes:
                continue
            if target_node["status"] not in allowed_statuses:
                continue
            traversed.append(edge)
            if target not in selected_ids:
                selected_ids.add(target)
                next_frontier.add(target)
        frontier = next_frontier
        if not frontier:
            break

    mandatory_nodes = [catalog.nodes[node_id] for node_id in mandatory_ids]
    role_rank = {"primary": 0, "required_dependency": 1, "conditional_evidence": 2}
    layer_nodes = [
        catalog.nodes[catalog.layer_nodes[layer]]
        for layer in sorted(roles, key=lambda item: (role_rank[roles[item]], item))
        if catalog.layer_nodes[layer] in selected_ids
    ]
    other_decisions = sorted(
        (
            catalog.nodes[node_id]
            for node_id in selected_ids
            if node_id.startswith("decision.") and node_id not in mandatory_ids
        ),
        key=lambda node: node["id"],
    )
    return mandatory_nodes + other_decisions + layer_nodes, roles, traversed


def _git_changed_paths(repo_root: Path, commit: str) -> set[str]:
    try:
        completed = subprocess.run(
            ["git", "diff", "--name-only", commit, "--"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContextLibrarianError(
            f"cannot compare last_verified_commit {commit} to checkout: {exc}"
        ) from exc
    return {line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()}


def _matches_tracked_path(changed: str, tracked: str) -> bool:
    tracked = tracked.replace("\\", "/")
    return changed == tracked or fnmatch.fnmatch(changed, tracked) or changed.startswith(
        tracked.rstrip("/") + "/"
    )


def _freshness(
    catalog: Catalog, nodes: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    by_commit: dict[str, set[str]] = {}
    result: dict[str, dict[str, Any]] = {}
    for node in nodes:
        commit = node["last_verified_commit"]
        if commit not in by_commit:
            by_commit[commit] = _git_changed_paths(catalog.repo_root, commit)
        changed = by_commit[commit]
        code_changes = sorted(
            path
            for path in changed
            if any(_matches_tracked_path(path, tracked) for tracked in node["code_paths"])
        )
        test_changes = sorted(
            path
            for path in changed
            if any(_matches_tracked_path(path, tracked) for tracked in node["test_paths"])
        )
        doc_paths = [ref["path"] for ref in node["canonical_docs"]]
        doc_changes = sorted(
            path
            for path in changed
            if any(_matches_tracked_path(path, tracked) for tracked in doc_paths)
        )
        result[node["id"]] = {
            "stale": bool(code_changes),
            "code_changes": code_changes,
            "test_changes": test_changes,
            "documentation_changes": doc_changes,
        }
    return result


def _unique_references(
    nodes: list[dict[str, Any]], field: str, maximum_documents: int
) -> list[tuple[str, dict[str, Any]]]:
    """Round-robin references so every selected node gets provenance first."""
    result: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    depth = 0
    while len(result) < maximum_documents:
        added = False
        for node in nodes:
            references = [
                ref
                for ref in node[field]
                if field != "canonical_docs"
                or ref.get("status") not in DEFAULT_EXCLUDED_STATUSES
            ]
            if depth >= len(references):
                continue
            ref = references[depth]
            if ref["path"] in seen:
                continue
            seen.add(ref["path"])
            result.append((node["id"], ref))
            added = True
            if len(result) >= maximum_documents:
                break
        if not added and all(depth >= len(node[field]) - 1 for node in nodes):
            break
        depth += 1
    return result


def _approximate_char_estimate(text: str) -> int:
    """פרוקסי מבוסס-ספירת-תווים לשימוש בטוקנים — NOT a real tokenizer
    count. `ceil(len(text) / _CHARS_PER_APPROXIMATE_TOKEN)` היא היוריסטיקה
    לא-מאומתת; ראו את
    `docs/context_librarian/TOKEN_ESTIMATION_BENCHMARK.md` ל-benchmark
    הממתין מול token counts אמיתיים של Anthropic, ולמה המקדם לא שונה בלי
    הנתונים האלו. קוראים לפונקציה אסור שיציגו את הערך הזה כ-token count
    מדויק או יטענו לחיסכון בטוקנים על סמכו בלבד."""
    return math.ceil(len(text) / _CHARS_PER_APPROXIMATE_TOKEN)


def _qualifies_as_production_evidence(
    reference: dict[str, Any], verified_path: str | None
) -> bool:
    return (
        bool(verified_path)
        and reference.get("path") == verified_path
        and reference.get("status") in QUALIFYING_PRODUCTION_EVIDENCE_STATUSES
        and "production" in reference.get("scope", "").casefold()
    )


def _path_char_estimate(repo_root: Path, references: Iterable[tuple[str, dict[str, Any]]]) -> int:
    """אותה היוריסטיקה לא-מאומתת chars/4 כמו _approximate_char_estimate(),
    מיושמת על קבצי מקור בדיסק. קוראת את הטקסט בפועל ומשתמשת ב-len() —
    ולא ב-stat().st_size — מכיוון שספירת bytes וספירת תווים מתפצלות
    עבור תוכן UTF-8 רב-בייטי (עברית בפרט), מה שהיה מנפח את האומדן הזה
    ביחס לספירת התווים הזיכרונית של _approximate_char_estimate() עבור
    אותו תוכן."""
    total = 0
    seen: set[str] = set()
    for _, ref in references:
        if ref["path"] in seen:
            continue
        seen.add(ref["path"])
        try:
            total += math.ceil(
                len((repo_root / ref["path"]).read_text(encoding="utf-8"))
                / _CHARS_PER_APPROXIMATE_TOKEN
            )
        except (OSError, UnicodeDecodeError):
            continue
    return total


def _render(
    catalog: Catalog,
    profile: dict[str, Any],
    query: str,
    nodes: list[dict[str, Any]],
    roles: dict[str, str],
    traversed: list[dict[str, Any]],
    freshness: dict[str, dict[str, Any]],
    max_documents: int,
    max_tokens: int,
    production_claim: bool,
    verified_production_evidence: str | None,
) -> str:
    decision_nodes = [node for node in nodes if node["type"] == "decision"]
    layer_nodes = [node for node in nodes if node["type"] == "layer"]
    evidence_budget = min(
        sum(bool(node["production_evidence"]) for node in layer_nodes),
        max_documents // 3,
    )
    docs = _unique_references(
        nodes, "canonical_docs", max_documents - evidence_budget
    )
    evidence = _unique_references(
        layer_nodes, "production_evidence", evidence_budget
    )

    selected_layer_ids = {node["id"].split(".", 1)[1] for node in layer_nodes}
    expected_layers = set(profile["primary_layers"]) | set(
        profile["required_dependency_layers"]
    )
    layer_coverage = len(selected_layer_ids & expected_layers) / max(1, len(expected_layers))
    mandatory_ids = {
        f"decision.{item}" for item in profile["mandatory_canonical_decisions"]
    }
    selected_ids = {node["id"] for node in nodes}
    authority_coverage = len(mandatory_ids & selected_ids) / max(1, len(mandatory_ids))
    stale_count = sum(1 for node in layer_nodes if freshness[node["id"]]["stale"])
    freshness_ratio = (len(layer_nodes) - stale_count) / max(1, len(layer_nodes))
    provenance_slots = len(layer_nodes) * 4
    provenance_present = sum(
        bool(node[field])
        for node in layer_nodes
        for field in ("canonical_docs", "code_paths", "test_paths", "production_evidence")
    )
    provenance_completeness = provenance_present / max(1, provenance_slots)
    leakage = sorted(selected_layer_ids & set(profile["excluded_areas"]))
    stale_node_ids = sorted(
        node["id"] for node in layer_nodes if freshness[node["id"]]["stale"]
    )
    conflict_edges = sorted(
        f"{edge['from']} -> {edge['to']}"
        for edge in traversed
        if edge["type"] == "conflicts_with"
    )
    qualifying_evidence = sum(
        _qualifies_as_production_evidence(ref, verified_production_evidence)
        for _, ref in evidence
    )
    workflow_gate = evaluate_workflow_gate(
        stale_node_ids=stale_node_ids,
        mandatory_authority_coverage=authority_coverage,
        production_claim=production_claim,
        qualifying_production_evidence=qualifying_evidence,
        unresolved_conflicts=conflict_edges,
        excluded_layer_leakage=leakage,
    )
    normalised_query = _normalise_query(query)
    matched_layers = sum(
        1
        for node in layer_nodes
        if any(
            token and token in normalised_query
            for token in re.findall(r"[\w-]+", node["name"].casefold())
        )
        or any(term.casefold() in normalised_query for term in profile["selection_terms"])
    )
    query_precision = matched_layers / max(1, len(layer_nodes))

    lines: list[str] = [
        f"# BOSS Context Bundle — {profile['id']}",
        "",
        f"Query: {query or '(none)'}",
        f"Profile: {profile['description']}",
        "Authority: navigation metadata only; inspect cited sources before coding.",
        "",
        "## Agent Consumption Contract",
        "",
        "Use an explicit profile, read this bundle fully, inspect cited sources, and stop on stale nodes or incomplete authority coverage.",
        "Contract: `docs/context_librarian/AGENT_CONSUMPTION_CONTRACT.md`",
        "",
        "## Agent Workflow Gate",
        "",
        f"- status: {workflow_gate['status']}",
        f"- reasons: {workflow_gate['reasons']}",
        f"- stale_nodes: {len(stale_node_ids)} {stale_node_ids}",
        f"- mandatory_authority_coverage: {authority_coverage:.0%}",
        f"- production_claim: {str(production_claim).lower()}",
        f"- verified_production_evidence: {verified_production_evidence or 'none'}",
        f"- qualifying_production_evidence: {qualifying_evidence}",
        f"- unresolved_source_conflicts: {len(conflict_edges)} {conflict_edges}",
        f"- excluded_layer_leakage: {len(leakage)} {leakage}",
        "- A STOP status blocks planning and code changes, not bundle creation.",
        "",
        "## Canonical Decisions",
        "",
    ]
    for node in decision_nodes:
        lines.append(f"- `{node['id']}` — {node['name']}: {node['notes'][0]}")

    lines.extend(["", "## Selected Layers", ""])
    for node in layer_nodes:
        layer_id = node["id"].split(".", 1)[1]
        fresh = freshness[node["id"]]
        stale_label = "STALE: code changed" if fresh["stale"] else "fresh against tracked code"
        lines.append(
            f"- `{layer_id}` ({roles[layer_id]}, {node['status']}, {stale_label}) — {node['notes'][0]}"
        )

    lines.extend(["", "## Canonical Documents", ""])
    lines.extend(
        f"- `{ref['path']}` — {ref['role']} [{ref['status']}] (via `{node_id}`)"
        for node_id, ref in docs
    )
    if not docs:
        lines.append("- None selected.")

    lines.extend(["", "## Code", ""])
    for node in layer_nodes:
        lines.append(f"- `{node['id']}`: " + ", ".join(f"`{path}`" for path in node["code_paths"]))

    lines.extend(["", "## Tests", ""])
    for node in layer_nodes:
        lines.append(f"- `{node['id']}`: " + ", ".join(f"`{path}`" for path in node["test_paths"]))

    lines.extend(["", "## Production Evidence", ""])
    if evidence:
        lines.extend(
            f"- `{ref['path']}` — {ref['observed_on']}; {ref['scope']} [{ref['status']}] (via `{node_id}`)"
            for node_id, ref in evidence
        )
    else:
        lines.append("- No production evidence selected. Do not make a production claim.")

    lines.extend(["", "## Feature Flags", ""])
    for node in layer_nodes:
        for flag in node["feature_flags"]:
            lines.append(
                f"- `{flag['name']}` — default `{flag['default_state']}`; "
                f"documented: {flag['documented_state']}; scope: {flag['evidence_scope']}"
            )
    if not any(node["feature_flags"] for node in layer_nodes):
        lines.append("- None selected.")

    lines.extend(["", "## Freshness", ""])
    for node in layer_nodes:
        state = freshness[node["id"]]
        lines.append(
            f"- `{node['id']}` verified at `{node['last_verified_commit']}`: "
            f"code_changes={state['code_changes'] or []}; test_changes={state['test_changes'] or []}; "
            f"documentation_changes={state['documentation_changes'] or []}"
        )

    lines.extend(["", "## Traversed Typed Edges", ""])
    if traversed:
        lines.extend(
            f"- `{edge['from']}` --{edge['type']}--> `{edge['to']}`"
            for edge in sorted(
                traversed, key=lambda edge: (edge["from"], edge["type"], edge["to"])
            )
        )
    else:
        lines.append("- No additional allowed edge was traversed.")

    lines.extend(["", "## Do Not Assume", ""])
    lines.extend(f"- {rule}" for rule in SAFETY_RULES)
    if stale_count:
        lines.append("- One or more selected nodes are stale; inspect changed code before coding.")

    lines.extend(["", "## Out of Scope", ""])
    if profile["excluded_areas"]:
        lines.extend(f"- Layer `{item}`." for item in profile["excluded_areas"])
    else:
        lines.append("- No layer exclusion; scope is still limited to cited sources and typed edges.")
    lines.extend(
        [
            "- Runtime wiring, databases, GraphRAG, vector search, MCP, Redis, and LLM calls.",
            "- Treating generated output as durable system or lifecycle state.",
        ]
    )

    source_tokens = _path_char_estimate(catalog.repo_root, docs + evidence)
    lines.extend(
        [
            "",
            "## Quality Metrics",
            "",
            f"- required_layer_coverage: {layer_coverage:.0%}",
            f"- mandatory_authority_coverage: {authority_coverage:.0%}",
            f"- freshness_ratio: {freshness_ratio:.0%} ({stale_count} stale layer nodes)",
            f"- provenance_completeness: {provenance_completeness:.0%}",
            f"- excluded_layer_leakage: {len(leakage)} {leakage}",
            f"- query_match_precision_proxy: {query_precision:.0%}",
            f"- document_budget: {len(docs) + len(evidence)}/{max_documents}",
            "- approximate_char_estimate_budget (chars/4 proxy, NOT a real "
            "tokenizer count — see TOKEN_ESTIMATION_BENCHMARK.md): "
            "__TOKEN_COUNT__/" + str(max_tokens),
            "- referenced_source_to_bundle_char_estimate_savings: __TOKEN_SAVINGS__",
            "",
            "## Selection Manifest",
            "",
            "- deterministic: true",
            "- llm_used: false",
            "- embeddings_used: false",
            "- historical_and_superseded_default_exclusion: true",
            "- automatic_profile_selection: false (use `suggest-profile` for explainable ranking)",
        ]
    )
    template = "\n".join(lines) + "\n"
    token_count = 0
    savings_text = "0%"
    for _ in range(5):
        rendered = template.replace("__TOKEN_COUNT__", str(token_count)).replace(
            "__TOKEN_SAVINGS__", savings_text
        )
        new_token_count = _approximate_char_estimate(rendered)
        savings = (
            0.0
            if source_tokens == 0
            else max(0.0, 1 - new_token_count / source_tokens)
        )
        new_savings_text = f"{savings:.0%}"
        if new_token_count == token_count and new_savings_text == savings_text:
            return rendered
        token_count = new_token_count
        savings_text = new_savings_text
    return template.replace("__TOKEN_COUNT__", str(token_count)).replace(
        "__TOKEN_SAVINGS__", savings_text
    )


def build_bundle(
    catalog: Catalog,
    *,
    task_type: str,
    query: str = "",
    max_tokens: int | None = None,
    max_documents: int | None = None,
    production_claim: bool = False,
    verified_production_evidence: str | None = None,
) -> str:
    if task_type not in catalog.profiles:
        available = ", ".join(sorted(catalog.profiles))
        raise ContextLibrarianError(
            f"unknown task type {task_type!r}; choose one of: {available}"
        )
    profile = catalog.profiles[task_type]
    token_budget = min(
        max_tokens or profile["maximum_approximate_token_budget"],
        profile["maximum_approximate_token_budget"],
    )
    document_budget = min(
        max_documents or profile["maximum_documents"],
        profile["maximum_documents"],
    )
    if token_budget <= 0 or document_budget <= 0:
        raise ContextLibrarianError("token and document budgets must be positive")
    if verified_production_evidence and not production_claim:
        raise ContextLibrarianError(
            "--verified-production-evidence requires --production-claim"
        )

    nodes, roles, traversed = _select_nodes(catalog, profile, query)
    freshness = _freshness(catalog, nodes)
    bundle = _render(
        catalog,
        profile,
        query,
        nodes,
        roles,
        traversed,
        freshness,
        document_budget,
        token_budget,
        production_claim,
        verified_production_evidence,
    )
    actual_tokens = _approximate_char_estimate(bundle)
    if actual_tokens > token_budget:
        raise ContextLibrarianError(
            f"required context needs approximately {actual_tokens} "
            f"chars/4-estimated tokens, exceeding the {token_budget} budget"
        )
    return bundle
