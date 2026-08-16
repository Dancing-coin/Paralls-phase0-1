from __future__ import annotations

from pydantic import ValidationError

from app.gameplay.semantic_authority import SemanticEcologyFrostCommand
from app.gameplay.shared_contracts import SemanticSnapshot
from app.gameplay.semantic_authority import SemanticSettlementAuthority
from app.gameplay.semantic_registry import SemanticRegistry
from app.gameplay.ecology_runtime import EcologyHazardAuthority
from test_infra_ecology_frost_state_obligation import CROP_REF, HAZARD_REF, REGION_REF, STREAM, _seed, _seed_with_hazard_privacy


def _command(store, *, key: str = "semantic:frost:apply", revision: int | None = None, magnitude: int = 50, digest: str = "sha256:frost"):
    snapshot = SemanticSnapshot(entity_ref=CROP_REF, policy_context_ref="policy:ecology", digest=digest, source_revision_vector={"semantic": 1})
    return SemanticEcologyFrostCommand(command_id=key, idempotency_key=key, principal_ref="authority:semantic", hazard_ref=HAZARD_REF, crop_ref=CROP_REF, region_ref=REGION_REF, expected_revision=store.get_stream_head(STREAM) if revision is None else revision, magnitude=magnitude, due_tick=4, resistance_revision=1, semantic_snapshot=snapshot, expected_snapshot_digest=digest)


def test_semantic_ecology_frost_command_forbids_free_owner_stream_and_payload_fields() -> None:
    snapshot = SemanticSnapshot(entity_ref="crop:valley:wheat", policy_context_ref="policy:ecology", digest="sha256:snapshot", source_revision_vector={"semantic": 1})
    command = SemanticEcologyFrostCommand(
        command_id="semantic:frost:1", idempotency_key="semantic:frost:1",
        principal_ref="authority:semantic", hazard_ref="hazard:valley:frost",
        crop_ref="crop:valley:wheat", region_ref="region:valley", expected_revision=5,
        magnitude=50, due_tick=4, resistance_revision=1,
        semantic_snapshot=snapshot, expected_snapshot_digest="sha256:snapshot",
    )

    assert command.effect_ref == "effect:frost"
    assert command.state_ref == "state:frosted@1"
    try:
        SemanticEcologyFrostCommand(**{**command.model_dump(), "stream_id": "gameplay:ecology:forged"})
    except ValidationError:
        pass
    else:
        raise AssertionError("free_stream_field_accepted")


def test_semantic_ecology_frost_maps_only_to_existing_ecology_owner_append() -> None:
    store, _authority = _seed()
    snapshot = SemanticSnapshot(entity_ref=CROP_REF, policy_context_ref="policy:ecology", digest="sha256:frost", source_revision_vector={"semantic": 1})
    command = SemanticEcologyFrostCommand(
        command_id="semantic:frost:apply", idempotency_key="semantic:frost:apply",
        principal_ref="authority:semantic", hazard_ref=HAZARD_REF, crop_ref=CROP_REF,
        region_ref=REGION_REF, expected_revision=store.get_stream_head(STREAM), magnitude=50,
        due_tick=4, resistance_revision=1, semantic_snapshot=snapshot,
        expected_snapshot_digest=snapshot.digest,
    )

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_frost(command)

    assert result.committed is True
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.ecology.crop_state_applied", "gameplay.ecology.crop_state_obligation_opened"
    ]


def test_semantic_ecology_frost_rejects_stale_revision_without_write() -> None:
    store, _authority = _seed()
    semantic = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())
    stale = semantic.settle_closed_ecology_frost(_command(store, revision=before - 1, key="semantic:frost:stale"))

    assert not stale.committed and stale.failure and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_semantic_ecology_frost_rejects_snapshot_mismatch_without_write() -> None:
    store, _authority = _seed()
    semantic = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())
    mismatch = semantic.settle_closed_ecology_frost(
        _command(store, key="semantic:frost:mismatch").model_copy(
            update={"expected_snapshot_digest": "sha256:wrong"}
        )
    )

    assert not mismatch.committed and mismatch.failure and mismatch.failure.error_code == "semantic_ecology_snapshot_mismatch"
    assert len(store.read_events()) == before


def test_semantic_ecology_frost_replays_exact_duplicate_without_second_write() -> None:
    store, _authority = _seed()
    semantic = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())
    command = _command(store, key="semantic:frost:duplicate")
    first = semantic.settle_closed_ecology_frost(command)
    duplicate = semantic.settle_closed_ecology_frost(command)

    assert first.committed
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == before + 2


def test_semantic_ecology_frost_rejects_changed_duplicate_without_write() -> None:
    store, _authority = _seed()
    semantic = SemanticSettlementAuthority(store=store, registry=SemanticRegistry())
    before = len(store.read_events())
    first = semantic.settle_closed_ecology_frost(_command(store, key="semantic:frost:changed-duplicate"))
    duplicate = semantic.settle_closed_ecology_frost(
        _command(store, key="semantic:frost:changed-duplicate", magnitude=55)
    )

    assert first.committed
    assert not duplicate.committed and duplicate.failure and duplicate.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before + 2


def test_semantic_ecology_frost_rejects_authority_only_hazard_without_write() -> None:
    store, _authority = _seed_with_hazard_privacy(privacy_scope="authority_only")
    before = len(store.read_events())

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_frost(_command(store, key="semantic:frost:private-source"))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "ecology_crop_state_source_privacy_denied"
    assert len(store.read_events()) == before


def test_semantic_ecology_frost_rejects_forged_region_relation_without_write() -> None:
    store, _authority = _seed()
    before = len(store.read_events())
    forged = _command(store, key="semantic:frost:forged-region").model_copy(
        update={"region_ref": "region:forged"}
    )

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_frost(forged)

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_semantic_ecology_frost_requires_closed_adapter_matrix_row_without_write(monkeypatch) -> None:
    store, _authority = _seed()
    before = len(store.read_events())
    monkeypatch.setattr(
        SemanticRegistry,
        "closed_state_lifecycle_adapter_contracts",
        staticmethod(lambda: ()),
    )

    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_frost(
        _command(store, key="semantic:frost:adapter-missing")
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "semantic_ecology_adapter_unregistered"
    assert len(store.read_events()) == before


def test_semantic_ecology_frost_reuses_ecology_checkpoint_tail_replay() -> None:
    store, _authority = _seed()
    result = SemanticSettlementAuthority(store=store, registry=SemanticRegistry()).settle_closed_ecology_frost(_command(store, key="semantic:frost:replay"))

    assert result.committed
    owner = EcologyHazardAuthority(store=store)
    assert owner.crop_state_replay().projection_hash == owner.crop_state_replay(checkpoint_at=5).projection_hash
