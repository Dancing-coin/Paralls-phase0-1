from __future__ import annotations

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    FacilityOperationalVerificationIntentV1,
    Recipe,
)
from test_infra_construction_mill_reinforcement import _intent, _setup
from test_inf1aj_facility_public_use import _verified_case
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog


def _enable_request(authority, verification_event, *, facility_revision: int = 1, correlation_id: str = "corr:mill-reinforcement:public-use"):
    return authority.enable_mill_reinforced_public_use(
        verification_event_id=verification_event.event_id,
        expected_verification_revision=verification_event.stream_revision,
        expected_facility_revision=facility_revision,
        expected_stream_revision=verification_event.stream_revision,
        command_id="public-use:mill-reinforcement",
        idempotency_key=(
            f"construction:facility-mill-reinforced-public-use:{verification_event.event_id}:"
            f"{verification_event.stream_revision}:{facility_revision}:{verification_event.stream_revision}:v1"
        ),
        causation_id=verification_event.event_id,
        correlation_id=correlation_id,
        submitted_at="2026-08-28T00:01:00Z",
    )


def test_inf1al_completed_mill_reinforced_run_enables_public_use() -> None:
    store, authority, _registry, acquisition_id = _setup()
    reinforcement = authority.reinforce_mill_from_package(_intent(acquisition_id))
    assert reinforcement.committed

    facility = authority.projector().facilities["facility:mill-reinforcement:1"]
    recipe = Recipe(
        recipe_ref="recipe:mill-reinforcement:public-use",
        inputs={},
        output_item="item:flour",
        duration_ticks=1,
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:mill-reinforcement:public-use",
        tick=10,
        command_id="run:mill-reinforcement:public-use:start",
        idempotency_key="run:mill-reinforcement:public-use:start",
        causation_id="cause:mill-reinforcement:public-use:start",
        correlation_id="corr:mill-reinforcement:public-use",
    ).committed
    run = authority.projector().runs["run:mill-reinforcement:public-use"]
    assert authority.settle_finish_run(
        run,
        tick=11,
        recipe=recipe,
        command_id="run:mill-reinforcement:public-use:finish",
        idempotency_key="run:mill-reinforcement:public-use:finish",
        causation_id="cause:mill-reinforcement:public-use:finish",
        correlation_id="corr:mill-reinforcement:public-use",
    ).committed
    finished = store.read_stream(facility_stream := f"gameplay:construction_production:{facility.facility_ref}")[-1]
    started = store.read_stream(facility_stream)[-2]
    verification = authority.verify_facility_operationally(
        FacilityOperationalVerificationIntentV1(
            run_finished_event_id=finished.event_id,
            expected_run_finished_revision=finished.stream_revision,
            expected_run_started_revision=started.stream_revision,
            expected_facility_revision=1,
            expected_stream_revision=store.get_stream_head(facility_stream),
            command_id="verification:mill-reinforcement:public-use",
            idempotency_key=(
                f"construction:facility-operational-verification:{finished.event_id}:"
                f"{finished.stream_revision}:1:{store.get_stream_head(facility_stream)}:v1"
            ),
            causation_id=finished.event_id,
            correlation_id="corr:mill-reinforcement:public-use",
            submitted_at="2026-08-28T00:00:00Z",
        )
    )
    assert verification.committed
    verification_event = store.get_event(verification.committed_event_ids[0])

    result = _enable_request(authority, verification_event)
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["facility_kind"] == "mill_reinforced"
    assert event.payload["next_public_use_status"] == "enabled"
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:construction-facility-mill-reinforced-public-use@1",
        contract_kind="lifecycle",
    )
    assert contract.event_types == ("gameplay.construction_production.facility_public_use_enabled",)


def test_inf1al_duplicate_changed_duplicate_and_replay_are_bounded() -> None:
    store, authority, _registry, acquisition_id = _setup()
    assert authority.reinforce_mill_from_package(_intent(acquisition_id)).committed
    facility = authority.projector().facilities["facility:mill-reinforcement:1"]
    recipe = Recipe(recipe_ref="recipe:mill-reinforcement:replay", inputs={}, output_item="item:flour", duration_ticks=1)
    assert authority.settle_start_run(facility=facility, recipe=recipe, run_ref="run:mill-reinforcement:replay", tick=10, command_id="run:mill-reinforcement:replay:start", idempotency_key="run:mill-reinforcement:replay:start", causation_id="cause:start", correlation_id="corr:replay").committed
    run = authority.projector().runs["run:mill-reinforcement:replay"]
    assert authority.settle_finish_run(run, tick=11, recipe=recipe, command_id="run:mill-reinforcement:replay:finish", idempotency_key="run:mill-reinforcement:replay:finish", causation_id="cause:finish", correlation_id="corr:replay").committed
    stream = f"gameplay:construction_production:{facility.facility_ref}"
    events = store.read_stream(stream)
    finished = events[-1]
    started = events[-2]
    verification = authority.verify_facility_operationally(FacilityOperationalVerificationIntentV1(run_finished_event_id=finished.event_id, expected_run_finished_revision=finished.stream_revision, expected_run_started_revision=started.stream_revision, expected_facility_revision=1, expected_stream_revision=store.get_stream_head(stream), command_id="verification:replay", idempotency_key=f"construction:facility-operational-verification:{finished.event_id}:{finished.stream_revision}:1:{store.get_stream_head(stream)}:v1", causation_id=finished.event_id, correlation_id="corr:replay", submitted_at="2026-08-28T00:00:00Z"))
    assert verification.committed
    verification_event = store.get_event(verification.committed_event_ids[0])
    first = _enable_request(authority, verification_event)
    assert first.committed
    duplicate = _enable_request(authority, verification_event)
    changed = _enable_request(authority, verification_event, correlation_id="corr:changed")
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert authority.projector().facilities[facility.facility_ref].public_use_status == "enabled"
    assert authority.projector().facilities == authority.projector(checkpoint_at=5).facilities


def test_inf1al_wrong_kind_is_zero_write() -> None:
    store, authority, verification_event = _verified_case(suffix="wrong-kind", facility_kind="oven")
    before = store.export_snapshot()
    denied = _enable_request(authority, verification_event)
    assert not denied.committed
    assert store.export_snapshot() == before
