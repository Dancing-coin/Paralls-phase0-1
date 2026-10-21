"""Typed Equipment boundary; no client Body projection or seeded app assets."""
from types import SimpleNamespace

import pytest

from app import main
from app.gameplay.event_store import DurableGameplayEventStore
from app.services.runtime_execution import RuntimeExecution
from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope
from app.gameplay.resource_modifier_admission import CONTENT_PATH
from app.gameplay import resource_modifier_admission
from app.gameplay.inventory_runtime import InventoryRuntimeError
from test_equipment_command_service import _admit_presence, _auth, _command, WORLD


def test_equipment_application_uses_shared_store_and_registered_content(tmp_path, monkeypatch):
    content_path = tmp_path / "mana-focus-charm.v1.yaml"
    content_path.write_bytes(CONTENT_PATH.read_bytes())
    monkeypatch.setattr(resource_modifier_admission, "CONTENT_PATH", content_path)
    store = DurableGameplayEventStore(tmp_path / "equipment-app.sqlite")
    execution = RuntimeExecution()
    monkeypatch.setattr(main, "gameplay_event_store", store, raising=False)
    monkeypatch.setattr(main, "embodied_controller_auth_service", _auth(), raising=False)
    monkeypatch.setattr(main, "_population_runtime_driver", SimpleNamespace(
        world_runtime=SimpleNamespace(mode=SimpleNamespace(world_ref=WORLD)),
        clock=SimpleNamespace(timeline=SimpleNamespace(timeline_id="timeline:main"))))
    monkeypatch.setattr(main, "inventory_definition_registry",
                        main.build_production_inventory_definition_registry(), raising=False)
    monkeypatch.setattr(main, "equipment_command_service", None, raising=False)
    reopened = None
    try:
        execution.submit(main._assemble_equipment_runtime).result(timeout=10)
        assert main.equipment_command_service.store is store
        assert store.read_events() == []  # registering content creates no asset
        _admit_presence(store)
        from app.gameplay.inventory_runtime import InventoryAuthorityService, ContainerSpec
        owner = InventoryAuthorityService(store=store, registry=main.inventory_definition_registry)
        assert owner.create_container(command_id="bag", actor_ref="char_a",
            spec=ContainerSpec("container:bag", 10, 10, 4), idempotency_key="bag",
            causation_id="intent", correlation_id="corr").committed
        assert owner.instantiate(command_id="item", actor_ref="char_a", item_id="focus:1",
            definition_id="item:mana-focus-charm@1", quantity=1, container_id="container:bag",
            idempotency_key="item", causation_id="intent", correlation_id="corr").committed
        request = Envelope(message_type="equipment_command", payload=_command(
            item_id="focus:1", slot_key="charm").model_dump(mode="json"))
        def route(connection="connection:equipment"):
            return execution.submit(lambda: main._handle_envelope(request,
                connection_context=WebSocketConnectionContext(remote_host="127.0.0.1",
                    observed_at=2, connection_ref=connection))[0]["payload"]).result(timeout=10)
        first = route()
        assert first["accepted"], first
        first_batch = store.get_transaction(first["receipt"]["transaction_id"])
        assert any(key.startswith("equipment-content-revision:resource-equipment:mana-focus-charm@1")
                   for key in first_batch.pinned_revisions)
        assert any(key.startswith("equipment-content-digest:sha256:")
                   for key in first_batch.pinned_revisions)
        count = len(store.read_events())
        assert not route("unbound")["accepted"]
        assert len(store.read_events()) == count
        store.close()
        reopened = DurableGameplayEventStore(tmp_path / "equipment-app.sqlite")
        monkeypatch.setattr(main, "gameplay_event_store", reopened)
        monkeypatch.setattr(main, "embodied_controller_auth_service", _auth())
        monkeypatch.setattr(main, "inventory_definition_registry",
                            main.build_production_inventory_definition_registry())
        execution.submit(main._assemble_equipment_runtime).result(timeout=10)
        original_content = content_path.read_bytes()
        changed_content = original_content.replace(
            b"definition_id: item:mana-focus-charm@1",
            b"definition_id: item:mana-focus-charm@2",
        )
        content_path.write_bytes(changed_content)
        changed_request = Envelope(message_type="equipment_command", payload=_command(
            item_id="focus:1", slot_key="charm", idempotency_key="equip:new").model_dump(mode="json"))
        try:
            changed = execution.submit(lambda: main._handle_envelope(changed_request,
                connection_context=WebSocketConnectionContext(remote_host="127.0.0.1",
                    observed_at=2, connection_ref="connection:equipment"))[0]["payload"]).result(timeout=10)
            assert not changed["accepted"]
            assert changed["error_code"] == "equipment_content_source_changed"
            assert len(reopened.read_events()) == count
            with pytest.raises(InventoryRuntimeError, match="inventory_item_definition_unknown"):
                main.inventory_definition_registry.item("item:mana-focus-charm@2")
            retry = route()
            assert retry["accepted"], retry
            assert retry["receipt"]["idempotency_status"] == "duplicate_replayed"
            assert len(reopened.read_events()) == count
        finally:
            content_path.write_bytes(original_content)
        execution.submit(main._assemble_equipment_runtime).result(timeout=10)
        retry = route()
        assert retry["accepted"], retry
        assert retry["receipt"]["idempotency_status"] == "duplicate_replayed"
        assert retry["receipt"]["committed_event_ids"] == first["receipt"]["committed_event_ids"]
        assert len(reopened.read_events()) == count
    finally:
        assert execution.stop(timeout_seconds=2)
        (reopened or store).close()


def test_equipment_prediction_typed_ingress_recovers_same_durable_owner_receipt(tmp_path, monkeypatch):
    from test_equipment_command_service import _setup, _service
    from app.gameplay.prediction_authority import PredictionAuthority
    store, auth, equipment = _setup(tmp_path)
    monkeypatch.setattr(main, "gameplay_event_store", store, raising=False)
    monkeypatch.setattr(main, "equipment_command_service", equipment, raising=False)
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=2,
                                         connection_ref="connection:equipment")
    def route(operation, **values):
        return main._handle_envelope(Envelope(message_type="equipment_prediction", payload={
            "operation": operation, "prediction_id": "prediction:app:1", **values,
        }), connection_context=context)[0]["payload"]
    reopened = None
    try:
        command = _command().model_dump(mode="json")
        baseline = len(store.read_events())
        preview = route("preview", command=command, idempotency_key="prediction:open")
        assert preview["accepted"], preview
        assert len(store.read_events()) == baseline + 1
        assert not store.read_events(event_type="gameplay.equipment.activation_started")
        confirmed = route("confirm", command=command, idempotency_key="prediction:confirm")
        assert confirmed["accepted"], confirmed
        assert confirmed["owner_receipt"]["committed"]
        assert confirmed["confirmation_receipt"]["committed"]
        event_ids = confirmed["owner_receipt"]["committed_event_ids"]
        count = len(store.read_events())
        store.close()
        reopened = DurableGameplayEventStore(tmp_path / "equipment.sqlite")
        replacement, _ = _service(reopened, auth)
        monkeypatch.setattr(main, "gameplay_event_store", reopened)
        monkeypatch.setattr(main, "equipment_command_service", replacement)
        retry = route("confirm", command=command, idempotency_key="prediction:confirm")
        assert retry["accepted"], retry
        assert retry["owner_receipt"]["committed_event_ids"] == event_ids
        assert retry["owner_receipt"]["idempotency_status"] == "duplicate_replayed"
        assert len(reopened.read_events()) == count
        assert PredictionAuthority(store=reopened).replay("prediction:app:1") == PredictionAuthority(
            store=reopened).replay("prediction:app:1", checkpoint_at=1)
        lookup = route("lookup", actor_id="char_a")
        assert lookup["accepted"] and lookup["state"]["status"] == "confirmed"
        denied = main._handle_envelope(Envelope(message_type="equipment_prediction", payload={
            "operation": "lookup", "prediction_id": "prediction:app:1", "actor_id": "char_a",
        }), connection_context=WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=2,
            connection_ref="unbound"))[0]["payload"]
        assert not denied["accepted"]
        assert len(reopened.read_events()) == count
    finally:
        (reopened or store).close()


@pytest.mark.parametrize("driver", [None, SimpleNamespace(current_tick=7)])
def test_equipment_prediction_deadline_uses_operational_time_without_population_driver(tmp_path, monkeypatch, driver):
    from test_equipment_command_service import _setup
    store, auth, equipment = _setup(tmp_path)
    monkeypatch.setattr(main, "gameplay_event_store", store, raising=False)
    monkeypatch.setattr(main, "equipment_command_service", equipment, raising=False)
    monkeypatch.setattr(main, "equipment_prediction_service", None)
    monkeypatch.setattr(main, "_population_runtime_driver", driver)
    operational = [100]
    monkeypatch.setattr(main, "time", lambda: operational[0])
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=2,
                                         connection_ref="connection:equipment")
    def route(operation, **values):
        return main._handle_envelope(Envelope(message_type="equipment_prediction", payload={
            "operation": operation, "prediction_id": "prediction:deadline", **values,
        }), connection_context=context)[0]["payload"]
    try:
        command = _command().model_dump(mode="json")
        opened = route("preview", command=command, idempotency_key="deadline:open", ttl=5)
        assert opened["accepted"], opened
        if driver is None:
            operational[0] = 106
        else:
            driver.current_tick = 106
        result = route("confirm", command=command, idempotency_key="deadline:confirm")
        if driver is None:
            assert not result["accepted"], result
            assert result["error_code"] == "equipment_prediction_expired"
            assert not store.read_events(event_type="gameplay.equipment.activation_started")
        else:
            assert result["accepted"], result
    finally:
        store.close()


def test_equipment_prediction_invalid_request_is_zero_write(tmp_path, monkeypatch):
    from test_equipment_command_service import _setup
    store, auth, equipment = _setup(tmp_path)
    monkeypatch.setattr(main, "gameplay_event_store", store, raising=False)
    monkeypatch.setattr(main, "equipment_command_service", equipment, raising=False)
    monkeypatch.setattr(main, "equipment_prediction_service", None)
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=2,
                                         connection_ref="connection:equipment")
    try:
        baseline = len(store.read_events())
        result = main._handle_envelope(Envelope(message_type="equipment_prediction", payload={
            "operation": "preview", "prediction_id": "prediction:invalid",
            "command": _command().model_dump(mode="json"), "idempotency_key": 123,
        }), connection_context=context)[0]["payload"]
        assert not result["accepted"]
        assert len(store.read_events()) == baseline
    finally:
        store.close()
