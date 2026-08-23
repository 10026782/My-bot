from __future__ import annotations

import os
import subprocess
from unittest.mock import patch

from workers.adapters import SubprocessHarnessAdapter
from workers.contracts import Qualification, WorkerProfile, WorkerRequest, WorkerResult, WorkerStatus
from workers.registry import WorkerRegistry, WorkerRouter


def request(**overrides):
    values = dict(request_id="r1", task="fix it", role="builder", repo_path=".", allowed_paths=("app.py",))
    values.update(overrides)
    return WorkerRequest(**values)


def test_unknown_harness_fails_closed():
    profile = WorkerProfile("w", "builder", "future", enabled=True)
    result = WorkerRouter(WorkerRegistry((profile,), adapters={})).execute(request(), "w")
    assert result.status is WorkerStatus.BLOCKED
    assert result.summary == "unknown_harness"


def test_missing_executable_is_blocked():
    with patch("workers.adapters.shutil.which", return_value=None):
        result = SubprocessHarnessAdapter("qwen").execute(request(), WorkerProfile("w", "builder", "qwen"))
    assert result.status is WorkerStatus.BLOCKED
    assert result.summary == "harness_not_installed"


def test_disabled_and_unqualified_workers_cannot_run():
    profile = WorkerProfile("w", "builder", "qwen", enabled=False)
    adapter = SubprocessHarnessAdapter("qwen", allow_execution=True)
    with patch.object(adapter, "available", return_value=type("A", (), {"available": True})()):
        assert adapter.execute(request(), profile).summary == "worker_disabled"
    profile = WorkerProfile("w", "builder", "qwen", enabled=True)
    with patch.object(adapter, "available", return_value=type("A", (), {"available": True})()):
        assert adapter.execute(request(), profile).summary == "worker_unqualified"


def test_unsafe_permission_profile_is_blocked():
    profile = WorkerProfile("w", "builder", "qwen", enabled=True, qualification=Qualification.PILOT)
    adapter = SubprocessHarnessAdapter("qwen", allow_execution=True)
    with patch.object(adapter, "available", return_value=type("A", (), {"available": True})()):
        assert adapter.execute(request(), profile).summary == "unsafe_permission_profile"


def test_prose_only_success_is_invalid():
    result = WorkerResult("r1", "w", WorkerStatus.SUCCESS, summary="done", exit_code=0)
    assert result.status is WorkerStatus.INVALID_RESULT


def test_unexecuted_verification_command_cannot_create_success():
    profile = WorkerProfile(
        "w", "builder", "qwen", enabled=True,
        permission_profile="development_isolated_worktree",
        qualification=Qualification.PILOT,
    )
    adapter = SubprocessHarnessAdapter("qwen", allow_execution=True)
    with patch.object(adapter, "available", return_value=type("A", (), {"available": True})()), \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=[
                 subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 0, stdout=""),
                 subprocess.CompletedProcess([], 1),
             ],
         ) as run:
        result = adapter.execute(request(verification_commands=("pytest test.py",)), profile)
    assert run.call_count == 3
    assert result.status is WorkerStatus.FAILED
    assert not [e for e in result.evidence if e.startswith("verification-executed")]


def test_forbidden_paths_are_preserved():
    result = request(forbidden_paths=(".env", "secrets/"))
    assert result.forbidden_paths == (".env", "secrets/")


PILOT_PROFILE = WorkerProfile(
    "w", "builder", "qwen", enabled=True,
    permission_profile="development_isolated_worktree",
    qualification=Qualification.PILOT,
)


def pilot_adapter():
    adapter = SubprocessHarnessAdapter("qwen", allow_execution=True)
    return patch.object(adapter, "available", return_value=type("A", (), {"available": True})()), adapter


def test_harness_timeout_reports_timeout_status():
    availability_patch, adapter = pilot_adapter()
    with availability_patch, \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=subprocess.TimeoutExpired(cmd="qwen", timeout=300),
         ):
        result = adapter.execute(request(), PILOT_PROFILE)
    assert result.status is WorkerStatus.TIMEOUT
    assert result.summary == "harness timed out"


def test_child_environment_is_allowlisted():
    from workers.adapters import _child_environment
    environ = {"PATH": "/usr/bin", "HOME": "/home/x", "LC_ALL": "C",
               "MY_SERVICE_API_KEY": "leak", "CUSTOM_TOKEN": "leak", "FEATURE_FLAG": "on"}
    with patch.dict(os.environ, environ, clear=True):
        child = _child_environment()
    assert child == {"PATH": "/usr/bin", "HOME": "/home/x", "LC_ALL": "C"}


def test_forbidden_path_touch_fails_even_on_failed_harness():
    availability_patch, adapter = pilot_adapter()
    with availability_patch, \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=[
                 subprocess.CompletedProcess([], 1),
                 subprocess.CompletedProcess([], 0, stdout="?? secrets/key.txt\n"),
             ],
         ):
        result = adapter.execute(request(forbidden_paths=("secrets/",)), PILOT_PROFILE)
    assert result.status is WorkerStatus.FAILED
    assert result.summary == "path_boundary_violation"
    assert result.evidence == ["path-violation:forbidden-path:secrets/key.txt"]


def test_rename_into_forbidden_path_is_rejected():
    availability_patch, adapter = pilot_adapter()
    with availability_patch, \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=[
                 subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 0, stdout='R  app.py -> ".env"\n'),
                 subprocess.CompletedProcess([], 0, stdout=""),
             ],
         ):
        result = adapter.execute(
            request(allowed_paths=("app.py",), forbidden_paths=(".env",)), PILOT_PROFILE
        )
    assert result.status is WorkerStatus.FAILED
    assert result.summary == "path_boundary_violation"
    assert any(".env" in entry for entry in result.evidence)


def test_change_outside_allowed_paths_is_rejected():
    availability_patch, adapter = pilot_adapter()
    with availability_patch, \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=[
                 subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 0, stdout=" M workers/adapters.py\n"),
             ],
         ) as run:
        result = adapter.execute(request(allowed_paths=("app.py",)), PILOT_PROFILE)
    assert run.call_count == 2
    assert result.status is WorkerStatus.FAILED
    assert result.summary == "path_boundary_violation"
    assert not result.test_results


def test_in_bounds_success_keeps_evidence_and_reruns_audit_after_verification():
    availability_patch, adapter = pilot_adapter()
    with availability_patch, \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=[
                 subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 0, stdout=" M app.py\n"),
                 subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 0, stdout=" M app.py\n"),
             ],
         ) as run:
        result = adapter.execute(
            request(allowed_paths=("app.py",), verification_commands=("pytest test.py",)),
            PILOT_PROFILE,
        )
    assert run.call_count == 4
    assert result.status is WorkerStatus.SUCCESS
    assert result.evidence == ["verification-executed:pytest test.py"]


def test_gitignored_forbidden_path_change_is_detected(tmp_path):
    target = tmp_path / ".env"
    target.write_text("A=1\n")
    ignored_request = request(
        repo_path=str(tmp_path),
        allowed_paths=("app.py",),
        forbidden_paths=(".env",),
        verification_commands=("pytest test.py",),
    )

    def harness_mutates_ignored_file_then_audits(command, **kwargs):
        if command[0] == "qwen":
            target.write_text("A=2\n")
            return subprocess.CompletedProcess([], 0)
        return subprocess.CompletedProcess([], 0, stdout="")

    availability_patch, adapter = pilot_adapter()
    with availability_patch, \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=harness_mutates_ignored_file_then_audits,
         ):
        result = adapter.execute(ignored_request, PILOT_PROFILE)
    assert result.status is WorkerStatus.FAILED
    assert result.summary == "path_boundary_violation"
    assert result.evidence == ["path-violation:forbidden-ignored-change:.env"]


def test_unauditable_forbidden_area_fails_closed_before_execution(tmp_path):
    forbidden_dir = tmp_path / "secrets"
    forbidden_dir.mkdir()
    unavailable_request = request(
        repo_path=str(tmp_path),
        allowed_paths=("app.py",),
        forbidden_paths=("secrets/",),
    )
    availability_patch, adapter = pilot_adapter()
    with availability_patch, \
         patch("workers.adapters.os.walk", side_effect=OSError("denied")), \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=[
                 subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 0, stdout=""),
             ],
         ) as run:
        result = adapter.execute(unavailable_request, PILOT_PROFILE)
    assert result.status is WorkerStatus.BLOCKED
    assert result.summary == "path_audit_unavailable"
    assert run.call_count == 0


def test_untouched_gitignored_forbidden_path_does_not_fail():
    availability_patch, adapter = pilot_adapter()
    ignored_request = request(
        forbidden_paths=(".env",), verification_commands=("pytest test.py",)
    )
    with availability_patch, \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=[
                 subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 0, stdout=" M app.py\n"),
                 subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 0, stdout=" M app.py\n"),
             ],
         ) as run:
        result = adapter.execute(ignored_request, PILOT_PROFILE)
    assert run.call_count == 4
    assert result.status is WorkerStatus.SUCCESS
    assert result.evidence == ["verification-executed:pytest test.py"]
    assert not [e for e in result.evidence if e.startswith("path-violation")]
    assert result.status is WorkerStatus.SUCCESS
    assert not [e for e in result.evidence if e.startswith("path-violation")]


def test_unauditable_worktree_fails_closed():
    availability_patch, adapter = pilot_adapter()
    with availability_patch, \
         patch(
             "workers.adapters.subprocess.run",
             side_effect=[
                 subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 128),
             ],
         ):
        result = adapter.execute(request(), PILOT_PROFILE)
    assert result.status is WorkerStatus.BLOCKED
    assert result.summary == "path_audit_unavailable"


def test_same_harness_supports_different_models():
    a = WorkerProfile("a", "builder", "claude", model="model-a")
    b = WorkerProfile("b", "reviewer", "claude", model="model-b")
    assert a.harness == b.harness and a.model != b.model


def test_same_role_supports_different_harnesses():
    a = WorkerProfile("a", "builder", "claude")
    b = WorkerProfile("b", "builder", "qwen")
    assert a.role == b.role and a.harness != b.harness


def test_profile_and_result_have_no_secret_fields():
    assert not {"api_key", "token", "secret"} & WorkerProfile("w", "builder", "qwen").to_dict().keys()
    assert not {"api_key", "token", "secret"} & WorkerResult("r", "w", WorkerStatus.BLOCKED).to_dict().keys()


def test_dry_run_does_not_execute_subprocess():
    with patch("workers.adapters.subprocess.run") as run:
        result = WorkerRouter(WorkerRegistry()).dry_run(request())
    run.assert_not_called()
    assert result.summary == "dry_run"


def test_new_workers_default_unqualified():
    assert all(p.qualification is Qualification.UNQUALIFIED for p in WorkerRegistry().profiles.values())
