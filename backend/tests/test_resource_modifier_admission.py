from __future__ import annotations

from decimal import Decimal
import pytest

from app.gameplay.ability_runtime import AbilityDefinitionRegistry
from app.gameplay.equipment_runtime import EquipmentAuthorityService, EquipmentDefinitionRegistry, EquipmentProfile, EquipmentProjector, EquipmentSlotDefinition
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry
from app.gameplay.modifier_runtime import ModifierDefinitionRegistry
from app.gameplay.models import AppendBatchResult, GameplayFailure
from app.gameplay.resource_body_runtime import BodyRuntimeProjection, ResourceBodyRuntimeProjector
from app.gameplay.resource_modifier_admission import ResourceModifierBridgeOwner, ResourceModifierMappingRegistry, register_mana_focus_content
from app.gameplay.resource_recovery import ResourceRecoveryAuthorityService
from test_resource_recovery import _cadence


ACTOR = "actor:mana-focus-test"


def _system(store):
    inventory = InventoryDefinitionRegistry()
    equipment = EquipmentDefinitionRegistry()
    modifiers = ModifierDefinitionRegistry()
    mappings = ResourceModifierMappingRegistry()
    register_mana_focus_content(inventory=inventory, equipment=equipment, modifiers=modifiers, mappings=mappings)
    ability = AbilityDefinitionRegistry()
    service = EquipmentAuthorityService(store=store, inventory_registry=inventory, equipment_registry=equipment,
        ability_registry=ability, modifier_registry=modifiers, slots=(EquipmentSlotDefinition("charm"),),
        resource_modifier_mappings=mappings)
    return inventory, service


def _seed(store, inventory):
    owner = InventoryAuthorityService(store=store, registry=inventory)
    assert owner.create_container(command_id="cmd:bag", actor_ref=ACTOR, spec=ContainerSpec("container:bag", 20, 20, 4), idempotency_key="bag", causation_id="cause", correlation_id="corr").committed
    assert owner.instantiate(command_id="cmd:focus", actor_ref=ACTOR, item_id="item:mana-focus-charm:one", definition_id="item:mana-focus-charm@1", quantity=1, container_id="container:bag", idempotency_key="focus", causation_id="cause", correlation_id="corr").committed
    stream = f"gameplay:resources:{ACTOR}"
    batch = {"transaction_id":"tx:mana","command_id":"cmd:mana","expected_stream_revisions":{stream:0},"events":[{"event_id":"evt:mana","event_type":"gameplay.resource.materialized","schema_version":1,"stream_id":stream,"stream_revision":0,"global_sequence":0,"transaction_id":"tx:mana","command_id":"cmd:mana","causation_id":"cause","correlation_id":"corr","visibility_policy":"authority_only","payload":{"actor_ref":ACTOR,"resource_id":"core.mana","minimum":0,"maximum":10,"current":4,"definition_version":"mana@1","resource_schema":"resource.v2","capacity":10,"base_capacity":10,"locked":0,"debt":0,"debt_ceiling":0,"materialized_world_tick":0,"world_ref":"world","timeline_ref":"timeline","recovery_amount":1,"recovery_period_world_ticks":5,"modifier_ledger":[],"modifier_ledger_digest":"sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"}}],"idempotency_record":{"principal_ref":"test","idempotency_key":"mana","payload_digest":"d"},"outbox_entries":[],"result_digest":"d","projection_refresh_hints":[]}
    assert store.append_batch(batch).committed


def _equip(store):
    inventory, service = _system(store)
    _seed(store, inventory)
    result = service.equip(command_id="cmd:equip-focus", actor_ref=ACTOR, item_id="item:mana-focus-charm:one", source_container_id="container:bag", slot_key="charm", body=BodyRuntimeProjection(ACTOR, {}, {}, {}, "body"), idempotency_key="equip-focus", causation_id="cause:equip", correlation_id="corr:equip")
    assert result.committed
    return inventory, service, result


def test_real_equipment_activation_bridges_mana_recovery_and_unequip_detaches():
    store = GameplayEventStore()
    inventory, equipment, result = _equip(store)
    entry = ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_stream(f"gameplay:resources:{ACTOR}")).entries["core.mana"]
    assert entry.capacity == 10 and entry.current == 4
    assert entry.modifier_ledger[0]["amount"] == 1
    assert entry.modifier_ledger[0]["operation"] == "recovery_delta"
    assert entry.modifier_ledger[0]["mapping_revision"] == "resource-modifier-mapping:mana-focus-recovery@1"
    activation_id = next(iter(EquipmentProjector().rebuild(ACTOR, store.read_events()).activations))
    ended = equipment.unequip(command_id="cmd:unequip-focus", actor_ref=ACTOR, activation_id=activation_id, destination_container_id="container:bag", body=BodyRuntimeProjection(ACTOR, {}, {}, {}, "body"), idempotency_key="unequip-focus", causation_id="cause:unequip", correlation_id="corr:unequip")
    assert ended.committed
    final = ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_stream(f"gameplay:resources:{ACTOR}")).entries["core.mana"]
    assert final.modifier_ledger == ()


def test_equipment_lost_bridge_response_recovers_on_exact_duplicate(tmp_path, monkeypatch):
    path = tmp_path / "mana-focus.sqlite"
    store = DurableGameplayEventStore(path)
    inventory, equipment = _system(store)
    _seed(store, inventory)
    original = store.append_batch
    dropped = False
    def lose_bridge_response(batch):
        nonlocal dropped
        result = original(batch)
        principal = batch.idempotency_record.principal_ref if hasattr(batch, "idempotency_record") else batch["idempotency_record"]["principal_ref"]
        if principal == "resource_modifier_bridge" and not dropped:
            dropped = True
            raise RuntimeError("response_lost_after_commit")
        return result
    monkeypatch.setattr(store, "append_batch", lose_bridge_response)
    kwargs = dict(command_id="cmd:equip-lost", actor_ref=ACTOR, item_id="item:mana-focus-charm:one", source_container_id="container:bag", slot_key="charm", body=BodyRuntimeProjection(ACTOR, {}, {}, {}, "body"), idempotency_key="equip-lost", causation_id="cause:equip", correlation_id="corr:equip")
    with pytest.raises(RuntimeError, match="response_lost_after_commit"):
        equipment.equip(**kwargs)
    store.close()
    reopened = DurableGameplayEventStore(path)
    inventory2, equipment2 = _system(reopened)
    retry = equipment2.equip(**kwargs)
    assert retry.idempotency_status == "duplicate_replayed"
    assert ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, reopened.read_stream(f"gameplay:resources:{ACTOR}")).entries["core.mana"].modifier_ledger
    reopened.close()


def test_rejected_equipment_append_does_not_attempt_resource_bridge(monkeypatch):
    store = GameplayEventStore()
    inventory, equipment = _system(store)
    _seed(store, inventory)
    original = store.append_batch
    def reject_equipment(batch):
        principal = batch.idempotency_record.principal_ref if hasattr(batch, "idempotency_record") else batch["idempotency_record"]["principal_ref"]
        if principal == "actor_gameplay.equipment_domain":
            return AppendBatchResult(committed=False, transaction_id="tx:rejected", command_id=batch["command_id"],
                idempotency_status="rejected", failure=GameplayFailure(error_code="revision_conflict",
                message="revision_conflict", failed_stage="append", retriable=True))
        return original(batch)
    monkeypatch.setattr(store, "append_batch", reject_equipment)
    before = store.get_stream_head(f"gameplay:resources:{ACTOR}")
    result = equipment.equip(command_id="cmd:rejected", actor_ref=ACTOR, item_id="item:mana-focus-charm:one",
        source_container_id="container:bag", slot_key="charm", body=BodyRuntimeProjection(ACTOR, {}, {}, {}, "body"),
        idempotency_key="equip-rejected", causation_id="cause:equip", correlation_id="corr:equip")
    assert not result.committed
    assert store.get_stream_head(f"gameplay:resources:{ACTOR}") == before


def test_bridge_rejects_forged_or_unmapped_source_without_resource_write():
    # Covered through the application integration: only the registered focus template
    # is mapped. A combat template's canonical equipment transaction cannot touch mana.
    store = GameplayEventStore()
    inventory, equipment, result = _equip(store)
    before = store.get_stream_head(f"gameplay:resources:{ACTOR}")
    bridge = ResourceModifierBridgeOwner(store=store, mappings=ResourceModifierMappingRegistry(), modifiers=ModifierDefinitionRegistry())
    with pytest.raises(ValueError, match="resource_modifier_mapping_unknown"):
        bridge.sync_equipment_transaction(result.transaction_id)
    assert store.get_stream_head(f"gameplay:resources:{ACTOR}") == before


def test_full_and_checkpoint_tail_replay_same_modifier_ledger():
    store = GameplayEventStore()
    _equip(store)
    projector = ResourceBodyRuntimeProjector()
    stream = f"gameplay:resources:{ACTOR}"
    events = store.read_stream(stream)
    full = projector.rebuild_resources(ACTOR, events)
    checkpoint = projector.rebuild_resources(ACTOR, events[:1])
    checkpoint_tail = projector.rebuild_resources(ACTOR, events[1:], checkpoint=checkpoint)
    assert checkpoint_tail.entries == full.entries
    assert checkpoint_tail.source_revision_vector == full.source_revision_vector


def test_recovery_uses_first_population_boundary_after_equipment_source():
    store = GameplayEventStore()
    _equip(store)
    _cadence(store)
    result = ResourceRecoveryAuthorityService(store=store).recover(
        actor_ref=ACTOR, world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
        idempotency_key="recover-after-focus", expected_revision=2,
    )
    assert result.committed
    recovered = [event for event in store.read_stream(f"gameplay:resources:{ACTOR}") if event.event_type == "gameplay.resource.recovered"]
    assert len(recovered) == 1
    assert recovered[0].payload["delta"] == 5
    assert recovered[0].payload["modifier_effective_boundaries"][0]["effective_world_tick"] == 20


def test_recovery_duplicate_is_stable_after_durable_reopen_later_equipment_and_cadence(tmp_path):
    path = tmp_path / "recovery.sqlite"
    store = DurableGameplayEventStore(path)
    _, equipment, _ = _equip(store)
    _cadence(store)
    owner = ResourceRecoveryAuthorityService(store=store)
    first = owner.recover(actor_ref=ACTOR, world_ref="world", timeline_ref="timeline",
        confirmed_world_tick=20, idempotency_key="stable-recovery", expected_revision=2)
    assert first.committed
    store.close()

    store = DurableGameplayEventStore(path)
    _, equipment = _system(store)
    owner = ResourceRecoveryAuthorityService(store=store)
    owner = ResourceRecoveryAuthorityService(store=store)
    activation_id = next(iter(EquipmentProjector().rebuild(ACTOR, store.read_events()).activations))
    detached = equipment.unequip(command_id="cmd:unequip-after-recovery", actor_ref=ACTOR,
        activation_id=activation_id, destination_container_id="container:bag",
        body=BodyRuntimeProjection(ACTOR, {}, {}, {}, "body"), idempotency_key="unequip-after-recovery",
        causation_id="cause:later", correlation_id="corr:later")
    assert detached.committed
    _cadence(store, 40)
    replay = owner.recover(actor_ref=ACTOR, world_ref="world", timeline_ref="timeline",
        confirmed_world_tick=20, idempotency_key="stable-recovery", expected_revision=2)
    assert replay.idempotency_status == "duplicate_replayed"
    store.close()


def test_recovery_after_real_equipment_detach_uses_payload_source_transaction(tmp_path):
    path = tmp_path / "detach-recovery.sqlite"
    store = DurableGameplayEventStore(path)
    _, equipment, _ = _equip(store)
    _cadence(store)
    owner = ResourceRecoveryAuthorityService(store=store)
    first = owner.recover(actor_ref=ACTOR, world_ref="world", timeline_ref="timeline",
        confirmed_world_tick=20, idempotency_key="before-detach", expected_revision=2)
    assert first.committed
    activation_id = next(iter(EquipmentProjector().rebuild(ACTOR, store.read_events()).activations))
    assert equipment.unequip(command_id="cmd:detach-recovery", actor_ref=ACTOR,
        activation_id=activation_id, destination_container_id="container:bag",
        body=BodyRuntimeProjection(ACTOR, {}, {}, {}, "body"), idempotency_key="detach-recovery",
        causation_id="cause:detach", correlation_id="corr:detach").committed
    _cadence(store, 40)
    store.close()
    store = DurableGameplayEventStore(path)
    owner = ResourceRecoveryAuthorityService(store=store)
    result = owner.recover(actor_ref=ACTOR, world_ref="world", timeline_ref="timeline",
        confirmed_world_tick=40, idempotency_key="after-detach", expected_revision=4)
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    # The focus applies at 25/30/35; the detach boundary at 40 restores base recovery.
    assert event.payload["delta"] == 1  # capacity 10, previous current 9
    assert len(event.payload["modifier_effective_boundaries"]) == 2
    boundary = next(item for item in event.payload["modifier_effective_boundaries"]
                    if item["effective_world_tick"] == 40)
    assert store.get_event(boundary["source_event_id"]).event_type == "gameplay.modifier.source_deactivated"
    retry = owner.recover(actor_ref=ACTOR, world_ref="world", timeline_ref="timeline",
        confirmed_world_tick=40, idempotency_key="after-detach", expected_revision=4)
    assert retry.idempotency_status == "duplicate_replayed"
    assert retry.committed_event_ids == result.committed_event_ids
    events = store.read_stream(f"gameplay:resources:{ACTOR}")
    projector = ResourceBodyRuntimeProjector()
    full = projector.rebuild_resources(ACTOR, events)
    checkpoint = projector.rebuild_resources(ACTOR, events[:3])
    tail = projector.rebuild_resources(ACTOR, events[3:], checkpoint=checkpoint)
    assert tail == full
    assert full.entries["core.mana"].modifier_ledger == ()
    store.close()
