from app.models.siming_narrative import (
    InterventionSeed,
    NarrativeCoreResult,
    NarrativeObligationLedger,
    NarrativeStateSnapshot,
    QualitySignal,
)
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    StateTreeNode,
    StateTreeSnapshot,
)
from app.services.siming_feature_registry import SimingFeatureRegistry
from app.services.siming_quality_monitor import SimingQualityMonitor


def make_state_tree() -> StateTreeSnapshot:
    return StateTreeSnapshot(
        snapshot_id="state_tree:room_demo:301",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="corr_demo",
        environment=StateTreeNode(
            node_id="env_lamp",
            owner_system="esm",
            authority="mirror",
            status="fresh",
            summary={"established_fact_id": "visual_fact:300:light", "visible_actor_ids": ["char_c"]},
        ),
        character=StateTreeNode(
            node_id="char_b",
            owner_system="character_agent",
            authority="mirror",
            status="fresh",
            summary={"target_actor_id": "char_b", "recent_participation_count": 0},
        ),
        storyline=StateTreeNode(
            node_id="storyline:room_demo",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={"conversation_candidate_actor_ids": ["char_c"]},
        ),
        group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
    )


def make_narrative() -> NarrativeCoreResult:
    state = NarrativeStateSnapshot(
        snapshot_id="narrative:room_demo:301",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        active_phase="rising",
        pressure_level="normal",
        causation_id="visual_fact:300",
        correlation_id="corr_demo",
    )
    return NarrativeCoreResult(
        state=state,
        ledger=NarrativeObligationLedger(
            ledger_id="ledger:narrative:room_demo:301",
            room_id="room_demo",
            world_ts=300,
            sim_tick_ts=301,
            causation_id="visual_fact:300",
            correlation_id="corr_demo",
        ),
        seeds=[
            InterventionSeed(
                seed_id="seed:1",
                seed_type="unresolved_reveal",
                basis_snapshot_ref=state.snapshot_id,
                target_refs=["char_b", "env_lamp"],
                suggested_band="fact_reveal",
                explanation="surface established fact",
            )
        ],
    )


def test_quality_monitor_runs_all_required_dimensions_without_placeholder_scores() -> None:
    result = SimingQualityMonitor().evaluate(state_tree=make_state_tree(), narrative=make_narrative())

    assert set(result.snapshot.dimensions) == {
        "information_distribution",
        "participation_distribution",
        "conversation_access_fairness",
        "suspicion_heat_distribution",
        "evidence_visibility_distribution",
    }
    assert result.snapshot.dimensions["information_distribution"].score > 0.5
    assert result.snapshot.dimensions["information_distribution"].status == "stale"
    assert result.snapshot.dimensions["participation_distribution"].score > 0.5
    assert result.snapshot.dimensions["participation_distribution"].status == "partial"
    assert result.snapshot.dimensions["suspicion_heat_distribution"].status in {"partial", "unavailable"}
    assert not any(signal.dimension == "suspicion_heat_distribution" for signal in result.signals)
    assert any(signal.dimension == "evidence_visibility_distribution" for signal in result.signals)


def test_quality_monitor_marks_failed_auditor_partial_without_interrupting_tick() -> None:
    monitor = SimingQualityMonitor(force_failed_dimensions={"conversation_access_fairness"})

    result = monitor.evaluate(state_tree=make_state_tree(), narrative=make_narrative())

    assert result.snapshot.dimensions["conversation_access_fairness"].status == "unavailable"
    assert result.snapshot.dimensions["conversation_access_fairness"].score == 0.0
    assert not any(signal.dimension == "conversation_access_fairness" for signal in result.signals)
    assert "quality_monitor_partial" in result.risk_tags


def test_quality_monitor_includes_registered_dimensions_for_policy_mappings() -> None:
    registry = SimingFeatureRegistry()
    registry.register_fairness_dimension("resource_pressure", required=False)
    registry.register_policy_mapping(
        dimension_id="resource_pressure",
        reject_reason_tag="resource_pressure_sensitive",
        rejection_reason="resource_pressure_policy_rejected",
    )

    result = SimingQualityMonitor(
        feature_registry=registry
    ).evaluate(state_tree=make_state_tree(), narrative=make_narrative())

    dimension = result.snapshot.dimensions["resource_pressure"]
    assert dimension.status == "fresh"
    assert dimension.score == 0.0
    assert dimension.reason == "registered fairness dimension available"
    assert dimension.mapped_to_policy is True
