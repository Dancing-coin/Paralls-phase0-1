from __future__ import annotations

import pytest

from app.gameplay.semantic_registry import SemanticRegistryError, StateLifecycleAdapterContract, SemanticRegistry


def test_closed_adapter_matrix_exposes_only_existing_semantic_owner_adapters() -> None:
    contracts = SemanticRegistry.closed_state_lifecycle_adapter_contracts()

    assert {(item.effect_ref, item.state_ref) for item in contracts} == {
        ("effect:maintenance_required", "state:maintenance_due"),
        ("effect:cold_exposure", "state:cold"),
        ("effect:drought", "state:drought@1"),
        ("effect:heat_exposure", "state:overheated"),
        ("effect:dehydration_exposure", "state:dehydrated"),
        ("effect:fatigue_exposure", "state:fatigued"),
        ("effect:frost", "state:frosted@1"),
    }
    assert all("apply" in item.operations for item in contracts)
    assert SemanticRegistry.require_closed_state_lifecycle_adapter(
        effect_ref="effect:fatigue_exposure", state_ref="state:fatigued", operation="apply"
    ).adapter_ref == "SemanticSettlementAuthority.settle_closed_survival_state"
    assert SemanticRegistry.require_closed_state_lifecycle_adapter(
        effect_ref="effect:cold_exposure", state_ref="state:cold", operation="dispel"
    ).adapter_ref == "SemanticSettlementAuthority.settle_closed_survival_state"


def test_closed_adapter_matrix_admits_ecology_frost_apply_only() -> None:
    adapter = SemanticRegistry.require_closed_state_lifecycle_adapter(
        effect_ref="effect:frost", state_ref="state:frosted@1", operation="apply"
    )

    assert adapter.owner_ref == "authority:ecology"
    assert adapter.adapter_ref == "SemanticSettlementAuthority.settle_closed_ecology_frost"
    with pytest.raises(SemanticRegistryError, match="semantic_lifecycle_adapter_operation_unregistered"):
        SemanticRegistry.require_closed_state_lifecycle_adapter(
            effect_ref="effect:frost", state_ref="state:frosted@1", operation="expire"
        )


def test_closed_adapter_matrix_admits_ecology_drought_apply_only() -> None:
    drought = SemanticRegistry.require_closed_state_lifecycle_adapter(
        effect_ref="effect:drought", state_ref="state:drought@1", operation="apply"
    )

    assert drought.owner_ref == "authority:ecology"
    assert drought.adapter_ref == "SemanticSettlementAuthority.settle_closed_ecology_drought"
    with pytest.raises(SemanticRegistryError, match="semantic_lifecycle_adapter_operation_unregistered"):
        SemanticRegistry.require_closed_state_lifecycle_adapter(
            effect_ref="effect:drought", state_ref="state:drought@1", operation="expire"
        )


def test_closed_adapter_matrix_rejects_unadmitted_owner_operation() -> None:
    with pytest.raises(SemanticRegistryError, match="semantic_lifecycle_adapter_operation_unregistered"):
        SemanticRegistry.require_closed_state_lifecycle_adapter(
            effect_ref="effect:maintenance_required",
            state_ref="state:maintenance_due",
            operation="transform",
        )
