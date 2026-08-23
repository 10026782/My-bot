"""C02-C04 Approval Coverage PR2: TMA Assets/Ventures use the gateway."""

from flask import Flask

from identity import Role
import tma_api


class _Identity:
    tenant_id = "tenant-test"
    memory_key = "user-test"
    user_id = "user-test"
    display_name = "Test Owner"

    def __init__(self, role):
        self.role = role

    @property
    def is_owner(self):
        return self.role == Role.OWNER


def _client(monkeypatch, role=Role.OWNER):
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": "1"})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: _Identity(role))
    return app.test_client()


def test_tma_assets_and_ventures_owner_writes_use_gateway(monkeypatch):
    queued = []

    def queue(action, payload, identity, label):
        queued.append((action, payload, label))
        return "approval-1", {"ok": True, "status": "executed"}, 200

    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", queue)
    monkeypatch.setattr(tma_api, "_at_patch", lambda *args: (_ for _ in ()).throw(AssertionError("direct patch")))
    monkeypatch.setattr(tma_api, "_at_post", lambda *args: (_ for _ in ()).throw(AssertionError("direct post")))
    client = _client(monkeypatch)
    headers = {"X-Telegram-Init-Data": "valid"}

    assert client.patch(
        "/api/assets/recASSET1", json={"Status": "active"}, headers=headers
    ).status_code == 200
    assert client.post(
        "/api/ventures", json={"name": "New venture"}, headers=headers
    ).status_code == 200
    assert client.patch(
        "/api/ventures/recVENTURE1", json={"next_action": "Review"}, headers=headers
    ).status_code == 200

    assert [(action, payload["table"]) for action, payload, _ in queued] == [
        ("tma_update_asset", "Assets"),
        ("tma_create_venture", "Ventures"),
        ("tma_update_venture", "Ventures"),
    ]


def test_tma_assets_and_ventures_remain_owner_only(monkeypatch):
    called = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", lambda *args: called.append(args))
    client = _client(monkeypatch, role=Role.MANAGER)
    headers = {"X-Telegram-Init-Data": "valid"}

    assert client.patch("/api/assets/recASSET1", json={"Status": "active"}, headers=headers).status_code == 403
    assert client.post("/api/ventures", json={"name": "Blocked"}, headers=headers).status_code == 403
    assert client.patch("/api/ventures/recVENTURE1", json={"notes": "Blocked"}, headers=headers).status_code == 403
    assert called == []
