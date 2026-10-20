"""Authenticated faction facts reach the existing owner through real runtime HTTP."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from threading import Event

import pytest
import pytest_asyncio
import httpx
from fastapi.testclient import TestClient

from app.config import WorldAdminCredentialSettings
from app.services.world_admin_auth_service import WorldAdminCredentialVerifier

SECRET = "f" * 40
HEADERS = {"Authorization": "Bearer " + SECRET}
PATH = "/admin/combat-faction-relations"


def verifier(principal="principal:faction-admin", worlds=("world:bakery-district",)):
    return WorldAdminCredentialVerifier((WorldAdminCredentialSettings(
        credential_ref="credential:faction-admin", principal_ref=principal,
        world_refs=worlds, secret=SECRET, expires_at=9999999999),))


@pytest_asyncio.fixture
async def runtime(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "world.sqlite3"))
    monkeypatch.setattr(main.settings, "character_model_provider_kind", "local")
    monkeypatch.setattr(main.settings, "siming_llm_mode", "disabled")
    idle = asyncio.Event()
    async def pause(_):
        idle.set()
        await asyncio.Future()
    monkeypatch.setattr(main, "_population_runtime_sleep", pause)
    async def start():
        idle.clear()
        await main._start_population_runtime_on_startup()
        await asyncio.wait_for(idle.wait(), 5)
    await start()
    world = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main._population_runtime_driver.world_runtime.mode.world_ref))
    monkeypatch.setattr(main, "world_admin_credential_verifier", verifier(worlds=(world,)))
    payload = dict(world_ref=world, timeline_ref="timeline:faction-admission",
        actor_ref="character:char_a", target_ref="character:char_b", hostile=True,
        command_id="faction:admin:1", idempotency_key="faction:admin:1",
        causation_id="admin:policy-update:1", correlation_id="corr:faction:1")
    try:
        yield main, payload, start
    finally:
        await main._stop_population_runtime_on_shutdown()


@pytest.mark.asyncio
async def test_faction_http_provenance_reopen_and_changed_retry(runtime, monkeypatch):
    main, payload, start = runtime
    def events(): return main.gameplay_event_store.read_events()
    async def read(): return await asyncio.wrap_future(main.runtime_execution.submit(events))
    before = await read()
    client = TestClient(main.component_app, client=("127.0.0.1", 48110))
    assert client.post(PATH, json=payload).status_code == 403
    assert client.post(PATH, json=payload, headers={"Authorization": "Bearer invalid"}).status_code == 403
    assert client.post(PATH, json={**payload, "world_ref": "world:other"}, headers=HEADERS).status_code == 403
    remote = TestClient(main.component_app, client=("198.51.100.1", 48111))
    assert remote.post(PATH, json=payload, headers=HEADERS).status_code == 403
    remote.close()
    assert client.post(PATH, json={**payload, "hostile": 1}, headers=HEADERS).status_code == 422
    assert client.post(PATH, json={**payload, "actor_ref": "char_a"}, headers=HEADERS).status_code == 422
    assert client.post(PATH, json={**payload, "authorized_caller": "world_admin"}, headers=HEADERS).status_code == 422
    assert await read() == before
    committed = client.post(PATH, json=payload, headers=HEADERS)
    assert committed.status_code == 200, committed.text
    original = committed.json()
    rows = await read()
    event = next(row for row in rows if row.event_id == original["committed_event_ids"][0])
    assert event.event_type == "gameplay.combat.faction_relation_recorded"
    assert event.payload["authenticated_principal_ref"] == "principal:faction-admin"
    assert event.payload["credential_ref"] == "credential:faction-admin"
    assert SECRET not in repr(rows)
    for change in ({"hostile": False}, {"correlation_id": "changed"}, {"causation_id": "changed"}):
        assert client.post(PATH, json={**payload, **change}, headers=HEADERS).status_code == 409
    assert await read() == rows
    await main._stop_population_runtime_on_shutdown()
    await start()
    restarted = await read()
    replay = client.post(PATH, json=payload, headers=HEADERS)
    assert replay.status_code == 200, replay.text
    assert replay.json()["committed_event_ids"] == original["committed_event_ids"]
    assert replay.json()["idempotency_status"] == "duplicate_replayed"
    assert await read() == restarted
    monkeypatch.setattr(main, "world_admin_credential_verifier", verifier("principal:replacement", (payload["world_ref"],)))
    assert client.post(PATH, json=payload, headers=HEADERS).status_code == 409
    assert await read() == restarted
    client.close()


@pytest.mark.asyncio
async def test_faction_queue_revocation_is_zero_write(runtime, monkeypatch):
    main, payload, _ = runtime
    execution = main.runtime_execution
    before = await asyncio.wrap_future(execution.submit(main.gameplay_event_store.read_events))
    blocked, release, submitted = Event(), Event(), Event()
    def hold():
        blocked.set()
        assert release.wait(5)
    blocker = execution.submit(hold)
    assert await asyncio.to_thread(blocked.wait, 5)
    original_submit = execution.submit
    def observe(command):
        result = original_submit(command)
        if command.__qualname__ == "record_world_admin_faction_relation.<locals>.command":
            submitted.set()
        return result
    monkeypatch.setattr(execution, "submit", observe)
    client = TestClient(main.component_app, client=("127.0.0.1", 48112))
    task = asyncio.create_task(asyncio.to_thread(client.post, PATH, json=payload, headers=HEADERS))
    try:
        assert await asyncio.to_thread(submitted.wait, 5)
        monkeypatch.setattr(main, "world_admin_credential_verifier", WorldAdminCredentialVerifier(()))
    finally:
        release.set()
    await asyncio.wrap_future(blocker)
    response = await asyncio.wait_for(task, 5)
    client.close()
    assert response.status_code == 403, response.text
    assert await asyncio.wrap_future(execution.submit(main.gameplay_event_store.read_events)) == before


def test_faction_real_http_process_restart(tmp_path):
    """Exercise the deployed ASGI lifespan and durable receipt over a real socket."""
    backend = Path(__file__).resolve().parents[1]
    graph = tmp_path / "world.sqlite3"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = dict(os.environ, PYTHONPATH=str(backend), PYTHONDONTWRITEBYTECODE="1",
        PARALLS_HEAVENLY_GRAPH_PATH=str(graph), CHARACTER_MODEL_PROVIDER_KIND="local",
        SIMING_LLM_MODE="disabled", WORLD_ADMIN_CREDENTIALS_JSON=json.dumps([dict(
            credential_ref="credential:faction-admin", principal_ref="principal:faction-admin",
            world_refs=["world:bakery-district"], secret=SECRET, expires_at=9999999999)]))
    payload = dict(world_ref="world:bakery-district", timeline_ref="timeline:process-proof",
        actor_ref="character:char_a", target_ref="character:char_b", hostile=True,
        command_id="faction:process:1", idempotency_key="faction:process:1",
        causation_id="admin:process:1", correlation_id="corr:process:1")
    receipts = []
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3) as client:
        for generation in range(2):
            with (tmp_path / f"backend-{generation}.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen([sys.executable, "-m", "uvicorn",
                    "app.main:component_app", "--host", "127.0.0.1", "--port", str(port),
                    "--log-level", "warning"], cwd=backend, env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 25
                    while True:
                        assert process.poll() is None, (tmp_path / f"backend-{generation}.log").read_text()
                        try:
                            health = client.get("/health").json()
                            if health["status"] == "ok" and health["runtime_execution"]["state"] == "running":
                                break
                        except (httpx.HTTPError, ValueError, KeyError, TypeError):
                            pass
                        assert time.monotonic() < deadline, "backend readiness timed out"
                        time.sleep(.05)
                    assert client.post(PATH, json=payload).status_code == 403
                    response = client.post(PATH, json=payload, headers=HEADERS)
                    assert response.status_code == 200, response.text
                    receipts.append(response.json())
                    assert client.post(PATH, json={**payload, "hostile": False}, headers=HEADERS).status_code == 409
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    assert receipts[1]["idempotency_status"] == "duplicate_replayed"
    assert receipts[1]["committed_event_ids"] == receipts[0]["committed_event_ids"]
    from app.gameplay.event_store import DurableGameplayEventStore
    store = DurableGameplayEventStore(graph.with_name(graph.name + ".gameplay.json"))
    try:
        rows = [row for row in store.read_events() if row.event_type == "gameplay.combat.faction_relation_recorded"]
        assert len(rows) == 1
        assert rows[0].event_id == receipts[0]["committed_event_ids"][0]
        assert rows[0].payload["authenticated_principal_ref"] == "principal:faction-admin"
        assert SECRET not in repr(rows)
    finally:
        store.close()
