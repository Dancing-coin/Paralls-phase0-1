from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.population_continuity.batch import ContinuityMergeAuthority, PopulationPlanner
from app.population_continuity.branch_preview import BranchPreviewRequest
from app.population_continuity.models import BatchIntentCandidate, PopulationWorldPlan, WorldModeProfile


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="simulation",
        revision="mode:inf4z:1",
        cadence_class="daily",
        batch_limit=2,
        wake_budget=2,
        catch_up_limit=1,
        allowed_intent_kinds=("supply", "inspection"),
        degraded_threshold=1,
    )


def _mode_for(mode_name: str, *, cadence_class: str, batch_limit: int, wake_budget: int) -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode=mode_name,
        revision=f"mode:inf4z:{mode_name}:1",
        cadence_class=cadence_class,
        batch_limit=batch_limit,
        wake_budget=wake_budget,
        catch_up_limit=1,
        allowed_intent_kinds=("supply", "inspection"),
        degraded_threshold=1,
    )


def _candidate(*, intent_kind: str = "supply") -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref=f"intent:inf4z:{intent_kind}",
        profile_ref="character:char_a",
        intent_kind=intent_kind,
        payload={
            "organization_ref": "organization:bakery",
            "counterparty_organization_ref": "organization:supplier",
            "commitment_ref": "commitment:inf4z:supply",
            "organization_grant_refs": [],
            "budget_reservation_refs": [],
            "stream_ref": "gameplay:organization:organization:bakery",
            "inspection_ref": "inspection:inf4z",
            "jurisdiction_ref": "jurisdiction:bakery",
            "policy_digest": "sha256:policy:inf4z",
            "evidence_ref": "evidence:inspection:inf4z",
            "passed": True,
        },
        expected_revisions={"gameplay:organization:organization:bakery": 0},
        policy_revision="mode:inf4z:1",
        package_revision="package:inf4z:1",
        idempotency_key=f"intent:inf4z:{intent_kind}",
        correlation_id="corr:inf4z",
        source_ref="population:planner",
        privacy_scope="actor:self",
    )


def test_inf4z_world_plan_pins_base_tail_revisions_and_budget() -> None:
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:1",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(_candidate(),),
        base_event_digest="sha256:base",
        tail_boundary=3,
        active_revision_refs=("mode:inf4z:1", "rules:inf4z:1"),
        source_revision_vector={"gameplay:organization:organization:bakery": 0},
        deterministic_seed="seed:inf4z",
        report_scope="actor:self",
    )

    assert isinstance(plan, PopulationWorldPlan)
    assert plan.base_event_digest == "sha256:base"
    assert plan.tail_boundary == 3
    assert plan.budget == 2
    assert plan.active_revision_refs == ("mode:inf4z:1", "rules:inf4z:1")


def _plan_for_mode(mode: WorldModeProfile) -> PopulationWorldPlan:
    return PopulationPlanner().plan_world(
        batch_ref=f"batch:inf4z:{mode.mode}",
        world_ref="world:bakery",
        mode=mode,
        candidates=(_candidate(),),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=(mode.revision,),
        source_revision_vector={"gameplay:organization:organization:bakery": 0},
        deterministic_seed=f"seed:inf4z:{mode.mode}",
        report_scope="actor:self",
    )


def test_inf4z_game_mode_preserves_caller_selected_interactive_budget() -> None:
    mode = _mode_for("game", cadence_class="interactive", batch_limit=1, wake_budget=1)
    plan = _plan_for_mode(mode)

    assert (plan.mode, plan.budget, plan.policy_revision) == ("game", 1, mode.revision)


def test_inf4z_simulation_mode_preserves_caller_selected_daily_budget() -> None:
    mode = _mode_for("simulation", cadence_class="daily", batch_limit=2, wake_budget=2)
    plan = _plan_for_mode(mode)

    assert (plan.mode, plan.budget, plan.policy_revision) == ("simulation", 2, mode.revision)


def test_inf4z_preview_mode_preserves_caller_selected_fixed_base_budget() -> None:
    mode = _mode_for("preview", cadence_class="fixed-base", batch_limit=3, wake_budget=3)
    plan = _plan_for_mode(mode)

    assert (plan.mode, plan.budget, plan.policy_revision) == ("preview", 3, mode.revision)


def test_inf4z_preview_world_plan_is_zero_write_at_production_merge_boundary() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    preview_mode = _mode_for("preview", cadence_class="fixed-base", batch_limit=1, wake_budget=1)
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:preview",
        world_ref="world:bakery",
        mode=preview_mode,
        candidates=(_candidate(),),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=(preview_mode.revision,),
        source_revision_vector={"gameplay:organization:organization:bakery": 0},
        deterministic_seed="seed:inf4z:preview",
        report_scope="actor:self",
    )

    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=preview_mode).merge_world_plan(plan)

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "preview_requires_branch"
    assert store.read_events() == []


def test_inf4z_supply_uses_existing_organization_owner_fragment_and_receipt() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:supply",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(_candidate(),),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4z:1",),
        source_revision_vector={"gameplay:organization:organization:bakery": 0},
        deterministic_seed="seed:inf4z",
        report_scope="actor:self",
    )

    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode()).merge_world_plan(plan)

    assert receipt.committed is True
    assert receipt.owner_receipt_ref == "actor_gameplay.organization_domain"
    event = store.read_stream("gameplay:organization:organization:bakery")[0]
    assert event.payload["owner_principal_ref"] == "actor_gameplay.organization_domain"
    assert event.event_type == "gameplay.organization.commerce_commitment_accepted"


def test_inf4z_unmapped_work_intent_is_zero_write() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:work",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(_candidate(intent_kind="work"),),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4z:1",),
        source_revision_vector={"gameplay:organization:organization:bakery": 0},
        deterministic_seed="seed:inf4z",
        report_scope="actor:self",
    )

    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode()).merge_world_plan(plan)

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "owner_mapping_unsupported"
    assert store.read_events() == []


def test_inf4z_legacy_population_merge_cannot_write_free_form_stream_or_event() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    candidate = _candidate(intent_kind="supply").model_copy(
        update={
            "payload": {
                "stream_ref": "population:character:char_a",
                "event_type": "population.intent.proposed",
            },
            "expected_revisions": {"population:character:char_a": 0},
            "idempotency_key": "intent:inf4z:legacy-free-form",
        }
    )
    plan = PopulationPlanner().plan(
        batch_ref="batch:inf4z:legacy-free-form",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(candidate,),
        input_digest="sha256:legacy-free-form",
        deterministic_seed="seed:inf4z:legacy-free-form",
    )

    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode()).merge(plan)

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "legacy_population_merge_retired"
    assert store.read_events() == []
    assert store.list_outbox() == []


def test_inf4z_inspection_uses_existing_government_owner_fragment_and_receipt() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    candidate = _candidate(intent_kind="inspection").model_copy(update={
        "expected_revisions": {"gameplay:government:organization:bakery": 0},
        "idempotency_key": "intent:inf4z:inspection",
    })
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:inspection",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(candidate,),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4z:1",),
        source_revision_vector={"gameplay:government:organization:bakery": 0},
        deterministic_seed="seed:inf4z",
        report_scope="actor:self",
    )
    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode()).merge_world_plan(plan)

    assert receipt.committed is True
    assert receipt.owner_receipt_ref == "actor_gameplay.government_domain"
    assert [event.event_type for event in store.read_stream("gameplay:government:organization:bakery")] == ["gameplay.government.inspection_recorded"]


def test_inf4z_inspection_writes_redacted_scoped_outbox_projection() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    candidate = _candidate(intent_kind="inspection").model_copy(update={
        "expected_revisions": {"gameplay:government:organization:bakery": 0},
        "idempotency_key": "intent:inf4z:inspection:outbox",
    })
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:inspection:outbox",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(candidate,),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4z:1",),
        source_revision_vector={"gameplay:government:organization:bakery": 0},
        deterministic_seed="seed:inf4z:inspection:outbox",
        report_scope="actor:self",
    )

    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode()).merge_world_plan(plan)
    inspection_outbox = [
        entry
        for entry in store.list_outbox()
        if entry.topic == "world.government.inspection.scoped_projection"
    ]
    replay = GameplayProjectionReplay(projector_id="population-continuity", projector_version="1")
    events = store.read_events()
    checkpoint = replay.create_checkpoint(events[:1])

    assert receipt.committed is True
    assert len(inspection_outbox) == 1
    assert inspection_outbox[0].audience == "actor:self"
    assert inspection_outbox[0].payload_projection == {
        "inspection_ref": "inspection:inf4z",
        "organization_ref": "organization:bakery",
        "jurisdiction_ref": "jurisdiction:bakery",
        "passed": True,
    }
    assert "evidence_ref" not in inspection_outbox[0].payload_projection
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(checkpoint, events[1:]).projection_hash


def test_inf4z_supply_production_full_and_checkpoint_tail_replay_match() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:replay",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(_candidate(),),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4z:1",),
        source_revision_vector={"gameplay:organization:organization:bakery": 0},
        deterministic_seed="seed:inf4z",
        report_scope="actor:self",
    )
    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode()).merge_world_plan(plan)
    replay = GameplayProjectionReplay(projector_id="population-continuity", projector_version="1")
    events = store.read_events()
    checkpoint = replay.create_checkpoint(events[:1])

    assert receipt.committed is True
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(checkpoint, events[1:]).projection_hash


def test_inf4z_supply_duplicate_idempotency_replays_existing_owner_receipt() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:duplicate",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(_candidate(),),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4z:1",),
        source_revision_vector={"gameplay:organization:organization:bakery": 0},
        deterministic_seed="seed:inf4z",
        report_scope="actor:self",
    )

    authority = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode())
    first = authority.merge_world_plan(plan)
    duplicate = authority.merge_world_plan(plan)

    assert first.committed is True
    assert duplicate.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1


def test_inf4z_supply_revision_conflict_is_zero_write() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:revision-conflict",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(_candidate(),),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4z:1",),
        source_revision_vector={"gameplay:organization:organization:bakery": 1},
        deterministic_seed="seed:inf4z",
        report_scope="actor:self",
    )

    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode()).merge_world_plan(plan)

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "source_revision_stale"
    assert store.read_events() == []


def test_inf4z_supply_privacy_scope_denial_is_zero_write() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:privacy",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(_candidate(),),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4z:1",),
        source_revision_vector={"gameplay:organization:organization:bakery": 0},
        deterministic_seed="seed:inf4z",
        report_scope="authority:private",
    )

    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode()).merge_world_plan(plan)

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "privacy_denial"
    assert store.read_events() == []


def test_inf4z_activation_lock_pending_is_zero_write() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    plan = PopulationPlanner().plan_world(
        batch_ref="batch:inf4z:lock-pending",
        world_ref="world:bakery",
        mode=_mode(),
        candidates=(_candidate(),),
        base_event_digest="sha256:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4z:1",),
        source_revision_vector={"gameplay:organization:organization:bakery": 0},
        deterministic_seed="seed:inf4z",
        report_scope="actor:self",
        activation_lock_refs=("lock:world:bakery:character:char_a",),
    )

    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode()).merge_world_plan(plan)

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "activation_lock_pending"
    assert store.read_events() == []


def test_inf4z_branch_request_pins_tail_and_source_digests() -> None:
    request = BranchPreviewRequest(
        branch_ref="branch:inf4z",
        world_ref="world:bakery",
        base_event_digest="sha256:base",
        base_checkpoint_sequence=2,
        tail_boundary=5,
        source_digests={"social": "sha256:social", "organization": "sha256:org"},
        active_revision_refs=("mode:inf4z:1", "rules:inf4z:1"),
        deterministic_seed="seed:inf4z",
        calibration_ref="calibration:1",
        privacy_scope="creator_debug",
    )

    assert request.base_checkpoint_sequence == 2
    assert request.tail_boundary == 5
    assert request.source_digests["organization"] == "sha256:org"
