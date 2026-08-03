import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.effective_stats import EffectiveStatResolver, StatBaseline
from app.gameplay.status_tags import StatusTagAuthorityService, StatusTagCommand, StatusTagDefinition, StatusTagModifierTemplate, StatusTagProjector, StatusTagRegistry, active_status_tag_modifiers
from app.gameplay.status_tags import StatusTagError


def _command(operation: str, tag_id: str, command_id: str, **extra: object) -> StatusTagCommand:
    values = {"command_id": command_id, "actor_ref": "actor:a", "authority_principal": "gameplay_authority", "idempotency_key": command_id, "payload_digest": f"sha256:{command_id}", "causation_id": command_id, "correlation_id": "corr:tag", "operation": operation, "tag_id": tag_id, "source_ref": "source:test"}
    values.update(extra)
    return StatusTagCommand(**values)


def test_unique_stack_and_explicit_expiry_replay_through_event_store() -> None:
    registry = StatusTagRegistry()
    registry.register(StatusTagDefinition(tag_id="poisoned", definition_version="1", stack_policy="stack_count", max_stacks=2))
    service = StatusTagAuthorityService(store=GameplayEventStore(), registry=registry)
    first = service.apply(_command("apply", "poisoned", "cmd:apply:1"))
    second = service.apply(_command("apply", "poisoned", "cmd:apply:2"))
    expired = service.apply(_command("expire", "poisoned", "cmd:expire", instance_id="tag:cmd:apply:1"))

    assert first.accepted and second.accepted and expired.accepted
    assert second.projection.active_instances["tag:cmd:apply:1"].stack_count == 2
    assert expired.projection.active_instances == {}


def test_exclusive_and_max_stack_reject_before_event_append() -> None:
    registry = StatusTagRegistry()
    registry.register(StatusTagDefinition(tag_id="guarded", definition_version="1", exclusivity_group="stance"))
    registry.register(StatusTagDefinition(tag_id="prone", definition_version="1", exclusivity_group="stance"))
    registry.register(StatusTagDefinition(tag_id="burning", definition_version="1", stack_policy="stack_count", max_stacks=1))
    store = GameplayEventStore()
    service = StatusTagAuthorityService(store=store, registry=registry)

    assert service.apply(_command("apply", "guarded", "cmd:guarded")).accepted
    assert service.apply(_command("apply", "prone", "cmd:prone")).reason_code == "status_tag_conflict"
    assert service.apply(_command("apply", "burning", "cmd:burning:1")).accepted
    assert service.apply(_command("apply", "burning", "cmd:burning:2")).reason_code == "status_tag_max_stacks_reached"
    assert [event.event_type for event in store.read_events()] == ["gameplay.status_tag.applied", "gameplay.status_tag.applied"]


def test_active_tag_modifier_is_typed_and_expires_with_its_source() -> None:
    registry = StatusTagRegistry()
    registry.register(StatusTagDefinition(tag_id="blessed", definition_version="1", modifier_templates=(StatusTagModifierTemplate(template_id="power", stat_id="combat.power", operation="additive", value="2", stacking_key="blessed-power"),)))
    store = GameplayEventStore()
    service = StatusTagAuthorityService(store=store, registry=registry)
    applied = service.apply(_command("apply", "blessed", "cmd:blessed"))
    baseline = StatBaseline(stat_id="combat.power", value="10", source_ref="profile")

    active = EffectiveStatResolver().resolve(baseline, active_status_tag_modifiers(applied.projection, registry))
    expired = service.apply(_command("expire", "blessed", "cmd:blessed:expire", instance_id="tag:cmd:blessed"))
    inactive = EffectiveStatResolver().resolve(baseline, active_status_tag_modifiers(expired.projection, registry))

    assert active.effective_value == 12
    assert inactive.effective_value == 10


def test_remove_and_authority_mismatch_are_explicit_and_idempotency_does_not_repeat_event() -> None:
    registry = StatusTagRegistry()
    registry.register(StatusTagDefinition(tag_id="wet", definition_version="1"))
    store = GameplayEventStore()
    service = StatusTagAuthorityService(store=store, registry=registry)
    applied = _command("apply", "wet", "cmd:wet")

    assert service.apply(applied).accepted
    assert service.apply(applied).accepted
    removed = service.apply(_command("remove", "wet", "cmd:wet:remove", instance_id="tag:cmd:wet"))
    assert removed.accepted and removed.projection.active_instances == {}
    assert [event.event_type for event in store.read_events()] == ["gameplay.status_tag.applied", "gameplay.status_tag.removed"]

    with pytest.raises(StatusTagError, match="status_tag_authority_mismatch"):
        service.apply(_command("apply", "wet", "cmd:untrusted", authority_principal="godot_client"))


def test_status_tag_checkpoint_plus_tail_rebuild_matches_full_projection() -> None:
    registry = StatusTagRegistry()
    registry.register(StatusTagDefinition(tag_id="wet", definition_version="1"))
    store = GameplayEventStore()
    service = StatusTagAuthorityService(store=store, registry=registry)
    assert service.apply(_command("apply", "wet", "cmd:checkpoint:wet")).accepted
    assert service.apply(_command("remove", "wet", "cmd:checkpoint:dry", instance_id="tag:cmd:checkpoint:wet")).accepted
    events = store.read_events()
    projector = StatusTagProjector(registry)

    full = projector.rebuild("actor:a", events)
    checkpointed = projector.rebuild("actor:a", events[1:], checkpoint=projector.rebuild("actor:a", events[:1]))

    assert checkpointed.active_instances == full.active_instances == {}
    assert checkpointed.source_revision_vector == full.source_revision_vector
