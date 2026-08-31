from __future__ import annotations

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from test_inf1ak_public_project_step_completion import _prepared_case


def _prepared_reservation_case(*, account_count: int = 1, initial_balance: int = 20):
    store, construction, _organization, fulfilled_source, _facility = _prepared_case()
    target_stream = "gameplay:construction_production:facility:inf1ak"
    target_head = store.get_stream_head(target_stream)
    step_result = construction.record_public_project_step_completion(
        source_event_id=fulfilled_source.event_id,
        expected_source_revision=fulfilled_source.stream_revision,
        expected_target_stream_revision=target_head,
        command_id="inf2ah:helper:step",
        idempotency_key=(
            f"construction:public-project-step:{fulfilled_source.event_id}:"
            f"{fulfilled_source.stream_revision}:0:{target_head}:v1"
        ),
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:00:00Z",
    )
    assert step_result.committed
    commitment_source = store.get_event(step_result.committed_event_ids[0])
    acquisition_stream = f"gameplay:construction_production:{commitment_source.payload['facility_ref']}"
    acquisition = next(
        event
        for event in store.read_stream(acquisition_stream)
        if event.event_type == "gameplay.construction_production.facility_acquired"
    )
    economy = EconomyAuthorityService(store=store)
    for index in range(account_count):
        assert economy.open_account(
            command_id=f"inf2ah:account:{index}",
            account_id=f"account:inf2ah:{index}",
            owner_ref=acquisition.payload["owner_ref"],
            currency_ref="currency:local",
            initial_balance=initial_balance,
            idempotency_key=f"inf2ah:account:{index}",
            causation_id="cause:inf2ah",
            correlation_id="corr:inf2ah",
        ).committed
    commitment_head = store.get_stream_head("gameplay:economy")
    commitment_result = economy.record_public_project_budget_commitment(
        source_event_id=commitment_source.event_id,
        expected_source_revision=commitment_source.stream_revision,
        expected_economy_stream_revision=commitment_head,
        command_id="inf2ah:commitment",
        idempotency_key=(
            f"economy:public-project-budget:{commitment_source.event_id}:"
            f"{commitment_source.stream_revision}:{commitment_head}:v1"
        ),
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:01:00Z",
    )
    assert commitment_result.committed
    commitment_event = store.get_event(commitment_result.committed_event_ids[0])
    return store, economy, commitment_event, acquisition


def test_inf2ah_reserves_exact_public_project_commitment_from_unique_owner_account() -> None:
    store, economy, commitment_event, acquisition = _prepared_reservation_case()
    expected_head = store.get_stream_head("gameplay:economy")

    result = economy.reserve_public_project_budget(
        commitment_event_id=commitment_event.event_id,
        expected_commitment_revision=commitment_event.stream_revision,
        expected_economy_stream_revision=expected_head,
        expected_acquisition_revision=acquisition.stream_revision,
        expected_facility_stream_revision=store.get_stream_head(acquisition.stream_id),
        command_id="inf2ah:reserve",
        idempotency_key=(
            f"economy:public-project-budget-reservation:{commitment_event.event_id}:"
            f"{commitment_event.stream_revision}:{acquisition.event_id}:{acquisition.stream_revision}:"
            f"{expected_head}:account:inf2ah:0:v1"
        ),
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:02:00Z",
    )

    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.economy.budget_reserved"
    assert event.visibility_policy == "authority_only"
    assert event.payload["reservation_ref"] == "reservation:public-project:workshop-bench:plot:inf1ak"
    assert event.payload["amount_minor"] == 12
    assert event.payload["account_id"] == "account:inf2ah:0"
    receipt = economy.public_project_budget_reservation_receipt_for(result=result, scope="authority")
    assert receipt.zero_write is False
    assert receipt.committed_event_ids == (event.event_id,)
    try:
        economy.public_project_budget_reservation_projection(scope="project")
    except Exception as exc:
        assert "scope_denied" in str(exc)
    else:
        raise AssertionError("project scope unexpectedly exposed authority reservation")
    projection = economy.public_project_budget_reservation_projection(scope="authority")
    assert tuple(projection["reservation_refs"]) == (event.payload["reservation_ref"],)
    tail = economy.public_project_budget_reservation_projection(
        scope="authority", checkpoint_at=event.global_sequence
    )
    assert projection == tail


def test_inf2ah_rejects_multiple_owner_accounts_without_mutation() -> None:
    store, economy, commitment_event, acquisition = _prepared_reservation_case(account_count=2)
    before = store.export_snapshot()
    head = store.get_stream_head("gameplay:economy")

    result = economy.reserve_public_project_budget(
        commitment_event_id=commitment_event.event_id,
        expected_commitment_revision=commitment_event.stream_revision,
        expected_economy_stream_revision=head,
        expected_acquisition_revision=acquisition.stream_revision,
        expected_facility_stream_revision=store.get_stream_head(acquisition.stream_id),
        command_id="inf2ah:ambiguous",
        idempotency_key="economy:public-project-budget-reservation:ambiguous",
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:02:00Z",
    )

    assert not result.committed
    assert result.failure and result.failure.error_code == "economy_public_project_budget_account_ambiguous"
    assert store.export_snapshot() == before


def test_inf2ah_exact_duplicate_replays_and_changed_duplicate_is_zero_write() -> None:
    store, economy, commitment_event, acquisition = _prepared_reservation_case()
    head = store.get_stream_head("gameplay:economy")
    key = (
        f"economy:public-project-budget-reservation:{commitment_event.event_id}:"
        f"{commitment_event.stream_revision}:{acquisition.event_id}:{acquisition.stream_revision}:"
        f"{head}:account:inf2ah:0:v1"
    )
    request = {
        "commitment_event_id": commitment_event.event_id,
        "expected_commitment_revision": commitment_event.stream_revision,
        "expected_economy_stream_revision": head,
        "expected_acquisition_revision": acquisition.stream_revision,
        "expected_facility_stream_revision": store.get_stream_head(acquisition.stream_id),
        "command_id": "inf2ah:duplicate:first",
        "idempotency_key": key,
        "causation_id": "cause:inf2ah",
        "correlation_id": "corr:inf2ah",
        "submitted_at": "2026-08-27T13:02:00Z",
    }
    first = economy.reserve_public_project_budget(**request)
    assert first.committed
    before = store.export_snapshot()
    duplicate = economy.reserve_public_project_budget(**{**request, "command_id": "inf2ah:duplicate:replay"})
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert store.export_snapshot() == before
    changed = economy.reserve_public_project_budget(**{**request, "correlation_id": "corr:inf2ah:changed"})
    assert not changed.committed
    assert changed.failure and changed.failure.error_code == "economy_public_project_budget_reservation_idempotency_key_reused"
    assert store.export_snapshot() == before


def test_inf2ah_missing_account_and_insufficient_funds_are_zero_write() -> None:
    store, economy, commitment_event, acquisition = _prepared_reservation_case(account_count=0)
    before = store.export_snapshot()
    head = store.get_stream_head("gameplay:economy")
    result = economy.reserve_public_project_budget(
        commitment_event_id=commitment_event.event_id,
        expected_commitment_revision=commitment_event.stream_revision,
        expected_economy_stream_revision=head,
        expected_acquisition_revision=acquisition.stream_revision,
        expected_facility_stream_revision=store.get_stream_head(acquisition.stream_id),
        command_id="inf2ah:missing-account",
        idempotency_key="economy:public-project-budget-reservation:missing-account",
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:02:00Z",
    )
    assert not result.committed
    assert result.failure and result.failure.error_code == "economy_public_project_budget_reservation_account_missing"
    assert store.export_snapshot() == before

    store2, economy2, commitment2, acquisition2 = _prepared_reservation_case(initial_balance=1)
    before2 = store2.export_snapshot()
    head2 = store2.get_stream_head("gameplay:economy")
    result2 = economy2.reserve_public_project_budget(
        commitment_event_id=commitment2.event_id,
        expected_commitment_revision=commitment2.stream_revision,
        expected_economy_stream_revision=head2,
        expected_acquisition_revision=acquisition2.stream_revision,
        expected_facility_stream_revision=store2.get_stream_head(acquisition2.stream_id),
        command_id="inf2ah:insufficient",
        idempotency_key="economy:public-project-budget-reservation:insufficient",
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:02:00Z",
    )
    assert not result2.committed
    assert result2.failure and result2.failure.error_code == "economy_public_project_budget_reservation_insufficient_funds"
    assert store2.export_snapshot() == before2


def test_inf2ah_stale_economy_or_facility_revision_is_zero_write() -> None:
    store, economy, commitment_event, acquisition = _prepared_reservation_case()
    before = store.export_snapshot()
    head = store.get_stream_head("gameplay:economy")
    key = "economy:public-project-budget-reservation:stale"
    stale_economy = economy.reserve_public_project_budget(
        commitment_event_id=commitment_event.event_id,
        expected_commitment_revision=commitment_event.stream_revision,
        expected_economy_stream_revision=head - 1,
        expected_acquisition_revision=acquisition.stream_revision,
        expected_facility_stream_revision=store.get_stream_head(acquisition.stream_id),
        command_id="inf2ah:stale-economy",
        idempotency_key=key,
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:02:00Z",
    )
    assert not stale_economy.committed
    assert stale_economy.failure and stale_economy.failure.error_code == "economy_public_project_budget_reservation_revision_conflict"
    assert store.export_snapshot() == before

    stale_facility = economy.reserve_public_project_budget(
        commitment_event_id=commitment_event.event_id,
        expected_commitment_revision=commitment_event.stream_revision,
        expected_economy_stream_revision=head,
        expected_acquisition_revision=acquisition.stream_revision,
        expected_facility_stream_revision=store.get_stream_head(acquisition.stream_id) - 1,
        command_id="inf2ah:stale-facility",
        idempotency_key="economy:public-project-budget-reservation:stale-facility",
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:02:00Z",
    )
    assert not stale_facility.committed
    assert stale_facility.failure and stale_facility.failure.error_code == "economy_public_project_budget_reservation_acquisition_invalid"
    assert store.export_snapshot() == before


def test_inf2ah_checkpoint_tail_replay_includes_reservation_after_checkpoint() -> None:
    store, economy, commitment_event, acquisition = _prepared_reservation_case()
    expected_head = store.get_stream_head("gameplay:economy")
    result = economy.reserve_public_project_budget(
        commitment_event_id=commitment_event.event_id,
        expected_commitment_revision=commitment_event.stream_revision,
        expected_economy_stream_revision=expected_head,
        expected_acquisition_revision=acquisition.stream_revision,
        expected_facility_stream_revision=store.get_stream_head(acquisition.stream_id),
        command_id="inf2ah:checkpoint-tail",
        idempotency_key=(
            f"economy:public-project-budget-reservation:{commitment_event.event_id}:"
            f"{commitment_event.stream_revision}:{acquisition.event_id}:{acquisition.stream_revision}:"
            f"{expected_head}:account:inf2ah:0:v1"
        ),
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:03:00Z",
    )
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    full = economy.public_project_budget_reservation_projection(scope="authority")
    tail = economy.public_project_budget_reservation_projection(
        scope="authority", checkpoint_at=commitment_event.global_sequence
    )
    assert event.global_sequence > commitment_event.global_sequence
    assert full == tail


def test_inf2ah_projector_rejects_forged_commitment_or_acquisition_provenance() -> None:
    store, economy, commitment_event, _acquisition = _prepared_reservation_case()
    head = store.get_stream_head("gameplay:economy")
    result = economy.reserve_public_project_budget(
        commitment_event_id=commitment_event.event_id,
        expected_commitment_revision=commitment_event.stream_revision,
        expected_economy_stream_revision=head,
        expected_acquisition_revision=1,
        expected_facility_stream_revision=store.get_stream_head("gameplay:construction_production:facility:inf1ak"),
        command_id="inf2ah:provenance",
        idempotency_key=(
            f"economy:public-project-budget-reservation:{commitment_event.event_id}:"
            f"{commitment_event.stream_revision}:{next(event.event_id for event in store.read_stream(commitment_event.payload['source_stream_id']) if event.event_type == 'gameplay.construction_production.facility_acquired')}:1:{head}:account:inf2ah:0:v1"
        ),
        causation_id="cause:inf2ah",
        correlation_id="corr:inf2ah",
        submitted_at="2026-08-27T13:03:00Z",
    )
    assert result.committed
    reservation_event = next(event for event in store.read_events() if event.event_id == result.committed_event_ids[0])
    reservation_event.payload["source_commitment_event_id"] = "event:forged"
    try:
        economy._projector.rebuild([*store.read_events()[:-1], reservation_event])
    except Exception as exc:
        assert "economy_public_project_budget_reservation_source_invalid" in str(exc)
    else:
        raise AssertionError("forged reservation provenance unexpectedly replayed")
