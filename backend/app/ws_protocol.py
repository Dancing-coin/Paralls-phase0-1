from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SEMANTIC_FORBIDDEN_FIELDS = {"raw_hit", "hit", "damage", "ammo", "projectile", "pose", "transform", "velocity", "ballistic_truth"}


class ActorControlIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    session_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    connection_epoch: int = Field(ge=1)
    client_sequence: int = Field(ge=1)
    physics_tick: int = Field(ge=0)
    lease_revision: int = Field(ge=0)
    control_intents: list[dict[str, object]] = Field(default_factory=list)
    action_request_ids: list[str] = Field(default_factory=list)
    sent_at: int = Field(ge=0)


class ActorActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    session_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    connection_epoch: int = Field(ge=1)
    client_sequence: int = Field(ge=1)
    physics_tick: int = Field(ge=0)
    action_instance_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    expected_revisions: dict[str, int] = Field(default_factory=dict)
    request: dict[str, object]

    @model_validator(mode="after")
    def semantic_only(self) -> "ActorActionRequest":
        present = SEMANTIC_FORBIDDEN_FIELDS.intersection(self.request)
        if present:
            raise ValueError(f"forbidden semantic action field: {', '.join(sorted(present))}")
        return self


class FutureBodyStreamEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    actor_ref: str = Field(min_length=1)
    authority_epoch: int = Field(ge=1)
    physics_tick: int = Field(ge=0)
    body_revision: int = Field(ge=1)
    base_body_revision: int | None = Field(default=None, ge=0)
    position: tuple[float, float, float]
    velocity: tuple[float, float, float]
    facing: tuple[float, float, float]
    grounded: bool
    support_ref: str = ""
    active_action_ids: list[str] = Field(default_factory=list)
    correction_reason: str = ""
    snapshot_checksum: str = Field(min_length=1)


class ProtocolAdmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    accepted: bool
    code: str
    admission_only: bool = True


class ConnectedActionProtocol:
    mode = "B"
    mode_c_gates = (
        "physical_authority_owner", "fixed_tick_body_schema", "collision_determinism",
        "prediction_correction_budget", "interest_management", "body_revision_replay_rollback",
        "abuse_validation",
    )

    def __init__(self) -> None:
        self._epoch = 1
        self._next_sequence = 1
        self._lease_revision = 0

    def reconnect(self) -> int:
        self._epoch += 1
        self._next_sequence = 1
        self._lease_revision = 0
        return self._epoch

    def admit_control(self, intent: ActorControlIntent) -> ProtocolAdmission:
        if intent.connection_epoch != self._epoch:
            return ProtocolAdmission(accepted=False, code="connection_epoch_stale")
        if intent.client_sequence < self._next_sequence:
            return ProtocolAdmission(accepted=False, code="duplicate_client_sequence")
        if intent.client_sequence > self._next_sequence:
            return ProtocolAdmission(accepted=False, code="sequence_gap")
        if intent.lease_revision < self._lease_revision:
            return ProtocolAdmission(accepted=False, code="lease_revision_stale")
        self._lease_revision = intent.lease_revision
        self._next_sequence += 1
        return ProtocolAdmission(accepted=True, code="admitted")

    def admit_action(self, request: ActorActionRequest) -> ProtocolAdmission:
        if request.connection_epoch != self._epoch:
            return ProtocolAdmission(accepted=False, code="connection_epoch_stale")
        expires_at = request.request.get("expires_at_tick")
        if isinstance(expires_at, int) and request.physics_tick > expires_at:
            return ProtocolAdmission(accepted=False, code="action_expired")
        return ProtocolAdmission(accepted=True, code="admitted")


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_type: str
    payload: dict


class WebSocketSessionRenewalRequest(BaseModel):
    """A renewal request contains no client-chosen identity, scope, or credential."""

    model_config = ConfigDict(extra="forbid")

    protocol_version: int = Field(ge=2)


class GameplayMirrorCapabilityOffer(BaseModel):
    """Feature preferences only; server policy still chooses identity, scope, and fields."""

    model_config = ConfigDict(extra="forbid")

    protocol_version: int = Field(ge=1)
    supports_snapshot: bool
    supports_delta: bool = False
    supports_receipt: bool = False
    projection_schemas: tuple[str, ...] = ()


class GameplayMirrorCapabilityProfile(BaseModel):
    """Server-selected delivery features; never an identity or read-scope grant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: int = Field(ge=1)
    supports_snapshot: bool = True
    supports_delta: bool = False
    supports_receipt: bool = False
    projection_schema: str = Field(min_length=1)


class GameplayMirrorReceipt(BaseModel):
    """Transport telemetry for one server-issued delivery sequence."""

    model_config = ConfigDict(extra="forbid")

    connection_epoch: int = Field(ge=1)
    delivery_sequence: int = Field(ge=1)


class GameplayMirrorPredictionResolution(BaseModel):
    """Server-issued resolution for one bounded, presentation-only prediction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prediction_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    resolution: Literal["confirmed", "rejected"]
    transaction_id: str = ""
    error_code: str = ""

    @model_validator(mode="after")
    def _validate_authority_result(self) -> "GameplayMirrorPredictionResolution":
        if self.resolution == "confirmed" and not self.transaction_id:
            raise ValueError("prediction_confirmation_transaction_required")
        if self.resolution == "rejected" and not self.error_code:
            raise ValueError("prediction_rejection_error_required")
        return self


class GameplayMirrorDeliveryEnvelope(BaseModel):
    """Versioned, already-filtered snapshot/delta transport wrapper."""

    model_config = ConfigDict(extra="forbid")

    delivery_kind: Literal["snapshot", "delta", "prediction"]
    connection_epoch: int = Field(ge=1)
    delivery_sequence: int = Field(ge=1)
    actor_ref: str = Field(min_length=1)
    projection_schema: str = Field(min_length=1)
    facade_revision: str = Field(min_length=1)
    base_facade_revision: str | None = None
    base_snapshot_checksum: str | None = None
    target_snapshot_checksum: str | None = None
    source_revision_vector: dict[str, int] | None = None
    payload: dict[str, object]
    prediction_resolutions: tuple[GameplayMirrorPredictionResolution, ...] = ()

    @model_validator(mode="after")
    def _validate_delivery_base(self) -> "GameplayMirrorDeliveryEnvelope":
        if self.delivery_kind == "prediction":
            if not self.prediction_resolutions:
                raise ValueError("prediction_resolution_required")
            return self
        if self.delivery_kind == "snapshot":
            return self
        if (
            not self.base_facade_revision
            or not self.base_snapshot_checksum
            or not self.target_snapshot_checksum
            or self.source_revision_vector is None
        ):
            raise ValueError("mirror_delta_exact_base_required")
        return self


class GovernmentDroughtAdvisoryDeliveryEnvelope(BaseModel):
    """Fixed project-scoped presentation message for a committed Government advisory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connection_epoch: int = Field(ge=1)
    delivery_sequence: int = Field(ge=1)
    projection_kind: Literal["government_drought_advisory.project.v1"]
    jurisdiction_ref: str = Field(min_length=1)
    advisory_refs: tuple[str, ...] = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(min_length=1)
    projection_hash: str = Field(min_length=1)


class GameplayMirrorProtocolError(BaseModel):
    """Finite Phase 4 control/error vocabulary shared by typed protocol handlers."""

    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "renewal_denied",
        "renewal_enrollment_required",
        "session_expired",
        "session_revoked",
        "mirror_sequence_invalid",
        "mirror_sequence_stale",
        "mirror_receipt_unknown",
        "mirror_receipt_out_of_window",
        "mirror_resync_required",
        "mirror_backpressure",
        "mirror_capability_incompatible",
    ]
