from __future__ import annotations

from app.gameplay import construction_production_runtime
from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
    Recipe,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError


FACILITY = "facility:operational-verification:1"
PLOT = "plot:operational-verification:1"
RUN = "run:operational-verification:1"
STREAM = f"gameplay:construction_production:{FACILITY}"


def _setup() -> tuple[GameplayEventStore, ConstructionProductionAuthority]:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref=FACILITY, plot_ref=PLOT, facility_kind="mill", condition=1.0)
    recipe = Recipe(recipe_ref="recipe:grain", inputs={}, output_item="item:flour", duration_ticks=1)
    assert authority.settle_facility_acquisition(
        plot=Plot(plot_ref=PLOT, jurisdiction_ref="jurisdiction:operational-verification", owner_ref="organization:mill"),
        facility=facility,
        command_id="facility:operational-verification:acquire",
        idempotency_key="facility:operational-verification:acquire",
        causation_id="cause:operational-verification:acquire",
        correlation_id="corr:operational-verification",
    ).committed
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref=RUN,
        tick=1,
        command_id="run:operational-verification:start",
        idempotency_key="run:operational-verification:start",
        causation_id="cause:operational-verification:start",
        correlation_id="corr:operational-verification",
    ).committed
    run = authority.projector().runs[RUN]
    assert authority.settle_finish_run(
        run,
        tick=2,
        recipe=recipe,
        command_id="run:operational-verification:finish",
        idempotency_key="run:operational-verification:finish",
        causation_id="cause:operational-verification:finish",
        correlation_id="corr:operational-verification",
    ).committed
    return store, authority


def _intent(store: GameplayEventStore, **updates: object):
    finished = next(event for event in reversed(store.read_stream(STREAM)) if event.event_type.endswith("run_finished"))
    started = next(event for event in store.read_stream(STREAM) if event.event_type.endswith("run_started"))
    values: dict[str, object] = {
        "run_finished_event_id": finished.event_id,
        "expected_run_finished_revision": finished.stream_revision,
        "expected_run_started_revision": started.stream_revision,
        "expected_facility_revision": 0,
        "expected_stream_revision": store.get_stream_head(STREAM),
        "command_id": "command:facility-operational-verification:1",
        "idempotency_key": "pending",
        "causation_id": finished.event_id,
        "correlation_id": "corr:facility-operational-verification:1",
        "submitted_at": "2026-08-27T00:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"construction:facility-operational-verification:{finished.event_id}:"
        f"{values['expected_run_finished_revision']}:{values['expected_facility_revision']}:"
        f"{values['expected_stream_revision']}:v1"
    )
    intent_type = getattr(construction_production_runtime, "FacilityOperationalVerificationIntentV1", None)
    assert intent_type is not None, "missing row-specific operational verification intent"
    return intent_type.model_validate(values)


def test_completed_run_commits_one_operational_verification_and_replays() -> None:
    store, authority = _setup()

    result = authority.verify_facility_operationally(_intent(store))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.facility_operationally_verified"
    assert event.visibility_policy == "project"
    assert event.payload["facility_ref"] == FACILITY
    assert event.payload["project_ref"] == PLOT
    assert event.payload["run_ref"] == RUN
    assert event.payload["verification_status"] == "operationally_verified"
    projection = authority.projector()
    assert projection.operational_verifications[FACILITY].run_ref == RUN
    assert projection == authority.projector(checkpoint_at=event.global_sequence)
    assert tuple(ConstructionProductionAuthority.facility_operational_verification_receipt_for(result=result, scope="project").committed_event_ids) == tuple(result.committed_event_ids)


def test_operational_verification_duplicate_changed_and_stale_source_are_zero_write() -> None:
    store, authority = _setup()
    request = _intent(store)
    first = authority.verify_facility_operationally(request)
    before = store.export_snapshot()

    duplicate = authority.verify_facility_operationally(request)
    changed = authority.verify_facility_operationally(request.model_copy(update={"correlation_id": "corr:changed"}))
    stale = authority.verify_facility_operationally(_intent(store, expected_stream_revision=2))

    assert first.committed
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed and changed.failure is not None
    assert not stale.committed and stale.failure is not None
    assert store.export_snapshot() == before


def test_operational_verification_rejects_private_source_and_catalog_mismatch() -> None:
    store, authority = _setup()
    finished = next(event for event in reversed(store.read_stream(STREAM)) if event.event_type.endswith("run_finished"))
    store._events_by_id[finished.event_id] = finished.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    before = store.export_snapshot()
    private = authority.verify_facility_operationally(_intent(store))
    assert not private.committed and private.failure is not None
    assert store.export_snapshot() == before

    store, authority = _setup()
    before = store.export_snapshot()

    def reject(*_args: object, **_kwargs: object) -> None:
        raise GovernedAuthorityContractError("governed_authority_contract_event_mismatch")

    original = GovernedAuthorityContractCatalog.require_operation
    try:
        GovernedAuthorityContractCatalog.require_operation = classmethod(reject)  # type: ignore[method-assign]
        result = authority.verify_facility_operationally(_intent(store))
    finally:
        GovernedAuthorityContractCatalog.require_operation = original  # type: ignore[method-assign]
    assert not result.committed and result.failure is not None
    assert store.export_snapshot() == before
