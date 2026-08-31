from __future__ import annotations

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority, WorkerContributionRef
from app.gameplay.settlement_plan import build_atomic_event_batch


def _prepared_case(*, visibility_scope: str) -> tuple[GameplayEventStore, OrganizationAuthority, object, object]:
    store = GameplayEventStore()
    construction = ConstructionProductionAuthority(store=store)
    organization = OrganizationAuthority(store=store)
    facility = Facility(facility_ref="facility:inf4v:edge", plot_ref="plot:inf4v:edge", facility_kind="oven", condition=1.0)
    recipe = Recipe(recipe_ref="recipe:inf4v:edge", inputs={}, output_item="item:inf4v:edge", duration_ticks=1)
    contribution = WorkerContributionRef(actor_ref="character:inf4v:edge", assignment_ref="assignment:inf4v:edge", work_order_ref="work-order:inf4v:edge", contribution_digest="sha256:inf4v-edge")
    assert construction.settle_facility_acquisition(plot=Plot(plot_ref="plot:inf4v:edge", jurisdiction_ref="jurisdiction:inf4v:edge", owner_ref="org:inf4v:edge"), facility=facility, command_id="inf4v:edge:acquire", idempotency_key="inf4v:edge:acquire", causation_id="cause", correlation_id="corr").committed
    assert organization.record_schedule(command_id="inf4v:edge:schedule", organization_ref="org:inf4v:edge", recipient_ref="character:inf4v:edge", membership_ref="membership:inf4v:edge", assignment_ref="assignment:inf4v:edge", role="operator", shift_ref="shift:inf4v:edge", operating_window_ref="window:inf4v:edge", work_order_ref="work-order:inf4v:edge", effective_from="2026-08-27T00:00:00Z", effective_to=None, visibility_scope=visibility_scope).committed
    assert construction.settle_start_run(facility=facility, recipe=recipe, run_ref="run:inf4v:edge", tick=1, command_id="inf4v:edge:start", idempotency_key="inf4v:edge:start", causation_id="cause", correlation_id="corr", worker_contribution_refs=(contribution,)).committed
    assert construction.settle_finish_run(construction.projector().runs["run:inf4v:edge"], tick=2, recipe=recipe, command_id="inf4v:edge:finish", idempotency_key="inf4v:edge:finish", causation_id="cause", correlation_id="corr").committed
    evidence = construction.record_completed_work_evidence(run_ref="run:inf4v:edge", contribution=contribution, evidence_ref="evidence:production-completed:run:inf4v:edge:sha256:inf4v-edge", observed_at="2026-08-27T12:00:00Z", command_id="inf4v:edge:evidence", idempotency_key="inf4v:edge:evidence", causation_id="cause", correlation_id="corr")
    assert evidence.committed
    source = store.get_event(evidence.committed_event_ids[0])
    schedule = next(event for event in store.read_stream("gameplay:organization:org:inf4v:edge") if event.event_type == "gameplay.organization.work_order_recorded")
    return store, organization, source, schedule


def test_inf4v_accepts_only_production_evidence_with_committed_organization_schedule() -> None:
    store = GameplayEventStore()
    construction = ConstructionProductionAuthority(store=store)
    organization = OrganizationAuthority(store=store)

    facility = Facility(facility_ref="facility:inf4v", plot_ref="plot:inf4v", facility_kind="oven", condition=1.0)
    recipe = Recipe(recipe_ref="recipe:inf4v", inputs={}, output_item="item:inf4v", duration_ticks=1)
    contribution = WorkerContributionRef(
        actor_ref="character:inf4v",
        assignment_ref="assignment:inf4v",
        work_order_ref="work-order:inf4v",
        evidence_refs=("evidence:inf4v",),
        contribution_digest="sha256:inf4v-contribution",
    )
    assert construction.settle_facility_acquisition(
        plot=Plot(plot_ref="plot:inf4v", jurisdiction_ref="jurisdiction:inf4v", owner_ref="org:inf4v"),
        facility=facility,
        command_id="inf4v:acquire",
        idempotency_key="inf4v:acquire",
        causation_id="cause:inf4v",
        correlation_id="corr:inf4v",
    ).committed
    assert organization.record_schedule(
        command_id="inf4v:schedule",
        organization_ref="org:inf4v",
        recipient_ref="character:inf4v",
        membership_ref="membership:inf4v",
        assignment_ref="assignment:inf4v",
        role="operator",
        shift_ref="shift:inf4v",
        operating_window_ref="window:inf4v",
        work_order_ref="work-order:inf4v",
        effective_from="2026-08-27T00:00:00Z",
        effective_to="2026-08-28T00:00:00Z",
        visibility_scope="organization:summary",
    ).committed
    assert construction.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:inf4v",
        tick=1,
        command_id="inf4v:start",
        idempotency_key="inf4v:start",
        causation_id="cause:inf4v",
        correlation_id="corr:inf4v",
        worker_contribution_refs=(contribution,),
    ).committed
    run = construction.projector().runs["run:inf4v"]
    assert construction.settle_finish_run(
        run,
        tick=2,
        recipe=recipe,
        command_id="inf4v:finish",
        idempotency_key="inf4v:finish",
        causation_id="cause:inf4v",
        correlation_id="corr:inf4v",
    ).committed

    evidence = construction.record_completed_work_evidence(
        run_ref="run:inf4v",
        contribution=contribution,
        evidence_ref="evidence:production-completed:run:inf4v:sha256:inf4v-contribution",
        observed_at="2026-08-27T12:00:00Z",
        command_id="inf4v:evidence",
        idempotency_key="inf4v:evidence",
        causation_id="cause:inf4v",
        correlation_id="corr:inf4v",
    )
    assert evidence.committed
    source_event = store.get_event(evidence.committed_event_ids[0])
    schedule_event = next(
        event
        for event in store.read_stream("gameplay:organization:org:inf4v")
        if event.event_type == "gameplay.organization.work_order_recorded"
    )
    idempotency_key = (
        f"organization:production-work-contribution:org:inf4v:{source_event.event_id}:"
        f"{source_event.stream_revision}:{schedule_event.event_id}:{schedule_event.stream_revision}:v1"
    )

    # RED: the row-specific Organization method does not exist yet.
    result = organization.accept_production_work_contribution(
        organization_ref="org:inf4v",
        source_evidence_event_id=source_event.event_id,
        expected_source_stream_revision=source_event.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v"),
        command_id="inf4v:accept",
        idempotency_key=idempotency_key,
        causation_id="cause:inf4v",
        correlation_id="corr:inf4v",
    )

    assert result.committed
    accepted = store.read_events()[-1]
    assert accepted.event_type == "gameplay.organization.production_work_contribution_accepted"
    assert accepted.visibility_policy == "organization:summary"
    assert accepted.payload["organization_ref"] == "org:inf4v"
    assert accepted.payload["source_evidence_event_id"] == source_event.event_id


def test_inf4v_rejects_untrusted_idempotency_key_without_write() -> None:
    store = GameplayEventStore()
    construction = ConstructionProductionAuthority(store=store)
    organization = OrganizationAuthority(store=store)
    facility = Facility(facility_ref="facility:inf4v:key", plot_ref="plot:inf4v:key", facility_kind="oven", condition=1.0)
    recipe = Recipe(recipe_ref="recipe:inf4v:key", inputs={}, output_item="item:inf4v:key", duration_ticks=1)
    contribution = WorkerContributionRef(actor_ref="character:inf4v:key", assignment_ref="assignment:inf4v:key", work_order_ref="work-order:inf4v:key", contribution_digest="sha256:inf4v-key")
    assert construction.settle_facility_acquisition(plot=Plot(plot_ref="plot:inf4v:key", jurisdiction_ref="jurisdiction:inf4v:key", owner_ref="org:inf4v:key"), facility=facility, command_id="inf4v:key:acquire", idempotency_key="inf4v:key:acquire", causation_id="cause", correlation_id="corr").committed
    assert organization.record_schedule(command_id="inf4v:key:schedule", organization_ref="org:inf4v:key", recipient_ref="character:inf4v:key", membership_ref="membership:inf4v:key", assignment_ref="assignment:inf4v:key", role="operator", shift_ref="shift:inf4v:key", operating_window_ref="window:inf4v:key", work_order_ref="work-order:inf4v:key", effective_from="2026-08-27T00:00:00Z", effective_to=None, visibility_scope="organization:summary").committed
    assert construction.settle_start_run(facility=facility, recipe=recipe, run_ref="run:inf4v:key", tick=1, command_id="inf4v:key:start", idempotency_key="inf4v:key:start", causation_id="cause", correlation_id="corr", worker_contribution_refs=(contribution,)).committed
    assert construction.settle_finish_run(construction.projector().runs["run:inf4v:key"], tick=2, recipe=recipe, command_id="inf4v:key:finish", idempotency_key="inf4v:key:finish", causation_id="cause", correlation_id="corr").committed
    evidence = construction.record_completed_work_evidence(run_ref="run:inf4v:key", contribution=contribution, evidence_ref="evidence:production-completed:run:inf4v:key:sha256:inf4v-key", observed_at="2026-08-27T12:00:00Z", command_id="inf4v:key:evidence", idempotency_key="inf4v:key:evidence", causation_id="cause", correlation_id="corr")
    assert evidence.committed
    source = store.get_event(evidence.committed_event_ids[0])
    before = store.export_snapshot()

    result = organization.accept_production_work_contribution(
        organization_ref="org:inf4v:key",
        source_evidence_event_id=source.event_id,
        expected_source_stream_revision=source.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:key"),
        command_id="inf4v:key:accept",
        idempotency_key="caller-chosen-key",
        causation_id="cause",
        correlation_id="corr",
    )

    assert not result.committed
    assert result.failure and result.failure.error_code == "organization_work_contribution_idempotency_key_invalid"
    assert store.export_snapshot() == before


def test_inf4v_replays_exact_duplicate_and_rejects_changed_duplicate() -> None:
    store = GameplayEventStore()
    construction = ConstructionProductionAuthority(store=store)
    organization = OrganizationAuthority(store=store)
    facility = Facility(facility_ref="facility:inf4v:dup", plot_ref="plot:inf4v:dup", facility_kind="oven", condition=1.0)
    recipe = Recipe(recipe_ref="recipe:inf4v:dup", inputs={}, output_item="item:inf4v:dup", duration_ticks=1)
    contribution = WorkerContributionRef(actor_ref="character:inf4v:dup", assignment_ref="assignment:inf4v:dup", work_order_ref="work-order:inf4v:dup", contribution_digest="sha256:inf4v-dup")
    assert construction.settle_facility_acquisition(plot=Plot(plot_ref="plot:inf4v:dup", jurisdiction_ref="jurisdiction:inf4v:dup", owner_ref="org:inf4v:dup"), facility=facility, command_id="inf4v:dup:acquire", idempotency_key="inf4v:dup:acquire", causation_id="cause", correlation_id="corr").committed
    assert organization.record_schedule(command_id="inf4v:dup:schedule", organization_ref="org:inf4v:dup", recipient_ref="character:inf4v:dup", membership_ref="membership:inf4v:dup", assignment_ref="assignment:inf4v:dup", role="operator", shift_ref="shift:inf4v:dup", operating_window_ref="window:inf4v:dup", work_order_ref="work-order:inf4v:dup", effective_from="2026-08-27T00:00:00Z", effective_to=None, visibility_scope="organization:summary").committed
    assert construction.settle_start_run(facility=facility, recipe=recipe, run_ref="run:inf4v:dup", tick=1, command_id="inf4v:dup:start", idempotency_key="inf4v:dup:start", causation_id="cause", correlation_id="corr", worker_contribution_refs=(contribution,)).committed
    assert construction.settle_finish_run(construction.projector().runs["run:inf4v:dup"], tick=2, recipe=recipe, command_id="inf4v:dup:finish", idempotency_key="inf4v:dup:finish", causation_id="cause", correlation_id="corr").committed
    evidence = construction.record_completed_work_evidence(run_ref="run:inf4v:dup", contribution=contribution, evidence_ref="evidence:production-completed:run:inf4v:dup:sha256:inf4v-dup", observed_at="2026-08-27T12:00:00Z", command_id="inf4v:dup:evidence", idempotency_key="inf4v:dup:evidence", causation_id="cause", correlation_id="corr")
    assert evidence.committed
    source = store.get_event(evidence.committed_event_ids[0])
    schedule = next(event for event in store.read_stream("gameplay:organization:org:inf4v:dup") if event.event_type == "gameplay.organization.work_order_recorded")
    key = f"organization:production-work-contribution:org:inf4v:dup:{source.event_id}:{source.stream_revision}:{schedule.event_id}:{schedule.stream_revision}:v1"
    first = organization.accept_production_work_contribution(organization_ref="org:inf4v:dup", source_evidence_event_id=source.event_id, expected_source_stream_revision=source.stream_revision, expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:dup"), command_id="inf4v:dup:accept", idempotency_key=key, causation_id="cause", correlation_id="corr")
    assert first.committed
    before = store.export_snapshot()
    duplicate = organization.accept_production_work_contribution(organization_ref="org:inf4v:dup", source_evidence_event_id=source.event_id, expected_source_stream_revision=source.stream_revision, expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:dup"), command_id="inf4v:dup:accept-replay", idempotency_key=key, causation_id="cause", correlation_id="corr")
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert store.export_snapshot() == before
    full_view = organization.work_contribution_acceptance_view_for(organization_ref="org:inf4v:dup")
    replayed = GameplayEventStore()
    for index, original in enumerate(store.read_stream("gameplay:organization:org:inf4v:dup"), start=1):
        batch = build_atomic_event_batch(
            command_id=f"inf4v:dup:replay:{index}",
            principal_ref="actor_gameplay.organization_domain",
            stream_id=original.stream_id,
            expected_revision=replayed.get_stream_head(original.stream_id),
            event_specs=[(original.event_type, original.payload)],
            idempotency_key=f"inf4v:dup:replay:{index}",
            causation_id="replay",
            correlation_id="replay",
        )
        batch = batch.model_copy(
            update={"events": [event.model_copy(update={"visibility_policy": original.visibility_policy}) for event in batch.events]},
            deep=True,
        )
        assert replayed.append_batch(batch).committed
    tail_view = OrganizationAuthority(store=replayed).work_contribution_acceptance_view_for(organization_ref="org:inf4v:dup")
    assert full_view.acceptance_rows == tail_view.acceptance_rows
    assert full_view.source_revision_vector == tail_view.source_revision_vector
    changed = organization.accept_production_work_contribution(organization_ref="org:inf4v:dup", source_evidence_event_id=source.event_id, expected_source_stream_revision=source.stream_revision, expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:dup"), command_id="inf4v:dup:accept-changed", idempotency_key=key, causation_id="changed", correlation_id="corr")
    assert not changed.committed
    assert changed.failure and changed.failure.error_code == "organization_work_contribution_idempotency_key_reused"
    assert store.export_snapshot() == before


def test_inf4v_rejects_private_schedule_access_and_preserves_zero_write() -> None:
    store, organization, source, schedule = _prepared_case(visibility_scope="actor:character:inf4v:edge")
    before = store.export_snapshot()
    key = f"organization:production-work-contribution:org:inf4v:edge:{source.event_id}:{source.stream_revision}:{schedule.event_id}:{schedule.stream_revision}:v1"
    result = organization.accept_production_work_contribution(
        organization_ref="org:inf4v:edge",
        source_evidence_event_id=source.event_id,
        expected_source_stream_revision=source.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4v:edge:accept",
        idempotency_key=key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert not result.committed
    assert result.failure and result.failure.error_code == "organization_work_contribution_schedule_missing"
    assert store.export_snapshot() == before


def test_inf4v_rejects_facility_owned_by_another_organization() -> None:
    store, organization, source, schedule = _prepared_case(visibility_scope="organization:summary")
    before = store.export_snapshot()
    key = f"organization:production-work-contribution:org:other:{source.event_id}:{source.stream_revision}:{schedule.event_id}:{schedule.stream_revision}:v1"
    result = organization.accept_production_work_contribution(
        organization_ref="org:other",
        source_evidence_event_id=source.event_id,
        expected_source_stream_revision=source.stream_revision,
        expected_organization_stream_revision=0,
        command_id="inf4v:owner-mismatch",
        idempotency_key=key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert not result.committed
    assert result.failure and result.failure.error_code == "organization_work_contribution_facility_owner_missing"
    assert store.export_snapshot() == before


def test_inf4v_rejects_stale_source_stream_head_before_append() -> None:
    store, organization, source, schedule = _prepared_case(visibility_scope="organization:summary")
    construction = ConstructionProductionAuthority(store=store)
    # Advance the Construction stream after the completion evidence was committed.
    assert construction.settle_facility_repair(
        facility_ref="facility:inf4v:edge",
        repair_ref="repair:inf4v:edge",
        repair_amount=0.1,
        expected_revision=4,
        idempotency_key="repair:inf4v:edge",
        causation_id="cause",
        correlation_id="corr",
        source_ref="source:repair",
        submitted_at="2026-08-27T13:00:00Z",
        privacy_scope="project",
    ).committed
    before = store.export_snapshot()
    key = f"organization:production-work-contribution:org:inf4v:edge:{source.event_id}:{source.stream_revision}:{schedule.event_id}:{schedule.stream_revision}:v1"
    result = organization.accept_production_work_contribution(
        organization_ref="org:inf4v:edge",
        source_evidence_event_id=source.event_id,
        expected_source_stream_revision=source.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4v:stale-source",
        idempotency_key=key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert not result.committed
    assert result.failure and result.failure.error_code == "organization_work_contribution_source_invalid"
    assert store.export_snapshot() == before


def test_inf4w_fulfills_only_the_exact_inf4v_accepted_work_order() -> None:
    store, organization, source, schedule = _prepared_case(visibility_scope="organization:summary")
    accepted_key = f"organization:production-work-contribution:org:inf4v:edge:{source.event_id}:{source.stream_revision}:{schedule.event_id}:{schedule.stream_revision}:v1"
    accepted = organization.accept_production_work_contribution(
        organization_ref="org:inf4v:edge",
        source_evidence_event_id=source.event_id,
        expected_source_stream_revision=source.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:accept",
        idempotency_key=accepted_key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert accepted.committed
    accepted_event = store.get_event(accepted.committed_event_ids[0])
    fulfillment_key = f"organization:production-work-order-fulfillment:{accepted_event.event_id}:{accepted_event.stream_revision}:v1"

    # RED: the exact fulfillment operation is intentionally absent.
    result = organization.fulfill_production_work_order(
        organization_ref="org:inf4v:edge",
        accepted_event_id=accepted_event.event_id,
        expected_accepted_revision=accepted_event.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:fulfill",
        idempotency_key=fulfillment_key,
        causation_id="cause",
        correlation_id="corr",
    )

    assert result.committed
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.organization.work_order_fulfilled"
    assert event.visibility_policy == "organization:summary"
    assert event.payload["accepted_event_id"] == accepted_event.event_id
    assert event.payload["prior_status"] == "accepted"
    assert event.payload["next_status"] == "fulfilled"


def test_inf4w_exact_duplicate_replays_receipt_and_changed_duplicate_is_zero_write() -> None:
    store, organization, source, schedule = _prepared_case(visibility_scope="organization:summary")
    accepted_key = f"organization:production-work-contribution:org:inf4v:edge:{source.event_id}:{source.stream_revision}:{schedule.event_id}:{schedule.stream_revision}:v1"
    accepted = organization.accept_production_work_contribution(
        organization_ref="org:inf4v:edge",
        source_evidence_event_id=source.event_id,
        expected_source_stream_revision=source.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:dup:accept",
        idempotency_key=accepted_key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert accepted.committed
    accepted_event = store.get_event(accepted.committed_event_ids[0])
    key = f"organization:production-work-order-fulfillment:{accepted_event.event_id}:{accepted_event.stream_revision}:v1"
    first = organization.fulfill_production_work_order(
        organization_ref="org:inf4v:edge",
        accepted_event_id=accepted_event.event_id,
        expected_accepted_revision=accepted_event.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:dup:fulfill",
        idempotency_key=key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert first.committed
    before = store.export_snapshot()
    duplicate = organization.fulfill_production_work_order(
        organization_ref="org:inf4v:edge",
        accepted_event_id=accepted_event.event_id,
        expected_accepted_revision=accepted_event.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:dup:replay",
        idempotency_key=key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert store.export_snapshot() == before
    changed = organization.fulfill_production_work_order(
        organization_ref="org:inf4v:edge",
        accepted_event_id=accepted_event.event_id,
        expected_accepted_revision=accepted_event.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:dup:changed",
        idempotency_key=key,
        causation_id="changed",
        correlation_id="corr",
    )
    assert not changed.committed
    assert changed.failure and changed.failure.error_code == "organization_work_order_fulfillment_idempotency_key_reused"
    assert store.export_snapshot() == before


def test_inf4w_full_and_checkpoint_tail_fulfillment_projection_match() -> None:
    store, organization, source, schedule = _prepared_case(visibility_scope="organization:summary")
    accepted_key = f"organization:production-work-contribution:org:inf4v:edge:{source.event_id}:{source.stream_revision}:{schedule.event_id}:{schedule.stream_revision}:v1"
    accepted = organization.accept_production_work_contribution(
        organization_ref="org:inf4v:edge",
        source_evidence_event_id=source.event_id,
        expected_source_stream_revision=source.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:replay:accept",
        idempotency_key=accepted_key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert accepted.committed
    accepted_event = store.get_event(accepted.committed_event_ids[0])
    fulfillment_key = f"organization:production-work-order-fulfillment:{accepted_event.event_id}:{accepted_event.stream_revision}:v1"
    fulfilled = organization.fulfill_production_work_order(
        organization_ref="org:inf4v:edge",
        accepted_event_id=accepted_event.event_id,
        expected_accepted_revision=accepted_event.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:replay:fulfill",
        idempotency_key=fulfillment_key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert fulfilled.committed
    full = organization.work_order_fulfillment_view_for(organization_ref="org:inf4v:edge")

    replayed = GameplayEventStore()
    for index, original in enumerate(store.read_stream("gameplay:organization:org:inf4v:edge"), start=1):
        batch = build_atomic_event_batch(
            command_id=f"inf4w:replay:tail:{index}",
            principal_ref="actor_gameplay.organization_domain",
            stream_id=original.stream_id,
            expected_revision=replayed.get_stream_head(original.stream_id),
            event_specs=[(original.event_type, original.payload)],
            idempotency_key=f"inf4w:replay:tail:{index}",
            causation_id="replay",
            correlation_id="replay",
        ).model_copy(
            update={"events": [event.model_copy(update={"visibility_policy": original.visibility_policy}) for event in build_atomic_event_batch(
                command_id=f"inf4w:replay:tail:visibility:{index}",
                principal_ref="actor_gameplay.organization_domain",
                stream_id=original.stream_id,
                expected_revision=replayed.get_stream_head(original.stream_id),
                event_specs=[(original.event_type, original.payload)],
                idempotency_key=f"inf4w:replay:tail:visibility:{index}",
                causation_id="replay",
                correlation_id="replay",
            ).events]},
            deep=True,
        )
        assert replayed.append_batch(batch).committed
    tail = OrganizationAuthority(store=replayed).work_order_fulfillment_view_for(organization_ref="org:inf4v:edge")
    assert full.fulfillment_rows == tail.fulfillment_rows
    assert full.source_revision_vector == tail.source_revision_vector


def test_inf4w_unknown_or_stale_accepted_source_is_zero_write() -> None:
    store, organization, source, schedule = _prepared_case(visibility_scope="organization:summary")
    before = store.export_snapshot()
    unknown = organization.fulfill_production_work_order(
        organization_ref="org:inf4v:edge",
        accepted_event_id="event:missing",
        expected_accepted_revision=1,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:missing",
        idempotency_key="organization:production-work-order-fulfillment:event:missing:1:v1",
        causation_id="cause",
        correlation_id="corr",
    )
    assert not unknown.committed
    assert unknown.failure and unknown.failure.error_code == "organization_work_order_fulfillment_source_missing"
    assert store.export_snapshot() == before

    accepted_key = f"organization:production-work-contribution:org:inf4v:edge:{source.event_id}:{source.stream_revision}:{schedule.event_id}:{schedule.stream_revision}:v1"
    accepted = organization.accept_production_work_contribution(
        organization_ref="org:inf4v:edge",
        source_evidence_event_id=source.event_id,
        expected_source_stream_revision=source.stream_revision,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:stale:accept",
        idempotency_key=accepted_key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert accepted.committed
    accepted_event = store.get_event(accepted.committed_event_ids[0])
    key = f"organization:production-work-order-fulfillment:{accepted_event.event_id}:{accepted_event.stream_revision}:v1"
    stale = organization.fulfill_production_work_order(
        organization_ref="org:inf4v:edge",
        accepted_event_id=accepted_event.event_id,
        expected_accepted_revision=accepted_event.stream_revision - 1,
        expected_organization_stream_revision=store.get_stream_head("gameplay:organization:org:inf4v:edge"),
        command_id="inf4w:stale:fulfill",
        idempotency_key=key,
        causation_id="cause",
        correlation_id="corr",
    )
    assert not stale.committed
    assert stale.failure and stale.failure.error_code == "organization_work_order_fulfillment_source_invalid"
