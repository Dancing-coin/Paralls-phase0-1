from __future__ import annotations

from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_runtime_state import (
    FairnessDimensionSnapshot,
    ProjectionRunSnapshot,
    StateTreeNode,
    StateTreeSnapshot,
    StorylineStateSnapshot,
)
from app.services.siming_fairness_aggregate import compute_fairness_aggregate
from app.services.siming_read_model import SimingReadModelBuilder


def _state_tree() -> StateTreeSnapshot:
    def node(node_id: str, owner: str) -> StateTreeNode:
        return StateTreeNode(
            node_id=node_id, owner_system=owner, authority="mirror", status="fresh", summary={}
        )

    from app.models.siming_runtime_state import GroupSimulationBranchSnapshot

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
        environment=node("env", "esm"),
        character=node("char_b", "character_agent"),
        storyline=node("storyline", "siming"),
        group_simulation=GroupSimulationBranchSnapshot(status="fresh", summary={}),
    )


def _fairness(policy_imbalanced: bool) -> FairnessStateSnapshot:
    dimensions = {
        dimension_id: FairnessDimensionSnapshot(
            dimension_id=dimension_id,
            status="fresh",
            score=1.0 if (policy_imbalanced and dimension_id == "participation_distribution") else 0.0,
            reason="test",
            mapped_to_policy=True,
        )
        for dimension_id in (
            "information_distribution",
            "participation_distribution",
            "conversation_access_fairness",
            "suspicion_heat_distribution",
            "evidence_visibility_distribution",
        )
    }
    aggregate = compute_fairness_aggregate(dimensions)
    return FairnessStateSnapshot(
        snapshot_id="fairness:1",
        room_id="room:1",
        scene_id="scene:1",
        zone_id="zone:1",
        causation_id="cause:1",
        correlation_id="corr:1",
        dimensions=dimensions,
        global_imbalance_score=aggregate.score,
        dominant_imbalance_type=aggregate.dominant,
        imbalance_reasons=list(aggregate.reasons),
    )


def _storyline() -> StorylineStateSnapshot:
    return StorylineStateSnapshot(
        snapshot_id="storyline:1",
        schema_version=1,
        producer_system="siming.storyline",
        room_id="room:1",
        world_ts=100,
        sim_tick_ts=100,
        causation_id="cause:1",
        correlation_id="corr:1",
        active_phase="setup",
    )


def _projection() -> ProjectionRunSnapshot:
    return ProjectionRunSnapshot(
        projection_id="projection:1",
        schema_version=1,
        producer_system="siming.projection",
        room_id="room:1",
        world_ts=100,
        sim_tick_ts=100,
        causation_id="cause:1",
        correlation_id="corr:1",
        status="fresh",
    )


def _build(fairness: FairnessStateSnapshot):
    return SimingReadModelBuilder().build_read_model(
        state_tree=_state_tree(),
        fairness=fairness,
        storyline=_storyline(),
        projection=_projection(),
        audit_records=[],
    )


def test_read_model_reports_the_computed_dominant_imbalance() -> None:
    model = _build(_fairness(policy_imbalanced=True))

    assert model.current_state["imbalance_type"] == "participation_starvation"


def test_read_model_reports_balanced_when_nothing_is_imbalanced() -> None:
    model = _build(_fairness(policy_imbalanced=False))

    assert model.current_state["imbalance_type"] == "balanced"


def test_read_model_exposes_the_global_imbalance_score() -> None:
    model = _build(_fairness(policy_imbalanced=True))

    assert model.current_state["global_imbalance_score"] == 0.28


def test_read_model_omits_the_score_when_not_computed() -> None:
    legacy = FairnessStateSnapshot(
        snapshot_id="fairness:legacy",
        room_id="room:1",
        scene_id="scene:1",
        zone_id="zone:1",
        causation_id="cause:1",
        correlation_id="corr:1",
    )

    model = _build(legacy)

    # Not computed must not be presented as a balanced measurement.
    assert "global_imbalance_score" not in model.current_state
    assert model.current_state["imbalance_type"] == "information_visibility"
