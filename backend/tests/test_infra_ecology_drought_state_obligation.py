from __future__ import annotations

import pytest

from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.ecology_runtime import EcologyDroughtProcessPolicy
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry
from app.gameplay.shared_contracts import GameplayCommandEnvelope, ScheduledObligation
from app.gameplay.shared_contracts import SettlementReceipt
from app.world_runtime.obligations import (
    ObligationLifecycleProjection,
    ObligationLifecycleRegistration,
    ObligationSettlementCoordinator,
)
from app.world_runtime.simulation_clock import SimulationClock
from test_infra_ecology_process_lifecycle import _envelope, _record


REGION_REF = "region:process"
STREAM = EcologyHazardAuthority.ecology_stream_id(region_ref=REGION_REF)
POLICY_REF = "policy:ecology_drought_state_expiry@1"


def _apply_command(
    *,
    key: str = "ecology:drought-state:apply:1",
    expected_revision: int,
    scope: str = "project",
) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.ecology.apply_drought_state",
        command_version=1,
        principal_ref=EcologyHazardAuthority._PRINCIPAL,
        actor_ref=REGION_REF,
        project_ref="project:demo",
        idempotency_key=key,
        expected_revisions={STREAM: expected_revision},
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        source_ref=EcologyHazardAuthority._PRINCIPAL,
        submitted_at="2026-08-16T00:00:00Z",
        pinned_revisions={"ecology": expected_revision},
        payload={"visibility_scope": scope},
    )


def _application(*, effect_ref: str = "effect:drought", due_tick: int = 6) -> EffectApplication:
    return EffectApplication(
        effect_ref=effect_ref,
        target_component_ref=REGION_REF,
        magnitude=1,
        stack_key="ecology-state:drought",
        expires_at_tick=due_tick,
        causal_chain_id="event:drought",
    )


def _resistance(*, effect_ref: str = "effect:drought") -> ResistanceProfile:
    return ResistanceProfile(
        effect_ref=effect_ref,
        source_ref=REGION_REF,
        modifier_basis_points=0,
        revision=1,
    )


def _state(*, state_ref: str = "state:drought@1") -> StateDefinition:
    return StateDefinition(
        state_ref=state_ref,
        stack_policy="refresh",
        stack_limit=1,
        expiry_policy="scheduled",
    )


def _registration() -> ObligationLifecycleRegistration:
    return ObligationLifecycleRegistration(
        policy_ref=POLICY_REF,
        policy_revision="1",
        owner_ref=EcologyHazardAuthority._PRINCIPAL,
        stream_pattern="gameplay:ecology:{region_ref}",
        opened_event_type="gameplay.ecology.drought_state_obligation_opened",
        settled_event_type="gameplay.ecology.drought_state_obligation_settled",
        expired_event_type="gameplay.ecology.drought_state_expired",
        visibility_scope="project",
    )


def _replace_event(
    store: GameplayEventStore,
    event_id: str,
    *,
    event_type: str | None = None,
    stream_id: str | None = None,
    visibility_policy: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    current = store.get_event(event_id)
    updated = current.model_copy(
        update={
            "event_type": event_type or current.event_type,
            "stream_id": stream_id or current.stream_id,
            "visibility_policy": visibility_policy or current.visibility_policy,
            "payload": payload or current.payload,
        },
        deep=True,
    )
    for index, event in enumerate(store._events):  # type: ignore[attr-defined]
        if event.event_id == event_id:
            store._events[index] = updated  # type: ignore[attr-defined]
            break
    store._events_by_id[event_id] = updated  # type: ignore[attr-defined]


def _seed_process() -> tuple[GameplayEventStore, EcologyHazardAuthority, str, int]:
    store = GameplayEventStore()
    authority = _record(store)
    result = authority.advance_drought_process(
        envelope=_envelope(
            command_id="command:drought",
            key="ecology:drought:3",
            expected_revision=5,
            tick=3,
        ),
        policy=EcologyDroughtProcessPolicy(),
        region_ref=REGION_REF,
    )
    assert result.committed is True
    source = next(
        event
        for event in reversed(store.read_events())
        if event.event_type == "gameplay.ecology.drought_process_advanced"
    )
    return store, authority, source.event_id, source.stream_revision


def _apply(
    authority: EcologyHazardAuthority,
    *,
    key: str = "ecology:drought-state:apply:1",
    expected_revision: int,
    scope: str = "project",
    source_event_id: str,
    source_event_revision: int,
    effect_ref: str = "effect:drought",
    state_ref: str = "state:drought@1",
    due_tick: int = 6,
):
    apply = getattr(authority, "apply_drought_state", None)
    assert callable(apply), "EcologyHazardAuthority.apply_drought_state missing"
    return apply(
        command=_apply_command(key=key, expected_revision=expected_revision, scope=scope),
        region_ref=REGION_REF,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
        application=_application(effect_ref=effect_ref, due_tick=due_tick),
        resistance=_resistance(effect_ref=effect_ref),
        definition=_state(state_ref=state_ref),
    )


def _open_obligation(store: GameplayEventStore):
    lifecycle = ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events())
    assert len(lifecycle.open) == 1
    return next(iter(lifecycle.open.values()))


def _due_obligation(
    store: GameplayEventStore,
    *,
    status: str = "due",
) -> ScheduledObligation:
    view = ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events())
    obligation = next(
        item
        for item in view.to_scheduled_obligations()
        if item.obligation_id == _open_obligation(store).obligation_id
    )
    return obligation.model_copy(update={"status": status}, deep=True)


def _settle_due(
    store: GameplayEventStore,
    authority: EcologyHazardAuthority,
):
    due = SimulationClock(world_ref="world:demo", catch_up_budget=1).advance(
        _due_obligation(store).due_tick,
        (_due_obligation(store),),
    ).due[0]
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(_registration(),),
    )
    build = getattr(authority, "build_drought_state_fragment", None)
    assert callable(build), "EcologyHazardAuthority.build_drought_state_fragment missing"
    plan = coordinator.plan_settle(
        obligation=due,
        fragments=(
            build(
                obligation=due,
                region_ref=REGION_REF,
                expected_revision=store.get_stream_head(STREAM),
            ),
        ),
        principal_ref="world_runtime.caller",
    )
    assert plan.ready and plan.owner_commit_batch is not None
    return authority.commit_obligation_batch(plan.owner_commit_batch)


def test_ecology_drought_state_apply_commits_on_existing_ecology_stream() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()

    result = _apply(
        authority,
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )

    assert result.committed is True
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.drought_state_applied",
        "gameplay.ecology.drought_state_obligation_opened",
    ]
    assert _open_obligation(store).due_tick == 6


def test_ecology_drought_state_rejects_missing_source_without_write() -> None:
    store, authority, _source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())

    result = _apply(
        authority,
        key="ecology:drought-state:missing-source",
        expected_revision=store.get_stream_head(STREAM),
        source_event_id="event:missing",
        source_event_revision=source_event_revision,
    )

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_source_missing"
    assert len(store.read_events()) == before


def test_ecology_drought_state_duplicate_replays_without_second_append() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())
    head = store.get_stream_head(STREAM)

    first = _apply(
        authority,
        key="ecology:drought-state:duplicate",
        expected_revision=head,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )
    duplicate = _apply(
        authority,
        key="ecology:drought-state:duplicate",
        expected_revision=head,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == before + 2


def test_ecology_drought_state_changed_duplicate_is_zero_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())
    head = store.get_stream_head(STREAM)
    assert _apply(
        authority,
        key="ecology:drought-state:changed",
        expected_revision=head,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    ).committed is True

    changed = _apply(
        authority,
        key="ecology:drought-state:changed",
        expected_revision=head,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
        due_tick=7,
    )

    assert changed.committed is False
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before + 2


def test_ecology_drought_state_revision_conflict_is_zero_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())

    stale = _apply(
        authority,
        key="ecology:drought-state:stale",
        expected_revision=store.get_stream_head(STREAM) - 1,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )

    assert stale.committed is False
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_ecology_drought_state_nonproject_privacy_is_zero_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())

    private = _apply(
        authority,
        key="ecology:drought-state:private",
        expected_revision=store.get_stream_head(STREAM),
        scope="authority_only",
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )

    assert private.committed is False
    assert private.failure is not None and private.failure.error_code == "ecology_drought_state_privacy_scope_denied"
    assert len(store.read_events()) == before


def test_ecology_drought_state_rejects_catalog_owner_guard_without_write(monkeypatch) -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())
    original = SemanticRegistry.require_closed_state_owner_contract

    def forged(cls, *, effect_ref: str, state_ref: str):
        return original(effect_ref=effect_ref, state_ref=state_ref).model_copy(
            update={"stream_pattern": "gameplay:ecology:forged"}
        )

    monkeypatch.setattr(SemanticRegistry, "require_closed_state_owner_contract", classmethod(forged))
    result = _apply(
        authority,
        key="ecology:drought-state:forged-contract",
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_row_unregistered"
    assert len(store.read_events()) == before


def test_ecology_drought_state_rejects_wrong_effect_without_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())

    result = _apply(
        authority,
        key="ecology:drought-state:wrong-effect",
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
        effect_ref="effect:frost",
    )

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_row_unregistered"
    assert len(store.read_events()) == before


def test_ecology_drought_state_rejects_wrong_definition_without_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())
    apply = getattr(authority, "apply_drought_state", None)
    assert callable(apply), "EcologyHazardAuthority.apply_drought_state missing"

    result = apply(
        command=_apply_command(
            key="ecology:drought-state:wrong-definition",
            expected_revision=store.get_stream_head(STREAM),
        ),
        region_ref=REGION_REF,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
        application=_application(),
        resistance=_resistance(),
        definition=StateDefinition(
            state_ref="state:drought@1",
            stack_policy="refresh",
            stack_limit=2,
            expiry_policy="scheduled",
        ),
    )

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_row_unregistered"
    assert len(store.read_events()) == before


def test_ecology_drought_state_due_expiry_settles_through_existing_coordinator() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    assert _apply(
        authority,
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    ).committed is True

    result = _settle_due(store, authority)

    assert result.committed is True
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.drought_state_expired",
        "gameplay.ecology.drought_state_obligation_settled",
    ]


def test_ecology_drought_state_fragment_rejects_missing_opening_event_provenance_without_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    assert _apply(
        authority,
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    ).committed is True
    due = _due_obligation(store)
    missing_opening = due.model_copy(
        update={
            "source_refs": tuple(
                source_ref
                for source_ref in due.source_refs
                if not source_ref.startswith("opening_event:")
            )
        },
        deep=True,
    )
    before = store.export_snapshot()

    with pytest.raises(ValueError, match="ecology_drought_state_fragment_invalid"):
        authority.build_drought_state_fragment(
            obligation=missing_opening,
            region_ref=REGION_REF,
            expected_revision=store.get_stream_head(STREAM),
        )

    assert store.export_snapshot() == before


def test_ecology_drought_state_outbox_and_receipt_are_append_derived() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    head = store.get_stream_head(STREAM)
    applied = _apply(
        authority,
        key="ecology:drought-state:receipt",
        expected_revision=head,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )
    settled = _settle_due(store, authority)

    assert applied.committed_event_ids
    assert settled.committed_event_ids
    receipt = SettlementReceipt.from_append_result(
        result=settled,
        audit_refs=("plan:ecology:drought-state:settlement",),
        pinned_revisions={STREAM: store.get_stream_head(STREAM)},
    )
    assert receipt.idempotency_status == settled.idempotency_status
    assert receipt.committed_event_ids == tuple(settled.committed_event_ids)
    assert {entry.audience for entry in store.list_outbox()} == {"project"}
    assert {entry.topic for entry in store.list_outbox()} >= {
        "world.ecology.scoped_projection",
        "world.obligation.scoped_projection",
    }


def test_ecology_drought_state_full_replay_rebuilds_committed_history() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    head = store.get_stream_head(STREAM)
    assert _apply(
        authority,
        key="ecology:drought-state:replay",
        expected_revision=head,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    ).committed is True
    assert _settle_due(store, authority).committed is True

    replay = getattr(authority, "drought_state_replay", None)
    assert callable(replay), "EcologyHazardAuthority.drought_state_replay missing"
    result = replay()

    assert result.succeeded is True
    assert result.state[STREAM]["last_event_type"] == "gameplay.ecology.drought_state_obligation_settled"


def test_ecology_drought_state_checkpoint_tail_replay_matches_full_replay() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    head = store.get_stream_head(STREAM)
    assert _apply(
        authority,
        key="ecology:drought-state:checkpoint",
        expected_revision=head,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    ).committed is True
    assert _settle_due(store, authority).committed is True

    replay = getattr(authority, "drought_state_replay", None)
    assert callable(replay), "EcologyHazardAuthority.drought_state_replay missing"
    assert replay().projection_hash == replay(checkpoint_at=11).projection_hash


def test_ecology_drought_state_rejects_private_source_without_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())
    _replace_event(store, source_event_id, visibility_policy="authority_only")

    result = _apply(
        authority,
        key="ecology:drought-state:private-source",
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_source_privacy_denied"
    assert len(store.read_events()) == before


def test_ecology_drought_state_rejects_forged_source_without_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())
    source = store.get_event(source_event_id)
    forged_payload = {**source.payload, "region_ref": "region:forged"}
    _replace_event(store, source_event_id, payload=forged_payload)

    result = _apply(
        authority,
        key="ecology:drought-state:forged-source",
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_source_invalid"
    assert len(store.read_events()) == before


def test_ecology_drought_state_rejects_stale_source_revision_without_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())

    result = _apply(
        authority,
        key="ecology:drought-state:stale-source",
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision - 1,
    )

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_source_invalid"
    assert len(store.read_events()) == before


def test_ecology_drought_state_rejects_historical_source_after_newer_process_without_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    assert authority.advance_drought_process(
        envelope=_envelope(
            command_id="command:drought:newer",
            key="ecology:drought:newer",
            expected_revision=store.get_stream_head(STREAM),
            tick=4,
        ),
        policy=EcologyDroughtProcessPolicy(),
        region_ref=REGION_REF,
    ).committed is True
    before = len(store.read_events())

    result = _apply(
        authority,
        key="ecology:drought-state:historical-source",
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_source_stale"
    assert len(store.read_events()) == before


def test_ecology_drought_state_replays_exact_duplicate_after_newer_process_without_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    command_key = "ecology:drought-state:historical-duplicate"
    head = store.get_stream_head(STREAM)
    first = _apply(
        authority,
        key=command_key,
        expected_revision=head,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )
    assert first.committed is True
    assert authority.advance_drought_process(
        envelope=_envelope(
            command_id="command:drought:duplicate-newer",
            key="ecology:drought:duplicate-newer",
            expected_revision=store.get_stream_head(STREAM),
            tick=4,
        ),
        policy=EcologyDroughtProcessPolicy(),
        region_ref=REGION_REF,
    ).committed is True
    before = len(store.read_events())

    duplicate = _apply(
        authority,
        key=command_key,
        expected_revision=head,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    )

    assert duplicate.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == before


def test_ecology_drought_state_rejects_second_active_obligation_without_write() -> None:
    store, authority, source_event_id, source_event_revision = _seed_process()
    assert _apply(
        authority,
        key="ecology:drought-state:first",
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
    ).committed is True
    before = len(store.read_events())
    assert authority.advance_drought_process(
        envelope=_envelope(
            command_id="command:drought:6",
            key="ecology:drought:6",
            expected_revision=store.get_stream_head(STREAM),
            tick=6,
        ),
        policy=EcologyDroughtProcessPolicy(),
        region_ref=REGION_REF,
    ).committed is True
    second_source = next(
        event
        for event in reversed(store.read_events())
        if event.event_type == "gameplay.ecology.drought_process_advanced"
    )

    result = _apply(
        authority,
        key="ecology:drought-state:second-open",
        expected_revision=store.get_stream_head(STREAM),
        source_event_id=second_source.event_id,
        source_event_revision=second_source.stream_revision,
    )

    assert result.committed is False
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_already_open"
    assert len(store.read_events()) == before + 4
