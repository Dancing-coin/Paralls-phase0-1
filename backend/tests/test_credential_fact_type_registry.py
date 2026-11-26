from copy import deepcopy

import pytest

from app.gameplay.fact_type_registry import FactTypeRegistry, RegistrationRejected

FACT = "fact:credential:*:link"
MACHINE = "machine_def/credential_link@1"


def declarations():
    return dict(
        facts={FACT: dict(owner_ref="Credential", primitive="machine", identity="entity_ref",
                          visibility={"class": "private"}, state_set_ref=MACHINE)},
        machines={MACHINE: dict(states=["absent", "issued", "revoked", "superseded"],
            terminal_states=["revoked", "superseded"], transitions=[["absent", "issued"], ["issued", "revoked"], ["issued", "superseded"]])},
        owners=["Credential"], resolve_order={"before": [], "unrelated": [FACT]}, models={}, handlers={},
    )


def test_machine_topology_and_terminal_invariant():
    data = declarations()
    registry = FactTypeRegistry.compile(**data)
    assert registry.facts[FACT].resolution_order == 10
    assert registry.machines[MACHINE]["terminal_states"] == ("revoked", "superseded")
    data["machines"][MACHINE]["transitions"].append(["revoked", "issued"])
    with pytest.raises(RegistrationRejected, match="facttype_machine_invalid"):
        FactTypeRegistry.compile(**data)


def test_topology_uses_stable_ids_and_dense_order_and_rejects_cycles():
    data = declarations()
    second = "fact:credential:*:attestation"
    third = "fact:credential:*:review"
    data["facts"] = {third: deepcopy(data["facts"][FACT]), FACT: data["facts"][FACT], second: deepcopy(data["facts"][FACT])}
    data["resolve_order"] = {"before": [[third, second]], "unrelated": [FACT]}
    first = FactTypeRegistry.compile(**data)
    data["facts"] = dict(reversed(list(data["facts"].items())))
    assert list(FactTypeRegistry.compile(**data).facts) == list(first.facts) == [FACT, third, second]
    assert [f.resolution_order for f in first.facts.values()] == [10, 11, 12]
    data["resolve_order"]["before"].append([second, third])
    with pytest.raises(RegistrationRejected, match="facttype_resolution_order_cycle"):
        FactTypeRegistry.compile(**data)


def test_unrelated_fact_types_follow_owner_order_with_stable_fact_id_tiebreak():
    data = declarations()
    ownership = "fact:ownership:*:title"
    facility_alpha = "fact:facility:*:alpha-gate"
    facility_omega = "fact:facility:*:omega-gate"
    ownership_fact = deepcopy(data["facts"][FACT])
    facility_fact = deepcopy(data["facts"][FACT])
    ownership_fact["owner_ref"] = "Ownership"
    facility_fact["owner_ref"] = "Production"
    data["facts"].update({
        facility_omega: deepcopy(facility_fact),
        ownership: ownership_fact,
        facility_alpha: facility_fact,
    })
    data["owners"].extend(["Ownership", "Production"])
    data["resolve_order"]["unrelated"] = list(data["facts"])

    registry = FactTypeRegistry.compile(**data)

    assert list(registry.facts) == [FACT, ownership, facility_alpha, facility_omega]
    orders = [fact.resolution_order for fact in registry.facts.values()]
    assert orders == [10, 11, 12, 13]
    assert len(orders) == len(set(orders))
    assert orders == list(range(10, 10 + len(orders)))


def test_code_and_data_models_share_registration_and_evaluation():
    data = declarations()
    def condition(inputs, params):
        return inputs["threshold"] >= params["minimum"]
    common = dict(owner_ref="Credential", reads=["threshold"], writes_fact_types=[FACT],
        input_schema="threshold@1", output_schema="condition@1", params={"minimum": 2},
        determinism_policy=dict(numeric_precision="fixed_point", rounding="floor", iteration_order="resolution_order", random="none"))
    data["models"] = {"code@1": dict(common, implementation="code"), "data@1": dict(common, implementation="data", evaluator_ref="compare@1")}
    data["handlers"] = {"code@1": condition, "compare@1": condition}
    registry = FactTypeRegistry.compile(**data)
    assert set(registry.models) == {"code@1", "data@1"}
    assert registry.evaluate("code@1", {"threshold": 2}) is True
    assert registry.evaluate("data@1", {"threshold": 1}) is False


@pytest.mark.parametrize(("primitive", "fields"), [
    pytest.param("holdings", {}, id="holdings"),
    pytest.param("bond", {"bond_types": ["title"]}, id="bond"),
    pytest.param("process", {"process_kind": "temporal"}, id="process"),
    pytest.param("place", {"place_kind": "location"}, id="place"),
])
def test_registry_accepts_registered_non_machine_primitives(primitive, fields):
    data = declarations()
    fact = data["facts"][FACT]
    fact["primitive"] = primitive
    fact.pop("state_set_ref")
    fact.update(fields)

    registry = FactTypeRegistry.compile(**data)

    assert registry.facts[FACT].primitive == primitive


def test_registry_rejects_state_set_on_non_machine_primitive():
    data = declarations()
    data["facts"][FACT]["primitive"] = "bond"

    with pytest.raises(RegistrationRejected) as error:
        FactTypeRegistry.compile(**data)

    matching = [
        violation for violation in error.value.violations
        if violation.code == "facttype_field_primitive_invalid"
    ]
    assert [violation.target for violation in matching] == [FACT]
