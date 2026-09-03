from app.character_agent.models.simulation_seed import CharacterContinuityReceipt
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationOwnerReceipt,
    PopulationProjection,
    PopulationReadSet,
)
from app.services.siming_population_capability import PopulationSimulationCapability


def _read_set(
    window: str = "W0",
    budget: int = 3,
    revision: int = 1,
    *,
    selector_revision: str = "selector:cohort-bakery:v1",
    ruleset_revision: str = "rules:cohort-bakery:v1",
    policy_revision: str = "mode:v1",
    catch_up_limit: int = 3,
):
    cadence = PopulationCadenceInput(
        cadence_id=f"cadence:cohort:bakery:{window}", world_ref="world:bakery", world_mode_ref="mode:bakery",
        world_mode_revision="mode:v1", cadence_source_ref="world:bakery", cadence_source_revision=revision,
        window_start=0, window_end=1, base_checkpoint_ref="checkpoint:1", base_checkpoint_digest="sha256:cp",
        base_revision_vector={"world:bakery": revision}, policy_revision=policy_revision, selector_revision=selector_revision,
        ruleset_revision=ruleset_revision, deterministic_seed=f"seed:{window}", catch_up_limit=catch_up_limit, budget=budget,
        report_scope="organization:summary",
    )
    rows = (
        PopulationProjection(ref=f"projection:char_a:{window}", scope="organization:summary", revision_vector={"world:bakery": revision}, payload={"actor_ref": "character:char_a", "candidate_kind": "schedule_gated_supply"}),
        PopulationProjection(ref=f"projection:char_b:{window}", scope="public", revision_vector={"world:bakery": revision}, payload={"actor_ref": "character:char_b", "candidate_kind": "routine_work"}),
        PopulationProjection(ref=f"projection:char_c:{window}", scope="organization:summary", revision_vector={"world:bakery": revision}, payload={"actor_ref": "character:char_c", "candidate_kind": "relationship_negotiation"}),
    )
    return cadence, PopulationReadSet.from_inputs(cadence, rows)


class _Owner:
    def __init__(self, committed=True): self.calls, self.committed, self.keys = [], committed, set()
    def submit(self, intent, *, read_set):
        self.calls.append(intent)
        duplicate = intent.idempotency_key in self.keys
        self.keys.add(intent.idempotency_key)
        return PopulationOwnerReceipt(receipt_ref=f"receipt:{intent.intent_ref}", owner_ref="owner:organization", event_family="gameplay.organization.commerce_commitment_accepted", committed=self.committed, revision_vector={"world:bakery": 2}, zero_write=not self.committed, idempotency_status="duplicate_replayed" if duplicate else ("new_commit" if self.committed else "idempotency_key_reused"))


class _Continuity:
    def __init__(self): self.revisions = {"character:char_a": 0, "character:char_b": 0, "character:char_c": 0}; self.commands = []
    def current_revision(self, actor_ref): return self.revisions[actor_ref]
    def apply_command(self, command):
        self.commands.append(command)
        before = self.revisions[command.actor_ref]
        duplicate = any(item.command_id == command.command_id for item in self.commands[:-1])
        if duplicate:
            return CharacterContinuityReceipt(receipt_ref=f"receipt:{command.command_id}", command_id=command.command_id, actor_ref=command.actor_ref, status="idempotent_replay", character_revision_before=before, character_revision_after=before)
        self.revisions[command.actor_ref] += 1
        return CharacterContinuityReceipt(receipt_ref=f"receipt:{command.command_id}", command_id=command.command_id, actor_ref=command.actor_ref, status="committed", character_revision_before=before, character_revision_after=before + 1)


class CohortCapabilityFixture:
    def __init__(self):
        self.owner, self.continuity = _Owner(), _Continuity()
        self.capability = PopulationSimulationCapability(owner_executor=self.owner, continuity_port=self.continuity)

    @classmethod
    def create(cls): return cls()

    def run_window(self, window="W0", *, revision=1):
        cadence, read_set = _read_set(window, revision=revision)
        return self.capability.run_cohort_cycle(cadence, read_set)


def test_w0_routes_owner_char_a_and_core_char_a_char_b_only():
    cadence, read_set = _read_set()
    owner, continuity = _Owner(), _Continuity()
    result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_cohort_cycle(cadence, read_set)
    assert result.status == "accepted"
    assert [call.profile_ref for call in owner.calls] == ["character:char_a"]
    assert [command.actor_ref for command in continuity.commands] == ["character:char_a", "character:char_b"]
    assert result.report.cohort_ref == "cohort:bakery:W0"


def test_missing_owner_receipt_blocks_all_cohort_core_commands():
    cadence, read_set = _read_set()
    owner, continuity = _Owner(False), _Continuity()
    result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_cohort_cycle(cadence, read_set)
    assert result.status == "owner_settlement_required"
    assert continuity.commands == []
    assert any(seed.owner_effect_status == "owner_settlement_required" for seed in result.seed_candidates)


def test_budget_two_leaves_char_c_unprocessed_and_never_core_command():
    cadence, read_set = _read_set(budget=2)
    owner, continuity = _Owner(), _Continuity()
    result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_cohort_cycle(cadence, read_set)
    assert result.report.unprocessed_cohort_refs == ("projection:char_c:W0",)
    assert all(command.actor_ref != "character:char_c" for command in continuity.commands)


def test_w1_uses_new_source_revision_and_per_actor_monotonic_revision():
    fixture = CohortCapabilityFixture.create()
    assert fixture.run_window("W0").status == "accepted"
    assert fixture.run_window("W1", revision=2).status == "accepted"
    assert [command.expected_character_revision for command in fixture.continuity.commands if command.actor_ref == "character:char_a"] == [0, 1]
    assert [command.expected_character_revision for command in fixture.continuity.commands if command.actor_ref == "character:char_b"] == [0, 1]


def test_duplicate_replay_and_changed_source_are_distinct():
    fixture = CohortCapabilityFixture.create()
    fixture.run_window("W0")
    duplicate = fixture.run_window("W0")
    assert duplicate.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert duplicate.continuity_receipts[0].status == "idempotent_replay"

    changed = fixture.run_window("W1", revision=3)
    assert changed.status == "accepted"


def test_cohort_projection_exposure_cannot_create_char_b_memory_candidate():
    cadence, read_set = _read_set()
    rows = tuple(p.model_copy(update={"payload": {**p.payload, "exposure_basis": "affected_directly"}}) if p.payload["actor_ref"] == "character:char_b" else p for p in read_set.projections)
    read_set = read_set.from_inputs(cadence, rows)
    owner, continuity = _Owner(), _Continuity()
    result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_cohort_cycle(cadence, read_set)
    routine = next(seed for seed in result.seed_candidates if seed.actor_ref == "character:char_b")
    assert routine.memory_candidates == ()


def test_changed_v1_pins_requeue_before_owner_and_character_core():
    for changed in (
        {"selector_revision": "selector:forged"},
        {"ruleset_revision": "rules:forged"},
        {"policy_revision": "policy:forged"},
    ):
        cadence, read_set = _read_set(**changed)
        owner, continuity = _Owner(), _Continuity()
        result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_cohort_cycle(cadence, read_set)
        assert result.status == "requeue"
        assert result.reason == "stale_read_set"
        assert owner.calls == []
        assert continuity.commands == []


def test_missing_duplicate_or_mismatched_fixed_actor_requeues_zero_write():
    cadence, base = _read_set()
    variants = (
        base.projections[:2],
        (base.projections[0], base.projections[0].model_copy(update={"ref": "projection:char_a:W0:duplicate"}), base.projections[2]),
        tuple(
            projection.model_copy(update={"ref": "projection:char_x:W0"})
            if projection.payload["actor_ref"] == "character:char_c"
            else projection
            for projection in base.projections
        ),
        tuple(
            projection.model_copy(update={"payload": {**projection.payload, "actor_ref": "character:unknown"}})
            if projection.payload["actor_ref"] == "character:char_c"
            else projection
            for projection in base.projections
        ),
    )
    for rows in variants:
        read_set = PopulationReadSet.from_inputs(cadence, rows)
        owner, continuity = _Owner(), _Continuity()
        result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_cohort_cycle(cadence, read_set)
        assert result.status == "requeue"
        assert result.reason == "cohort_input_invalid"
        assert owner.calls == []
        assert continuity.commands == []


def test_catch_up_zero_leaves_all_fixed_actors_unprocessed():
    cadence, read_set = _read_set(catch_up_limit=0)
    owner, continuity = _Owner(), _Continuity()
    result = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity).run_cohort_cycle(cadence, read_set)
    assert result.status == "accepted"
    assert result.report.selected_cohort_refs == ()
    assert result.report.unprocessed_cohort_refs == (
        "projection:char_a:W0",
        "projection:char_b:W0",
        "projection:char_c:W0",
    )
    assert owner.calls == []
    assert continuity.commands == []
