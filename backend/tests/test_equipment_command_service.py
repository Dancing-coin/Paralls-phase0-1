"""Allowlisted production admission contract tests, using real domain owners."""
from pathlib import Path
from hashlib import sha256

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.ability_runtime import AbilityDefinitionRegistry
from app.gameplay.equipment_runtime import EquipmentDefinitionRegistry, EquipmentProfile, EquipmentRuntimeError, EquipmentSlotDefinition
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.modifier_runtime import ModifierDefinitionRegistry
from app.gameplay.resource_materialization import CharacterResourceMaterializationCaller, ResourceMaterializationAuthorityService
from app.gameplay.resource_modifier_admission import ResourceModifierMappingRegistry, register_mana_focus_content
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_presence import PopulationActivationPresenceService
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import CharacterDespawnRequest, PopulationPresenceAuthority
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService, EmbodiedControllerEnrollment
from app.services.equipment_command_service import EquipmentCommand, EquipmentCommandService, EquipmentContentSource, EquipmentWorldScope


ACTOR = "char_a"
CHARACTER = "character:char_a"
WORLD = "world:bakery"


def _auth(actor_id="char_a"):
    auth = EmbodiedControllerAuthService()
    secret = auth.create_trusted_local_launch_credential(actor_id=actor_id,
        controller_instance_id="controller:equipment", issued_at=1, expires_at=100)
    bound = auth.bind_controller(EmbodiedControllerEnrollment(
        credential_kind="trusted_local_launch", credential=secret, actor_id=actor_id,
        controller_instance_id="controller:equipment", protocol_version=1),
        remote_host="127.0.0.1", now=2, connection_ref="connection:equipment")
    assert bound.accepted
    return auth


def _service(store, auth, scope=None, content_source=None):
    inventory = InventoryDefinitionRegistry()
    inventory.register_item(ItemDefinition("item:sword", "1", 1, 1))
    equipment = EquipmentDefinitionRegistry()
    equipment.register_profile("item:sword", EquipmentProfile("profile:sword", ("right_hand",)))
    return EquipmentCommandService(store=store, controller_auth=auth,
        scope_resolver=scope or (lambda: EquipmentWorldScope(WORLD, "timeline:main")),
        inventory_registry=inventory, equipment_registry=equipment,
        ability_registry=AbilityDefinitionRegistry(), modifier_registry=ModifierDefinitionRegistry(),
        slots=(EquipmentSlotDefinition("right_hand"),), content_source=content_source), inventory


def _admit_presence(store):
    profiles = CharacterProfileRegistry.from_directory(
        Path(__file__).resolve().parents[2] / "assets/characters/profiles")
    grant = ActivationGrant(profile_ref=CHARACTER, world_ref=WORLD,
        package_revision="package:bakery-authored-agents:v1", policy_revision="policy:population:v1",
        scope_grant=("actor:self",))
    service = PopulationActivationPresenceService(store=store,
        activation_authority=ProfileActivationAuthority(registry=profiles, store=store, grants=(grant,)),
        presence_authority=PopulationPresenceAuthority(store=store),
        resource_materialization_caller=CharacterResourceMaterializationCaller(
            authority=ResourceMaterializationAuthorityService(store=store, registry=profiles)))
    result = service.commit_and_spawn(ActivationProposal(
        proposal_id="proposal:equipment", profile_ref=CHARACTER, world_ref=WORLD,
        package_revision=grant.package_revision, policy_revision=grant.policy_revision,
        activation_reason="population-cadence", scope_grant=("actor:self",), cadence_class="simulation",
        expected_revisions={f"population:{WORLD}": 0}, idempotency_key="equipment:activation",
        correlation_id="correlation:equipment", source_ref="population:siming"),
        presence_idempotency_key="equipment:presence", presence_expected_revision=0,
        resource_timeline_ref="timeline:main", resource_world_tick=0)
    assert result.presence.committed
    assert result.resources is not None and result.resources.committed, result.resource_stop_reason


def _inventory(store, registry):
    owner = InventoryAuthorityService(store=store, registry=registry)
    assert owner.create_container(command_id="equipment:bag", actor_ref=ACTOR,
        spec=ContainerSpec("container:bag", 10, 10, 4), idempotency_key="equipment:bag",
        causation_id="cause", correlation_id="corr").committed
    assert owner.instantiate(command_id="equipment:item", actor_ref=ACTOR,
        item_id="sword:1", definition_id="item:sword", quantity=1, container_id="container:bag",
        idempotency_key="equipment:item", causation_id="cause", correlation_id="corr").committed


def _command(**changes):
    data = dict(command_id="equip:1", actor_id="char_a", world_ref=WORLD,
        timeline_ref="timeline:main", incarnation=1, operation="equip", item_id="sword:1",
        container_id="container:bag", slot_key="right_hand", idempotency_key="equip:1",
        causation_id="intent:equip:1", correlation_id="correlation:equip:1")
    data.update(changes)
    return EquipmentCommand(**data)


def _setup(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "equipment.sqlite")
    auth = _auth()
    service, registry = _service(store, auth)
    _admit_presence(store)
    _inventory(store, registry)
    return store, auth, service


def test_real_owner_chain_equips_and_replays_after_durable_close_reopen(tmp_path):
    store, _, service = _setup(tmp_path)
    first = service.submit(_command(), connection_ref="connection:equipment")
    assert first.committed
    batch = store.get_transaction(first.transaction_id)
    assert batch.idempotency_record.principal_ref == "actor_gameplay.equipment_domain"
    assert batch.read_stream_revisions[f"presence:{WORLD}"] == 1
    assert batch.read_stream_revisions[f"gameplay:body:{ACTOR}"] == 0
    assert [event.event_type for event in batch.events] == [
        "gameplay.inventory.item_equipped", "gameplay.equipment.activation_started"]
    count = len(store.read_events())
    store.close()
    reopened = DurableGameplayEventStore(tmp_path / "equipment.sqlite")
    replacement, _ = _service(reopened, _auth())
    duplicate = replacement.submit(_command(), connection_ref="connection:equipment")
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert len(reopened.read_events()) == count
    with pytest.raises(EquipmentRuntimeError, match="idempotency_key_reused"):
        replacement.submit(_command(slot_key="left_hand"), connection_ref="connection:equipment")
    assert len(reopened.read_events()) == count
    reopened.close()


def test_registered_mana_focus_content_uses_production_admission_and_resource_bridge(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "formal-content.sqlite")
    inventory = InventoryDefinitionRegistry()
    equipment = EquipmentDefinitionRegistry()
    modifiers = ModifierDefinitionRegistry()
    mappings = ResourceModifierMappingRegistry()
    register_mana_focus_content(inventory=inventory, equipment=equipment,
                                modifiers=modifiers, mappings=mappings)
    service = EquipmentCommandService(store=store, controller_auth=_auth(),
        scope_resolver=lambda: EquipmentWorldScope(WORLD, "timeline:main"),
        inventory_registry=inventory, equipment_registry=equipment,
        ability_registry=AbilityDefinitionRegistry(), modifier_registry=modifiers,
        slots=(EquipmentSlotDefinition("charm"),), resource_modifier_mappings=mappings)
    _admit_presence(store)
    inventory_owner = InventoryAuthorityService(store=store, registry=inventory)
    assert inventory_owner.create_container(command_id="focus:bag", actor_ref=ACTOR,
        spec=ContainerSpec("container:bag", 10, 10, 4), idempotency_key="focus:bag",
        causation_id="cause", correlation_id="corr").committed
    assert inventory_owner.instantiate(command_id="focus:item", actor_ref=ACTOR,
        item_id="focus:1", definition_id="item:mana-focus-charm@1", quantity=1,
        container_id="container:bag", idempotency_key="focus:item",
        causation_id="cause", correlation_id="corr").committed
    result = service.submit(_command(item_id="focus:1", slot_key="charm"), connection_ref="connection:equipment")
    assert result.committed
    resources = ResourceBodyRuntimeProjector().rebuild_resources(ACTOR,
        store.read_stream(f"gameplay:resources:{ACTOR}"))
    assert resources.entries["core.mana"].modifier_ledger[0]["amount"] == 1
    duplicate = service.submit(_command(item_id="focus:1", slot_key="charm"), connection_ref="connection:equipment")
    assert duplicate.idempotency_status == "duplicate_replayed"
    store.close()


@pytest.mark.parametrize("change,error", [
    ({"timeline_ref": "timeline:other"}, "equipment_world_timeline_mismatch"),
    ({"world_ref": "world:other"}, "equipment_world_timeline_mismatch"),
    ({"incarnation": 2}, "equipment_presence_invalid"),
    ({"actor_id": "char_b"}, "controller_binding_subject_mismatch"),
])
def test_wrong_scope_or_incarnation_is_zero_write(tmp_path, change, error):
    store, _, service = _setup(tmp_path)
    before = len(store.read_events())
    with pytest.raises(EquipmentRuntimeError, match=error):
        service.submit(_command(**change), connection_ref="connection:equipment")
    assert len(store.read_events()) == before
    store.close()


def test_despawned_actor_cannot_change_equipment(tmp_path):
    store, _, service = _setup(tmp_path)
    assert PopulationPresenceAuthority(store=store).despawn(CharacterDespawnRequest(
        world_ref=WORLD, character_ref=CHARACTER, incarnation=1, reason="left-world",
        expected_revision=1, idempotency_key="despawn:equipment")).committed
    before = len(store.read_events())
    with pytest.raises(EquipmentRuntimeError, match="equipment_presence_invalid"):
        service.submit(_command(), connection_ref="connection:equipment")
    assert len(store.read_events()) == before
    store.close()


def test_controller_is_resolved_again_immediately_before_owner_append(tmp_path, monkeypatch):
    store, auth, service = _setup(tmp_path)
    original = auth.resolve_controller_binding
    calls = 0
    def resolve(**kwargs):
        nonlocal calls
        calls += 1
        result = original(**kwargs)
        if calls >= 3:
            return result.model_copy(update={"accepted": False, "binding": None, "error_code": "controller_revoked"})
        return result
    monkeypatch.setattr(auth, "resolve_controller_binding", resolve)
    before = len(store.read_events())
    with pytest.raises(EquipmentRuntimeError, match="controller_revoked"):
        service.submit(_command(), connection_ref="connection:equipment")
    assert len(store.read_events()) == before
    store.close()


def test_content_source_change_before_append_is_rejected_without_write(tmp_path, monkeypatch):
    path = tmp_path / "equipment.yaml"
    path.write_text("revision: equipment-content@1\n", encoding="utf-8")
    def load():
        raw = path.read_bytes()
        return EquipmentContentSource(raw.decode().strip().split(": ")[1],
                                      "sha256:" + sha256(raw).hexdigest())
    store = DurableGameplayEventStore(tmp_path / "content-race.sqlite")
    auth = _auth()
    service, inventory = _service(store, auth, content_source=load)
    _admit_presence(store)
    _inventory(store, inventory)
    resolve = auth.resolve_controller_binding
    calls = 0
    def mutate_before_append(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            path.write_text("revision: equipment-content@2\n", encoding="utf-8")
        return resolve(**kwargs)
    monkeypatch.setattr(auth, "resolve_controller_binding", mutate_before_append)
    before = len(store.read_events())
    with pytest.raises(EquipmentRuntimeError, match="equipment_content_source_changed"):
        service.submit(_command(), connection_ref="connection:equipment")
    assert len(store.read_events()) == before
    store.close()


def test_exact_replay_uses_persisted_content_pin_after_source_rotation(tmp_path):
    source = [EquipmentContentSource("equipment-content@1", "sha256:" + "1" * 64)]
    store = DurableGameplayEventStore(tmp_path / "content-replay.sqlite")
    service, inventory = _service(store, _auth(), content_source=lambda: source[0])
    _admit_presence(store)
    _inventory(store, inventory)
    first = service.submit(_command(), connection_ref="connection:equipment")
    assert first.committed
    batch = store.get_transaction(first.transaction_id)
    assert batch.pinned_revisions["equipment-content-revision:equipment-content@1"] == 1
    assert batch.pinned_revisions["equipment-content-digest:sha256:" + "1" * 64] == 1
    count = len(store.read_events())
    source[0] = EquipmentContentSource("equipment-content@2", "sha256:" + "2" * 64)
    with pytest.raises(EquipmentRuntimeError, match="equipment_content_source_changed"):
        service.submit(_command(idempotency_key="equip:new"), connection_ref="connection:equipment")
    store.close()
    store = DurableGameplayEventStore(tmp_path / "content-replay.sqlite")
    service, _ = _service(store, _auth(), content_source=lambda: source[0])
    replay = service.submit(_command(), connection_ref="connection:equipment")
    assert replay.idempotency_status == "duplicate_replayed"
    assert replay.command_id == first.command_id
    with pytest.raises(EquipmentRuntimeError, match="idempotency_key_reused"):
        service.submit(_command(correlation_id="changed"), connection_ref="connection:equipment")
    assert len(store.read_events()) == count
    store.close()


def test_presence_racing_owner_append_is_rejected_by_shared_store_read_pins(tmp_path, monkeypatch):
    store, _, service = _setup(tmp_path)
    original = store.append_batch
    def append(batch):
        monkeypatch.setattr(store, "append_batch", original)
        assert PopulationPresenceAuthority(store=store).despawn(CharacterDespawnRequest(
            world_ref=WORLD, character_ref=CHARACTER, incarnation=1, reason="left-world",
            expected_revision=1, idempotency_key="despawn:race")).committed
        return original(batch)
    monkeypatch.setattr(store, "append_batch", append)
    result = service.submit(_command(), connection_ref="connection:equipment")
    assert not result.committed
    assert not store.read_events(event_type="gameplay.equipment.activation_started")
    store.close()


def test_owner_response_lost_then_exact_retry_recovers_and_unequips(tmp_path, monkeypatch):
    store, _, service = _setup(tmp_path)
    original = store.append_batch
    def lose_response(batch):
        result = original(batch)
        assert result.committed
        raise ConnectionError("owner response lost after Durable commit")
    monkeypatch.setattr(store, "append_batch", lose_response)
    with pytest.raises(ConnectionError, match="response lost"):
        service.submit(_command(), connection_ref="connection:equipment")
    store.close()
    reopened = DurableGameplayEventStore(tmp_path / "equipment.sqlite")
    replacement, _ = _service(reopened, _auth())
    recovered = replacement.submit(_command(), connection_ref="connection:equipment")
    assert recovered.idempotency_status == "duplicate_replayed"
    activation = reopened.get_event(recovered.committed_event_ids[-1]).payload["activation_id"]
    unequip = replacement.submit(_command(command_id="unequip:1", operation="unequip",
        item_id="", slot_key="", activation_id=activation, idempotency_key="unequip:1"),
        connection_ref="connection:equipment")
    assert unequip.committed
    assert reopened.get_event(unequip.committed_event_ids[-1]).event_type == "gameplay.equipment.activation_ended"
    reopened.close()


@pytest.mark.parametrize("mutation", ["range", "vector", "payload", "digest"])
def test_tampered_receipt_is_rejected_without_new_writes(tmp_path, monkeypatch, mutation):
    store, _, service = _setup(tmp_path)
    first = service.submit(_command(), connection_ref="connection:equipment")
    before = len(store.read_events())
    if mutation in {"range", "vector"}:
        original = store.get_by_idempotency
        def result(*args, **kwargs):
            receipt = original(*args, **kwargs)
            if receipt is None:
                return receipt
            return receipt.model_copy(update={"global_sequence_range": (1, 999)} if mutation == "range"
                else {"resulting_stream_revisions": {}})
        monkeypatch.setattr(store, "get_by_idempotency", result)
    elif mutation == "payload":
        original = store.get_event
        def event(event_id):
            value = original(event_id)
            if event_id == first.committed_event_ids[-1]:
                return value.model_copy(update={"payload": {**value.payload, "slot_key": "forged"}})
            return value
        monkeypatch.setattr(store, "get_event", event)
    else:
        original = store.get_transaction
        def transaction(transaction_id):
            value = original(transaction_id)
            return value.model_copy(update={"result_digest": "forged"}) if transaction_id == first.transaction_id else value
        monkeypatch.setattr(store, "get_transaction", transaction)
    with pytest.raises(EquipmentRuntimeError, match="equipment_admission_receipt_invalid"):
        service.submit(_command(), connection_ref="connection:equipment")
    assert len(store.read_events()) == before
    store.close()
