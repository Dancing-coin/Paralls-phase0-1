from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog


def test_inventory_platform_catalog_has_exact_owner_bound_core_rows():
    refs = (
        "inf:inventory-item-definition-instance-lot@1",
        "inf:inventory-container-graph@1",
        "inf:inventory-custody-reservation@1",
        "inf:inventory-condition-expiry@1",
        "inf:inventory-transport-delivery@1",
    )
    for ref in refs:
        contract = GovernedAuthorityContractCatalog.require(contract_ref=ref)
        assert contract.owner_ref == "actor_gameplay.inventory_domain"
        assert contract.receipt_reader_ref == "GameplayEventStore.append_batch"
        assert contract.projection_scope == "project"
