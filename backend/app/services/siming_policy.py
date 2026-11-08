from dataclasses import dataclass

from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.services.siming_feature_registry import SimingFeatureRegistry


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

    def __init__(self, feature_registry: SimingFeatureRegistry | None = None) -> None:
        self._feature_registry = feature_registry or SimingFeatureRegistry()

    def evaluate(
        self, candidate: InterventionCandidate, *, snapshot: FairnessStateSnapshot
    ) -> SimingPolicyResult:
        # TODO: S6 (05-待决问题与缺陷登记.md - 司命断点)
        #   Qualification judgment only checks actor_id. Should check full FactType eligibility in Phase 2.
        reasons: list[str] = []

        unknown_facts = [
            fact_id
            for fact_id in candidate.established_fact_ids
            if fact_id not in snapshot.known_fact_ids
        ]
        if unknown_facts:
            reasons.append("unknown_fact_reference")

        if candidate.target_actor_id:
            # NOTE: S6 断点（05-待决问题与缺陷登记.md 第四章断点清单）
            # 当前实现：资格判定只检查 target_actor_id（过渡期方案）
            #
            # 短期方案（Q2-A）：
            #   - 保持 actor-only 判定
            #   - environment_id/object_id 不走资格检查（由 ESM/Owner 自己验证）
            #
            # 长期目标（Q2-C，Phase 2+）：
            #   - 扩展到非角色实体（environment_id, object_id）
            #   - 统一 entity eligibility registry
            #   - 资格判定由 Owner domain 提供，不在司命硬编码
            #
            # See: docs/reference/phase1-siming/Q1-Q2-decisions.md
            # TODO: S6 长期 - 改为统一 entity eligibility registry（Phase 2）
            if candidate.target_actor_id in snapshot.blocked_actor_ids:
                reasons.append("actor_not_eligible")
            elif candidate.target_actor_id not in snapshot.eligible_actor_ids:
                reasons.append("actor_not_eligible")

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
