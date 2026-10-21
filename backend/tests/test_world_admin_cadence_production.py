"""Authenticated admin HTTP ingress reaches the existing Durable cadence owner."""

import asyncio
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.config import WorldAdminCredentialSettings
from app.services.world_admin_auth_service import WorldAdminCredentialVerifier
import pytest_asyncio
from test_combat_faction_admin_application import runtime


@pytest_asyncio.fixture
async def application(runtime):
    main, _, start = runtime

    async def advance(tick):
        await asyncio.wrap_future(main.runtime_execution.submit(
            lambda: main._population_runtime_driver.tick(tick)))

    async def ensure_started():
        if main.runtime_execution is None:
            await start()

    yield main, ensure_started, advance


def _verifier(*, worlds=("world:bakery-district",), expires_at=9999999999,
              principal_ref="principal:bakery-admin"):
    return WorldAdminCredentialVerifier((WorldAdminCredentialSettings(
        credential_ref="credential:bakery-admin:v1",
        principal_ref=principal_ref,
        world_refs=worlds,
        secret="a" * 40,
        expires_at=expires_at,
    ),))


@pytest.mark.asyncio
async def test_authenticated_admin_revokes_cadence_through_http_and_durable_replay(application, monkeypatch):
    main, start, advance = application
    await start()
    await advance(86400)
    cadence_id = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main._population_runtime_driver.world_runtime.latest_confirmation.cadence_id))
    world_ref = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main._population_runtime_driver.world_runtime.mode.world_ref))
    payload = dict(world_ref=world_ref, cadence_id=cadence_id,
                   reason_code="administrator_cancelled", command_id="admin:cancel:1")
    headers = {"Authorization": "Bearer " + "a" * 40}
    client = TestClient(main.component_app, client=("127.0.0.1", 47221))
    before = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))

    monkeypatch.setattr(main, "world_admin_credential_verifier", WorldAdminCredentialVerifier(()), raising=False)
    assert client.post("/admin/cadence-revocations", json=payload, headers=headers).status_code == 503
    monkeypatch.setattr(main, "world_admin_credential_verifier", _verifier())
    assert client.post("/admin/cadence-revocations", json=payload).status_code == 403
    assert client.post("/admin/cadence-revocations", json=payload,
                       headers={"Authorization": "Bearer wrong"}).status_code == 403
    remote = TestClient(main.component_app, client=("203.0.113.9", 47222))
    assert remote.post("/admin/cadence-revocations", json=payload, headers=headers).status_code == 403
    monkeypatch.setattr(main, "world_admin_credential_verifier", _verifier(worlds=("world:other",)))
    assert client.post("/admin/cadence-revocations", json=payload, headers=headers).status_code == 403
    monkeypatch.setattr(main, "world_admin_credential_verifier", _verifier(expires_at=1))
    assert client.post("/admin/cadence-revocations", json=payload, headers=headers).status_code == 403
    monkeypatch.setattr(main, "world_admin_credential_verifier", _verifier(worlds=("world:other",)))
    assert client.post("/admin/cadence-revocations", json={**payload, "world_ref": "world:other"},
                       headers=headers).status_code == 409
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == before

    monkeypatch.setattr(main, "world_admin_credential_verifier", _verifier())
    response = client.post("/admin/cadence-revocations", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["committed"] is True
    event = await asyncio.wrap_future(main.runtime_execution.submit(lambda: next(
        item for item in main.gameplay_event_store.read_events()
        if item.event_type == "population.cadence.revoked")))
    assert event.payload["authenticated_principal_ref"] == "principal:bakery-admin"
    assert event.payload["credential_ref"] == "credential:bakery-admin:v1"
    assert "a" * 40 not in str(event.payload) + response.text
    committed = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))

    changed = client.post("/admin/cadence-revocations", json={**payload, "reason_code": "changed"},
                          headers=headers)
    assert changed.status_code == 409
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == committed

    monkeypatch.setattr(main, "world_admin_credential_verifier", _verifier(expires_at=1))
    assert client.post("/admin/cadence-revocations", json=payload, headers=headers).status_code == 403
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == committed
    monkeypatch.setattr(main, "world_admin_credential_verifier", _verifier())

    await main._stop_population_runtime_on_shutdown()
    await start()
    committed = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))
    replayed = client.post("/admin/cadence-revocations", json=payload, headers=headers)
    assert replayed.status_code == 200
    assert replayed.json()["committed_event_ids"] == response.json()["committed_event_ids"]
    assert replayed.json()["idempotency_status"] == "duplicate_replayed"
    secure_remote = TestClient(main.component_app, base_url="https://admin.example",
                               client=("203.0.113.9", 47223))
    assert secure_remote.post("/admin/cadence-revocations", json=payload,
                              headers=headers).json()["idempotency_status"] == "duplicate_replayed"
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == committed
    client.close()
    remote.close()
    secure_remote.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_change", ["expired", "disabled", "identity_changed"])
async def test_admin_auth_changing_in_runtime_queue_rejects_without_write(application, monkeypatch, auth_change):
    main, start, advance = application
    await start()
    await advance(86400)
    execution = main.runtime_execution
    driver = main._population_runtime_driver
    payload = await asyncio.wrap_future(execution.submit(lambda: dict(
        world_ref=driver.world_runtime.mode.world_ref,
        cadence_id=driver.world_runtime.latest_confirmation.cadence_id,
        reason_code="administrator_cancelled", command_id="admin:queued-expiry:1",
    )))
    before = await asyncio.wrap_future(execution.submit(main.gameplay_event_store.export_snapshot))
    now = [100]
    monkeypatch.setattr(main, "time", lambda: now[0])
    monkeypatch.setattr(main, "world_admin_credential_verifier", _verifier(expires_at=100))
    blocked, release, submitted = Event(), Event(), Event()

    def hold_owner():
        blocked.set()
        assert release.wait(5), "test failed to release runtime owner"

    blocker = execution.submit(hold_owner)
    assert await asyncio.to_thread(blocked.wait, 5)
    original_submit = execution.submit

    def observe_submit(command):
        future = original_submit(command)
        submitted.set()
        return future

    monkeypatch.setattr(execution, "submit", observe_submit)
    client = TestClient(main.component_app, client=("127.0.0.1", 47224))
    response_task = asyncio.create_task(asyncio.to_thread(
        client.post, "/admin/cadence-revocations", json=payload,
        headers={"Authorization": "Bearer " + "a" * 40},
    ))
    try:
        assert await asyncio.to_thread(submitted.wait, 5)
        if auth_change == "expired":
            now[0] = 101
        elif auth_change == "disabled":
            monkeypatch.setattr(main, "world_admin_credential_verifier", WorldAdminCredentialVerifier(()))
        else:
            monkeypatch.setattr(main, "world_admin_credential_verifier",
                                _verifier(expires_at=100, principal_ref="principal:replacement"))
    finally:
        release.set()
    await asyncio.wrap_future(blocker)
    response = await asyncio.wait_for(response_task, 5)
    client.close()
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["error_code"] == "world_admin_unauthorized"
    assert await asyncio.wrap_future(execution.submit(main.gameplay_event_store.export_snapshot)) == before


def _admin_runtime_child(*args):
    """Keep the production child, with one deterministic Population boundary."""
    import json
    from pathlib import Path
    from app import main
    from app.services.runtime_process import runtime_child_main

    original_start = main._start_population_runtime_on_startup

    async def start():
        await original_start()

        def confirm_boundary():
            driver = main._population_runtime_driver
            driver.tick(driver.current_tick + driver.window_size)
            return dict(world_ref=driver.world_runtime.mode.world_ref,
                        cadence_id=driver.world_runtime.latest_confirmation.cadence_id)

        identity = await asyncio.wrap_future(main.runtime_execution.submit(confirm_boundary))
        Path(main.settings.heavenly_graph_path).with_suffix(".admin-cadence.json").write_text(
            json.dumps(identity), encoding="utf-8")

    main._start_population_runtime_on_startup = start
    runtime_child_main(*args)


@pytest.mark.parametrize("scheme,peer,expected", [
    ("http", "127.0.0.1", 200),
    ("https", "203.0.113.9", 200),
    ("http", "203.0.113.9", 403),
    ("http", "127.0.0.1", 503),
])
def test_production_spawn_admin_ingress_preserves_credentials_and_transport(
    tmp_path, monkeypatch, scheme, peer, expected,
):
    import json
    import os
    from app import main
    from app.gameplay.event_store import DurableGameplayEventStore
    import app.services.runtime_process as runtime_process

    graph_path = tmp_path / "admin-world.sqlite3"
    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(graph_path))
    monkeypatch.setattr(main.settings, "world_admin_credentials", [] if expected == 503 else [WorldAdminCredentialSettings(
        credential_ref="credential:spawn-admin:v1", principal_ref="principal:spawn-admin",
        world_refs=("world:bakery-district",), secret="b" * 40, expires_at=9999999999,
    )])
    monkeypatch.setattr(runtime_process, "CHILD_TARGET", _admin_runtime_child)
    with TestClient(main.app, base_url=f"{scheme}://admin.example", client=(peer, 47225)) as client:
        host = main.app.state.runtime_process
        assert host.process.pid != os.getpid()
        payload = dict(json.loads(graph_path.with_suffix(".admin-cadence.json").read_text(encoding="utf-8")),
                       command_id="admin:spawn:1", reason_code="administrator_cancelled")
        response = client.post("/admin/cadence-revocations", json=payload,
                               headers={"Authorization": "Bearer " + "b" * 40,
                                        "X-Forwarded-Proto": "https"})
        assert response.status_code == expected, response.text
        assert "b" * 40 not in response.text + client.get("/health").text
        if expected == 200:
            assert response.json()["committed"]
    assert host.process.exitcode == 0
    assert host.snapshot()["execution_credit"]["current"] == 0
    store = DurableGameplayEventStore(graph_path.with_name(graph_path.name + ".gameplay.json"))
    try:
        revoked = [event for event in store.read_events() if event.event_type == "population.cadence.revoked"]
        assert len(revoked) == (1 if expected == 200 else 0)
        if revoked:
            assert revoked[0].payload["authenticated_principal_ref"] == "principal:spawn-admin"
            assert revoked[0].payload["credential_ref"] == "credential:spawn-admin:v1"
            assert "b" * 40 not in str(revoked[0].payload)
    finally:
        store.close()
    if expected == 200:
        with TestClient(main.app, base_url=f"{scheme}://admin.example", client=(peer, 47225)) as client:
            replay_host = main.app.state.runtime_process
            assert replay_host.process.pid != host.process.pid
            replayed = client.post("/admin/cadence-revocations", json=payload,
                                   headers={"Authorization": "Bearer " + "b" * 40})
            assert replayed.status_code == 200, replayed.text
            assert replayed.json()["idempotency_status"] == "duplicate_replayed"
            assert replayed.json()["committed_event_ids"] == response.json()["committed_event_ids"]
        assert replay_host.process.exitcode == 0
        assert replay_host.snapshot()["execution_credit"]["current"] == 0

