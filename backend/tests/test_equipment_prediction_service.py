from __future__ import annotations

import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.equipment_runtime import EquipmentRuntimeError
from app.gameplay.prediction_authority import PredictionAuthority
from app.services.equipment_prediction_service import EquipmentPredictionService
from test_equipment_command_service import _command, _setup


@pytest.mark.parametrize("confirmed", [False, True])
@pytest.mark.parametrize("damage", ["result_digest", "event_payload", "event_refs"])
def test_prediction_authority_revalidates_owner_receipt_on_first_and_duplicate_confirm(
        tmp_path, monkeypatch, confirmed, damage):
    store, auth, equipment = _setup(tmp_path)
    prediction = _prediction(store, auth, equipment)
    command = _command()
    prediction.preview(command, connection_ref="connection:equipment",
                       prediction_id="prediction:integrity", idempotency_key="integrity:open")
    owner = equipment.submit(command, connection_ref="connection:equipment")
    authority = prediction.prediction
    arguments = dict(prediction_id="prediction:integrity", idempotency_key="integrity:confirm",
                     owner_principal="actor_gameplay.equipment_domain",
                     owner_idempotency_key=f"{command.actor_ref}:production:v1:{command.idempotency_key}")
    if confirmed:
        assert authority.confirm(**arguments).committed
    original = store.get_transaction
    def altered(transaction_id):
        batch = original(transaction_id)
        if transaction_id != owner.transaction_id:
            return batch
        if damage == "result_digest":
            return batch.model_copy(update={"result_digest": "0" * 64})
        event = batch.events[0]
        change = ({"payload": {**event.payload, "unexpected": "tampered"}}
                  if damage == "event_payload" else {"event_id": "event:forged"})
        return batch.model_copy(update={"events": [event.model_copy(update=change), *batch.events[1:]]})
    monkeypatch.setattr(store, "get_transaction", altered)
    before = len(store.read_events())
    try:
        result = authority.confirm(**arguments)
        assert not result.committed
        assert len(store.read_events()) == before
    finally:
        store.close()


def _prediction(store, auth, service, *, now=lambda: 10):
    return EquipmentPredictionService(
        equipment=service, prediction=PredictionAuthority(store=store), now=now
    )


def test_equipment_preview_confirm_uses_real_owner_receipt(tmp_path):
    store, auth, equipment = _setup(tmp_path)
    prediction = _prediction(store, auth, equipment)
    command = _command()
    opened = prediction.preview(command, connection_ref="connection:equipment",
                                prediction_id="equipment-pred:1", idempotency_key="pred:open")
    assert opened.prediction.committed
    result = prediction.confirm(command, connection_ref="connection:equipment",
                                prediction_id="equipment-pred:1", confirm_idempotency_key="pred:confirm")
    assert result.owner is not None and result.owner.committed
    assert result.confirmation is not None and result.confirmation.committed
    assert prediction.prediction.state("equipment-pred:1").status == "confirmed"
    store.close()


def test_equipment_prediction_durable_reopen_and_changed_duplicate(tmp_path):
    path = tmp_path / "equipment.sqlite"
    store, auth, equipment = _setup(tmp_path)
    prediction = _prediction(store, auth, equipment)
    command = _command()
    first = prediction.preview(command, connection_ref="connection:equipment",
                               prediction_id="equipment-pred:2", idempotency_key="pred:open")
    assert first.prediction.committed
    duplicate = prediction.preview(command, connection_ref="connection:equipment",
                                   prediction_id="equipment-pred:2", idempotency_key="pred:open")
    assert duplicate.prediction.idempotency_status == "duplicate_replayed"
    with pytest.raises(EquipmentRuntimeError, match="equipment_prediction_intent_changed"):
        prediction.confirm(_command(slot_key="left_hand"), connection_ref="connection:equipment",
                           prediction_id="equipment-pred:2", confirm_idempotency_key="pred:changed")
    store.close()
    reopened = DurableGameplayEventStore(path)
    replacement, _ = _setup_replacement(reopened, auth)
    restored = _prediction(reopened, auth, replacement)
    confirmed = restored.confirm(command, connection_ref="connection:equipment",
                                 prediction_id="equipment-pred:2", confirm_idempotency_key="pred:confirm")
    assert confirmed.owner is not None and confirmed.owner.committed
    assert confirmed.confirmation is not None and confirmed.confirmation.committed
    reopened.close()


def _setup_replacement(store, auth):
    from test_equipment_command_service import _service
    return _service(store, auth)


def test_equipment_prediction_rechecks_scope_and_revocation(tmp_path):
    store, auth, equipment = _setup(tmp_path)
    prediction = _prediction(store, auth, equipment)
    command = _command()
    prediction.preview(command, connection_ref="connection:equipment",
                       prediction_id="equipment-pred:3", idempotency_key="pred:open")
    binding = auth.resolve_controller_binding(actor_id="char_a", connection_ref="connection:equipment").binding
    auth.revoke_controller_epoch(controller_instance_id=binding.controller_instance_id,
                                 connection_epoch=binding.connection_epoch)
    with pytest.raises(EquipmentRuntimeError, match="controller_binding_required"):
        prediction.confirm(command, connection_ref="connection:equipment",
                           prediction_id="equipment-pred:3", confirm_idempotency_key="pred:confirm")
    assert prediction.prediction.state("equipment-pred:3").status == "pending"
    store.close()


def test_equipment_prediction_expiry_is_operational_deadline(tmp_path):
    store, auth, equipment = _setup(tmp_path)
    clock = [10]
    prediction = _prediction(store, auth, equipment, now=lambda: clock[0])
    command = _command()
    prediction.preview(command, connection_ref="connection:equipment",
                       prediction_id="equipment-pred:4", idempotency_key="pred:open", ttl=1)
    clock[0] = 12
    with pytest.raises(EquipmentRuntimeError, match="equipment_prediction_expired"):
        prediction.confirm(command, connection_ref="connection:equipment",
                           prediction_id="equipment-pred:4", confirm_idempotency_key="pred:confirm")
    assert prediction.prediction.state("equipment-pred:4").status == "expired"
    store.close()


def test_preview_duplicate_keeps_original_deadline_after_clock_advances(tmp_path):
    store, auth, equipment = _setup(tmp_path)
    clock = [10]
    prediction = _prediction(store, auth, equipment, now=lambda: clock[0])
    command = _command()
    prediction.preview(command, connection_ref="connection:equipment",
                       prediction_id="equipment-pred:deadline", idempotency_key="pred:deadline", ttl=5)
    clock[0] = 12
    duplicate = prediction.preview(command, connection_ref="connection:equipment",
                                   prediction_id="equipment-pred:deadline", idempotency_key="pred:deadline", ttl=5)
    assert duplicate.prediction.idempotency_status == "duplicate_replayed"
    assert prediction.prediction.state("equipment-pred:deadline").expires_at == 15
    store.close()


def test_preview_read_set_conflict_rejects_before_equipment_write(tmp_path):
    from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService

    store, auth, equipment = _setup(tmp_path)
    prediction = _prediction(store, auth, equipment)
    command = _command()
    prediction.preview(command, connection_ref="connection:equipment",
                       prediction_id="equipment-pred:cas", idempotency_key="pred:cas")
    inventory = InventoryAuthorityService(store=store,
        registry=equipment._owner_arguments["inventory_registry"])
    assert inventory.create_container(command_id="inventory:later-container", actor_ref="char_a",
        spec=ContainerSpec("container:later", 1, 1, 1), idempotency_key="inventory:later-container",
        causation_id="cause", correlation_id="corr").committed
    before = store.get_stream_head("gameplay:equipment:char_a")
    with pytest.raises(EquipmentRuntimeError, match="equipment_prediction_revision_conflict"):
        prediction.confirm(command, connection_ref="connection:equipment",
                           prediction_id="equipment-pred:cas", confirm_idempotency_key="pred:cas:confirm")
    assert store.get_stream_head("gameplay:equipment:char_a") == before
    store.close()


def test_prediction_expiry_and_revoke_require_actor_scope(tmp_path):
    store, auth, equipment = _setup(tmp_path)
    clock = [10]
    prediction = _prediction(store, auth, equipment, now=lambda: clock[0])
    command = _command()
    prediction.preview(command, connection_ref="connection:equipment",
                       prediction_id="equipment-pred:scope", idempotency_key="pred:scope", ttl=1)
    clock[0] = 12
    with pytest.raises(EquipmentRuntimeError, match="controller_binding_required"):
        prediction.expire(prediction_id="equipment-pred:scope", actor_id="char_a",
                          connection_ref="connection:wrong", idempotency_key="pred:expire")
    assert prediction.prediction.state("equipment-pred:scope").status == "pending"
    with pytest.raises(EquipmentRuntimeError, match="controller_binding_subject_mismatch"):
        prediction.revoke(prediction_id="equipment-pred:scope", actor_id="someone_else",
                          connection_ref="connection:equipment", idempotency_key="pred:revoke")
    assert prediction.prediction.state("equipment-pred:scope").status == "pending"
    assert prediction.lookup("equipment-pred:scope", actor_id="char_a",
                             connection_ref="connection:equipment").status == "pending"
    assert prediction.revoke(prediction_id="equipment-pred:scope", actor_id="char_a",
        connection_ref="connection:equipment", idempotency_key="pred:valid-revoke").committed
    assert prediction.lookup("equipment-pred:scope", actor_id="char_a",
                             connection_ref="connection:equipment").status == "revoked"
    store.close()


def test_equipment_prediction_recovers_owner_commit_after_response_loss(tmp_path, monkeypatch):
    store, auth, equipment = _setup(tmp_path)
    prediction = _prediction(store, auth, equipment)
    command = _command()
    prediction.preview(command, connection_ref="connection:equipment",
                       prediction_id="equipment-pred:5", idempotency_key="pred:open")
    original = equipment.submit
    lost = {"raised": False}

    def submit_then_lose(*args, **kwargs):
        result = original(*args, **kwargs)
        if not lost["raised"]:
            lost["raised"] = True
            raise TimeoutError("simulated owner response loss")
        return result

    monkeypatch.setattr(equipment, "submit", submit_then_lose)
    with pytest.raises(TimeoutError):
        prediction.confirm(command, connection_ref="connection:equipment",
                           prediction_id="equipment-pred:5", confirm_idempotency_key="pred:confirm")
    count = len(store.read_events())
    path = tmp_path / "equipment.sqlite"
    store.close()
    store = DurableGameplayEventStore(path)
    equipment, _ = _setup_replacement(store, auth)
    prediction = _prediction(store, auth, equipment)
    recovered = prediction.confirm(command, connection_ref="connection:equipment",
                                   prediction_id="equipment-pred:5", confirm_idempotency_key="pred:confirm")
    assert recovered.owner is not None and recovered.owner.idempotency_status == "duplicate_replayed"
    assert recovered.confirmation is not None and recovered.confirmation.committed
    assert prediction.prediction.state("equipment-pred:5").status == "confirmed"
    assert len(store.read_events()) == count + 1
    again = prediction.confirm(command, connection_ref="connection:equipment",
        prediction_id="equipment-pred:5", confirm_idempotency_key="pred:confirm")
    assert again.confirmation.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == count + 1
    store.close()


def test_prediction_rejects_binding_epoch_replacement(tmp_path):
    from app.services.embodied_controller_auth_service import EmbodiedControllerEnrollment
    store, auth, equipment = _setup(tmp_path)
    prediction = _prediction(store, auth, equipment)
    prediction.preview(_command(), connection_ref="connection:equipment",
                       prediction_id="equipment-pred:epoch", idempotency_key="pred:epoch")
    secret = auth.create_trusted_local_launch_credential(actor_id="char_a",
        controller_instance_id="controller:equipment", issued_at=3, expires_at=100)
    assert auth.bind_controller(EmbodiedControllerEnrollment(
        credential_kind="trusted_local_launch", credential=secret, actor_id="char_a",
        controller_instance_id="controller:equipment", protocol_version=1),
        remote_host="127.0.0.1", now=4, connection_ref="connection:equipment").accepted
    count = len(store.read_events())
    with pytest.raises(EquipmentRuntimeError, match="equipment_prediction_intent_changed"):
        prediction.confirm(_command(), connection_ref="connection:equipment",
            prediction_id="equipment-pred:epoch", confirm_idempotency_key="pred:epoch:confirm")
    assert len(store.read_events()) == count
    store.close()


def test_preview_receipt_tamper_rejects_zero_owner_writes(tmp_path, monkeypatch):
    store, auth, equipment = _setup(tmp_path)
    prediction = _prediction(store, auth, equipment)
    preview = prediction.preview(_command(), connection_ref="connection:equipment",
        prediction_id="equipment-pred:tamper", idempotency_key="pred:tamper")
    original = store.get_transaction
    def tampered(transaction_id):
        batch = original(transaction_id)
        if transaction_id == preview.prediction.transaction_id:
            return batch.model_copy(update={"result_digest": "sha256:" + "0" * 64})
        return batch
    monkeypatch.setattr(store, "get_transaction", tampered)
    count = len(store.read_events())
    with pytest.raises(EquipmentRuntimeError, match="equipment_prediction_receipt_invalid"):
        prediction.confirm(_command(), connection_ref="connection:equipment",
            prediction_id="equipment-pred:tamper", confirm_idempotency_key="pred:tamper:confirm")
    assert len(store.read_events()) == count
    store.close()
