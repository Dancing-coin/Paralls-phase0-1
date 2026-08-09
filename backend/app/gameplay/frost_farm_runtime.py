"""Bounded frost-farm contract sample; all writes terminate at GameplayEventStore."""

from __future__ import annotations

from hashlib import sha256
import json

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel
from app.gameplay.shared_contracts import GameplayCommandEnvelope, ProjectionEnvelope
from app.gameplay.models import ReplayResult
from app.gameplay.settlement_plan import SettlementPlan


class FarmPlot(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plot_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    revision: int = Field(default=0, ge=0)


class CropState(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    crop_ref: str = Field(min_length=1)
    plot_ref: str = Field(min_length=1)
    state: str = Field(min_length=1)
    health: int = Field(ge=0, le=100)


class EnvironmentFact(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_ref: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    intensity: float = Field(ge=0)
    evidence_ref: str = Field(min_length=1)
    revision: int = Field(default=0, ge=0)


class ResistanceProfile(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_ref: str = Field(min_length=1)
    resistance: float = Field(ge=0, le=1)
    revision: int = Field(default=1, ge=1)


class FrostEffectInput(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plot: FarmPlot
    crop: CropState
    resistance: ResistanceProfile
    frost_intensity: float = Field(ge=0)
    permission_scope: str = Field(min_length=1)
    environment_fact: EnvironmentFact | None = None
    expected_plot_revision: int | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "FrostEffectInput":
        if self.crop.plot_ref != self.plot.plot_ref:
            raise ValueError("target_missing")
        if self.permission_scope != self.plot.owner_ref:
            raise ValueError("permission_denied")
        if self.expected_plot_revision is not None and self.expected_plot_revision != self.plot.revision:
            raise ValueError("revision_conflict")
        return self


class FrostEvaluationResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    crop_ref: str
    effect_applied: bool
    damage: int = Field(ge=0)
    next_health: int = Field(ge=0, le=100)
    result_digest: str
    failure_code: str | None = None


class FrostFarmAuthority:
    owner = "frost_farm"

    @staticmethod
    def evaluate(effect: FrostEffectInput) -> FrostEvaluationResult:
        if effect.environment_fact is not None and effect.environment_fact.kind != "frost":
            return FrostEvaluationResult(
                crop_ref=effect.crop.crop_ref,
                effect_applied=False,
                damage=0,
                next_health=effect.crop.health,
                result_digest="sha256:rejected",
                failure_code="precondition_failed",
            )
        effective_intensity = effect.environment_fact.intensity if effect.environment_fact is not None else effect.frost_intensity
        damage = min(effect.crop.health, int(round(effective_intensity * (1 - effect.resistance.resistance) * 100)))
        next_health = effect.crop.health - damage
        payload = {
            "crop_ref": effect.crop.crop_ref,
            "plot_ref": effect.plot.plot_ref,
            "damage": damage,
            "next_health": next_health,
            "resistance_revision": effect.resistance.revision,
        }
        digest = "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return FrostEvaluationResult(
            crop_ref=effect.crop.crop_ref,
            effect_applied=damage > 0,
            damage=damage,
            next_health=next_health,
            result_digest=digest,
        )

    @classmethod
    def settle(cls, effect: FrostEffectInput, *, command: GameplayCommandEnvelope, store: GameplayEventStore):
        result = cls.evaluate(effect)
        if result.failure_code is not None:
            raise ValueError(result.failure_code)
        payload = dict(command.payload)
        payload.update(
            {
                "stream_ref": effect.plot.plot_ref,
                "event_type": "farm.crop_frost_evaluated",
                "crop_ref": result.crop_ref,
                "damage": result.damage,
                "next_health": result.next_health,
                "evidence_refs": [effect.environment_fact.evidence_ref] if effect.environment_fact else [],
            }
        )
        bound_command = command.model_copy(update={"payload": payload}, deep=True)
        return store.append_batch(SettlementPlan.from_command_envelope(bound_command).to_atomic_event_batch())


def project_frost_result(result: ReplayResult, *, scope: str) -> ProjectionEnvelope:
    if not result.succeeded:
        raise ValueError("projection_unavailable")
    payload: dict[str, object] = {}
    for stream_state in result.state.values():
        if not isinstance(stream_state, dict):
            continue
        event_payload = stream_state.get("last_payload")
        if isinstance(event_payload, dict):
            payload.update(event_payload)
    if scope != "authority":
        payload = {key: payload[key] for key in ("crop_ref", "damage", "next_health") if key in payload}
    return ProjectionEnvelope(
        schema_id="projection:frost-farm",
        schema_version=1,
        projection_revision=f"global:{result.last_global_sequence}",
        source_revision_vector=result.source_revision_vector,
        privacy_scope=scope,
        payload=payload,
        evidence_refs=(),
    )


__all__ = [
    "CropState",
    "EnvironmentFact",
    "FarmPlot",
    "FrostEffectInput",
    "FrostEvaluationResult",
    "FrostFarmAuthority",
    "ResistanceProfile",
    "project_frost_result",
]
