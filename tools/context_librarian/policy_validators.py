"""Deterministic structural/content predicates for auto-registration policies.

A policy's `path_patterns` glob is candidate selection only -- it is never
sufficient by itself to prove a runtime-consumed source still belongs to its
approved class. Every policy with `auto_registration_allowed=True` must have
an entry here; `validate_predicate()` fails closed (returns False) for any
policy id with no registered predicate, and every predicate itself fails
closed on I/O/decoding errors rather than raising past the caller.

VALIDATOR_VERSION is a single, deliberately coarse version counter for this
whole module -- bumped whenever ANY predicate function's logic changes.
reconcile.py's revalidation pass compares it against the version stored at
registration time; a mismatch forces a fresh predicate run against the
current file, exactly like a `policy_version` bump does. This module never
imports anything from reconcile.py/librarian.py's write paths -- it only
reads file content.

The real authority boundary these predicates check is *wiring*, not
*vocabulary*: whether the live runtime (tools/dispatcher.py, app.py) ever
calls INTO a candidate module -- not whether the module's own text happens
to mention dispatcher/gateway symbols. A bounded staging-verification
script for the Approvals layer legitimately imports and exercises the real
ActionGateway against a staging environment -- that IS its purpose, not an
authority grant -- so a naive "reject any mention of ActionGateway" check
would incorrectly fail exactly the files this policy exists to approve.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

VALIDATOR_VERSION = 1

_GUARD_FILES = ("tools/dispatcher.py", "app.py")
# Applied only to non-staging classes (research tools, recommendation
# catalogs, cross-layer metadata) that have no legitimate reason to ever
# mention live dispatch/execution machinery at all -- unlike a staging
# verification script, whose whole point is exercising that machinery.
_HIGH_RISK_CONTENT_TERMS = (
    "dispatch_tool(",
    "def dispatch_tool",
    "ActionGateway(",
    "action_gateway.",
    "from tools.dispatcher import",
    "from tools import dispatcher",
    "airtable_gateway.write",
    "enforce_tenant_scope(",
)


def _read_text(repo_root: Path, path: str) -> str | None:
    try:
        return (repo_root / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _no_high_risk_content(text: str) -> bool:
    return not any(term in text for term in _HIGH_RISK_CONTENT_TERMS)


def _has_main_entrypoint(text: str) -> bool:
    return '__name__ == "__main__"' in text or "__name__ == '__main__'" in text


def _not_wired_into_live_runtime(repo_root: Path, path: str) -> bool:
    """True iff the live dispatch/webhook entry points never reference this
    module by name -- proves the runtime never calls INTO this code,
    regardless of what this code itself calls out to."""
    module_stem = Path(path).stem
    for guard_file in _GUARD_FILES:
        guard_text = _read_text(repo_root, guard_file)
        if guard_text is not None and module_stem in guard_text:
            return False
    return True


def _validate_staging_verification(repo_root: Path, path: str) -> bool | None:
    """Bounded, manually-invoked staging verification: a standalone script
    (has a __main__ entrypoint, so it is never silently imported as a
    library) that the live runtime never calls into."""
    text = _read_text(repo_root, path)
    if text is None:
        return None
    return _has_main_entrypoint(text) and _not_wired_into_live_runtime(repo_root, path)


def _validate_offline_research_tool(repo_root: Path, path: str) -> bool | None:
    text = _read_text(repo_root, path)
    if text is None:
        return None
    return _no_high_risk_content(text) and _not_wired_into_live_runtime(repo_root, path)


def _validate_external_recommendation_catalog(repo_root: Path, path: str) -> bool | None:
    text = _read_text(repo_root, path)
    if text is None:
        return None
    return _no_high_risk_content(text) and _not_wired_into_live_runtime(repo_root, path)


def _validate_cross_layer_supporting_metadata(repo_root: Path, path: str) -> bool | None:
    text = _read_text(repo_root, path)
    if text is None:
        return None
    return _no_high_risk_content(text)


def _validate_external_execution_runtime(repo_root: Path, path: str) -> bool | None:
    """Prove the approved External Execution runtime source class by exact path."""
    text = _read_text(repo_root, path)
    if text is None:
        return None
    required = {
        "core/external_execution_boundary.py": ("class ExternalExecutionBoundary",),
        "core/external_execution_repository.py": ("class ExternalExecutionRepository",),
        "core/external_poll_lease.py": ("class ExternalPollLeaseRepository",),
        "core/moneyprinterturbo_adapter.py": ("class MoneyPrinterTurboAdapter",),
        "core/mpt_runtime_policy.py": ("class MPTExecutionPolicy", "def classify_failure"),
        "core/migrations/002_external_poll_leases.sql": (
            "CREATE TABLE IF NOT EXISTS external_poll_leases",
            "job_id TEXT PRIMARY KEY",
            "lease_token TEXT NOT NULL UNIQUE",
            "idx_external_poll_leases_expiry",
        ),
    }
    markers = required.get(path)
    return bool(markers) and all(marker in text for marker in markers)


VALIDATORS: dict[str, Callable[[Path, str], bool | None]] = {
    "STAGING_VERIFICATION_F15": _validate_staging_verification,
    "STAGING_VERIFICATION_APPROVALS_BUG_FAMILY": _validate_staging_verification,
    "STAGING_VERIFICATION_TURN_COORDINATOR": _validate_staging_verification,
    "OFFLINE_RESEARCH_TOOL": _validate_offline_research_tool,
    "EXTERNAL_RECOMMENDATION_CATALOG": _validate_external_recommendation_catalog,
    "EXTERNAL_RECOMMENDATION_CATALOG_TEST": _validate_external_recommendation_catalog,
    "CROSS_LAYER_SUPPORTING_METADATA": _validate_cross_layer_supporting_metadata,
    "EXTERNAL_EXECUTION_RUNTIME": _validate_external_execution_runtime,
}


def validate_predicate(policy_id: str, repo_root: Path, path: str) -> bool | None:
    """True: predicate proven satisfied. False: predicate proven violated.
    None: no predicate registered, or the file couldn't be read -- callers
    MUST treat None the same as False (cannot prove -> fail closed), the
    distinction exists only so callers can report *why* in decision_queue
    notes."""
    validator = VALIDATORS.get(policy_id)
    if validator is None:
        return None
    return validator(repo_root, path)
