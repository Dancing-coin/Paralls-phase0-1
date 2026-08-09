from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.frost_farm_runtime import (
    CropState,
    EnvironmentFact,
    FarmPlot,
    FrostEffectInput,
    FrostFarmAuthority,
    ResistanceProfile,
)
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _command(key: str = "frost:1") -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="farm.apply_frost",
        command_version=1,
        principal_ref="owner:farm",
        actor_ref="actor:farm",
        project_ref="project:farm",
        transaction_id=f"transaction:{key}",
        idempotency_key=f"idempotency:{key}",
        expected_revisions={"plot:frost:1": 0},
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        source_ref="source:environment",
        submitted_at="2026-08-07T00:00:00Z",
        pinned_revisions={"world": 1, "policy": 1},
        payload={"stream_ref": "plot:frost:1", "event_type": "farm.crop_frost_evaluated"},
    )


def _effect(*, resistance: float = 0.25, permission: str = "owner:farm") -> FrostEffectInput:
    return FrostEffectInput(
        plot=FarmPlot(plot_ref="plot:frost:1", jurisdiction_ref="jurisdiction:north", owner_ref="owner:farm"),
        crop=CropState(crop_ref="crop:wheat:1", plot_ref="plot:frost:1", state="growing", health=100),
        resistance=ResistanceProfile(profile_ref="resistance:wheat:v1", resistance=resistance),
        frost_intensity=0.8,
        permission_scope=permission,
        environment_fact=EnvironmentFact(fact_ref="fact:frost:1", kind="frost", intensity=0.8, evidence_ref="evidence:frost:1"),
    )


def test_frost_hit_and_resistance_are_deterministic() -> None:
    first = FrostFarmAuthority.evaluate(_effect())
    second = FrostFarmAuthority.evaluate(_effect())
    assert first == second
    assert first.damage == 60


def test_full_resistance_rejects_effect_without_writing() -> None:
    result = FrostFarmAuthority.evaluate(_effect(resistance=1.0))
    assert result.damage == 0
    assert result.effect_applied is False


def test_permission_failure_and_duplicate_settlement_are_structured() -> None:
    with pytest.raises(ValueError, match="permission_denied"):
        _effect(permission="owner:other")
    store = GameplayEventStore()
    first = FrostFarmAuthority.settle(_effect(), command=_command(), store=store)
    duplicate = FrostFarmAuthority.settle(_effect(), command=_command(), store=store)
    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1
