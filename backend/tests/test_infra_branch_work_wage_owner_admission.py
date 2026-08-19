from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import WorkerContributionRef
from app.gameplay.replay import GameplayProjectionReplay
from app.population_continuity.batch import (
    BranchWorkWageRequest,
    ContinuityMergeAuthority,
    PopulationPlanner,
    _production_wage_plan_digest,
)
from app.population_continuity.branch_preview import (
    BranchPreviewAuthority,
    BranchPreviewRequest,
    CalibrationInput,
    ReferenceDataset,
    _event_digest,
)
from app.population_continuity.models import BatchIntentCandidate, PopulationWorldPlan, WorldModeProfile
from app.population_continuity.source_inputs import ProductionCompletedEvidenceInput


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="simulation",
        revision="policy:1",
        cadence_class="daily",
        batch_limit=1,
        wake_budget=1,
        catch_up_limit=1,
        allowed_intent_kinds=("work",),
        degraded_threshold=1,
        allowed_privacy_scopes=("actor:self",),
    )


def _contribution() -> WorkerContributionRef:
    return WorkerContributionRef(
        actor_ref="character:char_b",
        assignment_ref="assignment:baker",
        work_order_ref="work:bread",
        evidence_refs=("evidence:input:bread:1",),
        contribution_digest="sha256:contribution:bread:1",
    )


def _source() -> tuple[GameplayEventStore, ConstructionProductionAuthority, ProductionCompletedEvidenceInput]:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:bakery", plot_ref="plot:bakery", facility_kind="oven", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread", inputs={}, output_item="item:bread", duration_ticks=2)
    assert authority.settle_facility_acquisition(
        plot=Plot(plot_ref="plot:bakery", jurisdiction_ref="jurisdiction:bakery", owner_ref="org:bakery"),
        facility=facility,
        command_id="facility:acquire",
        idempotency_key="facility:acquire",
        causation_id="cause",
        correlation_id="corr",
    ).committed
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:bread:1",
        tick=1,
        command_id="run:start",
        idempotency_key="run:start",
        causation_id="cause",
        correlation_id="corr",
        worker_contribution_refs=(_contribution(),),
    ).committed
    assert authority.settle_finish_run(
        authority.projector().runs["run:bread:1"],
        tick=3,
        recipe=recipe,
        command_id="run:finish",
        idempotency_key="run:finish",
        causation_id="cause",
        correlation_id="corr",
    ).committed
    evidence_ref = "evidence:production-completed:run:bread:1:sha256:contribution:bread:1"
    assert authority.record_completed_work_evidence(
        run_ref="run:bread:1",
        contribution=_contribution(),
        evidence_ref=evidence_ref,
        observed_at="2026-08-13T00:00:00Z",
        command_id="evidence:1",
        idempotency_key="evidence:1",
        causation_id="cause",
        correlation_id="corr",
    ).committed
    return store, authority, ProductionCompletedEvidenceInput.freeze(
        recipient_ref="character:char_b",
        observed_at="2026-08-13T00:01:00Z",
        view=authority.completed_evidence_view_for(recipient_ref="character:char_b"),
    )


def _candidate() -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref="intent:branch-wage:1",
        profile_ref="character:char_b",
        intent_kind="work",
        payload={
            "organization_ref": "org:bakery",
            "wage_obligation_ref": "wage:bread:1",
            "wage_amount_minor": 75,
            "wage_policy_revision": "policy:wage:1",
        },
        expected_revisions={},
        policy_revision="policy:1",
        package_revision="package:1",
        idempotency_key="intent:branch-wage:1",
        correlation_id="corr:branch-wage:1",
        source_ref="planner",
        privacy_scope="actor:self",
    )


def _plan(store: GameplayEventStore, source: ProductionCompletedEvidenceInput) -> PopulationWorldPlan:
    candidate = _candidate()
    wage_stream = "gameplay:economy:wage:character:char_b"
    planned = PopulationPlanner().plan_production_evidence_wage(
        store=store,
        batch_ref="batch:branch-wage:1",
        world_ref="world:bakery",
        mode=_mode(),
        production_evidence_input=source,
        candidate=candidate.model_copy(update={"expected_revisions": {wage_stream: store.get_stream_head(wage_stream)}}),
        base_event_digest="sha256:base",
        tail_boundary=len(store.read_events()),
        active_revision_refs=("policy:wage:1",),
        deterministic_seed="seed",
        report_scope="actor:self",
    )
    assert planned.accepted and planned.plan is not None
    return planned.plan


def _branch(store: GameplayEventStore, candidate: BatchIntentCandidate) -> tuple[BranchPreviewAuthority, dict[str, object]]:
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    base_events = store.read_events()
    branch_ref = "branch:work-wage:1"
    request = BranchPreviewRequest(
        branch_ref=branch_ref,
        world_ref="world:bakery",
        base_event_digest=_event_digest(base_events),
        base_checkpoint_sequence=len(base_events),
        tail_boundary=len(base_events),
        deterministic_seed="seed:branch-wage",
        active_revision_refs=("policy:1",),
        calibration_ref="calibration:1",
        privacy_scope="creator_debug",
    )
    assert authority.preview(
        request=request,
        dataset=ReferenceDataset(
            dataset_ref="dataset:branch-wage:1",
            provenance="fixture",
            license_ref="license:permitted",
            schema_revision="1",
            digest="sha256:dataset:branch-wage",
            classification="creator_debug",
            allowed_scopes=("creator_debug",),
        ),
        calibration=CalibrationInput(
            calibration_ref="calibration:1",
            dataset_ref="dataset:branch-wage:1",
            parameter_mapping_revision="map:1",
            world_revision="world:1",
            ruleset_revision="rules:1",
            privacy_scope="creator_debug",
        ),
        family_inputs=(),
        candidates=(candidate,),
        mode=_mode(),
    ).accepted
    assert authority.record_isolated_branch_snapshot(
        branch_ref=branch_ref,
        expected_revision=0,
        idempotency_key="snapshot:branch-wage:1",
        privacy_scope="creator_debug",
    ).committed
    snapshot = store.read_stream(authority.admission_stream_id(branch_ref=branch_ref))[0]
    return authority, dict(snapshot.payload)


def _request(plan: PopulationWorldPlan, snapshot: dict[str, object], **overrides: object) -> BranchWorkWageRequest:
    descriptor = next(record for record in snapshot["records"] if record["kind"] == "branch_descriptor")
    candidate_record = next(record for record in snapshot["records"] if record.get("kind") == "branch_candidate_proposed")
    values = {
        "batch_ref": plan.batch_ref,
        "branch_ref": snapshot["branch_ref"],
        "branch_buffer_digest": snapshot["buffer_digest"],
        "branch_base_event_digest": descriptor["base_event_digest"],
        "branch_base_checkpoint_sequence": descriptor["base_checkpoint_sequence"],
        "branch_tail_boundary": descriptor["tail_boundary"],
        "branch_replay_contract_digest": descriptor["replay_contract_digest"],
        "candidate_intent_ref": candidate_record["intent_ref"],
        "candidate_digest": candidate_record["candidate_digest"],
        "worker_ref": "character:char_b",
        "production_evidence_ref": plan.production_evidence_refs[0],
        "authenticated_actor_ref": "character:char_b",
        "wage_plan_digest": _production_wage_plan_digest(plan),
    }
    values.update(overrides)
    return BranchWorkWageRequest(**values)


def test_inf4t_commits_only_existing_economy_wage_for_committed_production_and_valid_branch_request() -> None:
    store, _, source = _source()
    plan = _plan(store, source)
    _, snapshot = _branch(store, plan.candidates[0])
    result = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode()).merge_branch_work_wage(request=_request(plan, snapshot), wage_plan=plan)
    assert result.committed and result.owner_receipt_ref == EconomyAuthority._PRINCIPAL
    assert store.read_events()[-1].event_type == "gameplay.economy.wage_accrued"
    assert all(not event.stream_id.startswith("gameplay:branch_preview:") for event in store.read_events()[-1:])
    outbox = store.list_outbox()[-1]
    assert outbox.audience == "actor:character:char_b"
    assert outbox.payload_projection == {"accrual_ref": "wage:bread:1", "evidence_ref": plan.production_evidence_refs[0]}


def test_inf4t_rejects_branch_only_or_forged_pins_without_write() -> None:
    store, _, source = _source()
    plan = _plan(store, source)
    _, snapshot = _branch(store, plan.candidates[0])
    merge = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode())
    before = len(store.read_events())
    missing = merge.merge_branch_work_wage(request=_request(plan, snapshot, production_evidence_ref="evidence:missing"), wage_plan=plan)
    forged = merge.merge_branch_work_wage(request=_request(plan, snapshot, branch_buffer_digest="sha256:forged"), wage_plan=plan)
    assert not missing.committed and not forged.committed
    assert len(store.read_events()) == before


def test_inf4t_rejects_worker_privacy_revision_and_caller_target_fields_without_write() -> None:
    store, _, source = _source()
    plan = _plan(store, source)
    _, snapshot = _branch(store, plan.candidates[0])
    merge = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode())
    before = len(store.read_events())
    for update in (
        {"worker_ref": "character:other", "authenticated_actor_ref": "character:other"},
        {"authenticated_actor_ref": "authority:caller"},
        {"branch_replay_contract_digest": "sha256:forged"},
        {"wage_plan_digest": "sha256:forged"},
    ):
        result = merge.merge_branch_work_wage(request=_request(plan, snapshot, **update), wage_plan=plan)
        assert not result.committed
    assert len(store.read_events()) == before

    stale_source_store, source_authority, stale_source = _source()
    stale_source_plan = _plan(stale_source_store, stale_source)
    _, stale_source_snapshot = _branch(stale_source_store, stale_source_plan.candidates[0])
    assert source_authority.settle_maintenance_obligation(
        source_authority.projector().runs["run:bread:1"],
        obligation_ref="obligation:stale-source:1",
        command_id="maintenance:stale-source:1",
        idempotency_key="maintenance:stale-source:1",
        causation_id="cause",
        correlation_id="corr",
    ).committed
    source_before = len(stale_source_store.read_events())
    stale_source_result = ContinuityMergeAuthority(store=stale_source_store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode()).merge_branch_work_wage(request=_request(stale_source_plan, stale_source_snapshot), wage_plan=stale_source_plan)
    assert not stale_source_result.committed and len(stale_source_store.read_events()) == source_before

    stale_wage_store, _, stale_wage_source = _source()
    stale_wage_plan = _plan(stale_wage_store, stale_wage_source)
    stale_wage_candidate = stale_wage_plan.candidates[0].model_copy(
        update={"expected_revisions": {"gameplay:economy:wage:character:char_b": 1}}
    )
    stale_wage_plan = stale_wage_plan.model_copy(update={"candidates": (stale_wage_candidate,)})
    _, stale_wage_snapshot = _branch(stale_wage_store, stale_wage_candidate)
    wage_before = len(stale_wage_store.read_events())
    stale_wage_result = ContinuityMergeAuthority(store=stale_wage_store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode()).merge_branch_work_wage(request=_request(stale_wage_plan, stale_wage_snapshot), wage_plan=stale_wage_plan)
    assert not stale_wage_result.committed and len(stale_wage_store.read_events()) == wage_before


def test_inf4t_exact_duplicate_replays_changed_duplicate_is_zero_write_and_replay_is_separate() -> None:
    store, _, source = _source()
    plan = _plan(store, source)
    branch, snapshot = _branch(store, plan.candidates[0])
    merge = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode())
    request = _request(plan, snapshot)
    first = merge.merge_branch_work_wage(request=request, wage_plan=plan)
    duplicate = merge.merge_branch_work_wage(request=request, wage_plan=plan)
    changed = merge.merge_branch_work_wage(request=request.model_copy(update={"candidate_digest": "sha256:changed"}), wage_plan=plan)
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert branch.durable_branch_projection("branch:work-wage:1")["projection_hash"] == branch.durable_branch_projection("branch:work-wage:1", checkpoint_at=1)["projection_hash"]
    assert len(store.read_stream("gameplay:economy:wage:character:char_b")) == 1
    assert branch.production_replay().projection_hash == branch.production_replay(checkpoint_at=4).projection_hash
    replay = GameplayProjectionReplay(projector_id="branch-work-wage", projector_version="1")
    assert replay.full_replay(store.read_events()).projection_hash == replay.checkpoint_plus_tail_replay(replay.create_checkpoint(store.read_events()[:4]), store.read_events()[4:]).projection_hash


def test_inf4t_branch_scope_is_creator_debug_and_no_combined_or_compensation_surface_exists() -> None:
    store, _, source = _source()
    plan = _plan(store, source)
    _, snapshot = _branch(store, plan.candidates[0])
    assert snapshot["records"]
    result = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode()).merge_branch_work_wage(request=_request(plan, snapshot, branch_base_event_digest="sha256:empty"), wage_plan=plan)
    assert not result.committed
    assert all(event.visibility_policy != "public" for event in store.read_events())
    assert not any("compens" in event.event_type or "payroll" in event.event_type for event in store.read_events())
