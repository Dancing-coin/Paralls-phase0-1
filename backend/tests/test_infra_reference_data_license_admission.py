from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.reference_data_runtime import ReferenceDataAuthority, ReferenceDatasetRecord
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.population_continuity.branch_preview import (
    BranchPreviewAuthority,
    BranchPreviewRequest,
    CalibrationInput,
    FrozenReferenceDatasetInput,
)
from app.population_continuity.models import WorldModeProfile


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _envelope(*, command_id: str, expected_revision: int = 0) -> GameplayCommandEnvelope:
    stream_id = ReferenceDataAuthority.dataset_stream_id(dataset_ref="dataset:prices:1")
    return GameplayCommandEnvelope(
        command_id=command_id,
        command_type="reference_data.register",
        command_version=1,
        principal_ref="authority:reference_data",
        idempotency_key=command_id,
        expected_revisions={stream_id: expected_revision},
        causation_id=f"cause:{command_id}",
        correlation_id=f"corr:{command_id}",
        source_ref="authority:reference_data",
        submitted_at="2026-08-13T00:00:00Z",
    )


def _record() -> ReferenceDatasetRecord:
    return ReferenceDatasetRecord(
        dataset_ref="dataset:prices:1",
        provenance="fixture",
        license_ref="license:permitted",
        schema_revision="1",
        digest="sha256:dataset",
        classification="creator_debug",
        allowed_scopes=("creator_debug",),
        license_status="permitted",
    )


def _request() -> BranchPreviewRequest:
    return BranchPreviewRequest(
        branch_ref="branch:licensed",
        world_ref="world:bakery",
        base_event_digest="sha256:empty",
        deterministic_seed="seed:licensed",
        active_revision_refs=("mode:licensed",),
        calibration_ref="calibration:licensed",
        privacy_scope="creator_debug",
    )


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="preview",
        revision="mode:licensed",
        cadence_class="fixed-base",
        batch_limit=1,
        wake_budget=1,
        catch_up_limit=1,
        allowed_intent_kinds=("supply",),
        degraded_threshold=1,
    )


def test_inf4z_authoritative_reference_dataset_admits_branch_without_production_write() -> None:
    store = GameplayEventStore()
    owner = ReferenceDataAuthority(store=store)
    registered = owner.register(envelope=_envelope(command_id="reference:register"), record=_record())
    assert registered.committed is True
    view = owner.view_for(dataset_ref="dataset:prices:1", reader_scope="authority", expected_dataset_revision=1)
    assert view.accepted and view.view is not None
    frozen = FrozenReferenceDatasetInput.freeze(view=view.view)
    result = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR)).preview_authorized(
        request=_request(),
        dataset_input=frozen,
        calibration=CalibrationInput(calibration_ref="calibration:licensed", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"),
        family_inputs=(),
        candidates=(),
        mode=_mode(),
    )
    assert result.accepted is True
    assert len(store.read_events()) == 1


def test_inf4z_reference_dataset_revocation_rejects_branch_without_production_write() -> None:
    store = GameplayEventStore()
    owner = ReferenceDataAuthority(store=store)
    owner.register(envelope=_envelope(command_id="reference:register"), record=_record())
    authority_view = owner.view_for(dataset_ref="dataset:prices:1", reader_scope="authority")
    assert authority_view.view is not None
    frozen = FrozenReferenceDatasetInput.freeze(view=authority_view.view)
    owner.revoke(envelope=_envelope(command_id="reference:revoke", expected_revision=1), dataset_ref="dataset:prices:1")
    view = owner.view_for(dataset_ref="dataset:prices:1", reader_scope="authority")
    rejected_preview = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR)).preview_authorized(
        request=_request(), dataset_input=frozen,
        calibration=CalibrationInput(calibration_ref="calibration:licensed", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"),
        family_inputs=(), candidates=(), mode=_mode(),
    )

    assert view.accepted is False
    assert view.error_code == "reference_dataset_revoked"
    assert rejected_preview.accepted is False
    assert rejected_preview.error_code == "reference_dataset_revoked"
    assert len(store.read_events()) == 2
    assert len(store.list_outbox()) == 2


def test_inf4z_forged_reference_dataset_digest_rejects_branch_without_write() -> None:
    store = GameplayEventStore()
    owner = ReferenceDataAuthority(store=store)
    owner.register(envelope=_envelope(command_id="reference:register"), record=_record())
    view = owner.view_for(dataset_ref="dataset:prices:1", reader_scope="authority", expected_dataset_revision=1)
    assert view.view is not None
    frozen = FrozenReferenceDatasetInput.freeze(view=view.view).model_copy(update={"projection_digest": "sha256:forged"})
    result = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR)).preview_authorized(
        request=_request(), dataset_input=frozen,
        calibration=CalibrationInput(calibration_ref="calibration:licensed", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"),
        family_inputs=(), candidates=(), mode=_mode(),
    )

    assert result.accepted is False
    assert result.error_code == "reference_dataset_projection_digest_mismatch"
    assert len(store.read_events()) == 1
    assert len(store.list_outbox()) == 1


def test_inf4z_reference_dataset_full_and_checkpoint_tail_replay_match() -> None:
    store = GameplayEventStore()
    owner = ReferenceDataAuthority(store=store)
    owner.register(envelope=_envelope(command_id="reference:register"), record=_record())
    owner.correct(envelope=_envelope(command_id="reference:correct", expected_revision=1), record=_record().model_copy(update={"digest": "sha256:dataset:corrected"}))

    assert owner.replay().projection_hash == owner.replay(checkpoint_at=1).projection_hash


def test_inf4z_reference_dataset_register_appends_authority_outbox() -> None:
    store = GameplayEventStore()
    registered = ReferenceDataAuthority(store=store).register(envelope=_envelope(command_id="reference:register"), record=_record())

    assert registered.committed is True
    assert registered.resulting_stream_revisions == {ReferenceDataAuthority.dataset_stream_id(dataset_ref="dataset:prices:1"): 1}
    assert [event.event_type for event in store.read_events()] == ["gameplay.reference_data.dataset_registered"]
    assert [entry.topic for entry in store.list_outbox()] == ["world.reference_data.scoped_projection"]
    assert store.list_outbox()[0].audience == "authority_only"
    assert "license_ref" not in store.list_outbox()[0].payload_projection


def test_inf4z_reference_dataset_correction_advances_view_revision_and_outbox() -> None:
    store = GameplayEventStore()
    owner = ReferenceDataAuthority(store=store)
    owner.register(envelope=_envelope(command_id="reference:register"), record=_record())
    corrected = owner.correct(envelope=_envelope(command_id="reference:correct", expected_revision=1), record=_record().model_copy(update={"digest": "sha256:dataset:corrected"}))
    view = owner.view_for(dataset_ref="dataset:prices:1", reader_scope="authority", expected_dataset_revision=2)

    assert corrected.committed is True
    assert corrected.resulting_stream_revisions == {ReferenceDataAuthority.dataset_stream_id(dataset_ref="dataset:prices:1"): 2}
    assert view.accepted and view.view is not None
    assert view.view.digest == "sha256:dataset:corrected"
    assert view.view.source_revision_vector == {ReferenceDataAuthority.dataset_stream_id(dataset_ref="dataset:prices:1"): 2}
    assert [entry.payload_projection["event_type"] for entry in store.list_outbox()] == ["gameplay.reference_data.dataset_registered", "gameplay.reference_data.dataset_corrected"]


def test_inf4z_reference_data_owner_mismatch_is_zero_write() -> None:
    store = GameplayEventStore()
    rejected = ReferenceDataAuthority(store=store).register(
        envelope=_envelope(command_id="reference:wrong-owner").model_copy(update={"principal_ref": "creator:tool"}),
        record=_record(),
    )

    assert rejected.committed is False
    assert rejected.failure is not None
    assert rejected.failure.error_code == "reference_data_authority_required"
    assert store.read_events() == []
    assert store.list_outbox() == []


def test_inf4z_reference_data_revision_conflict_is_zero_write() -> None:
    store = GameplayEventStore()
    rejected = ReferenceDataAuthority(store=store).register(
        envelope=_envelope(command_id="reference:stale", expected_revision=1), record=_record()
    )

    assert rejected.committed is False
    assert rejected.failure is not None
    assert rejected.failure.error_code == "revision_conflict"
    assert store.read_events() == []
    assert store.list_outbox() == []


def test_inf4z_reference_data_duplicate_and_changed_duplicate_are_distinct() -> None:
    store = GameplayEventStore()
    owner = ReferenceDataAuthority(store=store)
    envelope = _envelope(command_id="reference:duplicate")
    first = owner.register(envelope=envelope, record=_record())
    duplicate = owner.register(envelope=envelope, record=_record())
    changed = owner.register(envelope=envelope, record=_record().model_copy(update={"digest": "sha256:changed"}))

    assert first.committed is True
    assert duplicate.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert changed.committed is False
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 1
    assert len(store.list_outbox()) == 1


def test_inf4z_reference_dataset_view_scope_and_preview_scope_are_zero_write() -> None:
    store = GameplayEventStore()
    owner = ReferenceDataAuthority(store=store)
    owner.register(envelope=_envelope(command_id="reference:register"), record=_record())
    denied_view = owner.view_for(dataset_ref="dataset:prices:1", reader_scope="creator")
    authority_view = owner.view_for(dataset_ref="dataset:prices:1", reader_scope="authority")
    assert authority_view.view is not None
    frozen = FrozenReferenceDatasetInput.freeze(view=authority_view.view)
    denied_preview = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR)).preview_authorized(
        request=_request().model_copy(update={"privacy_scope": "public"}),
        dataset_input=frozen,
        calibration=CalibrationInput(calibration_ref="calibration:licensed", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"),
        family_inputs=(), candidates=(), mode=_mode(),
    )

    assert denied_view.accepted is False
    assert denied_view.error_code == "reference_dataset_scope_denied"
    assert denied_preview.accepted is False
    assert denied_preview.error_code == "dataset_scope_denied"
    assert len(store.read_events()) == 1
    assert len(store.list_outbox()) == 1
