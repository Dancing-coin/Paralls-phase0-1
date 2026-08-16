from __future__ import annotations

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Recipe
from app.gameplay.ecology_runtime import EcologyHazardAuthority, EcologyWeatherFrontPropagationPolicy
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from backend.tests.test_infra_ecology_weather_front_construction_edge import _record_ecology, _propagate


def _setup():
    store = GameplayEventStore()
    ecology = _record_ecology(store)
    assert _propagate(store, ecology).committed
    construction = ConstructionProductionAuthority(store=store)
    runs = tuple(
        construction.start_run(
            facility=Facility(facility_ref=facility_ref, plot_ref="plot:fanout", facility_kind="mill", condition=1, revision=0),
            recipe=Recipe(recipe_ref=f"recipe:{facility_ref}", inputs={}, output_item="item:bread", duration_ticks=1),
            run_ref=f"run:{facility_ref}", tick=0,
        )
        for facility_ref in ("facility:fanout:a", "facility:fanout:b")
    )
    return store, ecology, construction, runs


def test_weather_front_construction_fanout_writes_two_existing_target_streams_in_one_batch() -> None:
    store, ecology, construction, runs = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance_fanout(
        facility_refs=tuple(run.facility_ref for run in runs), region_ref="region:edge:target"
    )
    assert error is None and intent is not None
    expected = {f"gameplay:construction_production:{run.facility_ref}": store.get_stream_head(f"gameplay:construction_production:{run.facility_ref}") for run in runs}
    result = construction.settle_canonical_weather_front_maintenance_fanout(
        command=intent.command, admission=intent.admission, runs=runs,
        obligation_refs=("obligation:fanout:a", "obligation:fanout:b"), command_id="command:fanout",
        idempotency_key="construction:fanout", causation_id="event:weather", correlation_id="corr:weather",
        expected_revisions=expected,
    )
    assert result.committed
    assert [store.read_stream(f"gameplay:construction_production:{run.facility_ref}")[-1].event_type for run in runs] == [
        "gameplay.construction_production.maintenance_obligation_created",
        "gameplay.construction_production.maintenance_obligation_created",
    ]


def test_weather_front_construction_fanout_rejects_missing_admission_without_write() -> None:
    store, ecology, construction, runs = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance_fanout(facility_refs=tuple(run.facility_ref for run in runs), region_ref="region:edge:target")
    assert error is None and intent is not None
    expected = {f"gameplay:construction_production:{run.facility_ref}": store.get_stream_head(f"gameplay:construction_production:{run.facility_ref}") for run in runs}
    before = len(store.read_events())
    denied = construction.settle_canonical_weather_front_maintenance_fanout(command=intent.command, admission=None, runs=runs, obligation_refs=("a", "b"), command_id="command:denied", idempotency_key="fanout:denied", causation_id="cause", correlation_id="corr", expected_revisions=expected)
    assert denied.failure is not None and denied.failure.error_code == "weather_front_maintenance_fanout_admission_required"
    assert len(store.read_events()) == before


def test_weather_front_construction_fanout_is_revisioned_idempotent_private_and_replayable() -> None:
    store, ecology, construction, runs = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance_fanout(facility_refs=tuple(run.facility_ref for run in runs), region_ref="region:edge:target")
    assert error is None and intent is not None
    expected = {f"gameplay:construction_production:{run.facility_ref}": store.get_stream_head(f"gameplay:construction_production:{run.facility_ref}") for run in runs}
    first = construction.settle_canonical_weather_front_maintenance_fanout(command=intent.command, admission=intent.admission, runs=runs, obligation_refs=("a", "b"), command_id="command:first", idempotency_key="fanout:one", causation_id="cause", correlation_id="corr", expected_revisions=expected)
    duplicate = construction.settle_canonical_weather_front_maintenance_fanout(command=intent.command, admission=intent.admission, runs=runs, obligation_refs=("a", "b"), command_id="command:first", idempotency_key="fanout:one", causation_id="cause", correlation_id="corr", expected_revisions=expected)
    before = len(store.read_events())
    stale = construction.settle_canonical_weather_front_maintenance_fanout(command=intent.command, admission=intent.admission, runs=runs, obligation_refs=("c", "d"), command_id="command:stale", idempotency_key="fanout:stale", causation_id="cause", correlation_id="corr", expected_revisions={key: 0 for key in expected})
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before
    assert all(entry.audience == "project" for entry in store.list_outbox()[-2:])
    from app.gameplay.replay import GameplayProjectionReplay
    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="infra-weather-construction-fanout", projector_version="1")
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(replay.create_checkpoint(events[:-1]), events[-1:]).projection_hash


def test_weather_front_construction_fanout_rejects_changed_duplicate_and_private_command_without_write() -> None:
    store, ecology, construction, runs = _setup()
    intent, error = ecology.admit_weather_front_to_construction_maintenance_fanout(facility_refs=tuple(run.facility_ref for run in runs), region_ref="region:edge:target")
    assert error is None and intent is not None
    expected = {f"gameplay:construction_production:{run.facility_ref}": store.get_stream_head(f"gameplay:construction_production:{run.facility_ref}") for run in runs}
    assert construction.settle_canonical_weather_front_maintenance_fanout(command=intent.command, admission=intent.admission, runs=runs, obligation_refs=("a", "b"), command_id="command:changed", idempotency_key="fanout:changed", causation_id="cause", correlation_id="corr", expected_revisions=expected).committed
    before = len(store.read_events())
    changed = construction.settle_canonical_weather_front_maintenance_fanout(command=intent.command, admission=intent.admission, runs=runs, obligation_refs=("c", "d"), command_id="command:changed-2", idempotency_key="fanout:changed", causation_id="cause", correlation_id="corr", expected_revisions=expected)
    private = construction.settle_canonical_weather_front_maintenance_fanout(command=intent.command.model_copy(update={"privacy_scope": "authority_only"}), admission=intent.admission, runs=runs, obligation_refs=("e", "f"), command_id="command:private", idempotency_key="fanout:private", causation_id="cause", correlation_id="corr", expected_revisions=expected)
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert private.failure is not None and private.failure.error_code == "weather_front_maintenance_fanout_source_denied"
    assert len(store.read_events()) == before
