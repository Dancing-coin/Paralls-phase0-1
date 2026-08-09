from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.frost_farm_runtime import (
    CropState,
    EnvironmentFact,
    FarmPlot,
    FrostEffectInput,
    FrostFarmAuthority,
    ResistanceProfile,
)
from app.gameplay.ownership_contract_debt_sample import OwnershipContractDebtSample
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import SettlementPlan
from app.gameplay.shared_contracts import GameplayCommandEnvelope


@dataclass(frozen=True)
class GeneralizationComparison:
    samples: tuple[str, ...]
    shared_contract_fields: tuple[str, ...]
    sample_only_fields: dict[str, tuple[str, ...]]
    owner_diff: dict[str, str]
    replay_hashes: dict[str, str]
    deferred_domains: tuple[str, ...]


def _replay_hash(sample: str, events: list[object]) -> str:
    replay = GameplayProjectionReplay(projector_id=f"projection:{sample}", projector_version="v1")
    result = replay.full_replay(events)  # type: ignore[arg-type]
    if not result.succeeded:
        raise ValueError(f"{sample}_replay_failed")
    return result.projection_hash


def _frost_events() -> list[object]:
    effect = FrostEffectInput(
        plot=FarmPlot(plot_ref="plot:frost:p1e", jurisdiction_ref="jurisdiction:north", owner_ref="owner:farm"),
        crop=CropState(crop_ref="crop:wheat:p1e", plot_ref="plot:frost:p1e", state="growing", health=100),
        resistance=ResistanceProfile(profile_ref="resistance:wheat:v1", resistance=0.25),
        frost_intensity=0.8,
        permission_scope="owner:farm",
        environment_fact=EnvironmentFact(fact_ref="fact:frost:p1e", kind="frost", intensity=0.8, evidence_ref="evidence:frost:p1e"),
    )
    command = GameplayCommandEnvelope(
        command_id="command:frost:p1e",
        command_type="farm.apply_frost",
        command_version=1,
        principal_ref="owner:farm",
        actor_ref="actor:farm",
        project_ref="project:p1e",
        transaction_id="transaction:frost:p1e",
        idempotency_key="idempotency:frost:p1e",
        expected_revisions={"plot:frost:p1e": 0},
        causation_id="causation:frost:p1e",
        correlation_id="correlation:frost:p1e",
        source_ref="source:environment",
        submitted_at="p1e",
        pinned_revisions={"world": 1, "policy": 1},
        payload={"stream_ref": "plot:frost:p1e", "event_type": "farm.crop_frost_evaluated"},
    )
    store = GameplayEventStore()
    result = FrostFarmAuthority.settle(effect, command=command, store=store)
    if not result.committed:
        raise ValueError("frost_farm_settlement_failed")
    return store.read_events()


def _bakery_events() -> list[object]:
    store = GameplayEventStore()
    BakeryReferenceScenario.default().execute_period(1, store=store)
    return store.read_events()


def _ownership_contract_debt_events() -> list[object]:
    sample = OwnershipContractDebtSample(
        applicant_ref="character:char_a",
        collateral_ref="ownership:right:1",
        principal=100,
        term_ticks=10,
    )
    store = GameplayEventStore()
    result = store.append_batch(
        SettlementPlan.from_command_envelope(
            sample.to_command(custody_ref="ownership:right:1", permission_scope="character:char_a")
        ).to_atomic_event_batch()
    )
    if not result.committed:
        raise ValueError("ownership_contract_debt_settlement_failed")
    return store.read_events()


def build_generalization_comparison() -> GeneralizationComparison:
    samples = ("frost-farm", "bakery-single-owner", "ownership-contract-debt")
    events = {
        "frost-farm": _frost_events(),
        "bakery-single-owner": _bakery_events(),
        "ownership-contract-debt": _ownership_contract_debt_events(),
    }
    shared_candidates = (
        "command_id",
        "expected_revisions",
        "idempotency_key",
        "causation_id",
        "correlation_id",
        "pinned_revisions",
    )
    shared_contract_fields = tuple(
        field for field in shared_candidates if field in GameplayCommandEnvelope.model_fields
    )
    sample_only_fields = {
        "frost-farm": tuple(
            field
            for field in ("frost_intensity", "resistance", "environment_fact")
            if field in FrostEffectInput.model_fields
        ),
        "bakery-single-owner": tuple(
            field
            for field in ("facility", "recipe", "permit", "period_count")
            if field in BakeryReferenceScenario.__dataclass_fields__
        ),
        "ownership-contract-debt": tuple(
            field
            for field in ("collateral_ref", "principal", "term_ticks")
            if field in OwnershipContractDebtSample.model_fields
        ),
    }
    owner_diff = {
        "frost-farm": FrostFarmAuthority.owner,
        "bakery-single-owner": ",".join(sorted({event.stream_id.split(":")[1] for event in events["bakery-single-owner"]})),
        "ownership-contract-debt": events["ownership-contract-debt"][0].event_type.split(".")[1],
    }
    return GeneralizationComparison(
        samples=samples,
        shared_contract_fields=shared_contract_fields,
        sample_only_fields=sample_only_fields,
        owner_diff=owner_diff,
        replay_hashes={sample: _replay_hash(sample, sample_events) for sample, sample_events in events.items()},
        deferred_domains=("dynamic market", "Population Simulation", "Creator Control Plane"),
    )


__all__ = ["GeneralizationComparison", "build_generalization_comparison"]
