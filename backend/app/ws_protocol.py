from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
