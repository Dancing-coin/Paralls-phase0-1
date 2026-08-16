from __future__ import annotations

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.ecology_runtime import CropRecord, EcologyHazardAuthority, HazardRecord
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_effects import ResistanceProfile


def _hazard(**changes: object) -> HazardRecord:
    values = {
        "hazard_ref": "hazard:frost:regional:1", "region_ref": "region:valley", "effect_ref": "effect:frost",
        "severity_basis_points": 5_000, "due_tick": 3, "duration_ticks": 1,
        "causal_parent_refs": ("event:weather:1",), "semantic_revision": "semantic:1",
        "rule_revision": "rule:1", "policy_revision": "policy:1",
        "idempotency_key": "hazard:frost:regional:1", "privacy_scope": "project",
    }
    values.update(changes)
    return HazardRecord(**values)


def _crop() -> CropRecord:
    return CropRecord(crop_ref="crop:wheat:regional:1", region_ref="region:valley", plot_ref="plot:bakery:regional:1", health=100, growth_basis_points=5_000, revision=0, owner_ref="authority:crop")


def _setup(*, frost_due_tick: int = 3) -> tuple[GameplayEventStore, EcologyHazardAuthority, ConstructionProductionAuthority]:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    ecology.settle_frost(hazard=_hazard(due_tick=frost_due_tick), crop=_crop(), resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:regional:1", modifier_basis_points=0, revision=1))
    construction = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:bakery:regional:1", plot_ref="plot:bakery:regional:1", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread:regional:1", inputs={}, output_item="item:bread", duration_ticks=3)
    construction.settle_facility_acquisition(plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:1", owner_ref="owner:1"), facility=facility, command_id="command:facility:regional:1", idempotency_key="idem:facility:regional:1", causation_id="cause:facility:regional:1", correlation_id="corr:facility:regional:1")
    construction.settle_start_run(facility=facility, recipe=recipe, run_ref="run:bakery:regional:1", tick=0, command_id="command:run:regional:1", idempotency_key="idem:run:regional:1", causation_id="cause:run:regional:1", correlation_id="corr:run:regional:1")
    return store, ecology, construction


def test_committed_frost_proposal_has_no_target_and_construction_commits_one_finish_event() -> None:
    store, ecology, construction = _setup()

    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1")
    result = construction.settle_frost_due_finish(proposal.proposal)

    assert proposal.accepted is True and proposal.proposal is not None
    assert not hasattr(proposal.proposal, "run_ref")
    assert result.committed is True
    finished = store.read_events()[-1]
    assert finished.event_type == "gameplay.construction_production.run_finished"
    assert finished.payload["frost_propagation"]["hazard_ref"] == "hazard:frost:regional:1"
    assert len(result.committed_event_ids) == 1


def test_frost_finish_writes_one_scoped_outbox_entry() -> None:
    store, ecology, construction = _setup()
    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    before = len(store.list_outbox())

    construction.settle_frost_due_finish(proposal)

    assert len(store.list_outbox()) == before + 1
    assert store.list_outbox()[-1].payload_projection == {
        "facility_ref": "facility:bakery:regional:1",
        "run_ref": "run:bakery:regional:1",
        "completed_tick": 3,
    }


def test_frost_finish_duplicate_is_idempotent_without_second_production_write() -> None:
    store, ecology, construction = _setup()
    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal

    construction.settle_frost_due_finish(proposal)
    duplicate = construction.settle_frost_due_finish(proposal)

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 4


def test_frost_finish_changed_proposal_after_commit_is_zero_write_rejected() -> None:
    store, ecology, construction = _setup()
    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    construction.settle_frost_due_finish(proposal)
    before = len(store.read_events())

    changed = construction.settle_frost_due_finish(proposal.model_copy(update={"due_tick": 4}))

    assert changed.error_code == "frost_production_source_revision_conflict"
    assert changed.idempotency_status == "rejected"
    assert len(store.read_events()) == before


def test_frost_finish_source_revision_conflict_is_zero_write() -> None:
    store, ecology, construction = _setup(frost_due_tick=2)
    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    before = len(store.read_events())

    stale_source = construction.settle_frost_due_finish(proposal.model_copy(update={"source_stream_revision": 0}))

    assert stale_source.error_code == "frost_production_source_revision_conflict"
    assert len(store.read_events()) == before


def test_frost_finish_not_due_target_is_zero_write() -> None:
    store, ecology, construction = _setup(frost_due_tick=2)
    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    before = len(store.read_events())

    stale_target = construction.settle_frost_due_finish(proposal)

    assert stale_target.error_code == "frost_production_target_not_due"
    assert len(store.read_events()) == before


def test_frost_finish_missing_target_is_zero_write() -> None:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    ecology.settle_frost(hazard=_hazard(), crop=_crop(), resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:regional:1", modifier_basis_points=0, revision=1))
    construction = ConstructionProductionAuthority(store=store)
    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    before = len(store.read_events())

    result = construction.settle_frost_due_finish(proposal)

    assert result.error_code == "frost_production_target_missing"
    assert len(store.read_events()) == before


def test_frost_finish_private_scope_is_zero_write() -> None:
    scoped_store, scoped_ecology, scoped_construction = _setup()
    scoped_proposal = scoped_ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    scoped_before = len(scoped_store.read_events())

    private = scoped_construction.settle_frost_due_finish(scoped_proposal.model_copy(update={"privacy_scope": "authority_only"}))

    assert private.error_code == "frost_production_privacy_scope_denied"
    assert len(scoped_store.read_events()) == scoped_before


def test_frost_finish_retry_is_zero_write() -> None:
    scoped_store, scoped_ecology, scoped_construction = _setup()
    scoped_proposal = scoped_ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    scoped_before = len(scoped_store.read_events())

    retry = scoped_construction.settle_frost_due_finish(scoped_proposal, retry_policy={"attempts": 1})

    assert retry.error_code == "frost_production_retry_unsupported"
    assert len(scoped_store.read_events()) == scoped_before


def test_frost_finish_compensation_is_zero_write() -> None:

    scoped_store, scoped_ecology, scoped_construction = _setup()
    scoped_proposal = scoped_ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    scoped_before = len(scoped_store.read_events())
    compensation = scoped_construction.settle_frost_due_finish(scoped_proposal, compensation_policy={"event": "ecology.compensate"})

    assert compensation.error_code == "frost_production_compensation_unsupported"
    assert len(scoped_store.read_events()) == scoped_before


def test_frost_finish_public_projection_redacts_provenance() -> None:
    _, ecology, construction = _setup()
    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    construction.settle_frost_due_finish(proposal)

    public = construction.frost_finish_projection(scope="public")

    assert public["frost_propagation"] == ()


def test_frost_finish_authority_projection_retains_provenance() -> None:
    _, ecology, construction = _setup()
    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    construction.settle_frost_due_finish(proposal)

    authority = construction.frost_finish_projection(scope="authority")

    assert authority["frost_propagation"][0]["hazard_ref"] == "hazard:frost:regional:1"


def test_frost_finish_checkpoint_tail_replay_is_deterministic() -> None:
    _, ecology, construction = _setup()
    proposal = ecology.propose_frost_due_finish(hazard_ref="hazard:frost:regional:1").proposal
    construction.settle_frost_due_finish(proposal)

    assert construction.replay_projection().projection_hash == construction.replay_projection(checkpoint_at=2).projection_hash
