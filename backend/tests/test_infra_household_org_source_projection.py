from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from test_p5_social_knowledge import _registry
from app.population_continuity.source_inputs import HouseholdScheduleInput, OrganizationScheduleInput
from app.population_continuity.batch import ContinuityMergeAuthority, PopulationPlanner
from app.population_continuity.models import BatchIntentCandidate, WorldModeProfile
from app.population_continuity.social_input import FrozenSocialPlanningInput
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import PendingChange
from app.character_agent.profile.registry import CharacterProfileRegistry
from pathlib import Path
from app.gameplay.replay import GameplayProjectionReplay


def test_social_authority_records_scoped_household_membership_and_reads_it() -> None:
    authority = SocialFactAuthority(registry=_registry(), store=GameplayEventStore())
    result = authority.record_household_membership(
        command_id="command:inf4x:household:1",
        household_ref="household:bakery",
        member_ref="character:baker",
        relation_kind="member",
        membership_status="active",
        effective_from="2026-08-13T00:00:00Z",
        effective_to=None,
        residence_ref="residence:bakery",
        visibility="actor:character:baker",
        recipient_ref="character:baker",
        observed_at="2026-08-13T00:00:00Z",
    )

    assert result.committed is True
    view = authority.household_view_for(recipient_ref="character:baker", now="2026-08-13T00:00:00Z")
    assert view.household_memberships[0]["household_ref"] == "household:bakery"
    assert view.source_revision_vector
    assert authority._store.list_outbox()[0].audience == "actor:character:baker"
    assert authority.household_view_for(
        recipient_ref="character:other", now="2026-08-13T00:00:00Z"
    ).household_memberships == ()


def test_organization_authority_records_schedule_and_rejects_other_recipient() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    result = authority.record_schedule(
        command_id="command:inf4x:organization:1",
        organization_ref="org:bakery",
        recipient_ref="character:baker",
        membership_ref="membership:baker",
        assignment_ref="assignment:baker",
        role="baker",
        shift_ref="shift:morning",
        operating_window_ref="window:morning",
        work_order_ref="work:bread",
        effective_from="2026-08-13T00:00:00Z",
        effective_to=None,
        visibility_scope="actor:character:baker",
    )

    assert result.committed is True
    view = authority.schedule_view_for(
        organization_ref="org:bakery",
        recipient_ref="character:baker",
        observed_at="2026-08-13T00:00:00Z",
    )
    assert view.organization_memberships[0]["membership_ref"] == "membership:baker"
    assert len(store.list_outbox()) == 4
    assert {entry.audience for entry in store.list_outbox()} == {"actor:character:baker"}
    denied = authority.schedule_view_for(
        organization_ref="org:bakery",
        recipient_ref="character:other",
        observed_at="2026-08-13T00:00:00Z",
    )
    assert denied.organization_memberships == ()


def test_source_views_reject_stale_revision_without_writes() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    result = authority.record_schedule(
        command_id="command:inf4x:organization:2",
        organization_ref="org:bakery",
        recipient_ref="character:baker",
        membership_ref="membership:baker",
        assignment_ref="assignment:baker",
        role="baker",
        shift_ref="shift:morning",
        operating_window_ref="window:morning",
        work_order_ref="work:bread",
        effective_from="2026-08-13T00:00:00Z",
        effective_to=None,
        visibility_scope="actor:character:baker",
    )
    assert result.committed is True
    view = authority.schedule_view_for(
        organization_ref="org:bakery",
        recipient_ref="character:baker",
        observed_at="2026-08-13T00:00:00Z",
    )
    assert view.validate_against(store=store) is True
    authority.record_schedule(
        command_id="command:inf4x:organization:2:correction",
        organization_ref="org:bakery",
        recipient_ref="character:baker",
        membership_ref="membership:baker",
        assignment_ref="assignment:baker",
        role="baker",
        shift_ref="shift:evening",
        operating_window_ref="window:evening",
        work_order_ref="work:bread-evening",
        effective_from="2026-08-13T12:00:00Z",
        effective_to=None,
        visibility_scope="actor:character:baker",
    )
    assert view.validate_against(store=store) is False
    assert len(store.read_events()) == 8


def test_population_inputs_freeze_owner_provenance_and_revision_vectors() -> None:
    social = SocialFactAuthority(registry=_registry(), store=GameplayEventStore())
    social_result = social.record_household_membership(
        command_id="command:inf4x:household:3",
        household_ref="household:bakery",
        member_ref="character:baker",
        relation_kind="member",
        membership_status="active",
        effective_from="2026-08-13T00:00:00Z",
        effective_to=None,
        residence_ref="residence:bakery",
        visibility="actor:character:baker",
        recipient_ref="character:baker",
        observed_at="2026-08-13T00:00:00Z",
    )
    assert social_result.committed is True
    household = HouseholdScheduleInput.freeze(
        recipient_ref="character:baker",
        observed_at="2026-08-13T00:00:00Z",
        view=social.household_view_for(recipient_ref="character:baker", now="2026-08-13T00:00:00Z"),
    )
    organization_store = GameplayEventStore()
    organization = OrganizationAuthority(store=organization_store)
    organization.record_schedule(
        command_id="command:inf4x:organization:3",
        organization_ref="org:bakery",
        recipient_ref="character:baker",
        membership_ref="membership:baker",
        assignment_ref="assignment:baker",
        role="baker",
        shift_ref="shift:morning",
        operating_window_ref="window:morning",
        work_order_ref="work:bread",
        effective_from="2026-08-13T00:00:00Z",
        effective_to=None,
        visibility_scope="actor:character:baker",
    )
    organization_input = OrganizationScheduleInput.freeze(
        recipient_ref="character:baker",
        observed_at="2026-08-13T00:00:00Z",
        view=organization.schedule_view_for(organization_ref="org:bakery", recipient_ref="character:baker", observed_at="2026-08-13T00:00:00Z"),
    )
    assert household.owner_principal_ref == "authority:p5:social"
    assert organization_input.owner_principal_ref == "actor_gameplay.organization_domain"
    assert household.input_digest != organization_input.input_digest


def test_population_planner_pins_both_owner_vectors_and_merge_rechecks_them() -> None:
    store = GameplayEventStore()
    social = SocialFactAuthority(registry=_registry(), store=store)
    social.record_household_membership(
        command_id="command:inf4x:household:4",
        household_ref="household:bakery",
        member_ref="character:char_a",
        relation_kind="member",
        membership_status="active",
        effective_from="2026-08-13T00:00:00Z",
        effective_to=None,
        residence_ref="residence:bakery",
        visibility="actor:character:char_a",
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
    )
    organization = OrganizationAuthority(store=store)
    organization.record_schedule(
        command_id="command:inf4x:organization:4",
        organization_ref="org:bakery",
        recipient_ref="character:char_a",
        membership_ref="membership:char_a",
        assignment_ref="assignment:char_a",
        role="baker",
        shift_ref="shift:morning",
        operating_window_ref="window:morning",
        work_order_ref="work:bread",
        effective_from="2026-08-13T00:00:00Z",
        effective_to=None,
        visibility_scope="actor:character:char_a",
    )
    household = HouseholdScheduleInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=social.household_view_for(recipient_ref="character:char_a", now="2026-08-13T00:00:00Z"),
    )
    organization_input = OrganizationScheduleInput.freeze(
        recipient_ref="character:char_a",
        observed_at="2026-08-13T00:00:00Z",
        view=organization.schedule_view_for(organization_ref="org:bakery", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z"),
    )
    mode = WorldModeProfile(
        world_ref="world:bakery", mode="simulation", revision="mode:inf4x:1", cadence_class="daily",
        batch_limit=1, wake_budget=1, catch_up_limit=1, allowed_intent_kinds=("work",), degraded_threshold=1,
    )
    candidate = BatchIntentCandidate(
        intent_ref="intent:inf4x:work", profile_ref="character:char_a", intent_kind="work",
        payload={"stream_ref": "population:character:char_a", "event_type": "population.intent.proposed"},
        expected_revisions={"population:character:char_a": 0}, policy_revision="mode:inf4x:1", package_revision="package:inf4x:1",
        idempotency_key="intent:inf4x:work", correlation_id="corr:inf4x:work", source_ref="population:planner", privacy_scope="actor:self",
    )
    planned = PopulationPlanner().plan_from_source_inputs(
        store=store, batch_ref="batch:inf4x:1", world_ref="world:bakery", mode=mode,
        household_input=household, organization_input=organization_input, candidates=(candidate,), deterministic_seed="seed:inf4x",
    )
    assert planned.accepted is True and planned.plan is not None
    assert planned.plan.household_source_revision_vector == household.source_revision_vector
    assert planned.plan.organization_source_revision_vector == organization_input.source_revision_vector
    registry = CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles")
    events_before = store.read_events()
    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=mode).merge(planned.plan)
    assert receipt.zero_write is True
    assert receipt.stop_reason == "legacy_population_merge_retired"
    duplicate = ContinuityMergeAuthority(store=store, registry=registry, mode=mode).merge(planned.plan)
    assert duplicate.zero_write is True
    assert store.read_events() == events_before


def test_world_input_planner_preserves_social_household_and_organization_pins_without_merging_work() -> None:
    store = GameplayEventStore()
    social = SocialFactAuthority(registry=_registry(), store=store)
    social.record_household_membership(
        command_id="command:inf4x:world-household", household_ref="household:bakery", member_ref="character:char_a",
        relation_kind="member", membership_status="active", effective_from="2026-08-13T00:00:00Z", effective_to=None,
        residence_ref="residence:bakery", visibility="actor:character:char_a", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z",
    )
    organization = OrganizationAuthority(store=store)
    organization.record_schedule(
        command_id="command:inf4x:world-organization", organization_ref="org:bakery", recipient_ref="character:char_a",
        membership_ref="membership:char_a", assignment_ref="assignment:char_a", role="baker", shift_ref="shift:morning",
        operating_window_ref="window:morning", work_order_ref="work:bread", effective_from="2026-08-13T00:00:00Z", effective_to=None,
        visibility_scope="actor:character:char_a",
    )
    social_input = FrozenSocialPlanningInput.freeze(
        recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z",
        view=social.view_for(recipient_ref="character:char_a", now="2026-08-13T00:00:00Z"),
    )
    household = HouseholdScheduleInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=social.household_view_for(recipient_ref="character:char_a", now="2026-08-13T00:00:00Z"))
    organization_input = OrganizationScheduleInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=organization.schedule_view_for(organization_ref="org:bakery", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z"))
    mode = WorldModeProfile(world_ref="world:bakery", mode="simulation", revision="mode:inf4x:world:1", cadence_class="daily", batch_limit=1, wake_budget=1, catch_up_limit=1, allowed_intent_kinds=("work",), degraded_threshold=1)
    candidate = BatchIntentCandidate(intent_ref="intent:inf4x:world-work", profile_ref="character:char_a", intent_kind="work", payload={"work_order_ref": "work:bread"}, expected_revisions={}, policy_revision=mode.revision, package_revision="package:inf4x:world:1", idempotency_key="intent:inf4x:world-work", correlation_id="corr:inf4x:world-work", source_ref="population:planner", privacy_scope="actor:self")

    result = PopulationPlanner().plan_from_world_inputs(
        store=store, batch_ref="batch:inf4x:world", world_ref="world:bakery", mode=mode,
        social_input=social_input, household_input=household, organization_input=organization_input,
        candidates=(candidate,), deterministic_seed="seed:inf4x:world", mode_name="simulation",
    )

    assert result.accepted is True and result.plan is not None
    assert result.plan.social_source_revision_vector == social_input.source_revision_vector
    assert result.plan.household_source_revision_vector == household.source_revision_vector
    assert result.plan.organization_source_revision_vector == organization_input.source_revision_vector
    assert result.plan.input_digest not in {social_input.input_digest, household.input_digest, organization_input.input_digest}
    registry = CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles")
    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=mode).merge(result.plan)
    assert receipt.zero_write is True and receipt.stop_reason == "legacy_population_merge_retired"


def test_schedule_gated_supply_uses_existing_organization_fragment_with_pinned_sources() -> None:
    store = GameplayEventStore()
    social = SocialFactAuthority(registry=_registry(), store=store)
    social.record_household_membership(command_id="command:inf4a:household", household_ref="household:bakery", member_ref="character:char_a", relation_kind="member", membership_status="active", effective_from="2026-08-13T00:00:00Z", effective_to=None, residence_ref="residence:bakery", visibility="actor:character:char_a", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z")
    organization = OrganizationAuthority(store=store)
    organization.record_schedule(command_id="command:inf4a:schedule", organization_ref="org:bakery", recipient_ref="character:char_a", membership_ref="membership:char_a", assignment_ref="assignment:char_a", role="baker", shift_ref="shift:morning", operating_window_ref="window:morning", work_order_ref="work:bread", effective_from="2026-08-13T00:00:00Z", effective_to=None, visibility_scope="actor:character:char_a")
    social_input = FrozenSocialPlanningInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=social.view_for(recipient_ref="character:char_a", now="2026-08-13T00:00:00Z"))
    household = HouseholdScheduleInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=social.household_view_for(recipient_ref="character:char_a", now="2026-08-13T00:00:00Z"))
    organization_input = OrganizationScheduleInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=organization.schedule_view_for(organization_ref="org:bakery", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z"))
    mode = WorldModeProfile(world_ref="world:bakery", mode="simulation", revision="mode:inf4a:1", cadence_class="daily", batch_limit=1, wake_budget=1, catch_up_limit=1, allowed_intent_kinds=("supply",), degraded_threshold=1)
    candidate = BatchIntentCandidate(intent_ref="intent:inf4a:supply", profile_ref="character:char_a", intent_kind="supply", payload={"organization_ref": "org:bakery", "counterparty_organization_ref": "org:supplier", "commitment_ref": "commitment:inf4a", "organization_grant_refs": [], "budget_reservation_refs": [], "schedule_work_order_ref": "work:bread"}, expected_revisions=dict(organization_input.source_revision_vector), policy_revision=mode.revision, package_revision="package:inf4a:1", idempotency_key="intent:inf4a:supply", correlation_id="corr:inf4a", source_ref="population:planner", privacy_scope="actor:self")

    planned = PopulationPlanner().plan_schedule_gated_supply(store=store, batch_ref="batch:inf4a:supply", world_ref="world:bakery", mode=mode, social_input=social_input, household_input=household, organization_input=organization_input, candidate=candidate, base_event_digest="sha256:base", tail_boundary=len(store.read_events()), active_revision_refs=(mode.revision,), deterministic_seed="seed:inf4a", report_scope="actor:self")

    assert planned.accepted is True and planned.plan is not None
    receipt = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"), mode=mode).merge_schedule_gated_supply(plan=planned.plan, social_input=social_input, household_input=household, organization_input=organization_input)
    assert receipt.committed is True and receipt.owner_receipt_ref == "actor_gameplay.organization_domain"
    event = store.read_stream("gameplay:organization:org:bakery")[-1]
    assert event.event_type == "gameplay.organization.commerce_commitment_accepted"
    assert planned.plan.organization_schedule_ref == "org:bakery"
    assert planned.plan.household_input_digest == household.input_digest


def test_schedule_gated_supply_rejects_lock_stale_source_and_missing_work_order_without_writes() -> None:
    store = GameplayEventStore()
    social = SocialFactAuthority(registry=_registry(), store=store)
    social.record_household_membership(command_id="command:inf4a:reject-household", household_ref="household:bakery", member_ref="character:char_a", relation_kind="member", membership_status="active", effective_from="2026-08-13T00:00:00Z", effective_to=None, residence_ref="residence:bakery", visibility="actor:character:char_a", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z")
    organization = OrganizationAuthority(store=store)
    organization.record_schedule(command_id="command:inf4a:reject-schedule", organization_ref="org:bakery", recipient_ref="character:char_a", membership_ref="membership:char_a", assignment_ref="assignment:char_a", role="baker", shift_ref="shift:morning", operating_window_ref="window:morning", work_order_ref="work:bread", effective_from="2026-08-13T00:00:00Z", effective_to=None, visibility_scope="actor:character:char_a")
    social_input = FrozenSocialPlanningInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=social.view_for(recipient_ref="character:char_a", now="2026-08-13T00:00:00Z"))
    household = HouseholdScheduleInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=social.household_view_for(recipient_ref="character:char_a", now="2026-08-13T00:00:00Z"))
    organization_input = OrganizationScheduleInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=organization.schedule_view_for(organization_ref="org:bakery", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z"))
    mode = WorldModeProfile(world_ref="world:bakery", mode="simulation", revision="mode:inf4a:1", cadence_class="daily", batch_limit=1, wake_budget=1, catch_up_limit=1, allowed_intent_kinds=("supply",), degraded_threshold=1)
    def candidate(work_order: str) -> BatchIntentCandidate:
        return BatchIntentCandidate(intent_ref="intent:inf4a:reject", profile_ref="character:char_a", intent_kind="supply", payload={"organization_ref": "org:bakery", "counterparty_organization_ref": "org:supplier", "commitment_ref": "commitment:inf4a:reject", "organization_grant_refs": [], "budget_reservation_refs": [], "schedule_work_order_ref": work_order}, expected_revisions=dict(organization_input.source_revision_vector), policy_revision=mode.revision, package_revision="package:inf4a:1", idempotency_key="intent:inf4a:reject", correlation_id="corr:inf4a:reject", source_ref="population:planner", privacy_scope="actor:self")
    before = len(store.read_events())
    missing = PopulationPlanner().plan_schedule_gated_supply(store=store, batch_ref="batch:inf4a:missing", world_ref="world:bakery", mode=mode, social_input=social_input, household_input=household, organization_input=organization_input, candidate=candidate("work:missing"), base_event_digest="sha256:base", tail_boundary=before, active_revision_refs=(mode.revision,), deterministic_seed="seed:inf4a", report_scope="actor:self")
    locked = PopulationPlanner().plan_schedule_gated_supply(store=store, batch_ref="batch:inf4a:locked", world_ref="world:bakery", mode=mode, social_input=social_input, household_input=household, organization_input=organization_input, candidate=candidate("work:bread"), base_event_digest="sha256:base", tail_boundary=before, active_revision_refs=(mode.revision,), deterministic_seed="seed:inf4a", report_scope="actor:self", activation_lock_refs=("lock:inf4a",))
    assert missing.accepted is False and missing.error_code == "schedule_work_order_missing"
    assert locked.accepted is True and locked.plan is not None
    receipt = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"), mode=mode).merge_schedule_gated_supply(plan=locked.plan, social_input=social_input, household_input=household, organization_input=organization_input)
    assert receipt.zero_write is True and receipt.stop_reason == "activation_lock_pending"
    assert len(store.read_events()) == before


def test_released_activation_pending_schedule_merges_only_through_existing_organization_owner() -> None:
    store = GameplayEventStore()
    social = SocialFactAuthority(registry=_registry(), store=store)
    social.record_household_membership(command_id="command:inf4c:household", household_ref="household:bakery", member_ref="character:char_a", relation_kind="member", membership_status="active", effective_from="2026-08-13T00:00:00Z", effective_to=None, residence_ref="residence:bakery", visibility="actor:character:char_a", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z")
    organization = OrganizationAuthority(store=store)
    organization.record_schedule(command_id="command:inf4c:schedule", organization_ref="org:bakery", recipient_ref="character:char_a", membership_ref="membership:char_a", assignment_ref="assignment:char_a", role="baker", shift_ref="shift:morning", operating_window_ref="window:morning", work_order_ref="work:bread", effective_from="2026-08-13T00:00:00Z", effective_to=None, visibility_scope="actor:character:char_a")
    social_input = FrozenSocialPlanningInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=social.view_for(recipient_ref="character:char_a", now="2026-08-13T00:00:00Z"))
    household = HouseholdScheduleInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=social.household_view_for(recipient_ref="character:char_a", now="2026-08-13T00:00:00Z"))
    organization_input = OrganizationScheduleInput.freeze(recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", view=organization.schedule_view_for(organization_ref="org:bakery", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z"))
    mode = WorldModeProfile(world_ref="world:bakery", mode="simulation", revision="mode:inf4c:1", cadence_class="daily", batch_limit=1, wake_budget=1, catch_up_limit=1, allowed_intent_kinds=("supply",), degraded_threshold=1)
    candidate = BatchIntentCandidate(intent_ref="intent:inf4c:supply", profile_ref="character:char_a", intent_kind="supply", payload={"organization_ref": "org:bakery", "counterparty_organization_ref": "org:supplier", "commitment_ref": "commitment:inf4c", "organization_grant_refs": [], "budget_reservation_refs": [], "schedule_work_order_ref": "work:bread"}, expected_revisions=dict(organization_input.source_revision_vector), policy_revision=mode.revision, package_revision="package:inf4c:1", idempotency_key="intent:inf4c:supply", correlation_id="corr:inf4c", source_ref="population:planner", privacy_scope="actor:self")
    plan = PopulationPlanner().plan_schedule_gated_supply(store=store, batch_ref="batch:inf4c:supply", world_ref="world:bakery", mode=mode, social_input=social_input, household_input=household, organization_input=organization_input, candidate=candidate, base_event_digest="sha256:base", tail_boundary=len(store.read_events()), active_revision_refs=(mode.revision,), deterministic_seed="seed:inf4c", report_scope="actor:self", activation_lock_refs=("lock:world:bakery:character:char_a",))
    assert plan.accepted and plan.plan is not None
    activation = ProfileActivationAuthority(registry=CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"), store=store)
    assert activation.lock(world_ref="world:bakery", profile_ref="character:char_a", expected_revision=0).committed
    pending = activation.record_pending(PendingChange(change_ref="pending:inf4c:supply", lock_ref="lock:world:bakery:character:char_a", profile_ref="character:char_a", expected_revision=0, payload={"kind": "schedule_gated_supply", "plan_digest": PopulationPlanner.schedule_pending_digest(plan.plan)}, privacy_scope="actor:self"))
    assert pending.committed is True
    released = activation.release_lock(lock_ref="lock:world:bakery:character:char_a", expected_revision=2)
    assert released.committed is True

    merger = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"), mode=mode)
    receipt = merger.merge_released_schedule_gated_supply(plan=plan.plan, pending_change_ref="pending:inf4c:supply", social_input=social_input, household_input=household, organization_input=organization_input)

    assert receipt.committed is True and receipt.owner_receipt_ref == "actor_gameplay.organization_domain"
    assert store.read_stream("gameplay:organization:org:bakery")[-1].event_type == "gameplay.organization.commerce_commitment_accepted"
    assert activation.pending_projection("world:bakery")["pending:inf4c:supply"]["status"] == "released"


def test_activation_pending_schedule_forgery_or_stale_release_is_zero_write_at_organization_boundary() -> None:
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"), store=store)
    assert authority.lock(world_ref="world:bakery", profile_ref="character:char_a", expected_revision=0).committed
    forged = authority.record_pending(PendingChange(change_ref="pending:forged", lock_ref="lock:world:bakery:character:char_a", profile_ref="character:char_a", expected_revision=0, payload={"kind": "free_form_world_write"}, privacy_scope="actor:self"))
    stale = authority.release_lock(lock_ref="lock:world:bakery:character:char_a", expected_revision=0)
    assert forged.zero_write is True and forged.stop_reason == "pending_change_kind_unsupported"
    assert stale.zero_write is True and stale.stop_reason == "revision_conflict"
    assert all(event.stream_id != "gameplay:organization:org:bakery" for event in store.read_events())


def test_population_source_input_scope_and_stale_rejection_are_zero_write() -> None:
    store = GameplayEventStore()
    household = HouseholdScheduleInput(
        recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", owner_principal_ref="authority:p5:social",
        projection_digest="sha256:household", source_revision_vector={"gameplay:relationship:missing": 1}, household_memberships=(),
    )
    organization = OrganizationScheduleInput(
        recipient_ref="character:char_b", observed_at="2026-08-13T00:00:00Z", owner_principal_ref="actor_gameplay.organization_domain",
        organization_ref="org:bakery", projection_digest="sha256:organization", source_revision_vector={}, organization_memberships=(), role_terms=(), shift_offers=(), work_orders=(),
    )
    mode = WorldModeProfile(
        world_ref="world:bakery", mode="simulation", revision="mode:inf4x:1", cadence_class="daily",
        batch_limit=1, wake_budget=1, catch_up_limit=1, allowed_intent_kinds=("work",), degraded_threshold=1,
    )
    result = PopulationPlanner().plan_from_source_inputs(
        store=store, batch_ref="batch:inf4x:denied", world_ref="world:bakery", mode=mode,
        household_input=household, organization_input=organization, candidates=(), deterministic_seed="seed:inf4x",
    )
    assert result.accepted is False
    assert result.error_code == "source_recipient_scope_denied"
    assert store.read_events() == []


def test_population_planner_rejects_forged_source_provenance_and_digest_without_writes() -> None:
    store = GameplayEventStore()
    household = HouseholdScheduleInput(
        recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", owner_principal_ref="forged:owner",
        projection_digest="sha256:forged", source_revision_vector={}, household_memberships=(),
    )
    organization = OrganizationScheduleInput(
        recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z", owner_principal_ref="forged:owner",
        organization_ref="org:bakery", projection_digest="sha256:forged", source_revision_vector={}, organization_memberships=(), role_terms=(), shift_offers=(), work_orders=(),
    )
    mode = WorldModeProfile(
        world_ref="world:bakery", mode="simulation", revision="mode:inf4x:1", cadence_class="daily",
        batch_limit=1, wake_budget=1, catch_up_limit=1, allowed_intent_kinds=("work",), degraded_threshold=1,
    )
    result = PopulationPlanner().plan_from_source_inputs(
        store=store, batch_ref="batch:inf4x:forged", world_ref="world:bakery", mode=mode,
        household_input=household, organization_input=organization, candidates=(), deterministic_seed="seed:inf4x",
    )
    assert result.accepted is False
    assert result.error_code == "source_provenance_denied"
    assert store.read_events() == []


def test_organization_schedule_hides_summary_details_and_inactive_windows() -> None:
    store = GameplayEventStore()
    authority = OrganizationAuthority(store=store)
    authority.record_schedule(
        command_id="command:inf4x:organization:summary", organization_ref="org:bakery", recipient_ref="character:char_a",
        membership_ref="membership:char_a", assignment_ref="assignment:char_a", role="baker", shift_ref="shift:future",
        operating_window_ref="window:future", work_order_ref="work:future", effective_from="2026-08-14T00:00:00Z", effective_to=None,
        visibility_scope="organization:summary",
    )
    authority.record_schedule(
        command_id="command:inf4x:organization:expired", organization_ref="org:bakery", recipient_ref="character:char_a",
        membership_ref="membership:expired", assignment_ref="assignment:expired", role="baker", shift_ref="shift:expired",
        operating_window_ref="window:expired", work_order_ref="work:expired", effective_from="2026-08-10T00:00:00Z", effective_to="2026-08-12T00:00:00Z",
        visibility_scope="actor:character:char_a",
    )
    other = authority.schedule_view_for(organization_ref="org:bakery", recipient_ref="character:char_b", observed_at="2026-08-15T00:00:00Z")
    actor = authority.schedule_view_for(organization_ref="org:bakery", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z")
    assert other.organization_memberships == ({"organization_ref": "org:bakery", "visibility_scope": "organization:summary"},)
    assert actor.organization_memberships == ()


def test_household_and_organization_source_replay_matches_checkpoint_tail() -> None:
    store = GameplayEventStore()
    social = SocialFactAuthority(registry=_registry(), store=store)
    social.record_household_membership(
        command_id="command:inf4x:household:5", household_ref="household:bakery", member_ref="character:char_a",
        relation_kind="member", membership_status="active", effective_from="2026-08-13T00:00:00Z", effective_to=None,
        residence_ref="residence:bakery", visibility="actor:character:char_a", recipient_ref="character:char_a", observed_at="2026-08-13T00:00:00Z",
    )
    organization = OrganizationAuthority(store=store)
    organization.record_schedule(
        command_id="command:inf4x:organization:5", organization_ref="org:bakery", recipient_ref="character:char_a",
        membership_ref="membership:char_a", assignment_ref="assignment:char_a", role="baker", shift_ref="shift:morning",
        operating_window_ref="window:morning", work_order_ref="work:bread", effective_from="2026-08-13T00:00:00Z", effective_to=None,
        visibility_scope="actor:character:char_a",
    )
    replay = GameplayProjectionReplay(projector_id="infra-household-org-source", projector_version="1")
    events = store.read_events()
    checkpoint = replay.create_checkpoint(events[:1])
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(checkpoint, events[1:]).projection_hash
