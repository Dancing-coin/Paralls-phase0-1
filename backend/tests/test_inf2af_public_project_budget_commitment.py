from __future__ import annotations

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from test_inf1ak_public_project_step_completion import _prepared_case


def _prepared_budget_case() -> tuple[GameplayEventStore, EconomyAuthorityService, object, str]:
    store, construction, _, fulfilled_source, _ = _prepared_case()
    target_head = store.get_stream_head("gameplay:construction_production:facility:inf1ak")
    step = construction.record_public_project_step_completion(
        source_event_id=fulfilled_source.event_id,
        expected_source_revision=fulfilled_source.stream_revision,
        expected_target_stream_revision=target_head,
        command_id="inf2af:helper:step",
        idempotency_key=f"construction:public-project-step:{fulfilled_source.event_id}:{fulfilled_source.stream_revision}:0:{target_head}:v1",
        causation_id="cause:inf2af",
        correlation_id="corr:inf2af",
        submitted_at="2026-08-27T12:10:00Z",
    )
    assert step.committed
    source_event = store.get_event(step.committed_event_ids[0])
    economy = EconomyAuthorityService(store=store)
    economy_head = store.get_stream_head("gameplay:economy")
    key = f"economy:public-project-budget:{source_event.event_id}:{source_event.stream_revision}:{economy_head}:v1"
    return store, economy, source_event, key


def test_inf2af_records_one_fixed_budget_commitment_from_public_project_step() -> None:
    store, construction, _, fulfilled_source, _ = _prepared_case()
    project_target = store.get_stream_head("gameplay:construction_production:facility:inf1ak")
    step = construction.record_public_project_step_completion(
        source_event_id=fulfilled_source.event_id,
        expected_source_revision=fulfilled_source.stream_revision,
        expected_target_stream_revision=project_target,
        command_id="inf2af:project-step",
        idempotency_key=f"construction:public-project-step:{fulfilled_source.event_id}:{fulfilled_source.stream_revision}:0:{project_target}:v1",
        causation_id="cause:inf2af",
        correlation_id="corr:inf2af",
        submitted_at="2026-08-27T12:10:00Z",
    )
    assert step.committed
    source_event = store.get_event(step.committed_event_ids[0])
    economy = EconomyAuthorityService(store=store)

    # RED: the exact Economy operation is not implemented yet.
    result = economy.record_public_project_budget_commitment(
        source_event_id=source_event.event_id,
        expected_source_revision=source_event.stream_revision,
        expected_economy_stream_revision=store.get_stream_head("gameplay:economy"),
        command_id="inf2af:budget",
        idempotency_key=(
            f"economy:public-project-budget:{source_event.event_id}:{source_event.stream_revision}:"
            f"{store.get_stream_head('gameplay:economy')}:v1"
        ),
        causation_id="cause:inf2af",
        correlation_id="corr:inf2af",
        submitted_at="2026-08-27T12:11:00Z",
    )

    assert result.committed
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.economy.public_project_budget_commitment_recorded"
    assert event.visibility_policy == "authority_only"
    assert event.payload["amount_minor"] == 12
    assert event.payload["currency_ref"] == "currency:local"
    assert event.payload["status"] == "committed"


def test_inf2af_exact_duplicate_replays_receipt_and_changed_duplicate_is_zero_write() -> None:
    store, economy, source_event, key = _prepared_budget_case()
    first = economy.record_public_project_budget_commitment(
        source_event_id=source_event.event_id,
        expected_source_revision=source_event.stream_revision,
        expected_economy_stream_revision=0,
        command_id="inf2af:duplicate:first",
        idempotency_key=key,
        causation_id="cause:inf2af",
        correlation_id="corr:inf2af",
        submitted_at="2026-08-27T12:11:00Z",
    )
    assert first.committed
    before = store.export_snapshot()
    duplicate = economy.record_public_project_budget_commitment(
        source_event_id=source_event.event_id,
        expected_source_revision=source_event.stream_revision,
        expected_economy_stream_revision=0,
        command_id="inf2af:duplicate:replay",
        idempotency_key=key,
        causation_id="cause:inf2af",
        correlation_id="corr:inf2af",
        submitted_at="2026-08-27T12:11:00Z",
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert store.export_snapshot() == before
    changed = economy.record_public_project_budget_commitment(
        source_event_id=source_event.event_id,
        expected_source_revision=source_event.stream_revision,
        expected_economy_stream_revision=0,
        command_id="inf2af:duplicate:changed",
        idempotency_key=key,
        causation_id="changed",
        correlation_id="corr:inf2af",
        submitted_at="2026-08-27T12:11:00Z",
    )
    assert not changed.committed
    assert changed.failure and changed.failure.error_code == "economy_public_project_budget_idempotency_key_reused"
    assert store.export_snapshot() == before
    receipt = economy.public_project_budget_commitment_receipt_for(result=first, scope="authority")
    assert receipt.transaction_id == first.transaction_id


def test_inf2af_wrong_step_and_stale_source_are_zero_write() -> None:
    store, construction, _, fulfilled_source, _ = _prepared_case()
    target_head = store.get_stream_head("gameplay:construction_production:facility:inf1ak")
    wrong_step = construction.record_public_project_step_completion(
        source_event_id=fulfilled_source.event_id,
        expected_source_revision=fulfilled_source.stream_revision,
        expected_target_stream_revision=target_head,
        command_id="inf2af:wrong-step",
        idempotency_key=f"construction:public-project-step:{fulfilled_source.event_id}:{fulfilled_source.stream_revision}:0:{target_head}:v1",
        causation_id="cause:inf2af",
        correlation_id="corr:inf2af",
        submitted_at="2026-08-27T12:10:00Z",
    )
    assert wrong_step.committed
    source_event = store.get_event(wrong_step.committed_event_ids[0])
    economy = EconomyAuthorityService(store=store)
    before = store.export_snapshot()
    invalid = economy.record_public_project_budget_commitment(
        source_event_id=source_event.event_id,
        expected_source_revision=source_event.stream_revision - 1,
        expected_economy_stream_revision=0,
        command_id="inf2af:stale",
        idempotency_key=f"economy:public-project-budget:{source_event.event_id}:{source_event.stream_revision - 1}:0:v1",
        causation_id="cause:inf2af",
        correlation_id="corr:inf2af",
        submitted_at="2026-08-27T12:11:00Z",
    )
    assert not invalid.committed
    assert invalid.failure and invalid.failure.error_code == "economy_public_project_budget_source_invalid"
    assert store.export_snapshot() == before


def test_inf2af_projection_is_authority_only_and_replay_matches() -> None:
    store, economy, source_event, key = _prepared_budget_case()
    before_accounts = economy._projector.rebuild(store.read_events()).accounts
    result = economy.record_public_project_budget_commitment(
        source_event_id=source_event.event_id,
        expected_source_revision=source_event.stream_revision,
        expected_economy_stream_revision=0,
        command_id="inf2af:replay",
        idempotency_key=key,
        causation_id="cause:inf2af",
        correlation_id="corr:inf2af",
        submitted_at="2026-08-27T12:11:00Z",
    )
    assert result.committed
    budget_event = store.get_event(result.committed_event_ids[0])
    projection = economy.public_project_budget_commitment_projection(scope="authority")
    assert list(projection["commitments"])[0].startswith("budget-commitment:public-project")
    try:
        economy.public_project_budget_commitment_projection(scope="project")
    except Exception as exc:
        assert "scope_denied" in str(exc)
    else:
        raise AssertionError("project scope unexpectedly exposed authority budget")
    tail = economy.public_project_budget_commitment_projection(scope="authority", checkpoint_at=budget_event.global_sequence)
    assert projection["commitments"] == tail["commitments"]
    after_accounts = economy._projector.rebuild(store.read_events()).accounts
    assert before_accounts == after_accounts
