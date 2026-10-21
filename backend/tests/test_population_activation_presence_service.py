from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.event_store import DurableGameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_presence import PopulationActivationPresenceService
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import CharacterSpawnRequest, PopulationPresenceAuthority


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _proposal(**overrides):
    values = {
        "proposal_id": "proposal:presence:1",
        "profile_ref": "character:char_a",
        "world_ref": "world:bakery",
        "package_revision": "package:bakery-authored-agents:v1",
        "policy_revision": "policy:population:v1",
        "activation_reason": "population-cadence",
        "scope_grant": ("actor:self",),
        "cadence_class": "simulation",
        "expected_revisions": {"population:world:bakery": 0},
        "idempotency_key": "activation:presence:1",
        "correlation_id": "corr:presence:1",
        "source_ref": "population:siming",
    }
    values.update(overrides)
    return ActivationProposal(**values)


def _service():
    store = GameplayEventStore()
    grant = ActivationGrant(
        profile_ref="character:char_a",
        world_ref="world:bakery",
        package_revision="package:bakery-authored-agents:v1",
        policy_revision="policy:population:v1",
        scope_grant=("actor:self",),
    )
    activation = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        store=store,
        grants=(grant,),
    )
    return store, PopulationActivationPresenceService(
        store=store,
        activation_authority=activation,
        presence_authority=PopulationPresenceAuthority(store=store),
    )


def test_activation_presence_reuses_activation_receipt_after_partial_success():
    store, service = _service()
    first = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:1", presence_expected_revision=99
    )
    assert first.activation.committed
    assert first.presence is not None and not first.presence.committed
    assert first.recovery_required
    assert len(store.read_stream("population:world:bakery")) == 1

    retry = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:1", presence_expected_revision=0
    )
    assert retry.activation.committed
    assert retry.activation.idempotency_status == "duplicate_replayed"
    assert retry.presence is not None and retry.presence.committed
    assert len(store.read_stream("population:world:bakery")) == 1
    assert len(store.read_stream("presence:world:bakery")) == 1
    alive = store.read_events(event_type="gameplay.character.life_state_changed")
    assert len(alive) == 1
    assert alive[0].payload["from_state"] == "unknown"
    assert alive[0].payload["to_state"] == "alive"
    assert alive[0].payload["incarnation"] == 1
    assert alive[0].schema_version == 2


def test_activation_presence_rejects_without_existing_grant_and_writes_nothing():
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR), store=store
    )
    service = PopulationActivationPresenceService(
        store=store,
        activation_authority=authority,
        presence_authority=PopulationPresenceAuthority(store=store),
    )
    result = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:denied", presence_expected_revision=0
    )
    assert not result.activation.committed
    assert result.activation.stop_reason == "activation_source_unauthorized"
    assert result.presence is None
    assert store.read_events() == []


def test_activation_presence_partial_success_recovers_after_durable_reopen(tmp_path):
    path = tmp_path / "population-presence.sqlite"
    store = DurableGameplayEventStore(path)
    _, service = _service_with_store(store)
    first = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:durable:1", presence_expected_revision=99
    )
    assert first.activation.committed and first.recovery_required
    assert first.presence is not None and not first.presence.committed
    store.close()

    reopened = DurableGameplayEventStore(path)
    activation = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        store=reopened,
        grants=(ActivationGrant(
            profile_ref="character:char_a",
            world_ref="world:bakery",
            package_revision="package:bakery-authored-agents:v1",
            policy_revision="policy:population:v1",
            scope_grant=("actor:self",),
        ),),
    )
    restored = PopulationActivationPresenceService(
        store=reopened,
        activation_authority=activation,
        presence_authority=PopulationPresenceAuthority(store=reopened),
    )
    retry = restored.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:durable:1", presence_expected_revision=0
    )
    assert retry.activation.committed
    assert retry.activation.idempotency_status == "duplicate_replayed"
    assert retry.presence is not None and retry.presence.committed
    assert len(reopened.read_stream("population:world:bakery")) == 1
    assert len(reopened.read_stream("presence:world:bakery")) == 1
    assert len(reopened.read_events(event_type="gameplay.character.life_state_changed")) == 1
    reopened.close()


def _service_with_store(store):
    grant = ActivationGrant(
        profile_ref="character:char_a",
        world_ref="world:bakery",
        package_revision="package:bakery-authored-agents:v1",
        policy_revision="policy:population:v1",
        scope_grant=("actor:self",),
    )
    activation = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR), store=store, grants=(grant,)
    )
    return store, PopulationActivationPresenceService(
        store=store,
        activation_authority=activation,
        presence_authority=PopulationPresenceAuthority(store=store),
    )


def _resource_service(store):
    from app.gameplay.resource_materialization import (
        CharacterResourceMaterializationCaller, ResourceMaterializationAuthorityService,
    )
    _, service = _service_with_store(store)
    service.resource_materialization_caller = CharacterResourceMaterializationCaller(
        authority=ResourceMaterializationAuthorityService(
            store=store, registry=service.activation_authority.registry,
        ),
    )
    return service


def _spawn_resources(service, tick=0, timeline="population:world:bakery"):
    return service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:resources", presence_expected_revision=0,
        resource_timeline_ref=timeline, resource_world_tick=tick,
    )


def test_activation_resource_handoff_durable_receipt_later_tick_and_new_authorities(tmp_path):
    path = tmp_path / "activation-resources.sqlite"
    store = DurableGameplayEventStore(path)
    first = _spawn_resources(_resource_service(store))
    assert first.activation.committed and first.presence.committed
    assert first.resources.committed and not first.recovery_required
    events = store.read_stream("gameplay:resources:char_a")
    assert {event.payload["resource_id"] for event in events} == {
        "core.stamina", "core.mana", "core.action_points",
    }
    assert len(events) == 3 and len({event.transaction_id for event in events}) == 1
    assert all(event.visibility_policy == "authority_only" for event in events)
    assert len(store.read_events(event_type="gameplay.character.life_state_changed")) == 1
    ids = first.resources.committed_event_ids
    store.close()

    reopened = DurableGameplayEventStore(path)
    service = _resource_service(reopened)
    retry = _spawn_resources(service, tick=10)
    assert retry.resources.committed_event_ids == ids
    assert retry.resources.idempotency_status == "duplicate_replayed"
    assert not retry.recovery_required
    assert len(reopened.read_stream("gameplay:resources:char_a")) == 3
    wrong_timeline = _spawn_resources(service, tick=10, timeline="timeline:other")
    assert wrong_timeline.recovery_required
    assert wrong_timeline.resource_stop_reason == "resource_idempotency_key_reused"
    reopened.close()


def test_presence_despawn_and_new_incarnation_do_not_repeat_alive_transition():
    from app.population_continuity.presence_runtime import CharacterDespawnRequest

    store, service = _service()
    first = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:first", presence_expected_revision=0
    )
    assert first.presence is not None and first.presence.committed
    assert first.presence.incarnation == 1
    service.presence_authority.despawn(CharacterDespawnRequest(
        world_ref="world:bakery", character_ref="character:char_a", incarnation=1,
        reason="explicit-departure", idempotency_key="despawn:first", expected_revision=1,
    ))
    second = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:second", presence_expected_revision=2
    )
    assert second.presence is not None and second.presence.committed
    assert second.presence.incarnation == 2
    alive = store.read_events(event_type="gameplay.character.life_state_changed")
    assert len(alive) == 1
    assert alive[0].payload["incarnation"] == 1


def test_initial_alive_lifecycle_recovers_after_durable_reopen(tmp_path):
    path = tmp_path / "presence-life-state.sqlite"
    store = DurableGameplayEventStore(path)
    _, service = _service_with_store(store)
    first = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:life-durable", presence_expected_revision=0
    )
    assert first.presence is not None and first.presence.committed
    initial_events = store.read_events(event_type="gameplay.character.life_state_changed")
    assert len(initial_events) == 1
    event_ids = [event.event_id for event in initial_events]
    store.close()

    reopened = DurableGameplayEventStore(path)
    _, restored = _service_with_store(reopened)
    retry = restored.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:life-durable", presence_expected_revision=0
    )
    assert retry.presence is not None and retry.presence.idempotency_status == "duplicate_replayed"
    assert [event.event_id for event in reopened.read_events(event_type="gameplay.character.life_state_changed")] == event_ids
    reopened.close()


def test_initial_alive_owner_replays_its_durable_receipt_after_reopen(tmp_path):
    from app.gameplay.life_state_runtime import CanonicalLifeStateAuthority

    path = tmp_path / "presence-life-owner-replay.sqlite"
    store = DurableGameplayEventStore(path)
    _, service = _service_with_store(store)
    result = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:owner-replay", presence_expected_revision=0
    )
    assert result.presence is not None and result.presence.committed
    activation = store.get_event(result.activation.committed_event_ids[0])
    presence = store.get_event(result.presence.committed_event_ids[0])
    original = store.read_events(event_type="gameplay.character.life_state_changed")[0]
    store.close()

    reopened = DurableGameplayEventStore(path)
    replay = CanonicalLifeStateAuthority(store=reopened).initialize_alive_from_presence(
        activation_event_id=activation.event_id,
        presence_event_id=presence.event_id,
        expected_activation_revision=activation.stream_revision,
        expected_presence_revision=presence.stream_revision,
        command_id=f"life-state:presence:{presence.event_id}",
        idempotency_key=f"life-state:presence:{presence.event_id}",
        causation_id=presence.event_id,
        correlation_id=activation.correlation_id,
    )
    assert replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == [original.event_id]
    assert len(reopened.read_events(event_type="gameplay.character.life_state_changed")) == 1
    reopened.close()


def test_application_retry_rejects_tampered_initial_alive_transaction():
    store, service = _service()
    first = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:life-tampered", presence_expected_revision=0
    )
    alive = store.read_events(event_type="gameplay.character.life_state_changed")[0]
    original = store.get_transaction(alive.transaction_id)
    get_transaction = store.get_transaction
    tampered = original.model_copy(update={"events": [
        alive.model_copy(update={"schema_version": 1}, deep=True)
    ]}, deep=True)
    store.get_transaction = lambda transaction_id: (
        tampered if transaction_id == alive.transaction_id else get_transaction(transaction_id)
    )
    count = len(store.read_events())
    retry = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:life-tampered", presence_expected_revision=0
    )
    assert first.presence.committed and retry.presence.committed
    assert retry.recovery_required
    assert retry.life_state_stop_reason == "life_state_idempotency_key_reused"
    assert retry.life_state is not None and not retry.life_state.committed
    assert retry.resource_stop_reason is None
    assert len(store.read_events()) == count


def test_initial_alive_owner_rejects_activation_from_untrusted_transaction():
    from app.gameplay.life_state_runtime import CanonicalLifeStateAuthority

    store, service = _service()
    activation = service.activation_authority.commit(_proposal())
    presence = service.presence_authority.spawn(CharacterSpawnRequest(
        world_ref="world:bakery", character_ref="character:char_a",
        activation_event_id=activation.committed_event_ids[0], idempotency_key="presence:owner-source",
        expected_revision=0,
    ))
    assert activation.committed and presence.committed
    activation = store.get_event(activation.committed_event_ids[0])
    presence = store.get_event(presence.committed_event_ids[0])
    tx = store.get_transaction(activation.transaction_id)
    assert tx is not None
    forged = tx.idempotency_record.model_copy(update={"principal_ref": "untrusted:caller"})
    original_get_transaction = store.get_transaction
    store.get_transaction = lambda transaction_id: (
        tx.model_copy(update={"idempotency_record": forged}, deep=True)
        if transaction_id == activation.transaction_id else original_get_transaction(transaction_id)
    )
    rejected = CanonicalLifeStateAuthority(store=store).initialize_alive_from_presence(
        activation_event_id=activation.event_id,
        presence_event_id=presence.event_id,
        expected_activation_revision=activation.stream_revision,
        expected_presence_revision=presence.stream_revision,
        command_id="life-state:forged-source",
        idempotency_key="life-state:forged-source",
        causation_id=presence.event_id,
        correlation_id=activation.correlation_id,
    )
    assert not rejected.committed
    assert rejected.failure.error_code == "life_state_presence_source_invalid"


def test_activation_resource_partial_failure_recovers_without_repeating_domain_events(tmp_path):
    path = tmp_path / "activation-resources-recovery.sqlite"
    store = DurableGameplayEventStore(path)
    service = _resource_service(store)
    caller = service.resource_materialization_caller
    original = caller.materialize

    def conflict(**request):
        return original(**{**request, "expected_revision": 99})

    caller.materialize = conflict
    first = _spawn_resources(service)
    assert first.activation.committed and first.presence.committed
    assert first.recovery_required and not first.resources.committed
    assert store.read_stream("gameplay:resources:char_a") == []
    store.close()
    reopened = DurableGameplayEventStore(path)
    recovered = _spawn_resources(_resource_service(reopened), tick=10)
    assert recovered.resources.committed and not recovered.recovery_required
    assert len(reopened.read_stream("population:world:bakery")) == 1
    assert len(reopened.read_stream("presence:world:bakery")) == 1
    assert len(reopened.read_stream("gameplay:resources:char_a")) == 3
    reopened.close()


def test_activation_resource_handoff_rejects_despanwed_presence_without_resource_write():
    from app.population_continuity.presence_runtime import CharacterDespawnRequest
    store, service = _service()
    first = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="presence:resources", presence_expected_revision=0,
    )
    assert first.presence.committed
    service.presence_authority.despawn(CharacterDespawnRequest(
        world_ref="world:bakery", character_ref="character:char_a", incarnation=1,
        reason="explicit-departure", idempotency_key="despawn:resource-test", expected_revision=1,
    ))
    hook = _resource_service(store)
    result = _spawn_resources(hook)
    assert result.recovery_required
    assert result.resource_stop_reason == "activation_resource_presence_inactive"
    assert store.read_stream("gameplay:resources:char_a") == []


def test_activation_resource_duplicate_rejects_tampered_receipt_metadata(tmp_path):
    path = tmp_path / "activation-resources-tampered.sqlite"
    store = DurableGameplayEventStore(path)
    first = _spawn_resources(_resource_service(store))
    assert first.resources is not None and first.resources.committed
    original = store.get_transaction(first.resources.transaction_id)
    assert original is not None
    store.close()

    reopened = DurableGameplayEventStore(path)
    tampered_event = original.events[0].model_copy(update={"schema_version": 2}, deep=True)
    tampered = original.model_copy(update={"events": [tampered_event, *original.events[1:]]}, deep=True)
    get_transaction = reopened.get_transaction
    reopened.get_transaction = lambda transaction_id: (
        tampered if transaction_id == first.resources.transaction_id else get_transaction(transaction_id)
    )
    retry = _spawn_resources(_resource_service(reopened), tick=10)
    assert retry.recovery_required
    assert retry.resource_stop_reason == "resource_idempotency_key_reused"
    reopened.close()
