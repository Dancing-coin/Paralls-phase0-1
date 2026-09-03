from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog


def test_complete_economy_family_descriptors_are_unique_and_owner_bound():
    rows = [
        descriptor
        for descriptor in GovernedAuthorityContractCatalog.all_descriptors()
        if descriptor.family_ref in {
            "currency_issuance@1",
            "fx_fixing@1",
            "account_ledger@1",
            "hold_obligation@1",
            "quote_order@1",
            "deterministic_clearing@1",
            "commerce_delivery_settlement@1",
            "organization_labor_period@1",
            "tax_regulation@1",
            "credit_collateral@1",
            "insurance_contract@1",
            "security_holding@1",
            "insolvency_resolution@1",
            "regional_macro_close@1",
        }
    ]
    assert len(rows) == 14
    assert len({row.descriptor_ref for row in rows}) == 14
    assert all(row.owner_ref == "actor_gameplay.economy_domain" for row in rows)


def test_economy_catalog_uses_actual_market_and_macro_event_coordinates():
    quote = GovernedAuthorityContractCatalog.require(contract_ref="inf:economy-quote-order@1")
    macro = GovernedAuthorityContractCatalog.require(contract_ref="inf:economy-regional-macro-close@1")
    assert quote.event_types == ("gameplay.economy.market_quote_recorded@1",)
    assert quote.stream_patterns == ("gameplay:economy:market:quote:{subject_ref}",)
    assert quote.projection_scope == "project"
    assert macro.event_types == ("gameplay.economy.regional_macro_period_closed@1",)
    assert macro.stream_patterns == ("gameplay:economy:macro:{subject_ref}",)
