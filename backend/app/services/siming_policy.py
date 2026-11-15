from dataclasses import dataclass

from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.services.siming_feature_registry import SimingFeatureRegistry


@dataclass(frozen=True)
class EntityEligibilityRegistry:
    actors: tuple[str, ...] = ()
    environments: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()

    def is_eligible(self, entity_kind: str, entity_id: str) -> bool:
        values = {
            "actor": self.actors,
            "environment": self.environments,
            "object": self.objects,
        }.get(entity_kind)
        return values is not None and entity_id in values


@dataclass(frozen=True)
class SimingPolicyResult:
    accepted: bool
    reasons: list[str]


class SimingInterventionPolicy:
    UNSAFE_REASON_TAGS = {
        "locked_truth_rewrite",
        "skip_role_autonomy",
        "skip_esm",
        "phase2_projection_required",
    }

    def __init__(self, feature_registry: SimingFeatureRegistry | None = None,
                 entity_registry: EntityEligibilityRegistry | None = None) -> None:
        self._feature_registry = feature_registry or SimingFeatureRegistry()
        self._entity_registry = entity_registry

    def evaluate(
        self, candidate: InterventionCandidate, *, snapshot: FairnessStateSnapshot
    ) -> SimingPolicyResult:
        # S6: every supplied target must independently pass eligibility.
        reasons: list[str] = []

        unknown_facts = [
            fact_id
            for fact_id in candidate.established_fact_ids
            if fact_id not in snapshot.known_fact_ids
        ]
        if unknown_facts:
            reasons.append("unknown_fact_reference")

        actors = set(snapshot.eligible_actor_ids)
        if self._entity_registry is not None:
            actors.update(self._entity_registry.actors)
        if candidate.target_actor_id:
            if candidate.target_actor_id in snapshot.blocked_actor_ids:
                reasons.append("actor_not_eligible")
            elif candidate.target_actor_id not in actors:
                reasons.append("actor_not_eligible")

        environments = set(snapshot.eligible_environment_ids)
        objects = set(snapshot.eligible_object_ids)
        if self._entity_registry is not None:
            environments.update(self._entity_registry.environments)
            objects.update(self._entity_registry.objects)
        if (candidate.target_environment_id
                and candidate.target_environment_id not in environments):
            reasons.append("environment_not_eligible")
        if (candidate.target_object_id
                and candidate.target_object_id not in objects):
            reasons.append("object_not_eligible")

        for tag in candidate.reason_tags:
            if tag in self.UNSAFE_REASON_TAGS:
                reasons.append(tag)

        if (
            candidate.proposed_band == "environment_request"
            and "esm_validated_request" not in candidate.reason_tags
        ):
            reasons.append("environment_request_requires_esm_path")

        for dimension_id, dimension in snapshot.dimensions.items():
            if not dimension.mapped_to_policy:
                continue
            mapping = self._feature_registry.policy_mapping_for(dimension_id)
            if (
                mapping is not None
                and mapping.reject_reason_tag in candidate.reason_tags
            ):
                reasons.append(mapping.rejection_reason)

        if reasons:
            return SimingPolicyResult(accepted=False, reasons=reasons)
        return SimingPolicyResult(accepted=True, reasons=["established_fact_visible"])
