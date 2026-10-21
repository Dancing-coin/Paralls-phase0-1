from dataclasses import replace
from fractions import Fraction

import pytest

from app.gameplay.action_window_runtime import ActionTemporalContext, freeze_action_time_binding
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.p5.investigation_conflict import InvestigationConflictAuthority
from test_action_conflict_window import _command, _graph, _intent, _registry, _seed_source, _snapshot, ROLE_REF
from test_temporal_mapping_contract import configured_clock


def context():
    clock, mapping = configured_clock()
    mapping = replace(mapping, ratio=Fraction(1), max_lateness=10)
    return ActionTemporalContext(clock=clock, mapping=mapping, source_revision="source@1",
                                 sampled_at=0, received_at=1, cutoff_tick=1,
                                 late_input_policy_ref="policy:reject-late", ordering_policy_ref="policy:atomic")


def bound_intent(ctx):
    intent = _intent()
    return intent.model_copy(update={"time_binding": freeze_action_time_binding(
        intent, ctx, idempotency_key=_command().idempotency_key,
        expected_authority_revisions=dict(_command().expected_revisions))})


def resolve(owner, intent, ctx):
    return owner.resolve_action_window(command=_command(), intent=intent, graph=_graph(),
                                      spatial_snapshot=_snapshot(), role_ref=ROLE_REF, now="operational-only",
                                      temporal_context=ctx, require_temporal_binding=True)


def owner_store():
    store = GameplayEventStore()
    _seed_source(store)
    return InvestigationConflictAuthority(registry=_registry(), store=store), store


def test_owner_freezes_actual_event_time_and_replays_before_current_time_validation():
    owner, store = owner_store()
    ctx = context()
    intent = bound_intent(ctx)
    first = resolve(owner, intent, ctx)
    assert first.committed
    event = store.get_event(first.receipt.committed_event_ids[0])
    assert event.payload["time_binding"] == intent.time_binding.model_dump(mode="json")
    assert event.payload["time_binding"]["settlement_window"]["frozen_read_set"]
    duplicate = resolve(owner, intent, replace(ctx, received_at=1000))
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.receipt.committed_event_ids == first.receipt.committed_event_ids
    changed = intent.model_copy(update={"time_binding": intent.time_binding.model_copy(update={"received_at": 2})})
    assert resolve(owner, changed, ctx).error_code == "action_window_idempotency_reused"


@pytest.mark.parametrize("change", ["missing", "timeline", "mapping", "source", "profile", "late", "window"])
def test_owner_rejects_unbound_stale_or_changed_temporal_inputs_zero_write(change):
    owner, store = owner_store()
    ctx = context()
    intent = bound_intent(ctx)
    if change == "missing":
        intent = _intent()
    elif change == "mapping":
        ctx = replace(ctx, mapping=replace(ctx.mapping, revision="2"))
    elif change == "source":
        ctx = replace(ctx, source_revision="source@2")
    elif change == "profile":
        ctx.clock.temporal_profile = replace(ctx.clock.temporal_profile, revision="2")
    elif change == "timeline":
        ctx.clock.timeline = replace(ctx.clock.timeline, timeline_id="other")
    elif change == "late":
        ctx = replace(ctx, received_at=2)
    elif change == "window":
        intent = intent.model_copy(update={"window_start_tick": 1, "window_end_tick": 2})
    result = resolve(owner, intent, ctx)
    assert not result.committed
    assert result.error_code
    assert store.get_stream_head(next(iter(_command().expected_revisions))) == 0


def test_clock_cannot_confirm_action_after_cutoff():
    ctx = context()
    ctx.clock.tick = 2
    with pytest.raises(ValueError, match="cutoff"):
        bound_intent(ctx)


@pytest.mark.parametrize("field,value", [
    ("cutoff_tick", 2), ("sampled_at", 1), ("source_revision", "source@2"),
    ("settlement_window", {"window_ref": "changed"}),
])
def test_changed_duplicate_cannot_replace_frozen_time_input(field, value):
    owner, store = owner_store()
    ctx = context()
    intent = bound_intent(ctx)
    first = resolve(owner, intent, ctx)
    changed = intent.model_copy(update={"time_binding": intent.time_binding.model_copy(update={field: value})})
    assert resolve(owner, changed, ctx).error_code == "action_window_idempotency_reused"
    stream = next(iter(_command().expected_revisions))
    assert store.get_stream_head(stream) == 4
    assert [event.event_type for event in store.read_stream(stream)] == [
        "gameplay.conflict.encounter_started",
        "gameplay.conflict.action_window_resolved",
        "gameplay.conflict.control_changed",
        "gameplay.conflict.encounter_closed",
    ]
    assert not store.read_stream(stream, event_type="gameplay.conflict.terminal_outcome_recorded")
    assert first.committed


def test_owner_preserves_legacy_event_without_claiming_time_evidence():
    owner, store = owner_store()
    result = owner.resolve_action_window(command=_command(), intent=_intent(), graph=_graph(),
                                        spatial_snapshot=_snapshot(), role_ref=ROLE_REF, now="legacy")
    assert result.committed
    assert "time_binding" not in store.get_event(result.receipt.committed_event_ids[0]).payload
    assert resolve(owner, _intent(), None).idempotency_status == "duplicate_replayed"


def test_owner_rechecks_actual_write_revision_after_temporal_admission():
    owner, store = owner_store()
    ctx = context()
    intent = bound_intent(ctx)
    command = _command().model_copy(update={"expected_revisions": {next(iter(_command().expected_revisions)): 1}})
    intent = intent.model_copy(update={"time_binding": freeze_action_time_binding(
        intent, ctx, idempotency_key=command.idempotency_key,
        expected_authority_revisions=dict(command.expected_revisions))})
    result = owner.resolve_action_window(command=command, intent=intent, graph=_graph(),
                                        spatial_snapshot=_snapshot(), role_ref=ROLE_REF, now="operational-only",
                                        temporal_context=ctx, require_temporal_binding=True)
    assert result.error_code == "action_window_conflict_revision_stale"
    assert store.get_stream_head(next(iter(command.expected_revisions))) == 0


def test_durable_restart_preserves_time_pins_and_original_receipt(tmp_path):
    path = tmp_path / "action.sqlite"
    ctx = context()
    intent = bound_intent(ctx)
    store = DurableGameplayEventStore(path)
    _seed_source(store)
    first = resolve(InvestigationConflictAuthority(registry=_registry(), store=store), intent, ctx)
    assert first.committed
    pins = store.get_event(first.receipt.committed_event_ids[0]).payload["time_binding"]
    store.close()
    restored = DurableGameplayEventStore(path)
    try:
        owner = InvestigationConflictAuthority(registry=_registry(), store=restored)
        duplicate = resolve(owner, intent, None)
        assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
        assert duplicate.receipt.committed_event_ids == first.receipt.committed_event_ids
        assert restored.get_event(first.receipt.committed_event_ids[0]).payload["time_binding"] == pins
        stream = next(iter(_command().expected_revisions))
        assert restored.get_stream_head(stream) == 4
        assert not restored.read_stream(stream, event_type="gameplay.conflict.terminal_outcome_recorded")
    finally:
        restored.close()
