from app.models.siming_event import FairnessStateSnapshot, SimingAuditRecord
from app.models.siming_runtime_state import (
    CheckpointType,
    NarrativeReadModel,
    ProjectionRunSnapshot,
    SimingCheckpoint,
    StateTreeSnapshot,
    StorylineStateSnapshot,
)
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle


def perception_identity_from_bundle(bundle: CanonicalPerceptBundle) -> dict[str, object]:
    return {
        "bundle_id": bundle.bundle_id,
        "query_id": bundle.query_id,
        "capture_root_id": bundle.capture_root_id,
        "capture_id": bundle.capture_id,
        "clock_domain": bundle.clock_domain,
        "monotonic_tick": bundle.monotonic_tick,
        "source_frame_index": bundle.source_frame_index,
        "world_anchor_id": bundle.world_anchor_id,
        "subject_ref": bundle.subject_ref,
        "target_ref": bundle.target_ref or str(bundle.target_state.get("target_ref", "") or ""),
        "source_ref_lineage": list(bundle.source_ref_lineage),
        "wall_clock_ts": bundle.wall_clock_ts,
    }


class SimingReadModelBuilder:
    def build_bundle_read_model(
        self,
        bundle: CanonicalPerceptBundle,
        *,
        producer_ts: int,
    ) -> NarrativeReadModel:
        room_id = str(bundle.local_spatial_state.get("room_id", "") or "room_demo")
        scene_id = str(bundle.local_spatial_state.get("scene_id", "") or "scene_demo")
        zone_id = str(bundle.local_spatial_state.get("zone_id", "") or "zone_focus")
        perception_identity = perception_identity_from_bundle(bundle)
        return NarrativeReadModel(
            read_model_id=f"read:{bundle.bundle_id}",
            schema_version=1,
            producer_system="siming.read_model",
            room_id=room_id,
            scene_scope=f"{scene_id}/{zone_id}",
            world_ts=producer_ts,
            sim_tick_ts=producer_ts,
            current_state={
                "source_bundle_id": bundle.bundle_id,
                "imbalance_type": "l1_world_fact_visibility",
                "intervention_urgency": "normal",
                "perception_identity": perception_identity,
                "capture_root_id": bundle.capture_root_id,
                "clock_domain": bundle.clock_domain,
                "monotonic_tick": bundle.monotonic_tick,
                "world_anchor_id": bundle.world_anchor_id,
            },
            focus_entities=list(bundle.structured_fact_refs),
            intervention_surface={
                "target_state": dict(bundle.target_state),
                "perception_identity": perception_identity,
            },
            narrative_surface={
                "environment_state": dict(bundle.environment_state),
                "source_ref_lineage": list(bundle.source_ref_lineage),
            },
            derived_from_snapshot_ref=bundle.bundle_id,
        )

    def build_checkpoint(
        self,
        *,
        state_tree: StateTreeSnapshot,
        fairness: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
        checkpoint_type: CheckpointType = "fairness_after",
    ) -> SimingCheckpoint:
        return SimingCheckpoint(
            checkpoint_id=(
                f"checkpoint:{checkpoint_type}:{state_tree.room_id}:{state_tree.sim_tick_ts}:{fairness.snapshot_id}"
            ),
            schema_version=1,
            room_id=state_tree.room_id,
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            checkpoint_type=checkpoint_type,
            fairness_snapshot_ref=fairness.snapshot_id,
            state_tree_snapshot_ref=state_tree.snapshot_id,
            storyline_snapshot_ref=storyline.snapshot_id,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
        )

    def build_read_model(
        self,
        *,
        state_tree: StateTreeSnapshot,
        fairness: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
        projection: ProjectionRunSnapshot,
        audit_records: list[SimingAuditRecord],
        narrative_summary: dict[str, object] | None = None,
        quality_summary: dict[str, object] | None = None,
        guardrail_summary: dict[str, object] | None = None,
        checkpoint_summary: dict[str, object] | None = None,
    ) -> NarrativeReadModel:
        narrative_surface = {
            "projection_status": projection.status,
            "candidate_hint_count": len(projection.candidate_hints),
        }
        if narrative_summary:
            narrative_surface.update(narrative_summary)

        intervention_surface = {
            "audit_statuses": [audit.status for audit in audit_records],
        }
        if quality_summary:
            intervention_surface.update(quality_summary)
        if guardrail_summary:
            intervention_surface.update(guardrail_summary)

        current_state = {
            "imbalance_type": "information_visibility",
            "intervention_urgency": "normal",
            "active_phase_marker": storyline.active_phase,
        }
        if checkpoint_summary:
            current_state["checkpoint"] = dict(checkpoint_summary)

        return NarrativeReadModel(
            read_model_id=f"read:{state_tree.room_id}:{state_tree.sim_tick_ts}",
            schema_version=1,
            producer_system="siming.read_model",
            room_id=state_tree.room_id,
            scene_scope=f"{state_tree.scene_id}/{state_tree.zone_id}",
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            current_state=current_state,
            focus_entities=[state_tree.environment.node_id, state_tree.character.node_id],
            intervention_surface=intervention_surface,
            narrative_surface=narrative_surface,
            derived_from_snapshot_ref=fairness.snapshot_id,
        )
