from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.civilization_capability_runtime import (
    CivilizationCapabilityAuthority,
    CivilizationCapabilityRecord,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.social_knowledge import SocialRecipientView
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.population_continuity.batch import PopulationPlanner
from app.population_continuity.batch import ContinuityMergeAuthority
from app.population_continuity.models import (
    BatchIntentCandidate,
    PopulationWorldPlan,
    WorldModeProfile,
)
from app.population_continuity.social_input import FrozenSocialPlanningInput
from app.population_continuity.source_inputs import (
    HouseholdScheduleInput,
    OrganizationScheduleInput,
)


def _view(*, digest: str = "sha256:social-view") -> SocialRecipientView:
    return SocialRecipientView(
        relationship_facts=(
            {
                "relationship_ref": "gameplay:relationship:public",
                "source_ref": "character:guard:alpha",
                "target_ref": "character:baker:beta",
                "relation_kind": "trusts",
                "projected_confidence": 0.8,
                "visibility": "public",
            },
        ),
        knowledge_facts=(),
        reputation={"character:baker:beta": {"trusts": 0.8}},
        source_revision_vector={"gameplay:relationship:public": 1},
        projection_hash=digest,
    )


def _record_social_source(store: GameplayEventStore) -> None:
    result = store.append_batch(
        build_atomic_event_batch(
            command_id="command:inf4r:social-source",
            principal_ref="authority:p5:social",
            stream_id="gameplay:relationship:public",
            expected_revision=0,
            event_specs=[("gameplay.social.relationship_fact_recorded", {"source": "test"})],
            idempotency_key="inf4r:social-source",
            causation_id="cause:inf4r:social-source",
            correlation_id="corr:inf4r:social-source",
        )
    )
    assert result.committed is True


def test_inf4r_freezes_social_view_recipient_time_digest_and_source_vector() -> None:
    frozen = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:guard:alpha",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(),
    )

    assert frozen.recipient_ref == "character:guard:alpha"
    assert frozen.observed_at == "2026-08-13T00:00:00Z"
    assert frozen.projection_digest == "sha256:social-view"
    assert frozen.source_revision_vector == {"gameplay:relationship:public": 1}


def test_inf4r_frozen_social_input_rejects_stale_source_vector_without_writes() -> None:
    store = GameplayEventStore()
    frozen = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:guard:alpha",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(),
    )

    result = frozen.validate_against(store=store)

    assert result.accepted is False
    assert result.error_code == "social_source_revision_stale"
    assert store.read_events() == []


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="simulation",
        revision="mode:inf4r:1",
        cadence_class="daily",
        batch_limit=2,
        wake_budget=2,
        catch_up_limit=1,
        allowed_intent_kinds=("work",),
        degraded_threshold=1,
    )


def _candidate() -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref="intent:inf4r:work",
        profile_ref="character:char_a",
        intent_kind="work",
        payload={"stream_ref": "population:character:char_a", "event_type": "population.intent.proposed"},
        expected_revisions={"population:character:char_a": 0},
        policy_revision="mode:inf4r:1",
        package_revision="package:inf4r:1",
        idempotency_key="intent:inf4r:work",
        correlation_id="corr:inf4r:work",
        source_ref="population:planner",
        privacy_scope="actor:self",
    )


def test_inf4r_planner_pins_social_view_digest_into_deterministic_plan() -> None:
    store = GameplayEventStore()
    _record_social_source(store)
    social_input = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(digest="sha256:scoped-social"),
    )

    result = PopulationPlanner().plan_from_social_input(
        store=store,
        batch_ref="batch:inf4r:daily",
        world_ref="world:bakery",
        mode=_mode(),
        social_input=social_input,
        candidates=(_candidate(),),
        deterministic_seed="seed:inf4r",
    )

    assert result.accepted is True and result.plan is not None
    assert result.plan.input_digest == social_input.input_digest
    assert result.plan.candidates == (_candidate(),)
    assert len(store.read_events()) == 1


def test_inf4r_planner_rejects_unsupported_schedule_or_capability_inputs_without_writes() -> None:
    store = GameplayEventStore()
    _record_social_source(store)
    social_input = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(),
    )

    result = PopulationPlanner().plan_from_social_input(
        store=store,
        batch_ref="batch:inf4r:unsupported",
        world_ref="world:bakery",
        mode=_mode(),
        social_input=social_input,
        candidates=(_candidate(),),
        deterministic_seed="seed:inf4r",
        unsupported_inputs=("household_schedule", "organization_schedule", "civilization_capability"),
    )

    assert result.accepted is False
    assert result.error_code == "inf4r_unsupported_input"
    assert len(store.read_events()) == 1


def test_inf4y_capability_owner_view_is_rejected_before_population_source_admission_without_writes() -> None:
    store = GameplayEventStore()
    capability_authority = CivilizationCapabilityAuthority(store=store)
    activation = capability_authority.activate(
        envelope=GameplayCommandEnvelope(
            command_id="command:inf4y:capability",
            command_type="gameplay.civilization_capability.activate",
            command_version=1,
            principal_ref="authority:civilization_capability",
            idempotency_key="inf4y:capability",
            expected_revisions={"gameplay:civilization_capability:jurisdiction:bakery": 0},
            causation_id="cause:inf4y:capability",
            correlation_id="corr:inf4y:capability",
            source_ref="authority:civilization_capability",
            submitted_at="2026-08-13T00:00:00Z",
        ),
        record=CivilizationCapabilityRecord(
            capability_ref="capability:bakery-permit",
            jurisdiction_ref="jurisdiction:bakery",
            policy_revision="policy:inf4y:1",
            effective_tick=1,
        ),
    )
    view = capability_authority.view_for(
        capability_ref="capability:bakery-permit",
        jurisdiction_ref="jurisdiction:bakery",
        reader_scope="authority",
        now_tick=1,
    )
    social_input = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(),
    )

    result = PopulationPlanner().plan_from_world_inputs(
        store=store,
        batch_ref="batch:inf4y:capability-rejected",
        world_ref="world:bakery",
        mode=_mode(),
        social_input=social_input,
        household_input=None,
        organization_input=None,
        capability_input=view.view,
        candidates=(_candidate(),),
        deterministic_seed="seed:inf4y",
        mode_name="simulation",
    )

    assert activation.committed is True
    assert view.accepted is True and view.view is not None
    assert result.accepted is False
    assert result.error_code == "civilization_capability_consumer_not_admitted"
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.civilization_capability.activated"
    ]


def test_inf4r_social_input_digest_binds_recipient_time_and_source_vector() -> None:
    first = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(digest="sha256:same-view"),
    )
    different_time = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T01:00:00Z",
        view=_view(digest="sha256:same-view"),
    )
    different_recipient = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_b",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(digest="sha256:same-view"),
    )

    assert first.input_digest != different_time.input_digest
    assert first.input_digest != different_recipient.input_digest


def test_inf4r_planner_rejects_candidate_outside_social_recipient_scope_without_writes() -> None:
    store = GameplayEventStore()
    _record_social_source(store)
    social_input = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(),
    )
    outside_scope = _candidate().model_copy(update={"profile_ref": "character:char_b"})

    result = PopulationPlanner().plan_from_social_input(
        store=store,
        batch_ref="batch:inf4r:scope",
        world_ref="world:bakery",
        mode=_mode(),
        social_input=social_input,
        candidates=(outside_scope,),
        deterministic_seed="seed:inf4r",
    )

    assert result.accepted is False
    assert result.error_code == "social_recipient_scope_denied"
    assert len(store.read_events()) == 1


def test_inf4r_legacy_merge_rejects_stale_frozen_social_proposal_without_write() -> None:
    store = GameplayEventStore()
    _record_social_source(store)
    social_input = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(),
    )
    planned = PopulationPlanner().plan_from_social_input(
        store=store,
        batch_ref="batch:inf4r:stale-after-plan",
        world_ref="world:bakery",
        mode=_mode(),
        social_input=social_input,
        candidates=(_candidate(),),
        deterministic_seed="seed:inf4r",
    )
    assert planned.plan is not None
    store.append_batch(
        build_atomic_event_batch(
            command_id="command:inf4r:social-changed",
            principal_ref="authority:p5:social",
            stream_id="gameplay:relationship:public",
            expected_revision=1,
            event_specs=[("gameplay.social.relationship_fact_recorded", {"source": "changed"})],
            idempotency_key="inf4r:social-changed",
            causation_id="cause:inf4r:social-changed",
            correlation_id="corr:inf4r:social-changed",
        )
    )

    receipt = ContinuityMergeAuthority(
        store=store,
        registry=CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"),
        mode=_mode(),
    ).merge(planned.plan)

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "legacy_population_merge_retired"
    assert len(store.read_events()) == 2


def test_inf4r_social_source_replays_full_and_checkpoint_tail_without_legacy_merge_write() -> None:
    store = GameplayEventStore()
    _record_social_source(store)
    social_input = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(),
    )
    planned = PopulationPlanner().plan_from_social_input(
        store=store,
        batch_ref="batch:inf4r:replay",
        world_ref="world:bakery",
        mode=_mode(),
        social_input=social_input,
        candidates=(_candidate(),),
        deterministic_seed="seed:inf4r",
    )
    assert planned.plan is not None
    receipt = ContinuityMergeAuthority(
        store=store,
        registry=CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"),
        mode=_mode(),
    ).merge(planned.plan)
    replay = GameplayProjectionReplay(projector_id="population-continuity", projector_version="1")
    events = store.read_events()
    checkpoint = replay.create_checkpoint(events[:1])

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "legacy_population_merge_retired"
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(checkpoint, events[1:]).projection_hash


def test_inf4z_population_world_plan_pins_mode_sources_boundary_and_locks() -> None:
    plan = PopulationWorldPlan(
        batch_ref="batch:inf4z:game",
        world_ref="world:bakery",
        mode="game",
        mode_revision="mode:inf4z:game:1",
        package_revision="package:inf4z:1",
        policy_revision="policy:inf4z:1",
        deterministic_seed="seed:inf4z:game",
        input_digest="sha256:inf4z",
        source_vectors={
            "social": {"gameplay:relationship:public": 1},
            "household": {"gameplay:relationship:household": 2},
            "organization": {"gameplay:organization:bakery": 3},
        },
        base_checkpoint_event_count=4,
        tail_event_count=2,
        budget=1,
        activation_locks=("lock:world:bakery:character:char_a",),
        idempotency_keys=("intent:inf4z:1",),
        report_scope="actor:self",
        candidates=(_candidate(),),
    )

    assert plan.mode == "game"
    assert plan.base_checkpoint_event_count == 4
    assert plan.tail_event_count == 2
    assert plan.activation_locks == ("lock:world:bakery:character:char_a",)


def test_inf4z_world_plan_rejects_missing_admitted_source_without_writes() -> None:
    store = GameplayEventStore()
    _record_social_source(store)
    social_input = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=_view(),
    )

    result = PopulationPlanner().plan_from_world_inputs(
        store=store,
        batch_ref="batch:inf4z:missing-source",
        world_ref="world:bakery",
        mode=_mode(),
        social_input=social_input,
        household_input=None,
        organization_input=None,
        candidates=(_candidate(),),
        deterministic_seed="seed:inf4z",
        mode_name="simulation",
    )

    assert result.accepted is False
    assert result.error_code == "population_world_source_missing"
    assert len(store.read_events()) == 1
