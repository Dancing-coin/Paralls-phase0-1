import pytest

from app.gameplay.fact_type_registry import FactTypeRegistry, RegistrationRejected
from app.gameplay.rule_pack_validator import load_pack


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


def test_holdings_sum_fact_type_loads_from_rule_pack(tmp_path):
    pack = tmp_path / "holdings-pack"
    (pack / "fact_types").mkdir(parents=True)
    (pack / "aggregation_models").mkdir()
    (pack / "pack.yaml").write_text(
        """pack_id: "holdings_reference"
pack_version: "1.0.0"
schema_version: 1
parent_pack: null
owners: ["Inventory"]
contents:
  fact_types: ["holdings"]
  aggregation_models: ["quantity"]
resolve_order:
  before: []
  unrelated: ["fact:inventory:store-01:holdings"]
""",
        encoding="utf-8",
    )
    (pack / "fact_types" / "holdings.yaml").write_text(
        """fact:inventory:store-01:holdings:
  owner_ref: "Inventory"
  primitive: "holdings"
  event_schema_ref: "holdings@v1"
  visibility:
    class: "authority_only"
""",
        encoding="utf-8",
    )
    (pack / "aggregation_models" / "quantity.yaml").write_text(
        """quantity:
  mode: "sum"
""",
        encoding="utf-8",
    )

    loaded = load_pack(pack, handlers={})

    assert loaded.registry.facts[FACT].primitive == "holdings"
    assert loaded.aggregation_models["quantity"]["mode"] == "sum"
