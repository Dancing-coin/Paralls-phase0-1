from __future__ import annotations

from pydantic import ValidationError

from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.semantic_authority import (
    SemanticEcologyDroughtCommand,
    SemanticSettlementAuthority,
)
from app.gameplay.semantic_registry import SemanticRegistry
from app.gameplay.shared_contracts import SemanticSnapshot
from test_infra_ecology_drought_state_obligation import (
    REGION_REF,
    STREAM,
    _replace_event,
    _seed_process,
)


def _command(
    store,
    *,
    source_event_id: str,
    source_event_revision: int,
    key: str = "semantic:drought:apply",
    revision: int | None = None,
    due_tick: int = 6,
    digest: str = "sha256:drought",
):
    snapshot = SemanticSnapshot(
        entity_ref=REGION_REF,
        policy_context_ref="policy:ecology",
        digest=digest,
        source_revision_vector={"semantic": 1},
    )
    return SemanticEcologyDroughtCommand(
        command_id=key,
        idempotency_key=key,
        principal_ref="authority:semantic",
        region_ref=REGION_REF,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
        expected_revision=store.get_stream_head(STREAM) if revision is None else revision,
        due_tick=due_tick,
        resistance_revision=1,
        semantic_snapshot=snapshot,
        expected_snapshot_digest=digest,
    )


def test_semantic_ecology_drought_command_forbids_free_owner_stream_and_payload_fields() -> None:
    snapshot = SemanticSnapshot(
        entity_ref=REGION_REF,
        policy_context_ref="policy:ecology",
        digest="sha256:snapshot",
        source_revision_vector={"semantic": 1},
    )
    command = SemanticEcologyDroughtCommand(
        command_id="semantic:drought:1",
        idempotency_key="semantic:drought:1",
        principal_ref="authority:semantic",
        region_ref=REGION_REF,
        source_event_id="event:drought",
        source_event_revision=9,
        expected_revision=9,
        due_tick=6,
        resistance_revision=1,
        semantic_snapshot=snapshot,
        expected_snapshot_digest=snapshot.digest,
    )

    assert command.effect_ref == "effect:drought"
    assert command.state_ref == "state:drought@1"
    try:
        SemanticEcologyDroughtCommand(**{**command.model_dump(), "stream_id": "gameplay:ecology:forged"})
    except ValidationError:
        pass
    else:
        raise AssertionError("free_stream_field_accepted")


def test_semantic_ecology_drought_maps_only_to_existing_ecology_owner_append() -> None:
    store, _authority, source_event_id, source_event_revision = _seed_process()

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_drought(
        _command(store, source_event_id=source_event_id, source_event_revision=source_event_revision)
    )

    assert result.committed is True
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.drought_state_applied",
        "gameplay.ecology.drought_state_obligation_opened",
    ]


def test_semantic_ecology_drought_rejects_stale_revision_without_write() -> None:
    store, _authority, source_event_id, source_event_revision = _seed_process()
    semantic = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())

    stale = semantic.settle_closed_ecology_drought(
        _command(
            store,
            source_event_id=source_event_id,
            source_event_revision=source_event_revision,
            key="semantic:drought:stale",
            revision=before - 1,
        )
    )

    assert not stale.committed
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_semantic_ecology_drought_rejects_snapshot_mismatch_without_write() -> None:
    store, _authority, source_event_id, source_event_revision = _seed_process()
    semantic = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())

    mismatch = semantic.settle_closed_ecology_drought(
        _command(
            store,
            source_event_id=source_event_id,
            source_event_revision=source_event_revision,
            key="semantic:drought:mismatch",
        ).model_copy(update={"expected_snapshot_digest": "sha256:wrong"})
    )

    assert not mismatch.committed
    assert mismatch.failure is not None and mismatch.failure.error_code == "semantic_ecology_snapshot_mismatch"
    assert len(store.read_events()) == before


def test_semantic_ecology_drought_replays_exact_duplicate_without_second_write() -> None:
    store, _authority, source_event_id, source_event_revision = _seed_process()
    semantic = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())
    command = _command(
        store,
        source_event_id=source_event_id,
        source_event_revision=source_event_revision,
        key="semantic:drought:duplicate",
    )

    first = semantic.settle_closed_ecology_drought(command)
    duplicate = semantic.settle_closed_ecology_drought(command)

    assert first.committed
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == before + 2


def test_semantic_ecology_drought_rejects_changed_duplicate_without_write() -> None:
    store, _authority, source_event_id, source_event_revision = _seed_process()
    semantic = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())
    assert semantic.settle_closed_ecology_drought(
        _command(
            store,
            source_event_id=source_event_id,
            source_event_revision=source_event_revision,
            key="semantic:drought:changed",
        )
    ).committed

    changed = semantic.settle_closed_ecology_drought(
        _command(
            store,
            source_event_id=source_event_id,
            source_event_revision=source_event_revision,
            key="semantic:drought:changed",
            due_tick=7,
        )
    )

    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before + 2


def test_semantic_ecology_drought_rejects_private_source_without_write() -> None:
    store, _authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())
    _replace_event(store, source_event_id, visibility_policy="authority_only")

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_drought(
        _command(
            store,
            source_event_id=source_event_id,
            source_event_revision=source_event_revision,
            key="semantic:drought:private-source",
        )
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "ecology_drought_state_source_privacy_denied"
    assert len(store.read_events()) == before


def test_semantic_ecology_drought_requires_closed_adapter_matrix_row_without_write(monkeypatch) -> None:
    store, _authority, source_event_id, source_event_revision = _seed_process()
    before = len(store.read_events())
    monkeypatch.setattr(
        SemanticRegistry,
        "closed_state_lifecycle_adapter_contracts",
        staticmethod(lambda: ()),
    )

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_drought(
        _command(
            store,
            source_event_id=source_event_id,
            source_event_revision=source_event_revision,
            key="semantic:drought:adapter-missing",
        )
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "semantic_ecology_drought_adapter_unregistered"
    assert len(store.read_events()) == before


def test_semantic_ecology_drought_reuses_ecology_checkpoint_tail_replay() -> None:
    store, _authority, source_event_id, source_event_revision = _seed_process()
    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_drought(
        _command(
            store,
            source_event_id=source_event_id,
            source_event_revision=source_event_revision,
            key="semantic:drought:replay",
        )
    )

    assert result.committed
    owner = EcologyHazardAuthority(store=store)
    assert owner.drought_state_replay().projection_hash == owner.drought_state_replay(checkpoint_at=9).projection_hash
