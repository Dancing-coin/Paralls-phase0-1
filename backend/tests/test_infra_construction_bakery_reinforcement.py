from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot
from app.gameplay.event_store import GameplayEventStore


FACILITY = "facility:bakery-reinforcement:1"
STREAM = f"gameplay:construction_production:{FACILITY}"


def _seed(*, facility_kind: str = "bakery") -> tuple[GameplayEventStore, ConstructionProductionAuthority, str]:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    acquired = authority.settle_facility_acquisition(
        plot=Plot(
            plot_ref="plot:bakery-reinforcement:1",
            jurisdiction_ref="jurisdiction:bakery-reinforcement:1",
            owner_ref="organization:bakery-reinforcement:1",
        ),
        facility=Facility(
            facility_ref=FACILITY,
            plot_ref="plot:bakery-reinforcement:1",
            facility_kind=facility_kind,
            condition=0.4,
        ),
        command_id="facility:bakery-reinforcement:acquire",
        idempotency_key="facility:bakery-reinforcement:acquire",
        causation_id="cause:bakery-reinforcement:acquire",
        correlation_id="corr:bakery-reinforcement:acquire",
    )
    assert acquired.committed
    return store, authority, acquired.committed_event_ids[0]


def _zero_write(store: GameplayEventStore) -> dict[str, object]:
    snapshot = store.export_snapshot()
    return {key: snapshot[key] for key in ("events", "outbox", "idempotency")}


def _reinforce(authority: ConstructionProductionAuthority, acquisition_event_id: str, **updates: object):
    values = {
        "facility_ref": FACILITY,
        "acquisition_event_id": acquisition_event_id,
        "expected_revision": 1,
        "expected_facility_revision": 0,
        "idempotency_key": f"facility-transform:bakery-reinforcement:{FACILITY}:{acquisition_event_id}:v1",
        "causation_id": acquisition_event_id,
        "correlation_id": "corr:bakery-reinforcement:1",
        "submitted_at": "2026-08-17T00:00:00Z",
    }
    values.update(updates)
    return authority.reinforce_bakery_facility(**values)


def test_bakery_reinforcement_appends_one_owner_event_receipt_and_projection() -> None:
    store, authority, acquisition_event_id = _seed()

    result = _reinforce(authority, acquisition_event_id)

    assert result.committed
    assert result.committed_event_ids
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.construction_production.facility_transformed"
    assert event.visibility_policy == "project"
    assert event.payload["acquisition_event_id"] == acquisition_event_id
    assert event.payload["acquisition_event_revision"] == 1
    assert event.payload["prior_kind"] == "bakery"
    assert event.payload["next_kind"] == "bakery_reinforced"
    facility = authority.projector().facilities[FACILITY]
    assert facility.facility_kind == "bakery_reinforced"
    assert facility.condition == pytest.approx(0.4)
    assert facility.revision == 1
    assert store.get_stream_head(STREAM) == 2


def test_bakery_reinforcement_exact_duplicate_replays_append_receipt_without_write() -> None:
    store, authority, acquisition_event_id = _seed()
    first = _reinforce(authority, acquisition_event_id)
    before = _zero_write(store)

    duplicate = _reinforce(authority, acquisition_event_id)

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert _zero_write(store) == before


def test_bakery_reinforcement_changed_duplicate_is_zero_write() -> None:
    store, authority, acquisition_event_id = _seed()
    assert _reinforce(authority, acquisition_event_id).committed
    for updates in (
        {"correlation_id": "corr:bakery-reinforcement:changed"},
        {"expected_revision": 2},
        {"expected_facility_revision": 1},
    ):
        before = _zero_write(store)
        rejected = _reinforce(authority, acquisition_event_id, **updates)

        assert not rejected.committed
        assert rejected.failure is not None
        assert rejected.failure.error_code == "idempotency_key_reused"
        assert _zero_write(store) == before


@pytest.mark.parametrize(
    ("seed_kind", "event_id", "updates", "error_code"),
    [
        ("bakery", "event:missing", {}, "construction_bakery_reinforcement_source_missing"),
        ("mill", "seed", {}, "construction_bakery_reinforcement_source_kind_invalid"),
        ("bakery", "seed", {"expected_revision": 0}, "revision_conflict"),
        ("bakery", "seed", {"expected_facility_revision": 1}, "construction_bakery_reinforcement_facility_revision_conflict"),
        ("bakery", "seed", {"idempotency_key": "wrong"}, "construction_bakery_reinforcement_idempotency_key_invalid"),
    ],
)
def test_bakery_reinforcement_source_and_revision_rejections_are_zero_write(
    seed_kind: str,
    event_id: str,
    updates: dict[str, object],
    error_code: str,
) -> None:
    store, authority, acquisition_event_id = _seed(facility_kind=seed_kind)
    before = _zero_write(store)
    event_id = acquisition_event_id if event_id == "seed" else event_id

    rejected = _reinforce(authority, event_id, **updates)

    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == error_code
    assert _zero_write(store) == before


def test_bakery_reinforcement_resolves_privacy_and_target_kind_inside_owner() -> None:
    store, authority, acquisition_event_id = _seed()
    before = _zero_write(store)

    with pytest.raises(TypeError):
        _reinforce(authority, acquisition_event_id, privacy_scope="authority_only")
    with pytest.raises(TypeError):
        _reinforce(authority, acquisition_event_id, next_kind="mill")

    assert _zero_write(store) == before
    result = _reinforce(authority, acquisition_event_id)
    outbox = store.list_outbox()[-1]
    assert outbox.audience == "project"
    assert outbox.payload_projection == {"facility_ref": FACILITY, "next_kind": "bakery_reinforced"}
    assert "acquisition_event_id" not in outbox.payload_projection
    assert result.committed


def test_bakery_reinforcement_can_follow_repair_with_current_pins_and_preserves_condition() -> None:
    store, authority, acquisition_event_id = _seed()
    repair = authority.settle_facility_repair(
        facility_ref=FACILITY,
        repair_ref="repair-order:bakery-reinforcement:1",
        repair_amount=0.3,
        expected_revision=1,
        idempotency_key="repair:bakery-reinforcement:1",
        causation_id="cause:repair:bakery-reinforcement:1",
        correlation_id="corr:repair:bakery-reinforcement:1",
        source_ref="work-order:bakery-reinforcement:1",
        submitted_at="2026-08-17T00:00:00Z",
        privacy_scope="project",
    )
    assert repair.committed

    result = _reinforce(
        authority,
        acquisition_event_id,
        expected_revision=2,
        expected_facility_revision=1,
    )

    assert result.committed
    facility = authority.projector().facilities[FACILITY]
    assert facility.facility_kind == "bakery_reinforced"
    assert facility.condition == pytest.approx(0.7)
    assert facility.revision == 2
    assert store.read_events()[-1].payload["acquisition_event_id"] == acquisition_event_id


def test_bakery_reinforcement_full_and_checkpoint_tail_replay_match() -> None:
    _, authority, acquisition_event_id = _seed()
    assert _reinforce(authority, acquisition_event_id).committed

    full = authority.projector()
    tail = authority.projector(checkpoint_at=1)

    assert full.facilities == tail.facilities
    assert full.source_revision_vector == tail.source_revision_vector


def test_bakery_reinforcement_is_terminal_and_has_no_compensation_or_fanout_surface() -> None:
    store, authority, acquisition_event_id = _seed()
    before = _zero_write(store)

    assert not hasattr(authority, "compensate_facility_transform")
    assert not hasattr(authority, "reverse_facility_transform")
    assert not hasattr(authority, "reinforce_facilities")
    with pytest.raises(AttributeError):
        getattr(authority, "compensate_facility_transform")

    assert _zero_write(store) == before
    assert _reinforce(authority, acquisition_event_id).committed
    assert not any("transformed_compensated" in event.event_type for event in store.read_events())
