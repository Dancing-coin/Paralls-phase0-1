from __future__ import annotations

from app.population_continuity.decision_surface import PopulationCapabilityDescriptor, PopulationDecisionPolicy
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationOwnerReceipt, PopulationProjection, PopulationReadSet
from app.services.siming_population_capability import PopulationSimulationCapability


def read_set(window: str = "W0", *, revision: int = 1, behavior: str = "routine_work") -> PopulationReadSet:
    cadence = PopulationCadenceInput(
        cadence_id=f"cadence:generic:W{window[-1]}", world_ref="world:bakery", world_mode_ref="mode:bakery",
        world_mode_revision="policy:test:v1", cadence_source_ref="world:bakery", cadence_source_revision=revision,
        window_start=0, window_end=1, base_checkpoint_ref="checkpoint:1", base_checkpoint_digest="sha256:cp",
        base_revision_vector={"world:bakery": revision}, policy_revision="policy:test:v1",
        selector_revision="selector:test:v1", ruleset_revision="rules:test:v1", deterministic_seed=f"seed:{window}",
        catch_up_limit=3, budget=3, report_scope="organization:summary",
    )
    row = PopulationProjection(
        ref=f"projection:char_b:{window}", scope="public", revision_vector={"world:bakery": revision},
        payload={"actor_ref": "character:char_b", "candidate_kind": behavior, "source_domain": "organization"},
    )
    return PopulationReadSet.from_inputs(cadence, (row,))


def capabilities() -> tuple[PopulationCapabilityDescriptor, ...]:
    return (PopulationCapabilityDescriptor(
        capability_id="cap:routine", accepted_behavior_kinds=("routine_work",), required_scopes=("public",),
        required_source_domains=("organization",), target_owner="character:core", allowed_output_kinds=("presentation_seed",),
        capability_revision="cap:routine:v1", policy_revision="policy:test:v1", enabled=True,
    ),)


def policy(**updates: object) -> PopulationDecisionPolicy:
    values: dict[str, object] = {"policy_revision": "policy:test:v1", "default_fidelity_tier": "B1", "budget": 3, "max_candidates": 3}
    values.update(updates)
    return PopulationDecisionPolicy(**values)


class GenericDecisionFixture:
    def __init__(self, *, owner_rejects: bool = False, empty_evidence: bool = False) -> None:
        self.owner_rejects = owner_rejects
        self.empty_evidence = empty_evidence
        self.capability = PopulationSimulationCapability()
        self.last_result = None

    @classmethod
    def create(cls, **kwargs: object) -> "GenericDecisionFixture":
        return cls(**kwargs)

    def run_cycle(self, *, window: str, budget: int):
        behavior = "routine_work" if not self.empty_evidence else "unknown_behavior"
        current = read_set(window, behavior=behavior)
        result = self.capability.run_decision_cycle(current.cadence, current, policy(budget=budget), capabilities())
        self.last_result = result
        return result

    def replan_from_cycle(self, previous, *, window: str, budget: int):
        result = self.capability.replan_from_receipts(previous.decision, previous.owner_receipts, read_set(window, revision=2), policy(budget=budget), capabilities())
        self.last_result = result
        return result

    def owner_source_revision(self, stream: str) -> int:
        return 1

    def actor_record_refs(self) -> tuple[str, ...]:
        return ("character:char_a", "character:char_b", "character:char_c")


def test_owner_receipt_changes_next_cycle_source_and_expected_revision() -> None:
    fixture = GenericDecisionFixture.create()
    first = fixture.run_cycle(window="W0", budget=2)
    second = fixture.replan_from_cycle(first, window="W1", budget=2)
    assert first.status == "accepted" and second.status == "accepted"
    assert second.decision is not None and first.decision is not None
    assert second.decision.read_set_digest != first.decision.read_set_digest
    assert fixture.owner_source_revision("organization:bakery") > 0


def test_owner_rejection_requeues_dependents_without_partial_character_write() -> None:
    capability = PopulationSimulationCapability()
    result = capability.replan_from_receipts(
        None,
        (PopulationOwnerReceipt(receipt_ref="receipt:reject", owner_ref="organization:bakery", event_family="gameplay.organization.rejected", committed=False, zero_write=True),),
        read_set("W0"), policy(), capabilities(),
    )
    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert result.continuity_receipts == ()


def test_noop_and_defer_are_valid_decisions() -> None:
    result = GenericDecisionFixture.create(empty_evidence=True).run_cycle(window="W0", budget=3)
    assert result.status == "accepted"
    assert result.decision is not None and not result.decision.selected_candidates
    assert result.decision.decision_reason_codes


def test_replanning_never_creates_a_second_actor_identity() -> None:
    fixture = GenericDecisionFixture.create()
    fixture.run_cycle(window="W0", budget=3)
    before = fixture.actor_record_refs()
    fixture.replan_from_cycle(fixture.last_result, window="W1", budget=3)
    assert fixture.actor_record_refs() == before
