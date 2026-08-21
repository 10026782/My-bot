from __future__ import annotations

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


def test_forbidden_paths_are_preserved():
    result = request(forbidden_paths=(".env", "secrets/"))
    assert result.forbidden_paths == (".env", "secrets/")


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
