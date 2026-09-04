from __future__ import annotations

from app.gameplay.econ1_economy_runtime import OperatingWindow
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.population_continuity.owner_adapters import OrganizationOperatingWindowDueOwnerExecutor
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationProjection,
    PopulationReadSet,
)
from app.services.siming_population_capability import PopulationSimulationCapability


def _read_set() -> PopulationReadSet:
    cadence = PopulationCadenceInput(
        cadence_id="cadence:generic:W0",
        world_ref="world:generic",
        world_mode_ref="mode:generic",
        world_mode_revision="policy:population:v1",
        cadence_source_ref="world:generic",
        cadence_source_revision=2,
        window_start=0,
        window_end=1,
        base_checkpoint_ref="checkpoint:generic:1",
        base_checkpoint_digest="sha256:checkpoint:generic:1",
        base_revision_vector={"world:generic": 2},
        policy_revision="policy:population:v1",
        selector_revision="selector:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed="seed:generic:W0",
        catch_up_limit=1,
        budget=1,
        report_scope="organization:summary",
    )
    stream_ref = "gameplay:organization:window:window:generic"
    projection = PopulationProjection(
        ref="projection:organization-window:W0",
        scope="organization:summary",
        revision_vector={stream_ref: 2},
        payload={
            "actor_ref": "character:char_a",
            "candidate_kind": "organization_operating_window_due",
            "source_domain": "organization",
            "intent_kind": "operating_window_due",
            "stream_ref": stream_ref,
            "organization_ref": "org:generic",
            "window_ref": "window:generic",
        },
    )
    return PopulationReadSet.from_inputs(cadence, (projection,))


def test_generic_operating_window_due_uses_existing_owner_and_receipt() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    assert authority.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=OperatingWindow(
            window_ref="window:generic",
            organization_ref="org:generic",
            opens_at_tick=1,
            closes_at_tick=5,
            policy_revision="policy:window:1",
            source_revision="schedule:1",
        ),
        visibility_scope="project",
    ).committed
    assert authority.close_operating_window(
        command_id="command:window:close",
        idempotency_key="window:close",
        causation_id="cause:window:close",
        correlation_id="corr:window:close",
        organization_ref="org:generic",
        window_ref="window:generic",
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed

    read_set = _read_set()
    result = PopulationSimulationCapability(
        owner_executors={
            "population:organization-window-due:v1": OrganizationOperatingWindowDueOwnerExecutor(
                authority=authority
            )
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)

    assert result.status == "accepted"
    assert result.owner_receipts[0].committed
    assert result.owner_receipts[0].event_family == "gameplay.organization.operating_window_due_recorded"
    assert store.get_stream_head("gameplay:organization:window:window:generic") == 3


def test_generic_operating_window_due_duplicate_replay_is_zero_write_acceptance() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    assert authority.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=OperatingWindow(
            window_ref="window:generic",
            organization_ref="org:generic",
            opens_at_tick=1,
            closes_at_tick=5,
            policy_revision="policy:window:1",
            source_revision="schedule:1",
        ),
        visibility_scope="project",
    ).committed
    assert authority.close_operating_window(
        command_id="command:window:close",
        idempotency_key="window:close",
        causation_id="cause:window:close",
        correlation_id="corr:window:close",
        organization_ref="org:generic",
        window_ref="window:generic",
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed
    read_set = _read_set()
    capability = PopulationSimulationCapability(
        owner_executors={
            "population:organization-window-due:v1": OrganizationOperatingWindowDueOwnerExecutor(
                authority=authority
            )
        }
    )

    first = capability.run_default_decision_cycle(read_set.cadence, read_set)
    replay = capability.run_default_decision_cycle(read_set.cadence, read_set)

    assert first.status == "accepted"
    assert replay.status == "accepted"
    assert replay.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert replay.owner_receipts[0].zero_write
    assert store.get_stream_head("gameplay:organization:window:window:generic") == 3


def test_generic_operating_window_due_stale_revision_requeues_without_write() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    assert authority.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=OperatingWindow(
            window_ref="window:generic",
            organization_ref="org:generic",
            opens_at_tick=1,
            closes_at_tick=5,
            policy_revision="policy:window:1",
            source_revision="schedule:1",
        ),
        visibility_scope="project",
    ).committed
    assert authority.close_operating_window(
        command_id="command:window:close",
        idempotency_key="window:close",
        causation_id="cause:window:close",
        correlation_id="corr:window:close",
        organization_ref="org:generic",
        window_ref="window:generic",
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed
    base = _read_set()
    stale_projection = base.projections[0].model_copy(
        update={"revision_vector": {"gameplay:organization:window:window:generic": 1}}
    )
    stale_read_set = PopulationReadSet.from_inputs(base.cadence, (stale_projection,))
    result = PopulationSimulationCapability(
        owner_executors={
            "population:organization-window-due:v1": OrganizationOperatingWindowDueOwnerExecutor(
                authority=authority
            )
        }
    ).run_default_decision_cycle(stale_read_set.cadence, stale_read_set)

    assert result.status == "requeue"
    assert result.reason == "owner_rejected"
    assert result.owner_receipts[0].zero_write
    assert store.get_stream_head("gameplay:organization:window:window:generic") == 2


def test_generic_operating_window_due_owner_rejection_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    assert authority.open_operating_window(
        command_id="command:window:open",
        idempotency_key="window:open",
        causation_id="cause:window:open",
        correlation_id="corr:window:open",
        window=OperatingWindow(
            window_ref="window:generic",
            organization_ref="org:generic",
            opens_at_tick=1,
            closes_at_tick=5,
            policy_revision="policy:window:1",
            source_revision="schedule:1",
        ),
        visibility_scope="project",
    ).committed
    assert authority.close_operating_window(
        command_id="command:window:close",
        idempotency_key="window:close",
        causation_id="cause:window:close",
        correlation_id="corr:window:close",
        organization_ref="org:generic",
        window_ref="window:generic",
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed
    base = _read_set()
    rejected_projection = base.projections[0].model_copy(
        update={"payload": {**base.projections[0].payload, "window_ref": "window:missing"}}
    )
    rejected_read_set = PopulationReadSet.from_inputs(base.cadence, (rejected_projection,))
    result = PopulationSimulationCapability(
        owner_executors={
            "population:organization-window-due:v1": OrganizationOperatingWindowDueOwnerExecutor(
                authority=authority
            )
        }
    ).run_default_decision_cycle(rejected_read_set.cadence, rejected_read_set)

    assert result.status == "requeue"
    assert result.reason == "owner_rejected"
    assert result.owner_receipts[0].zero_write
    assert store.get_stream_head("gameplay:organization:window:window:generic") == 2
