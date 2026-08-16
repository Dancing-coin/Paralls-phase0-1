from __future__ import annotations

import pytest

from app.gameplay.semantic_registry import SemanticRegistry, SemanticRegistryError


def test_finite_lifecycle_contract_reader_materializes_only_existing_owner_rows() -> None:
    contracts = SemanticRegistry.closed_lifecycle_owner_contracts()

    assert [
        (contract.effect_ref, contract.state_ref, contract.owner_ref, contract.stream_pattern)
        for contract in contracts
    ] == [
        ("effect:cold_exposure", "state:cold", "actor_gameplay.survival_domain", "gameplay:survival:{actor_ref}"),
        ("effect:dehydration_exposure", "state:dehydrated", "actor_gameplay.survival_domain", "gameplay:survival:{actor_ref}"),
        ("effect:drought", "state:drought@1", "authority:ecology", "gameplay:ecology:{region_ref}"),
        ("effect:fatigue_exposure", "state:fatigued", "actor_gameplay.survival_domain", "gameplay:survival:{actor_ref}"),
        ("effect:frost", "state:frosted@1", "authority:ecology", "gameplay:ecology:{region_ref}"),
        ("effect:heat_exposure", "state:overheated", "actor_gameplay.survival_domain", "gameplay:survival:{actor_ref}"),
        (
            "effect:maintenance_required",
            "state:maintenance_due",
            "actor_gameplay.construction_production_domain",
            "gameplay:construction_production:{facility_ref}",
        ),
        ("effect:wage_accrual_due", None, "actor_gameplay.econ1_economy_domain", "gameplay:economy:wage:{worker_ref}"),
    ]


@pytest.mark.parametrize(
    ("effect_ref", "state_ref"),
    [
        ("effect:foreign", None),
        ("effect:frost", "state:blighted@1"),
        ("effect:wage_accrual_due", "state:wage"),
    ],
)
def test_finite_lifecycle_contract_reader_rejects_unknown_rows(effect_ref: str, state_ref: str | None) -> None:
    with pytest.raises(SemanticRegistryError, match="semantic_lifecycle_owner_contract_unknown"):
        SemanticRegistry.require_closed_lifecycle_owner_contract(effect_ref=effect_ref, state_ref=state_ref)


def test_finite_lifecycle_contract_reader_fixes_owner_actions_and_terminal_event_families() -> None:
    survival = SemanticRegistry.require_closed_lifecycle_owner_contract(
        effect_ref="effect:cold_exposure",
        state_ref="state:cold",
    )
    construction = SemanticRegistry.require_closed_lifecycle_owner_contract(
        effect_ref="effect:maintenance_required",
        state_ref="state:maintenance_due",
    )
    economy = SemanticRegistry.require_closed_lifecycle_owner_contract(effect_ref="effect:wage_accrual_due")

    assert survival.action_effect_refs == ("effect:state_dispel", "effect:state_transform_recovery")
    assert "gameplay.survival.obligation_retry_scheduled" in survival.event_types
    assert construction.action_effect_refs == ("effect:maintenance_state_dispel",)
    assert "gameplay.construction_production.maintenance_state_obligation_cancelled" in construction.event_types
    assert economy.action_effect_refs == ()
    assert "gameplay.economy.wage_obligation_compensated" in economy.event_types


def test_finite_lifecycle_contract_reader_exposes_fixed_projection_revision_idempotency_and_replay_metadata() -> None:
    ecology = SemanticRegistry.require_closed_lifecycle_owner_contract(
        effect_ref="effect:frost",
        state_ref="state:frosted@1",
    )

    assert ecology.projection_scope == "project"
    assert ecology.outbox_topic == "world.ecology.scoped_projection"
    assert ecology.revision_rule == "expected_stream_head_and_canonical_source"
    assert ecology.idempotency_strategy == "committed_application_digest"
    assert ecology.replay_reader_ref == "EcologyHazardAuthority.crop_state_replay"


def test_finite_lifecycle_contract_reader_exposes_drought_projection_revision_idempotency_and_replay_metadata() -> None:
    drought = SemanticRegistry.require_closed_lifecycle_owner_contract(
        effect_ref="effect:drought",
        state_ref="state:drought@1",
    )

    assert drought.projection_scope == "project"
    assert drought.outbox_topic == "world.ecology.scoped_projection"
    assert drought.revision_rule == "expected_stream_head_and_canonical_source"
    assert drought.idempotency_strategy == "committed_application_digest"
    assert drought.replay_reader_ref == "EcologyHazardAuthority.drought_state_replay"
