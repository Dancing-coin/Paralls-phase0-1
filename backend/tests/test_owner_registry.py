import pytest

from app.contracts.owner_registry import OWNER_REGISTRY
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.organization_government_runtime import GovernmentAuthority, OrganizationAuthority
from app.gameplay.survival_runtime import SurvivalAuthority


def test_owner_principals_resolve_from_owner_registry():
    assert ConstructionProductionAuthority._PRINCIPAL == OWNER_REGISTRY.get("construction_production").principal_ref
    assert EconomyAuthority._PRINCIPAL == OWNER_REGISTRY.get("economy").principal_ref
    assert GovernmentAuthority._PRINCIPAL == OWNER_REGISTRY.get("government").principal_ref
    assert OrganizationAuthority._PRINCIPAL == OWNER_REGISTRY.get("organization").principal_ref
    assert SurvivalAuthority._PRINCIPAL == OWNER_REGISTRY.get("survival").principal_ref


def test_owner_registry_rejects_undeclared_owner():
    with pytest.raises(ValueError, match="owner_declaration_unknown:future_owner"):
        OWNER_REGISTRY.get("future_owner")


def test_all_fact_types_have_owner_in_registry():
    from app.models.fact_type import FACT_TYPE_TO_OWNER, FactType

    for fact_type in FactType:
        owner_id = FACT_TYPE_TO_OWNER[fact_type]
        assert OWNER_REGISTRY.get(owner_id).owner_ref == owner_id
