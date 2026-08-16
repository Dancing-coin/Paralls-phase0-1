from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import (
    GovernedAuthorityContractCatalog,
    GovernedAuthorityContractError,
)
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.survival_runtime import SurvivalAuthority


def _survival_command(*, key: str = "survival-fatigue:catalog", expected_revision: int = 0) -> GameplayCommandEnvelope:
    actor_ref = "character:ava"
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.survival.apply_state",
        command_version=1,
        principal_ref=SurvivalAuthority._PRINCIPAL,
        actor_ref=actor_ref,
        project_ref="project:demo",
        idempotency_key=key,
        expected_revisions={f"gameplay:survival:{actor_ref}": expected_revision},
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        source_ref="proposal:semantic:fatigue:1",
        submitted_at="2026-08-16T00:00:00Z",
        pinned_revisions={"semantic": 1},
        payload={},
    )


def _survival_application() -> EffectApplication:
    return EffectApplication(
        effect_ref="effect:fatigue_exposure",
        target_component_ref="character:ava",
        magnitude=100,
        stack_key="fatigue",
        expires_at_tick=8,
        causal_chain_id="chain:fatigue:1",
    )


def _survival_resistance() -> ResistanceProfile:
    return ResistanceProfile(
        effect_ref="effect:fatigue_exposure",
        source_ref="character:ava",
        modifier_basis_points=2_500,
        revision=1,
    )


def _survival_state() -> StateDefinition:
    return StateDefinition(
        state_ref="state:fatigued",
        stack_policy="refresh",
        stack_limit=1,
        expiry_policy="scheduled",
        transform_targets=("state:recovering",),
    )


def _seed_construction_facility(store: GameplayEventStore) -> None:
    authority = ConstructionProductionAuthority(store=store)
    plot = Plot(
        plot_ref="plot:bakery:1",
        jurisdiction_ref="jurisdiction:demo",
        owner_ref="org:bakery",
    )
    facility = Facility(
        facility_ref="facility:bakery:1",
        plot_ref=plot.plot_ref,
        facility_kind="bakery",
        condition=1.0,
    )
    assert authority.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id="construction:facility:1",
        idempotency_key="construction:facility:1",
        causation_id="cause:facility:1",
        correlation_id="corr:facility:1",
    ).committed


def test_lifecycle_contract_catalog_materializes_only_the_five_exact_owner_rows() -> None:
    lifecycle_contracts = tuple(
        contract
        for contract in GovernedAuthorityContractCatalog.contracts()
        if contract.contract_ref.endswith(("state-expiry@1", "accrual-obligation@1"))
    )

    assert [
        (
            contract.contract_ref,
            contract.owner_ref,
            contract.stream_patterns,
            contract.event_types,
            contract.projection_scope,
        )
        for contract in lifecycle_contracts
    ] == [
        (
            "inf:construction-maintenance-state-expiry@1",
            "actor_gameplay.construction_production_domain",
            ("gameplay:construction_production:{facility_ref}",),
            (
                "gameplay.construction_production.maintenance_state_applied",
                "gameplay.construction_production.maintenance_state_obligation_opened",
                "gameplay.construction_production.maintenance_state_expired",
                "gameplay.construction_production.maintenance_state_obligation_settled",
                "gameplay.construction_production.maintenance_state_dispelled",
                "gameplay.construction_production.maintenance_state_obligation_cancelled",
            ),
            "project",
        ),
        (
            "inf:ecology-drought-state-expiry@1",
            "authority:ecology",
            ("gameplay:ecology:{region_ref}",),
            (
                "gameplay.ecology.drought_state_applied",
                "gameplay.ecology.drought_state_obligation_opened",
                "gameplay.ecology.drought_state_expired",
                "gameplay.ecology.drought_state_obligation_settled",
            ),
            "project",
        ),
        (
            "inf:ecology-frost-state-expiry@1",
            "authority:ecology",
            ("gameplay:ecology:{region_ref}",),
            (
                "gameplay.ecology.crop_state_applied",
                "gameplay.ecology.crop_state_obligation_opened",
                "gameplay.ecology.crop_state_expired",
                "gameplay.ecology.crop_state_obligation_settled",
                "gameplay.ecology.crop_state_dispelled",
                "gameplay.ecology.crop_state_obligation_cancelled",
            ),
            "project",
        ),
        (
            "inf:economy-wage-accrual-obligation@1",
            "actor_gameplay.econ1_economy_domain",
            ("gameplay:economy:wage:{worker_ref}",),
            (
                "gameplay.economy.wage_obligation_opened",
                "gameplay.economy.wage_accrued",
                "gameplay.economy.wage_obligation_settled",
                "gameplay.economy.wage_obligation_retry_scheduled",
                "gameplay.economy.wage_obligation_cancelled",
                "gameplay.economy.wage_obligation_expired",
                "gameplay.economy.wage_accrual_compensated",
                "gameplay.economy.wage_obligation_compensated",
            ),
            "project",
        ),
        (
            "inf:survival-state-expiry@1",
            "actor_gameplay.survival_domain",
            ("gameplay:survival:{actor_ref}",),
            (
                "gameplay.survival.state_applied",
                "gameplay.survival.obligation_opened",
                "gameplay.survival.state_expired",
                "gameplay.survival.obligation_settled",
                "gameplay.survival.state_dispelled",
                "gameplay.survival.state_transformed",
                "gameplay.survival.obligation_cancelled",
                "gameplay.survival.obligation_retry_scheduled",
                "gameplay.survival.state_compensated",
                "gameplay.survival.obligation_compensated",
            ),
            "project",
        ),
    ]
    assert all(contract.contract_ref != "inf:state-lifecycle@1" for contract in lifecycle_contracts)


def test_require_operation_accepts_the_exact_survival_lifecycle_row() -> None:
    contract = GovernedAuthorityContractCatalog.require_operation(
        contract_ref="inf:survival-state-expiry@1",
        contract_kind="lifecycle",
        owner_ref="actor_gameplay.survival_domain",
        stream_ids=("gameplay:survival:character:ava",),
        event_types=("gameplay.survival.state_applied", "gameplay.survival.obligation_opened"),
        projection_scope="project",
    )

    assert contract.contract_ref == "inf:survival-state-expiry@1"


def test_require_operation_rejects_the_survival_row_when_owner_is_wrong() -> None:
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_owner_mismatch"):
        GovernedAuthorityContractCatalog.require_operation(
            contract_ref="inf:survival-state-expiry@1",
            contract_kind="lifecycle",
            owner_ref="authority:ecology",
            stream_ids=("gameplay:survival:character:ava",),
            event_types=("gameplay.survival.state_applied",),
            projection_scope="project",
        )


def test_require_operation_rejects_the_survival_row_when_stream_is_wrong() -> None:
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_stream_mismatch"):
        GovernedAuthorityContractCatalog.require_operation(
            contract_ref="inf:survival-state-expiry@1",
            contract_kind="lifecycle",
            owner_ref="actor_gameplay.survival_domain",
            stream_ids=("gameplay:ecology:character:ava",),
            event_types=("gameplay.survival.state_applied",),
            projection_scope="project",
        )


def test_require_operation_rejects_the_survival_row_when_event_is_wrong() -> None:
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_event_mismatch"):
        GovernedAuthorityContractCatalog.require_operation(
            contract_ref="inf:survival-state-expiry@1",
            contract_kind="lifecycle",
            owner_ref="actor_gameplay.survival_domain",
            stream_ids=("gameplay:survival:character:ava",),
            event_types=("gameplay.survival.unknown_event",),
            projection_scope="project",
        )


def test_require_operation_rejects_the_survival_row_when_scope_is_wrong() -> None:
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_owner_mismatch"):
        GovernedAuthorityContractCatalog.require_operation(
            contract_ref="inf:survival-state-expiry@1",
            contract_kind="lifecycle",
            owner_ref="actor_gameplay.survival_domain",
            stream_ids=("gameplay:survival:character:ava",),
            event_types=("gameplay.survival.state_applied",),
            projection_scope="authority_only",
        )


def test_survival_owner_gate_rejects_before_append_and_keeps_the_store_unchanged(monkeypatch) -> None:
    store = GameplayEventStore()

    def reject_contract(**_kwargs):
        raise GovernedAuthorityContractError("governed_authority_contract_event_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_contract)
    before = len(store.read_events())
    result = SurvivalAuthority(store=store).apply_effect_state(
        command=_survival_command(),
        application=_survival_application(),
        resistance=_survival_resistance(),
        definition=_survival_state(),
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "governed_authority_contract_event_mismatch"
    assert len(store.read_events()) == before


def test_construction_owner_gate_rejects_before_append_and_keeps_the_store_unchanged(monkeypatch) -> None:
    store = GameplayEventStore()
    _seed_construction_facility(store)

    def reject_contract(**_kwargs):
        raise GovernedAuthorityContractError("governed_authority_contract_event_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_contract)
    before = len(store.read_events())
    result = ConstructionProductionAuthority(store=store).apply_maintenance_state(
        command_id="command:construction-maintenance:catalog",
        idempotency_key="construction-maintenance:catalog",
        facility_ref="facility:bakery:1",
        expected_revision=1,
        causation_id="cause:construction-maintenance:catalog",
        correlation_id="corr:construction-maintenance:catalog",
        source_ref="semantic_registry",
        submitted_at="semantic-authority",
        pinned_revisions={"semantic": 1},
        semantic_snapshot_digest="digest:construction-maintenance:catalog",
        application=EffectApplication(
            effect_ref="effect:maintenance_required",
            target_component_ref="facility:bakery:1",
            magnitude=120,
            stack_key="maintenance",
            expires_at_tick=None,
            causal_chain_id="chain:construction-maintenance:catalog",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:maintenance_required",
            source_ref="facility:bakery:1",
            modifier_basis_points=2_500,
            revision=3,
        ),
        definition=StateDefinition(
            state_ref="state:maintenance_due",
            stack_policy="replace",
            stack_limit=1,
            expiry_policy="none",
        ),
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "governed_authority_contract_event_mismatch"
    assert len(store.read_events()) == before
