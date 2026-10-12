import pytest

from app.population_continuity.flood_vertical import FloodPopulationFixture
from app.population_continuity.member_ledger import member_result_stream


@pytest.fixture
def supply_case(tmp_path):
    value = FloodPopulationFixture.create(storage_root=tmp_path)
    try:
        yield value
    finally:
        value.close()


def test_read_dependency_change_at_actual_append_rejects_supply(supply_case, monkeypatch):
    original = supply_case.store.append_batch
    changed = False

    def race(batch):
        nonlocal changed
        if not changed and any(event.event_type == "gameplay.organization.commerce_commitment_accepted" for event in batch.events):
            changed = True
            assert supply_case.world.resume().committed
        return original(batch)

    monkeypatch.setattr(supply_case.store, "append_batch", race)
    result = supply_case.run_window(from_tick=0, to_tick=3600)
    assert changed
    assert result.owner_receipts and not result.owner_receipts[0].committed
    assert result.owner_receipts[0].zero_write
    assert not any(event.event_type == "gameplay.organization.commerce_commitment_accepted" for event in supply_case.business_events())
    assert supply_case.character_runtime.get_continuity_revision("char_a") == 0


def test_changed_frozen_payload_cannot_replay_successful_delivery(supply_case):
    supply_case.run_window(from_tick=0, to_tick=3600)
    event = supply_case.events[(0, 3600)].model_copy(deep=True)
    row = next(item for item in event.payload["population_projections"] if item["payload"].get("candidate_kind") == "schedule_gated_supply")
    row["payload"]["schedule_gated_supply_source_context"]["candidate"]["payload"]["commitment_ref"] = "commitment:changed"
    before = supply_case.authority_snapshot()
    with pytest.raises(ValueError, match="authority_event_id_conflict"):
        supply_case.bus.publish(event)
    assert supply_case.authority_snapshot() == before


def test_member_revision_change_at_cadence_append_rejects_before_owner_execution(supply_case, monkeypatch):
    original = supply_case.store.append_batch
    changed = False
    hot = supply_case.world.population_hot_state.export_rows()

    def race(batch):
        nonlocal changed
        if not changed and any(event.event_type == "population.cadence.admitted" for event in batch.events):
            changed = True
            stream = supply_case.world.member_ledger_stream(supply_case.cohort_ref)
            actor_stream = member_result_stream(stream, "character:char_a")
            assert actor_stream in batch.read_stream_revisions
            expected = batch.read_stream_revisions[actor_stream]
            result = supply_case.world.confirm_member_result(cohort_ref=supply_case.cohort_ref,
                actor_ref="character:char_a", result_ref=supply_case.schedule.committed_event_ids[0],
                expected_revision=supply_case.store.get_stream_head(stream), idempotency_key="race:member")
            assert result.committed
            assert supply_case.store.get_stream_head(actor_stream) > expected
        return original(batch)

    monkeypatch.setattr(supply_case.store, "append_batch", race)
    with pytest.raises(ValueError, match="flood_publication_rejected"):
        supply_case.run_window(from_tick=0, to_tick=3600)
    assert changed and supply_case.world.population_hot_state.export_rows() == hot
    assert not any(event.event_type == "gameplay.organization.commerce_commitment_accepted" for event in supply_case.business_events())
