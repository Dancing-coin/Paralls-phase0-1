from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector
from app.gameplay.resource_materialization import (
    CharacterResourceMaterializationCaller,
    ResourceMaterializationAuthorityService,
)
from app.gameplay.settlement_plan import build_atomic_event_batch


PROFILE_DIR = Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"
STREAM = "gameplay:resources:char_a"


def _registry():
    return CharacterProfileRegistry.from_directory(PROFILE_DIR)


def _args(**changes):
    return dict(actor_ref="char_a", world_ref="world:bakery", timeline_ref="timeline:main",
                world_tick=0, idempotency_key="materialize:char_a", expected_revision=0) | changes


@pytest.mark.parametrize("value", [True, False, 0.0, -1])
def test_materialization_rejects_invalid_tick_before_replay(value):
    store = GameplayEventStore()
    owner = ResourceMaterializationAuthorityService(store=store, registry=_registry())
    assert owner.materialize(**_args()).committed
    before = store.read_events()
    with pytest.raises(ValueError, match="resource_world_tick_invalid"):
        owner.materialize(**_args(world_tick=value))
    assert store.read_events() == before


@pytest.mark.parametrize("changes", [dict(world_ref=""), dict(timeline_ref=""), dict(idempotency_key=""),
    dict(read_stream_revisions={"guard": True}), dict(read_stream_revisions={"guard": 0.0}),
    dict(read_stream_revisions={"": 0})])
def test_materialization_rejects_invalid_scope_key_or_read_set(changes):
    store = GameplayEventStore()
    owner = ResourceMaterializationAuthorityService(store=store, registry=_registry())
    with pytest.raises(ValueError):
        owner.materialize(**_args(**changes))
    assert not store.read_events()


def _replace_template(registry, **changes):
    profile = registry.get("char_a")
    template = profile.resource_template.model_copy(update=changes)
    registry._profiles_by_actor_id["char_a"] = profile.model_copy(update={"resource_template": template})


def test_original_materialization_receipt_recovers_without_current_content(tmp_path):
    path = tmp_path / "original-receipt.sqlite3"
    store = DurableGameplayEventStore(path)
    original = ResourceMaterializationAuthorityService(store=store, registry=_registry()).materialize(**_args())
    store.close()
    restored = DurableGameplayEventStore(path)
    try:
        owner = ResourceMaterializationAuthorityService(store=restored)
        retry = CharacterResourceMaterializationCaller(authority=owner).materialize(**_args(expected_revision=3))
        assert retry.committed_event_ids == original.committed_event_ids
        assert retry.idempotency_status == "duplicate_replayed"
        assert len(restored.read_stream(STREAM)) == 3
        with pytest.raises(ValueError, match="idempotency_key_reused"):
            owner.materialize(**_args(world_ref="world:main", expected_revision=3))
        with pytest.raises(ValueError, match="resource_template_source_unavailable"):
            owner.materialize(**_args(idempotency_key="new-key", expected_revision=3))
    finally:
        restored.close()


def test_caller_recovers_original_receipt_after_authored_policy_revocation():
    registry, store = _registry(), GameplayEventStore()
    owner = ResourceMaterializationAuthorityService(store=store, registry=registry)
    caller = CharacterResourceMaterializationCaller(authority=owner)
    original = caller.materialize(**_args())
    profile = registry.get("char_a")
    registry._profiles_by_actor_id["char_a"] = profile.model_copy(update={"resource_template": None})
    retry = caller.materialize(**_args(expected_revision=3))
    assert retry.committed_event_ids == original.committed_event_ids
    assert retry.idempotency_status == "duplicate_replayed"
    assert len(store.read_stream(STREAM)) == 3


def test_new_materialization_uses_immutable_composition_not_mutable_profile_reference():
    registry, store = _registry(), GameplayEventStore()
    owner = ResourceMaterializationAuthorityService(store=store, registry=registry)
    registry.get("char_a").resource_template.resources[0].initial = 1
    receipt = owner.materialize(**_args())
    assert receipt.committed
    assert store.read_stream(STREAM)[0].payload["current"] == 100


def test_materialization_does_not_rematerialize_an_actor_in_another_world():
    store = GameplayEventStore()
    owner = ResourceMaterializationAuthorityService(store=store, registry=_registry())
    assert owner.materialize(**_args()).committed
    with pytest.raises(ValueError, match="resource_already_materialized"):
        owner.materialize(**_args(world_ref="world:main", idempotency_key="other-world", expected_revision=3))
    assert len(store.read_stream(STREAM)) == 3


def test_profile_resource_capacity_rejects_maximum_above_capacity():
    from app.character_agent.profile.models import CharacterResourcePolicyEntry
    data = _registry().get("char_a").resource_template.resources[0].model_dump(mode="json")
    data.update(capacity=5, base_capacity=5, initial=1, maximum=100)
    with pytest.raises(ValueError, match="capacity_below_maximum"):
        CharacterResourcePolicyEntry.model_validate(data)


@pytest.mark.parametrize("actor", ["character:", "actor:char_a"])
def test_materialization_rejects_empty_or_unadmitted_actor_alias(actor):
    owner = ResourceMaterializationAuthorityService(store=GameplayEventStore(), registry=_registry())
    with pytest.raises(ValueError, match="resource_actor_"):
        owner.materialize(**_args(actor_ref=actor))


@pytest.mark.parametrize("changes, error", [
    (dict(valid_until_world_tick=0), "resource_template_confirmed_time_required"),
    (dict(read_principals=("other-reader",)), "resource_template_read_denied"),
])
def test_materialization_rejects_expired_or_unreadable_authored_policy(changes, error):
    registry, store = _registry(), GameplayEventStore()
    _replace_template(registry, **changes)
    owner = ResourceMaterializationAuthorityService(store=store, registry=registry)
    with pytest.raises(ValueError, match=error):
        owner.materialize(**_args(world_tick=1))
    assert not store.read_events()


def test_owner_rereads_registry_and_rejects_changed_frozen_policy():
    registry, store = _registry(), GameplayEventStore()
    frozen = registry.resource_template_source("char_a", world_ref="world:bakery", timeline_ref="timeline:main")
    _replace_template(registry, binding_revision="binding:changed@2")
    owner = ResourceMaterializationAuthorityService(store=store, registry=registry)
    with pytest.raises(ValueError, match="resource_template_source_changed"):
        owner.materialize(**_args(source=frozen))
    assert not store.read_events()


def test_materialization_rejects_new_key_and_changed_duplicate_without_writes():
    store = GameplayEventStore()
    owner = ResourceMaterializationAuthorityService(store=store, registry=_registry())
    first = owner.materialize(**_args())
    retry = owner.materialize(**_args(expected_revision=3))
    assert first.committed_event_ids == retry.committed_event_ids
    assert retry.idempotency_status == "duplicate_replayed"
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        owner.materialize(**_args(world_tick=1, expected_revision=3))
    with pytest.raises(ValueError, match="resource_already_materialized"):
        owner.materialize(**_args(idempotency_key="new-key", expected_revision=3))
    assert len(store.read_events()) == 3


def test_materialization_stale_read_set_rejects_entire_batch():
    store = GameplayEventStore()
    owner = ResourceMaterializationAuthorityService(store=store, registry=_registry())
    result = owner.materialize(**_args(read_stream_revisions={"population:guard": 1}))
    assert not result.committed
    assert not store.read_events()


def test_materialization_real_reopen_full_and_checkpoint_tail_with_adjustment(tmp_path):
    path = tmp_path / "resource-materialization.sqlite3"
    store = DurableGameplayEventStore(path)
    owner = ResourceMaterializationAuthorityService(store=store, registry=_registry())
    first = CharacterResourceMaterializationCaller(authority=owner).materialize(**_args())
    materialized = store.read_stream(STREAM)[0].payload
    assert materialized["resource_schema"] == "resource.v2"
    assert materialized["capacity"] == materialized["base_capacity"] == materialized["maximum"]
    assert materialized["locked"] == materialized["debt"] == materialized["debt_ceiling"] == 0
    projector = ResourceBodyRuntimeProjector()
    checkpoint = projector.rebuild_resources("char_a", store.read_stream(STREAM))
    boundary = store.get_last_global_sequence()
    assert store.append_batch(build_atomic_event_batch(
        command_id="resource:consume", principal_ref="gameplay_authority", stream_id=STREAM,
        expected_revision=3, event_specs=[("gameplay.resource.adjusted", {
            "actor_ref": "char_a", "resource_id": "core.stamina", "delta": -5,
        })], idempotency_key="consume", causation_id="cause:consume", correlation_id="corr:consume",
    )).committed
    store.close()
    reopened = DurableGameplayEventStore(path)
    restored_owner = ResourceMaterializationAuthorityService(store=reopened, registry=_registry())
    retry = CharacterResourceMaterializationCaller(authority=restored_owner).materialize(**_args(expected_revision=4))
    assert retry.idempotency_status == "duplicate_replayed"
    assert retry.committed_event_ids == first.committed_event_ids
    events = reopened.read_stream(STREAM)
    full = projector.rebuild_resources("char_a", events)
    tail = projector.rebuild_resources("char_a", [event for event in events if event.global_sequence > boundary], checkpoint=checkpoint)
    assert full == tail
    assert full.entries["core.stamina"].current == 95
    assert len(events) == 4
    assert all(event.visibility_policy == "authority_only" for event in events[:3])
    assert full.entries["core.stamina"].definition_version == "character-template:char_a@1"
    reopened.close()


def test_materialization_rejects_incomplete_duplicate_receipt(monkeypatch):
    store = GameplayEventStore()
    owner = ResourceMaterializationAuthorityService(store=store, registry=_registry())
    first = owner.materialize(**_args())
    original_get = store.get_by_idempotency

    def incomplete_receipt(principal_ref, idempotency_key):
        result = original_get(principal_ref, idempotency_key)
        if result is not None:
            return result.model_copy(update={"committed_event_ids": result.committed_event_ids[:1]}, deep=True)
        return None

    monkeypatch.setattr(store, "get_by_idempotency", incomplete_receipt)
    before = store.read_events()
    with pytest.raises(ValueError, match="resource_receipt_incomplete"):
        owner.materialize(**_args(expected_revision=3))
    assert store.read_events() == before
    assert first.committed_event_ids == [event.event_id for event in store.read_stream(STREAM)]


@pytest.mark.parametrize("corruption", ["missing_transaction", "payload", "visibility", "revision_vector"])
def test_materialization_rejects_inconsistent_duplicate_transaction(monkeypatch, corruption):
    store = GameplayEventStore()
    owner = ResourceMaterializationAuthorityService(store=store, registry=_registry())
    first = owner.materialize(**_args())
    transaction = store.get_transaction(first.transaction_id)
    before = store.read_events()
    if corruption == "revision_vector":
        damaged = first.model_copy(update={"resulting_stream_revisions": {STREAM: 1}}, deep=True)
        monkeypatch.setattr(store, "get_by_idempotency", lambda *args: damaged)
    elif corruption == "missing_transaction":
        monkeypatch.setattr(store, "get_transaction", lambda *args: None)
    else:
        event = transaction.events[0]
        changes = {"payload": dict(event.payload, current=1)} if corruption == "payload" else {"visibility_policy": "project"}
        damaged_event = event.model_copy(update=changes, deep=True)
        damaged_transaction = transaction.model_copy(update={"events": [damaged_event, *transaction.events[1:]]}, deep=True)
        monkeypatch.setattr(store, "get_transaction", lambda *args: damaged_transaction)
    with pytest.raises(ValueError, match="resource_receipt_incomplete"):
        owner.materialize(**_args(expected_revision=3))
    assert store.read_events() == before
