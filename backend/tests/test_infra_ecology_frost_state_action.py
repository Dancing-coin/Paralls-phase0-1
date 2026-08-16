from __future__ import annotations

from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.semantic_authority import (
    SemanticEcologyFrostStateActionCommand,
    SemanticSettlementAuthority,
)
from app.gameplay.semantic_registry import SemanticRegistry
from app.gameplay.shared_contracts import SemanticSnapshot
from test_infra_ecology_frost_state_obligation import (
    CROP_REF,
    HAZARD_REF,
    REGION_REF,
    STREAM,
    _apply,
    _seed,
)


def _command(store, *, key: str = "semantic:frost:dispel:1", revision: int | None = None, scope: str = "project"):
    snapshot = SemanticSnapshot(
        entity_ref=CROP_REF,
        policy_context_ref="policy:ecology",
        digest="sha256:frost-dispel",
        source_revision_vector={"semantic": 1},
    )
    return SemanticEcologyFrostStateActionCommand(
        command_id=key,
        idempotency_key=key,
        principal_ref="authority:semantic",
        hazard_ref=HAZARD_REF,
        crop_ref=CROP_REF,
        region_ref=REGION_REF,
        expected_revision=store.get_stream_head(STREAM) if revision is None else revision,
        semantic_snapshot=snapshot,
        expected_snapshot_digest=snapshot.digest,
        privacy_scope=scope,
    )


def _seed_active_state():
    store, ecology = _seed()
    assert _apply(ecology).committed
    return store


def test_semantic_ecology_frost_dispel_cancels_exact_open_obligation_in_one_owner_batch() -> None:
    store = _seed_active_state()

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_frost_state_action(
        _command(store)
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.crop_state_dispelled",
        "gameplay.ecology.crop_state_obligation_cancelled",
    ]
    assert {event.stream_id for event in store.read_events()[-2:]} == {STREAM}


def test_semantic_ecology_frost_dispel_duplicate_replays_without_second_append() -> None:
    store = _seed_active_state()
    authority = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    command = _command(store, key="semantic:frost:dispel:duplicate")

    first = authority.settle_closed_ecology_frost_state_action(command)
    duplicate = authority.settle_closed_ecology_frost_state_action(command)

    assert first.committed and duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 9


def test_semantic_ecology_frost_dispel_rejects_changed_duplicate_without_write() -> None:
    store = _seed_active_state()
    authority = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    assert authority.settle_closed_ecology_frost_state_action(
        _command(store, key="semantic:frost:dispel:changed")
    ).committed

    command = _command(store, key="semantic:frost:dispel:changed")
    changed = authority.settle_closed_ecology_frost_state_action(
        command.model_copy(
            update={
                "semantic_snapshot": command.semantic_snapshot.model_copy(
                    update={"source_revision_vector": {"semantic": 2}}
                )
            }
        )
    )

    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 9


def test_semantic_ecology_frost_dispel_rejects_inactive_source_without_write() -> None:
    store, _ecology = _seed()
    before = len(store.read_events())

    rejected = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_frost_state_action(
        _command(store, key="semantic:frost:dispel:inactive")
    )

    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "ecology_crop_state_action_source_not_open"
    assert len(store.read_events()) == before


def test_semantic_ecology_frost_dispel_rejects_stale_revision_without_write() -> None:
    store = _seed_active_state()
    authority = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())

    stale = authority.settle_closed_ecology_frost_state_action(
        _command(store, key="semantic:frost:dispel:stale", revision=before - 1)
    )

    assert not stale.committed and stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_semantic_ecology_frost_dispel_rejects_private_input_without_write() -> None:
    store = _seed_active_state()
    authority = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())

    private = authority.settle_closed_ecology_frost_state_action(
        _command(store, key="semantic:frost:dispel:private", scope="authority_only")
    )

    assert not private.committed and private.failure is not None and private.failure.error_code == "semantic_ecology_action_privacy_denied"
    assert len(store.read_events()) == before


def test_semantic_ecology_frost_dispel_rejects_missing_action_contract_without_write(monkeypatch) -> None:
    store = _seed_active_state()
    before = len(store.read_events())
    original = SemanticRegistry.require_closed_lifecycle_owner_contract

    def without_action(cls, *, effect_ref: str, state_ref: str | None = None):
        return original(effect_ref=effect_ref, state_ref=state_ref).model_copy(
            update={"action_effect_refs": ()}
        )

    monkeypatch.setattr(
        SemanticRegistry,
        "require_closed_lifecycle_owner_contract",
        classmethod(without_action),
    )
    rejected = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_frost_state_action(
        _command(store, key="semantic:frost:dispel:contract")
    )

    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "semantic_ecology_action_unregistered"
    assert len(store.read_events()) == before


def test_semantic_ecology_frost_dispel_replays_full_and_checkpoint_tail() -> None:
    store = _seed_active_state()
    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_frost_state_action(
        _command(store, key="semantic:frost:dispel:replay")
    )

    assert result.committed
    ecology = EcologyHazardAuthority(store=store)
    assert ecology.crop_state_replay().projection_hash == ecology.crop_state_replay(checkpoint_at=7).projection_hash
