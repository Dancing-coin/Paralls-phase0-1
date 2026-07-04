from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.player_input import InteractIntent
from app.models.world_result import ConstraintStateResult
from app.services.esm_service import ESMService
from app.services.physical_interaction_channel import (
    PhysicalContactObservation,
    PhysicalEffectKind,
    PhysicalInteractionChannel,
    PhysicalInteractionRequest,
    PhysicalInteractionResult,
)
from app.world_runtime.intelligence_upgrade import InteractionIntentFrame


PolicyKind = Literal[
    "semantic-only",
    "physical-only",
    "semantic-goal-physical-effect-mixed",
    "denied-by-constraint",
    "requires-active-perception",
    "requires-authority-confirmation",
]
ChannelKind = Literal["semantic", "physical"]


class StructuredInteractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: InteractionIntentFrame
    player_id: str = "system"
    room_id: str = "room_demo"
    scene_id: str = "scene_demo"
    zone_id: str = "zone_focus"
    producer_ts: int = 0
    target_object_id: str = ""
    actor_position: tuple[float, float, float] | None = None
    perception_ready: bool = True
    authority_confirmed: bool = True
    authority_ref: str = ""
    constraint_refs: list[str] = Field(default_factory=list)
    physical_effect_kind: PhysicalEffectKind | None = None
    physical_observation: PhysicalContactObservation | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_raw_input_noise(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        forbidden = {"raw_keyboard", "raw_mouse", "raw_camera", "raw_input", "camera_noise", "mouse_delta"}
        present = sorted(forbidden.intersection(value.keys()))
        if present:
            raise ValueError(f"raw input is not accepted by interaction orchestration: {', '.join(present)}")
        return value

    @model_validator(mode="after")
    def validate_target_ref(self) -> "StructuredInteractionRequest":
        target_refs = self.intent.target_refs.get("object_ids", [])
        resolved = self.target_object_id or (target_refs[0] if target_refs else "")
        if not resolved and self.intent.physical_affordance:
            raise ValueError("physical interaction intents require a target_object_id or object_ids target ref")
        self.target_object_id = resolved
        return self


class ChannelRequestEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: ChannelKind
    request_id: str
    payload: dict[str, Any]


class ChannelResultEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: ChannelKind
    result_id: str
    status: str
    payload: dict[str, Any]


class InteractionOrchestrationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    intent_id: str
    policy: PolicyKind
    selected_channels: list[ChannelKind] = Field(default_factory=list)
    channel_requests: list[ChannelRequestEnvelope] = Field(default_factory=list)
    degrade_reason: str = ""
    active_perception_request_ref: str = ""
    authority_confirmation_request_ref: str = ""
    forbidden_ownership: list[str] = Field(
        default_factory=lambda: ["character_mind_core", "siming_main_brain", "esm_authority"]
    )


class InteractionOrchestrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    plan: InteractionOrchestrationPlan
    channel_results: list[ChannelResultEnvelope] = Field(default_factory=list)
    unified_result_family: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal["completed", "denied", "degraded"] = "completed"
    trace_refs: list[str] = Field(default_factory=list)


class InteractionOrchestrationService:
    def __init__(
        self,
        *,
        esm_service: ESMService | None = None,
        physical_channel: PhysicalInteractionChannel | None = None,
    ) -> None:
        self._esm = esm_service or ESMService()
        self._physical = physical_channel or PhysicalInteractionChannel()
        self.trace: list[dict[str, object]] = []

    def plan(self, request: StructuredInteractionRequest) -> InteractionOrchestrationPlan:
        plan_id = f"interaction_plan:{request.intent.intent_id}"
        physical_kind = request.physical_effect_kind or self._physical_kind_for(request.intent.physical_affordance)
        if request.constraint_refs:
            return InteractionOrchestrationPlan(
                plan_id=plan_id,
                intent_id=request.intent.intent_id,
                policy="denied-by-constraint",
                degrade_reason="constraint refs block interaction before channel execution",
            )
        if not request.perception_ready:
            return InteractionOrchestrationPlan(
                plan_id=plan_id,
                intent_id=request.intent.intent_id,
                policy="requires-active-perception",
                degrade_reason="perception refs are insufficient for interaction",
                active_perception_request_ref=f"active_perception:{request.intent.actor_id}:{request.target_object_id or 'target'}",
            )
        if not request.authority_confirmed:
            return InteractionOrchestrationPlan(
                plan_id=plan_id,
                intent_id=request.intent.intent_id,
                policy="requires-authority-confirmation",
                degrade_reason="semantic authority confirmation is required",
                authority_confirmation_request_ref=f"authority_confirmation:{request.intent.intent_id}",
            )
        if physical_kind is None:
            return InteractionOrchestrationPlan(
                plan_id=plan_id,
                intent_id=request.intent.intent_id,
                policy="semantic-only",
                selected_channels=["semantic"],
                channel_requests=[
                    ChannelRequestEnvelope(
                        channel="semantic",
                        request_id=f"semantic:{request.intent.intent_id}",
                        payload=request.intent.model_dump(),
                    )
                ],
            )
        if request.intent.semantic_intent in {"physical_only", "contact_only", "blocking_only"}:
            return InteractionOrchestrationPlan(
                plan_id=plan_id,
                intent_id=request.intent.intent_id,
                policy="physical-only",
                selected_channels=["physical"],
                channel_requests=[
                    ChannelRequestEnvelope(
                        channel="physical",
                        request_id=f"physical:{request.intent.intent_id}",
                        payload={"effect_kind": physical_kind, "target_object_id": request.target_object_id},
                    )
                ],
            )
        return InteractionOrchestrationPlan(
            plan_id=plan_id,
            intent_id=request.intent.intent_id,
            policy="semantic-goal-physical-effect-mixed",
            selected_channels=["semantic", "physical"],
            channel_requests=[
                ChannelRequestEnvelope(
                    channel="semantic",
                    request_id=f"semantic:{request.intent.intent_id}",
                    payload=request.intent.model_dump(),
                ),
                ChannelRequestEnvelope(
                    channel="physical",
                    request_id=f"physical:{request.intent.intent_id}",
                    payload={"effect_kind": physical_kind, "target_object_id": request.target_object_id},
                ),
            ],
        )

    def execute(self, request: StructuredInteractionRequest) -> InteractionOrchestrationResult:
        plan = self.plan(request)
        if plan.policy in {"requires-active-perception", "requires-authority-confirmation"}:
            result = InteractionOrchestrationResult(
                result_id=f"interaction_result:{request.intent.intent_id}",
                plan=plan,
                status="degraded",
                trace_refs=[plan.active_perception_request_ref or plan.authority_confirmation_request_ref],
            )
            self._trace(result)
            return result
        if plan.policy == "denied-by-constraint":
            constraint = self._constraint_result(request, "denied_by_constraint", plan.degrade_reason)
            result = InteractionOrchestrationResult(
                result_id=f"interaction_result:{request.intent.intent_id}",
                plan=plan,
                status="denied",
                unified_result_family=[constraint.model_dump()],
                channel_results=[
                    ChannelResultEnvelope(
                        channel="semantic",
                        result_id=constraint.result_id,
                        status="rejected",
                        payload=constraint.model_dump(),
                    )
                ],
            )
            self._trace(result)
            return result

        channel_results: list[ChannelResultEnvelope] = []
        unified_results: list[dict[str, Any]] = []
        semantic_approved = request.authority_confirmed
        semantic_result_ref = request.authority_ref or f"authority:{request.intent.intent_id}"
        if "semantic" in plan.selected_channels:
            semantic_result = self._execute_semantic(request)
            semantic_approved = getattr(semantic_result, "settlement_status", "") in {"accepted", "applied"} or getattr(
                semantic_result, "resolution_status", ""
            ) == "accepted"
            semantic_result_ref = semantic_result.result_id
            payload = semantic_result.model_dump()
            unified_results.append(payload)
            channel_results.append(
                ChannelResultEnvelope(
                    channel="semantic",
                    result_id=semantic_result.result_id,
                    status=getattr(semantic_result, "settlement_status", "") or getattr(semantic_result, "resolution_status", ""),
                    payload=payload,
                )
            )
        if "physical" in plan.selected_channels:
            physical_result = self._execute_physical(request, semantic_approved=semantic_approved, authority_ref=semantic_result_ref)
            unified_results.extend(physical_result.unified_results)
            channel_results.append(
                ChannelResultEnvelope(
                    channel="physical",
                    result_id=physical_result.result_id,
                    status="applied" if physical_result.effect_applied else "rejected",
                    payload=physical_result.model_dump(),
                )
            )
        result = InteractionOrchestrationResult(
            result_id=f"interaction_result:{request.intent.intent_id}",
            plan=plan,
            channel_results=channel_results,
            unified_result_family=unified_results,
            status="completed" if all(result.status != "rejected" for result in channel_results) else "denied",
            trace_refs=[f"interaction_trace:{request.intent.intent_id}"],
        )
        self._trace(result)
        return result

    def _execute_semantic(self, request: StructuredInteractionRequest):
        event = InteractIntent(
            player_id=request.player_id,
            room_id=request.room_id,
            scene_id=request.scene_id,
            zone_id=request.zone_id,
            actor_id=request.intent.actor_id,
            intent_type="interact_intent",
            producer_ts=request.producer_ts,
            target_object_id=request.target_object_id or "target_unknown",
            interaction_type=request.intent.semantic_intent or "inspect",
        )
        return self._esm.resolve_interaction(event, actor_position=request.actor_position)

    def _execute_physical(
        self,
        request: StructuredInteractionRequest,
        *,
        semantic_approved: bool,
        authority_ref: str,
    ) -> PhysicalInteractionResult:
        effect_kind = request.physical_effect_kind or self._physical_kind_for(request.intent.physical_affordance) or "contact"
        return self._physical.apply(
            PhysicalInteractionRequest(
                request_id=f"physical:{request.intent.intent_id}",
                actor_id=request.intent.actor_id,
                room_id=request.room_id,
                scene_id=request.scene_id,
                zone_id=request.zone_id,
                target_object_id=request.target_object_id,
                effect_kind=effect_kind,
                semantic_approved=semantic_approved,
                authority_ref=authority_ref,
                contact_observation=request.physical_observation,
                constraint_refs=list(request.constraint_refs),
                producer_ts=request.producer_ts,
            )
        )

    def _constraint_result(self, request: StructuredInteractionRequest, code: str, summary: str) -> ConstraintStateResult:
        return ConstraintStateResult(
            request_ref=f"interaction:{request.intent.intent_id}",
            result_id=f"constraint:interaction:{request.intent.intent_id}",
            room_id=request.room_id,
            scene_id=request.scene_id,
            zone_id=request.zone_id,
            actor_id=request.intent.actor_id,
            source_type="interaction_orchestration_service",
            entity_id=request.target_object_id,
            target_object_id=request.target_object_id or None,
            result_type="constraint_state_result",
            causation_id=request.intent.intent_id,
            correlation_id=request.intent.intent_id,
            producer_ts=request.producer_ts + 1,
            constraint_type="interaction_orchestration_policy",
            constraint_code=code,
            constraint_summary=summary,
            blocking_entity_refs=list(request.constraint_refs),
            settlement_status="rejected",
        )

    def _physical_kind_for(self, affordance: str) -> PhysicalEffectKind | None:
        if affordance in {"contact", "push", "pull", "carry", "grab", "blocking"}:
            return affordance  # type: ignore[return-value]
        if affordance == "continuous_contact":
            return "contact"
        return None

    def _trace(self, result: InteractionOrchestrationResult) -> None:
        self.trace.append(
            {
                "result_id": result.result_id,
                "policy": result.plan.policy,
                "selected_channels": list(result.plan.selected_channels),
                "status": result.status,
                "unified_result_count": len(result.unified_result_family),
            }
        )
