from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.world_result import BodyStateResult, ConstraintStateResult, EnvironmentStateResult, ObjectStateResult


PhysicalEffectKind = Literal["contact", "push", "pull", "carry", "grab", "blocking"]


class PhysicalContactObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_ref: str
    body_ref: str
    object_ref: str
    environment_ref: str = ""
    normal_summary: str = ""
    sampled_by: Literal["godot_physical_interaction_probe", "backend_contract_probe"] = "backend_contract_probe"


class PhysicalInteractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    actor_id: str
    room_id: str
    scene_id: str = "scene_demo"
    zone_id: str = "zone_focus"
    target_object_id: str
    effect_kind: PhysicalEffectKind
    semantic_approved: bool
    authority_ref: str = ""
    contact_observation: PhysicalContactObservation | None = None
    constraint_refs: list[str] = Field(default_factory=list)
    producer_ts: int = 0


class PhysicalInteractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    request_id: str
    actor_id: str
    target_object_id: str
    effect_kind: PhysicalEffectKind
    effect_applied: bool
    structured_physical_effect_refs: list[str] = Field(default_factory=list)
    object_state_observation_refs: list[str] = Field(default_factory=list)
    environment_state_observation_refs: list[str] = Field(default_factory=list)
    body_state_observation_refs: list[str] = Field(default_factory=list)
    unified_results: list[dict[str, object]] = Field(default_factory=list)
    constraint_result: dict[str, object] | None = None


class PhysicalInteractionChannel:
    def apply(self, request: PhysicalInteractionRequest) -> PhysicalInteractionResult:
        if not request.semantic_approved or request.constraint_refs:
            constraint = ConstraintStateResult(
                request_ref=request.request_id,
                result_id=f"constraint:{request.request_id}",
                room_id=request.room_id,
                scene_id=request.scene_id,
                zone_id=request.zone_id,
                actor_id=request.actor_id,
                source_type="esm_physical_channel",
                entity_id=request.target_object_id,
                target_object_id=request.target_object_id,
                result_type="constraint_state_result",
                causation_id=request.authority_ref or request.request_id,
                correlation_id=request.request_id,
                producer_ts=request.producer_ts + 1,
                constraint_type="physical_channel_constraint",
                constraint_code="semantic_authority_required" if not request.semantic_approved else "blocked_by_constraint",
                constraint_summary="physical effect blocked before application",
                blocking_entity_refs=request.constraint_refs or [request.target_object_id],
                settlement_status="rejected",
            )
            return PhysicalInteractionResult(
                result_id=f"physical_result:{request.request_id}",
                request_id=request.request_id,
                actor_id=request.actor_id,
                target_object_id=request.target_object_id,
                effect_kind=request.effect_kind,
                effect_applied=False,
                constraint_result=constraint.model_dump(),
                unified_results=[constraint.model_dump()],
            )

        effect_ref = f"physical_effect:{request.effect_kind}:{request.target_object_id}:{request.producer_ts}"
        object_ref = f"object_state_obs:{request.target_object_id}:{request.producer_ts}"
        body_ref = f"body_state_obs:{request.actor_id}:{request.producer_ts}"
        environment_ref = f"environment_state_obs:{request.zone_id}:{request.producer_ts}"
        object_result = ObjectStateResult(
            request_ref=request.request_id,
            result_id=f"object_state:{request.request_id}",
            room_id=request.room_id,
            scene_id=request.scene_id,
            zone_id=request.zone_id,
            actor_id=request.actor_id,
            source_type="esm_physical_channel",
            entity_id=request.target_object_id,
            target_object_id=request.target_object_id,
            result_type="object_state_result",
            causation_id=request.authority_ref or request.request_id,
            correlation_id=request.request_id,
            producer_ts=request.producer_ts + 1,
            machine_id=f"physical:{request.effect_kind}",
            previous_state="stable",
            current_state=f"physical_{request.effect_kind}_applied",
            change_summary=f"{request.effect_kind} effect applied to {request.target_object_id}",
            settlement_status="applied",
        )
        body_result = BodyStateResult(
            request_ref=request.request_id,
            result_id=f"body_state:{request.request_id}",
            room_id=request.room_id,
            scene_id=request.scene_id,
            zone_id=request.zone_id,
            actor_id=request.actor_id,
            source_type="esm_physical_channel",
            entity_id=request.actor_id,
            target_object_id=request.target_object_id,
            result_type="body_state_result",
            causation_id=request.authority_ref or request.request_id,
            correlation_id=request.request_id,
            producer_ts=request.producer_ts + 2,
            body_state_class=f"physical_{request.effect_kind}",
            previous_state="ready",
            current_state="contact_applied",
            change_summary=f"{request.actor_id} applied {request.effect_kind} to {request.target_object_id}",
            settlement_status="applied",
        )
        environment_result = EnvironmentStateResult(
            request_ref=request.request_id,
            result_id=f"environment_state:{request.request_id}",
            room_id=request.room_id,
            scene_id=request.scene_id,
            zone_id=request.zone_id,
            actor_id=request.actor_id,
            source_type="esm_physical_channel",
            entity_id=request.zone_id,
            target_object_id=request.target_object_id,
            target_environment_id=request.contact_observation.environment_ref if request.contact_observation else request.zone_id,
            result_type="environment_state_result",
            causation_id=request.authority_ref or request.request_id,
            correlation_id=request.request_id,
            producer_ts=request.producer_ts + 3,
            machine_id=f"physical:{request.effect_kind}",
            previous_state="stable",
            current_state="physical_effect_observed",
            change_summary=f"{request.effect_kind} observation available to L1/ESM feedback",
            affected_zone_ids=[request.zone_id],
            field_delta_summary=["physical_effect_observed"],
            updated_at=request.producer_ts + 3,
            settlement_status="observed",
        )
        return PhysicalInteractionResult(
            result_id=f"physical_result:{request.request_id}",
            request_id=request.request_id,
            actor_id=request.actor_id,
            target_object_id=request.target_object_id,
            effect_kind=request.effect_kind,
            effect_applied=True,
            structured_physical_effect_refs=[effect_ref],
            object_state_observation_refs=[object_ref],
            environment_state_observation_refs=[environment_ref],
            body_state_observation_refs=[body_ref],
            unified_results=[
                object_result.model_dump(),
                body_result.model_dump(),
                environment_result.model_dump(),
            ],
        )
