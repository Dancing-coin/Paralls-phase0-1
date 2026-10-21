"""Explicit typed application boundary with real authored bakery source/Durable."""
from pathlib import Path

from app import main
from app.gameplay.economy_random_registry import EconomyRandomPolicyRegistry
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import DurableGameplayEventStore
from app.population_continuity.economy_random_caller import PopulationEconomyRandomCaller
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.runtime_publication import RuntimeCadencePublisher
from app.population_continuity.world import WorldContinuityRuntime
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.runtime_execution import RuntimeExecution
from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.world_runtime.population_driver import PopulationCadenceDriver
from app.world_runtime.simulation_clock import population_clock_profile
from app.ws_protocol import Envelope
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService
from test_economy_random_command_service import _auth


POLICIES = Path(__file__).resolve().parents[2] / "assets/gameplay/economy_random"


def _request(tick):
    return Envelope(message_type="economy_random_command", payload={
        "request_id": "explicit-bakery-draw-1", "actor_ref": "char_a",
        "policy_ref": "policy:economy_bakery_lottery@1",
        "world_ref": "world:bakery-district",
        "timeline_ref": "population:world:bakery-district", "world_tick": tick,
    })


def _route(execution, request, connection="connection"):
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=1,
                                         connection_ref=connection)
    return execution.submit(lambda: main._handle_envelope(
        request, connection_context=context)[0]["payload"]).result(timeout=10)


def test_typed_explicit_bakery_demand_real_source_and_durable_reopen(tmp_path, monkeypatch):
    path = tmp_path / "bakery-random.db"
    store = DurableGameplayEventStore(path)
    execution = RuntimeExecution()
    registry = EconomyRandomPolicyRegistry.from_directory(POLICIES)
    source = registry.source("policy:economy_bakery_lottery@1")
    assert source.world_scope == ("world:bakery-district",)
    assert source.timeline_scope == ("population:world:bakery-district",)
    assert registry.source("policy:economy_lottery@1").world_scope == ("world:main",)
    create_stormnight_event_schema_registry().require("economy.random.command.requested@1", 1)
    mode = main._bakery_population_mode()
    world = WorldContinuityRuntime(store=store, mode=mode, roster=PopulationRoster(actor_ids=("char_a",)))
    assert world.resume().committed
    publisher = RuntimeCadencePublisher(world_runtime=world, event_bus=InMemoryAuthorityEventBus(),
        room_id="room:bakery", scene_id="scene:bakery", zone_id="zone:bakery")
    window = int(population_clock_profile(main.settings.population_runtime_profile)["window_ticks"])
    driver = PopulationCadenceDriver(world_runtime=world, publish_window=publisher,
        window_size=window, catch_up_limit=mode.catch_up_limit)
    driver.require_temporal_authorization = True
    caller = PopulationEconomyRandomCaller(store=store, registry=registry, population_driver=driver)
    monkeypatch.setattr(main, "gameplay_event_store", store, raising=False)
    monkeypatch.setattr(main, "economy_random_caller", caller)
    monkeypatch.setattr(main, "embodied_controller_auth_service", _auth(), raising=False)
    reopened = None
    try:
        assert execution.submit(lambda: driver.tick(window)).result(timeout=10).published_cadence_ids
        assert not store.read_stream("gameplay:economy")  # cadence did not create a draw
        response = _route(execution, _request(window))
        assert response["accepted"], response
        assert response["result_ref"] and response["candidate_ref"]
        assert "seed" not in str(response)
        trigger_id = response["trigger_receipt"]["committed_event_ids"][0]
        result_id = response["economy_receipt"]["committed_event_ids"][0]
        trigger = store.get_event(trigger_id)
        result = store.get_event(result_id)
        assert result.causation_id == trigger.event_id
        assert result.payload["source_digest"] == source.source_digest
        assert trigger.payload["request"]["policy_ref"] == source.demand_ref
        count = len(store.read_events())
        store.close()
        reopened = DurableGameplayEventStore(path)
        monkeypatch.setattr(main, "gameplay_event_store", reopened)
        monkeypatch.setattr(main, "economy_random_caller",
            PopulationEconomyRandomCaller(store=reopened, registry=registry))
        monkeypatch.setattr(main, "embodied_controller_auth_service", _auth())
        duplicate = _route(execution, _request(window))
        assert duplicate["accepted"], duplicate
        assert duplicate["economy_receipt"]["committed_event_ids"] == [result_id]
        assert duplicate["economy_receipt"]["idempotency_status"] == "duplicate_replayed"
        assert len(reopened.read_events()) == count
        missing = _route(execution, _request(window), connection="unbound")
        assert not missing["accepted"] and missing["error_code"] == "controller_binding_required"
        changed = _request(window)
        changed.payload["world_tick"] += 1
        conflict = _route(execution, changed)
        assert not conflict["accepted"] and conflict["error_code"] == "economy_random_trigger_identity_conflict"
        assert len(reopened.read_events()) == count
    finally:
        assert execution.stop(timeout_seconds=2)
        if reopened is not None:
            reopened.close()
        else:
            store.close()


def test_real_fastapi_websocket_controller_bind_then_random_command(tmp_path, monkeypatch):
    """Controlled loopback websocket boundary: bind and explicit draw share one connection."""
    from fastapi.testclient import TestClient
    from contextlib import nullcontext

    main.reset_runtime_state()
    execution = RuntimeExecution()
    store = DurableGameplayEventStore(tmp_path / "network-bakery.db")
    registry = EconomyRandomPolicyRegistry.from_directory(POLICIES)
    mode = main._bakery_population_mode()
    world = WorldContinuityRuntime(store=store, mode=mode, roster=PopulationRoster(actor_ids=("char_a",)))
    assert world.resume().committed
    publisher = RuntimeCadencePublisher(world_runtime=world, event_bus=InMemoryAuthorityEventBus(),
        room_id="room:bakery", scene_id="scene:bakery", zone_id="zone:bakery")
    window = int(population_clock_profile(main.settings.population_runtime_profile)["window_ticks"])
    driver = PopulationCadenceDriver(world_runtime=world, publish_window=publisher,
        window_size=window, catch_up_limit=mode.catch_up_limit)
    driver.require_temporal_authorization = True
    assert driver.tick(window).published_cadence_ids
    auth = EmbodiedControllerAuthService()
    secret = auth.create_trusted_local_launch_credential(
        actor_id="char_a", controller_instance_id="controller:network", issued_at=1, expires_at=1000)
    monkeypatch.setattr(main, "gameplay_event_store", store, raising=False)
    monkeypatch.setattr(main, "economy_random_caller",
        PopulationEconomyRandomCaller(store=store, registry=registry, population_driver=driver), raising=False)
    monkeypatch.setattr(main, "embodied_controller_auth_service", auth, raising=False)
    monkeypatch.setattr(main, "runtime_execution", execution, raising=False)
    monkeypatch.setattr(main, "_mirror_transport_accepting", True, raising=False)
    try:
        # Explicitly assembled real runtime, so do not also invoke application lifespan.
        with nullcontext(TestClient(main.component_app, client=("127.0.0.1", 47072))) as client:
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json({"message_type": "embodied_controller_bind", "payload": {
                    "credential_kind": "trusted_local_launch", "credential": secret,
                    "actor_id": "char_a", "controller_instance_id": "controller:network",
                    "protocol_version": 1,
                }})
                bind_ack = websocket.receive_json()
                assert bind_ack["payload"]["accepted"], bind_ack
                bind_result = websocket.receive_json()
                assert bind_ack["payload"]["accepted"]
                assert bind_result["message_type"] == "embodied_controller_bound"
                websocket.send_json({"message_type": "economy_random_command", "payload": {
                    "request_id": "network-draw-1", "actor_ref": "char_a",
                    "policy_ref": "policy:economy_bakery_lottery@1",
                    "world_ref": "world:bakery-district",
                    "timeline_ref": "population:world:bakery-district", "world_tick": window,
                }})
                response = websocket.receive_json()
                assert response["message_type"] == "economy_random_command_result"
                assert response["payload"]["accepted"]
                assert response["payload"]["economy_receipt"]["committed_event_ids"]
                assert "seed" not in str(response)
        # A new connection with no controller bind is rejected before any append.
        before = len(store.read_events())
        with nullcontext(TestClient(main.component_app, client=("127.0.0.1", 47073))) as client:
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json({"message_type": "economy_random_command", "payload": {
                    "request_id": "network-unbound", "actor_ref": "char_a",
                    "policy_ref": "policy:economy_bakery_lottery@1",
                    "world_ref": "world:bakery-district",
                    "timeline_ref": "population:world:bakery-district", "world_tick": window,
                }})
                rejected = websocket.receive_json()
                assert not rejected["payload"]["accepted"]
                assert rejected["payload"]["error_code"] == "controller_binding_required"
        assert len(store.read_events()) == before
    finally:
        assert execution.stop(timeout_seconds=2)
        store.close()
