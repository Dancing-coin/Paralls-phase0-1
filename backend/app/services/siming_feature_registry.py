from dataclasses import dataclass


@dataclass(frozen=True)
class FairnessDimensionRegistration:
    dimension_id: str
    required: bool = False


@dataclass(frozen=True)
class PolicyMappingRegistration:
    dimension_id: str
    reject_reason_tag: str
    rejection_reason: str


class SimingFeatureRegistry:
    CORE_DIMENSIONS = (
        "information_distribution",
        "participation_distribution",
        "conversation_access_fairness",
        "suspicion_heat_distribution",
        "evidence_visibility_distribution",
    )

    def __init__(self) -> None:
        self._dimensions: dict[str, FairnessDimensionRegistration] = {}
        self._policy_mappings: dict[str, PolicyMappingRegistration] = {}
        for dimension_id in self.CORE_DIMENSIONS:
            self._dimensions[dimension_id] = FairnessDimensionRegistration(
                dimension_id=dimension_id,
                required=True,
            )
            self._policy_mappings[dimension_id] = PolicyMappingRegistration(
                dimension_id=dimension_id,
                reject_reason_tag=f"{dimension_id}_sensitive",
                rejection_reason=f"{dimension_id}_policy_rejected",
            )

    def register_fairness_dimension(self, dimension_id: str, *, required: bool) -> None:
        self._dimensions[dimension_id] = FairnessDimensionRegistration(
            dimension_id=dimension_id,
            required=required,
        )

    def register_policy_mapping(
        self, dimension_id: str, reject_reason_tag: str, rejection_reason: str
    ) -> None:
        if dimension_id not in self._dimensions:
            raise ValueError(
                "fairness dimension must be registered before policy mapping"
            )
        self._policy_mappings[dimension_id] = PolicyMappingRegistration(
            dimension_id=dimension_id,
            reject_reason_tag=reject_reason_tag,
            rejection_reason=rejection_reason,
        )

    def fairness_dimensions(self) -> list[FairnessDimensionRegistration]:
        return list(self._dimensions.values())

    def policy_mapping_for(self, dimension_id: str) -> PolicyMappingRegistration | None:
        return self._policy_mappings.get(dimension_id)
