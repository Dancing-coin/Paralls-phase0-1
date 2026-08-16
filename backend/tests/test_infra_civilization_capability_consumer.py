from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.civilization_capability_runtime import (
    CivilizationCapabilityAuthority,
    CivilizationCapabilityRecord,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.population_continuity.batch import ContinuityMergeAuthority, PopulationPlanner
from app.population_continuity.capability_input import FrozenCapabilityEligibilityInput
from app.population_continuity.models import BatchIntentCandidate, WorldModeProfile


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"
CAPABILITY_STREAM = "gameplay:civilization_capability:jurisdiction:bakery"
ORGANIZATION_STREAM = "gameplay:organization:organization:bakery"
GOVERNMENT_STREAM = "gameplay:government:organization:bakery"


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="simulation",
        revision="mode:inf4y:1",
        cadence_class="daily",
        batch_limit=1,
        wake_budget=1,
        catch_up_limit=1,
        allowed_intent_kinds=("supply", "inspection"),
        degraded_threshold=1,
    )


def _capability_envelope(*, command_id: str = "command:inf4y:activate", expected_revision: int = 0) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=command_id,
        command_type="gameplay.civilization_capability.activate",
        command_version=1,
        principal_ref="authority:civilization_capability",
        idempotency_key=command_id,
        expected_revisions={CAPABILITY_STREAM: expected_revision},
        causation_id=f"cause:{command_id}",
        correlation_id=f"corr:{command_id}",
        source_ref="authority:civilization_capability",
        submitted_at="2026-08-13T00:00:00Z",
    )


def _activate(store: GameplayEventStore, *, visibility: str = "authority_only") -> FrozenCapabilityEligibilityInput:
    authority = CivilizationCapabilityAuthority(store=store)
    result = authority.activate(
        envelope=_capability_envelope(),
        record=CivilizationCapabilityRecord(
            capability_ref="capability:bakery-permit",
            jurisdiction_ref="jurisdiction:bakery",
            policy_revision="policy:inf4y:1",
            effective_tick=1,
            visibility=visibility,
        ),
    )
    assert result.committed is True
    view = authority.view_for(
        capability_ref="capability:bakery-permit",
        jurisdiction_ref="jurisdiction:bakery",
        reader_scope="authority",
        now_tick=1,
    )
    assert view.accepted is True and view.view is not None
    return FrozenCapabilityEligibilityInput.freeze(
        view=view.view,
        evaluated_tick=1,
        source_revision_vector={CAPABILITY_STREAM: store.get_stream_head(CAPABILITY_STREAM)},
    )


def _candidate(*, intent_kind: str = "supply", capability_ref: str = "capability:bakery-permit") -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref=f"intent:inf4y:{intent_kind}",
        profile_ref="character:char_a",
        intent_kind=intent_kind,
        payload={
            "organization_ref": "organization:bakery",
            "counterparty_organization_ref": "organization:supplier",
            "commitment_ref": "commitment:inf4y:supply",
            "organization_grant_refs": [],
            "budget_reservation_refs": [],
            "required_capability_ref": capability_ref,
            "required_capability_jurisdiction_ref": "jurisdiction:bakery",
        },
        expected_revisions={ORGANIZATION_STREAM: 0},
        policy_revision="mode:inf4y:1",
        package_revision="package:inf4y:1",
        idempotency_key=f"intent:inf4y:{intent_kind}",
        correlation_id="corr:inf4y",
        source_ref="population:planner",
        privacy_scope="actor:self",
    )


def _inspection_candidate(
    *,
    capability_ref: str = "capability:bakery-permit",
    jurisdiction_ref: str = "jurisdiction:bakery",
) -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref="intent:inf4y:inspection",
        profile_ref="character:char_a",
        intent_kind="inspection",
        payload={
            "organization_ref": "organization:bakery",
            "inspection_ref": "inspection:inf4y:bakery",
            "jurisdiction_ref": jurisdiction_ref,
            "required_capability_ref": capability_ref,
            "required_capability_jurisdiction_ref": jurisdiction_ref,
            "policy_digest": "sha256:inspection-policy:inf4y:1",
            "evidence_ref": "evidence:inspection:inf4y:1",
            "passed": True,
        },
        expected_revisions={GOVERNMENT_STREAM: 0},
        policy_revision="mode:inf4y:1",
        package_revision="package:inf4y:1",
        idempotency_key="intent:inf4y:inspection",
        correlation_id="corr:inf4y",
        source_ref="population:planner",
        privacy_scope="actor:self",
    )


def _plan(store: GameplayEventStore, *, capability_input: FrozenCapabilityEligibilityInput, candidate: BatchIntentCandidate | None = None):
    return PopulationPlanner().plan_capability_gated_supply(
        store=store,
        batch_ref="batch:inf4y:supply",
        world_ref="world:bakery",
        mode=_mode(),
        capability_input=capability_input,
        candidate=candidate or _candidate(),
        base_event_digest="sha256:inf4y:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4y:1", "policy:inf4y:1"),
        deterministic_seed="seed:inf4y",
        report_scope="actor:self",
    )


def _merge(store: GameplayEventStore, plan):
    return ContinuityMergeAuthority(
        store=store,
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        mode=_mode(),
    ).merge_capability_gated_supply(plan)


def _plan_inspection(
    store: GameplayEventStore,
    *,
    capability_input: FrozenCapabilityEligibilityInput,
    candidate: BatchIntentCandidate | None = None,
):
    return PopulationPlanner().plan_capability_gated_inspection(
        store=store,
        batch_ref="batch:inf4y:inspection",
        world_ref="world:bakery",
        mode=_mode(),
        capability_input=capability_input,
        candidate=candidate or _inspection_candidate(),
        base_event_digest="sha256:inf4y:inspection-base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4y:1", "policy:inf4y:1"),
        deterministic_seed="seed:inf4y:inspection",
        report_scope="actor:self",
    )


def _merge_inspection(store: GameplayEventStore, plan):
    return ContinuityMergeAuthority(
        store=store,
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        mode=_mode(),
    ).merge_capability_gated_inspection(plan)


def test_inf4y_capability_gated_supply_uses_existing_organization_fragment_and_receipt() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)

    planned = _plan(store, capability_input=capability_input)
    assert planned.accepted is True and planned.plan is not None
    receipt = _merge(store, planned.plan)

    assert receipt.committed is True
    assert receipt.owner_receipt_ref == "actor_gameplay.organization_domain"
    event = store.read_stream(ORGANIZATION_STREAM)[0]
    assert event.event_type == "gameplay.organization.commerce_commitment_accepted"


def test_inf4y_capability_gated_supply_event_redacts_capability_details() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    planned = _plan(store, capability_input=capability_input)
    assert planned.accepted is True and planned.plan is not None

    receipt = _merge(store, planned.plan)
    event = store.read_stream(ORGANIZATION_STREAM)[0]

    assert receipt.committed is True
    assert event.payload["capability_eligibility_digest"] == capability_input.input_digest
    assert not {"capability_ref", "source_event_refs", "capability_view"}.intersection(event.payload)


def test_inf4y_capability_stale_revision_is_zero_write_before_organization_owner() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    authority = CivilizationCapabilityAuthority(store=store)
    correction = authority.correct(
        envelope=_capability_envelope(command_id="command:inf4y:correct", expected_revision=1),
        record=CivilizationCapabilityRecord(
            capability_ref="capability:bakery-permit",
            jurisdiction_ref="jurisdiction:bakery",
            policy_revision="policy:inf4y:2",
            effective_tick=1,
            visibility="authority_only",
        ),
    )

    planned = _plan(store, capability_input=capability_input)

    assert correction.committed is True
    assert planned.accepted is False
    assert planned.error_code == "capability_source_revision_stale"
    assert store.read_stream(ORGANIZATION_STREAM) == []


def test_inf4y_capability_digest_forgery_is_zero_write() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)

    forged_digest = _plan(
        store,
        capability_input=capability_input.model_copy(update={"projection_digest": "sha256:forged"}),
    )

    assert forged_digest.error_code == "capability_projection_digest_mismatch"
    assert store.read_stream(ORGANIZATION_STREAM) == []


def test_inf4y_capability_not_effective_is_zero_write() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)

    not_effective = _plan(
        store,
        capability_input=capability_input.model_copy(update={"evaluated_tick": 0}),
    )

    assert not_effective.error_code == "civilization_capability_not_effective"
    assert store.read_stream(ORGANIZATION_STREAM) == []


def test_inf4y_capability_non_authority_scope_is_zero_write() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)

    non_authority_scope = _plan(
        store,
        capability_input=capability_input.model_copy(update={"reader_scope": "actor"}),
    )

    assert non_authority_scope.error_code == "capability_reader_scope_denied"
    assert store.read_stream(ORGANIZATION_STREAM) == []


def test_inf4y_capability_source_event_forgery_is_zero_write() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)

    forged_events = _plan(
        store,
        capability_input=capability_input.model_copy(update={"source_event_refs": ("event:forged",)}),
    )

    assert forged_events.error_code == "capability_source_event_mismatch"
    assert store.read_stream(ORGANIZATION_STREAM) == []


def test_inf4y_capability_candidate_mapping_mismatch_is_zero_write() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)

    mismatched_candidate = _plan(
        store,
        capability_input=capability_input,
        candidate=_candidate(capability_ref="capability:other"),
    )

    assert mismatched_candidate.error_code == "capability_candidate_mapping_denied"
    assert store.read_stream(ORGANIZATION_STREAM) == []


def test_inf4y_capability_gated_supply_rejects_unapproved_intent_without_writes() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)

    planned = _plan(store, capability_input=capability_input, candidate=_candidate(intent_kind="inspection"))

    assert planned.accepted is False
    assert planned.error_code == "capability_consumer_intent_unsupported"
    assert store.read_stream(ORGANIZATION_STREAM) == []


def test_inf4y_capability_policy_must_be_pinned_in_active_revisions_without_writes() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    result = PopulationPlanner().plan_capability_gated_supply(
        store=store,
        batch_ref="batch:inf4y:untracked-policy",
        world_ref="world:bakery",
        mode=_mode(),
        capability_input=capability_input,
        candidate=_candidate(),
        base_event_digest="sha256:inf4y:base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4y:1",),
        deterministic_seed="seed:inf4y",
        report_scope="actor:self",
    )

    assert result.accepted is False
    assert result.error_code == "capability_policy_not_pinned"
    assert store.read_stream(ORGANIZATION_STREAM) == []


def test_inf4y_revoked_capability_is_zero_write_before_organization_owner() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    revoked = CivilizationCapabilityAuthority(store=store).revoke(
        envelope=_capability_envelope(command_id="command:inf4y:revoke", expected_revision=1),
        capability_ref="capability:bakery-permit",
        jurisdiction_ref="jurisdiction:bakery",
    )

    planned = _plan(store, capability_input=capability_input)

    assert revoked.committed is True
    assert planned.error_code == "capability_source_revision_stale"
    assert store.read_stream(ORGANIZATION_STREAM) == []


def test_inf4y_organization_revision_conflict_is_zero_write_after_capability_admission() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    planned = _plan(store, capability_input=capability_input)
    assert planned.accepted is True and planned.plan is not None
    store.append_batch(
        build_atomic_event_batch(
            command_id="command:inf4y:organization-change",
            principal_ref="actor_gameplay.organization_domain",
            stream_id=ORGANIZATION_STREAM,
            expected_revision=0,
            event_specs=[("gameplay.organization.test_revision_advanced", {})],
            idempotency_key="inf4y:organization-change",
            causation_id="cause:inf4y:organization-change",
            correlation_id="corr:inf4y:organization-change",
        )
    )
    receipt = ContinuityMergeAuthority(
        store=store,
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        mode=_mode(),
    ).merge_capability_gated_supply(planned.plan)

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "source_revision_stale"
    assert len(store.read_stream(ORGANIZATION_STREAM)) == 1


def test_inf4y_capability_gated_supply_is_idempotent() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    planned = _plan(store, capability_input=capability_input)
    assert planned.plan is not None
    first = _merge(store, planned.plan)
    duplicate = _merge(store, planned.plan)

    assert first.committed is True
    assert duplicate.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"


def test_inf4y_capability_gated_supply_replays_full_checkpoint_tail() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    planned = _plan(store, capability_input=capability_input)
    assert planned.plan is not None

    receipt = _merge(store, planned.plan)
    replay = GameplayProjectionReplay(projector_id="population-continuity", projector_version="1")
    events = store.read_events()
    checkpoint = replay.create_checkpoint(events[:1])

    assert receipt.committed is True
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(checkpoint, events[1:]).projection_hash


def test_inf4y_capability_stream_revision_is_pinned_independently_from_capability_revision() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    authority = CivilizationCapabilityAuthority(store=store)
    second = authority.activate(
        envelope=_capability_envelope(command_id="command:inf4y:second", expected_revision=1),
        record=CivilizationCapabilityRecord(
            capability_ref="capability:other-permit",
            jurisdiction_ref="jurisdiction:bakery",
            policy_revision="policy:inf4y:1",
            effective_tick=1,
            visibility="authority_only",
        ),
    )
    assert second.committed is True
    assert capability_input.capability_revision == 1
    assert store.get_stream_head(CAPABILITY_STREAM) == 2

    refreshed_view = authority.view_for(
        capability_ref="capability:bakery-permit",
        jurisdiction_ref="jurisdiction:bakery",
        reader_scope="authority",
        now_tick=1,
    )
    assert refreshed_view.accepted is True and refreshed_view.view is not None
    planned = _plan(
        store,
        capability_input=FrozenCapabilityEligibilityInput.freeze(
            view=refreshed_view.view,
            evaluated_tick=1,
            source_revision_vector={CAPABILITY_STREAM: 2},
        ),
    )

    assert planned.accepted is True


def test_inf4y_changed_capability_gated_duplicate_is_zero_write() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    planned = _plan(store, capability_input=capability_input)
    assert planned.plan is not None
    first = _merge(store, planned.plan)
    changed = planned.plan.model_copy(
        update={"capability_eligibility_digest": "sha256:changed"}
    )

    rejected = _merge(store, changed)

    assert first.committed is True
    assert rejected.committed is False
    assert rejected.zero_write is True
    assert rejected.stop_reason == "idempotency_key_reused"
    assert len(store.read_stream(ORGANIZATION_STREAM)) == 1


def test_inf4y_capability_gated_inspection_uses_existing_government_fragment_and_receipt() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(store, capability_input=_activate(store))

    assert planned.accepted is True and planned.plan is not None
    receipt = _merge_inspection(store, planned.plan)
    event = store.read_stream(GOVERNMENT_STREAM)[0]

    assert receipt.committed is True
    assert receipt.owner_receipt_ref == "actor_gameplay.government_domain"
    assert event.event_type == "gameplay.government.inspection_recorded"


def test_inf4y_capability_gated_inspection_redacts_capability_details() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    planned = _plan_inspection(store, capability_input=capability_input)

    assert planned.plan is not None
    receipt = _merge_inspection(store, planned.plan)
    event = store.read_stream(GOVERNMENT_STREAM)[0]

    assert receipt.committed is True
    assert event.payload["capability_eligibility_digest"] == capability_input.input_digest
    assert event.payload["capability_consumer_plan_digest"].startswith("sha256:")
    assert not {"capability_ref", "source_event_refs", "capability_view"}.intersection(event.payload)


def test_inf4y_capability_gated_inspection_writes_actor_scoped_outbox_projection() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(store, capability_input=_activate(store))

    assert planned.plan is not None
    receipt = _merge_inspection(store, planned.plan)
    outbox = store.list_outbox()

    assert receipt.committed is True
    inspection_outbox = [entry for entry in outbox if entry.topic == "world.government.inspection.scoped_projection"]

    assert len(inspection_outbox) == 1
    assert inspection_outbox[0].audience == "actor:self"
    assert inspection_outbox[0].payload_projection["capability_eligibility_digest"].startswith("sha256:")
    assert not {"capability_ref", "source_event_refs", "capability_view", "evidence_ref"}.intersection(inspection_outbox[0].payload_projection)


def test_inf4y_capability_gated_inspection_rejects_jurisdiction_mismatch_without_writes() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(
        store,
        capability_input=_activate(store),
        candidate=_inspection_candidate(jurisdiction_ref="jurisdiction:other"),
    )

    assert planned.accepted is False
    assert planned.error_code == "capability_candidate_mapping_denied"
    assert store.read_stream(GOVERNMENT_STREAM) == []


def test_inf4y_capability_gated_inspection_stale_source_is_zero_write() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    correction = CivilizationCapabilityAuthority(store=store).correct(
        envelope=_capability_envelope(command_id="command:inf4y:inspection-correct", expected_revision=1),
        record=CivilizationCapabilityRecord(
            capability_ref="capability:bakery-permit",
            jurisdiction_ref="jurisdiction:bakery",
            policy_revision="policy:inf4y:2",
            effective_tick=1,
            visibility="authority_only",
        ),
    )
    planned = _plan_inspection(store, capability_input=capability_input)

    assert correction.committed is True
    assert planned.accepted is False
    assert planned.error_code == "capability_source_revision_stale"
    assert store.read_stream(GOVERNMENT_STREAM) == []


def test_inf4y_capability_gated_inspection_not_effective_is_zero_write() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(
        store,
        capability_input=_activate(store).model_copy(update={"evaluated_tick": 0}),
    )

    assert planned.accepted is False
    assert planned.error_code == "civilization_capability_not_effective"
    assert store.read_stream(GOVERNMENT_STREAM) == []


def test_inf4y_capability_gated_inspection_source_event_forgery_is_zero_write() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(
        store,
        capability_input=_activate(store).model_copy(update={"source_event_refs": ("event:forged",)}),
    )

    assert planned.accepted is False
    assert planned.error_code == "capability_source_event_mismatch"
    assert store.read_stream(GOVERNMENT_STREAM) == []


def test_inf4y_capability_gated_inspection_revoked_source_is_zero_write() -> None:
    store = GameplayEventStore()
    capability_input = _activate(store)
    revoked = CivilizationCapabilityAuthority(store=store).revoke(
        envelope=_capability_envelope(command_id="command:inf4y:inspection-revoke", expected_revision=1),
        capability_ref="capability:bakery-permit",
        jurisdiction_ref="jurisdiction:bakery",
    )
    planned = _plan_inspection(store, capability_input=capability_input)

    assert revoked.committed is True
    assert planned.accepted is False
    assert planned.error_code == "capability_source_revision_stale"
    assert store.read_stream(GOVERNMENT_STREAM) == []


def test_inf4y_capability_gated_inspection_forged_input_is_zero_write() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(
        store,
        capability_input=_activate(store).model_copy(update={"projection_digest": "sha256:forged"}),
    )

    assert planned.accepted is False
    assert planned.error_code == "capability_projection_digest_mismatch"
    assert store.read_stream(GOVERNMENT_STREAM) == []


def test_inf4y_capability_gated_inspection_non_authority_scope_is_zero_write() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(
        store,
        capability_input=_activate(store).model_copy(update={"reader_scope": "actor"}),
    )

    assert planned.accepted is False
    assert planned.error_code == "capability_reader_scope_denied"
    assert store.read_stream(GOVERNMENT_STREAM) == []


def test_inf4y_capability_gated_inspection_unpinned_policy_is_zero_write() -> None:
    store = GameplayEventStore()
    result = PopulationPlanner().plan_capability_gated_inspection(
        store=store,
        batch_ref="batch:inf4y:inspection-untracked-policy",
        world_ref="world:bakery",
        mode=_mode(),
        capability_input=_activate(store),
        candidate=_inspection_candidate(),
        base_event_digest="sha256:inf4y:inspection-base",
        tail_boundary=0,
        active_revision_refs=("mode:inf4y:1",),
        deterministic_seed="seed:inf4y:inspection",
        report_scope="actor:self",
    )

    assert result.accepted is False
    assert result.error_code == "capability_policy_not_pinned"
    assert store.read_stream(GOVERNMENT_STREAM) == []


def test_inf4y_capability_gated_inspection_merge_privacy_denial_is_zero_write() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(store, capability_input=_activate(store))
    assert planned.plan is not None

    receipt = _merge_inspection(
        store,
        planned.plan.model_copy(update={"report_scope": "creator:private"}),
    )

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "privacy_denial"
    assert store.read_stream(GOVERNMENT_STREAM) == []


def test_inf4y_capability_gated_inspection_government_revision_conflict_is_zero_write() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(store, capability_input=_activate(store))
    assert planned.plan is not None
    store.append_batch(
        build_atomic_event_batch(
            command_id="command:inf4y:government-change",
            principal_ref="actor_gameplay.government_domain",
            stream_id=GOVERNMENT_STREAM,
            expected_revision=0,
            event_specs=[("gameplay.government.test_revision_advanced", {})],
            idempotency_key="inf4y:government-change",
            causation_id="cause:inf4y:government-change",
            correlation_id="corr:inf4y:government-change",
        )
    )
    receipt = _merge_inspection(store, planned.plan)

    assert receipt.committed is False
    assert receipt.zero_write is True
    assert receipt.stop_reason == "source_revision_stale"
    assert len(store.read_stream(GOVERNMENT_STREAM)) == 1


def test_inf4y_capability_gated_inspection_is_idempotent_and_changed_duplicate_is_zero_write() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(store, capability_input=_activate(store))
    assert planned.plan is not None

    first = _merge_inspection(store, planned.plan)
    duplicate = _merge_inspection(store, planned.plan)
    changed = _merge_inspection(
        store,
        planned.plan.model_copy(update={"capability_eligibility_digest": "sha256:changed"}),
    )

    assert first.committed is True
    assert duplicate.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert changed.committed is False
    assert changed.zero_write is True
    assert changed.stop_reason == "idempotency_key_reused"
    assert len(store.read_stream(GOVERNMENT_STREAM)) == 1


def test_inf4y_capability_gated_inspection_replays_full_checkpoint_tail() -> None:
    store = GameplayEventStore()
    planned = _plan_inspection(store, capability_input=_activate(store))
    assert planned.plan is not None
    receipt = _merge_inspection(store, planned.plan)
    replay = GameplayProjectionReplay(projector_id="population-continuity", projector_version="1")
    events = store.read_events()
    checkpoint = replay.create_checkpoint(events[:1])

    assert receipt.committed is True
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(checkpoint, events[1:]).projection_hash
