from __future__ import annotations

from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RealizationRoute = Literal["embodied_controller_v1"]
SettlementWriterKind = Literal["esm_compatibility_adapter", "gameplay_event_batch_writer"]
AuthorityRoute = Literal["esm", "gameplay", "composite"]
AuthorityOutcome = Literal["committed", "rejected", "unknown"]
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
FORBIDDEN_ACTION_ATTEMPT_FIELDS = {
    "damage", "hit", "hit_confirmed", "ammo", "ammo_delta", "projectile",
    "projectile_id", "ballistic_outcome", "ballistic_truth", "pose",
    "transform", "velocity", "raw_pose", "raw_clip_filename",
}


class StrictEmbodiedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActionAttempt(StrictEmbodiedModel):
    """Canonical semantic request crossing the embodiment/authority boundary."""

    attempt_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    action_instance_id: str = Field(min_length=1)
    semantic_action_id: str = Field(min_length=1)
    target_refs: list[str] = Field(default_factory=list)
    contact_marker_id: str = Field(min_length=1)
    contact_marker_time_seconds: float | None = Field(default=None, ge=0.0)
    action_family: str | None = None
    weapon_ref: str | None = None
    physics_tick: int = Field(ge=0)
    # Mode B transport identity. Defaults preserve Phase 0 fixture callers that
    # predate the connected-action envelope; real transport callers must set
    # these explicitly and the authority admission fence observes that field
    # presence via ``model_fields_set``.
    connection_epoch: int = Field(default=1, ge=1)
    client_sequence: int = Field(default=1, ge=1)
    physics_evidence_refs: list[str] = Field(default_factory=list)
    physics_evidence_digest: str | None = None
    action_descriptor_digest: str | None = None
    authority_route: AuthorityRoute
    owner_contract_ref: str | None = None
    expected_revisions: dict[str, int] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1)
    command_version: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    privacy_scope: str = Field(min_length=1)
    collider_refs: list[str] = Field(default_factory=list)
    hit_sensor_refs: list[str] = Field(default_factory=list)
    contact_points: list[dict[str, object]] = Field(default_factory=list)
    submitted_at: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def reject_client_truth(cls, value: object) -> object:
        if isinstance(value, dict):
            present = sorted(FORBIDDEN_ACTION_ATTEMPT_FIELDS.intersection(value.keys()))
            if present:
                raise ValueError(f"forbidden action attempt field: {', '.join(present)}")
        return value

    @model_validator(mode="after")
    def validate_bounds(self) -> "ActionAttempt":
        limits = {
            "target_refs": (self.target_refs, 8),
            "physics_evidence_refs": (self.physics_evidence_refs, 8),
            "collider_refs": (self.collider_refs, 32),
            "hit_sensor_refs": (self.hit_sensor_refs, 16),
            "contact_points": (self.contact_points, 32),
        }
        for name, (values, limit) in limits.items():
            if len(values) > limit:
                raise ValueError(f"{name}_limit")
        if len(self.canonical_payload_bytes()) > 32 * 1024:
            raise ValueError("payload_limit_exceeded")
        return self

    def canonical_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json", exclude={"submitted_at"})
        return payload

    def canonical_payload_bytes(self) -> bytes:
        return json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    @property
    def payload_digest(self) -> str:
        return "sha256:" + sha256(self.canonical_payload_bytes()).hexdigest()

    @property
    def request_digest(self) -> str:
        """Stable alias used by Mode B replay/evidence consumers."""

        return self.payload_digest


class AuthorityResult(StrictEmbodiedModel):
    attempt_id: str = Field(min_length=1)
    action_instance_id: str = Field(min_length=1)
    transaction_id: str | None = None
    outcome: AuthorityOutcome
    committed_event_ids: list[str] = Field(default_factory=list)
    resulting_revisions: dict[str, int] = Field(default_factory=dict)
    failed_stage: str | None = None
    failed_code: str | None = None
    failed_precondition: str | None = None
    recovery_action: str | None = None
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    authority_scope: str = Field(min_length=1)
    committed_projection: dict[str, object] = Field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json")


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
    turn_id: str = ""
    execution_contract_ref: str = ""
    episode_ref: str = ""
    pre_capture_ref: str = ""

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
