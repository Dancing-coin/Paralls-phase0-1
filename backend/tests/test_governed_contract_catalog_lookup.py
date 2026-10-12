from __future__ import annotations

import pytest

from app.gameplay.governed_contract_catalog import (
    GovernedAuthorityContract,
    GovernedAuthorityContractCatalog,
    GovernedAuthorityContractError,
)


CONTRACT_REF = "inf:branch-work-wage-admission@1"


def test_repeated_lookup_does_not_reconstruct_unrelated_static_contracts(monkeypatch) -> None:
    expected = GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF)
    constructed_refs: list[str] = []
    original_init = GovernedAuthorityContract.__init__

    def record_construction(self, **values) -> None:
        constructed_refs.append(values["contract_ref"])
        original_init(self, **values)

    monkeypatch.setattr(GovernedAuthorityContract, "__init__", record_construction)
    for _ in range(28):
        actual = GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF)
        assert actual == expected
        assert actual is not expected

    assert constructed_refs == [CONTRACT_REF] * 28


def test_static_lookup_returns_independent_model_storage() -> None:
    first = GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF)
    expected = first.model_dump(mode="python")
    first.__dict__["owner_ref"] = "tampered:owner"
    first.__dict__["stream_patterns"] = ("gameplay:tampered",)
    first.__dict__["contract_ref"] = "tampered:contract"
    first.__pydantic_fields_set__.clear()

    second = GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF)
    assert second.model_dump(mode="python") == expected
    assert second.__pydantic_fields_set__ == set(GovernedAuthorityContract.model_fields)


def test_public_contract_catalog_mutation_does_not_change_lookup_or_next_catalog() -> None:
    first = GovernedAuthorityContractCatalog.contracts()
    selected = next(item for item in first if item.contract_ref == CONTRACT_REF)
    expected = selected.model_dump(mode="python")
    selected.__dict__["owner_ref"] = "tampered:owner"
    selected.__dict__["event_types"] = ("gameplay.tampered",)

    looked_up = GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF)
    next_selected = next(
        item for item in GovernedAuthorityContractCatalog.contracts() if item.contract_ref == CONTRACT_REF
    )
    assert looked_up.model_dump(mode="python") == expected
    assert next_selected.model_dump(mode="python") == expected
    assert looked_up is not selected
    assert next_selected is not selected


def test_lookup_observes_subclass_catalog_changes() -> None:
    contract = GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF)
    owner_ref = "owner:first"

    class SpecializedCatalog(GovernedAuthorityContractCatalog):
        @staticmethod
        def contracts() -> tuple[GovernedAuthorityContract, ...]:
            return (contract.model_copy(update={"owner_ref": owner_ref}),)

    assert SpecializedCatalog.require(contract_ref=CONTRACT_REF).owner_ref == "owner:first"
    owner_ref = "owner:second"
    assert SpecializedCatalog.require(contract_ref=CONTRACT_REF).owner_ref == "owner:second"


def test_lookup_observes_replaced_catalog_after_static_lookup(monkeypatch) -> None:
    original = GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF)
    replacement = original.model_copy(update={"owner_ref": "owner:replacement"})
    monkeypatch.setattr(
        GovernedAuthorityContractCatalog, "contracts", staticmethod(lambda: (replacement,))
    )

    assert GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF) is replacement
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_kind_mismatch"):
        GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF, contract_kind="policy")


def test_unknown_lookup_remains_fail_closed() -> None:
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_unknown"):
        GovernedAuthorityContractCatalog.require(contract_ref="inf:unadmitted@1")


@pytest.mark.parametrize("contract_ref", [None, [], {}])
def test_invalid_contract_reference_remains_unknown(contract_ref) -> None:
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_unknown"):
        GovernedAuthorityContractCatalog.require(contract_ref=contract_ref)


def test_lookup_accepts_unhashable_string_subclass() -> None:
    class UnhashableReference(str):
        __hash__ = None

    contract = GovernedAuthorityContractCatalog.require(contract_ref=UnhashableReference(CONTRACT_REF))
    assert contract.contract_ref == CONTRACT_REF


def test_lookup_preserves_linear_equality_for_string_subclass_with_custom_hash() -> None:
    class CustomHashReference(str):
        def __hash__(self) -> int:
            return hash("inf:unrelated-hash@1")

    contract = GovernedAuthorityContractCatalog.require(contract_ref=CustomHashReference(CONTRACT_REF))
    assert contract.contract_ref == CONTRACT_REF


def test_lookup_observes_changed_closed_family_catalog(monkeypatch) -> None:
    original = GovernedAuthorityContractCatalog.require(contract_ref=CONTRACT_REF)
    platform_ref = "inf:runtime-closed-family@1"
    replacement = original.model_copy(update={"contract_ref": platform_ref, "owner_ref": "owner:first"})
    monkeypatch.setattr(
        GovernedAuthorityContractCatalog,
        "closed_family_contracts",
        staticmethod(lambda: (replacement,)),
    )

    assert GovernedAuthorityContractCatalog.require(contract_ref=platform_ref).owner_ref == "owner:first"
    replacement = replacement.model_copy(update={"owner_ref": "owner:second"})
    assert GovernedAuthorityContractCatalog.require(contract_ref=platform_ref).owner_ref == "owner:second"
