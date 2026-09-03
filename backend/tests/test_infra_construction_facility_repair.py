from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot
from app.gameplay.event_store import GameplayEventStore


FACILITY = "facility:repair:1"
STREAM = f"gameplay:construction_production:{FACILITY}"


def _seed() -> tuple[GameplayEventStore, ConstructionProductionAuthority]:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    assert authority.settle_facility_acquisition(
        plot=Plot(
            plot_ref="plot:repair:1",
            jurisdiction_ref="jurisdiction:repair:1",
            owner_ref="organization:repair:1",
        ),
        facility=Facility(
            facility_ref=FACILITY,
            plot_ref="plot:repair:1",
            facility_kind="bakery",
            condition=0.4,
        ),
        command_id="facility:repair:acquire",
        idempotency_key="facility:repair:acquire",
        causation_id="cause:repair:acquire",
        correlation_id="corr:repair:acquire",
    ).committed
    return store, authority


def _zero_write(store: GameplayEventStore) -> dict[str, object]:
    snapshot = store.export_snapshot()
    return {key: snapshot[key] for key in ("events", "outbox", "idempotency")}


def _repair(authority: ConstructionProductionAuthority, **updates: object):
    values = {
        "facility_ref": FACILITY,
        "repair_ref": "repair-order:1",
        "repair_amount": 0.3,
        "expected_revision": 1,
        "idempotency_key": "repair:1",
        "causation_id": "cause:repair:1",
        "correlation_id": "corr:repair:1",
        "source_ref": "work-order:repair:1",
        "submitted_at": "2026-08-17T00:00:00Z",
        "privacy_scope": "project",
    }
    values.update(updates)
    return authority.settle_facility_repair(**values)


def test_facility_repair_appends_owner_event_and_projects_condition() -> None:
    store, authority = _seed()

    result = _repair(authority)

    assert result.committed
    assert result.committed_event_ids
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.construction_production.facility_repaired"
    assert event.visibility_policy == "project"
    assert event.payload["prior_condition"] == pytest.approx(0.4)
    assert event.payload["next_condition"] == pytest.approx(0.7)
    assert authority.projector().facilities[FACILITY].condition == pytest.approx(0.7)


def test_facility_repair_exact_duplicate_is_receipt_replay_without_write() -> None:
    store, authority = _seed()
    first = _repair(authority)
    before = _zero_write(store)

    duplicate = _repair(authority)

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert _zero_write(store) == before


def test_facility_repair_changed_duplicate_is_zero_write() -> None:
    store, authority = _seed()
    assert _repair(authority).committed
    before = _zero_write(store)

    rejected = _repair(authority, repair_amount=0.2)

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "idempotency_key_reused"
    assert _zero_write(store) == before


def test_facility_repair_replay_rejects_stream_or_privacy_tamper() -> None:
    store, authority = _seed()
    result = _repair(authority)
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    wrong_stream = event.model_copy(update={"stream_id": "gameplay:construction_production:facility:other"}, deep=True)
    with pytest.raises(ValueError, match="facility_repair_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], wrong_stream])
    private = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    with pytest.raises(ValueError, match="facility_repair_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], private])


@pytest.mark.parametrize(
    "mutation",
    [
        {"next_condition": 1.5},
        {"next_condition": -0.1},
        {"facility_revision": 3},
    ],
)
def test_facility_repair_replay_rejects_condition_or_revision_tamper(mutation: dict[str, object]) -> None:
    store, authority = _seed()
    result = _repair(authority)
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    tampered = event.model_copy(update={"payload": {**event.payload, **mutation}}, deep=True)
    with pytest.raises(ValueError, match="facility_repair_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


@pytest.mark.parametrize(
    ("updates", "error_code"),
    [
        ({"expected_revision": 0, "idempotency_key": "repair:stale"}, "revision_conflict"),
        ({"privacy_scope": "authority_only", "idempotency_key": "repair:private"}, "construction_repair_privacy_scope_denied"),
        ({"repair_amount": 0, "idempotency_key": "repair:zero"}, "construction_repair_amount_invalid"),
    ],
)
def test_facility_repair_rejections_are_zero_write(updates: dict[str, object], error_code: str) -> None:
    store, authority = _seed()
    before = _zero_write(store)

    rejected = _repair(authority, **updates)

    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == error_code
    assert _zero_write(store) == before


def test_facility_repair_compensation_restores_prior_condition() -> None:
    store, authority = _seed()
    repair = _repair(authority)
    repair_event_id = repair.committed_event_ids[0]

    result = authority.compensate_facility_repair(
        repair_event_id=repair_event_id,
        expected_revision=2,
        reason_ref="policy:repair-reversal:1",
        idempotency_key="repair:compensate:1",
        causation_id=repair_event_id,
        correlation_id="corr:repair:compensate:1",
        source_ref="policy:repair-reversal:1",
        submitted_at="2026-08-17T00:01:00Z",
        privacy_scope="project",
    )

    assert result.committed
    assert store.read_events()[-1].event_type == "gameplay.construction_production.facility_repair_compensated"
    assert authority.projector().facilities[FACILITY].condition == pytest.approx(0.4)


def test_facility_repair_compensation_exact_duplicate_replays_receipt_without_write() -> None:
    store, authority = _seed()
    repair = _repair(authority)
    values = {
        "repair_event_id": repair.committed_event_ids[0],
        "expected_revision": 2,
        "reason_ref": "policy:repair-reversal:1",
        "idempotency_key": "repair:compensate:1",
        "causation_id": repair.committed_event_ids[0],
        "correlation_id": "corr:repair:compensate:1",
        "source_ref": "policy:repair-reversal:1",
        "submitted_at": "2026-08-17T00:01:00Z",
        "privacy_scope": "project",
    }
    first = authority.compensate_facility_repair(**values)
    before = _zero_write(store)

    duplicate = authority.compensate_facility_repair(**values)

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert _zero_write(store) == before


def test_facility_repair_full_and_checkpoint_tail_replay_match() -> None:
    store, authority = _seed()
    repair = _repair(authority)
    assert repair.committed
    assert authority.compensate_facility_repair(
        repair_event_id=repair.committed_event_ids[0],
        expected_revision=2,
        reason_ref="policy:repair-reversal:1",
        idempotency_key="repair:compensate:1",
        causation_id=repair.committed_event_ids[0],
        correlation_id="corr:repair:compensate:1",
        source_ref="policy:repair-reversal:1",
        submitted_at="2026-08-17T00:01:00Z",
        privacy_scope="project",
    ).committed

    full = authority.projector()
    tail = authority.projector(checkpoint_at=1)
    assert full.facilities == tail.facilities
    assert full.source_revision_vector == tail.source_revision_vector
