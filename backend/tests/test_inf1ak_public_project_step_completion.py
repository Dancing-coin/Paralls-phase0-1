from __future__ import annotations

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority, WorkerContributionRef


def _prepared_case(*, work_order_ref: str = "work-order:public-project:workshop-bench@1") -> tuple[GameplayEventStore, ConstructionProductionAuthority, OrganizationAuthority, object, object]:
    store = GameplayEventStore()
    construction = ConstructionProductionAuthority(store=store)
    organization = OrganizationAuthority(store=store)
    facility = Facility(facility_ref="facility:inf1ak", plot_ref="plot:inf1ak", facility_kind="oven", condition=1.0)
    recipe = Recipe(recipe_ref="recipe:inf1ak", inputs={}, output_item="item:inf1ak", duration_ticks=1)
    contribution = WorkerContributionRef(
        actor_ref="character:inf1ak",
        assignment_ref="assignment:inf1ak",
        work_order_ref=work_order_ref,
        contribution_digest="sha256:inf1ak-contribution",
    )
    assert construction.settle_facility_acquisition(
        plot=Plot(plot_ref="plot:inf1ak", jurisdiction_ref="jurisdiction:inf1ak", owner_ref="org:inf1ak"),
        facility=facility,
        command_id="inf1ak:acquire",
        idempotency_key="inf1ak:acquire",
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
    ).committed
    assert organization.record_schedule(
        command_id="inf1ak:schedule",
        organization_ref="org:inf1ak",
        recipient_ref="character:inf1ak",
        membership_ref="membership:inf1ak",
        assignment_ref="assignment:inf1ak",
        role="public-project",
        shift_ref="shift:inf1ak",
        operating_window_ref="window:inf1ak",
        work_order_ref=work_order_ref,
        effective_from="2026-08-27T00:00:00Z",
        effective_to=None,
        visibility_scope="organization:summary",
    ).committed
    assert construction.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:inf1ak",
        tick=1,
        command_id="inf1ak:start",
        idempotency_key="inf1ak:start",
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
        worker_contribution_refs=(contribution,),
    ).committed
    assert construction.settle_finish_run(
        construction.projector().runs["run:inf1ak"],
        tick=2,
        recipe=recipe,
        command_id="inf1ak:finish",
        idempotency_key="inf1ak:finish",
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
    ).committed
    evidence = construction.record_completed_work_evidence(
        run_ref="run:inf1ak",
        contribution=contribution,
        evidence_ref="evidence:production-completed:run:inf1ak:sha256:inf1ak-contribution",
        observed_at="2026-08-27T12:00:00Z",
        command_id="inf1ak:evidence",
        idempotency_key="inf1ak:evidence",
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
    )
    assert evidence.committed
    source = store.get_event(evidence.committed_event_ids[0])
    schedule = next(event for event in store.read_stream("gameplay:organization:org:inf1ak") if event.event_type == "gameplay.organization.work_order_recorded")
    accepted_key = f"organization:production-work-contribution:org:inf1ak:{source.event_id}:{source.stream_revision}:{schedule.event_id}:{schedule.stream_revision}:v1"
    accepted = organization.accept_production_work_contribution(
        organization_ref="org:inf1ak",
        source_evidence_event_id=source.event_id,
        expected_source_stream_revision=source.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf1ak"),
        command_id="inf1ak:accept",
        idempotency_key=accepted_key,
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
    )
    assert accepted.committed
    accepted_event = store.get_event(accepted.committed_event_ids[0])
    fulfillment_key = f"organization:production-work-order-fulfillment:{accepted_event.event_id}:{accepted_event.stream_revision}:v1"
    fulfilled = organization.fulfill_production_work_order(
        organization_ref="org:inf1ak",
        accepted_event_id=accepted_event.event_id,
        expected_accepted_revision=accepted_event.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf1ak"),
        command_id="inf1ak:fulfill",
        idempotency_key=fulfillment_key,
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
    )
    assert fulfilled.committed
    return store, construction, organization, store.get_event(fulfilled.committed_event_ids[0]), facility


def test_inf1ak_records_one_fixed_public_project_step_from_organization_fulfillment() -> None:
    store, construction, _, source, _ = _prepared_case()
    result = construction.record_public_project_step_completion(
        source_event_id=source.event_id,
        expected_source_revision=source.stream_revision,
        expected_target_stream_revision=store.get_stream_head("gameplay:construction_production:facility:inf1ak"),
        command_id="inf1ak:project-step",
        idempotency_key=(
            f"construction:public-project-step:{source.event_id}:{source.stream_revision}:0:"
            f"{store.get_stream_head('gameplay:construction_production:facility:inf1ak')}:v1"
        ),
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
        submitted_at="2026-08-27T12:02:00Z",
    )

    assert result.committed
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.construction_production.public_project_step_completed"
    assert event.visibility_policy == "project"
    assert event.payload["project_step_ref"] == "project-step:public-project:workshop-bench@1"
    assert construction.projector().facilities["facility:inf1ak"].completed_project_step_refs == (
        "project-step:public-project:workshop-bench@1",
    )


def test_inf1ak_rejects_wrong_literal_work_order_without_write() -> None:
    store, construction, _, source, _ = _prepared_case(work_order_ref="work-order:other@1")
    before = store.export_snapshot()
    result = construction.record_public_project_step_completion(
        source_event_id=source.event_id,
        expected_source_revision=source.stream_revision,
        expected_target_stream_revision=store.get_stream_head("gameplay:construction_production:facility:inf1ak"),
        command_id="inf1ak:wrong-work-order",
        idempotency_key=f"construction:public-project-step:{source.event_id}:{source.stream_revision}:0:4:v1",
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
        submitted_at="2026-08-27T12:02:00Z",
    )
    assert not result.committed
    assert result.failure and result.failure.error_code == "public_project_step_source_invalid"
    assert store.export_snapshot() == before


def test_inf1ak_exact_duplicate_replays_receipt_and_changed_duplicate_is_zero_write() -> None:
    store, construction, _, source, _ = _prepared_case()
    target_stream = "gameplay:construction_production:facility:inf1ak"
    target_head = store.get_stream_head(target_stream)
    key = f"construction:public-project-step:{source.event_id}:{source.stream_revision}:0:{target_head}:v1"
    first = construction.record_public_project_step_completion(
        source_event_id=source.event_id,
        expected_source_revision=source.stream_revision,
        expected_target_stream_revision=target_head,
        command_id="inf1ak:duplicate:first",
        idempotency_key=key,
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
        submitted_at="2026-08-27T12:02:00Z",
    )
    assert first.committed
    before = store.export_snapshot()
    duplicate = construction.record_public_project_step_completion(
        source_event_id=source.event_id,
        expected_source_revision=source.stream_revision,
        expected_target_stream_revision=target_head,
        command_id="inf1ak:duplicate:replay",
        idempotency_key=key,
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
        submitted_at="2026-08-27T12:02:00Z",
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert store.export_snapshot() == before
    changed = construction.record_public_project_step_completion(
        source_event_id=source.event_id,
        expected_source_revision=source.stream_revision,
        expected_target_stream_revision=target_head,
        command_id="inf1ak:duplicate:changed",
        idempotency_key=key,
        causation_id="changed",
        correlation_id="corr:inf1ak",
        submitted_at="2026-08-27T12:02:00Z",
    )
    assert not changed.committed
    assert changed.failure and changed.failure.error_code == "public_project_step_idempotency_key_reused"
    assert store.export_snapshot() == before
    receipt = construction.public_project_step_receipt_for(result=first, scope="project")
    assert receipt.transaction_id == first.transaction_id


def test_inf1ak_full_and_checkpoint_tail_replay_match() -> None:
    store, construction, _, source, _ = _prepared_case()
    target_stream = "gameplay:construction_production:facility:inf1ak"
    key = f"construction:public-project-step:{source.event_id}:{source.stream_revision}:0:{store.get_stream_head(target_stream)}:v1"
    result = construction.record_public_project_step_completion(
        source_event_id=source.event_id,
        expected_source_revision=source.stream_revision,
        expected_target_stream_revision=store.get_stream_head(target_stream),
        command_id="inf1ak:replay",
        idempotency_key=key,
        causation_id="cause:inf1ak",
        correlation_id="corr:inf1ak",
        submitted_at="2026-08-27T12:02:00Z",
    )
    assert result.committed
    full = construction.projector()
    tail = construction.projector(checkpoint_at=4)
    assert full.facilities == tail.facilities
    assert full.source_revision_vector == tail.source_revision_vector
