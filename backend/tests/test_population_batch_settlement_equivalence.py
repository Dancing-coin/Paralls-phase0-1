from __future__ import annotations

from app.gameplay.econ1_economy_runtime import OperatingWindow
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayFailure
from app.gameplay.organization_government_runtime import OrganizationAuthority, OperatingWindowDueRequest
from app.population_continuity.owner_adapters import (
    OrganizationOperatingWindowDueOwnerExecutor,
)
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationProjection,
    PopulationReadSet,
)
from app.services.siming_population_capability import PopulationSimulationCapability


def _cadence() -> PopulationCadenceInput:
    return PopulationCadenceInput(
        cadence_id="cadence:owner-batch:1",
        world_ref="world:batch",
        world_mode_ref="mode:batch",
        world_mode_revision="mode:batch@1",
        cadence_source_ref="world:batch",
        cadence_source_revision=4,
        window_start=10,
        window_end=20,
        base_checkpoint_ref="checkpoint:batch:1",
        base_checkpoint_digest="sha256:batch",
        base_revision_vector={"world:batch": 4},
        policy_revision="policy:population:v1",
        selector_revision="selector:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed="seed:batch:1",
        catch_up_limit=4,
        budget=4,
        report_scope="organization:summary",
    )


def _closed_window(authority: OrganizationAuthority, suffix: str) -> tuple[str, str]:
    organization_ref = f"org:{suffix}"
    window_ref = f"window:{suffix}"
    assert authority.open_operating_window(
        command_id=f"command:{suffix}:open",
        idempotency_key=f"window:{suffix}:open",
        causation_id=f"cause:{suffix}:open",
        correlation_id=f"corr:{suffix}",
        window=OperatingWindow(
            window_ref=window_ref,
            organization_ref=organization_ref,
            opens_at_tick=1,
            closes_at_tick=5,
            policy_revision="policy:window:1",
            source_revision="schedule:1",
        ),
        visibility_scope="project",
    ).committed
    assert authority.close_operating_window(
        command_id=f"command:{suffix}:close",
        idempotency_key=f"window:{suffix}:close",
        causation_id=f"cause:{suffix}:close",
        correlation_id=f"corr:{suffix}",
        organization_ref=organization_ref,
        window_ref=window_ref,
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed
    return organization_ref, window_ref


def _read_set(*windows: tuple[str, str], stale_window: str = "") -> PopulationReadSet:
    cadence = _cadence()
    projections = tuple(
        PopulationProjection(
            ref=f"projection:{window_ref}",
            scope="organization:summary",
            revision_vector={
                f"gameplay:organization:window:{window_ref}": (
                    1 if window_ref == stale_window else 2
                )
            },
            payload={
                "actor_ref": f"character:{organization_ref.removeprefix('org:')}",
                "candidate_kind": "organization_operating_window_due",
                "fidelity_tier": "B1",
                "source_domain": "organization",
                "intent_kind": "operating_window_due",
                "stream_ref": f"gameplay:organization:window:{window_ref}",
                "organization_ref": organization_ref,
                "window_ref": window_ref,
            },
        )
        for organization_ref, window_ref in windows
    )
    return PopulationReadSet.from_inputs(cadence, projections)


def _capability(authority: OrganizationAuthority) -> PopulationSimulationCapability:
    return PopulationSimulationCapability(
        owner_executors={
            "population:organization-window-due:v1": (
                OrganizationOperatingWindowDueOwnerExecutor(authority=authority)
            )
        }
    )


def _due_request(suffix: str, *, idempotency_key: str | None = None) -> OperatingWindowDueRequest:
    return OperatingWindowDueRequest(
        command_id=f"candidate:organization_operating_window_due:character:{suffix}:projection:window:{suffix}",
        idempotency_key=idempotency_key or f"candidate:organization_operating_window_due:character:{suffix}:projection:window:{suffix}",
        causation_id="cadence:owner-batch:1",
        correlation_id="cadence:owner-batch:1",
        organization_ref=f"org:{suffix}",
        window_ref=f"window:{suffix}",
        expected_stream_revision=2,
        visibility_scope="project",
    )


def test_disjoint_operating_windows_commit_in_one_real_owner_batch() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    windows = (_closed_window(authority, "alpha"), _closed_window(authority, "beta"))
    before_transactions = len(store.read_transactions())

    result = _capability(authority).run_default_decision_cycle(
        _cadence(), _read_set(*windows)
    )

    assert result.status == "accepted"
    assert result.production_append_count == 1
    assert len(result.owner_receipts) == 2
    assert all(receipt.settlement_status == "committed" for receipt in result.owner_receipts)
    assert len(store.read_transactions()) == before_transactions + 1
    committed_batch = store.read_transactions()[-1]
    assert len(committed_batch.events) == 2
    assert len(committed_batch.owner_fragments) == 2
    assert [event.stream_id for event in committed_batch.events] == sorted(
        event.stream_id for event in committed_batch.events
    )


def test_owner_batch_returns_only_each_intents_global_sequence() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    for suffix in ("alpha", "beta"):
        _closed_window(authority, suffix)

    result = authority.record_operating_windows_due_batch(
        tuple(_due_request(suffix) for suffix in ("alpha", "beta"))
    )

    sequence_ranges = {
        item.global_sequence_range for item in result.results.values()
    }
    assert len(sequence_ranges) == 2
    assert all(value is not None and value[0] == value[1] for value in sequence_ranges)


def test_invalid_window_is_rejected_without_swallowing_disjoint_valid_window() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    alpha = _closed_window(authority, "alpha")
    beta = _closed_window(authority, "beta")
    before_transactions = len(store.read_transactions())

    result = _capability(authority).run_default_decision_cycle(
        _cadence(), _read_set(alpha, beta, stale_window=beta[1])
    )

    assert result.status == "requeue"
    assert result.production_append_count == 1
    by_actor = {receipt.receipt_ref: receipt for receipt in result.owner_receipts}
    assert any(receipt.settlement_status == "committed" for receipt in by_actor.values())
    assert any(receipt.settlement_status == "requeue" for receipt in by_actor.values())
    assert len(store.read_transactions()) == before_transactions + 1
    assert store.get_stream_head(f"gameplay:organization:window:{alpha[1]}") == 3
    assert store.get_stream_head(f"gameplay:organization:window:{beta[1]}") == 2


def test_owner_batch_duplicate_replay_is_zero_write_per_actor() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    windows = (_closed_window(authority, "alpha"), _closed_window(authority, "beta"))
    capability = _capability(authority)
    read_set = _read_set(*windows)

    first = capability.run_default_decision_cycle(_cadence(), read_set)
    replay = capability.run_default_decision_cycle(_cadence(), read_set)

    assert first.production_append_count == 1
    assert replay.production_append_count == 0
    assert all(receipt.settlement_status == "duplicate" for receipt in replay.owner_receipts)
    assert all(receipt.zero_write for receipt in replay.owner_receipts)
    assert len(store.read_transactions()) == 5


def test_batched_intent_replays_after_cohort_membership_changes() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    for suffix in ("alpha", "beta", "gamma"):
        _closed_window(authority, suffix)
    first = authority.record_operating_windows_due_batch(
        (_due_request("alpha"), _due_request("beta"))
    )
    store = GameplayEventStore.from_snapshot(store.export_snapshot())
    authority = OrganizationAuthority(store=store)
    before_retry = len(store.read_transactions())

    retry = authority.record_operating_windows_due_batch(
        (_due_request("alpha"), _due_request("gamma"))
    )

    assert first.append_count == 1
    assert retry.append_count == 1
    assert retry.results[_due_request("alpha").command_id].idempotency_status == "duplicate_replayed"
    assert retry.results[_due_request("gamma").command_id].idempotency_status == "new_commit"
    assert len(store.read_transactions()) == before_retry + 1


def test_batch_rejects_existing_single_idempotency_key_with_changed_payload() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    for suffix in ("alpha", "beta"):
        _closed_window(authority, suffix)
    first = _due_request("alpha", idempotency_key="window-due:shared")
    committed = authority.record_operating_window_due(
        **first.model_dump()
    )
    changed = _due_request("beta", idempotency_key="window-due:shared")

    retry = authority.record_operating_windows_due_batch((changed,))

    assert committed.committed
    assert retry.append_count == 0
    changed_result = retry.results[changed.command_id]
    assert not changed_result.committed
    assert changed_result.failure is not None
    assert changed_result.failure.error_code == "idempotency_key_reused"


def test_owner_batch_matches_ordered_single_owner_results() -> None:
    batch_store = GameplayEventStore()
    batch_authority = OrganizationAuthority(store=batch_store)
    batch_windows = (
        _closed_window(batch_authority, "alpha"),
        _closed_window(batch_authority, "beta"),
    )
    batch_result = _capability(batch_authority).run_default_decision_cycle(
        _cadence(), _read_set(*batch_windows)
    )

    single_store = GameplayEventStore()
    single_authority = OrganizationAuthority(store=single_store)
    single_windows = (
        _closed_window(single_authority, "alpha"),
        _closed_window(single_authority, "beta"),
    )
    single_results = tuple(
        _capability(single_authority).run_default_decision_cycle(
            _cadence(), _read_set(window)
        )
        for window in single_windows
    )

    assert batch_result.production_append_count == 1
    assert sum(item.production_append_count for item in single_results) == 2
    assert sorted(
        (receipt.settlement_status, tuple(sorted(receipt.revision_vector.items())))
        for receipt in batch_result.owner_receipts
    ) == sorted(
        (receipt.settlement_status, tuple(sorted(receipt.revision_vector.items())))
        for item in single_results
        for receipt in item.owner_receipts
    )
    batch_due = sorted(
        (event.stream_id, event.event_type, event.payload)
        for event in batch_store.read_events()
        if event.event_type == "gameplay.organization.operating_window_due_recorded"
    )
    single_due = sorted(
        (event.stream_id, event.event_type, event.payload)
        for event in single_store.read_events()
        if event.event_type == "gameplay.organization.operating_window_due_recorded"
    )
    assert batch_due == single_due


def test_owner_batch_append_failure_rolls_back_every_valid_stream() -> None:
    class FailingBatchStore(GameplayEventStore):
        def append_batch(self, payload):
            if hasattr(payload, "owner_fragments") and len(payload.owner_fragments) == 2:
                return AppendBatchResult(
                    committed=False,
                    transaction_id=payload.transaction_id,
                    command_id=payload.command_id,
                    idempotency_status="rejected",
                    failure=GameplayFailure(
                        error_code="injected_owner_batch_failure",
                        message="injected_owner_batch_failure",
                        failed_stage="append",
                        retriable=True,
                    ),
                )
            return super().append_batch(payload)

    store = FailingBatchStore()
    authority = OrganizationAuthority(store=store)
    windows = (_closed_window(authority, "alpha"), _closed_window(authority, "beta"))
    before_transactions = len(store.read_transactions())

    result = _capability(authority).run_default_decision_cycle(
        _cadence(), _read_set(*windows)
    )

    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert all(receipt.settlement_status == "requeue" for receipt in result.owner_receipts)
    assert len(store.read_transactions()) == before_transactions
    assert all(
        store.get_stream_head(f"gameplay:organization:window:{window_ref}") == 2
        for _, window_ref in windows
    )


def test_owner_adapter_rejects_noncanonical_window_stream() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    organization_ref, window_ref = _closed_window(authority, "alpha")
    cadence = _cadence()
    forged_stream = "gameplay:organization:window:window:forged"
    projection = PopulationProjection(
        ref="projection:forged-window-stream",
        scope="organization:summary",
        revision_vector={forged_stream: 2},
        payload={
            "actor_ref": "character:alpha",
            "candidate_kind": "organization_operating_window_due",
            "fidelity_tier": "B1",
            "source_domain": "organization",
            "intent_kind": "operating_window_due",
            "stream_ref": forged_stream,
            "organization_ref": organization_ref,
            "window_ref": window_ref,
        },
    )

    result = _capability(authority).run_default_decision_cycle(
        cadence, PopulationReadSet.from_inputs(cadence, (projection,))
    )

    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert result.owner_receipts[0].settlement_status == "rejected"
    assert store.get_stream_head(f"gameplay:organization:window:{window_ref}") == 2
