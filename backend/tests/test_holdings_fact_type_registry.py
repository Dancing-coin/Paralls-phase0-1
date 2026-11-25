import pytest

from app.gameplay.fact_type_registry import FactTypeRegistry, RegistrationRejected


FACT = "fact:inventory:store-01:holdings"


def declarations():
    return dict(
        facts={FACT: {
            "owner_ref": "Inventory",
            "primitive": "holdings",
            "visibility": {"class": "authority_only"},
        }},
        machines={}, owners=["Inventory"],
        resolve_order={"before": [], "unrelated": [FACT]},
        models={}, handlers={},
    )


def test_holdings_fact_type_compiles_without_machine_or_pool_definition():
    registry = FactTypeRegistry.compile(**declarations())

    assert registry.facts[FACT].primitive == "holdings"
    assert registry.facts[FACT].state_set_ref is None


def test_holdings_fact_type_rejects_machine_state_set_reference():
    data = declarations()
    data["facts"][FACT]["state_set_ref"] = "machine_def:inventory@1"

    with pytest.raises(RegistrationRejected, match="facttype_schema_unknown"):
        FactTypeRegistry.compile(**data)
