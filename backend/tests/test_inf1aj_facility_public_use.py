from __future__ import annotations

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    FacilityOperationalVerificationIntentV1,
    Plot,
    Recipe,
)
from app.gameplay.event_store import GameplayEventStore


def _verified_case(*, suffix: str, facility_kind: str = "oven") -> tuple[GameplayEventStore, ConstructionProductionAuthority, object]:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref=f"facility:inf1aj:{suffix}",
        plot_ref=f"plot:inf1aj:{suffix}",
        facility_kind=facility_kind,
        condition=1.0,
    )
    recipe = Recipe(
        recipe_ref=f"recipe:inf1aj:{suffix}",
        inputs={},
        output_item=f"item:inf1aj:{suffix}",
        duration_ticks=1,
    )
    assert authority.settle_facility_acquisition(
        plot=Plot(
            plot_ref=facility.plot_ref,
            jurisdiction_ref=f"jurisdiction:inf1aj:{suffix}",
            owner_ref=f"org:inf1aj:{suffix}",
        ),
        facility=facility,
        command_id=f"inf1aj:{suffix}:acquire",
        idempotency_key=f"inf1aj:{suffix}:acquire",
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
    ).committed
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref=f"run:inf1aj:{suffix}",
        tick=1,
        command_id=f"inf1aj:{suffix}:start",
        idempotency_key=f"inf1aj:{suffix}:start",
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
    ).committed
    run = authority.projector().runs[f"run:inf1aj:{suffix}"]
    assert authority.settle_finish_run(
        run,
        tick=2,
        recipe=recipe,
        command_id=f"inf1aj:{suffix}:finish",
        idempotency_key=f"inf1aj:{suffix}:finish",
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
    ).committed
    verification = authority.verify_facility_operationally(
        FacilityOperationalVerificationIntentV1(
            run_finished_event_id=f"event:inf1aj:{suffix}:finish:1",
            expected_run_finished_revision=3,
            expected_run_started_revision=2,
            expected_facility_revision=0,
            expected_stream_revision=3,
            command_id=f"inf1aj:{suffix}:verify",
            idempotency_key=f"construction:facility-operational-verification:event:inf1aj:{suffix}:finish:1:3:0:3:v1",
            causation_id="cause:inf1aj",
            correlation_id="corr:inf1aj",
            submitted_at="2026-08-27T12:00:00Z",
        )
    )
    assert verification.committed
    return store, authority, store.get_event(verification.committed_event_ids[0])


def test_inf1aj_enables_public_use_only_after_exact_oven_operational_verification() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:inf1aj",
        plot_ref="plot:inf1aj",
        facility_kind="oven",
        condition=1.0,
    )
    recipe = Recipe(
        recipe_ref="recipe:inf1aj",
        inputs={},
        output_item="item:inf1aj",
        duration_ticks=1,
    )
    assert authority.settle_facility_acquisition(
        plot=Plot(
            plot_ref="plot:inf1aj",
            jurisdiction_ref="jurisdiction:inf1aj",
            owner_ref="org:inf1aj",
        ),
        facility=facility,
        command_id="inf1aj:acquire",
        idempotency_key="inf1aj:acquire",
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
    ).committed
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:inf1aj",
        tick=1,
        command_id="inf1aj:start",
        idempotency_key="inf1aj:start",
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
    ).committed
    run = authority.projector().runs["run:inf1aj"]
    assert authority.settle_finish_run(
        run,
        tick=2,
        recipe=recipe,
        command_id="inf1aj:finish",
        idempotency_key="inf1aj:finish",
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
    ).committed
    verification = authority.verify_facility_operationally(
        FacilityOperationalVerificationIntentV1(
            run_finished_event_id="event:inf1aj:finish:1",
            expected_run_finished_revision=3,
            expected_run_started_revision=2,
            expected_facility_revision=0,
            expected_stream_revision=3,
            command_id="inf1aj:verify",
            idempotency_key="construction:facility-operational-verification:event:inf1aj:finish:1:3:0:3:v1",
            causation_id="cause:inf1aj",
            correlation_id="corr:inf1aj",
            submitted_at="2026-08-27T12:00:00Z",
        )
    )
    assert verification.committed
    verification_event = store.get_event(verification.committed_event_ids[0])

    # RED: the exact public-use operation is not implemented yet.
    result = authority.enable_facility_public_use(
        verification_event_id=verification_event.event_id,
        expected_verification_revision=verification_event.stream_revision,
        expected_facility_revision=0,
        expected_stream_revision=verification_event.stream_revision,
        command_id="inf1aj:enable",
        idempotency_key=(
            f"construction:facility-public-use-enable:{verification_event.event_id}:"
            f"{verification_event.stream_revision}:0:{verification_event.stream_revision}:v1"
        ),
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
        submitted_at="2026-08-27T12:01:00Z",
    )

    assert result.committed
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.construction_production.facility_public_use_enabled"
    assert event.visibility_policy == "project"
    assert event.payload["facility_ref"] == "facility:inf1aj"
    assert event.payload["next_public_use_status"] == "enabled"


def test_inf1aj_exact_duplicate_replays_receipt_and_changed_duplicate_is_zero_write() -> None:
    store, authority, verification_event = _verified_case(suffix="duplicate")
    key = f"construction:facility-public-use-enable:{verification_event.event_id}:{verification_event.stream_revision}:0:{verification_event.stream_revision}:v1"
    first = authority.enable_facility_public_use(
        verification_event_id=verification_event.event_id,
        expected_verification_revision=verification_event.stream_revision,
        expected_facility_revision=0,
        expected_stream_revision=verification_event.stream_revision,
        command_id="inf1aj:duplicate:enable",
        idempotency_key=key,
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
        submitted_at="2026-08-27T12:01:00Z",
    )
    assert first.committed
    before = store.export_snapshot()
    duplicate = authority.enable_facility_public_use(
        verification_event_id=verification_event.event_id,
        expected_verification_revision=verification_event.stream_revision,
        expected_facility_revision=0,
        expected_stream_revision=verification_event.stream_revision,
        command_id="inf1aj:duplicate:replay",
        idempotency_key=key,
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
        submitted_at="2026-08-27T12:01:00Z",
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert store.export_snapshot() == before
    changed = authority.enable_facility_public_use(
        verification_event_id=verification_event.event_id,
        expected_verification_revision=verification_event.stream_revision,
        expected_facility_revision=0,
        expected_stream_revision=verification_event.stream_revision,
        command_id="inf1aj:duplicate:changed",
        idempotency_key=key,
        causation_id="changed",
        correlation_id="corr:inf1aj",
        submitted_at="2026-08-27T12:01:00Z",
    )
    assert not changed.committed
    assert changed.failure and changed.failure.error_code == "facility_public_use_idempotency_key_reused"
    assert store.export_snapshot() == before


def test_inf1aj_rejects_non_oven_source_and_stale_stream_without_write() -> None:
    mill_store, mill_authority, mill_verification = _verified_case(suffix="mill", facility_kind="mill")
    before = mill_store.export_snapshot()
    mill_key = f"construction:facility-public-use-enable:{mill_verification.event_id}:{mill_verification.stream_revision}:0:{mill_verification.stream_revision}:v1"
    mill_result = mill_authority.enable_facility_public_use(
        verification_event_id=mill_verification.event_id,
        expected_verification_revision=mill_verification.stream_revision,
        expected_facility_revision=0,
        expected_stream_revision=mill_verification.stream_revision,
        command_id="inf1aj:mill:enable",
        idempotency_key=mill_key,
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
        submitted_at="2026-08-27T12:01:00Z",
    )
    assert not mill_result.committed
    assert mill_result.failure and mill_result.failure.error_code == "facility_public_use_eligibility_invalid"
    assert mill_store.export_snapshot() == before

    store, authority, verification_event = _verified_case(suffix="stale")
    facility_ref = verification_event.payload["facility_ref"]
    assert authority.settle_facility_repair(
        facility_ref=facility_ref,
        repair_ref="repair:inf1aj:stale",
        repair_amount=0.1,
        expected_revision=4,
        idempotency_key="repair:inf1aj:stale",
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
        source_ref="source:inf1aj:repair",
        submitted_at="2026-08-27T13:00:00Z",
        privacy_scope="project",
    ).committed
    before = store.export_snapshot()
    key = f"construction:facility-public-use-enable:{verification_event.event_id}:{verification_event.stream_revision}:0:{verification_event.stream_revision}:v1"
    stale = authority.enable_facility_public_use(
        verification_event_id=verification_event.event_id,
        expected_verification_revision=verification_event.stream_revision,
        expected_facility_revision=0,
        expected_stream_revision=verification_event.stream_revision,
        command_id="inf1aj:stale:enable",
        idempotency_key=key,
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
        submitted_at="2026-08-27T12:01:00Z",
    )
    assert not stale.committed
    assert stale.failure and stale.failure.error_code == "facility_public_use_source_invalid"
    assert store.export_snapshot() == before


def test_inf1aj_full_and_checkpoint_tail_replay_match() -> None:
    store, authority, verification_event = _verified_case(suffix="replay")
    key = f"construction:facility-public-use-enable:{verification_event.event_id}:{verification_event.stream_revision}:0:{verification_event.stream_revision}:v1"
    result = authority.enable_facility_public_use(
        verification_event_id=verification_event.event_id,
        expected_verification_revision=verification_event.stream_revision,
        expected_facility_revision=0,
        expected_stream_revision=verification_event.stream_revision,
        command_id="inf1aj:replay:enable",
        idempotency_key=key,
        causation_id="cause:inf1aj",
        correlation_id="corr:inf1aj",
        submitted_at="2026-08-27T12:01:00Z",
    )
    assert result.committed
    full = authority.projector()
    tail = authority.projector(checkpoint_at=2)
    facility = full.facilities["facility:inf1aj:replay"]
    assert facility.public_use_status == "enabled"
    assert full.facilities == tail.facilities
    assert full.source_revision_vector == tail.source_revision_vector
