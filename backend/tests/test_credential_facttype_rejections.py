"""Independent rejection witnesses, including an actual undeclared input read."""

import pytest

from app.gameplay.fact_type_registry import (
    FactTypeRegistry, RegistrationRejected, ResolverInputError,
)
from test_credential_fact_type_registry import FACT, declarations


def model(reads):
    return dict(owner_ref="Credential", implementation="code", reads=reads,
        writes_fact_types=[FACT], input_schema="credential_inputs@1",
        output_schema="condition@1", params={}, determinism_policy=dict(
            numeric_precision="fixed_point", rounding="floor",
            iteration_order="resolution_order", random="none"))


def test_facttype_visibility_missing():
    data = declarations()
    del data["facts"][FACT]["visibility"]
    with pytest.raises(RegistrationRejected, match="facttype_visibility_missing"):
        FactTypeRegistry.compile(**data)


def test_facttype_resolution_order_missing():
    data = declarations()
    data["resolve_order"] = {"before": [], "unrelated": []}
    with pytest.raises(RegistrationRejected, match="facttype_resolution_order_missing"):
        FactTypeRegistry.compile(**data)


def test_facttype_owner_unknown():
    data = declarations()
    data["facts"][FACT]["owner_ref"] = "UnregisteredOwner"
    with pytest.raises(RegistrationRejected, match="facttype_owner_unknown"):
        FactTypeRegistry.compile(**data)


def test_direct_compile_cannot_register_an_unknown_owner():
    data = declarations()
    data["owners"] = ["Credential", "SelfRegisteredOwner"]

    with pytest.raises(RegistrationRejected) as error:
        FactTypeRegistry.compile(**data)

    assert "facttype_owner_unknown" in {violation.code for violation in error.value.violations}


def test_resolver_owner_mismatch_in_inner_layer():
    data = declarations()
    data["owners"].append("Inventory")
    data["models"] = {"credential@1": model([])}
    data["models"]["credential@1"]["layers"] = [
        {"owner_ref": "Inventory", "writes_fact_types": [FACT]}]
    data["handlers"] = {"credential@1": lambda inputs, params: True}
    with pytest.raises(RegistrationRejected, match="resolver_owner_mismatch"):
        FactTypeRegistry.compile(**data)


def test_resolver_input_undeclared_during_actual_evaluation():
    data = declarations()
    accessed = []

    def reads_inventory(inputs, params):
        accessed.append("executed")
        return inputs["inventory.actor@1"]

    data["models"] = {"credential@1": model(["ownership.rights@1"])}
    data["handlers"] = {"credential@1": reads_inventory}
    registry = FactTypeRegistry.compile(**data)
    with pytest.raises(ResolverInputError, match="^resolver_input_undeclared$"):
        registry.evaluate("credential@1", {
            "ownership.rights@1": {}, "inventory.actor@1": {"item": "present"}})
    assert accessed == ["executed"]


def test_resolver_layer_output_must_be_in_model_write_set():
    data = declarations()
    model_spec = model([])
    model_spec["writes_fact_types"] = []
    model_spec["layers"] = [
        {"owner_ref": "Credential", "writes_fact_types": [FACT]},
    ]
    data["models"] = {"credential@1": model_spec}
    data["handlers"] = {"credential@1": lambda inputs, params: True}

    with pytest.raises(RegistrationRejected) as error:
        FactTypeRegistry.compile(**data)

    assert "resolver_writes_undeclared" in {
        violation.code for violation in error.value.violations
    }


def test_resolver_rejects_unfixed_randomness_policy():
    data = declarations()
    model_spec = model([])
    model_spec["determinism_policy"]["random"] = "seeded"
    data["models"] = {"credential@1": model_spec}
    data["handlers"] = {"credential@1": lambda inputs, params: True}

    with pytest.raises(RegistrationRejected, match="resolver_missing_determinism"):
        FactTypeRegistry.compile(**data)


def test_resolver_accepts_float64_numeric_precision():
    data = declarations()
    model_spec = model([])
    model_spec["determinism_policy"]["numeric_precision"] = "float64"
    data["models"] = {"credential@1": model_spec}
    data["handlers"] = {"credential@1": lambda inputs, params: True}

    registry = FactTypeRegistry.compile(**data)

    assert registry.models["credential@1"].determinism_policy["numeric_precision"] == "float64"


@pytest.mark.parametrize("seed_source", ["world_tick", "command_id"])
def test_resolver_accepts_seeded_randomness_with_declared_source(seed_source):
    data = declarations()
    model_spec = model([])
    model_spec["determinism_policy"].update(random="seeded", seed_source=seed_source)
    data["models"] = {"credential@1": model_spec}
    data["handlers"] = {"credential@1": lambda inputs, params: True}

    registry = FactTypeRegistry.compile(**data)

    policy = registry.models["credential@1"].determinism_policy
    assert policy["random"] == "seeded"
    assert policy["seed_source"] == seed_source


def test_resolver_rejects_seeded_randomness_with_unknown_source():
    data = declarations()
    model_spec = model([])
    model_spec["determinism_policy"].update(random="seeded", seed_source="system_time")
    data["models"] = {"credential@1": model_spec}
    data["handlers"] = {"credential@1": lambda inputs, params: True}

    with pytest.raises(RegistrationRejected, match="resolver_missing_determinism"):
        FactTypeRegistry.compile(**data)
