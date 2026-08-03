"""Bridges existing skill-path evaluation into the gameplay resource/body gate."""

from __future__ import annotations

from app.character_agent.skills.models import SkillEvaluationResult
from app.gameplay.resource_body_runtime import (
    BodyRuntimeProjection,
    GameplayActionSettlementCommand,
    GameplayActionSettlementResult,
    ResourceBodyActionSettlementService,
    ResourceStateProjection,
)


class SkillActionGateError(ValueError):
    """Raised when independently owned skill and gameplay inputs disagree."""


class SkillPathGameplayGate:
    """Uses an existing evaluated skill path as a read gate; it never owns skill state."""

    def __init__(self, *, resource_body_settlement: ResourceBodyActionSettlementService) -> None:
        self._resource_body_settlement = resource_body_settlement

    def settle(
        self,
        command: GameplayActionSettlementCommand,
        *,
        skill_evaluation: SkillEvaluationResult,
        resources: ResourceStateProjection,
        body: BodyRuntimeProjection,
        enabled_group_ids: tuple[str, ...],
    ) -> GameplayActionSettlementResult:
        if skill_evaluation.actor_id != command.actor_ref:
            raise SkillActionGateError("skill_actor_mismatch")
        if skill_evaluation.action_id != command.requirement.action_ref:
            raise SkillActionGateError("skill_action_mismatch")
        selected_path = skill_evaluation.selected_path
        if not selected_path or str(selected_path.get("eligibility_status", "")) != "eligible":
            return GameplayActionSettlementResult(False, "skill_path_not_eligible", ())
        return self._resource_body_settlement.settle(
            command,
            resources=resources,
            body=body,
            enabled_group_ids=enabled_group_ids,
        )


__all__ = ["SkillActionGateError", "SkillPathGameplayGate"]
