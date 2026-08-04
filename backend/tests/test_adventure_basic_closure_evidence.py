from __future__ import annotations

import pytest

from app.gameplay import adventure_basic_closure
from app.gameplay.adventure_basic_closure import capture_adventure_basic_closure
from app.gameplay.adventure_basic_reference import (
    AdventureBasicScenario1,
    AdventureBasicScenario2,
    AdventureBasicScenario3,
    AdventureBasicScenario4,
    AdventureBasicScenario5,
)
from app.gameplay.replay import GameplayProjectionReplay


def _scenario1() -> AdventureBasicScenario1:
    scenario = AdventureBasicScenario1.create()
    assert scenario.purchase_sword().committed
    assert scenario.equip_sword().committed
    return scenario


def _scenario2() -> AdventureBasicScenario2:
    scenario = AdventureBasicScenario2.create()
    assert scenario.purchase_sword().committed
    assert scenario.equip_sword().committed
    assert scenario.swing_sword().accepted
    return scenario


def _scenario3() -> AdventureBasicScenario3:
    scenario = AdventureBasicScenario3.create()
    assert scenario.equip_storage_ring().committed
    assert scenario.move_to_storage_ring(scenario.cargo_item_id).committed
    return scenario


def _scenario4() -> AdventureBasicScenario4:
    scenario = AdventureBasicScenario4.create()
    assert scenario.purchase_land().committed
    assert scenario.issue_deed_credential().committed
    assert scenario.transfer_land_right().committed
    return scenario


def _scenario5() -> AdventureBasicScenario5:
    scenario = AdventureBasicScenario5.create()
    assert scenario.gift_archive_relic().committed
    assert scenario.issue_archive_debt().committed
    assert scenario.repay_archive_debt(scenario.debt_principal).committed
    assert scenario.create_service_contract().committed
    assert scenario.discard_contract_document().committed
    assert scenario.complete_service_contract().committed
    return scenario


@pytest.mark.parametrize(
    ("scenario_id", "factory"),
    [
        ("scenario-1", _scenario1),
        ("scenario-2", _scenario2),
        ("scenario-3", _scenario3),
        ("scenario-4", _scenario4),
        ("scenario-5", _scenario5),
    ],
)
def test_each_adventure_basic_scenario_rebuilds_a_facade_with_canonical_replay_evidence(
    scenario_id: str,
    factory,
) -> None:
    evidence = capture_adventure_basic_closure(scenario_id=scenario_id, scenario=factory())

    assert evidence.scenario_id == scenario_id
    assert evidence.source_revision_vector
    assert evidence.result_metadata["transaction_count"] >= 1
    assert evidence.result_metadata["all_transactions_atomic"] is True
    assert evidence.explanation_trace
    assert all(entry["source_ref"].startswith("event:") for entry in evidence.explanation_trace)
    assert evidence.online_facade_hash == evidence.full_replay_facade_hash
    assert evidence.online_facade_hash == evidence.checkpoint_tail_facade_hash
    assert evidence.online_replay_hash == evidence.full_replay_hash
    assert evidence.online_replay_hash == evidence.checkpoint_tail_replay_hash
    assert evidence.online_facade == evidence.full_replay_facade
    assert evidence.online_facade == evidence.checkpoint_tail_facade


def test_duplicate_authority_command_keeps_atomic_transaction_evidence_stable() -> None:
    scenario = AdventureBasicScenario1.create()
    assert scenario.purchase_sword().committed
    transaction_count = len(scenario.store.read_transactions())

    duplicate = scenario.purchase_sword()
    evidence = capture_adventure_basic_closure(scenario_id="scenario-1", scenario=scenario)

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(scenario.store.read_transactions()) == transaction_count
    assert evidence.result_metadata["transaction_count"] == transaction_count
    assert evidence.result_metadata["idempotency_replay_safe"] is True


def test_checkpoint_tail_facade_records_the_checkpoint_provenance_event_sequence() -> None:
    scenario = _scenario1()
    events = tuple(scenario.store.read_events())
    checkpoint_index = max(1, len(events) // 2)
    replay = GameplayProjectionReplay(projector_id="adventure-basic:scenario-1", projector_version="v1")
    checkpoint = replay.create_checkpoint(list(events[:checkpoint_index]))

    reconstructed = adventure_basic_closure._reconstruct_checkpoint_tail_events(
        checkpoint=checkpoint,
        tail_events=events[checkpoint_index:],
        event_lookup={event.event_id: event for event in events},
    )
    evidence = capture_adventure_basic_closure(scenario_id="scenario-1", scenario=scenario)

    assert [event.event_id for event in reconstructed] == [event.event_id for event in events]
    assert evidence.checkpoint_tail_event_ids == tuple(event.event_id for event in reconstructed)
