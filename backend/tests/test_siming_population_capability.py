from __future__ import annotations

import pytest

from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_event import SimingInput
from app.population_continuity.batch import ContinuityMergeAuthority, PopulationPlanner
from app.population_continuity.decision_surface import PopulationCapabilityCatalog
from app.population_continuity.seed_planner import CharacterSeedPlanner
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationCycleResult, PopulationProjection, PopulationReadSet, PopulationBatchReport
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_population_capability import PopulationSimulationCapability, default_population_read_set_builder
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


def _b0_cadence_and_read_set(actor_count: int = 54):
    cadence = PopulationCadenceInput(
        cadence_id="cadence:b0:test:1",
        world_ref="world:b0",
        world_mode_ref="mode:b0",
        world_mode_revision="mode:b0@1",
        cadence_source_ref="world:b0",
        cadence_source_revision=7,
        window_start=100,
        window_end=120,
        base_checkpoint_ref="checkpoint:b0:1",
        base_checkpoint_digest="sha256:checkpoint:b0",
        base_revision_vector={"world:b0": 7},
        policy_revision="policy:population:v1",
        selector_revision="selector:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed="seed:b0:1",
        catch_up_limit=2,
        budget=2,
        report_scope="public",
    )
    projections = [
        PopulationProjection(
            ref=f"projection:b0:{index:03d}",
            scope="public",
            revision_vector={"world:b0": 7},
            payload={
                "actor_ref": f"character:resident_{index:03d}",
                "candidate_kind": "routine_work",
                "fidelity_tier": "B0",
                "from_tick": 100,
                "to_tick": 120,
                "simulation_tick_cursor": 120,
                "actor_revision": index,
                "state_deltas": {
                    "activity_phase": "routine",
                    "fatigue": (index % 100) / 100,
                    "need_pressure": 0.1,
                    "next_due_tick": 140,
                    "starvation_credit": 0.0,
                },
                "presentation_seed": {"task": "routine"},
                "due_obligation_refs": (),
                "scope": "public",
                "source_revision_vector": {"world:b0": 7},
                "idempotency_key": f"b0:cadence:b0:test:1:character:resident_{index:03d}",
            },
        )
        for index in range(actor_count)
    ]
    return cadence, PopulationReadSet.from_inputs(cadence, projections)


@pytest.mark.parametrize("actor_count", (12, 54, 1_000))
def test_b0_batch_returns_typed_cursor_for_every_actor_without_budget_or_owner(
    actor_count: int,
) -> None:
    cadence, read_set = _b0_cadence_and_read_set(actor_count)

    results = PopulationSimulationCapability().build_b0_continuous_deltas(cadence, read_set)

    assert len(results) == actor_count
    assert {item["actor_ref"] for item in results} == {
        f"character:resident_{index:03d}" for index in range(actor_count)
    }
    assert all(item["from_tick"] == 100 and item["to_tick"] == 120 for item in results)
    assert all(item["simulation_tick_cursor"] == 120 for item in results)
    assert all(item["actor_revision"] >= 0 for item in results)
    assert all(item["scope"] == "public" for item in results)
    assert all(item["source_revision_vector"] == {"world:b0": 7} for item in results)
    assert all(item["idempotency_key"].startswith("b0:cadence:b0:test:1:") for item in results)


def test_b0_projection_with_deep_state_fails_closed() -> None:
    cadence, read_set = _b0_cadence_and_read_set(1)
    deep = read_set.projections[0].model_copy(
        update={"payload": {**read_set.projections[0].payload, "llm_request": {"prompt": "x"}}}
    )
    with pytest.raises(ValueError, match="b0_deep_state_forbidden"):
        PopulationSimulationCapability().build_b0_continuous_deltas(
            cadence, PopulationReadSet.from_inputs(cadence, (deep,))
        )


def test_default_cycle_advances_all_b0_actors_outside_b1_budget() -> None:
    cadence, b0_read_set = _b0_cadence_and_read_set(50)
    expensive = tuple(
        PopulationProjection(
            ref=f"projection:tax:{index}",
            scope="public",
            revision_vector={"world:b0": 7},
            payload={
                "actor_ref": f"character:active_{index}",
                "candidate_kind": "tax_pressure",
                "source_domain": "economy",
                "fidelity_tier": "B1",
                "status": "due",
                "budget_cost": 1,
            },
        )
        for index in range(4)
    )
    read_set = PopulationReadSet.from_inputs(
        cadence, (*b0_read_set.projections, *expensive)
    )

    result = PopulationSimulationCapability().run_default_decision_cycle(
        cadence, read_set
    )

    assert result.status == "accepted"
    assert len(result.b0_results) == 50
    assert result.decision is not None
    assert result.decision.budget_used == 2
    assert len(result.decision.selected_candidates) == 2
    assert len(result.decision.deferred_candidates) == 2
    assert result.cognition_stats.b0_advanced == 50
    assert result.cognition_stats.deep_selected == 2
    assert result.cognition_stats.deep_deferred == 2
    assert result.cognition_stats.llm_queued == 0


def test_population_runtime_audit_exposes_bounded_cognition_counts() -> None:
    cadence, read_set = _b0_cadence_and_read_set(1)
    cadence = cadence.model_copy(
        update={"selector_revision": "selector:generic:population:v1"}
    )
    read_set = PopulationReadSet.from_inputs(cadence, read_set.projections)
    runtime = SimingRuntime(
        population_capability=PopulationSimulationCapability(),
        population_read_set_builder=lambda _event, _cadence: read_set,
    )

    result = runtime.tick(
        [
            SimingInput(
                input_type="population_cadence_input",
                source_event=cadence_event(**cadence.model_dump(mode="json")),
            )
        ]
    )

    audit = next(item for item in result.audit_records if "population_cycle" in item.reason)
    assert "b0=1" in audit.reason
    assert "quiet=1" in audit.reason
    assert "active=0" in audit.reason
    assert "llm_queued=0" in audit.reason


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

    def current_revision(self, actor_ref: str) -> int:
        return 0


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


class GenericDefaultRecordingPopulationCapability(RecordingPopulationCapability):
    def __init__(self) -> None:
        super().__init__()
        self.generic_calls = 0
        self.cohort_calls = 0

    def run_default_decision_cycle(self, cadence_input, read_set):
        self.generic_calls += 1
        report = PopulationBatchReport(batch_ref="batch:generic", read_set_digest=read_set.read_set_digest, result_digest="sha256:generic", budget_used=0, budget_remaining=cadence_input.budget)
        return PopulationCycleResult(status="accepted", batch_ref=report.batch_ref, report=report, production_append_count=0)

    def run_cohort_cycle(self, cadence_input, read_set):
        self.cohort_calls += 1
        return self.run_cycle(cadence_input, read_set)

    def run_decision_cycle(self, cadence_input, read_set, policy, capabilities):
        return self.run_default_decision_cycle(cadence_input, read_set)


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


def test_default_production_builder_supplies_bakery_owner_context() -> None:
    fixture = BakeryDistrictPopulationFixture.create(
        profile_dir=Path(__file__).parents[2] / "assets" / "characters" / "profiles"
    )
    activation = ProfileActivationAuthority(registry=fixture.registry, store=fixture.store)
    planned, social, household, organization = fixture._plan_schedule_gated_supply(
        batch_ref="batch:test:production", recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        activation_lock_refs=("lock:world:bakery-district:character:char_a",),
    )
    assert planned.plan is not None
    _, _, pending_change_ref = fixture._admit_released_schedule_gated_supply(
        activation=activation, batch_ref="batch:test:production",
        recipient_ref="character:char_a", plan=planned.plan,
    )
    plan = planned.plan
    candidate = plan.candidates[0]
    cadence = cadence_input(
        world_ref=plan.world_ref,
        world_mode_ref="mode:bakery-district",
        world_mode_revision=plan.mode_revision,
        policy_revision=plan.policy_revision,
        cadence_source_ref="gameplay:organization:org:bakery",
        cadence_source_revision=4,
        base_revision_vector={"gameplay:organization:org:bakery": 4},
        report_scope=plan.report_scope,
    )
    event = cadence_event()
    event = event.model_copy(
        update={
            "payload": {
                "population_cadence": cadence.model_dump(mode="json"),
                "population_world_plan": plan.model_dump(mode="json"),
                "activation_pending_projection": activation.pending_projection(plan.world_ref),
                "social_projection": social.model_dump(mode="json"),
                "household_projection": household.model_dump(mode="json"),
                "organization_projection": organization.model_dump(mode="json"),
                "population_projections": [{
                    "ref": "supply",
                    "scope": plan.report_scope,
                    "revision_vector": {"gameplay:organization:org:bakery": 4},
                    "payload": {
                        "actor_ref": candidate.profile_ref,
                        "candidate_kind": "schedule_gated_supply",
                        "state_deltas": {"task": "restock"},
                    },
                }],
            }
        }
    )
    read_set = default_population_read_set_builder(event, cadence)
    owner = ScheduleGatedSupplyOwnerExecutor(
        merger=ContinuityMergeAuthority(store=fixture.store, registry=fixture.registry, mode=fixture.mode),
        context_builder=ScheduleGatedSupplyOwnerExecutor.context_from_intent_payload,
    )
    result = PopulationSimulationCapability(owner_executor=owner).run_cycle(cadence, read_set)
    assert result.status == "accepted"
    assert result.production_append_count == 1
    assert result.owner_receipts[0].event_family == ScheduleGatedSupplyOwnerExecutor.EVENT_FAMILY
    assert result.owner_receipts[0].committed
    assert fixture.store.read_events()[-1].event_type == ScheduleGatedSupplyOwnerExecutor.EVENT_FAMILY


def test_tick_routes_population_once() -> None:
    recorder = GenericDefaultRecordingPopulationCapability()
    runtime = SimingRuntime(population_capability=recorder)
    result = runtime.tick([SimingInput(input_type="population_cadence_input", source_event=cadence_event(cadence_id="cadence:cohort:bakery:W0", selector_revision="selector:cohort-bakery:v1", ruleset_revision="rules:cohort-bakery:v1"))])
    assert recorder.calls == 1
    assert runtime.pending_count == 0
    assert runtime._siming_receipts == {}
    assert result.read_model is None
    assert any("population_cycle" in audit.reason for audit in result.audit_records)


def test_non_v1_population_cadence_defaults_to_generic_decision_surface() -> None:
    recorder = GenericDefaultRecordingPopulationCapability()
    event = cadence_event(cadence_id="cadence:generic:1", selector_revision="selector:generic:population:v1")
    result = SimingRuntime(population_capability=recorder).tick(
        [SimingInput(input_type="population_cadence_input", source_event=event)]
    )
    assert recorder.generic_calls == 1
    assert recorder.cohort_calls == 0
    assert result.read_model is None
    assert any("population_cycle" in audit.reason for audit in result.audit_records)


def test_population_cadence_never_falls_through_to_generic_observe_pipeline() -> None:
    class ForbiddenObservePipeline:
        def observe(self, events):
            raise AssertionError("population_cadence_fell_through")

    class ForbiddenLlmProvider:
        def generate_candidates(self, **kwargs):
            raise AssertionError("population_cadence_called_llm")

        def generate_adaptive_bridge_proposals(self, **kwargs):
            raise AssertionError("population_cadence_called_llm")

    recorder = GenericDefaultRecordingPopulationCapability()
    event = cadence_event(
        cadence_id="cadence:generic:no-fallthrough",
        selector_revision="selector:generic:population:v1",
    )

    result = SimingRuntime(
        population_capability=recorder,
        observe_pipeline=ForbiddenObservePipeline(),
        llm_provider=ForbiddenLlmProvider(),
    ).tick([SimingInput(input_type="population_cadence_input", source_event=event)])

    assert recorder.generic_calls == 1
    assert any("population_cycle" in audit.reason for audit in result.audit_records)


def test_explicit_expensive_candidates_require_due_or_activation_authority() -> None:
    cadence, _ = _b0_cadence_and_read_set(0)
    cadence = cadence.model_copy(update={"budget": 4, "catch_up_limit": 4})
    projections = tuple(
        PopulationProjection(
            ref=f"projection:{name}",
            scope="public",
            revision_vector={"world:b0": 7},
            payload={
                "actor_ref": f"character:{name}",
                "candidate_kind": "tax_pressure",
                "source_domain": "economy",
                "fidelity_tier": tier,
                **extra,
            },
        )
        for name, tier, extra in (
            ("not_due", "B1", {}),
            ("unsupported", "B3", {"status": "due"}),
            ("due", "B1", {"status": "due"}),
            (
                "activated",
                "B2",
                {
                    "activation_receipt_ref": "activation:character:activated:1",
                    "activation_status": "released",
                },
            ),
        )
    )

    result = PopulationSimulationCapability().run_default_decision_cycle(
        cadence, PopulationReadSet.from_inputs(cadence, projections)
    )

    assert result.decision is not None
    assert {item.actor_ref for item in result.decision.selected_candidates} == {
        "character:due",
        "character:activated",
    }
    assert result.cognition_stats.deep_selected == 2
    assert result.cognition_stats.deep_deferred == 2


def test_legacy_projection_without_tier_cannot_bypass_non_expensive_policy() -> None:
    cadence, _ = _b0_cadence_and_read_set(0)
    projection = PopulationProjection(
        ref="projection:legacy-policy-b0",
        scope="public",
        revision_vector={"world:b0": 7},
        payload={
            "actor_ref": "character:legacy",
            "candidate_kind": "tax_pressure",
            "source_domain": "economy",
        },
    )
    capability = PopulationSimulationCapability()
    policy = capability.default_decision_policy(cadence).model_copy(
        update={"default_fidelity_tier": "B0"}
    )

    result = capability.run_decision_cycle(
        cadence,
        PopulationReadSet.from_inputs(cadence, (projection,)),
        policy,
        capability.default_capabilities(cadence),
    )

    assert result.decision is not None
    assert result.decision.selected_candidates == ()
    assert result.cognition_stats.deep_selected == 0
    assert result.cognition_stats.deep_deferred == 1


def test_v1_population_cadence_keeps_cohort_fixture_path() -> None:
    recorder = GenericDefaultRecordingPopulationCapability()
    event = cadence_event(
        cadence_id="cadence:cohort:bakery:W0",
        selector_revision="selector:cohort-bakery:v1",
        ruleset_revision="rules:cohort-bakery:v1",
    )
    result = SimingRuntime(population_capability=recorder).tick(
        [SimingInput(input_type="population_cadence_input", source_event=event)]
    )
    assert recorder.generic_calls == 0
    assert recorder.cohort_calls == 1
    assert result.read_model is None
    assert any("population_cycle" in audit.reason for audit in result.audit_records)


def test_unknown_population_selector_requeues_without_fallback() -> None:
    recorder = GenericDefaultRecordingPopulationCapability()
    event = cadence_event(selector_revision="selector:generic:legacy:v1")
    result = SimingRuntime(population_capability=recorder).tick(
        [SimingInput(input_type="population_cadence_input", source_event=event)]
    )
    assert recorder.generic_calls == 0 and recorder.cohort_calls == 0
    assert result.audit_records[-1].reason == "population_requeue:unknown_selector"


def test_generic_population_decision_requires_admitted_descriptors() -> None:
    recorder = GenericDefaultRecordingPopulationCapability()
    event = cadence_event(
        selector_revision="selector:generic:population:v1",
    ).model_copy(
        update={
            "payload": {
                **cadence_event(selector_revision="selector:generic:population:v1").payload,
                "population_decision": {"policy": {}, "capabilities": []},
            }
        }
    )
    result = SimingRuntime(population_capability=recorder).tick(
        [SimingInput(input_type="population_cadence_input", source_event=event)]
    )
    assert recorder.generic_calls == 0
    assert result.audit_records[-1].reason == "population_requeue:capability_descriptor_missing"


def test_consumer_maps_cadence_event() -> None:
    inputs = SimingEventConsumer().handle_event(cadence_event())
    assert len(inputs) == 1 and inputs[0].input_type == "population_cadence_input"


@pytest.mark.parametrize("field,value", [
    ("population_decision", None),
    ("population_decision", []),
    ("population_decision", "invalid"),
    ("population_owner_receipt", None),
    ("population_owner_receipt", []),
    ("population_owner_receipt", "invalid"),
])
def test_malformed_population_payload_never_uses_default(field, value) -> None:
    recorder = GenericDefaultRecordingPopulationCapability()
    event = cadence_event(selector_revision="selector:generic:population:v1")
    event.payload[field] = value
    result = SimingRuntime(population_capability=recorder).tick([
        SimingInput(input_type="population_cadence_input", source_event=event)
    ])
    assert recorder.generic_calls == recorder.cohort_calls == recorder.calls == 0
    assert result.audit_records[-1].reason.startswith("population_requeue:")


def test_receipt_runner_missing_never_uses_generic_default() -> None:
    recorder = GenericDefaultRecordingPopulationCapability()
    event = cadence_event(selector_revision="selector:generic:population:v1")
    event.payload["population_owner_receipt"] = {
        "receipt_ref": "receipt:production", "owner_ref": "actor_gameplay.organization_domain",
        "event_family": "gameplay.organization.production_work_contribution_accepted",
        "committed": True, "revision_vector": {"world:bakery": 1}, "zero_write": False,
    }
    event.payload["population_projections"] = [{
        "ref": "projection:production", "scope": "organization:summary",
        "revision_vector": {"world:bakery": 1}, "payload": {},
    }]
    result = SimingRuntime(population_capability=recorder).tick([
        SimingInput(input_type="population_cadence_input", source_event=event)
    ])
    assert recorder.generic_calls == recorder.cohort_calls == recorder.calls == 0
    assert result.audit_records[-1].reason == "population_requeue:runner_missing"


def test_fixture_runner_missing_never_uses_legacy_cycle() -> None:
    recorder = RecordingPopulationCapability()
    event = cadence_event(selector_revision="selector:cohort-bakery:v1")
    result = SimingRuntime(population_capability=recorder).tick([
        SimingInput(input_type="population_cadence_input", source_event=event)
    ])
    assert recorder.calls == 0
    assert result.audit_records[-1].reason == "population_requeue:runner_missing"


@pytest.mark.parametrize("invalid_descriptor", [None, "invalid", {"capability_id": "unknown"}])
def test_mixed_capability_descriptors_cannot_silently_drop_invalid_entries(invalid_descriptor) -> None:
    recorder = GenericDefaultRecordingPopulationCapability()
    event = cadence_event(selector_revision="selector:generic:population:v1")
    cadence = PopulationCadenceInput.from_authority_event(event)
    event.payload["population_decision"] = {
        "policy": PopulationSimulationCapability.default_decision_policy(cadence).model_dump(mode="json"),
        "capabilities": [PopulationCapabilityCatalog.default(cadence.policy_revision)[0].model_dump(mode="json"), invalid_descriptor],
    }
    result = SimingRuntime(population_capability=recorder).tick([
        SimingInput(input_type="population_cadence_input", source_event=event)
    ])
    assert recorder.generic_calls == recorder.cohort_calls == recorder.calls == 0
    assert result.audit_records[-1].reason.startswith("population_requeue:")


def test_admitted_explicit_generic_decision_ignores_fixture_cadence_id_prefix() -> None:
    recorder = GenericDefaultRecordingPopulationCapability()
    event = cadence_event(cadence_id="cadence:cohort:bakery:W0", selector_revision="selector:generic:population:v1")
    cadence = PopulationCadenceInput.from_authority_event(event)
    event.payload["population_decision"] = {
        "policy": PopulationSimulationCapability.default_decision_policy(cadence).model_dump(mode="json"),
        "capabilities": [PopulationCapabilityCatalog.default(cadence.policy_revision)[0].model_dump(mode="json")],
    }
    SimingRuntime(population_capability=recorder).tick([
        SimingInput(input_type="population_cadence_input", source_event=event)
    ])
    assert recorder.generic_calls == 1
    assert recorder.cohort_calls == recorder.calls == 0
