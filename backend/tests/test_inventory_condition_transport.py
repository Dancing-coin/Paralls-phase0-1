from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_condition_transport import ConditionRecord, InventoryConditionTransportAuthority, TransportRecord


def test_condition_and_transport_lifecycle_replays_full_and_tail():
    store = GameplayEventStore(); authority = InventoryConditionTransportAuthority(store=store)
    assert authority.record_condition(command_id="c", idempotency_key="i:c", record=ConditionRecord(asset_ref="lot:apple@1", quality_basis_points=9000, durability_basis_points=8000, policy_ref="policy:quality@1"), expected_revision=0, causation_id="cause", correlation_id="corr").committed
    transport = TransportRecord(transport_ref="transport:apple@1", asset_ref="lot:apple@1", source_container_ref="container:src@1", destination_container_ref="container:dst@1", carrier_ref="carrier:org@1", status="in_transit", delivery_window_tick=10, policy_ref="policy:delivery@1", source_revision=0)
    assert authority.begin_transport(command_id="t", idempotency_key="i:t", record=transport, expected_revision=0, causation_id="cause", correlation_id="corr").committed
    assert authority.transition_transport(command_id="td", idempotency_key="i:td", transport_ref="transport:apple@1", status="delivered", expected_revision=1, causation_id="cause", correlation_id="corr").committed
    full = authority.projector.rebuild(store.read_events()); checkpoint = authority.projector.rebuild(store.read_events()[:1]); tail = authority.projector.rebuild(store.read_events()[1:], checkpoint=checkpoint)
    assert full == tail
    assert full.transports["transport:apple@1"].status == "delivered"


def test_transport_transition_rejects_missing_state_without_write():
    store = GameplayEventStore(); authority = InventoryConditionTransportAuthority(store=store)
    before = store.export_snapshot()
    try:
        authority.transition_transport(command_id="bad", idempotency_key="bad", transport_ref="transport:none@1", status="lost", expected_revision=0, causation_id="cause", correlation_id="corr")
    except ValueError:
        pass
    assert store.export_snapshot() == before
