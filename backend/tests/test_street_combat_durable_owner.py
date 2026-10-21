from __future__ import annotations

from app.gameplay.event_store import DurableGameplayEventStore
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService
from test_street_combat_authority import _contact_digest, _contact_ref, attempt


def _service(path):
    store = DurableGameplayEventStore(path)
    service = EmbodiedAuthoritySettlementService(store=store)
    assert service.record_street_pose("street_bandage", (0.0, 0.2, -9.8), physics_tick=100)
    assert service.record_street_pose("char_a", (-2.0, 0.2, -9.8), physics_tick=100)
    return store, service


def test_street_owner_durable_commit_recovers_receipt_and_projection(tmp_path):
    path = tmp_path / "street-owner.db"
    store, service = _service(path)
    strike = attempt("durable-hit")
    first = service.settle_street_combat(strike)
    assert first.outcome == "committed"
    assert service.street_actor_state("char_a")["hp"] == 80
    store.close()

    reopened, recovered = _service(path)
    try:
        assert recovered.street_actor_state("char_a")["hp"] == 80
        duplicate = recovered.settle_street_combat(strike)
        assert duplicate.committed_event_ids == first.committed_event_ids
        assert duplicate.transaction_id == first.transaction_id
        assert duplicate.committed_projection == first.committed_projection
        assert recovered.street_actor_state("char_a")["hp"] == 80
        changed = attempt("durable-hit", semantic_action_id="action:melee.short_punch")
        rejected = recovered.settle_street_combat(changed)
        assert rejected.outcome == "rejected"
        assert rejected.failed_code == "idempotency_key_reused"
        event = reopened.get_event(first.committed_event_ids[0])
        tx = reopened.get_transaction(event.transaction_id)
        assert tx is not None
        assert tx.idempotency_record.principal_ref == recovered._STREET_PRINCIPAL
        assert event.stream_id == recovered._STREET_STREAM
        assert event.payload["actors"]["char_a"]["hp"] == 80
    finally:
        reopened.close()


def test_street_owner_append_failure_does_not_install_candidate_state(tmp_path):
    path = tmp_path / "street-owner-failure.db"
    store, service = _service(path)
    try:
        strike = attempt("durable-failure")
        store._write_ready = False
        rejected = service.settle_street_combat(strike)
        assert rejected.outcome == "rejected"
        assert rejected.failed_code == "projection_not_ready"
        assert service.street_actor_state("char_a")["hp"] == 100
        assert service.street_actor_state("street_bandage")["stamina"] == 100
        assert service.mutation_count == 0
        assert store.read_stream(service._STREET_STREAM) == []
        store._write_ready = True
        accepted = service.settle_street_combat(strike)
        assert accepted.outcome == "committed"
        assert service.street_actor_state("char_a")["hp"] == 80
        assert service.mutation_count == 1
    finally:
        store.close()
