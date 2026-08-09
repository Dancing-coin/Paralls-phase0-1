from __future__ import annotations

import pytest


def test_ownership_contract_debt_sample_requires_existing_character_and_fixed_terms() -> None:
    from app.gameplay.ownership_contract_debt_sample import OwnershipContractDebtSample

    sample = OwnershipContractDebtSample(applicant_ref="character:char_a", collateral_ref="ownership:right:1", principal=100, term_ticks=10)
    assert sample.contract_ref.startswith("contract:")
    assert sample.debt_obligation_ref.startswith("debt:")
    with pytest.raises(ValueError, match="character_record_required"):
        OwnershipContractDebtSample(applicant_ref="npc:synthetic", collateral_ref="ownership:right:1", principal=100, term_ticks=10)
    with pytest.raises(ValueError, match="fixed_terms_required"):
        OwnershipContractDebtSample(applicant_ref="character:char_a", collateral_ref="ownership:right:1", principal=100, term_ticks=0)


def test_ownership_contract_debt_sample_builds_a_replayable_command() -> None:
    from app.gameplay.event_store import GameplayEventStore
    from app.gameplay.ownership_contract_debt_sample import OwnershipContractDebtSample
    from app.gameplay.settlement_plan import SettlementPlan

    sample = OwnershipContractDebtSample(
        applicant_ref="character:char_a",
        collateral_ref="ownership:right:1",
        principal=100,
        term_ticks=10,
    )
    command = sample.to_command(custody_ref="ownership:right:1", permission_scope="character:char_a")
    result = GameplayEventStore().append_batch(SettlementPlan.from_command_envelope(command).to_atomic_event_batch())
    assert result.committed is True


def test_ownership_contract_debt_sample_composes_existing_ownership_and_debt_authorities() -> None:
    from app.gameplay.event_store import GameplayEventStore
    from app.gameplay.ownership_contract_debt_sample import OwnershipContractDebtSample

    store = GameplayEventStore()
    result = OwnershipContractDebtSample(
        applicant_ref="character:char_a",
        collateral_ref="ownership:right:1",
        principal=100,
        term_ticks=10,
    ).settle_authorities(store=store, custody_ref="ownership:right:1", permission_scope="character:char_a")

    assert result["receipt"].committed is True
    event_types = [event.event_type for event in store.read_events()]
    assert "gameplay.ownership.right_granted" in event_types
    assert "gameplay.contract.simple_debt_created" in event_types
    assert "gameplay.debt.claim_issued" in event_types
