from __future__ import annotations

import pytest

from app.gameplay.semantic_registry import SemanticRegistry, SemanticRegistryError


def test_closed_state_owner_contract_matrix_materializes_all_admitted_rows() -> None:
    contracts = SemanticRegistry.closed_state_owner_contracts()

    assert [(contract.effect_ref, contract.state_ref, contract.owner_ref) for contract in contracts] == [
        ("effect:cold_exposure", "state:cold", "actor_gameplay.survival_domain"),
        ("effect:dehydration_exposure", "state:dehydrated", "actor_gameplay.survival_domain"),
        ("effect:drought", "state:drought@1", "authority:ecology"),
        ("effect:fatigue_exposure", "state:fatigued", "actor_gameplay.survival_domain"),
        ("effect:frost", "state:frosted@1", "authority:ecology"),
        ("effect:heat_exposure", "state:overheated", "actor_gameplay.survival_domain"),
        ("effect:maintenance_required", "state:maintenance_due", "actor_gameplay.construction_production_domain"),
    ]


@pytest.mark.parametrize(
    ("effect_ref", "state_ref"),
    [
        ("effect:foreign", "state:cold"),
        ("effect:frost", "state:blighted@1"),
        ("effect:maintenance_required", "state:frosted@1"),
    ],
)
def test_closed_state_owner_contract_matrix_rejects_unregistered_pairs(effect_ref: str, state_ref: str) -> None:
    with pytest.raises(SemanticRegistryError, match="semantic_state_owner_contract_unknown"):
        SemanticRegistry.require_closed_state_owner_contract(effect_ref=effect_ref, state_ref=state_ref)


def test_closed_state_owner_contract_matrix_fixes_ecology_event_family_and_privacy() -> None:
    contract = SemanticRegistry.require_closed_state_owner_contract(
        effect_ref="effect:frost",
        state_ref="state:frosted@1",
    )

    assert contract.stream_pattern == "gameplay:ecology:{region_ref}"
    assert contract.apply_event_type == "gameplay.ecology.crop_state_applied"
    assert contract.opened_event_type == "gameplay.ecology.crop_state_obligation_opened"
    assert contract.settled_event_type == "gameplay.ecology.crop_state_obligation_settled"
    assert contract.projection_scope == "project"


def test_closed_state_owner_contract_matrix_fixes_ecology_drought_event_family_and_privacy() -> None:
    drought = SemanticRegistry.require_closed_state_owner_contract(
        effect_ref="effect:drought",
        state_ref="state:drought@1",
    )

    assert drought.stream_pattern == "gameplay:ecology:{region_ref}"
    assert drought.apply_event_type == "gameplay.ecology.drought_state_applied"
    assert drought.opened_event_type == "gameplay.ecology.drought_state_obligation_opened"
    assert drought.settled_event_type == "gameplay.ecology.drought_state_obligation_settled"
    assert drought.projection_scope == "project"
