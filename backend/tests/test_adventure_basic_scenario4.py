from __future__ import annotations

import pytest

from app.gameplay.adventure_basic_reference import (
    AdventureBasicScenario4,
    AdventureBasicScenarioError,
)


def _purchased_scenario() -> AdventureBasicScenario4:
    scenario = AdventureBasicScenario4.create()
    assert scenario.purchase_land().committed
    return scenario


def test_scenario4_purchase_atomically_transfers_land_deed_and_right_then_dropping_the_deed_does_not_transfer_title() -> None:
    scenario = _purchased_scenario()
    purchase_events = scenario.store.read_transactions()[-1].events

    assert [event.event_type for event in purchase_events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.inventory.item_transferred_out",
        "gameplay.inventory.item_transferred_in",
        "gameplay.ownership.right_transferred",
        "gameplay.commerce.fixed_offer_consumed",
        "gameplay.commerce.purchase_settled",
    ]
    assert scenario.inventory().locations[scenario.land_deed_item_id] == scenario.player_backpack_id
    assert scenario.ownership().rights[scenario.land_right_id].holder_ref == scenario.player_ref

    drop = scenario.drop_land_deed()

    assert drop.committed
    assert scenario.inventory().locations[scenario.land_deed_item_id] == scenario.world_deed_container_id
    assert scenario.ownership().rights[scenario.land_right_id].holder_ref == scenario.player_ref


def test_scenario4_rejects_title_transfer_without_present_credential_then_transfers_only_by_the_explicit_authority_command() -> None:
    scenario = _purchased_scenario()
    assert scenario.issue_deed_credential().committed
    assert scenario.drop_land_deed().committed
    before_rejected_transfer = scenario.store.read_events()

    with pytest.raises(AdventureBasicScenarioError, match="land_right_credential_required"):
        scenario.transfer_land_right()

    assert scenario.store.read_events() == before_rejected_transfer
    assert scenario.ownership().rights[scenario.land_right_id].holder_ref == scenario.player_ref

    assert scenario.retrieve_land_deed().committed
    transfer = scenario.transfer_land_right()

    assert transfer.committed
    assert scenario.ownership().rights[scenario.land_right_id].holder_ref == scenario.recipient_ref
    assert scenario.inventory().locations[scenario.land_deed_item_id] == scenario.player_backpack_id


def test_scenario4_rejects_wrong_holder_or_stale_right_revision_without_partial_mutation() -> None:
    scenario = _purchased_scenario()
    assert scenario.issue_deed_credential().committed
    before = scenario.store.read_events()

    with pytest.raises(AdventureBasicScenarioError, match="land_right_revision_conflict"):
        scenario.transfer_land_right(expected_ownership_revision=0)

    assert scenario.store.read_events() == before
    assert scenario.ownership().rights[scenario.land_right_id].holder_ref == scenario.player_ref


def test_scenario4_replays_an_identical_land_right_transfer_without_a_second_title_mutation() -> None:
    scenario = _purchased_scenario()
    assert scenario.issue_deed_credential().committed

    first = scenario.transfer_land_right()
    event_count_after_first = len(scenario.store.read_events())
    replayed = scenario.transfer_land_right()

    assert first.committed
    assert replayed.committed
    assert replayed.idempotency_status == "duplicate_replayed"
    assert len(scenario.store.read_events()) == event_count_after_first
    assert scenario.ownership().rights[scenario.land_right_id].holder_ref == scenario.recipient_ref
