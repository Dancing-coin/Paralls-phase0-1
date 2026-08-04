from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RealizationRoute = Literal["legacy_character_replica", "embodied_controller_v1"]
SettlementWriterKind = Literal["esm_compatibility_adapter", "gameplay_event_batch_writer"]
AnchorRole = Literal[
    "approach_stance",
    "contact",
    "grip",
    "place",
    "handoff_source",
    "handoff_target",
    "social_slot",
    "observation",
]
BindingHealth = Literal["healthy", "unhealthy", "stale", "missing"]
TerminalStatus = Literal[
    "contact_observed",
    "completed_without_contact",
    "aborted",
    "interrupted",
    "failed_precondition",
    "failed_navigation",
    "failed_alignment",
    "missed_contact",
    "observation_invalid",
]
InteractionSessionState = Literal[
    "proposed",
    "awaiting_responses",
    "authorized",
    "realizing",
    "settling",
    "committed",
    "rejected",
    "cancelled",
    "interrupted",
    "expired",
]

FORBIDDEN_EMBODIED_REQUEST_FIELDS = {
    "raw_keyboard",
    "raw_mouse",
    "raw_camera",
    "raw_input",
    "camera_noise",
    "mouse_delta",
    "bone_transforms",
    "bone_stream",
    "rigid_body_velocity",
    "rigid_body_impulse",
    "velocity",
    "impulse",
    "node_path",
    "gdscript",
    "final_world_state",
    "world_truth_claim",
}
FORBIDDEN_LOCAL_OUTCOME_FIELDS = {
    "bone_transforms",
    "bone_stream",
    "rigid_body_stream",
    "raw_physics_dump",
    "applied_world_state",
    "world_truth_claim",
    "character_actor_status",
}


class StrictEmbodiedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _reject_forbidden_fields(value: object, forbidden_fields: set[str]) -> object:
    if not isinstance(value, dict):
        return value
    present = sorted(forbidden_fields.intersection(value.keys()))
    if present:
        raise ValueError(f"forbidden embodied contract field: {', '.join(present)}")
    return value


class LocalBindingRef(StrictEmbodiedModel):
    node_ref: str = Field(min_length=1)
    collider_refs: list[str] = Field(min_length=1)
    navigation_footprint_ref: str = Field(min_length=1)


class SceneAffordanceAnchor(StrictEmbodiedModel):
    anchor_id: str = Field(min_length=1)
    role: AnchorRole
    local_transform: dict[str, object] = Field(default_factory=dict)
    reach_constraints: dict[str, object] = Field(default_factory=dict)


class SceneAffordance(StrictEmbodiedModel):
    affordance_id: str = Field(min_length=1)
    action_semantic: str = Field(min_length=1)
    preconditions: list[str] = Field(default_factory=list)
    execution_profile_ref: str = Field(min_length=1)
    observation_rule_ref: str = Field(min_length=1)
    policy_ref: str = Field(min_length=1)


class GroundingCatalogRefs(StrictEmbodiedModel):
    entity_ref: str = Field(min_length=1)
    collider_refs: list[str] = Field(min_length=1)
    anchor_refs: list[str] = Field(min_length=1)


class SceneAffordanceRecord(StrictEmbodiedModel):
    entity_ref: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    scene_instance_id: str = Field(min_length=1)
    binding_revision: int = Field(ge=1)
    semantic_type: str = Field(min_length=1)
    semantic_tags: list[str] = Field(default_factory=list)
    authoritative_state_ref: str = Field(min_length=1)
    local_binding: LocalBindingRef
    anchors: list[SceneAffordanceAnchor] = Field(min_length=1)
    affordances: list[SceneAffordance] = Field(min_length=1)
    grounding_catalog_refs: GroundingCatalogRefs
    physical_profile_ref: str = ""
    visibility_policy: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    binding_health: BindingHealth = "healthy"

    @model_validator(mode="after")
    def validate_grounding_identity(self) -> "SceneAffordanceRecord":
        if self.entity_ref != self.grounding_catalog_refs.entity_ref:
            raise ValueError("grounding catalog identity mismatch: entity_ref")
        if self.local_binding.collider_refs != self.grounding_catalog_refs.collider_refs:
            raise ValueError("grounding catalog identity mismatch: collider_refs")
        anchor_refs = [anchor.anchor_id for anchor in self.anchors]
        if anchor_refs != self.grounding_catalog_refs.anchor_refs:
            raise ValueError("grounding catalog identity mismatch: anchor_refs")
        return self


class EmbodiedActionRequest(StrictEmbodiedModel):
    request_id: str = Field(min_length=1)
    interaction_attempt_id: str = Field(min_length=1)
    session_id: str | None = None
    actor_id: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    action_semantic: str = Field(min_length=1)
    affordance_id: str = Field(min_length=1)
    authority_preflight_ref: str = Field(min_length=1)
    policy_revision: int = Field(ge=1)
    scene_revision: int = Field(ge=1)
    binding_revision: int = Field(ge=1)
    required_anchor_roles: list[AnchorRole] = Field(min_length=1)
    execution_profile_ref: str = Field(min_length=1)
    expiration_tick: int = Field(ge=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    realization_route: RealizationRoute
    settlement_writer_kind: SettlementWriterKind

    @model_validator(mode="before")
    @classmethod
    def validate_control_boundary(cls, value: object) -> object:
        value = _reject_forbidden_fields(value, FORBIDDEN_EMBODIED_REQUEST_FIELDS)
        if isinstance(value, dict) and isinstance(value.get("settlement_writer_kind"), list):
            raise ValueError("embodied request must name a single settlement writer")
        if isinstance(value, dict) and isinstance(value.get("realization_route"), list):
            raise ValueError("embodied request must name a single realization route")
        return value


class ControllerBinding(StrictEmbodiedModel):
    binding_id: str = Field(min_length=1)
    authenticated_principal_ref: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    controller_instance_id: str = Field(min_length=1)
    connection_epoch: int = Field(ge=1)
    state: Literal["bound", "revoked"] = "bound"


class ControllerExecutionGrant(StrictEmbodiedModel):
    grant_id: str = Field(min_length=1)
    authenticated_principal_ref: str = Field(min_length=1)
    controller_instance_id: str = Field(min_length=1)
    connection_epoch: int = Field(ge=1)
    interaction_attempt_id: str = Field(min_length=1)
    session_id: str | None = None
    actor_id: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    affordance_id: str = Field(min_length=1)
    request_digest: str = Field(min_length=1)
    scene_revision: int = Field(ge=1)
    binding_revision: int = Field(ge=1)
    policy_revision: int = Field(ge=1)
    issued_at: int = Field(ge=0)
    expires_at: int = Field(ge=1)
    one_time_outcome_nonce: str = Field(min_length=1)
    allowed_phase_range: tuple[int, int] = (1, 100)
    state: Literal["issued", "consumed", "revoked", "expired"] = "issued"


class ContactObservation(StrictEmbodiedModel):
    contact_ref: str = Field(min_length=1)
    actor_contact_ref: str = Field(min_length=1)
    target_collider_ref: str = Field(min_length=1)
    contact_window_ref: str = Field(min_length=1)
    observation_rule_ref: str = ""
    hand_alignment_error_m: float | None = Field(default=None, ge=0.0)


class ObjectObservation(StrictEmbodiedModel):
    object_ref: str = Field(min_length=1)
    previous_state: str = Field(min_length=1)
    observed_state: str = Field(min_length=1)
    observation_rule_ref: str = Field(min_length=1)


class LocalExecutionOutcome(StrictEmbodiedModel):
    interaction_attempt_id: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    terminal_status: TerminalStatus
    observed_at: int = Field(ge=0)
    actor_pose_ref: str = Field(min_length=1)
    target_binding_ref: str = Field(min_length=1)
    contact_observation: ContactObservation | None = None
    object_observation: ObjectObservation | None = None
    body_observation: dict[str, object] | None = None
    environment_observation: dict[str, object] | None = None
    failure_code: str = ""
    trace_refs: list[str] = Field(default_factory=list)
    # Semantic local realization evidence is auditable but cannot assert world truth.
    local_ownership_restored: bool = True
    selected_action_tags: list[str] = Field(default_factory=list)
    phase_action_tags: dict[str, list[str]] = Field(default_factory=dict)
    local_root_motion_phase_refs: dict[str, list[str]] = Field(default_factory=dict)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    controller_grant_id: str = Field(min_length=1)
    connection_epoch: int = Field(ge=1)
    terminal_sequence: int = Field(ge=1)
    outcome_nonce: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def validate_local_boundary(cls, value: object) -> object:
        return _reject_forbidden_fields(value, FORBIDDEN_LOCAL_OUTCOME_FIELDS)

    @field_validator("controller_grant_id", "outcome_nonce")
    @classmethod
    def require_non_empty_attestation(cls, value: str) -> str:
        if value == "":
            raise ValueError("controller_grant_id and outcome_nonce are required")
        return value


class EmbodiedPresentationObservation(StrictEmbodiedModel):
    """A bounded local acknowledgement of an already-applied authority result."""

    interaction_attempt_id: str = Field(min_length=1)
    settlement_id: str = Field(min_length=1)
    snapshot_digest: str = Field(min_length=1)


class EmbodiedSettlementResult(StrictEmbodiedModel):
    settlement_ref: str = Field(min_length=1)
    interaction_attempt_id: str = Field(min_length=1)
    session_id: str | None = None
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    settlement_writer_kind: SettlementWriterKind
    outcome: Literal["committed", "rejected", "not_committed", "observation_rejected"]
    authority_result_refs: list[str] = Field(default_factory=list)
    resulting_world_state_refs: list[str] = Field(default_factory=list)
    retry_policy: str = "none"
    presentation_directive: dict[str, object] = Field(default_factory=dict)


class InteractionSessionParticipantTerm(StrictEmbodiedModel):
    participant_ref: str = Field(min_length=1)
    slot_id: str = Field(min_length=1)
    consent_state: Literal["pending", "accepted", "rejected", "cancelled"] = "pending"
    response_ref: str = ""


class InteractionSessionSlotAssignment(StrictEmbodiedModel):
    slot_id: str = Field(min_length=1)
    participant_ref: str = Field(min_length=1)
    role: str = Field(min_length=1)
    reservation_ref: str = Field(min_length=1)
    reservation_state: Literal["reserved", "released"] = "reserved"


class InteractionSessionTerminalObservation(StrictEmbodiedModel):
    participant_ref: str = Field(min_length=1)
    attempt_ref: str = Field(min_length=1)
    terminal_status: Literal["completed", "refused", "cancelled", "interrupted", "failed"]
    payload_digest: str = Field(min_length=1)


class InteractionSession(StrictEmbodiedModel):
    session_id: str = Field(min_length=1)
    semantic_action: str = Field(min_length=1)
    initiator_ref: str = Field(min_length=1)
    participant_refs: list[str] = Field(min_length=2)
    target_refs: list[str] = Field(default_factory=list)
    state: InteractionSessionState
    participant_terms: list[InteractionSessionParticipantTerm] = Field(min_length=1)
    slot_assignments: list[InteractionSessionSlotAssignment] = Field(default_factory=list)
    reservation_refs: list[str] = Field(default_factory=list)
    authority_preflight_ref: str = Field(min_length=1)
    policy_revision: int = Field(ge=1)
    scene_revision: int = Field(ge=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    attempt_refs: list[str] = Field(default_factory=list)
    settlement_ref: str | None = None
    visibility_policy: str = Field(min_length=1)
    audit_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_session_participants(self) -> "InteractionSession":
        if self.initiator_ref not in self.participant_refs:
            raise ValueError("initiator_ref must be one of participant_refs")
        term_refs = [term.participant_ref for term in self.participant_terms]
        if sorted(term_refs) != sorted(self.participant_refs):
            raise ValueError("participant_terms must match participant_refs")
        slot_refs = [slot.participant_ref for slot in self.slot_assignments]
        unknown_slots = sorted(set(slot_refs).difference(self.participant_refs))
        if unknown_slots:
            raise ValueError("slot assignment participant is not in participant_refs")
        return self


class SettlementWriterSelection(StrictEmbodiedModel):
    writer_kind: SettlementWriterKind | None = None
    accepted: bool
    error_code: str = ""
    effect_scope: str
    dual_write: bool = False


class EmbodiedSettlementWriterSelector:
    def __init__(self, *, gameplay_event_batch_writer_available: bool) -> None:
        self.gameplay_event_batch_writer_available = gameplay_event_batch_writer_available

    def select(
        self,
        *,
        action_semantic: str,
        effect_scope: str,
        requested_writer_kind: SettlementWriterKind,
    ) -> SettlementWriterSelection:
        if requested_writer_kind == "esm_compatibility_adapter":
            if action_semantic == "kick" and effect_scope == "single_object_physical":
                return SettlementWriterSelection(
                    writer_kind="esm_compatibility_adapter",
                    accepted=True,
                    effect_scope=effect_scope,
                )
            return SettlementWriterSelection(
                accepted=False,
                effect_scope=effect_scope,
                error_code="esm_compatibility_adapter_scope_violation",
            )
        if not self.gameplay_event_batch_writer_available:
            return SettlementWriterSelection(
                accepted=False,
                effect_scope=effect_scope,
                error_code="gameplay_event_batch_writer_unavailable",
            )
        return SettlementWriterSelection(
            writer_kind="gameplay_event_batch_writer",
            accepted=True,
            effect_scope=effect_scope,
        )


class EmbodiedProjectionPolicy(StrictEmbodiedModel):
    policy_ref: str = Field(min_length=1)
    allowed_fields: set[str] = Field(default_factory=set)

    @classmethod
    def public_observatory(cls) -> "EmbodiedProjectionPolicy":
        return cls(
            policy_ref="projection:public_observatory:v1",
            allowed_fields={
                "interaction_attempt_id",
                "session_id",
                "safe_phase",
                "settlement_status",
                "retry_directive",
                "presentation_directive",
                "public_effect_summary",
                "visible_evidence_refs",
                "sync_status",
            },
        )

    def project(self, payload: dict[str, object]) -> dict[str, object]:
        return {key: payload[key] for key in payload if key in self.allowed_fields}


class EmbodiedEvidenceEvent(StrictEmbodiedModel):
    attempt_id: str = Field(min_length=1)
    event_kind: Literal[
        "request_authorized",
        "registry_binding",
        "local_phase",
        "terminal_local_observation",
        "settlement",
        "presentation",
        "late_after_terminal",
        "session_lifecycle",
        "participant_terminal_observation",
    ]
    emitter_kind: Literal["backend", "controller", "godot_mirror", "observatory"]
    emitter_id: str = Field(min_length=1)
    emitter_epoch: int = Field(ge=1)
    source_sequence: int = Field(ge=1)
    server_ledger_sequence: int = Field(ge=1)
    payload_digest: str = Field(min_length=1)
    occurred_at: int = Field(ge=0)
    recorded_at: int = Field(ge=0)
    projection_policy_ref: str = Field(min_length=1)
