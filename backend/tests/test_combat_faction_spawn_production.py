"""Faction provenance must cross the production ASGI spawn boundary."""
import os

import pytest
from fastapi.testclient import TestClient

from app.config import WorldAdminCredentialSettings
from app.gameplay.event_store import DurableGameplayEventStore


@pytest.mark.parametrize("scheme,peer,expected", [
    ("http", "127.0.0.1", 200),
    ("https", "203.0.113.9", 200),
    ("http", "203.0.113.9", 403),
])
def test_spawn_faction_http_original_receipt_and_transport(tmp_path, monkeypatch, scheme, peer, expected):
    from app import main
    path = tmp_path / "faction-spawn.sqlite3"
    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(path))
    monkeypatch.setattr(main.settings, "character_model_provider_kind", "local")
    monkeypatch.setattr(main.settings, "siming_llm_mode", "disabled")
    monkeypatch.setattr(main.settings, "world_admin_credentials", [WorldAdminCredentialSettings(
        credential_ref="credential:spawn-faction", principal_ref="principal:spawn-faction",
        world_refs=("world:bakery-district",), secret="c" * 40, expires_at=9999999999)])
    payload = dict(world_ref="world:bakery-district", timeline_ref="timeline:explicit-admin-policy",
        actor_ref="character:char_a", target_ref="character:char_b", hostile=True,
        command_id="faction:spawn:1", idempotency_key="faction:spawn:1",
        causation_id="admin:policy:1", correlation_id="corr:faction:spawn")
    headers = {"Authorization": "Bearer " + "c" * 40, "X-Forwarded-Proto": "https"}
    route = "/admin/combat-faction-relations"
    with TestClient(main.app, base_url=f"{scheme}://admin.example", client=(peer, 47123)) as client:
        host = main.app.state.runtime_process
        assert host.process.pid != os.getpid()
        assert client.post(route, json=payload).status_code == 403
        response = client.post(route, json=payload, headers=headers)
        assert response.status_code == expected, response.text
        if expected == 200:
            assert response.json()["committed"]
            changed = client.post(route, json={**payload, "hostile": False}, headers=headers)
            assert changed.status_code == 409
        assert "c" * 40 not in response.text + client.get("/health").text
    assert host.process.exitcode == 0
    assert host.snapshot()["execution_credit"]["current"] == 0

    def events():
        store = DurableGameplayEventStore(path.with_name(path.name + ".gameplay.json"))
        try:
            return store.read_stream("faction:world:bakery-district:timeline:explicit-admin-policy")
        finally:
            store.close()

    committed = events()
    assert len(committed) == (1 if expected == 200 else 0)
    if expected != 200:
        return
    assert committed[0].payload["authenticated_principal_ref"] == "principal:spawn-faction"
    assert committed[0].payload["credential_ref"] == "credential:spawn-faction"
    assert "c" * 40 not in str(committed[0].payload)
    with TestClient(main.app, base_url=f"{scheme}://admin.example", client=(peer, 47123)) as client:
        reopened = main.app.state.runtime_process
        assert reopened.process.pid != host.process.pid
        replay = client.post(route, json=payload, headers=headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()["committed_event_ids"] == response.json()["committed_event_ids"]
        assert replay.json()["idempotency_status"] == "duplicate_replayed"
    assert reopened.process.exitcode == 0
    assert reopened.snapshot()["execution_credit"]["current"] == 0
    assert events() == committed
