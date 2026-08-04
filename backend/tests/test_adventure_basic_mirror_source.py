from __future__ import annotations

import pytest

from app.gameplay.adventure_basic_reference import (
    AdventureBasicScenario1,
    AdventureBasicScenario2,
    AdventureBasicScenario3,
    AdventureBasicScenario4,
    AdventureBasicScenario5,
)
from app.gameplay.adventure_basic_mirror_source import (
    AdventureBasicMirrorSource,
    AdventureBasicMirrorSourceError,
)


def test_scenario_mirror_source_rebuilds_a_filtered_post_commit_view_without_writing() -> None:
    scenario = AdventureBasicScenario1.create()
    assert scenario.purchase_sword().committed
    assert scenario.equip_sword().committed
    snapshot_before = scenario.store.export_snapshot()

    view = AdventureBasicMirrorSource(
        scenario_id="scenario-1",
        scenario=scenario,
    ).godot_view()

    assert scenario.store.export_snapshot() == snapshot_before
    assert view.actor_ref == scenario.player_ref
    assert view.consumer == "godot"
    assert tuple(view.groups) == ("adventure.basic.scenario-1",)
    envelope = view.groups["adventure.basic.scenario-1"]
    assert envelope.definition_version == "1"
    assert envelope.projection_schema_version == 1
    assert envelope.payload["scenario_id"] == "scenario-1"
    assert envelope.payload["presentation_state"] == "sword_equipped"
    assert envelope.payload["facade_checksum"] == envelope.projection_revision
    assert str(envelope.payload["latest_transaction_id"]).startswith("tx:adventure-basic:")
    assert envelope.payload["source_revision_vector"] == dict(view.source_revision_vector)
    assert "authority_command" not in str(envelope.payload)
    assert "world_truth_claim" not in str(envelope.payload)
    assert "private_mind_state" not in str(envelope.payload)


def test_scenario_one_mirror_state_is_derived_from_committed_facade_progress() -> None:
    scenario = AdventureBasicScenario1.create()
    source = AdventureBasicMirrorSource(scenario_id="scenario-1", scenario=scenario)

    assert source.godot_view().groups["adventure.basic.scenario-1"].payload["presentation_state"] == "sword_offer_available"
    assert scenario.purchase_sword().committed
    assert source.godot_view().groups["adventure.basic.scenario-1"].payload["presentation_state"] == "sword_purchased"
    assert scenario.equip_sword().committed
    assert source.godot_view().groups["adventure.basic.scenario-1"].payload["presentation_state"] == "sword_equipped"


def test_remaining_scenario_mirror_states_change_only_with_their_committed_facades() -> None:
    scenario2 = AdventureBasicScenario2.create()
    scenario2_source = AdventureBasicMirrorSource(scenario_id="scenario-2", scenario=scenario2)
    assert scenario2_source.godot_view().groups["adventure.basic.scenario-2"].payload["presentation_state"] == "sword_action_unavailable"
    assert scenario2.purchase_sword().committed
    assert scenario2.equip_sword().committed
    assert scenario2_source.godot_view().groups["adventure.basic.scenario-2"].payload["presentation_state"] == "sword_action_ready"
    assert scenario2.swing_sword().accepted
    assert scenario2_source.godot_view().groups["adventure.basic.scenario-2"].payload["presentation_state"] == "resource_action_resolved"

    scenario3 = AdventureBasicScenario3.create()
    scenario3_source = AdventureBasicMirrorSource(scenario_id="scenario-3", scenario=scenario3)
    assert scenario3_source.godot_view().groups["adventure.basic.scenario-3"].payload["presentation_state"] == "storage_ring_available"
    assert scenario3.equip_storage_ring().committed
    assert scenario3_source.godot_view().groups["adventure.basic.scenario-3"].payload["presentation_state"] == "storage_ring_equipped"
    assert scenario3.move_to_storage_ring(scenario3.cargo_item_id).committed
    assert scenario3_source.godot_view().groups["adventure.basic.scenario-3"].payload["presentation_state"] == "storage_ring_loaded"

    scenario4 = AdventureBasicScenario4.create()
    scenario4_source = AdventureBasicMirrorSource(scenario_id="scenario-4", scenario=scenario4)
    assert scenario4_source.godot_view().groups["adventure.basic.scenario-4"].payload["presentation_state"] == "land_right_available"
    assert scenario4.purchase_land().committed
    assert scenario4_source.godot_view().groups["adventure.basic.scenario-4"].payload["presentation_state"] == "land_right_purchased"
    assert scenario4.issue_deed_credential().committed
    assert scenario4.transfer_land_right().committed
    assert scenario4_source.godot_view().groups["adventure.basic.scenario-4"].payload["presentation_state"] == "land_right_transferred"

    scenario5 = AdventureBasicScenario5.create()
    scenario5_source = AdventureBasicMirrorSource(scenario_id="scenario-5", scenario=scenario5)
    assert scenario5_source.godot_view().groups["adventure.basic.scenario-5"].payload["presentation_state"] == "gift_debt_contract_available"
    assert scenario5.gift_archive_relic().committed
    assert scenario5.issue_archive_debt().committed
    assert scenario5.repay_archive_debt(scenario5.debt_principal).committed
    assert scenario5.create_service_contract().committed
    assert scenario5.discard_contract_document().committed
    assert scenario5.complete_service_contract().committed
    assert scenario5_source.godot_view().groups["adventure.basic.scenario-5"].payload["presentation_state"] == "gift_debt_contract_settled"


def test_scenario_mirror_source_rejects_mismatched_scenario_type_before_projection() -> None:
    scenario = AdventureBasicScenario2.create()
    snapshot_before = scenario.store.export_snapshot()

    with pytest.raises(AdventureBasicMirrorSourceError, match="adventure_basic_mirror_scenario_mismatch"):
        AdventureBasicMirrorSource(scenario_id="scenario-1", scenario=scenario)

    assert scenario.store.export_snapshot() == snapshot_before
