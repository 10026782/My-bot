"""Reusable classification policies for already-approved source classes.

A policy is how an owner decision made once (e.g. "business_tool_registry.py
is a non-authoritative external recommendation catalog") gets reused
deterministically for every future path matching that same class, instead of
re-asking the same architectural question every reconcile cycle. See
docs/context_librarian/RECONCILIATION.md section B/E.

Matching is glob-only (Python fnmatch semantics) against the full
repo-relative path -- deliberately not the loose substring matching that
caused the docs/ux/reference-evidence STOP false positive this module
replaces the ad-hoc part of. A policy is authority *reuse*, never authority
*grant*: it only ever fires for a path that already matches a pattern an
owner explicitly wrote down.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.context_librarian.librarian import ContextLibrarianError
from tools.context_librarian.policy_validators import VALIDATORS

POLICY_REGISTRY_RELATIVE_PATH = Path("docs/context_librarian/policies/policy_registry.json")
POLICY_SCHEMA_RELATIVE_PATH = Path("docs/context_librarian/schema/policy_schema.json")
_SUPPORTED_SCHEMA_MAJOR = 1


@dataclass(frozen=True)
class Policy:
    id: str
    policy_version: int
    description: str
    path_patterns: tuple[str, ...]
    runtime_consumed: bool
    authority: bool
    eligible_target: str | None
    target_field: str | None
    auto_registration_allowed: bool
    classification_when_matched: str
    notes: tuple[str, ...]

    def matches(self, path: str) -> bool:
        normalised = path.replace("\\", "/")
        return any(fnmatch.fnmatch(normalised, pattern) for pattern in self.path_patterns)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextLibrarianError(f"cannot load {path}: {exc}") from exc


def load_policy_registry(repo_root: Path | str) -> tuple[Policy, ...]:
    """Loads and validates the policy registry against its schema.

    Fail-closed like every other Context Librarian catalog load: a malformed
    or unknown-shaped policy raises ContextLibrarianError rather than being
    silently skipped, since a policy that silently failed to load would
    silently stop reusing an owner's prior decision.
    """
    repo_root = Path(repo_root).resolve()
    schema = _load_json(repo_root / POLICY_SCHEMA_RELATIVE_PATH)
    version = schema.get("schema_version")
    if not isinstance(version, str) or not version.startswith(f"{_SUPPORTED_SCHEMA_MAJOR}."):
        raise ContextLibrarianError(f"unsupported policy schema version {version!r}")
    required = set(schema["required"])
    allowed = set(schema["allowed"])
    valid_classifications = set(schema["classification_when_matched_values"])
    valid_target_fields = set(schema["target_field_values"])

    data = _load_json(repo_root / POLICY_REGISTRY_RELATIVE_PATH)
    if not isinstance(data, dict):
        raise ContextLibrarianError(f"{POLICY_REGISTRY_RELATIVE_PATH} must contain an object")
    reg_version = data.get("schema_version")
    if not isinstance(reg_version, str) or not reg_version.startswith(f"{_SUPPORTED_SCHEMA_MAJOR}."):
        raise ContextLibrarianError(f"unsupported policy registry schema version {reg_version!r}")

    policies: list[Policy] = []
    seen_ids: set[str] = set()
    for raw in data.get("policies", []):
        if not isinstance(raw, dict):
            raise ContextLibrarianError("policy entry must be an object")
        missing = sorted(required - set(raw))
        unknown = sorted(set(raw) - allowed)
        if missing:
            raise ContextLibrarianError(f"policy {raw.get('id', '<missing>')}: missing fields: {', '.join(missing)}")
        if unknown:
            raise ContextLibrarianError(f"policy {raw.get('id', '<missing>')}: unknown fields: {', '.join(unknown)}")
        policy_id = raw["id"]
        if policy_id in seen_ids:
            raise ContextLibrarianError(f"duplicate policy id {policy_id}")
        seen_ids.add(policy_id)
        if not isinstance(raw["path_patterns"], list) or not raw["path_patterns"]:
            raise ContextLibrarianError(f"policy {policy_id}: path_patterns must be a non-empty list")
        if raw["classification_when_matched"] not in valid_classifications:
            raise ContextLibrarianError(
                f"policy {policy_id}: unknown classification_when_matched "
                f"{raw['classification_when_matched']!r}"
            )
        eligible_target = raw["eligible_target"]
        target_field = raw["target_field"]
        # target_field is never inferred from path/filename prose -- it is an
        # explicit, owner-authored field. The only structural rule enforced
        # here is consistency with eligible_target's nullability.
        if eligible_target is None and target_field is not None:
            raise ContextLibrarianError(
                f"policy {policy_id}: target_field must be null when eligible_target is null"
            )
        if eligible_target is not None and target_field not in valid_target_fields:
            raise ContextLibrarianError(
                f"policy {policy_id}: target_field must be one of {sorted(valid_target_fields)} "
                "when eligible_target is set"
            )
        if eligible_target is None and bool(raw["auto_registration_allowed"]):
            raise ContextLibrarianError(
                f"policy {policy_id}: auto_registration_allowed cannot be true "
                "without an eligible_target/target_field to register into"
            )
        if bool(raw["auto_registration_allowed"]) and policy_id not in VALIDATORS:
            # Message E correction item 1: a path glob is candidate selection
            # only -- an auto-registration policy without a deterministic
            # structural/content predicate can never prove a match still
            # belongs to its approved class.
            raise ContextLibrarianError(
                f"policy {policy_id}: auto_registration_allowed is true but no "
                "structural/content predicate is registered for it in "
                "tools/context_librarian/policy_validators.py"
            )
        policy_version = raw["policy_version"]
        if not isinstance(policy_version, int) or isinstance(policy_version, bool) or policy_version < 1:
            raise ContextLibrarianError(f"policy {policy_id}: policy_version must be a positive integer")
        policies.append(
            Policy(
                id=policy_id,
                policy_version=policy_version,
                description=raw["description"],
                path_patterns=tuple(raw["path_patterns"]),
                runtime_consumed=bool(raw["runtime_consumed"]),
                authority=bool(raw["authority"]),
                eligible_target=eligible_target,
                target_field=target_field,
                auto_registration_allowed=bool(raw["auto_registration_allowed"]),
                classification_when_matched=raw["classification_when_matched"],
                notes=tuple(raw.get("notes", [])),
            )
        )
    return tuple(policies)


def match_policy(path: str, policies: tuple[Policy, ...]) -> Policy | None:
    """Returns the first policy whose path_patterns match, or None.

    Policies are checked in registry-declaration order; a path is expected
    to match at most one policy class in practice (the registry's patterns
    are deliberately narrow/non-overlapping), so first-match is equivalent
    to unique-match for every policy defined today. Callers that need to
    detect ambiguity (more than one matching policy) should use
    matching_policies() instead -- this function alone cannot distinguish
    "one clean match" from "first of several conflicting matches".
    """
    for policy in policies:
        if policy.matches(path):
            return policy
    return None


def matching_policies(path: str, policies: tuple[Policy, ...]) -> tuple[Policy, ...]:
    """Returns every policy whose path_patterns match `path`, in registry order."""
    return tuple(policy for policy in policies if policy.matches(path))
