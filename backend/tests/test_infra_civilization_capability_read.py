from __future__ import annotations

from app.gameplay.civilization_capability_runtime import (
    CivilizationCapabilityAuthority,
    CivilizationCapabilityRecord,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _record(*, policy_revision: str = "policy:1", effective_tick: int = 5, visibility: str = "project") -> CivilizationCapabilityRecord:
    return CivilizationCapabilityRecord(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        policy_revision=policy_revision,
        effective_tick=effective_tick,
        visibility=visibility,
    )


def _envelope(
    *,
    command_id: str = "command:capability:activate",
    idempotency_key: str = "capability:irrigation:activate",
    expected_revision: int = 0,
    principal_ref: str = "authority:civilization_capability",
    source_ref: str = "authority:civilization_capability",
) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=command_id,
        command_type="gameplay.civilization_capability.activate",
        command_version=1,
        principal_ref=principal_ref,
        idempotency_key=idempotency_key,
        expected_revisions={"gameplay:civilization_capability:jurisdiction:valley": expected_revision},
        causation_id=f"cause:{command_id}",
        correlation_id=f"corr:{command_id}",
        source_ref=source_ref,
        submitted_at="2026-08-13T00:00:00Z",
    )


def test_civilization_capability_activation_uses_one_canonical_stream_and_outbox() -> None:
    store = GameplayEventStore()
    authority = CivilizationCapabilityAuthority(store=store)

    result = authority.activate(envelope=_envelope(), record=_record())

    assert result.committed is True
    assert [event.event_type for event in store.read_events()] == ["gameplay.civilization_capability.activated"]
    assert {event.stream_id for event in store.read_events()} == {"gameplay:civilization_capability:jurisdiction:valley"}
    assert len(store.list_outbox()) == 1


def test_civilization_capability_rejects_wrong_authority_without_writes() -> None:
    store = GameplayEventStore()
    authority = CivilizationCapabilityAuthority(store=store)

    result = authority.activate(
        envelope=_envelope(principal_ref="client:creator", source_ref="client:creator"),
        record=_record(),
    )

    assert result.failure is not None and result.failure.error_code == "civilization_capability_authority_required"
    assert store.read_events() == []


def test_civilization_capability_duplicate_is_idempotent_but_changed_duplicate_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = CivilizationCapabilityAuthority(store=store)
    first = authority.activate(envelope=_envelope(), record=_record())
    duplicate = authority.activate(envelope=_envelope(), record=_record())
    changed = authority.activate(envelope=_envelope(), record=_record(policy_revision="policy:2"))

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 1


def test_civilization_capability_rejects_revision_conflict_without_writes() -> None:
    store = GameplayEventStore()
    authority = CivilizationCapabilityAuthority(store=store)

    result = authority.activate(envelope=_envelope(expected_revision=1), record=_record())

    assert result.failure is not None and result.failure.error_code == "revision_conflict"
    assert store.read_events() == []


def test_civilization_capability_view_enforces_jurisdiction_effective_tick_and_privacy_scope() -> None:
    store = GameplayEventStore()
    authority = CivilizationCapabilityAuthority(store=store)
    authority.activate(envelope=_envelope(), record=_record(visibility="authority_only"))

    authority_view = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="authority",
        now_tick=5,
    )
    wrong_jurisdiction = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:other",
        reader_scope="authority",
        now_tick=5,
    )
    early = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="authority",
        now_tick=4,
    )
    public = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="public",
        now_tick=5,
    )

    assert authority_view.accepted is True and authority_view.view is not None
    assert authority_view.view.source_event_refs == (
        "event:command:capability:activate:gameplay:civilization_capability:jurisdiction:valley:1",
    )
    assert wrong_jurisdiction.error_code == "civilization_capability_jurisdiction_mismatch"
    assert early.error_code == "civilization_capability_not_effective"
    assert public.error_code == "civilization_capability_scope_denied"


def test_civilization_capability_scope_filtering_is_independent_for_actor_creator_and_public() -> None:
    store = GameplayEventStore()
    authority = CivilizationCapabilityAuthority(store=store)
    authority.activate(envelope=_envelope(), record=_record(visibility="actor_only"))

    actor = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="actor",
        now_tick=5,
    )
    creator = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="creator",
        now_tick=5,
    )
    public = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="public",
        now_tick=5,
    )

    assert actor.accepted is True
    assert creator.error_code == "civilization_capability_scope_denied"
    assert public.error_code == "civilization_capability_scope_denied"


def test_civilization_capability_creator_scope_is_not_an_actor_or_public_view() -> None:
    store = GameplayEventStore()
    authority = CivilizationCapabilityAuthority(store=store)
    authority.activate(envelope=_envelope(), record=_record(visibility="creator_only"))

    creator = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="creator",
        now_tick=5,
    )
    actor = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="actor",
        now_tick=5,
    )

    assert creator.accepted is True
    assert actor.error_code == "civilization_capability_scope_denied"


def test_civilization_capability_read_rejects_stale_source_revision_without_writes() -> None:
    store = GameplayEventStore()
    authority = CivilizationCapabilityAuthority(store=store)
    authority.activate(envelope=_envelope(), record=_record())

    stale = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="authority",
        now_tick=5,
        expected_capability_revision=2,
    )

    assert stale.error_code == "civilization_capability_revision_conflict"
    assert len(store.read_events()) == 1


def test_civilization_capability_revoke_and_correction_are_event_derived_and_replay_equivalent() -> None:
    store = GameplayEventStore()
    authority = CivilizationCapabilityAuthority(store=store)
    authority.activate(envelope=_envelope(), record=_record())
    correction = authority.correct(
        envelope=_envelope(
            command_id="command:capability:correct",
            idempotency_key="capability:irrigation:correct",
            expected_revision=1,
        ),
        record=_record(policy_revision="policy:2"),
    )
    corrected_view = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="authority",
        now_tick=10,
    )
    revocation = authority.revoke(
        envelope=_envelope(
            command_id="command:capability:revoke",
            idempotency_key="capability:irrigation:revoke",
            expected_revision=2,
        ),
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
    )
    view = authority.view_for(
        capability_ref="capability:irrigation",
        jurisdiction_ref="jurisdiction:valley",
        reader_scope="authority",
        now_tick=10,
    )

    assert correction.committed is True
    assert corrected_view.accepted is True and corrected_view.view is not None
    assert corrected_view.view.capability_revision == 2
    assert corrected_view.view.policy_revision == "policy:2"
    assert len(corrected_view.view.source_event_refs) == 2
    assert revocation.committed is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.civilization_capability.activated",
        "gameplay.civilization_capability.corrected",
        "gameplay.civilization_capability.revoked",
    ]
    assert view.accepted is False and view.error_code == "civilization_capability_revoked"
    assert authority.replay().projection_hash == authority.replay(checkpoint_at=1).projection_hash
