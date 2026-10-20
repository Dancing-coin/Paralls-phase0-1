"""Data-only slow proposal contract; admission and goal writes remain owner work."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.character_agent.models.goal_runtime import CharacterActiveGoalFrame
from app.character_agent.models.mind_frame import CharacterMindFrame
from app.character_agent.cognition.capability_envelope import CapabilityEnvelope
from app.character_agent.cognition.cognition_policy import CognitionPolicy


GOAL_PROPOSAL_CONTRACT = "goal_proposal:v1"
GENERATIVE_PROVIDERS = {"deepseek", "qwen", "seed_doubao", "openai_compatible"}


class GoalProposalContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    trigger_kind: Literal[
        "repeated_failure", "phase_change", "context_conflict", "goal_conflict",
        "complex_information_failure", "high_risk_information_failure", "persistent_information_failure",
    ]
    trigger_source_ref: str = Field(min_length=1)
    frame: CharacterMindFrame
    current_goal_state: CharacterActiveGoalFrame | None
    goal_state_history: list[CharacterActiveGoalFrame]
    interpretation_summary: str
    evidence_refs: list[str]
    capability_envelope: CapabilityEnvelope
    cognition_policy: CognitionPolicy
    goal_revision: int = Field(ge=0, strict=True)
    expires_at: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def require_frozen_policy(cls, value: object) -> object:
        if isinstance(value, dict):
            for key, digest in (("capability_envelope", "envelope_digest"), ("cognition_policy", "policy_digest")):
                raw = value.get(key)
                if not isinstance(raw, dict) or not raw.get(digest):
                    raise ValueError("goal proposal requires frozen capability and cognition contracts")
        return value

    @model_validator(mode="after")
    def validate_frozen_context(self) -> GoalProposalContext:
        frame = self.frame
        if not frame.turn_id or not frame.frame_digest or frame.frame_digest != frame._content_digest():
            raise ValueError("goal proposal requires an intact frozen frame")
        self.cognition_policy.validate_envelope(
            self.capability_envelope, actor_id=self.actor_id, turn_id=frame.turn_id,
            turn_actor_id=frame.actor_id, policy_revision=frame.policy_revision,
            source_event_ref=self.trigger_source_ref,
        )
        if self.trigger_source_ref not in frame.source_refs:
            raise ValueError("goal proposal trigger is outside frozen frame")
        validate_evidence_refs(self.evidence_refs, set(frame.source_refs))
        if self.trigger_source_ref not in self.evidence_refs:
            raise ValueError("goal proposal trigger requires permitted evidence")
        if not self.request_id.strip():
            raise ValueError("goal proposal request identity must not be blank")
        return self


def validate_evidence_refs(refs: object, allowed: set[str]) -> list[str]:
    if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in allowed for ref in refs):
        raise ValueError("goal proposal evidence refs are outside frozen request")
    if len(refs) != len(set(refs)):
        raise ValueError("goal proposal evidence refs must be unique")
    return list(refs)


def validate_proposal_output(output: dict[str, object], allowed_refs: list[str]) -> dict[str, object]:
    if set(output) != {"active_goal_frame", "evidence_refs"}:
        raise ValueError("goal proposal output must contain only active_goal_frame and evidence_refs")
    frame = CharacterActiveGoalFrame.model_validate(output["active_goal_frame"], strict=True)
    if not frame.primary_goal.strip():
        raise ValueError("goal proposal primary goal must not be blank")
    allowed = set(allowed_refs)
    refs = validate_evidence_refs(output["evidence_refs"], allowed)
    goal_ids = [goal.goal_id for goal in frame.goal_portfolio]
    if len(goal_ids) != len(set(goal_ids)):
        raise ValueError("goal proposal portfolio identities must be unique")
    known = set(goal_ids)
    if frame.dominant_goal_id and frame.dominant_goal_id not in known:
        raise ValueError("goal proposal dominant goal is outside portfolio")
    validate_evidence_refs(frame.preserved_goal_ids, known)
    validate_evidence_refs(frame.suppressed_goal_ids, known)
    if set(frame.preserved_goal_ids) & set(frame.suppressed_goal_ids):
        raise ValueError("goal proposal cannot preserve and suppress the same goal")
    for goal in frame.goal_portfolio:
        if any(not value.strip() for value in (goal.goal_id, goal.goal, goal.source)):
            raise ValueError("goal proposal portfolio identity, goal and source must not be blank")
        validate_evidence_refs(goal.supporting_evidence, allowed)
    return {"active_goal_frame": frame.model_dump(mode="json"), "evidence_refs": refs}


def validate_proposal_request(request: dict[str, object]) -> GoalProposalContext | None:
    contract = request.get("output_contract")
    if contract is None:
        return None
    if contract != GOAL_PROPOSAL_CONTRACT or request.get("task_kind") != "l3_planning":
        raise ValueError("unsupported character output contract")
    route = request.get("route")
    if not isinstance(route, dict) or route.get("provider_kind") not in GENERATIVE_PROVIDERS:
        raise ValueError("goal proposal requires an explicit generative provider")
    return GoalProposalContext.model_validate(request.get("context"))
