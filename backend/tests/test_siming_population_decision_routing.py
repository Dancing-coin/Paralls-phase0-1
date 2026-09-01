from __future__ import annotations

from app.population_continuity.decision_surface import PopulationCapabilityDescriptor, PopulationDecisionPolicy
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationOwnerReceipt, PopulationProjection, PopulationReadSet
from app.services.siming_population_capability import PopulationSimulationCapability
from app.character_agent.models.simulation_seed import CharacterContinuityReceipt


class Owner:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def submit(self, intent, *, read_set):
        self.calls.append(intent)
        return PopulationOwnerReceipt(
            receipt_ref=f"receipt:{intent.intent_ref}", owner_ref="organization:bakery",
            event_family="gameplay.organization.commerce_commitment_accepted", committed=True,
            revision_vector={"world:bakery": 1}, zero_write=False,
        )


class Continuity:
    def __init__(self) -> None:
        self.commands: list[object] = []

    def current_revision(self, actor_ref: str) -> int:
        return 0

    def apply_command(self, command):
        self.commands.append(command)
        return CharacterContinuityReceipt(
            receipt_ref=f"receipt:{command.command_id}", command_id=command.command_id,
            actor_ref=command.actor_ref, status="committed", character_revision_before=0,
            character_revision_after=1,
        )


def read_set() -> PopulationReadSet:
    cadence = PopulationCadenceInput(
        cadence_id="cadence:generic:W0", world_ref="world:bakery", world_mode_ref="mode:bakery",
        world_mode_revision="policy:test:v1", cadence_source_ref="world:bakery", cadence_source_revision=1,
        window_start=0, window_end=1, base_checkpoint_ref="checkpoint:1", base_checkpoint_digest="sha256:cp",
        base_revision_vector={"world:bakery": 1}, policy_revision="policy:test:v1",
        selector_revision="selector:test:v1", ruleset_revision="rules:test:v1", deterministic_seed="seed:W0",
        catch_up_limit=3, budget=3, report_scope="organization:summary",
    )
    rows = (
        PopulationProjection(ref="projection:char_a:W0", scope="organization:summary", revision_vector={"world:bakery": 1}, payload={"actor_ref": "character:char_a", "candidate_kind": "schedule_gated_supply", "source_domain": "organization"}),
        PopulationProjection(ref="projection:char_b:W0", scope="public", revision_vector={"world:bakery": 1}, payload={"actor_ref": "character:char_b", "candidate_kind": "routine_work", "source_domain": "organization"}),
        PopulationProjection(ref="projection:char_c:W0", scope="public", revision_vector={"world:bakery": 1}, payload={"actor_ref": "character:char_c", "candidate_kind": "relationship_negotiation", "source_domain": "social"}),
    )
    return PopulationReadSet.from_inputs(cadence, rows)


def capabilities() -> tuple[PopulationCapabilityDescriptor, ...]:
    return (
        PopulationCapabilityDescriptor(capability_id="cap:supply", accepted_behavior_kinds=("schedule_gated_supply",), required_scopes=("organization:summary",), required_source_domains=("organization",), target_owner="organization:bakery", allowed_output_kinds=("owner_bound_intent", "character_core_command"), capability_revision="cap:supply:v1", policy_revision="policy:test:v1", enabled=True),
        PopulationCapabilityDescriptor(capability_id="cap:routine", accepted_behavior_kinds=("routine_work",), required_scopes=("public",), required_source_domains=("organization",), target_owner="character:core", allowed_output_kinds=("presentation_seed",), capability_revision="cap:routine:v1", policy_revision="policy:test:v1", enabled=True),
        PopulationCapabilityDescriptor(capability_id="cap:activation", accepted_behavior_kinds=("relationship_negotiation",), required_scopes=("public",), required_source_domains=("social",), target_owner="character:activation", allowed_output_kinds=("activation_candidate",), capability_revision="cap:activation:v1", policy_revision="policy:test:v1", enabled=True),
    )


def policy(**updates: object) -> PopulationDecisionPolicy:
    values: dict[str, object] = {"policy_revision": "policy:test:v1", "default_fidelity_tier": "B1", "budget": 3, "max_candidates": 3, "player_proximity_weight": 1.0, "owner_consequence_weight": 1.0, "propagation_weight": 1.0, "narrative_obligation_weight": 1.0, "starvation_weight": 1.0}
    values.update(updates)
    return PopulationDecisionPolicy(**values)


def test_siming_can_select_owner_seed_activation_or_defer_in_one_cycle() -> None:
    owner, continuity = Owner(), Continuity()
    result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_decision_cycle(read_set().cadence, read_set(), policy(), capabilities())
    assert result.status == "accepted"
    assert [item.profile_ref for item in owner.calls] == ["character:char_a"]
    assert {item.actor_ref for item in continuity.commands} <= {"character:char_a", "character:char_b"}
    assert result.decision is not None and result.decision.deferred_candidates == ()


def test_player_proximity_policy_can_choose_char_c_activation_without_core_command() -> None:
    owner, continuity = Owner(), Continuity()
    result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_decision_cycle(read_set().cadence, read_set(), policy(player_proximity_weight=10.0), capabilities())
    assert result.decision is not None
    assert all(command.actor_ref != "character:char_c" for command in continuity.commands)


def test_owner_mapping_cannot_be_overridden_by_candidate_payload() -> None:
    cadence, base = read_set().cadence, read_set()
    rows = tuple(
        projection.model_copy(update={"payload": {**projection.payload, "owner_ref": "owner:forged"}})
        if projection.payload.get("actor_ref") == "character:char_a" else projection
        for projection in base.projections
    )
    forged = PopulationReadSet.from_inputs(cadence, rows)
    owner, continuity = Owner(), Continuity()
    result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_decision_cycle(cadence, forged, policy(), capabilities())
    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert owner.calls == [] and continuity.commands == []


def test_budget_and_fidelity_change_selection_but_not_write_authority() -> None:
    low = PopulationSimulationCapability(owner_executor=Owner(), continuity_port=Continuity()).run_decision_cycle(read_set().cadence, read_set(), policy(budget=1, max_candidates=1), capabilities())
    high_owner = Owner()
    high = PopulationSimulationCapability(owner_executor=high_owner, continuity_port=Continuity()).run_decision_cycle(read_set().cadence, read_set(), policy(budget=3), capabilities())
    assert low.report.owner_intent_count <= high.report.owner_intent_count
    assert low.report.owner_intent_count <= 1
    assert all(receipt.owner_ref == "organization:bakery" for receipt in high.owner_receipts)
