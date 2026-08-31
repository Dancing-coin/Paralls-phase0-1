from __future__ import annotations

import pytest

from app.gameplay.closed_generic_gameplay_families import (
    BOUNDED_PROJECT_BUDGET_BLOCKER,
    BoundedProjectBudgetCloseIntent,
    BoundedProjectBudgetConsumptionIntent,
    BoundedProjectBudgetIntent,
    BoundedProjectBudgetProjectStepIntent,
    BoundedProjectBudgetReservationIntent,
)
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from closed_generic_manifest_fixtures import load_manifest
from test_inf2af_public_project_budget_commitment import _prepared_budget_case
from test_inf1ak_public_project_step_completion import _prepared_case


def _activated_budget_registry(*keys: str) -> GameplayPatchRegistry:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifests = tuple(load_manifest(key) for key in keys)
    registry.install_many(manifests)
    registry.activate(tuple(manifest.patch_revision_id for manifest in manifests))
    return registry


def test_bounded_project_budget_derives_fixed_amount_currency_and_project_from_source() -> None:
    store, economy, source, _ = _prepared_budget_case()

    result = economy.settle_bounded_project_budget(
        intent=BoundedProjectBudgetIntent(
            source_event_id=source.event_id,
            command_id="command:bounded-budget",
            correlation_id="corr:bounded-budget",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )

    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["family_ref"] == "bounded_project_budget@1"
    assert event.payload["amount_minor"] == 12
    assert event.payload["currency_ref"] == "currency:local"
    assert event.payload["project_ref"] == source.payload["project_ref"]


def test_bounded_project_budget_replays_duplicate_and_rejects_changed_duplicate() -> None:
    store, economy, source, _ = _prepared_budget_case()
    intent = BoundedProjectBudgetIntent(
        source_event_id=source.event_id,
        command_id="command:bounded-budget",
        correlation_id="corr:bounded-budget",
        submitted_at="2026-08-30T00:00:00Z",
    )
    first = economy.settle_bounded_project_budget(intent=intent)
    before = tuple(store.read_events())
    duplicate = economy.settle_bounded_project_budget(intent=intent)
    changed = economy.settle_bounded_project_budget(intent=intent.model_copy(update={"correlation_id": "corr:changed"}))

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed and changed.failure is not None
    assert tuple(store.read_events()) == before


def test_bounded_project_budget_intent_rejects_caller_amount_currency_account_and_stream() -> None:
    with pytest.raises(Exception):
        BoundedProjectBudgetIntent.model_validate(
            {
                "source_event_id": "event:project-step",
                "command_id": "command:budget",
                "correlation_id": "corr:budget",
                "submitted_at": "2026-08-30T00:00:00Z",
                "amount": 99,
                "currency_ref": "currency:caller",
                "account_id": "account:caller",
                "stream_id": "gameplay:caller",
            }
        )


def test_bounded_project_budget_reservation_wrapper_derives_all_authority_coordinates() -> None:
    from test_inf2ah_public_project_budget_reservation import _prepared_reservation_case

    store, economy, commitment, _acquisition = _prepared_reservation_case()
    result = economy.settle_bounded_project_budget_reservation(
        intent=BoundedProjectBudgetReservationIntent(
            commitment_event_id=commitment.event_id,
            command_id="command:bounded-budget-reservation",
            causation_id=commitment.event_id,
            correlation_id="corr:bounded-budget-reservation",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.economy.budget_reserved"
    assert event.payload["family_ref"] == "bounded_project_budget@1"
    assert event.payload["amount_minor"] == 12
    assert event.payload["currency_ref"] == "currency:local"
    assert event.payload["project_ref"] == commitment.payload["project_ref"]


def test_bounded_project_budget_consumption_wrapper_replays_and_changed_duplicate_is_zero_write() -> None:
    from test_inf2ai_public_project_budget_consumption import (
        _prepared_consumption_case,
    )

    store, economy, commitment, reservation, activity = _prepared_consumption_case()
    intent = BoundedProjectBudgetConsumptionIntent(
        commitment_event_id=commitment.event_id,
        reservation_event_id=reservation.event_id,
        activity_event_id=activity.event_id,
        command_id="command:bounded-budget-consumption",
        causation_id=activity.event_id,
        correlation_id="corr:bounded-budget-consumption",
        submitted_at="2026-08-30T00:00:00Z",
    )
    first = economy.settle_bounded_project_budget_consumption(intent=intent)
    assert first.committed, first.failure
    before = store.export_snapshot()
    duplicate = economy.settle_bounded_project_budget_consumption(intent=intent)
    changed = economy.settle_bounded_project_budget_consumption(
        intent=intent.model_copy(update={"correlation_id": "corr:changed"})
    )

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert store.export_snapshot() == before


def test_bounded_project_budget_close_wrapper_derives_execution_binding_and_rejects_coordinates() -> None:
    from test_inf2ak_public_project_budget_close import _prepared_close_case

    store, economy, consumed, execution = _prepared_close_case()
    result = economy.settle_bounded_project_budget_close(
        intent=BoundedProjectBudgetCloseIntent(
            budget_consumed_event_id=consumed.event_id,
            execution_event_id=execution.event_id,
            command_id="command:bounded-budget-close",
            causation_id=execution.event_id,
            correlation_id="corr:bounded-budget-close",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.economy.public_project_budget_closed"
    assert event.payload["family_ref"] == "bounded_project_budget@1"
    assert event.payload["project_ref"] == consumed.payload["project_ref"]
    assert event.payload["facility_ref"] == consumed.payload["facility_ref"]

    with pytest.raises(Exception):
        BoundedProjectBudgetCloseIntent.model_validate(
            {
                "budget_consumed_event_id": consumed.event_id,
                "execution_event_id": execution.event_id,
                "command_id": "command:bounded-budget-close-forged",
                "causation_id": execution.event_id,
                "correlation_id": "corr:bounded-budget-close-forged",
                "submitted_at": "2026-08-30T00:00:00Z",
                "project_ref": "plot:caller",
                "amount_minor": 999,
                "currency_ref": "currency:caller",
                "stream_id": "gameplay:caller",
            }
        )


def test_bounded_project_budget_blocker_records_the_single_project_budget_row() -> None:
    assert BOUNDED_PROJECT_BUDGET_BLOCKER.family_ref == "bounded_project_budget@1"
    assert any("12" in value and "currency:local" in value for value in BOUNDED_PROJECT_BUDGET_BLOCKER.candidate_values)
    assert BOUNDED_PROJECT_BUDGET_BLOCKER.source_refs
    assert BOUNDED_PROJECT_BUDGET_BLOCKER.recommended_decision


def test_bounded_project_budget_blocker_records_the_full_inf2_source_chain_and_manifests() -> None:
    assert BOUNDED_PROJECT_BUDGET_BLOCKER.candidate_values == (
        "commitment: fixed one municipal public-project step commitment on project-step:public-project:workshop-bench@1",
        "reservation: fixed one owner-derived currency:local account reservation on the same municipal chain",
        "consumption: fixed one authority-only consumed marker from INF-4AG plus INF-2AH",
        "close: fixed one authority-only terminal close marker from INF-2AI plus INF-4AJ",
        "amount/currency: hard-coded at 12 currency:local with no second admitted budget content instance",
    )
    assert BOUNDED_PROJECT_BUDGET_BLOCKER.source_refs == (
        "backend/app/gameplay/economy_runtime.py:settle_bounded_project_budget",
        "backend/tests/test_inf2af_public_project_budget_commitment.py:test_inf2af_records_one_fixed_budget_commitment_from_public_project_step",
        "backend/tests/test_inf2ah_public_project_budget_reservation.py:test_inf2ah_reserves_exact_public_project_commitment_from_unique_owner_account",
        "backend/tests/test_inf2ai_public_project_budget_consumption.py:test_inf2ai_consumes_one_reserved_public_project_budget_from_completed_activity",
        "backend/tests/test_inf2ak_public_project_budget_close.py:test_inf2ak_closes_consumed_budget_after_matching_project_execution",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-27-inf-2af-public-project-budget-commitment-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-27-inf-2ah-public-project-budget-reservation-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-28-inf-2ai-public-project-budget-consumption-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-28-inf-2ak-public-project-budget-close-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v5-public-workshop-session.manifest.json",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v6-public-milling-session.manifest.json",
    )


def test_bounded_project_budget_manifests_are_immutable_and_activation_pins_both_bindings() -> None:
    workshop = load_manifest("bounded-project-budget-workshop-v1")
    maintenance = load_manifest("bounded-project-budget-maintenance-v1")

    assert workshop.content_digest == workshop.expected_content_digest()
    assert maintenance.content_digest == maintenance.expected_content_digest()
    assert workshop.content_digest != maintenance.content_digest
    assert workshop.platform_extension is not None
    assert maintenance.platform_extension is not None
    assert len(workshop.platform_extension.package_definitions) == 1
    assert len(maintenance.platform_extension.package_definitions) == 1
    assert (
        workshop.platform_extension.package_definitions[0].typed_content["source_project_step_ref"]
        != maintenance.platform_extension.package_definitions[0].typed_content["source_project_step_ref"]
    )

    registry = _activated_budget_registry(
        "bounded-project-budget-workshop-v1",
        "bounded-project-budget-maintenance-v1",
    )
    active = registry.active_patch_set
    assert active is not None
    assert len(active.capability_bindings) == 2
    assert {
        (binding.package_revision, binding.content_digest, binding.declaration_digest)
        for binding in active.capability_bindings
    } == {
        (
            manifest.patch_revision_id,
            manifest.content_digest,
            manifest.platform_extension.outcome_declarations[0].declaration_digest,
        )
        for manifest in (workshop, maintenance)
    }


def test_bounded_project_budget_construction_adapter_accepts_maintenance_source_and_replays() -> None:
    store, _construction, _organization, fulfilled_source, _facility = _prepared_case(
        work_order_ref="work-order:public-project:maintenance@1"
    )
    registry = _activated_budget_registry("bounded-project-budget-maintenance-v1")
    construction = ConstructionProductionAuthority(store=store, package_registry=registry)
    target_stream = "gameplay:construction_production:facility:inf1ak"
    target_head = store.get_stream_head(target_stream)
    intent = BoundedProjectBudgetProjectStepIntent(
        source_event_id=fulfilled_source.event_id,
        expected_source_revision=fulfilled_source.stream_revision,
        expected_target_stream_revision=target_head,
        command_id="bounded-budget:maintenance:step",
        idempotency_key=(
            f"construction:bounded-project-budget-step:{fulfilled_source.event_id}:"
            f"{fulfilled_source.stream_revision}:{target_head}:v1"
        ),
        causation_id=fulfilled_source.event_id,
        correlation_id="bounded-budget:maintenance:step",
        submitted_at="2026-08-30T00:00:00Z",
    )

    first = construction.settle_bounded_project_budget_project_step(intent=intent)
    assert first.committed, first.failure
    event = store.get_event(first.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.public_project_step_completed"
    assert event.visibility_policy == "project"
    assert event.payload["project_step_ref"] == "project-step:public-project:maintenance@1"
    assert event.payload["source_work_order_ref"] == "work-order:public-project:maintenance@1"
    assert event.payload["family_ref"] == "bounded_project_budget@1"
    assert event.payload["package_revision"] == load_manifest(
        "bounded-project-budget-maintenance-v1"
    ).patch_revision_id

    before = store.export_snapshot()
    duplicate = construction.settle_bounded_project_budget_project_step(intent=intent)
    changed = construction.settle_bounded_project_budget_project_step(
        intent=intent.model_copy(update={"correlation_id": "bounded-budget:changed"})
    )
    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert store.export_snapshot() == before


def test_bounded_project_budget_economy_adapter_derives_maintenance_content_and_project() -> None:
    store, _construction, _organization, fulfilled_source, _facility = _prepared_case(
        work_order_ref="work-order:public-project:maintenance@1"
    )
    registry = _activated_budget_registry("bounded-project-budget-maintenance-v1")
    construction = ConstructionProductionAuthority(store=store, package_registry=registry)
    target_stream = "gameplay:construction_production:facility:inf1ak"
    step = construction.settle_bounded_project_budget_project_step(
        intent=BoundedProjectBudgetProjectStepIntent(
            source_event_id=fulfilled_source.event_id,
            expected_source_revision=fulfilled_source.stream_revision,
            expected_target_stream_revision=store.get_stream_head(target_stream),
            command_id="bounded-budget:maintenance:step",
            idempotency_key=(
                f"construction:bounded-project-budget-step:{fulfilled_source.event_id}:"
                f"{fulfilled_source.stream_revision}:{store.get_stream_head(target_stream)}:v1"
            ),
            causation_id=fulfilled_source.event_id,
            correlation_id="bounded-budget:maintenance:step",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )
    assert step.committed, step.failure
    source = store.get_event(step.committed_event_ids[0])

    from app.gameplay.economy_runtime import EconomyAuthorityService

    economy = EconomyAuthorityService(store=store, package_registry=registry)
    result = economy.settle_bounded_project_budget(
        intent=BoundedProjectBudgetIntent(
            source_event_id=source.event_id,
            command_id="bounded-budget:maintenance:economy",
            correlation_id="bounded-budget:maintenance:economy",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )
    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    content = load_manifest("bounded-project-budget-maintenance-v1").platform_extension.package_definitions[0].typed_content
    assert event.payload["family_ref"] == "bounded_project_budget@1"
    assert event.payload["amount_minor"] == content["amount"]
    assert event.payload["currency_ref"] == content["currency_ref"]
    assert event.payload["project_ref"] == source.payload["project_ref"]
    assert event.payload["project_step_ref"] == content["source_project_step_ref"]
    assert event.payload["package_revision"] == load_manifest(
        "bounded-project-budget-maintenance-v1"
    ).patch_revision_id

    before = store.export_snapshot()
    duplicate = economy.settle_bounded_project_budget(
        intent=BoundedProjectBudgetIntent(
            source_event_id=source.event_id,
            command_id="bounded-budget:maintenance:economy-replay",
            correlation_id="bounded-budget:maintenance:economy",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )
    changed = economy.settle_bounded_project_budget(
        intent=BoundedProjectBudgetIntent(
            source_event_id=source.event_id,
            command_id="bounded-budget:maintenance:economy-changed",
            correlation_id="bounded-budget:maintenance:changed",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )
    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == result.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert store.export_snapshot() == before


@pytest.mark.parametrize(
    ("package_key", "work_order_ref", "expected_amount"),
    (
        ("bounded-project-budget-workshop-v1", "work-order:public-project:workshop-bench@1", 12),
        ("bounded-project-budget-maintenance-v1", "work-order:public-project:maintenance@1", 7),
    ),
)
def test_bounded_project_budget_completes_each_admitted_content_lifecycle(
    package_key: str, work_order_ref: str, expected_amount: int
) -> None:
    store, _construction, _organization, fulfilled_source, facility = _prepared_case(
        work_order_ref=work_order_ref
    )
    registry = _activated_budget_registry(package_key)
    construction = ConstructionProductionAuthority(store=store, package_registry=registry)
    target_stream = f"gameplay:construction_production:{facility.facility_ref}"
    step = construction.settle_bounded_project_budget_project_step(
        intent=BoundedProjectBudgetProjectStepIntent(
            source_event_id=fulfilled_source.event_id,
            expected_source_revision=fulfilled_source.stream_revision,
            expected_target_stream_revision=store.get_stream_head(target_stream),
            command_id=f"bounded-budget:{package_key}:lifecycle-step",
            idempotency_key=(
                f"construction:bounded-project-budget-step:{fulfilled_source.event_id}:"
                f"{fulfilled_source.stream_revision}:{store.get_stream_head(target_stream)}:v1"
            ),
            causation_id=fulfilled_source.event_id,
            correlation_id=f"bounded-budget:{package_key}:lifecycle",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )
    assert step.committed, step.failure
    step_event = store.get_event(step.committed_event_ids[0])
    from app.gameplay.economy_runtime import EconomyAuthorityService

    economy = EconomyAuthorityService(store=store, package_registry=registry)
    assert economy.open_account(
        command_id=f"bounded-budget:{package_key}:account",
        account_id=f"account:bounded-budget:{package_key}",
        owner_ref="org:inf1ak",
        currency_ref="currency:local",
        initial_balance=20,
        idempotency_key=f"bounded-budget:{package_key}:account",
        causation_id=step_event.event_id,
        correlation_id=f"bounded-budget:{package_key}:lifecycle",
    ).committed
    commitment = economy.settle_bounded_project_budget(
        intent=BoundedProjectBudgetIntent(
            source_event_id=step_event.event_id,
            command_id=f"bounded-budget:{package_key}:commitment",
            correlation_id=f"bounded-budget:{package_key}:lifecycle",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )
    assert commitment.committed, commitment.failure
    commitment_event = store.get_event(commitment.committed_event_ids[0])
    reservation = economy.settle_bounded_project_budget_reservation(
        intent=BoundedProjectBudgetReservationIntent(
            commitment_event_id=commitment_event.event_id,
            command_id=f"bounded-budget:{package_key}:reservation",
            causation_id=commitment_event.event_id,
            correlation_id=f"bounded-budget:{package_key}:lifecycle",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )
    assert reservation.committed, reservation.failure
    reservation_event = store.get_event(reservation.committed_event_ids[0])
    consumption = economy.settle_bounded_project_budget_consumption(
        intent=BoundedProjectBudgetConsumptionIntent(
            commitment_event_id=commitment_event.event_id,
            reservation_event_id=reservation_event.event_id,
            activity_event_id=step_event.event_id,
            command_id=f"bounded-budget:{package_key}:consumption",
            causation_id=step_event.event_id,
            correlation_id=f"bounded-budget:{package_key}:lifecycle",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )
    assert consumption.committed, consumption.failure
    consumed_event = store.get_event(consumption.committed_event_ids[0])
    closed = economy.settle_bounded_project_budget_close(
        intent=BoundedProjectBudgetCloseIntent(
            budget_consumed_event_id=consumed_event.event_id,
            execution_event_id=step_event.event_id,
            command_id=f"bounded-budget:{package_key}:close",
            causation_id=step_event.event_id,
            correlation_id=f"bounded-budget:{package_key}:lifecycle",
            submitted_at="2026-08-30T00:00:00Z",
        )
    )
    assert closed.committed, closed.failure
    commitment_view = economy.public_project_budget_commitment_projection(scope="authority")
    reservation_view = economy.public_project_budget_reservation_projection(scope="authority")
    consumption_view = economy.public_project_budget_consumption_projection(scope="authority")
    close_view = economy.public_project_budget_close_projection(scope="authority")
    assert any(row["amount_minor"] == expected_amount for row in commitment_view["commitments"].values())
    assert reservation_view["reservation_refs"]
    assert consumption_view["consumption_refs"]
    assert close_view["closure_refs"]
    assert commitment_view == economy.public_project_budget_commitment_projection(scope="authority", checkpoint_at=step_event.global_sequence)
    assert reservation_view == economy.public_project_budget_reservation_projection(scope="authority", checkpoint_at=step_event.global_sequence)
    assert consumption_view == economy.public_project_budget_consumption_projection(scope="authority", checkpoint_at=step_event.global_sequence)
    assert close_view == economy.public_project_budget_close_projection(scope="authority", checkpoint_at=step_event.global_sequence)
    economy._projector.rebuild(store.read_events())
