from dataclasses import replace
from fractions import Fraction

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.status_tags import (
    StatusTagAuthorityService,
    StatusTagCommand,
    StatusTagDefinition,
    StatusTagRegistry,
    StatusTagTemporalContext,
)
from app.world_runtime.scheduling import select_temporal_work
from app.world_runtime.temporal_contracts import ClockMapping, SimulationTime


def _context(*, step: int = 10, mapping_revision: str = "1", timeline_id: str = "world:1") -> StatusTagTemporalContext:
    mapping = ClockMapping(
        mapping_id="physics",
        revision=mapping_revision,
        source_clock_ref="physics",
        source_unit_ref="frame",
        target_timeline_ref=timeline_id,
        target_profile_revision="profile:1",
        source_origin=0,
        target_origin=0,
        ratio=Fraction(1),
        rounding_policy="exact",
        valid_source_interval=(0, 1000),
        max_lateness=0,
        evidence_source_policy_ref="test",
    )
    return StatusTagTemporalContext(
        now=SimulationTime(timeline_id, step, Fraction(step)),
        mapping=mapping,
        profile_revision="profile:1",
        source_revision="physics:1",
        evidence_freshness=0,
    )


def _command(operation: str, command_id: str, **extra: object) -> StatusTagCommand:
    values = {
        "command_id": command_id,
        "actor_ref": "actor:a",
        "authority_principal": "gameplay_authority",
        "idempotency_key": command_id,
        "payload_digest": f"sha256:{command_id}",
        "causation_id": command_id,
        "correlation_id": "corr:status",
        "operation": operation,
        "tag_id": "timed",
        "source_ref": "source:test",
    }
    values.update(extra)
    return StatusTagCommand(**values)


def _service() -> tuple[StatusTagAuthorityService, GameplayEventStore]:
    registry = StatusTagRegistry()
    registry.register(StatusTagDefinition(tag_id="timed", definition_version="1"))
    store = GameplayEventStore()
    return StatusTagAuthorityService(store=store, registry=registry), store


def test_timed_status_freezes_temporal_reference_and_expires_via_scheduled_owner_request():
    service, store = _service()
    accepted = service.apply(_command("apply", "apply:1"), temporal=_context(step=10), expires_after_steps=5)
    assert accepted.accepted
    instance = next(iter(accepted.projection.active_instances.values()))
    assert instance.expiry is not None
    assert instance.expiry.due_step == 15

    work = service.expiration_work(accepted.projection)
    selected, deferred = select_temporal_work((work,), now=_context(step=15).now, budget=1)
    assert not deferred
    expired = service.submit_expiration_request(selected[0], temporal=_context(step=15))
    assert expired.accepted
    assert expired.projection.active_instances == {}
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.status_tag.applied",
        "gameplay.status_tag.expired",
    ]


@pytest.mark.parametrize(
    "temporal, expected",
    [(_context(step=14), "status_tag_not_due"), (_context(step=15, mapping_revision="2"), "status_tag_mapping_stale")],
)
def test_expiration_request_revalidates_due_time_and_mapping(temporal, expected):
    service, _ = _service()
    accepted = service.apply(_command("apply", "apply:stale"), temporal=_context(step=10), expires_after_steps=5)
    request = service.expiration_work(accepted.projection)
    with pytest.raises(ValueError, match=expected):
        service.submit_expiration_request(request, temporal=temporal)


def test_duplicate_expiration_request_and_changed_duplicate_are_owner_idempotent():
    service, store = _service()
    temporal = _context(step=10)
    accepted = service.apply(_command("apply", "apply:dup"), temporal=temporal, expires_after_steps=5)
    request = service.expiration_work(accepted.projection)
    first = service.submit_expiration_request(request, temporal=_context(step=15))
    second = service.submit_expiration_request(request, temporal=_context(step=15))
    assert first.accepted and second.accepted
    assert len(store.read_events()) == 2
    changed = replace(request, expected_revision_vector=(("gameplay:status_tags:actor:a", 999),))
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        service.submit_expiration_request(changed, temporal=_context(step=15))


def test_checkpoint_tail_recovery_preserves_expiry_and_old_event_has_no_fabricated_time():
    service, store = _service()
    legacy = service.apply(_command("apply", "apply:legacy"))
    assert legacy.accepted
    legacy_instance = next(iter(legacy.projection.active_instances.values()))
    assert legacy_instance.expiry is None
    assert service.apply(_command("remove", "remove:legacy", instance_id=legacy_instance.instance_id)).accepted

    timed = service.apply(_command("apply", "apply:new"), temporal=_context(step=10), expires_after_steps=5)
    events = store.read_events()
    # Historical schema-v1 events have neither expiry nor a request fingerprint.
    events[:2] = [event.model_copy(update={"payload": {
        key: value for key, value in event.payload.items() if key != "request_fingerprint"
    }}) for event in events[:2]]
    projector = service.projector
    full = projector.rebuild("actor:a", events)
    checkpoint = projector.rebuild("actor:a", events[:1])
    tail = projector.rebuild("actor:a", events[1:], checkpoint=checkpoint)
    assert tail.active_instances == full.active_instances
    assert next(item for item in tail.active_instances.values() if item.instance_id == "tag:apply:new").expiry.due_step == 15
    legacy_event = next(event for event in events if event.event_id == "evt:apply:legacy:status-tag")
    assert "expiry" not in legacy_event.payload


def test_multiple_deadlines_and_permanent_state_produce_independent_work():
    service, store = _service()
    service._registry.register(StatusTagDefinition(tag_id="permanent", definition_version="1"))
    assert service.expiration_works(service.projector.rebuild("actor:a", [])) == ()
    service.apply(_command("apply", "permanent", tag_id="permanent"))
    service._registry.register(StatusTagDefinition(tag_id="other", definition_version="1"))
    service.apply(_command("apply", "one"), temporal=_context(), expires_after_steps=5)
    result = service.apply(_command("apply", "two", tag_id="other"), temporal=_context(), expires_after_steps=5)
    works = service.expiration_works(result.projection)
    assert len(works) == 2
    service.submit_expiration_request(works[0], temporal=_context(step=15))
    with pytest.raises(ValueError, match="status_tag_revision_stale"):
        service.submit_expiration_request(works[1], temporal=_context(step=15))
    # A fresh owner read and complete revalidation creates successor work.
    projection = service.projector.rebuild("actor:a", store.read_events())
    service.submit_expiration_request(service.expiration_works(projection)[0], temporal=_context(step=15))
    assert len(service.projector.rebuild("actor:a", store.read_events()).active_instances) == 1


@pytest.mark.parametrize("change", [dict(source_ref="changed"), dict(tag_id="changed"), dict(operation="remove")])
def test_changed_apply_duplicate_cannot_hide_behind_caller_digest(change):
    service, _ = _service()
    command = _command("apply", "same")
    service.apply(command)
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        service.apply(command.model_copy(update=change))


def test_changed_duration_duplicate_is_rejected_and_exact_returns_original_receipt():
    service, _ = _service()
    command = _command("apply", "duration")
    first = service.apply(command, temporal=_context(), expires_after_steps=5)
    duplicate = service.apply(command, temporal=_context(), expires_after_steps=5)
    assert duplicate.append_result == first.append_result
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        service.apply(command, temporal=_context(), expires_after_steps=6)


def test_changed_expiration_work_time_pins_cannot_reuse_receipt():
    service, _ = _service()
    result = service.apply(_command("apply", "pins"), temporal=_context(), expires_after_steps=5)
    work = service.expiration_work(result.projection)
    service.submit_expiration_request(work, temporal=_context(step=15))
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        service.submit_expiration_request(replace(work, due_time=_context(step=16).now), temporal=_context(step=16))


def test_time_migration_exact_retry_replays_and_changed_source_revision_is_rejected():
    service, store = _service()
    applied = service.apply(_command("apply", "migration-source"), temporal=_context(step=10), expires_after_steps=5)
    stream_id = "gameplay:status_tags:actor:a"
    migration = {
        "actor_ref": "actor:a",
        "migration_id": "migration:status:1",
        "expected_revision": store.get_stream_head(stream_id),
        "old_context": _context(step=10),
        "new_context": _context(step=10, mapping_revision="2"),
        "old_profile_revision": "profile:1",
        "new_profile_revision": "profile:2",
        "old_step_duration": Fraction(1),
        "new_step_duration": Fraction(2),
        "boundary_tick": 10,
    }

    first = service.migrate_time(**migration)
    exact_retry = service.migrate_time(**migration)
    assert first.committed and exact_retry.committed
    assert exact_retry.committed_event_ids == first.committed_event_ids

    changed = {**migration, "new_context": replace(migration["new_context"], source_revision="physics:changed")}
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        service.migrate_time(**changed)
    assert len(store.read_events()) == 2


def test_time_migration_receipt_survives_durable_reopen_with_new_authority(tmp_path):
    from app.gameplay.event_store import DurableGameplayEventStore

    path = tmp_path / "status-migration.sqlite"
    first_store = DurableGameplayEventStore(path)
    registry = StatusTagRegistry()
    registry.register(StatusTagDefinition(tag_id="timed", definition_version="1"))
    first_service = StatusTagAuthorityService(store=first_store, registry=registry)
    first_service.apply(_command("apply", "durable-migration-source"), temporal=_context(step=10), expires_after_steps=5)
    migration = {
        "actor_ref": "actor:a", "migration_id": "migration:durable",
        "expected_revision": first_store.get_stream_head("gameplay:status_tags:actor:a"),
        "old_context": _context(step=10), "new_context": _context(step=10, mapping_revision="2"),
        "old_profile_revision": "profile:1", "new_profile_revision": "profile:2",
        "old_step_duration": Fraction(1), "new_step_duration": Fraction(2), "boundary_tick": 10,
    }
    first = first_service.migrate_time(**migration)
    first_store.close()

    reopened = DurableGameplayEventStore(path)
    new_registry = StatusTagRegistry()
    new_registry.register(StatusTagDefinition(tag_id="timed", definition_version="1"))
    new_service = StatusTagAuthorityService(store=reopened, registry=new_registry)
    duplicate = new_service.migrate_time(**migration)
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    reopened.close()
