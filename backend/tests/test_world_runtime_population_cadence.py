from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.character_agent.models.simulation_seed import CharacterContinuityReceipt
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupViewProjector
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.siming_contracts import PopulationReadSet
from app.services.siming_population_capability import PopulationSimulationCapability
from app.population_continuity.world import WorldContinuityRuntime


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:test",
        mode="simulation",
        revision="mode:test:v1",
        cadence_class="daily",
        batch_limit=3,
        wake_budget=3,
        catch_up_limit=2,
        degraded_threshold=20,
    )


def test_world_runtime_builds_replayable_population_cadence_from_committed_world_revision() -> None:
    store = GameplayEventStore()
    runtime = WorldContinuityRuntime(store=store, mode=_mode())
    receipt = runtime.resume()

    cadence = runtime.build_population_cadence(window_start=10, window_end=11)

    assert receipt.committed
    assert cadence.cadence_id == "cadence:world:test:10"
    assert cadence.cadence_source_ref == "world:world:test"
    assert cadence.cadence_source_revision == 1
    assert cadence.base_revision_vector == {"world:world:test": 1}
    assert cadence.selector_revision == "selector:generic:population:v1"
    assert cadence.base_checkpoint_digest.startswith("sha256:")


def test_world_runtime_cadence_uses_revision_heads_without_scanning_history() -> None:
    store = GameplayEventStore()
    runtime = WorldContinuityRuntime(store=store, mode=_mode())
    runtime.resume()

    def fail_history_scan(**_: object) -> list[object]:
        raise AssertionError("cadence construction must not scan the event history")

    store.read_events = fail_history_scan  # type: ignore[method-assign]

    cadence = runtime.build_population_cadence(window_start=10, window_end=11)

    assert cadence.cadence_source_revision == 1


def test_world_runtime_cadence_does_not_read_unrelated_stream_heads() -> None:
    store = GameplayEventStore()
    runtime = WorldContinuityRuntime(store=store, mode=_mode())
    runtime.resume()

    store.get_stream_heads = lambda: (_ for _ in ()).throw(  # type: ignore[method-assign]
        AssertionError("cadence construction must only read its declared world stream")
    )

    cadence = runtime.build_population_cadence(window_start=10, window_end=11)

    assert cadence.base_revision_vector == {"world:world:test": 1}


def test_world_runtime_rejects_an_empty_population_window() -> None:
    runtime = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())

    with pytest.raises(ValueError, match="population_cadence_window_invalid"):
        runtime.build_population_cadence(window_start=10, window_end=10)


def test_world_runtime_builds_all_twelve_resident_b0_previews() -> None:
    store = GameplayEventStore()
    runtime = WorldContinuityRuntime(store=store, mode=_mode())
    runtime.resume()
    cadence = runtime.build_population_cadence(window_start=3, window_end=4)

    projections = runtime.build_population_projections(cadence)

    assert len(projections) == 12
    assert len({item.payload["actor_ref"] for item in projections}) == 12
    assert projections[0].payload["actor_ref"] == "character:resident_01"
    assert projections[0].payload["candidate_kind"] == "routine_work"
    assert projections[0].payload["starvation_credit"] > 0
    assert projections[0].payload["simulation_tick_cursor"] == 4
    assert projections[0].payload["from_tick"] == 0
    assert projections[0].payload["to_tick"] == 4
    assert projections[0].payload["due_obligation_refs"] == ()
    assert "threshold_refs" in projections[0].payload["presentation_seed"]
    assert set(projections[0].payload["state_deltas"]) == {
        "last_update_tick",
        "activity_phase",
        "fatigue",
        "need_pressure",
        "next_due_tick",
        "starvation_credit",
    }
    assert projections[0].revision_vector == cadence.base_revision_vector


def test_world_runtime_carries_redacted_population_view_into_projection_payload() -> None:
    store = GameplayEventStore()
    runtime = WorldContinuityRuntime(store=store, mode=_mode())
    runtime.resume()
    cadence = runtime.build_population_cadence(window_start=3, window_end=4)
    registry = StateGroupRegistry()
    registry.register(
        StateGroupDefinition(
            group_id="character.commitments",
            definition_version="1.0.0",
            projection_schema_version=1,
            shared_fields=("next_due_tick", "private_note"),
            population_allowed_fields=("next_due_tick",),
        )
    )
    state = CharacterGameRuntimeStateBuilder(registry).build(
        actor_ref="character:resident_01",
        enabled_group_ids=("character.commitments",),
        group_payloads={
            "character.commitments": {"next_due_tick": 120, "private_note": "hidden"}
        },
        source_revision_vector={"world:world:test": 1},
        registry_revision="registry:test",
        world_config_revision="world:test",
        active_patch_set_revision="patch:test",
    )
    view = StateGroupViewProjector([], registry=registry).population_view(
        state,
        allowed_group_ids=("character.commitments",),
    )

    projections = runtime.build_population_projections(
        cadence,
        population_views={"character:resident_01": view},
    )
    payload = next(item.payload for item in projections if item.payload["actor_ref"] == "character:resident_01")

    assert payload["population_state"] == {
        "character.commitments": {"next_due_tick": 120}
    }
    assert "private_note" not in str(payload)


def test_main_publishes_one_generic_cadence_for_the_world_window() -> None:
    import app.main as main
    from app.services.authority_event_bus import InMemoryAuthorityEventBus

    store = GameplayEventStore()
    runtime = WorldContinuityRuntime(store=store, mode=_mode())
    runtime.resume()
    main.authority_event_bus = InMemoryAuthorityEventBus()
    main.siming_event_pipeline = SimpleNamespace(drain_observatory_messages=lambda: None)

    event = main.publish_population_cadence_window(
        world_runtime=runtime,
        window_start=3,
        window_end=4,
        room_id="room:test",
        scene_id="scene:test",
        zone_id="zone:test",
        causation_id="cause:test",
        correlation_id="corr:test",
    )

    assert event is not None
    assert event.payload["population_cadence"]["selector_revision"] == "selector:generic:population:v1"
    assert len(event.payload["population_projections"]) == 12


class _RecordingContinuityPort:
    def __init__(self) -> None:
        self.revisions: dict[str, int] = {}
        self.commands = []

    def current_revision(self, actor_ref: str) -> int:
        return self.revisions.get(actor_ref, 0)

    def apply_command(self, command):
        before = self.current_revision(command.actor_ref)
        self.revisions[command.actor_ref] = before + 1
        self.commands.append(command)
        return CharacterContinuityReceipt(
            receipt_ref=f"receipt:{command.command_id}",
            command_id=command.command_id,
            actor_ref=command.actor_ref,
            status="committed",
            character_revision_before=before,
            character_revision_after=before + 1,
            cursor_vector={},
        )


def test_twelve_residents_publish_b0_results_without_character_core_writes() -> None:
    runtime = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    runtime.resume()
    continuity = _RecordingContinuityPort()
    capability = PopulationSimulationCapability(continuity_port=continuity)

    for window_start in range(12):
        cadence = runtime.build_population_cadence(
            window_start=window_start,
            window_end=window_start + 1,
        )
        read_set = PopulationReadSet.from_inputs(
            cadence,
            runtime.build_population_projections(cadence),
        )
        result = capability.run_default_decision_cycle(cadence, read_set)
        assert result.status == "accepted"

    assert continuity.revisions == {}
    assert continuity.commands == []
