from __future__ import annotations

from app.services.siming_quality_monitor import SimingQualityMonitor


def _state_tree(*, suspicion_heat: object = None) -> object:
    from app.models.siming_runtime_state import (
        GroupSimulationBranchSnapshot,
        StateTreeNode,
        StateTreeSnapshot,
    )

    character_summary: dict[str, object] = {"target_actor_id": "char_b"}
    if suspicion_heat is not None:
        character_summary["suspicion_heat"] = suspicion_heat

    def node(node_id: str, owner_system: str, summary: dict[str, object]) -> StateTreeNode:
        return StateTreeNode(
            node_id=node_id,
            owner_system=owner_system,
            authority="mirror",
            status="fresh",
            summary=summary,
        )

    return StateTreeSnapshot(
        snapshot_id="state_tree:room:1",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room:1",
        scene_id="scene:1",
        zone_id="zone:1",
        world_ts=100,
        sim_tick_ts=100,
        causation_id="cause:1",
        correlation_id="corr:1",
        environment=node("env", "esm", {}),
        character=node("char_b", "character_agent", character_summary),
        storyline=node("storyline", "siming", {}),
        group_simulation=GroupSimulationBranchSnapshot(status="fresh", summary={}),
    )


def _narrative() -> object:
    from app.models.siming_narrative import NarrativeCoreResult, NarrativeObligationLedger

    return NarrativeCoreResult(
        state=_narrative_state(),
        ledger=NarrativeObligationLedger(
            ledger_id="ledger:narrative:room:1",
            room_id="room:1",
            world_ts=100,
            sim_tick_ts=100,
            causation_id="cause:1",
            correlation_id="corr:1",
        ),
        seeds=[],
    )


def _narrative_state() -> object:
    from app.models.siming_narrative import NarrativeStateSnapshot

    return NarrativeStateSnapshot(
        snapshot_id="narrative:1",
        schema_version=1,
        producer_system="siming.narrative_core",
        room_id="room:1",
        scene_id="scene:1",
        zone_id="zone:1",
        world_ts=100,
        sim_tick_ts=100,
        active_phase="setup",
        pressure_level="low",
        open_threads=[],
        active_markers=[],
        causation_id="cause:1",
        correlation_id="corr:1",
    )


def _suspicion_dimension(state_tree: object) -> object:
    result = SimingQualityMonitor().evaluate(state_tree=state_tree, narrative=_narrative())
    return result.snapshot.dimensions["suspicion_heat_distribution"]


def test_suspicion_dimension_is_unavailable_only_when_source_absent() -> None:
    dimension = _suspicion_dimension(_state_tree())

    assert dimension.status == "unavailable"
    assert "absent" in dimension.reason


def test_present_but_calm_suspicion_is_measured_not_unavailable() -> None:
    dimension = _suspicion_dimension(_state_tree(suspicion_heat={"char_a": 0.1, "char_b": 0.2}))

    assert dimension.status == "fresh"
    assert dimension.score == 0.0
    assert dimension.reason == "suspicion heat within bounds"


def test_concentrated_suspicion_is_a_high_severity_signal() -> None:
    dimension = _suspicion_dimension(_state_tree(suspicion_heat={"char_a": 0.95}))

    assert dimension.status == "stale"
    assert dimension.score == 0.9


def test_spread_suspicion_is_medium_severity() -> None:
    dimension = _suspicion_dimension(
        _state_tree(suspicion_heat={"char_a": 0.9, "char_b": 0.85})
    )

    assert dimension.status == "partial"
    assert dimension.score == 0.6


def test_non_numeric_heat_values_are_ignored_not_coerced() -> None:
    dimension = _suspicion_dimension(
        _state_tree(suspicion_heat={"char_a": True, "char_b": "0.99", "char_c": 0.1})
    )

    # Forged booleans and strings must not become measurements.
    assert dimension.status == "fresh"
    assert dimension.score == 0.0


def test_suspicion_heat_feeds_the_aggregate() -> None:
    calm = SimingQualityMonitor().evaluate(
        state_tree=_state_tree(suspicion_heat={"char_a": 0.1}), narrative=_narrative()
    )
    hot = SimingQualityMonitor().evaluate(
        state_tree=_state_tree(suspicion_heat={"char_a": 0.95}), narrative=_narrative()
    )

    # Both snapshots now carry a computed aggregate rather than nothing.
    assert calm.snapshot.global_imbalance_score is not None
    assert hot.snapshot.global_imbalance_score is not None
    # The hot candidate raises the suspicion dimension into the computable set,
    # which is what makes it eligible for dominance at all.
    assert "suspicion_heat_distribution" in hot.snapshot.dimensions
    assert hot.snapshot.dimensions["suspicion_heat_distribution"].score == 0.9
    # Dominance still follows the fixed published order: participation outranks
    # suspicion, so an imbalanced participation dimension wins even when
    # suspicion is also hot.  That ordering is the contract, not an accident.
    assert hot.snapshot.dominant_imbalance_type in {
        "participation_starvation",
        "information_starvation",
        "suspicion_runaway",
    }
