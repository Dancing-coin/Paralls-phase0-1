import pytest

from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    NarrativeObligation,
    NarrativeObligationLedgerSnapshot,
    ProjectionRunSnapshot,
    StateTreeNode,
    StateTreeSnapshot,
    StorylineStateSnapshot,
)
from app.services.siming_projection import StubGroupSimulationBridge, StubStorylineProjection


def make_state_tree() -> StateTreeSnapshot:
    return StateTreeSnapshot(
        snapshot_id="state_tree:room_demo:1",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        environment=StateTreeNode(
            node_id="environment:env_lamp",
            owner_system="L1/ESM",
            authority="mirror",
            status="fresh",
            summary={},
        ),
        character=StateTreeNode(
            node_id="character:char_b",
            owner_system="character_agent",
            authority="mirror",
            status="fresh",
            summary={},
        ),
        storyline=StateTreeNode(
            node_id="storyline:room_demo:main",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={},
        ),
        group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
    )


def make_fairness() -> FairnessStateSnapshot:
    return FairnessStateSnapshot(
        snapshot_id="fairness:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
        blocked_actor_ids=[],
        recent_intervention_ids=[],
    )


def make_storyline() -> StorylineStateSnapshot:
    return StorylineStateSnapshot(
        snapshot_id="storyline:1",
        schema_version=1,
        producer_system="siming.storyline",
        room_id="room_demo",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        active_phase="rising",
    )


def test_group_bridge_returns_read_only_unavailable_branch_by_default() -> None:
    branch = StubGroupSimulationBridge().summarize(room_id="room_demo")

    assert branch.status == "unavailable"
    assert branch.summary["mode"] == "shape_only"
    assert branch.summary["room_id"] == "room_demo"


def test_storyline_projection_returns_fresh_snapshot_with_basis_refs() -> None:
    projection = StubStorylineProjection().project(
        state_tree=make_state_tree(),
        fairness=make_fairness(),
        storyline=make_storyline(),
        ledger=NarrativeObligationLedgerSnapshot(
            ledger_id="obligation:1",
            schema_version=1,
            producer_system="siming.obligation",
            room_id="room_demo",
            world_ts=300,
            sim_tick_ts=301,
            causation_id="visual_fact:300",
            correlation_id="visual_fact:300",
            obligations=[],
        ),
    )

    assert projection.status == "fresh"
    assert projection.basis_state_tree_ref == "state_tree:room_demo:1"
    assert projection.basis_fairness_snapshot_ref == "fairness:1"
    assert projection.room_id == "room_demo"
    assert projection.producer_system == "siming.projection"
    assert projection.causation_id == "visual_fact:300"
    assert projection.correlation_id == "visual_fact:300"


def test_open_obligations_become_candidate_hints() -> None:
    projection = StubStorylineProjection().project(
        state_tree=make_state_tree(),
        fairness=make_fairness(),
        storyline=make_storyline(),
        ledger=NarrativeObligationLedgerSnapshot(
            ledger_id="obligation:1",
            schema_version=1,
            producer_system="siming.obligation",
            room_id="room_demo",
            world_ts=300,
            sim_tick_ts=301,
            causation_id="visual_fact:300",
            correlation_id="visual_fact:300",
            obligations=[
                NarrativeObligation(
                    obligation_id="obl:1",
                    source_ref="marker:1",
                    obligation_type="unresolved_reveal",
                    status="open",
                    reason="Reveal an established fact.",
                )
            ],
        ),
    )

    assert projection.candidate_hints == [
        {
            "obligation_id": "obl:1",
            "reason": "Reveal an established fact.",
            "suggested_band": "fact_reveal",
        }
    ]


def test_closed_obligations_do_not_become_candidate_hints() -> None:
    projection = StubStorylineProjection().project(
        state_tree=make_state_tree(),
        fairness=make_fairness(),
        storyline=make_storyline(),
        ledger=NarrativeObligationLedgerSnapshot(
            ledger_id="obligation:1",
            schema_version=1,
            producer_system="siming.obligation",
            room_id="room_demo",
            world_ts=300,
            sim_tick_ts=301,
            causation_id="visual_fact:300",
            correlation_id="visual_fact:300",
            obligations=[
                NarrativeObligation(
                    obligation_id="obl:closed",
                    source_ref="marker:1",
                    obligation_type="unresolved_reveal",
                    status="closed",
                    reason="Already resolved.",
                )
            ],
        ),
    )

    assert projection.candidate_hints == []


def test_candidate_hints_do_not_include_decision_ids() -> None:
    projection = StubStorylineProjection().project(
        state_tree=make_state_tree(),
        fairness=make_fairness(),
        storyline=make_storyline(),
        ledger=NarrativeObligationLedgerSnapshot(
            ledger_id="obligation:1",
            schema_version=1,
            producer_system="siming.obligation",
            room_id="room_demo",
            world_ts=300,
            sim_tick_ts=301,
            causation_id="visual_fact:300",
            correlation_id="visual_fact:300",
            obligations=[
                NarrativeObligation(
                    obligation_id="obl:1",
                    source_ref="marker:1",
                    obligation_type="unresolved_reveal",
                    status="open",
                    reason="Reveal an established fact.",
                )
            ],
        ),
    )

    assert "decision_id" not in projection.candidate_hints[0]


def test_projection_rejects_conflicting_status_aliases() -> None:
    with pytest.raises(
        ValueError,
        match="status and branch_status must match",
    ):
        ProjectionRunSnapshot(
            projection_id="projection:room_demo:301",
            schema_version=1,
            producer_system="siming.projection",
            room_id="room_demo",
            world_ts=300,
            sim_tick_ts=301,
            causation_id="visual_fact:300",
            correlation_id="visual_fact:300",
            status="fresh",
            branch_status="stale",
        )
