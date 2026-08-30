from __future__ import annotations

from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_event import SimingInput
from app.population_continuity.batch import ContinuityMergeAuthority, PopulationPlanner
from app.population_continuity.seed_planner import CharacterSeedPlanner
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationCycleResult, PopulationProjection, PopulationReadSet, PopulationBatchReport
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_population_capability import PopulationSimulationCapability
from app.services.siming_runtime import SimingRuntime
from app.population_continuity.owner_adapters import ScheduleGatedSupplyOwnerExecutor
from app.population_continuity.vertical import BakeryDistrictPopulationFixture
from app.population_continuity.activation import ProfileActivationAuthority
from pathlib import Path
from app.character_agent.models.simulation_seed import CharacterContinuityReceipt
from dataclasses import dataclass


def cadence_input(**updates: object) -> PopulationCadenceInput:
    values: dict[str, object] = {
        "cadence_id": "cadence:bakery:1", "world_ref": "world:bakery", "world_mode_ref": "mode:bakery",
        "world_mode_revision": "mode:v1", "cadence_source_ref": "world:bakery", "cadence_source_revision": 1,
        "window_start": 100, "window_end": 101, "base_checkpoint_ref": "checkpoint:bakery:1",
        "base_checkpoint_digest": "sha256:checkpoint", "base_revision_vector": {"world:bakery": 1},
        "policy_revision": "policy:v1", "selector_revision": "selector:v1", "ruleset_revision": "ruleset:v1",
        "deterministic_seed": "seed:bakery:1", "catch_up_limit": 2, "budget": 2, "report_scope": "organization:summary",
    }
    values.update(updates)
    return PopulationCadenceInput(**values)


def read_set() -> PopulationReadSet:
    return PopulationReadSet.from_inputs(cadence_input(), ())


def stale_cadence_input() -> PopulationCadenceInput:
    return cadence_input(cadence_source_revision=2, base_revision_vector={"world:bakery": 2})


def stale_read_set() -> PopulationReadSet:
    projection = PopulationProjection(ref="stale", scope="organization:summary", revision_vector={"world:bakery": 2}, payload={})
    return PopulationReadSet.from_inputs(cadence_input(), (projection,))


def read_set_with_supply_candidate() -> PopulationReadSet:
    projection = PopulationProjection(ref="supply", scope="organization:summary", revision_vector={"world:bakery": 1}, payload={"actor_ref": "character:char_a", "candidate_kind": "schedule_gated_supply", "state_deltas": {"task": "restock"}, "owner_receipt_ref": "receipt:supply"})
    return PopulationReadSet.from_inputs(cadence_input(), (projection,))


@dataclass
class RecordingContinuityPort:
    commands: list[object]

    def apply_command(self, command: object) -> CharacterContinuityReceipt:
        self.commands.append(command)
        return CharacterContinuityReceipt(
            receipt_ref=f"continuity:{command.command_id}", command_id=command.command_id,
            actor_ref=command.actor_ref, status="committed", character_revision_before=0,
            character_revision_after=1, source_owner_receipt_refs=command.source_owner_receipt_refs,
        )


def capability_with_bakery_owner() -> tuple[PopulationSimulationCapability, RecordingContinuityPort]:
    fixture = BakeryDistrictPopulationFixture.create(
        profile_dir=Path(__file__).parents[2] / "assets" / "characters" / "profiles"
    )
    activation = ProfileActivationAuthority(registry=fixture.registry, store=fixture.store)
    planned, social, household, organization = fixture._plan_schedule_gated_supply(
        batch_ref="batch:test:owner", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z",
        activation_lock_refs=("lock:world:bakery-district:character:char_a",),
    )
    assert planned.plan is not None
    _, _, pending_change_ref = fixture._admit_released_schedule_gated_supply(
        activation=activation, batch_ref="batch:test:owner", recipient_ref="character:char_a", plan=planned.plan,
    )
    merger = ContinuityMergeAuthority(store=fixture.store, registry=fixture.registry, mode=fixture.mode)
    continuity = RecordingContinuityPort([])
    owner = ScheduleGatedSupplyOwnerExecutor(
        merger=merger, plan=planned.plan, pending_change_ref=pending_change_ref,
        social_input=social, household_input=household, organization_input=organization,
    )
    return PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity), continuity


def cadence_event(**payload: object) -> AuthorityEvent:
    data = cadence_input().model_dump(mode="json")
    data.update(payload)
    return AuthorityEvent(event_id="event:cadence:1", event_type="population_cadence_event", producer_ts=100, room_id="room:main", scene_id="scene:main", zone_id="zone:main", source=AuthorityEventSource(layer="L2", system="test"), routing=AuthorityEventRouting(audience_mode="broadcast", routing_mode="event_type"), priority="p2", durability="replayable", causation_id="cause:cadence", correlation_id="corr:cadence", payload={"population_cadence": data})


class RecordingPopulationCapability:
    def __init__(self) -> None:
        self.calls = 0

    def run_cycle(self, cadence_input: PopulationCadenceInput, read_set: PopulationReadSet) -> PopulationCycleResult:
        self.calls += 1
        report = PopulationBatchReport(batch_ref="batch:empty", read_set_digest=read_set.read_set_digest, result_digest="sha256:empty", budget_used=0, budget_remaining=cadence_input.budget)
        return PopulationCycleResult(status="accepted", batch_ref=report.batch_ref, report=report, production_append_count=0)


def test_missing_owner_is_zero_write() -> None:
    result = PopulationSimulationCapability(planner=PopulationPlanner(), seed_planner=CharacterSeedPlanner()).run_cycle(cadence_input(), read_set_with_supply_candidate())
    assert result.status == "owner_settlement_required"
    assert result.seed_candidates
    assert result.production_append_count == 0


def test_stale_read_set_requeues_without_planner_write() -> None:
    result = PopulationSimulationCapability(planner=PopulationPlanner(), seed_planner=CharacterSeedPlanner()).run_cycle(stale_cadence_input(), stale_read_set())
    assert result.status == "requeue"
    assert result.reason == "stale_read_set"
    assert result.production_append_count == 0


def test_semantically_stale_projection_requeues_before_planner() -> None:
    class CountingPlanner(PopulationPlanner):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def plan_population_cycle(self, read_set: PopulationReadSet):
            self.calls += 1
            return super().plan_population_cycle(read_set)

    planner = CountingPlanner()
    result = PopulationSimulationCapability(planner=planner).run_cycle(cadence_input(), stale_read_set())
    assert result.status == "requeue"
    assert result.reason == "stale_read_set"
    assert planner.calls == 0


def test_registered_supply_owner_returns_exact_event_family() -> None:
    class Merger:
        def merge_released_schedule_gated_supply(self, **_: object):
            return type("Receipt", (), {"committed": True, "revision_vector": {"gameplay:organization:bakery": 2}, "owner_receipt_ref": "actor_gameplay.organization_domain"})()

    owner = ScheduleGatedSupplyOwnerExecutor(merger=Merger(), plan=object(), pending_change_ref="pending:1")
    result = owner.submit(
        type("Intent", (), {"intent_kind": "supply", "intent_ref": "intent:1"})(),
        read_set=read_set_with_supply_candidate(),
    )
    assert result.owner_ref == "actor_gameplay.organization_domain"
    assert result.event_family == "gameplay.organization.commerce_commitment_accepted"


def test_committed_owner_receipt_reaches_continuity_port() -> None:
    capability, continuity = capability_with_bakery_owner()
    result = capability.run_cycle(cadence_input(), read_set_with_supply_candidate())
    assert result.status == "accepted"
    assert result.owner_receipts[0].receipt_ref == "actor_gameplay.organization_domain"
    assert result.seed_candidates[0].owner_effect_status == "settled"
    assert result.seed_candidates[0].source_owner_receipt_refs == ("actor_gameplay.organization_domain",)
    assert continuity.commands[0].source_owner_receipt_refs == ("actor_gameplay.organization_domain",)


def test_tick_routes_population_once() -> None:
    recorder = RecordingPopulationCapability()
    result = SimingRuntime(population_capability=recorder).tick([SimingInput(input_type="population_cadence_input", source_event=cadence_event())])
    assert recorder.calls == 1
    assert result.read_model is not None


def test_consumer_maps_cadence_event() -> None:
    inputs = SimingEventConsumer().handle_event(cadence_event())
    assert len(inputs) == 1 and inputs[0].input_type == "population_cadence_input"
