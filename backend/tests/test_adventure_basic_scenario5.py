from __future__ import annotations

import pytest

from app.gameplay.adventure_basic_reference import (
    AdventureBasicScenario5,
    AdventureBasicScenarioError,
)


def test_scenario5_gift_debt_and_typed_contract_lifecycles_remain_independent_and_atomic() -> None:
    scenario = AdventureBasicScenario5.create()

    gifted = scenario.gift_archive_relic()
    assert gifted.committed
    assert [event.event_type for event in scenario.store.read_transactions()[-1].events] == [
        "gameplay.inventory.item_transferred_out",
        "gameplay.inventory.item_transferred_in",
        "gameplay.ownership.right_transferred",
        "gameplay.commerce.gift_settled",
    ]
    assert scenario.recipient_inventory().locations[scenario.gift_item_id] == scenario.recipient_backpack_id
    assert scenario.ownership().rights[scenario.gift_right_id].holder_ref == scenario.recipient_ref
    assert scenario.gift_archive_relic().idempotency_status == "duplicate_replayed"

    issued = scenario.issue_archive_debt()
    assert issued.committed
    assert [event.event_type for event in scenario.store.read_transactions()[-1].events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.contract.simple_debt_created",
        "gameplay.debt.claim_issued",
        "gameplay.commerce.debt_issued_settled",
    ]
    repaid = scenario.repay_archive_debt(scenario.debt_principal)
    assert repaid.committed
    assert scenario.debt().claims[scenario.debt_id].status == "satisfied"
    assert scenario.debt().contracts[scenario.debt_contract_id].status == "fulfilled"

    assert scenario.create_service_contract().committed
    assert scenario.discard_contract_document().committed
    assert scenario.inventory().locations[scenario.contract_document_item_id] == scenario.discarded_document_container_id
    completed = scenario.complete_service_contract()
    assert completed.committed
    assert scenario.contracts().contracts[scenario.service_contract_id].status == "fulfilled"
    assert scenario.contracts().contracts[scenario.service_contract_id].completion_evidence_ref == scenario.service_evidence_ref


def test_scenario5_structured_failures_leave_no_partial_gift_debt_or_contract_mutation() -> None:
    scenario = AdventureBasicScenario5.create()
    assert scenario.fill_recipient_backpack().committed
    before_gift = scenario.store.read_events()
    with pytest.raises(AdventureBasicScenarioError, match="inventory_capacity_exceeded"):
        scenario.gift_archive_relic()
    assert scenario.store.read_events() == before_gift
    assert scenario.ownership().rights[scenario.gift_right_id].holder_ref == scenario.player_ref

    assert scenario.issue_archive_debt().committed
    before_payment = scenario.store.read_events()
    with pytest.raises(AdventureBasicScenarioError, match="economy_payment_exceeds_outstanding"):
        scenario.repay_archive_debt(scenario.debt_principal + 1)
    assert scenario.store.read_events() == before_payment
    assert scenario.debt().claims[scenario.debt_id].outstanding_amount == scenario.debt_principal

    assert scenario.create_service_contract().committed
    assert scenario.discard_contract_document().committed
    before_contract = scenario.store.read_events()
    with pytest.raises(AdventureBasicScenarioError, match="contract_completion_evidence_invalid"):
        scenario.complete_service_contract(completion_evidence_kind="wrong_evidence")
    assert scenario.store.read_events() == before_contract
    assert scenario.contracts().contracts[scenario.service_contract_id].status == "active"
