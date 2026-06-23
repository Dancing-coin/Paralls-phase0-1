from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_runtime_state import FairnessDimensionSnapshot, StateTreeSnapshot
from app.services.siming_feature_registry import SimingFeatureRegistry


class SimingFairnessAuditEngine:
    DEFAULT_DIMENSIONS = (
        "information_distribution",
        "participation_distribution",
        "conversation_access_fairness",
        "suspicion_heat_distribution",
        "evidence_visibility_distribution",
    )

    def __init__(self, feature_registry: SimingFeatureRegistry | None = None) -> None:
        self._feature_registry = feature_registry or SimingFeatureRegistry()

    def build_snapshot(self, state_tree: StateTreeSnapshot) -> FairnessStateSnapshot:
        established_fact_id = state_tree.environment.summary.get("established_fact_id")
        target_actor_id = state_tree.character.summary.get("target_actor_id")

        known_fact_ids = [established_fact_id] if established_fact_id else []
        eligible_actor_ids = [target_actor_id] if target_actor_id else []

        dimensions = {
            dimension_id: FairnessDimensionSnapshot(
                dimension_id=dimension_id,
                status="fresh",
                score=0.5,
                reason="default fairness dimension active",
                mapped_to_policy=True,
            )
            for dimension_id in self.DEFAULT_DIMENSIONS
        }

        for registration in self._feature_registry.fairness_dimensions():
            dimensions[registration.dimension_id] = FairnessDimensionSnapshot(
                dimension_id=registration.dimension_id,
                status="fresh",
                score=0.5,
                reason="registered fairness dimension available",
                mapped_to_policy=(
                    self._feature_registry.policy_mapping_for(registration.dimension_id)
                    is not None
                ),
            )

        return FairnessStateSnapshot(
            snapshot_id=f"fairness:{state_tree.snapshot_id}",
            room_id=state_tree.room_id,
            scene_id=state_tree.scene_id,
            zone_id=state_tree.zone_id,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
            known_fact_ids=known_fact_ids,
            eligible_actor_ids=eligible_actor_ids,
            blocked_actor_ids=[],
            recent_intervention_ids=[],
            dimensions=dimensions,
        )
