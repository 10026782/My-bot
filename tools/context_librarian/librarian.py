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
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
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
        "last_observed_commit",
        "last_semantic_review_commit",
        "confidence",
        "notes",
        "extensions",
    }
)
# Additive, optional, backward-compatible split introduced alongside
# reconcile.py (see docs/context_librarian/RECONCILIATION.md): existing
# `last_verified_commit` keeps its exact current meaning and writers
# (librarian.refresh_after_merge's --write path, and the local post-merge
# git hook via tools/context_librarian/refresh_after_merge.py --apply) —
# neither is touched by this change. `last_observed_commit` is a purely
# mechanical "last commit the reconcile engine scanned this node against"
# marker, written only by reconcile.py. `last_semantic_review_commit` is
# manual-only — a human explicitly re-examined this node's authority/
# ownership boundary as of that commit; nothing writes it automatically.
_OPTIONAL_COMMIT_FIELDS = ("last_observed_commit", "last_semantic_review_commit")
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
        "bounded_local_expansions",
        "extensions",
    }
)
PROFILE_REQUIRED_FIELDS = PROFILE_FIELDS - {"extensions"}
BOUNDED_LOCAL_EXPANSION_REQUIRED_FIELDS = frozenset({"path", "anchor", "window_lines", "role"})
# אופציונלי, additive, ברירת מחדל True (5.5 של CONSUMPTION_ENFORCEMENT_PLAN.md):
# מסמן אם ההרחבה חובה לפני מסקנה סופית (נצרך ע"י consumption_checklist()).
BOUNDED_LOCAL_EXPANSION_OPTIONAL_FIELDS = frozenset({"required_for_conclusion"})
BOUNDED_LOCAL_EXPANSION_FIELDS = (
    BOUNDED_LOCAL_EXPANSION_REQUIRED_FIELDS | BOUNDED_LOCAL_EXPANSION_OPTIONAL_FIELDS
)
# תקרה קשיחה, לא ברירת מחדל: הרחבה מוגבלת חייבת להישאר חלון-קטע קטן וקבוע-גודל
# סביב anchor שמוגדר ב-profile. זו לא תכונת חיפוש והיא לעולם לא מונעת ע"י
# free-text query, ולכן לא יכולה לגדול מניסוח ה-query (N17 pilot Task 3:
# "query must not inflate context unnecessarily").
MAXIMUM_LOCAL_EXPANSION_WINDOW_LINES = 200
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
    for optional_field in _OPTIONAL_COMMIT_FIELDS:
        if optional_field in node and not re.fullmatch(
            schema["commit_pattern"], str(node[optional_field])
        ):
            raise ContextLibrarianError(f"{label}: invalid {optional_field}")
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
    profile: dict[str, Any],
    edge_types: set[str],
    layer_ids: set[str],
    repo_root: Path,
    label: str,
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
    if not isinstance(profile["bounded_local_expansions"], list):
        raise ContextLibrarianError(f"{label}: bounded_local_expansions must be a list")
    resolved_repo_root = repo_root.resolve()
    for expansion in profile["bounded_local_expansions"]:
        # isinstance נבדק ראשון: set() על ערך שאינו iterable (למשל JSON null)
        # מעלה TypeError גולמי במקום כשל-סגור מבוקר.
        if not isinstance(expansion, dict) or not (
            BOUNDED_LOCAL_EXPANSION_REQUIRED_FIELDS
            <= set(expansion)
            <= BOUNDED_LOCAL_EXPANSION_FIELDS
        ):
            raise ContextLibrarianError(
                f"{label}: bounded_local_expansions entry must be an object with "
                f"exactly {sorted(BOUNDED_LOCAL_EXPANSION_REQUIRED_FIELDS)} and "
                f"optionally {sorted(BOUNDED_LOCAL_EXPANSION_OPTIONAL_FIELDS)}"
            )
        if "required_for_conclusion" in expansion and not isinstance(
            expansion["required_for_conclusion"], bool
        ):
            raise ContextLibrarianError(
                f"{label}: bounded_local_expansions required_for_conclusion must be a bool"
            )
        if not isinstance(expansion["anchor"], str) or not expansion["anchor"]:
            raise ContextLibrarianError(
                f"{label}: bounded_local_expansions anchor must be a non-empty string"
            )
        if not isinstance(expansion["role"], str) or not expansion["role"]:
            raise ContextLibrarianError(
                f"{label}: bounded_local_expansions role must be a non-empty string"
            )
        window_lines = expansion["window_lines"]
        if (
            not isinstance(window_lines, int)
            or isinstance(window_lines, bool)
            or not 0 < window_lines <= MAXIMUM_LOCAL_EXPANSION_WINDOW_LINES
        ):
            raise ContextLibrarianError(
                f"{label}: bounded_local_expansions window_lines must be an int in "
                f"1..{MAXIMUM_LOCAL_EXPANSION_WINDOW_LINES}"
            )
        raw_path = expansion["path"]
        if not isinstance(raw_path, str) or not raw_path:
            raise ContextLibrarianError(
                f"{label}: bounded_local_expansions path must be a non-empty string"
            )
        # Accept both platform spellings so catalog validation has the same
        # result on Windows and POSIX hosts.
        if (
            Path(raw_path).is_absolute()
            or PurePosixPath(raw_path).is_absolute()
            or PureWindowsPath(raw_path).is_absolute()
        ):
            raise ContextLibrarianError(
                f"{label}: bounded_local_expansions path must be relative: {raw_path}"
            )
        # resolve() + relative_to(): חוסם ".." traversal ונתיבים מוחלטים כאחד,
        # כדי ש-_local_expansions() לא יוכל לחשוף קובץ שרירותי מחוץ לריפו.
        resolved_path = (repo_root / raw_path).resolve()
        try:
            resolved_path.relative_to(resolved_repo_root)
        except ValueError:
            raise ContextLibrarianError(
                f"{label}: bounded_local_expansions path escapes repo root: {raw_path}"
            ) from None
        if not resolved_path.exists():
            raise ContextLibrarianError(
                f"{label}: bounded_local_expansions path does not exist: {raw_path}"
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
            profile, edge_types, set(layer_nodes), repo_root, f"profile:{profile_id}"
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
    direct_source_reverified: bool = False,
    verification_ledger: Iterable[str] = (),
    authority_missing: Iterable[str] = (),
    canonical_state_undetermined: Iterable[str] = (),
    stale_authority_runtime_changes: Iterable[str] = (),
    new_authority_sources: Iterable[str] = (),
    authority_changing_unregistered_sources: Iterable[str] = (),
    github_activity: Iterable[str] = (),
) -> dict[str, Any]:
    """Return the manual agent-bootstrap stop decision and its reasons.

    This gate is reported inside a bundle. It deliberately does not prevent a
    stale bundle from being rendered, because agents need the bundle to learn
    what changed and which sources require direct verification.
    """
    stale = sorted(set(stale_node_ids))
    ledger = sorted(set(verification_ledger))
    verified_with_record = direct_source_reverified and bool(ledger)
    conflicts = sorted(set(unresolved_conflicts))
    leakage = sorted(set(excluded_layer_leakage))
    missing = sorted(set(authority_missing))
    undetermined = sorted(set(canonical_state_undetermined))
    stale_runtime = sorted(set(stale_authority_runtime_changes))
    new_authority = sorted(set(new_authority_sources))
    unregistered_authority = sorted(set(authority_changing_unregistered_sources))
    activity = sorted(set(github_activity))
    reasons: list[str] = []
    warnings: list[str] = []
    review_required: list[str] = []
    if missing or mandatory_authority_coverage < 1.0:
        reasons.append("mandatory_authority_incomplete")
    if production_claim and qualifying_production_evidence == 0:
        reasons.append("production_evidence_missing")
    if conflicts:
        reasons.append("unresolved_source_conflict")
    if undetermined:
        reasons.append("canonical_state_undetermined")
    if stale_runtime:
        reasons.append("stale_authority_runtime_change")
    if unregistered_authority:
        reasons.append("unregistered_authority_change")
    if leakage:
        reasons.append("excluded_layer_leakage")
    if stale:
        warnings.append(
            "stale_nodes_after_direct_verification"
            if verified_with_record
            else "stale_nodes"
        )
    if activity:
        warnings.append("github_activity")
    if new_authority:
        review_required.extend(f"new_authority_source:{path}" for path in new_authority)
    if stale and not verified_with_record:
        review_required.append("direct_source_reverification")
    status = "STOP" if reasons else "REVIEW_REQUIRED" if review_required else "WARNING" if warnings else "PROCEED"
    return {
        "status": status,
        "planning_allowed": not reasons,
        "reasons": reasons,
        "warnings": warnings,
        "review_required": sorted(review_required),
        "stale_nodes": stale,
        "direct_source_reverified": direct_source_reverified,
        "verification_ledger": ledger,
        "authority_missing": missing,
        "canonical_state_undetermined": undetermined,
        "stale_authority_runtime_changes": stale_runtime,
        "new_authority_sources": new_authority,
        "unregistered_authority_changes": unregistered_authority,
        "github_activity": activity,
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


def _git_output(repo_root: Path, args: list[str]) -> str:
    """מריצה פקודת git ומחזירה פלט נקי או שגיאת provenance ברורה."""
    try:
        completed = subprocess.run(
            ["git", *args], cwd=repo_root, check=True, capture_output=True,
            text=True, encoding="utf-8"
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContextLibrarianError(f"git {' '.join(args)} failed: {exc}") from exc
    return completed.stdout.strip()


def _catalog_node_files(catalog: Catalog) -> dict[str, Path]:
    """ממפה node לקובץ הקטלוג שמכיל אותו לצורך כתיבה מכנית."""
    result: dict[str, Path] = {}
    paths = sorted((catalog.catalog_root / "layers").glob("*.json"))
    paths.append(catalog.catalog_root / "decisions/canonical_boundaries.json")
    for path in paths:
        data = _load_catalog_json(path)
        for node in data.get("nodes", []):
            result[node["id"]] = path
    return result


def _catalog_referenced_paths(catalog: Catalog) -> set[str]:
    """מחזירה את כל הנתיבים שכבר רשומים במקורות הקטלוג."""
    paths: set[str] = set()
    for node in catalog.nodes.values():
        paths.update(node["code_paths"])
        paths.update(node["test_paths"])
        paths.update(ref["path"] for ref in node["canonical_docs"])
        paths.update(ref["path"] for ref in node["production_evidence"])
    # Catalog files are the Librarian's own metadata infrastructure. They are
    # registered by the catalog loader itself, not by a domain node's
    # code_paths/canonical_docs. Treating them as unregistered domain sources
    # would turn every catalog file into a false authority STOP.
    catalog_files = sorted((catalog.catalog_root / "layers").glob("*.json"))
    catalog_files.append(catalog.catalog_root / "decisions/canonical_boundaries.json")
    paths.update(
        str(path.relative_to(catalog.repo_root)).replace("\\", "/")
        for path in catalog_files
    )
    # These files are the Librarian's own versioned infrastructure rather than
    # domain sources. Keep the list explicit so a genuinely new tooling file
    # still reaches source discovery for review instead of being auto-accepted.
    paths.update(
        {
            ".githooks/post-merge",
            "docs/context_librarian/generated/.gitkeep",
            "docs/context_librarian/schema/edge_schema.json",
            "docs/context_librarian/schema/node_schema.json",
            "docs/context_librarian/schema/policy_schema.json",
            "docs/context_librarian/task_profiles/profiles.json",
            "docs/context_librarian/policies/policy_registry.json",
            "docs/context_librarian/reconciliation_state.json",
            "tools/context_librarian/__init__.py",
            "tools/context_librarian/__main__.py",
            "tools/context_librarian/benchmark_token_estimate.py",
            "tools/context_librarian/librarian.py",
            "tools/context_librarian/local_post_merge_check.sh",
            "tools/context_librarian/manage_hooks.py",
            "tools/context_librarian/owner_decision_report.py",
            "tools/context_librarian/pilot_preflight.py",
            "tools/context_librarian/refresh_after_merge.py",
            "tools/context_librarian/policy_registry.py",
            "tools/context_librarian/policy_validators.py",
            "tools/context_librarian/reconcile.py",
            "tools/context_librarian/reconciliation_state.py",
            ".github/workflows/context-librarian-reconcile.yml",
        }
    )
    return {path.replace("\\", "/") for path in paths}


_AUTHORITY_TERMS = frozenset({
    "authority", "approval", "action_contract", "action_gateway", "ownership",
    "queue", "evidence", "canonical", "source_of_truth",
})


def _is_consumption_ledger_artifact(catalog: Catalog, raw_path: str) -> bool:
    """קובץ JSON שמכיל את כל שדות ה-ledger הקנוניים (LEDGER_TOP_LEVEL_REQUIRED_FIELDS,
    למטה) הוא פלט שנוצר ע"י verify-consumption/pilot_preflight — ראיית consumption/
    governance (ומפורשות לא production: הוא כולל תמיד "production_claim"), לא קוד
    ולא production evidence. בודקת מבנה בפועל ולא רק שם קובץ, כך שקובץ אחר עם
    "ledger"/"approval" בשם אך בלי המבנה הזה עדיין ייתפס כרגיל (STOP/REVIEW_REQUIRED),
    וקובץ עם המבנה הזה ייתפס גם אם שמו לא מרמז עליו."""
    full_path = catalog.repo_root / raw_path
    try:
        data = json.loads(full_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and LEDGER_TOP_LEVEL_REQUIRED_FIELDS <= set(data)


_NON_BLOCKING_NEW_SOURCE_CLASSIFICATIONS = frozenset({"WARNING", "GOVERNANCE_ARTIFACT"})


def classify_new_sources(
    catalog: Catalog, paths: Iterable[str]
) -> list[dict[str, str]]:
    """מסווגת קבצים לא-רשומים בלי לרשום אוטומטית את משמעותם."""
    registered = _catalog_referenced_paths(catalog)
    result: list[dict[str, str]] = []
    for raw_path in sorted({path.replace("\\", "/") for path in paths} - registered):
        lower = raw_path.casefold()
        name = PurePosixPath(lower).name
        if lower.endswith(".json") and _is_consumption_ledger_artifact(catalog, raw_path):
            result.append({
                "path": raw_path,
                "classification": "GOVERNANCE_ARTIFACT",
                "reason": (
                    "generated Context Librarian consumption ledger — governance/"
                    "review evidence, not a runtime or production source; no layer "
                    "classification required"
                ),
            })
            continue
        if name.startswith("test_") or "/test" in lower or lower.startswith("test"):
            classification, reason = "WARNING", "new test source"
        elif lower.endswith((".md", ".rst", ".txt")) or any(
            term in lower for term in ("changelog", "audit", "planning")
        ):
            classification, reason = "WARNING", "new documentation/audit/planning source"
        elif lower.endswith((".py", ".js", ".ts", ".tsx")):
            classification, reason = "REVIEW_REQUIRED", "new runtime source"
        elif lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp")):
            # Raster images are inert binary assets — they cannot carry
            # dispatch/approval/authority logic, so a path-substring hit on
            # an _AUTHORITY_TERMS word (e.g. a directory literally named
            # "reference-evidence") is a naming coincidence, not a real
            # authority signal. Treat like docs: non-blocking, never STOP.
            classification, reason = "WARNING", "new image/asset source"
        else:
            classification, reason = "REVIEW_REQUIRED", "new source with unknown role"
        if classification != "WARNING" and any(term in name or term in lower for term in _AUTHORITY_TERMS):
            classification, reason = "STOP", "unregistered source may change authority"
        result.append({"path": raw_path, "classification": classification, "reason": reason})
    return result


def discover_new_sources(
    catalog: Catalog, *, changed_paths: Iterable[str] | None = None,
    main_ref: str = "origin/main"
) -> list[dict[str, str]]:
    """מזהה קבצים חדשים מאז עוגן ה-refresh הקנוני ומסווגת אותם לבדיקה."""
    if changed_paths is None:
        main_sha = _git_output(catalog.repo_root, ["rev-parse", "--verify", main_ref])
        anchors = sorted({
            node["last_verified_commit"]
            for node in catalog.nodes.values()
            if node.get("last_verified_commit")
        })
        base = (
            _git_output(catalog.repo_root, ["merge-base", "--octopus", *anchors])
            if anchors
            else _git_output(catalog.repo_root, ["rev-parse", f"{main_sha}^"])
        )
        changed_paths = _git_output(
            catalog.repo_root, ["diff", "--diff-filter=A", "--name-only", base, main_sha]
        ).splitlines()
    return classify_new_sources(catalog, changed_paths)


def _node_changed_between(catalog: Catalog, node: dict[str, Any], main_sha: str) -> set[str]:
    old = node["last_verified_commit"]
    if old == main_sha:
        changed = set()
    else:
        changed = set(_git_output(catalog.repo_root, ["diff", "--name-only", old, main_sha]).splitlines())
    tracked = (
        node["code_paths"] + node["test_paths"]
        + [ref["path"] for ref in node["canonical_docs"]]
        + [ref["path"] for ref in node["production_evidence"]]
    )
    return {path for path in changed if any(_matches_tracked_path(path, item) for item in tracked)}


def refresh_proposal(catalog: Catalog, *, main_ref: str = "origin/main") -> dict[str, Any]:
    """מחשבת הצעת refresh מכנית מול SHA קנוני של main."""
    main_sha = _git_output(catalog.repo_root, ["rev-parse", "--verify", main_ref])
    updates: list[dict[str, Any]] = []
    for node in sorted(catalog.nodes.values(), key=lambda item: item["id"]):
        changed = sorted(_node_changed_between(catalog, node, main_sha))
        if changed:
            updates.append({
                "node_id": node["id"],
                "from": node["last_verified_commit"],
                "to": main_sha,
                "changed_paths": changed,
            })
    new_sources = discover_new_sources(catalog, main_ref=main_ref)
    has_blocking_new_sources = any(
        item["classification"] not in _NON_BLOCKING_NEW_SOURCE_CLASSIFICATIONS
        for item in new_sources
    )
    status = (
        "CHANGES_REQUIRED"
        if updates or has_blocking_new_sources
        else "WARNING"
        if new_sources
        else "OK"
    )
    return {
        "status": status,
        "main_ref": main_ref,
        "canonical_main_sha": main_sha,
        "updates": updates,
        "new_sources": new_sources,
        "authority_review_required": any(
            item["classification"] not in _NON_BLOCKING_NEW_SOURCE_CLASSIFICATIONS
            for item in new_sources
        ),
    }


def refresh_after_merge(
    catalog: Catalog, *, main_ref: str = "origin/main", write: bool = False
) -> dict[str, Any]:
    """מיישמת רק עדכוני provenance מכניים; סיווג authority נשאר לבדיקה."""
    proposal = refresh_proposal(catalog, main_ref=main_ref)
    if not write or proposal["status"] == "OK":
        return proposal
    live = _git_provenance(catalog.repo_root)
    if live["branch"] != "main" or live["commit"] != proposal["canonical_main_sha"]:
        raise ContextLibrarianError(
            "refresh write requires checkout branch main at the canonical main SHA; "
            "local hooks are advisory and must not write branch provenance"
        )
    files = _catalog_node_files(catalog)
    original: dict[Path, str] = {}
    data_by_file: dict[Path, dict[str, Any]] = {}
    for update in proposal["updates"]:
        path = files[update["node_id"]]
        if path not in data_by_file:
            original[path] = path.read_text(encoding="utf-8")
            data_by_file[path] = _load_catalog_json(path)
        for node in data_by_file[path]["nodes"]:
            if node["id"] == update["node_id"]:
                node["last_verified_commit"] = proposal["canonical_main_sha"]
    try:
        for path, data in data_by_file.items():
            payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
                handle.write(payload)
                temporary = Path(handle.name)
            os.replace(temporary, path)
        load_catalog(catalog.repo_root)
    except Exception:
        for path, text in original.items():
            path.write_text(text, encoding="utf-8", newline="\n")
        raise
    proposal["status"] = "REFRESHED"
    return proposal


_MAIN_REF_CANDIDATES = ("origin/main", "main")


def _git_provenance(repo_root: Path) -> dict[str, str]:
    """מדווח את ה-commit/branch המדויקים שמהם נבנה bundle, והאם ה-commit הזה
    הגיע בפועל ל-`main` — לעולם לא בהנחה משם branch או ממי שכותב על ה-bundle
    בדיעבד.

    מתקן את הממצא ה-Critical של פיילוט N17 מ-28/07/2026: bundle שנבנה מענף
    לא-ממוזג (`17b0a67`, קיים רק על `claude/context-librarian-non-inferiority-pilot`)
    תואר ב-review packet כמשקף את `main` ב-`ffa678a7`. `on_main` הוא "yes"
    רק כאשר ה-commit הבנוי מוכח כ-ancestor של (או שווה ל-) `main` ref שניתן
    לפתור; "no" כאשר מוכח שאינו כזה; "unknown" כאשר אף אחד מהשניים לא ניתן
    לקביעה (למשל אין `origin` remote מוגדר) — "unknown" לעולם לא מטופל כ-
    "yes" ע"י הקוראים.
    """

    def _run(args: list[str]) -> tuple[int, str]:
        try:
            completed = subprocess.run(
                args, cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
            )
        except OSError:
            return 1, ""
        return completed.returncode, completed.stdout.strip()

    commit_code, commit = _run(["git", "rev-parse", "HEAD"])
    if commit_code != 0 or not commit:
        return {
            "commit": "unknown",
            "branch": "unknown",
            "on_main": "unknown",
            "on_main_history": "unknown",
            "at_origin_main_tip": "unknown",
        }
    branch_code, branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch if branch_code == 0 and branch else "unknown"

    origin_main_code, origin_main = _run(
        ["git", "rev-parse", "--verify", "--quiet", "origin/main"]
    )
    at_origin_main_tip = (
        "yes" if origin_main_code == 0 and commit == origin_main else "no"
        if origin_main_code == 0
        else "unknown"
    )

    on_main_history = "unknown"
    for main_ref in _MAIN_REF_CANDIDATES:
        ref_code, _ = _run(["git", "rev-parse", "--verify", "--quiet", main_ref])
        if ref_code != 0:
            continue
        ancestor_code, _ = _run(["git", "merge-base", "--is-ancestor", commit, main_ref])
        on_main_history = "yes" if ancestor_code == 0 else "no"
        break
    return {
        "commit": commit,
        "branch": branch,
        # Backward-compatible alias retained for existing callers/bundles.
        "on_main": on_main_history,
        "on_main_history": on_main_history,
        "at_origin_main_tip": at_origin_main_tip,
    }


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
    nodes: list[dict[str, Any]], field: str
) -> list[tuple[str, dict[str, Any]]]:
    """מחזירה את כל המקורות בסדר round-robin דטרמיניסטי.

    אכיפת תקציב שייכת ל-``build_bundle``; הפונקציה אינה משמיטה מקור בשקט.
    """
    result: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    depth = 0
    while True:
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
        if not added and all(
            depth >= len(
                [
                    ref
                    for ref in node[field]
                    if field != "canonical_docs"
                    or ref.get("status") not in DEFAULT_EXCLUDED_STATUSES
                ]
            ) - 1
            for node in nodes
        ):
            break
        depth += 1
    return result


def _local_expansions(
    repo_root: Path, profile: dict[str, Any]
) -> list[dict[str, Any]]:
    """חלונות-קטע דטרמיניסטיים, מוגדרי-profile, סביב anchor קבוע.

    בניגוד לכל מה ש-_select_nodes()/_render() מושכים בדרך כלל, זו לא הפניה
    לנתיב-קובץ שהסוכן צריך לפתוח בנפרד — החלון המותאם משוקע ישירות בתוך ה-
    bundle. הפונקציה קיימת עבור מצב-הכשל הספציפי שפיילוט N17 מ-28/07/2026
    מצא ב-`turn_coordinator_routing`: באג (BUG-140) שיושב מרחק קצר מתחת לבאג
    אחר (BUG-130) באותו קובץ-לוג גדול שהחקירה כבר פתחה, אך לא נקרא עד שם.
    ההרחבה מוגדרת-profile, לא query-driven, ומוגבלת-קשיח ע"י `window_lines`
    (<= MAXIMUM_LOCAL_EXPANSION_WINDOW_LINES) — ניסוח query חופשי לא יכול
    לגדל או להפעיל את הסעיף הזה, ולכן לא יכול לנפח context בדרך שהרחבה
    לא-מוגבלת ומונעת-query הייתה יכולה.
    """
    results: list[dict[str, Any]] = []
    for expansion in profile["bounded_local_expansions"]:
        path = repo_root / expansion["path"]
        try:
            source_lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise ContextLibrarianError(
                f"cannot read bounded_local_expansions path {expansion['path']}: {exc}"
            ) from exc
        anchor = expansion["anchor"]
        match_index = next(
            (index for index, line in enumerate(source_lines) if anchor in line),
            None,
        )
        if match_index is None:
            raise ContextLibrarianError(
                f"bounded_local_expansions anchor {anchor!r} not found in "
                f"{expansion['path']}; the profile is stale — update or remove "
                "this entry rather than let it silently stop expanding"
            )
        window = source_lines[match_index : match_index + expansion["window_lines"]]
        results.append(
            {
                "path": expansion["path"],
                "anchor": anchor,
                "matched_line": match_index + 1,
                "role": expansion["role"],
                "excerpt": "\n".join(window),
            }
        )
    return results


def consumption_checklist(
    catalog: Catalog, profile: dict[str, Any], production_claim: bool = False
) -> list[str]:
    """Mandatory-tier item ids for this profile (CONSUMPTION_ENFORCEMENT_PLAN.md 5.1).

    Deliberately narrower than everything `_select_nodes()` may pull into a
    bundle: only primary/required-dependency layers, mandatory canonical
    decisions, and expansions marked `required_for_conclusion` are mandatory.
    `optional_evidence`/`conditional_optional_evidence` stay query-triggered
    and advisory — they are never added here, so the checklist cannot grow
    the bundle or force reading of non-material sources.
    """
    mandatory_layer_names = dict.fromkeys(
        list(profile["primary_layers"]) + list(profile["required_dependency_layers"])
    )
    layer_nodes = [
        catalog.nodes[catalog.layer_nodes[name]]
        for name in mandatory_layer_names
        if name in catalog.layer_nodes
    ]
    decision_nodes = [
        catalog.nodes[f"decision.{decision}"]
        for decision in profile["mandatory_canonical_decisions"]
        if f"decision.{decision}" in catalog.nodes
    ]

    def _current_docs(node: dict[str, Any]) -> list[str]:
        # Mirrors _unique_references()'s own historical/superseded exclusion —
        # a superseded document is not mandatory reading, it is why the
        # bundle excludes it everywhere else too.
        return [
            ref["path"]
            for ref in node["canonical_docs"]
            if ref.get("status") not in DEFAULT_EXCLUDED_STATUSES
        ]

    items: set[str] = set()
    for node in layer_nodes:
        items.update(f"code:{path}" for path in node["code_paths"])
        items.update(f"test:{path}" for path in node["test_paths"])
        items.update(f"doc:{path}" for path in _current_docs(node))
        if production_claim:
            items.update(f"evidence:{ref['path']}" for ref in node["production_evidence"])
    for node in decision_nodes:
        items.update(f"doc:{path}" for path in _current_docs(node))
    items.update(
        f"decision:{decision}" for decision in profile["mandatory_canonical_decisions"]
    )
    for expansion in profile["bounded_local_expansions"]:
        if expansion.get("required_for_conclusion", True):
            items.add(f"expansion:{expansion['path']}#{expansion['anchor']}")
    return sorted(items)


REVIEW_RECEIPT_REQUIRED_FIELDS = frozenset(
    {
        "item_id",
        "path",
        "commit",
        "branch",
        "profile",
        "query",
        "reviewed_by",
        "reviewed_at",
        "reason",
        "evidence_reference",
    }
)
WAIVED_SOURCE_REQUIRED_FIELDS = REVIEW_RECEIPT_REQUIRED_FIELDS | {
    "approved_by",
    "approved_at",
}
LEDGER_TOP_LEVEL_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "task_type",
        "profile",
        "query",
        "production_claim",
        "bundle_generated_commit",
        "bundle_generated_branch",
        "required_sources",
        "review_receipts",
        "waived_sources",
    }
)
# Fields whose only requirement is "present and a non-empty string" — every
# required field except item_id/path, which get their own dedicated checks
# (item_id against required_sources, path against item_id).
_ATTRIBUTION_STRING_FIELDS = frozenset(
    {
        "commit",
        "branch",
        "profile",
        "query",
        "reviewed_by",
        "reviewed_at",
        "approved_by",
        "approved_at",
    }
)


def _expected_path_for_item(item_id: str) -> str | None:
    """The path implied by an item id — the single source of truth a
    receipt's own `path` field must agree with, so a receipt cannot claim
    review of one item while its evidence actually points at another file.
    """
    prefix, _, rest = item_id.partition(":")
    if prefix == "decision":
        return None
    if prefix == "expansion":
        return rest.partition("#")[0]
    return rest
# case-insensitive, stripped — a "placeholder-looking" waiver reason (5.3) is
# rejected the same as an empty one; this is a small, explicit denylist, not
# an attempt at general prose-quality detection.
_PLACEHOLDER_REASON_STRINGS = frozenset(
    {"todo", "tbd", "n/a", "na", "placeholder", "...", "-", "reason", "waived", "skip"}
)


def _looks_like_placeholder_reason(reason: str) -> bool:
    return reason.strip().casefold() in _PLACEHOLDER_REASON_STRINGS


@dataclass(frozen=True)
class ConsumptionVerificationResult:
    status: str
    exit_code: int
    blocked_reasons: tuple[str, ...]
    unreviewed_sources: tuple[str, ...]
    warnings: tuple[str, ...]


def _validate_ledger_entry(
    entry: Any,
    required_fields: frozenset[str],
    ledger: dict[str, Any],
    kind: str,
    required_sources: set[str],
    reasons: list[str],
) -> tuple[str | None, bool]:
    if not isinstance(entry, dict):
        reasons.append(f"{kind} entry must be an object")
        return None, False
    item_id = entry.get("item_id")
    missing = sorted(required_fields - set(entry))
    extra = sorted(set(entry) - required_fields)
    if missing:
        reasons.append(
            f"{kind} entry {item_id or '<missing item_id>'} missing fields: "
            f"{', '.join(missing)}"
        )
    if extra:
        reasons.append(
            f"{kind} entry {item_id or '<missing item_id>'} has unknown fields: "
            f"{', '.join(extra)}"
        )
    if missing or extra:
        return item_id, False

    valid = True
    if not isinstance(item_id, str) or item_id not in required_sources:
        reasons.append(
            f"{kind} entry has item_id {item_id!r}, which is not in this "
            "profile+query's mandatory tier (required_sources) right now"
        )
        # No expected path to check against an unrecognised item_id — bail
        # out of this entry's remaining checks, it cannot be counted anyway.
        return item_id, False

    expected_path = _expected_path_for_item(item_id)
    if entry["path"] != expected_path:
        reasons.append(
            f"{kind} entry {item_id} has path {entry['path']!r}, expected "
            f"{expected_path!r} (path must match the item_id it claims to review)"
        )
        valid = False

    for field in ("reason", "evidence_reference"):
        if not isinstance(entry[field], str):
            reasons.append(f"{kind} entry {item_id} {field} must be a string")
            valid = False
        elif not entry[field].strip():
            reasons.append(f"{kind} entry {item_id} has empty {field}")
            valid = False
    for field in sorted(_ATTRIBUTION_STRING_FIELDS & required_fields):
        if not isinstance(entry[field], str) or not entry[field].strip():
            reasons.append(f"{kind} entry {item_id} {field} must be a non-empty string")
            valid = False
    if not valid:
        # reason/evidence_reference are used as a dict key below (duplicate
        # detection) — a non-string value (e.g. a list) is unhashable, so a
        # malformed entry must be rejected here, before it can reach that.
        return item_id, False
    if (
        kind == "waived_sources"
        and entry["reason"].strip()
        and _looks_like_placeholder_reason(entry["reason"])
    ):
        reasons.append(f"{kind} entry {item_id} has a placeholder-looking reason")
        valid = False

    entry_identity = (
        entry["commit"],
        entry["branch"],
        entry["profile"],
        _normalise_query(entry["query"]),
    )
    top_identity = (
        ledger["bundle_generated_commit"],
        ledger["bundle_generated_branch"],
        ledger["profile"],
        _normalise_query(ledger["query"]),
    )
    if entry_identity != top_identity:
        reasons.append(
            f"{kind} entry {item_id} identity (commit/branch/profile/query) does not "
            "match the ledger's own top-level identity"
        )
        valid = False

    if kind == "waived_sources" and entry["approved_by"] == entry["reviewed_by"]:
        reasons.append(
            f"waived_sources entry {item_id} is self-approved "
            "(approved_by equals reviewed_by; independent approval is required)"
        )
        valid = False

    return item_id, valid


def verify_consumption(
    catalog: Catalog,
    *,
    task_type: str,
    query: str,
    ledger: dict[str, Any],
    production_claim: bool = False,
) -> ConsumptionVerificationResult:
    """Fail-closed check: every mandatory-tier item is reviewed or waived.

    Proves accounting completeness only — that every `consumption_checklist()`
    item has a `review_receipts`/`waived_sources` entry with a genuine,
    live-matching identity — never comprehension or correctness (Section 4/
    9 of CONSUMPTION_ENFORCEMENT_PLAN.md). `unreviewed_sources` and pass/fail
    are always computed here, never accepted from the ledger itself.
    """
    if task_type not in catalog.profiles:
        available = ", ".join(sorted(catalog.profiles))
        raise ContextLibrarianError(
            f"unknown task type {task_type!r}; choose one of: {available}"
        )
    profile = catalog.profiles[task_type]

    if not isinstance(ledger, dict):
        raise ContextLibrarianError("ledger must be a JSON object")
    missing_top = sorted(LEDGER_TOP_LEVEL_REQUIRED_FIELDS - set(ledger))
    forged = sorted(set(ledger) - LEDGER_TOP_LEVEL_REQUIRED_FIELDS)
    if missing_top:
        raise ContextLibrarianError(
            f"ledger missing top-level fields: {', '.join(missing_top)}"
        )
    if forged:
        raise ContextLibrarianError(
            "ledger has forged/unknown top-level fields (unreviewed_sources and "
            f"any pass/fail field must never be written by hand): {', '.join(forged)}"
        )
    for field in ("required_sources", "review_receipts", "waived_sources"):
        if not isinstance(ledger[field], list):
            raise ContextLibrarianError(f"ledger {field} must be a list")

    reasons: list[str] = []
    warnings: list[str] = []

    live = _git_provenance(catalog.repo_root)
    declared_production_claim = ledger.get("production_claim")
    if not isinstance(declared_production_claim, bool):
        reasons.append("ledger production_claim must be a boolean")
    elif declared_production_claim != production_claim:
        reasons.append(
            f"ledger production_claim ({declared_production_claim}) does not match "
            f"the --production-claim this verification was run with ({production_claim}) "
            "— a ledger authored for a production claim must be verified with "
            "--production-claim, and vice versa, or evidence review can be silently "
            "skipped"
        )
    top_identity_ok = (
        ledger["bundle_generated_commit"] == live["commit"]
        and ledger["bundle_generated_branch"] == live["branch"]
        and ledger["profile"] == task_type
        and ledger["task_type"] == task_type
        and _normalise_query(ledger["query"]) == _normalise_query(query)
    )
    if not top_identity_ok:
        reasons.append(
            "ledger top-level identity (commit/branch/profile/query) does not "
            "match a bundle recomputable right now for this exact profile+query "
            "— treat this the same as an expired waiver"
        )

    required_sources = consumption_checklist(catalog, profile, production_claim=production_claim)
    required_sources_set = set(required_sources)

    declared_required = ledger["required_sources"]
    if not all(isinstance(item, str) for item in declared_required):
        reasons.append("ledger required_sources must be a list of strings")
    elif set(declared_required) != required_sources_set:
        reasons.append(
            "ledger required_sources does not match the live-recomputed mandatory "
            f"tier for this profile+query: missing_from_ledger="
            f"{sorted(required_sources_set - set(declared_required))}, "
            f"extra_in_ledger={sorted(set(declared_required) - required_sources_set)}"
        )

    all_entries = list(ledger["review_receipts"]) + list(ledger["waived_sources"])
    item_id_counts: dict[str, int] = {}
    for entry in all_entries:
        if isinstance(entry, dict) and isinstance(entry.get("item_id"), str):
            item_id_counts[entry["item_id"]] = item_id_counts.get(entry["item_id"], 0) + 1
    duplicated_item_ids = {item_id for item_id, count in item_id_counts.items() if count > 1}
    if duplicated_item_ids:
        reasons.append(
            "item_id appears in more than one review_receipts/waived_sources entry "
            f"combined (exactly one entry per item is required): "
            f"{sorted(duplicated_item_ids)}"
        )

    accounted_ids: set[str] = set()
    duplicate_groups: dict[tuple[str, str], list[str]] = {}
    for entry in ledger["review_receipts"]:
        item_id, valid = _validate_ledger_entry(
            entry, REVIEW_RECEIPT_REQUIRED_FIELDS, ledger, "review_receipts",
            required_sources_set, reasons,
        )
        if valid and item_id and item_id not in duplicated_item_ids:
            accounted_ids.add(item_id)
            duplicate_groups.setdefault(
                (entry["reason"], entry["evidence_reference"]), []
            ).append(item_id)
    for entry in ledger["waived_sources"]:
        item_id, valid = _validate_ledger_entry(
            entry, WAIVED_SOURCE_REQUIRED_FIELDS, ledger, "waived_sources",
            required_sources_set, reasons,
        )
        if valid and item_id and item_id not in duplicated_item_ids:
            accounted_ids.add(item_id)
            duplicate_groups.setdefault(
                (entry["reason"], entry["evidence_reference"]), []
            ).append(item_id)

    unreviewed = sorted(required_sources_set - accounted_ids)
    if unreviewed:
        reasons.append(f"unreviewed_sources: {unreviewed}")

    for item_ids in duplicate_groups.values():
        if len(item_ids) > 1:
            warnings.append(
                "duplicate reason/evidence_reference across items: "
                f"{sorted(item_ids)} — verify these are genuinely distinct reviews"
            )

    if reasons:
        return ConsumptionVerificationResult(
            status="CONCLUSION_BLOCKED",
            exit_code=2,
            blocked_reasons=tuple(reasons),
            unreviewed_sources=tuple(unreviewed),
            warnings=tuple(warnings),
        )
    return ConsumptionVerificationResult(
        status="CONSUMPTION: COMPLETE",
        exit_code=0,
        blocked_reasons=(),
        unreviewed_sources=(),
        warnings=tuple(warnings),
    )


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
    git_provenance: dict[str, str],
    expansions: list[dict[str, Any]],
    direct_source_reverified: bool,
    verification_ledger: Iterable[str],
) -> str:
    decision_nodes = [node for node in nodes if node["type"] == "decision"]
    layer_nodes = [node for node in nodes if node["type"] == "layer"]
    docs = _unique_references(nodes, "canonical_docs")
    evidence = _unique_references(layer_nodes, "production_evidence")

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
        direct_source_reverified=direct_source_reverified,
        verification_ledger=verification_ledger,
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

    on_main = git_provenance.get(
        "on_main_history", git_provenance.get("on_main", "unknown")
    )
    at_origin_main_tip = git_provenance.get("at_origin_main_tip", "unknown")
    lines: list[str] = [
        f"# BOSS Context Bundle — {profile['id']}",
        "",
        f"Query: {query or '(none)'}",
        f"Profile: {profile['description']}",
        "Authority: navigation metadata only; inspect cited sources before coding.",
        "",
        "## Bundle Provenance",
        "",
        f"- generated_commit: `{git_provenance['commit']}`",
        f"- generated_branch: `{git_provenance['branch']}`",
        f"- on_main_history: {on_main}",
        f"- at_origin_main_tip: {at_origin_main_tip}",
    ]
    if on_main != "yes":
        lines.append("- WARNING: commit is not proven on `main`; cite generated_commit/branch.")
    elif at_origin_main_tip == "no":
        lines.append(
            "- WARNING: this commit is in `origin/main` history but is not the "
            "local `origin/main` tip; do not describe this bundle as reflecting "
            "the latest origin/main state."
        )
    lines.extend(
        [
            "",
            "## Agent Consumption Contract",
            "",
            "Use an explicit profile and inspect cited sources; stop only on STOP.",
            "Contract: `docs/context_librarian/AGENT_CONSUMPTION_CONTRACT.md`",
            "",
            "## Consumption Checklist",
            "",
            "Mandatory-tier sources (primary/required-dependency code and tests, "
            "mandatory canonical documents and decisions, expansions marked "
            "`required_for_conclusion`, and production evidence only when a "
            "production claim is made) that must be reviewed or explicitly "
            "waived — with independent-reviewer approval — before a final "
            "conclusion. Verify with `verify-consumption`; see "
            "`docs/context_librarian/AGENT_CONSUMPTION_CONTRACT.md`.",
            "",
        ]
    )
    checklist_items = consumption_checklist(catalog, profile, production_claim)
    if checklist_items:
        lines.extend(f"- `{item_id}`" for item_id in checklist_items)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Agent Workflow Gate",
            "",
            f"- status: {workflow_gate['status']}",
            f"- reasons: {workflow_gate['reasons']}",
            f"- verification_ledger: {workflow_gate['verification_ledger']}",
            f"- stale_nodes: {len(stale_node_ids)} {stale_node_ids}",
            f"- mandatory_authority_coverage: {authority_coverage:.0%}",
            f"- production_claim: {str(production_claim).lower()}",
            f"- verified_production_evidence: {verified_production_evidence or 'none'}",
            f"- qualifying_production_evidence: {qualifying_evidence}",
            f"- unresolved_source_conflicts: {len(conflict_edges)} {conflict_edges}",
            f"- excluded_layer_leakage: {len(leakage)} {leakage}",
            "- STOP blocks planning/code changes; stale alone is not STOP.",
            "",
            "## Canonical Decisions",
            "",
        ]
    )
    for node in decision_nodes:
        notes = iter(node["notes"])
        first_note = next(notes)
        lines.append(f"- `{node['id']}` — {node['name']}: {first_note}")
        lines.extend(f"    - {extra_note}" for extra_note in notes)

    lines.extend(["", "## Selected Layers", ""])
    for node in layer_nodes:
        layer_id = node["id"].split(".", 1)[1]
        fresh = freshness[node["id"]]
        stale_label = "STALE: code changed" if fresh["stale"] else "fresh against tracked code"
        notes = iter(node["notes"])
        first_note = next(notes)
        lines.append(
            f"- `{layer_id}` ({roles[layer_id]}, {node['status']}, {stale_label}) — {first_note}"
        )
        lines.extend(f"    - {extra_note}" for extra_note in notes)

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
            code_reference = (
                f"; code: `{flag['code_reference']}`"
                if flag.get("code_reference")
                else ""
            )
            lines.append(
                f"- `{flag['name']}` — default `{flag['default_state']}`; "
                f"documented: {flag['documented_state']}; scope: {flag['evidence_scope']}"
                f"{code_reference}"
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

    lines.extend(["", "## Local Context Expansion", ""])
    if expansions:
        lines.append(
            "Deterministic, profile-defined excerpt windows around a fixed "
            "anchor — bounded by `window_lines`, not query-driven, so "
            "free-text query wording cannot grow or trigger this section."
        )
        for item in expansions:
            lines.append(
                f"- `{item['path']}` around {item['anchor']!r} "
                f"(matched at line {item['matched_line']}, {item['role']}):"
            )
            lines.extend(f"    {excerpt_line}" for excerpt_line in item["excerpt"].splitlines())
    else:
        lines.append("- None configured for this profile.")

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


def _budget_breakdown(
    nodes: list[dict[str, Any]],
    docs: list[tuple[str, dict[str, Any]]],
    evidence: list[tuple[str, dict[str, Any]]],
) -> list[str]:
    """מתארת את metadata של המועמד לפי node ומקור לצורך breakdown."""
    breakdown: list[str] = []
    for node in nodes:
        metadata = "\n".join(
            [*node["notes"], *node["code_paths"], *node["test_paths"]]
        )
        if metadata:
            breakdown.append(
                f"{node['id']} (metadata): {_approximate_char_estimate(metadata)}"
            )
    for node_id, reference in [*docs, *evidence]:
        source = reference["path"]
        breakdown.append(
            f"{node_id} -> {source}: {_approximate_char_estimate(source)}"
        )
    return sorted(breakdown)


def _format_budget_overflow(
    *, estimated_tokens: int, budget: int, breakdown: list[str]
) -> str:
    overflow = estimated_tokens - budget
    details = "\n".join(f"  - {item} estimated tokens" for item in breakdown)
    return (
        "context budget overflow: "
        f"estimated_tokens={estimated_tokens}, budget={budget}, overflow={overflow}\n"
        "breakdown by node/source:\n"
        f"{details}"
    )


def _format_document_overflow(
    *,
    estimated_tokens: int,
    token_budget: int,
    selected_documents: int,
    budget: int,
    references: list[tuple[str, dict[str, Any]]],
    breakdown: list[str],
) -> str:
    sources = ", ".join(
        f"{node_id}:{reference['path']}" for node_id, reference in references
    )
    details = "\n".join(f"  - {item} estimated tokens" for item in breakdown)
    return (
        "context document budget overflow: "
        f"estimated_tokens={estimated_tokens}, budget={token_budget}, "
        f"overflow={estimated_tokens - token_budget}; "
        f"selected_documents={selected_documents}, budget={budget}, "
        f"overflow={selected_documents - budget}; no source was omitted; "
        f"sources={sources}\n"
        "breakdown by node/source:\n"
        f"{details}"
    )


def _build_bundle_unchecked(
    catalog: Catalog,
    *,
    task_type: str,
    query: str,
    max_tokens: int | None,
    max_documents: int | None,
    production_claim: bool,
    verified_production_evidence: str | None,
    assert_main: bool,
    assert_on_main_history: bool,
    assert_at_origin_main_tip: bool,
    direct_source_reverified: bool = False,
    verification_ledger: Iterable[str] = (),
) -> tuple[str, int, int, list[str], int, int, list[tuple[str, dict[str, Any]]]]:
    """הליבה המשותפת של `build_bundle()`/`estimate_bundle()`: מאמתת קלט,
    פותרת git provenance, בוחרת nodes, ומרנדרת את טקסט ה-bundle.

    מחזירה bundle, מדדי token/document ו-breakdown בלי לבדוק אם
    `actual_tokens` נכנס בתוך `token_budget` — ההחלטה הזו (לזרוק שגיאה
    או לדווח) שייכת לקורא, לעולם לא לפונקציה הזו. כל כשל אחר כאן (task
    type לא ידוע, תקציבים לא-חוקיים, git provenance שלא הוכח כשנדרש)
    הוא שגיאת קלט/מבנה, לא שאלת תקציב, וזורק שגיאה תמיד עבור שני
    הקוראים.
    """
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

    git_provenance = _git_provenance(catalog.repo_root)
    history_asserted = assert_main or assert_on_main_history
    on_main_history = git_provenance.get(
        "on_main_history", git_provenance.get("on_main", "unknown")
    )
    at_origin_main_tip = git_provenance.get("at_origin_main_tip", "unknown")
    if history_asserted and on_main_history != "yes":
        raise ContextLibrarianError(
            "--assert-main/--assert-on-main-history was passed but generated_commit "
            f"{git_provenance['commit']!r} on branch "
            f"{git_provenance['branch']!r} is not a proven ancestor of origin/main "
            f"(on_main_history={on_main_history}); refusing to generate a "
            "bundle that would claim to reflect main's current state"
        )
    if assert_at_origin_main_tip and at_origin_main_tip != "yes":
        raise ContextLibrarianError(
            "--assert-at-origin-main-tip was passed but generated_commit "
            f"{git_provenance['commit']!r} does not equal origin/main "
            f"(at_origin_main_tip={at_origin_main_tip}); refusing to generate "
            "a bundle that would claim to reflect origin/main's tip"
        )

    nodes, roles, traversed = _select_nodes(catalog, profile, query)
    freshness = _freshness(catalog, nodes)
    expansions = _local_expansions(catalog.repo_root, profile)
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
        git_provenance,
        expansions,
        direct_source_reverified,
        verification_ledger,
    )
    actual_tokens = _approximate_char_estimate(bundle)
    docs = _unique_references(nodes, "canonical_docs")
    evidence = _unique_references(
        [node for node in nodes if node["type"] == "layer"],
        "production_evidence",
    )
    references = [*docs, *evidence]
    selected_documents = len({reference["path"] for _, reference in references})
    breakdown = _budget_breakdown(nodes, docs, evidence)
    return (
        bundle, actual_tokens, token_budget, breakdown,
        selected_documents, document_budget, references,
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
    assert_main: bool = False,
    assert_on_main_history: bool = False,
    assert_at_origin_main_tip: bool = False,
    direct_source_reverified: bool = False,
    verification_ledger: Iterable[str] = (),
) -> str:
    (
        bundle, actual_tokens, token_budget, breakdown,
        selected_documents, document_budget, references,
    ) = _build_bundle_unchecked(
        catalog,
        task_type=task_type,
        query=query,
        max_tokens=max_tokens,
        max_documents=max_documents,
        production_claim=production_claim,
        verified_production_evidence=verified_production_evidence,
        assert_main=assert_main,
        assert_on_main_history=assert_on_main_history,
        assert_at_origin_main_tip=assert_at_origin_main_tip,
        direct_source_reverified=direct_source_reverified,
        verification_ledger=verification_ledger,
    )
    if selected_documents > document_budget:
        raise ContextLibrarianError(
            _format_document_overflow(
                estimated_tokens=actual_tokens,
                token_budget=token_budget,
                selected_documents=selected_documents,
                budget=document_budget,
                references=references,
                breakdown=breakdown,
            )
        )
    if actual_tokens > token_budget:
        raise ContextLibrarianError(
            _format_budget_overflow(
                estimated_tokens=actual_tokens,
                budget=token_budget,
                breakdown=breakdown,
            )
        )
    return bundle


@dataclass(frozen=True)
class BundleEstimate:
    """תוצאת dry-run שלא זורקת שגיאה, עבור profile+query בודדים.

    `actual_tokens`/`token_budget` הם בדיוק אותם מספרים ש-`build_bundle()`
    היה משתמש בהם כדי להחליט אם לזרוק שגיאה — זה לא קירוב נפרד וזול
    שמחושב מתת-קבוצה של שדות (code_paths/test_paths/canonical_docs/notes
    בלבד היו מפספסים את באנר ה-git-provenance, את טקסט ה-mandatory-
    decisions, ואת קטעי ה-edges/freshness — כולם נספרים לתקציב האמיתי).
    `fits` דורש שגם תקציב ה-token וגם תקציב המסמכים יעמדו במגבלה.
    """

    task_type: str
    query: str
    fits: bool
    actual_tokens: int
    token_budget: int
    selected_documents: int = 0
    document_budget: int = 0
    document_fits: bool = True


def estimate_bundle(
    catalog: Catalog,
    *,
    task_type: str,
    query: str = "",
    max_tokens: int | None = None,
    max_documents: int | None = None,
    production_claim: bool = False,
    verified_production_evidence: str | None = None,
    direct_source_reverified: bool = False,
    verification_ledger: Iterable[str] = (),
) -> BundleEstimate:
    """dry run של `build_bundle()`: אותה לוגיקת selection/render/measure,
    בשימוש חוזר ולא בכפילות, אבל מדווחת חריגת תקציב כ-
    `BundleEstimate(fits=False, ...)` שמוחזר במקום לזרוק שגיאה.

    מיועדת לבדיקת עריכת קטלוג מועמדת — למשל `load_catalog()` ואז שינוי
    `catalog.nodes[...]` בזיכרון בלבד — מול כל profile מושפע *לפני*
    כתיבה לדיסק, כך שקונפליקט תקציב הוא מספר מדווח אחד במקום לולאת
    edit/test/edit בניסוי וטעייה. git provenance עדיין נאסף ונכלל
    ברינדור (ה-banner משפיע על actual_tokens בדיוק כמו ב-build_bundle()),
    אבל בדיקות ה-assertion בסגנון `--assert-main`/`--assert-on-main-history`
    לעולם לא נאכפות כאן — provenance שלא הוכח כ-main לעולם לא זורק שגיאה
    מ-estimate_bundle(), רק ההיטל שלו על actual_tokens נכנס לחישוב. ולעולם
    לא כותבת שום דבר.

    שגיאות מבניות (task type לא ידוע, תקציבים לא-חוקיים, `--production-
    claim` חסר) גם הן לא שאלות תקציב וזורקות שגיאה בכל זאת, בדיוק כמו
    `build_bundle()`.
    """
    (
        bundle, actual_tokens, token_budget, _,
        selected_documents, document_budget, _,
    ) = _build_bundle_unchecked(
        catalog,
        task_type=task_type,
        query=query,
        max_tokens=max_tokens,
        max_documents=max_documents,
        production_claim=production_claim,
        verified_production_evidence=verified_production_evidence,
        assert_main=False,
        assert_on_main_history=False,
        assert_at_origin_main_tip=False,
        direct_source_reverified=direct_source_reverified,
        verification_ledger=verification_ledger,
    )
    del bundle  # dry run: טקסט ה-bundle המרונדר עצמו לא מעניין את הקורא
    return BundleEstimate(
        task_type=task_type,
        query=query,
        fits=actual_tokens <= token_budget and selected_documents <= document_budget,
        actual_tokens=actual_tokens,
        token_budget=token_budget,
        selected_documents=selected_documents,
        document_budget=document_budget,
        document_fits=selected_documents <= document_budget,
    )


def estimate_all_profiles(
    catalog: Catalog, *, query: str = ""
) -> tuple[BundleEstimate, ...]:
    """`estimate_bundle()` עבור כל profile בקטלוג, ממוין לפי id.

    נוחות לתרחיש הנפוץ: בדיקת כל הפרופילים ללא צורך בטיפול פר-פרופיל
    בשגיאות מבניות. `_check_budget_overflow()` ב-`refresh_after_merge.py`
    שומרת בכוונה על הלולאה הפרטית שלה במקום להשתמש בפונקציה הזו — היא
    צריכה ללכוד שגיאה מבנית לכל profile בנפרד ולהמשיך לפרופיל הבא, בעוד
    `estimate_all_profiles()` הייתה זורקת שגיאה בפרופיל הראשון שנכשל
    ועוצרת שם. שתיהן, לעומת זאת, קוראות ל-`estimate_bundle()` המשותף
    ולא לגרסה כפולה של לוגיקת ה-render/measure עצמה.
    """
    return tuple(
        estimate_bundle(catalog, task_type=task_type, query=query)
        for task_type in sorted(catalog.profiles)
    )
