"""Runtime seam tests for TC8 ownership around existing lifecycle calls."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("TELEGRAM_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "pat-test")
os.environ.setdefault("AIRTABLE_BASE_ID", "app-test")

import app


@dataclass
class _State:
    version: int
    state: str


@dataclass
class _Contract:
    tenant_id: str = "tenant-a"
    canonical_user_id: str = "user-a"
    contract_id: str = "contract-1"
    status: str = "pending"


class _RuntimeRepo:
    state = _State(version=1, state="active")
    lock = threading.Lock()

    def begin_or_get(self, tenant, user, turn, contract):
        assert (tenant, user, contract) == ("tenant-a", "user-a", "contract-1")
        return _RuntimeRepo.state

    def claim(self, tenant, user, *, expected_version, operation_id, owner_kind):
        with _RuntimeRepo.lock:
            if _RuntimeRepo.state.state != "active" or expected_version != _RuntimeRepo.state.version:
                from core.turn_state_repository import TurnStateConflictError
                raise TurnStateConflictError("race")
            _RuntimeRepo.state = _State(version=expected_version + 1, state="claimed")
            return type("Result", (), {"state": _RuntimeRepo.state})()

    def finalize(self, *args, **kwargs):
        with _RuntimeRepo.lock:
            _RuntimeRepo.state = _State(version=_RuntimeRepo.state.version + 1, state="terminal")

    def release(self, *args, **kwargs):
        with _RuntimeRepo.lock:
            _RuntimeRepo.state = _State(version=_RuntimeRepo.state.version + 1, state="released")


def test_callback_and_text_runtime_seam_has_one_effective_owner(monkeypatch):
    monkeypatch.setattr("core.turn_state_repository.TurnStateRepository", _RuntimeRepo)
    _RuntimeRepo.state = _State(version=1, state="active")
    results, conflicts = [], []

    def attempt(kind):
        try:
            results.append(app._tc8_claim_contract(
                _Contract(), owner_kind=kind, turn_id=f"{kind}:1",
            ))
        except Exception:
            conflicts.append(kind)

    threads = [threading.Thread(target=attempt, args=("callback",)),
               threading.Thread(target=attempt, args=("text",))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 1
    assert len(conflicts) == 1


def test_runtime_seam_finalizes_from_actioncontract_status_only(monkeypatch):
    monkeypatch.setattr("core.turn_state_repository.TurnStateRepository", _RuntimeRepo)
    _RuntimeRepo.state = _State(version=1, state="active")
    context = app._tc8_claim_contract(
        _Contract(), owner_kind="callback", turn_id="callback:1",
    )
    contract = _Contract(status="completed")
    app._tc8_finish_contract(context, contract)
    assert _RuntimeRepo.state.state == "terminal"
